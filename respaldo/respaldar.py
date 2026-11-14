"""Respalda la base de la nube (Turso) en Google Drive, igual que el botón
"Guardar base de datos en Google Drive" del programa del computador:

  Mi unidad/<carpeta>/backups_db/tienda_backup_AAAA-MM-DD_HH-MM-SS.db   uno por respaldo
  Mi unidad/<carpeta>/db_actual/tienda.db                               siempre el último

y deja solo los últimos 30 respaldos (los viejos van a la papelera de Drive).

Lo corre la tarea de GitHub .github/workflows/respaldo.yml: todas las noches,
y cuando se toca «Respaldar en Google Drive» en la pestaña Más de la página.

    python -m respaldo.respaldar           respalda
    python -m respaldo.respaldar --probar  solo copia la base y entra a Drive, sin subir nada

Variables de entorno (ver respaldo/LEEME.md):
  TURSO_URL, TURSO_TOKEN                 la base (escribe en ajustes cuándo fue el respaldo)
  GOOGLE_CLIENTE_ID, GOOGLE_CLIENTE_SECRETO, GOOGLE_REFRESH_TOKEN
  RESPALDO_CARPETA                       la carpeta en Mi unidad (Emprendimiento)
  RESPALDO_ORIGEN                        qué lo lanzó, para mostrarlo en la página
  TZ=America/Bogota                      para que la hora sea la de Colombia

El repositorio es público y lo que se imprime aquí se ve en GitHub: no se
imprime nada de los datos, ni siquiera cuántas filas tiene cada tabla.
"""
import argparse
import os
import sqlite3
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.nube import conexion_directa  # noqa: E402
from respaldo.drive import Drive, token_de_acceso  # noqa: E402
from utils import respaldo_drive  # noqa: E402

MAX_BACKUPS = 30
HOLGURA = 5         # como el computador: se limpia cuando pasan de 35, no en cada respaldo
INTENTOS_COPIA = 3


# ── La copia ─────────────────────────────────────────────────────────────────
def copiar(nube, destino):
    """Copia todas las tablas de la nube a un archivo SQLite nuevo y comprueba
    que quedó sano y con todas las filas leídas."""
    dst = sqlite3.connect(destino)
    try:
        esquema = [tuple(f) for f in nube.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'").fetchall()]
        leidas = {}
        for tipo, nombre, sql in esquema:
            if tipo != "table":
                continue
            dst.execute(sql)
            filas = [tuple(f) for f in nube.execute(f'SELECT * FROM "{nombre}"').fetchall()]
            if filas:
                dst.executemany(f'INSERT INTO "{nombre}" VALUES ({",".join("?" * len(filas[0]))})', filas)
            leidas[nombre] = len(filas)
        for tipo, _, sql in esquema:        # índices y disparadores, ya con los datos
            if tipo != "table":
                dst.execute(sql)
        if dst.execute("SELECT 1 FROM sqlite_master WHERE name = 'sqlite_sequence'").fetchone():
            dst.execute("DELETE FROM sqlite_sequence")
            dst.executemany("INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)",
                            [tuple(f) for f in nube.execute("SELECT name, seq FROM sqlite_sequence").fetchall()])
        dst.commit()
        if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("La copia no pasó la verificación de integridad")
        for nombre, cuantas in leidas.items():
            if dst.execute(f'SELECT COUNT(*) FROM "{nombre}"').fetchone()[0] != cuantas:
                raise RuntimeError(f"A la copia le faltan filas de {nombre}")
        if not leidas.get("clients") or not leidas.get("products"):
            raise RuntimeError("La copia salió sin clientes o sin productos: no se sube")
    finally:
        dst.close()


def copia_en_bytes(abrir_nube):
    """La copia, reintentando si Turso corta la conexión a mitad de camino."""
    for intento in range(INTENTOS_COPIA):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "tienda.db"
            nube = abrir_nube()
            try:
                copiar(nube, ruta)
                return ruta.read_bytes()
            except (sqlite3.OperationalError, ValueError) as e:
                if intento == INTENTOS_COPIA - 1:
                    raise
                print(f"La nube cortó la copia ({type(e).__name__}); se intenta de nuevo")
                time.sleep(5)
            finally:
                nube.close()


# ── Drive ────────────────────────────────────────────────────────────────────
def limpiar(drive, carpeta_id, max_backups=MAX_BACKUPS, holgura=HOLGURA):
    """Deja los últimos max_backups. Devuelve cuántos mandó a la papelera."""
    backups = sorted((a for a in drive.listar(carpeta_id)
                      if a["name"].startswith("tienda_backup_") and a["name"].endswith(".db")),
                     key=lambda a: a["name"])
    if len(backups) <= max_backups + holgura:
        return 0
    viejos = backups[:len(backups) - max_backups]
    for a in viejos:
        drive.a_la_papelera(a["id"])
    return len(viejos)


def subir(drive, carpeta, contenido, ahora):
    raiz = drive.carpeta(carpeta)
    backups, actual = drive.carpeta("backups_db", raiz), drive.carpeta("db_actual", raiz)
    nombre = f"tienda_backup_{ahora:%Y-%m-%d_%H-%M-%S}.db"
    drive.subir(nombre, backups, contenido)
    existente = drive.buscar("tienda.db", actual)
    if existente:
        drive.reemplazar(existente[0]["id"], contenido)
    else:
        drive.subir("tienda.db", actual, contenido)
    return nombre, limpiar(drive, backups)


# ── Todo junto ───────────────────────────────────────────────────────────────
def _variable(nombre):
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise SystemExit(f"Falta la variable {nombre} (ver respaldo/LEEME.md)")
    return valor


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--probar", action="store_true", help="copiar y entrar a Drive, sin subir nada")
    args = parser.parse_args()

    url, token = _variable("TURSO_URL"), _variable("TURSO_TOKEN")
    credenciales = [_variable(v) for v in ("GOOGLE_CLIENTE_ID", "GOOGLE_CLIENTE_SECRETO", "GOOGLE_REFRESH_TOKEN")]
    carpeta = os.environ.get("RESPALDO_CARPETA", "").strip() or "Emprendimiento"
    origen = os.environ.get("RESPALDO_ORIGEN", "").strip() or "a mano"
    ahora = datetime.now()

    try:
        contenido = copia_en_bytes(lambda: conexion_directa(url, token))
        print(f"Copia lista y verificada ({len(contenido) / 1e6:.1f} MB)")
        drive = Drive(token_de_acceso(*credenciales))
        if args.probar:
            hay = drive.buscar(carpeta, "root", carpeta=True)
            print(f"Drive: {'sí' if hay else 'no'} existe la carpeta {carpeta} en Mi unidad"
                  f"{'' if hay else ' (se crearía en el primer respaldo)'}")
            return
        nombre, quitados = subir(drive, carpeta, contenido, ahora)
        print(f"Subido a Drive: {carpeta}/backups_db/{nombre} y {carpeta}/db_actual/tienda.db")
        if quitados:
            print(f"{quitados} respaldos viejos a la papelera de Drive")
        error = ""
    except Exception as e:
        error = str(e) or type(e).__name__
        if args.probar:
            raise
    try:        # para que la página muestre cómo le fue
        conn = conexion_directa(url, token)
        try:
            respaldo_drive.anotar(conn, ahora, origen, error[:300])
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"No se pudo anotar el resultado en la base: {e}")
    if error:
        raise SystemExit(f"El respaldo falló: {error}")


if __name__ == "__main__":
    main()
