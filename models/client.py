from config.database import get_connection

class Client:
    def __init__(self, id=None, name=None, phone=None, address=None, 
                 credit_limit=0.0, total_debt=0.0, notes=None):
        self.id = id
        self.name = name
        self.phone = phone
        self.address = address
        self.credit_limit = credit_limit
        self.total_debt = total_debt
        self.notes = notes
    
    @staticmethod
    def get_all():
        """Obtiene todos los clientes"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, phone, address, credit_limit, total_debt, notes
            FROM clients 
            ORDER BY name
        ''')
        
        clients = []
        for row in cursor.fetchall():
            client = Client(
                id=row['id'],
                name=row['name'],
                phone=row['phone'] if row['phone'] else None,
                address=row['address'] if row['address'] else None,
                credit_limit=row['credit_limit'] if row['credit_limit'] else 0.0,
                total_debt=row['total_debt'],
                notes=row['notes'] if row['notes'] else None
            )
            clients.append(client)
        
        conn.close()
        return clients
    
    @staticmethod
    def get_by_id(client_id):
        """Obtiene un cliente por ID"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, phone, address, credit_limit, total_debt, notes
            FROM clients 
            WHERE id = ?
        ''', (client_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return Client(
                id=row['id'], 
                name=row['name'],
                phone=row['phone'] if row['phone'] else None,
                address=row['address'] if row['address'] else None,
                credit_limit=row['credit_limit'] if row['credit_limit'] else 0.0,
                total_debt=row['total_debt'],
                notes=row['notes'] if row['notes'] else None
            )
        return None
    
    def save(self):
        """Guarda un nuevo cliente"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO clients (name, phone, address, credit_limit, total_debt, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (self.name, self.phone, self.address, 
              self.credit_limit or 0.0, self.total_debt or 0.0, self.notes))
        
        self.id = cursor.lastrowid
        conn.commit()
        conn.close()
        return self.id
    
    def update(self):
        """Actualiza el cliente existente"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE clients 
            SET name = ?, phone = ?, address = ?, credit_limit = ?, notes = ?
            WHERE id = ?
        ''', (self.name, self.phone, self.address, 
              self.credit_limit or 0.0, self.notes, self.id))
        
        conn.commit()
        conn.close()
    
    def delete(self):
        """Elimina el cliente"""
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar si el cliente tiene deuda
        if self.total_debt and self.total_debt > 0:
            raise Exception("No se puede eliminar un cliente con deuda pendiente")
        
        cursor.execute('DELETE FROM clients WHERE id = ?', (self.id,))
        conn.commit()
        conn.close()
    
    def add_debt(self, amount, description):
        """Agrega deuda al cliente"""
        conn = get_connection()
        cursor = conn.cursor()
        
        # Actualizar deuda total del cliente
        cursor.execute('''
            UPDATE clients 
            SET total_debt = total_debt + ?
            WHERE id = ?
        ''', (amount, self.id))
        
        # Registrar transacción
        cursor.execute('''
            INSERT INTO client_transactions (client_id, transaction_type, amount, description)
            VALUES (?, 'debit', ?, ?)
        ''', (self.id, amount, description))
        
        conn.commit()
        conn.close()
        
        self.total_debt = (self.total_debt or 0.0) + amount
    
    def pay_debt(self, amount, description):
        """Registra un pago (reduce la deuda)"""
        conn = get_connection()
        cursor = conn.cursor()
        
        # No permitir pago mayor a la deuda
        current_debt = self.total_debt or 0.0
        if amount > current_debt:
            amount = current_debt
        
        # Actualizar deuda del cliente
        cursor.execute('''
            UPDATE clients 
            SET total_debt = total_debt - ?
            WHERE id = ?
        ''', (amount, self.id))
        
        # Registrar transacción
        cursor.execute('''
            INSERT INTO client_transactions (client_id, transaction_type, amount, description)
            VALUES (?, 'credit', ?, ?)
        ''', (self.id, amount, description))
        
        conn.commit()
        conn.close()
        
        self.total_debt = current_debt - amount
        return amount
    
    def get_transactions(self, limit=50):
        """Obtiene el historial de transacciones del cliente"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT transaction_type, amount, description, created_at
            FROM client_transactions
            WHERE client_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (self.id, limit))
        
        transactions = cursor.fetchall()
        conn.close()
        return transactions
    
    @staticmethod
    def search(query):
        """Busca clientes por nombre o teléfono"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, phone, address, credit_limit, total_debt, notes
            FROM clients 
            WHERE name LIKE ? OR phone LIKE ?
            ORDER BY name
        ''', (f'%{query}%', f'%{query}%'))
        
        clients = []
        for row in cursor.fetchall():
            client = Client(
                id=row['id'], 
                name=row['name'],
                phone=row['phone'] if row['phone'] else None,
                address=row['address'] if row['address'] else None,
                credit_limit=row['credit_limit'] if row['credit_limit'] else 0.0,
                total_debt=row['total_debt'],
                notes=row['notes'] if row['notes'] else None
            )
            clients.append(client)
        
        conn.close()
        return clients
    
    def available_credit(self):
        """Calcula el crédito disponible"""
        credit = self.credit_limit or 0.0
        debt = self.total_debt or 0.0
        return max(0, credit - debt)
    
    def can_buy(self, amount):
        """Verifica si el cliente puede comprar por el monto especificado"""
        return self.available_credit() >= amount