#!/bin/bash
# Crea el acceso directo de la aplicación en el menú de Ubuntu, con su logo.
# Todo se instala en tu carpeta personal: no necesita sudo ni toca el sistema.
set -e
cd "$(dirname "$0")"
RAIZ="$(pwd)"

mkdir -p ~/.local/share/applications ~/.local/share/icons

cp "$RAIZ/assets/icon.png" ~/.local/share/icons/charcuteria-hye.png

cat > ~/.local/share/applications/charcuteria-hye.desktop <<DESKTOP
[Desktop Entry]
Type=Application
Name=Charcutería H&E
Comment=Sistema de gestión de inventario, ventas y clientes
Exec=$RAIZ/dist-linux/CharcuteriaHYE
Path=$RAIZ/dist-linux
Icon=charcuteria-hye
Terminal=false
Categories=Office;Finance;
DESKTOP

chmod +x ~/.local/share/applications/charcuteria-hye.desktop
update-desktop-database ~/.local/share/applications 2>/dev/null || true

echo "Listo. Busca «Charcutería» en el menú de aplicaciones."
echo "Para quitarlo:  rm ~/.local/share/applications/charcuteria-hye.desktop"
