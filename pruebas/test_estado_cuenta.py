"""Pruebas del estado de cuenta. No usan internet ni la base real:

    python -m unittest pruebas.test_estado_cuenta
"""
import io
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils import estado_cuenta  # noqa: E402

ESQUEMA = """
    CREATE TABLE clients (id INTEGER PRIMARY KEY, name TEXT, total_debt REAL DEFAULT 0);
    CREATE TABLE client_transactions (id INTEGER PRIMARY KEY, client_id INTEGER, transaction_type TEXT,
        amount REAL, description TEXT, sale_id INTEGER, created_at TEXT);
    CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT);
    CREATE TABLE sales (id INTEGER PRIMARY KEY, adjustment_reason TEXT);
    CREATE TABLE sales_eliminadas (id INTEGER PRIMARY KEY, adjustment_reason TEXT);
    CREATE TABLE sale_details (id INTEGER PRIMARY KEY, sale_id INTEGER, product_id INTEGER,
        quantity REAL, sale_price REAL, subtotal REAL);
    CREATE TABLE sale_details_eliminados (id INTEGER PRIMARY KEY, sale_id INTEGER, product_name TEXT,
        quantity REAL, sale_price REAL, subtotal REAL);
"""


def base():
    conn = sqlite3.connect(":memory:")
    conn.executescript(ESQUEMA)
    conn.execute("INSERT INTO clients VALUES (1, 'Ana Pérez', 60000)")
    conn.execute("INSERT INTO products VALUES (1, 'Queso')")
    for sale_id, comentario in ((1, "Venta del 25/10"), (2, None), (3, "   ")):
        conn.execute("INSERT INTO sales VALUES (?, ?)", (sale_id, comentario))
    conn.execute("INSERT INTO sales_eliminadas VALUES (4, 'De la que se borró')")
    for sale_id in (1, 2, 3, 4):
        conn.execute("INSERT INTO sale_details (sale_id, product_id, quantity, sale_price, subtotal) "
                     "VALUES (?, 1, 1, 15000, 15000)", (sale_id,))
        conn.execute("""INSERT INTO client_transactions
                        (client_id, transaction_type, amount, description, sale_id, created_at)
                        VALUES (1, 'debit', 15000, 'Venta fiada', ?, '2026-10-26 10:00:00')""", (sale_id,))
    return conn


class Comentarios(unittest.TestCase):
    def test_salen_aunque_la_venta_no_tenga_ajuste(self):
        compras = estado_cuenta.calcular(base(), 1)["movimientos"]
        self.assertEqual([m["comentario"] for m in compras],
                         ["Venta del 25/10", "", "", "De la que se borró"])

    def test_cargo_sin_venta_no_tiene_comentario(self):
        conn = base()
        conn.execute("UPDATE client_transactions SET sale_id = NULL WHERE sale_id = 1")
        self.assertEqual(estado_cuenta.calcular(conn, 1)["movimientos"][0]["comentario"], "")

    def test_el_pdf_aguanta_caracteres_raros(self):
        datos = estado_cuenta.calcular(base(), 1)
        datos["movimientos"][0]["comentario"] = "<b>2 & 3</b> sin cerrar <font"
        pdf = io.BytesIO()
        estado_cuenta.exportar_pdf(datos, pdf)
        self.assertTrue(pdf.getvalue().startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
