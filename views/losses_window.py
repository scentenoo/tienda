import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from models.loss import Loss
from models.product import Product
from utils.validators import validate_number, validate_positive

class LossesWindow:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        
        # Inicializar variables
        self.unit_cost_var = tk.StringVar()
        self.product_var = tk.StringVar()  # Añadir esta línea
        self.products = {}  # Añadir esta línea
        
        # Verificar si el usuario tiene permisos (solo admin)
        if self.user.role != 'admin':
            messagebox.showwarning("Acceso Denegado", 
                                 "Solo los administradores pueden acceder a este módulo.")
            return
        
        # Crear ventana
        self.window = tk.Toplevel(parent)
        self.window.title("Gestión de Pérdidas y Mermas")
        self.window.geometry("1500x650")
        self.window.resizable(True, True)
        
        # Centrar ventana
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        # Configurar UI
        self.setup_ui()
        
        # Cargar datos
        self.load_data()
    
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Frame principal
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, text="Gestión de Pérdidas y Mermas", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Frame para filtros
        filter_frame = ttk.LabelFrame(main_frame, text="Filtros", padding="10")
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Filtros
        ttk.Label(filter_frame, text="Desde:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.start_date_var = tk.StringVar()
        start_date_entry = ttk.Entry(filter_frame, textvariable=self.start_date_var, width=12)
        start_date_entry.grid(row=0, column=1, pady=5, padx=5)
        
        ttk.Label(filter_frame, text="Hasta:").grid(row=0, column=2, sticky=tk.W, pady=5)
        self.end_date_var = tk.StringVar()
        end_date_entry = ttk.Entry(filter_frame, textvariable=self.end_date_var, width=12)
        end_date_entry.grid(row=0, column=3, pady=5, padx=5)
        
        ttk.Label(filter_frame, text="Tipo:").grid(row=0, column=4, sticky=tk.W, pady=5)
        self.loss_type_var = tk.StringVar()
        loss_type_combo = ttk.Combobox(filter_frame, textvariable=self.loss_type_var, width=15, state="readonly")
        loss_type_combo['values'] = ["Todos", "Vencimiento", "Daño", "Robo", "Otro"]
        loss_type_combo.current(0)
        loss_type_combo.grid(row=0, column=5, pady=5, padx=5)
        
        # Botones de filtro
        ttk.Button(filter_frame, text="Filtrar", command=self.apply_filters).grid(row=0, column=6, padx=5)
        ttk.Button(filter_frame, text="Limpiar", command=self.clear_filters).grid(row=0, column=7, padx=5)
        
        # Frame para lista y formulario
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Frame para formulario
        form_frame = ttk.LabelFrame(content_frame, text="Registrar Pérdida", padding="10")
        form_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
       # Campos del formulario
        ttk.Label(form_frame, text="Producto:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.product_var = tk.StringVar()
        self.product_combo = ttk.Combobox(form_frame, textvariable=self.product_var, width=25, state="readonly")
        self.product_combo.grid(row=0, column=1, pady=5, padx=5)
        
        # Cargar productos y configurar el combobox
        self.load_products()
        
        # Vincular función al evento <<ComboboxSelected>>
        self.product_combo.bind("<<ComboboxSelected>>", self.update_unit_cost)
        
        # Inicializar el costo unitario con el primer producto (si existe)
        if self.products:
            first_product_key = next(iter(self.products))
            first_product = self.products[first_product_key]
            self.unit_cost_var.set(str(first_product.cost_price))
        else:
            self.unit_cost_var.set("")

        # Vincular función al evento <<ComboboxSelected>>
        self.product_combo.bind("<<ComboboxSelected>>", self.update_unit_cost)
        
        ttk.Label(form_frame, text="Cantidad:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.quantity_var = tk.StringVar()
        quantity_entry = ttk.Entry(form_frame, textvariable=self.quantity_var, width=10)
        quantity_entry.grid(row=1, column=1, pady=5, padx=5, sticky=tk.W)
        
        ttk.Label(form_frame, text="Costo Unitario:").grid(row=2, column=0, sticky=tk.W, pady=5)
        unit_cost_entry = ttk.Entry(form_frame, textvariable=self.unit_cost_var, width=10)
        unit_cost_entry.grid(row=2, column=1, pady=5, padx=5, sticky=tk.W)
        
        ttk.Label(form_frame, text="Fecha:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.loss_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        loss_date_entry = ttk.Entry(form_frame, textvariable=self.loss_date_var, width=12)
        loss_date_entry.grid(row=3, column=1, pady=5, padx=5, sticky=tk.W)
        
        ttk.Label(form_frame, text="Tipo de Pérdida:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.form_loss_type_var = tk.StringVar(value="Vencimiento")
        form_loss_type_combo = ttk.Combobox(form_frame, textvariable=self.form_loss_type_var, width=15, state="readonly")
        form_loss_type_combo['values'] = ["Vencimiento", "Daño", "Robo", "Otro"]
        form_loss_type_combo.grid(row=4, column=1, pady=5, padx=5, sticky=tk.W)
        
        ttk.Label(form_frame, text="Motivo:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.reason_var = tk.StringVar()
        reason_entry = ttk.Entry(form_frame, textvariable=self.reason_var, width=25)
        reason_entry.grid(row=5, column=1, pady=5, padx=5)
        
        ttk.Label(form_frame, text="Notas:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.notes_var = tk.StringVar()
        notes_entry = ttk.Entry(form_frame, textvariable=self.notes_var, width=25)
        notes_entry.grid(row=6, column=1, pady=5, padx=5)
        
        # Botones
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="Guardar", command=self.save_loss).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Limpiar", command=self.clear_form).pack(side=tk.LEFT, padx=5)
        
        # Frame para lista de pérdidas
        list_frame = ttk.LabelFrame(content_frame, text="Pérdidas Registradas", padding="10")
        list_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Treeview para mostrar pérdidas
        columns = ('ID', 'Fecha', 'Producto', 'Cantidad', 'Costo Total', 'Tipo', 'Motivo')
        self.losses_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        # Configurar columnas
        self.losses_tree.heading('ID', text='ID')
        self.losses_tree.heading('Fecha', text='Fecha')
        self.losses_tree.heading('Producto', text='Producto')
        self.losses_tree.heading('Cantidad', text='Cantidad')
        self.losses_tree.heading('Costo Total', text='Costo Total')
        self.losses_tree.heading('Tipo', text='Tipo')
        self.losses_tree.heading('Motivo', text='Motivo')
        
        self.losses_tree.column('ID', width=50, anchor=tk.CENTER)
        self.losses_tree.column('Fecha', width=100)
        self.losses_tree.column('Producto', width=150)
        self.losses_tree.column('Cantidad', width=80, anchor=tk.CENTER)
        self.losses_tree.column('Costo Total', width=100, anchor=tk.E)
        self.losses_tree.column('Tipo', width=100)
        self.losses_tree.column('Motivo', width=150)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.losses_tree.yview)
        self.losses_tree.configure(yscroll=scrollbar.set)
        
        # Empaquetar treeview y scrollbar
        self.losses_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Botones para ver detalles y eliminar
        action_frame = ttk.Frame(list_frame)
        action_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(action_frame, text="Ver Detalles", command=self.view_loss_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Eliminar", command=self.delete_loss).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Actualizar", command=self.load_data).pack(side=tk.RIGHT, padx=5)
        
        # Frame para resumen
        summary_frame = ttk.LabelFrame(main_frame, text="Resumen de Pérdidas", padding="10")
        summary_frame.pack(fill=tk.X, pady=10)
        
        # Etiquetas de resumen
        self.total_losses_label = ttk.Label(summary_frame, text="Total de Pérdidas: $0.00")
        self.total_losses_label.pack(side=tk.LEFT, padx=20)
        
        self.expiration_losses_label = ttk.Label(summary_frame, text="Por Vencimiento: $0.00")
        self.expiration_losses_label.pack(side=tk.LEFT, padx=20)
        
        self.damage_losses_label = ttk.Label(summary_frame, text="Por Daño: $0.00")
        self.damage_losses_label.pack(side=tk.LEFT, padx=20)
        
        self.other_losses_label = ttk.Label(summary_frame, text="Otros: $0.00")
        self.other_losses_label.pack(side=tk.LEFT, padx=20)
    
    def load_products(self):
        """Carga los productos en el combobox"""
        try:
            products = Product.get_all()
            if not products:  # Si no hay productos
                messagebox.showwarning("Advertencia", "No hay productos registrados. Registre productos primero.")
                self.product_combo['values'] = ["No hay productos"]
                self.product_combo.set("No hay productos")
                return
                
            self.products = {f"{p.id} - {p.name}": p for p in products}
            product_list = list(self.products.keys())
            
            # Configurar Combobox
            self.product_combo['values'] = product_list
            self.product_combo.set(product_list[0] if product_list else "")
            
            # Actualizar costo unitario del primer producto
            if product_list:
                self.update_unit_cost()
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar productos: {str(e)}")
            print(f"Error detallado: {e}")  # Log para debugging
        

    def update_unit_cost(self, event=None):
        """Actualiza el costo unitario cuando cambia la selección del producto"""
        try:
            selected_key = self.product_var.get()
            if selected_key and selected_key in self.products:
                selected_product = self.products[selected_key]
                self.unit_cost_var.set(f"{selected_product.cost_price:.2f}")
            else:
                self.unit_cost_var.set("0.00")
        except Exception as e:
            print(f"Error al actualizar costo unitario: {e}")
            self.unit_cost_var.set("0.00")
            
        
    def load_data(self):
        """Carga las pérdidas en el treeview"""
        try:
            # Limpiar treeview
            for item in self.losses_tree.get_children():
                self.losses_tree.delete(item)
            
            # Obtener filtros
            start_date = self.start_date_var.get() if self.start_date_var.get() else None
            end_date = self.end_date_var.get() if self.end_date_var.get() else None
            loss_type = None if self.loss_type_var.get() == "Todos" else self.loss_type_var.get()
            
            # Obtener pérdidas
            losses = Loss.get_all(start_date, end_date, None, loss_type)
            
            if not losses:
                self.losses_tree.insert('', tk.END, values=("No hay datos", "", "", "", "", "", ""))
                self.update_summary([], start_date, end_date)
                return
            
            # Insertar en treeview
            for loss in losses:
                self.losses_tree.insert('', tk.END, values=(
                    loss.id,
                    loss.loss_date.strftime("%Y-%m-%d") if isinstance(loss.loss_date, datetime) else loss.loss_date,
                    loss.product_name,
                    f"{loss.quantity:.2f}",
                    f"${loss.total_cost:.2f}",
                    loss.loss_type,
                    loss.reason
                ))
            
            # Actualizar resumen
            self.update_summary(losses, start_date, end_date)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar datos: {str(e)}")
    
    def update_summary(self, losses, start_date=None, end_date=None):
        """Actualiza el resumen de pérdidas"""
        try:
            # Obtener resumen por tipo
            summary = Loss.get_summary_by_type(start_date, end_date)
            
            # Inicializar valores
            total = 0
            expiration = 0
            damage = 0
            other = 0
            
            # Procesar resumen
            for item in summary:
                amount = item['total']
                total += amount
                
                if item['loss_type'] == 'Vencimiento':
                    expiration = amount
                elif item['loss_type'] == 'Daño':
                    damage = amount
                else:
                    other += amount
            
            # Actualizar etiquetas
            self.total_losses_label.config(text=f"Total de Pérdidas: ${total:.2f}")
            self.expiration_losses_label.config(text=f"Por Vencimiento: ${expiration:.2f}")
            self.damage_losses_label.config(text=f"Por Daño: ${damage:.2f}")
            self.other_losses_label.config(text=f"Otros: ${other:.2f}")
            
        except Exception as e:
            print(f"Error al actualizar resumen: {e}")
    
    def apply_filters(self):
        """Aplica los filtros seleccionados"""
        self.load_data()
    
    def clear_filters(self):
        """Limpia los filtros"""
        self.start_date_var.set("")
        self.end_date_var.set("")
        self.loss_type_var.set("Todos")
        self.load_data()
    
    def save_loss(self):
        """Guarda una nueva pérdida"""
        try:
            # Validar campos
            if not self.product_var.get():
                messagebox.showerror("Error", "Debe seleccionar un producto")
                return
            
            quantity = validate_positive(self.quantity_var.get(), "Cantidad")
            if quantity is None:
                return

            unit_cost = validate_positive(self.unit_cost_var.get(), "Costo Unitario")
            if unit_cost is None:
                return
            
            if not self.reason_var.get():
                messagebox.showerror("Error", "Debe ingresar un motivo")
                return
            
            # Obtener producto seleccionado
            product_key = self.product_var.get()
            product = self.products[product_key]
            
            # Verificar stock disponible
            if quantity > product.stock:
                messagebox.showerror("Error", f"Stock insuficiente. Disponible: {product.stock}")
                return
            
            # Calcular costo total
            total_cost = quantity * unit_cost
            
            # Crear objeto de pérdida
            loss = Loss(
                product_id=product.id,
                quantity=quantity,
                unit_cost=unit_cost,
                total_cost=total_cost,
                loss_date=datetime.strptime(self.loss_date_var.get(), "%Y-%m-%d") if self.loss_date_var.get() else datetime.now(),
                reason=self.reason_var.get(),
                loss_type=self.form_loss_type_var.get(),
                notes=self.notes_var.get(),
                created_by=self.user.id
            )
            
            # Guardar pérdida
            if loss.save():
                messagebox.showinfo("Éxito", "Pérdida registrada correctamente")
                self.clear_form()
                self.load_data()
                # Recargar productos para actualizar stock
                self.load_products()
            else:
                messagebox.showerror("Error", "No se pudo registrar la pérdida")

            if not self.products or self.product_var.get() == "No hay productos":
                messagebox.showerror("Error", "No hay productos disponibles")
                return
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar pérdida: {str(e)}")
    
    def clear_form(self):
        """Limpia el formulario"""
        self.quantity_var.set("")
        self.unit_cost_var.set("")
        self.loss_date_var.set(datetime.now().strftime("%Y-%m-%d"))
        self.form_loss_type_var.set("Vencimiento")
        self.reason_var.set("")
        self.notes_var.set("")
        
        # Seleccionar primer producto y actualizar costo
        if self.products:
            self.product_combo.current(0)
            selected_product = self.products[self.product_combo.get()]
            self.unit_cost_var.set(str(selected_product.cost_price))
    
    def view_loss_details(self):
        """Muestra los detalles de una pérdida"""
        selected = self.losses_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Por favor seleccione una pérdida para ver detalles")
            return
        
        # Obtener ID de la pérdida seleccionada
        loss_id = self.losses_tree.item(selected[0], 'values')[0]
        
        # Obtener pérdida
        loss = Loss.get_by_id(loss_id)
        if not loss:
            messagebox.showerror("Error", "No se encontró la pérdida")
            return
        
        # Mostrar detalles en una ventana
        details_window = tk.Toplevel(self.window)
        details_window.title(f"Detalles de Pérdida #{loss.id}")
        details_window.geometry("500x400")
        details_window.resizable(False, False)
        
        # Centrar ventana
        details_window.update_idletasks()
        width = details_window.winfo_width()
        height = details_window.winfo_height()
        x = (details_window.winfo_screenwidth() // 2) - (width // 2)
        y = (details_window.winfo_screenheight() // 2) - (height // 2)
        details_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        # Frame principal
        main_frame = ttk.Frame(details_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        ttk.Label(main_frame, text=f"Detalles de Pérdida #{loss.id}", 
                 font=("Arial", 14, "bold")).pack(pady=(0, 20))
        
        # Detalles
        details_frame = ttk.Frame(main_frame)
        details_frame.pack(fill=tk.BOTH, expand=True)
        
        # Columna 1
        col1 = ttk.Frame(details_frame)
        col1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        ttk.Label(col1, text="Producto:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Label(col1, text=loss.product_name).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(col1, text="Cantidad:", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Label(col1, text=f"{loss.quantity:.2f}").grid(row=1, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(col1, text="Costo Unitario:", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Label(col1, text=f"${loss.unit_cost:.2f}").grid(row=2, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(col1, text="Costo Total:", font=("Arial", 10, "bold")).grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Label(col1, text=f"${loss.total_cost:.2f}").grid(row=3, column=1, sticky=tk.W, pady=5)
        
        # Columna 2
        col2 = ttk.Frame(details_frame)
        col2.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        ttk.Label(col2, text="Fecha:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Label(col2, text=loss.loss_date.strftime("%Y-%m-%d") if isinstance(loss.loss_date, datetime) else loss.loss_date).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(col2, text="Tipo:", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Label(col2, text=loss.loss_type).grid(row=1, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(col2, text="Registrado por:", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Label(col2, text=loss.user_name).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(col2, text="Fecha de registro:", font=("Arial", 10, "bold")).grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Label(col2, text=loss.created_at.strftime("%Y-%m-%d %H:%M") if isinstance(loss.created_at, datetime) else loss.created_at).grid(row=3, column=1, sticky=tk.W, pady=5)
        
        # Motivo y notas
        notes_frame = ttk.Frame(main_frame)
        notes_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(notes_frame, text="Motivo:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Label(notes_frame, text=loss.reason).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(notes_frame, text="Notas:", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky=tk.NW, pady=5)
        notes_text = tk.Text(notes_frame, height=4, width=40, wrap=tk.WORD)
        notes_text.grid(row=1, column=1, pady=5)
        notes_text.insert(tk.END, loss.notes if loss.notes else "")
        notes_text.config(state=tk.DISABLED)
        
        # Botón de cerrar
        ttk.Button(main_frame, text="Cerrar", command=details_window.destroy).pack(pady=10)
    
    def delete_loss(self):
        """Elimina una pérdida seleccionada"""
        selected = self.losses_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Por favor seleccione una pérdida para eliminar")
            return
        
        # Obtener ID de la pérdida seleccionada
        loss_id = self.losses_tree.item(selected[0], 'values')[0]
        
        # Verificar que el ID no sea "No hay datos"
        if loss_id == "No hay datos":
            messagebox.showwarning("Advertencia", "No hay pérdidas para eliminar")
            return
        
        # Confirmar eliminación
        if not messagebox.askyesno("Confirmar", "¿Está seguro de eliminar esta pérdida?\nEsta acción restaurará el stock del producto."):
            return
        
        try:
            # Obtener la pérdida
            loss = Loss.get_by_id(loss_id)
            
            if loss is None:
                messagebox.showerror("Error", "No se encontró la pérdida seleccionada")
                return
            
            # Verificar que sea una instancia válida de Loss
            if not hasattr(loss, 'delete'):
                messagebox.showerror("Error", "Error interno: objeto Loss inválido")
                print(f"Tipo de objeto recuperado: {type(loss)}")
                print(f"Atributos del objeto: {dir(loss)}")
                return
            print(f"Tipo de loss: {type(loss)}")
            print(f"Es instancia de Loss: {isinstance(loss, Loss)}")
            print(f"Tiene método delete: {hasattr(loss, 'delete')}")
            # Intentar eliminar la pérdida
            if loss.delete():
                messagebox.showinfo("Éxito", "Pérdida eliminada correctamente")
                self.load_data()  # Recargar datos
                self.load_products()  # Actualizar lista de productos
            else:
                messagebox.showerror("Error", "No se pudo eliminar la pérdida")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al eliminar pérdida: {str(e)}")
            print(f"Error detallado: {e}")
            import traceback
            traceback.print_exc()