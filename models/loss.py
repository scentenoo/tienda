from config.database import get_connection
from datetime import datetime

class Loss:
    def __init__(self, id=None, product_id=None, quantity=None, unit_cost=None, 
                 total_cost=None, loss_date=None, reason=None, loss_type=None, 
                 notes=None, created_by=None, created_at=None):
        self.id = id
        self.product_id = product_id
        self.quantity = quantity
        self.unit_cost = unit_cost
        self.total_cost = total_cost
        self.loss_date = loss_date if loss_date else datetime.now()
        self.reason = reason
        self.loss_type = loss_type  # 'expiration', 'damage', 'theft', 'other'
        self.notes = notes
        self.created_by = created_by
        self.created_at = created_at if created_at else datetime.now()
    
    def save(self):
        """Guarda la pérdida en la base de datos y actualiza el inventario"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Iniciar transacción
            conn.execute("BEGIN TRANSACTION")
            
            # Guardar la pérdida
            if self.id is None:
                cursor.execute('''
                    INSERT INTO losses (product_id, quantity, unit_cost, total_cost, 
                                      loss_date, reason, loss_type, notes, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (self.product_id, self.quantity, self.unit_cost, self.total_cost,
                      self.loss_date, self.reason, self.loss_type, self.notes, self.created_by))
                self.id = cursor.lastrowid
            else:
                cursor.execute('''
                    UPDATE losses 
                    SET product_id=?, quantity=?, unit_cost=?, total_cost=?, 
                        loss_date=?, reason=?, loss_type=?, notes=?, created_by=?
                    WHERE id=?
                ''', (self.product_id, self.quantity, self.unit_cost, self.total_cost,
                      self.loss_date, self.reason, self.loss_type, self.notes, 
                      self.created_by, self.id))
            
            # Actualizar el inventario (reducir stock)
            cursor.execute('''
                UPDATE products 
                SET stock = stock - ? 
                WHERE id = ?
            ''', (self.quantity, self.product_id))
            
            # Confirmar transacción
            conn.commit()
            return True
            
        except Exception as e:
            # Revertir en caso de error
            conn.rollback()
            print(f"Error al guardar pérdida: {e}")
            return False
        finally:
            conn.close()
    
    @staticmethod
    def get_all(start_date=None, end_date=None, product_id=None, loss_type=None):
        """Obtiene todas las pérdidas con filtros opcionales"""
        conn = get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT l.*, p.name as product_name, u.name as user_name
            FROM losses l
            JOIN products p ON l.product_id = p.id
            JOIN users u ON l.created_by = u.id
            WHERE 1=1
        '''
        params = []
        
        if start_date:
            query += " AND l.loss_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND l.loss_date <= ?"
            params.append(end_date)
        
        if product_id:
            query += " AND l.product_id = ?"
            params.append(product_id)
        
        if loss_type:
            query += " AND l.loss_type = ?"
            params.append(loss_type)
        
        query += " ORDER BY l.loss_date DESC"
        
        cursor.execute(query, params)
        losses_data = cursor.fetchall()
        conn.close()
        
        losses = []
        for loss_data in losses_data:
            loss = Loss(
                id=loss_data['id'],
                product_id=loss_data['product_id'],
                quantity=loss_data['quantity'],
                unit_cost=loss_data['unit_cost'],
                total_cost=loss_data['total_cost'],
                loss_date=loss_data['loss_date'],
                reason=loss_data['reason'],
                loss_type=loss_data['loss_type'],
                notes=loss_data['notes'],
                created_by=loss_data['created_by'],
                created_at=loss_data['created_at']
            )
            # Agregar datos adicionales
            loss.product_name = loss_data['product_name']
            loss.user_name = loss_data['user_name']
            losses.append(loss)
        
        return losses
    
    @staticmethod
    def get_by_id(loss_id):
        """Obtiene una pérdida por su ID"""
        try:
            loss_id = int(loss_id)  # Asegurar que sea un entero
        except (ValueError, TypeError):
            print(f"Error: ID de pérdida inválido: {loss_id}")
            return None
            
        conn = get_connection()
        if conn is None:
            print("Error: No se pudo conectar a la base de datos")
            return None
            
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT l.*, p.name as product_name, u.name as user_name
                FROM losses l
                JOIN products p ON l.product_id = p.id
                JOIN users u ON l.created_by = u.id
                WHERE l.id = ?
            ''', (loss_id,))
            
            loss_data = cursor.fetchone()
            
            if not loss_data:
                print(f"No se encontró pérdida con ID: {loss_id}")
                return None
                
            # Crear instancia de Loss con todos los atributos básicos
            loss = Loss(
                id=loss_data['id'],
                product_id=loss_data['product_id'],
                quantity=loss_data['quantity'],
                unit_cost=loss_data['unit_cost'],
                total_cost=loss_data['total_cost'],
                loss_date=loss_data['loss_date'],
                reason=loss_data['reason'],
                loss_type=loss_data['loss_type'],
                notes=loss_data['notes'],
                created_by=loss_data['created_by'],
                created_at=loss_data['created_at']
            )
            
            # Agregar atributos adicionales
            loss.product_name = loss_data['product_name']
            loss.user_name = loss_data['user_name']
            
            return loss
            
        except Exception as e:
            print(f"Error al obtener pérdida: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            conn.close()

    @classmethod
    def get_total_losses(cls):
        """Obtiene el total de pérdidas en dinero"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT COALESCE(SUM(total_cost), 0) as total FROM losses')
            result = cursor.fetchone()
            conn.close()
            
            return float(result['total']) if result else 0.0
            
        except Exception as e:
            print(f"Error al calcular pérdidas: {e}")
            return 0.0
    
    def delete(self):
        """Elimina la pérdida y restaura el stock del producto"""
        if self.id is None:
            print("Error: No se puede eliminar una pérdida sin ID")
            return False
            
        conn = get_connection()
        if conn is None:
            print("Error: No se pudo conectar a la base de datos")
            return False
            
        cursor = conn.cursor()
        
        try:
            # Iniciar transacción
            conn.execute("BEGIN TRANSACTION")
            
            # 1. Obtener los datos de la pérdida antes de eliminarla
            cursor.execute('SELECT product_id, quantity FROM losses WHERE id = ?', (self.id,))
            loss_data = cursor.fetchone()
            
            if not loss_data:
                print(f"Error: No se encontró la pérdida con ID {self.id}")
                conn.rollback()
                return False
            
            product_id, quantity = loss_data['product_id'], loss_data['quantity']
            
            # 2. Restaurar el stock del producto
            cursor.execute('''
                UPDATE products 
                SET stock = stock + ? 
                WHERE id = ?
            ''', (quantity, product_id))
            
            # Verificar que el producto fue actualizado
            if cursor.rowcount == 0:
                print(f"Error: No se pudo actualizar el producto con ID {product_id}")
                conn.rollback()
                return False
            
            # 3. Eliminar la pérdida
            cursor.execute('DELETE FROM losses WHERE id = ?', (self.id,))
            
            # Verificar que la pérdida fue eliminada
            if cursor.rowcount == 0:
                print(f"Error: No se pudo eliminar la pérdida con ID {self.id}")
                conn.rollback()
                return False
            
            # Confirmar transacción
            conn.commit()
            print(f"Pérdida {self.id} eliminada correctamente")
            return True
            
        except Exception as e:
            conn.rollback()
            print(f"Error al eliminar pérdida: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            conn.close()
    
    @staticmethod
    def get_summary_by_type(start_date=None, end_date=None):
        """Obtiene un resumen de pérdidas por tipo"""
        conn = get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT loss_type, SUM(total_cost) as total, COUNT(*) as count
            FROM losses
            WHERE 1=1
        '''
        params = []
        
        if start_date:
            query += " AND loss_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND loss_date <= ?"
            params.append(end_date)
        
        query += " GROUP BY loss_type ORDER BY total DESC"
        
        cursor.execute(query, params)
        summary = cursor.fetchall()
        conn.close()
        
        return summary