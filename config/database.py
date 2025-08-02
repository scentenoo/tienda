import sqlite3
import os

def get_connection():
    """Obtiene conexión a la base de datos"""
    if not os.path.exists('data'):
        os.makedirs('data')
    
    conn = sqlite3.connect('data/tienda.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Inicializa la base de datos con las tablas necesarias"""
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
        from utils.security import hash_password
        admin_password = hash_password("admin123")
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla clientes (actualizada)
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
            transaction_type TEXT NULL,
            amount REAL NOT NULL,
            description TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients (id)
        )
    ''')
    
    # NUEVAS TABLAS AGREGADAS:
    
    # Tabla de ventas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            total REAL NOT NULL,
            payment_type TEXT NULL,
            paid_amount REAL DEFAULT 0.0,
            remaining_debt REAL DEFAULT 0.0,
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
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            subtotal REAL NOT NULL,
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
            unit_cost REAL,
            subtotal REAL NOT NULL,
            unit_price REAL,
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
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Crear usuario admin por defecto
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, password, role) 
        VALUES ('admin', 'admin123', 'admin')
    ''')
    
    # Agregar columnas nuevas a la tabla clients si no existen
    try:
        cursor.execute('ALTER TABLE clients ADD COLUMN phone TEXT')
    except sqlite3.OperationalError:
        pass  # La columna ya existe
    
    try:
        cursor.execute('ALTER TABLE clients ADD COLUMN address TEXT')
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute('ALTER TABLE clients ADD COLUMN credit_limit REAL DEFAULT 0.0')
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute('ALTER TABLE clients ADD COLUMN notes TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE sales ADD COLUMN notes TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE purchases ADD COLUMN date TEXT DEFAULT CURRENT_TIMESTAMP')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE expenses ADD COLUMN date TEXT DEFAULT CURRENT_TIMESTAMP')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE purchases ADD COLUMN product_id TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE purchases ADD COLUMN quantity REAL DEFAULT 0.0')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE purchases ADD COLUMN unit_price REAL DEFAULT 0.0')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE purchases ADD COLUMN freight TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE purchases ADD COLUMN tax TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE purchases ADD COLUMN invoice_number TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE purchases ADD COLUMN subtotal TEXT')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE purchase_details ADD COLUMN unit_price REAL NULL')
    except sqlite3.OperationalError:
        pass
    # NUEVO CÓDIGO AÑADIDO:
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_details_new (
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

    # Copiar datos existentes
    cursor.execute('''
        INSERT INTO purchase_details_new (id, purchase_id, product_id, quantity, unit_cost, unit_price, subtotal)
        SELECT id, purchase_id, product_id, quantity, unit_cost, unit_price, subtotal FROM purchase_details
    ''')

    # Eliminar tabla original
    cursor.execute('DROP TABLE IF EXISTS purchase_details')

    # Renombrar la nueva tabla
    cursor.execute('ALTER TABLE purchase_details_new RENAME TO purchase_details')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales_new (
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

    # Eliminar tabla original
    cursor.execute('DROP TABLE IF EXISTS sales')

    # Renombrar la nueva tabla
    cursor.execute('ALTER TABLE sales_new RENAME TO sales')

    conn.commit()
    conn.close()
    print("Base de datos inicializada correctamente")