import os
import sys


def get_base_path():
    """
    Carpeta base de la aplicación:
    - Si está empaquetada con PyInstaller (.exe), es la carpeta donde vive el .exe.
    - Si corre como script normal, es la raíz del proyecto (un nivel arriba de utils/).
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_data_dir():
    base_dir = os.path.join(get_base_path(), "data")
    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def get_db_path():
    """Archivo de la base. Con la base en la nube (data/nube.json) es la copia
    local que mantiene Turso, no el tienda.db de antes, que queda intacto."""
    base_dir = get_data_dir()
    if os.path.exists(os.path.join(base_dir, "nube.json")):
        return os.path.join(base_dir, "tienda_nube.db")
    return os.path.join(base_dir, "tienda.db")


def get_resource_path(*partes):
    """Ruta de un recurso que viaja dentro del ejecutable (assets/…).

    No es lo mismo que get_base_path(): los datos empaquetados con PyInstaller
    en modo onefile se extraen a una carpeta temporal, no viven junto al
    ejecutable.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *partes)
