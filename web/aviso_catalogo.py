"""Avisar a GitHub que regenere el catálogo de clientes ya, sin esperar la
media hora, cuando se crea, cambia o borra un producto.

Es opcional. Solo hace algo si la página tiene estas dos variables:
  CATALOGO_REPO    el repositorio, por ejemplo scentenoo/tienda
  CATALOGO_TOKEN   un token de GitHub que solo pueda lanzar tareas de ese
                   repositorio (fine-grained, permiso "Actions: Read and write")

Nunca detiene ni daña lo que se estaba guardando: va en un hilo aparte y, si
falla, queda anotado en el registro y el catálogo se actualiza igual en la
siguiente media hora.
"""
import json
import logging
import os
import threading
import urllib.request

ARCHIVO_DE_LA_TAREA = "catalogo.yml"
RAMA = "main"
registro = logging.getLogger(__name__)


def _pedir(repo, token):
    solicitud = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/workflows/{ARCHIVO_DE_LA_TAREA}/dispatches",
        data=json.dumps({"ref": RAMA}).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "charcuteria-hye"})
    try:
        urllib.request.urlopen(solicitud, timeout=10).close()
    except Exception:
        registro.exception("No se pudo avisar al catálogo; se actualizará en la siguiente media hora")


def avisar():
    """Devuelve el hilo que hace el aviso, o None si no está configurado."""
    repo, token = os.environ.get("CATALOGO_REPO"), os.environ.get("CATALOGO_TOKEN")
    if not (repo and token):
        return None
    hilo = threading.Thread(target=_pedir, args=(repo, token), daemon=True)
    hilo.start()
    return hilo
