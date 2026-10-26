"""Pruebas de los cobros por WhatsApp. No usan internet ni la base real:

    python -m unittest pruebas.test_cobros
"""
import os
import sqlite3
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("TURSO_URL", "libsql://prueba")
os.environ.setdefault("TURSO_TOKEN", "prueba")
os.environ.setdefault("CLAVE_HUELLA", "prueba")
os.environ.setdefault("SECRETO", "prueba")

from utils import cobros  # noqa: E402

ESQUEMA = """
    CREATE TABLE clients (id INTEGER PRIMARY KEY, name TEXT UNIQUE, phone TEXT, address TEXT,
        credit_limit REAL DEFAULT 0, total_debt REAL DEFAULT 0, notes TEXT);
    CREATE TABLE client_transactions (id INTEGER PRIMARY KEY, client_id INTEGER, transaction_type TEXT,
        amount REAL, description TEXT, sale_id INTEGER, created_at TEXT);
    CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL, stock INTEGER);
    CREATE TABLE sales (id INTEGER PRIMARY KEY, client_id INTEGER, total REAL, status TEXT, created_at TEXT);
    CREATE TABLE sale_details (id INTEGER PRIMARY KEY, sale_id INTEGER, product_id INTEGER, quantity REAL,
        unit_price REAL, subtotal REAL);
"""


def base():
    conn = sqlite3.connect(":memory:")
    conn.executescript(ESQUEMA)
    cobros.preparar(conn)
    cobros.preparar(conn)      # la segunda vez no falla
    return conn


def cliente(conn, cid, nombre, deuda, cobro=None, telefono="3001234567"):
    conn.execute("INSERT INTO clients (id, name, phone, total_debt, cobro) VALUES (?, ?, ?, ?, ?)",
                 (cid, nombre, telefono, deuda, cobro))
    if deuda:
        conn.execute("""INSERT INTO client_transactions (client_id, transaction_type, amount, description, created_at)
                        VALUES (?, 'debit', ?, 'Fiado', '2026-10-01 10:00:00')""", (cid, deuda))


class Periodos(unittest.TestCase):
    def test_semanal_desde_el_sabado(self):
        sabado = date(2026, 10, 24)
        for d, esperado in ((date(2026, 10, 23), date(2026, 10, 17)),    # viernes: el sábado pasado
                            (sabado, sabado), (date(2026, 10, 26), sabado)):
            self.assertEqual(cobros.inicio_periodo("semanal", d), esperado)

    def test_semanal_en_domingo(self):
        self.assertEqual(cobros.inicio_periodo("semanal", date(2026, 10, 24), dia_semanal=6),
                         date(2026, 10, 18))

    def test_quincenal(self):
        casos = {date(2026, 10, 14): date(2026, 9, 30), date(2026, 10, 15): date(2026, 10, 15),
                 date(2026, 10, 16): date(2026, 10, 15), date(2026, 10, 30): date(2026, 10, 15),
                 date(2026, 10, 31): date(2026, 10, 31), date(2026, 11, 1): date(2026, 10, 31),
                 date(2027, 2, 28): date(2027, 2, 28), date(2027, 3, 2): date(2027, 2, 28)}
        for hoy, esperado in casos.items():
            self.assertEqual(cobros.inicio_periodo("quincenal", hoy), esperado, hoy)


class Mensaje(unittest.TestCase):
    def test_lo_escrito_y_la_parte_fija(self):
        texto = cobros.mensaje(cobros.MENSAJE, " Ana ", 125000, "https://x/cuenta/abc", "Nequi 300")
        self.assertEqual(texto, cobros.MENSAJE + "\n\n"
                         "Saldo pendiente: $125.000\n"
                         "Aquí está el detalle de tu estado de cuenta: https://x/cuenta/abc\n"
                         "Puedes pagarnos a: Nequi 300")
        self.assertNotIn("Ana", texto)

    def test_sin_cuenta_no_sale_esa_linea(self):
        self.assertNotIn("pagarnos", cobros.mensaje(cobros.MENSAJE, "Ana", 1000, "e", ""))

    def test_con_deuda_en_el_texto_no_se_repite(self):
        texto = cobros.mensaje("Hola {nombre}, debes {deuda}.", "Ana", 1000, "e", "")
        self.assertEqual(texto, "Hola Ana, debes $1.000.\n\nAquí está el detalle de tu estado de cuenta: e")

    def test_no_se_puede_cambiar_el_enlace_ni_la_cuenta(self):
        texto = cobros.mensaje("{enlace} {cuenta} {otro}", "Ana", 1000, "https://x", "Nequi")
        self.assertTrue(texto.startswith("{enlace} {cuenta} {otro}\n\n"))


