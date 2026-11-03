"""Pruebas de Qué pedir, el conteo del martes, los pedidos en camino y los
avisos. No usan internet ni la base real:

    python -m unittest pruebas.test_reposicion
"""
import json
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

from utils import reposicion  # noqa: E402

MARTES = date(2026, 11, 3)

# Las tablas como están en la base real (solo las columnas que se usan)
ESQUEMA = """
    CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT);
    CREATE TABLE products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, price REAL NOT NULL,
        stock INTEGER DEFAULT 0, cost_price REAL DEFAULT 0.0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        categoria TEXT, catalogo TEXT DEFAULT 'auto');
    CREATE TABLE clients (id INTEGER PRIMARY KEY, name TEXT UNIQUE, phone TEXT, address TEXT,
        credit_limit REAL DEFAULT 0, total_debt REAL DEFAULT 0, notes TEXT, created_at TEXT);
    CREATE TABLE client_transactions (id INTEGER PRIMARY KEY, client_id INTEGER, transaction_type TEXT,
        amount REAL, description TEXT, sale_id INTEGER, created_at TEXT);
    CREATE TABLE sales (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, total REAL NOT NULL,
        payment_type TEXT, payment_method TEXT, paid_amount REAL DEFAULT 0, remaining_debt REAL DEFAULT 0,
        adjustment REAL DEFAULT 0, adjustment_reason TEXT, notes TEXT, updated_at TEXT, user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'paid');
    CREATE TABLE sale_details (id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL, quantity REAL NOT NULL, unit_price REAL, sale_price REAL,
        subtotal REAL, cost_price REAL DEFAULT 0);
    CREATE TABLE purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, total REAL NOT NULL,
        iva REAL DEFAULT 0.0, shipping REAL DEFAULT 0.0, date TEXT DEFAULT CURRENT_TIMESTAMP,
        invoice_number TEXT, supplier TEXT, freight TEXT, tax TEXT, subtotal TEXT, lote_id TEXT,
        shipping_total REAL DEFAULT 0.0);
    CREATE TABLE purchase_details (id INTEGER PRIMARY KEY AUTOINCREMENT, purchase_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL, quantity INTEGER NOT NULL, unit_cost REAL, unit_price REAL NOT NULL,
        subtotal REAL NOT NULL);
    CREATE TABLE losses (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL,
        quantity REAL NOT NULL, unit_cost REAL NOT NULL, total_cost REAL NOT NULL, loss_date TIMESTAMP NOT NULL,
        reason TEXT NOT NULL, loss_type TEXT NOT NULL, notes TEXT, created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE domicilio_envios (dia TEXT NOT NULL, client_id INTEGER NOT NULL, enviado TEXT NOT NULL,
        PRIMARY KEY (dia, client_id));
    INSERT INTO users VALUES (1, 'admin', 'admin');
"""


def base():
    conn = sqlite3.connect(":memory:")
    conn.executescript(ESQUEMA)
    # Productos con nombres de verdad, para que tomen su grupo solos
    for pid, nombre, stock, costo in ((1, "Mayonesa Mavesa", 5, 14200), (2, "Samba", 23, 3000),
                                      (3, "Masa Facil", 7, 4200), (4, "Queso Costeño 1k", 8.5, 20000),
                                      (5, "Frescolita", 0, 0)):
        conn.execute("INSERT INTO products (id, name, price, stock, cost_price) VALUES (?, ?, ?, ?, ?)",
                     (pid, nombre, costo * 1.5 or 7500, stock, costo))
    reposicion.preparar(conn)
    reposicion.preparar(conn)      # la segunda vez no falla
    return conn


def vender(conn, product_id, cantidad, dia, client_id=None):
    cur = conn.execute("INSERT INTO sales (client_id, total, status, payment_method, created_at) "
                       "VALUES (?, 1000, 'paid', 'cash', ?)", (client_id, f"{dia} 19:00:00"))
    conn.execute("INSERT INTO sale_details (sale_id, product_id, quantity, subtotal) VALUES (?, ?, ?, 1000)",
                 (cur.lastrowid, product_id, cantidad))
    conn.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (cantidad, product_id))


def comprar(conn, product_id, cantidad, dia):
    cur = conn.execute("INSERT INTO purchases (total, date) VALUES (1000, ?)", (f"{dia} 10:00:00",))
    conn.execute("INSERT INTO purchase_details (purchase_id, product_id, quantity, unit_price, subtotal) "
                 "VALUES (?, ?, ?, 1, 1)", (cur.lastrowid, product_id, cantidad))
    conn.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (cantidad, product_id))


