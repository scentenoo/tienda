import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from models.user import User
from views.main_window import MainWindow
from utils.theme import FONT_TITLE, FONT_NORMAL, FONT_BOLD, FONT_SMALL
from utils.ventanas import centrar_ventana

class LoginWindow:
    def __init__(self, parent):
        self.parent = parent
        self.login_success = False

        # Crear ventana de login
        self.window = tk.Toplevel(parent)
        self.window.title("Sistema de Gestión - Login")
        self.window.resizable(False, False)

        # Hacer la ventana visible y traerla al frente
        self.window.lift()
        self.window.attributes('-topmost', True)
        self.window.after_idle(self.window.attributes, '-topmost', False)

        # Centrar ventana
        centrar_ventana(self.window, 460, 420)

        # Configurar UI
        self.setup_ui()

        # Configurar eventos
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.window.focus_force()

        # Enfocar en el campo de usuario después de un momento
        self.window.after(100, lambda: self.username_entry.focus())

    def setup_ui(self):
        """Configura la interfaz de usuario"""
        outer = ttk.Frame(self.window, padding=30)
        outer.pack(fill=tk.BOTH, expand=True)

        # Tarjeta de login
        card = ttk.Frame(outer, bootstyle="light", padding=30)
        card.pack(fill=tk.BOTH, expand=True)

        ttk.Label(card, text="SISTEMA DE GESTIÓN", font=FONT_TITLE,
                  bootstyle="inverse-light", anchor=tk.CENTER).pack(fill=tk.X, pady=(0, 4))

        ttk.Label(card, text="Tienda de Charcutería", font=FONT_NORMAL,
                  bootstyle="secondary", anchor=tk.CENTER).pack(fill=tk.X, pady=(0, 30))

        form_frame = ttk.Frame(card, bootstyle="light")
        form_frame.pack(fill=tk.X)

        ttk.Label(form_frame, text="Usuario", font=FONT_BOLD,
                  bootstyle="inverse-light").pack(anchor=tk.W, pady=(0, 5))
        self.username_entry = ttk.Entry(form_frame, width=30, font=FONT_NORMAL)
        self.username_entry.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(form_frame, text="Contraseña", font=FONT_BOLD,
                  bootstyle="inverse-light").pack(anchor=tk.W, pady=(0, 5))
        self.password_entry = ttk.Entry(form_frame, width=30, show="*", font=FONT_NORMAL)
        self.password_entry.pack(fill=tk.X, pady=(0, 25))

        login_button = ttk.Button(form_frame, text="INICIAR SESIÓN",
                                   command=self.login, bootstyle="primary")
        login_button.pack(fill=tk.X, ipady=6)

        # Bind Enter key
        self.window.bind('<Return>', lambda event: self.login())

        # Información de credenciales
        info_frame = ttk.Frame(card, bootstyle="light")
        info_frame.pack(side=tk.BOTTOM, pady=(30, 0))

        ttk.Label(info_frame, text="Credenciales por defecto:", font=FONT_SMALL,
                  bootstyle="secondary", anchor=tk.CENTER).pack()
        ttk.Label(info_frame, text="Usuario: admin | Contraseña: admin123", font=FONT_SMALL,
                  bootstyle="secondary", anchor=tk.CENTER).pack(pady=(2, 0))

    def login(self):
        """Maneja el proceso de login"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        # Validar campos
        if not username:
            messagebox.showerror("Error", "Por favor ingrese el usuario")
            self.username_entry.focus()
            return

        if not password:
            messagebox.showerror("Error", "Por favor ingrese la contraseña")
            self.password_entry.focus()
            return

        try:
            # Intentar autenticar
            user = User.authenticate(username, password)

            if user:
                print(f"✓ Usuario autenticado: {user.username} ({user.role})")

                # Mostrar mensaje de bienvenida personalizado
                messagebox.showinfo("Bienvenido",
                                f"Bienvenido, {user.name}!\n"
                                f"Has iniciado sesión como {user.role.capitalize()}")

                # Cerrar ventana de login
                self.window.destroy()

                # Mostrar ventana principal
                self.parent.deiconify()
                main_window = MainWindow(self.parent, user)

                self.login_success = True

            else:
                messagebox.showerror("Error de Autenticación",
                                "Usuario o contraseña incorrectos.\n\n"
                                "Verifique sus credenciales e intente nuevamente.")
                self.password_entry.delete(0, tk.END)
                self.username_entry.focus()

        except Exception as e:
            messagebox.showerror("Error de Sistema",
                            f"Error al conectar con la base de datos:\n{e}")
            print(f"✗ Error en login: {e}")

    def on_closing(self):
        """Maneja el cierre de la ventana de login"""
        result = messagebox.askyesno("Confirmar Salida",
                                   "¿Está seguro que desea cerrar la aplicación?")
        if result:
            self.parent.quit()
