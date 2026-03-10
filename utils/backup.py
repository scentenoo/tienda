import sqlite3
import time
import shutil
import logging
import os
from datetime import datetime
from pathlib import Path

# ── Configuración ────────────────────────────────────────────────────────────
ORIGEN_DB   = Path(r"C:\Users\Samir\Documents\GitHub\tienda\data\tienda.db")
BACKUP_DIR  = Path(r"G:\Mi unidad\Emprendimiento\backups_db")
SYNC_DIR    = Path(r"G:\Mi unidad\Emprendimiento\db_actual")
SYNC_DB     = SYNC_DIR / "tienda.db"

MAX_BACKUPS     = 30
MAX_REINTENTOS  = 6
ESPERA_BASE     = 3

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(BACKUP_DIR.parent / "backup.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


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
      2. Escribe directamente en destino con nombre temporal
      3. Reemplaza atómicamente
    """
    destino_temp = destino.with_suffix(".tmp")

    # Paso 1: esperar que el origen esté libre
    log.info("Verificando que el archivo origen esté libre…")
    esperar_archivo_libre(origen)

    # Paso 2: copiar directo a Drive con nombre temporal
    log.info("Copiando a Drive…")
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


# ── Función principal ─────────────────────────────────────────────────────────
def backup_y_sync_drive() -> dict:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    SYNC_DIR.mkdir(parents=True, exist_ok=True)

    if not ORIGEN_DB.exists():
        raise FileNotFoundError(f"BD origen no encontrada: {ORIGEN_DB}")

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

    # ── 2. Sync ──────────────────────────────────────────────────────────────
    log.info("Sincronizando con Drive → %s", SYNC_DB)

    # Reutilizamos el backup ya verificado como fuente, así no leemos
    # la BD de producción dos veces
    sync_seguro(ruta_backup, SYNC_DB)

    log.info("Sync completado ✓")
    return {"backup": str(ruta_backup), "sync": str(SYNC_DB), "fecha": fecha}


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        resultado = backup_y_sync_drive()
        log.info("Todo listo: %s", resultado)
    except Exception as e:
        log.critical("Error crítico: %s", e)
        raise