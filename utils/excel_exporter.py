import pandas as pd
from datetime import datetime
import os
from models.sale import Sale
from models.purchase import Purchase
from models.expense import Expense
from models.product import Product
from models.client import Client
from config.database import get_connection

class ExcelExporter:
    @staticmethod
    def export_sales(filename=None):
        """Exporta las ventas a un archivo Excel"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ventas_{timestamp}.xlsx"
        
        try:
            # Obtener datos
            sales = Sale.get_all()
            products = {p.id: p.name for p in Product.get_all()}
            clients = {c.id: c.name for c in Client.get_all()}
            
            # Preparar datos para el DataFrame
            data = []
            for sale in sales:
                # Obtener detalles de la venta
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
                
                client_name = clients.get(sale.client_id, "N/A") if sale.client_id else "Venta de Contado"
                
                if details:
                    for detail in details:
                        product_name = detail['product_name']
                        
                        data.append({
                            'ID': sale.id,
                            'Producto': product_name,
                            'Cliente': client_name,
                            'Cantidad': detail['quantity'],
                            'Precio Unitario': detail['unit_price'],
                            'Total': sale.total,
                            'Estado': 'Pagado' if sale.status == 'paid' else 'Pendiente',
                            'Fecha': sale.created_at if sale.created_at else "N/A"
                        })
                else:
                    # Si no hay detalles, mostrar solo la información básica de la venta
                    data.append({
                        'ID': sale.id,
                        'Producto': "N/A",
                        'Cliente': client_name,
                        'Cantidad': "N/A",
                        'Precio Unitario': "N/A",
                        'Total': sale.total,
                        'Estado': 'Pagado' if sale.status == 'paid' else 'Pendiente',
                        'Fecha': sale.created_at if sale.created_at else "N/A"
                    })
            
            # Crear DataFrame y exportar
            df = pd.DataFrame(data)
            
            # Crear directorio de exportación si no existe
            export_dir = "exports"
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)
            
            filepath = os.path.join(export_dir, filename)
            df.to_excel(filepath, index=False)
            
            return filepath
            
        except Exception as e:
            raise Exception(f"Error al exportar ventas: {str(e)}")
    
    @staticmethod
    def export_purchases(filename=None):
        """Exporta las compras a un archivo Excel"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"compras_{timestamp}.xlsx"
        
        try:
            # Obtener datos
            purchases = Purchase.get_all()
            products = {p.id: p.name for p in Product.get_all()}
            
            # Preparar datos para el DataFrame
            data = []
            for purchase in purchases:
                # Obtener detalles de la compra
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
                        product_name = detail['product_name']
                        
                        data.append({
                            'ID': purchase.id,
                            'Producto': product_name,
                            'Cantidad': detail['quantity'],
                            'Precio Unitario': detail['unit_price'],
                            'Flete': purchase.shipping,
                            'IVA': purchase.iva,
                            'Total': purchase.total,
                            'No. Factura': purchase.invoice_number or "N/A",
                            'Fecha': purchase.date if purchase.date else "N/A"
                        })
                else:
                    # Si no hay detalles, mostrar solo la información básica de la compra
                    data.append({
                        'ID': purchase.id,
                        'Producto': "N/A",
                        'Cantidad': "N/A",
                        'Precio Unitario': "N/A",
                        'Flete': purchase.shipping,
                        'IVA': purchase.iva,
                        'Total': purchase.total,
                        'No. Factura': purchase.invoice_number or "N/A",
                        'Fecha': purchase.date if purchase.date else "N/A"
                    })
            
            # Crear DataFrame y exportar
            df = pd.DataFrame(data)
            
            # Crear directorio de exportación si no existe
            export_dir = "exports"
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)
            
            filepath = os.path.join(export_dir, filename)
            df.to_excel(filepath, index=False)
            
            return filepath
            
        except Exception as e:
            raise Exception(f"Error al exportar compras: {str(e)}")
    
    @staticmethod
    def export_cash_flow(filename=None):
        """Exporta el libro diario de ingresos y egresos"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"libro_diario_{timestamp}.xlsx"
        
        try:
            # Obtener todos los movimientos
            movements = []
            
            # Obtener datos de referencia
            products = {p.id: p.name for p in Product.get_all()}
            
            # Agregar ventas como ingresos
            sales = Sale.get_all()
            for sale in sales:
                if sale.status == 'paid' or sale.payment_method == 'cash':  # Solo ventas pagadas
                    # Obtener detalles de la venta
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
                    
                    if details:
                        for detail in details:
                            product_name = detail['product_name']
                            movements.append({
                                'Fecha': sale.created_at,
                                'Tipo': 'Ingreso',
                                'Concepto': f"Venta - {product_name}",
                                'Cantidad': detail['quantity'],
                                'Monto': detail['subtotal'],
                                'Saldo Running': 0
                            })
                    else:
                        # Si no hay detalles, usar la información general de la venta
                        movements.append({
                            'Fecha': sale.created_at,
                            'Tipo': 'Ingreso',
                            'Concepto': f"Venta #{sale.id}",
                            'Cantidad': 1,
                            'Monto': sale.total,
                            'Saldo Running': 0
                        })
            
            # Agregar compras como egresos
            purchases = Purchase.get_all()
            for purchase in purchases:
                # Obtener detalles de la compra
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
                        product_name = detail['product_name']
                        movements.append({
                            'Fecha': purchase.date,
                            'Tipo': 'Egreso',
                            'Concepto': f"Compra - {product_name}",
                            'Cantidad': detail['quantity'],
                            'Monto': -detail['subtotal'],
                            'Saldo Running': 0
                        })
                else:
                    # Si no hay detalles, usar la información general de la compra
                    movements.append({
                        'Fecha': purchase.date,
                        'Tipo': 'Egreso',
                        'Concepto': f"Compra #{purchase.id}",
                        'Cantidad': 1,
                        'Monto': -purchase.total,
                        'Saldo Running': 0
                    })
            
            # Agregar gastos operativos como egresos
            expenses = Expense.get_all()
            for expense in expenses:
                movements.append({
                    'Fecha': expense.date,
                    'Tipo': 'Egreso',
                    'Concepto': f"Gasto Operativo - {expense.description}",
                    'Cantidad': 1,
                    'Monto': -expense.amount,
                    'Saldo Running': 0
                })
            
            for movement in movements:
                if movement['Fecha'] and isinstance(movement['Fecha'], str):
                    try:
                        # Intentar convertir la cadena a datetime
                        movement['Fecha'] = datetime.strptime(movement['Fecha'], "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        # Si falla, usar una fecha mínima
                        movement['Fecha'] = datetime.min

            # Ordenar por fecha (manejar fechas None)
            movements.sort(key=lambda x: x['Fecha'] if x['Fecha'] else datetime.min)

            # Calcular saldo corriente
            running_balance = 0
            for movement in movements:
                running_balance += movement['Monto']
                movement['Saldo Running'] = running_balance
                
                # Formatear fecha para mostrar
                if movement['Fecha']:
                    if isinstance(movement['Fecha'], datetime):
                        # Si es datetime, formatearlo
                        movement['Fecha'] = movement['Fecha'].strftime("%Y-%m-%d %H:%M:%S")
                else:
                    movement['Fecha'] = "N/A"
            
            # Crear DataFrame
            df = pd.DataFrame(movements)
            
            # Crear directorio de exportación si no existe
            export_dir = "exports"
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)
            
            filepath = os.path.join(export_dir, filename)
            
            # Crear un archivo Excel con múltiples hojas
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Hoja principal con movimientos
                df.to_excel(writer, sheet_name='Libro Diario', index=False)
                
                # Hoja de resumen
                try:
                    total_sales = Sale.get_total_sales()
                    total_purchases = Purchase.get_total_purchases()
                    total_expenses = Expense.get_total_expenses()
                    cash_in_hand = total_sales - total_purchases - total_expenses
                    
                    summary_data = {
                        'Concepto': ['Total Ventas', 'Total Compras', 'Total Gastos Operativos', 'Efectivo en Posesión'],
                        'Monto': [total_sales, total_purchases, total_expenses, cash_in_hand]
                    }
                    
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Resumen', index=False)
                    
                except Exception as e:
                    print(f"Error al crear resumen: {e}")
                    # Crear resumen vacío en caso de error
                    summary_df = pd.DataFrame({'Error': [f'No se pudo generar resumen: {e}']})
                    summary_df.to_excel(writer, sheet_name='Resumen', index=False)
            
            return filepath
            
        except Exception as e:
            raise Exception(f"Error al exportar libro diario: {str(e)}")