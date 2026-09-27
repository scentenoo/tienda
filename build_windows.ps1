# Compila el ejecutable de Windows en dist\CharcuteriaHYE\ (carpeta, no un solo .exe)
Set-Location -Path $PSScriptRoot

# Python 3.13: la librería de la base en la nube (libsql) no tiene versión
# para Windows con 3.14. Si el .venv es de otra versión, se rehace.
$version = if (Test-Path ".venv\Scripts\python.exe") { & .venv\Scripts\python.exe -c "import sys; print('%d.%d' % sys.version_info[:2])" } else { "" }
if ($version -ne "3.13") {
    Write-Host ">> Creando entorno virtual .venv (Python 3.13)"
    if (Test-Path ".venv") { Remove-Item -Recurse -Force .venv }
    uv venv .venv --python 3.13
}

Write-Host ">> Instalando dependencias"
uv pip install -q -r requirements.txt pyinstaller --python .venv

# La base de producción vive en dist\CharcuteriaHYE\data, y PyInstaller con
# --noconfirm BORRA la carpeta de salida entera antes de escribir. Por eso se
# compila aparte y luego se copia el programa encima, sin tocar data\.
$destino = "dist\CharcuteriaHYE"
if (Test-Path "$destino\data") {
    $respaldo = "dist\respaldo-data-" + (Get-Date -Format "yyyy-MM-dd_HH-mm")
    Write-Host ">> Respaldando $destino\data en $respaldo"
    Copy-Item -Recurse "$destino\data" $respaldo
}

Write-Host ">> Compilando"
.venv\Scripts\pyinstaller.exe --noconfirm --distpath build\salida --workpath build CharcuteriaHYE.spec
if ($LASTEXITCODE -ne 0) { throw "Falló la compilación" }

Write-Host ">> Copiando el programa a $destino (sin tocar data\ ni la base)"
# /MIR deja la carpeta igual a la compilada, pero lo excluido (/XD, /XF)
# no se copia ni se borra.
robocopy "build\salida\CharcuteriaHYE" $destino /MIR /NFL /NDL /NJH /NP `
    /XD data /XF tienda.db tienda.db-shm tienda.db-wal error_log.txt respaldo.log | Out-Null
if ($LASTEXITCODE -ge 8) { throw "Falló la copia (robocopy $LASTEXITCODE)" }
# robocopy devuelve 1-7 cuando todo salió bien; que no parezca un error
$global:LASTEXITCODE = 0

Write-Host ""
Write-Host "Listo: $destino\CharcuteriaHYE.exe"
