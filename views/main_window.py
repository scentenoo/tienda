import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from views.users_window import UsersWindow
from views.losses_window import LossesWindow
from utils.backup import backup_y_sync_drive
from utils.theme import FONT_TITLE, header_bar
from utils.ventanas import hacer_modal
class MainWindow:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        self.sales_window = None  # Referencia a la ventana de ventas
        self.clients_window = None  # Referencia a la ventana de clientes
        self.huella_bd = self._huella_bd()  # Para saber al salir si hubo cambios
        
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

        # Frame principal
        main_frame = ttk.Frame(self.parent)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_bar(main_frame, "Sistema de Gestión Charcutería HYE", on_logout=self.logout,
                   logout_text="Cerrar Sesión")

        # Contenido principal
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(pady=40, padx=30, fill=tk.BOTH, expand=True)

        # Título
        ttk.Label(content_frame,
                text="Menú principal",
                font=FONT_TITLE).pack(pady=(0, 20))

        # Botones principales, cada módulo con un color semántico propio
        buttons = [
            ("💰 VENTAS", self.open_sales, "primary"),
            ("👥 CLIENTES", self.open_clients, "info"),
            ("📦 INVENTARIO", self.open_inventory, "secondary"),
            ("💵 CAJA DEL DÍA", self.open_cash_register, "success"),
        ]

        if self.user.role == 'admin':
            buttons.extend([
                ("🛒 COMPRAS", self.open_purchases, "warning"),
                ("📉 PÉRDIDAS", self.open_losses, "danger"),
                ("⚙️ USUARIOS", self.open_users, "dark"),
                ("💸 GASTOS OPERATIVOS", self.open_expenses, "success-outline"),
                ("📊 INFORMES", self.open_conciliacion, "info-outline"),
                ("📈 PANEL DE ANÁLISIS", self.open_panel, "primary-outline"),
            ])

        for text, command, bootstyle in buttons:
            btn = ttk.Button(content_frame, text=text, command=command,
                              bootstyle=bootstyle)
            btn.pack(pady=6, fill=tk.X, ipady=8)

        # Footer
        footer = ttk.Frame(main_frame, bootstyle="dark")
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(footer, text="© 2023 Charcutería HYE - Versión 1.0",
                bootstyle="inverse-dark").pack(pady=10)
    
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
            operations_menu.add_command(label="Informes (Conciliación / Pendientes)",
                                        command=self.open_conciliacion)
            operations_menu.add_command(label="Panel de Análisis", command=self.open_panel)
        
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
    
    def _huella_bd(self):
        """Tamaño y fecha de la base, para detectar si se tocó algo."""
        try:
            from utils.paths import get_db_path
            ruta = get_db_path()
            return (os.path.getsize(ruta), os.path.getmtime(ruta))
        except Exception:
            return None

    def hubo_cambios(self):
        actual = self._huella_bd()
        return actual is not None and self.huella_bd is not None and actual != self.huella_bd

    def on_closing(self):
        """Al salir, si se tocó la base, se respalda en Google Drive."""
        if not self.hubo_cambios():
            if messagebox.askyesno("Salir", "¿Está seguro que desea salir del sistema?"):
                self.parent.quit()
            return

        respuesta = messagebox.askyesnocancel(
            "Salir",
            "Hubo cambios en la base de datos durante esta sesión.\n\n"
            "¿Respaldar en Google Drive antes de salir?\n\n"
            "Sí — respaldar y salir (tarda menos de un minuto)\n"
            "No — salir sin respaldar")

        if respuesta is None:      # Canceló: no se sale
            return
        if not respuesta:
            self.parent.quit()
            return

        self._respaldar_y_salir()

    def _respaldar_y_salir(self):
        """Respalda en segundo plano y cierra al terminar, sin congelar nada."""
        espera = self._ventana_de_espera()
        resultado = queue.Queue()

        def trabajo():
            try:
                resultado.put(("ok", backup_y_sync_drive()))
            except Exception as e:
                resultado.put(("error", e))

        threading.Thread(target=trabajo, daemon=True).start()

        def revisar():
            try:
                estado, dato = resultado.get_nowait()
            except queue.Empty:
                self.parent.after(200, revisar)
                return

            espera.destroy()
            if estado == "ok":
                messagebox.showinfo(
                    "Respaldo completado",
                    f"La base quedó respaldada en Google Drive.\n\n{dato['drive']}")
            else:
                # Un fallo de red no puede dejar al usuario atrapado en la app
                messagebox.showwarning(
                    "No se pudo respaldar",
                    f"{dato}\n\nSe cierra igualmente. El respaldo local sí se hizo "
                    f"si el fallo fue solo de subida.")
            self.parent.quit()

        self.parent.after(200, revisar)

    def subir_a_google_drive(self):
        """Lanza el backup en un hilo aparte. La subida a Drive tarda cerca de
        un minuto, y hacerla en el hilo de Tk dejaba la ventana congelada."""
        espera = self._ventana_de_espera()
        resultado = queue.Queue()

        def trabajo():
            try:
                resultado.put(("ok", backup_y_sync_drive()))
            except Exception as e:
                resultado.put(("error", e))

        threading.Thread(target=trabajo, daemon=True).start()

        def revisar():
            try:
                estado, dato = resultado.get_nowait()
            except queue.Empty:
                self.parent.after(200, revisar)
                return

            espera.destroy()
            if estado == "ok":
                messagebox.showinfo(
                    "Google Drive actualizado",
                    f"✔ Backup local:\n{dato['backup']}\n\n"
                    f"✔ Copia de trabajo:\n{dato['sync']}\n\n"
                    f"✔ Subido a Drive:\n{dato['drive']}\n\n"
                    f"✔ Libro para Excel:\n{dato['excel']}\n\n"
                    f"✔ Libro listo para abrir:\n{dato['libro']}\n\n"
                    f"Fecha: {dato['fecha']}"
                )
            else:
                messagebox.showerror("Error", str(dato))

        self.parent.after(200, revisar)

    def _ventana_de_espera(self):
        """Diálogo modal con barra de progreso mientras se sube a Drive."""
        ventana = tk.Toplevel(self.parent)
        ventana.title("Google Drive")
        ventana.geometry("400x140")
        ventana.resizable(False, False)
        ventana.transient(self.parent)
        hacer_modal(ventana)
        x = (ventana.winfo_screenwidth() - 400) // 2
        y = (ventana.winfo_screenheight() - 140) // 2
        ventana.geometry(f"400x140+{x}+{y}")
        # Que no se pueda cerrar a mitad de la subida
        ventana.protocol("WM_DELETE_WINDOW", lambda: None)

        ttk.Label(
            ventana,
            text="Subiendo a Google Drive…\nSuele tardar alrededor de un minuto.",
            justify="center",
        ).pack(pady=(25, 15))
        barra = ttk.Progressbar(ventana, mode="indeterminate", length=320)
        barra.pack()
        barra.start(12)
        return ventana
    
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
    
    def open_conciliacion(self):
        """Conciliación de caja y pendientes: lo que antes se miraba en el Excel."""
        from views.conciliacion_window import ConciliacionWindow
        ConciliacionWindow(self.parent)

    def open_panel(self):
        """Gráficas equivalentes a las del informe de Power BI."""
        from views.panel_window import PanelWindow
        PanelWindow(self.parent)

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