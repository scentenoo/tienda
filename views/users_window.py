import tkinter as tk
from tkinter import ttk, messagebox
from models.user import User
from utils.security import hash_password

class UsersWindow:
    def __init__(self, parent, user):
        self.parent = parent
        self.user = user
        
        # Verificar si el usuario es administrador
        if self.user.role != 'admin':
            messagebox.showerror("Acceso Denegado", "Solo los administradores pueden acceder a esta sección")
            return
        
        # Crear ventana
        self.window = tk.Toplevel(parent)
        self.window.title("Gestión de Usuarios")
        self.window.geometry("1300x500")
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
        title_label = ttk.Label(main_frame, text="Gestión de Usuarios", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Frame para formulario y lista
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Frame para formulario
        form_frame = ttk.LabelFrame(content_frame, text="Nuevo Usuario", padding="10")
        form_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # Campos del formulario
        ttk.Label(form_frame, text="Nombre Completo:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.name_var, width=25).grid(row=0, column=1, pady=5, padx=5)
        
        ttk.Label(form_frame, text="Usuario:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.username_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.username_var, width=25).grid(row=1, column=1, pady=5, padx=5)
        
        ttk.Label(form_frame, text="Contraseña:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.password_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.password_var, width=25, show="*").grid(row=2, column=1, pady=5, padx=5)
        
        ttk.Label(form_frame, text="Rol:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.role_var = tk.StringVar(value="employee")
        role_combo = ttk.Combobox(form_frame, textvariable=self.role_var, width=15, state="readonly")
        role_combo['values'] = ["admin", "employee"]
        role_combo.grid(row=3, column=1, pady=5, padx=5, sticky=tk.W)
        
        ttk.Label(form_frame, text="Puesto:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.position_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.position_var, width=25).grid(row=4, column=1, pady=5, padx=5)
        
        # Botones
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="Guardar", command=self.save_user).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Limpiar", command=self.clear_form).pack(side=tk.LEFT, padx=5)
        
        # Frame para lista de usuarios
        list_frame = ttk.LabelFrame(content_frame, text="Usuarios Registrados", padding="10")
        list_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Treeview para mostrar usuarios
        columns = ('ID', 'Nombre', 'Usuario', 'Rol', 'Puesto')
        self.users_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        # Configurar columnas
        self.users_tree.heading('ID', text='ID')
        self.users_tree.heading('Nombre', text='Nombre')
        self.users_tree.heading('Usuario', text='Usuario')
        self.users_tree.heading('Rol', text='Rol')
        self.users_tree.heading('Puesto', text='Puesto')
        
        self.users_tree.column('ID', width=50, anchor=tk.CENTER)
        self.users_tree.column('Nombre', width=150)
        self.users_tree.column('Usuario', width=100)
        self.users_tree.column('Rol', width=100, anchor=tk.CENTER)
        self.users_tree.column('Puesto', width=150)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.users_tree.yview)
        self.users_tree.configure(yscroll=scrollbar.set)
        
        # Empaquetar treeview y scrollbar
        self.users_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Botones para editar y eliminar
        action_frame = ttk.Frame(list_frame)
        action_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(action_frame, text="Editar", command=self.edit_user).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Eliminar", command=self.delete_user).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Actualizar", command=self.load_data).pack(side=tk.RIGHT, padx=5)
    
    def load_data(self):
        """Carga los usuarios en el treeview"""
        # Limpiar treeview
        for item in self.users_tree.get_children():
            self.users_tree.delete(item)
        
        # Obtener usuarios
        users = User.get_all()
        
        # Insertar en treeview
        for user in users:
            self.users_tree.insert('', tk.END, values=(
                user.id,
                user.name,
                user.username,
                user.role,
                user.position if hasattr(user, 'position') else "N/A"
            ))
    
    def save_user(self):
        """Guarda un nuevo usuario"""
        # Obtener datos del formulario
        name = self.name_var.get().strip()
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        role = self.role_var.get()
        position = self.position_var.get().strip()
        
        # Validar campos
        if not name or not username or not password:
            messagebox.showerror("Error", "Por favor complete todos los campos obligatorios")
            return
        
        try:
            # Verificar si el usuario ya existe
            if User.get_by_username(username):
                messagebox.showerror("Error", f"El usuario '{username}' ya existe")
                return
            
            # Crear usuario
            user = User(
                name=name,
                username=username,
                password=hash_password(password),
                role=role,
                position=position
            )
            
            # Guardar usuario
            if user.save():
                messagebox.showinfo("Éxito", f"Usuario '{username}' creado correctamente")
                self.clear_form()
                self.load_data()
            else:
                messagebox.showerror("Error", "No se pudo guardar el usuario")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar usuario: {str(e)}")
    
    def clear_form(self):
        """Limpia el formulario"""
        self.name_var.set("")
        self.username_var.set("")
        self.password_var.set("")
        self.role_var.set("employee")
        self.position_var.set("")
    
    def edit_user(self):
        """Edita un usuario existente"""
        # Obtener selección
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Por favor seleccione un usuario para editar")
            return
        
        # Obtener datos del usuario seleccionado
        user_id = self.users_tree.item(selected[0], 'values')[0]
        
        # Abrir ventana de edición
        edit_window = tk.Toplevel(self.window)
        edit_window.title("Editar Usuario")
        edit_window.geometry("400x300")
        edit_window.resizable(False, False)
        
        # Centrar ventana
        edit_window.update_idletasks()
        width = edit_window.winfo_width()
        height = edit_window.winfo_height()
        x = (edit_window.winfo_screenwidth() // 2) - (width // 2)
        y = (edit_window.winfo_screenheight() // 2) - (height // 2)
        edit_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        # Obtener usuario
        user = User.get_by_id(user_id)
        if not user:
            messagebox.showerror("Error", "No se encontró el usuario")
            edit_window.destroy()
            return
        
        # Frame principal
        main_frame = ttk.Frame(edit_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Campos del formulario
        ttk.Label(main_frame, text="Nombre Completo:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar(value=user.name)
        ttk.Entry(main_frame, textvariable=name_var, width=25).grid(row=0, column=1, pady=5, padx=5)
        
        ttk.Label(main_frame, text="Usuario:").grid(row=1, column=0, sticky=tk.W, pady=5)
        username_var = tk.StringVar(value=user.username)
        ttk.Entry(main_frame, textvariable=username_var, width=25, state="readonly").grid(row=1, column=1, pady=5, padx=5)
        
        ttk.Label(main_frame, text="Nueva Contraseña:").grid(row=2, column=0, sticky=tk.W, pady=5)
        password_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=password_var, width=25, show="*").grid(row=2, column=1, pady=5, padx=5)
        
        ttk.Label(main_frame, text="Rol:").grid(row=3, column=0, sticky=tk.W, pady=5)
        role_var = tk.StringVar(value=user.role)
        role_combo = ttk.Combobox(main_frame, textvariable=role_var, width=15, state="readonly")
        role_combo['values'] = ["admin", "employee"]
        role_combo.grid(row=3, column=1, pady=5, padx=5, sticky=tk.W)
        
        ttk.Label(main_frame, text="Puesto:").grid(row=4, column=0, sticky=tk.W, pady=5)
        position_var = tk.StringVar(value=user.position if hasattr(user, 'position') else "")
        ttk.Entry(main_frame, textvariable=position_var, width=25).grid(row=4, column=1, pady=5, padx=5)
        
        # Botones
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="Guardar", command=lambda: self.save_edited_user(
            edit_window, user, name_var.get(), password_var.get(), role_var.get(), position_var.get()
        )).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Cancelar", command=edit_window.destroy).pack(side=tk.LEFT, padx=5)
    
    def save_edited_user(self, window, user, name, password, role, position):
        """Guarda los cambios de un usuario editado"""
        try:
            # Actualizar datos
            user.name = name
            if password:
                user.password = hash_password(password)
            user.role = role
            user.position = position
            
            # Guardar cambios
            if user.save():
                messagebox.showinfo("Éxito", f"Usuario '{user.username}' actualizado correctamente")
                window.destroy()
                self.load_data()
            else:
                messagebox.showerror("Error", "No se pudo actualizar el usuario")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al actualizar usuario: {str(e)}")
    
    def delete_user(self):
        """Elimina un usuario"""
        # Obtener selección
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Por favor seleccione un usuario para eliminar")
            return
        
        # Obtener datos del usuario seleccionado
        user_id = self.users_tree.item(selected[0], 'values')[0]
        username = self.users_tree.item(selected[0], 'values')[2]
        
        # Confirmar eliminación
        if not messagebox.askyesno("Confirmar", f"¿Está seguro de eliminar el usuario '{username}'?"):
            return
        
        # Verificar que no sea el usuario actual
        if str(user_id) == str(self.user.id):
            messagebox.showerror("Error", "No puede eliminar su propio usuario")
            return
        
        try:
            # Obtener usuario
            user = User.get_by_id(user_id)
            if not user:
                messagebox.showerror("Error", "No se encontró el usuario")
                return
            
            # Eliminar usuario
            if user.delete():
                messagebox.showinfo("Éxito", f"Usuario '{username}' eliminado correctamente")
                self.load_data()
            else:
                messagebox.showerror("Error", "No se pudo eliminar el usuario")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al eliminar usuario: {str(e)}")