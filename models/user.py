from config.database import get_connection
from utils.security import verify_password

class User:
    def __init__(self, id=None, username=None, password=None, role=None, name=None, position=None):
        self.id = id
        self.username = username
        self.password = password
        self.role = role
        self.name = name if name else username  # Si no hay nombre, usar username
        self.position = position
    
    @staticmethod
    def authenticate(username, password):
        """Autentica un usuario con su nombre de usuario y contraseña"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user_data = cursor.fetchone()
        
        conn.close()
        
        if user_data and verify_password(user_data['password'], password):
            return User(
                id=user_data['id'],
                username=user_data['username'],
                password=user_data['password'],  # Ya está hasheada
                role=user_data['role'],
                name=user_data['name'],
                position=user_data['position'] if 'position' in user_data else None
            )
        
        return None
        
    def save(self):
        """Guarda el usuario en la base de datos"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            if self.id is None:
                cursor.execute('''
                    INSERT INTO users (username, password, role, name, position) 
                    VALUES (?, ?, ?, ?, ?)
                ''', (self.username, self.password, self.role, self.name, self.position))
                self.id = cursor.lastrowid
            else:
                cursor.execute('''
                    UPDATE users SET username = ?, password = ?, role = ?, name = ?, position = ? 
                    WHERE id = ?
                ''', (self.username, self.password, self.role, self.name, self.position, self.id))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error al guardar usuario: {e}")
            return False
        finally:
            conn.close()
    
    def delete(self):
        """Elimina el usuario de la base de datos"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM users WHERE id = ?', (self.id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error al eliminar usuario: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def get_all():
        """Obtiene todos los usuarios de la base de datos"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users ORDER BY username')
        users_data = cursor.fetchall()
        
        conn.close()
        
        users = []
        for user_data in users_data:
            user = User(
                id=user_data['id'],
                username=user_data['username'],
                password=user_data['password'],
                role=user_data['role'],
                name=user_data['name'] if 'name' in user_data else user_data['username'],
                position=user_data['position'] if 'position' in user_data else None
            )
            users.append(user)
        
        return users
    
    @staticmethod
    def get_by_id(user_id):
        """Obtiene un usuario por su ID"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user_data = cursor.fetchone()
        
        conn.close()
        
        if user_data:
            return User(
                id=user_data['id'],
                username=user_data['username'],
                password=user_data['password'],
                role=user_data['role'],
                name=user_data['name'] if 'name' in user_data else user_data['username'],
                position=user_data['position'] if 'position' in user_data else None
            )
        
        return None
    
    @staticmethod
    def get_by_username(username):
        """Obtiene un usuario por su nombre de usuario"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user_data = cursor.fetchone()
        
        conn.close()
        
        if user_data:
            return User(
                id=user_data['id'],
                username=user_data['username'],
                password=user_data['password'],
                role=user_data['role'],
                name=user_data['name'] if 'name' in user_data else user_data['username'],
                position=user_data['position'] if 'position' in user_data else None
            )
        
        return None