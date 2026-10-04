"""Pruebas del catálogo de clientes. No usan internet ni la base real:

    python -m unittest pruebas.test_catalogo
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "herramientas"))

import preparar_catalogo  # noqa: E402
from catalogo import generar  # noqa: E402
from servicios import catalogo as reglas  # noqa: E402
from servicios.inventario import crear_producto, editar_producto  # noqa: E402
from web import aviso_catalogo  # noqa: E402

HOY = date(2026, 10, 4)

ESQUEMA_VIEJO = """
    CREATE TABLE products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
        price REAL NOT NULL, stock INTEGER DEFAULT 0, cost_price REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL NOT NULL,
        date TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE purchase_details (id INTEGER PRIMARY KEY AUTOINCREMENT, purchase_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL, quantity INTEGER NOT NULL, unit_price REAL NOT NULL,
        subtotal REAL NOT NULL);
    CREATE TABLE sales (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE sale_details (id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL, quantity REAL NOT NULL);
"""


def base(con_columnas=True):
    conn = sqlite3.connect(":memory:")
    conn.executescript(ESQUEMA_VIEJO)
    if con_columnas:
        conn.execute("ALTER TABLE products ADD COLUMN categoria TEXT")
        conn.execute("ALTER TABLE products ADD COLUMN catalogo TEXT DEFAULT 'auto'")
    return conn


def producto(conn, nombre, precio=10000, stock=0, categoria=None, catalogo="auto", compra=None, costo=7777):
    cursor = conn.execute(
        "INSERT INTO products (name, price, stock, cost_price, categoria, catalogo) VALUES (?, ?, ?, ?, ?, ?)",
        (nombre, precio, stock, costo, categoria, catalogo))
    if compra:
        compra_id = conn.execute("INSERT INTO purchases (total, date) VALUES (1, ?)",
                                 (compra + " 10:00:00",)).lastrowid
        conn.execute("INSERT INTO purchase_details (purchase_id, product_id, quantity, unit_price, subtotal) "
                     "VALUES (?, ?, 1, 1, 1)", (compra_id, cursor.lastrowid))
    return cursor.lastrowid


def venta(conn, dia, *product_ids):
    """Una venta del día con esos productos (uno por renglón)."""
    sale_id = conn.execute("INSERT INTO sales (total, created_at) VALUES (1, ?)",
                           (dia + " 10:00:00",)).lastrowid
    for product_id in product_ids:
        conn.execute("INSERT INTO sale_details (sale_id, product_id, quantity) VALUES (?, ?, 1)",
                     (sale_id, product_id))


def visibles(conn):
    return {p["nombre"]: p["estado"] for p in reglas.productos_visibles(conn, HOY)}


class ReglaDeVisibilidad(unittest.TestCase):
    def test_con_stock_aparece_segun_la_cantidad(self):
        conn = base()
        producto(conn, "Mucho", stock=6)
        producto(conn, "Poco", stock=5)
        self.assertEqual(visibles(conn), {"Mucho": "disponible", "Poco": "pocas"})

    def test_agotado_y_comprado_hace_poco_va_por_encargo(self):
        conn = base()
        producto(conn, "Reciente", stock=0, compra="2026-09-26")
        producto(conn, "En el límite", stock=0, compra="2026-08-04")      # justo 2 meses
        self.assertEqual(visibles(conn), {"Reciente": "encargo", "En el límite": "encargo"})

    def test_agotado_y_sin_comprar_hace_mas_de_dos_meses_se_oculta(self):
        conn = base()
        producto(conn, "Viejo", stock=0, compra="2026-08-03")
        producto(conn, "Nunca comprado", stock=0)
        self.assertEqual(visibles(conn), {})

    def test_cuenta_la_compra_mas_reciente(self):
        conn = base()
        i = producto(conn, "Dos compras", stock=0, compra="2026-03-01")
        compra_id = conn.execute("INSERT INTO purchases (total, date) VALUES (1, '2026-09-30 09:00:00')").lastrowid
        conn.execute("INSERT INTO purchase_details (purchase_id, product_id, quantity, unit_price, subtotal) "
                     "VALUES (?, ?, 1, 1, 1)", (compra_id, i))
        self.assertEqual(visibles(conn), {"Dos compras": "encargo"})

    def test_siempre_aparece_aunque_lleve_mucho_agotado(self):
        conn = base()
        producto(conn, "Bajo pedido", stock=0, catalogo="siempre")
        self.assertEqual(visibles(conn), {"Bajo pedido": "encargo"})

    def test_nunca_no_aparece_aunque_haya_stock(self):
        conn = base()
        producto(conn, "Ajuste", stock=50, catalogo="nunca", compra="2026-10-01")
        self.assertEqual(visibles(conn), {})

    def test_sin_precio_no_aparece(self):
        conn = base()
        producto(conn, "Regalo", precio=0, stock=9)
        self.assertEqual(visibles(conn), {})

    def test_modo_vacio_cuenta_como_automatico(self):
        conn = base()
        producto(conn, "Sin modo", stock=3, catalogo=None)
        self.assertEqual(visibles(conn), {"Sin modo": "pocas"})

    def test_no_sale_ni_el_costo_ni_la_cantidad(self):
        conn = base()
        producto(conn, "Queso", precio=30000, stock=14, costo=21000)
        (p,) = reglas.productos_visibles(conn, HOY)
        self.assertEqual(set(p), {"id", "nombre", "precio", "categoria", "estado", "medio_kilo"})

    def test_solo_el_queso_costeno_se_pide_por_medio_kilo(self):
        conn = base()
        for i in range(1, 30):      # el Queso Costeño es el id 29
            producto(conn, f"Producto {i}", stock=10)
        medio = {p["id"] for p in reglas.productos_visibles(conn, HOY) if p["medio_kilo"]}
        self.assertEqual(medio, {29})


class Secciones(unittest.TestCase):
    def test_orden_de_categorias_y_lo_de_encargo_al_final(self):
        conn = base()
        producto(conn, "Anis", stock=9, categoria="licores")
        producto(conn, "Zeta queso", stock=9, categoria="quesos")
        producto(conn, "Alfa queso", stock=0, categoria="quesos", compra="2026-09-30")
        producto(conn, "Raro", stock=9, categoria="no existe")
        producto(conn, "Sin categoría", stock=9)
        s = reglas.secciones(reglas.productos_visibles(conn, HOY))
        self.assertEqual([x["clave"] for x in s], ["quesos", "licores", "otros"])
        self.assertEqual([p["nombre"] for p in s[0]["productos"]], ["Zeta queso", "Alfa queso"])
        self.assertEqual([p["nombre"] for p in s[2]["productos"]], ["Raro", "Sin categoría"])
        self.assertTrue(s[1]["leyenda_licor"])
        self.assertFalse(s[0]["leyenda_licor"])


    def test_dentro_de_cada_categoria_primero_lo_que_mas_se_vende(self):
        conn = base()
        poco = producto(conn, "Alfa", stock=9, categoria="quesos")
        mucho = producto(conn, "Zeta", stock=9, categoria="quesos")
        producto(conn, "Beta sin ventas", stock=9, categoria="quesos")
        viejo = producto(conn, "Gama", stock=9, categoria="quesos")
        encargo = producto(conn, "Omega", stock=0, categoria="quesos", compra="2026-09-30")
        venta(conn, "2026-09-20", mucho, poco)
        venta(conn, "2026-09-21", mucho)
        venta(conn, "2026-10-01", encargo)
        for _ in range(5):                      # muchas, pero hace más de 90 días
            venta(conn, "2026-05-01", viejo)
        (s,) = reglas.secciones(reglas.productos_visibles(conn, HOY))
        self.assertEqual([p["nombre"] for p in s["productos"]],
                         ["Zeta", "Alfa", "Beta sin ventas", "Gama", "Omega"])


class Inventario(unittest.TestCase):
    def test_crear_y_editar_con_los_campos_del_catalogo(self):
        conn = base()
        i = crear_producto(conn, "Ponche Crema", 70000, 0, categoria="licores", catalogo="siempre")
        self.assertEqual(reglas.opciones_del_producto(conn, i), {"categoria": "licores", "catalogo": "siempre"})
        editar_producto(conn, i, "Ponche Crema", 72000, categoria="bebidas")
        self.assertEqual(reglas.opciones_del_producto(conn, i), {"categoria": "bebidas", "catalogo": "siempre"})
        self.assertEqual(conn.execute("SELECT price, stock FROM products WHERE id = ?", (i,)).fetchone(), (72000, 0))

    def test_valores_raros_caen_en_lo_de_siempre(self):
        conn = base()
        i = crear_producto(conn, "X", 1000, 1, categoria="Quezos", catalogo="a veces")
        self.assertEqual(reglas.opciones_del_producto(conn, i), {"categoria": "otros", "catalogo": "auto"})

    def test_sin_esos_campos_funciona_en_una_base_sin_las_columnas(self):
        conn = base(con_columnas=False)
        self.assertFalse(reglas.tiene_columnas(conn))
        i = crear_producto(conn, "Viejo", 5000, 2)
        editar_producto(conn, i, "Viejo", 6000)
        editar_producto(conn, i, "Viejo", 6000, 7)
        self.assertEqual(conn.execute("SELECT name, price, stock FROM products").fetchall(), [("Viejo", 6000, 7)])
        self.assertIsNone(reglas.opciones_del_producto(conn, i))


class PrepararLaBase(unittest.TestCase):
    def test_primero_muestra_y_solo_aplica_cuando_se_pide(self):
        conn = base(con_columnas=False)
        for nombre in ("Queso Costeño 1k", "ajuste", "Producto nuevo"):
            conn.execute("INSERT INTO products (name, price, stock) VALUES (?, 1000, 1)", (nombre,))

        informe = preparar_catalogo.preparar(conn, aplicar=False)
        self.assertFalse(reglas.tiene_columnas(conn))
        self.assertIn("No se cambió nada", informe[-1])

        preparar_catalogo.preparar(conn, aplicar=True)
        self.assertEqual(conn.execute("SELECT name, categoria, catalogo FROM products ORDER BY id").fetchall(),
                         [("Queso Costeño 1k", "quesos", "auto"), ("ajuste", None, "nunca"),
                          ("Producto nuevo", None, "auto")])

    def test_repetirlo_no_cambia_lo_que_se_puso_a_mano(self):
        conn = base()
        conn.execute("INSERT INTO products (name, price, categoria, catalogo) VALUES ('Samba', 1, 'despensa', 'siempre')")
        preparar_catalogo.preparar(conn, aplicar=True)
        self.assertEqual(conn.execute("SELECT categoria, catalogo FROM products").fetchone(), ("despensa", "siempre"))

    def test_la_lista_no_repite_productos_ni_inventa_categorias(self):
        nombres = [n.lower() for lista in preparar_catalogo.PRODUCTOS.values() for n in lista]
        self.assertEqual(len(nombres), len(set(nombres)))
        self.assertLessEqual(set(preparar_catalogo.PRODUCTOS), {clave for clave, _ in reglas.CATEGORIAS})


class Pagina(unittest.TestCase):
    AHORA = datetime(2026, 10, 4, 13, 5, tzinfo=generar.ZONA)

    def test_la_pagina_lleva_lo_publico_y_nada_mas(self):
        conn = base()
        producto(conn, "Queso <b>Costeño</b> \"1k\"", precio=30000, stock=14, categoria="quesos", costo=21987)
        producto(conn, "Ajuste", precio=20000, stock=3, catalogo="nunca")
        html = generar.construir(conn, "313 701 3735", "https://ejemplo.github.io/tienda/", self.AHORA)
        self.assertIn("Queso &lt;b&gt;Costeño&lt;/b&gt;", html)      # el nombre va escapado
        self.assertNotIn("<b>Costeño", html)
        self.assertIn("$30.000", html)
        self.assertIn('data-whatsapp="573137013735"', html)
        self.assertIn("Actualizado el 4 de octubre a la 1:05 p. m.", html)
        self.assertIn('content="https://ejemplo.github.io/tienda/logo-he.png"', html)
        self.assertNotIn("21987", html)                              # ni el costo
        self.assertNotIn("Ajuste", html)
        self.assertNotIn('class="foto"', html)                       # sin fotos, sin recuadros

    def test_con_fotos_el_que_no_tiene_sale_con_su_inicial(self):
        conn = base()
        a = producto(conn, "Anis", stock=9, categoria="licores")
        producto(conn, "Cacique", stock=9, categoria="licores")
        html = generar.construir(conn, "3137013735", ahora=self.AHORA, fotos={a: f"{a}.webp"})
        self.assertIn(f'<img src="fotos/{a}.webp"', html)
        self.assertIn('<span aria-hidden="true">C</span>', html)
        self.assertIn("Prohíbese el expendio de bebidas embriagantes", html)

    def test_sin_productos_no_se_publica_un_catalogo_vacio(self):
        with self.assertRaises(SystemExit):
            generar.construir(base(), "3137013735", ahora=self.AHORA)

    def test_sin_numero_de_whatsapp_no_se_genera(self):
        conn = base()
        producto(conn, "Anis", stock=9)
        with self.assertRaises(SystemExit):
            generar.construir(conn, "", ahora=self.AHORA)

    def test_genera_los_archivos_del_sitio(self):
        conn = base()
        producto(conn, "Anis", stock=9)
        with tempfile.TemporaryDirectory() as carpeta:
            generar.generar(carpeta, conn, "3137013735", ahora=self.AHORA)
            self.assertEqual(sorted(os.listdir(carpeta)), ["icono-192.png", "index.html", "logo-he.png"])

    def test_solo_cuentan_las_fotos_con_el_id_como_nombre(self):
        with tempfile.TemporaryDirectory() as carpeta:
            for nombre in ("29.jpg", "42.WEBP", "queso.jpg", "LEEME.txt"):
                (Path(carpeta) / nombre).write_bytes(b"x")
            self.assertEqual(generar.fotos_disponibles(Path(carpeta)), {29: "29.jpg", 42: "42.WEBP"})


class AvisoAlCatalogo(unittest.TestCase):
    def test_sin_configurar_no_hace_nada(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(aviso_catalogo.avisar())

    def test_configurado_lanza_la_tarea_de_github(self):
        entorno = {"CATALOGO_REPO": "scentenoo/tienda", "CATALOGO_TOKEN": "secreto"}
        with mock.patch.dict(os.environ, entorno, clear=True), \
                mock.patch("urllib.request.urlopen") as abrir:
            aviso_catalogo.avisar().join(5)
        (solicitud,), opciones = abrir.call_args
        self.assertEqual(solicitud.full_url,
                         "https://api.github.com/repos/scentenoo/tienda/actions/workflows/catalogo.yml/dispatches")
        self.assertEqual(solicitud.get_method(), "POST")
        self.assertEqual(solicitud.data, b'{"ref": "main"}')
        self.assertEqual(solicitud.get_header("Authorization"), "Bearer secreto")
        self.assertEqual(opciones["timeout"], 10)

    def test_si_github_falla_no_se_rompe_nada(self):
        entorno = {"CATALOGO_REPO": "scentenoo/tienda", "CATALOGO_TOKEN": "secreto"}
        with mock.patch.dict(os.environ, entorno, clear=True), \
                mock.patch("urllib.request.urlopen", side_effect=OSError("sin internet")), \
                self.assertLogs(aviso_catalogo.registro, level="ERROR"):
            aviso_catalogo.avisar().join(5)


if __name__ == "__main__":
    unittest.main()
