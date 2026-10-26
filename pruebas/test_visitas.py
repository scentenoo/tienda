"""Pruebas de las visitas al catálogo. No usan internet ni la base real:

    python -m unittest pruebas.test_visitas

(Las del recibidor de Cloudflare van aparte: node visitas/prueba.mjs)
"""
import os
import sqlite3
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("TURSO_URL", "libsql://prueba")
os.environ.setdefault("TURSO_TOKEN", "prueba")
os.environ.setdefault("CLAVE_HUELLA", "prueba")
os.environ.setdefault("SECRETO", "prueba")

from utils import visitas_catalogo as vc  # noqa: E402

URL = "https://x.github.io/tienda/"
TABLA = """CREATE TABLE eventos (id INTEGER PRIMARY KEY, momento TEXT, visitante TEXT, visita TEXT,
           codigo TEXT, tipo TEXT, dato TEXT, valor REAL, pais TEXT)"""


def base_visitas():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute(TABLA)
    return conn


def anotar(conn, visitante, tipo, dato=None, valor=None, codigo=None, visita="v1", hace_min=5):
    momento = (datetime.now(timezone.utc) - timedelta(minutes=hace_min)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    conn.execute("INSERT INTO eventos (momento, visitante, visita, codigo, tipo, dato, valor) VALUES (?,?,?,?,?,?,?)",
                 (momento, visitante, visita, codigo, tipo, dato, valor))


class Codigos(unittest.TestCase):
    def test_siempre_el_mismo_y_distinto_por_cliente(self):
        self.assertEqual(vc.codigo(5, "s"), vc.codigo(5, "s"))
        self.assertNotEqual(vc.codigo(5, "s"), vc.codigo(6, "s"))
        self.assertNotEqual(vc.codigo(5, "s"), vc.codigo(5, "otro"))
        self.assertRegex(vc.codigo(5, "s"), r"^[a-z2-7]{8}$")     # lo que acepta el recibidor

    def test_el_enlace_del_mensaje(self):
        texto = f"Mira aquí: {URL} y escríbenos"
        self.assertEqual(vc.poner_codigo(texto, URL, 5, "s"), f"Mira aquí: {URL}?c={vc.codigo(5, 's')} y escríbenos")
        self.assertEqual(vc.poner_codigo("Sin enlace", URL, 5, "s"), "Sin enlace")
        self.assertEqual(vc.poner_codigo(texto, "", 5, "s"), texto)
        self.assertTrue(vc.con_codigo("https://a.co/?x=1", 5, "s").startswith("https://a.co/?x=1&c="))


class Resumen(unittest.TestCase):
    def setUp(self):
        self.conn = base_visitas()
        self.clientes = {vc.codigo(1, "s"): (1, "Ana"), vc.codigo(2, "s"): (2, "Beto"), vc.codigo(3, "s"): (3, "Caro")}
        ana, beto, caro = (vc.codigo(i, "s") for i in (1, 2, 3))
        # Ana: entra, busca harina (no hay), agrega queso y lo envía
        anotar(self.conn, "aaaaaaaa", "entrada", codigo=ana, hace_min=30)
        anotar(self.conn, "aaaaaaaa", "busqueda", "harina pan", 0, codigo=ana, hace_min=29)
        anotar(self.conn, "aaaaaaaa", "agregar", "Queso", 1, codigo=ana, hace_min=28)
        anotar(self.conn, "aaaaaaaa", "enviar", "1 producto", 22000, codigo=ana, hace_min=27)
        # Beto: agrega mortadela y queso, quita el queso y se va sin enviar
        anotar(self.conn, "bbbbbbbb", "entrada", codigo=beto, hace_min=20)
        anotar(self.conn, "bbbbbbbb", "agregar", "Mortadela", 1, codigo=beto, hace_min=19)
        anotar(self.conn, "bbbbbbbb", "agregar", "Queso", 1, codigo=beto, hace_min=19)
        anotar(self.conn, "bbbbbbbb", "quitar", "Queso", 0, codigo=beto, hace_min=18)
        anotar(self.conn, "bbbbbbbb", "salida", None, 125, codigo=beto, hace_min=17)
        # Caro: entra dos veces y solo mira
        anotar(self.conn, "cccccccc", "entrada", codigo=caro, visita="c1", hace_min=15)
        anotar(self.conn, "cccccccc", "entrada", codigo=caro, visita="c2", hace_min=10)
        # Alguien sin código, desde el estado
        anotar(self.conn, "dddddddd", "entrada")
        anotar(self.conn, "dddddddd", "busqueda", "Harina PAN", 0)
        # De hace dos semanas: no entra en los 7 días
        anotar(self.conn, "eeeeeeee", "entrada", hace_min=14 * 24 * 60)

    def r(self, dias=7):
        return vc.resumen(vc.eventos(self.conn, vc.desde_hace(dias)), self.clientes)

    def test_embudo(self):
        self.assertEqual(self.r()["embudo"], [("Entraron", 4), ("Agregaron algo", 2),
                                              ("Abrieron el pedido", 1), ("Tocaron enviar", 1)])
        self.assertEqual(self.r(30)["embudo"][0], ("Entraron", 5))

    def test_por_cliente_primero_quien_armo_y_no_envio(self):
        personas = self.r()["personas"]
        self.assertEqual([(p["nombre"], p["estado"]) for p in personas],
                         [("Beto", "armo"), ("Caro", "miro"), ("Ana", "envio")])
        beto, caro, ana = personas
        self.assertEqual(beto["en_pedido"], ["Mortadela"])
        self.assertEqual(beto["agrego"], ["Mortadela", "Queso"])
        self.assertEqual(beto["minutos"], 2)
        self.assertEqual(caro["visitas"], 2)
        self.assertEqual((ana["total_enviado"], ana["busco"]), (22000, ["harina pan"]))

    def test_busquedas_sin_resultado_una_vez_por_persona(self):
        r = self.r()
        self.assertEqual(r["sin_resultado"], [("harina pan", 2)])
        self.assertEqual(r["agregados"][0], ("Queso", 2))
        self.assertEqual((r["con_nombre"], r["sin_nombre"]), (3, 1))

    def test_hora_de_colombia(self):
        self.assertEqual(vc._hora_local("2026-10-26T23:05:01.123Z").strftime("%d %H:%M"), "26 18:05")


class Pagina(unittest.TestCase):
    def setUp(self):
        import web.app as w
        import web.historial as historial
        import web.visitas as wv
        self.w = w
        self.tienda = sqlite3.connect(":memory:", check_same_thread=False)
        self.tienda.row_factory = sqlite3.Row
        self.tienda.executescript("""
            CREATE TABLE clients (id INTEGER PRIMARY KEY, name TEXT UNIQUE, phone TEXT, total_debt REAL DEFAULT 0);
            CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL, stock INTEGER);
            CREATE TABLE sales (id INTEGER PRIMARY KEY, client_id INTEGER, total REAL, status TEXT, created_at TEXT);
            CREATE TABLE sale_details (id INTEGER PRIMARY KEY, sale_id INTEGER, product_id INTEGER, quantity REAL);
            INSERT INTO clients VALUES (1, 'Ana María', '3001234567', 0);
            INSERT INTO products VALUES (1, 'Queso', 22000, 5);""")
        hace = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d 18:00:00")
        for _ in range(2):
            cur = self.tienda.execute("INSERT INTO sales (client_id, total, status, created_at) VALUES (1, 22000, 'paid', ?)", (hace,))
            self.tienda.execute("INSERT INTO sale_details (sale_id, product_id, quantity) VALUES (?, 1, 1)", (cur.lastrowid,))
        self.visitas = base_visitas()
        anotar(self.visitas, "aaaaaaaa", "entrada", codigo=vc.codigo(1, w.app.secret_key))
        anotar(self.visitas, "aaaaaaaa", "agregar", "Queso", 1, codigo=vc.codigo(1, w.app.secret_key))
        w._tablas_domicilio = False
        visitas = mock.MagicMock(wraps=self.visitas)
        visitas.close = mock.Mock()       # la página la cierra; la prueba la sigue usando
        self.base_visitas = mock.patch.object(wv, "_base_visitas", return_value=visitas)
        for parche in (mock.patch.object(w, "db", return_value=w._ConexionVisita(self.tienda)),
                       mock.patch.object(wv, "db", return_value=w._ConexionVisita(self.tienda)),
                       self.base_visitas,
                       mock.patch.object(historial, "_anotar_visita")):
            parche.start()
            self.addCleanup(parche.stop)
        self.cliente = w.app.test_client()
        with self.cliente.session_transaction() as sesion:
            sesion["ingreso"] = True
            sesion["csrf"] = "c"

    def test_pagina(self):
        html = self.cliente.get("/catalogo/visitas").get_data(as_text=True)
        self.assertIn("Ana María", html)
        self.assertIn("Armó y no envió", html)
        self.assertIn("Queso", html)

    def test_sin_configurar(self):
        import web.visitas as wv
        with mock.patch.object(wv, "_base_visitas", return_value=None):
            html = self.cliente.get("/catalogo/visitas").get_data(as_text=True)
        self.assertIn("VISITAS_TURSO_URL", html)

    def test_sin_visitas_todavia(self):
        self.visitas.execute("DROP TABLE eventos")
        r = self.cliente.get("/catalogo/visitas?dias=1")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Ningún cliente ha entrado", r.get_data(as_text=True))

    def test_pide_contraseña(self):
        with self.cliente.session_transaction() as sesion:
            sesion.clear()
        self.assertEqual(self.cliente.get("/catalogo/visitas").status_code, 302)

    def test_domicilio_manda_el_enlace_con_codigo(self):
        with mock.patch.dict(os.environ, {"CATALOGO_URL": URL}):
            html = unquote(self.cliente.get("/domicilio").get_data(as_text=True))
        self.assertIn(f"{URL}?c={vc.codigo(1, self.w.app.secret_key)}", html)


if __name__ == "__main__":
    unittest.main()
