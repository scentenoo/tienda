#!/bin/bash
# Compila el ejecutable de Linux en dist-linux/CharcuteriaHYE
# Requisito previo (una sola vez):
#   sudo apt install python3-tk python3-venv
set -e
cd "$(dirname "$0")"

python3 -c "import tkinter" 2>/dev/null || {
    echo "ERROR: falta tkinter. Ejecuta: sudo apt install python3-tk"; exit 1; }

if [ ! -d ".venv-linux" ]; then
    echo ">> Creando entorno virtual .venv-linux"
    python3 -m venv .venv-linux
fi

echo ">> Instalando dependencias"
.venv-linux/bin/pip install --upgrade pip -q
.venv-linux/bin/pip install -q -r requirements.txt pyinstaller

echo ">> Compilando"
.venv-linux/bin/pyinstaller --noconfirm \
    --distpath dist-linux --workpath build-linux \
    CharcuteriaHYE-linux.spec

mkdir -p dist-linux/data
echo ""
echo "Listo: dist-linux/CharcuteriaHYE"
