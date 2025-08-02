from config.database import get_connection
from datetime import datetime

class Sale:
    def __init__(self, id=None, client_id=None, client_name=None, total=None, 
                 payment_method=None, notes=None, created_at=None, items=None, user_id=None, status=None):
        self.id = id
        self.client_id = client_id
        self.client_name = client_name
        self.total = total
        self.payment_method = payment_method
        self.notes = notes
        self.created_at = created_at
        self.items = items or []
        self.user_id = user_id
        self.status = status  # Nuevo atributo para el estado de la venta
    
    @staticmethod
    def get_all():
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT s.id, s.client_id, c.name as client_name, s.total, 
                s.payment_type, s.notes, s.created_at, s.status
            FROM sales s
            LEFT JOIN clients c ON s.client_id = c.id
            ORDER BY s.created_at DESC
        ''')
        
        sales = []
        for row in cursor.fetchall():
            sale = Sale(
                id=row['id'],
                client_id=row['client_id'],
                client_name=row['client_name'] if row['client_name'] else "Venta al contado",
                total=row['total'],
                payment_method=row['payment_type'],
                notes=row['notes'] if row['notes'] else None,
                created_at=row['created_at'],
                status=row['status']  # Añadir el status
            )
            sales.append(sale)
        
        conn.close()
        return sales
    
    def save(self):
        """Guarda la venta en la base de datos"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            if self.id is None:
                cursor.execute('''
                    INSERT INTO sales (client_id, total, payment_type, notes, created_at, user_id, status) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (self.client_id, self.total, 
                    self.payment_method, self.notes, 
                    self.created_at, self.user_id, self.status))
                self.id = cursor.lastrowid
            else:
                cursor.execute('''
                    UPDATE sales SET client_id = ?, total = ?, payment_type = ?, 
                                notes = ?, created_at = ?, user_id = ?, status = ? 
                    WHERE id = ?
                ''', (self.client_id, self.total, 
                    self.payment_method, self.notes, 
                    self.created_at, self.user_id, self.status, self.id))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error al guardar la venta: {e}")
            return False
        finally:
            conn.close()
        
    def get_items(self):
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT product_id, product_name, quantity, unit_price, subtotal
            FROM sale_items WHERE sale_id = ?
        ''', (self.id,))
        
        items = []
        for row in cursor.fetchall():
            items.append({
                'product_id': row['product_id'],
                'product_name': row['product_name'],
                'quantity': row['quantity'],
                'unit_price': row['unit_price'],
                'subtotal': row['subtotal']
            })
        
        conn.close()
        return items
    
    @classmethod
    def get_total_sales(cls):
        """Retorna el total de todas las ventas"""
        try:
            from config.database import get_connection
            cursor = get_connection().cursor()
            
            # Sin filtro por status ya que la columna no existe
            cursor.execute("SELECT COALESCE(SUM(total), 0) FROM sales")
            result = cursor.fetchone()
            cursor.close()
            return result[0] if result else 0
        except Exception as e:
            print(f"Error al obtener total de ventas: {e}")
            return 0
        
    def delete(self):
        """Elimina la venta de la base de datos"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM sales WHERE id = ?', (self.id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error al eliminar la venta: {e}")
            return False
        finally:
            conn.close()
        
    @staticmethod
    def get_by_date_range(start_date, end_date):
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT s.id, s.client_id, c.name as client_name, s.total, 
                   s.payment_method, s.notes, s.created_at
            FROM sales s
            LEFT JOIN clients c ON s.client_id = c.id
            WHERE DATE(s.created_at) BETWEEN ? AND ?
            ORDER BY s.created_at DESC
        ''', (start_date, end_date))
        
        sales = []
        for row in cursor.fetchall():
            sale = Sale(
                id=row['id'],
                client_id=row['client_id'],
                client_name=row['client_name'] if row['client_name'] else "Venta al contado",
                total=row['total'],
                payment_method=row['payment_method'],
                notes=row['notes'] if row['notes'] else None,
                created_at=row['created_at']
            )
            sales.append(sale)
        
        conn.close()
        return sales