import os
import sys
import tkinter as tk
from tkinter import messagebox
from datetime import datetime

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

base_path = get_base_path()
os.chdir(base_path)

data_dir = os.path.join(base_path, "data")
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

from config.database import init_database
from models.user import User

def main():
    try:
        init_database()

        root = tk.Tk()
        root.withdraw()
        root.protocol("WM_DELETE_WINDOW", root.quit)

        # Contar usuarios registrados
        users = User.get_all()

        if len(users) == 1:
            # Un solo usuario: entrar directo sin login
            user = users[0]
            print(f"✓ Acceso automático: {user.username} ({user.role})")
            root.deiconify()
            from views.main_window import MainWindow
            MainWindow(root, user)
        else:
            # Más de un usuario: mostrar login normal
            from views.login_window import LoginWindow
            LoginWindow(root)

        root.mainloop()

    except Exception as e:
        import traceback
        error_msg = f"Error crítico: {str(e)}\n\n{traceback.format_exc()}"
        messagebox.showerror("Error de Inicialización", error_msg)
        log_path = os.path.join(base_path, "error_log.txt")
        with open(log_path, "a") as f:
            f.write(f"{datetime.now()}: {error_msg}\n")

if __name__ == "__main__":
    main()