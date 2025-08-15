# diagnostico.py
import sqlite3

def check_database():
    conn = sqlite3.connect('data/tienda.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=== VERIFICANDO BASE DE DATOS ===\n")
    
    # Verificar ventas
    cursor.execute("SELECT COUNT(*) as total FROM sales")
    total_sales = cursor.fetchone()['total']
    print(f"Total de ventas en la BD: {total_sales}")
    
    if total_sales > 0:
        print("\nÚltimas 5 ventas:")
        cursor.execute("SELECT * FROM sales ORDER BY id DESC LIMIT 5")
        for sale in cursor.fetchall():
            print(f"ID: {sale['id']}, Total: {sale['total']}, Status: {sale['status']}, Fecha: {sale['created_at']}")
    
    # Verificar detalles de ventas
    cursor.execute("SELECT COUNT(*) as total FROM sale_details")
    total_details = cursor.fetchone()['total']
    print(f"\nTotal de detalles de venta: {total_details}")
    
    conn.close()

if __name__ == "__main__":
    check_database()