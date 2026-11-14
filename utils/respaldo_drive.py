"""Lo que se sabe del respaldo en Google Drive que hace GitHub (respaldo/):
cuándo fue el último, si salió bien y si hay uno pedido desde la página.

Se guarda en la tabla ajustes, la misma de los cobros:
  respaldo_ultimo   {"fecha": "AAAA-MM-DD HH:MM:SS", "origen": "...", "error": "..." o ""}
  respaldo_pedido   "AAAA-MM-DD HH:MM:SS": cuándo se tocó el botón
Como el resto de servicios, nada aquí hace commit.
"""
import json
import sqlite3
from datetime import datetime

FORMATO = "%Y-%m-%d %H:%M:%S"
# Si lo pedido no llega en este tiempo, se deja de mostrar «en curso»
MINUTOS_EN_CURSO = 15


def _preparar(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS ajustes (clave TEXT PRIMARY KEY, valor TEXT)")


def _poner(conn, clave, valor):
    _preparar(conn)
    conn.execute("INSERT INTO ajustes (clave, valor) VALUES (?, ?) "
                 "ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor", (clave, valor))


def anotar(conn, ahora, origen, error=""):
    """Lo llama el respaldo al terminar, haya salido bien o no."""
    _poner(conn, "respaldo_ultimo", json.dumps(
        {"fecha": ahora.strftime(FORMATO), "origen": origen, "error": error}, ensure_ascii=False))


def pedir(conn, ahora):
    """Lo llama la página al tocar el botón."""
    _poner(conn, "respaldo_pedido", ahora.strftime(FORMATO))


def estado(conn, ahora):
    """{"ultimo": {"fecha": datetime, "origen", "error"} o None,
        "en_curso": datetime en que se pidió, o None}. Una sola consulta: va
    en la pestaña Más."""
    try:
        valores = dict(tuple(f) for f in conn.execute(
            "SELECT clave, valor FROM ajustes WHERE clave IN ('respaldo_ultimo', 'respaldo_pedido')"
        ).fetchall())
    except sqlite3.OperationalError:     # todavía no existe la tabla
        valores = {}
    ultimo = None
    try:
        datos = json.loads(valores.get("respaldo_ultimo") or "null")
        if datos:
            ultimo = {**datos, "fecha": datetime.strptime(datos["fecha"], FORMATO)}
    except (ValueError, KeyError, TypeError):
        pass
    en_curso = None
    try:
        pedido = datetime.strptime(valores.get("respaldo_pedido") or "", FORMATO)
        if ((ultimo is None or pedido > ultimo["fecha"])
                and (ahora - pedido).total_seconds() < MINUTOS_EN_CURSO * 60):
            en_curso = pedido
    except ValueError:
        pass
    return {"ultimo": ultimo, "en_curso": en_curso}
