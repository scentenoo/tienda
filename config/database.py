import sqlite3
import os


def get_connection():
    """Obtiene conexión a la base de datos con configuraciones mejoradas"""
    if not os.path.exists('data'):
        os.makedirs('data')
    
    conn = sqlite3.connect('data/tienda.db', timeout=30.0)  # Timeout de 30 segundos
    conn.row_factory = sqlite3.Row
    
    # Configuraciones adicionales para mejorar rendimiento
    conn.execute('PRAGMA journal_mode=WAL')  # Write-Ahead Logging
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA temp_store=MEMORY')
    conn.execute('PRAGMA mmap_size=268435456')  # 256MB
    
    return conn

def migrate_sales_table():
    """Migra la tabla de ventas sin perder datos - VERSIÓN SEGURA"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar estructura actual de la tabla sales
        cursor.execute("PRAGMA table_info(sales)")
        columns = {column[1]: column for column in cursor.fetchall()}
        
        # Lista de columnas que debe tener la tabla sales
        required_columns = {
            'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
            'client_id': 'INTEGER',
            'total': 'REAL NOT NULL',
            'payment_type': 'TEXT NULL',
            'payment_method': 'TEXT NULL',
            'paid_amount': 'REAL DEFAULT 0.0',
            'remaining_debt': 'REAL DEFAULT 0.0',
            'notes': 'TEXT',
            'user_id': 'INTEGER',
            'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'status': 'TEXT DEFAULT "paid"'
        }
        
        # Agregar columnas faltantes una por una (SEGURO)
        for column_name, column_def in required_columns.items():
            if column_name not in columns:
                try:
                    if column_name == 'id':
                        continue  # No se puede agregar PRIMARY KEY con ALTER
                    
                    cursor.execute(f'ALTER TABLE sales ADD COLUMN {column_name} {column_def}')
                    print(f"Columna {column_name} agregada a sales")
                except sqlite3.OperationalError as e:
                    print(f"Columna {column_name} ya existe o error: {e}")
        
        # Migrar datos de payment_type a payment_method si es necesario
        if 'payment_type' in columns and 'payment_method' in columns:
            cursor.execute('UPDATE sales SET payment_method = payment_type WHERE payment_method IS NULL OR payment_method = ""')
        
        # Asegurar que todas las ventas tengan un status válido
        cursor.execute('UPDATE sales SET status = "paid" WHERE status IS NULL OR status = ""')
        
        conn.commit()
        print("Tabla sales migrada correctamente sin pérdida de datos")
        
    except Exception as e:
        print(f"Error al migrar tabla sales: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            

def init_database():
    """Inicializa la base de datos con las tablas necesarias - VERSIÓN CORREGIDA"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Tabla usuarios
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'employee',
                name TEXT,
                position TEXT
            )
        ''')

        # Verificar si hay usuarios, si no, crear el admin por defecto
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            try:
                from utils.security import hash_password
                admin_password = hash_password("admin123")
            except ImportError:
                admin_password = "admin123"  # Fallback si no existe la función hash
            
            cursor.execute(
                "INSERT INTO users (username, password, role, name, position) VALUES (?, ?, ?, ?, ?)",
                ("admin", admin_password, "admin", "Administrador", "Gerente")
            )
            print("Usuario administrador creado con éxito")
        
        # Tabla productos  
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                price REAL NOT NULL,
                stock INTEGER DEFAULT 0,
                cost_price REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla clientes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                phone TEXT,
                address TEXT,
                credit_limit REAL DEFAULT 0.0,
                total_debt REAL DEFAULT 0.0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla para historial de transacciones de clientes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS client_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT NOT NULL,
                sale_id INTEGER NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients (id),
                FOREIGN KEY (sale_id) REFERENCES sales (id)
            )
        ''')
        
        # Tabla de ventas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                total REAL NOT NULL,
                payment_type TEXT NULL,
                payment_method TEXT NULL,
                paid_amount REAL DEFAULT 0.0,
                remaining_debt REAL DEFAULT 0.0,
                notes TEXT,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'paid',
                FOREIGN KEY (client_id) REFERENCES clients (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Tabla de detalles de ventas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sale_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity REAL NOT NULL,
                unit_price REAL NOT NULL,
                sale_price REAL NOT NULL,
                subtotal REAL NOT NULL,
                cost_price REAL DEFAULT 0,
                FOREIGN KEY (sale_id) REFERENCES sales (id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')
        
        # Tabla de compras
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                total REAL NOT NULL,
                iva REAL DEFAULT 0.0,
                shipping REAL DEFAULT 0.0,
                date TEXT DEFAULT CURRENT_TIMESTAMP,
                invoice_number TEXT,
                supplier TEXT,
                freight TEXT,
                tax TEXT,
                subtotal TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Tabla de detalles de compras
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchase_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_cost REAL NULL,
                unit_price REAL NOT NULL,
                subtotal REAL NOT NULL,
                FOREIGN KEY (purchase_id) REFERENCES purchases (id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')
        
        # Tabla de gastos operativos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT,
                date TEXT DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # Tabla de pérdidas/mermas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS losses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                quantity REAL NOT NULL,
                unit_cost REAL NOT NULL,
                total_cost REAL NOT NULL,
                loss_date TIMESTAMP NOT NULL,
                reason TEXT NOT NULL,
                loss_type TEXT NOT NULL,
                notes TEXT,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        ''')
        
        # Agregar columnas faltantes de forma segura
        safe_add_columns = [
            ('clients', 'phone', 'TEXT'),
            ('clients', 'address', 'TEXT'),
            ('clients', 'credit_limit', 'REAL DEFAULT 0.0'),
            ('clients', 'notes', 'TEXT'),
            ('sales', 'notes', 'TEXT'),
            ('sale_details', 'cost_price', 'REAL DEFAULT 0'),
            ('sale_details', 'sale_price', 'REAL'),
            ('purchases', 'date', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
            ('expenses', 'date', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
            ('purchases', 'freight', 'TEXT'),
            ('purchases', 'tax', 'TEXT'),
            ('purchases', 'subtotal', 'TEXT'),
        ]
        
        for table, column, definition in safe_add_columns:
            try:
                cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
                print(f"Columna {column} agregada a {table}")
            except sqlite3.OperationalError:
                pass  # La columna ya existe
        
        # Migrar datos de unit_price a sale_price en sale_details si es necesario
        try:
            cursor.execute('UPDATE sale_details SET sale_price = unit_price WHERE sale_price IS NULL')
        except sqlite3.OperationalError:
            pass
        
        conn.commit()
        print("Base de datos inicializada correctamente")
        
        # Cerrar conexión antes de llamar a migrate_sales_table
        migrate_client_transactions_table() 

    except Exception as e:
        print(f"Error al inicializar base de datos: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            try:
                conn.close()
            except sqlite3.ProgrammingError:
                pass  # Ya estaba cerrada


def migrate_client_transactions_table():
    """Agrega la columna sale_id a client_transactions si no existe"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar si la columna sale_id ya existe
        cursor.execute("PRAGMA table_info(client_transactions)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'sale_id' not in columns:
            cursor.execute('''
                ALTER TABLE client_transactions 
                ADD COLUMN sale_id INTEGER NULL
            ''')
            print("Columna sale_id agregada a client_transactions")
            
            # Agregar la foreign key constraint si no existe
            cursor.execute('''
                PRAGMA foreign_key_list(client_transactions)
            ''')
            fks = cursor.fetchall()
            sale_id_fk_exists = any(fk[3] == 'sales' for fk in fks)
            
            if not sale_id_fk_exists:
                # SQLite no permite agregar FK constraints con ALTER TABLE,
                # así que necesitamos recrear la tabla
                print("Recreando tabla client_transactions con FK constraint...")
                
                # 1. Crear tabla temporal
                cursor.execute('''
                    CREATE TABLE temp_client_transactions AS
                    SELECT * FROM client_transactions
                ''')
                
                # 2. Eliminar tabla original
                cursor.execute('DROP TABLE client_transactions')
                
                # 3. Crear nueva tabla con la estructura correcta
                cursor.execute('''
                    CREATE TABLE client_transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        client_id INTEGER NOT NULL,
                        transaction_type TEXT NOT NULL,
                        amount REAL NOT NULL,
                        description TEXT NOT NULL,
                        sale_id INTEGER NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (client_id) REFERENCES clients (id),
                        FOREIGN KEY (sale_id) REFERENCES sales (id)
                    )
                ''')
                
                # 4. Copiar datos de vuelta
                cursor.execute('''
                    INSERT INTO client_transactions
                    SELECT * FROM temp_client_transactions
                ''')
                
                # 5. Eliminar tabla temporal
                cursor.execute('DROP TABLE temp_client_transactions')
                
        conn.commit()
        print("Migración de client_transactions completada")
        
    except Exception as e:
        print(f"Error al migrar client_transactions: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def update_client_debt_on_payment(client_id, payment_amount, sale_id):
    """Actualiza la deuda del cliente cuando se realiza un pago"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Actualizar deuda total del cliente
        cursor.execute('''
            UPDATE clients 
            SET total_debt = total_debt - ? 
            WHERE id = ?
        ''', (payment_amount, client_id))
        
        # Registrar transacción de pago
        cursor.execute('''
            INSERT INTO client_transactions 
                (client_id, transaction_type, amount, description, sale_id)  # sale_id agregado
            VALUES (?, 'payment', ?, ?, ?)  # Un parámetro más
        ''', (client_id, -payment_amount, f"Pago de venta #{sale_id}", sale_id))  # sale_id incluido
        
        # Actualizar status de la venta si está completamente pagada
        cursor.execute('''
            SELECT total, paid_amount FROM sales WHERE id = ?
        ''', (sale_id,))
        
        sale_data = cursor.fetchone()
        if sale_data:
            total = sale_data['total']
            paid_amount = (sale_data['paid_amount'] or 0) + payment_amount
            
            if paid_amount >= total:
                # Venta completamente pagada
                cursor.execute('''
                    UPDATE sales 
                    SET status = 'paid', paid_amount = ?, remaining_debt = 0
                    WHERE id = ?
                ''', (paid_amount, sale_id))
            else:
                # Pago parcial
                cursor.execute('''
                    UPDATE sales 
                    SET paid_amount = ?, remaining_debt = ?
                    WHERE id = ?
                ''', (paid_amount, total - paid_amount, sale_id))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Error al actualizar deuda del cliente: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def verify_data_integrity():
    """Verifica la integridad de los datos entre ventas y clientes"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar que la deuda total de clientes coincida con ventas pendientes
        cursor.execute('''
            SELECT 
                c.id,
                c.name,
                c.total_debt,
                COALESCE(SUM(s.total - COALESCE(s.paid_amount, 0)), 0) as calculated_debt
            FROM clients c
            LEFT JOIN sales s ON c.id = s.client_id AND s.status = 'pending'
            GROUP BY c.id, c.name, c.total_debt
            HAVING c.total_debt != calculated_debt
        ''')
        
        discrepancies = cursor.fetchall()
        if discrepancies:
            print("Discrepancias encontradas en deudas:")
            for row in discrepancies:
                print(f"Cliente: {row['name']}, Deuda registrada: {row['total_debt']}, Deuda calculada: {row['calculated_debt']}")
        else:
            print("Integridad de datos verificada: OK")
            
    except Exception as e:
        print(f"Error al verificar integridad: {e}")
    finally:
        if conn:
            conn.close()

def migrate_datetime_precision():
    """Asegura que created_at tenga precisión de tiempo"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verificar el tipo de dato actual
        cursor.execute("PRAGMA table_info(client_transactions)")
        columns = cursor.fetchall()
        created_at_type = next((col[2] for col in columns if col[1] == 'created_at'), '')
        
        if 'TIMESTAMP' not in created_at_type.upper():
            # Migrar a TIMESTAMP si no lo es
            cursor.executescript('''
                BEGIN;
                CREATE TABLE temp_transactions AS SELECT * FROM client_transactions;
                DROP TABLE client_transactions;
                CREATE TABLE client_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL,
                    transaction_type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    description TEXT NOT NULL,
                    sale_id INTEGER NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clients (id),
                    FOREIGN KEY (sale_id) REFERENCES sales (id)
                );
                INSERT INTO client_transactions 
                SELECT * FROM temp_transactions;
                DROP TABLE temp_transactions;
                COMMIT;
            ''')
            print("Migración a TIMESTAMP completada")
        
        conn.commit()
    except Exception as e:
        print(f"Error en migrate_datetime_precision: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def fix_all_client_debts():
    """Función para ejecutar una vez y arreglar todo"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("🔄 Iniciando corrección completa...")
        
        # 1. Recalcular todas las deudas basándose en transacciones
        cursor.execute("SELECT id FROM clients")
        client_ids = [row[0] for row in cursor.fetchall()]
        
        for client_id in client_ids:
            # Calcular deuda real
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN transaction_type = 'debit' THEN amount ELSE 0 END), 0) as debits,
                    COALESCE(SUM(CASE WHEN transaction_type = 'credit' THEN amount ELSE 0 END), 0) as credits
                FROM client_transactions 
                WHERE client_id = ?
            """, (client_id,))
            
            result = cursor.fetchone()
            debits = float(result[0])
            credits = float(result[1])
            real_debt = max(0, debits - credits)
            
            # Actualizar cliente
            cursor.execute("""
                UPDATE clients 
                SET total_debt = ?, updated_at = datetime('now', 'localtime')
                WHERE id = ?
            """, (real_debt, client_id))
        
        # 2. Sincronizar estados de ventas
        # Marcar como pagadas las ventas de clientes sin deuda
        cursor.execute('''
            UPDATE sales 
            SET status = 'paid', 
                paid_amount = total, 
                remaining_debt = 0,
                updated_at = datetime('now', 'localtime')
            WHERE client_id IN (
                SELECT id FROM clients WHERE total_debt = 0
            ) AND status = 'pending'
        ''')
        
        updated_sales = cursor.rowcount
        
        # 3. Para clientes con deuda, ajustar estados de ventas
        cursor.execute('''
            SELECT c.id, c.total_debt
            FROM clients c
            WHERE c.total_debt > 0
        ''')
        
        clients_with_debt = cursor.fetchall()
        
        for client in clients_with_debt:
            client_id = client['id']
            current_debt = client['total_debt']
            
            # Obtener ventas pendientes (más antiguas primero)
            cursor.execute('''
                SELECT id, total
                FROM sales 
                WHERE client_id = ? AND status = 'pending'
                ORDER BY created_at ASC
            ''', (client_id,))
            
            pending_sales = cursor.fetchall()
            
            # Distribuir la deuda en las ventas
            remaining_debt = current_debt
            for sale in pending_sales:
                if remaining_debt <= 0:
                    # Esta venta está pagada
                    cursor.execute('''
                        UPDATE sales 
                        SET status = 'paid', paid_amount = total, remaining_debt = 0
                        WHERE id = ?
                    ''', (sale['id'],))
                elif remaining_debt >= sale['total']:
                    # Esta venta sigue pendiente completa
                    remaining_debt -= sale['total']
                    cursor.execute('''
                        UPDATE sales 
                        SET paid_amount = 0, remaining_debt = ?
                        WHERE id = ?
                    ''', (sale['total'], sale['id']))
                else:
                    # Esta venta está parcialmente pagada
                    paid_amount = sale['total'] - remaining_debt
                    cursor.execute('''
                        UPDATE sales 
                        SET paid_amount = ?, remaining_debt = ?
                        WHERE id = ?
                    ''', (paid_amount, remaining_debt, sale['id']))
                    remaining_debt = 0
        
        conn.commit()
        conn.close()
        
        print(f"✅ Corrección completa terminada. {updated_sales} ventas actualizadas")
        return True
        
    except Exception as e:
        print(f"❌ Error en corrección: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False

def migrate_transaction_times():
    """Corrige las horas incorrectas en transacciones existentes"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. Identificar transacciones con horas incorrectas (ej: 19:16 cuando deberían ser 14:16)
        cursor.execute('''
            UPDATE client_transactions
            SET created_at = datetime(created_at, '-5 hours')
            WHERE strftime('%H', created_at) = '19'
              AND strftime('%d', created_at) = '11'
              AND strftime('%m', created_at) = '08'
              AND strftime('%Y', created_at) = '2025'
        ''')
        
        conn.commit()
        print(f"Transacciones corregidas: {cursor.rowcount}")
    except Exception as e:
        print(f"Error en migración: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()