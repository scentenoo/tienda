import tkinter as tk
from tkinter import ttk, messagebox
from models.expense import Expense
from utils.validators import validate_required, validate_positive
from datetime import datetime

class ExpensesWindow:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        
        # Crear ventana
        self.window = tk.Toplevel(parent)
        self.window.title("Gastos Operativos")
        self.window.geometry("800x600")
        self.window.resizable(True, True)
        
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
        notebook.add(self.new_expense_frame, text="Nuevo Gasto")
        self.setup_new_expense_ui()
        
        # Pestaña lista de gastos
        self.expenses_list_frame = ttk.Frame(notebook)
        notebook.add(self.expenses_list_frame, text="Lista de Gastos")
        self.setup_expenses_list_ui()
    
    def setup_new_expense_ui(self):
        """Configura la UI para nuevo gasto"""
        main_frame = ttk.Frame(self.new_expense_frame, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Título
        title_label = ttk.Label(main_frame, text="Registrar Nuevo Gasto Operativo", 
                               font=("Arial", 14, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 30))
        
        # Descripción
        ttk.Label(main_frame, text="Descripción:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.description_var = tk.StringVar()
        description_entry = ttk.Entry(main_frame, textvariable=self.description_var, width=40)
        description_entry.grid(row=1, column=1, pady=5, padx=(10, 0), sticky=(tk.W, tk.E))
        
        # Monto
        ttk.Label(main_frame, text="Monto:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.amount_var = tk.StringVar()
        amount_entry = ttk.Entry(main_frame, textvariable=self.amount_var, width=20)
        amount_entry.grid(row=2, column=1, pady=5, padx=(10, 0), sticky=tk.W)
        
        # Fecha (opcional, por defecto hoy)
        ttk.Label(main_frame, text="Fecha (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.date_var = tk.StringVar()
        self.date_var.set(datetime.now().strftime("%Y-%m-%d"))
        date_entry = ttk.Entry(main_frame, textvariable=self.date_var, width=20)
        date_entry.grid(row=3, column=1, pady=5, padx=(10, 0), sticky=tk.W)
        
        # Botones
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=30)
        
        ttk.Button(button_frame, text="Guardar Gasto", 
                  command=self.save_expense).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Limpiar", 
                  command=self.clear_form).pack(side=tk.LEFT, padx=10)
        
        # Configurar grid weights
        main_frame.columnconfigure(1, weight=1)
        
        # Focus en descripción
        description_entry.focus()
    
    def setup_expenses_list_ui(self):
        """Configura la UI para lista de gastos"""
        main_frame = ttk.Frame(self.expenses_list_frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, text="Lista de Gastos Operativos", 
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Frame para controles
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Filtros por fecha
        ttk.Label(controls_frame, text="Desde:").pack(side=tk.LEFT, padx=(0, 5))
        self.date_from_var = tk.StringVar()
        date_from_entry = ttk.Entry(controls_frame, textvariable=self.date_from_var, width=12)
        date_from_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(controls_frame, text="Hasta:").pack(side=tk.LEFT, padx=(0, 5))
        self.date_to_var = tk.StringVar()
        date_to_entry = ttk.Entry(controls_frame, textvariable=self.date_to_var, width=12)
        date_to_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(controls_frame, text="Filtrar", 
                  command=self.filter_expenses).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Actualizar", 
                  command=self.load_data).pack(side=tk.LEFT, padx=5)
        
        # Treeview para mostrar gastos
        columns = ('ID', 'Descripción', 'Monto', 'Fecha')
        self.expenses_tree = ttk.Treeview(main_frame, columns=columns, show='headings')
        
        # Configurar columnas
        for col in columns:
            self.expenses_tree.heading(col, text=col)
            if col == 'ID':
                self.expenses_tree.column(col, width=50)
            elif col == 'Monto':
                self.expenses_tree.column(col, width=100)
            elif col == 'Fecha':
                self.expenses_tree.column(col, width=120)
            else:
                self.expenses_tree.column(col, width=300)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.expenses_tree.yview)
        h_scrollbar = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=self.expenses_tree.xview)
        self.expenses_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Frame para el treeview
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.expenses_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Bind para selección
        self.expenses_tree.bind('<<TreeviewSelect>>', self.on_expense_select)
        
        # Frame para botones de acción
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(action_frame, text="Editar", 
                  command=self.edit_expense).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Eliminar", 
                  command=self.delete_expense).pack(side=tk.LEFT, padx=5)
        
        # Etiqueta para total
        self.total_label = ttk.Label(action_frame, text="Total: $0.00", 
                                    font=("Arial", 12, "bold"))
        self.total_label.pack(side=tk.RIGHT)
    
    def load_data(self):
        """Carga los datos de gastos"""
        self.expenses = Expense.get_all()
        self.update_expenses_tree()
    
    def update_expenses_tree(self):
        """Actualiza el árbol de gastos"""
        # Limpiar árbol
        for item in self.expenses_tree.get_children():
            self.expenses_tree.delete(item)
        
        total = 0
        
        # Agregar gastos
        for expense in self.expenses:
            # Formatear fecha
            date_str = expense.date.strftime("%Y-%m-%d %H:%M") if expense.date else "N/A"
            
            # Insertar en árbol
            self.expenses_tree.insert('', tk.END, values=(
                expense.id,
                expense.description,
                f"${expense.amount:.2f}",
                date_str
            ))
            
            total += expense.amount
        
        # Actualizar total
        self.total_label.config(text=f"Total: ${total:.2f}")
    
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
        """Guarda el gasto"""
        # Validaciones
        description = self.description_var.get().strip()
        if not validate_required(description):
            messagebox.showerror("Error", "La descripción no puede estar vacía")
            return
        
        try:
            amount = float(self.amount_var.get())
            if not validate_positive(amount):
                messagebox.showerror("Error", "El monto debe ser mayor a 0")
                return
        except ValueError:
            messagebox.showerror("Error", "El monto debe ser un número válido")
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
            messagebox.showinfo("Éxito", "Gasto guardado correctamente")
            self.clear_form()
            self.load_data()
        else:
            messagebox.showerror("Error", "No se pudo guardar el gasto")
    
    def clear_form(self):
        """Limpia el formulario"""
        self.description_var.set("")
        self.amount_var.set("")
        self.date_var.set(datetime.now().strftime("%Y-%m-%d"))
    
    def edit_expense(self):
        """Edita el gasto seleccionado"""
        if not self.selected_expense:
            messagebox.showwarning("Advertencia", "Seleccione un gasto para editar")
            return
        
        self.expense_dialog(self.selected_expense)
    
    def expense_dialog(self, expense):
        """Diálogo para editar gasto"""
        dialog = tk.Toplevel(self.window)
        dialog.title("Editar Gasto")
        dialog.geometry("400x200")
        dialog.resizable(False, False)
        dialog.transient(self.window)
        dialog.grab_set()
        
        # Centrar diálogo
        dialog.update_idletasks()
        x = dialog.winfo_reqwidth()
        y = dialog.winfo_reqheight()
        pos_x = (dialog.winfo_screenwidth() // 2) - (x // 2)
        pos_y = (dialog.winfo_screenheight() // 2) - (y // 2)
        dialog.geometry(f"{x}x{y}+{pos_x}+{pos_y}")
        
        # Contenido del diálogo
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Descripción
        ttk.Label(main_frame, text="Descripción:").grid(row=0, column=0, sticky=tk.W, pady=5)
        description_var = tk.StringVar(value=expense.description)
        description_entry = ttk.Entry(main_frame, textvariable=description_var, width=30)
        description_entry.grid(row=0, column=1, pady=5)
        
        # Monto
        ttk.Label(main_frame, text="Monto:").grid(row=1, column=0, sticky=tk.W, pady=5)
        amount_var = tk.StringVar(value=str(expense.amount))
        amount_entry = ttk.Entry(main_frame, textvariable=amount_var, width=30)
        amount_entry.grid(row=1, column=1, pady=5)
        
        # Fecha
        ttk.Label(main_frame, text="Fecha:").grid(row=2, column=0, sticky=tk.W, pady=5)
        date_var = tk.StringVar(value=expense.date.strftime("%Y-%m-%d") if expense.date else "")
        date_entry = ttk.Entry(main_frame, textvariable=date_var, width=30)
        date_entry.grid(row=2, column=1, pady=5)
        
        def save_changes():
            # Validaciones
            description = description_var.get().strip()
            if not validate_required(description):
                messagebox.showerror("Error", "La descripción no puede estar vacía")
                return
            
            try:
                amount = float(amount_var.get())
                if not validate_positive(amount):
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
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Guardar", command=save_changes).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        description_entry.focus()
        dialog.bind('<Return>', lambda e: save_changes())
    
    def delete_expense(self):
        """Elimina el gasto seleccionado"""
        if not self.selected_expense:
            messagebox.showwarning("Advertencia", "Seleccione un gasto para eliminar")
            return
        
        if messagebox.askyesno("Confirmar", 
            f"¿Está seguro de eliminar el gasto '{self.selected_expense.description}'?"):
            
            self.selected_expense.delete()
            self.load_data()
            self.selected_expense = None
            messagebox.showinfo("Éxito", "Gasto eliminado correctamente")
    
    def filter_expenses(self):
        """Filtra los gastos por fecha"""
        # TODO: Implementar filtrado por rango de fechas
        messagebox.showinfo("Info", "Filtrado por fecha en desarrollo")