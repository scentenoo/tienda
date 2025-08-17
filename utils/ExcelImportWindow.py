import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import filedialog
import os
from config.database import get_connection

class ExcelImportWindow:
    def __init__(self, parent, inventory_window):
        self.parent = parent
        self.inventory_window = inventory_window
        self.excel_data = None
        
        # Crear ventana
        self.window = tk.Toplevel(parent)
        self.window.title("Importar Productos desde Excel")
        self.window.geometry("900x700")
        self.window.transient(parent)
        self.window.grab_set()
        
        self.center_window()
        self.setup_ui()
    
    def center_window(self):
        """Centra la ventana en la pantalla"""
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 800) // 2
        y = (self.window.winfo_screenheight() - 600) // 2
        self.window.geometry(f"900x700+{x}+{y}")
    
    def setup_ui(self):
        # Cambiar el tamaño de la ventana a uno más manejable
        self.window.geometry("900x700")  # Ajustado de 800x600
        
        main_frame = ttk.Frame(self.window, padding="15")  # Reducir padding
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título con menos espacio inferior
        title_label = ttk.Label(main_frame, text="📊 Importar Productos desde Excel", 
                            font=("Arial", 14, "bold"))  # Fuente un poco más pequeña
        title_label.pack(pady=(0, 10))  # Menos espacio después del título
        
        # Instrucciones con menos padding
        instructions_frame = ttk.LabelFrame(main_frame, text="📋 Instrucciones", padding="10")
        instructions_frame.pack(fill=tk.X, pady=(0, 10))
        
        instructions_text = """
        El archivo Excel debe tener las siguientes columnas (exactamente con estos nombres):
        • Nombre: Nombre del producto
        • Precio: Precio unitario (número)
        • Stock: Cantidad en inventario (número entero)
        
        Formato aceptado: .xlsx, .xls
        
        Nota: Los productos existentes con el mismo nombre serán actualizados.
        """
        
        ttk.Label(instructions_frame, text=instructions_text, 
                 font=("Arial", 10), justify=tk.LEFT).pack(anchor=tk.W)
        
        # Selección de archivo
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(file_frame, text="Archivo Excel:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        file_select_frame = ttk.Frame(file_frame)
        file_select_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.file_path_var = tk.StringVar()
        self.file_entry = ttk.Entry(file_select_frame, textvariable=self.file_path_var, 
                                   state="readonly", width=50)
        self.file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(file_select_frame, text="Seleccionar Archivo", 
                  command=self.select_file).pack(side=tk.RIGHT, padx=(10, 0))
        
        # Vista previa de datos
        preview_frame = ttk.LabelFrame(main_frame, text="👁️ Vista Previa", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # Tabla de vista previa
        columns = ("Nombre", "Precio", "Stock", "Estado")
        self.preview_tree = ttk.Treeview(preview_frame, columns=columns, 
                                        show="headings", height=8)
        
        # Configurar columnas
        self.preview_tree.heading("Nombre", text="Nombre")
        self.preview_tree.heading("Precio", text="Precio")
        self.preview_tree.heading("Stock", text="Stock")
        self.preview_tree.heading("Estado", text="Estado")
        
        self.preview_tree.column("Nombre", width=200)
        self.preview_tree.column("Precio", width=100)
        self.preview_tree.column("Stock", width=100)
        self.preview_tree.column("Estado", width=150)
        
        # Scrollbar para vista previa
        preview_scroll = ttk.Scrollbar(preview_frame, orient="vertical", 
                                     command=self.preview_tree.yview)
        self.preview_tree.configure(yscrollcommand=preview_scroll.set)
        
        self.preview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Botones
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        
        ttk.Button(buttons_frame, text="Cancelar", 
                  command=self.cancel).pack(side=tk.RIGHT, padx=(10, 0))
        
        self.import_button = ttk.Button(buttons_frame, text="Importar Productos", 
                                       command=self.import_products, state="disabled")
        self.import_button.pack(side=tk.RIGHT)
        
        # Estadísticas
        self.stats_label = ttk.Label(buttons_frame, text="Seleccione un archivo para comenzar", 
                                    font=("Arial", 10))
        self.stats_label.pack(side=tk.LEFT, pady=(10, 0))
    
    def select_file(self):
        """Selecciona el archivo Excel"""
        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo Excel",
            filetypes=[
                ("Archivos Excel", "*.xlsx *.xls"),
                ("Todos los archivos", "*.*")
            ]
        )
        
        if file_path:
            self.file_path_var.set(file_path)
            self.load_excel_data(file_path)
    
    def load_excel_data(self, file_path):
        """Carga y valida los datos del Excel"""
        try:
            # Leer archivo Excel
            df = pd.read_excel(file_path)
            
            # Validar columnas requeridas
            required_columns = ['Nombre', 'Precio', 'Stock']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                messagebox.showerror("Error", 
                                   f"Faltan las siguientes columnas: {', '.join(missing_columns)}")
                return
            
            # Limpiar y validar datos
            df = df[required_columns].copy()  # Solo columnas necesarias
            df = df.dropna()  # Eliminar filas vacías
            
            # Validar datos
            valid_data = []
            for index, row in df.iterrows():
                nombre = str(row['Nombre']).strip()
                precio = row['Precio']
                stock = row['Stock']
                estado = "✅ Válido"
                
                # Validaciones
                if not nombre or nombre.lower() == 'nan':
                    estado = "❌ Nombre vacío"
                elif not isinstance(precio, (int, float)) or precio < 0:
                    estado = "❌ Precio inválido"
                elif not isinstance(stock, (int, float)) or stock < 0 or stock != int(stock):
                    estado = "❌ Stock inválido"
                
                valid_data.append({
                    'nombre': nombre,
                    'precio': float(precio) if isinstance(precio, (int, float)) else 0,
                    'stock': int(stock) if isinstance(stock, (int, float)) else 0,
                    'estado': estado,
                    'valido': estado == "✅ Válido"
                })
            
            self.excel_data = valid_data
            self.populate_preview()
            
            # Estadísticas
            total = len(valid_data)
            validos = sum(1 for item in valid_data if item['valido'])
            invalidos = total - validos
            
            stats_text = f"Total: {total} | Válidos: {validos} | Con errores: {invalidos}"
            self.stats_label.config(text=stats_text)
            
            # Habilitar botón de importar si hay datos válidos
            if validos > 0:
                self.import_button.config(state="normal")
            else:
                self.import_button.config(state="disabled")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al leer archivo Excel: {e}")
    
    def populate_preview(self):
        """Llena la vista previa con los datos"""
        # Limpiar tabla
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)
        
        # Agregar datos
        for item in self.excel_data:
            precio_formatted = f"${item['precio']:,.2f}"
            
            tags = []
            if not item['valido']:
                tags.append("error")
            
            self.preview_tree.insert("", "end",
                                   values=(item['nombre'], precio_formatted, 
                                          item['stock'], item['estado']),
                                   tags=tags)
        
        # Configurar colores
        self.preview_tree.tag_configure("error", background="#f8d7da")
    
    def import_products(self):
        """Importa los productos válidos"""
        if not self.excel_data:
            return
        
        valid_items = [item for item in self.excel_data if item['valido']]
        
        if not valid_items:
            messagebox.showwarning("Sin datos válidos", "No hay productos válidos para importar")
            return
        
        result = messagebox.askyesno("Confirmar Importación", 
                                   f"¿Desea importar {len(valid_items)} productos válidos?\n\n"
                                   f"Los productos existentes con el mismo nombre serán actualizados.")
        
        if not result:
            return
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            imported = 0
            updated = 0
            errors = []
            
            for item in valid_items:
                try:
                    # Verificar si el producto existe
                    cursor.execute("SELECT id FROM products WHERE LOWER(name) = LOWER(?)", 
                                 (item['nombre'],))
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Actualizar producto existente
                        cursor.execute('''
                            UPDATE products 
                            SET price = ?, stock = ? 
                            WHERE id = ?
                        ''', (item['precio'], item['stock'], existing['id']))
                        updated += 1
                    else:
                        # Insertar nuevo producto
                        cursor.execute('''
                            INSERT INTO products (name, price, stock) 
                            VALUES (?, ?, ?)
                        ''', (item['nombre'], item['precio'], item['stock']))
                        imported += 1
                        
                except Exception as e:
                    errors.append(f"Error con '{item['nombre']}': {e}")
            
            conn.commit()
            conn.close()
            
            # Mostrar resultados
            result_text = f"Importación completada:\n"
            result_text += f"• Productos nuevos: {imported}\n"
            result_text += f"• Productos actualizados: {updated}\n"
            
            if errors:
                result_text += f"• Errores: {len(errors)}\n\nErrores:\n" + "\n".join(errors[:5])
                if len(errors) > 5:
                    result_text += f"\n... y {len(errors)-5} errores más"
            
            messagebox.showinfo("Importación Completada", result_text)
            
            # Actualizar inventario
            self.inventory_window.refresh_products()
            
            # Cerrar ventana
            self.window.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error durante la importación: {e}")
    
    def cancel(self):
        """Cancela la importación"""
        self.window.destroy()