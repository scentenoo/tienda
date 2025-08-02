import tkinter as tk
from tkinter import ttk, messagebox
from views.users_window import UsersWindow

class MainWindow:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        
        # Limpiar la ventana principal
        for widget in self.parent.winfo_children():
            widget.destroy()
        
        # Configurar ventana principal
        self.parent.title(f"Sistema de Gestión - {user.username} ({user.role})")
        self.parent.geometry("900x700")
        
        # Centrar ventana
        self.center_window()
        
        # Configurar el protocolo de cierre
        self.parent.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.setup_ui()
    
    def center_window(self):
        """Centra la ventana en la pantalla"""
        self.parent.update_idletasks()
        x = (self.parent.winfo_screenwidth() - 900) // 2
        y = (self.parent.winfo_screenheight() - 700) // 2
        self.parent.geometry(f"900x700+{x}+{y}")
    
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Crear menú
        self.create_menu()
        
        # Frame principal
        main_frame = ttk.Frame(self.parent, padding="30")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título de bienvenida
        welcome_label = ttk.Label(main_frame, 
                                 text="Sistema de Gestión de Charcuteria HYE",
                                 font=("Arial", 20, "bold"))
        welcome_label.pack(pady=(0, 10))
        
        # Subtitle con info del usuario
        user_label = ttk.Label(main_frame, 
                              text=f"Bienvenido: {self.user.username} | Rol: {self.user.role}",
                              font=("Arial", 12), 
                              foreground="blue")
        user_label.pack(pady=(0, 40))
        
        # Frame para botones principales
        buttons_container = ttk.Frame(main_frame)
        buttons_container.pack(expand=True)
        
        # Primera fila de botones
        row1_frame = ttk.Frame(buttons_container)
        row1_frame.pack(pady=20)
        
        # Estilo de botones
        button_style = {
            "width": 25,
            "padding": (20, 10)
        }
        
        # Modificar esta parte en setup_ui() de MainWindow
        sales_btn = ttk.Button(row1_frame, text="💰 VENTAS", 
                            command=self.open_sales, **button_style)
        sales_btn.pack(side=tk.LEFT, padx=15)

        # Solo mostrar botón de compras a administradores
        if self.user.role == 'admin':
            purchases_btn = ttk.Button(row1_frame, text="🛒 COMPRAS", 
                                    command=self.open_purchases, **button_style)
            purchases_btn.pack(side=tk.LEFT, padx=15)

        clients_btn = ttk.Button(row1_frame, text="👥 CLIENTES", 
                                command=self.open_clients, **button_style)
        clients_btn.pack(side=tk.LEFT, padx=15)
        
        # Segunda fila de botones
        row2_frame = ttk.Frame(buttons_container)
        row2_frame.pack(pady=20)
        
        inventory_btn = ttk.Button(row2_frame, text="📦 INVENTARIO", 
                                  command=self.open_inventory, **button_style)
        inventory_btn.pack(side=tk.LEFT, padx=15)
        
        # Solo mostrar opciones de admin para administradores
        if self.user.role == 'admin':
            expenses_btn = ttk.Button(row2_frame, text="💸 GASTOS", 
                                     command=self.open_expenses, **button_style)
            expenses_btn.pack(side=tk.LEFT, padx=15)
            
            reports_btn = ttk.Button(row2_frame, text="📊 REPORTES", 
                                    command=self.open_reports, **button_style)
            reports_btn.pack(side=tk.LEFT, padx=15)
        
        # Separador
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=40)
        
        # Información del sistema
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(side=tk.BOTTOM)
        
        status_label = ttk.Label(info_frame, 
                               text="✅ Sistema listo para usar", 
                               font=("Arial", 11), 
                               foreground="green")
        status_label.pack()
        
        version_label = ttk.Label(info_frame, 
                                text="Versión 1.0 | Sistema de Gestión Comercial", 
                                font=("Arial", 9), 
                                foreground="gray")
        version_label.pack(pady=5)

        # Agregar botón de cierre de sesión en la parte superior
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Información del usuario
        user_info = ttk.Label(header_frame, 
                            text=f"Usuario: {self.user.name} | Rol: {self.user.role.capitalize()}", 
                            font=("Arial", 10))
        user_info.pack(side=tk.LEFT, padx=10)
        
        # Botón de cierre de sesión
        logout_btn = ttk.Button(header_frame, text="Cerrar Sesión", command=self.logout)
        logout_btn.pack(side=tk.RIGHT, padx=10)
    
    def create_menu(self):
        """Crea el menú de la aplicación"""
        menubar = tk.Menu(self.parent)
        self.parent.config(menu=menubar)
        
        # Menú Archivo
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=file_menu)
        file_menu.add_command(label="Cerrar Sesión", command=self.logout)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.on_closing)
        
        # Menú Operaciones
        operations_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Operaciones", menu=operations_menu)
        operations_menu.add_command(label="Ventas", command=self.open_sales)
        
        # Solo mostrar Compras a los administradores
        if self.user.role == 'admin':
            operations_menu.add_command(label="Compras", command=self.open_purchases)
        
        operations_menu.add_command(label="Clientes", command=self.open_clients)
        operations_menu.add_command(label="Inventario", command=self.open_inventory)
        
        if self.user.role == 'admin':
            operations_menu.add_separator()
            operations_menu.add_command(label="Gestión de Usuarios", command=self.open_users)
            operations_menu.add_command(label="Gastos Operativos", command=self.open_expenses)
            operations_menu.add_command(label="Reportes", command=self.open_reports)
        
        # Menú Ayuda
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayuda", menu=help_menu)
        help_menu.add_command(label="Acerca de", command=self.show_about)

    def logout(self):
        """Cierra la sesión actual y muestra la ventana de login"""
        if messagebox.askyesno("Cerrar Sesión", "¿Está seguro que desea cerrar sesión?"):
            # Ocultar ventana principal
            self.parent.withdraw()
            
            # Limpiar cualquier dato de sesión si es necesario
            self.user = None
            
            # Destruir todos los widgets hijos de la ventana principal
            for widget in self.parent.winfo_children():
                widget.destroy()
            
            # Mostrar ventana de login nuevamente
            from views.login_window import LoginWindow
            LoginWindow(self.parent)
    
    def on_closing(self):
        """Maneja el cierre de la ventana"""
        if messagebox.askyesno("Salir", "¿Está seguro que desea salir del sistema?"):
            self.parent.quit()
    
    def show_about(self):
        """Muestra información sobre el sistema"""
        messagebox.showinfo("Acerca de", 
                           "Sistema de Gestión de Charcuteria HYE\n"
                           "Versión 1.0\n\n"
                           "Desarrollado para gestión de:\n"
                           "• Inventarios y productos\n"
                           "• Ventas al contado y fiadas\n"
                           "• Control de clientes\n"
                           "• Reportes financieros\n\n"
                           "Desarrollado en Python con Tkinter")
    
    def open_sales(self):
        """Abre la ventana de ventas"""
        try:
            from views.sales_window import SalesWindow
            SalesWindow(self.parent, self.user)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir ventas: {e}")
        
    def open_purchases(self):
        """Abre la ventana de compras"""
        # Verificar si el usuario tiene permisos
        if self.user.role != 'admin':
            messagebox.showwarning("Acceso Denegado", 
                                "Solo los administradores pueden acceder a este módulo.")
            return
            
        try:
            from views.purchases_window import PurchasesWindow
            PurchasesWindow(self.parent, self.user)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir compras: {e}")

    def open_clients(self):
        """Abre la ventana de clientes"""
        from views.clients_window import ClientsWindow
        ClientsWindow(self.parent, self.user)
    
    def open_inventory(self):
        """Abre la ventana de inventario"""
        from views.inventory_window import InventoryWindow
        InventoryWindow(self.parent, self.user)
    
    def open_expenses(self):
        """Abre la ventana de gastos operativos"""
        if self.user.role == 'admin':
            try:
                from views.expenses_window import ExpensesWindow
                ExpensesWindow(self.parent, self.user)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir gastos: {e}")
        else:
            messagebox.showwarning("Acceso Denegado", 
                                 "Solo los administradores pueden acceder a este módulo.")
    
    def open_reports(self):
        """Abre la ventana de reportes"""
        if self.user.role == 'admin':
            try:
                from views.reports_window import ReportsWindow
                ReportsWindow(self.parent, self.user)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir reportes: {e}")
        else:
            messagebox.showwarning("Acceso Denegado", 
                                 "Solo los administradores pueden acceder a este módulo.")
            
    def open_users(self):
        """Abre la ventana de gestión de usuarios"""
        if self.user.role == 'admin':
            try:
                UsersWindow(self.parent, self.user)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir gestión de usuarios: {e}")
        else:
            messagebox.showwarning("Acceso Denegado", 
                                "Solo los administradores pueden acceder a este módulo.")