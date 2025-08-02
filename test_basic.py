import sys
import os

print("Verificando estructura del proyecto...")

# Verificar que los directorios existen
dirs_to_check = ['config', 'models', 'views', 'utils']
for dir_name in dirs_to_check:
    if os.path.exists(dir_name):
        print(f"✓ Directorio {dir_name} existe")
        init_file = os.path.join(dir_name, '__init__.py')
        if os.path.exists(init_file):
            print(f"✓ {init_file} existe")
        else:
            print(f"✗ {init_file} NO existe - creándolo...")
            with open(init_file, 'w') as f:
                f.write("# Init file\n")
    else:
        print(f"✗ Directorio {dir_name} NO existe")

# Verificar archivos específicos
files_to_check = [
    'config/database.py',
    'models/user.py', 
    'views/login_window.py',
    'views/main_window.py'
]

for file_path in files_to_check:
    if os.path.exists(file_path):
        print(f"✓ {file_path} existe")
    else:
        print(f"✗ {file_path} NO existe")

print("\nIntentando importaciones...")

try:
    from config.database import init_database
    print("✓ config.database importado correctamente")
except Exception as e:
    print(f"✗ Error importando config.database: {e}")

try:
    from models.user import User
    print("✓ models.user.User importado correctamente")
except Exception as e:
    print(f"✗ Error importando models.user.User: {e}")

try:
    from views.login_window import LoginWindow
    print("✓ views.login_window.LoginWindow importado correctamente")
except Exception as e:
    print(f"✗ Error importando views.login_window.LoginWindow: {e}")

print("\nPrueba completada.")