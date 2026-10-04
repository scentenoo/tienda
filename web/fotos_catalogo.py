"""Las fotos del catálogo de clientes, desde el formulario de producto.

Las fotos viven en el repositorio, en catalogo/fotos/<id>.jpg (el disco de
Render se borra en cada despliegue). Subir o quitar una es un cambio en
GitHub, y ese cambio lanza solo la tarea que publica el catálogo.

Usa las mismas variables que web/aviso_catalogo.py; el token necesita,
además de "Actions", el permiso "Contents: Read and write". Sin ellas, el
formulario no muestra la sección de la foto.

El teléfono ya manda la foto recortada y achicada (un JPEG pequeño); aquí
solo se revisa que lo sea.
"""
import base64
import json
import os
import urllib.error
import urllib.request

CARPETA = "catalogo/fotos"
RAMA = "main"
TAMANO_MAXIMO = 1_500_000      # bytes; las del teléfono llegan alrededor de 100 KB


class ErrorFoto(Exception):
    """Algo que se le puede decir tal cual a quien usa la página."""


def configurado():
    return bool(os.environ.get("CATALOGO_REPO") and os.environ.get("CATALOGO_TOKEN"))


def _ruta(product_id):
    return f"{CARPETA}/{int(product_id)}.jpg"


def _pedir(metodo, product_id, cuerpo=None):
    """(código HTTP, respuesta en JSON) de la API de contenidos de GitHub."""
    repo, token = os.environ["CATALOGO_REPO"], os.environ["CATALOGO_TOKEN"]
    url = f"https://api.github.com/repos/{repo}/contents/{_ruta(product_id)}"
    if metodo == "GET":
        url += f"?ref={RAMA}"
    solicitud = urllib.request.Request(
        url, method=metodo, data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "charcuteria-hye"})
    try:
        with urllib.request.urlopen(solicitud, timeout=15) as respuesta:
            return respuesta.status, json.loads(respuesta.read() or b"{}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return 404, {}
        if e.code in (401, 403):
            raise ErrorFoto("GitHub no dejó cambiar la foto: revise que el token tenga el "
                            "permiso «Contents: Read and write» y que no esté vencido.") from e
        raise ErrorFoto(f"GitHub respondió con un error ({e.code}). Intente de nuevo.") from e
    except (urllib.error.URLError, OSError) as e:
        raise ErrorFoto("No se pudo hablar con GitHub. Revise la conexión e intente de nuevo.") from e


def consultar(product_id):
    """La foto actual como data: URI para mostrarla en el formulario (la
    política de seguridad de la página solo deja imágenes propias o data:),
    o None si el producto no tiene."""
    codigo, datos = _pedir("GET", product_id)
    if codigo == 404 or datos.get("encoding") != "base64":
        return None
    return "data:image/jpeg;base64," + datos["content"].replace("\n", "")


def _sha_actual(product_id):
    codigo, datos = _pedir("GET", product_id)
    return None if codigo == 404 else datos.get("sha")


def subir(product_id, contenido, nombre_producto=""):
    if not contenido:
        raise ErrorFoto("No llegó ninguna foto.")
    if len(contenido) > TAMANO_MAXIMO:
        raise ErrorFoto("La foto es demasiado grande.")
    if not contenido.startswith(b"\xff\xd8\xff"):
        raise ErrorFoto("Eso no parece una foto (se esperaba un JPEG).")
    cuerpo = {"message": f"Foto del catálogo: {nombre_producto or product_id}".strip(),
              "content": base64.b64encode(contenido).decode(), "branch": RAMA}
    sha = _sha_actual(product_id)
    if sha:
        cuerpo["sha"] = sha         # reemplaza la que había
    _pedir("PUT", product_id, cuerpo)


def quitar(product_id, nombre_producto=""):
    """Borra la foto; si no había, no hace nada."""
    sha = _sha_actual(product_id)
    if sha:
        _pedir("DELETE", product_id, {"message": f"Quitar foto del catálogo: {nombre_producto or product_id}",
                                      "sha": sha, "branch": RAMA})
