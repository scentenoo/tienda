"""Qué hacen los clientes en el catálogo: quién entra, qué busca, qué agrega
y si envía el pedido (ver visitas/LEEME.md).

El catálogo avisa cada cosa al recibidor de Cloudflare (visitas/worker.js),
que la guarda en una base de Turso aparte, solo de visitas. Aquí se lee esa
base y se resume para la página privada.

Para saber de quién es cada visita, el enlace que se manda por Domicilio
lleva un código por cliente (?c=…). El código sale del número del cliente
firmado con SECRETO: no dice el nombre, no se puede adivinar el de otro y no
hace falta guardarlo en ninguna parte. Si se cambia SECRETO, los enlaces ya
enviados quedan como visitas sin nombre.
"""
import base64
import hashlib
import hmac
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ZONA = ZoneInfo("America/Bogota")
LARGO_CODIGO = 8
MAXIMO_EVENTOS = 50_000     # por consulta: de sobra para un mes


# ── El código de cada cliente ────────────────────────────────────────────────
def codigo(client_id, secreto):
    """'k7m2q4xa': 8 letras y números, siempre el mismo para el mismo cliente."""
    firma = hmac.new(str(secreto).encode(), f"catalogo:{client_id}".encode(), hashlib.sha256).digest()
    return base64.b32encode(firma).decode().lower()[:LARGO_CODIGO]


def con_codigo(url, client_id, secreto):
    return url + ("&" if "?" in url else "?") + "c=" + codigo(client_id, secreto)


def poner_codigo(texto, url, client_id, secreto):
    """El mensaje con el enlace del catálogo cambiado por el de este cliente.
    Si el mensaje no trae el enlace (lo quitaron al editarlo), queda igual."""
    if not url or url not in texto:
        return texto
    return texto.replace(url, con_codigo(url, client_id, secreto))


def nombres_por_codigo(conn, secreto):
    """{código: (id, nombre)} de todos los clientes."""
    return {codigo(cid, secreto): (cid, nombre)
            for cid, nombre in conn.execute("SELECT id, name FROM clients")}


# ── Leer y resumir ───────────────────────────────────────────────────────────
def eventos(conn, desde):
    """Lo anotado desde ese momento (con zona), del más viejo al más nuevo."""
    desde_utc = desde.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    filas = conn.execute(
        "SELECT momento, visitante, visita, codigo, tipo, dato, valor FROM eventos "
        "WHERE momento >= ? ORDER BY momento LIMIT ?", (desde_utc, MAXIMO_EVENTOS)).fetchall()
    return [{"momento": _hora_local(f[0]), "visitante": f[1], "visita": f[2], "codigo": f[3],
             "tipo": f[4], "dato": f[5], "valor": f[6]} for f in filas]


def _hora_local(texto):
    """'2026-10-26T23:05:01.123Z' (UTC, como lo guarda el recibidor) → hora de Colombia."""
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(ZONA)


def resumen(lista, clientes):
    """Lo que se muestra en la página. clientes: {código: (id, nombre)}."""
    por_visitante = {}
    for e in lista:
        por_visitante.setdefault(e["visitante"], []).append(e)

    def hicieron(*tipos):
        return sum(any(e["tipo"] in tipos for e in es) for es in por_visitante.values())

    embudo = [("Entraron", len(por_visitante)),
              ("Agregaron algo", hicieron("agregar")),
              ("Abrieron el pedido", hicieron("ver_pedido", "enviar")),
              ("Tocaron enviar", hicieron("enviar"))]

    busquedas, sin_resultado, agregados, categorias = Counter(), Counter(), Counter(), Counter()
    for es in por_visitante.values():
        # Cada cosa cuenta una vez por persona: diez búsquedas de lo mismo son una
        busquedas.update({(e["dato"] or "").strip().lower() for e in es if e["tipo"] == "busqueda"} - {""})
        sin_resultado.update({(e["dato"] or "").strip().lower() for e in es
                              if e["tipo"] == "busqueda" and not e["valor"]} - {""})
        agregados.update({e["dato"] for e in es if e["tipo"] == "agregar" and e["dato"]})
        categorias.update({e["dato"] for e in es if e["tipo"] == "categoria" and e["dato"]})

    personas = []
    por_codigo = {}
    for e in lista:
        if e["codigo"] in clientes:
            por_codigo.setdefault(e["codigo"], []).append(e)
    for cod, es in por_codigo.items():
        personas.append(_persona(clientes[cod], es))
    # Primero a quien escribirle: armó el pedido y no lo envió
    orden = {"armo": 0, "miro": 1, "envio": 2}
    personas.sort(key=lambda p: (orden[p["estado"]], -p["ultima"].timestamp()))

    sin_nombre = {v for v, es in por_visitante.items() if not any(e["codigo"] in clientes for e in es)}
    return {"embudo": embudo, "personas": personas, "sin_nombre": len(sin_nombre),
            "con_nombre": len(por_codigo),
            "busquedas": busquedas.most_common(15), "sin_resultado": sin_resultado.most_common(15),
            "agregados": agregados.most_common(15), "categorias": categorias.most_common(10)}


def _persona(cliente, es):
    """Lo que hizo un cliente: cuántas veces entró, qué agregó, si envió."""
    cid, nombre = cliente
    agrego = []
    for e in es:
        if e["tipo"] == "agregar" and e["dato"] and e["dato"] not in agrego:
            agrego.append(e["dato"])
    envios = [e for e in es if e["tipo"] == "enviar"]
    busco = []
    for e in es:
        texto = (e["dato"] or "").strip().lower()
        if e["tipo"] == "busqueda" and texto and texto not in busco:
            busco.append(texto)
    # Lo que tenía en el pedido al final (valor = cuántos quedaron después del toque)
    quedo = {}
    for e in es:
        if e["tipo"] in ("agregar", "quitar") and e["dato"]:
            quedo[e["dato"]] = e["valor"] or 0
        elif e["tipo"] == "vaciar":
            quedo = {}
    estado = "envio" if envios else ("armo" if any(quedo.values()) else "miro")
    segundos = Counter()
    for e in es:
        if e["tipo"] == "salida" and e["valor"]:
            segundos[e["visita"]] = max(segundos[e["visita"]], e["valor"])
    return {"id": cid, "nombre": nombre, "estado": estado,
            "visitas": len({e["visita"] for e in es}), "ultima": max(e["momento"] for e in es),
            "agrego": agrego, "en_pedido": [n for n, c in quedo.items() if c],
            "busco": busco, "total_enviado": envios[-1]["valor"] if envios else None,
            "minutos": round(sum(segundos.values()) / 60)}


def desde_hace(dias, ahora=None):
    """El comienzo de los últimos `dias` días contando hoy: 1 = desde la medianoche."""
    ahora = ahora or datetime.now(ZONA)
    return (ahora - timedelta(days=dias - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
