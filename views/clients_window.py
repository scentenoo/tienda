import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from models.client import Client
from config.database import get_connection
import sqlite3
from config.database import sync_client_sales_status_on_payment
from views.sale_detail_window import SaleDetailWindow
from utils.theme import FONT_TITLE, FONT_HEADER, FONT_BOLD, FONT_NORMAL, FONT_SMALL, ROW_COLORS, role_color
from utils.ventanas import hacer_modal, centrar_ventana
from utils.estado_cuenta import generar_y_abrir
from servicios.abonos import registrar_abono

class ClientsWindow:
    def __init__(self, parent, user, main_window=None):
        self.parent = parent
        self.user = user
        self.main_window = main_window
        self.clients = []
        self.selected_client = None

        # Ventana
        self.window = tk.Toplevel(parent)
        self.window.title("Clientes")
        self.window.resizable(True, True)
        centrar_ventana(self.window, 1000, 650)
        self.window.minsize(850, 550)

        # UI
        self.setup_ui()
        self.refresh_clients()
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)



    def manage_credit(self):
        """Abre ventana para gestionar crédito del cliente"""
        if not self.selected_client:
            messagebox.showwarning("Selección requerida",
                                 "Por favor seleccione un cliente")
            return

        # Pasar referencia del main_window
        CreditManagementWindow(self.window, self, self.selected_client, self.main_window)

    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # 1. Frame principal (base para todo)
        main_frame = ttk.Frame(self.window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        self.main_frame = main_frame  # Guardar como atributo si lo necesitas después

        # 2. Título
        ttk.Label(
            main_frame,
            text="👥 GESTIÓN DE CLIENTES",
            font=FONT_TITLE
        ).pack(pady=(0, 20))

        # 3. Frame de controles (búsqueda/botones)
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 15))

        # Botones
        actions = [
            ("➕ Nuevo", self.add_client, "primary"),
            ("✏️ Editar", self.edit_client, "info"),
            ("💰 Crédito", self.manage_credit, "warning"),
            ("📋 Historial", self.view_history, "secondary"),
            ("🗑️ Eliminar", self.delete_client, "danger")
        ]

        for text, cmd, bootstyle in actions:
            ttk.Button(
                controls_frame,
                text=text,
                command=cmd,
                bootstyle=bootstyle
            ).pack(side=tk.LEFT, padx=5)

        # Búsqueda
        ttk.Label(controls_frame, text="🔍 Buscar:").pack(side=tk.LEFT, padx=(20, 5))
        self.search_var = tk.StringVar()
        ttk.Entry(controls_frame, textvariable=self.search_var, width=25).pack(side=tk.LEFT)
        self.search_var.trace_add('write', self.on_search)

        # 4. Frame de estadísticas (empaquetado ANTES que la tabla, con
        # side=BOTTOM, para que reserve su espacio fijo abajo: si se
        # empaqueta después, la tabla con expand=True se come todo el
        # espacio disponible y lo deja en cero, igual que el footer en
        # main_window.py)
        stats_frame = ttk.LabelFrame(main_frame, text="📊 Estadísticas", padding=10)
        stats_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(15, 0))
        self.stats_label = ttk.Label(stats_frame, text="Cargando datos...")
        self.stats_label.pack()

        # 5. Tabla de clientes
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("ID", "Nombre", "Teléfono", "Límite", "Deuda", "Disponible", "Estado")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)

        col_config = {
            "ID": (50, 40, "center"),
            "Nombre": (150, 100, "w"),
            "Teléfono": (100, 80, "center"),
            "Límite": (125, 90, "e"),
            "Deuda": (125, 90, "e"),
            "Disponible": (125, 90, "e"),
            "Estado": (100, 80, "center"),
        }
        for col in columns:
            self.tree.heading(col, text=col)
            width, minwidth, anchor = col_config[col]
            self.tree.column(col, width=width, minwidth=minwidth, anchor=anchor)

        # Scrollbars
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # Configurar eventos
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
    
    def refresh_clients(self):
        """Recarga la lista de clientes"""
        try:
            self.clients = Client.get_all()
            self.populate_tree()
            self.update_statistics()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar clientes: {e}")
    
    # Reemplaza el método populate_tree en la clase ClientsWindow

    def populate_tree(self, clients=None):
        """Llena el treeview con los clientes"""
        # Limpiar árbol
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        clients_to_show = clients if clients is not None else self.clients
        
        # Agregar clientes
        for client in clients_to_show:
            available_credit = client.available_credit()
            
            # CORRECCIÓN: Determinar estado más claro
            if client.total_debt == 0:
                status = "✅ Al día"
                tags = ["good"]
            elif client.total_debt >= client.credit_limit and client.credit_limit > 0:
                status = "❌ Límite"
                tags = ["limit"]
            elif client.total_debt > client.credit_limit * 0.8 and client.credit_limit > 0:
                status = "⚠️ Alerta"
                tags = ["warning"]
            elif client.total_debt > 0:
                status = "⏳ Pendiente"  # Cambio aquí: en lugar de "💳 Crédito"
                tags = ["credit"]
            else:
                status = "✅ Al día"
                tags = ["good"]
            
            self.tree.insert("", "end", values=(
                client.id,
                client.name,
                client.phone or "N/A",
                f"${client.credit_limit:,.2f}",
                f"${client.total_debt:,.2f}",
                f"${available_credit:,.2f}",
                status
            ), tags=tags)
        
        # Configurar colores
        self.tree.tag_configure("good", **ROW_COLORS["success"])
        self.tree.tag_configure("credit", **ROW_COLORS["warning"])  # Amarillo para pendientes
        self.tree.tag_configure("warning", **ROW_COLORS["warning"])
        self.tree.tag_configure("limit", **ROW_COLORS["danger"])
    
    def on_search(self, *args):
        """Filtra clientes por búsqueda"""
        search_term = self.search_var.get().strip()
        
        if not search_term:
            self.populate_tree()
            return
        
        try:
            filtered_clients = Client.search(search_term)
            self.populate_tree(filtered_clients)
        except Exception as e:
            messagebox.showerror("Error", f"Error en la búsqueda: {e}")
    
    def on_select(self, event):
        """Maneja la selección de un cliente"""
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            values = item['values']
            try:
                client_id = values[0]
                self.selected_client = Client.get_by_id(client_id)
            except:
                self.selected_client = None
        else:
            self.selected_client = None
    
    def update_statistics(self):
        """Actualiza las estadísticas"""
        if not self.clients:
            self.stats_label.config(text="No hay clientes registrados")
            return
        
        total_clients = len(self.clients)
        total_debt = sum(client.total_debt for client in self.clients)
        total_credit_limit = sum(client.credit_limit for client in self.clients)
        clients_with_debt = sum(1 for client in self.clients if client.total_debt > 0)
        clients_at_limit = sum(1 for client in self.clients 
                              if client.credit_limit > 0 and client.total_debt >= client.credit_limit)
        
        stats_text = f"Clientes: {total_clients} | "
        stats_text += f"Deuda Total: ${total_debt:,.2f} | "
        stats_text += f"Límite Total: ${total_credit_limit:,.2f} | "
        stats_text += f"Con Deuda: {clients_with_debt} | "
        stats_text += f"En Límite: {clients_at_limit}"
        
        self.stats_label.config(text=stats_text)
    
    def add_client(self):
        """Abre ventana para agregar cliente"""
        ClientFormWindow(self.window, self, mode="add")
    
    def edit_client(self):
        """Abre ventana para editar cliente"""
        if not self.selected_client:
            messagebox.showwarning("Selección requerida", 
                                 "Por favor seleccione un cliente para editar")
            return
        
        ClientFormWindow(self.window, self, mode="edit", client=self.selected_client)
    
    def manage_credit(self):
        """Abre ventana para gestionar crédito del cliente"""
        if not self.selected_client:
            messagebox.showwarning("Selección requerida", 
                                 "Por favor seleccione un cliente")
            return
        
        CreditManagementWindow(self.window, self, self.selected_client)
    
    def view_history(self):
        """Muestra el historial del cliente"""
        if not self.selected_client:
            messagebox.showwarning("Selección requerida", 
                                 "Por favor seleccione un cliente")
            return
        
        ClientHistoryWindow(self.window, self.selected_client)
    
    def delete_client(self):
        """Elimina el cliente seleccionado"""
        if not self.selected_client:
            messagebox.showwarning("Selección requerida", 
                                 "Por favor seleccione un cliente para eliminar")
            return
        
        if self.selected_client.total_debt > 0:
            messagebox.showerror("No se puede eliminar", 
                               f"El cliente '{self.selected_client.name}' tiene una deuda de "
                               f"${self.selected_client.total_debt:,.2f}.\n\n"
                               f"Debe saldar la deuda antes de eliminar el cliente.")
            return
        
        result = messagebox.askyesno("Confirmar eliminación", 
                                   f"¿Está seguro que desea eliminar al cliente:\n"
                                   f"'{self.selected_client.name}'?\n\n"
                                   f"Esta acción no se puede deshacer.")
        
        if result:
            try:
                self.selected_client.delete()
                messagebox.showinfo("Éxito", "Cliente eliminado correctamente")
                self.refresh_clients()
                
            except Exception as e:
                messagebox.showerror("Error", f"Error al eliminar cliente: {e}")
    
    def on_closing(self):
        """Cierra la ventana"""
        self.window.destroy()


