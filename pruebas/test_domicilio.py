"""Pruebas del domicilio de la semana. No usan internet ni la base real:

    python -m unittest pruebas.test_domicilio
"""
import os
import sqlite3
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("TURSO_URL", "libsql://prueba")
os.environ.setdefault("TURSO_TOKEN", "prueba")
os.environ.setdefault("CLAVE_HUELLA", "prueba")
os.environ.setdefault("SECRETO", "prueba")

from utils import domicilio  # noqa: E402

HOY = date(2026, 10, 22)    # jueves

ESQUEMA = """
    CREATE TABLE clients (id INTEGER PRIMARY KEY, name TEXT UNIQUE, phone TEXT, total_debt REAL DEFAULT 0);
    CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL, stock INTEGER);
    CREATE TABLE sales (id INTEGER PRIMARY KEY, client_id INTEGER, total REAL, status TEXT, created_at TEXT);
    CREATE TABLE sale_details (id INTEGER PRIMARY KEY, sale_id INTEGER, product_id INTEGER, quantity REAL);
"""


def base():
    conn = sqlite3.connect(":memory:")
    conn.executescript(ESQUEMA)
    conn.execute("INSERT INTO products VALUES (1, 'Queso', 22000, 10)")
    return conn


def cliente(conn, cid, nombre, telefono="3001234567", deuda=0, compras=(3,), pendiente=None):
    """compras: hace cuántos días compró; pendiente: hace cuántos días quedó
    sin pagar la venta más vieja."""
    conn.execute("INSERT INTO clients VALUES (?, ?, ?, ?)", (cid, nombre, telefono, deuda))
    for hace in compras:
        estado = "pending" if hace == pendiente else "paid"
        cur = conn.execute("INSERT INTO sales (client_id, total, status, created_at) VALUES (?, 22000, ?, ?)",
                           (cid, estado, (HOY - timedelta(days=hace)).isoformat() + " 18:00:00"))
        conn.execute("INSERT INTO sale_details (sale_id, product_id, quantity) VALUES (?, 1, 1)",
                     (cur.lastrowid,))


class Reparto(unittest.TestCase):
    def setUp(self):
        self.conn = base()

    def nombres(self):
        return [[c["nombre"] for c in grupo] for grupo in domicilio.clientes(self.conn, HOY)]

    def test_al_dia_y_con_telefono_se_le_escribe(self):
        cliente(self.conn, 1, "Ana")
        self.assertEqual(self.nombres(), [["Ana"], [], []])

    def test_debe_poco_y_hace_poco_igual_se_le_escribe(self):
        cliente(self.conn, 1, "Ana", deuda=150_000, compras=(10,), pendiente=10)
        self.assertEqual(self.nombres(), [["Ana"], [], []])

    def test_debe_mucho_no(self):
        cliente(self.conn, 1, "Ana", deuda=150_001, compras=(3,), pendiente=3)
        escribir, deben, _ = domicilio.clientes(self.conn, HOY)
        self.assertEqual(escribir, [])
        self.assertEqual(deben[0]["motivo"], "monto")

    def test_debe_desde_hace_mucho_no(self):
        cliente(self.conn, 1, "Ana", deuda=20_000, compras=(22, 5), pendiente=22)
        escribir, deben, _ = domicilio.clientes(self.conn, HOY)
        self.assertEqual(escribir, [])
        self.assertEqual((deben[0]["motivo"], deben[0]["dias_debe"]), ("dias", 22))

    def test_21_dias_justos_todavia_si(self):
        cliente(self.conn, 1, "Ana", deuda=20_000, compras=(21,), pendiente=21)
        self.assertEqual(self.nombres(), [["Ana"], [], []])

    def test_sin_telefono_aparte(self):
        cliente(self.conn, 1, "Ana", telefono=None)
        self.assertEqual(self.nombres(), [[], [], ["Ana"]])

    def test_quien_no_compra_hace_4_meses_no_sale(self):
        cliente(self.conn, 1, "Ana", compras=(130,))
        self.assertEqual(self.nombres(), [[], [], []])


class Mensaje(unittest.TestCase):
    def test_con_y_sin_catalogo(self):
        con = domicilio.mensaje("https://x.github.io/tienda/")
        self.assertTrue(con.startswith("¡Hola! Hoy en la tarde-noche hacemos domicilios."))
        self.assertIn("https://x.github.io/tienda/", con)
        self.assertNotIn("http", domicilio.mensaje(""))

    def test_url_del_catalogo(self):
        with mock.patch.dict(os.environ, {"CATALOGO_REPO": "Scentenoo/tienda"}, clear=True):
            self.assertEqual(domicilio.url_catalogo(), "https://scentenoo.github.io/tienda/")
        with mock.patch.dict(os.environ, {"CATALOGO_URL": "https://otra.co/", "CATALOGO_REPO": "a/b"}, clear=True):
            self.assertEqual(domicilio.url_catalogo(), "https://otra.co/")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(domicilio.url_catalogo(), "")


