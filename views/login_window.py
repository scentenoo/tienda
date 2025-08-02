import tkinter as tk
from tkinter import ttk, messagebox
from models.user import User
from views.main_window import MainWindow

class LoginWindow:
    def __init__(self, parent):
        self.parent = parent
        self.login_success = False
        
        # Crear ventana de login
        self.window = tk.Toplevel(parent)
        self.window.title("Sistema de Gestión - Login")
        self.window.geometry("450x350")
        self.window.resizable(False, False)
        
        # Hacer la ventana visible y traerla al frente
        self.window.lift()
        self.window.attributes('-topmost', True)
        self.window.after_idle(self.window.attributes, '-topmost', False)
        
        # Centrar ventana
        self.center_window()
        
        # Configurar UI
        self.setup_ui()
        
        # Configurar eventos
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.window.focus_force()
        
        # Enfocar en el campo de usuario después de un momento
        self.window.after(100, lambda: self.username_entry.focus())
    
    def center_window(self):
        """Centra la ventana en la pantalla"""
        self.window.update_idletasks()
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - 450) // 2
        y = (screen_height - 350) // 2
        self.window.geometry(f"450x350+{x}+{y}")
    
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Frame principal con color de fondo
        main_frame = tk.Frame(self.window, bg='#f0f0f0', padx=40, pady=30)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = tk.Label(main_frame, 
                              text="SISTEMA DE GESTIÓN", 
                              font=("Arial", 18, "bold"),
                              bg='#f0f0f0',
                              fg='#2c3e50')
        title_label.pack(pady=(0, 10))
        
        subtitle_label = tk.Label(main_frame, 
                                 text="Tienda de Charcutería", 
                                 font=("Arial", 12),
                                 bg='#f0f0f0',
                                 fg='#34495e')
        subtitle_label.pack(pady=(0, 40))
        
        # Frame para el formulario
        form_frame = tk.Frame(main_frame, bg='#f0f0f0')
        form_frame.pack(pady=20)
        
        # Campo Usuario
        tk.Label(form_frame, text="Usuario:", 
                font=("Arial", 11, "bold"),
                bg='#f0f0f0').pack(anchor=tk.W, pady=(0, 5))
        
        self.username_entry = tk.Entry(form_frame, 
                                      width=30, 
                                      font=("Arial", 11),
                                      relief='solid',
                                      bd=1)
        self.username_entry.pack(pady=(0, 15))
        
        # Campo Contraseña
        tk.Label(form_frame, text="Contraseña:", 
                font=("Arial", 11, "bold"),
                bg='#f0f0f0').pack(anchor=tk.W, pady=(0, 5))
        
        self.password_entry = tk.Entry(form_frame, 
                                      width=30, 
                                      show="*", 
                                      font=("Arial", 11),
                                      relief='solid',
                                      bd=1)
        self.password_entry.pack(pady=(0, 25))
        
        # Botón de login
        login_button = tk.Button(form_frame, 
                               text="INICIAR SESIÓN", 
                               command=self.login,
                               font=("Arial", 11, "bold"),
                               bg='#3498db',
                               fg='white',
                               width=25,
                               height=2,
                               relief='flat',
                               cursor='hand2')
        login_button.pack(pady=10)
        
        # Bind Enter key
        self.window.bind('<Return>', lambda event: self.login())
        
        # Información de credenciales
        info_frame = tk.Frame(main_frame, bg='#f0f0f0')
        info_frame.pack(side=tk.BOTTOM, pady=(30, 0))
        
        tk.Label(info_frame, 
                text="Credenciales por defecto:", 
                font=("Arial", 9, "bold"),
                bg='#f0f0f0',
                fg='#7f8c8d').pack()
        
        tk.Label(info_frame, 
                text="Usuario: admin | Contraseña: admin123", 
                font=("Arial", 9),
                bg='#f0f0f0',
                fg='#95a5a6').pack(pady=(2, 0))
    
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