def stock(conn, pid):
    return conn.execute("SELECT stock FROM products WHERE id = ?", (pid,)).fetchone()[0]


class Grupos(unittest.TestCase):
    def test_los_productos_conocidos_toman_su_grupo_y_su_caja(self):
        conn = base()
        filas = dict(((f[0], (f[1], f[2])) for f in conn.execute("SELECT id, grupo, caja FROM products")))
        self.assertEqual(filas[1], ("cucuta", 12))
        self.assertEqual(filas[2], ("cucuta", 20))
        self.assertEqual(filas[3], ("medellin", 5))
        self.assertEqual(filas[4], ("queso", 1))
        self.assertEqual(filas[5], (None, None))

    def test_poner_grupo(self):
        conn = base()
        reposicion.poner_grupo(conn, 5, "medellin", "6")
        self.assertEqual(reposicion.grupo_del_producto(conn, 5), {"grupo": "medellin", "caja": 6})
        reposicion.poner_grupo(conn, 5, "", "")
        self.assertEqual(reposicion.grupo_del_producto(conn, 5), {"grupo": "", "caja": None})
        with self.assertRaises(ValueError):
            reposicion.poner_grupo(conn, 5, "cucuta", "doce")


class Demanda(unittest.TestCase):
    def test_solo_cuenta_los_dias_en_que_habia(self):
        conn = base()
        conn.execute("UPDATE products SET stock = 0 WHERE id = 2")
        # Llegan 20 hace 14 días y se venden en una semana; después, agotado
        comprar(conn, 2, 20, MARTES - timedelta(days=14))
        for k in range(7):
            vender(conn, 2, 20 / 7, MARTES - timedelta(days=13 - k))
        semanal = reposicion.demanda(conn, MARTES, [2])[2]
        # 20 en ~7 días con stock: unas 20 por semana, no 20 / 8 semanas
        self.assertGreater(semanal, 15)

    def test_sin_ventas_es_cero(self):
        self.assertEqual(reposicion.demanda(base(), MARTES, [1]), {1: 0})


class Sugerencias(unittest.TestCase):
    def setUp(self):
        self.conn = base()
        # Mayonesa: 10 por semana durante 8 semanas, con stock siempre
        comprar(self.conn, 1, 100, MARTES - timedelta(days=60))
        for semana in range(8):
            vender(self.conn, 1, 10, MARTES - timedelta(days=7 * semana + 1))
        self.conn.execute("UPDATE products SET stock = 5 WHERE id = 1")

    def mayonesa(self):
        return next(i for i in reposicion.sugerencias(self.conn, MARTES)["cucuta"]["items"] if i["id"] == 1)

    def test_pide_en_cajas_completas(self):
        m = self.mayonesa()
        # Llega en 7 días: lo que hay (5) se acaba antes. Hay que cubrir 1,5 semanas: 15 → 24 (cajas de 12)
        self.assertAlmostEqual(m["semanal"], 10, delta=0.5)
        self.assertEqual(m["pedir"], 24)
        self.assertTrue(m["urgente"])

    def test_lo_que_viene_en_camino_se_descuenta(self):
        reposicion.crear_pedido(self.conn, "cucuta", {1: 24}, MARTES + timedelta(days=2), MARTES)
        m = self.mayonesa()
        self.assertEqual(m["camino"], 24)
        self.assertEqual(m["pedir"], 0)
        self.assertFalse(m["urgente"])

    def test_minimo_de_cucuta(self):
        c = reposicion.sugerencias(self.conn, MARTES)["cucuta"]
        self.assertEqual(c["total"], 24 * 14200)
        self.assertTrue(c["alcanza_minimo"])
        self.assertEqual(c["llega"], MARTES + timedelta(days=7))

    def test_medellin_llega_el_dia_del_viaje(self):
        reposicion.poner_viaje(self.conn, MARTES + timedelta(days=2), MARTES)
        s = reposicion.sugerencias(self.conn, MARTES)
        self.assertEqual(s["medellin"]["llega"], MARTES + timedelta(days=2))
        self.assertEqual(s["queso"]["llega"], date(2026, 11, 8))      # el domingo
        with self.assertRaises(ValueError):
            reposicion.poner_viaje(self.conn, MARTES - timedelta(days=1), MARTES)
        # Un viaje que ya pasó no cuenta
        self.assertIsNone(reposicion.viaje_medellin(self.conn, MARTES + timedelta(days=3)))


