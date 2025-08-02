import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from models.sale import Sale
from models.purchase import Purchase
from models.expense import Expense
from utils.excel_exporter import ExcelExporter
import os
from config.database import get_connection

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
        self.window.geometry("700x600")
        self.window.resizable(True, True)
        
        self.setup_ui()
        self.load_financial_summary()
    
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Frame principal
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, text="Reportes y Análisis Financiero", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Frame para resumen financiero
        summary_frame = ttk.LabelFrame(main_frame, text="Resumen Financiero", padding="15")
        summary_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Variables para mostrar totales
        self.financial_labels = {}
        
        # Total de ventas
        sales_frame = ttk.Frame(summary_frame)
        sales_frame.grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(sales_frame, text="Total Ventas:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.financial_labels['sales'] = ttk.Label(sales_frame, text="$0.00", 
                                                  font=("Arial", 10), foreground="green")
        self.financial_labels['sales'].pack(side=tk.LEFT, padx=(10, 0))
        
        # Total de compras
        purchases_frame = ttk.Frame(summary_frame)
        purchases_frame.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)
        ttk.Label(purchases_frame, text="Total Compras:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.financial_labels['purchases'] = ttk.Label(purchases_frame, text="$0.00", 
                                                      font=("Arial", 10), foreground="red")
        self.financial_labels['purchases'].pack(side=tk.LEFT, padx=(10, 0))
        
        # Total gastos operativos
        expenses_frame = ttk.Frame(summary_frame)
        expenses_frame.grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(expenses_frame, text="Gastos Operativos:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.financial_labels['expenses'] = ttk.Label(expenses_frame, text="$0.00", 
                                                     font=("Arial", 10), foreground="red")
        self.financial_labels['expenses'].pack(side=tk.LEFT, padx=(10, 0))
        
        # Efectivo en posesión
        cash_frame = ttk.Frame(summary_frame)
        cash_frame.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        ttk.Label(cash_frame, text="Efectivo en Posesión:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        self.financial_labels['cash'] = ttk.Label(cash_frame, text="$0.00", 
                                                 font=("Arial", 12, "bold"), foreground="blue")
        self.financial_labels['cash'].pack(side=tk.LEFT, padx=(10, 0))
        
        # Botón para actualizar
        ttk.Button(summary_frame, text="Actualizar Datos", 
                  command=self.load_financial_summary).grid(row=2, column=0, columnspan=2, pady=10)
        
        # Frame para exportaciones
        export_frame = ttk.LabelFrame(main_frame, text="Exportar Reportes", padding="15")
        export_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Botones de exportación
        export_buttons = [
            ("Exportar Ventas", self.export_sales),
            ("Exportar Compras", self.export_purchases),
            ("Exportar Libro Diario", self.export_cash_flow),
            ("Exportar Reporte Completo", self.export_complete_report)
        ]
        
        for i, (text, command) in enumerate(export_buttons):
            row = i // 2
            col = i % 2
            ttk.Button(export_frame, text=text, command=command, width=20).grid(
                row=row, column=col, padx=10, pady=5)
        
        # Frame para análisis adicional
        analysis_frame = ttk.LabelFrame(main_frame, text="Análisis", padding="15")
        analysis_frame.pack(fill=tk.BOTH, expand=True)
        
        # Notebook para diferentes análisis
        notebook = ttk.Notebook(analysis_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Pestaña de productos más vendidos
        products_frame = ttk.Frame(notebook)
        notebook.add(products_frame, text="Productos Más Vendidos")
        self.setup_products_analysis(products_frame)
        
        # Pestaña de clientes con más deuda
        clients_frame = ttk.Frame(notebook)
        notebook.add(clients_frame, text="Clientes con Deuda")
        self.setup_clients_analysis(clients_frame)
    
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
    
    def load_financial_summary(self):
        """Carga el resumen financiero"""
        try:
            total_sales = Sale.get_total_sales()
            total_purchases = Purchase.get_total_purchases()
            total_expenses = Expense.get_total_expenses()
            cash_in_hand = total_sales - total_purchases - total_expenses
            
            self.financial_labels['sales'].config(text=f"${total_sales:.2f}")
            self.financial_labels['purchases'].config(text=f"${total_purchases:.2f}")
            self.financial_labels['expenses'].config(text=f"${total_expenses:.2f}")
            self.financial_labels['cash'].config(text=f"${cash_in_hand:.2f}")
            
            # Cambiar color según si hay ganancia o pérdida
            if cash_in_hand >= 0:
                self.financial_labels['cash'].config(foreground="green")
            else:
                self.financial_labels['cash'].config(foreground="red")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar resumen financiero: {str(e)}")
    
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
                    f"{product['total_quantity']:.2f}",
                    f"${product['total_revenue']:.2f}"
                ))
                
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
                    f"${client['total_debt']:.2f}",
                    last_purchase
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar análisis de clientes: {str(e)}")
            # Insertar mensaje de error en el árbol
            self.clients_tree.insert('', tk.END, values=(f"Error: {str(e)}", "", ""))
    
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
                cashflow_file = ExcelExporter.export_cash_flow(f"libro_diario_{timestamp}.xlsx")
                
                # Mover archivos a la carpeta seleccionada
                import shutil
                shutil.move(sales_file, os.path.join(folder, os.path.basename(sales_file)))
                shutil.move(purchases_file, os.path.join(folder, os.path.basename(purchases_file)))
                shutil.move(cashflow_file, os.path.join(folder, os.path.basename(cashflow_file)))
                
                messagebox.showinfo("Éxito", f"Reportes completos exportados a:\n{folder}")
                
                # Preguntar si desea abrir la carpeta
                if messagebox.askyesno("Abrir carpeta", "¿Desea abrir la carpeta con los reportes?"):
                    os.startfile(folder)  # Windows
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error al exportar reportes: {str(e)}")