#!/bin/bash
# Actualiza el Excel con los datos de la base. Reemplaza al botón
# "Actualizar" de Power Query, que solo funcionaba en Excel sobre Windows.
cd "$(dirname "$0")"
exec .venv-linux/bin/python actualizar_excel.py "$@"
