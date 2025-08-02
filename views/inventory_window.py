import tkinter as tk
from tkinter import ttk, messagebox
from config.database import get_connection

class InventoryWindow:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        
        # Crear ventana
        self.window = tk.Toplevel(parent)
        self.window.title("Gestión de Inventario")
        self.window.geometry("1000x700")
        self.window.transient(parent)
        
        # Centrar ventana
        self.center_window()
        
        # Variables
        self.products = []
        self.selected_product = None
        
        # Configurar UI
        self.setup_ui()
        
        # Cargar productos
        self.refresh_products()
        
        # Configurar cierre
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def center_window(self):
        """Centra la ventana en la pantalla"""
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 1000) // 2
        y = (self.window.winfo_screenheight() - 700) // 2
        self.window.geometry(f"1000x700+{x}+{y}")
    
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Frame principal
        main_frame = ttk.Frame(self.window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, 
                               text="📦 GESTIÓN DE INVENTARIO", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Frame superior con controles
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Botones de acción
        ttk.Button(controls_frame, text="➕ Nuevo Producto", 
                  command=self.add_product).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(controls_frame, text="✏️ Editar", 
                  command=self.edit_product).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(controls_frame, text="🗑️ Eliminar", 
                  command=self.delete_product).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(controls_frame, text="🔄 Actualizar", 
                  command=self.refresh_products).pack(side=tk.LEFT, padx=(0, 20))
        
        # Búsqueda
        ttk.Label(controls_frame, text="Buscar:").pack(side=tk.LEFT, padx=(20, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search)
        search_entry = ttk.Entry(controls_frame, textvariable=self.search_var, width=25)
        search_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        # Frame para la tabla
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Crear Treeview
        columns = ("ID", "Producto", "Precio", "Stock", "Valor Total")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=20)
        
        # Configurar columnas
        self.tree.heading("ID", text="ID")
        self.tree.heading("Producto", text="Nombre del Producto")
        self.tree.heading("Precio", text="Precio Unit.")
        self.tree.heading("Stock", text="Stock")
        self.tree.heading("Valor Total", text="Valor Total")
        
        self.tree.column("ID", width=60, anchor="center")
        self.tree.column("Producto", width=300, anchor="w")
        self.tree.column("Precio", width=120, anchor="e")
        self.tree.column("Stock", width=100, anchor="center")
        self.tree.column("Valor Total", width=120, anchor="e")
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Empaquetar tabla y scrollbars
        self.tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")
        
        # Bind selección
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", lambda e: self.edit_product())
        
        # Frame inferior con estadísticas
        stats_frame = ttk.LabelFrame(main_frame, text="Estadísticas", padding="10")
        stats_frame.pack(fill=tk.X, pady=(15, 0))
        
        self.stats_label = ttk.Label(stats_frame, text="", font=("Arial", 10))
        self.stats_label.pack()
    
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
                                   f"Esta acción no se puede deshacer.")
        
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