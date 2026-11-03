"""Qué pedir, el conteo del martes, los pedidos en camino y los avisos al
celular (la regla está en utils/reposicion.py). Se registran en la misma app
de web/app.py, que las importa al final.

Los avisos son notificaciones del navegador (Web Push). Aquí solo se guarda
la suscripción de cada celular; los manda la tarea de GitHub de
.github/workflows/avisos.yml (ver avisos/LEEME.md). Necesitan la variable
VAPID_PUBLICA; sin ella la página de avisos dice que faltan por configurar."""
import json
import logging
import os
import urllib.request
from datetime import date

from flask import abort, redirect, render_template, request, session, url_for

from utils import reposicion
from web.app import (_db_reposicion, _leer_decimal, _revisar_csrf, _usuario_admin, app,
                     requiere_ingreso)

registro = logging.getLogger(__name__)


def _quien():
    return "hermana" if session.get("sin_gastos") else "dueño"


def _fecha(texto):
    try:
        return date.fromisoformat(texto or "")
    except ValueError:
        return None


# ── Qué pedir ────────────────────────────────────────────────────────────────
@app.get("/pedidos")
@requiere_ingreso
def pedidos_pagina():
    hoy = date.today()
    conn = _db_reposicion()
    grupos = reposicion.sugerencias(conn, hoy)
    sin_grupo = conn.execute("SELECT COUNT(*) FROM products WHERE (grupo IS NULL OR grupo = '') "
                             "AND price > 0 AND name != 'Ajuste'").fetchone()[0]
    return render_template(
        "pedidos.html", grupos=grupos, hoy=hoy, dia_corto=reposicion.dia_corto,
        ultimo=reposicion.ultimo_conteo(conn), conteo_hecho=reposicion.conteo_hecho(conn, hoy),
        en_camino=reposicion.en_camino(conn), sin_grupo=sin_grupo,
        aviso=session.pop("aviso_pedidos", None), error=session.pop("error_pedidos", None))


@app.post("/pedidos/<grupo>")
@requiere_ingreso
def pedido_crear(grupo):
    _revisar_csrf()
    if grupo not in reposicion.GRUPOS:
        abort(404)
    hoy = date.today()
    conn = _db_reposicion()
    cantidades = {}
    for clave, valor in request.form.items():
        if clave.startswith("q_") and clave[2:].isdigit():
            cantidades[int(clave[2:])] = _leer_decimal(valor)
    llega = _fecha(request.form.get("llega")) or reposicion.llegada(grupo, hoy, reposicion.viaje_medellin(conn, hoy))
    try:
        reposicion.crear_pedido(conn, grupo, cantidades, llega, hoy)
        conn.commit()
        session["aviso_pedidos"] = (f"✓ Pedido a {reposicion.GRUPOS[grupo]['nombre']} anotado. "
                                    "Cuando llegue, tóquelo abajo para registrarlo como compra.")
    except ValueError as e:
        conn.rollback()
        session["error_pedidos"] = str(e)
    return redirect(url_for("pedidos_pagina") + ("#en-camino" if "aviso_pedidos" in session else f"#{grupo}"))


@app.post("/pedidos/viaje")
@requiere_ingreso
def pedido_viaje():
    _revisar_csrf()
    conn = _db_reposicion()
    try:
        reposicion.poner_viaje(conn, _fecha(request.form.get("viaje")), date.today())
        conn.commit()
    except ValueError as e:
        conn.rollback()
        session["error_pedidos"] = str(e)
    return redirect(url_for("pedidos_pagina") + "#medellin")


@app.post("/pedido/<int:pedido_id>/cancelar")
@requiere_ingreso
def pedido_cancelar(pedido_id):
    _revisar_csrf()
    conn = _db_reposicion()
    reposicion.cerrar_pedido(conn, pedido_id, "cancelado")
    conn.commit()
    session["aviso_pedidos"] = "Pedido quitado de los que van en camino."
    return redirect(url_for("pedidos_pagina") + "#en-camino")


# ── El conteo del martes ─────────────────────────────────────────────────────
@app.get("/conteo")
@requiere_ingreso
def conteo_pagina():
    conn = _db_reposicion()
    hoy = date.today()
    return render_template("conteo.html", grupos=reposicion.para_contar(conn),
                           nombres={k: g["nombre"] for k, g in reposicion.GRUPOS.items()},
                           ultimo=reposicion.ultimo_conteo(conn),
                           hecho=reposicion.conteo_hecho(conn, hoy), error=None, datos={})


@app.post("/conteo")
@requiere_ingreso
def conteo_guardar():
    _revisar_csrf()
    conn = _db_reposicion()
    contados = {}
    for clave, valor in request.form.items():
        if clave.startswith("c_") and clave[2:].isdigit() and valor.strip():
            contados[int(clave[2:])] = _leer_decimal(valor)
    try:
        conteo_id = reposicion.guardar_conteo(conn, contados, date.today(), _quien(), _usuario_admin(conn))
        conn.commit()
    except ValueError as e:
        conn.rollback()
        return render_template("conteo.html", grupos=reposicion.para_contar(conn),
                               nombres={k: g["nombre"] for k, g in reposicion.GRUPOS.items()},
                               ultimo=reposicion.ultimo_conteo(conn), hecho=False, error=str(e),
                               datos=request.form)
    return redirect(url_for("conteo_resultado", conteo_id=conteo_id))


