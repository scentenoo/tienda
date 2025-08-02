from config.database import get_connection
from datetime import datetime

class AccountReceivable:
    def __init__(self, id=None, client_id=None, client_name=None, 
                 transaction_type=None, amount=None, description=None, created_at=None):
        self.id = id
        self.client_id = client_id
        self.client_name = client_name
        self.transaction_type = transaction_type
        self.amount = amount
        self.description = description
        self.created_at = created_at
    
    @staticmethod
    def get_all_transactions():
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ct.id, ct.client_id, c.name as client_name, ct.transaction_type,
                   ct.amount, ct.description, ct.created_at
            FROM client_transactions ct
            INNER JOIN clients c ON ct.client_id = c.id
            ORDER BY ct.created_at DESC
        ''')
        
        transactions = []
        for row in cursor.fetchall():
            transaction = AccountReceivable(
                id=row['id'],
                client_id=row['client_id'],
                client_name=row['client_name'],
                transaction_type=row['transaction_type'],
                amount=row['amount'],
                description=row['description'] if row['description'] else None,
                created_at=row['created_at']
            )
            transactions.append(transaction)
        
        conn.close()
        return transactions
    
    @staticmethod
    def get_clients_with_debt():
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, phone, total_debt
            FROM clients 
            WHERE total_debt > 0
            ORDER BY total_debt DESC
        ''')
        
        clients = []
        for row in cursor.fetchall():
            clients.append({
                'id': row['id'],
                'name': row['name'],
                'phone': row['phone'] if row['phone'] else None,
                'total_debt': row['total_debt']
            })
        
        conn.close()
        return clients
    
    @staticmethod
    def add_payment(client_id, amount, description="Pago"):
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Agregar transacción de pago (crédito)
            cursor.execute('''
                INSERT INTO client_transactions (client_id, transaction_type, amount, description, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (client_id, 'credit', amount, description, 
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            # Actualizar deuda del cliente
            cursor.execute('''
                UPDATE clients SET total_debt = total_debt - ? WHERE id = ?
            ''', (amount, client_id))
            
            # Asegurar que la deuda no sea negativa
            cursor.execute('''
                UPDATE clients SET total_debt = 0 WHERE id = ? AND total_debt < 0
            ''', (client_id,))
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    @staticmethod
    def get_client_transactions(client_id):
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, transaction_type, amount, description, created_at
            FROM client_transactions 
            WHERE client_id = ?
            ORDER BY created_at DESC
        ''', (client_id,))
        
        transactions = []
        for row in cursor.fetchall():
            transactions.append({
                'id': row['id'],
                'transaction_type': row['transaction_type'],
                'amount': row['amount'],
                'description': row['description'] if row['description'] else None,
                'created_at': row['created_at']
            })
        
        conn.close()
        return transactions