class Conteo(unittest.TestCase):
    def setUp(self):
        self.conn = base()

    def test_faltante_sobrante_y_vacios(self):
        cid = reposicion.guardar_conteo(self.conn, {1: 2, 2: 25, 4: 8.5}, MARTES, "hermana", 1)
        self.assertEqual(stock(self.conn, 1), 2)       # faltaban 3: pérdida
        self.assertEqual(stock(self.conn, 2), 25)      # sobraban 2
        self.assertEqual(stock(self.conn, 3), 7)       # no se contó: no se toca
        perdida = self.conn.execute("SELECT quantity, total_cost, reason FROM losses").fetchone()
        self.assertEqual(perdida, (3, 3 * 14200, reposicion.MOTIVO_FALTANTE))
        c = reposicion.conteo(self.conn, cid)
        self.assertEqual(c["faltante"], 3 * 14200)
        self.assertEqual(c["sobrante"], 2 * 3000)
        self.assertEqual([f["id"] for f in c["faltan"]], [1])
        self.assertEqual([f["id"] for f in c["sobran"]], [2])
        self.assertEqual([f["id"] for f in c["cuadran"]], [4])
        self.assertTrue(reposicion.conteo_hecho(self.conn, MARTES))

    def test_nada_contado_o_negativo(self):
        with self.assertRaises(ValueError):
            reposicion.guardar_conteo(self.conn, {}, MARTES, "dueño", 1)
        with self.assertRaises(ValueError):
            reposicion.guardar_conteo(self.conn, {1: -1}, MARTES, "dueño", 1)

    def test_aparecio_en_partes(self):
        cid = reposicion.guardar_conteo(self.conn, {1: 2}, MARTES, "dueño", 1)
        reposicion.aparecio(self.conn, cid, 1, 1)
        self.assertEqual(stock(self.conn, 1), 3)
        self.assertEqual(self.conn.execute("SELECT quantity, total_cost FROM losses").fetchone(), (2, 2 * 14200))
        with self.assertRaises(ValueError):
            reposicion.aparecio(self.conn, cid, 1, 5)
        reposicion.aparecio(self.conn, cid, 1, 2)
        self.assertEqual(stock(self.conn, 1), 5)
        self.assertIsNone(self.conn.execute("SELECT 1 FROM losses").fetchone())
        self.assertEqual(reposicion.conteo(self.conn, cid)["sin_explicar"], 0)

    def test_la_semana_del_conteo_empieza_el_martes(self):
        reposicion.guardar_conteo(self.conn, {1: 5}, MARTES, "dueño", 1)
        self.conn.execute("UPDATE conteos SET hecho = '2026-11-02 10:00:00'")       # lunes
        self.assertTrue(reposicion.conteo_hecho(self.conn, date(2026, 11, 2)))
        self.assertFalse(reposicion.conteo_hecho(self.conn, MARTES))

    def test_pistas_quien_suele_llevarlo(self):
        for cid, nombre in ((1, "Ana"), (2, "Beto"), (3, "Caro")):
            self.conn.execute("INSERT INTO clients (id, name) VALUES (?, ?)", (cid, nombre))
        hace = lambda d: (MARTES - timedelta(days=d)).isoformat()      # noqa: E731
        for d in (30, 20, 10):
            vender(self.conn, 1, 1, hace(d), client_id=1)        # Ana: seguido, nada esta semana
            vender(self.conn, 1, 1, hace(d), client_id=2)        # Beto: seguido...
            vender(self.conn, 1, 1, hace(d + 1), client_id=3)    # Caro: seguido
        vender(self.conn, 1, 1, hace(2), client_id=2)            # ...pero ya tiene venta esta semana
        self.conn.execute("INSERT INTO domicilio_envios VALUES (?, 3, ?)", (hace(1), hace(1)))
        self.conn.execute("UPDATE products SET stock = 10 WHERE id = 1")
        cid = reposicion.guardar_conteo(self.conn, {1: 7}, MARTES, "dueño", 1)
        desde = reposicion.desde_para_pistas(self.conn, cid, MARTES)
        self.assertEqual(desde, MARTES - timedelta(days=7))
        nombres = [c["nombre"] for c in reposicion.pistas(self.conn, cid, desde)[1]]
        self.assertEqual(nombres, ["Caro", "Ana"])      # Caro primero: le escribieron para el domicilio


