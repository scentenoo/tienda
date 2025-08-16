import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from models.sale import Sale
from models.purchase import Purchase
from models.expense import Expense
from models.loss import Loss  # Agregar importación de Loss
from utils.excel_exporter import ExcelExporter
import os
from config.database import get_connection
from utils.formatters import format_currency, format_number

class ReportsWindow:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        
        # Verificar que el usuario sea administrador
        if user.role != 'admin':
            messagebox.showerror("Error", "Solo los administradores pueden acceder a los reportes")
            return
        
        # Crear ventana
        self.window = tk.Toplevel(parent)
        self.window.title("Reportes y Análisis")
        self.window.geometry("900x700")
        self.window.resizable(True, True)
        
        # Inicializar el diccionario primero
        self.financial_labels = {}
        
        # Luego configurar la UI
        self.setup_ui()
        
        # Finalmente cargar los datos
        self.load_financial_summary()
    
    def setup_ui(self):
        """Configura la interfaz de usuario con pestañas y nuevo estilo"""
        # Configuración de estilos
        self.style = ttk.Style()
        self.style.configure('TFrame', background='#f5f5f5')
        self.style.configure('TButton', font=('Arial', 10), padding=8)
        self.style.configure('Header.TLabel', font=('Arial', 12, 'bold'), foreground='#495057')
        self.style.configure('TNotebook', background='#f5f5f5')
        self.style.configure('TNotebook.Tab', font=('Arial', 10, 'bold'), padding=[10, 5])
        
        # Frame principal
        main_frame = ttk.Frame(self.window, style='TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header
        header = tk.Frame(main_frame, bg='#343a40', height=50)
        header.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(header, 
                text="Reportes y Análisis Financiero", 
                font=("Arial", 16, "bold"),
                foreground="white",
                background="#343a40").pack(side=tk.LEFT, padx=20)
        
        # Notebook (pestañas)
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Pestaña 1: Resumen Financiero
        summary_tab = ttk.Frame(notebook)
        notebook.add(summary_tab, text="📊 Resumen")
        self.setup_summary_tab(summary_tab)
        
        # Pestaña 3: Exportar
        export_tab = ttk.Frame(notebook)
        notebook.add(export_tab, text="📤 Exportar")
        self.setup_export_tab(export_tab)

    def setup_summary_tab(self, parent):
        """Configura la pestaña de resumen financiero con herramientas de diagnóstico MEJORADAS"""
        # Frame con scroll
        canvas = tk.Canvas(parent, borderwidth=0, background="#ffffff")
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Sección de flujo de efectivo
        cash_frame = ttk.LabelFrame(scrollable_frame, text="Flujo de Efectivo", padding=10)
        cash_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Crear filas para los datos financieros
        self.create_summary_row(cash_frame, "💰 Ingresos por Ventas:", 'sales', "green")
        self.create_summary_row(cash_frame, "💸 Egresos por Compras:", 'purchases', "red")
        self.create_summary_row(cash_frame, "🏪 Gastos Operativos:", 'expenses', "red")
        self.create_summary_row(cash_frame, "💵 EFECTIVO DISPONIBLE:", 'cash', "blue", bold=True)
        
        # Sección de inventario
        inventory_frame = ttk.LabelFrame(scrollable_frame, text="Valor del Inventario", padding=10)
        inventory_frame.pack(fill=tk.X, pady=5, padx=5)
        
        self.create_summary_row(inventory_frame, "📦 Valor de Compras:", 'inventory_purchases', "blue")
        self.create_summary_row(inventory_frame, "✅ Valor Vendido:", 'inventory_sold', "green")
        self.create_summary_row(inventory_frame, "🚚 Flete Pagado:", 'total_freight', "red")
        self.create_summary_row(inventory_frame, "🧾 IVA Pagado:", 'total_iva', "red")
        self.create_summary_row(inventory_frame, "❌ Pérdidas de Inventario:", 'losses', "orange")
        self.create_summary_row(inventory_frame, "📊 INVENTARIO ACTUAL:", 'current_inventory', "purple", bold=True)
        
        # Frame para botones (EXPANDIDO)
        buttons_frame = ttk.Frame(scrollable_frame)
        buttons_frame.pack(pady=15)
        
        # Fila 1 de botones
        row1 = ttk.Frame(buttons_frame)
        row1.pack(pady=5)
        
        ttk.Button(row1, 
                text="🔄 Actualizar Datos", 
                command=self.load_financial_summary,
                style='TButton').pack(side=tk.LEFT, padx=5)
        
        ttk.Button(row1, 
                text="💳 Sincronizar Pagos", 
                command=self.sync_sales_with_partial_payments,
                style='TButton').pack(side=tk.LEFT, padx=5)
        
    def create_summary_row(self, parent, label_text, key, color, bold=False):
        """Crea una fila de resumen financiero"""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=2)
        
        font = ("Arial", 11, "bold") if bold else ("Arial", 10, "bold")
        ttk.Label(frame, text=label_text, font=font).pack(side=tk.LEFT)
        
        value_font = ("Arial", 12, "bold") if bold else ("Arial", 10)
        self.financial_labels[key] = ttk.Label(frame, text="$0.00", 
                                            font=value_font, 
                                            foreground=color,
                                            anchor='e')
        self.financial_labels[key].pack(side=tk.RIGHT, fill=tk.X, expand=True)

    def setup_analysis_tab(self, parent):
        """Configura la pestaña de análisis"""
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Pestaña de productos
        products_frame = ttk.Frame(notebook)
        notebook.add(products_frame, text="📦 Productos")
        self.setup_products_analysis(products_frame)
        
        # Pestaña de clientes
        clients_frame = ttk.Frame(notebook)
        notebook.add(clients_frame, text="👥 Clientes")
        self.setup_clients_analysis(clients_frame)
        
        # Pestaña de pérdidas
        losses_frame = ttk.Frame(notebook)
        notebook.add(losses_frame, text="❌ Pérdidas")
        self.setup_losses_analysis(losses_frame)

    def setup_export_tab(self, parent):
        """Configura la pestaña de exportación"""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        ttk.Label(frame, 
                text="Exportar Reportes", 
                font=("Arial", 14, "bold")).pack(pady=(0, 20))
        
        # Botones de exportación
        export_buttons = [
            ("📊 Ventas", self.export_sales),
            ("🛒 Compras", self.export_purchases),
            ("❌ Pérdidas", self.export_losses),
            ("💰 Flujo de Caja", self.export_cash_flow),
            ("📦 Inventario", self.export_inventory_flow),
            ("📑 Reporte Completo", self.export_complete_report)
        ]
        
        for text, command in export_buttons:
            btn = ttk.Button(frame, text=text, command=command, style='TButton')
            btn.pack(fill=tk.X, pady=5)
        
    def setup_products_analysis(self, parent):
        """Configura el análisis de productos"""
        # Treeview para productos más vendidos
        columns = ('Producto', 'Cantidad Vendida', 'Ingresos Totales')
        self.products_tree = ttk.Treeview(parent, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.products_tree.heading(col, text=col)
            if col == 'Cantidad Vendida':
                self.products_tree.column(col, width=150)
            elif col == 'Ingresos Totales':
                self.products_tree.column(col, width=150)
            else:
                self.products_tree.column(col, width=200)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.products_tree.yview)
        self.products_tree.configure(yscrollcommand=scrollbar.set)
        
        self.products_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Botón para actualizar análisis
        ttk.Button(parent, text="Actualizar Análisis", 
                  command=self.load_products_analysis).pack(pady=5)
    
    def setup_clients_analysis(self, parent):
        """Configura el análisis de clientes"""
        # Treeview para clientes con deuda
        columns = ('Cliente', 'Deuda Total', 'Última Compra')
        self.clients_tree = ttk.Treeview(parent, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.clients_tree.heading(col, text=col)
            if col == 'Deuda Total':
                self.clients_tree.column(col, width=120)
            elif col == 'Última Compra':
                self.clients_tree.column(col, width=150)
            else:
                self.clients_tree.column(col, width=200)
        
        # Scrollbar
        scrollbar2 = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.clients_tree.yview)
        self.clients_tree.configure(yscrollcommand=scrollbar2.set)
        
        self.clients_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar2.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Botón para actualizar análisis
        ttk.Button(parent, text="Actualizar Análisis", 
                  command=self.load_clients_analysis).pack(pady=5)
    
    def setup_losses_analysis(self, parent):
        """Configura el análisis de pérdidas - NUEVO"""
        # Treeview para análisis de pérdidas
        columns = ('Producto', 'Cantidad Perdida', 'Costo Total', 'Tipo Principal')
        self.losses_tree = ttk.Treeview(parent, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.losses_tree.heading(col, text=col)
            if col == 'Cantidad Perdida':
                self.losses_tree.column(col, width=120)
            elif col == 'Costo Total':
                self.losses_tree.column(col, width=100)
            elif col == 'Tipo Principal':
                self.losses_tree.column(col, width=120)
            else:
                self.losses_tree.column(col, width=180)
        
        # Scrollbar
        scrollbar3 = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.losses_tree.yview)
        self.losses_tree.configure(yscrollcommand=scrollbar3.set)
        
        self.losses_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar3.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Botón para actualizar análisis
        ttk.Button(parent, text="Actualizar Análisis", 
                  command=self.load_losses_analysis).pack(pady=5)
        
    def calculate_inventory_sold_with_full_costs(self):
        """
        Método alternativo más detallado para calcular inventario vendido
        incluyendo todos los costos asociados (flete e IVA)
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            print("🔍 Calculando inventario vendido con costos completos...")
            
            # Obtener todas las ventas con costos detallados - NOMBRES CORREGIDOS
            cursor.execute('''
                SELECT 
                    p.id as product_id,
                    p.name as product_name,
                    p.cost_price,
                    SUM(sd.quantity) as total_sold_qty,
                    -- Calcular costo promedio con flete e IVA (COLUMNAS CORRECTAS)
                    AVG(
                        pd.unit_cost + 
                        COALESCE(
                            CASE 
                                WHEN pd.subtotal > 0 AND pur.shipping IS NOT NULL AND pur.shipping != '' AND CAST(pur.shipping AS REAL) > 0
                                THEN (CAST(pur.shipping AS REAL) / pd.subtotal) * pd.unit_cost
                                ELSE 0
                            END, 0
                        ) +
                        COALESCE(
                            CASE 
                                WHEN pd.subtotal > 0 AND pur.iva IS NOT NULL AND pur.iva != '' AND CAST(pur.iva AS REAL) > 0
                                THEN (CAST(pur.iva AS REAL) / pd.subtotal) * pd.unit_cost
                                ELSE 0
                            END, 0
                        )
                    ) as avg_full_cost
                FROM sale_details sd
                JOIN products p ON sd.product_id = p.id
                LEFT JOIN purchase_details pd ON pd.product_id = p.id
                LEFT JOIN purchases pur ON pd.purchase_id = pur.id
                GROUP BY p.id, p.name, p.cost_price
                HAVING total_sold_qty > 0
            ''')
            
            products_data = cursor.fetchall()
            total_inventory_sold = 0
            
            print(f"📦 Analizando {len(products_data)} productos vendidos:")
            
            for product in products_data:
                # Usar el costo completo si está disponible, sino usar cost_price
                unit_cost = product['avg_full_cost'] if product['avg_full_cost'] else product['cost_price']
                product_value = product['total_sold_qty'] * unit_cost
                total_inventory_sold += product_value
                
                print(f"  • {product['product_name']}: {product['total_sold_qty']} unidades × ${unit_cost:.2f} = ${product_value:.2f}")
            
            conn.close()
            
            print(f"💰 Total inventario vendido: ${total_inventory_sold:,.2f}")
            return total_inventory_sold
            
        except Exception as e:
            print(f"Error en calculate_inventory_sold_with_full_costs: {e}")
            if conn:
                conn.close()
            return 0.0
    
    def load_financial_summary(self):
        """Carga y actualiza el resumen financiero con manejo mejorado de errores"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Obtener totales diferenciados
            cursor.execute('''
                SELECT 
                    SUM(CASE WHEN status = 'paid' THEN total ELSE 0 END) as paid_sales,
                    SUM(CASE WHEN status = 'pending' THEN total ELSE 0 END) as credit_sales,
                    SUM(total) as total_sales
                FROM sales
            ''')
            sales_data = cursor.fetchone()
            
            # Resto de cálculos
            total_purchases = Purchase.get_total_purchases()
            total_expenses = Expense.get_total_expenses()
            total_losses = Loss.get_total_losses()
            
            # Actualizar UI con ambos tipos de ventas
            self.financial_labels['sales'].config(
                text=f"{format_currency(sales_data['paid_sales'])} (Pagadas)",
                foreground="green"
            )
            
            if 'credit_sales' in self.financial_labels:
                self.financial_labels['credit_sales'].config(
                    text=f"{format_currency(sales_data['credit_sales'])} (Fiadas)",
                    foreground="orange"
                )


            # Obtener datos financieros básicos
            financial_data = self._fetch_financial_data()
            
            # Calcular valores derivados
            calculations = self._perform_calculations(financial_data)
            
            # Actualizar la interfaz de usuario
            self._update_ui(financial_data, calculations)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar resumen: {str(e)}")
        finally:
            if conn:
                conn.close()

    def sync_client_sales_status_on_payment(client_id):
        """
        Sincroniza automáticamente el estado de las ventas cuando se hace un pago - VERSIÓN CORREGIDA
        """
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Obtener la deuda actual del cliente
            cursor.execute("SELECT total_debt FROM clients WHERE id = ?", (client_id,))
            client_result = cursor.fetchone()
            
            if not client_result:
                return False
            
            client_debt = float(client_result[0])
            
            # Detectar columna de estado
            cursor.execute("PRAGMA table_info(sales)")
            table_info = cursor.fetchall()
            column_names = [column[1] for column in table_info]
            
            if 'payment_status' in column_names:
                status_column = 'payment_status'
            elif 'status' in column_names:
                status_column = 'status'
            else:
                return False
            
            # Si la deuda es 0, marcar todas las ventas como pagadas
            if client_debt <= 0:
                # *** CORRECCIÓN: Sin updated_at ***
                update_query = f'''
                    UPDATE sales 
                    SET {status_column} = 'paid'
                    WHERE client_id = ? AND {status_column} = 'pending'
                '''
                cursor.execute(update_query, (client_id,))
                
            else:
                # Aplicar lógica cronológica de pagos
                query = f'''
                    SELECT id, total, created_at, {status_column}
                    FROM sales 
                    WHERE client_id = ?
                    ORDER BY datetime(created_at) ASC
                '''
                cursor.execute(query, (client_id,))
                all_sales = cursor.fetchall()
                
                # Calcular cuánto se ha pagado
                total_sales = sum(float(sale[1]) for sale in all_sales)
                total_paid = total_sales - client_debt
                
                # Aplicar pagos cronológicamente
                remaining_payment = total_paid
                
                for sale in all_sales:
                    sale_id = sale[0]
                    sale_total = float(sale[1])
                    current_status = sale[3]
                    
                    if remaining_payment >= sale_total:
                        # Esta venta debe estar pagada
                        if current_status != 'paid':
                            # *** CORRECCIÓN: Sin updated_at ***
                            update_query = f'''
                                UPDATE sales 
                                SET {status_column} = 'paid'
                                WHERE id = ?
                            '''
                            cursor.execute(update_query, (sale_id,))
                        
                        remaining_payment -= sale_total
                        
                    else:
                        # Esta venta debe estar pendiente
                        if current_status == 'paid':
                            # *** CORRECCIÓN: Sin updated_at ***
                            update_query = f'''
                                UPDATE sales 
                                SET {status_column} = 'pending'
                                WHERE id = ?
                            '''
                            cursor.execute(update_query, (sale_id,))
                        
                        break
            
            conn.commit()
            return True
            
        except Exception as e:
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()


    def sync_all_client_sales_status():
        """Sincroniza el estado de todas las ventas basándose en la deuda real - VERSIÓN CORREGIDA"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            print("🔄 Iniciando sincronización completa de estados de ventas...")
            print("=" * 60)
            
            # Detectar columna de estado
            cursor.execute("PRAGMA table_info(sales)")
            table_info = cursor.fetchall()
            column_names = [column[1] for column in table_info]
            
            if 'payment_status' in column_names:
                status_column = 'payment_status'
            elif 'status' in column_names:
                status_column = 'status'
            else:
                print("❌ ERROR: No se encontró columna de estado en sales")
                return False
            
            print(f"📊 Usando columna de estado: '{status_column}'")
            
            # Obtener todos los clientes con sus deudas reales
            cursor.execute("""
                SELECT 
                    c.id,
                    c.name,
                    c.total_debt,
                    COALESCE(SUM(
                        CASE 
                            WHEN ct.transaction_type = 'debit' THEN ct.amount
                            WHEN ct.transaction_type = 'credit' THEN -ct.amount
                            ELSE 0
                        END
                    ), 0) as calculated_debt
                FROM clients c
                LEFT JOIN client_transactions ct ON c.id = ct.client_id
                GROUP BY c.id, c.name, c.total_debt
            """)
            
            clients_data = cursor.fetchall()
            total_clients_processed = 0
            total_sales_updated = 0
            
            for client in clients_data:
                client_id = client[0]
                client_name = client[1]
                registered_debt = float(client[2])
                calculated_debt = float(client[3])
                
                print(f"\n👤 Cliente: {client_name} (ID: {client_id})")
                print(f"   💳 Deuda registrada: ${registered_debt:,.2f}")
                print(f"   🧮 Deuda calculada: ${calculated_debt:,.2f}")
                
                # Usar la deuda registrada como referencia
                current_debt = registered_debt
                
                # Obtener todas las ventas de este cliente ordenadas cronológicamente
                query = f'''
                    SELECT id, total, {status_column}, created_at, notes
                    FROM sales 
                    WHERE client_id = ?
                    ORDER BY datetime(created_at) ASC
                '''
                cursor.execute(query, (client_id,))
                client_sales = cursor.fetchall()
                
                if not client_sales:
                    print(f"   ℹ️ Sin ventas registradas")
                    continue
                
                print(f"   📋 Ventas encontradas: {len(client_sales)}")
                
                # Procesar las ventas según la deuda actual
                remaining_debt = current_debt
                sales_updated_for_client = 0
                
                for sale in client_sales:
                    sale_id = sale[0]
                    sale_total = float(sale[1])
                    current_status = sale[2]
                    sale_date = sale[3][:19]
                    sale_notes = sale[4] or ""
                    
                    if current_debt <= 0:
                        # Cliente sin deuda - todas las ventas deben estar pagadas
                        if current_status != 'paid':
                            # *** CORRECCIÓN: Sin updated_at ***
                            update_query = f'''
                                UPDATE sales 
                                SET {status_column} = 'paid',
                                    notes = ?
                                WHERE id = ?
                            '''
                            updated_notes = f"{sale_notes} [Auto-pagada por sincronización]".strip()
                            cursor.execute(update_query, (updated_notes, sale_id))
                            sales_updated_for_client += 1
                            print(f"      ✅ Venta #{sale_id} marcada como PAGADA (cliente sin deuda)")
                    
                    elif remaining_debt >= sale_total:
                        # Esta venta específica sigue pendiente
                        remaining_debt -= sale_total
                        if current_status != 'pending':
                            # *** CORRECCIÓN: Sin updated_at ***
                            update_query = f'''
                                UPDATE sales 
                                SET {status_column} = 'pending'
                                WHERE id = ?
                            '''
                            cursor.execute(update_query, (sale_id,))
                            sales_updated_for_client += 1
                            print(f"      ⚠️ Venta #{sale_id} marcada como PENDIENTE (${sale_total:,.2f})")
                    
                    else:
                        # Esta venta está parcialmente pagada o completamente pagada
                        if remaining_debt > 0:
                            # Pago parcial - actualizar el monto pendiente
                            paid_amount = sale_total - remaining_debt
                            # *** CORRECCIÓN: Sin updated_at ***
                            update_query = f'''
                                UPDATE sales 
                                SET total = ?,
                                    {status_column} = 'pending',
                                    notes = ?
                                WHERE id = ?
                            '''
                            updated_notes = f"{sale_notes} [Abono parcial ${paid_amount:,.2f} - Saldo: ${remaining_debt:,.2f}]".strip()
                            cursor.execute(update_query, (remaining_debt, updated_notes, sale_id))
                            sales_updated_for_client += 1
                            print(f"      💳 Venta #{sale_id} ABONO PARCIAL: Pagado ${paid_amount:,.2f}, Saldo ${remaining_debt:,.2f}")
                            remaining_debt = 0
                        else:
                            # Completamente pagada
                            if current_status != 'paid':
                                # *** CORRECCIÓN: Sin updated_at ***
                                update_query = f'''
                                    UPDATE sales 
                                    SET {status_column} = 'paid',
                                        notes = ?
                                    WHERE id = ?
                                '''
                                updated_notes = f"{sale_notes} [Pagada por sincronización]".strip()
                                cursor.execute(update_query, (updated_notes, sale_id))
                                sales_updated_for_client += 1
                                print(f"      ✅ Venta #{sale_id} marcada como PAGADA")
                
                total_sales_updated += sales_updated_for_client
                total_clients_processed += 1
                
                if sales_updated_for_client > 0:
                    print(f"   📊 Ventas actualizadas: {sales_updated_for_client}")
                else:
                    print(f"   ✅ Ventas ya estaban sincronizadas")
            
            # Confirmar cambios
            conn.commit()
            
            print(f"\n🎯 SINCRONIZACIÓN COMPLETADA")
            print("=" * 40)
            print(f"👥 Clientes procesados: {total_clients_processed}")
            print(f"📋 Ventas actualizadas: {total_sales_updated}")
            print(f"✅ Todas las ventas están ahora sincronizadas con las deudas reales")
            
            return True
            
        except Exception as e:
            error_msg = f"Error en sincronización: {e}"
            print(f"❌ {error_msg}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def _fetch_financial_data(self):
        """Obtiene los datos financieros usando las columnas paid_amount y remaining_debt existentes"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # 1. CÁLCULO CORRECTO usando las columnas existentes
            print("💰 Calculando ventas reales usando paid_amount y remaining_debt...")
            
            cursor.execute('''
                SELECT 
                    COALESCE(SUM(total), 0) as total_sales,
                    COALESCE(SUM(COALESCE(paid_amount, 0)), 0) as actual_paid,
                    COALESCE(SUM(COALESCE(remaining_debt, total)), 0) as actual_pending
                FROM sales
            ''')
            
            sales_data = cursor.fetchone()
            total_sales = float(sales_data['total_sales'])
            actual_paid = float(sales_data['actual_paid'])
            actual_pending = float(sales_data['actual_pending'])
            
            # Verificación de consistencia
            calculated_total = actual_paid + actual_pending
            if abs(calculated_total - total_sales) > 0.01:  # Tolerancia de 1 centavo
                print(f"⚠️ Inconsistencia detectada:")
                print(f"   Total ventas: ${total_sales:,.2f}")
                print(f"   Pagado + Pendiente: ${calculated_total:,.2f}")
                print(f"   Diferencia: ${abs(calculated_total - total_sales):,.2f}")
                
                # Usar datos de transacciones como respaldo
                cursor.execute('SELECT COALESCE(SUM(total_debt), 0) FROM clients')
                current_debt = float(cursor.fetchone()[0])
                actual_paid = total_sales - current_debt
                actual_pending = current_debt
                
                print(f"   Usando método alternativo:")
                print(f"   Pagado (corregido): ${actual_paid:,.2f}")
                print(f"   Pendiente (corregido): ${actual_pending:,.2f}")
            
            print(f"📊 Resumen de ventas:")
            print(f"   Total: ${total_sales:,.2f}")
            print(f"   Pagado: ${actual_paid:,.2f}")
            print(f"   Pendiente: ${actual_pending:,.2f}")
            
            # 2. Deuda actual para verificación
            cursor.execute('SELECT COALESCE(SUM(total_debt), 0) FROM clients')
            current_debt = float(cursor.fetchone()[0])
            
            # 3. Otros totales (sin cambios)
            total_purchases = float(Purchase.get_total_purchases() or 0)
            total_expenses = float(Expense.get_total_expenses() or 0)
            total_losses = float(Loss.get_total_losses() or 0)
            
            # 4. Inventario vendido simple (solo cost_price)
            cursor.execute('''
                SELECT COALESCE(SUM(sd.quantity * p.cost_price), 0) as inventory_sold_simple
                FROM sale_details sd
                JOIN products p ON sd.product_id = p.id
            ''')
            inventory_result = cursor.fetchone()
            inventory_sold = float(inventory_result[0] if inventory_result else 0)
            
            # 5. Calcular totales de flete e IVA
            cursor.execute('''
                SELECT 
                    COALESCE(SUM(CASE WHEN shipping IS NOT NULL AND shipping != '' AND shipping != '0' 
                                THEN CAST(shipping AS REAL) ELSE 0 END), 0) as total_freight,
                    COALESCE(SUM(CASE WHEN iva IS NOT NULL AND iva != '' AND iva != '0' 
                                THEN CAST(iva AS REAL) ELSE 0 END), 0) as total_iva
                FROM purchases
            ''')
            additional_costs_result = cursor.fetchone()
            total_freight = float(additional_costs_result[0] if additional_costs_result else 0)
            total_iva = float(additional_costs_result[1] if additional_costs_result else 0)
            
            return {
                'total_sales': total_sales,
                'paid_sales': actual_paid,        # DINERO REALMENTE RECIBIDO
                'credit_sales': actual_pending,   # DINERO PENDIENTE DE COBRO
                'total_purchases': total_purchases,
                'total_expenses': total_expenses,
                'total_losses': total_losses,
                'inventory_sold': inventory_sold,
                'current_debt': current_debt,     # Para verificación
                'total_freight': total_freight,
                'total_iva': total_iva
            }
            
        except Exception as e:
            print(f"Error detallado en _fetch_financial_data: {str(e)}")
            return {
                'total_sales': 0.0, 'paid_sales': 0.0, 'credit_sales': 0.0,
                'total_purchases': 0.0, 'total_expenses': 0.0, 'total_losses': 0.0,
                'inventory_sold': 0.0, 'current_debt': 0.0, 'total_freight': 0.0, 'total_iva': 0.0
            }
        finally:
            if conn:
                conn.close()

    def sync_sales_with_partial_payments(self):
        """Sincroniza los estados de ventas considerando pagos parciales correctamente"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            print("🔄 Sincronizando ventas con pagos parciales...")
            
            # 1. Obtener todos los clientes y sus deudas actuales
            cursor.execute('''
                SELECT id, name, total_debt
                FROM clients
                ORDER BY id
            ''')
            
            clients = cursor.fetchall()
            
            for client in clients:
                client_id = client['id']
                current_debt = float(client['total_debt'] or 0)
                
                print(f"📝 Procesando cliente: {client['name']} (Deuda: ${current_debt:,.2f})")
                
                if current_debt == 0:
                    # Cliente sin deuda - todas sus ventas están pagadas
                    cursor.execute('''
                        UPDATE sales 
                        SET status = 'paid', 
                            paid_amount = total, 
                            remaining_debt = 0
                        WHERE client_id = ? AND (status != 'paid' OR paid_amount != total)
                    ''', (client_id,))
                    
                    updated = cursor.rowcount
                    if updated > 0:
                        print(f"   ✅ {updated} ventas marcadas como pagadas")
                
                else:
                    # Cliente con deuda - calcular pagos parciales
                    cursor.execute('''
                        SELECT id, total, COALESCE(paid_amount, 0) as current_paid
                        FROM sales 
                        WHERE client_id = ?
                        ORDER BY created_at ASC
                    ''', (client_id,))
                    
                    sales = cursor.fetchall()
                    
                    # Calcular cuánto se ha pagado en total
                    total_sales_amount = sum(sale['total'] for sale in sales)
                    total_paid_amount = total_sales_amount - current_debt
                    
                    print(f"   📊 Total vendido: ${total_sales_amount:,.2f}")
                    print(f"   💰 Total pagado: ${total_paid_amount:,.2f}")
                    print(f"   🔴 Pendiente: ${current_debt:,.2f}")
                    
                    # Distribuir el pago entre las ventas (FIFO - más antiguas primero)
                    remaining_payment = total_paid_amount
                    
                    for sale in sales:
                        sale_id = sale['id']
                        sale_total = sale['total']
                        
                        if remaining_payment <= 0:
                            # No hay más pago para esta venta
                            new_paid = 0
                            new_remaining = sale_total
                            new_status = 'pending'
                        elif remaining_payment >= sale_total:
                            # Esta venta está completamente pagada
                            new_paid = sale_total
                            new_remaining = 0
                            new_status = 'paid'
                            remaining_payment -= sale_total
                        else:
                            # Esta venta tiene pago parcial
                            new_paid = remaining_payment
                            new_remaining = sale_total - remaining_payment
                            new_status = 'pending'
                            remaining_payment = 0
                        
                        # Actualizar la venta solo si hay cambios
                        cursor.execute('''
                            UPDATE sales 
                            SET paid_amount = ?, 
                                remaining_debt = ?, 
                                status = ?
                            WHERE id = ? AND (
                                COALESCE(paid_amount, 0) != ? OR 
                                COALESCE(remaining_debt, 0) != ? OR 
                                status != ?
                            )
                        ''', (new_paid, new_remaining, new_status, sale_id, new_paid, new_remaining, new_status))
                        
                        if cursor.rowcount > 0:
                            print(f"   🔄 Venta #{sale_id}: Pagado=${new_paid:,.2f}, Pendiente=${new_remaining:,.2f}")
            
            conn.commit()
            print("✅ Sincronización completada")
            
            # Recargar datos financieros
            self.load_financial_summary()
            
            return True
            
        except Exception as e:
            print(f"❌ Error en sincronización: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def _perform_calculations(self, data):
        """Realiza los cálculos derivados con inventario vendido simple"""
        # Efectivo = ventas pagadas - compras - gastos
        cash_in_hand = data['paid_sales'] - data['total_purchases'] - data['total_expenses']
        
        # Inventario actual = compras - inventario vendido (solo cost_price) - pérdidas
        current_inventory_value = data['total_purchases'] - data['inventory_sold'] - data['total_losses']
        
        return {
            'cash_in_hand': cash_in_hand,
            'current_inventory_value': max(0, current_inventory_value),  # No negativo
        }


    def _perform_calculations(self, data):
        """Realiza los cálculos derivados"""
        # Efectivo = ventas pagadas - compras - gastos
        cash_in_hand = data['paid_sales'] - data['total_purchases'] - data['total_expenses']
        
        # Inventario actual = compras - inventario vendido - pérdidas
        current_inventory_value = data['total_purchases'] - data['inventory_sold'] - data['total_losses'] - data['total_freight'] - data['total_iva']
        
        return {
            'cash_in_hand': cash_in_hand,
            'current_inventory_value': max(0, current_inventory_value),  # No negativo
        }

    def force_refresh_all_data(self):
        """Fuerza la actualización de todos los datos y ventanas"""
        try:
            print("🔄 Forzando actualización completa...")
            
            # 1. Recalcular deudas de clientes
            self.recalculate_client_debts()
            
            # 2. Actualizar todas las ventanas abiertas
            if hasattr(self, 'refresh_all_windows'):
                self.refresh_all_windows()
            
            # 3. Limpiar caché de reportes si existe
            if hasattr(self, 'reports_cache'):
                self.reports_cache = {}
            
            # 4. Forzar recálculo de estadísticas
            if hasattr(self, 'update_dashboard_stats'):
                self.update_dashboard_stats()
            
            print("✅ Actualización completa terminada")
            
        except Exception as e:
            print(f"Error en actualización completa: {e}")

    def recalculate_client_debts(self):
        """Recalcula todas las deudas de clientes basándose en transacciones"""
        try:
            from config.database import get_connection
            
            conn = get_connection()
            cursor = conn.cursor()
            
            # Obtener todos los clientes
            cursor.execute("SELECT id FROM clients")
            client_ids = [row[0] for row in cursor.fetchall()]
            
            for client_id in client_ids:
                # Calcular deuda real basada en transacciones
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(CASE WHEN transaction_type = 'debit' THEN amount ELSE 0 END), 0) as debits,
                        COALESCE(SUM(CASE WHEN transaction_type = 'credit' THEN amount ELSE 0 END), 0) as credits
                    FROM client_transactions 
                    WHERE client_id = ?
                """, (client_id,))
                
                result = cursor.fetchone()
                debits = float(result[0])
                credits = float(result[1])
                calculated_debt = max(0, debits - credits)
                
                # Actualizar cliente
                cursor.execute("""
                    UPDATE clients 
                    SET total_debt = ?, updated_at = datetime('now', 'localtime')
                    WHERE id = ?
                """, (calculated_debt, client_id))
            
            conn.commit()
            conn.close()
            
            print(f"✅ Deudas recalculadas para {len(client_ids)} clientes")
            
        except Exception as e:
            print(f"Error recalculando deudas: {e}")

    def fix_sales_payment_status(self):
        """Corrige el estado de pago de las ventas"""
        try:
            from config.database import get_connection
            
            conn = get_connection()
            cursor = conn.cursor()
            
            # Obtener clientes sin deuda
            cursor.execute("SELECT id FROM clients WHERE total_debt = 0")
            clients_no_debt = [row[0] for row in cursor.fetchall()]
            
            # Marcar todas las ventas de estos clientes como pagadas
            for client_id in clients_no_debt:
                cursor.execute("""
                    UPDATE sales 
                    SET status = 'paid', updated_at = datetime('now', 'localtime')
                    WHERE client_id = ? AND status = 'pending'
                """, (client_id,))
                
                updated = cursor.rowcount
                if updated > 0:
                    print(f"✅ {updated} ventas marcadas como 'paid' para cliente {client_id}")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error corrigiendo estados de venta: {e}")

    def fix_all_sales_status():
        """Función simple para arreglar estados de ventas"""
        try:
            from config.database import get_connection
            
            conn = get_connection()
            cursor = conn.cursor()
            
            print("🔄 Arreglando estados de ventas...")
            
            # Marcar como pagadas todas las ventas de clientes sin deuda
            cursor.execute('''
                UPDATE sales 
                SET status = 'paid'
                WHERE client_id IN (
                    SELECT id FROM clients WHERE total_debt = 0 OR total_debt IS NULL
                ) AND status = 'pending'
            ''')
            
            updated = cursor.rowcount
            conn.commit()
            conn.close()
            
            print(f"✅ {updated} ventas marcadas como pagadas")
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False

    # Método para agregar a tu CreditManagementWindow
    def refresh_and_close_fixed(self):
        """Versión mejorada del refresh_and_close"""
        try:
            # 1. Forzar recálculo de deuda del cliente específico
            self.recalculate_single_client_debt()
            
            # 2. Actualizar cliente desde BD
            from models.client import Client
            self.client = Client.get_by_id(self.client.id)
            
            # 3. Actualizar ventana de clientes
            if hasattr(self, 'clients_window') and self.clients_window:
                self.clients_window.refresh_clients()
            
            # 4. Actualizar todas las ventanas
            if hasattr(self, 'main_window') and self.main_window:
                if hasattr(self.main_window, 'force_refresh_all_data'):
                    self.main_window.force_refresh_all_data()
                elif hasattr(self.main_window, 'refresh_all_windows'):
                    self.main_window.refresh_all_windows()
            
            print(f"🔄 Cliente actualizado: {self.client.name} - Deuda: ${self.client.total_debt:,.2f}")
            
        except Exception as e:
            print(f"Error en refresh_and_close: {e}")
        finally:
            self.window.destroy()

    def recalculate_single_client_debt(self):
        """Recalcula la deuda de un cliente específico"""
        try:
            from config.database import get_connection
            
            conn = get_connection()
            cursor = conn.cursor()
            
            # Calcular deuda basada en transacciones
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN transaction_type = 'debit' THEN amount ELSE 0 END), 0) as debits,
                    COALESCE(SUM(CASE WHEN transaction_type = 'credit' THEN amount ELSE 0 END), 0) as credits
                FROM client_transactions 
                WHERE client_id = ?
            """, (self.client.id,))
            
            result = cursor.fetchone()
            debits = float(result[0])
            credits = float(result[1])
            calculated_debt = max(0, debits - credits)
            
            # Actualizar cliente
            cursor.execute("""
                UPDATE clients 
                SET total_debt = ?, updated_at = datetime('now', 'localtime')
                WHERE id = ?
            """, (calculated_debt, self.client.id))
            
            # Si no hay deuda, marcar ventas como pagadas
            if calculated_debt == 0:
                cursor.execute("""
                    UPDATE sales 
                    SET status = 'paid', updated_at = datetime('now', 'localtime')
                    WHERE client_id = ? AND status = 'pending'
                """, (self.client.id,))
                
                updated_sales = cursor.rowcount
                if updated_sales > 0:
                    print(f"✅ {updated_sales} ventas marcadas como 'paid'")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error recalculando deuda del cliente: {e}")

    def _update_ui(self, data, calculations):
        """Actualiza la UI con validaciones"""
        try:
            # Flujo de efectivo
            sales_text = f"{format_currency(data['total_sales'])} (P:{format_currency(data['paid_sales'])}, F:{format_currency(data['credit_sales'])}, Deben:{format_currency(data['current_debt'])})"
            self.financial_labels['sales'].config(text=sales_text, foreground="green")
            self.financial_labels['purchases'].config(text=format_currency(data['total_purchases']), foreground="red")
            self.financial_labels['expenses'].config(text=format_currency(data['total_expenses']), foreground="red")
            self.financial_labels['cash'].config(
                text=format_currency(calculations['cash_in_hand']), 
                foreground="green" if calculations['cash_in_hand'] >= 0 else "red"
            )
            
            # Inventario
            self.financial_labels['inventory_purchases'].config(text=format_currency(data['total_purchases']), foreground="blue")
            self.financial_labels['inventory_sold'].config(text=format_currency(data['inventory_sold']), foreground="green")
            self.financial_labels['losses'].config(text=format_currency(data['total_losses']), foreground="orange")
            self.financial_labels['current_inventory'].config(
                text=format_currency(calculations['current_inventory_value']), 
                foreground="purple" if calculations['current_inventory_value'] >= 0 else "red"
            )
            
            # Utilidad (SOLO ventas pagadas)
            self.financial_labels['profit_sales'].config(text=format_currency(data['paid_sales']), foreground="green")
            self.financial_labels['cogs'].config(text=format_currency(data['cogs']), foreground="red")
            self.financial_labels['profit_expenses'].config(text=format_currency(data['total_expenses']), foreground="red")
            self.financial_labels['net_profit'].config(
                text=format_currency(calculations['net_profit']), 
                foreground="darkgreen" if calculations['net_profit'] >= 0 else "red"
            )
            
            print(f"DEBUG - Datos actualizados:")
            print(f"COGS: {data['cogs']}")
            print(f"Inventory sold: {data['inventory_sold']}")
            print(f"Losses: {data['total_losses']}")
            
        except Exception as e:
            print(f"Error al actualizar UI: {str(e)}")
            messagebox.showerror("Error", f"No se pudo actualizar la interfaz: {str(e)}")

    def _update_ui(self, data, calculations):
        """Actualiza la UI usando los labels existentes en self.financial_labels"""
        try:
            # Verificar datos
            required_keys = ['paid_sales', 'credit_sales', 'total_sales']
            if not all(key in data for key in required_keys):
                raise ValueError("Datos de ventas incompletos")
            
            # Actualizar directamente aquí
            # Flujo de efectivo
            sales_text = f"{format_currency(data['total_sales'])} (P:{format_currency(data['paid_sales'])}, F:{format_currency(data['credit_sales'])})"
            self.financial_labels['sales'].config(text=sales_text, foreground="green")
            self.financial_labels['purchases'].config(text=format_currency(data['total_purchases']), foreground="red")
            self.financial_labels['expenses'].config(text=format_currency(data['total_expenses']), foreground="red")
            self.financial_labels['cash'].config(text=format_currency(calculations['cash_in_hand']), 
                                            foreground="green" if calculations['cash_in_hand'] >= 0 else "red")
            
            # Inventario
            self.financial_labels['inventory_purchases'].config(text=format_currency(data['total_purchases']), foreground="blue")
            self.financial_labels['inventory_sold'].config(text=format_currency(data['inventory_sold']), foreground="green")
            self.financial_labels['total_freight'].config(text=format_currency(data['total_freight']), foreground="red")     # NUEVO
            self.financial_labels['total_iva'].config(text=format_currency(data['total_iva']), foreground="red")
            self.financial_labels['losses'].config(text=format_currency(data['total_losses']), foreground="orange")
            self.financial_labels['current_inventory'].config(text=format_currency(calculations['current_inventory_value']), 
                                                            foreground="purple" if calculations['current_inventory_value'] >= 0 else "red")
            

            
        except Exception as e:
            print(f"Error al actualizar UI: {str(e)}")
            messagebox.showerror("Error", f"No se pudo actualizar la interfaz: {str(e)}")

    def _update_inventory_section(self, data, calculations):
        """Actualiza la sección de valor del inventario"""
        self.financial_labels['inventory_purchases'].config(
            text=format_currency(data['total_purchases']),
            foreground="blue"
        )
        self.financial_labels['inventory_sold'].config(
            text=format_currency(data['inventory_sold']),
            foreground="green" if data['inventory_sold'] > 0 else "black"
        )
        self.financial_labels['losses'].config(
            text=format_currency(data['total_losses']),
            foreground="orange" if data['total_losses'] > 0 else "black"
        )
        self.financial_labels['current_inventory'].config(
            text=format_currency(calculations['current_inventory_value']),
            foreground="purple" if calculations['current_inventory_value'] >= 0 else "red"
        )

    def _update_profit_section(self, data, calculations):
        """Actualiza la sección de utilidad neta"""
        # USAR SOLO VENTAS PAGADAS para utilidad
        self.financial_labels['profit_sales'].config(
            text=format_currency(data['paid_sales']),  # Era: data['total_sales']
            foreground="green"
        )
        self.financial_labels['cogs'].config(
            text=format_currency(data['cogs']),
            foreground="red"
        )
        self.financial_labels['profit_expenses'].config(
            text=format_currency(data['total_expenses']),
            foreground="red"
        )
        
        # Recalcular utilidad neta SOLO con ventas pagadas
        net_profit = data['paid_sales'] - data['cogs'] - data['total_expenses']
        self.financial_labels['net_profit'].config(
            text=format_currency(net_profit),
            foreground="darkgreen" if net_profit >= 0 else "red",
            font=("Arial", 12, "bold")
        )

    def _handle_error(self, error):
        """Maneja errores y muestra mensajes al usuario"""
        error_msg = f"Error al cargar resumen financiero: {str(error)}"
        print(error_msg)  # Log para depuración
        messagebox.showerror("Error", error_msg)

    def get_inventory_sold_at_cost(self):
        """Calcula el valor del inventario vendido al precio de costo"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Consulta mejorada que considera TODAS las ventas (pagadas y fiadas)
            cursor.execute('''
                SELECT SUM(sd.quantity * p.cost_price) as total_cost
                FROM sale_details sd
                JOIN products p ON sd.product_id = p.id
                JOIN sales s ON sd.sale_id = s.id
                WHERE s.status IN ('paid', 'pending')  -- Incluye tanto pagadas como fiadas
            ''')
            
            result = cursor.fetchone()
            conn.close()
            
            return float(result['total_cost']) if result and result['total_cost'] else 0.0
            
        except Exception as e:
            print(f"Error al calcular inventario vendido al costo: {e}")
            return 0.0

    def export_inventory_flow(self):
        """Exporta el libro de movimientos de inventario (incluye pérdidas)"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                title="Guardar libro de inventario"
            )
            
            if filename:
                filepath = ExcelExporter.export_inventory_flow(os.path.basename(filename))
                
                # Mover el archivo a la ubicación seleccionada
                import shutil
                shutil.move(filepath, filename)
                
                messagebox.showinfo("Éxito", f"Libro de inventario exportado a:\n{filename}")
                
                # Preguntar si desea abrir el archivo
                if messagebox.askyesno("Abrir archivo", "¿Desea abrir el archivo exportado?"):
                    os.startfile(filename)  # Windows
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error al exportar libro de inventario: {str(e)}")
    
    def load_products_analysis(self):
        """Carga el análisis de productos más vendidos"""
        try:
            # Limpiar árbol
            for item in self.products_tree.get_children():
                self.products_tree.delete(item)
            
            # Obtener datos de ventas por producto
            conn = get_connection()
            cursor = conn.cursor()
            
            # Consulta para obtener productos más vendidos
            cursor.execute('''
                SELECT p.id, p.name, 
                    SUM(sd.quantity) as total_quantity,
                    SUM(sd.quantity * sd.unit_price) as total_revenue
                FROM sale_details sd
                JOIN products p ON sd.product_id = p.id
                JOIN sales s ON sd.sale_id = s.id
                GROUP BY p.id
                ORDER BY total_quantity DESC
                LIMIT 20
            ''')
            
            products_data = cursor.fetchall()
            conn.close()
            
            if not products_data:
                self.products_tree.insert('', tk.END, values=("No hay datos disponibles", "", ""))
                return
            
            # Insertar datos en el árbol
            for product in products_data:
                self.products_tree.insert('', tk.END, values=(
                product['name'],
                format_number(product['total_quantity']),
                format_currency(product['total_revenue'])))
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar análisis de productos: {str(e)}")
            # Insertar mensaje de error en el árbol
            self.products_tree.insert('', tk.END, values=(f"Error: {str(e)}", "", ""))
    
    def load_clients_analysis(self):
        """Carga el análisis de clientes con deuda"""
        try:
            # Limpiar árbol
            for item in self.clients_tree.get_children():
                self.clients_tree.delete(item)
            
            # Obtener datos de clientes con deuda
            conn = get_connection()
            cursor = conn.cursor()
            
            # Consulta para obtener clientes con deuda
            cursor.execute('''
                SELECT c.id, c.name, c.total_debt,
                    MAX(s.created_at) as last_purchase
                FROM clients c
                LEFT JOIN sales s ON c.id = s.client_id
                WHERE c.total_debt > 0
                GROUP BY c.id
                ORDER BY c.total_debt DESC
            ''')
            
            clients_data = cursor.fetchall()
            conn.close()
            
            if not clients_data:
                self.clients_tree.insert('', tk.END, values=("No hay clientes con deuda", "", ""))
                return
            
            # Insertar datos en el árbol
            for client in clients_data:
                last_purchase = client['last_purchase'] if client['last_purchase'] else "Sin compras"
                
                self.clients_tree.insert('', tk.END, values=(
                    client['name'],
                    format_currency(client['total_debt']),
                    last_purchase
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar análisis de clientes: {str(e)}")
            # Insertar mensaje de error en el árbol
            self.clients_tree.insert('', tk.END, values=(f"Error: {str(e)}", "", ""))
    
    def load_losses_analysis(self):
        """Carga el análisis de pérdidas por producto - NUEVO"""
        try:
            # Limpiar árbol
            for item in self.losses_tree.get_children():
                self.losses_tree.delete(item)
            
            # Obtener datos de pérdidas por producto
            conn = get_connection()
            cursor = conn.cursor()
            
            # Consulta para obtener pérdidas agrupadas por producto
            cursor.execute('''
                SELECT p.name as product_name, 
                    SUM(l.quantity) as total_quantity,
                    SUM(l.total_cost) as total_cost,
                    l.loss_type,
                    COUNT(*) as loss_count
                FROM losses l
                JOIN products p ON l.product_id = p.id
                GROUP BY p.id, l.loss_type
                ORDER BY total_cost DESC
                LIMIT 20
            ''')
            
            losses_data = cursor.fetchall()
            conn.close()
            
            if not losses_data:
                self.losses_tree.insert('', tk.END, values=("No hay pérdidas registradas", "", "", ""))
                return
            
            # Agrupar por producto para obtener el tipo principal de pérdida
            product_losses = {}
            for loss in losses_data:
                product_name = loss['product_name']
                if product_name not in product_losses:
                    product_losses[product_name] = {
                        'total_quantity': 0,
                        'total_cost': 0,
                        'main_type': loss['loss_type'],
                        'max_cost': loss['total_cost']
                    }
                
                product_losses[product_name]['total_quantity'] += loss['total_quantity']
                product_losses[product_name]['total_cost'] += loss['total_cost']
                
                # Determinar el tipo principal (el que más costo ha generado)
                if loss['total_cost'] > product_losses[product_name]['max_cost']:
                    product_losses[product_name]['main_type'] = loss['loss_type']
                    product_losses[product_name]['max_cost'] = loss['total_cost']
            
            # Insertar datos en el árbol
            for product_name, data in sorted(product_losses.items(), key=lambda x: x[1]['total_cost'], reverse=True):
                self.losses_tree.insert('', tk.END, values=(
                    product_name,
                    format_number(data['total_quantity']),
                    format_currency(data['total_cost']),
                    data['main_type']
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar análisis de pérdidas: {str(e)}")
            # Insertar mensaje de error en el árbol
            self.losses_tree.insert('', tk.END, values=(f"Error: {str(e)}", "", "", ""))
    
    def export_sales(self):
        """Exporta las ventas a Excel"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                title="Guardar reporte de ventas"
            )
            
            if filename:
                filepath = ExcelExporter.export_sales(os.path.basename(filename))
                
                # Mover el archivo a la ubicación seleccionada
                import shutil
                shutil.move(filepath, filename)
                
                messagebox.showinfo("Éxito", f"Reporte de ventas exportado a:\n{filename}")
                
                # Preguntar si desea abrir el archivo
                if messagebox.askyesno("Abrir archivo", "¿Desea abrir el archivo exportado?"):
                    os.startfile(filename)  # Windows
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error al exportar ventas: {str(e)}")
    
    def export_purchases(self):
        """Exporta las compras a Excel"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                title="Guardar reporte de compras"
            )
            
            if filename:
                filepath = ExcelExporter.export_purchases(os.path.basename(filename))
                
                # Mover el archivo a la ubicación seleccionada
                import shutil
                shutil.move(filepath, filename)
                
                messagebox.showinfo("Éxito", f"Reporte de compras exportado a:\n{filename}")
                
                # Preguntar si desea abrir el archivo
                if messagebox.askyesno("Abrir archivo", "¿Desea abrir el archivo exportado?"):
                    os.startfile(filename)  # Windows
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error al exportar compras: {str(e)}")
    
    def export_losses(self):
        """Exporta las pérdidas a Excel - NUEVO"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                title="Guardar reporte de pérdidas"
            )
            
            if filename:
                filepath = ExcelExporter.export_losses(os.path.basename(filename))
                
                # Mover el archivo a la ubicación seleccionada
                import shutil
                shutil.move(filepath, filename)
                
                messagebox.showinfo("Éxito", f"Reporte de pérdidas exportado a:\n{filename}")
                
                # Preguntar si desea abrir el archivo
                if messagebox.askyesno("Abrir archivo", "¿Desea abrir el archivo exportado?"):
                    os.startfile(filename)  # Windows
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error al exportar pérdidas: {str(e)}")
    
    def export_cash_flow(self):
        """Exporta el libro diario de ingresos y egresos"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                title="Guardar libro diario"
            )
            
            if filename:
                filepath = ExcelExporter.export_cash_flow(os.path.basename(filename))
                
                # Mover el archivo a la ubicación seleccionada
                import shutil
                shutil.move(filepath, filename)
                
                messagebox.showinfo("Éxito", f"Libro diario exportado a:\n{filename}")
                
                # Preguntar si desea abrir el archivo
                if messagebox.askyesno("Abrir archivo", "¿Desea abrir el archivo exportado?"):
                    os.startfile(filename)  # Windows
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error al exportar libro diario: {str(e)}")
    
    def export_complete_report(self):
        """Exporta un reporte completo con todas las secciones"""
        try:
            folder = filedialog.askdirectory(title="Seleccionar carpeta para reportes")
            
            if folder:
                messagebox.showinfo("Procesando", "Generando reportes completos...")
                
                # Exportar todos los reportes
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                sales_file = ExcelExporter.export_sales(f"ventas_completas_{timestamp}.xlsx")
                purchases_file = ExcelExporter.export_purchases(f"compras_completas_{timestamp}.xlsx")
                losses_file = ExcelExporter.export_losses(f"perdidas_completas_{timestamp}.xlsx")  # NUEVO
                cashflow_file = ExcelExporter.export_cash_flow(f"libro_diario_{timestamp}.xlsx")
                inventory_file = ExcelExporter.export_inventory_flow(f"libro_inventario_{timestamp}.xlsx")
                
                # Mover archivos a la carpeta seleccionada
                import shutil
                shutil.move(sales_file, os.path.join(folder, os.path.basename(sales_file)))
                shutil.move(purchases_file, os.path.join(folder, os.path.basename(purchases_file)))
                shutil.move(losses_file, os.path.join(folder, os.path.basename(losses_file)))  # NUEVO
                shutil.move(cashflow_file, os.path.join(folder, os.path.basename(cashflow_file)))
                shutil.move(inventory_file, os.path.join(folder, os.path.basename(inventory_file)))
                
                messagebox.showinfo("Éxito", f"Reportes completos exportados a:\n{folder}")
                
                # Preguntar si desea abrir la carpeta
                if messagebox.askyesno("Abrir carpeta", "¿Desea abrir la carpeta con los reportes?"):
                    os.startfile(folder)  # Windows
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error al exportar reportes: {str(e)}")

    def sync_sales_status_with_debt(self):
        """Sincroniza el estado de las ventas con la deuda real de los clientes"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # 1. Marcar como 'paid' todas las ventas de clientes sin deuda
            cursor.execute('''
                UPDATE sales 
                SET status = 'paid', 
                    paid_amount = total, 
                    remaining_debt = 0
                WHERE client_id IN (
                    SELECT id FROM clients WHERE total_debt = 0
                ) AND status = 'pending'
            ''')
            
            updated_sales = cursor.rowcount
            print(f"✅ {updated_sales} ventas marcadas como 'paid'")
            
            # 2. Para clientes con deuda > 0, marcar las ventas más antiguas como pagadas
            # hasta que la suma coincida con la deuda real
            cursor.execute('''
                SELECT c.id, c.name, c.total_debt
                FROM clients c
                WHERE c.total_debt > 0
            ''')
            
            clients_with_debt = cursor.fetchall()
            
            for client in clients_with_debt:
                client_id = client['id']
                current_debt = client['total_debt']
                
                # Obtener ventas pendientes ordenadas por fecha (más antiguas primero)
                cursor.execute('''
                    SELECT id, total, COALESCE(paid_amount, 0) as paid_amount
                    FROM sales 
                    WHERE client_id = ? AND status = 'pending'
                    ORDER BY created_at ASC
                ''', (client_id,))
                
                pending_sales = cursor.fetchall()
                total_pending = sum(sale['total'] - sale['paid_amount'] for sale in pending_sales)
                
                if total_pending > current_debt:
                    # Hay más ventas pendientes que deuda real
                    # Marcar algunas como pagadas
                    remaining_debt = current_debt
                    
                    for sale in pending_sales:
                        sale_balance = sale['total'] - sale['paid_amount']
                        
                        if remaining_debt <= 0:
                            # Esta venta debe estar completamente pagada
                            cursor.execute('''
                                UPDATE sales 
                                SET status = 'paid', 
                                    paid_amount = total, 
                                    remaining_debt = 0
                                WHERE id = ?
                            ''', (sale['id'],))
                            
                        elif remaining_debt < sale_balance:
                            # Esta venta está parcialmente pagada
                            new_paid_amount = sale['total'] - remaining_debt
                            cursor.execute('''
                                UPDATE sales 
                                SET paid_amount = ?, 
                                    remaining_debt = ?
                                WHERE id = ?
                            ''', (new_paid_amount, remaining_debt, sale['id']))
                            remaining_debt = 0
                            
                        else:
                            # Esta venta sigue pendiente completamente
                            remaining_debt -= sale_balance
            
            conn.commit()
            conn.close()
            
            print(f"✅ Estados de ventas sincronizados para {len(clients_with_debt)} clientes con deuda")
            
            # Recargar el resumen financiero
            self.load_financial_summary()
            
            return True
            
        except Exception as e:
            print(f"❌ Error al sincronizar estados: {e}")
            if conn:
                conn.rollback()
                conn.close()
            return False
    
    def diagnose_inventory_discrepancy(self):
        """Diagnostica discrepancias en el inventario y ofrece soluciones"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            print("🔍 DIAGNÓSTICO DE INVENTARIO")
            print("=" * 50)
            
            # 1. Verificar productos con stock vs ventas
            cursor.execute('''
                SELECT 
                    p.id,
                    p.name,
                    p.cost_price,
                    COALESCE(SUM(pd.quantity), 0) as purchased_qty,
                    COALESCE(SUM(sd.quantity), 0) as sold_qty,
                    COALESCE(SUM(l.quantity), 0) as lost_qty,
                    (COALESCE(SUM(pd.quantity), 0) - COALESCE(SUM(sd.quantity), 0) - COALESCE(SUM(l.quantity), 0)) as calculated_stock
                FROM products p
                LEFT JOIN purchase_details pd ON p.id = pd.product_id
                LEFT JOIN sale_details sd ON p.id = sd.product_id
                LEFT JOIN losses l ON p.id = l.product_id
                GROUP BY p.id
                HAVING calculated_stock > 0
            ''')
            
            stock_discrepancies = cursor.fetchall()
            
            print("📦 PRODUCTOS CON STOCK APARENTE:")
            for product in stock_discrepancies:
                print(f"  • {product['name']}")
                print(f"    - Comprado: {product['purchased_qty']}")
                print(f"    - Vendido: {product['sold_qty']}")
                print(f"    - Perdido: {product['lost_qty']}")
                print(f"    - Stock calculado: {product['calculated_stock']}")
                print(f"    - Valor stock: ${product['calculated_stock'] * product['cost_price']:,.2f}")
                print()
            
            # 2. Verificar inconsistencias en precios de costo
            cursor.execute('''
                SELECT DISTINCT p.id, p.name, p.cost_price,
                    AVG(pd.unit_cost) as avg_purchase_price
                FROM products p
                JOIN purchase_details pd ON p.id = pd.product_id
                GROUP BY p.id
                HAVING ABS(p.cost_price - AVG(pd.unit_cost)) > 0.01
            ''')
            
            price_discrepancies = cursor.fetchall()
            
            if price_discrepancies:
                print("💰 INCONSISTENCIAS EN PRECIOS DE COSTO:")
                for product in price_discrepancies:
                    print(f"  • {product['name']}")
                    print(f"    - Precio en producto: ${product['cost_price']:,.2f}")
                    print(f"    - Precio promedio compras: ${product['avg_purchase_price']:,.2f}")
                    print()
            
            # 3. Calcular el verdadero valor del inventario
            total_purchases = 0
            total_sold_at_cost = 0
            total_losses = 0
            
            cursor.execute('SELECT SUM(total_cost) FROM purchases')
            result = cursor.fetchone()
            total_purchases = float(result[0] if result[0] else 0)
            
            cursor.execute('''
                SELECT SUM(sd.quantity * p.cost_price)
                FROM sale_details sd
                JOIN products p ON sd.product_id = p.id
            ''')
            result = cursor.fetchone()
            total_sold_at_cost = float(result[0] if result[0] else 0)
            
            cursor.execute('SELECT SUM(total_cost) FROM losses')
            result = cursor.fetchone()
            total_losses = float(result[0] if result[0] else 0)
            
            calculated_inventory = total_purchases - total_sold_at_cost - total_losses
            
            print("📊 RESUMEN FINANCIERO:")
            print(f"  Total compras: ${total_purchases:,.2f}")
            print(f"  Vendido (a costo): ${total_sold_at_cost:,.2f}")
            print(f"  Pérdidas: ${total_losses:,.2f}")
            print(f"  Inventario calculado: ${calculated_inventory:,.2f}")
            print()
            
            # 4. Proponer soluciones
            if calculated_inventory > 100:  # Si hay más de $100 en inventario
                print("🔧 SOLUCIONES RECOMENDADAS:")
                print("  1. Verificar que todos los productos vendidos estén registrados")
                print("  2. Registrar pérdidas/mermas no contabilizadas")
                print("  3. Actualizar stock_quantity en productos a 0")
                print("  4. Revisar precios de costo inconsistentes")
                
                if messagebox.askyesno("Corregir Stock", 
                                    f"¿Desea poner en 0 el stock de todos los productos?\n"
                                    f"Inventario actual calculado: ${calculated_inventory:,.2f}"):
                    self.zero_out_all_stock()
            
            conn.close()
            return calculated_inventory
            
        except Exception as e:
            print(f"Error en diagnóstico: {e}")
            if conn:
                conn.close()
            return None

    def zero_out_all_stock(self):
        """Registra diferencias como pérdidas en lugar de modificar stock"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Encontrar productos con stock calculado > 0
            cursor.execute('''
                SELECT 
                    p.id, p.name, p.cost_price,
                    (COALESCE(SUM(pd.quantity), 0) - COALESCE(SUM(sd.quantity), 0) - COALESCE(SUM(l.quantity), 0)) as stock_diff
                FROM products p
                LEFT JOIN purchase_details pd ON p.id = pd.product_id
                LEFT JOIN sale_details sd ON p.id = sd.product_id  
                LEFT JOIN losses l ON p.id = l.product_id
                GROUP BY p.id
                HAVING stock_diff > 0
            ''')
            
            products = cursor.fetchall()
            total_registered = 0
            
            for product in products:
                loss_value = product['stock_diff'] * product['cost_price']
                cursor.execute('''
                    INSERT INTO losses (product_id, quantity, unit_cost, total_cost, loss_type, reason, created_at)
                    VALUES (?, ?, ?, ?, 'adjustment', 'Ajuste inventario', datetime('now', 'localtime'))
                ''', (product['id'], product['stock_diff'], product['cost_price'], loss_value))
                total_registered += 1
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Éxito", f"Se registraron {total_registered} ajustes como pérdidas")
            self.load_financial_summary()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

    def register_inventory_loss_bulk(self):
        """Registra las diferencias de inventario como pérdidas"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Obtener productos con stock calculado > 0
            cursor.execute('''
                SELECT 
                    p.id, p.name, p.cost_price,
                    (COALESCE(SUM(pd.quantity), 0) - COALESCE(SUM(sd.quantity), 0) - COALESCE(SUM(l.quantity), 0)) as stock_diff
                FROM products p
                LEFT JOIN purchase_details pd ON p.id = pd.product_id
                LEFT JOIN sale_details sd ON p.id = sd.product_id
                LEFT JOIN losses l ON p.id = l.product_id
                GROUP BY p.id
                HAVING stock_diff > 0
            ''')
            
            products_with_stock = cursor.fetchall()
            
            if not products_with_stock:
                messagebox.showinfo("Info", "No hay discrepancias de inventario para registrar")
                return
            
            total_loss_value = 0
            registered_losses = 0
            
            for product in products_with_stock:
                if product['stock_diff'] > 0:
                    loss_value = product['stock_diff'] * product['cost_price']
                    total_loss_value += loss_value
                    
                    # Registrar la pérdida
                    cursor.execute('''
                        INSERT INTO losses (product_id, quantity, unit_cost, total_cost, loss_type, reason, created_at)
                        VALUES (?, ?, ?, ?, 'inventory_adjustment', 'Ajuste por diferencia de inventario', datetime('now', 'localtime'))
                    ''', (product['id'], product['stock_diff'], product['cost_price'], loss_value))
                    
                    registered_losses += 1
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Éxito", 
                            f"Se registraron {registered_losses} pérdidas por ajuste de inventario\n"
                            f"Valor total: ${total_loss_value:,.2f}")
            
            # Recargar datos
            self.load_financial_summary()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error registrando pérdidas: {e}")

    def get_inventory_sold_with_proportional_costs(self):
        """
        Calcula el valor del inventario vendido incluyendo proporcionalmente
        flete e IVA basado en las compras originales
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Obtener todas las ventas con sus detalles y calcular costo real
            cursor.execute('''
                SELECT 
                    sd.product_id,
                    sd.quantity as sold_qty,
                    p.cost_price as base_cost,
                    -- Calcular costo total promedio por producto (incluyendo flete/IVA)
                    AVG(pd.unit_cost + 
                        COALESCE(pd.unit_freight, 0) + 
                        COALESCE(pd.unit_tax, 0)) as avg_total_cost_per_unit
                FROM sale_details sd
                JOIN products p ON sd.product_id = p.id
                JOIN purchase_details pd ON pd.product_id = p.id
                GROUP BY sd.sale_id, sd.product_id
            ''')
            
            sales_data = cursor.fetchall()
            total_inventory_sold = 0
            
            for sale in sales_data:
                # Usar el costo total promedio (base + flete + IVA proporcional)
                real_unit_cost = sale['avg_total_cost_per_unit']
                sold_value = sale['sold_qty'] * real_unit_cost
                total_inventory_sold += sold_value
            
            conn.close()
            return total_inventory_sold
            
        except Exception as e:
            print(f"Error calculando inventario vendido con costos reales: {e}")
            return 0.0

    def calculate_real_inventory_value(self):
        """
        Calcula el valor real del inventario considerando todos los costos
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # 1. Total invertido en compras (precio + flete + IVA)
            cursor.execute('''
                SELECT SUM(total_cost) as total_purchases
                FROM purchases
            ''')
            total_purchases = cursor.fetchone()['total_purchases'] or 0
            
            # 2. Inventario vendido con costos proporcionales
            cursor.execute('''
                SELECT 
                    p.id,
                    p.cost_price,
                    SUM(sd.quantity) as total_sold,
                    -- Calcular costo promedio real por unidad para este producto
                    (SELECT AVG(
                        pd.unit_cost + 
                        COALESCE((pd.unit_cost * pur.freight_cost / pur.subtotal), 0) +
                        COALESCE((pd.unit_cost * pur.tax_amount / pur.subtotal), 0)
                    ) 
                    FROM purchase_details pd 
                    JOIN purchases pur ON pd.purchase_id = pur.id
                    WHERE pd.product_id = p.id) as real_avg_cost
                FROM products p
                JOIN sale_details sd ON p.id = sd.product_id
                GROUP BY p.id
            ''')
            
            products_sold = cursor.fetchall()
            total_sold_value = 0
            
            for product in products_sold:
                if product['real_avg_cost']:
                    sold_value = product['total_sold'] * product['real_avg_cost']
                    total_sold_value += sold_value
            
            # 3. Total de pérdidas
            cursor.execute('SELECT SUM(total_cost) FROM losses')
            total_losses = cursor.fetchone()[0] or 0
            
            # 4. Inventario real
            real_inventory = total_purchases - total_sold_value - total_losses
            
            conn.close()
            
            return {
                'total_purchases': total_purchases,
                'inventory_sold_real': total_sold_value,
                'total_losses': total_losses,
                'real_inventory_value': max(0, real_inventory)
            }
            
        except Exception as e:
            print(f"Error calculando inventario real: {e}")
            return None
        
    def diagnose_inventory_calculation(self):
        """Diagnostica los cálculos de inventario paso a paso"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            print("🔍 DIAGNÓSTICO DETALLADO DEL INVENTARIO")
            print("=" * 60)
            
            # 1. Total de compras
            cursor.execute('SELECT SUM(total) FROM purchases')
            total_purchases = cursor.fetchone()[0] or 0
            print(f"1. Total invertido en compras: ${total_purchases:,.2f}")
            
            # 2. Desglose de compras con flete e IVA
            cursor.execute('''
                SELECT 
                    COUNT(*) as num_purchases,
                    SUM(CASE WHEN subtotal IS NOT NULL AND subtotal != '' 
                        THEN CAST(subtotal AS REAL) ELSE 0 END) as subtotal_sum,
                    SUM(CASE WHEN freight IS NOT NULL AND freight != '' AND freight != '0' 
                        THEN CAST(freight AS REAL) ELSE 0 END) as freight_sum,
                    SUM(CASE WHEN tax IS NOT NULL AND tax != '' AND tax != '0' 
                        THEN CAST(tax AS REAL) ELSE 0 END) as tax_sum
                FROM purchases
            ''')
            
            purchase_breakdown = cursor.fetchone()
            print(f"   - Número de compras: {purchase_breakdown[0]}")
            print(f"   - Subtotal productos: ${purchase_breakdown[1]:,.2f}")
            print(f"   - Total flete: ${purchase_breakdown[2]:,.2f}")
            print(f"   - Total IVA: ${purchase_breakdown[3]:,.2f}")
            
            # 3. Inventario vendido simple (solo cost_price)
            cursor.execute('''
                SELECT COALESCE(SUM(sd.quantity * p.cost_price), 0) as simple_sold
                FROM sale_details sd
                JOIN products p ON sd.product_id = p.id
            ''')
            simple_sold = cursor.fetchone()[0]
            print(f"2. Inventario vendido (solo costo base): ${simple_sold:,.2f}")
            
            # 4. Intentar inventario vendido con costos completos
            inventory_with_costs = self.calculate_inventory_sold_with_full_costs()
            print(f"3. Inventario vendido (con flete e IVA): ${inventory_with_costs:,.2f}")
            
            # 5. Pérdidas
            cursor.execute('SELECT COALESCE(SUM(total_cost), 0) FROM losses')
            total_losses = cursor.fetchone()[0] or 0
            print(f"4. Pérdidas registradas: ${total_losses:,.2f}")
            
            # 6. Inventario restante
            remaining_simple = total_purchases - simple_sold - total_losses
            remaining_with_costs = total_purchases - inventory_with_costs - total_losses
            
            print(f"\n📊 INVENTARIO RESTANTE:")
            print(f"   - Con costo base: ${remaining_simple:,.2f}")
            print(f"   - Con costos completos: ${remaining_with_costs:,.2f}")
            
            # 7. Verificar si hay productos con stock aparente
            cursor.execute('''
                SELECT 
                    p.name,
                    COALESCE(SUM(pd.quantity), 0) as purchased,
                    COALESCE(SUM(sd.quantity), 0) as sold,
                    COALESCE(SUM(l.quantity), 0) as lost,
                    (COALESCE(SUM(pd.quantity), 0) - COALESCE(SUM(sd.quantity), 0) - COALESCE(SUM(l.quantity), 0)) as apparent_stock
                FROM products p
                LEFT JOIN purchase_details pd ON p.id = pd.product_id
                LEFT JOIN sale_details sd ON p.id = sd.product_id
                LEFT JOIN losses l ON p.id = l.product_id
                GROUP BY p.id, p.name
                HAVING apparent_stock > 0
                ORDER BY apparent_stock DESC
                LIMIT 10
            ''')
            
            products_with_stock = cursor.fetchall()
            if products_with_stock:
                print(f"\n📦 PRODUCTOS CON STOCK APARENTE:")
                for product in products_with_stock:
                    print(f"   • {product[0]}: {product[4]} unidades (C:{product[1]}, V:{product[2]}, P:{product[3]})")
            
            # 8. Mostrar mensaje al usuario
            messagebox.showinfo("Diagnóstico Completado", 
                            f"Diagnóstico completado. Revisa la consola para detalles.\n\n"
                            f"Resumen:\n"
                            f"• Total compras: ${total_purchases:,.2f}\n"
                            f"• Inventario vendido (simple): ${simple_sold:,.2f}\n"
                            f"• Inventario vendido (con costos): ${inventory_with_costs:,.2f}\n"
                            f"• Pérdidas: ${total_losses:,.2f}\n"
                            f"• Inventario restante (estimado): ${remaining_with_costs:,.2f}")
            
            conn.close()
            return {
                'total_purchases': total_purchases,
                'simple_sold': simple_sold,
                'inventory_with_costs': inventory_with_costs,
                'total_losses': total_losses,
                'remaining_simple': remaining_simple,
                'remaining_with_costs': remaining_with_costs
            }
            
        except Exception as e:
            print(f"Error en diagnóstico: {e}")
            messagebox.showerror("Error", f"Error en diagnóstico: {e}")
            if conn:
                conn.close()
            return None
        
    def show_inventory_discrepancies(self):
        """Muestra las discrepancias de inventario sin registrarlas automáticamente"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Obtener productos con posibles discrepancias
            cursor.execute('''
                SELECT 
                    p.id, p.name, p.cost_price,
                    COALESCE(SUM(pd.quantity), 0) as purchased,
                    COALESCE(SUM(sd.quantity), 0) as sold,
                    COALESCE(SUM(l.quantity), 0) as lost,
                    (COALESCE(SUM(pd.quantity), 0) - COALESCE(SUM(sd.quantity), 0) - COALESCE(SUM(l.quantity), 0)) as stock_diff
                FROM products p
                LEFT JOIN purchase_details pd ON p.id = pd.product_id
                LEFT JOIN sale_details sd ON p.id = sd.product_id
                LEFT JOIN losses l ON p.id = l.product_id
                GROUP BY p.id, p.name, p.cost_price
                HAVING stock_diff != 0
                ORDER BY stock_diff DESC
            ''')
            
            discrepancies = cursor.fetchall()
            conn.close()
            
            if not discrepancies:
                messagebox.showinfo("Info", "No se encontraron discrepancias de inventario")
                return
            
            # Crear ventana para mostrar discrepancias
            discrepancy_window = tk.Toplevel(self.window)
            discrepancy_window.title("Discrepancias de Inventario")
            discrepancy_window.geometry("800x500")
            
            # Frame con scroll
            main_frame = ttk.Frame(discrepancy_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            ttk.Label(main_frame, 
                    text="Discrepancias de Inventario Detectadas", 
                    font=("Arial", 14, "bold")).pack(pady=(0, 10))
            
            ttk.Label(main_frame, 
                    text="Estas diferencias deben revisarse manualmente y registrarse en el módulo de Pérdidas/Mermas si corresponde:", 
                    font=("Arial", 10), 
                    foreground="red").pack(pady=(0, 10))
            
            # Treeview para mostrar discrepancias
            columns = ('Producto', 'Comprado', 'Vendido', 'Perdido', 'Diferencia', 'Valor Diferencia')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)
            
            # Configurar columnas
            for col in columns:
                tree.heading(col, text=col)
                if col in ['Comprado', 'Vendido', 'Perdido', 'Diferencia']:
                    tree.column(col, width=80)
                elif col == 'Valor Diferencia':
                    tree.column(col, width=120)
                else:
                    tree.column(col, width=200)
            
            # Scrollbar
            scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Insertar datos
            total_discrepancy_value = 0
            for disc in discrepancies:
                value_diff = disc[6] * disc[2]  # stock_diff * cost_price
                total_discrepancy_value += abs(value_diff)
                
                tree.insert('', tk.END, values=(
                    disc[1],  # name
                    format_number(disc[3]),  # purchased
                    format_number(disc[4]),  # sold
                    format_number(disc[5]),  # lost
                    format_number(disc[6]),  # stock_diff
                    format_currency(value_diff)  # value
                ))
            
            # Label con total
            ttk.Label(main_frame, 
                    text=f"Valor total de discrepancias: {format_currency(total_discrepancy_value)}", 
                    font=("Arial", 12, "bold"),
                    foreground="red").pack(pady=10)
            
            ttk.Label(main_frame, 
                    text="💡 Utiliza el módulo de Pérdidas/Mermas para registrar cualquier pérdida real", 
                    font=("Arial", 10),
                    foreground="blue").pack(pady=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error mostrando discrepancias: {e}")
            if conn:
                conn.close()
    
    def diagnose_payment_discrepancies(self):
        """Diagnostica discrepancias entre pagos registrados y deudas de clientes"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            print("🔍 DIAGNÓSTICO DE PAGOS PARCIALES")
            print("=" * 50)
            
            # 1. Verificar consistencia general
            cursor.execute('''
                SELECT 
                    SUM(total) as total_sales,
                    SUM(COALESCE(paid_amount, 0)) as total_paid,
                    SUM(COALESCE(remaining_debt, total)) as total_pending,
                    (SELECT SUM(total_debt) FROM clients) as client_debts
                FROM sales
            ''')
            
            summary = cursor.fetchone()
            
            print("📊 RESUMEN GENERAL:")
            print(f"   Total vendido: ${summary['total_sales']:,.2f}")
            print(f"   Total pagado (sales): ${summary['total_paid']:,.2f}")
            print(f"   Total pendiente (sales): ${summary['total_pending']:,.2f}")
            print(f"   Deudas de clientes: ${summary['client_debts']:,.2f}")
            print()
            
            # 2. Verificar clientes con discrepancias
            cursor.execute('''
                SELECT 
                    c.id,
                    c.name,
                    c.total_debt,
                    COALESCE(SUM(s.total - COALESCE(s.paid_amount, 0)), 0) as calculated_debt,
                    COALESCE(SUM(s.total), 0) as total_sales_client,
                    COALESCE(SUM(COALESCE(s.paid_amount, 0)), 0) as total_paid_client
                FROM clients c
                LEFT JOIN sales s ON c.id = s.client_id
                GROUP BY c.id, c.name, c.total_debt
                HAVING ABS(c.total_debt - calculated_debt) > 0.01
                ORDER BY ABS(c.total_debt - calculated_debt) DESC
            ''')
            
            discrepancies = cursor.fetchall()
            
            if discrepancies:
                print("⚠️ DISCREPANCIAS ENCONTRADAS:")
                for client in discrepancies:
                    print(f"   • {client['name']}:")
                    print(f"     - Deuda registrada: ${client['total_debt']:,.2f}")
                    print(f"     - Deuda calculada: ${client['calculated_debt']:,.2f}")
                    print(f"     - Diferencia: ${abs(client['total_debt'] - client['calculated_debt']):,.2f}")
                    print(f"     - Total vendido: ${client['total_sales_client']:,.2f}")
                    print(f"     - Total pagado: ${client['total_paid_client']:,.2f}")
                    print()
            else:
                print("✅ No se encontraron discrepancias significativas")
            
            # 3. Mostrar algunos ejemplos de ventas con pagos parciales
            cursor.execute('''
                SELECT 
                    s.id,
                    c.name as client_name,
                    s.total,
                    COALESCE(s.paid_amount, 0) as paid_amount,
                    COALESCE(s.remaining_debt, s.total) as remaining_debt,
                    s.status,
                    s.created_at
                FROM sales s
                JOIN clients c ON s.client_id = c.id
                WHERE COALESCE(s.paid_amount, 0) > 0 AND COALESCE(s.remaining_debt, 0) > 0
                ORDER BY s.created_at DESC
                LIMIT 5
            ''')
            
            partial_payments = cursor.fetchall()
            
            if partial_payments:
                print("💳 EJEMPLOS DE PAGOS PARCIALES:")
                for sale in partial_payments:
                    print(f"   • Venta #{sale['id']} - {sale['client_name']}")
                    print(f"     - Total: ${sale['total']:,.2f}")
                    print(f"     - Pagado: ${sale['paid_amount']:,.2f}")
                    print(f"     - Pendiente: ${sale['remaining_debt']:,.2f}")
                    print(f"     - Fecha: {sale['created_at']}")
                    print()
            
            conn.close()
            
            # Mostrar resultado al usuario
            messagebox.showinfo("Diagnóstico Completado", 
                            f"Diagnóstico completado. Ver consola para detalles.\n\n"
                            f"Resumen:\n"
                            f"• Total vendido: ${summary['total_sales']:,.2f}\n"
                            f"• Total pagado: ${summary['total_paid']:,.2f}\n"
                            f"• Total pendiente: ${summary['total_pending']:,.2f}\n"
                            f"• Discrepancias: {len(discrepancies)} clientes")
            
        except Exception as e:
            print(f"Error en diagnóstico: {e}")
            messagebox.showerror("Error", f"Error en diagnóstico: {e}")
            if conn:
                conn.close()

    def fix_all_data_integrity(self):
        """Corrige automáticamente todos los problemas de integridad de datos"""
        try:
            # Confirmar con el usuario
            if not messagebox.askyesno("Confirmar Corrección", 
                                    "¿Está seguro de que desea corregir automáticamente todos los datos?\n\n"
                                    "Esto actualizará:\n"
                                    "• Estados de ventas (paid/pending)\n"
                                    "• Montos pagados y pendientes\n"
                                    "• Deudas de clientes\n\n"
                                    "Recomendamos hacer backup antes de continuar."):
                return
            
            conn = get_connection()
            cursor = conn.cursor()
            
            print("🔧 INICIANDO CORRECCIÓN AUTOMÁTICA DE DATOS")
            print("=" * 50)
            
            # 1. Recalcular deudas de clientes basándose en transacciones
            print("📊 Paso 1: Recalculando deudas de clientes...")
            
            cursor.execute("SELECT id, name FROM clients")
            clients = cursor.fetchall()
            
            clients_updated = 0
            for client in clients:
                client_id = client['id']
                
                # Calcular deuda real basada en transacciones
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(CASE WHEN transaction_type = 'debit' THEN amount ELSE 0 END), 0) as debits,
                        COALESCE(SUM(CASE WHEN transaction_type = 'credit' THEN amount ELSE 0 END), 0) as credits
                    FROM client_transactions 
                    WHERE client_id = ?
                """, (client_id,))
                
                result = cursor.fetchone()
                if result:
                    debits = float(result['debits'] or 0)
                    credits = float(result['credits'] or 0)
                    calculated_debt = max(0, debits - credits)
                    
                    # Actualizar solo si hay diferencia
                    cursor.execute("SELECT total_debt FROM clients WHERE id = ?", (client_id,))
                    current_debt = float(cursor.fetchone()['total_debt'] or 0)
                    
                    if abs(current_debt - calculated_debt) > 0.01:
                        cursor.execute("""
                            UPDATE clients 
                            SET total_debt = ?
                            WHERE id = ?
                        """, (calculated_debt, client_id))
                        clients_updated += 1
                        print(f"   ✅ Cliente {client['name']}: ${current_debt:,.2f} → ${calculated_debt:,.2f}")
            
            print(f"   📈 {clients_updated} clientes actualizados")
            
            # 2. Sincronizar estados de ventas
            print("💳 Paso 2: Sincronizando estados de ventas...")
            
            # Para cada cliente, distribuir pagos correctamente
            cursor.execute("SELECT id, name, total_debt FROM clients")
            clients = cursor.fetchall()
            
            sales_updated = 0
            for client in clients:
                client_id = client['id']
                current_debt = float(client['total_debt'] or 0)
                
                # Obtener todas las ventas del cliente
                cursor.execute('''
                    SELECT id, total
                    FROM sales 
                    WHERE client_id = ?
                    ORDER BY created_at ASC
                ''', (client_id,))
                
                sales = cursor.fetchall()
                
                if not sales:
                    continue
                
                # Calcular cuánto se ha pagado en total
                total_sales_amount = sum(sale['total'] for sale in sales)
                total_paid = total_sales_amount - current_debt
                
                # Distribuir pagos (FIFO)
                remaining_payment = max(0, total_paid)
                
                for sale in sales:
                    sale_id = sale['id']
                    sale_total = sale['total']
                    
                    if remaining_payment <= 0:
                        # No hay pago para esta venta
                        new_paid = 0
                        new_remaining = sale_total
                        new_status = 'pending'
                    elif remaining_payment >= sale_total:
                        # Venta completamente pagada
                        new_paid = sale_total
                        new_remaining = 0
                        new_status = 'paid'
                        remaining_payment -= sale_total
                    else:
                        # Pago parcial
                        new_paid = remaining_payment
                        new_remaining = sale_total - remaining_payment
                        new_status = 'pending'
                        remaining_payment = 0
                    
                    # Actualizar venta
                    cursor.execute('''
                        UPDATE sales 
                        SET paid_amount = ?, 
                            remaining_debt = ?, 
                            status = ?
                        WHERE id = ?
                    ''', (new_paid, new_remaining, new_status, sale_id))
                    
                    if cursor.rowcount > 0:
                        sales_updated += 1
            
            print(f"   📈 {sales_updated} ventas actualizadas")
            
            # 3. Verificación final
            print("✅ Paso 3: Verificación final...")
            
            cursor.execute('''
                SELECT 
                    SUM(total) as total_sales,
                    SUM(COALESCE(paid_amount, 0)) as total_paid,
                    SUM(COALESCE(remaining_debt, 0)) as total_pending,
                    (SELECT SUM(total_debt) FROM clients) as client_debts
                FROM sales
            ''')
            
            verification = cursor.fetchone()
            
            print(f"   📊 Total ventas: ${verification['total_sales']:,.2f}")
            print(f"   💰 Total pagado: ${verification['total_paid']:,.2f}")
            print(f"   🔴 Total pendiente: ${verification['total_pending']:,.2f}")
            print(f"   👥 Deudas clientes: ${verification['client_debts']:,.2f}")
            
            # Verificar consistencia
            paid_plus_pending = verification['total_paid'] + verification['total_pending']
            pending_vs_debts = abs(verification['total_pending'] - verification['client_debts'])
            
            if abs(paid_plus_pending - verification['total_sales']) < 0.01 and pending_vs_debts < 0.01:
                print("   ✅ Datos consistentes")
            else:
                print(f"   ⚠️ Inconsistencia detectada:")
                print(f"      Diferencia ventas: ${abs(paid_plus_pending - verification['total_sales']):,.2f}")
                print(f"      Diferencia deudas: ${pending_vs_debts:,.2f}")
            
            conn.commit()
            conn.close()
            
            # Actualizar la interfaz
            self.load_financial_summary()
            
            messagebox.showinfo("Corrección Completada", 
                            f"Corrección automática completada:\n\n"
                            f"• {clients_updated} clientes actualizados\n"
                            f"• {sales_updated} ventas sincronizadas\n\n"
                            f"Los datos han sido actualizados en la interfaz.")
            
            print("🎉 CORRECCIÓN COMPLETADA EXITOSAMENTE")
            return True
            
        except Exception as e:
            print(f"❌ Error en corrección automática: {e}")
            messagebox.showerror("Error", f"Error durante la corrección: {str(e)}")
            if conn:
                conn.rollback()
                conn.close()
            return False