class Guardado(unittest.TestCase):
    def setUp(self):
        self.conn = base()
        domicilio.preparar(self.conn)
        domicilio.preparar(self.conn)      # la segunda vez no falla
        cliente(self.conn, 1, "Ana")

    def test_el_mensaje_queda_para_las_semanas_siguientes(self):
        self.assertIsNone(domicilio.mensaje_guardado(self.conn))
        domicilio.guardar_mensaje(self.conn, HOY, "  Hola  ")
        domicilio.guardar_mensaje(self.conn, HOY, "Hola de nuevo")
        self.assertEqual(domicilio.mensaje_guardado(self.conn), "Hola de nuevo")
        domicilio.guardar_mensaje(self.conn, HOY + timedelta(days=7), "Otra semana")
        self.assertEqual(domicilio.mensaje_guardado(self.conn), "Otra semana")
        domicilio.restaurar_mensaje(self.conn)
        self.assertIsNone(domicilio.mensaje_guardado(self.conn))

    def test_mensaje_vacio_o_largo(self):
        with self.assertRaisesRegex(ValueError, "vacío"):
            domicilio.guardar_mensaje(self.conn, HOY, "   ")
        with self.assertRaisesRegex(ValueError, "largo"):
            domicilio.guardar_mensaje(self.conn, HOY, "x" * (domicilio.LARGO_MAXIMO + 1))

    def test_enviados_por_dia(self):
        domicilio.marcar_enviado(self.conn, HOY, 1)
        domicilio.marcar_enviado(self.conn, HOY, 1)       # tocar dos veces no duplica
        self.assertEqual(domicilio.enviados(self.conn, HOY), {1})
        self.assertEqual(domicilio.enviados(self.conn, HOY + timedelta(days=1)), set())
        with self.assertRaisesRegex(ValueError, "no existe"):
            domicilio.marcar_enviado(self.conn, HOY, 99)


class Rutas(unittest.TestCase):
    def setUp(self):
        import web.app as w
        import web.historial as historial
        self.conn = base()
        self.conn.row_factory = sqlite3.Row
        cliente(self.conn, 1, "Ana")
        cliente(self.conn, 2, "Beto")
        w._tablas_domicilio = False
        for parche in (mock.patch.object(w, "db", return_value=w._ConexionVisita(self.conn)),
                       mock.patch.object(historial, "_anotar_visita")):     # el historial va a la base real
            parche.start()
            self.addCleanup(parche.stop)
        self.hoy = date.today()
        self.cliente = w.app.test_client()
        with self.cliente.session_transaction() as sesion:
            sesion["ingreso"] = True
            sesion["csrf"] = "c"

    def test_marcar_enviado_se_ve_al_volver(self):
        r = self.cliente.post("/domicilio/enviado", data={"csrf": "c", "client_id": "2"})
        self.assertEqual(r.status_code, 204)
        html = self.cliente.get("/domicilio").get_data(as_text=True)
        self.assertIn("1 de 2 enviados", html)
        self.assertIn('data-id="2" class="enviado"', html)

    def test_guardar_mensaje_y_volver_al_de_siempre(self):
        self.cliente.post("/domicilio/mensaje", data={"csrf": "c", "mensaje": "Hoy hay arepas"})
        html = self.cliente.get("/domicilio").get_data(as_text=True)
        self.assertIn("Mensaje guardado", html)
        self.assertIn(">Hoy hay arepas</textarea>", html)
        self.assertIn("text=Hoy%20hay%20arepas", html)
        self.cliente.post("/domicilio/mensaje", data={"csrf": "c", "restaurar": "1"})
        html = self.cliente.get("/domicilio").get_data(as_text=True)
        self.assertIn("Hoy en la tarde-noche", html)

    def test_mensaje_vacio_avisa(self):
        self.cliente.post("/domicilio/mensaje", data={"csrf": "c", "mensaje": " "})
        html = self.cliente.get("/domicilio").get_data(as_text=True)
        self.assertIn("no puede quedar vacío", html)

    def test_sin_dias_para_elegir(self):
        html = self.cliente.get("/domicilio").get_data(as_text=True)
        self.assertNotIn("?dia=", html)
        self.assertNotIn('name="dia"', html)
        self.assertIn("Hoy en la tarde-noche", html)

    def test_sin_csrf_o_cliente_raro_no(self):
        domicilio.preparar(self.conn)
        r = self.cliente.post("/domicilio/enviado", data={"client_id": "1"})
        self.assertEqual(r.status_code, 400)
        r = self.cliente.post("/domicilio/enviado", data={"csrf": "c", "client_id": "x"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(domicilio.enviados(self.conn, self.hoy), set())


if __name__ == "__main__":
    unittest.main()