class ClientFormWindow:
    def __init__(self, parent, clients_window, mode="add", client=None):
        self.parent = parent
        self.clients_window = clients_window
        self.mode = mode
        self.client = client
        
        # Crear ventana
        self.window = tk.Toplevel(parent)
        title = "Nuevo Cliente" if mode == "add" else "Editar Cliente"
        self.window.title(title)
        self.window.resizable(True, True)
        centrar_ventana(self.window, 550, 600)
        self.window.transient(parent)
        hacer_modal(self.window)

        # Configurar UI
        self.setup_ui()

        # Si es modo edición, cargar datos
        if mode == "edit" and client:
            self.load_client_data()

    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Frame principal
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_text = "➕ Agregar Nuevo Cliente" if self.mode == "add" else "✏️ Editar Cliente"
        title_label = ttk.Label(main_frame, text=title_text, font=FONT_HEADER)
        title_label.pack(pady=(0, 30))
        
        # Formulario
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.X, pady=(0, 30))
        
        # Nombre del cliente
        ttk.Label(form_frame, text="Nombre Completo:*", font=FONT_BOLD).pack(anchor=tk.W, pady=(0, 5))
        self.name_entry = ttk.Entry(form_frame, width=50, font=FONT_NORMAL)
        self.name_entry.pack(fill=tk.X, pady=(0, 15))
        
        # Teléfono
        ttk.Label(form_frame, text="Teléfono:", font=FONT_BOLD).pack(anchor=tk.W, pady=(0, 5))
        self.phone_entry = ttk.Entry(form_frame, width=30, font=FONT_NORMAL)
        self.phone_entry.pack(anchor=tk.W, pady=(0, 15))
        
        # Dirección
        ttk.Label(form_frame, text="Dirección:", font=FONT_BOLD).pack(anchor=tk.W, pady=(0, 5))
        self.address_entry = ttk.Entry(form_frame, width=50, font=FONT_NORMAL)
        self.address_entry.pack(fill=tk.X, pady=(0, 15))
        
        # Límite de crédito
        ttk.Label(form_frame, text="Límite de Crédito:", font=FONT_BOLD).pack(anchor=tk.W, pady=(0, 5))
        
        credit_frame = ttk.Frame(form_frame)
        credit_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(credit_frame, text="$").pack(side=tk.LEFT)
        self.credit_limit_entry = ttk.Entry(credit_frame, width=20, font=FONT_NORMAL)
        self.credit_limit_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.credit_limit_entry.insert(0, "0.00")
        
        # Notas
        ttk.Label(form_frame, text="Notas:", font=FONT_BOLD).pack(anchor=tk.W, pady=(0, 5))
        
        notes_frame = ttk.Frame(form_frame)
        notes_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.notes_text = tk.Text(notes_frame, height=4, font=FONT_NORMAL, wrap=tk.WORD)
        notes_scroll = ttk.Scrollbar(notes_frame, orient="vertical", command=self.notes_text.yview)
        self.notes_text.configure(yscrollcommand=notes_scroll.set)
        
        self.notes_text.pack(side="left", fill="both", expand=True)
        notes_scroll.pack(side="right", fill="y")
        
        # Nota obligatoria
        ttk.Label(form_frame, text="* Campos obligatorios", 
                 font=FONT_SMALL, bootstyle="secondary").pack(anchor=tk.W, pady=(5, 0))
        
        # Botones
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(buttons_frame, text="Cancelar",
                  command=self.cancel, bootstyle="secondary").pack(side=tk.RIGHT, padx=(10, 0))

        save_text = "Guardar Cliente" if self.mode == "add" else "Actualizar Cliente"
        ttk.Button(buttons_frame, text=save_text,
                  command=self.save, bootstyle="primary").pack(side=tk.RIGHT)
        
        # Enfocar en el primer campo
        self.name_entry.focus()
    
    def load_client_data(self):
        """Carga los datos del cliente en modo edición"""
        if self.client:
            self.name_entry.insert(0, self.client.name)
            if self.client.phone:
                self.phone_entry.insert(0, self.client.phone)
            if self.client.address:
                self.address_entry.insert(0, self.client.address)
            
            self.credit_limit_entry.delete(0, tk.END)
            self.credit_limit_entry.insert(0, f"{self.client.credit_limit:.2f}")
            
            if self.client.notes:
                self.notes_text.insert("1.0", self.client.notes)
    
    def save(self):
        """Guarda o actualiza el cliente"""
        # Validar campos
        name = self.name_entry.get().strip()
        phone = self.phone_entry.get().strip()
        address = self.address_entry.get().strip()
        credit_limit_str = self.credit_limit_entry.get().strip()
        notes = self.notes_text.get("1.0", tk.END).strip()
        
        if not name:
            messagebox.showerror("Error", "El nombre del cliente es obligatorio")
            self.name_entry.focus()
            return
        
        try:
            credit_limit = float(credit_limit_str) if credit_limit_str else 0.0
            if credit_limit < 0:
                raise ValueError("El límite de crédito no puede ser negativo")
        except ValueError:
            messagebox.showerror("Error", "Ingrese un límite de crédito válido")
            self.credit_limit_entry.focus()
            return
        
        try:
            if self.mode == "add":
                # Crear nuevo cliente
                client = Client(
                    name=name,
                    phone=phone if phone else None,
                    address=address if address else None,
                    credit_limit=credit_limit,
                    total_debt=0.0,
                    notes=notes if notes else None
                )
                client.save()
                messagebox.showinfo("Éxito", "Cliente agregado correctamente")
                
            else:  # mode == "edit"
                # Actualizar cliente existente
                self.client.name = name
                self.client.phone = phone if phone else None
                self.client.address = address if address else None
                self.client.credit_limit = credit_limit
                self.client.notes = notes if notes else None
                
                self.client.update()
                messagebox.showinfo("Éxito", "Cliente actualizado correctamente")
            
            # Refresh de la ventana padre
            self.clients_window.refresh_clients()
            
            # Cerrar ventana
            self.window.destroy()
            
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                messagebox.showerror("Error", "Ya existe un cliente con ese nombre")
            else:
                messagebox.showerror("Error", f"Error al guardar cliente: {e}")
    
    def cancel(self):
        """Cancela la operación"""
        self.window.destroy()


