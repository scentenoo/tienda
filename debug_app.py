import tkinter as tk
from views.login_window import LoginWindow
from config.database import init_database

def main():
    try:
        print("=== INICIANDO APLICACIÓN ===")
        
        # Inicializar base de datos
        print("1. Inicializando base de datos...")
        init_database()
        print("   ✓ Base de datos lista")
        
        # Crear ventana principal
        print("2. Creando ventana principal...")
        root = tk.Tk()
        root.withdraw()  # Ocultar inicialmente
        root.title("Sistema de Gestión")
        print("   ✓ Ventana principal creada y oculta")
        
        # Configurar cierre
        def on_quit():
            print("   → Cerrando aplicación...")
            root.quit()
        
        root.protocol("WM_DELETE_WINDOW", on_quit)
        
        # Mostrar login
        print("3. Creando ventana de login...")
        login_window = LoginWindow(root)
        print("   ✓ Ventana de login creada")
        print("   ✓ Ventana de login debe estar visible ahora")
        
        print("4. Iniciando bucle principal...")
        print("   → La aplicación está corriendo")
        print("   → Use las credenciales: admin / admin123")
        print("   → Presione Ctrl+C para forzar cierre si es necesario")
        
        # Iniciar mainloop
        root.mainloop()
        
        print("=== APLICACIÓN TERMINADA ===")
        
    except KeyboardInterrupt:
        print("\n✗ Aplicación interrumpida por el usuario")
    except Exception as e:
        print(f"✗ Error inesperado: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()