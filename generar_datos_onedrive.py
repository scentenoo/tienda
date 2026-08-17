#!/usr/bin/env python3
"""Genera datos.xlsx a mano. La app lo hace sola al guardar la base."""
import sys
from pathlib import Path

from utils.datos_excel import generar

SALIDA_POR_DEFECTO = Path.home() / "Documentos" / "datos.xlsx"
BD_POR_DEFECTO     = Path(__file__).resolve().parent / "dist-linux" / "data" / "tienda.db"

if __name__ == "__main__":
    salida = Path(sys.argv[1]) if len(sys.argv) > 1 else SALIDA_POR_DEFECTO
    bd     = Path(sys.argv[2]) if len(sys.argv) > 2 else BD_POR_DEFECTO
    tablas = generar(salida, bd)
    print(f"{tablas} tablas escritas en {salida}")