@app.get("/conteo/<int:conteo_id>")
@requiere_ingreso
def conteo_resultado(conteo_id):
    conn = _db_reposicion()
    datos = reposicion.conteo(conn, conteo_id)
    if datos is None:
        abort(404)
    desde = reposicion.desde_para_pistas(conn, conteo_id, date.fromisoformat(datos["hecho"][:10]))
    return render_template("conteo_resultado.html", c=datos, pistas=reposicion.pistas(conn, conteo_id, desde),
                           desde=reposicion.dia_corto(desde), aviso=session.pop("aviso_conteo", None),
                           error=session.pop("error_conteo", None))


@app.post("/conteo/<int:conteo_id>/aparecio")
@requiere_ingreso
def conteo_aparecio(conteo_id):
    _revisar_csrf()
    conn = _db_reposicion()
    try:
        product_id = int(request.form.get("product_id", ""))
    except ValueError:
        abort(400)
    try:
        reposicion.aparecio(conn, conteo_id, product_id, _leer_decimal(request.form.get("cantidad")))
        conn.commit()
        session["aviso_conteo"] = ("✓ Listo: ya no cuenta como faltante. "
                                   "Si todavía no anotó la venta, anótela ahora.")
    except ValueError as e:
        conn.rollback()
        session["error_conteo"] = str(e)
    return redirect(url_for("conteo_resultado", conteo_id=conteo_id) + f"#p{product_id}")


# ── Avisos al celular ────────────────────────────────────────────────────────
def _clave_publica():
    return os.environ.get("VAPID_PUBLICA", "").strip()


def _puede_probar():
    return bool(os.environ.get("CATALOGO_REPO") and os.environ.get("CATALOGO_TOKEN"))


@app.get("/avisos")
@requiere_ingreso
def avisos_pagina():
    conn = _db_reposicion()
    return render_template("avisos.html", clave=_clave_publica(), puede_probar=_puede_probar(),
                           celulares=reposicion.suscripciones(conn),
                           aviso=session.pop("aviso_avisos", None))


@app.post("/avisos/suscribir")
@requiere_ingreso
def avisos_suscribir():
    """Lo llama la página al activar los avisos, sin salir de ella."""
    _revisar_csrf()
    conn = _db_reposicion()
    ua = request.headers.get("User-Agent", "")
    equipo = next((n for k, n in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"),
                                  ("Windows", "Windows"), ("Mac OS", "Mac")) if k in ua), "Otro")
    try:
        reposicion.guardar_suscripcion(conn, request.form.get("datos", ""), _quien(), equipo)
        conn.commit()
    except ValueError:
        abort(400)
    return "", 204


@app.post("/avisos/quitar")
@requiere_ingreso
def avisos_quitar():
    _revisar_csrf()
    conn = _db_reposicion()
    reposicion.quitar_suscripcion(conn, request.form.get("endpoint", ""))
    conn.commit()
    return "", 204


@app.post("/avisos/probar")
@requiere_ingreso
def avisos_probar():
    """Pide a GitHub que mande ya un aviso de prueba a todos los celulares."""
    _revisar_csrf()
    if not _puede_probar():
        abort(404)
    solicitud = urllib.request.Request(
        f"https://api.github.com/repos/{os.environ['CATALOGO_REPO']}/actions/workflows/avisos.yml/dispatches",
        data=json.dumps({"ref": "main", "inputs": {"prueba": "si"}}).encode(), method="POST",
        headers={"Authorization": f"Bearer {os.environ['CATALOGO_TOKEN']}",
                 "Accept": "application/vnd.github+json", "Content-Type": "application/json",
                 "User-Agent": "charcuteria-hye"})
    try:
        urllib.request.urlopen(solicitud, timeout=10).close()
        session["aviso_avisos"] = "✓ Pedido. En uno o dos minutos debe llegar el aviso de prueba."
    except Exception:
        registro.exception("No se pudo pedir el aviso de prueba")
        session["aviso_avisos"] = "GitHub no recibió el pedido. Intente de nuevo en un rato."
    return redirect(url_for("avisos_pagina"))


# El trabajador del navegador que muestra los avisos. Va en la raíz para que
# cubra toda la página.
TRABAJADOR = """
self.addEventListener("push", function (e) {
  var d = {};
  try { d = e.data ? e.data.json() : {}; } catch (_) { d = { titulo: e.data && e.data.text() }; }
  e.waitUntil(self.registration.showNotification(d.titulo || "Charcutería HYE", {
    body: d.cuerpo || "", icon: "/estatico/icono-192.png", badge: "/estatico/icono-192.png",
    tag: d.clave || undefined, data: { url: d.url || "/" }
  }));
});
self.addEventListener("notificationclick", function (e) {
  e.notification.close();
  var url = new URL((e.notification.data && e.notification.data.url) || "/", self.location.origin).href;
  e.waitUntil(clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (ventanas) {
    for (var i = 0; i < ventanas.length; i++) {
      if ("navigate" in ventanas[i]) { ventanas[i].focus(); return ventanas[i].navigate(url); }
    }
    return clients.openWindow(url);
  }));
});
"""


@app.get("/sw.js")
def trabajador_avisos():
    return app.response_class(TRABAJADOR, mimetype="application/javascript")
