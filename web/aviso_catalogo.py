"""Avisar a GitHub que regenere el catálogo de clientes ya, sin esperar la
media hora, cuando se crea, cambia o borra un producto.

Es opcional. Solo hace algo si la página tiene estas dos variables:
  CATALOGO_REPO    el repositorio, por ejemplo scentenoo/tienda
  CATALOGO_TOKEN   un token de GitHub que solo pueda lanzar tareas de ese
                   repositorio (fine-grained, permiso "Actions: Read and write")

Nunca detiene ni daña lo que se estaba guardando: va en un hilo aparte y, si
falla, queda anotado en el registro y el catálogo se actualiza igual en la
siguiente media hora.

También se puede pedir a mano, con el botón de la pestaña Más. El mismo
token sirve para lanzar el respaldo en Google Drive (lanzar_tarea).
"""
import json
import logging
import os
import threading
import urllib.request

ARCHIVO_DE_LA_TAREA = "catalogo.yml"
RAMA = "main"
registro = logging.getLogger(__name__)


def configurado():
    return bool(os.environ.get("CATALOGO_REPO") and os.environ.get("CATALOGO_TOKEN"))


def _pedir(repo, token, archivo=ARCHIVO_DE_LA_TAREA, entradas=None):
    """True si GitHub recibió el aviso."""
    cuerpo = {"ref": RAMA, **({"inputs": entradas} if entradas else {})}
    solicitud = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/workflows/{archivo}/dispatches",
        data=json.dumps(cuerpo).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "charcuteria-hye"})
    try:
        urllib.request.urlopen(solicitud, timeout=10).close()
        return True
    except Exception:
        registro.exception("No se pudo lanzar la tarea %s en GitHub", archivo)
        return False


def avisar():
    """Devuelve el hilo que hace el aviso, o None si no está configurado."""
    if not configurado():
        return None
    repo, token = os.environ["CATALOGO_REPO"], os.environ["CATALOGO_TOKEN"]
    hilo = threading.Thread(target=_pedir, args=(repo, token), daemon=True)
    hilo.start()
    return hilo


def actualizar_ya():
    """El botón «Actualizar el catálogo»: espera la respuesta de GitHub para
    poder decir si quedó pedido. True si GitHub lo recibió."""
    return configurado() and _pedir(os.environ["CATALOGO_REPO"], os.environ["CATALOGO_TOKEN"])


def lanzar_tarea(archivo, entradas=None):
    """Lanza otra tarea de GitHub del repositorio y espera la respuesta.
    True si GitHub la recibió."""
    return configurado() and _pedir(os.environ["CATALOGO_REPO"], os.environ["CATALOGO_TOKEN"],
                                    archivo, entradas)