class Reparto(unittest.TestCase):
    def setUp(self):
        self.conn = base()
        self.hoy = date(2026, 10, 26)
        cliente(self.conn, 1, "Ana", 50000, "semanal")
        cliente(self.conn, 2, "Beto", 90000, "quincenal")
        cliente(self.conn, 3, "Caro", 20000)
        cliente(self.conn, 4, "Dani", 0, "semanal")      # no debe: no sale

    def nombres(self):
        return [[c["nombre"] for c in g] for g in cobros.clientes(self.conn, self.hoy)]

    def test_reparto(self):
        self.assertEqual(self.nombres(), [["Beto", "Ana"], [], ["Caro"]])

    def test_cobrado_sale_aparte_hasta_el_siguiente_periodo(self):
        cobros.marcar_cobrado(self.conn, 1, self.hoy)
        cobros.marcar_cobrado(self.conn, 1, self.hoy)       # dos toques, una marca
        self.assertEqual(self.nombres(), [["Beto"], ["Ana"], ["Caro"]])
        self.hoy = date(2026, 10, 31)                        # sábado: semana nueva
        self.assertEqual(self.nombres()[0], ["Beto", "Ana"])

    def test_sin_frecuencia_no_se_marca(self):
        with self.assertRaises(ValueError):
            cobros.marcar_cobrado(self.conn, 3, self.hoy)

    def test_poner_frecuencia(self):
        cobros.poner_frecuencia(self.conn, 3, "quincenal")
        self.assertEqual(cobros.frecuencia(self.conn, 3), "quincenal")
        cobros.poner_frecuencia(self.conn, 3, "")
        self.assertIsNone(cobros.frecuencia(self.conn, 3))
        with self.assertRaises(ValueError):
            cobros.poner_frecuencia(self.conn, 3, "mensual")
        with self.assertRaises(ValueError):
            cobros.poner_frecuencia(self.conn, 99, "semanal")


class Ajustes(unittest.TestCase):
    def setUp(self):
        self.conn = base()

    def test_por_defecto(self):
        a = cobros.ajustes(self.conn)
        self.assertEqual((a["cuenta"], a["mensaje"], a["dia_semanal"], a["personalizado"]),
                         ("", cobros.MENSAJE, 5, False))

    def test_mensaje(self):
        cobros.guardar_mensaje(self.conn, "  Hola  ")
        self.assertEqual((cobros.ajustes(self.conn)["mensaje"], cobros.ajustes(self.conn)["personalizado"]),
                         ("Hola", True))
        cobros.guardar_mensaje(self.conn, cobros.MENSAJE)
        self.assertFalse(cobros.ajustes(self.conn)["personalizado"])
        with self.assertRaisesRegex(ValueError, "vacío"):
            cobros.guardar_mensaje(self.conn, "  ")
        with self.assertRaisesRegex(ValueError, "largo"):
            cobros.guardar_mensaje(self.conn, "x" * (cobros.LARGO_MAXIMO + 1))

    def test_cuenta_aparte_del_mensaje(self):
        cobros.guardar_mensaje(self.conn, "Hola")
        cobros.guardar_cuenta(self.conn, " Nequi 300 ", "6")
        a = cobros.ajustes(self.conn)
        self.assertEqual((a["cuenta"], a["mensaje"], a["dia_semanal"]), ("Nequi 300", "Hola", 6))
        for dia in ("9", "x", None):
            with self.assertRaisesRegex(ValueError, "día"):
                cobros.guardar_cuenta(self.conn, "", dia)


