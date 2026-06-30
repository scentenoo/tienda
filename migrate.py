"""
migrate_lotes.py
----------------
Migra los datos históricos de purchases para:
1. Agregar columna lote_id y shipping_total si no existen
2. Asignar lote_id a cada registro agrupando por ventana de 10 segundos
3. Corregir shipping: el primer ítem del lote lleva el flete total, los demás 0
4. Llenar shipping_total con el flete total del lote en todos los registros

Ejecutar UNA sola vez antes de usar la nueva versión de la app.
"""

import sqlite3
import os
from datetime import datetime

# Ruta relativa a la DB — ajusta si tu carpeta data está en otro lugar
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "tienda.db")


def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Agregar columnas si no existen
    for col, definition in [("lote_id", "TEXT"), ("shipping_total", "REAL DEFAULT 0.0")]:
        try:
            cursor.execute(f"ALTER TABLE purchases ADD COLUMN {col} {definition}")
            print(f"Columna '{col}' agregada.")
        except sqlite3.OperationalError:
            print(f"Columna '{col}' ya existe, se omite.")

    # 2. Leer todos los registros ordenados por fecha
    cursor.execute("SELECT id, shipping, date FROM purchases ORDER BY date ASC")
    rows = cursor.fetchall()

    if not rows:
        print("No hay registros en purchases.")
        conn.close()
        return

    # 3. Agrupar por ventana de 10 segundos
    lotes = []
    lote_actual = []
    prev_time = None

    for row in rows:
        t = datetime.strptime(row["date"], "%Y-%m-%d %H:%M:%S")
        if prev_time is None or (t - prev_time).total_seconds() <= 10:
            lote_actual.append(dict(row))
        else:
            lotes.append(lote_actual)
            lote_actual = [dict(row)]
        prev_time = t
    if lote_actual:
        lotes.append(lote_actual)

    print(f"Lotes detectados: {len(lotes)}")

    # 4. Generar updates
    updates = []
    for i, lote in enumerate(lotes):
        # lote_id basado en la fecha del primer elemento
        lote_id = datetime.strptime(lote[0]["date"], "%Y-%m-%d %H:%M:%S").strftime("%Y%m%d%H%M%S")
        n = len(lote)
        flete_unitario = lote[0]["shipping"]
        flete_total = flete_unitario * n

        for j, item in enumerate(lote):
            shipping_corregido = flete_total if j == 0 else 0.0
            updates.append((lote_id, flete_total, shipping_corregido, item["id"]))
            print(f"  Lote {i+1} | id={item['id']} | lote_id={lote_id} | "
                  f"shipping_total={flete_total} | shipping={shipping_corregido}")

    # 5. Aplicar updates
    cursor.executemany(
        "UPDATE purchases SET lote_id = ?, shipping_total = ?, shipping = ? WHERE id = ?",
        updates
    )
    conn.commit()
    print(f"\nMigración completada. {len(updates)} registros actualizados.")
    conn.close()


if __name__ == "__main__":
    migrate()