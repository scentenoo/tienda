import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from models.product import Product
from models.client import Client
from models.sale import Sale
from utils.validators import validate_number, validate_positive
from datetime import datetime, timedelta
from utils.formatters import format_number, format_currency
from utils.validators import safe_float_conversion
from utils.theme import FONT_TITLE, FONT_HEADER, FONT_BOLD, FONT_NORMAL, FONT_SMALL, ROW_COLORS

from config.database import get_connection
from servicios.ventas import editar_venta, eliminar_venta, registrar_venta
from views.sale_detail_window import SaleDetailWindow
from utils.ventanas import hacer_modal, centrar_ventana

class SalesWindow:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        self.window = tk.Toplevel(parent)
        self.window.title("Gestión de Ventas")
        self.window.resizable(True, True)
        centrar_ventana(self.window, 1100, 800)
        self.window.minsize(950, 650)

        # Variables
        self.products = []
        self.clients = []
        self.sales = []
        self.sale_items = []  # Lista de productos en la venta actual
        self.filtered_products = []  # Lista de productos filtrados para búsqueda
        self.is_filtering = False  # Flag para controlar el filtrado
        self._typing_timer = None
        self._last_search = ""
        self._is_clicking = False
        # AGREGAR ESTAS NUEVAS VARIABLES:
        self.adjustment_var = tk.StringVar(value="0")
        self.adjustment_reason_var = tk.StringVar()
                
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
    
    # REDISEÑO DE INTERFAZ DE VENTAS - SIN SCROLL
