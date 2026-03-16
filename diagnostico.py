import sqlite3

import os

base = r"C:\Users\samir\Documents\GitHub\tienda"
for root, dirs, files in os.walk(base):
    # Ignorar carpetas irrelevantes
    dirs[:] = [d for d in dirs if d not in ['.venv', '__pycache__', '.git']]
    level = root.replace(base, '').count(os.sep)
    indent = '  ' * level
    print(f"{indent}{os.path.basename(root)}/")
    for f in files:
        print(f"{'  ' * (level+1)}{f}")