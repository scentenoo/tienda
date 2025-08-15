from config.database import get_connection
import sqlite3  # Agregar esta línea

class Product:
    def __init__(self, id=None, name=None, price=None, stock=None, cost_price=None, created_at=None):
        self.id = id
        self.name = name
        self.price = price
        self.stock = stock
        self.cost_price = cost_price  # Añadir aquí
        self.created_at = created_at
    
    @staticmethod
    def get_all():
        """Obtiene todos los productos de la base de datos"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM products ORDER BY name')
        products_data = cursor.fetchall()
        
        conn.close()
        
        products = []
        for product_data in products_data:
            product = Product(
                id=product_data['id'],
                name=product_data['name'],
                price=product_data['price'],
                stock=product_data['stock'],
                cost_price=product_data['cost_price'],  # Añadir aquí
                created_at=product_data['created_at']
            )
            products.append(product)
        
        return products
    
    @staticmethod
    def get_by_id(product_id):
        """Obtiene un producto por ID"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return Product(row['id'], row['name'], row['price'], row['stock'])
        return None
    
    @staticmethod
    def get_by_name(name):
        """Obtiene un producto por nombre"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM products WHERE name = ?', (name,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return Product(row['id'], row['name'], row['price'], row['stock'])
        return None
    
    def save(self):
        """Guarda el producto en la base de datos"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            if self.id is None:
                cursor.execute('''
                    INSERT INTO products (name, price, stock) 
                    VALUES (?, ?, ?)
                ''', (self.name, self.price, self.stock))
                self.id = cursor.lastrowid
            else:
                cursor.execute('''
                    UPDATE products SET name = ?, price = ?, stock = ? 
                    WHERE id = ?
                ''', (self.name, self.price, self.stock, self.id))
            
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def delete(self):
        """Elimina el producto"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM products WHERE id = ?', (self.id,))
        conn.commit()
        conn.close()
    
    def update_stock(self, quantity_change):
        """Actualiza el stock del producto"""
        self.stock += quantity_change
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE products SET stock = ? WHERE id = ?', 
                      (self.stock, self.id))
        conn.commit()
        conn.close()