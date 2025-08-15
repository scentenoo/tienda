import tkinter as tk
from tkinter import ttk, messagebox
from models.client import Client
from config.database import get_connection
import sqlite3

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
        self.window.geometry("1000x650")
        self.window.resizable(True, True)
        self.center_window()

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
    
    def center_window(self):
        """Centra la ventana en la pantalla"""
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 1000) // 2
        y = (self.window.winfo_screenheight() - 650) // 2
        self.window.geometry(f"1000x650+{x}+{y}")
    
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
            font=("Helvetica", 16, "bold"),
            foreground="#333"
        ).pack(pady=(0, 20))

        # 3. Frame de controles (búsqueda/botones)
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 15))

        # Botones
        actions = [
            ("➕ Nuevo", self.add_client),
            ("✏️ Editar", self.edit_client),
            ("💰 Crédito", self.manage_credit),
            ("📋 Historial", self.view_history),
            ("🗑️ Eliminar", self.delete_client)
        ]
        
        for text, cmd in actions:
            ttk.Button(
                controls_frame,
                text=text,
                command=cmd
            ).pack(side=tk.LEFT, padx=5)

        # Búsqueda
        ttk.Label(controls_frame, text="🔍 Buscar:").pack(side=tk.LEFT, padx=(20, 5))
        self.search_var = tk.StringVar()
        ttk.Entry(controls_frame, textvariable=self.search_var, width=25).pack(side=tk.LEFT)
        self.search_var.trace('w', self.on_search)

        # 4. Tabla de clientes
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("ID", "Nombre", "Teléfono", "Límite", "Deuda", "Estado")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, anchor="center")

        # Scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        # 5. Frame de estadísticas (¡Ahora con main_frame definido!)
        stats_frame = ttk.LabelFrame(main_frame, text="📊 Estadísticas", padding=10)
        stats_frame.pack(fill=tk.X, pady=(15, 0))
        self.stats_label = ttk.Label(stats_frame, text="Cargando datos...")
        self.stats_label.pack()

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
    
    def populate_tree(self, clients=None):
        """Llena el treeview con los clientes"""
        # Limpiar árbol
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        clients_to_show = clients if clients is not None else self.clients
        
        # Agregar clientes
        for client in clients_to_show:
            available_credit = client.available_credit()
            
            # Determinar estado
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
                status = "💳 Crédito"
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
        self.tree.tag_configure("good", background="#d4edda")
        self.tree.tag_configure("credit", background="#cce5ff")
        self.tree.tag_configure("warning", background="#fff3cd")
        self.tree.tag_configure("limit", background="#f8d7da")
    
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
        self.window.geometry("550x500")
        self.window.transient(parent)
        self.window.grab_set()
        
        # Centrar ventana
        self.center_window()
        
        # Configurar UI
        self.setup_ui()
        
        # Si es modo edición, cargar datos
        if mode == "edit" and client:
            self.load_client_data()
    
    def center_window(self):
        """Centra la ventana en la pantalla"""
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 550) // 2
        y = (self.window.winfo_screenheight() - 500) // 2
        self.window.geometry(f"550x600+{x}+{y}")
    
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Frame principal
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_text = "➕ Agregar Nuevo Cliente" if self.mode == "add" else "✏️ Editar Cliente"
        title_label = ttk.Label(main_frame, text=title_text, font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 30))
        
        # Formulario
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.X, pady=(0, 30))
        
        # Nombre del cliente
        ttk.Label(form_frame, text="Nombre Completo:*", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        self.name_entry = ttk.Entry(form_frame, width=50, font=("Arial", 10))
        self.name_entry.pack(fill=tk.X, pady=(0, 15))
        
        # Teléfono
        ttk.Label(form_frame, text="Teléfono:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        self.phone_entry = ttk.Entry(form_frame, width=30, font=("Arial", 10))
        self.phone_entry.pack(anchor=tk.W, pady=(0, 15))
        
        # Dirección
        ttk.Label(form_frame, text="Dirección:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        self.address_entry = ttk.Entry(form_frame, width=50, font=("Arial", 10))
        self.address_entry.pack(fill=tk.X, pady=(0, 15))
        
        # Límite de crédito
        ttk.Label(form_frame, text="Límite de Crédito:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        credit_frame = ttk.Frame(form_frame)
        credit_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(credit_frame, text="$").pack(side=tk.LEFT)
        self.credit_limit_entry = ttk.Entry(credit_frame, width=20, font=("Arial", 10))
        self.credit_limit_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.credit_limit_entry.insert(0, "0.00")
        
        # Notas
        ttk.Label(form_frame, text="Notas:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        notes_frame = ttk.Frame(form_frame)
        notes_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.notes_text = tk.Text(notes_frame, height=4, font=("Arial", 10), wrap=tk.WORD)
        notes_scroll = ttk.Scrollbar(notes_frame, orient="vertical", command=self.notes_text.yview)
        self.notes_text.configure(yscrollcommand=notes_scroll.set)
        
        self.notes_text.pack(side="left", fill="both", expand=True)
        notes_scroll.pack(side="right", fill="y")
        
        # Nota obligatoria
        ttk.Label(form_frame, text="* Campos obligatorios", 
                 font=("Arial", 9), foreground="gray").pack(anchor=tk.W, pady=(5, 0))
        
        # Botones
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(buttons_frame, text="Cancelar", 
                  command=self.cancel).pack(side=tk.RIGHT, padx=(10, 0))
        
        save_text = "Guardar Cliente" if self.mode == "add" else "Actualizar Cliente"
        ttk.Button(buttons_frame, text=save_text, 
                  command=self.save).pack(side=tk.RIGHT)
        
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
        self.window.geometry("700x650")  # Más ancho y más alto
        self.window.minsize(700, 550)   # Tamaño mínimo
        self.window.transient(parent)
        self.window.grab_set()
        
        # Centrar ventana
        self.center_window()
        
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
    
    def center_window(self):
        """Centra la ventana en la pantalla"""
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 600) // 2
        y = (self.window.winfo_screenheight() - 450) // 2
        self.window.geometry(f"600x450+{x}+{y}")
    
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Frame principal
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, 
                               text=f"💰 GESTIÓN DE CRÉDITO", 
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        client_label = ttk.Label(main_frame, 
                                text=f"Cliente: {self.client.name}", 
                                font=("Arial", 12, "bold"))
        client_label.pack(pady=(0, 20))
        
        # Frame de información del cliente
        info_frame = ttk.LabelFrame(main_frame, text="Información del Crédito", padding="15")
        info_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Información en grid
        ttk.Label(info_frame, text="Límite de Crédito:", 
                 font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Label(info_frame, text=f"${self.client.credit_limit:,.2f}", 
                 font=("Arial", 10)).grid(row=0, column=1, sticky=tk.W, padx=(20, 0), pady=2)
        
        ttk.Label(info_frame, text="Deuda Actual:", 
                 font=("Arial", 10, "bold")).grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Label(info_frame, text=f"${self.client.total_debt:,.2f}", 
                 font=("Arial", 10), foreground="red" if self.client.total_debt > 0 else "black").grid(row=1, column=1, sticky=tk.W, padx=(20, 0), pady=2)
        
        available = self.client.available_credit()
        ttk.Label(info_frame, text="Crédito Disponible:", 
                 font=("Arial", 10, "bold")).grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Label(info_frame, text=f"${available:,.2f}", 
                 font=("Arial", 10), foreground="green" if available > 0 else "red").grid(row=2, column=1, sticky=tk.W, padx=(20, 0), pady=2)
        
        # Frame para operaciones
        operations_frame = ttk.LabelFrame(main_frame, text="Operaciones", padding="15")
        operations_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Frame para agregar deuda
        if self.client.available_credit() > 0:
            debt_frame = ttk.Frame(operations_frame)
            debt_frame.pack(fill=tk.X, pady=(0, 15))
            
            ttk.Label(debt_frame, text="Agregar Deuda:", 
                     font=("Arial", 10, "bold")).pack(anchor=tk.W)
            
            debt_input_frame = ttk.Frame(debt_frame)
            debt_input_frame.pack(fill=tk.X, pady=(5, 0))
            
            ttk.Label(debt_input_frame, text="Monto: $").pack(side=tk.LEFT)
            self.debt_amount_entry = ttk.Entry(debt_input_frame, width=15)
            self.debt_amount_entry.pack(side=tk.LEFT, padx=(5, 10))
            
            ttk.Label(debt_input_frame, text="Descripción:").pack(side=tk.LEFT, padx=(10, 5))
            self.debt_desc_entry = ttk.Entry(debt_input_frame, width=25)
            self.debt_desc_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
            
            ttk.Button(debt_input_frame, text="Agregar Deuda", 
                      command=self.add_debt).pack(side=tk.RIGHT)
        
        # Frame para registrar pago
        if self.client.total_debt > 0:
            payment_frame = ttk.Frame(operations_frame)
            payment_frame.pack(fill=tk.X, pady=(0, 10))
            
            ttk.Label(payment_frame, text="Registrar Pago:", 
                     font=("Arial", 10, "bold")).pack(anchor=tk.W)
            
            payment_input_frame = ttk.Frame(payment_frame)
            payment_input_frame.pack(fill=tk.X, pady=(5, 0))
            
            ttk.Label(payment_input_frame, text="Monto: $").pack(side=tk.LEFT)
            self.payment_amount_entry = ttk.Entry(payment_input_frame, width=15)
            self.payment_amount_entry.pack(side=tk.LEFT, padx=(5, 10))
            
            ttk.Label(payment_input_frame, text="Descripción:").pack(side=tk.LEFT, padx=(10, 5))
            self.payment_desc_entry = ttk.Entry(payment_input_frame, width=25)
            self.payment_desc_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
            
            ttk.Button(payment_input_frame, text="Registrar Pago", 
                      command=self.register_payment).pack(side=tk.RIGHT)
        
        # Botones inferiores
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(20, 0))
        
        ttk.Button(buttons_frame, text="Ver Historial", 
                  command=self.view_history).pack(side=tk.LEFT)
        
        ttk.Button(buttons_frame, text="Cerrar", 
                  command=self.close_window).pack(side=tk.RIGHT)
    
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
        """Registra un pago del cliente y actualiza ventas pendientes"""
        try:
            # Obtener y validar datos de entrada
            amount_str = self.payment_amount_entry.get().strip()
            description = self.payment_desc_entry.get().strip()
            
            # Validaciones de entrada
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
            
            # Verificar que no exceda la deuda actual
            if amount > self.client.total_debt:
                messagebox.showerror("Error", 
                    f"El monto excede la deuda actual\n"
                    f"Deuda actual: ${self.client.total_debt:,.2f}\n"
                    f"Monto ingresado: ${amount:,.2f}")
                self.payment_amount_entry.focus()
                return
            
            # Confirmar operación
            result = messagebox.askyesno("Confirmar Pago", 
                f"¿Desea registrar este pago?\n\n"
                f"Cliente: {self.client.name}\n"
                f"Monto: ${amount:,.2f}\n"
                f"Descripción: {description}\n\n"
                f"Deuda actual: ${self.client.total_debt:,.2f}\n"
                f"Deuda después del pago: ${self.client.total_debt - amount:,.2f}")
            
            if result:
                # PRIMERO: Actualizar ventas pendientes
                updated_sales = self.update_sales_payment_status(amount)
                
                # SEGUNDO: Registrar el pago en el cliente
                self.client.pay_debt(amount, description)
                
                # TERCERO: Actualizar el cliente desde la base de datos
                self.client = Client.get_by_id(self.client.id)
                
                # Limpiar campos
                self.payment_amount_entry.delete(0, tk.END)
                self.payment_desc_entry.delete(0, tk.END)
                
                # Mostrar mensaje de éxito
                remaining_debt = self.client.total_debt
                success_message = f"¡Pago registrado correctamente!\n\n"
                success_message += f"Monto pagado: ${amount:,.2f}\n"
                
                if remaining_debt == 0:
                    success_message += "¡La deuda ha sido saldada completamente!\n\n"
                else:
                    success_message += f"Deuda restante: ${remaining_debt:,.2f}\n\n"
                
                # Agregar información de ventas actualizadas
                if updated_sales['total_updated'] > 0:
                    success_message += f"📋 {updated_sales['total_updated']} ventas actualizadas a estado 'paid'\n"
                    
                messagebox.showinfo("Pago Registrado", success_message)
                
                # Actualizar la interfaz y cerrar
                self.refresh_and_close()
                
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error inesperado:\n{str(e)}")
            print(f"Error en register_payment: {e}")

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
                    # Pago parcial - dividir la venta
                    paid_amount = remaining_payment
                    remaining_amount = sale_total - paid_amount
                    
                    # Actualizar la venta original con el monto pagado
                    cursor.execute('''
                        UPDATE sales 
                        SET total = ?, status = 'paid', updated_at = datetime('now', 'localtime')
                        WHERE id = ?
                    ''', (paid_amount, sale_id))
                    
                    # Crear nueva venta con el monto restante
                    cursor.execute('''
                        INSERT INTO sales (client_id, total, status, notes, created_at, updated_at)
                        VALUES (?, ?, 'pending', ?, ?, datetime('now', 'localtime'))
                    ''', (
                        self.client.id, 
                        remaining_amount, 
                        f"Saldo pendiente de venta #{sale_id}", 
                        sale[2]  # Mantener la fecha original
                    ))
                    
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
                    
                    cursor.execute('''
                        UPDATE sales 
                        SET status = 'paid',
                            total = ?
                        WHERE id = ?
                    ''', (paid_amount, sale['id']))
                    
                    cursor.execute('''
                        INSERT INTO sales (client_id, total, status, notes, created_at)
                        VALUES (?, ?, 'pending', ?, ?)
                    ''', (self.client.id, remaining_amount, 
                        f"Pago parcial - Restante de venta #{sale['id']}", 
                        sale['created_at']))
                    
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

    def show_payment_allocation(self, amount):
        """Muestra cómo se distribuirá el pago entre las ventas pendientes - VERSIÓN CORREGIDA"""
        pending_sales = self.get_pending_sales()
        if not pending_sales:
            return "No hay ventas pendientes"
        
        allocation_text = ""
        remaining_payment = amount
        
        for i, sale in enumerate(pending_sales, 1):
            if remaining_payment <= 0:
                break
                
            sale_total = float(sale['total'])
            sale_date = sale['created_at'][:16]  # Solo fecha y hora sin segundos
            
            if remaining_payment >= sale_total:
                allocation_text += f"✅ Venta #{sale['id']} ({sale_date}): ${sale_total:,.2f} - PAGADA COMPLETA\n"
                remaining_payment -= sale_total
            else:
                allocation_text += f"⚠️ Venta #{sale['id']} ({sale_date}): ${remaining_payment:,.2f} de ${sale_total:,.2f} - PAGO PARCIAL\n"
                remaining_payment = 0
        
        if remaining_payment > 0:
            allocation_text += f"\n💰 Sobrante: ${remaining_payment:,.2f}"
        
        return allocation_text.strip()
    
    def view_history(self):
        """Muestra el historial del cliente"""
        ClientHistoryWindow(self.window, self.client)
    
    def refresh_and_close(self):
        """Actualiza la ventana principal y cierra esta ventana"""
        self.clients_window.refresh_clients()
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
        self.window.geometry("800x600")
        self.window.transient(parent)
        self.window.grab_set()
        
        # Configurar el evento de cerrar ventana
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)
        
        # Configurar UI
        self.setup_ui()
        
        # Cargar historial
        self.load_history()

    def close_window(self):
        """Cierra la ventana del historial del cliente"""
        self.window.destroy()

    def on_closing(self):
        """Maneja el evento de cerrar la ventana"""
        self.window.destroy()
    
    def center_window(self):
        """Centra la ventana en la pantalla"""
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 700) // 2
        y = (self.window.winfo_screenheight() - 500) // 2
        self.window.geometry(f"700x500+{x}+{y}")
    
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Frame principal
        main_frame = ttk.Frame(self.window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, 
                               text=f"📋 HISTORIAL DE TRANSACCIONES", 
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # CORRECCIÓN: Usar self.selected_client.name en lugar de diccionario
        client_label = ttk.Label(main_frame, 
                                text=f"Cliente: {self.selected_client.name}", 
                                font=("Arial", 12, "bold"))
        client_label.pack(pady=(0, 20))
        
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
        
        self.tree.column("Fecha", width=150, anchor="center")
        self.tree.column("Tipo", width=100, anchor="center")
        self.tree.column("Monto", width=120, anchor="e")
        self.tree.column("Descripción", width=250, anchor="w")
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scrollbar.set)
        
        # Empaquetar tabla y scrollbars
        self.tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        
        # Configurar colores para diferentes tipos
        self.tree.tag_configure("debit", background="#ffebee")  # Rojo claro para débitos
        self.tree.tag_configure("credit", background="#e8f5e8")  # Verde claro para créditos
        self.tree.tag_configure('deuda', background='#ffdddd', foreground='black')  # Rojo claro
        self.tree.tag_configure('pago', background='#ddffdd', foreground='black')   # Verde claro

        # Frame para botones
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        
        # Botón de cerrar
        ttk.Button(
            button_frame, 
            text="Cerrar", 
            command=self.close_window
        ).pack(side=tk.RIGHT)
        
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
        style = ttk.Style()
        style.configure('Debit.Treeview', foreground='red')
        style.configure('Credit.Treeview', foreground='green')
        style.configure('Reversal.Treeview', foreground='orange')
        
        self.tree.tag_configure('deuda', background='#ffeeee')
        self.tree.tag_configure('pago', background='#eeffee')
        self.tree.tag_configure('reversion', background='#fff8e8')

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
            
            self.tree.insert('', 'end',
                values=(
                    fecha_display,
                    tipo_display,
                    monto_formateado,
                    descripcion.strip()
                ),
                tags=(tag,)
            )
        except Exception as e:
            print(f"Error al procesar transacción: {e}")
            self.tree.insert('', 'end',
                values=("Error", "Error", "$0.00", f"Error: {str(e)}"),
                tags=('error',)
            )
            
    def configure_tree_tags(self):
        """Configura los estilos para diferentes tipos de transacciones"""
        self.tree.tag_configure('deuda', background='#ffdddd', foreground='black')
        self.tree.tag_configure('pago', background='#ddffdd', foreground='black')
        self.tree.tag_configure('reversion', background='#fff3e0', foreground='black')
        self.tree.tag_configure('ajuste', background='#e3f2fd', foreground='black')
        self.tree.tag_configure('info', background='#f5f5f5', foreground='gray')

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