class Rutas(unittest.TestCase):
    def setUp(self):
        import web.app as w
        import web.historial as historial
        self.conn = base()
        self.conn.row_factory = sqlite3.Row
        cliente(self.conn, 1, "Ana", 50000, "semanal")
        cliente(self.conn, 2, "Caro", 20000)
        for parche in (mock.patch.object(w, "db", return_value=w._ConexionVisita(self.conn)),
                       mock.patch("web.cobros.db", return_value=w._ConexionVisita(self.conn)),
                       mock.patch.object(historial, "db", return_value=w._ConexionVisita(self.conn)),
                       mock.patch.object(historial, "_anotar_visita")):     # el historial va a la base real
            parche.start()
            self.addCleanup(parche.stop)
        self.cliente = w.app.test_client()
        with self.cliente.session_transaction() as sesion:
            sesion["ingreso"] = True
            sesion["csrf"] = "c"

    def pagina(self):
        return self.cliente.get("/cobros").get_data(as_text=True)

    def test_pagina(self):
        html = self.pagina()
        self.assertIn("1 cliente deben y no tienen frecuencia", html)
        self.assertIn("Falta el número de cuenta", html)
        self.assertIn("Saldo pendiente: $50.000", unquote(html))

    def test_filtro_por_frecuencia(self):
        cliente(self.conn, 3, "Beto", 90000, "quincenal")
        cliente(self.conn, 4, "Eva", 10000, "semanal")

        def lista(ver=None):
            html = self.cliente.get("/cobros", query_string={"ver": ver} if ver else {}).get_data(as_text=True)
            toca = html.split('id="toca"')[1].split("</ul>")[0]
            return [n for n in ("Ana", "Beto", "Eva") if n in toca], html
        # Todos: primero los semanales, cada grupo del que más debe al que menos
        nombres, html = lista()
        self.assertEqual(sorted(nombres, key=html.index), ["Ana", "Eva", "Beto"])
        self.assertIn("Semanal (2)", html)
        self.assertIn("Quincenal (1)", html)
        self.assertEqual(lista("semanal")[0], ["Ana", "Eva"])
        self.assertEqual(lista("quincenal")[0], ["Beto"])
        self.assertEqual(lista("otra")[0], ["Ana", "Beto", "Eva"])

    def test_marcar_frecuencia_desde_la_pagina(self):
        r = self.cliente.post("/cobros/frecuencia", data={"csrf": "c", "client_id": "2", "cobro": "quincenal"})
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("no tienen frecuencia", self.pagina())

    def test_enviado(self):
        r = self.cliente.post("/cobros/enviado", data={"csrf": "c", "client_id": "1"})
        self.assertEqual(r.status_code, 204)
        self.assertIn("Ya se les cobró (1)", self.pagina())
        r = self.cliente.post("/cobros/enviado", data={"client_id": "1"})
        self.assertEqual(r.status_code, 400)

    def test_mensaje(self):
        self.cliente.post("/cobros/mensaje", data={"csrf": "c", "mensaje": "Hola {nombre}, debes {deuda}."})
        html = unquote(self.pagina())
        self.assertIn("Mensaje guardado", html)
        self.assertIn("Hola Ana, debes $50.000.\n\nAquí está el detalle de tu estado de cuenta: http", html)
        self.cliente.post("/cobros/mensaje", data={"csrf": "c", "restaurar": "1"})
        self.assertIn(cobros.MENSAJE, unquote(self.pagina()))

    def test_cuenta(self):
        r = self.cliente.post("/cobros/cuenta", data={"csrf": "c", "cuenta": "Nequi 300", "dia_semanal": "6"})
        self.assertEqual(r.status_code, 302)
        html = unquote(self.pagina())
        self.assertIn("Puedes pagarnos a: Nequi 300", html)
        self.assertIn("Semanales: cada domingo", html)
        self.assertNotIn("Falta el número de cuenta", html)

    def test_la_hermana_no_cambia_la_cuenta(self):
        with self.cliente.session_transaction() as sesion:
            sesion["sin_gastos"] = True
        self.assertEqual(self.cliente.get("/cobros/cuenta").status_code, 404)
        r = self.cliente.post("/cobros/cuenta", data={"csrf": "c", "cuenta": "Otra", "dia_semanal": "5"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(cobros.ajustes(self.conn)["cuenta"], "")
        self.assertIn("Pídale al dueño", self.pagina())

    def test_enlace_al_estado_de_cuenta(self):
        import web.cobros as wc
        with self.cliente.application.test_request_context("/", base_url="https://tienda.example"):
            enlace = wc.enlace_estado(1)
        self.assertTrue(enlace.startswith("https://tienda.example/cuenta/"))
        ruta = enlace.removeprefix("https://tienda.example")
        with self.cliente.session_transaction() as sesion:
            sesion.clear()                                   # lo abre el cliente, sin contraseña
        r = self.cliente.get(ruta)
        self.assertEqual((r.status_code, r.mimetype), (200, "application/pdf"))
        self.assertEqual(self.cliente.get(ruta[:-3] + "xyz").status_code, 404)    # cambiado: no sirve
        with mock.patch("itsdangerous.timed.time.time", return_value=4102444800):  # año 2100
            self.assertEqual(self.cliente.get(ruta).status_code, 404)              # vencido

    def test_las_demas_paginas_siguen_con_contraseña(self):
        with self.cliente.session_transaction() as sesion:
            sesion.clear()
        self.assertEqual(self.cliente.get("/cobros").status_code, 302)

    def test_formulario_del_cliente_guarda_la_frecuencia(self):
        html = self.cliente.get("/cliente/1/editar").get_data(as_text=True)
        self.assertIn('value="semanal" selected', html)
        self.cliente.post("/cliente/2/editar", data={"csrf": "c", "nombre": "Caro", "cobro": "semanal"})
        self.assertEqual(cobros.frecuencia(self.conn, 2), "semanal")


if __name__ == "__main__":
    unittest.main()
