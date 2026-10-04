"""Las fotos del catálogo desde el formulario de producto (web/fotos_catalogo.py).
GitHub nunca se toca de verdad: urlopen está reemplazado."""
import base64
import io
import json
import os
import sqlite3
import unittest
import urllib.error
from unittest import mock

os.environ.setdefault("TURSO_URL", "libsql://prueba")
os.environ.setdefault("TURSO_TOKEN", "prueba")
os.environ.setdefault("CLAVE_HUELLA", "prueba")
os.environ.setdefault("SECRETO", "prueba")

from web import fotos_catalogo  # noqa: E402

ENTORNO = {"CATALOGO_REPO": "scentenoo/tienda", "CATALOGO_TOKEN": "secreto"}
JPEG = b"\xff\xd8\xff\xe0" + b"x" * 100
URL = "https://api.github.com/repos/scentenoo/tienda/contents/catalogo/fotos/29.jpg"


class _Respuesta(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def _respuesta(datos):
    return _Respuesta(json.dumps(datos).encode())


class FotosEnGitHub(unittest.TestCase):
    def setUp(self):
        parche = mock.patch.dict(os.environ, ENTORNO)
        parche.start()
        self.addCleanup(parche.stop)

    def test_sin_configurar_no_aparece(self):
        with mock.patch.dict(os.environ, {"CATALOGO_REPO": "", "CATALOGO_TOKEN": ""}):
            self.assertFalse(fotos_catalogo.configurado())
        self.assertTrue(fotos_catalogo.configurado())

    def test_subir_una_nueva(self):
        with mock.patch("urllib.request.urlopen",
                        side_effect=[urllib.error.HTTPError(URL, 404, "", {}, None), _respuesta({})]) as abrir:
            fotos_catalogo.subir(29, JPEG, "Queso Costeño")
        consulta, subida = [c.args[0] for c in abrir.call_args_list]
        self.assertEqual(consulta.full_url, URL + "?ref=main")
        self.assertEqual(subida.full_url, URL)
        self.assertEqual(subida.get_method(), "PUT")
        cuerpo = json.loads(subida.data)
        self.assertEqual(base64.b64decode(cuerpo["content"]), JPEG)
        self.assertEqual(cuerpo["branch"], "main")
        self.assertNotIn("sha", cuerpo)
        self.assertIn("Queso Costeño", cuerpo["message"])

    def test_cambiar_una_que_ya_estaba(self):
        with mock.patch("urllib.request.urlopen",
                        side_effect=[_respuesta({"sha": "abc"}), _respuesta({})]) as abrir:
            fotos_catalogo.subir(29, JPEG)
        self.assertEqual(json.loads(abrir.call_args_list[1].args[0].data)["sha"], "abc")

    def test_no_sube_lo_que_no_es_una_foto(self):
        with mock.patch("urllib.request.urlopen") as abrir:
            for contenido in (b"", b"<script>", b"\xff\xd8\xff" + b"x" * fotos_catalogo.TAMANO_MAXIMO):
                with self.assertRaises(fotos_catalogo.ErrorFoto):
                    fotos_catalogo.subir(29, contenido)
        abrir.assert_not_called()

    def test_quitar(self):
        with mock.patch("urllib.request.urlopen",
                        side_effect=[_respuesta({"sha": "abc"}), _respuesta({})]) as abrir:
            fotos_catalogo.quitar(29)
        borrado = abrir.call_args_list[1].args[0]
        self.assertEqual(borrado.get_method(), "DELETE")
        self.assertEqual(json.loads(borrado.data)["sha"], "abc")

    def test_quitar_sin_foto_no_hace_nada(self):
        with mock.patch("urllib.request.urlopen",
                        side_effect=[urllib.error.HTTPError(URL, 404, "", {}, None)]) as abrir:
            fotos_catalogo.quitar(29)
        self.assertEqual(abrir.call_count, 1)

    def test_consultar_la_devuelve_para_mostrarla(self):
        contenido = base64.encodebytes(JPEG).decode()      # GitHub la manda con saltos de línea
        with mock.patch("urllib.request.urlopen",
                        return_value=_respuesta({"encoding": "base64", "content": contenido})):
            imagen = fotos_catalogo.consultar(29)
        self.assertEqual(imagen, "data:image/jpeg;base64," + base64.b64encode(JPEG).decode())

    def test_token_sin_permiso_lo_dice_claro(self):
        with mock.patch("urllib.request.urlopen",
                        side_effect=urllib.error.HTTPError(URL, 403, "", {}, None)), \
                self.assertRaisesRegex(fotos_catalogo.ErrorFoto, "Contents"):
            fotos_catalogo.consultar(29)


class RutasDeLaFoto(unittest.TestCase):
    def setUp(self):
        from web.app import app
        import web.historial as historial
        import web.operaciones as operaciones
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO products (id, name) VALUES (29, 'Queso Costeño')")
        for parche in (mock.patch.dict(os.environ, ENTORNO),
                       mock.patch.object(operaciones, "db", return_value=conn),
                       mock.patch.object(historial, "_anotar_visita")):     # el historial va a la base real
            parche.start()
            self.addCleanup(parche.stop)
        self.cliente = app.test_client()
        with self.cliente.session_transaction() as sesion:
            sesion["ingreso"] = True
            sesion["csrf"] = "c"

    def test_subir(self):
        with mock.patch.object(fotos_catalogo, "subir") as subir:
            r = self.cliente.post("/producto/29/foto",
                                  data={"csrf": "c", "foto": (io.BytesIO(JPEG), "foto.jpg")})
        self.assertEqual(r.get_json(), {"ok": True})
        subir.assert_called_once_with(29, JPEG, "Queso Costeño")

    def test_el_error_llega_como_mensaje(self):
        with mock.patch.object(fotos_catalogo, "quitar",
                               side_effect=fotos_catalogo.ErrorFoto("No se pudo")):
            r = self.cliente.post("/producto/29/foto/quitar", data={"csrf": "c"})
        self.assertEqual((r.status_code, r.get_json()), (400, {"error": "No se pudo"}))

    def test_sin_csrf_no_hace_nada(self):
        with mock.patch.object(fotos_catalogo, "subir") as subir:
            r = self.cliente.post("/producto/29/foto", data={"foto": (io.BytesIO(JPEG), "f.jpg")})
        self.assertEqual(r.status_code, 400)
        subir.assert_not_called()

    def test_producto_que_no_existe(self):
        r = self.cliente.post("/producto/999/foto/quitar", data={"csrf": "c"})
        self.assertEqual(r.status_code, 404)

    def test_sin_ingresar_no_entra(self):
        with self.cliente.session_transaction() as sesion:
            sesion.clear()
        r = self.cliente.post("/producto/29/foto/quitar", data={"csrf": "c"})
        self.assertEqual(r.status_code, 302)

    def test_sin_configurar_no_existe(self):
        with mock.patch.dict(os.environ, {"CATALOGO_REPO": "", "CATALOGO_TOKEN": ""}):
            r = self.cliente.post("/producto/29/foto/quitar", data={"csrf": "c"})
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
