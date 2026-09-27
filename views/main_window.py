import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from views.users_window import UsersWindow
from views.losses_window import LossesWindow
from utils.backup import backup_y_sync_drive
from utils.theme import FONT_TITLE, header_bar
from utils.ventanas import hacer_modal, centrar_ventana
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
        self.parent.resizable(True, True)
        centrar_ventana(self.parent, 900, 820)
        self.parent.minsize(800, 650)

        # Configurar el protocolo de cierre
        self.parent.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        self.create_menu()

        # Frame principal
        main_frame = ttk.Frame(self.parent)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_bar(main_frame, "Sistema de Gestión Charcutería HYE", on_logout=self.logout,
                   logout_text="Cerrar Sesión")

        # Footer (se empaqueta antes que el contenido para que quede fijo
        # abajo y nunca se lo coma el área con scroll)
        footer = ttk.Frame(main_frame, bootstyle="dark")
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(footer, text="© 2023 Charcutería HYE - Versión 1.0",
                bootstyle="inverse-dark").pack(pady=10)

        # Contenido principal, con scroll: en pantallas chicas o con
        # escalado de Windows el menú de administrador (10 botones) no
        # entra completo, y sin esto los últimos botones quedaban fuera
        # de la vista sin ninguna forma de llegar a ellos.
        canvas = tk.Canvas(main_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        content_frame = ttk.Frame(canvas)
        content_window = canvas.create_window((0, 0), window=content_frame, anchor="nw")
        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(content_window, width=e.width)
        )

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-event.delta / 120), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        inner = ttk.Frame(content_frame, padding=(30, 40))
        inner.pack(fill=tk.X)

        # Título
        ttk.Label(inner,
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
            btn = ttk.Button(inner, text=text, command=command,
                              bootstyle=bootstyle)
            btn.pack(pady=6, fill=tk.X, ipady=8)
    
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
            "¿Respaldar en Google Drive?\n\n"
            "Sí — el respaldo sigue en segundo plano y la app cierra ya\n"
            "No — salir sin respaldar")

        if respuesta is None:      # Canceló: no se sale
            return
        if not respuesta:
            self.parent.quit()
            return

        if self._lanzar_respaldo_aparte():
            self.parent.quit()
        else:
            # Sin ejecutable propio (modo desarrollo): se espera con ventana
            self._respaldar_y_salir()

    def _lanzar_respaldo_aparte(self) -> bool:
        """Lanza el respaldo como proceso independiente y devuelve el control.

        Así el cierre es inmediato: la subida a Drive tarda cerca de un minuto
        por el coste de conexión, y no tiene sentido que el usuario lo espere.
        """
        if not getattr(sys, "frozen", False):
            return False
        try:
            registro = open(os.path.join(os.path.dirname(sys.executable),
                                         "respaldo.log"), "a")
            subprocess.Popen(
                [sys.executable, "--respaldo"],
                stdout=registro, stderr=registro,
                start_new_session=True,      # sobrevive al cierre de la app
            )
            return True
        except Exception as e:
            print(f"No se pudo lanzar el respaldo aparte: {e}")
            return False

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
                    f"✔ Base respaldada y sincronizada en Google Drive:\n{dato['drive']}\n\n"
                    f"Fecha: {dato['fecha']}"
                )
            else:
                messagebox.showerror("Error", str(dato))

        self.parent.after(200, revisar)

    def _ventana_de_espera(self):
        """Diálogo modal con barra de progreso mientras se sube a Drive."""
        ventana = tk.Toplevel(self.parent)
        ventana.title("Google Drive")
        ventana.resizable(False, False)
        ventana.transient(self.parent)
        hacer_modal(ventana)
        centrar_ventana(ventana, 400, 140)
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