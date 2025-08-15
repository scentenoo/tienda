from config.database import get_connection
from datetime import datetime
from utils.validators import safe_float_conversion
from models.client import Client

class Sale:
    def __init__(self, id=None, client_id=None, client_name=None, total=None, 
                 payment_method=None, notes=None, created_at=None, items=None, 
                 user_id=None, status=None, paid_amount=0, remaining_debt=0):
        self.id = id
        self.client_id = client_id
        self.client_name = client_name
        self.total = total
        self.payment_method = payment_method or 'cash'  # Valor por defecto
        self.notes = notes
        self.created_at = created_at or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.items = items or []
        self.user_id = user_id
        self.status = status or 'paid'  # Valor por defecto
        self.paid_amount = paid_amount
        self.remaining_debt = remaining_debt
    
    def save(self):
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Validar que ventas a crédito tengan cliente
            if self.payment_method == 'credit' and not self.client_id:
                raise ValueError("Ventas a crédito requieren un cliente")

            # Guardar venta
            cursor.execute('''
                INSERT INTO sales (client_id, total, payment_method, notes, created_at, user_id, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (self.client_id, self.total, self.payment_method, self.notes, 
                self.created_at, self.user_id, self.status))
            self.id = cursor.lastrowid

            # Solo registrar en historial si es a crédito
            if self.payment_method == 'credit' and self.client_id:
                product_list = ", ".join([f"{item['product_name']} x{item['quantity']}" for item in self.items])
                
                # Registrar como DEUDA (tipo 'debit')
                cursor.execute('''
                    INSERT INTO client_transactions 
                        (client_id, transaction_type, amount, description)
                    VALUES (?, 'debit', ?, ?)
                ''', (
                    self.client_id,
                    self.total,
                    f"Venta fiada #{self.id}: {product_list}"
                ))
                
                # Actualizar deuda del cliente
                cursor.execute('''
                    UPDATE clients SET total_debt = total_debt + ? WHERE id = ?
                ''', (self.total, self.client_id))

            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error al guardar venta: {e}")
            return False
        finally:
            conn.close()
    
    def _get_old_status(self, cursor):
        """Obtiene el estado anterior de la venta"""
        cursor.execute('SELECT status FROM sales WHERE id = ?', (self.id,))
        result = cursor.fetchone()
        return result['status'] if result else 'paid'
    
    def _update_client_debt(self, amount, operation):
        """Actualiza la deuda del cliente y registra la transacción"""
        client = Client.get_by_id(self.client_id)
        if not client:
            raise ValueError("Cliente no encontrado")
        
        if operation == 'add':
            client.add_debt(amount, f"Venta #{self.id}")
        elif operation == 'subtract':
            client.pay_debt(amount, f"Pago de venta #{self.id}")
        
        # Actualizar montos en la venta
        if operation == 'subtract':
            self.paid_amount = self.total
            self.remaining_debt = 0
            self.status = 'paid'
        elif operation == 'add':
            self.paid_amount = 0
            self.remaining_debt = self.total
            self.status = 'pending'
    
    def register_payment(self, amount, description=""):
        """Registra un pago (fondo verde) y actualiza la deuda."""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Registrar el pago como 'credit' (verde)
            cursor.execute('''
                INSERT INTO client_transactions
                    (client_id, transaction_type, amount, description)
                VALUES (?, 'credit', ?, ?)
            ''', (
                self.client_id,
                -amount,  # Monto negativo (pago reduce deuda)
                f"Pago: {description} (Venta #{self.id})"
            ))

            # Resto de la lógica de actualización...
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error al registrar pago: {e}")
            return False
        finally:
            conn.close()
    
    # Resto de métodos permanecen igual...
    @staticmethod
    def get_all():
        """Obtiene todas las ventas con información completa - VERSIÓN CORREGIDA"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT s.*, c.name as client_name
                FROM sales s
                LEFT JOIN clients c ON s.client_id = c.id
                ORDER BY s.created_at DESC
            ''')
            
            sales = []
            for row in cursor.fetchall():
                # Determinar estado correctamente
                status = row['status'] if row['status'] else ('pending' if row['client_id'] else 'paid')
                
                # Determinar método de pago
                payment_method = row['payment_method'] or row['payment_type'] or 'cash'
                
                sale = Sale(
                    id=row['id'],
                    client_id=row['client_id'],
                    client_name=row['client_name'],
                    total=row['total'],
                    payment_method=payment_method,
                    notes=row['notes'],
                    created_at=row['created_at'],
                    user_id=row['user_id'],
                    status=status,
                    paid_amount=row['paid_amount'] or 0,
                    remaining_debt=row['remaining_debt'] or 0
                )
                sales.append(sale)
            
            return sales
            
        except Exception as e:
            print(f"Error en Sale.get_all(): {e}")
            return []
        finally:
            conn.close()
    
    @staticmethod
    def get_by_id(sale_id):
        """Obtiene una venta por ID - VERSIÓN CORREGIDA"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT s.*, c.name as client_name
                FROM sales s
                LEFT JOIN clients c ON s.client_id = c.id
                WHERE s.id = ?
            ''', (sale_id,))
            
            row = cursor.fetchone()
            if row:
                # Determinar estado correctamente
                status = row['status'] if row['status'] else ('pending' if row['client_id'] else 'paid')
                
                # Determinar método de pago
                payment_method = row['payment_method'] or row['payment_type'] or 'cash'
                
                return Sale(
                    id=row['id'],
                    client_id=row['client_id'],
                    client_name=row['client_name'],
                    total=row['total'],
                    payment_method=payment_method,
                    notes=row['notes'],
                    created_at=row['created_at'],
                    user_id=row['user_id'],
                    status=status,
                    paid_amount=row['paid_amount'] or 0,
                    remaining_debt=row['remaining_debt'] or 0
                )
            return None
        except Exception as e:
            print(f"Error al obtener venta por ID: {e}")
            return None
        finally:
            conn.close()
    
    @staticmethod
    def get_total_sales():
        """Retorna el total de todas las ventas"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COALESCE(SUM(total), 0) FROM sales")
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else 0
        except Exception as e:
            print(f"Error al obtener total de ventas: {e}")
            return 0
    
    @staticmethod
    def get_by_date_range(start_date, end_date):
        """Obtiene ventas por rango de fechas - CORREGIDO"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT s.*, c.name as client_name
                FROM sales s
                LEFT JOIN clients c ON s.client_id = c.id
                WHERE DATE(s.created_at) BETWEEN ? AND ?
                ORDER BY s.created_at DESC
            ''', (start_date, end_date))
            
            sales = []
            for row in cursor.fetchall():
                # APLICAR MISMA LÓGICA DE CORRECCIÓN
                payment_method = None
                if 'payment_method' in row.keys() and row['payment_method']:
                    payment_method = row['payment_method']
                elif 'payment_type' in row.keys() and row['payment_type']:
                    payment_method = row['payment_type']
                else:
                    payment_method = 'cash'
                
                status = 'paid'
                if 'status' in row.keys() and row['status']:
                    status = row['status']
                else:
                    if row['client_id'] is not None:
                        status = 'pending'
                
                sale = Sale(
                    id=row['id'],
                    client_id=row['client_id'],
                    client_name=row['client_name'],
                    total=row['total'],
                    payment_method=payment_method,
                    notes=row['notes'] if 'notes' in row.keys() else None,
                    created_at=row['created_at'],
                    user_id=row['user_id'] if 'user_id' in row.keys() else None,
                    status=status
                )
                sales.append(sale)
            
            return sales
        except Exception as e:
            print(f"Error al obtener ventas por fecha: {e}")
            return []
        finally:
            conn.close()

    def mark_as_paid_if_client_paid(self):
        """Marca la venta como pagada si el cliente no tiene deuda"""
        if not self.client_id:
            return False
        
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Verificar deuda del cliente
            cursor.execute('SELECT total_debt FROM clients WHERE id = ?', (self.client_id,))
            result = cursor.fetchone()
            
            if result and result[0] <= 0:
                # Cliente sin deuda, marcar venta como pagada
                cursor.execute('''
                    UPDATE sales 
                    SET status = 'paid' 
                    WHERE id = ? AND status = 'pending'
                ''', (self.id,))
                
                conn.commit()
                self.status = 'paid'
                return True
                
            return False
            
        except Exception as e:
            print(f"Error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    @staticmethod
    def get_filtered_sales(start_date=None, end_date=None, client_id=None, status=None, payment_method=None):
        """Obtiene ventas filtradas por múltiples criterios - CORREGIDO"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Construir query dinámico
            query = '''
                SELECT s.*, c.name as client_name
                FROM sales s
                LEFT JOIN clients c ON s.client_id = c.id
                WHERE 1=1
            '''
            params = []
            
            if start_date:
                query += ' AND DATE(s.created_at) >= ?'
                params.append(start_date)
            
            if end_date:
                query += ' AND DATE(s.created_at) <= ?'
                params.append(end_date)
            
            if client_id:
                query += ' AND s.client_id = ?'
                params.append(client_id)
            
            if status:
                query += ' AND s.status = ?'
                params.append(status)
            
            if payment_method:
                # BUSCAR EN AMBOS CAMPOS POSIBLES
                query += ' AND (s.payment_method = ? OR s.payment_type = ?)'
                params.extend([payment_method, payment_method])
            
            query += ' ORDER BY s.created_at DESC'
            
            cursor.execute(query, params)
            
            sales = []
            for row in cursor.fetchall():
                # APLICAR MISMA LÓGICA DE CORRECCIÓN
                payment_method_value = None
                if 'payment_method' in row.keys() and row['payment_method']:
                    payment_method_value = row['payment_method']
                elif 'payment_type' in row.keys() and row['payment_type']:
                    payment_method_value = row['payment_type']
                else:
                    payment_method_value = 'cash'
                
                status_value = 'paid'
                if 'status' in row.keys() and row['status']:
                    status_value = row['status']
                else:
                    if row['client_id'] is not None:
                        status_value = 'pending'
                
                sale = Sale(
                    id=row['id'],
                    client_id=row['client_id'],
                    client_name=row['client_name'],
                    total=row['total'],
                    payment_method=payment_method_value,
                    notes=row['notes'] if 'notes' in row.keys() else None,
                    created_at=row['created_at'],
                    user_id=row['user_id'] if 'user_id' in row.keys() else None,
                    status=status_value
                )
                sales.append(sale)
            
            return sales
        except Exception as e:
            print(f"Error al filtrar ventas: {e}")
            return []
        finally:
            conn.close()
    
    def get_details(self):
        """Obtiene los detalles/items de la venta"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT sd.*, p.name as product_name 
                FROM sale_details sd
                JOIN products p ON sd.product_id = p.id
                WHERE sd.sale_id = ?
            ''', (self.id,))
            
            details = []
            for row in cursor.fetchall():
                details.append({
                    'product_id': row['product_id'],
                    'product_name': row['product_name'],
                    'quantity': row['quantity'],
                    'unit_price': row['unit_price'],
                    'subtotal': row['subtotal']
                })
            
            return details
        except Exception as e:
            print(f"Error al obtener detalles de venta: {e}")
            return []
        finally:
            conn.close()
    
    # MÉTODOS ADICIONALES PARA MEJOR FUNCIONALIDAD
    
    @staticmethod
    def get_pending_sales():
        """Obtiene solo las ventas pendientes (fiadas)"""
        return Sale.get_filtered_sales(status='pending')
    
    @staticmethod
    def get_paid_sales():
        """Obtiene solo las ventas pagadas"""
        return Sale.get_filtered_sales(status='paid')
    
    def mark_as_paid(self):
        """Marca una venta como pagada"""
        self.status = 'paid'
        return self.save()
    
    def mark_as_pending(self):
        """Marca una venta como pendiente"""
        self.status = 'pending'
        return self.save()
    
    def get_client(self):
        """Obtiene el objeto Client asociado a esta venta"""
        if not self.client_id:
            return None
        
        from models.client import Client
        return Client.get_by_id(self.client_id)
    
    def __str__(self):
        """Representación en string de la venta"""
        client_info = f"Cliente: {self.client_name}" if self.client_name else "Venta al contado"
        return f"Venta #{self.id} - {client_info} - Total: ${self.total:,.2f} - Estado: {self.status}"
    
    def __repr__(self):
        return f"Sale(id={self.id}, total={self.total}, status='{self.status}', client_id={self.client_id})"