import os
import sys
import tkinter as tk
from tkinter import messagebox
from datetime import datetime

# Determinar la ruta base de la aplicación
def get_base_path():
    if getattr(sys, 'frozen', False):
        # Si está empaquetada con PyInstaller
        return os.path.dirname(sys.executable)
    else:
        # Si se ejecuta como script
        return os.path.dirname(os.path.abspath(__file__))

# Configurar la ruta base
base_path = get_base_path()
os.chdir(base_path)

# Asegurarse de que las carpetas necesarias existan
data_dir = os.path.join(base_path, "data")
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

# Importar después de configurar rutas
from views.login_window import LoginWindow
from config.database import init_database

def main():
    try:
        # Inicializar base de datos
        init_database()
        
        # Crear ventana principal (pero mantenerla oculta)
        root = tk.Tk()
        root.withdraw()  # Ocultar ventana principal inicialmente
        
        # Configurar el comportamiento al cerrar
        root.protocol("WM_DELETE_WINDOW", root.quit)
        
        # Mostrar ventana de login
        def show_login():
            login_window = LoginWindow(root)
            # El LoginWindow manejará mostrar la ventana principal
        
        # Ejecutar el login
        show_login()
        
        # Iniciar el loop principal
        root.mainloop()
    except Exception as e:
        # Manejo de errores
        import traceback
        error_msg = f"Error crítico: {str(e)}\n\n{traceback.format_exc()}"
        messagebox.showerror("Error de Inicialización", error_msg)
        
        # Guardar log de errores
        log_path = os.path.join(base_path, "error_log.txt")
        with open(log_path, "a") as f:
            f.write(f"{datetime.now()}: {error_msg}\n")

if __name__ == "__main__":
    main()