class CreditManagementWindow:
    def __init__(self, parent, clients_window, client, main_window=None):
        self.parent = parent
        self.clients_window = clients_window
        self.client = client
        self.main_window = main_window  # Nueva referencia
        
        # Crear ventana
        self.window = tk.Toplevel(parent)
        self.window.title(f"Gestión de Crédito - {client.name}")
        centrar_ventana(self.window, 700, 650)
        self.window.minsize(700, 550)   # Tamaño mínimo
        self.window.transient(parent)
        hacer_modal(self.window)

        # Configurar UI
        self.setup_ui()

    def refresh_and_close(self):
        """Actualiza todas las ventanas y cierra esta ventana"""
        # Actualizar ventana de clientes
        self.clients_window.refresh_clients()

        # Actualizar todas las ventanas desde main_window
        if self.main_window:
            self.main_window.refresh_all_windows()

        # Cerrar ventana actual
        self.window.destroy()

    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Frame principal
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, 
                               text=f"💰 GESTIÓN DE CRÉDITO", 
                               font=FONT_HEADER)
        title_label.pack(pady=(0, 10))
        
        client_label = ttk.Label(main_frame, 
                                text=f"Cliente: {self.client.name}", 
                                font=FONT_HEADER)
        client_label.pack(pady=(0, 20))
        
        # Frame de información del cliente
        info_frame = ttk.LabelFrame(main_frame, text="Información del Crédito", padding="15")
        info_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Información en grid
        ttk.Label(info_frame, text="Límite de Crédito:", 
                 font=FONT_BOLD).grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Label(info_frame, text=f"${self.client.credit_limit:,.2f}", 
                 font=FONT_NORMAL).grid(row=0, column=1, sticky=tk.W, padx=(20, 0), pady=2)
        
        ttk.Label(info_frame, text="Deuda Actual:", 
                 font=FONT_BOLD).grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Label(info_frame, text=f"${self.client.total_debt:,.2f}",
                 font=FONT_NORMAL, bootstyle="danger" if self.client.total_debt > 0 else "default").grid(row=1, column=1, sticky=tk.W, padx=(20, 0), pady=2)

        available = self.client.available_credit()
        ttk.Label(info_frame, text="Crédito Disponible:",
                 font=FONT_BOLD).grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Label(info_frame, text=f"${available:,.2f}",
                 font=FONT_NORMAL, bootstyle="success" if available > 0 else "danger").grid(row=2, column=1, sticky=tk.W, padx=(20, 0), pady=2)
        
        # Frame para operaciones
        operations_frame = ttk.LabelFrame(main_frame, text="Operaciones", padding="15")
        operations_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Frame para agregar deuda
        if self.client.available_credit() > 0:
            debt_frame = ttk.Frame(operations_frame)
            debt_frame.pack(fill=tk.X, pady=(0, 15))
            
            ttk.Label(debt_frame, text="Agregar Deuda:", 
                     font=FONT_BOLD).pack(anchor=tk.W)
            
            debt_input_frame = ttk.Frame(debt_frame)
            debt_input_frame.pack(fill=tk.X, pady=(5, 0))
            
            ttk.Label(debt_input_frame, text="Monto: $").pack(side=tk.LEFT)
            self.debt_amount_entry = ttk.Entry(debt_input_frame, width=15)
            self.debt_amount_entry.pack(side=tk.LEFT, padx=(5, 10))
            
            ttk.Label(debt_input_frame, text="Descripción:").pack(side=tk.LEFT, padx=(10, 5))
            self.debt_desc_entry = ttk.Entry(debt_input_frame, width=25)
            self.debt_desc_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
            
            ttk.Button(debt_input_frame, text="Agregar Deuda",
                      command=self.add_debt, bootstyle="warning").pack(side=tk.RIGHT)
        
        # Frame para registrar pago
       # Frame para registrar pago (MODIFICADO)
        if self.client.total_debt > 0:
            payment_frame = ttk.Frame(operations_frame)
            payment_frame.pack(fill=tk.X, pady=(0, 10))
            
            ttk.Label(payment_frame, text="Registrar Pago/Abono:", 
                    font=FONT_BOLD).pack(anchor=tk.W)
            
            payment_input_frame = ttk.Frame(payment_frame)
            payment_input_frame.pack(fill=tk.X, pady=(5, 0))
            
            ttk.Label(payment_input_frame, text="Monto: $").pack(side=tk.LEFT)
            self.payment_amount_entry = ttk.Entry(payment_input_frame, width=15)
            self.payment_amount_entry.pack(side=tk.LEFT, padx=(5, 10))
            
            ttk.Label(payment_input_frame, text="Descripción:").pack(side=tk.LEFT, padx=(10, 5))
            self.payment_desc_entry = ttk.Entry(payment_input_frame, width=25)
            self.payment_desc_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
            
            ttk.Button(payment_input_frame, text="Registrar Pago",
                    command=self.register_payment, bootstyle="success").pack(side=tk.RIGHT)
            
            # Agregar etiqueta informativa
            info_label = ttk.Label(payment_frame, 
                                text="💡 Puede registrar cualquier monto. Si excede la deuda, se creará crédito a favor.",
                                font=FONT_SMALL, bootstyle="secondary")
            info_label.pack(anchor=tk.W, pady=(5, 0))

        
        # Botones inferiores
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(20, 0))
        
        ttk.Button(buttons_frame, text="Ver Historial",
                  command=self.view_history, bootstyle="info").pack(side=tk.LEFT)
        ttk.Button(buttons_frame, text="📄 Estado de cuenta",
                  command=lambda: generar_y_abrir(self.client.id),
                  bootstyle="success").pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(buttons_frame, text="Cerrar",
                  command=self.close_window, bootstyle="secondary").pack(side=tk.RIGHT)
        
    def handle_excess_credit(self, client_id, excess_amount):
        """Maneja el crédito a favor cuando el pago excede la deuda"""
        try:
            from config.database import get_connection
            
            conn = get_connection()
            cursor = conn.cursor()
            
            # Registrar transacción de crédito a favor
            cursor.execute('''
                INSERT INTO client_transactions 
                    (client_id, transaction_type, amount, description, created_at)
                VALUES (?, ?, ?, ?, datetime('now', 'localtime'))
            ''', (client_id, 'credit_balance', excess_amount, 
                f'Crédito a favor por exceso en pago de ${excess_amount:,.2f}'))
            
            conn.commit()
            conn.close()
            
            print(f"💰 Crédito a favor registrado: ${excess_amount:,.2f}")
            
        except Exception as e:
            print(f"Error al registrar crédito a favor: {e}")

    # MÉTODO PARA CONSULTAR CRÉDITO A FAVOR
    def get_client_credit_balance(self, client_id):
        """Obtiene el saldo de crédito a favor del cliente"""
        try:
            from config.database import get_connection
            
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT COALESCE(SUM(
                    CASE 
                        WHEN transaction_type = 'credit_balance' THEN amount
                        WHEN transaction_type = 'credit_used' THEN -amount
                        ELSE 0
                    END
                ), 0) as credit_balance
                FROM client_transactions
                WHERE client_id = ?
            ''', (client_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            return float(result[0]) if result else 0.0
            
        except Exception as e:
            print(f"Error al consultar crédito a favor: {e}")
            return 0.0
    
    def add_debt(self):
        """Agrega deuda al cliente"""
        try:
            amount_str = self.debt_amount_entry.get().strip()
            description = self.debt_desc_entry.get().strip()
            
            if not amount_str:
                messagebox.showerror("Error", "Ingrese el monto de la deuda")
                return
            
            if not description:
                messagebox.showerror("Error", "Ingrese una descripción")
                return
            
            amount = float(amount_str)
            if amount <= 0:
                messagebox.showerror("Error", "El monto debe ser mayor a cero")
                return
            
            if amount > self.client.available_credit():
                messagebox.showerror("Error", 
                                   f"El monto excede el crédito disponible\n"
                                   f"Disponible: ${self.client.available_credit():,.2f}")
                return
            
            # Confirmar operación
            result = messagebox.askyesno("Confirmar", 
                                       f"¿Agregar deuda de ${amount:,.2f}?\n"
                                       f"Descripción: {description}")
            
            if result:
                self.client.add_debt(amount, description)
                messagebox.showinfo("Éxito", "Deuda agregada correctamente")
                self.refresh_and_close()
                
        except ValueError:
            messagebox.showerror("Error", "Ingrese un monto válido")
    
    # En CreditManagementWindow, modifica el método register_payment:

    def add_debt(self):
        """Agrega deuda al cliente"""
        try:
            amount_str = self.debt_amount_entry.get().strip()
            description = self.debt_desc_entry.get().strip()
            
            if not amount_str:
                messagebox.showerror("Error", "Ingrese el monto de la deuda")
                return
            
            if not description:
                messagebox.showerror("Error", "Ingrese una descripción")
                return
            
            amount = float(amount_str)
            if amount <= 0:
                messagebox.showerror("Error", "El monto debe ser mayor a cero")
                return
            
            if amount > self.client.available_credit():
                messagebox.showerror("Error", 
                                f"El monto excede el crédito disponible\n"
                                f"Disponible: ${self.client.available_credit():,.2f}")
                return
            
            # Confirmar operación
            result = messagebox.askyesno("Confirmar", 
                                    f"¿Agregar deuda de ${amount:,.2f}?\n"
                                    f"Descripción: {description}")
            
            if result:
                self.client.add_debt(amount, description)
                messagebox.showinfo("Éxito", "Deuda agregada correctamente")
                self.refresh_and_close()
                
        except ValueError:
            messagebox.showerror("Error", "Ingrese un monto válido")

    def register_payment(self):
        """Registra un pago del cliente aplicándolo directamente a ventas específicas - VERSIÓN CORREGIDA"""
        try:
            # Obtener y validar datos de entrada
            amount_str = self.payment_amount_entry.get().strip()
            description = self.payment_desc_entry.get().strip()
            
            # Validaciones básicas
            if not amount_str:
                messagebox.showerror("Error", "Ingrese el monto del pago")
                self.payment_amount_entry.focus()
                return
                
            if not description:
                messagebox.showerror("Error", "Ingrese una descripción")
                self.payment_desc_entry.focus()
                return
            
            # Convertir y validar monto
            try:
                amount = float(amount_str)
            except ValueError:
                messagebox.showerror("Error", "Ingrese un monto válido (solo números)")
                self.payment_amount_entry.focus()
                return
            
            if amount <= 0:
                messagebox.showerror("Error", "El monto debe ser mayor a cero")
                self.payment_amount_entry.focus()
                return
            
            # CORRECCIÓN 1: Refrescar datos del cliente desde la BD
            self.client = Client.get_by_id(self.client.id)
            deuda_actual = self.client.total_debt
            
            # Mostrar preview de cómo se aplicará el pago
            preview = self.show_payment_allocation_preview(amount)
            
            # Mensaje de confirmación detallado
            if amount > deuda_actual:
                exceso = amount - deuda_actual
                mensaje_confirmacion = (
                    f"💰 PAGO MAYOR A LA DEUDA\n\n"
                    f"👤 Cliente: {self.client.name}\n"
                    f"💳 Deuda actual: ${deuda_actual:,.2f}\n"
                    f"💰 Pago recibido: ${amount:,.2f}\n"
                    f"💵 Exceso del pago: ${exceso:,.2f}\n\n"
                    f"DISTRIBUCIÓN DEL PAGO:\n"
                    f"{preview}\n\n"
                    f"✅ La deuda se saldará COMPLETAMENTE\n"
                    f"⚠️ El exceso se registrará como crédito a favor\n\n"
                    f"📝 Descripción: {description}\n\n"
                    f"¿Desea procesar este pago?"
                )
            elif amount == deuda_actual:
                mensaje_confirmacion = (
                    f"✅ PAGO EXACTO - SALDA DEUDA\n\n"
                    f"👤 Cliente: {self.client.name}\n"
                    f"💳 Deuda actual: ${deuda_actual:,.2f}\n"
                    f"💰 Pago recibido: ${amount:,.2f}\n\n"
                    f"DISTRIBUCIÓN DEL PAGO:\n"
                    f"{preview}\n\n"
                    f"✅ La deuda se saldará COMPLETAMENTE\n\n"
                    f"📝 Descripción: {description}\n\n"
                    f"¿Desea procesar este pago?"
                )
            else:
                saldo_restante = deuda_actual - amount
                mensaje_confirmacion = (
                    f"💳 ABONO PARCIAL\n\n"
                    f"👤 Cliente: {self.client.name}\n"
                    f"💳 Deuda actual: ${deuda_actual:,.2f}\n"
                    f"💰 Abono: ${amount:,.2f}\n"
                    f"💳 Saldo restante: ${saldo_restante:,.2f}\n\n"
                    f"DISTRIBUCIÓN DEL ABONO:\n"
                    f"{preview}\n\n"
                    f"📝 Descripción: {description}\n\n"
                    f"¿Desea procesar este abono?"
                )
            
            # Confirmar operación
            result = messagebox.askyesno("Confirmar Pago", mensaje_confirmacion)
            
            if result:
                # Pago, crédito a favor y estado de las ventas en un solo
                # guardado (ver servicios/abonos.py)
                success = False
                conn = get_connection()
                try:
                    self.window.config(cursor="watch")
                    self.window.update_idletasks()
                    resumen = registrar_abono(conn, self.client.id, amount, description)
                    conn.commit()
                    success = True
                    debt_reduced, excess_amount = resumen["aplicado"], resumen["exceso"]
                except Exception as e:
                    conn.rollback()
                    print(f"Error al registrar el pago: {e}")
                finally:
                    self.window.config(cursor="")
                    conn.close()

                if success:
                    # Limpiar campos
                    self.payment_amount_entry.delete(0, tk.END)
                    self.payment_desc_entry.delete(0, tk.END)
                    
                    # Mostrar mensaje de éxito
                    self.show_simple_payment_success(amount, deuda_actual, debt_reduced, excess_amount)
                    
                    # CORRECCIÓN 4: Refrescar todas las ventanas
                    self.refresh_and_close()
                else:
                    messagebox.showerror("Error", "Error al procesar el pago")
                    
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error inesperado:\n{str(e)}")
            print(f"❌ Error en register_payment: {e}")

    def process_complete_payment(self, payment_amount, description):
        """
        Procesa un pago completo: actualiza ventas, cliente y transacciones - VERSIÓN CORREGIDA
        """
        from config.database import get_connection
        from datetime import datetime
        
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            print(f"\n💰 PROCESANDO PAGO COMPLETO: ${payment_amount:,.2f}")
            print("=" * 60)
            
            # PASO 1: Detectar estructura de la tabla sales
            cursor.execute("PRAGMA table_info(sales)")
            table_info = cursor.fetchall()
            column_names = [column[1] for column in table_info]
            
            if 'payment_status' in column_names:
                status_column = 'payment_status'
            elif 'status' in column_names:
                status_column = 'status'
            else:
                return {'success': False, 'error': 'No se encontró columna de estado en sales'}
            
            print(f"📊 Usando columna de estado: '{status_column}'")
            
            # PASO 2: Obtener ventas pendientes ordenadas cronológicamente
            query = f'''
                SELECT id, total, created_at, notes
                FROM sales 
                WHERE client_id = ? AND {status_column} = 'pending'
                ORDER BY datetime(created_at) ASC
            '''
            
            cursor.execute(query, (self.client.id,))
            pending_sales = cursor.fetchall()
            
            print(f"📋 Ventas pendientes encontradas: {len(pending_sales)}")
            
            if not pending_sales:
                print("ℹ️ No hay ventas pendientes")
                if payment_amount > 0:
                    cursor.execute('''
                        INSERT INTO client_transactions 
                        (client_id, transaction_type, amount, description, created_at)
                        VALUES (?, 'credit', ?, ?, datetime('now', 'localtime'))
                    ''', (self.client.id, payment_amount, f"{description} - Crédito a favor"))
                    
                    print(f"💵 Registrado como crédito a favor: ${payment_amount:,.2f}")
                
                conn.commit()
                return {
                    'success': True, 
                    'sales_paid_complete': 0,
                    'sales_paid_partial': 0,
                    'excess_credit': payment_amount
                }
            
            # PASO 3: Aplicar el pago a las ventas
            remaining_payment = payment_amount
            updated_sales = []
            sales_paid_complete = 0
            sales_paid_partial = 0
            total_debt_reduced = 0
            
            for sale in pending_sales:
                if remaining_payment <= 0:
                    break
                    
                sale_id = sale[0]
                sale_total = float(sale[1])
                sale_date = sale[2]
                sale_notes = sale[3] or ""
                
                print(f"\n📄 Procesando Venta #{sale_id}")
                print(f"   💰 Debe: ${sale_total:,.2f}")
                print(f"   💳 Pago disponible: ${remaining_payment:,.2f}")
                
                if remaining_payment >= sale_total:
                    # ✅ PAGO COMPLETO - Marcar como pagada
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                    updated_notes = f"{sale_notes} [PAGADA el {timestamp}]".strip()
                    
                    # *** CORRECCIÓN: Sin updated_at ***
                    update_query = f'''
                        UPDATE sales 
                        SET {status_column} = 'paid',
                            notes = ?
                        WHERE id = ?
                    '''
                    cursor.execute(update_query, (updated_notes, sale_id))
                    
                    remaining_payment -= sale_total
                    total_debt_reduced += sale_total
                    sales_paid_complete += 1
                    
                    print(f"   ✅ PAGADA COMPLETAMENTE")
                    print(f"   💰 Pago restante: ${remaining_payment:,.2f}")
                    
                else:
                    # ⚠️ PAGO PARCIAL - Actualizar monto pendiente
                    paid_amount = remaining_payment
                    new_debt = sale_total - paid_amount
                    
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                    updated_notes = f"{sale_notes} [Abono ${paid_amount:,.2f} el {timestamp} - Saldo: ${new_debt:,.2f}]".strip()
                    
                    # *** CORRECCIÓN: Sin updated_at ***
                    # El total de la venta NO se toca: es lo que se vendió.
                    # El abono se registra en paid_amount y remaining_debt.
                    update_query = f'''
                        UPDATE sales 
                        SET paid_amount = COALESCE(paid_amount, 0) + ?,
                            remaining_debt = ?,
                            notes = ?
                        WHERE id = ?
                    '''
                    cursor.execute(update_query, (paid_amount, new_debt, updated_notes, sale_id))
                    
                    total_debt_reduced += paid_amount
                    sales_paid_partial += 1
                    
                    print(f"   ⚠️ PAGO PARCIAL")
                    print(f"   💳 Abono: ${paid_amount:,.2f}")
                    print(f"   📊 Saldo pendiente: ${new_debt:,.2f}")
                    
                    remaining_payment = 0  # Se agotó el pago
            
            # PASO 4: Actualizar deuda del cliente - SIN updated_at
            cursor.execute('''
                UPDATE clients 
                SET total_debt = MAX(0, total_debt - ?)
                WHERE id = ?
            ''', (total_debt_reduced, self.client.id))
            
            print(f"\n💳 Deuda reducida en: ${total_debt_reduced:,.2f}")
            
            # PASO 5: Registrar transacción de pago
            cursor.execute('''
                INSERT INTO client_transactions 
                (client_id, transaction_type, amount, description, created_at)
                VALUES (?, 'credit', ?, ?, datetime('now', 'localtime'))
            ''', (self.client.id, total_debt_reduced, description))
            
            # PASO 6: Manejar exceso como crédito a favor
            excess_credit = 0
            if remaining_payment > 0:
                excess_credit = remaining_payment
                cursor.execute('''
                    INSERT INTO client_transactions 
                    (client_id, transaction_type, amount, description, created_at)
                    VALUES (?, 'credit_balance', ?, ?, datetime('now', 'localtime'))
                ''', (self.client.id, excess_credit, f"Crédito a favor por exceso en pago"))
                
                print(f"💵 Exceso registrado como crédito: ${excess_credit:,.2f}")
            
            # PASO 7: Confirmar todos los cambios
            conn.commit()
            
            print(f"\n🎯 RESUMEN FINAL:")
            print("=" * 50)
            print(f"💰 Pago procesado: ${payment_amount:,.2f}")
            print(f"💳 Aplicado a deuda: ${total_debt_reduced:,.2f}")
            print(f"✅ Ventas pagadas completamente: {sales_paid_complete}")
            print(f"⚠️ Ventas con abono parcial: {sales_paid_partial}")
            print(f"💵 Crédito a favor: ${excess_credit:,.2f}")
            
            return {
                'success': True,
                'total_updated': len(updated_sales),
                'sales_paid_complete': sales_paid_complete,
                'sales_paid_partial': sales_paid_partial,
                'debt_reduced': total_debt_reduced,
                'excess_credit': excess_credit
            }
            
        except Exception as e:
            error_msg = f"Error al procesar pago completo: {e}"
            print(f"❌ {error_msg}")
            if conn:
                conn.rollback()
            return {'success': False, 'error': error_msg}
        finally:
            if conn:
                conn.close()


    def show_payment_success_message(self, amount, deuda_anterior, resultado):
        """Muestra mensaje de éxito del pago con información detallada"""
        try:
            # Refrescar cliente desde BD para obtener nueva deuda
            self.client = Client.get_by_id(self.client.id)
            deuda_nueva = self.client.total_debt
            exceso = resultado.get('excess_credit', 0)
            
            if deuda_nueva <= 0 and deuda_anterior > 0:
                # Deuda saldada completamente
                if exceso > 0:
                    mensaje = (
                        f"🎉 ¡DEUDA SALDADA COMPLETAMENTE!\n\n"
                        f"💰 Pago recibido: ${amount:,.2f}\n"
                        f"💳 Deuda anterior: ${deuda_anterior:,.2f}\n"
                        f"💵 Crédito a favor: ${exceso:,.2f}\n\n"
                        f"✅ Ventas pagadas: {resultado.get('sales_paid_complete', 0)}\n"
                        f"⚠️ Abonos parciales: {resultado.get('sales_paid_partial', 0)}\n\n"
                        f"🎯 El cliente está al día y tiene crédito a favor."
                    )
                else:
                    mensaje = (
                        f"🎉 ¡DEUDA SALDADA EXACTAMENTE!\n\n"
                        f"💰 Pago recibido: ${amount:,.2f}\n"
                        f"💳 Deuda anterior: ${deuda_anterior:,.2f}\n\n"
                        f"✅ Ventas pagadas: {resultado.get('sales_paid_complete', 0)}\n"
                        f"⚠️ Abonos parciales: {resultado.get('sales_paid_partial', 0)}\n\n"
                        f"🎯 El cliente está completamente al día."
                    )
            else:
                # Abono parcial
                mensaje = (
                    f"💳 ABONO REGISTRADO EXITOSAMENTE\n\n"
                    f"💰 Abono recibido: ${amount:,.2f}\n"
                    f"💳 Deuda anterior: ${deuda_anterior:,.2f}\n"
                    f"💳 Saldo actual: ${deuda_nueva:,.2f}\n\n"
                    f"✅ Ventas pagadas: {resultado.get('sales_paid_complete', 0)}\n"
                    f"⚠️ Abonos parciales: {resultado.get('sales_paid_partial', 0)}\n\n"
                    f"📊 Progreso del pago registrado correctamente."
                )
            
            messagebox.showinfo("Pago Procesado", mensaje)
            
        except Exception as e:
            messagebox.showinfo("Éxito", f"Pago de ${amount:,.2f} procesado correctamente")
            print(f"Error en mensaje de éxito: {e}")


    def process_payment_to_sales_exact(self, payment_amount):
        """Procesa el pago aplicándolo exactamente a las ventas pendientes"""
        try:
            from config.database import get_connection
            from datetime import datetime
            
            conn = get_connection()
            cursor = conn.cursor()
            
            print(f"\n🏦 PROCESANDO PAGO EXACTO: ${payment_amount:,.2f} para {self.client.name}")
            print("=" * 70)
            
            # PASO 1: Detectar estructura de la tabla
            cursor.execute("PRAGMA table_info(sales)")
            table_info = cursor.fetchall()
            column_names = [column[1] for column in table_info]
            
            if 'payment_status' in column_names:
                status_column = 'payment_status'
            elif 'status' in column_names:
                status_column = 'status'
            else:
                print("❌ ERROR: No se encontró columna de estado")
                conn.close()
                return {'total_updated': 0, 'sales_updated': [], 'error': 'No status column'}
            
            print(f"📊 Usando columna de estado: '{status_column}'")
            
            # PASO 2: Obtener ventas pendientes ordenadas cronológicamente
            query = f'''
                SELECT id, total, created_at, notes
                FROM sales 
                WHERE client_id = ? AND {status_column} = 'pending'
                ORDER BY datetime(created_at) ASC
            '''
            
            cursor.execute(query, (self.client.id,))
            pending_sales = cursor.fetchall()
            
            print(f"📋 Ventas pendientes: {len(pending_sales)}")
            
            if not pending_sales:
                print("ℹ️ No hay ventas pendientes - Pago aplicado como abono general")
                conn.close()
                return {'total_updated': 0, 'sales_updated': [], 'message': 'No pending sales'}
            
            # Mostrar ventas antes del procesamiento
            total_pending = 0
            for i, sale in enumerate(pending_sales, 1):
                sale_total = float(sale[1])
                total_pending += sale_total
                print(f"   {i}. Venta #{sale[0]}: ${sale_total:,.2f} ({sale[2][:19]})")
            
            print(f"💰 Total pendiente en ventas: ${total_pending:,.2f}")
            print(f"💳 Pago exacto a aplicar: ${payment_amount:,.2f}")
            
            # PASO 3: Aplicar el pago exactamente a las ventas
            remaining_payment = payment_amount
            updated_sales = []
            sales_paid_complete = 0
            sales_paid_partial = 0
            
            for sale in pending_sales:
                if remaining_payment <= 0:
                    print(f"   ⏹️ Pago agotado, ventas restantes sin cambios")
                    break
                    
                sale_id = sale[0]
                sale_total = float(sale[1])
                sale_date = sale[2]
                sale_notes = sale[3] or ""
                
                print(f"\n🔄 Procesando Venta #{sale_id}")
                print(f"   💰 Debe actualmente: ${sale_total:,.2f}")
                print(f"   💳 Pago disponible: ${remaining_payment:,.2f}")
                
                if remaining_payment >= sale_total:
                    # ✅ PAGO COMPLETO - Marcar como pagada
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                    updated_notes = f"{sale_notes} [PAGADA el {timestamp}]".strip()
                    
                    update_query = f'''
                        UPDATE sales 
                        SET {status_column} = 'paid',
                            notes = ?,
                            updated_at = datetime('now', 'localtime')
                        WHERE id = ?
                    '''
                    cursor.execute(update_query, (updated_notes, sale_id))
                    
                    remaining_payment -= sale_total
                    sales_paid_complete += 1
                    
                    updated_sales.append({
                        'id': sale_id,
                        'original_amount': sale_total,
                        'amount_paid': sale_total,
                        'remaining_debt': 0,
                        'status': 'paid_complete',
                        'date': sale_date[:19]
                    })
                    
                    print(f"   ✅ PAGADA COMPLETAMENTE")
                    print(f"   💰 Pago restante: ${remaining_payment:,.2f}")
                    
                else:
                    # ⚠️ PAGO PARCIAL - Actualizar monto pendiente
                    paid_amount = remaining_payment
                    new_debt = sale_total - paid_amount
                    
                    print(f"   ⚠️ PAGO PARCIAL")
                    print(f"   💳 Abono: ${paid_amount:,.2f}")
                    print(f"   📊 Saldo pendiente: ${new_debt:,.2f}")
                    
                    # Actualizar la venta con el nuevo saldo pendiente
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                    updated_notes = f"{sale_notes} [Abono ${paid_amount:,.2f} el {timestamp} - Saldo: ${new_debt:,.2f}]".strip()
                    
                    # El total de la venta NO se toca: es lo que se vendió.
                    # El abono se registra en paid_amount y remaining_debt.
                    update_query = f'''
                        UPDATE sales 
                        SET paid_amount = COALESCE(paid_amount, 0) + ?,
                            remaining_debt = ?,
                            notes = ?,
                            updated_at = datetime('now', 'localtime')
                        WHERE id = ?
                    '''
                    cursor.execute(update_query, (paid_amount, new_debt, updated_notes, sale_id))
                    
                    sales_paid_partial += 1
                    
                    updated_sales.append({
                        'id': sale_id,
                        'original_amount': sale_total,
                        'amount_paid': paid_amount,
                        'remaining_debt': new_debt,
                        'status': 'paid_partial',
                        'date': sale_date[:19]
                    })
                    
                    remaining_payment = 0  # Se agotó el pago exactamente
                    print(f"   💳 Pago agotado exactamente")
            
            # PASO 4: Confirmar todos los cambios
            conn.commit()
            conn.close()
            
            # PASO 5: Resumen final
            print(f"\n🎯 RESUMEN FINAL:")
            print("=" * 50)
            print(f"💰 Pago procesado: ${payment_amount:,.2f}")
            print(f"✅ Ventas pagadas completamente: {sales_paid_complete}")
            print(f"⚠️ Ventas con abono parcial: {sales_paid_partial}")
            print(f"📊 Total ventas afectadas: {len(updated_sales)}")
            print(f"💳 Pago restante: ${remaining_payment:,.2f} (debe ser $0.00)")
            
            if remaining_payment > 0.01:  # Tolerancia para decimales
                print(f"⚠️ ADVERTENCIA: Quedó pago sin aplicar: ${remaining_payment:,.2f}")
            
            return {
                'total_updated': len(updated_sales),
                'sales_updated': updated_sales,
                'sales_paid_complete': sales_paid_complete,
                'sales_paid_partial': sales_paid_partial,
                'remaining_payment': remaining_payment,
                'status_column_used': status_column
            }
            
        except Exception as e:
            error_msg = f"Error al procesar pago exacto: {e}"
            print(f"❌ {error_msg}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return {'total_updated': 0, 'sales_updated': [], 'error': error_msg}
        
    # Agregar estos dos métodos a la clase CreditManagementWindow

    def update_sales_status_after_payment(self, payment_amount):
        """Actualiza el estado de las ventas después de un pago"""
        try:
            from config.database import get_connection
            from datetime import datetime
            
            # Refrescar datos del cliente
            self.client = Client.get_by_id(self.client.id)
            
            # Si el cliente no tiene deuda, marcar todas las ventas pendientes como pagadas
            if self.client.total_debt <= 0:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Detectar columna de estado
                cursor.execute("PRAGMA table_info(sales)")
                table_info = cursor.fetchall()
                column_names = [column[1] for column in table_info]
                
                status_column = 'payment_status' if 'payment_status' in column_names else 'status'
                
                # Marcar ventas pendientes como pagadas
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                
                update_query = f'''
                    UPDATE sales 
                    SET {status_column} = 'paid',
                        notes = COALESCE(notes, '') || ' [SALDADA el {timestamp}]'
                    WHERE client_id = ? AND {status_column} = 'pending'
                '''
                cursor.execute(update_query, (self.client.id,))
                
                conn.commit()
                conn.close()
                    
        except Exception as e:
            print(f"Error al actualizar ventas: {e}")

    def show_simple_payment_success(self, amount, deuda_anterior, debt_reduced, excess_amount):
        """Muestra mensaje de éxito simplificado"""
        if debt_reduced >= deuda_anterior and deuda_anterior > 0:
            if excess_amount > 0:
                mensaje = (f"🎉 ¡DEUDA SALDADA!\n\n"
                        f"💰 Pago: ${amount:,.2f}\n"
                        f"💳 Deuda saldada: ${debt_reduced:,.2f}\n"
                        f"💵 Crédito a favor: ${excess_amount:,.2f}")
            else:
                mensaje = (f"🎉 ¡DEUDA SALDADA!\n\n"
                        f"💰 Pago: ${amount:,.2f}")
        else:
            nueva_deuda = deuda_anterior - debt_reduced
            mensaje = (f"💳 ABONO REGISTRADO\n\n"
                    f"💰 Abono: ${amount:,.2f}\n"
                    f"💳 Saldo actual: ${nueva_deuda:,.2f}")
        
        messagebox.showinfo("Pago Procesado", mensaje)

    def update_sales_payment_status(self, payment_amount):
        """Actualiza el estado de las ventas pendientes a 'paid' basándose en el pago"""
        try:
            from config.database import get_connection
            
            conn = get_connection()
            cursor = conn.cursor()
            
            # Obtener ventas pendientes ordenadas por fecha
            cursor.execute('''
                SELECT id, total, created_at 
                FROM sales 
                WHERE client_id = ? AND status = 'pending'
                ORDER BY created_at ASC
            ''', (self.client.id,))
            
            pending_sales = cursor.fetchall()
            
            if not pending_sales:
                conn.close()
                return {'total_updated': 0, 'sales_updated': []}
            
            remaining_payment = payment_amount
            updated_sales = []
            
            # Procesar cada venta pendiente
            for sale in pending_sales:
                if remaining_payment <= 0:
                    break
                    
                sale_id = sale[0]
                sale_total = float(sale[1])
                
                if remaining_payment >= sale_total:
                    # Pago completo de esta venta
                    cursor.execute('''
                        UPDATE sales 
                        SET status = 'paid', updated_at = datetime('now', 'localtime')
                        WHERE id = ?
                    ''', (sale_id,))
                    
                    remaining_payment -= sale_total
                    updated_sales.append({
                        'id': sale_id,
                        'amount_paid': sale_total,
                        'status': 'paid_complete'
                    })
                    
                    print(f"✅ Venta #{sale_id} marcada como 'paid' - Monto: ${sale_total:,.2f}")
                    
                else:
                    # Pago parcial
                    paid_amount = remaining_payment
                    remaining_amount = sale_total - paid_amount
                    
                    # Antes esto partía la venta en dos: dejaba la original con
                    # el monto abonado marcada como pagada y creaba otra venta
                    # por el resto. Esa venta nueva nacía sin líneas de detalle,
                    # falseando el conteo de ventas y el costo de lo vendido.
                    # Ahora la venta se queda como está y el abono se anota.
                    cursor.execute('''
                        UPDATE sales 
                        SET paid_amount = COALESCE(paid_amount, 0) + ?,
                            remaining_debt = ?,
                            updated_at = datetime('now', 'localtime')
                        WHERE id = ?
                    ''', (paid_amount, remaining_amount, sale_id))
                    
                    updated_sales.append({
                        'id': sale_id,
                        'amount_paid': paid_amount,
                        'remaining': remaining_amount,
                        'status': 'paid_partial'
                    })
                    
                    remaining_payment = 0
                    print(f"⚠️ Venta #{sale_id} pago parcial - Pagado: ${paid_amount:,.2f}, Restante: ${remaining_amount:,.2f}")
            
            # Confirmar cambios
            conn.commit()
            conn.close()
            
            print(f"🔄 Total de ventas actualizadas: {len(updated_sales)}")
            
            return {
                'total_updated': len(updated_sales),
                'sales_updated': updated_sales,
                'remaining_payment': remaining_payment
            }
            
        except Exception as e:
            print(f"❌ Error al actualizar estado de ventas: {e}")
            if conn:
                conn.rollback()
                conn.close()
            return {'total_updated': 0, 'sales_updated': [], 'error': str(e)}



    def update_pending_sales_to_paid(self):
        """Actualiza las ventas pendientes a pagadas cuando la deuda se salda"""
        try:
            from config.database import get_connection
            
            conn = get_connection()
            cursor = conn.cursor()
            
            # Si el cliente no tiene deuda restante, marcar todas las ventas pendientes como pagadas
            if self.client.total_debt == 0:
                cursor.execute('''
                    UPDATE sales 
                    SET payment_status = 'paid', 
                        updated_at = CURRENT_TIMESTAMP
                    WHERE client_id = ? AND payment_status = 'pending'
                ''', (self.client.id,))
                
                updated_sales = cursor.rowcount
                conn.commit()
                
                if updated_sales > 0:
                    print(f"✅ {updated_sales} ventas marcadas como pagadas para el cliente {self.client.name}")
            
            conn.close()
            
        except Exception as e:
            print(f"Error al actualizar ventas pendientes: {e}")
            # No mostrar error al usuario, es un proceso interno

    # Agregar estos métodos a la clase CreditManagementWindow

    def get_pending_sales(self):
        """Obtiene las ventas pendientes del cliente - VERSIÓN CORREGIDA"""
        try:
            from config.database import get_connection
            
            conn = get_connection()
            cursor = conn.cursor()
            
            # CORRECCIÓN: Usar los nombres correctos de columnas
            cursor.execute('''
                SELECT id, total, created_at, notes
                FROM sales 
                WHERE client_id = ? AND status = 'pending'
                ORDER BY created_at ASC
            ''', (self.client.id,))
            
            # Convertir a diccionarios para fácil acceso
            columns = [description[0] for description in cursor.description]
            pending_sales = []
            
            for row in cursor.fetchall():
                sale_dict = dict(zip(columns, row))
                pending_sales.append(sale_dict)
            
            conn.close()
            
            print(f"📊 Ventas pendientes encontradas: {len(pending_sales)}")
            for sale in pending_sales:
                print(f"   - Venta #{sale['id']}: ${sale['total']:,.2f}")
            
            return pending_sales
            
        except Exception as e:
            print(f"Error al obtener ventas pendientes: {e}")
            return []

    def mark_specific_sales_as_paid(self, payment_amount):
        """Marca ventas específicas como pagadas basándose en el monto del pago"""
        try:
            from config.database import get_connection
            
            pending_sales = self.get_pending_sales()
            if not pending_sales:
                return []
            
            conn = get_connection()
            cursor = conn.cursor()
            
            remaining_payment = payment_amount
            updated_sales = []
            
            for sale in pending_sales:
                if remaining_payment <= 0:
                    break
                    
                sale_total = sale['total']  # Usar 'total' en lugar de 'total_amount'
                
                if remaining_payment >= sale_total:
                    cursor.execute('''
                        UPDATE sales 
                        SET status = 'paid'
                        WHERE id = ?
                    ''', (sale['id'],))
                    
                    remaining_payment -= sale_total
                    updated_sales.append({
                        'id': sale['id'],
                        'amount': sale_total,
                        'date': sale['created_at'],
                        'status': 'paid_complete'
                    })
                else:
                    paid_amount = remaining_payment
                    remaining_amount = sale_total - paid_amount
                    
                    # La venta conserva su total y su estado pendiente; el
                    # abono queda anotado. Antes se partía en dos y la mitad
                    # nueva nacía sin líneas de detalle.
                    cursor.execute('''
                        UPDATE sales 
                        SET paid_amount = COALESCE(paid_amount, 0) + ?,
                            remaining_debt = ?
                        WHERE id = ?
                    ''', (paid_amount, remaining_amount, sale['id']))
                    
                    updated_sales.append({
                        'id': sale['id'],
                        'amount': paid_amount,
                        'date': sale['created_at'],
                        'status': 'paid_partial',
                        'remaining': remaining_amount
                    })
                    
                    remaining_payment = 0
            
            conn.commit()
            conn.close()
            
            return updated_sales
            
        except Exception as e:
            print(f"Error al marcar ventas específicas como pagadas: {e}")
            return []

    def show_payment_allocation_preview(self, amount):
        """Muestra cómo se distribuirá el pago entre las ventas pendientes"""
        try:
            from config.database import get_connection
            
            conn = get_connection()
            cursor = conn.cursor()
            
            # Detectar columna de estado
            cursor.execute("PRAGMA table_info(sales)")
            table_info = cursor.fetchall()
            column_names = [column[1] for column in table_info]
            
            status_column = 'payment_status' if 'payment_status' in column_names else 'status'
            
            # Obtener ventas pendientes
            cursor.execute(f'''
                SELECT id, total, created_at
                FROM sales 
                WHERE client_id = ? AND {status_column} = 'pending'
                ORDER BY datetime(created_at) ASC
            ''', (self.client.id,))
            
            pending_sales = cursor.fetchall()
            conn.close()
            
            if not pending_sales:
                if amount > 0:
                    return f"💵 Todo el pago (${amount:,.2f}) se registrará como crédito a favor"
                return "No hay ventas pendientes"
            
            allocation_text = ""
            remaining_payment = amount
            total_debt = sum(float(sale[1]) for sale in pending_sales)
            
            for i, sale in enumerate(pending_sales, 1):
                if remaining_payment <= 0:
                    allocation_text += f"⏸️ Venta #{sale[0]}: ${sale[1]:,.2f} - SIN CAMBIOS\n"
                    continue
                    
                sale_total = float(sale[1])
                sale_date = sale[2][:16]
                
                if remaining_payment >= sale_total:
                    allocation_text += f"✅ Venta #{sale[0]} ({sale_date}): ${sale_total:,.2f} - PAGADA COMPLETA\n"
                    remaining_payment -= sale_total
                else:
                    saldo = sale_total - remaining_payment
                    allocation_text += f"⚠️ Venta #{sale[0]} ({sale_date}): Abono ${remaining_payment:,.2f}, Saldo ${saldo:,.2f}\n"
                    remaining_payment = 0
            
            # Agregar información del exceso si lo hay
            if amount > total_debt:
                exceso = amount - total_debt
                allocation_text += f"\n💵 Exceso como crédito: ${exceso:,.2f}"
            
            return allocation_text.strip()
            
        except Exception as e:
            return f"Error al calcular distribución: {e}"
    
    def process_payment_with_accumulation(self, payment_amount):
        """Procesa el pago aplicándolo exactamente a las ventas pendientes"""
        try:
            from config.database import get_connection
            from datetime import datetime
            
            conn = get_connection()
            cursor = conn.cursor()
            
            print(f"\n💰 PROCESANDO PAGO CON ACUMULACIÓN: ${payment_amount:,.2f}")
            print("=" * 60)
            
            # PASO 1: Detectar estructura de la tabla
            cursor.execute("PRAGMA table_info(sales)")
            table_info = cursor.fetchall()
            column_names = [column[1] for column in table_info]
            
            if 'payment_status' in column_names:
                status_column = 'payment_status'
            elif 'status' in column_names:
                status_column = 'status'
            else:
                print("❌ ERROR: No se encontró columna de estado")
                conn.close()
                return {'error': 'No status column found'}
            
            print(f"📊 Usando columna de estado: '{status_column}'")
            
            # PASO 2: Obtener ventas pendientes ordenadas cronológicamente
            query = f'''
                SELECT id, total, created_at, notes
                FROM sales 
                WHERE client_id = ? AND {status_column} = 'pending'
                ORDER BY datetime(created_at) ASC
            '''
            
            cursor.execute(query, (self.client.id,))
            pending_sales = cursor.fetchall()
            
            print(f"📋 Ventas pendientes encontradas: {len(pending_sales)}")
            
            if not pending_sales:
                print("ℹ️ No hay ventas pendientes")
                # Si hay pago y no hay ventas pendientes, registrar como crédito a favor
                if payment_amount > 0:
                    self.handle_excess_credit(self.client.id, payment_amount)
                conn.close()
                return {'message': 'No pending sales', 'excess_credit': payment_amount}
            
            # PASO 3: Mostrar estado inicial
            total_pending = sum(float(sale[1]) for sale in pending_sales)
            print(f"💳 Total pendiente en ventas: ${total_pending:,.2f}")
            print(f"💰 Pago a aplicar: ${payment_amount:,.2f}")
            
            for i, sale in enumerate(pending_sales, 1):
                print(f"   {i}. Venta #{sale[0]}: ${float(sale[1]):,.2f} ({sale[2][:19]})")
            
            # PASO 4: Procesar el pago exactamente
            remaining_payment = payment_amount
            updated_sales = []
            sales_paid_complete = 0
            sales_paid_partial = 0
            
            for sale in pending_sales:
                if remaining_payment <= 0:
                    print(f"   ⏸️ Pago agotado, ventas restantes sin cambios")
                    break
                    
                sale_id = sale[0]
                sale_total = float(sale[1])
                sale_date = sale[2]
                sale_notes = sale[3] or ""
                
                print(f"\n📄 Procesando Venta #{sale_id}")
                print(f"   💰 Debe actualmente: ${sale_total:,.2f}")
                print(f"   💳 Pago disponible: ${remaining_payment:,.2f}")
                
                if remaining_payment >= sale_total:
                    # ✅ PAGO COMPLETO - Marcar como pagada
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                    updated_notes = f"{sale_notes} [PAGADA el {timestamp}]".strip()
                    
                    update_query = f'''
                        UPDATE sales 
                        SET {status_column} = 'paid',
                            notes = ?,
                            updated_at = datetime('now', 'localtime')
                        WHERE id = ?
                    '''
                    cursor.execute(update_query, (updated_notes, sale_id))
                    
                    remaining_payment -= sale_total
                    sales_paid_complete += 1
                    
                    updated_sales.append({
                        'id': sale_id,
                        'original_amount': sale_total,
                        'amount_paid': sale_total,
                        'remaining_debt': 0,
                        'status': 'paid_complete',
                        'date': sale_date[:19]
                    })
                    
                    print(f"   ✅ PAGADA COMPLETAMENTE")
                    print(f"   💰 Pago restante: ${remaining_payment:,.2f}")
                    
                else:
                    # ⚠️ PAGO PARCIAL - Actualizar monto pendiente
                    paid_amount = remaining_payment
                    new_debt = sale_total - paid_amount
                    
                    print(f"   ⚠️ PAGO PARCIAL")
                    print(f"   💳 Abono: ${paid_amount:,.2f}")
                    print(f"   📊 Saldo pendiente: ${new_debt:,.2f}")
                    
                    # Actualizar la venta con el nuevo saldo pendiente
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                    updated_notes = f"{sale_notes} [Abono ${paid_amount:,.2f} el {timestamp} - Saldo: ${new_debt:,.2f}]".strip()
                    
                    # El total de la venta NO se toca: es lo que se vendió.
                    # El abono se registra en paid_amount y remaining_debt.
                    update_query = f'''
                        UPDATE sales 
                        SET paid_amount = COALESCE(paid_amount, 0) + ?,
                            remaining_debt = ?,
                            notes = ?,
                            updated_at = datetime('now', 'localtime')
                        WHERE id = ?
                    '''
                    cursor.execute(update_query, (paid_amount, new_debt, updated_notes, sale_id))
                    
                    sales_paid_partial += 1
                    
                    updated_sales.append({
                        'id': sale_id,
                        'original_amount': sale_total,
                        'amount_paid': paid_amount,
                        'remaining_debt': new_debt,
                        'status': 'paid_partial',
                        'date': sale_date[:19]
                    })
                    
                    remaining_payment = 0  # Se agotó el pago exactamente
                    print(f"   💳 Pago agotado exactamente")
            
            # PASO 5: Manejar exceso de pago como crédito a favor
            if remaining_payment > 0:
                print(f"\n💵 EXCESO DE PAGO: ${remaining_payment:,.2f}")
                self.handle_excess_credit(self.client.id, remaining_payment)
            
            # PASO 6: Confirmar todos los cambios
            conn.commit()
            conn.close()
            
            # PASO 7: Resumen final
            print(f"\n🎯 RESUMEN FINAL:")
            print("=" * 50)
            print(f"💰 Pago procesado: ${payment_amount:,.2f}")
            print(f"✅ Ventas pagadas completamente: {sales_paid_complete}")
            print(f"⚠️ Ventas con abono parcial: {sales_paid_partial}")
            print(f"📊 Total ventas afectadas: {len(updated_sales)}")
            print(f"💳 Exceso como crédito: ${remaining_payment:,.2f}")
            
            return {
                'total_updated': len(updated_sales),
                'sales_updated': updated_sales,
                'sales_paid_complete': sales_paid_complete,
                'sales_paid_partial': sales_paid_partial,
                'excess_credit': remaining_payment,
                'status_column_used': status_column
            }
            
        except Exception as e:
            error_msg = f"Error al procesar pago con acumulación: {e}"
            print(f"❌ {error_msg}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return {'total_updated': 0, 'sales_updated': [], 'error': error_msg}
    
    def view_history(self):
        """Muestra el historial del cliente"""
        ClientHistoryWindow(self.window, self.client)
    
    def refresh_and_close(self):
        """Actualiza todas las ventanas y cierra esta ventana"""
        # Actualizar ventana de clientes
        self.clients_window.refresh_clients()
        
        # Actualizar todas las ventanas desde main_window si existe
        if self.main_window:
            self.main_window.refresh_all_windows()
        
        # Cerrar ventana actual
        self.window.destroy()
    
    def close_window(self):
        """Cierra la ventana"""
        self.window.destroy()


class ClientHistoryWindow:
    def __init__(self, parent, client):
        # Validación inicial del cliente
        if not client or not hasattr(client, 'id') or not hasattr(client, 'name'):
            raise ValueError("Cliente inválido: faltan atributos requeridos")
        self.parent = parent
        self.selected_client = client
        
        # Crear ventana
        self.window = tk.Toplevel(parent)
        self.window.title(f"Historial - {client.name}")
        centrar_ventana(self.window, 800, 600)
        self.window.minsize(650, 480)
        self.window.transient(parent)
        hacer_modal(self.window)
        
        # Configurar el evento de cerrar ventana
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)
        
        # Configurar UI
        self.setup_ui()
        
        # Cargar historial
        self.load_history()

    def close_window(self):
        """Cierra la ventana del historial del cliente"""
        self.window.destroy()

    def _on_history_row_double_click(self, event=None):
        """Doble clic sobre una fila del historial: abre el detalle de la venta"""
        self.view_selected_sale_detail()

    def view_selected_sale_detail(self):
        """Abre el detalle de la venta asociada a la fila seleccionada"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Información", "Seleccione una fila del historial primero")
            return

        sale_id = self.row_sale_map.get(selected[0])
        if not sale_id:
            messagebox.showinfo(
                "Sin venta asociada",
                "Esta fila del historial no corresponde a una venta "
                "(por ejemplo, es un pago o un ajuste sin venta asociada)."
            )
            return

        SaleDetailWindow(self.window, sale_id)

    def on_closing(self):
        """Maneja el evento de cerrar la ventana"""
        self.window.destroy()
    
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Frame principal
        main_frame = ttk.Frame(self.window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, 
                               text=f"📋 HISTORIAL DE TRANSACCIONES", 
                               font=FONT_HEADER)
        title_label.pack(pady=(0, 10))
        
        # CORRECCIÓN: Usar self.selected_client.name en lugar de diccionario
        client_label = ttk.Label(main_frame, 
                                text=f"Cliente: {self.selected_client.name}", 
                                font=FONT_HEADER)
        client_label.pack(pady=(0, 20))

        # Frame para botones (empaquetado ANTES que la tabla, con
        # side=BOTTOM, para que "Cerrar" no se lo coma el expand=True
        # de la tabla)
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(15, 0))

        # Botón para ver el detalle de la venta seleccionada
        ttk.Button(
            button_frame,
            text="🧾 Ver Detalle de Venta",
            command=self.view_selected_sale_detail,
            bootstyle="info"
        ).pack(side=tk.LEFT)

        # PDF para mandarle al cliente cuando pregunta de qué debe
        ttk.Button(
            button_frame,
            text="📄 Estado de cuenta",
            command=lambda: generar_y_abrir(self.selected_client.id),
            bootstyle="success"
        ).pack(side=tk.LEFT, padx=(8, 0))

        # Botón de cerrar
        ttk.Button(
            button_frame,
            text="Cerrar",
            command=self.close_window,
            bootstyle="secondary"
        ).pack(side=tk.RIGHT)

        # Frame para la tabla
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Crear Treeview
        columns = ("Fecha", "Tipo", "Monto", "Descripción")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        
        # Configurar columnas
        self.tree.heading("Fecha", text="Fecha")
        self.tree.heading("Tipo", text="Tipo")
        self.tree.heading("Monto", text="Monto")
        self.tree.heading("Descripción", text="Descripción")
        
        self.tree.column("Fecha", width=150, minwidth=110, anchor="center")
        self.tree.column("Tipo", width=100, minwidth=80, anchor="center")
        self.tree.column("Monto", width=140, minwidth=100, anchor="e")
        self.tree.column("Descripción", width=250, minwidth=150, anchor="w")

        # Scrollbars
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Empaquetar tabla y scrollbars
        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # Configurar colores para diferentes tipos
        self.tree.tag_configure("debit", **ROW_COLORS["danger"])
        self.tree.tag_configure("credit", **ROW_COLORS["success"])
        self.tree.tag_configure('deuda', **ROW_COLORS["danger"])
        self.tree.tag_configure('pago', **ROW_COLORS["success"])

        # Mapa fila -> sale_id, para poder abrir el detalle de la venta
        # directamente desde el historial (sin tener que ir a buscarla
        # manualmente a la lista de ventas).
        self.row_sale_map = {}

        # Doble clic sobre una fila con venta asociada = ver detalle
        self.tree.bind('<Double-1>', self._on_history_row_double_click)

    def load_history(self):
        """Carga el historial de transacciones con orden cronológico preciso"""
        if not hasattr(self.selected_client, 'id'):
            messagebox.showerror("Error", "Cliente no válido")
            return

        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # CORRECCIÓN: Incluir segundos en la fecha mostrada
            cursor.execute('''
                SELECT 
                    strftime('%Y-%m-%d %H:%M:%S', created_at) as fecha_completa,
                    transaction_type as tipo,
                    amount as monto,
                    description as descripcion,
                    sale_id,
                    created_at
                FROM client_transactions
                WHERE client_id = ?
                ORDER BY datetime(created_at) ASC
            ''', (self.selected_client.id,))

            self.tree.delete(*self.tree.get_children())
            self.row_sale_map = {}
            self.configure_tree_styles()

            for row in cursor.fetchall():
                self.process_transaction_row(row)

        except sqlite3.Error as e:
            messagebox.showerror("Error de BD", f"No se pudo cargar el historial:\n{str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Error inesperado:\n{str(e)}")
        finally:
            if conn:
                conn.close()

    def configure_tree_styles(self):
        """Configura los estilos visuales para diferentes tipos de transacciones"""
        self.tree.tag_configure('deuda', **ROW_COLORS["danger"])
        self.tree.tag_configure('pago', **ROW_COLORS["success"])
        self.tree.tag_configure('reversion', **ROW_COLORS["warning"])
        self.tree.tag_configure('ajuste', **ROW_COLORS["info"])

    def process_transaction_row(self, row):
        """Procesa y muestra una fila individual del historial"""
        try:
            tipo_map = {
                'debit': ('DEUDA', 'deuda'),
                'credit': ('PAGO', 'pago'),
                'debit_reversal': ('REVERSIÓN', 'reversion'),
                'payment': ('PAGO', 'pago'),
                'adjustment': ('AJUSTE', 'ajuste')
            }
            
            # Obtener datos de la fila
            fecha_completa = str(row[0]) if row[0] else 'Fecha desconocida'
            raw_type = str(row[1]).lower() if row[1] else ''
            monto = float(row[2]) if row[2] else 0.0
            descripcion = str(row[3]) if row[3] else 'Sin descripción'
            sale_id = row[4] if len(row) > 4 and row[4] else None
            
            tipo_display, tag = tipo_map.get(raw_type, (raw_type.upper(), ''))
            
            # Formato de monto
            if raw_type in ['credit', 'debit_reversal', 'payment']:
                monto_formateado = f"-${abs(monto):,.2f}"
            else:
                monto_formateado = f"${abs(monto):,.2f}"
            
            # Descripción con sale_id
            if sale_id:
                descripcion = f"{descripcion.strip()} (Venta #{sale_id})"
            
            # CORRECCIÓN: Mostrar fecha completa con segundos
            fecha_display = fecha_completa  # Ya incluye segundos del SELECT
            
            item_id = self.tree.insert('', 'end',
                values=(
                    fecha_display,
                    tipo_display,
                    monto_formateado,
                    descripcion.strip()
                ),
                tags=(tag,)
            )

            # Registrar la venta asociada (si existe) para poder abrir su
            # detalle directamente desde esta ventana de historial.
            if sale_id:
                self.row_sale_map[item_id] = sale_id
        except Exception as e:
            print(f"Error al procesar transacción: {e}")
            self.tree.insert('', 'end',
                values=("Error", "Error", "$0.00", f"Error: {str(e)}"),
                tags=('error',)
            )
            
    def configure_tree_tags(self):
        """Configura los estilos para diferentes tipos de transacciones"""
        self.tree.tag_configure('deuda', **ROW_COLORS["danger"])
        self.tree.tag_configure('pago', **ROW_COLORS["success"])
        self.tree.tag_configure('reversion', **ROW_COLORS["warning"])
        self.tree.tag_configure('ajuste', **ROW_COLORS["info"])
        self.tree.tag_configure('info', background=role_color('light'))

    def add_transaction_to_tree(self, row):
        """Añade transacciones manteniendo el orden cronológico"""
        # Convertir tipos de transacción a español
        tipo_map = {
            'debit': 'DEUDA',
            'credit': 'PAGO',
            'debit_reversal': 'REVERSIÓN',
            'payment': 'PAGO'
        }
        
        tipo = tipo_map.get(row['tipo'].lower(), row['tipo'])
        monto = f"${abs(float(row['monto'])):,.2f}" if row['monto'] else "$0.00"
        
        self.tree.insert('', 'end', 
            values=(
                row['fecha'],
                tipo,
                monto,
                row['descripcion']
            ),
            tags=(tipo.lower(),)
        )

    def get_transaction_style(self, transaction_type):
        """Devuelve el estilo y texto a mostrar para cada tipo de transacción"""
        transaction_type = (transaction_type or "").lower()
        
        if transaction_type == 'debit':
            return 'deuda', 'DEUDA'
        elif transaction_type == 'credit':
            return 'pago', 'PAGO'
        elif transaction_type == 'reversal':
            return 'reversion', 'REVERSIÓN'
        elif transaction_type == 'adjustment':
            return 'ajuste', 'AJUSTE'
        else:
            return '', transaction_type.upper()
        
    def create_transaction(client_id, transaction_type, amount, description):
        """Crea una transacción con timestamp local correcto"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # CORRECCIÓN: Usar 'localtime' para hora local correcta
            cursor.execute('''
                INSERT INTO client_transactions 
                    (client_id, transaction_type, amount, description, created_at)
                VALUES (?, ?, ?, ?, datetime('now', 'localtime'))
            ''', (client_id, transaction_type.lower(), abs(amount), description.strip()))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error al crear transacción: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()