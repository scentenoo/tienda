import os
import sys
import traceback
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import ttkbootstrap as ttk

# Un print() con tilde o emoji revienta con UnicodeEncodeError si la consola
# usa cp1252 (el default en Windows) o si PyInstaller redirige stdout a un
# stream que tampoco es UTF-8. Forzarlo aquí evita que cualquier print()
# suelto en cualquier módulo tumbe la aplicación entera.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

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
from utils.ventanas import centrar_ventana
from utils.theme import configure_treeview_style

def aplicar_icono(root):
    """Pone el logo en la barra de título de todas las ventanas.

    iconphoto(True, …) lo hereda cualquier Toplevel que se abra después, así
    que basta con hacerlo una vez sobre la raíz.
    """
    try:
        from utils.paths import get_resource_path

        ico_path = get_resource_path("assets", "icon.ico")

        if sys.platform == "win32":
            # En Windows, iconphoto por sí solo no siempre actualiza el
            # icono de la esquina de la ventana (bug conocido de Tk); el
            # mecanismo nativo que sí funciona ahí es iconbitmap con el
            # propio .ico. Se hace con default=True para que también lo
            # hereden las ventanas Toplevel que se abran después.
            root.iconbitmap(default=ico_path)

        from PIL import Image, ImageTk

        imagen = Image.open(ico_path)
        # Hay que conservar la referencia o el recolector se lleva la imagen
        root._icono = ImageTk.PhotoImage(imagen.convert("RGBA"))
        root.iconphoto(True, root._icono)
    except Exception as e:
        print(f"No se pudo aplicar el icono: {e}")


def respaldo_en_segundo_plano():
    """Modo sin ventana: solo respalda y sale.

    Lo lanza la propia aplicación al cerrarse, como proceso aparte, para que
    el usuario no espere el minuto que tarda la subida a Drive.
    """
    from utils.backup import backup_y_sync_drive
    try:
        info = backup_y_sync_drive()
        print(f"Respaldo completado: {info['drive']}")
        return 0
    except Exception as e:
        print(f"Respaldo fallido: {e}")
        return 1


def main():
    try:
        init_database()

        # iconphoto=None evita que ttkbootstrap ponga su propio icono por
        # defecto antes de que aplicar_icono() ponga el logo real: en
        # Windows, una vez fijado el icono "default" de la ventana raíz, una
        # segunda llamada a wm_iconbitmap(default=...) no lo reemplaza.
        root = ttk.Window(themename="flatly", iconphoto=None)
        # Fijar el tamaño real ANTES de la primera realización de la
        # ventana (más abajo): si esta se crea nativamente sin geometría
        # (tamaño "natural" ~200x200, el del Canvas vacío del menú), ese
        # tamaño queda encolado como evento <Configure> pendiente y
        # Windows lo aplica más tarde, pisando cualquier geometry() que se
        # haya hecho mientras tanto.
        centrar_ventana(root, 900, 820)
        configure_treeview_style()
        root.withdraw()

        def reportar_error(tipo, valor, rastro):
            """Sin esto, un error dentro de cualquier botón o ventana se traga
            en silencio y la ventana queda en blanco sin explicación."""
            detalle = "".join(traceback.format_exception(tipo, valor, rastro))
            try:
                with open(os.path.join(base_path, "error_log.txt"), "a", encoding="utf-8") as f:
                    f.write(f"{datetime.now()}: {detalle}\n")
            except Exception:
                pass
            messagebox.showerror("Error", f"{valor}\n\n{detalle[-800:]}")

        root.report_callback_exception = reportar_error
        # Forzar la creación de la ventana nativa (aunque siga oculta) antes
        # de fijar el icono: si se llama sobre una ventana aún no
        # "realizada", Windows la descarta al mapearla más tarde.
        root.update()
        aplicar_icono(root)
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
        error_msg = f"Error crítico: {str(e)}\n\n{traceback.format_exc()}"
        messagebox.showerror("Error de Inicialización", error_msg)
        log_path = os.path.join(base_path, "error_log.txt")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now()}: {error_msg}\n")

if __name__ == "__main__":
    if "--respaldo" in sys.argv:
        sys.exit(respaldo_en_segundo_plano())
    main()