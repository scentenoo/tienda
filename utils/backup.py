import sqlite3
import time
import shutil
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from utils.paths import get_db_path

# ── Configuración ────────────────────────────────────────────────────────────
# Se puede sobreescribir con variables de entorno:
#   CHARCUTERIA_BACKUP_DIR      carpeta local donde se guardan los backups
#   CHARCUTERIA_RCLONE_REMOTE   destino en Drive, con formato "remoto:carpeta"
def _resolver_origen() -> Path:
    """La base de producción es la que vive junto al ejecutable. Corriendo como
    script, get_db_path() apunta a la copia del proyecto, que está atrasada;
    publicar esa por error sobrescribiría la buena en Drive."""
    if os.environ.get("CHARCUTERIA_DB"):
        return Path(os.environ["CHARCUTERIA_DB"])
    if not getattr(sys, "frozen", False):
        del_ejecutable = Path(__file__).resolve().parent.parent / "dist-linux" / "data" / "tienda.db"
        if del_ejecutable.exists():
            return del_ejecutable
    return Path(get_db_path())


ORIGEN_DB = _resolver_origen()

# Carpeta que Google Drive sincroniza sola en Windows. En Linux no existe, y
# escribir esa ruta literal crearía una carpeta basura llamada "G:\Mi unidad\…",
# porque la barra invertida es un carácter válido en nombres de archivo.
DRIVE_WINDOWS = Path(r"G:\Mi unidad\Emprendimiento")


def _base_dir_por_defecto() -> Path:
    if os.name == "nt" and DRIVE_WINDOWS.exists():
        return DRIVE_WINDOWS
    return Path.home() / "Backups" / "CharcuteriaHYE"


BASE_DIR   = Path(os.environ.get("CHARCUTERIA_BACKUP_DIR") or _base_dir_por_defecto())
BACKUP_DIR = BASE_DIR / "backups_db"
SYNC_DIR   = BASE_DIR / "db_actual"
SYNC_DB    = SYNC_DIR / "tienda.db"

# Si escribimos dentro de la carpeta que Drive ya sincroniza (Windows), no hay
# nada que subir. Si no, la subida la hace rclone.
DENTRO_DE_DRIVE = BASE_DIR == DRIVE_WINDOWS
RCLONE_REMOTE   = os.environ.get("CHARCUTERIA_RCLONE_REMOTE", "gdrive:Emprendimiento")

MAX_BACKUPS     = 30
MAX_REINTENTOS  = 6
ESPERA_BASE     = 3
RCLONE_TIMEOUT  = 600

# Destino en OneDrive del libro que lee Excel Online. Si el remoto no está
# configurado, el backup sigue funcionando igual y solo lo salta.
# La UNAL bloquea las aplicaciones de terceros contra su OneDrive, así que el
# libro se deja listo en disco y se sube a mano desde el navegador. Si algún
# día hay un remoto configurado, se sube solo.
ONEDRIVE_REMOTE = os.environ.get("CHARCUTERIA_ONEDRIVE_REMOTE", "onedrive:CharcuteriaHYE")
DATOS_XLSX      = Path(os.environ.get("CHARCUTERIA_DATOS_XLSX")
                       or Path.home() / "Documentos" / "datos.xlsx")

# Forzar IPv4. Con IPv6 activo cada operación tarda ~55s esperando a que
# venza el intento de conexión; por IPv4 baja a ~13s. Se puede desactivar
# poniendo CHARCUTERIA_RCLONE_IPV4=0.
RCLONE_ARGS_BASE = [] if os.environ.get("CHARCUTERIA_RCLONE_IPV4") == "0" else ["--bind", "0.0.0.0"]

log = logging.getLogger(__name__)


def _configurar_log() -> None:
    """Manda el log a la carpeta de backups. Se llama al ejecutar, no al
    importar, para no crear archivos solo por abrir la aplicación."""
    if any(isinstance(h, logging.FileHandler) for h in log.handlers):
        return
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    formato = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    archivo = logging.FileHandler(BASE_DIR / "backup.log", encoding="utf-8")
    archivo.setFormatter(formato)
    consola = logging.StreamHandler()
    consola.setFormatter(formato)
    log.addHandler(archivo)
    log.addHandler(consola)
    log.setLevel(logging.INFO)


# ── Helpers ──────────────────────────────────────────────────────────────────
def exportar_db_segura(origen: Path, destino: Path) -> None:
    """Copia la BD usando la API nativa de SQLite (sin bloqueos)."""
    with sqlite3.connect(origen) as src, sqlite3.connect(destino) as dst:
        src.backup(dst)


def limpiar_backups_antiguos(directorio: Path, max_backups: int) -> None:
    backups = sorted(directorio.glob("tienda_backup_*.db"))
    for archivo in backups[: max(0, len(backups) - max_backups)]:
        archivo.unlink()
        log.info("Backup antiguo eliminado: %s", archivo.name)


def verificar_integridad(ruta_db: Path) -> bool:
    try:
        with sqlite3.connect(ruta_db) as conn:
            return conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    except sqlite3.Error as e:
        log.error("Error de integridad en %s: %s", ruta_db, e)
        return False


