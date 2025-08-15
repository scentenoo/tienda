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
        
        # Pestaña 2: Análisis
        analysis_tab = ttk.Frame(notebook)
        notebook.add(analysis_tab, text="📈 Análisis")
        self.setup_analysis_tab(analysis_tab)
        
        # Pestaña 3: Exportar
        export_tab = ttk.Frame(notebook)
        notebook.add(export_tab, text="📤 Exportar")
        self.setup_export_tab(export_tab)

    def setup_summary_tab(self, parent):
        """Configura la pestaña de resumen financiero"""
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
        self.create_summary_row(inventory_frame, "❌ Pérdidas de Inventario:", 'losses', "orange")
        self.create_summary_row(inventory_frame, "📊 INVENTARIO ACTUAL:", 'current_inventory', "purple", bold=True)
        
        # Sección de utilidad
        profit_frame = ttk.LabelFrame(scrollable_frame, text="Utilidad Neta", padding=10)
        profit_frame.pack(fill=tk.X, pady=5, padx=5)
        
        self.create_summary_row(profit_frame, "💰 Ingresos por Ventas:", 'profit_sales', "green")
        self.create_summary_row(profit_frame, "📦 Costo Productos Vendidos:", 'cogs', "red")
        self.create_summary_row(profit_frame, "🏪 Gastos Operativos:", 'profit_expenses', "red")
        self.create_summary_row(profit_frame, "💎 UTILIDAD NETA:", 'net_profit', "darkgreen", bold=True)
        
        # Botón de actualización
        ttk.Button(scrollable_frame, 
                text="🔄 Actualizar Datos", 
                command=self.load_financial_summary,
                style='TButton').pack(pady=10)

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
    
    def load_financial_summary(self):
        """Carga el resumen financiero separando efectivo e inventario"""
        try:
            # FLUJO DE EFECTIVO (movimientos reales de dinero)
            total_sales = Sale.get_total_sales()
            total_purchases = Purchase.get_total_purchases()
            total_expenses = Expense.get_total_expenses()
            cash_in_hand = total_sales - total_purchases - total_expenses  # SIN pérdidas
            
            # VALOR DEL INVENTARIO
            total_losses = Loss.get_total_losses()
            
            # Calcular valor del inventario actual
            # (Compras - Valor vendido al costo - Pérdidas)
            inventory_sold_at_cost = self.get_inventory_sold_at_cost()
            current_inventory_value = total_purchases - inventory_sold_at_cost - total_losses
            
            # Actualizar etiquetas de efectivo
            self.financial_labels['sales'].config(text=format_currency(total_sales))
            self.financial_labels['purchases'].config(text=format_currency(total_purchases))
            self.financial_labels['expenses'].config(text=format_currency(total_expenses))
            self.financial_labels['cash'].config(text=format_currency(cash_in_hand))
            
            # Actualizar etiquetas de inventario
            self.financial_labels['inventory_purchases'].config(text=format_currency(total_purchases))
            self.financial_labels['inventory_sold'].config(text=format_currency(inventory_sold_at_cost))
            self.financial_labels['losses'].config(text=format_currency(total_losses))
            self.financial_labels['current_inventory'].config(text=format_currency(current_inventory_value))

            # UTILIDAD NETA
            # Costo de productos vendidos (usando cost_price de sale_details o products)
            conn = get_connection()
            cursor = conn.cursor()

            # Obtener costo de productos vendidos
            cursor.execute('''
            SELECT SUM(sd.quantity * pd.unit_price) as cogs
            FROM sale_details sd
            JOIN sales s ON sd.sale_id = s.id
            JOIN purchase_details pd ON sd.product_id = pd.product_id
            WHERE s.status = 'paid'
        ''')
            result = cursor.fetchone()
            cogs = float(result['cogs']) if result and result['cogs'] else 0.0

            conn.close()

            # Calcular utilidad neta = Ingresos - Costo productos vendidos - Gastos operativos
            net_profit = total_sales - cogs - total_expenses

            # Actualizar etiquetas de utilidad
            self.financial_labels['profit_sales'].config(text=format_currency(total_sales))
            self.financial_labels['cogs'].config(text=format_currency(cogs))
            self.financial_labels['profit_expenses'].config(text=format_currency(total_expenses))
            self.financial_labels['net_profit'].config(text=format_currency(net_profit))

            # Color según ganancia/pérdida
            if net_profit >= 0:
                self.financial_labels['net_profit'].config(foreground="darkgreen")
            else:
                self.financial_labels['net_profit'].config(foreground="red")
            
            # Cambiar colores según el estado
            if cash_in_hand >= 0:
                self.financial_labels['cash'].config(foreground="green")
            else:
                self.financial_labels['cash'].config(foreground="red")
                
            if current_inventory_value >= 0:
                self.financial_labels['current_inventory'].config(foreground="purple")
            else:
                self.financial_labels['current_inventory'].config(foreground="red")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar resumen financiero: {str(e)}")

    def get_inventory_sold_at_cost(self):
        """Calcula el valor del inventario vendido al precio de costo"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Obtener el costo de los productos vendidos
            cursor.execute('''
                SELECT SUM(sd.quantity * p.cost_price) as total_cost
                FROM sale_details sd
                JOIN products p ON sd.product_id = p.id
                JOIN sales s ON sd.sale_id = s.id
                WHERE LOWER(s.type) != 'ajuste'
                AND s.status = 'paid'
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