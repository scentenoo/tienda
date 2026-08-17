# -*- mode: python ; coding: utf-8 -*-
# Spec para compilar en Linux (Ubuntu). El de Windows es CharcuteriaHYE.spec.
# Diferencias con el de Windows: un solo archivo (onefile) y sin icono
# (PyInstaller no admite .ico en ejecutables ELF).

from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=collect_data_files('ttkbootstrap'),
    # PIL._tkinter_finder lo carga Pillow dinámicamente desde ImageTk;
    # sin declararlo, ttkbootstrap falla al construir el tema.
    hiddenimports=['openpyxl', 'PIL.ImageTk', 'PIL._tkinter_finder'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CharcuteriaHYE',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
