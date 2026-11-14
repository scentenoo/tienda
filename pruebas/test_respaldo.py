"""Pruebas del respaldo en Google Drive. No usan internet ni la base real:

    python -m unittest pruebas.test_respaldo
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("TURSO_URL", "libsql://prueba")
os.environ.setdefault("TURSO_TOKEN", "prueba")
os.environ.setdefault("CLAVE_HUELLA", "prueba")
os.environ.setdefault("SECRETO", "prueba")

from respaldo import respaldar  # noqa: E402
from utils import respaldo_drive  # noqa: E402


def nube():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE clients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, total_debt REAL);
        CREATE TABLE products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);
        CREATE INDEX idx_nombre ON clients (name);
        INSERT INTO clients (name, total_debt) VALUES ('Ana', 50000), ('Beto', 0);
        INSERT INTO products (name) VALUES ('Queso');
    """)
    return conn


class DriveFalso:
    def __init__(self, archivos=None):
        self.carpetas, self.archivos, self.papelera, self.reemplazos = {}, list(archivos or []), [], []

    def carpeta(self, nombre, padre="root"):
        return self.carpetas.setdefault((nombre, padre), f"{padre}/{nombre}")

    def buscar(self, nombre, padre, carpeta=False):
        return [a for a in self.archivos if a["name"] == nombre and a["padre"] == padre]

    def listar(self, padre):
        return [a for a in self.archivos if a["padre"] == padre]

    def subir(self, nombre, padre, contenido):
        self.archivos.append({"id": f"id{len(self.archivos)}", "name": nombre, "padre": padre})
        return self.archivos[-1]["id"]

    def reemplazar(self, archivo_id, contenido):
        self.reemplazos.append(archivo_id)

    def a_la_papelera(self, archivo_id):
        self.papelera.append(archivo_id)
        self.archivos = [a for a in self.archivos if a["id"] != archivo_id]


class Copia(unittest.TestCase):
    def test_copia_igual(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "copia.db"
            respaldar.copiar(nube(), ruta)
            copia = sqlite3.connect(ruta)
            self.assertEqual(copia.execute("SELECT name, total_debt FROM clients ORDER BY id").fetchall(),
                             [("Ana", 50000), ("Beto", 0)])
            self.assertEqual(copia.execute("SELECT seq FROM sqlite_sequence WHERE name = 'clients'").fetchone(), (2,))
            self.assertTrue(copia.execute("SELECT 1 FROM sqlite_master WHERE name = 'idx_nombre'").fetchone())
            copia.close()

    def test_sin_productos_no_se_sube(self):
        conn = nube()
        conn.execute("DELETE FROM products")
        with tempfile.TemporaryDirectory() as carpeta, self.assertRaises(RuntimeError):
            respaldar.copiar(conn, Path(carpeta) / "copia.db")

    def test_reintenta_si_la_nube_corta(self):
        intentos = []

        def abrir():
            intentos.append(1)
            if len(intentos) == 1:
                rota = mock.Mock()
                rota.execute.side_effect = sqlite3.OperationalError("connection closed")
                return rota
            return nube()
        with mock.patch.object(respaldar.time, "sleep"):
            contenido = respaldar.copia_en_bytes(abrir)
        self.assertEqual(len(intentos), 2)
        self.assertTrue(contenido.startswith(b"SQLite format 3"))


class Subida(unittest.TestCase):
    def test_primera_vez_crea_y_despues_reemplaza(self):
        drive = DriveFalso()
        ahora = datetime(2026, 11, 14, 23, 43, 5)
        nombre, quitados = respaldar.subir(drive, "Emprendimiento", b"x", ahora)
        self.assertEqual((nombre, quitados), ("tienda_backup_2026-11-14_23-43-05.db", 0))
        actual = drive.carpeta("db_actual", drive.carpeta("Emprendimiento"))
        self.assertEqual(len(drive.buscar("tienda.db", actual)), 1)
        respaldar.subir(drive, "Emprendimiento", b"y", ahora + timedelta(days=1))
        self.assertEqual(len(drive.buscar("tienda.db", actual)), 1)      # no se duplica
        self.assertEqual(len(drive.reemplazos), 1)

    def test_limpia_los_viejos(self):
        viejos = [{"id": f"b{i:02}", "name": f"tienda_backup_2026-10-{i:02}_10-00-00.db", "padre": "c"}
                  for i in range(1, 37)] + [{"id": "otro", "name": "notas.txt", "padre": "c"}]
        drive = DriveFalso(viejos)
        self.assertEqual(respaldar.limpiar(drive, "c"), 6)
        self.assertEqual(drive.papelera, ["b01", "b02", "b03", "b04", "b05", "b06"])
        self.assertEqual(respaldar.limpiar(drive, "c"), 0)       # 30: hay holgura


class Estado(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.ahora = datetime(2026, 11, 14, 15, 0, 0)

    def test_sin_tabla(self):
        self.assertEqual(respaldo_drive.estado(self.conn, self.ahora), {"ultimo": None, "en_curso": None})

    def test_pedido_y_terminado(self):
        respaldo_drive.pedir(self.conn, self.ahora)
        self.assertEqual(respaldo_drive.estado(self.conn, self.ahora + timedelta(minutes=1))["en_curso"],
                         self.ahora)
        # Si no llega en 15 minutos, se deja de mostrar «en curso»
        self.assertIsNone(respaldo_drive.estado(self.conn, self.ahora + timedelta(minutes=20))["en_curso"])
        respaldo_drive.anotar(self.conn, self.ahora + timedelta(minutes=2), "desde la página")
        e = respaldo_drive.estado(self.conn, self.ahora + timedelta(minutes=3))
        self.assertIsNone(e["en_curso"])
        self.assertEqual((e["ultimo"]["fecha"], e["ultimo"]["origen"], e["ultimo"]["error"]),
                         (self.ahora + timedelta(minutes=2), "desde la página", ""))


class Boton(unittest.TestCase):
    def setUp(self):
        import web.app as w
        import web.historial as historial
        import web.operaciones as operaciones
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        for parche in (mock.patch.object(w, "db", return_value=w._ConexionVisita(self.conn)),
                       mock.patch.object(operaciones, "db", return_value=w._ConexionVisita(self.conn)),
                       mock.patch.object(historial, "db", return_value=w._ConexionVisita(self.conn)),
                       mock.patch.object(historial, "_anotar_visita"),
                       mock.patch.dict(os.environ, {"CATALOGO_REPO": "a/b", "CATALOGO_TOKEN": "t"})):
            parche.start()
            self.addCleanup(parche.stop)
        self.lanzar = mock.patch.object(operaciones.aviso_catalogo, "_pedir", return_value=True).start()
        self.addCleanup(mock.patch.stopall)
        self.cliente = w.app.test_client()
        with self.cliente.session_transaction() as sesion:
            sesion["ingreso"] = True
            sesion["csrf"] = "c"

    def test_pedir(self):
        r = self.cliente.post("/respaldo", data={"csrf": "c"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.lanzar.call_args.args[2:], ("respaldo.yml", {"origen": "desde la página"}))
        html = self.cliente.get("/mas").get_data(as_text=True)
        self.assertIn("Respaldando en Google Drive", html)
        self.assertIn("Pedido: en uno o dos minutos", html)

    def test_sin_csrf(self):
        self.assertEqual(self.cliente.post("/respaldo", data={}).status_code, 400)
        self.lanzar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