# Reemplaza la función setup_ui() en sales_window.py

    def setup_ui(self):
        """Configura la interfaz optimizada - TODO EN UNA PANTALLA"""

        # ═══════════════════════════════════════════════════════════
        # DISEÑO EN 2 COLUMNAS: IZQUIERDA (productos) | DERECHA (info)
        # ═══════════════════════════════════════════════════════════
        
        # Frame principal con padding reducido
        main_frame = ttk.Frame(self.new_sale_frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ─────────────────────────────────────────────────────────────
        # TÍTULO COMPACTO
        # ─────────────────────────────────────────────────────────────
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(title_frame, text="📝 Nueva Venta",
                font=FONT_TITLE, bootstyle="primary").pack(side=tk.LEFT)
        
        # ─────────────────────────────────────────────────────────────
        # CONTENEDOR DE 2 COLUMNAS
        # ─────────────────────────────────────────────────────────────
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)
        content_frame.rowconfigure(0, weight=1)
        content_frame.columnconfigure(0, weight=3)
        content_frame.columnconfigure(1, weight=2)

        # COLUMNA IZQUIERDA (60%) - Productos
        left_column = ttk.Frame(content_frame)
        left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        # COLUMNA DERECHA (40%) - Información de venta
        right_column = ttk.Frame(content_frame)
        right_column.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        
        # ═══════════════════════════════════════════════════════════
        # COLUMNA IZQUIERDA - AGREGAR PRODUCTOS
        # ═══════════════════════════════════════════════════════════
        
        # ─── Sección: Buscar Producto ───
        product_search_frame = ttk.LabelFrame(left_column, text=" 🔍 Buscar Producto ", padding="8")
        product_search_frame.pack(fill=tk.X, pady=(0, 8))
        
        # Fila 1: Producto y Precio
        row1 = ttk.Frame(product_search_frame)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="Producto:", width=10).pack(side=tk.LEFT)
        self.product_var = tk.StringVar()
        self.product_combo = ttk.Combobox(
            row1, 
            textvariable=self.product_var, 
            state="normal",
            width=25,
            font=FONT_NORMAL
        )
        self.product_combo.pack(side=tk.LEFT, padx=5)
        self.product_combo.bind('<KeyRelease>', self._on_product_typing)
        self.product_combo.bind('<<ComboboxSelected>>', self.on_product_selected)
        self.product_combo.bind('<Button-1>', self._on_combo_click)
        self.product_combo.bind('<Return>', self._on_product_enter)
        self.product_combo.bind('<Tab>', self._on_product_tab)
        self.product_combo.bind('<FocusOut>', self._on_product_focus_out)
        
        ttk.Label(row1, text="Precio:", width=6).pack(side=tk.LEFT, padx=(10, 0))
        self.unit_price_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.unit_price_var, state="readonly", 
                width=10, font=FONT_NORMAL, justify=tk.RIGHT).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row1, text="Stock:", width=6).pack(side=tk.LEFT)
        self.stock_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.stock_var, state="readonly", 
                width=8, font=FONT_NORMAL, justify=tk.RIGHT).pack(side=tk.LEFT, padx=5)
        
        # Fila 2: Cantidad, Dinero, Subtotal
        row2 = ttk.Frame(product_search_frame)
        row2.pack(fill=tk.X, pady=2)
        
        ttk.Label(row2, text="Cantidad:", width=10).pack(side=tk.LEFT)
        self.quantity_var = tk.StringVar()
        self.quantity_entry = ttk.Entry(
            row2, 
            textvariable=self.quantity_var, 
            width=10,
            font=FONT_NORMAL,
            justify=tk.RIGHT
        )
        self.quantity_entry.pack(side=tk.LEFT, padx=5)
        self.quantity_entry.bind('<KeyRelease>', self.calculate_item_total)
        
        ttk.Label(row2, text="O Dinero:", width=9).pack(side=tk.LEFT, padx=(10, 0))
        self.money_var = tk.StringVar()
        self.money_entry = ttk.Entry(
            row2, 
            textvariable=self.money_var, 
            width=10,
            font=FONT_NORMAL,
            justify=tk.RIGHT
        )
        self.money_entry.pack(side=tk.LEFT, padx=5)
        self.money_entry.bind('<KeyRelease>', self.calculate_quantity_from_money)
        
        ttk.Label(row2, text="Subtotal:", width=8).pack(side=tk.LEFT)
        self.subtotal_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.subtotal_var, state="readonly", 
                width=10, font=FONT_NORMAL, justify=tk.RIGHT).pack(side=tk.LEFT, padx=5)
        
        # Botón Agregar
        ttk.Button(
            product_search_frame, 
            text="➕ Agregar Producto",
            command=self.add_product_to_sale,
            bootstyle='success'
        ).pack(pady=(5, 0))
        
        # ─── Sección: Lista de Productos ───
        items_frame = ttk.LabelFrame(left_column, text=" 🛒 Productos en la Venta ", padding="8")
        items_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        
        # Botones de acciones (empaquetados ANTES que la tabla, con
        # side=BOTTOM, para que no se los coma el expand=True del árbol)
        items_buttons = ttk.Frame(items_frame)
        items_buttons.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))

        ttk.Button(items_buttons, text="🗑️ Quitar",
                command=self.remove_product_from_sale,
                bootstyle='danger').pack(side=tk.LEFT, padx=2)

        ttk.Button(items_buttons, text="🧹 Limpiar Todo",
                command=self.clear_sale_items,
                bootstyle='danger-outline').pack(side=tk.LEFT, padx=2)

        # Treeview
        items_table_frame = ttk.Frame(items_frame)
        items_table_frame.pack(fill=tk.BOTH, expand=True)
        items_table_frame.rowconfigure(0, weight=1)
        items_table_frame.columnconfigure(0, weight=1)

        columns = ('Producto', 'Cant.', 'P.Unit', 'Subtotal')
        self.items_tree = ttk.Treeview(
            items_table_frame,
            columns=columns,
            show='headings',
            height=8
        )

        # Configurar columnas más compactas
        self.items_tree.heading('Producto', text='Producto')
        self.items_tree.heading('Cant.', text='Cant.')
        self.items_tree.heading('P.Unit', text='P.Unit')
        self.items_tree.heading('Subtotal', text='Subtotal')

        self.items_tree.column('Producto', width=180, minwidth=120, anchor=tk.W)
        self.items_tree.column('Cant.', width=60, minwidth=50, anchor=tk.E)
        self.items_tree.column('P.Unit', width=100, minwidth=80, anchor=tk.E)
        self.items_tree.column('Subtotal', width=100, minwidth=80, anchor=tk.E)

        # Scrollbars
        items_vsb = ttk.Scrollbar(items_table_frame, orient=tk.VERTICAL, command=self.items_tree.yview)
        items_hsb = ttk.Scrollbar(items_table_frame, orient=tk.HORIZONTAL, command=self.items_tree.xview)
        self.items_tree.configure(yscrollcommand=items_vsb.set, xscrollcommand=items_hsb.set)

        self.items_tree.grid(row=0, column=0, sticky="nsew")
        items_vsb.grid(row=0, column=1, sticky="ns")
        items_hsb.grid(row=1, column=0, sticky="ew")

        # ═══════════════════════════════════════════════════════════
        # COLUMNA DERECHA - INFORMACIÓN DE VENTA
        # ═══════════════════════════════════════════════════════════
        
        # ─── Total de la Venta (destacado) ───
        total_frame = ttk.LabelFrame(right_column, text=" 💰 Total ", padding="10")
        total_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.total_sale_var = tk.StringVar(value="$0.00")
        ttk.Label(
            total_frame,
            textvariable=self.total_sale_var,
            font=FONT_TITLE,
            bootstyle="primary"
        ).pack()
        
        # ─── Estado y Tipo de Pago ───
        payment_frame = ttk.LabelFrame(right_column, text=" 💳 Forma de Pago ", padding="10")
        payment_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Estado de pago
        ttk.Label(payment_frame, text="Estado:", font=FONT_BOLD).pack(anchor=tk.W, pady=(0, 5))
        self.status_var = tk.StringVar(value="paid")
        
        status_buttons = ttk.Frame(payment_frame)
        status_buttons.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Radiobutton(
            status_buttons, 
            text="💵 Al Contado", 
            variable=self.status_var, 
            value="paid", 
            command=self.on_status_changed
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Radiobutton(
            status_buttons, 
            text="📝 Fiado", 
            variable=self.status_var, 
            value="pending", 
            command=self.on_status_changed
        ).pack(side=tk.LEFT)
        
        # Tipo de pago
        ttk.Label(payment_frame, text="Tipo:", font=FONT_BOLD).pack(anchor=tk.W, pady=(0, 5))
        self.payment_type_var = tk.StringVar(value="cash")
        payment_combo = ttk.Combobox(
            payment_frame, 
            textvariable=self.payment_type_var, 
            width=18, 
            state="readonly",
            font=FONT_NORMAL
        )
        payment_combo['values'] = ["Efectivo", "Crédito"]
        payment_combo.pack(fill=tk.X)
        
        # ─── Cliente (para ventas fiadas) ───
        client_frame = ttk.LabelFrame(right_column, text=" 👤 Cliente ", padding="10")
        client_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.client_var = tk.StringVar()
        self.client_combo = ttk.Combobox(
            client_frame, 
            textvariable=self.client_var, 
            width=22, 
            state="disabled",
            font=FONT_NORMAL
        )
        self.client_combo.pack(fill=tk.X, pady=(0, 5))

        # Búsqueda incremental: al escribir se filtra la lista de clientes,
        # en lugar de tener que deslizar el combo completo para encontrarlo.
        self._client_typing_timer = None
        self._last_client_search = None
        self.client_combo.bind('<KeyRelease>', self._on_client_typing)
        self.client_combo.bind('<Return>', self._on_client_enter)
        self.client_combo.bind('<Tab>', lambda e: self._verify_and_set_client())
        self.client_combo.bind('<FocusOut>', lambda e: self._verify_and_set_client())
        self.client_combo.bind('<Button-1>', self._on_client_combo_click)

        ttk.Label(
            client_frame,
            text="Escriba para buscar por nombre",
            font=FONT_SMALL,
            bootstyle='secondary'
        ).pack(anchor=tk.W)
        
        self.add_client_btn = ttk.Button(
            client_frame, 
            text="➕ Nuevo Cliente",
            command=self.add_new_client,
            state="disabled",
            bootstyle='success'
        )
        self.add_client_btn.pack(fill=tk.X)
        
        # ─── Ajustes (solo ventas fiadas) ───
        adjustment_frame = ttk.LabelFrame(right_column, text=" ⚖️ Ajustes ", padding="10")
        adjustment_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Ajuste numérico
        adj_row1 = ttk.Frame(adjustment_frame)
        adj_row1.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(adj_row1, text="Monto:", font=FONT_NORMAL).pack(side=tk.LEFT)
        self.adjustment_var = tk.StringVar(value="0")
        self.adjustment_entry = ttk.Entry(
            adj_row1, 
            textvariable=self.adjustment_var, 
            width=12,
            font=FONT_NORMAL,
            justify=tk.RIGHT,
            state="disabled"
        )
        self.adjustment_entry.pack(side=tk.LEFT, padx=(5, 0))
        self.adjustment_entry.bind('<KeyRelease>', self.calculate_total_with_adjustment)
        
        ttk.Label(
            adj_row1, 
            text="(+/-)",
            font=FONT_SMALL,
            bootstyle='secondary'
        ).pack(side=tk.LEFT, padx=(5, 0))
        
        # Razón del ajuste
        ttk.Label(adjustment_frame, text="Razón:", font=FONT_NORMAL).pack(anchor=tk.W, pady=(0, 2))
        self.adjustment_reason_var = tk.StringVar()
        self.adjustment_reason_entry = ttk.Entry(
            adjustment_frame,
            textvariable=self.adjustment_reason_var,
            font=FONT_NORMAL,
            state="disabled"
        )
        self.adjustment_reason_entry.pack(fill=tk.X)
        
        # ─── Botones de Acción ───
        action_frame = ttk.Frame(right_column)
        action_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(
            action_frame,
            text="💾 Guardar Venta",
            command=self.save_complete_sale,
            bootstyle='primary'
        ).pack(fill=tk.X, pady=(0, 5))

        ttk.Button(
            action_frame,
            text="🗑️ Limpiar Todo",
            command=self.clear_all_form,
            bootstyle='danger-outline'
        ).pack(fill=tk.X)
        
        # ═══════════════════════════════════════════════════════════
        # CONFIGURAR PESTAÑA DE LISTA DE VENTAS
        # ═══════════════════════════════════════════════════════════
        self.setup_sales_list_ui()
        
        # Ajustar focus inicial
        self.product_combo.focus_set()


    # NOTA: Esta función reemplaza completamente tu setup_ui() actual
    # El resto de funciones (load_data, add_product_to_sale, etc.) permanecen igual
    
    def setup_sales_list_ui(self):
        """Configura la UI para lista de ventas"""
        # Frame principal
        main_frame = ttk.Frame(self.sales_list_frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, text="Lista de Ventas", 
                               font=FONT_TITLE)
        title_label.pack(pady=(0, 10))
        
        # Frame para botones
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(controls_frame, text="Actualizar Lista",
                  command=self.load_sales, bootstyle="secondary-outline").pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Ver Detalles",
                  command=self.view_sale_details, bootstyle="info").pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Editar Venta",
                  command=self.edit_sale, bootstyle="primary").pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Eliminar Venta",
                  command=self.delete_sale, bootstyle="danger").pack(side=tk.LEFT, padx=5)

        # Treeview para mostrar ventas
        # NOTA: antes existía aquí un Frame vacío ("tree_frame") empaquetado con
        # fill=BOTH, expand=True por encima de la tabla. Al no contener nada,
        # ese frame igual reclamaba espacio vertical disponible y empujaba la
        # tabla hacia abajo, dejando el hueco entre los botones y la lista.
        # Se eliminó y la tabla se monta directamente en un contenedor grid.
        sales_table_frame = ttk.Frame(main_frame)
        sales_table_frame.pack(fill=tk.BOTH, expand=True)
        sales_table_frame.rowconfigure(0, weight=1)
        sales_table_frame.columnconfigure(0, weight=1)

        columns = ('ID', 'Cliente', 'Subtotal', 'Ajuste', 'Total', 'Estado', 'Tipo Pago', 'Fecha')
        self.sales_tree = ttk.Treeview(sales_table_frame, columns=columns, show='headings')
        self.sales_tree.tag_configure('credit', **ROW_COLORS['warning'])
        self.sales_tree.tag_configure('paid', **ROW_COLORS['success'])

        # Configurar columnas
        col_config = {
            'ID': (50, 40, 'center'),
            'Cliente': (150, 100, 'w'),
            'Subtotal': (125, 90, 'e'),
            'Ajuste': (125, 90, 'e'),
            'Total': (125, 90, 'e'),
            'Estado': (100, 80, 'center'),
            'Tipo Pago': (100, 80, 'center'),
            'Fecha': (150, 120, 'center'),
        }
        for col in columns:
            self.sales_tree.heading(col, text=col)
            width, minwidth, anchor = col_config[col]
            self.sales_tree.column(col, width=width, minwidth=minwidth, anchor=anchor)

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(sales_table_frame, orient=tk.VERTICAL, command=self.sales_tree.yview)
        h_scrollbar = ttk.Scrollbar(sales_table_frame, orient=tk.HORIZONTAL, command=self.sales_tree.xview)
        self.sales_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        self.sales_tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        # Doble clic sobre una venta = ver el detalle directamente
        self.sales_tree.bind('<Double-1>', lambda e: self.view_sale_details())

    def _on_product_typing(self, event=None):
        """Maneja la escritura en el campo de producto SIN interferencias"""
        # Cancelar timer anterior si existe
        if self._typing_timer:
            self.window.after_cancel(self._typing_timer)
        
        # Configurar nuevo timer para filtrar después de que termine de escribir
        self._typing_timer = self.window.after(300, self._perform_filtering)

    def _perform_filtering(self):
        """Realiza el filtrado sin interferir con el foco"""
        search_text = self.product_var.get().lower().strip()
        
        # Solo filtrar si el texto ha cambiado
        if search_text == self._last_search:
            return
        
        self._last_search = search_text
        
        if not search_text:
            # Mostrar todos los productos disponibles
            available_products = [p.name for p in self.products if p.stock > 0]
            self._update_combo_values(available_products)
            self._clear_product_info()
            return
        
        # Filtrar productos que coincidan
        filtered_products = []
        exact_match = None
        
        for product in self.products:
            if product.stock > 0:  # Solo productos con stock
                product_name_lower = product.name.lower()
                if search_text in product_name_lower:
                    filtered_products.append(product.name)
                    # Verificar coincidencia exacta
                    if product_name_lower == search_text:
                        exact_match = product
        
        # Actualizar lista de productos
        self._update_combo_values(filtered_products)
        
        # SOLO cargar info si hay coincidencia exacta Y no estamos escribiendo
        if exact_match and not self._is_typing_actively():
            self._load_product_info(exact_match)
        elif not exact_match:
            self._clear_product_info()

    def _on_product_focus_out(self, event=None):
        """Maneja cuando el campo pierde el foco - verifica selección"""
        self._verify_and_load_product()

    def _is_typing_actively(self):
        """Determina si el usuario está escribiendo activamente"""
        # Si el texto actual no coincide exactamente con ningún producto, está escribiendo
        current_text = self.product_var.get().strip()
        for product in self.products:
            if product.name == current_text:
                return False  # Coincidencia exacta, no está escribiendo
        return True  # No hay coincidencia exacta, probablemente escribiendo

        # 5. AGREGA este método para verificar selección:
    def _verify_and_load_product(self):
        """Verifica si hay un producto seleccionado válido y carga su información"""
        product_name = self.product_var.get().strip()
        if not product_name:
            self._clear_product_info()
            return
        
        # Buscar producto exacto
        selected_product = None
        for product in self.products:
            if product.name == product_name:
                selected_product = product
                break
        
        if selected_product:
            self._load_product_info(selected_product)
        else:
            # Si no es exacto, buscar el más cercano
            closest_match = None
            for product in self.products:
                if product.stock > 0 and product.name.lower().startswith(product_name.lower()):
                    closest_match = product
                    break
            
            if closest_match:
                # Autocompletar con el producto más cercano
                self.product_var.set(closest_match.name)
                self._load_product_info(closest_match)
            else:
                self._clear_product_info()

    def _update_combo_values(self, values):
        """Actualiza los valores del combo sin perder foco"""
        try:
            # Guardar posición del cursor
            cursor_pos = self.product_combo.index(tk.INSERT)
            
            # Actualizar valores
            self.product_combo['values'] = values
            
            # Restaurar posición del cursor si es posible
            try:
                self.product_combo.icursor(cursor_pos)
            except:
                pass  # Ignorar si no se puede restaurar
                
        except Exception as e:
            print(f"Error actualizando combo: {e}")

    def _load_product_info(self, product):
        """Carga la información del producto seleccionado"""
        self.unit_price_var.set(f"{product.price:,.2f}")
        self.stock_var.set(f"{product.stock}")

    def _clear_product_info(self):
        """Limpia la información del producto"""
        self.unit_price_var.set("")
        self.stock_var.set("")

    def _on_combo_click(self, event=None):
        """Maneja el clic en el combo"""
        self._is_clicking = True
        # Si está vacío, mostrar todos los productos
        if not self.product_var.get().strip():
            available_products = [p.name for p in self.products if p.stock > 0]
            self._update_combo_values(available_products)
        else:
            # Si hay texto, verificar si es un producto válido
            self.window.after(100, self._verify_and_load_product)  # Pequeño delay
        self._is_clicking = False

    def _on_product_enter(self, event=None):
        """Maneja Enter en el campo de producto"""
        self._verify_and_load_product()
        # Enfocar el campo de cantidad si hay un producto válido seleccionado
        if self.unit_price_var.get() and self.stock_var.get():
            if self.unit_price_var.get() and self.stock_var.get():
                self.quantity_entry.focus_set()
        return 'break'  # Evitar que se propague el evento


    def _on_product_tab(self, event=None):
        """Maneja Tab en el campo de producto"""
        self._verify_and_load_product()

    # ─────────────────────────────────────────────────────────────
    # Búsqueda incremental de cliente (venta fiada)
    # ─────────────────────────────────────────────────────────────
    def _on_client_typing(self, event=None):
        """Programa el filtrado de clientes mientras se escribe"""
        if event is not None and event.keysym in ('Tab', 'Return', 'Escape'):
            return
        if self._client_typing_timer:
            self.window.after_cancel(self._client_typing_timer)
        self._client_typing_timer = self.window.after(250, self._perform_client_filtering)

    def _perform_client_filtering(self):
        """Filtra la lista del combo de clientes según el texto escrito"""
        search_text = self.client_var.get().lower().strip()
        if search_text == self._last_client_search:
            return
        self._last_client_search = search_text

        if not search_text:
            self.client_combo['values'] = [c.name for c in self.clients]
            return

        filtered = [c.name for c in self.clients if search_text in c.name.lower()]
        self.client_combo['values'] = filtered

        # Mostrar la lista filtrada automáticamente para que sea evidente
        # que se está buscando (en vez de escribir "a ciegas")
        try:
            self.client_combo.event_generate('<Down>')
        except Exception:
            pass

    def _on_client_combo_click(self, event=None):
        """Si el campo está vacío, mostrar todos los clientes al hacer clic"""
        if not self.client_var.get().strip():
            self.client_combo['values'] = [c.name for c in self.clients]

    def _on_client_enter(self, event=None):
        """Maneja Enter en el campo de cliente"""
        self._verify_and_set_client()
        return 'break'

    def _verify_and_set_client(self):
        """
        Verifica que el texto escrito corresponda a un cliente real.
        Si hay una única coincidencia clara, autocompleta el nombre exacto.
        """
        typed = self.client_var.get().strip()
        if not typed:
            return

        # Coincidencia exacta (sin importar mayúsculas/minúsculas)
        for client in self.clients:
            if client.name.lower() == typed.lower():
                self.client_var.set(client.name)
                return

        # Coincidencia única por contención de texto -> autocompletar
        matches = [c for c in self.clients if typed.lower() in c.name.lower()]
        if len(matches) == 1:
            self.client_var.set(matches[0].name)
        # Si hay varias coincidencias o ninguna, se deja el texto tal cual
        # para que el usuario siga afinando la búsqueda; la validación final
        # de "cliente existente" ocurre al guardar la venta.

    def debug_products(self):
        """Método de debug para verificar productos cargados"""
        print(f"\n=== DEBUG PRODUCTOS ===")
        print(f"Total productos cargados: {len(self.products)}")
        for i, product in enumerate(self.products[:5]):  # Mostrar solo los primeros 5
            print(f"{i+1}. {product.name} - Stock: {product.stock} - Precio: {product.price}")
        if len(self.products) > 5:
            print(f"... y {len(self.products) - 5} más")
        print("=====================\n")

    def _select_current_product(self):
        """Selecciona el producto actual y carga su información"""
        product_name = self.product_var.get().strip()
        if not product_name:
            return
        
        # Buscar producto exacto
        selected_product = None
        for product in self.products:
            if product.name.lower() == product_name.lower():
                selected_product = product
                # Corregir capitalización
                self.product_var.set(product.name)
                break
        
        if selected_product:
            self._load_product_info(selected_product)
            # Enfocar siguiente campo
            self.window.after(50, lambda: self.quantity_var.focus_set() if hasattr(self, 'quantity_var') else None)
        else:
            # Producto no encontrado
            self._clear_product_info()
    
    def load_data(self):
        """Carga los datos necesarios"""
        self.load_products()
        self.load_clients()
        self.load_sales()
    
    def load_products(self):
        """Carga la lista de productos - MEJORADO CON DEBUG"""
        self.products = Product.get_all()
        # Filtrar solo productos con stock disponible
        available_products = [p.name for p in self.products if p.stock > 0]
        self.product_combo['values'] = available_products
        print(f"Productos cargados: {len(self.products)} total, {len(available_products)} disponibles")

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

    def _get_combo_entry(self):
        """Obtiene el widget Entry interno del Combobox"""
        return self.product_combo.nametowidget(self.product_combo.winfo_children()[0])


    def show_all_products(self):
        """Muestra todos los productos disponibles"""
        available_products = [p.name for p in self.products if p.stock > 0]
        self.product_combo['values'] = available_products

    # 4. MODIFICAR el método on_product_selected() para manejar mejor la selección:
    def on_product_selected(self, event=None):
        """Maneja la selección de producto desde el dropdown - MEJORADO"""
        print(f"Producto seleccionado: {self.product_var.get()}")  # Debug
        
        product_name = self.product_var.get().strip()
        if not product_name:
            self._clear_product_info()
            return
        
        # Buscar producto exacto
        found_product = None
        for product in self.products:
            if product.name == product_name:
                found_product = product
                break
        
        if found_product:
            print(f"Cargando info para: {found_product.name}, Stock: {found_product.stock}, Precio: {found_product.price}")  # Debug
            self._load_product_info(found_product)
            # Limpiar campos de cantidad al seleccionar nuevo producto
            self.quantity_var.set("")
            self.money_var.set("")
            self.subtotal_var.set("")
        else:
            print(f"Producto no encontrado: {product_name}")  # Debug
            self._clear_product_info()
    
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
        """Agrega un producto a la lista de venta - VALIDACIÓN MEJORADA"""
        # Validaciones
        product_name = self.product_var.get().strip()
        if not product_name:
            messagebox.showerror("Error", "Debe seleccionar un producto")
            self.product_combo.focus_set()
            return
        
        # Verificar que el producto existe exactamente como se escribió
        product = None
        for p in self.products:
            if p.name.lower() == product_name.lower():
                product = p
                # Actualizar el nombre con la capitalización correcta
                self.product_var.set(p.name)
                break
        
        if not product:
            messagebox.showerror("Error", f"Producto '{product_name}' no encontrado.\nVerifique que el nombre sea exacto.")
            self.product_combo.focus_set()
            return
        
        if product.stock <= 0:
            messagebox.showerror("Error", f"Producto '{product_name}' sin stock disponible")
            return
        
        # Verificar si se ingresó cantidad o dinero recibido
        has_quantity = self.quantity_var.get() and safe_float_conversion(self.quantity_var.get() or 0) > 0
        has_money = self.money_var.get() and safe_float_conversion(self.money_var.get() or 0) > 0
        
        if not has_quantity and not has_money:
            messagebox.showerror("Error", "Debe ingresar una cantidad o el dinero recibido")
            return
        
        try:
            quantity = safe_float_conversion(self.quantity_var.get() or 0)
            unit_price = safe_float_conversion(self.unit_price_var.get())
            subtotal = safe_float_conversion(self.subtotal_var.get())
            
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
            
            # Enfocar de nuevo en el combo de productos para siguiente producto
            self.product_combo.focus_set()
            
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
        """Calcula el total de la venta - AHORA LLAMA A LA FUNCIÓN CON AJUSTE"""
        self.calculate_total_with_adjustment()
    
    def clear_product_fields(self):
        """Limpia los campos de producto - VERSIÓN ACTUALIZADA"""
        self.product_var.set("")
        self._clear_product_info()
        self.quantity_var.set("")
        self.money_var.set("")
        self.subtotal_var.set("")
        self._last_search = ""
        # Mostrar todos los productos disponibles
        available_products = [p.name for p in self.products if p.stock > 0]
        self._update_combo_values(available_products)
        
    def on_status_changed(self):
        """Maneja el cambio de estado de pago - ACTUALIZADO CON AJUSTES"""
        if self.status_var.get() == "pending":
            # FIADO - Requiere cliente y permite ajustes
            # "normal" (en vez de "readonly") para poder escribir y filtrar
            self.client_combo.configure(state="normal")
            self.add_client_btn.configure(state="normal")
            self.adjustment_entry.configure(state="normal")
            self.adjustment_reason_entry.configure(state="normal")
        else:
            # AL CONTADO - No requiere cliente ni ajustes
            self.client_combo.configure(state="disabled")
            self.add_client_btn.configure(state="disabled")
            self.adjustment_entry.configure(state="disabled")
            self.adjustment_reason_entry.configure(state="disabled")
            self.client_var.set("")
            self.adjustment_var.set("0")
            self.adjustment_reason_var.set("")
        
        # Recalcular total con ajuste
        self.calculate_total_with_adjustment()
    
    def calculate_total_with_adjustment(self, event=None):
        """Calcula el total de la venta incluyendo ajustes"""
        # Calcular subtotal de productos
        subtotal = sum(item['subtotal'] for item in self.sale_items)
        
        # Obtener ajuste
        try:
            adjustment = safe_float_conversion(self.adjustment_var.get() or 0)
        except:
            adjustment = 0.0
        
        # Calcular total final
        total = subtotal + adjustment
        
        # Formatear y mostrar
        self.total_sale_var.set(format_currency(total))
        
        # Actualizar color del total según el ajuste
        if adjustment > 0:
            # Cargo adicional - color naranja
            pass  # Puedes agregar estilo si quieres
        elif adjustment < 0:
            # Descuento - color verde
            pass  # Puedes agregar estilo si quieres

    def add_new_client(self):
        """Abre diálogo para agregar nuevo cliente"""
        dialog = tk.Toplevel(self.window)
        dialog.title("Nuevo Cliente")
        dialog.resizable(False, False)
        dialog.transient(self.window)
        hacer_modal(dialog)
        centrar_ventana(dialog, 300, 500)

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
        
        ttk.Button(button_frame, text="Guardar", command=save_client, bootstyle="primary").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancelar", command=dialog.destroy, bootstyle="secondary").pack(side=tk.LEFT, padx=5)
        
        dialog.bind('<Return>', lambda e: save_client())
    
    def save_complete_sale(self):
        """Guarda la venta y actualiza la deuda del cliente inmediatamente"""
        if not self.sale_items:
            messagebox.showerror("Error", "Debe agregar al menos un producto a la venta")
            return

        # Validación estricta para ventas fiadas
        if self.status_var.get() == 'pending':
            self._verify_and_set_client()  # último intento de autocompletar por nombre
            if not self.client_var.get() or self.client_var.get() == "Sin cliente":
                messagebox.showerror("Error", "Debe seleccionar un cliente válido para ventas fiadas")
                return
            if not any(c.name == self.client_var.get() for c in self.clients):
                messagebox.showerror(
                    "Error",
                    f"'{self.client_var.get()}' no coincide con ningún cliente registrado.\n"
                    "Verifique el nombre o cree el cliente con '➕ Nuevo Cliente'."
                )
                return

        conn = None
        try:
            fiada = self.status_var.get() == 'pending'

            # Obtener cliente para ventas fiadas
            client_id = None
            if fiada:
                client = next((c for c in self.clients if c.name == self.client_var.get()), None)
                if not client:
                    raise ValueError("Cliente seleccionado no existe")
                client_id = client.id

            # Obtener ajuste
            adjustment = 0.0
            adjustment_reason = None
            if fiada:
                try:
                    adjustment = safe_float_conversion(self.adjustment_var.get() or 0)
                    adjustment_reason = self.adjustment_reason_var.get().strip() or None
                except:
                    adjustment = 0.0

            items = []
            for item in self.sale_items:
                product = next((p for p in self.products if p.id == item['product_id']), None)
                if not product:
                    raise ValueError(f"Producto ID {item['product_id']} no encontrado")
                items.append({**item, 'cost_price': product.cost_price})

            # Con la base en la nube guardar tarda ~1 s: que se note que está trabajando
            self.window.config(cursor="watch")
            self.window.update_idletasks()

            conn = get_connection()
            sale_id, _total = registrar_venta(conn, items, self.user.id, client_id, fiada,
                                              adjustment, adjustment_reason)
            conn.commit()

            # Mensaje de éxito con información del ajuste
            success_msg = f"Venta #{sale_id} guardada correctamente"
            if adjustment != 0:
                if adjustment > 0:
                    success_msg += f"\n(Cargo adicional: ${adjustment:,.2f})"
                else:
                    success_msg += f"\n(Descuento aplicado: ${abs(adjustment):,.2f})"
            
            messagebox.showinfo("Éxito", success_msg)
            self.clear_all_form()
            self.load_data()

        except Exception as e:
            if conn:
                conn.rollback()
            messagebox.showerror("Error", f"No se pudo completar la venta: {str(e)}")
        finally:
            self.window.config(cursor="")
            if conn:
                conn.close()
    
    def clear_all_form(self):
        """Limpia todo el formulario - MEJORADO CON AJUSTES"""
        self.clear_product_fields()
        self.sale_items.clear()
        self.update_items_tree()
        self.total_sale_var.set("$0.00")
        
        # RESETEAR A VALORES POR DEFECTO
        self.status_var.set("paid")
        self.client_var.set("")
        self.payment_type_var.set("cash")
        self.adjustment_var.set("0")          # NUEVO
        self.adjustment_reason_var.set("")    # NUEVO
        
        # Actualizar estado de controles
        self.on_status_changed()
    

    
    def view_sale_details(self):
        """Ver detalles completos de una venta seleccionada en la lista"""
        selected = self.sales_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Por favor seleccione una venta para ver detalles")
            return

        sale_id = self.sales_tree.item(selected[0], 'values')[0]
        SaleDetailWindow(self.window, sale_id)

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
            edit_window.resizable(False, False)
            centrar_ventana(edit_window, 400, 300)
            
            # Frame principal
            main_frame = ttk.Frame(edit_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Total (editable)
            ttk.Label(main_frame, text="Total:").grid(row=0, column=0, sticky=tk.W, pady=5)
            total_var = tk.StringVar(value=str(sale.total))
            total_entry = ttk.Entry(main_frame, textvariable=total_var, width=15)
            total_entry.grid(row=0, column=1, pady=5, padx=(5, 0))
            
            # Pagada / pendiente ya no se elige a mano: sale de los abonos
            # del cliente (servicios.ventas.editar_venta lo recalcula).
            ttk.Label(main_frame, text="Tipo:").grid(row=1, column=0, sticky=tk.W, pady=5)
            tipos = {"Contado": "cash", "Fiado": "credit"}
            payment_var = tk.StringVar(value="Fiado" if sale.payment_method == "credit" else "Contado")
            payment_combo = ttk.Combobox(main_frame, textvariable=payment_var, width=15, state="readonly")
            payment_combo['values'] = list(tipos)
            payment_combo.grid(row=1, column=1, pady=5, padx=(5, 0))

            # Cliente
            ttk.Label(main_frame, text="Cliente:").grid(row=2, column=0, sticky=tk.W, pady=5)
            actual = next((c.name for c in self.clients if c.id == sale.client_id), "")
            client_var = tk.StringVar(value=actual)
            client_combo = ttk.Combobox(main_frame, textvariable=client_var, width=20)
            client_combo['values'] = [c.name for c in self.clients]
            client_combo.grid(row=2, column=1, pady=5, padx=(5, 0))

            def save_changes():
                """Guardar cambios (antes creaba una venta duplicada)"""
                conn = None
                try:
                    new_total = safe_float_conversion(total_var.get())
                    fiada = tipos[payment_var.get()] == "credit"
                    cliente = next((c for c in self.clients if c.name == client_var.get()), None)
                    if fiada and cliente is None:
                        messagebox.showerror("Error", "Seleccione un cliente registrado para la venta fiada")
                        return

                    conn = get_connection()
                    editar_venta(conn, sale.id, new_total, fiada, cliente.id if cliente else None)
                    conn.commit()
                    messagebox.showinfo("Éxito", "Venta actualizada correctamente")
                    edit_window.destroy()
                    self.load_data()

                except ValueError as e:
                    if conn:
                        conn.rollback()
                    messagebox.showerror("Error", str(e) or "El total debe ser un número válido")
                except Exception as e:
                    if conn:
                        conn.rollback()
                    messagebox.showerror("Error", f"Error al actualizar: {str(e)}")
                finally:
                    if conn:
                        conn.close()
            
            # Botones
            button_frame = ttk.Frame(main_frame)
            button_frame.grid(row=4, column=0, columnspan=2, pady=20)
            
            ttk.Button(button_frame, text="Guardar", command=save_changes, bootstyle="primary").pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancelar", command=edit_window.destroy, bootstyle="secondary").pack(side=tk.LEFT, padx=5)
            
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
            try:
                # Stock, deuda, archivo y borrado: servicios/ventas.py
                eliminar_venta(conn, sale.id)
                conn.commit()
                messagebox.showinfo("Éxito", "Venta eliminada correctamente")
                self.load_data()
            except Exception as e:
                conn.rollback()
                messagebox.showerror("Error", f"Error al eliminar: {str(e)}")
            finally:
                conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Error inesperado: {str(e)}")
    
    def update_sales_tree(self):
        """Muestra las ventas con información de ajustes"""
        for item in self.sales_tree.get_children():
            self.sales_tree.delete(item)
        
        for sale in self.sales:
            # Obtener nombre del cliente
            client_name = "Venta al contado"
            if sale.client_id:
                client = next((c for c in self.clients if c.id == sale.client_id), None)
                client_name = client.name if client else "Cliente no encontrado"
            
            # Validación para ventas fiadas
            if sale.status == 'pending' and client_name == "Venta al contado":
                client_name = "CLIENTE FALTANTE"
            
            # Calcular subtotal y ajuste
            adjustment = getattr(sale, 'adjustment', 0) or 0
            subtotal = sale.total - adjustment
            
            self.sales_tree.insert('', tk.END, values=(
                sale.id,
                client_name,
                format_currency(subtotal),
                format_currency(adjustment),
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