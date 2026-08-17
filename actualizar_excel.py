#!/usr/bin/env python3
"""Actualiza el libro de Excel a mano. La app lo hace sola al guardar la base."""
import sys
from pathlib import Path

from utils.libro_excel import actualizar, LIBRO_POR_DEFECTO

BD_POR_DEFECTO = Path(__file__).resolve().parent / "dist-linux" / "data" / "tienda.db"

if __name__ == "__main__":
    libro = Path(sys.argv[1]) if len(sys.argv) > 1 else LIBRO_POR_DEFECTO
    bd    = Path(sys.argv[2]) if len(sys.argv) > 2 else BD_POR_DEFECTO
    print(f"Base de datos: {bd}")
    print(f"Libro:         {libro}\n")
    actualizar(libro, bd)
