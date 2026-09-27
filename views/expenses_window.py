import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from models.expense import Expense
from utils.validators import validate_required, validate_positive, safe_float_conversion
from utils.formatters import format_currency, format_number
from utils.theme import FONT_TITLE, FONT_HEADER, FONT_BOLD, FONT_NORMAL, FONT_SMALL, role_color
from datetime import datetime
from utils.ventanas import hacer_modal, centrar_ventana

class ExpensesWindow:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        
        # Crear ventana
        self.window = tk.Toplevel(parent)
        self.window.title("Gastos Operativos")
        self.window.resizable(True, True)
        centrar_ventana(self.window, 900, 700)
        self.window.minsize(800, 550)

        # Variables
        self.expenses = []
        self.selected_expense = None
        
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Notebook para pestañas
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Pestaña nuevo gasto
        self.new_expense_frame = ttk.Frame(notebook)
        notebook.add(self.new_expense_frame, text="  💰 Nuevo Gasto  ")
        self.setup_new_expense_ui()
        
        # Pestaña lista de gastos
        self.expenses_list_frame = ttk.Frame(notebook)
        notebook.add(self.expenses_list_frame, text="  📊 Lista de Gastos  ")
        self.setup_expenses_list_ui()
    
    def setup_new_expense_ui(self):
        """Configura la UI para nuevo gasto"""
        # Frame principal centrado
        container = ttk.Frame(self.new_expense_frame)
        container.pack(expand=True, fill=tk.BOTH)
        
        main_frame = ttk.Frame(container, padding="30")
        main_frame.pack(expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, text="💰 Registrar Nuevo Gasto Operativo",
                               font=FONT_TITLE)
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 30))
        
        # Descripción
        ttk.Label(main_frame, text="Descripción:", font=FONT_BOLD).grid(
            row=1, column=0, sticky=tk.W, pady=(10, 5))
        self.description_var = tk.StringVar()
        description_entry = ttk.Entry(main_frame, textvariable=self.description_var,
                                    width=50, font=FONT_NORMAL)
        description_entry.grid(row=2, column=0, columnspan=2, pady=(0, 15), sticky=(tk.W, tk.E))

        # Monto
        ttk.Label(main_frame, text="Monto:", font=FONT_BOLD).grid(
            row=3, column=0, sticky=tk.W, pady=(10, 5))

        # Frame para monto con formato en tiempo real
        amount_frame = ttk.Frame(main_frame)
        amount_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))

        ttk.Label(amount_frame, text="$", font=FONT_BOLD).pack(side=tk.LEFT)

        self.amount_var = tk.StringVar()
        self.amount_entry = ttk.Entry(amount_frame, textvariable=self.amount_var,
                                    width=20, font=FONT_BOLD, justify=tk.RIGHT)
        self.amount_entry.pack(side=tk.LEFT, padx=(5, 10))

        # Etiqueta para mostrar el monto formateado
        self.formatted_amount_label = ttk.Label(amount_frame, text="",
                                              font=FONT_NORMAL, bootstyle="secondary")
        self.formatted_amount_label.pack(side=tk.LEFT)

        # Bind para formato en tiempo real
        self.amount_var.trace_add('write', self.on_amount_change)

        # Fecha (opcional, por defecto hoy)
        ttk.Label(main_frame, text="Fecha (YYYY-MM-DD):", font=FONT_BOLD).grid(
            row=5, column=0, sticky=tk.W, pady=(10, 5))
        self.date_var = tk.StringVar()
        self.date_var.set(datetime.now().strftime("%Y-%m-%d"))
        date_entry = ttk.Entry(main_frame, textvariable=self.date_var,
                             width=20, font=FONT_NORMAL)
        date_entry.grid(row=6, column=0, sticky=tk.W, pady=(0, 30))

        # Botones con estilo mejorado
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)

        save_btn = ttk.Button(button_frame, text="💾 Guardar Gasto",
                            command=self.save_expense, bootstyle="primary")
        save_btn.pack(side=tk.LEFT, padx=10)

        clear_btn = ttk.Button(button_frame, text="🧹 Limpiar",
                             command=self.clear_form, bootstyle="secondary")
        clear_btn.pack(side=tk.LEFT, padx=10)
        
        # Configurar grid weights
        main_frame.columnconfigure(0, weight=1)
        
        # Focus en descripción
        description_entry.focus()
    
    def on_amount_change(self, *args):
        """Actualiza el formato del monto en tiempo real"""
        try:
            amount_str = self.amount_var.get().replace(',', '').replace('$', '').strip()
            if amount_str:
                amount = safe_float_conversion(amount_str)
                if amount > 0:
                    formatted = format_currency(amount)
                    self.formatted_amount_label.config(text=f"({formatted})")
                else:
                    self.formatted_amount_label.config(text="")
            else:
                self.formatted_amount_label.config(text="")
        except:
            self.formatted_amount_label.config(text="")
    
    def setup_expenses_list_ui(self):
        """Configura la UI para lista de gastos"""
        main_frame = ttk.Frame(self.expenses_list_frame, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, text="📊 Lista de Gastos Operativos",
                               font=FONT_TITLE)
        title_label.pack(pady=(0, 15))
        
        # Frame para controles
        controls_frame = ttk.LabelFrame(main_frame, text=" Filtros y Controles ", padding="10")
        controls_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Filtros por fecha
        filter_frame = ttk.Frame(controls_frame)
        filter_frame.pack(fill=tk.X)
        
        ttk.Label(filter_frame, text="📅 Desde:", font=FONT_BOLD).pack(side=tk.LEFT, padx=(0, 5))
        self.date_from_var = tk.StringVar()
        date_from_entry = ttk.Entry(filter_frame, textvariable=self.date_from_var, width=12)
        date_from_entry.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(filter_frame, text="📅 Hasta:", font=FONT_BOLD).pack(side=tk.LEFT, padx=(0, 5))
        self.date_to_var = tk.StringVar()
        date_to_entry = ttk.Entry(filter_frame, textvariable=self.date_to_var, width=12)
        date_to_entry.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Button(filter_frame, text="🔍 Filtrar",
                  command=self.filter_expenses, bootstyle="primary").pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="🔄 Actualizar",
                  command=self.load_data, bootstyle="secondary-outline").pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="📋 Exportar",
                  command=self.export_expenses, bootstyle="info").pack(side=tk.LEFT, padx=5)

        # Frame para estadísticas rápidas
        stats_frame = ttk.Frame(main_frame)
        stats_frame.pack(fill=tk.X, pady=(0, 10))

        self.total_label = ttk.Label(stats_frame, text="💰 Total: $0.00",
                                   font=FONT_HEADER, bootstyle="primary")
        self.total_label.pack(side=tk.RIGHT)

        self.count_label = ttk.Label(stats_frame, text="📝 Gastos: 0",
                                   font=FONT_BOLD)
        self.count_label.pack(side=tk.LEFT)
        
        # Frame para botones de acción (empaquetado ANTES que la tabla, con
        # side=BOTTOM, para que no se lo coma el expand=True del árbol)
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(15, 0))

        ttk.Button(action_frame, text="✏️ Editar",
                  command=self.edit_expense, bootstyle="info").pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="🗑️ Eliminar",
                  command=self.delete_expense, bootstyle="danger").pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="📊 Detalles",
                  command=self.view_expense_details, bootstyle="secondary-outline").pack(side=tk.LEFT, padx=5)

        # Treeview para mostrar gastos con mejor formato
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        columns = ('ID', 'Descripción', 'Monto', 'Fecha', 'Usuario')
        self.expenses_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        # Configurar columnas con mejor espaciado
        self.expenses_tree.heading('ID', text='ID')
        self.expenses_tree.column('ID', width=60, minwidth=50, anchor='center')

        self.expenses_tree.heading('Descripción', text='📝 Descripción')
        self.expenses_tree.column('Descripción', width=300, minwidth=180, anchor='w')

        self.expenses_tree.heading('Monto', text='💰 Monto')
        self.expenses_tree.column('Monto', width=150, minwidth=110, anchor='e')

        self.expenses_tree.heading('Fecha', text='📅 Fecha')
        self.expenses_tree.column('Fecha', width=140, minwidth=110, anchor='center')

        self.expenses_tree.heading('Usuario', text='👤 Usuario')
        self.expenses_tree.column('Usuario', width=120, minwidth=90, anchor='center')

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.expenses_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.expenses_tree.xview)
        self.expenses_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        self.expenses_tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        # Bind para selección
        self.expenses_tree.bind('<<TreeviewSelect>>', self.on_expense_select)

    def load_data(self):
        """Carga los datos de gastos"""
        try:
            self.expenses = Expense.get_all()
            self.update_expenses_tree()
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar gastos: {str(e)}")
    
    def update_expenses_tree(self):
        """Actualiza el árbol de gastos con formato mejorado"""
        # Limpiar árbol
        for item in self.expenses_tree.get_children():
            self.expenses_tree.delete(item)
        
        total = 0
        count = 0
        
        # Agregar gastos
        for expense in self.expenses:
            try:
                # Formatear fecha
                if hasattr(expense, 'date') and expense.date:
                    if isinstance(expense.date, str):
                        date_str = expense.date
                    else:
                        date_str = expense.date.strftime("%Y-%m-%d %H:%M")
                else:
                    date_str = "N/A"
                
                # Formatear monto con separadores de miles
                amount_formatted = format_currency(expense.amount)
                
                # Obtener nombre de usuario si está disponible
                user_name = getattr(expense, 'user_name', 'N/A')
                
                # Insertar en árbol con colores alternos
                item_id = self.expenses_tree.insert('', tk.END, values=(
                    expense.id,
                    expense.description,
                    amount_formatted,
                    date_str,
                    user_name
                ), tags=('evenrow' if count % 2 == 0 else 'oddrow',))
                
                total += expense.amount
                count += 1
                
            except Exception as e:
                print(f"Error procesando gasto {expense.id}: {e}")
                continue
        
        # Configurar colores alternos
        self.expenses_tree.tag_configure('evenrow', background=role_color('light'))
        self.expenses_tree.tag_configure('oddrow', background=role_color('bg'))
        
        # Actualizar estadísticas
        self.total_label.config(text=f"💰 Total: {format_currency(total)}")
        self.count_label.config(text=f"📝 Gastos: {count:,}")
    
    def on_expense_select(self, event=None):
        """Maneja la selección de un gasto"""
        selection = self.expenses_tree.selection()
        if not selection:
            self.selected_expense = None
            return
        
        # Obtener ID del gasto seleccionado
        item = self.expenses_tree.item(selection[0])
        expense_id = item['values'][0]
        
        # Buscar gasto en la lista
        for expense in self.expenses:
            if expense.id == expense_id:
                self.selected_expense = expense
                break
    
    def save_expense(self):
        """Guarda el gasto con validaciones mejoradas"""
        # Validaciones
        description = self.description_var.get().strip()
        if not validate_required(description):
            messagebox.showerror("Error", "La descripción no puede estar vacía")
            self.description_var.focus()
            return
        
        try:
            amount_str = self.amount_var.get().replace(',', '').replace('$', '').strip()
            amount = safe_float_conversion(amount_str)
            if not validate_positive(amount, "Monto"):
                messagebox.showerror("Error", "El monto debe ser mayor a 0")
                self.amount_entry.focus()
                return
        except ValueError:
            messagebox.showerror("Error", "El monto debe ser un número válido")
            self.amount_entry.focus()
            return
        
        # Validar fecha
        try:
            date_str = self.date_var.get().strip()
            if date_str:
                expense_date = datetime.strptime(date_str, "%Y-%m-%d")
            else:
                expense_date = datetime.now()
        except ValueError:
            messagebox.showerror("Error", "Formato de fecha inválido. Use YYYY-MM-DD")
            return
        
        # Crear gasto
        expense = Expense(
            description=description,
            amount=amount,
            date=expense_date,
            user_id=self.user.id
        )
        
        if expense.save():
            messagebox.showinfo("Éxito", 
                f"Gasto guardado correctamente:\n{description}\n{format_currency(amount)}")
            self.clear_form()
            self.load_data()
        else:
            messagebox.showerror("Error", "No se pudo guardar el gasto")
    
    def clear_form(self):
        """Limpia el formulario"""
        self.description_var.set("")
        self.amount_var.set("")
        self.date_var.set(datetime.now().strftime("%Y-%m-%d"))
        self.formatted_amount_label.config(text="")
    
    def edit_expense(self):
        """Edita el gasto seleccionado"""
        if not self.selected_expense:
            messagebox.showwarning("Advertencia", "Seleccione un gasto para editar")
            return
        
        self.expense_dialog(self.selected_expense)
    
    def expense_dialog(self, expense):
        """Diálogo para editar gasto con formato mejorado"""
        dialog = tk.Toplevel(self.window)
        dialog.title(f"✏️ Editar Gasto #{expense.id}")
        dialog.resizable(False, False)
        dialog.transient(self.window)
        hacer_modal(dialog)
        centrar_ventana(dialog, 500, 350)

        # Contenido del diálogo
        main_frame = ttk.Frame(dialog, padding="25")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, text=f"Editando Gasto #{expense.id}",
                               font=FONT_HEADER)
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # Descripción
        ttk.Label(main_frame, text="Descripción:", font=FONT_BOLD).grid(
            row=1, column=0, sticky=tk.W, pady=5)
        description_var = tk.StringVar(value=expense.description)
        description_entry = ttk.Entry(main_frame, textvariable=description_var, width=40)
        description_entry.grid(row=1, column=1, pady=5, sticky=(tk.W, tk.E))

        # Monto con formato
        ttk.Label(main_frame, text="Monto:", font=FONT_BOLD).grid(
            row=2, column=0, sticky=tk.W, pady=5)

        amount_frame = ttk.Frame(main_frame)
        amount_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(amount_frame, text="$", font=FONT_BOLD).pack(side=tk.LEFT)
        amount_var = tk.StringVar(value=str(expense.amount))
        amount_entry = ttk.Entry(amount_frame, textvariable=amount_var, width=15, justify=tk.RIGHT)
        amount_entry.pack(side=tk.LEFT, padx=(5, 10))

        # Etiqueta para mostrar formato
        amount_format_label = ttk.Label(amount_frame, text="", font=FONT_SMALL, bootstyle="secondary")
        amount_format_label.pack(side=tk.LEFT)
        
        def update_amount_format(*args):
            try:
                amount_str = amount_var.get().replace(',', '').replace('$', '').strip()
                if amount_str:
                    amount = safe_float_conversion(amount_str)
                    if amount > 0:
                        amount_format_label.config(text=f"({format_currency(amount)})")
                    else:
                        amount_format_label.config(text="")
                else:
                    amount_format_label.config(text="")
            except:
                amount_format_label.config(text="")
        
        amount_var.trace_add('write', update_amount_format)
        update_amount_format()  # Inicial
        
        # Fecha
        ttk.Label(main_frame, text="Fecha:", font=FONT_BOLD).grid(
            row=3, column=0, sticky=tk.W, pady=5)
        date_var = tk.StringVar(value=expense.date.strftime("%Y-%m-%d") if expense.date else "")
        date_entry = ttk.Entry(main_frame, textvariable=date_var, width=20)
        date_entry.grid(row=3, column=1, pady=5, sticky=tk.W)
        
        def save_changes():
            # Validaciones
            description = description_var.get().strip()
            if not validate_required(description):
                messagebox.showerror("Error", "La descripción no puede estar vacía")
                return
            
            try:
                amount_str = amount_var.get().replace(',', '').replace('$', '').strip()
                amount = safe_float_conversion(amount_str)
                if not validate_positive(amount, "Monto"):
                    messagebox.showerror("Error", "El monto debe ser mayor a 0")
                    return
            except ValueError:
                messagebox.showerror("Error", "El monto debe ser un número válido")
                return
            
            try:
                date_str = date_var.get().strip()
                expense_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()
            except ValueError:
                messagebox.showerror("Error", "Formato de fecha inválido. Use YYYY-MM-DD")
                return
            
            # Actualizar gasto
            expense.description = description
            expense.amount = amount
            expense.date = expense_date
            
            if expense.save():
                self.load_data()
                messagebox.showinfo("Éxito", "Gasto actualizado correctamente")
                dialog.destroy()
            else:
                messagebox.showerror("Error", "No se pudo actualizar el gasto")
        
        # Botones
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=30)
        
        ttk.Button(button_frame, text="💾 Guardar", command=save_changes, bootstyle="primary").pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="❌ Cancelar", command=dialog.destroy, bootstyle="secondary").pack(side=tk.LEFT, padx=10)
        
        # Configurar grid
        main_frame.columnconfigure(1, weight=1)
        
        description_entry.focus()
        dialog.bind('<Return>', lambda e: save_changes())
    
    def delete_expense(self):
        """Elimina el gasto seleccionado"""
        if not self.selected_expense:
            messagebox.showwarning("Advertencia", "Seleccione un gasto para eliminar")
            return
        
        formatted_amount = format_currency(self.selected_expense.amount)
        
        if messagebox.askyesno("Confirmar Eliminación", 
            f"¿Está seguro de eliminar este gasto?\n\n"
            f"📝 Descripción: {self.selected_expense.description}\n"
            f"💰 Monto: {formatted_amount}\n\n"
            f"Esta acción no se puede deshacer."):
            
            if self.selected_expense.delete():
                self.load_data()
                self.selected_expense = None
                messagebox.showinfo("Éxito", "Gasto eliminado correctamente")
            else:
                messagebox.showerror("Error", "No se pudo eliminar el gasto")
    
    def view_expense_details(self):
        """Muestra detalles completos del gasto"""
        if not self.selected_expense:
            messagebox.showwarning("Advertencia", "Seleccione un gasto para ver detalles")
            return
        
        # Crear ventana de detalles
        details = tk.Toplevel(self.window)
        details.title(f"📊 Detalles del Gasto #{self.selected_expense.id}")
        details.resizable(False, False)
        details.transient(self.window)
        hacer_modal(details)
        centrar_ventana(details, 400, 300)
        
        # Contenido
        frame = ttk.Frame(details, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Información del gasto
        info_text = f"""
📝 ID: {self.selected_expense.id}

📝 Descripción: {self.selected_expense.description}

💰 Monto: {format_currency(self.selected_expense.amount)}

📅 Fecha: {self.selected_expense.date.strftime("%Y-%m-%d %H:%M:%S") if self.selected_expense.date else 'N/A'}

👤 Usuario: {getattr(self.selected_expense, 'user_name', 'N/A')}
        """
        
        ttk.Label(frame, text=info_text, font=FONT_NORMAL, justify=tk.LEFT).pack()

        ttk.Button(frame, text="Cerrar", command=details.destroy, bootstyle="secondary").pack(pady=20)
    
    def filter_expenses(self):
        """Filtra los gastos por fecha"""
        date_from = self.date_from_var.get().strip()
        date_to = self.date_to_var.get().strip()
        
        if not date_from and not date_to:
            messagebox.showinfo("Info", "Ingrese al menos una fecha para filtrar")
            return
        
        try:
            filtered_expenses = []
            
            for expense in Expense.get_all():
                expense_date = expense.date
                if isinstance(expense_date, str):
                    expense_date = datetime.strptime(expense_date.split()[0], "%Y-%m-%d")
                
                include = True
                
                if date_from:
                    from_date = datetime.strptime(date_from, "%Y-%m-%d")
                    if expense_date < from_date:
                        include = False
                
                if date_to and include:
                    to_date = datetime.strptime(date_to, "%Y-%m-%d")
                    if expense_date > to_date:
                        include = False
                
                if include:
                    filtered_expenses.append(expense)
            
            self.expenses = filtered_expenses
            self.update_expenses_tree()
            
            messagebox.showinfo("Filtro Aplicado", 
                f"Se encontraron {len(filtered_expenses)} gastos en el rango seleccionado")
            
        except ValueError:
            messagebox.showerror("Error", "Formato de fecha inválido. Use YYYY-MM-DD")
        except Exception as e:
            messagebox.showerror("Error", f"Error al filtrar: {str(e)}")
    
    def export_expenses(self):
        """Exporta la lista de gastos (función placeholder)"""
        messagebox.showinfo("Exportar", "Función de exportación en desarrollo\n\n"
                           f"Se exportarían {len(self.expenses)} gastos")