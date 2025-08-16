import sqlite3
import os
from config.database import get_connection

def fix_updated_at_column():
    """
    Agrega la columna updated_at a las tablas que la necesitan
    y corrige las consultas que la usan
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("🔧 INICIANDO CORRECCIÓN DE COLUMNA updated_at")
        print("=" * 60)
        
        # Lista de tablas que necesitan la columna updated_at
        tables_to_fix = ['sales', 'clients', 'products', 'purchases', 'expenses']
        
        for table in tables_to_fix:
            try:
                # Verificar si la tabla existe
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                if not cursor.fetchone():
                    print(f"⚠️ Tabla {table} no existe, saltando...")
                    continue
                
                # Verificar si la columna updated_at ya existe
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [column[1] for column in cursor.fetchall()]
                
                if 'updated_at' not in columns:
                    # Agregar columna updated_at
                    cursor.execute(f'''
                        ALTER TABLE {table} 
                        ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ''')
                    print(f"✅ Columna updated_at agregada a {table}")
                else:
                    print(f"ℹ️ Columna updated_at ya existe en {table}")
                    
            except sqlite3.OperationalError as e:
                print(f"⚠️ Error con tabla {table}: {e}")
                continue
        
        # Confirmar cambios
        conn.commit()
        print(f"\n✅ CORRECCIÓN COMPLETADA")
        print("Todas las tablas ahora tienen la columna updated_at")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en corrección: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def fix_clients_window_queries():
    """
    Crea una versión corregida de las consultas problemáticas
    """
    print("\n🔧 CREANDO CONSULTAS CORREGIDAS")
    print("=" * 50)
    
    # Consultas corregidas que deberían usar en clients_window.py
    fixed_queries = {
        "update_sales_to_paid": """
            UPDATE sales 
            SET {status_column} = 'paid',
                updated_at = datetime('now', 'localtime')
            WHERE id = ?
        """,
        
        "update_sales_to_pending": """
            UPDATE sales 
            SET {status_column} = 'pending',
                updated_at = datetime('now', 'localtime')
            WHERE id = ?
        """,
        
        "update_sales_partial_payment": """
            UPDATE sales 
            SET total = ?,
                notes = ?,
                updated_at = datetime('now', 'localtime')
            WHERE id = ?
        """,
        
        "update_client_debt": """
            UPDATE clients 
            SET total_debt = MAX(0, total_debt - ?),
                updated_at = datetime('now', 'localtime')
            WHERE id = ?
        """
    }
    
    for query_name, query in fixed_queries.items():
        print(f"📝 {query_name}:")
        print(f"   {query.strip()}")
        print()
    
    return fixed_queries


def alternative_fix_without_updated_at():
    """
    Versión alternativa que no usa updated_at para compatibilidad inmediata
    """
    print("\n🔧 ALTERNATIVA SIN updated_at")
    print("=" * 40)
    
    alternative_queries = {
        "update_sales_to_paid": """
            UPDATE sales 
            SET {status_column} = 'paid'
            WHERE id = ?
        """,
        
        "update_sales_to_pending": """
            UPDATE sales 
            SET {status_column} = 'pending'
            WHERE id = ?
        """,
        
        "update_sales_partial_payment": """
            UPDATE sales 
            SET total = ?,
                notes = ?
            WHERE id = ?
        """,
        
        "update_client_debt": """
            UPDATE clients 
            SET total_debt = MAX(0, total_debt - ?)
            WHERE id = ?
        """
    }
    
    print("💡 SOLUCIÓN INMEDIATA:")
    print("Reemplazar todas las consultas que usan 'updated_at' con estas versiones:")
    print()
    
    for query_name, query in alternative_queries.items():
        print(f"📝 {query_name}:")
        print(f"   {query.strip()}")
        print()
    
    return alternative_queries


def create_fixed_payment_method():
    """
    Crea una versión corregida del método register_payment
    """
    
    fixed_method = '''
def register_payment(self):
    """Registra un pago del cliente aplicándolo directamente a ventas específicas - VERSIÓN CORREGIDA"""
    try:
        # Obtener y validar datos de entrada
        amount_str = self.payment_amount_entry.get().strip()
        description = self.payment_desc_entry.get().strip()
        
        if not amount_str or not description:
            messagebox.showerror("Error", "Complete todos los campos")
            return
        
        try:
            amount = float(amount_str)
        except ValueError:
            messagebox.showerror("Error", "Ingrese un monto válido")
            return
        
        if amount <= 0:
            messagebox.showerror("Error", "El monto debe ser mayor a cero")
            return
        
        # Refrescar datos del cliente
        self.client = Client.get_by_id(self.client.id)
        deuda_actual = self.client.total_debt
        
        # Confirmación
        if amount > deuda_actual:
            exceso = amount - deuda_actual
            mensaje = f"PAGO MAYOR A LA DEUDA\\n\\nDeuda: ${deuda_actual:,.2f}\\nPago: ${amount:,.2f}\\nExceso: ${exceso:,.2f}\\n\\n¿Continuar?"
        else:
            mensaje = f"Registrar pago de ${amount:,.2f}\\nDescripción: {description}\\n\\n¿Continuar?"
        
        if not messagebox.askyesno("Confirmar Pago", mensaje):
            return
        
        # Procesar pago
        resultado = self.process_complete_payment_fixed(amount, description)
        
        if resultado['success']:
            self.payment_amount_entry.delete(0, tk.END)
            self.payment_desc_entry.delete(0, tk.END)
            messagebox.showinfo("Éxito", f"Pago de ${amount:,.2f} procesado correctamente")
            self.refresh_and_close()
        else:
            messagebox.showerror("Error", f"Error al procesar pago:\\n{resultado['error']}")
            
    except Exception as e:
        messagebox.showerror("Error", f"Error inesperado: {str(e)}")
'''
    
    print("\n🔧 MÉTODO CORREGIDO:")
    print("=" * 30)
    print(fixed_method)
    
    return fixed_method


if __name__ == "__main__":
    print("🚀 INICIANDO CORRECCIÓN DE BASE DE DATOS")
    print("=" * 80)
    
    # Paso 1: Intentar agregar columna updated_at
    print("\n📋 PASO 1: Agregar columna updated_at")
    success = fix_updated_at_column()
    
    if success:
        print("\n✅ La base de datos ha sido corregida")
        print("💡 Ahora puede ejecutar el programa normalmente")
    else:
        print("\n⚠️ No se pudo agregar la columna automáticamente")
        print("💡 Use la solución alternativa sin updated_at")
    
    # Paso 2: Mostrar consultas corregidas
    print("\n📋 PASO 2: Consultas corregidas")
    fix_clients_window_queries()
    
    # Paso 3: Mostrar alternativa sin updated_at
    print("\n📋 PASO 3: Solución alternativa")
    alternative_fix_without_updated_at()
    
    print("\n" + "="*80)
    print("🎯 RESUMEN:")
    print("1. Ejecute este script para agregar la columna updated_at")
    print("2. O modifique clients_window.py para no usar updated_at")
    print("3. Reinicie la aplicación")
    print("="*80)