class Pedidos(unittest.TestCase):
    def test_crear_cerrar_y_validar(self):
        conn = base()
        pid = reposicion.crear_pedido(conn, "cucuta", {1: 24, 2: 0}, MARTES + timedelta(days=7), MARTES)
        p = reposicion.pedido(conn, pid)
        self.assertEqual([(i["id"], i["cantidad"]) for i in p["items"]], [(1, 24)])
        self.assertEqual(len(reposicion.en_camino(conn)), 1)
        reposicion.cerrar_pedido(conn, pid, "recibido", "lote1")
        self.assertEqual(reposicion.en_camino(conn), [])
        with self.assertRaises(ValueError):
            reposicion.crear_pedido(conn, "cucuta", {1: 0}, MARTES, MARTES)
        with self.assertRaises(ValueError):
            reposicion.crear_pedido(conn, "otro", {1: 1}, MARTES, MARTES)
        with self.assertRaises(ValueError):
            reposicion.crear_pedido(conn, "cucuta", {1: 1}, MARTES - timedelta(days=1), MARTES)


class Avisos(unittest.TestCase):
    def setUp(self):
        self.conn = base()
        comprar(self.conn, 1, 100, MARTES - timedelta(days=60))
        for semana in range(8):
            vender(self.conn, 1, 10, MARTES - timedelta(days=7 * semana + 1))
            vender(self.conn, 4, 30, MARTES - timedelta(days=7 * semana + 1))
        self.conn.execute("UPDATE products SET stock = 5 WHERE id = 1")
        self.conn.execute("UPDATE products SET stock = 8 WHERE id = 4")

    def claves(self, dia, momento="manana"):
        return [a["clave"].split(":")[0] for a in reposicion.avisos_de_hoy(self.conn, dia, momento)]

    def test_martes_sin_conteo_avisa_el_conteo_y_no_el_pedido(self):
        self.assertEqual(self.claves(MARTES), ["conteo"])
        self.assertEqual(self.claves(MARTES, "tarde"), ["conteo", "viaje"])

    def test_ya_contado_avisa_el_pedido_a_cucuta(self):
        reposicion.guardar_conteo(self.conn, {1: 5}, MARTES, "dueño", 1)
        avisos = reposicion.avisos_de_hoy(self.conn, MARTES, "manana")
        self.assertEqual([a["clave"] for a in avisos], [f"cucuta:{MARTES}"])
        self.assertIn("Mayonesa Mavesa", avisos[0]["cuerpo"])
        reposicion.crear_pedido(self.conn, "cucuta", {1: 24}, MARTES + timedelta(days=7), MARTES)
        self.assertEqual(self.claves(MARTES), [])

    def test_medellin_el_dia_antes_del_viaje(self):
        reposicion.guardar_conteo(self.conn, {1: 5}, MARTES, "dueño", 1)
        reposicion.crear_pedido(self.conn, "cucuta", {1: 24}, MARTES + timedelta(days=7), MARTES)
        vender(self.conn, 3, 14, MARTES - timedelta(days=3))
        reposicion.poner_viaje(self.conn, MARTES + timedelta(days=2), MARTES)
        self.assertEqual(self.claves(MARTES + timedelta(days=1)), ["medellin"])

    def test_domingo_el_queso(self):
        avisos = reposicion.avisos_de_hoy(self.conn, date(2026, 11, 8), "manana")
        queso = next(a for a in avisos if a["clave"].startswith("queso"))
        self.assertIn("kg", queso["cuerpo"])
        self.assertNotIn("queso", self.claves(date(2026, 11, 8), "tarde"))

    def test_pedido_atrasado(self):
        reposicion.crear_pedido(self.conn, "cucuta", {1: 24}, MARTES, MARTES)
        self.assertIn("atraso", self.claves(MARTES + timedelta(days=2)))

    def test_suscripciones_y_enviados(self):
        sub = {"endpoint": "https://fcm.googleapis.com/x", "keys": {"p256dh": "a", "auth": "b"}}
        reposicion.guardar_suscripcion(self.conn, json.dumps(sub), "hermana", "Android")
        reposicion.guardar_suscripcion(self.conn, json.dumps(sub), "hermana", "Android")    # no se repite
        self.assertEqual(len(reposicion.suscripciones(self.conn)), 1)
        with self.assertRaises(ValueError):
            reposicion.guardar_suscripcion(self.conn, '{"endpoint": "http://x"}', "dueño", "")
        self.assertFalse(reposicion.ya_enviado(self.conn, "x"))
        reposicion.marcar_enviado(self.conn, "x")
        reposicion.marcar_enviado(self.conn, "x")
        self.assertTrue(reposicion.ya_enviado(self.conn, "x"))


