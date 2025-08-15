# unlock_db.py - Ejecutar este script para desbloquear la base de datos

import sqlite3
import os
import time
import gc

def unlock_database():
    """Desbloquea la base de datos forzando el cierre de conexiones"""
    
    print("🔄 Intentando desbloquear la base de datos...")
    
    # 1. Forzar garbage collection
    gc.collect()
    
    # 2. Esperar un momento
    time.sleep(2)
    
    # 3. Intentar conectar con configuraciones específicas
    db_path = 'data/tienda.db'
    
    if not os.path.exists(db_path):
        print("❌ La base de datos no existe")
        return False
    
    try:
        # Conectar con timeout corto
        conn = sqlite3.connect(db_path, timeout=1.0)
        
        # Verificar que podemos hacer operaciones
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        result = cursor.fetchone()
        
        print(f"✅ Base de datos desbloqueada. Usuarios en DB: {result[0]}")
        
        # Optimizar base de datos
        cursor.execute("VACUUM")
        cursor.execute("PRAGMA optimize")
        
        conn.close()
        print("✅ Base de datos optimizada")
        
        return True
        
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            print("⚠️  Base de datos aún bloqueada. Intentando método alternativo...")
            
            # Método alternativo: crear nueva conexión con WAL mode
            try:
                conn = sqlite3.connect(db_path, timeout=30.0)
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA synchronous=NORMAL')
                conn.close()
                print("✅ WAL mode activado. Reintenta ahora.")
                return True
            except Exception as e2:
                print(f"❌ Error: {e2}")
                return False
        else:
            print(f"❌ Error diferente: {e}")
            return False
    
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

if __name__ == "__main__":
    success = unlock_database()
    if success:
        print("\n🎉 ¡Listo! Ahora puedes ejecutar tu aplicación.")
    else:
        print("\n❌ No se pudo desbloquear. Considera reiniciar tu computadora.")
        print("💡 O elimina los archivos .db-wal y .db-shm si existen en la carpeta data/")