def esperar_archivo_libre(ruta: Path, max_intentos: int = MAX_REINTENTOS, espera_base: int = ESPERA_BASE) -> None:
    """Espera hasta que el archivo no esté bloqueado por otro proceso."""
    espera = espera_base
    for intento in range(1, max_intentos + 1):
        try:
            # Intentar abrir en modo exclusivo es la forma más confiable de
            # saber si el archivo está libre
            with open(ruta, "r+b"):
                return  # archivo libre
        except (PermissionError, OSError):
            if intento == max_intentos:
                raise TimeoutError(
                    f"El archivo sigue bloqueado tras {max_intentos} intentos: {ruta}"
                )
            log.warning("Archivo bloqueado (intento %d/%d), esperando %ds…", intento, max_intentos, espera)
            time.sleep(espera)
            espera = min(espera * 2, 30)  # máximo 30s de espera


def sync_seguro(origen: Path, destino: Path) -> None:
    """
    Sincroniza origen → destino de forma segura en 3 pasos:
      1. Espera a que origen esté libre (antivirus, etc.)
      2. Escribe en destino con nombre temporal
      3. Reemplaza atómicamente
    """
    destino_temp = destino.with_suffix(".tmp")

    # Paso 1: esperar que el origen esté libre
    log.info("Verificando que el archivo origen esté libre…")
    esperar_archivo_libre(origen)

    # Paso 2: copiar con nombre temporal
    log.info("Copiando copia de trabajo…")
    shutil.copy2(origen, destino_temp)

    # Paso 3: reemplazar con reintentos
    espera = ESPERA_BASE
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            destino_temp.replace(destino)
            return
        except PermissionError:
            if intento == MAX_REINTENTOS:
                destino_temp.unlink(missing_ok=True)
                raise
            log.warning("Reemplazo bloqueado (intento %d/%d), esperando %ds…", intento, MAX_REINTENTOS, espera)
            time.sleep(espera)
            espera = min(espera * 2, 30)


# ── Subida a Drive con rclone ────────────────────────────────────────────────
def _ejecutar_rclone(args: list) -> subprocess.CompletedProcess:
    if shutil.which("rclone") is None:
        raise RuntimeError(
            "rclone no está instalado. Instálalo con:  sudo apt install rclone"
        )
    proceso = subprocess.run(
        ["rclone", *RCLONE_ARGS_BASE, *args],
        capture_output=True,
        text=True,
        timeout=RCLONE_TIMEOUT,
    )
    if proceso.returncode != 0:
        raise RuntimeError(f"rclone falló: {proceso.stderr.strip() or proceso.stdout.strip()}")
    return proceso


def verificar_remoto(remoto: str) -> None:
    """Comprueba que el remoto de rclone existe, para dar un error claro en
    vez de fallar a mitad de la subida."""
    nombre = remoto.split(":", 1)[0]
    configurados = _ejecutar_rclone(["listremotes"]).stdout.split()
    if f"{nombre}:" not in configurados:
        raise RuntimeError(
            f"El remoto '{nombre}' no está configurado en rclone.\n"
            f"Remotos disponibles: {', '.join(configurados) or 'ninguno'}\n"
            f"Configúralo con:  rclone config"
        )


def subir_a_drive(origen: Path, destino_remoto: str) -> None:
    log.info("Subiendo a Drive → %s", destino_remoto)
    _ejecutar_rclone(["copyto", str(origen), destino_remoto, "--retries", "3"])


def copiar_en_drive(origen_remoto: str, destino_remoto: str) -> None:
    """Copia de una ruta de Drive a otra. Al ser el mismo remoto, rclone lo
    resuelve del lado del servidor y no vuelve a subir el archivo."""
    log.info("Copiando dentro de Drive → %s", destino_remoto)
    _ejecutar_rclone(["copyto", origen_remoto, destino_remoto, "--retries", "3"])


def limpiar_backups_remotos(remoto: str, max_backups: int) -> None:
    """Deja en Drive solo los últimos max_backups, igual que en local.
    rclone los manda a la papelera de Drive, así que son recuperables."""
    salida = _ejecutar_rclone(["lsf", f"{remoto}/backups_db"]).stdout
    backups = sorted(
        nombre for nombre in (linea.strip() for linea in salida.splitlines())
        if nombre.startswith("tienda_backup_") and nombre.endswith(".db")
    )
    for nombre in backups[: max(0, len(backups) - max_backups)]:
        _ejecutar_rclone(["deletefile", f"{remoto}/backups_db/{nombre}"])
        log.info("Backup remoto eliminado: %s", nombre)


def _remoto_configurado(remoto: str) -> bool:
    nombre = remoto.split(":", 1)[0]
    try:
        return f"{nombre}:" in _ejecutar_rclone(["listremotes"]).stdout.split()
    except Exception:
        return False