class Pagina(unittest.TestCase):
    """Las pantallas, con la base de prueba en lugar de la real."""

    def setUp(self):
        import web.app as w
        import web.historial as historial
        self.conn = base()
        self.conn.row_factory = sqlite3.Row
        comprar(self.conn, 1, 100, date.today() - timedelta(days=60))
        vender(self.conn, 1, 30, date.today() - timedelta(days=3))
        for parche in (mock.patch.object(w, "db", return_value=w._ConexionVisita(self.conn)),
                       mock.patch.object(w, "_tablas_reposicion", False),
                       mock.patch.object(historial, "_anotar_visita")):
            parche.start()
            self.addCleanup(parche.stop)
        self.cliente = w.app.test_client()
        with self.cliente.session_transaction() as sesion:
            sesion["ingreso"] = True
            sesion["csrf"] = "c"

    def test_que_pedir(self):
        r = self.cliente.get("/pedidos")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn("Mayonesa Mavesa", html)
        self.assertIn('name="q_1"', html)
        self.assertIn("Todavía no se ha contado", html)

    def test_anotar_un_pedido_y_registrarlo_como_compra(self):
        r = self.cliente.post("/pedidos/cucuta", data={"csrf": "c", "q_1": "24", "q_2": "0"})
        self.assertEqual(r.status_code, 302)
        pedido_id = self.conn.execute("SELECT id FROM pedidos").fetchone()[0]
        r = self.cliente.get(f"/compra/nueva?pedido={pedido_id}")
        html = r.get_data(as_text=True)
        self.assertIn("Viene armada con el pedido a Cúcuta", html)
        self.assertIn('"pedido": ' + str(pedido_id), html)
        with self.cliente.session_transaction() as sesion:
            codigo = sesion["compra_codigo"]
        lote = {"factura": "", "iva": "", "flete": "70000", "pedido": pedido_id,
                "lineas": [{"id": 1, "nombre": "Mayonesa Mavesa", "q": "24", "costo": "14200"}]}
        antes = stock(self.conn, 1)
        r = self.cliente.post("/compra/nueva", data={"csrf": "c", "codigo": codigo, "borrador": json.dumps(lote)})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(stock(self.conn, 1), antes + 24)
        self.assertEqual(self.conn.execute("SELECT estado FROM pedidos").fetchone()[0], "recibido")

    def test_conteo_a_ciegas_y_resultado(self):
        html = self.cliente.get("/conteo").get_data(as_text=True)
        self.assertIn('name="c_1"', html)
        self.assertNotIn("La app decía", html)
        r = self.cliente.post("/conteo", data={"csrf": "c", "c_1": "60", "c_2": ""})
        self.assertEqual(r.status_code, 302)
        html = self.cliente.get(r.location).get_data(as_text=True)
        self.assertIn("La app decía 75, contaron 60", html)      # 5 + 100 comprados - 30 vendidos
        self.assertIn("Apareció", html)

    def test_grupo_en_el_formulario_de_producto(self):
        self.assertIn('value="cucuta" selected', self.cliente.get("/producto/1").get_data(as_text=True))
        r = self.cliente.post("/producto/5", data={"csrf": "c", "nombre": "Frescolita", "precio": "7500",
                                                   "stock": "", "grupo": "medellin", "caja": "6"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(reposicion.grupo_del_producto(self.conn, 5), {"grupo": "medellin", "caja": 6})

    def test_avisos_y_trabajador(self):
        with mock.patch.dict(os.environ, {"VAPID_PUBLICA": "BClave"}):
            html = self.cliente.get("/avisos").get_data(as_text=True)
        self.assertIn('"BClave"', html)
        r = self.cliente.get("/sw.js")
        self.assertEqual(r.mimetype, "application/javascript")
        self.assertIn("showNotification", r.get_data(as_text=True))
        sub = {"endpoint": "https://fcm.googleapis.com/x", "keys": {"p256dh": "a", "auth": "b"}}
        r = self.cliente.post("/avisos/suscribir", data={"csrf": "c", "datos": json.dumps(sub)})
        self.assertEqual(r.status_code, 204)
        self.assertEqual(reposicion.suscripciones(self.conn)[0]["quien"], "dueño")


if __name__ == "__main__":
    unittest.main()
