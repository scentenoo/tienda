import tkinter as tk
from tkinter import ttk, messagebox
from views.users_window import UsersWindow
from views.losses_window import LossesWindow
from utils.backup import backup_y_sync_drive
class MainWindow:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        self.sales_window = None  # Referencia a la ventana de ventas
        self.clients_window = None  # Referencia a la ventana de clientes
        
        # Limpiar la ventana principal
        for widget in self.parent.winfo_children():
            widget.destroy()
        
        # Configurar ventana principal
        self.parent.title(f"Sistema de Gestión - {user.username} ({user.role})")
        x = (self.parent.winfo_screenwidth() - 900) // 2
        y = (self.parent.winfo_screenheight() - 820) // 2
        self.parent.geometry(f"900x820+{x}+{y}")

        
        # Centrar ventana
        self.center_window()
        
        # Configurar el protocolo de cierre
        self.parent.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.setup_ui()
    
    def center_window(self):
        """Centra la ventana en la pantalla"""
        self.parent.update_idletasks()
        x = (self.parent.winfo_screenwidth() - 900) // 2
        y = (self.parent.winfo_screenheight() - 820) // 2
        self.parent.geometry(f"900x820+{x}+{y}")
    
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        self.create_menu()
        
        # Configuración de estilos
        self.style = ttk.Style()
        self.style.configure('TFrame', background='#f5f5f5')
        self.style.configure('TButton', font=('Arial', 11), padding=10)
        self.style.configure('Header.TLabel', font=('Arial', 12, 'bold'), foreground='#495057')
        
        # Frame principal
        main_frame = ttk.Frame(self.parent, style='TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header = tk.Frame(main_frame, bg='#343a40', height=60)
        header.pack(fill=tk.X)
        
        # Botón de logout
        logout_btn = ttk.Button(header, text="Cerrar Sesión", command=self.logout, style='Header.TButton')
        logout_btn.pack(side=tk.RIGHT, padx=20, pady=10)
        
        # Contenido principal
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(pady=40, padx=30, fill=tk.BOTH, expand=True)
        
        # Título
        ttk.Label(content_frame, 
                text="Sistema de Gestión Charcutería HYE",
                font=("Arial", 20, "bold")).pack(pady=(0, 20))
        
        # Botones principales
        button_style = {
            "width": 20,
            "padding": 15,
            "font": ('Arial', 11, 'bold')
        }
        
        buttons = [
            ("💰 VENTAS", self.open_sales),
            ("👥 CLIENTES", self.open_clients),
            ("📦 INVENTARIO", self.open_inventory),
            ("💵 CAJA DEL DÍA", self.open_cash_register)
        ]
        
        if self.user.role == 'admin':
            buttons.extend([
                ("🛒 COMPRAS", self.open_purchases),
                ("📉 PÉRDIDAS", self.open_losses),
                ("⚙️ USUARIOS", self.open_users),
                ("💸 GASTOS OPERATIVOS", self.open_expenses)
            ])
        
        for text, command in buttons:
            btn = tk.Button(content_frame, text=text, command=command,
                        bg='#4a6baf', fg='white', bd=0,
                        font=('Arial', 11, 'bold'),
                        padx=20, pady=10)
            btn.pack(pady=10, fill=tk.X)
        
        # Footer
        footer = tk.Frame(main_frame, bg='#343a40', height=40)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(footer, text="© 2023 Charcutería HYE - Versión 1.0", 
                foreground="white", background="#343a40").pack(pady=10)
    
    def create_menu(self):
        """Crea el menú de la aplicación"""
        menubar = tk.Menu(self.parent)
        self.parent.config(menu=menubar)
        
        # Menú Archivo
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=file_menu)
        file_menu.add_command(
            label="Guardar base de datos en Google Drive",
            command=self.subir_a_google_drive
        )
        file_menu.add_separator()
        file_menu.add_command(label="Cerrar Sesión", command=self.logout)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.on_closing)
        
        # Menú Operaciones
        operations_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Operaciones", menu=operations_menu)
        operations_menu.add_command(label="Ventas", command=self.open_sales)
        
        if self.user.role == 'admin':
            operations_menu.add_command(label="Compras", command=self.open_purchases)
            operations_menu.add_command(label="Pérdidas y Mermas", command=self.open_losses)
        
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
        from models.user import User
        users = User.get_all()
        
        if len(users) == 1:
            # Un solo usuario: cerrar sesión = cerrar app
            if messagebox.askyesno("Salir", "¿Está seguro que desea salir del sistema?"):
                self.parent.quit()
        else:
            # Varios usuarios: volver al login
            if messagebox.askyesno("Cerrar Sesión", "¿Está seguro que desea cerrar sesión?"):
                self.parent.withdraw()
                self.user = None
                for widget in self.parent.winfo_children():
                    widget.destroy()
                from views.login_window import LoginWindow
                LoginWindow(self.parent)
    
    def on_closing(self):
        """Maneja el cierre de la ventana"""
        if messagebox.askyesno("Salir", "¿Está seguro que desea salir del sistema?"):
            self.parent.quit()

    def subir_a_google_drive(self):
        try:
            info = backup_y_sync_drive()

            messagebox.showinfo(
                "Google Drive actualizado",
                f"✔ Backup creado:\n{info['backup']}\n\n"
                f"✔ Base sincronizada:\n{info['sync']}\n\n"
                f"Fecha: {info['fecha']}"
            )

        except Exception as e:
            messagebox.showerror("Error", str(e))
    
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
        """Abre la ventana de ventas y guarda la referencia"""
        try:
            # Si ya existe una ventana, verificar si sigue abierta
            if self.sales_window and hasattr(self.sales_window, 'window'):
                try:
                    if self.sales_window.window.winfo_exists():
                        self.sales_window.window.lift()  # Traer al frente
                        return
                except:
                    pass  # La ventana no existe, crear nueva
            
            from views.sales_window import SalesWindow
            self.sales_window = SalesWindow(self.parent, self.user)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir ventas: {e}")

    def open_losses(self):
        """Abre la ventana de pérdidas y mermas"""
        if self.user.role != 'admin':
            messagebox.showwarning("Acceso Denegado", 
                                "Solo los administradores pueden acceder a este módulo.")
            return
            
        try:
            from models.product import Product
            if not Product.get_all():
                messagebox.showwarning("Sin productos", "Debe registrar productos primero")
                return
                
            from views.losses_window import LossesWindow
            LossesWindow(self.parent, self.user)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir pérdidas: {e}")
            print(f"Error detallado: {e}")  # Para diagnóstico
        
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
        """Abre la ventana de clientes y guarda la referencia"""
        try:
            if self.clients_window and hasattr(self.clients_window, 'window'):
                try:
                    if self.clients_window.window.winfo_exists():
                        self.clients_window.window.lift()
                        return
                except:
                    pass
                
            from views.clients_window import ClientsWindow
            self.clients_window = ClientsWindow(self.parent, self.user)  # Elimina main_window=self
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir clientes: {e}")
    
    def refresh_all_windows(self):
        """Refresca todas las ventanas abiertas"""
        try:
            # Refrescar ventana de ventas
            if self.sales_window and hasattr(self.sales_window, 'window'):
                try:
                    if self.sales_window.window.winfo_exists():
                        if hasattr(self.sales_window, 'refresh_sales'):
                            self.sales_window.refresh_sales()
                            print("✅ Ventana de ventas actualizada")
                except:
                    self.sales_window = None
            
            # Refrescar ventana de clientes
            if self.clients_window and hasattr(self.clients_window, 'window'):
                try:
                    if self.clients_window.window.winfo_exists():
                        if hasattr(self.clients_window, 'refresh_clients'):
                            self.clients_window.refresh_clients()
                            print("✅ Ventana de clientes actualizada")
                except:
                    self.clients_window = None
                    
        except Exception as e:
            print(f"Error al refrescar ventanas: {e}")

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
            
    def open_cash_register(self):
        """Abre el módulo de caja del día"""
        try:
            from views.cash_register_window import CashRegisterWindow
            CashRegisterWindow(self.parent, self.user)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir caja: {e}")