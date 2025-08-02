import sqlite3
import os

def update_database():
    """Actualiza la base de datos agregando las columnas necesarias"""
    
    if not os.path.exists('data'):
        os.makedirs('data')
    
    conn = sqlite3.connect('data/tienda.db')
    cursor = conn.cursor()
    
    try:
        # Agregar nuevas columnas a la tabla clients
        columns_to_add = [
            ('phone', 'TEXT'),
            ('address', 'TEXT'), 
            ('credit_limit', 'REAL DEFAULT 0.0'),
            ('notes', 'TEXT')
        ]
        
        for column_name, column_type in columns_to_add:
            try:
                cursor.execute(f'ALTER TABLE clients ADD COLUMN {column_name} {column_type}')
                print(f"✓ Columna {column_name} agregada exitosamente")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print(f"○ Columna {column_name} ya existe")
                else:
                    print(f"✗ Error al agregar columna {column_name}: {e}")
        
        # Crear tabla de transacciones de clientes si no existe
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS client_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL,
                    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('debit', 'credit')),
                    amount REAL NOT NULL,
                    description TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clients (id)
                )
            ''')
            print("✓ Tabla client_transactions creada/verificada")
        except Exception as e:
            print(f"✗ Error al crear tabla de transacciones: {e}")
        
        conn.commit()
        print("\n✅ Base de datos actualizada exitosamente")
        
    except Exception as e:
        print(f"✗ Error general: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_database()