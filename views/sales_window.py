import tkinter as tk
from tkinter import ttk, messagebox
from models.product import Product
from models.client import Client
from models.sale import Sale
from utils.validators import validate_number, validate_positive
from datetime import datetime, timedelta
from tkinter import simpledialog
from utils.formatters import format_number, format_currency
from utils.validators import safe_float_conversion

from config.database import get_connection

class SalesWindow:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        self.window = tk.Toplevel(parent)
        self.window.title("Gestión de Ventas")
        self.window.geometry("1100x800")
        self.window.resizable(True, True)
        
        # Variables
        self.products = []
        self.clients = []
        self.sales = []
        self.sale_items = []  # Lista de productos en la venta actual
        
        # Crear notebook y frames para las pestañas
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Frame para nueva venta
        self.new_sale_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.new_sale_frame, text="  Nueva Venta  ")
        
        # Frame para lista de ventas
        self.sales_list_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.sales_list_frame, text="  Lista de Ventas  ")
        
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        # Frame contenedor principal para centrado
        container = ttk.Frame(self.new_sale_frame)
        container.pack(fill=tk.BOTH, expand=True, padx=50, pady=10)  # Ajusta padx para el margen
        
        # Configuración del scroll
        canvas = tk.Canvas(container, bg='#f8f9fa', highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        
        # Frame scrollable
        scrollable_frame = ttk.Frame(canvas, style='TFrame')
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Frame centrado para el contenido
        centered_frame = ttk.Frame(scrollable_frame)
        centered_frame.pack(expand=True, fill=tk.BOTH, padx=100)  # Ajusta padx para centrado
        
        # Configurar estilos
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Colores personalizados
        bg_color = '#f8f9fa'
        header_color = '#343a40'
        accent_color = '#4a6baf'
        success_color = '#28a745'
        danger_color = '#dc3545'
        
        # Configurar estilos
        self.style.configure('TFrame', background=bg_color)
        self.style.configure('TLabel', background=bg_color)
        self.style.configure('Header.TFrame', background=header_color)
        self.style.configure('Header.TLabel', foreground='white', background=header_color, font=('Arial', 10))
        self.style.configure('Accent.TButton', foreground='white', background=accent_color, font=('Arial', 10, 'bold'))
        self.style.configure('Success.TButton', foreground='white', background=success_color)
        self.style.configure('Danger.TButton', foreground='white', background=danger_color)
        
        # Contenido principal dentro del frame centrado
        main_frame = ttk.Frame(centered_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        ttk.Label(title_frame, text="Registrar Nueva Venta", 
                font=("Arial", 16, "bold"), foreground=accent_color).pack(side=tk.LEFT)
        
        # SECCIÓN 1: AGREGAR PRODUCTOS
        products_section = ttk.LabelFrame(main_frame, text=" Agregar Productos ", padding="15", style='TLabelframe')
        products_section.pack(fill=tk.X, pady=(0, 15))
        
        # Controles de producto
        product_controls = ttk.Frame(products_section)
        product_controls.pack(fill=tk.X, pady=(0, 10))
        
        # Producto
        ttk.Label(product_controls, text="Producto:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=(0, 5))
        self.product_var = tk.StringVar()
        self.product_combo = ttk.Combobox(
            product_controls, 
            textvariable=self.product_var, 
            state="readonly", 
            width=25,
            font=('Arial', 10)
        )
        self.product_combo.grid(row=0, column=1, pady=5, padx=(0, 15))
        self.product_combo.bind('<<ComboboxSelected>>', self.on_product_selected)
        
        # Precio unitario
        ttk.Label(product_controls, text="Precio:").grid(row=0, column=2, sticky=tk.W, pady=5, padx=(0, 5))
        self.unit_price_var = tk.StringVar()
        ttk.Entry(
            product_controls, 
            textvariable=self.unit_price_var, 
            state="readonly", 
            width=12,
            font=('Arial', 10),
            justify=tk.RIGHT
        ).grid(row=0, column=3, pady=5, padx=(0, 15))
        
        # Stock disponible
        ttk.Label(product_controls, text="Stock:").grid(row=0, column=4, sticky=tk.W, pady=5, padx=(0, 5))
        self.stock_var = tk.StringVar()
        ttk.Entry(
            product_controls, 
            textvariable=self.stock_var, 
            state="readonly", 
            width=8,
            font=('Arial', 10),
            justify=tk.RIGHT
        ).grid(row=0, column=5, pady=5, padx=(0, 15))
        
        # Segunda fila de controles - Diseño más limpio
        product_controls2 = ttk.Frame(products_section)
        product_controls2.pack(fill=tk.X, pady=(0, 10))
        
        # Cantidad
        ttk.Label(product_controls2, text="Cantidad:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=(0, 5))
        self.quantity_var = tk.StringVar()
        quantity_entry = ttk.Entry(
            product_controls2, 
            textvariable=self.quantity_var, 
            width=10,
            font=('Arial', 10),
            justify=tk.RIGHT
        )
        quantity_entry.grid(row=0, column=1, pady=5, padx=(0, 15))
        quantity_entry.bind('<KeyRelease>', self.calculate_item_total)
        
        # O Dinero
        ttk.Label(product_controls2, text="O Dinero:").grid(row=0, column=2, sticky=tk.W, pady=5, padx=(0, 5))
        self.money_var = tk.StringVar()
        money_entry = ttk.Entry(
            product_controls2, 
            textvariable=self.money_var, 
            width=12,
            font=('Arial', 10),
            justify=tk.RIGHT
        )
        money_entry.grid(row=0, column=3, pady=5, padx=(0, 15))
        money_entry.bind('<KeyRelease>', self.calculate_quantity_from_money)
        
        # Subtotal
        ttk.Label(product_controls2, text="Subtotal:").grid(row=0, column=4, sticky=tk.W, pady=5, padx=(0, 5))
        self.subtotal_var = tk.StringVar()
        ttk.Entry(
            product_controls2, 
            textvariable=self.subtotal_var, 
            state="readonly", 
            width=12,
            font=('Arial', 10),
            justify=tk.RIGHT
        ).grid(row=0, column=5, pady=5, padx=(0, 15))
        
        # Botón agregar producto con estilo
        ttk.Button(
            product_controls2, 
            text="➕ Agregar", 
            command=self.add_product_to_sale,
            style='Success.TButton'
        ).grid(row=0, column=6, pady=5, padx=(10, 0))
        
        # LISTA DE PRODUCTOS EN LA VENTA - Diseño mejorado
        items_section = ttk.LabelFrame(
            main_frame, 
            text=" Productos en la Venta ",
            padding="10",
            style='TLabelframe'
        )
        items_section.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Treeview con estilo mejorado
        style = ttk.Style()
        style.configure("Treeview.Heading", font=('Arial', 10, 'bold'))
        style.configure("Treeview", font=('Arial', 10), rowheight=25)
        
        columns = ('Producto', 'Cantidad', 'Precio Unit.', 'Subtotal')
        self.items_tree = ttk.Treeview(
            items_section, 
            columns=columns, 
            show='headings',
            style='Treeview'
        )
        
        # Configurar columnas
        for col in columns:
            self.items_tree.heading(col, text=col)
            if col == 'Cantidad':
                self.items_tree.column(col, width=80, anchor=tk.E)
            elif col in ['Precio Unit.', 'Subtotal']:
                self.items_tree.column(col, width=100, anchor=tk.E)
            else:
                self.items_tree.column(col, width=200, anchor=tk.W)
        
        # Scrollbar
        items_scrollbar = ttk.Scrollbar(items_section, orient=tk.VERTICAL, command=self.items_tree.yview)
        self.items_tree.configure(yscrollcommand=items_scrollbar.set)
        
        # Empaquetado
        self.items_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        items_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Botones de acción con nuevos estilos
        items_buttons = ttk.Frame(items_section)
        items_buttons.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(
            items_buttons, 
            text="🗑️ Eliminar", 
            command=self.remove_product_from_sale,
            style='Danger.TButton'
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            items_buttons, 
            text="🧹 Limpiar", 
            command=self.clear_sale_items,
            style='Danger.TButton'
        ).pack(side=tk.LEFT, padx=5)
        
        # SECCIÓN 2: INFORMACIÓN DE LA VENTA - Diseño mejorado
        sale_info_section = ttk.LabelFrame(
            main_frame, 
            text=" Información de la Venta ",
            padding="15",
            style='TLabelframe'
        )
        sale_info_section.pack(fill=tk.X, pady=(0, 15))
        
        # Grid mejor organizado
        sale_info_frame = ttk.Frame(sale_info_section)
        sale_info_frame.pack(fill=tk.X)
        
        # Total de la venta - Destacado
        ttk.Label(
            sale_info_frame, 
            text="TOTAL VENTA:", 
            font=("Arial", 12, "bold")
        ).grid(row=0, column=0, sticky=tk.W, pady=5)
        
        self.total_sale_var = tk.StringVar(value="$0.00")
        ttk.Label(
            sale_info_frame, 
            textvariable=self.total_sale_var, 
            font=("Arial", 12, "bold"), 
            foreground=accent_color
        ).grid(row=0, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        
        # Estado de pago - Mejor presentación
        ttk.Label(sale_info_frame, text="Estado:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.status_var = tk.StringVar(value="paid")
        
        status_frame = ttk.Frame(sale_info_frame)
        status_frame.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        
        ttk.Radiobutton(
            status_frame, 
            text="💵 Pagado", 
            variable=self.status_var, 
            value="paid", 
            command=self.on_status_changed
        ).pack(side=tk.LEFT)
        
        ttk.Radiobutton(
            status_frame, 
            text="📝 Fiado", 
            variable=self.status_var, 
            value="pending", 
            command=self.on_status_changed
        ).pack(side=tk.LEFT, padx=(15, 0))
        
        # Cliente - Diseño más compacto
        ttk.Label(sale_info_frame, text="Cliente:").grid(row=2, column=0, sticky=tk.W, pady=5)
        client_frame = ttk.Frame(sale_info_frame)
        client_frame.grid(row=2, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        
        self.client_var = tk.StringVar()
        self.client_combo = ttk.Combobox(
            client_frame, 
            textvariable=self.client_var, 
            width=25, 
            state="disabled",
            font=('Arial', 10)
        )
        self.client_combo.pack(side=tk.LEFT)
        
        self.add_client_btn = ttk.Button(
            client_frame, 
            text="➕ Nuevo", 
            command=self.add_new_client, 
            state="disabled",
            style='Success.TButton'
        )
        self.add_client_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        # Tipo de pago - Diseño mejorado
        ttk.Label(sale_info_frame, text="Tipo de Pago:").grid(row=3, column=0, sticky=tk.W, pady=5)
        payment_frame = ttk.Frame(sale_info_frame)
        payment_frame.grid(row=3, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        
        self.payment_type_var = tk.StringVar(value="cash")
        payment_type_combo = ttk.Combobox(
            payment_frame, 
            textvariable=self.payment_type_var, 
            width=15, 
            state="readonly",
            font=('Arial', 10)
        )
        payment_type_combo['values'] = ["Efectivo", "Crédito"]
        payment_type_combo.pack(side=tk.LEFT)
        
        # BOTONES FINALES - Diseño destacado
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(20, 10))
        
        ttk.Button(
            button_frame, 
            text="💾 Guardar Venta", 
            command=self.save_complete_sale, 
            style='Accent.TButton',
            padding=10
        ).pack(side=tk.LEFT, padx=10)
        
        ttk.Button(
            button_frame, 
            text="🗑️ Limpiar Todo", 
            command=self.clear_all_form,
            style='Danger.TButton',
            padding=10
        ).pack(side=tk.LEFT, padx=10)
        
       # Configurar scrollbars
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Configurar pestaña de lista de ventas
        self.setup_sales_list_ui()
        
        # Ajustar focus
        self.product_combo.focus_set()
    
    def setup_sales_list_ui(self):
        """Configura la UI para lista de ventas"""
        # Frame principal
        main_frame = ttk.Frame(self.sales_list_frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, text="Lista de Ventas", 
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Configurar estilos para el treeview
        self.style.configure('Treeview', rowheight=25)
        self.style.configure('credit.Treeview', foreground='#E65100', background='#FFF3E0')
        self.style.configure('paid.Treeview', foreground='#2E7D32', background='#E8F5E9')

        # Frame para botones
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(controls_frame, text="Actualizar Lista", 
                  command=self.load_sales).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Ver Detalles", 
                  command=self.view_sale_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Editar Venta", 
                  command=self.edit_sale).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Eliminar Venta", 
                  command=self.delete_sale).pack(side=tk.LEFT, padx=5)
        
        # Treeview para mostrar ventas
        columns = ('ID', 'Cliente', 'Total', 'Estado', 'Tipo Pago', 'Fecha')
        self.sales_tree = ttk.Treeview(main_frame, columns=columns, show='headings')
        
        # Configurar columnas
        for col in columns:
            self.sales_tree.heading(col, text=col)
            if col == 'ID':
                self.sales_tree.column(col, width=50)
            elif col == 'Total':
                self.sales_tree.column(col, width=100)
            elif col in ['Estado', 'Tipo Pago']:
                self.sales_tree.column(col, width=100)
            else:
                self.sales_tree.column(col, width=150)
        
        # Scrollbar
        v_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.sales_tree.yview)
        self.sales_tree.configure(yscrollcommand=v_scrollbar.set)
        
        # Frame para treeview y scrollbars
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.sales_tree.pack(fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
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
        """Carga la lista de clientes desde la base de datos"""
        try:
            self.clients = Client.get_all()
            client_names = [client.name for client in self.clients]
            self.client_combo['values'] = client_names
            print(f"Clientes cargados: {len(self.clients)}")  # Debug
        except Exception as e:
            print(f"Error al cargar clientes: {e}")  # Debug
            messagebox.showerror("Error", f"No se pudieron cargar los clientes: {str(e)}")
    
    def load_sales(self):
        """Carga la lista de ventas"""
        try:
            print("Cargando ventas...")  # Debug
            self.sales = Sale.get_all()
            print(f"Ventas cargadas: {len(self.sales)}")  # Debug
            self.update_sales_tree()
        except Exception as e:
            print(f"Error al cargar ventas: {e}")
            messagebox.showerror("Error", f"Error al cargar ventas: {str(e)}")
    
    def on_product_selected(self, event=None):
        """Maneja la selección de producto"""
        product_name = self.product_var.get()
        for product in self.products:
            if product.name == product_name:
                self.unit_price_var.set(f"{product.price:,.2f}")
                self.stock_var.set(f"{product.stock}")
                break
        self.calculate_item_total()
    
    def calculate_item_total(self, event=None):
        """Calcula el subtotal del producto actual"""
        try:
            quantity = safe_float_conversion(self.quantity_var.get() or 0)
            unit_price = safe_float_conversion(self.unit_price_var.get() or 0)
            subtotal = quantity * unit_price
            self.subtotal_var.set(f"{subtotal:,.2f}")
            # Limpiar campo de dinero si se modifica cantidad
            if event:
                self.money_var.set("")
        except ValueError:
            self.subtotal_var.set("0.00")
    
    def calculate_quantity_from_money(self, event=None):
        """Calcula la cantidad basada en dinero recibido"""
        try:
            money = safe_float_conversion(self.money_var.get() or 0)
            unit_price = safe_float_conversion(self.unit_price_var.get() or 0)
            if unit_price > 0:
                quantity = money / unit_price
                self.quantity_var.set(f"{quantity:,.2f}")
                self.subtotal_var.set(f"{money:,.2f}")
            # Limpiar cantidad si se modifica dinero
            if event:
                self.quantity_var.set("")
        except ValueError:
            pass
    
    def add_product_to_sale(self):
        """Agrega un producto a la lista de venta"""
        # Validaciones
        if not self.product_var.get():
            messagebox.showerror("Error", "Debe seleccionar un producto")
            return
        
        # Verificar si se ingresó cantidad o dinero recibido
        has_quantity = self.quantity_var.get() and safe_float_conversion(self.quantity_var.get() or 0) > 0
        has_money = self.money_var.get() and safe_float_conversion(self.money_var.get() or 0) > 0
        
        if not has_quantity and not has_money:
            messagebox.showerror("Error", "Debe ingresar una cantidad o el dinero recibido")
            return
        
        try:
            product_name = self.product_var.get()
            quantity = safe_float_conversion(self.quantity_var.get() or 0)
            unit_price = safe_float_conversion(self.unit_price_var.get())
            subtotal = safe_float_conversion(self.subtotal_var.get())
            
            # Buscar producto
            product = None
            for p in self.products:
                if p.name == product_name:
                    product = p
                    break
            
            if not product:
                messagebox.showerror("Error", "Producto no encontrado")
                return
            
            # Verificar que la cantidad sea válida
            if quantity <= 0:
                if has_money:
                    money = safe_float_conversion(self.money_var.get())
                    if unit_price > 0:
                        quantity = money / unit_price
                    else:
                        messagebox.showerror("Error", "El precio unitario debe ser mayor a 0")
                        return
                else:
                    messagebox.showerror("Error", "La cantidad debe ser mayor a 0")
                    return
            
            # Verificar stock
            total_quantity_in_sale = quantity
            for item in self.sale_items:
                if item['product_id'] == product.id:
                    total_quantity_in_sale += item['quantity']
            
            if product.stock < total_quantity_in_sale:
                messagebox.showerror("Error", f"Stock insuficiente. Disponible: {product.stock}, Solicitado: {total_quantity_in_sale}")
                return
            
            # Verificar si el producto ya está en la lista
            existing_item = None
            for item in self.sale_items:
                if item['product_id'] == product.id:
                    existing_item = item
                    break
            
            if existing_item:
                # Preguntar si quiere sumar las cantidades
                if messagebox.askyesno("Producto Existente", 
                                      f"El producto '{product_name}' ya está en la lista.\n¿Desea sumar las cantidades?"):
                    existing_item['quantity'] += quantity
                    existing_item['subtotal'] = existing_item['quantity'] * existing_item['unit_price']
                else:
                    return
            else:
                # Agregar nuevo producto a la lista
                sale_item = {
                    'product_id': product.id,
                    'product_name': product_name,
                    'quantity': quantity,
                    'unit_price': unit_price,
                    'subtotal': subtotal
                }
                self.sale_items.append(sale_item)
            
            # Actualizar la vista y limpiar campos
            self.update_items_tree()
            self.calculate_total_sale()
            self.clear_product_fields()
            
        except ValueError as e:
            messagebox.showerror("Error", f"Error en los datos: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Error al agregar producto: {str(e)}")
    
    def remove_product_from_sale(self):
        """Elimina un producto de la lista de venta"""
        selected = self.items_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Seleccione un producto para eliminar")
            return
        
        # Obtener el producto seleccionado
        item_values = self.items_tree.item(selected[0], 'values')
        product_name = item_values[0]
        
        # Buscar y eliminar de la lista
        for i, item in enumerate(self.sale_items):
            if item['product_name'] == product_name:
                del self.sale_items[i]
                break
        
        # Actualizar vista
        self.update_items_tree()
        self.calculate_total_sale()
        
        messagebox.showinfo("Éxito", f"Producto '{product_name}' eliminado de la venta")
    
    def clear_sale_items(self):
        """Limpia todos los productos de la venta"""
        if self.sale_items:
            if messagebox.askyesno("Confirmar", "¿Está seguro de limpiar todos los productos de la venta?"):
                self.sale_items.clear()
                self.update_items_tree()
                self.calculate_total_sale()
    
    def update_items_tree(self):
        """Actualiza el treeview de productos"""
        for item in self.items_tree.get_children():
            self.items_tree.delete(item)
        
        for sale_item in self.sale_items:
            self.items_tree.insert('', tk.END, values=(
                sale_item['product_name'],
                format_number(sale_item['quantity']),
                format_currency(sale_item['unit_price']),
                format_currency(sale_item['subtotal'])
            ))
    
    def calculate_total_sale(self):
        """Calcula el total de la venta"""
        total = sum(item['subtotal'] for item in self.sale_items)
        self.total_sale_var.set(format_currency(total))
    
    def clear_product_fields(self):
        """Limpia los campos de producto"""
        self.product_var.set("")
        self.unit_price_var.set("")
        self.stock_var.set("")
        self.quantity_var.set("")
        self.money_var.set("")
        self.subtotal_var.set("")
    
    def on_status_changed(self):
        """Maneja el cambio de estado de pago - CORREGIDO"""
        if self.status_var.get() == "pending":
            # FIADO - Requiere cliente
            self.client_combo.configure(state="readonly")
            self.add_client_btn.configure(state="normal")
        else:
            # AL CONTADO - No requiere cliente
            self.client_combo.configure(state="disabled")
            self.add_client_btn.configure(state="disabled")
            self.client_var.set("")  # Limpiar cliente seleccionado
    
    def add_new_client(self):
        """Abre diálogo para agregar nuevo cliente"""
        dialog = tk.Toplevel(self.window)
        dialog.title("Nuevo Cliente")
        dialog.geometry("300x300")
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
    
    def save_complete_sale(self):
        """Guarda la venta y actualiza la deuda del cliente inmediatamente"""
        if not self.sale_items:
            messagebox.showerror("Error", "Debe agregar al menos un producto a la venta")
            return

        # Validación estricta para ventas fiadas
        if self.status_var.get() == 'pending':
            if not self.client_var.get() or self.client_var.get() == "Sin cliente":
                messagebox.showerror("Error", "Debe seleccionar un cliente válido para ventas fiadas")
                return

        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Obtener cliente para ventas fiadas
            client_id = None
            client_name = "Venta al contado"
            if self.status_var.get() == 'pending':
                client = next((c for c in self.clients if c.name == self.client_var.get()), None)
                if not client:
                    raise ValueError("Cliente seleccionado no existe")
                client_id = client.id
                client_name = client.name

            # Calcular total de la venta
            total = sum(item['subtotal'] for item in self.sale_items)
            status = self.status_var.get()
            payment_method = 'credit' if status == 'pending' else 'cash'

            # 1. Insertar la venta
            cursor.execute('''
                INSERT INTO sales (client_id, total, status, payment_method, created_at, user_id)
                VALUES (?, ?, ?, ?, datetime('now', 'localtime'), ?)
            ''', (client_id, total, status, payment_method, self.user.id))
            
            sale_id = cursor.lastrowid

            # 2. Insertar detalles de venta
            for item in self.sale_items:
                product = next((p for p in self.products if p.id == item['product_id']), None)
                if not product:
                    raise ValueError(f"Producto ID {item['product_id']} no encontrado")

                cursor.execute('''
                    INSERT INTO sale_details 
                    (sale_id, product_id, quantity, unit_price, sale_price, subtotal, cost_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    sale_id,
                    item['product_id'],
                    item['quantity'],
                    item['unit_price'],
                    item['unit_price'],
                    item['subtotal'],
                    product.cost_price
                ))

                # Actualizar stock
                cursor.execute('''
                    UPDATE products SET stock = stock - ? WHERE id = ?
                ''', (item['quantity'], item['product_id']))

            # 3. ACTUALIZAR DEUDA DEL CLIENTE SI ES VENTA FIADA
            if status == 'pending' and client_id:
                # Actualizar deuda total del cliente
                cursor.execute('''
                    UPDATE clients 
                    SET total_debt = total_debt + ?
                    WHERE id = ?
                ''', (total, client_id))

                # Registrar transacción de deuda
                cursor.execute('''
                    INSERT INTO client_transactions 
                    (client_id, transaction_type, amount, description, sale_id, created_at)
                    VALUES (?, 'debit', ?, ?, ?, datetime('now', 'localtime'))
                ''', (
                    client_id,
                    total,
                    f"Venta fiada #{sale_id}",
                    sale_id
                ))

            conn.commit()
            messagebox.showinfo("Éxito", f"Venta #{sale_id} guardada correctamente")
            self.clear_all_form()
            self.load_data()  # Actualizar todas las vistas

        except Exception as e:
            if conn:
                conn.rollback()
            messagebox.showerror("Error", f"No se pudo completar la venta: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    def clear_all_form(self):
        """Limpia todo el formulario - MEJORADO"""
        self.clear_product_fields()
        self.sale_items.clear()
        self.update_items_tree()
        self.total_sale_var.set("$0.00")
        
        # RESETEAR A VALORES POR DEFECTO
        self.status_var.set("paid")  # Por defecto AL CONTADO
        self.client_var.set("")
        self.payment_type_var.set("cash")
        
        # Actualizar estado de controles
        self.on_status_changed()
    
    def view_sale_details(self):
        """Ver detalles completos de una venta"""
        selected = self.sales_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Por favor seleccione una venta para ver detalles")
            return
        
        try:
            sale_id = self.sales_tree.item(selected[0], 'values')[0]
            
            # Buscar la venta
            sale = None
            for s in self.sales:
                if str(s.id) == str(sale_id):
                    sale = s
                    break
            
            if not sale:
                messagebox.showerror("Error", "No se encontró la venta seleccionada")
                return
            
            # Crear ventana de detalles
            details_window = tk.Toplevel(self.window)
            details_window.title(f"Detalles de Venta #{sale.id}")
            details_window.geometry("600x500")
            details_window.resizable(True, True)
            
            # Frame principal
            main_frame = ttk.Frame(details_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Información general
            info_frame = ttk.LabelFrame(main_frame, text="Información General", padding=10)
            info_frame.pack(fill=tk.X, pady=(0, 15))
            
            ttk.Label(info_frame, text=f"Venta ID: {sale.id}", font=("Arial", 12, "bold")).pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Fecha: {sale.created_at}").pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Cliente: {sale.client_name if sale.client_name else 'Venta al contado'}").pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Estado: {'Pagado' if sale.status == 'paid' else 'Pendiente'}").pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Tipo de Pago: {'Efectivo' if sale.payment_method == 'cash' else 'Crédito'}").pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Total: {format_currency(sale.total)}", font=("Arial", 12, "bold")).pack(anchor=tk.W)
            
            # Productos
            products_frame = ttk.LabelFrame(main_frame, text="Productos Vendidos", padding=10)
            products_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
            
            # Treeview para productos
            columns = ('Producto', 'Cantidad', 'Precio Unit.', 'Subtotal')
            details_tree = ttk.Treeview(products_frame, columns=columns, show='headings')
            
            for col in columns:
                details_tree.heading(col, text=col)
                if col == 'Cantidad':
                    details_tree.column(col, width=100)
                elif col in ['Precio Unit.', 'Subtotal']:
                    details_tree.column(col, width=120)
                else:
                    details_tree.column(col, width=150)
            
            # Scrollbar
            details_scrollbar = ttk.Scrollbar(products_frame, orient=tk.VERTICAL, command=details_tree.yview)
            details_tree.configure(yscrollcommand=details_scrollbar.set)
            
            details_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Cargar detalles de la venta
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
            
            for detail in details:
                details_tree.insert('', tk.END, values=(
                    detail['product_name'],
                    format_number(detail['quantity']),
                    format_currency(detail['unit_price']),
                    format_currency(detail['subtotal'])
                ))
            
            # Botón cerrar
            ttk.Button(main_frame, text="Cerrar", command=details_window.destroy).pack(pady=10)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al mostrar detalles: {str(e)}")
    
    def edit_sale(self):
        """Editar venta - SIMPLIFICADO"""
        selected = self.sales_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Por favor seleccione una venta para editar")
            return
        
        try:
            sale_id = self.sales_tree.item(selected[0], 'values')[0]
            
            # Buscar la venta
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
            edit_window.title(f"Editar Venta #{sale.id}")
            edit_window.geometry("400x300")
            edit_window.resizable(False, False)
            
            # Frame principal
            main_frame = ttk.Frame(edit_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Total (editable)
            ttk.Label(main_frame, text="Total:").grid(row=0, column=0, sticky=tk.W, pady=5)
            total_var = tk.StringVar(value=str(sale.total))
            total_entry = ttk.Entry(main_frame, textvariable=total_var, width=15)
            total_entry.grid(row=0, column=1, pady=5, padx=(5, 0))
            
            # Estado
            ttk.Label(main_frame, text="Estado:").grid(row=1, column=0, sticky=tk.W, pady=5)
            status_var = tk.StringVar(value=sale.status if hasattr(sale, 'status') else "paid")
            status_combo = ttk.Combobox(main_frame, textvariable=status_var, width=15, state="readonly")
            status_combo['values'] = ["paid", "pending"]
            status_combo.grid(row=1, column=1, pady=5, padx=(5, 0))
            
            # Cliente
            ttk.Label(main_frame, text="Cliente:").grid(row=2, column=0, sticky=tk.W, pady=5)
            client_var = tk.StringVar(value=sale.client_name if hasattr(sale, 'client_name') and sale.client_name else "")
            client_combo = ttk.Combobox(main_frame, textvariable=client_var, width=20)
            client_combo['values'] = [c.name for c in self.clients]
            client_combo.grid(row=2, column=1, pady=5, padx=(5, 0))
            
            # Tipo de pago
            ttk.Label(main_frame, text="Tipo de Pago:").grid(row=3, column=0, sticky=tk.W, pady=5)
            payment_var = tk.StringVar(value=sale.payment_method if sale.payment_method else "cash")
            payment_combo = ttk.Combobox(main_frame, textvariable=payment_var, width=15, state="readonly")
            payment_combo['values'] = ["cash", "credit"]
            payment_combo.grid(row=3, column=1, pady=5, padx=(5, 0))
            
            def save_changes():
                """Guardar cambios"""
                try:
                    new_total = safe_float_conversion(total_var.get())
                    new_status = status_var.get()
                    new_client = client_var.get()
                    new_payment = payment_var.get()
                    
                    if new_total <= 0:
                        messagebox.showerror("Error", "El total debe ser mayor a cero")
                        return
                    
                    # Actualizar la venta
                    sale.total = new_total
                    sale.status = new_status
                    sale.client_name = new_client if new_client else None
                    sale.payment_method = new_payment
                    
                    # Buscar ID del cliente
                    sale.client_id = None
                    for client in self.clients:
                        if client.name == new_client:
                            sale.client_id = client.id
                            break
                    
                    if sale.save():
                        messagebox.showinfo("Éxito", "Venta actualizada correctamente")
                        edit_window.destroy()
                        self.load_sales()
                    else:
                        messagebox.showerror("Error", "No se pudo actualizar la venta")
                        
                except ValueError:
                    messagebox.showerror("Error", "El total debe ser un número válido")
                except Exception as e:
                    messagebox.showerror("Error", f"Error al actualizar: {str(e)}")
            
            # Botones
            button_frame = ttk.Frame(main_frame)
            button_frame.grid(row=4, column=0, columnspan=2, pady=20)
            
            ttk.Button(button_frame, text="Guardar", command=save_changes).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancelar", command=edit_window.destroy).pack(side=tk.LEFT, padx=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al editar venta: {str(e)}")
    
    def get_adjusted_time(base_time, minutes=1):
        """Ajusta una hora existente agregando minutos"""
        return (datetime.strptime(base_time, '%Y-%m-%d %H:%M:%S') 
            + timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')


    def delete_sale(self):
        """Eliminar venta y actualizar deuda del cliente con control de tiempo preciso"""
        selected = self.sales_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Seleccione una venta para eliminar")
            return
        
        try:
            sale_id = self.sales_tree.item(selected[0], 'values')[0]
            sale = next((s for s in self.sales if str(s.id) == str(sale_id)), None)
            
            if not sale:
                messagebox.showerror("Error", "Venta no encontrada")
                return
                
            if not messagebox.askyesno("Confirmar", 
                                    f"¿Eliminar venta #{sale_id}?\nEsta acción no se puede deshacer."):
                return
            
            conn = get_connection()
            cursor = conn.cursor()
            
            try:
                # 1. Obtener detalles para restaurar stock
                cursor.execute('SELECT product_id, quantity FROM sale_details WHERE sale_id = ?', (sale.id,))
                details = cursor.fetchall()
                
                # 2. Si era venta fiada, actualizar deuda
                if sale.status == "pending" and sale.client_id:
                    # Actualizar deuda del cliente
                    cursor.execute('''
                        UPDATE clients 
                        SET total_debt = total_debt - ?
                        WHERE id = ?
                    ''', (sale.total, sale.client_id))
                    
                    # CORRECCIÓN: Usar hora actual en lugar de calcular tiempo artificial
                    cursor.execute('''
                        INSERT INTO client_transactions 
                        (client_id, transaction_type, amount, description, created_at, sale_id)
                        VALUES (?, 'debit_reversal', ?, ?, datetime('now', 'localtime'), ?)
                    ''', (sale.client_id, sale.total, 
                        f"Reversión de venta #{sale.id}", sale.id))
                
                # 3. Eliminar registros
                cursor.execute('DELETE FROM sale_details WHERE sale_id = ?', (sale.id,))
                cursor.execute('DELETE FROM sales WHERE id = ?', (sale.id,))
                
                conn.commit()
                
                # 4. Actualizar stock localmente
                for detail in details:
                    product = next((p for p in self.products if p.id == detail['product_id']), None)
                    if product:
                        product.stock += detail['quantity']
                        product.save()
                
                messagebox.showinfo("Éxito", "Venta eliminada correctamente")
                self.load_data()
                
            except Exception as e:
                conn.rollback()
                messagebox.showerror("Error", f"Error al eliminar: {str(e)}")
                raise
            finally:
                conn.close()
                
        except Exception as e:
            messagebox.showerror("Error", f"Error inesperado: {str(e)}")
    
    def update_sales_tree(self):
        """Muestra las ventas asegurando que las fiadas tengan cliente"""
        for item in self.sales_tree.get_children():
            self.sales_tree.delete(item)
        
        for sale in self.sales:
            # Obtener nombre del cliente si existe
            client_name = "Venta al contado"
            if sale.client_id:
                client = next((c for c in self.clients if c.id == sale.client_id), None)
                client_name = client.name if client else "Cliente no encontrado"
            
            # Validación estricta para ventas fiadas
            if sale.status == 'pending' and client_name == "Venta al contado":
                client_name = "CLIENTE FALTANTE"  # Mensaje claro de error
                print(f"¡Alerta! Venta fiada sin cliente (ID: {sale.id})")
            
            self.sales_tree.insert('', tk.END, values=(
                sale.id,
                client_name,
                format_currency(sale.total),
                "PENDIENTE" if sale.status == 'pending' else "PAGADO",
                "Crédito" if sale.status == 'pending' else "Efectivo",
                self._format_date(sale.created_at)
            ), tags=('credit' if sale.status == 'pending' else 'paid',))

    def _format_date(self, date_value):
        """Formatea la fecha de manera segura"""
        if date_value is None:
            return "N/A"
        
        if isinstance(date_value, str):
            try:
                # Si es string, convertir a datetime primero
                from datetime import datetime
                if 'T' in date_value:  # Formato ISO
                    date_obj = datetime.fromisoformat(date_value)
                else:  # Otro formato de string
                    date_obj = datetime.strptime(date_value, '%Y-%m-%d %H:%M:%S')
                return date_obj.strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, AttributeError):
                return date_value  # Devuelve el string original si no se puede convertir
        elif hasattr(date_value, 'strftime'):  # Si ya es objeto datetime
            return date_value.strftime('%Y-%m-%d %H:%M:%S')
        else:
            return str(date_value)  # Como último recurso