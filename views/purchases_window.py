import tkinter as tk
from tkinter import ttk, messagebox
from models.product import Product
from models.purchase import Purchase
from utils.validators import validate_number, validate_positive
from datetime import datetime
from config.database import get_connection
from tkinter import simpledialog

class PurchasesWindow:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        
        # Verificar permisos PRIMERO
        if self.user.role != 'admin':
            messagebox.showerror("Acceso Denegado", 
                            "Solo los administradores pueden acceder a este módulo.")
            return
        
        # Inicializar atributos esenciales ANTES de cualquier uso
        self.colors = {
            'primary': '#2c3e50',
            'secondary': '#3498db',
            'success': '#27ae60',
            'warning': '#f39c12',
            'danger': '#e74c3c',
            'light': '#ecf0f1',
            'dark': '#34495e',
            'background': '#f8f9fa'
        }
        
        # Variables de datos
        self.products = []
        self.purchases = []
        self.current_batch = []
        
        # Crear ventana DESPUÉS de inicializar atributos
        self.window = tk.Toplevel(parent)
        self.window.title("Gestión de Compras")
        self.window.geometry("1100x750")
        self.window.resizable(True, True)
        
        # Configurar estilos (usa self.colors)
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_styles()  # Este método usa self.colors
        
        # Finalmente configurar la UI
        self.setup_ui()
        self.load_data()

    def format_currency(self, amount):
        """Formatea un número como moneda con separadores de miles"""
        try:
            if amount is None:
                return "$0"
            # Convertir a float si es string
            if isinstance(amount, str):
                amount = float(amount.replace('$', '').replace(',', ''))
            # Formatear con separadores de miles
            return f"${amount:,.2f}".replace(',', '.')
        except (ValueError, TypeError):
            return "$0"

    def format_number(self, number):
        """Formatea un número con separadores de miles (sin símbolo de moneda)"""
        try:
            if number is None:
                return "0"
            # Convertir a float si es string
            if isinstance(number, str):
                number = float(number)
            # Formatear con separadores de miles
            return f"{number:,.2f}".replace(',', '.')
        except (ValueError, TypeError):
            return "0"

    def configure_styles(self):
        """Configura los estilos usando self.colors"""
        try:
            self.style.configure('TFrame', background=self.colors['background'])
            self.style.configure('TButton', 
                            font=('Arial', 10), 
                            padding=8,
                            background=self.colors['secondary'],
                            foreground='white')
            self.style.map('TButton',
                        background=[('active', self.colors['primary'])])
            self.style.configure('Header.TLabel', 
                            font=('Arial', 12, 'bold'), 
                            foreground=self.colors['dark'])
            self.style.configure('TNotebook', background=self.colors['background'])
            self.style.configure('TNotebook.Tab', 
                            font=('Arial', 10, 'bold'), 
                            padding=[15, 5],
                            background=self.colors['light'],
                            foreground=self.colors['dark'])
            self.style.map('TNotebook.Tab',
                        background=[('selected', self.colors['primary'])],
                        foreground=[('selected', 'white')])
        except AttributeError as e:
            messagebox.showerror("Error de Configuración", 
                            f"No se pudo configurar estilos: {str(e)}")
            # Valores por defecto si colors no está disponible
            self.style.configure('TFrame', background='#f0f0f0')
            self.style.configure('TButton', background='#cccccc')

    def setup_ui(self):
        """Configura la interfaz principal"""
        # Frame principal con fondo claro
        main_frame = ttk.Frame(self.window, style='TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header con título
        header = tk.Frame(main_frame, bg=self.colors['primary'], height=60)
        header.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(header, 
                text="Gestión de Compras", 
                font=("Arial", 18, "bold"),
                foreground="white",
                background=self.colors['primary']).pack(side=tk.LEFT, padx=20)
        
        # Notebook para pestañas
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Pestaña nueva compra
        self.new_purchase_frame = ttk.Frame(notebook, style='TFrame')
        notebook.add(self.new_purchase_frame, text="➕ Nueva Compra")
        self.setup_new_purchase_ui()
        
        # Pestaña lote actual
        self.batch_frame = ttk.Frame(notebook, style='TFrame')
        notebook.add(self.batch_frame, text="📦 Lote Actual")
        self.setup_batch_ui()
        
        # Pestaña lista de compras
        self.purchases_list_frame = ttk.Frame(notebook, style='TFrame')
        notebook.add(self.purchases_list_frame, text="📋 Historial")
        self.setup_purchases_list_ui()

    def setup_new_purchase_ui(self):
        """Configura la UI para nueva compra"""
        main_frame = ttk.Frame(self.new_purchase_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Frame de formulario con borde
        form_frame = ttk.LabelFrame(main_frame, text="Datos de Compra", padding=15)
        form_frame.pack(fill=tk.X, pady=10)
        
        # Grid layout para controles
        form_frame.columnconfigure(1, weight=1)
        form_frame.columnconfigure(3, weight=1)
        
        # Producto
        ttk.Label(form_frame, text="Producto:", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=8)
        
        self.product_var = tk.StringVar()
        self.product_combo = ttk.Combobox(
            form_frame, 
            textvariable=self.product_var, 
            font=('Arial', 10),
            state='readonly',
            width=30)
        self.product_combo.grid(row=0, column=1, pady=8, padx=5, sticky=tk.EW)
        
        add_product_btn = ttk.Button(
            form_frame, 
            text="➕ Nuevo Producto", 
            command=self.add_new_product,
            style='TButton')
        add_product_btn.grid(row=0, column=2, columnspan=2, pady=8, padx=10, sticky=tk.E)
        
        # Cantidad y Precio
        ttk.Label(form_frame, text="Cantidad:", font=('Arial', 10, 'bold')).grid(
            row=1, column=0, sticky=tk.W, pady=8)
        
        self.quantity_var = tk.StringVar()
        ttk.Entry(form_frame, 
                textvariable=self.quantity_var, 
                font=('Arial', 10),
                width=15).grid(row=1, column=1, pady=8, padx=5, sticky=tk.W)
        
        ttk.Label(form_frame, text="Precio Unitario:", font=('Arial', 10, 'bold')).grid(
            row=1, column=2, sticky=tk.W, pady=8)
        
        self.unit_price_var = tk.StringVar()
        ttk.Entry(form_frame, 
                textvariable=self.unit_price_var, 
                font=('Arial', 10),
                width=15).grid(row=1, column=3, pady=8, padx=5, sticky=tk.W)
        
        # Factura
        ttk.Label(form_frame, text="N° Factura:", font=('Arial', 10, 'bold')).grid(
            row=2, column=0, sticky=tk.W, pady=8)
        
        self.invoice_var = tk.StringVar()
        ttk.Entry(form_frame, 
                textvariable=self.invoice_var, 
                font=('Arial', 10),
                width=30).grid(row=2, column=1, columnspan=3, pady=8, padx=5, sticky=tk.W)
        
        # Botones
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)
        
        ttk.Button(button_frame, 
                text="🛒 Agregar al Lote", 
                command=self.add_to_batch,
                style='TButton').pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, 
                text="🧹 Limpiar Formulario", 
                command=self.clear_form,
                style='TButton').pack(side=tk.LEFT, padx=5)
        
    def edit_purchase(self):
        """Edita la compra seleccionada"""
        selected = self.purchases_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Por favor seleccione una compra para editar")
            return
        
        # Obtener el ID de la compra seleccionada
        purchase_id = self.purchases_tree.item(selected[0], 'values')[0]
        
        # Buscar la compra en la lista de compras
        purchase = None
        for p in self.purchases:
            if str(p.id) == str(purchase_id):
                purchase = p
                break
        
        if not purchase:
            messagebox.showerror("Error", "No se encontró la compra seleccionada")
            return
        
        # Crear ventana de edición
        edit_window = tk.Toplevel(self.window)
        edit_window.title("Editar Compra")
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
        
        # Total
        ttk.Label(main_frame, text="Total:").grid(row=0, column=0, sticky=tk.W, pady=5)
        total_var = tk.StringVar(value=str(purchase.total) if purchase.total else "0.0")
        total_entry = ttk.Entry(main_frame, textvariable=total_var, width=10)
        total_entry.grid(row=0, column=1, pady=5, padx=(5, 0), sticky=tk.W)
        
        # IVA
        ttk.Label(main_frame, text="IVA:").grid(row=1, column=0, sticky=tk.W, pady=5)
        iva_var = tk.StringVar(value=str(purchase.iva) if purchase.iva else "0.0")
        iva_entry = ttk.Entry(main_frame, textvariable=iva_var, width=10)
        iva_entry.grid(row=1, column=1, pady=5, padx=(5, 0), sticky=tk.W)
        
        # Flete
        ttk.Label(main_frame, text="Flete:").grid(row=2, column=0, sticky=tk.W, pady=5)
        shipping_var = tk.StringVar(value=str(purchase.shipping) if purchase.shipping else "0.0")
        shipping_entry = ttk.Entry(main_frame, textvariable=shipping_var, width=10)
        shipping_entry.grid(row=2, column=1, pady=5, padx=(5, 0), sticky=tk.W)
        
        # Factura
        ttk.Label(main_frame, text="Factura:").grid(row=3, column=0, sticky=tk.W, pady=5)
        invoice_var = tk.StringVar(value=purchase.invoice_number if purchase.invoice_number else "")
        invoice_entry = ttk.Entry(main_frame, textvariable=invoice_var, width=15)
        invoice_entry.grid(row=3, column=1, pady=5, padx=(5, 0), sticky=tk.W)
        
        # Botones
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="Guardar", command=lambda: self.save_edited_purchase(
            edit_window, purchase, total_var.get(), iva_var.get(), shipping_var.get(), invoice_var.get()
        )).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Cancelar", command=edit_window.destroy).pack(side=tk.LEFT, padx=5)
    
    def setup_batch_ui(self):
        """Configura la UI para el lote actual"""
        main_frame = ttk.Frame(self.batch_frame, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Frame de información
        info_frame = ttk.LabelFrame(main_frame, text="Información del Lote", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Grid para controles de información
        info_frame.columnconfigure(1, weight=1)
        info_frame.columnconfigure(3, weight=1)
        
        # Flete
        ttk.Label(info_frame, text="Flete Total:", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=5)
        
        self.freight_var = tk.StringVar(value="0")
        ttk.Entry(info_frame, 
                textvariable=self.freight_var, 
                font=('Arial', 10),
                width=15).grid(row=0, column=1, pady=5, padx=5, sticky=tk.W)
        
        # IVA
        ttk.Label(info_frame, text="IVA Total:", font=('Arial', 10, 'bold')).grid(
            row=0, column=2, sticky=tk.W, pady=5)
        
        self.tax_var = tk.StringVar(value="0")
        ttk.Entry(info_frame, 
                textvariable=self.tax_var, 
                font=('Arial', 10),
                width=15).grid(row=0, column=3, pady=5, padx=5, sticky=tk.W)
        
        # Treeview para artículos del lote
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ('Producto', 'Cantidad', 'Precio Unit.', 'Subtotal')
        self.batch_tree = ttk.Treeview(
            tree_frame, 
            columns=columns, 
            show='headings',
            style='Treeview')
        
        # Configurar columnas
        col_widths = {'Producto': 250, 'Cantidad': 100, 'Precio Unit.': 120, 'Subtotal': 120}
        for col in columns:
            self.batch_tree.heading(col, text=col)
            self.batch_tree.column(col, width=col_widths.get(col, 100))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.batch_tree.yview)
        self.batch_tree.configure(yscrollcommand=scrollbar.set)
        
        self.batch_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Frame inferior con total y botones
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Total del lote
        self.total_label = ttk.Label(
            bottom_frame, 
            text="Total del Lote: $0", 
            font=("Arial", 12, "bold"),
            foreground=self.colors['primary'])
        self.total_label.pack(side=tk.LEFT, padx=10)
        
        # Botones
        button_frame = ttk.Frame(bottom_frame)
        button_frame.pack(side=tk.RIGHT)
        
        buttons = [
            ("🧮 Calcular Total", self.calculate_batch_total),
            ("🗑️ Eliminar Selección", self.remove_from_batch),
            ("🧹 Limpiar Lote", self.clear_batch),
            ("💾 Guardar Lote", self.save_batch)
        ]
        
        for text, cmd in buttons:
            ttk.Button(button_frame, 
                    text=text, 
                    command=cmd,
                    style='TButton').pack(side=tk.LEFT, padx=5)
    
    def setup_purchases_list_ui(self):
        """Configura la UI para lista de compras"""
        main_frame = ttk.Frame(self.purchases_list_frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, text="Lista de Compras", 
                            font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Frame para controles
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(controls_frame, text="Actualizar", 
                command=self.load_purchases).pack(side=tk.LEFT, padx=5)
        
        # Botones de editar y eliminar
        ttk.Button(controls_frame, text="Editar Compra", 
                command=self.edit_purchase).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Eliminar Compra", 
                command=self.delete_purchase).pack(side=tk.LEFT, padx=5)
        
        # Treeview para mostrar compras
        columns = ('ID', 'Producto', 'Cantidad', 'Precio Unit.', 'Flete', 'IVA', 'Total', 'Factura', 'Fecha')
        self.purchases_tree = ttk.Treeview(main_frame, columns=columns, show='headings')
        
        for col in columns:
            self.purchases_tree.heading(col, text=col)
            if col == 'ID':
                self.purchases_tree.column(col, width=50)
            elif col in ['Cantidad', 'Flete', 'IVA']:
                self.purchases_tree.column(col, width=80)
            elif col in ['Precio Unit.', 'Total']:
                self.purchases_tree.column(col, width=100)
            elif col == 'Factura':
                self.purchases_tree.column(col, width=100)
            else:
                self.purchases_tree.column(col, width=120)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.purchases_tree.yview)
        h_scrollbar = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=self.purchases_tree.xview)
        self.purchases_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.purchases_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

    def load_data(self):
        """Carga los datos necesarios"""
        self.load_products()
        self.load_purchases()
    
    def load_products(self):
        """Carga la lista de productos"""
        self.products = Product.get_all()
        product_names = [product.name for product in self.products]
        self.product_combo['values'] = product_names
    
    def load_purchases(self):
        """Carga la lista de compras"""
        self.purchases = Purchase.get_all()
        self.update_purchases_tree()
    
    def add_new_product(self):
        """Abre diálogo para agregar nuevo producto"""
        dialog = tk.Toplevel(self.window)
        dialog.title("Nuevo Producto")
        dialog.geometry("500x800")
        dialog.resizable(True, True)
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
        
        ttk.Label(main_frame, text="Nombre del Producto:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar()
        name_entry = ttk.Entry(main_frame, textvariable=name_var, width=30)
        name_entry.grid(row=0, column=1, pady=5)
        
        ttk.Label(main_frame, text="Precio de Venta:").grid(row=1, column=0, sticky=tk.W, pady=5)
        price_var = tk.StringVar()
        price_entry = ttk.Entry(main_frame, textvariable=price_var, width=30)
        price_entry.grid(row=1, column=1, pady=5)
        
        def save_product():
            name = name_var.get().strip()
            try:
                price = float(price_var.get())
                
                if not name:
                    messagebox.showerror("Error", "El nombre no puede estar vacío")
                    return
                
                if price <= 0:
                    messagebox.showerror("Error", "El precio debe ser mayor a 0")
                    return
                
                product = Product(name=name, price=price, stock=0)
                if product.save():
                    self.load_products()
                    self.product_var.set(name)
                    dialog.destroy()
                    messagebox.showinfo("Éxito", "Producto agregado correctamente")
                else:
                    messagebox.showerror("Error", "Ya existe un producto con ese nombre")
                    
            except ValueError:
                messagebox.showerror("Error", "El precio debe ser un número válido")
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Guardar", command=save_product).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        name_entry.focus()
        dialog.bind('<Return>', lambda e: save_product())
    
    def add_to_batch(self):
        """Agrega un artículo al lote actual"""
        # Validaciones
        if not self.product_var.get().strip():
            messagebox.showerror("Error", "Debe seleccionar o escribir un producto")
            return
        
        try:
            quantity = float(self.quantity_var.get())
            unit_price = float(self.unit_price_var.get())
            
            if quantity <= 0:
                messagebox.showerror("Error", "La cantidad debe ser mayor a 0")
                return
            
            if unit_price <= 0:
                messagebox.showerror("Error", "El precio debe ser mayor a 0")
                return
            
        except ValueError:
            messagebox.showerror("Error", "Cantidad y precio deben ser números válidos")
            return
        
        # Agregar al lote
        product_name = self.product_var.get().strip()
        subtotal = quantity * unit_price
        
        item = {
            'product_name': product_name,
            'quantity': quantity,
            'unit_price': unit_price,
            'subtotal': subtotal,
            'invoice_number': self.invoice_var.get().strip()
        }
        
        self.current_batch.append(item)
        self.update_batch_tree()
        self.clear_form()
    
    def update_batch_tree(self):
        """Actualiza el árbol del lote actual"""
        # Limpiar árbol
        for item in self.batch_tree.get_children():
            self.batch_tree.delete(item)
        
        # Agregar artículos con formato de números
        for item in self.current_batch:
            self.batch_tree.insert('', tk.END, values=(
                item['product_name'],
                self.format_number(item['quantity']),
                self.format_currency(item['unit_price']),
                self.format_currency(item['subtotal'])
            ))
    
    def calculate_batch_total(self):
        """Calcula el total del lote con flete e IVA total distribuido"""
        if not self.current_batch:
            self.total_label.config(text="Total del Lote: $0")
            return
        
        try:
            subtotal = sum(item['subtotal'] for item in self.current_batch)
            freight = float(self.freight_var.get() or 0)
            tax_total = float(self.tax_var.get() or 0)
            
            total = subtotal + freight + tax_total
            self.total_label.config(text=f"Total del Lote: {self.format_currency(total)}")
            
        except ValueError:
            messagebox.showerror("Error", "Flete e IVA deben ser números válidos")

    def save_edited_purchase(self, window, purchase, total, iva, shipping, invoice_number):
        """Guarda los cambios de la compra editada"""
        try:
            # Validar datos
            if not total or float(total) <= 0:
                messagebox.showerror("Error", "El total debe ser mayor a cero")
                return
            
            # Actualizar compra
            purchase.total = float(total)
            purchase.iva = float(iva) if iva else 0.0
            purchase.shipping = float(shipping) if shipping else 0.0
            purchase.invoice_number = invoice_number
            
            if purchase.save():
                messagebox.showinfo("Éxito", "Compra actualizada correctamente")
                window.destroy()
                self.load_data()
            else:
                messagebox.showerror("Error", "No se pudo actualizar la compra")
        
        except ValueError:
            messagebox.showerror("Error", "Por favor ingrese valores numéricos válidos")
        except Exception as e:
            messagebox.showerror("Error", f"Error al actualizar la compra: {str(e)}")

    def delete_purchase(self):
        """Elimina la compra seleccionada"""
        selected = self.purchases_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Por favor seleccione una compra para eliminar")
            return
        
        # Obtener el ID de la compra seleccionada
        purchase_id = self.purchases_tree.item(selected[0], 'values')[0]
        
        # Confirmar eliminación
        if not messagebox.askyesno("Confirmar", "¿Está seguro de eliminar esta compra?"):
            return
        
        # Buscar la compra en la lista de compras
        purchase = None
        for p in self.purchases:
            if str(p.id) == str(purchase_id):
                purchase = p
                break
        
        if not purchase:
            messagebox.showerror("Error", "No se encontró la compra seleccionada")
            return
        
        # Eliminar compra
        try:
            # Obtener detalles de la compra para actualizar el stock
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT pd.*, p.id as product_id, p.name as product_name, p.stock 
                FROM purchase_details pd
                JOIN products p ON pd.product_id = p.id
                WHERE pd.purchase_id = ?
            ''', (purchase.id,))
            
            details = cursor.fetchall()
            
            # Actualizar stock de productos
            for detail in details:
                product_id = detail['product_id']
                quantity = detail['quantity']
                
                # Buscar producto
                product = Product.get_by_id(product_id)
                if product:
                    # Restar la cantidad del stock
                    product.stock -= quantity
                    product.save()
            
            # Eliminar detalles de la compra
            cursor.execute('DELETE FROM purchase_details WHERE purchase_id = ?', (purchase.id,))
            conn.commit()
            conn.close()
            
            # Eliminar compra
            purchase.delete()
            
            messagebox.showinfo("Éxito", "Compra eliminada correctamente")
            self.load_data()
        
        except Exception as e:
            messagebox.showerror("Error", f"Error al eliminar la compra: {str(e)}")

    def show_distribution_info(self):
        """Muestra información detallada de la distribución de costos"""
        if not self.current_batch:
            return
        
        try:
            tax_total = float(self.tax_var.get() or 0)
            freight_total = float(self.freight_var.get() or 0)
            num_items = len(self.current_batch)
            
            tax_per_item = tax_total / num_items if num_items > 0 else 0
            freight_per_item = freight_total / num_items if num_items > 0 else 0
            
            info_window = tk.Toplevel(self.window)
            info_window.title("Distribución de Costos")
            info_window.geometry("400x200")
            info_window.resizable(False, False)
            
            main_frame = ttk.Frame(info_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(main_frame, text="Distribución de Costos por Producto", 
                    font=("Arial", 12, "bold")).pack(pady=(0, 10))
            
            ttk.Label(main_frame, text=f"Número de productos en lote: {num_items}").pack(anchor=tk.W)
            ttk.Label(main_frame, text=f"IVA total: {self.format_currency(tax_total)}").pack(anchor=tk.W)
            ttk.Label(main_frame, text=f"IVA por producto: {self.format_currency(tax_per_item)}").pack(anchor=tk.W)
            ttk.Label(main_frame, text=f"Flete total: {self.format_currency(freight_total)}").pack(anchor=tk.W)
            ttk.Label(main_frame, text=f"Flete por producto: {self.format_currency(freight_per_item)}").pack(anchor=tk.W)
            
            ttk.Button(main_frame, text="Cerrar", command=info_window.destroy).pack(pady=10)
            
        except ValueError:
            messagebox.showerror("Error", "Por favor ingrese valores numéricos válidos")
    
    def save_batch(self):
        """Guarda todo el lote de compras con IVA distribuido correctamente"""
        if not self.current_batch:
            messagebox.showwarning("Advertencia", "No hay artículos en el lote")
            return
        
        # Calcular totales primero
        self.calculate_batch_total()
        
        try:
            # OBTENER VALORES TOTALES
            freight_total = float(self.freight_var.get() or 0)
            tax_total = float(self.tax_var.get() or 0)
            
            # DISTRIBUIR POR PRODUCTO
            num_products = len(self.current_batch)
            freight_per_item = freight_total / num_products if num_products > 0 else 0
            tax_per_item = tax_total / num_products if num_products > 0 else 0
            
            saved_count = 0
            invoice_number = self.current_batch[0].get('invoice_number', '') if self.current_batch else ''
            
            for item in self.current_batch:
                # Buscar o crear producto
                product = Product.get_by_name(item['product_name'])
                if not product:
                    estimated_sale_price = item['unit_price'] * 1.3
                    product = Product(name=item['product_name'], 
                                    price=estimated_sale_price, stock=0)
                    if not product.save():
                        messagebox.showerror("Error", f"No se pudo crear el producto {item['product_name']}")
                        continue
                
                # CALCULAR TOTAL POR PRODUCTO
                product_total = item['subtotal'] + freight_per_item + tax_per_item
                
                # Crear compra con valores distribuidos
                purchase = Purchase(
                    user_id=self.user.id,
                    total=product_total,  # TOTAL CON FLETE E IVA
                    iva=tax_per_item,     # IVA DISTRIBUIDO
                    shipping=freight_per_item,  # FLETE DISTRIBUIDO
                    date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    invoice_number=invoice_number,
                    supplier="Sin proveedor"
                )
                
                if purchase.save():
                    # Guardar detalles y actualizar stock
                    conn = None
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute('''
                        INSERT INTO purchase_details (purchase_id, product_id, quantity, unit_cost, unit_price, subtotal)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (purchase.id, product.id, item['quantity'], item['unit_price'], item['unit_price'], item['subtotal']))
                        cursor.execute('''
                            UPDATE products SET cost_price = ? WHERE id = ?
                        ''', (item['unit_price'], product.id))
                        conn.commit()
                        
                        product.update_stock(item['quantity'])
                        saved_count += 1
                    except Exception as e:
                        messagebox.showerror("Error", f"Error al guardar detalles: {e}")
                    finally:
                        if conn:
                            conn.close()
            
            if saved_count > 0:
                messagebox.showinfo("Éxito", 
                    f"Se guardaron {saved_count} compras correctamente.\n\n"
                    f"Distribución:\n"
                    f"• IVA: {self.format_currency(tax_total)} → {self.format_currency(tax_per_item)} por producto\n"
                    f"• Flete: {self.format_currency(freight_total)} → {self.format_currency(freight_per_item)} por producto")
                
                self.clear_batch()
                self.load_data()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar el lote: {e}")
    
    def clear_batch(self):
        """Limpia el lote actual"""
        self.current_batch = []
        self.update_batch_tree()
        self.freight_var.set("0")
        self.tax_var.set("0")  # Limpiar también el IVA
        self.total_label.config(text="Total del Lote: $0")
    
    def remove_from_batch(self):
        """Elimina el artículo seleccionado del lote"""
        selection = self.batch_tree.selection()
        if not selection:
            messagebox.showwarning("Advertencia", "Seleccione un artículo para eliminar")
            return
        
        # Obtener índice del artículo seleccionado
        item_index = self.batch_tree.index(selection[0])
        
        if 0 <= item_index < len(self.current_batch):
            removed_item = self.current_batch.pop(item_index)
            self.update_batch_tree()
            messagebox.showinfo("Éxito", f"Artículo {removed_item['product_name']} eliminado del lote")
    
    def clear_form(self):
        """Limpia el formulario de nueva compra"""
        self.product_var.set("")
        self.quantity_var.set("")
        self.unit_price_var.set("")
        # No limpiar el número de factura para mantener consistencia en el lote
    
    def update_purchases_tree(self):
        """Actualiza el árbol de compras con números formateados"""
        # Limpiar árbol
        for item in self.purchases_tree.get_children():
            self.purchases_tree.delete(item)
        
        # Agregar compras con formato mejorado
        for purchase in self.purchases:
            # Obtener detalles de la compra desde purchase_details
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT pd.*, p.name as product_name 
                FROM purchase_details pd
                JOIN products p ON pd.product_id = p.id
                WHERE pd.purchase_id = ?
            ''', (purchase.id,))
            
            details = cursor.fetchall()
            conn.close()
            
            if details:
                for detail in details:
                    # Formatear fecha
                    date_str = purchase.date if purchase.date else "N/A"
                    
                    # Insertar en árbol con números formateados
                    self.purchases_tree.insert('', tk.END, values=(
                        purchase.id,
                        detail['product_name'],
                        self.format_number(detail['quantity']),
                        self.format_currency(detail['unit_price']),
                        self.format_currency(purchase.shipping) if purchase.shipping else "$0",
                        self.format_currency(purchase.iva) if purchase.iva else "$0",
                        self.format_currency(purchase.total) if purchase.total else "$0",
                        purchase.invoice_number or "N/A",
                        date_str
                    ))
            else:
                # Si no hay detalles, mostrar solo la información básica de la compra
                self.purchases_tree.insert('', tk.END, values=(
                    purchase.id,
                    "N/A",
                    "N/A",
                    "N/A",
                    self.format_currency(purchase.shipping) if purchase.shipping else "$0",
                    self.format_currency(purchase.iva) if purchase.iva else "$0",
                    self.format_currency(purchase.total) if purchase.total else "$0",
                    purchase.invoice_number or "N/A",
                    purchase.date if purchase.date else "N/A"
                ))