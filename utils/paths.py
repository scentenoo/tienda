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


def get_db_path():
    base_dir = os.path.join(get_base_path(), "data")
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, "tienda.db")