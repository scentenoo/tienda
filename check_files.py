import os

def check_file_content(filepath):
    """Verifica el contenido de un archivo"""
    print(f"\n=== Verificando {filepath} ===")
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    print(f"✓ Archivo tiene contenido ({len(content)} caracteres)")
                    # Mostrar las primeras líneas
                    lines = content.split('\n')[:5]
                    for i, line in enumerate(lines, 1):
                        print(f"  {i}: {line}")
                    if len(content.split('\n')) > 5:
                        print("  ...")
                else:
                    print("✗ Archivo está VACÍO")
        except Exception as e:
            print(f"✗ Error leyendo archivo: {e}")
    else:
        print("✗ Archivo NO existe")

# Verificar archivos críticos
files_to_check = [
    'config/database.py',
    'models/user.py',
    'views/login_window.py',
    'views/main_window.py'
]

for file_path in files_to_check:
    check_file_content(file_path)

print("\n=== Verificando imports básicos ===")
try:
    import sys
    sys.path.append('.')
    exec("from config.database import get_connection")
    print("✓ get_connection importado")
except Exception as e:
    print(f"✗ Error importando get_connection: {e}")

try:
    exec("from config.database import init_database")
    print("✓ init_database importado")
except Exception as e:
    print(f"✗ Error importando init_database: {e}")