def publicar_para_excel(ruta_bd: Path) -> str:
    """Deja listo el libro que lee Excel Online. Siempre lo escribe en disco;
    si además hay un remoto configurado, lo sube."""
    from utils.datos_excel import generar

    DATOS_XLSX.parent.mkdir(parents=True, exist_ok=True)
    tablas = generar(DATOS_XLSX, ruta_bd)
    log.info("Libro para Excel generado con %d tablas → %s", tablas, DATOS_XLSX)

    # A Drive va siempre, para que un flujo de Power Automate pueda recogerlo
    # y llevarlo a OneDrive. Las subidas son opcionales: si fallan, el libro ya
    # está en disco y el backup de la base no se puede ver afectado.
    if not DENTRO_DE_DRIVE:
        try:
            destino_drive = f"{RCLONE_REMOTE}/{DATOS_XLSX.name}"
            subir_a_drive(DATOS_XLSX, destino_drive)
        except Exception as e:
            log.warning("No se pudo subir el libro a Drive (%s)", e)

    if _remoto_configurado(ONEDRIVE_REMOTE):
        destino = f"{ONEDRIVE_REMOTE}/{DATOS_XLSX.name}"
        try:
            log.info("Subiendo a OneDrive → %s", destino)
            _ejecutar_rclone(["copyto", str(DATOS_XLSX), destino, "--retries", "3"])
            return destino
        except Exception as e:
            log.warning("No se pudo subir a OneDrive (%s); queda en disco", e)

    return f"{DATOS_XLSX}  (súbelo a OneDrive)"


def actualizar_libro_local(ruta_bd: Path) -> str:
    """Deja el libro de trabajo listo para abrir aquí mismo. Es el camino
    rápido: ~7 segundos, sin pasar por Drive ni OneDrive."""
    from utils.libro_excel import actualizar, LIBRO_POR_DEFECTO

    if not LIBRO_POR_DEFECTO.exists():
        return f"{LIBRO_POR_DEFECTO} (no existe todavía)"
    try:
        actualizar(LIBRO_POR_DEFECTO, ruta_bd)
        return str(LIBRO_POR_DEFECTO)
    except Exception as e:
        log.warning("No se pudo actualizar el libro local (%s)", e)
        return f"no se pudo actualizar ({e})"


# ── Función principal ─────────────────────────────────────────────────────────
def backup_y_sync_drive() -> dict:
    _configurar_log()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    SYNC_DIR.mkdir(parents=True, exist_ok=True)

    if not ORIGEN_DB.exists():
        raise FileNotFoundError(f"BD origen no encontrada: {ORIGEN_DB}")

    if not DENTRO_DE_DRIVE:
        # Falla antes de tocar nada si Drive no está accesible
        verificar_remoto(RCLONE_REMOTE)

    fecha       = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ruta_backup = BACKUP_DIR / f"tienda_backup_{fecha}.db"

    # ── 1. Backup ────────────────────────────────────────────────────────────
    log.info("Iniciando backup → %s", ruta_backup.name)
    exportar_db_segura(ORIGEN_DB, ruta_backup)

    if not verificar_integridad(ruta_backup):
        ruta_backup.unlink(missing_ok=True)
        raise RuntimeError("El backup no pasó la verificación de integridad.")

    (BACKUP_DIR / "ultimo_backup.txt").write_text(fecha, encoding="utf-8")
    limpiar_backups_antiguos(BACKUP_DIR, MAX_BACKUPS)
    log.info("Backup completado ✓")

    # ── 2. Copia de trabajo ──────────────────────────────────────────────────
    log.info("Actualizando copia de trabajo → %s", SYNC_DB)

    # Reutilizamos el backup ya verificado como fuente, así no leemos
    # la BD de producción dos veces
    sync_seguro(ruta_backup, SYNC_DB)

    # ── 3. Drive ─────────────────────────────────────────────────────────────
    if DENTRO_DE_DRIVE:
        # La carpeta ya la sincroniza el cliente de Google Drive
        destino_drive = str(SYNC_DB)
    else:
        destino_drive  = f"{RCLONE_REMOTE}/db_actual/tienda.db"
        remoto_backup  = f"{RCLONE_REMOTE}/backups_db/{ruta_backup.name}"
        subir_a_drive(ruta_backup, remoto_backup)
        copiar_en_drive(remoto_backup, destino_drive)
        limpiar_backups_remotos(RCLONE_REMOTE, MAX_BACKUPS)

    # ── 4. Libro de datos para Excel Online ──────────────────────────────
    destino_excel = publicar_para_excel(ORIGEN_DB)

    # ── 5. Libro local, listo para abrir sin esperar a la nube ───────────
    libro_local = actualizar_libro_local(ORIGEN_DB)

    log.info("Sync completado ✓")
    return {
        "backup": str(ruta_backup),
        "sync":   str(SYNC_DB),
        "drive":  destino_drive,
        "excel":  destino_excel,
        "libro":  libro_local,
        "fecha":  fecha,
    }


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        resultado = backup_y_sync_drive()
        log.info("Todo listo: %s", resultado)
    except Exception as e:
        _configurar_log()
        log.critical("Error crítico: %s", e)
        raise
