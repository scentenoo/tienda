from config.database import get_connection
from datetime import datetime

class Purchase:
    def __init__(self, id=None, user_id=None, total=None, 
                 iva=None, shipping=None, date=None, invoice_number=None, supplier="Sin proveedor"):
        self.id = id
        self.user_id = user_id
        self.total = total
        self.iva = iva
        self.shipping = shipping
        self.date = date
        self.invoice_number = invoice_number
        self.supplier = supplier
    
    @staticmethod
    def get_all():
        """Obtiene todas las compras"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM purchases ORDER BY date DESC')
        purchases = []
        
        for row in cursor.fetchall():
            purchase = Purchase(
                id=row['id'],
                user_id=row['user_id'],
                total=row['total'],
                iva=row['iva'],
                shipping=row['shipping'],
                date=row['date'],
                invoice_number=row['invoice_number'],
                supplier=row['supplier']
            )
            purchases.append(purchase)
        
        conn.close()
        return purchases
    
    def save(self):
        """Guarda la compra en la base de datos"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            if self.id is None:
                cursor.execute('''
                    INSERT INTO purchases (user_id, total, iva, shipping, 
                                         date, invoice_number, supplier) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (self.user_id, self.total, self.iva, 
                      self.shipping, self.date, self.invoice_number,
                      self.supplier if self.supplier else "Sin proveedor"))
                self.id = cursor.lastrowid
            else:
                cursor.execute('''
                    UPDATE purchases SET user_id = ?, total = ?, iva = ?, 
                                       shipping = ?, date = ?, invoice_number = ?, 
                                       supplier = ? 
                    WHERE id = ?
                ''', (self.user_id, self.total, self.iva, 
                      self.shipping, self.date, self.invoice_number,
                      self.supplier if self.supplier else "Sin proveedor", self.id))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error al guardar compra: {e}")
            return False
        finally:
            conn.close()
    
    @classmethod
    def get_total_purchases(cls):
        """Retorna el total de todas las compras"""
        try:
            from config.database import get_connection
            cursor = get_connection().cursor()
            cursor.execute("SELECT COALESCE(SUM(total), 0) FROM purchases")
            result = cursor.fetchone()
            cursor.close()
            return result[0] if result else 0
        except Exception as e:
            print(f"Error al obtener total de compras: {e}")
            return 0
    
    def delete(self):
        """Elimina la compra de la base de datos"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM purchases WHERE id = ?', (self.id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error al eliminar la compra: {e}")
            return False
        finally:
            conn.close()