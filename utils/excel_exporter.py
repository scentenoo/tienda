import pandas as pd
from datetime import datetime
import os
from models.sale import Sale
from models.purchase import Purchase
from models.expense import Expense
from models.product import Product
from models.client import Client
from models.loss import Loss
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
    def export_losses(filename=None):
        """Exporta las pérdidas a un archivo Excel"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"perdidas_{timestamp}.xlsx"
        
        try:
            # Obtener datos
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT l.*, p.name as product_name, u.name as user_name
                FROM losses l
                JOIN products p ON l.product_id = p.id
                JOIN users u ON l.created_by = u.id
            ''')
            losses_data = cursor.fetchall()
            conn.close()
            
            # Preparar datos para el DataFrame
            data = []
            for loss_data in losses_data:
                data.append({
                    'ID': loss_data['id'],
                    'Fecha': loss_data['loss_date'],
                    'Producto': loss_data['product_name'],
                    'Cantidad': loss_data['quantity'],
                    'Costo Unitario': loss_data['unit_cost'],
                    'Costo Total': loss_data['total_cost'],
                    'Tipo': loss_data['loss_type'],
                    'Motivo': loss_data['reason'],
                    'Notas': loss_data['notes'],
                    'Registrado por': loss_data['user_name']
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
            raise Exception(f"Error al exportar pérdidas: {str(e)}")

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
                if sale.status == 'paid':  # Solo ventas realmente pagadas
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
            
            # Agregar pérdidas como egresos - NUEVO
            losses = Loss.get_all()
            for loss in losses:
                movements.append({
                    'Fecha': loss.loss_date,
                    'Tipo': 'Egreso',
                    'Concepto': f"Pérdida - {loss.product_name} ({loss.loss_type})",
                    'Cantidad': loss.quantity,
                    'Monto': -loss.total_cost,  # Negativo porque es una pérdida
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
                
                # Hoja de resumen - ACTUALIZADA para incluir pérdidas
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT SUM(total) FROM sales WHERE status = 'paid'")
                    total_sales = cursor.fetchone()[0] or 0.0
                    conn.close()
                    total_purchases = Purchase.get_total_purchases()
                    total_expenses = Expense.get_total_expenses()
                    total_losses = Loss.get_total_losses()  # NUEVO
                    cash_in_hand = total_sales - total_purchases - total_expenses
                    
                    summary_data = {
                        'Concepto': ['Total Ventas', 'Total Compras', 'Total Gastos Operativos', 'Total Pérdidas', 'Efectivo en Posesión'],
                        'Monto': [total_sales, total_purchases, total_expenses, total_losses, cash_in_hand]  # ACTUALIZADO
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
        
    @staticmethod
    def export_inventory_flow(filename=None):
        """Exporta el libro de movimientos de inventario (incluye pérdidas)"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"libro_inventario_{timestamp}.xlsx"
        
        try:
            # Obtener todos los movimientos de inventario
            movements = []
            
            # Obtener datos de referencia
            products = {p.id: p.name for p in Product.get_all()}
            
            # Agregar compras como entradas de inventario
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
                            'Tipo': 'Entrada',
                            'Movimiento': 'Compra',
                            'Producto': product_name,
                            'Cantidad': detail['quantity'],
                            'Costo Unitario': detail['unit_price'],
                            'Costo Total': detail['subtotal'],
                            'Referencia': f"Compra #{purchase.id}",
                            'Notas': f"Factura: {purchase.invoice_number or 'N/A'}"
                        })
            
            # Agregar ventas como salidas de inventario (al costo)
            sales = Sale.get_all()
            for sale in sales:
                    # Obtener detalles de la venta con el costo del producto
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT sd.*, p.name as product_name, p.cost_price
                        FROM sale_details sd
                        JOIN products p ON sd.product_id = p.id
                        WHERE sd.sale_id = ?
                    ''', (sale.id,))
                    
                    details = cursor.fetchall()
                    conn.close()
                    
                    if details:
                        for detail in details:
                            product_name = detail['product_name']
                            cost_price = detail['cost_price'] or 0
                            movements.append({
                                'Fecha': sale.created_at,
                                'Tipo': 'Salida',
                                'Movimiento': 'Venta',
                                'Producto': product_name,
                                'Cantidad': -detail['quantity'],  # Negativo porque es salida
                                'Costo Unitario': cost_price,
                                'Costo Total': -(detail['quantity'] * cost_price),  # Negativo
                                'Referencia': f"Venta #{sale.id}",
                                'Notas': f"Precio venta: ${detail['unit_price']:.2f}"
                            })
            
            # Agregar pérdidas como salidas de inventario - ESTA ES LA PARTE CLAVE
            losses = Loss.get_all()
            for loss in losses:
                movements.append({
                    'Fecha': loss.loss_date,
                    'Tipo': 'Salida',
                    'Movimiento': 'Pérdida',
                    'Producto': loss.product_name,
                    'Cantidad': -loss.quantity,  # Negativo porque es salida
                    'Costo Unitario': loss.unit_cost,
                    'Costo Total': -loss.total_cost,  # Negativo
                    'Referencia': f"Pérdida #{loss.id}",
                    'Notas': f"{loss.loss_type}: {loss.reason}"
                })
            
            # Manejar fechas None y convertir strings a datetime si es necesario
            for movement in movements:
                if movement['Fecha'] and isinstance(movement['Fecha'], str):
                    try:
                        # Intentar convertir la cadena a datetime
                        movement['Fecha'] = datetime.strptime(movement['Fecha'], "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        try:
                            # Intentar formato solo fecha
                            movement['Fecha'] = datetime.strptime(movement['Fecha'], "%Y-%m-%d")
                        except ValueError:
                            # Si falla, usar una fecha mínima
                            movement['Fecha'] = datetime.min
            
            # Ordenar por fecha
            movements.sort(key=lambda x: x['Fecha'] if x['Fecha'] else datetime.min)
            
            # Formatear fechas para mostrar
            for movement in movements:
                if movement['Fecha']:
                    if isinstance(movement['Fecha'], datetime):
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
                # Hoja principal con movimientos de inventario
                df.to_excel(writer, sheet_name='Movimientos Inventario', index=False)
                
                # Hoja de resumen por producto
                try:
                    # Calcular resumen por producto
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    # Obtener resumen de inventario por producto
                    cursor.execute('''
                        SELECT 
                            p.name as producto,
                            p.stock as stock_actual,
                            p.cost_price as costo_actual,
                            (p.stock * p.cost_price) as valor_inventario,
                            COALESCE(compras.total_comprado, 0) as total_comprado,
                            COALESCE(ventas.total_vendido, 0) as total_vendido,
                            COALESCE(perdidas.total_perdido, 0) as total_perdido
                        FROM products p
                        LEFT JOIN (
                            SELECT pd.product_id, SUM(pd.quantity) as total_comprado
                            FROM purchase_details pd
                            GROUP BY pd.product_id
                        ) compras ON p.id = compras.product_id
                        LEFT JOIN (
                            SELECT sd.product_id, SUM(sd.quantity) as total_vendido
                            FROM sale_details sd
                            JOIN sales s ON sd.sale_id = s.id
                            WHERE s.status IN ('paid', 'pending')
                            GROUP BY sd.product_id
                        ) ventas ON p.id = ventas.product_id
                        LEFT JOIN (
                            SELECT l.product_id, SUM(l.quantity) as total_perdido
                            FROM losses l
                            GROUP BY l.product_id
                        ) perdidas ON p.id = perdidas.product_id
                        WHERE p.stock > 0 OR compras.total_comprado > 0 OR ventas.total_vendido > 0 OR perdidas.total_perdido > 0
                        ORDER BY valor_inventario DESC
                    ''')
                    
                    summary_data = cursor.fetchall()
                    conn.close()
                    
                    if summary_data:
                        summary_df = pd.DataFrame([
                            {
                                'Producto': row['producto'],
                                'Stock Actual': row['stock_actual'],
                                'Costo Unitario': row['costo_actual'],
                                'Valor Inventario': row['valor_inventario'],
                                'Total Comprado': row['total_comprado'],
                                'Total Vendido': row['total_vendido'],
                                'Total Perdido': row['total_perdido']
                            }
                            for row in summary_data
                        ])
                    else:
                        summary_df = pd.DataFrame({'Mensaje': ['No hay datos de inventario disponibles']})
                    
                    summary_df.to_excel(writer, sheet_name='Resumen por Producto', index=False)
                    
                except Exception as e:
                    print(f"Error al crear resumen de inventario: {e}")
                    # Crear resumen vacío en caso de error
                    error_df = pd.DataFrame({'Error': [f'No se pudo generar resumen: {e}']})
                    error_df.to_excel(writer, sheet_name='Resumen por Producto', index=False)
            
            return filepath
            
        except Exception as e:
            raise Exception(f"Error al exportar libro de inventario: {str(e)}")