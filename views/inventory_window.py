import tkinter as tk
from tkinter import ttk, messagebox
from config.database import get_connection
from utils.ExcelImportWindow import ExcelImportWindow
from views.users_window import UsersWindow

class InventoryWindow:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        
        # Configuración de ventana
        self.window = tk.Toplevel(parent)
        self.window.title("Gestión de Inventario")
        self.window.geometry("1100x750")  # Tamaño aumentado
        self.window.resizable(True, True)
        self.center_window()
        
        # Variables
        self.products = []
        self.selected_product = None
        
        # UI
        self.setup_ui()
        self.refresh_products()
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

    def center_window(self):
        """Centra la ventana en la pantalla"""
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() - width) // 2
        y = (self.window.winfo_screenheight() - height) // 2
        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def setup_ui(self):
        """Configuración completa de la UI con los problemas corregidos"""
        # Frame principal con scroll
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=25, pady=15)  # Reducido pady superior
        
        # Configuración de estilos (sin cambios)
        self.style = ttk.Style()
        self.style.theme_use('clam')
        bg_color = '#f8f9fa'
        dark_blue = '#2c3e50'
        accent_color = '#2980b9'
        
        self.style.configure('TFrame', background=bg_color)
        self.style.configure('Header.TLabel', font=('Helvetica', 16, 'bold'), foreground=dark_blue)
        self.style.configure('Accent.TButton', foreground='white', background=accent_color, padding=8)
        
        # Título
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 15))  # Reducido espacio bajo título
        ttk.Label(title_frame, text="📦 GESTIÓN DE INVENTARIO", style='Header.TLabel').pack()

        # Controles superiores
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Botones de acción (quitado el de ayuda que causaba error)
        actions = [
            ("➕ NUEVO", self.add_product, 'Accent.TButton'),
            ("✏️ EDITAR", self.edit_product),
            ("🗑️ ELIMINAR", self.delete_product),
            ("🔄 ACTUALIZAR", self.refresh_products)
        ]
         # NUEVO: Botón de importación solo para administradores
        if self.user.role == 'admin':  # Asumiendo que tienes un campo 'role' en user
            ttk.Button(
                controls_frame,
                text="📊 IMPORTAR EXCEL",
                command=self.import_from_excel,
                style='Accent.TButton'
            ).pack(side=tk.LEFT, padx=5)


        for text, cmd, *style in actions:
            ttk.Button(
                controls_frame,
                text=text,
                command=cmd,
                style=style[0] if style else 'TButton'
            ).pack(side=tk.LEFT, padx=5)

        # Búsqueda
        search_frame = ttk.Frame(controls_frame)
        search_frame.pack(side=tk.RIGHT)
        ttk.Label(search_frame, text="🔍").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.search_var, width=30).pack(side=tk.LEFT, padx=5)
        self.search_var.trace('w', self.on_search)

        # Tabla de productos
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("ID", "Producto", "Precio", "Stock", "Valor Total")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=16)
        
        # Config columnas
        col_config = [
            ("ID", 70, "center"),
            ("Producto", 350, "w"),
            ("Precio", 120, "e"),
            ("Stock", 100, "center"),
            ("Valor Total", 150, "e")
        ]
        
        for col, width, anchor in col_config:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor=anchor)

        # Scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Eventos
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", lambda e: self.edit_product())

        # SECCIÓN ESTADÍSTICAS (reposicionada más arriba)
        stats_frame = ttk.LabelFrame(
            main_frame,
            text="📊 RESUMEN",
            padding=(15, 10)
        )
        stats_frame.pack(fill=tk.X, pady=(15, 5))  # Menos espacio inferior
        
        self.stats_label = ttk.Label(
            stats_frame,
            text="Productos: 0 | Valor total: $0.00 | Stock bajo: 0",
            font=('Helvetica', 10, 'bold'),
            foreground=dark_blue
        )
        self.stats_label.pack()

    def import_from_excel(self):
        """Abre ventana para importar productos desde Excel"""
        ExcelImportWindow(self.window, self)
    
    def refresh_products(self):
        """Recarga la lista de productos"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, name, price, stock, (price * stock) as total_value
                FROM products 
                ORDER BY name
            ''')
            
            self.products = cursor.fetchall()
            conn.close()
            
            self.populate_tree()
            self.update_statistics()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar productos: {e}")
    
    def populate_tree(self, products=None):
        """Llena el treeview con los productos"""
        # Limpiar árbol
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        products_to_show = products if products is not None else self.products
        
        # Agregar productos
        for product in products_to_show:
            price_formatted = f"${product['price']:,.2f}"
            total_value_formatted = f"${product['total_value']:,.2f}"
            
            # Color por stock
            tags = []
            if product['stock'] <= 5:
                tags.append("low_stock")
            elif product['stock'] == 0:
                tags.append("no_stock")
            
            self.tree.insert("", "end", 
                           values=(product['id'], product['name'], 
                                 price_formatted, product['stock'], 
                                 total_value_formatted),
                           tags=tags)
        
        # Configurar colores
        self.tree.tag_configure("low_stock", background="#fff3cd")
        self.tree.tag_configure("no_stock", background="#f8d7da")
    
    def on_search(self, *args):
        """Filtra productos por búsqueda"""
        search_term = self.search_var.get().lower()
        
        if not search_term:
            self.populate_tree()
            return
        
        filtered_products = [
            product for product in self.products
            if search_term in product['name'].lower()
        ]
        
        self.populate_tree(filtered_products)
    
    def on_select(self, event):
        """Maneja la selección de un producto"""
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            values = item['values']
            self.selected_product = {
                'id': values[0],
                'name': values[1],
                'price': values[2],
                'stock': values[3]
            }
        else:
            self.selected_product = None
    
    def update_statistics(self):
        """Actualiza las estadísticas"""
        if not self.products:
            self.stats_label.config(text="No hay productos en el inventario")
            return
        
        total_products = len(self.products)
        total_items = sum(product['stock'] for product in self.products)
        total_value = sum(product['total_value'] for product in self.products)
        
        low_stock = sum(1 for product in self.products if 0 < product['stock'] <= 5)
        no_stock = sum(1 for product in self.products if product['stock'] == 0)
        
        stats_text = f"Productos: {total_products} | Items totales: {total_items:,} | "
        stats_text += f"Valor total: ${total_value:,.2f} | "
        stats_text += f"Stock bajo: {low_stock} | Sin stock: {no_stock}"
        
        self.stats_label.config(text=stats_text)
    
    def add_product(self):
        """Abre ventana para agregar producto"""
        ProductFormWindow(self.window, self, mode="add")
    
    def edit_product(self):
        """Abre ventana para editar producto"""
        if not self.selected_product:
            messagebox.showwarning("Selección requerida", 
                                 "Por favor seleccione un producto para editar")
            return
        
        ProductFormWindow(self.window, self, mode="edit", product=self.selected_product)
    
    def delete_product(self):
        """Elimina el producto seleccionado"""
        if not self.selected_product:
            messagebox.showwarning("Selección requerida", 
                                 "Por favor seleccione un producto para eliminar")
            return
        
        result = messagebox.askyesno("Confirmar eliminación", 
                                   f"¿Está seguro que desea eliminar el producto:\n"
                                   f"'{self.selected_product['name']}'?\n\n"
                                   f"Esta acción no se puede deshacer. Y si hizo compras con este producto generará graves errores")
        
        if result:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute("DELETE FROM products WHERE id = ?", 
                             (self.selected_product['id'],))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Éxito", "Producto eliminado correctamente")
                self.refresh_products()
                
            except Exception as e:
                messagebox.showerror("Error", f"Error al eliminar producto: {e}")
    
    def on_closing(self):
        """Cierra la ventana"""
        self.window.destroy()


class ProductFormWindow:
    def __init__(self, parent, inventory_window, mode="add", product=None):
        self.parent = parent
        self.inventory_window = inventory_window
        self.mode = mode
        self.product = product
        
        # Crear ventana
        self.window = tk.Toplevel(parent)
        title = "Nuevo Producto" if mode == "add" else "Editar Producto"
        self.window.title(title)
        self.window.geometry("500x400")
        self.window.transient(parent)
        self.window.grab_set()
        
        # Centrar ventana
        self.center_window()
        
        # Configurar UI
        self.setup_ui()
        
        # Si es modo edición, cargar datos
        if mode == "edit" and product:
            self.load_product_data()
    
    def center_window(self):
        """Centra la ventana en la pantalla"""
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 500) // 2
        y = (self.window.winfo_screenheight() - 400) // 2
        self.window.geometry(f"500x400+{x}+{y}")
    
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Frame principal
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_text = "➕ Agregar Nuevo Producto" if self.mode == "add" else "✏️ Editar Producto"
        title_label = ttk.Label(main_frame, text=title_text, font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 30))
        
        # Formulario
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.X, pady=(0, 30))
        
        # Nombre del producto
        ttk.Label(form_frame, text="Nombre del Producto:*", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        self.name_entry = ttk.Entry(form_frame, width=50, font=("Arial", 10))
        self.name_entry.pack(fill=tk.X, pady=(0, 15))
        
        # Precio
        ttk.Label(form_frame, text="Precio Unitario:*", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        price_frame = ttk.Frame(form_frame)
        price_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(price_frame, text="$").pack(side=tk.LEFT)
        self.price_entry = ttk.Entry(price_frame, width=20, font=("Arial", 10))
        self.price_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        # Stock inicial
        ttk.Label(form_frame, text="Stock Inicial:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        self.stock_entry = ttk.Entry(form_frame, width=20, font=("Arial", 10))
        self.stock_entry.pack(anchor=tk.W, pady=(0, 15))
        
        # Nota
        note_text = "* Campos obligatorios"
        if self.mode == "edit":
            note_text += "\nDeje el stock en blanco para mantener el actual"
        
        ttk.Label(form_frame, text=note_text, font=("Arial", 9), foreground="gray").pack(anchor=tk.W)
        
        # Botones
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        ttk.Button(buttons_frame, text="Cancelar", 
                  command=self.cancel).pack(side=tk.RIGHT, padx=(10, 0))
        
        save_text = "Guardar" if self.mode == "add" else "Actualizar"
        ttk.Button(buttons_frame, text=save_text, 
                  command=self.save).pack(side=tk.RIGHT)
        
        # Enfocar en el primer campo
        self.name_entry.focus()
    
    def load_product_data(self):
        """Carga los datos del producto en modo edición"""
        if self.product:
            self.name_entry.insert(0, self.product['name'])
            # Extraer el valor numérico del precio (quitar $ y comas)
            price_str = str(self.product['price']).replace('$', '').replace(',', '')
            self.price_entry.insert(0, price_str)
            self.stock_entry.insert(0, str(self.product['stock']))
    
    def save(self):
        """Guarda o actualiza el producto"""
        # Validar campos
        name = self.name_entry.get().strip()
        price_str = self.price_entry.get().strip()
        stock_str = self.stock_entry.get().strip()
        
        if not name:
            messagebox.showerror("Error", "El nombre del producto es obligatorio")
            self.name_entry.focus()
            return
        
        if not price_str:
            messagebox.showerror("Error", "El precio es obligatorio")
            self.price_entry.focus()
            return
        
        try:
            price = float(price_str)
            if price < 0:
                raise ValueError("El precio no puede ser negativo")
        except ValueError:
            messagebox.showerror("Error", "Ingrese un precio válido")
            self.price_entry.focus()
            return
        
        # Stock es opcional en modo edición
        stock = 0
        if stock_str:
            try:
                stock = int(stock_str)
                if stock < 0:
                    raise ValueError("El stock no puede ser negativo")
            except ValueError:
                messagebox.showerror("Error", "Ingrese un stock válido (número entero)")
                self.stock_entry.focus()
                return
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            if self.mode == "add":
                # Verificar si el producto ya existe
                cursor.execute("SELECT id FROM products WHERE LOWER(name) = LOWER(?)", (name,))
                if cursor.fetchone():
                    messagebox.showerror("Error", "Ya existe un producto con ese nombre")
                    conn.close()
                    return
                
                # Insertar nuevo producto
                cursor.execute('''
                    INSERT INTO products (name, price, stock) 
                    VALUES (?, ?, ?)
                ''', (name, price, stock))
                
                messagebox.showinfo("Éxito", "Producto agregado correctamente")
                
            else:  # mode == "edit"
                # Verificar si el nombre ya existe en otro producto
                cursor.execute('''
                    SELECT id FROM products 
                    WHERE LOWER(name) = LOWER(?) AND id != ?
                ''', (name, self.product['id']))
                
                if cursor.fetchone():
                    messagebox.showerror("Error", "Ya existe otro producto con ese nombre")
                    conn.close()
                    return
                
                # Actualizar producto existente
                if stock_str:  # Si se especificó stock, actualizarlo
                    cursor.execute('''
                        UPDATE products 
                        SET name = ?, price = ?, stock = ? 
                        WHERE id = ?
                    ''', (name, price, stock, self.product['id']))
                else:  # Si no se especificó stock, mantener el actual
                    cursor.execute('''
                        UPDATE products 
                        SET name = ?, price = ? 
                        WHERE id = ?
                    ''', (name, price, self.product['id']))
                
                messagebox.showinfo("Éxito", "Producto actualizado correctamente")
            
            conn.commit()
            conn.close()
            
            # Refresh de la ventana padre
            self.inventory_window.refresh_products()
            
            # Cerrar ventana
            self.window.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar producto: {e}")
    
    def cancel(self):
        """Cancela la operación"""
        self.window.destroy()