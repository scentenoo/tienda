import os

def get_db_path():
    base_dir = r"C:\Users\Samir\Documents\GitHub\tienda\data"
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, "tienda.db")