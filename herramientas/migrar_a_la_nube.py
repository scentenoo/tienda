"""Mudar la base de la tienda a la nube (Turso), o bajarla de vuelta.

MUDANZA (una sola vez, con la tienda cerrada y el programa cerrado):

    python herramientas/migrar_a_la_nube.py mudar dist/CharcuteriaHYE/data

  Antes hay que dejar en esa carpeta el archivo nube_pendiente.json con
  {"url": "libsql://…", "token": "…"} de la base de producción (vacía).
  El proceso:
    1. comprueba que el programa esté cerrado;
    2. respalda tienda.db en tienda-antes-de-la-nube-<fecha>.db;
    3. sube todas las tablas a la nube;
    4. compara la nube con tienda.db fila por fila;
    5. solo si todo coincide, renombra nube_pendiente.json a nube.json,
       que es lo que hace que el programa empiece a usar la nube.
  tienda.db queda intacto: para volver atrás basta con borrar nube.json
  (pero lo anotado en la nube después de la mudanza no estaría en él: para
  eso, primero "bajar").

BAJAR (respaldo completo, o para volver al archivo local):

    python herramientas/migrar_a_la_nube.py bajar dist/CharcuteriaHYE/data/nube.json copia.db
"""
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import libsql


def _conectar(credenciales):
    conn = libsql.connect(credenciales["url"], auth_token=credenciales["token"])
    # Como el sqlite3 del programa: hay movimientos que apuntan a ventas borradas
    conn.execute("PRAGMA foreign_keys=OFF")
    return conn


def _tablas(conn):
    return [f[0] for f in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name").fetchall()]


def _iguales(a, b):
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) <= 1e-6 * max(1.0, abs(float(a)))
        except (TypeError, ValueError):
            return False
    return a == b


def comparar(local, nube):
    """Compara todas las tablas fila por fila. Devuelve la lista de problemas."""
    problemas = []
    for tabla in _tablas(local) + ["sqlite_sequence"]:
        a = local.execute(f'SELECT * FROM "{tabla}" ORDER BY 1').fetchall()
        b = [tuple(f) for f in nube.execute(f'SELECT * FROM "{tabla}" ORDER BY 1').fetchall()]
        if len(a) != len(b):
            problemas.append(f"{tabla}: {len(a)} filas en el PC y {len(b)} en la nube")
            continue
        malas = sum(1 for x, y in zip(a, b)
                    if len(x) != len(y) or not all(_iguales(u, v) for u, v in zip(x, y)))
        if malas:
            problemas.append(f"{tabla}: {malas} filas distintas")
    return problemas


def subir(origen: Path, credenciales):
    src = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
    nube = _conectar(credenciales)
    if _tablas(nube):
        raise SystemExit("La base de la nube no está vacía. Por seguridad no se sobrescribe.")

    esquema = src.execute(
        "SELECT type, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    for tipo, sql in esquema:
        if tipo == "table":
            nube.execute(sql)
    for tabla in _tablas(src):
        columnas = len(src.execute(f'PRAGMA table_info("{tabla}")').fetchall())
        filas = src.execute(f'SELECT * FROM "{tabla}"').fetchall()
        marcas = "(" + ",".join("?" * columnas) + ")"
        lote = max(1, 400 // columnas)           # varias filas por viaje a la nube
        for i in range(0, len(filas), lote):
            parte = filas[i:i + lote]
            nube.execute(f'INSERT INTO "{tabla}" VALUES ' + ",".join([marcas] * len(parte)),
                         tuple(v for f in parte for v in f))
        print(f"  · {tabla}: {len(filas)} filas")
    for tipo, sql in esquema:
        if tipo != "table":
            nube.execute(sql)                    # índices, vistas, triggers
    nube.execute("DELETE FROM sqlite_sequence")
    for nombre, seq in src.execute("SELECT name, seq FROM sqlite_sequence").fetchall():
        nube.execute("INSERT INTO sqlite_sequence(name, seq) VALUES (?, ?)", (nombre, seq))
    nube.commit()
    return src, nube


def bajar(credenciales, destino: Path):
    if destino.exists():
        raise SystemExit(f"{destino} ya existe; elija otro nombre.")
    nube = _conectar(credenciales)
    dst = sqlite3.connect(destino)
    esquema = nube.execute(
        "SELECT type, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    for tipo, sql in esquema:
        if tipo == "table":
            dst.execute(sql)
    for tabla in _tablas(nube):
        filas = [tuple(f) for f in nube.execute(f'SELECT * FROM "{tabla}"').fetchall()]
        if filas:
            dst.executemany(f'INSERT INTO "{tabla}" VALUES ({",".join("?" * len(filas[0]))})', filas)
        print(f"  · {tabla}: {len(filas)} filas")
    for tipo, sql in esquema:
        if tipo != "table":
            dst.execute(sql)
    dst.execute("DELETE FROM sqlite_sequence")
    dst.executemany("INSERT INTO sqlite_sequence(name, seq) VALUES (?, ?)",
                    [tuple(f) for f in nube.execute("SELECT name, seq FROM sqlite_sequence").fetchall()])
    dst.commit()
    problemas = comparar(dst, nube)
    if problemas:
        raise SystemExit("La copia no coincide con la nube:\n  " + "\n  ".join(problemas))
    print(f"Listo: {destino} (idéntica a la nube)")


def _programa_abierto():
    if sys.platform != "win32":
        return False
    salida = subprocess.run(["tasklist", "/FI", "IMAGENAME eq CharcuteriaHYE.exe"],
                            capture_output=True, text=True).stdout
    return "CharcuteriaHYE.exe" in salida


def mudar(carpeta: Path):
    base = carpeta / "tienda.db"
    pendiente, activa = carpeta / "nube_pendiente.json", carpeta / "nube.json"
    if activa.exists():
        raise SystemExit("Esta carpeta ya usa la nube (existe nube.json).")
    if not base.exists() or not pendiente.exists():
        raise SystemExit(f"Faltan {base} o {pendiente}.")
    if _programa_abierto():
        raise SystemExit("Cierre el programa de la tienda antes de mudar la base.")
    credenciales = json.loads(pendiente.read_text(encoding="utf-8"))

    respaldo = carpeta / f"tienda-antes-de-la-nube-{datetime.now():%Y-%m-%d_%H-%M}.db"
    with sqlite3.connect(base) as src, sqlite3.connect(respaldo) as dst:
        src.backup(dst)
    print(f"1. Respaldo: {respaldo.name}")

    print("2. Subiendo a la nube…")
    t = time.time()
    src, nube = subir(respaldo, credenciales)
    print(f"   en {time.time() - t:.0f} s")

    print("3. Comparando fila por fila…")
    problemas = comparar(src, nube)
    if problemas:
        raise SystemExit("NO se activó la nube; no coincide:\n  " + "\n  ".join(problemas))
    deuda = src.execute("SELECT ROUND(SUM(total_debt), 2) FROM clients").fetchone()[0]
    deuda_nube = nube.execute("SELECT ROUND(SUM(total_debt), 2) FROM clients").fetchone()[0]
    print(f"   todo coincide (por cobrar: {deuda:,.0f} en el PC y {deuda_nube:,.0f} en la nube)")

    shutil.move(pendiente, activa)
    print("4. Nube activada: el programa ya usa la base en la nube.")
    print(f"   {base.name} queda intacto como respaldo; no lo borre.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "mudar":
        mudar(Path(sys.argv[2]))
    elif len(sys.argv) == 4 and sys.argv[1] == "bajar":
        bajar(json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")), Path(sys.argv[3]))
    else:
        print(__doc__)
        sys.exit(1)
