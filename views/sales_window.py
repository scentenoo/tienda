import tkinter as tk
from tkinter import ttk, messagebox
from models.product import Product
from models.client import Client
from models.sale import Sale
from utils.validators import validate_number, validate_positive
from datetime import datetime
from tkinter import simpledialog


from config.database import get_connection

class SalesWindow:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        
        # Crear ventana
        self.window = tk.Toplevel(parent)
        self.window.title("Gestión de Ventas")
        self.window.geometry("900x600")
        self.window.resizable(True, True)
        
        # Variables
        self.products = []
        self.clients = []
        self.sales = []
        
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Notebook para pestañas
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Pestaña nueva venta
        self.new_sale_frame = ttk.Frame(notebook)
        notebook.add(self.new_sale_frame, text="Nueva Venta")
        self.setup_new_sale_ui()

         # Añadir botones para editar y eliminar
        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(button_frame, text="Editar Venta", command=self.edit_sale).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Eliminar Venta", command=self.delete_sale).pack(side=tk.LEFT, padx=5)
        
        # Pestaña lista de ventas
        self.sales_list_frame = ttk.Frame(notebook)
        notebook.add(self.sales_list_frame, text="Lista de Ventas")
        self.setup_sales_list_ui()
    
    def setup_new_sale_ui(self):
        """Configura la UI para nueva venta"""
        # Frame principal
        main_frame = ttk.Frame(self.new_sale_frame, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Título
        title_label = ttk.Label(main_frame, text="Registrar Nueva Venta", 
                               font=("Arial", 14, "bold"))
        title_label.grid(row=0, column=0, columnspan=4, pady=(0, 20))
        
        # Producto
        ttk.Label(main_frame, text="Producto:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.product_var = tk.StringVar()
        self.product_combo = ttk.Combobox(main_frame, textvariable=self.product_var, 
                                         state="readonly", width=25)
        self.product_combo.grid(row=1, column=1, pady=5, padx=(5, 20))
        self.product_combo.bind('<<ComboboxSelected>>', self.on_product_selected)
        
        # Precio unitario (solo lectura)
        ttk.Label(main_frame, text="Precio Unitario:").grid(row=1, column=2, sticky=tk.W, pady=5)
        self.unit_price_var = tk.StringVar()
        unit_price_entry = ttk.Entry(main_frame, textvariable=self.unit_price_var, 
                                    state="readonly", width=15)
        unit_price_entry.grid(row=1, column=3, pady=5)
        
        # Cantidad o dinero recibido
        ttk.Label(main_frame, text="Cantidad:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.quantity_var = tk.StringVar()
        quantity_entry = ttk.Entry(main_frame, textvariable=self.quantity_var, width=15)
        quantity_entry.grid(row=2, column=1, pady=5, padx=(5, 0), sticky=tk.W)
        quantity_entry.bind('<KeyRelease>', self.calculate_total)
        
        ttk.Label(main_frame, text="O Dinero Recibido:").grid(row=2, column=2, sticky=tk.W, pady=5)
        self.money_var = tk.StringVar()
        money_entry = ttk.Entry(main_frame, textvariable=self.money_var, width=15)
        money_entry.grid(row=2, column=3, pady=5)
        money_entry.bind('<KeyRelease>', self.calculate_quantity)
        
        # Total
        ttk.Label(main_frame, text="Total:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.total_var = tk.StringVar()
        total_entry = ttk.Entry(main_frame, textvariable=self.total_var, 
                               state="readonly", width=15)
        total_entry.grid(row=3, column=1, pady=5, padx=(5, 0), sticky=tk.W)
        
        # Estado de pago
        ttk.Label(main_frame, text="Estado:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.status_var = tk.StringVar(value="paid")
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=4, column=1, columnspan=3, sticky=tk.W, pady=5, padx=(5, 0))
        
        ttk.Radiobutton(status_frame, text="Pagado", variable=self.status_var, 
                       value="paid", command=self.on_status_changed).pack(side=tk.LEFT)
        ttk.Radiobutton(status_frame, text="Pendiente (Fiado)", variable=self.status_var, 
                       value="pending", command=self.on_status_changed).pack(side=tk.LEFT, padx=(10, 0))
        
        # Cliente (solo si es fiado)
        ttk.Label(main_frame, text="Cliente:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.client_var = tk.StringVar()
        self.client_combo = ttk.Combobox(main_frame, textvariable=self.client_var, 
                                        width=25, state="disabled")
        self.client_combo.grid(row=5, column=1, columnspan=2, pady=5, padx=(5, 0), sticky=(tk.W, tk.E))
        
        # Botón agregar cliente
        self.add_client_btn = ttk.Button(main_frame, text="Nuevo Cliente", 
                                        command=self.add_new_client, state="disabled")
        self.add_client_btn.grid(row=5, column=3, pady=5)
        
        # Tipo de pago
        ttk.Label(main_frame, text="Tipo de Pago:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.payment_type_var = tk.StringVar(value="efectivo")
        payment_type_combo = ttk.Combobox(main_frame, textvariable=self.payment_type_var, 
                                         width=15, state="readonly")
        payment_type_combo['values'] = ["cash", "credit"]
        payment_type_labels = {"cash": "Efectivo", "credit": "Crédito"}
        payment_type_combo.grid(row=6, column=1, pady=5, padx=(5, 0), sticky=tk.W)

        # Mostrar etiquetas en español
        ttk.Label(main_frame, text="(Efectivo / Crédito)").grid(row=6, column=2, sticky=tk.W, pady=5)
        
        # Botones
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=4, pady=20)
        
        ttk.Button(button_frame, text="Guardar Venta", 
                  command=self.save_sale).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Limpiar", 
                  command=self.clear_form).pack(side=tk.LEFT, padx=5)
        
    def edit_sale(self):
        """Edita la venta seleccionada"""
        selected = self.sales_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Por favor seleccione una venta para editar")
            return
        
        # Obtener el ID de la venta seleccionada
        sale_id = self.sales_tree.item(selected[0], 'values')[0]
        
        # Buscar la venta en la lista de ventas
        sale = None
        for s in self.sales:
            if str(s.id) == str(sale_id):
                sale = s
                break
        
        if not sale:
            messagebox.showerror("Error", "No se encontró la venta seleccionada")
            return
        
        # Crear ventana de edición
        edit_window = tk.Toplevel(self.window)
        edit_window.title("Editar Venta")
        edit_window.geometry("400x300")
        edit_window.resizable(False, False)
        
        # Centrar ventana
        edit_window.update_idletasks()
        width = edit_window.winfo_width()
        height = edit_window.winfo_height()
        x = (edit_window.winfo_screenwidth() // 2) - (width // 2)
        y = (edit_window.winfo_screenheight() // 2) - (height // 2)
        edit_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        # Crear formulario
        main_frame = ttk.Frame(edit_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Cliente
        ttk.Label(main_frame, text="Cliente:").grid(row=0, column=0, sticky=tk.W, pady=5)
        client_var = tk.StringVar(value=sale.client_name if sale.client_name else "")
        client_combo = ttk.Combobox(main_frame, textvariable=client_var, width=20)
        client_combo['values'] = [c.name for c in self.clients]
        client_combo.grid(row=0, column=1, pady=5, padx=(5, 0), sticky=tk.W)
        
        # Total
        ttk.Label(main_frame, text="Total:").grid(row=1, column=0, sticky=tk.W, pady=5)
        total_var = tk.StringVar(value=str(sale.total) if sale.total else "0.0")
        total_entry = ttk.Entry(main_frame, textvariable=total_var, width=10)
        total_entry.grid(row=1, column=1, pady=5, padx=(5, 0), sticky=tk.W)
        
        # Estado
        ttk.Label(main_frame, text="Estado:").grid(row=2, column=0, sticky=tk.W, pady=5)
        status_var = tk.StringVar(value="paid" if sale.status == "paid" else "pending")
        status_combo = ttk.Combobox(main_frame, textvariable=status_var, width=15, state="readonly")
        status_combo['values'] = ["paid", "pending"]
        status_combo.grid(row=2, column=1, pady=5, padx=(5, 0), sticky=tk.W)
        
        # Botones
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="Guardar", command=lambda: self.save_edited_sale(
            edit_window, sale, client_var.get(), total_var.get(), status_var.get()
        )).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Cancelar", command=edit_window.destroy).pack(side=tk.LEFT, padx=5)

    
    def setup_sales_list_ui(self):
        """Configura la UI para lista de ventas"""
        # Frame principal
        main_frame = ttk.Frame(self.sales_list_frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, text="Lista de Ventas", 
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Frame para filtros y botones
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Filtro por fecha
        ttk.Label(controls_frame, text="Desde:").pack(side=tk.LEFT, padx=(0, 5))
        self.date_from_var = tk.StringVar()
        date_from_entry = ttk.Entry(controls_frame, textvariable=self.date_from_var, width=12)
        date_from_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(controls_frame, text="Hasta:").pack(side=tk.LEFT, padx=(0, 5))
        self.date_to_var = tk.StringVar()
        date_to_entry = ttk.Entry(controls_frame, textvariable=self.date_to_var, width=12)
        date_to_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(controls_frame, text="Filtrar", 
                  command=self.filter_sales).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Actualizar", 
                  command=self.load_sales).pack(side=tk.LEFT, padx=5)
        
        # Treeview para mostrar ventas
        columns = ('ID', 'Producto', 'Cliente', 'Cantidad', 'Precio Unit.', 'Total', 'Estado', 'Fecha')
        self.sales_tree = ttk.Treeview(main_frame, columns=columns, show='headings')
        
        # Configurar columnas
        for col in columns:
            self.sales_tree.heading(col, text=col)
            if col == 'ID':
                self.sales_tree.column(col, width=50)
            elif col in ['Cantidad', 'Precio Unit.', 'Total']:
                self.sales_tree.column(col, width=100)
            else:
                self.sales_tree.column(col, width=120)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.sales_tree.yview)
        h_scrollbar = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=self.sales_tree.xview)
        self.sales_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack treeview y scrollbars
        self.sales_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Frame para botones de acción
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(action_frame, text="Editar", 
                  command=self.edit_sale).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Eliminar", 
                  command=self.delete_sale).pack(side=tk.LEFT, padx=5)
    
    def load_data(self):
        """Carga los datos necesarios"""
        self.load_products()
        self.load_clients()
        self.load_sales()
    
    def load_products(self):
        """Carga la lista de productos"""
        self.products = Product.get_all()
        product_names = [product.name for product in self.products]
        self.product_combo['values'] = product_names
    
    def load_clients(self):
        """Carga la lista de clientes"""
        self.clients = Client.get_all()
        client_names = [client.name for client in self.clients]
        self.client_combo['values'] = client_names
    
    def load_sales(self):
        """Carga la lista de ventas"""
        self.sales = Sale.get_all()
        self.update_sales_tree()
    
    def on_product_selected(self, event=None):
        """Maneja la selección de producto"""
        product_name = self.product_var.get()
        for product in self.products:
            if product.name == product_name:
                self.unit_price_var.set(f"{product.price:.2f}")
                break
        self.calculate_total()
    
    def calculate_total(self, event=None):
        """Calcula el total basado en cantidad"""
        try:
            quantity = float(self.quantity_var.get() or 0)
            unit_price = float(self.unit_price_var.get() or 0)
            total = quantity * unit_price
            self.total_var.set(f"{total:.2f}")
            # Limpiar campo de dinero si se modifica cantidad
            if event:
                self.money_var.set("")
        except ValueError:
            self.total_var.set("0.00")
    
    def calculate_quantity(self, event=None):
        """Calcula la cantidad basada en dinero recibido"""
        try:
            money = float(self.money_var.get() or 0)
            unit_price = float(self.unit_price_var.get() or 0)
            if unit_price > 0:
                quantity = money / unit_price
                self.quantity_var.set(f"{quantity:.2f}")
                self.total_var.set(f"{money:.2f}")
            # Limpiar cantidad si se modifica dinero
            if event and self.quantity_var.get():
                self.quantity_var.set("")
        except ValueError:
            pass

    def save_edited_sale(self, window, sale, client_name, total, status):
        """Guarda los cambios de la venta editada"""
        try:
            # Validar datos
            if not total or float(total) <= 0:
                messagebox.showerror("Error", "El total debe ser mayor a cero")
                return
            
            # Buscar cliente por nombre
            client_id = None
            for client in self.clients:
                if client.name == client_name:
                    client_id = client.id
                    break
            
            # Actualizar venta
            sale.client_id = client_id
            sale.client_name = client_name
            sale.total = float(total)
            sale.status = status
            sale.payment_method = "cash" if status == "paid" else "credit"
            
            if sale.save():
                messagebox.showinfo("Éxito", "Venta actualizada correctamente")
                window.destroy()
                self.load_data()
            else:
                messagebox.showerror("Error", "No se pudo actualizar la venta")
        
        except ValueError:
            messagebox.showerror("Error", "Por favor ingrese valores numéricos válidos")
        except Exception as e:
            messagebox.showerror("Error", f"Error al actualizar la venta: {str(e)}")

    def delete_sale(self):
        """Elimina la venta seleccionada"""
        selected = self.sales_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Por favor seleccione una venta para eliminar")
            return
        
        # Obtener el ID de la venta seleccionada
        sale_id = self.sales_tree.item(selected[0], 'values')[0]
        
        # Confirmar eliminación
        if not messagebox.askyesno("Confirmar", "¿Está seguro de eliminar esta venta?"):
            return
        
        # Buscar la venta en la lista de ventas
        sale = None
        for s in self.sales:
            if str(s.id) == str(sale_id):
                sale = s
                break
        
        if not sale:
            messagebox.showerror("Error", "No se encontró la venta seleccionada")
            return
        
        # Eliminar venta
        try:
            # Si la venta es a crédito, actualizar la deuda del cliente
            if sale.status == "pending" and sale.client_id:
                # Buscar el cliente
                client = None
                for c in self.clients:
                    if c.id == sale.client_id:
                        client = c
                        break
                
                if client:
                    # Restar la deuda al cliente
                    description = f"Cancelación de venta #{sale.id}"
                    client.add_debt(-sale.total, description)
            
            # Eliminar detalles de la venta
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sale_details WHERE sale_id = ?', (sale.id,))
            conn.commit()
            conn.close()
            
            # Eliminar venta
            sale.delete()
            
            messagebox.showinfo("Éxito", "Venta eliminada correctamente")
            self.load_data()
        
        except Exception as e:
            messagebox.showerror("Error", f"Error al eliminar la venta: {str(e)}")
    
    def on_status_changed(self):
        """Maneja el cambio de estado de pago"""
        if self.status_var.get() == "pending":
            self.client_combo.configure(state="readonly")
            self.add_client_btn.configure(state="normal")
        else:
            self.client_combo.configure(state="disabled")
            self.add_client_btn.configure(state="disabled")
            self.client_var.set("")
    
    def add_new_client(self):
        """Abre diálogo para agregar nuevo cliente"""
        dialog = tk.Toplevel(self.window)
        dialog.title("Nuevo Cliente")
        dialog.geometry("300x150")
        dialog.resizable(False, False)
        dialog.transient(self.window)
        dialog.grab_set()
        
        # Centrar diálogo
        dialog.update_idletasks()
        x = dialog.winfo_reqwidth()
        y = dialog.winfo_reqheight()
        pos_x = (dialog.winfo_screenwidth() // 2) - (x // 2)
        pos_y = (dialog.winfo_screenheight() // 2) - (y // 2)
        dialog.geometry(f"{x}x{y}+{pos_x}+{pos_y}")
        
        # Contenido del diálogo
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Nombre del Cliente:").pack(pady=(0, 10))
        
        name_var = tk.StringVar()
        name_entry = ttk.Entry(main_frame, textvariable=name_var, width=30)
        name_entry.pack(pady=(0, 20))
        name_entry.focus()
        
        def save_client():
            name = name_var.get().strip()
            if not name:
                messagebox.showerror("Error", "El nombre no puede estar vacío")
                return
            
            client = Client(name=name)
            if client.save():
                self.load_clients()
                self.client_var.set(name)
                dialog.destroy()
                messagebox.showinfo("Éxito", "Cliente agregado correctamente")
            else:
                messagebox.showerror("Error", "Ya existe un cliente con ese nombre")
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack()
        
        ttk.Button(button_frame, text="Guardar", command=save_client).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        dialog.bind('<Return>', lambda e: save_client())
    
    def save_sale(self):
        """Guarda la venta"""
        # Validaciones
        if not self.product_var.get():
            messagebox.showerror("Error", "Debe seleccionar un producto")
            return
        
         # Verificar si se ingresó cantidad o dinero recibido
        has_quantity = self.quantity_var.get() and float(self.quantity_var.get() or 0) > 0
        has_money = self.money_var.get() and float(self.money_var.get() or 0) > 0
        
        if not has_quantity and not has_money:
            messagebox.showerror("Error", "Debe ingresar una cantidad o el dinero recibido")
            return
        
        if has_money and not has_quantity:
            try:
                money = float(self.money_var.get())
                unit_price = float(self.unit_price_var.get())
                if unit_price > 0:
                    quantity = money / unit_price
                    self.quantity_var.set(f"{quantity:.2f}")
                else:
                    messagebox.showerror("Error", "El precio unitario debe ser mayor a 0")
                    return
            except ValueError:
                messagebox.showerror("Error", "Valores inválidos para el cálculo")
                return
            
        if self.status_var.get() == "pending" and not self.client_var.get():
            messagebox.showerror("Error", "Debe seleccionar un cliente para ventas fiadas")
            return
        
        try:
            # Obtener datos
            product_name = self.product_var.get()
            quantity = float(self.quantity_var.get())
            unit_price = float(self.unit_price_var.get())
            total = float(self.total_var.get())
            status = self.status_var.get()
            
            # Buscar producto
            product = None
            for p in self.products:
                if p.name == product_name:
                    product = p
                    break
            
            if not product:
                messagebox.showerror("Error", "Producto no encontrado")
                return
            
            # Verificar stock
            if product.stock < quantity:
                messagebox.showerror("Error", f"Stock insuficiente. Disponible: {product.stock}")
                return
            
            # Buscar cliente si es necesario
            client_id = None
            client_name = None
            if status == "pending":
                client_name = self.client_var.get()
                for c in self.clients:
                    if c.name == client_name:
                        client_id = c.id
                        break
            
            # Determinar método de pago basado en el status
            payment_method = "efectivo" if status == "paid" else "credito"
            
            # Crear items para la venta
            items = [{
                'product_id': product.id,
                'product_name': product.name,
                'quantity': quantity,
                'unit_price': unit_price,
                'subtotal': total
            }]

            status = self.status_var.get()  # "paid" o "pending"
            
            # Crear venta con los parámetros correctos según tu modelo
            sale = Sale(
                client_id=client_id,
                client_name=client_name,
                total=total,
                payment_method="cash" if status == "paid" else "credit",  # Usar el estado para determinar el método de pago
                notes="",
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                user_id=self.user.id,
                status=status  # Guardar el estado directamente
            )
            
            if sale.save():
                # Guardar detalles de la venta
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO sale_details (sale_id, product_id, quantity, unit_price, subtotal)
                    VALUES (?, ?, ?, ?, ?)
                ''', (sale.id, product.id, quantity, unit_price, total))
                conn.commit()
                
                # Actualizar stock del producto
                product.stock -= quantity
                product.save()
                
                # Si es venta a crédito, actualizar la deuda del cliente
                if status == "pending" and client_id:
                    # Buscar el cliente
                    client = None
                    for c in self.clients:
                        if c.id == client_id:
                            client = c
                            break
                    
                    if client:
                        # Agregar la deuda al cliente
                        description = f"Venta #{sale.id}: {product_name} x {quantity}"
                        client.add_debt(total, description)
                        
                messagebox.showinfo("Éxito", "Venta guardada correctamente")
                self.clear_form()
                self.load_data()
            else:
                messagebox.showerror("Error", "No se pudo guardar la venta")
                
        except ValueError as e:
            messagebox.showerror("Error", f"Error en los datos: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar la venta: {str(e)}")
    
    def clear_form(self):
        """Limpia el formulario"""
        self.product_var.set("")
        self.unit_price_var.set("")
        self.quantity_var.set("")
        self.money_var.set("")
        self.total_var.set("")
        self.status_var.set("paid")
        self.client_var.set("")
        self.on_status_changed()
    
    def update_sales_tree(self):
        """Actualiza el árbol de ventas"""
        # Limpiar árbol
        for item in self.sales_tree.get_children():
            self.sales_tree.delete(item)
        
        # Agregar ventas
        for sale in self.sales:
            # Obtener detalles de la venta desde sale_details
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sd.*, p.name as product_name 
                FROM sale_details sd
                JOIN products p ON sd.product_id = p.id
                WHERE sd.sale_id = ?
            ''', (sale.id,))
            
            details = cursor.fetchall()
            conn.close()
            
            # Estado de pago
            status = "Pagado" if sale.status == "paid" else "Crédito"
            
            if details:
                for detail in details:
                    # Formatear fecha
                    date_str = sale.created_at if sale.created_at else "N/A"
                    
                    # Insertar en árbol - Ajustado para coincidir con las columnas
                    self.sales_tree.insert('', tk.END, values=(
                        sale.id,                                      # ID
                        detail['product_name'],                       # Producto
                        sale.client_name or "Venta al contado",       # Cliente
                        detail['quantity'],                           # Cantidad
                        f"${detail['unit_price']:.2f}",               # Precio Unit.
                        f"${sale.total:.2f}" if sale.total else "$0.00", # Total
                        status,                                       # Estado
                        date_str                                      # Fecha
                    ))
            else:
                # Si no hay detalles, mostrar solo la información básica de la venta
                self.sales_tree.insert('', tk.END, values=(
                    sale.id,                                      # ID
                    "N/A",                                        # Producto
                    sale.client_name or "Venta al contado",       # Cliente
                    "N/A",                                        # Cantidad
                    "N/A",                                        # Precio Unit.
                    f"${sale.total:.2f}" if sale.total else "$0.00", # Total
                    status,                                       # Estado
                    sale.created_at if sale.created_at else "N/A"  # Fecha
                ))
    
    def filter_sales(self):
        """Filtra las ventas por fecha"""
        # TODO: Implementar filtrado por fecha
        pass
    
    def edit_sale(self):
        """Edita la venta seleccionada"""
        selection = self.sales_tree.selection()
        if not selection:
            messagebox.showwarning("Advertencia", "Seleccione una venta para editar")
            return
        
        # TODO: Implementar edición de ventas
        messagebox.showinfo("Info", "Funcionalidad de edición en desarrollo")
    
    def delete_sale(self):
        """Elimina la venta seleccionada"""
        selection = self.sales_tree.selection()
        if not selection:
            messagebox.showwarning("Advertencia", "Seleccione una venta para eliminar")
            return
        
        if messagebox.askyesno("Confirmar", "¿Está seguro de eliminar esta venta?"):
            # TODO: Implementar eliminación de ventas
            messagebox.showinfo("Info", "Funcionalidad de eliminación en desarrollo")