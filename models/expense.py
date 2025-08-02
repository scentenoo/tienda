from config.database import get_connection
from datetime import datetime

class Expense:
    def __init__(self, id=None, description=None, amount=None, 
                 date=None, user_id=None):
        self.id = id
        self.description = description
        self.amount = amount
        self.date = date if date else datetime.now()
        self.user_id = user_id
    
    @classmethod
    def get_total_expenses(cls):
        """Retorna el total de todos los gastos"""
        try:
            cursor = get_connection().cursor()
            cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses")
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            print(f"Error al obtener total de gastos: {e}")
            return 0
    
    @staticmethod
    def get_all():
        """Obtiene todos los gastos operativos"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM expenses ORDER BY date DESC')
        expenses = []
        
        for row in cursor.fetchall():
            expense = Expense(
                row['id'], row['description'], row['amount'],
                datetime.fromisoformat(row['date']) if row['date'] else None,
                row['user_id']
            )
            expenses.append(expense)
        
        conn.close()
        return expenses
    
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
    
    def save(self):
        """Guarda el gasto en la base de datos"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            if self.id is None:
                cursor.execute('''
                    INSERT INTO expenses (description, amount, date, user_id) 
                    VALUES (?, ?, ?, ?)
                ''', (self.description, self.amount, self.date.isoformat(), self.user_id))
                self.id = cursor.lastrowid
            else:
                cursor.execute('''
                    UPDATE expenses SET description = ?, amount = ?, date = ?, user_id = ? 
                    WHERE id = ?
                ''', (self.description, self.amount, self.date.isoformat(), 
                      self.user_id, self.id))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error al guardar gasto: {e}")
            return False
        finally:
            conn.close()
    
    def delete(self):
        """Elimina el gasto"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM expenses WHERE id = ?', (self.id,))
        conn.commit()
        conn.close()