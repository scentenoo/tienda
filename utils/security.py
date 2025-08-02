import hashlib
import os

def hash_password(password):
    """
    Genera un hash seguro para la contraseña usando SHA-256
    
    Args:
        password (str): La contraseña en texto plano
        
    Returns:
        str: El hash de la contraseña
    """
    # Convertir la contraseña a bytes si es una cadena
    if isinstance(password, str):
        password = password.encode('utf-8')
    
    # Generar el hash usando SHA-256
    hash_obj = hashlib.sha256(password)
    
    # Devolver el hash en formato hexadecimal
    return hash_obj.hexdigest()

def verify_password(stored_hash, provided_password):
    """
    Verifica si una contraseña coincide con el hash almacenado
    
    Args:
        stored_hash (str): El hash almacenado en la base de datos
        provided_password (str): La contraseña proporcionada por el usuario
        
    Returns:
        bool: True si la contraseña coincide, False en caso contrario
    """
    # Generar el hash de la contraseña proporcionada
    provided_hash = hash_password(provided_password)
    
    # Comparar los hashes
    return stored_hash == provided_hash