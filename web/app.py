"""Página del celular (Flask).

Configuración por variables de entorno (en Cloud Run van como secretos):
  TURSO_URL, TURSO_TOKEN   la base en la nube
  CLAVE_HUELLA             huella de la contraseña (python -m web.clave)
  CLAVE_HUELLA_HERMANA     huella de una segunda contraseña (opcional): entra a
                           todo menos a los gastos
  SECRETO                  clave para firmar la sesión (cualquier texto largo al azar)
  GEMINI_API_KEY           para las ventas por audio (opcional; ver web/audios.py)
  TZ=America/Bogota        para que "hoy" sea el día de Colombia

Para probarla en el PC:  TIENDA_DESARROLLO=1 python -m web.app
(usa data/nube_prueba.json y acepta la contraseña de TIENDA_CLAVE_PRUEBA, y
la de TIENDA_CLAVE_HERMANA_PRUEBA para entrar sin gastos).
"""
import io
import json
import os
import secrets
import time
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import (Flask, abort, g, redirect, render_template, request,
                   send_file, session, url_for)

from config.nube import conexion_directa
from utils import estado_cuenta, perfil_clientes
from utils.conciliacion import MESES_ES, deudores, telefonos_clientes
from utils.informe_movil import html_pendientes
from servicios.abonos import registrar_abono
from servicios.clientes import (agregar_deuda, credito_disponible, crear_cliente,
                                editar_cliente, eliminar_cliente)
from servicios.ventas import editar_venta, eliminar_venta, preparar_items, registrar_venta
from web.clave import huella, verificar

RAIZ = Path(__file__).resolve().parent.parent
DESARROLLO = os.environ.get("TIENDA_DESARROLLO") == "1"

app = Flask(__name__, template_folder="plantillas", static_folder="estatico",
            static_url_path="/estatico")


def _configurar():
    url, token = os.environ.get("TURSO_URL"), os.environ.get("TURSO_TOKEN")
    clave = os.environ.get("CLAVE_HUELLA")
    secreto = os.environ.get("SECRETO")
    clave_hermana = os.environ.get("CLAVE_HUELLA_HERMANA")
    if DESARROLLO:
        if not url:
            prueba = json.loads((RAIZ / "data" / "nube_prueba.json").read_text(encoding="utf-8"))
            url, token = prueba["url"], prueba["token"]
        clave = clave or huella(os.environ.get("TIENDA_CLAVE_PRUEBA", "prueba1234"))
        secreto = secreto or "solo-para-desarrollo"
        clave_hermana = clave_hermana or huella(os.environ.get("TIENDA_CLAVE_HERMANA_PRUEBA", "hermana1234"))
    if not (url and token and clave and secreto):
        raise RuntimeError("Faltan TURSO_URL, TURSO_TOKEN, CLAVE_HUELLA o SECRETO")
    app.config.update(
        TURSO_URL=url, TURSO_TOKEN=token, CLAVE_HUELLA=clave, SECRET_KEY=secreto,
        CLAVE_HUELLA_HERMANA=clave_hermana,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=not DESARROLLO,
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    )


_configurar()


# ── Base de datos: una conexión por visita ───────────────────────────────────
class _ConexionVisita:
    """La conexión de la visita. Anota si algo se guardó, para que el
    historial sepa si lo que se intentó se hizo de verdad."""

    def __init__(self, conn):
        self._conn = conn
        self.guardo = False

    def __getattr__(self, nombre):
        return getattr(self._conn, nombre)

    def commit(self):
        self._conn.commit()
        self.guardo = True


def db():
    if "db" not in g:
        g.db = _ConexionVisita(conexion_directa(app.config["TURSO_URL"], app.config["TURSO_TOKEN"]))
    return g.db


@app.teardown_appcontext
def _cerrar_db(_error):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


# ── Seguridad ────────────────────────────────────────────────────────────────
# Después de 5 intentos fallidos en 15 minutos se bloquea el ingreso 15
# minutos. Es un solo usuario: el bloqueo es para todos, no por dirección.
FALLOS_MAXIMOS, VENTANA_FALLOS = 5, 15 * 60
_fallos = []


def _bloqueado():
    ahora = time.time()
    _fallos[:] = [t for t in _fallos if ahora - t < VENTANA_FALLOS]
    return len(_fallos) >= FALLOS_MAXIMOS


def _token_csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def _revisar_csrf():
    enviado = request.form.get("csrf", "")
    if not enviado or not secrets.compare_digest(enviado, session.get("csrf", "")):
        abort(400)


app.jinja_env.globals["csrf"] = _token_csrf


def requiere_ingreso(vista):
    @wraps(vista)
    def envuelta(*args, **kwargs):
        if not session.get("ingreso"):
            return redirect(url_for("ingresar", siguiente=request.path))
        return vista(*args, **kwargs)
    return envuelta


# La contraseña de la hermana entra a todo menos a los gastos: ni verlos,
# ni agregarlos, ni cambiarlos.
def ve_gastos():
    return not session.get("sin_gastos")


app.jinja_env.globals["ve_gastos"] = ve_gastos


def requiere_gastos(vista):
    @wraps(vista)
    def envuelta(*args, **kwargs):
        if not ve_gastos():
            abort(404)      # como si no existiera: sin avisarle nada
        return vista(*args, **kwargs)
    return envuelta


@app.after_request
def _cabeceras(resp):
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; "
        "frame-ancestors 'none'; base-uri 'none'")
    if not request.path.startswith("/estatico"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/ingresar", methods=["GET", "POST"])
def ingresar():
    error = None
    if request.method == "POST":
        _revisar_csrf()
        clave = request.form.get("clave", "")
        es_dueno = verificar(clave, app.config["CLAVE_HUELLA"])
        es_hermana = (not es_dueno and bool(app.config["CLAVE_HUELLA_HERMANA"])
                      and verificar(clave, app.config["CLAVE_HUELLA_HERMANA"]))
        if _bloqueado():
            error = "Demasiados intentos. Espere 15 minutos."
        elif es_dueno or es_hermana:
            _fallos.clear()
            session.clear()
            session.permanent = True
            session["ingreso"] = True
            if es_hermana:
                session["sin_gastos"] = True
            siguiente = request.args.get("siguiente", "/")
            # Solo rutas propias: nada de redirigir a otro sitio
            if not siguiente.startswith("/") or siguiente.startswith("//"):
                siguiente = "/"
            return redirect(siguiente)
        else:
            _fallos.append(time.time())
            error = "Contraseña incorrecta."
    return render_template("ingresar.html", error=error)


@app.post("/salir")
@requiere_ingreso
def salir():
    _revisar_csrf()
    session.clear()
    return redirect(url_for("ingresar"))


# ── Formatos ─────────────────────────────────────────────────────────────────
@app.template_filter("pesos")
def pesos(valor):
    return "$" + f"{round(valor or 0):,.0f}".replace(",", ".")


@app.template_filter("cantidad")
def cantidad(q):
    q = float(q or 0)
    return str(int(q)) if q.is_integer() else f"{q:.2f}".rstrip("0").replace(".", ",")


@app.template_filter("fecha")
def fecha(texto, con_hora=True):
    if not texto:
        return ""
    texto = str(texto).replace("T", " ")      # los gastos se guardan como 2026-09-21T00:00:00
    f = datetime.strptime(texto[:19], "%Y-%m-%d %H:%M:%S" if len(texto) >= 19 else "%Y-%m-%d")
    base = f"{f.day} {MESES_ES[f.month - 1][:3]}"
    if f.year != date.today().year:
        base += f" {f.year}"
    return base + (f.strftime(" · %I:%M %p").lower().replace(" 0", " ") if con_hora and len(str(texto)) >= 16 else "")


def _dia_largo(d: date) -> str:
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    return f"{dias[d.weekday()]} {d.day} de {MESES_ES[d.month - 1]}"


def _saludo() -> str:
    h = datetime.now().hour
    return "Buenos días" if h < 12 else "Buenas tardes" if h < 19 else "Buenas noches"


# ── Pantallas ────────────────────────────────────────────────────────────────
@app.get("/")
@requiere_ingreso
def inicio():
    conn = db()
    hoy = date.today().isoformat()
    mes = hoy[:7]
    cobrar = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(total_debt), 0) FROM clients WHERE total_debt > 0").fetchone()
    ventas_hoy = conn.execute("""
        SELECT COUNT(*), COALESCE(SUM(total), 0),
               COALESCE(SUM(CASE WHEN payment_method = 'credit' THEN total END), 0)
          FROM sales WHERE date(created_at) = ?""", (hoy,)).fetchone()
    contado_hoy = conn.execute("""
        SELECT COALESCE(SUM(total), 0) FROM sales
         WHERE date(created_at) = ? AND payment_method = 'cash' AND status = 'paid'""",
                               (hoy,)).fetchone()[0]
    abonos_hoy = conn.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM client_transactions
         WHERE transaction_type = 'credit' AND date(created_at) = ?""", (hoy,)).fetchone()[0]
    ventas_mes = conn.execute(
        "SELECT COALESCE(SUM(total), 0) FROM sales WHERE strftime('%Y-%m', created_at) = ?",
        (mes,)).fetchone()[0]
    agotados = conn.execute("SELECT COUNT(*) FROM products WHERE stock <= 0").fetchone()[0]
    toca = [p for p in perfil_clientes.perfiles(conn, date.today()) if p["estado"] == "toca"]
    return render_template(
        "inicio.html", hoy=_dia_largo(date.today()), saludo=_saludo(), mes=MESES_ES[int(mes[5:]) - 1],
        clientes_deben=cobrar[0], por_cobrar=cobrar[1],
        ventas_hoy=ventas_hoy[0], vendido_hoy=ventas_hoy[1], fiado_hoy=ventas_hoy[2],
        abonos_hoy=abonos_hoy, contado_hoy=contado_hoy, vendido_mes=ventas_mes, agotados=agotados,
        por_pedir_clientes=len(toca), por_pedir_total=sum(p["tipica"] for p in toca))


@app.get("/mas")
@requiere_ingreso
def mas():
    return render_template("mas.html")


@app.get("/pendientes")
@requiere_ingreso
def pendientes():
    conn = db()
    ids = {n: i for i, n in conn.execute("SELECT id, name FROM clients WHERE total_debt > 0")}
    enlaces = {n: url_for("cliente", client_id=i) for n, i in ids.items()}
    return html_pendientes(deudores(conn), telefonos_clientes(conn), enlaces,
                           f'<a class="volver" href="{url_for("inicio")}">‹ Inicio</a>')


@app.get("/pendientes/informe.html")
@requiere_ingreso
def pendientes_informe():
    """El mismo archivo HTML interactivo que "Enviar al celular" en el PC, para
    compartirlo por WhatsApp desde el teléfono."""
    conn = db()
    html = html_pendientes(deudores(conn), telefonos_clientes(conn))
    return app.response_class(html, mimetype="text/html", headers={
        "Content-Disposition": f'attachment; filename="pendientes_{date.today().isoformat()}.html"'})


@app.get("/clientes")
@requiere_ingreso
def clientes():
    q = request.args.get("q", "").strip()
    sql = "SELECT id, name, phone, total_debt FROM clients"
    params = ()
    if q:
        sql += " WHERE name LIKE ?"
        params = (f"%{q}%",)
    filas = db().execute(sql + " ORDER BY total_debt > 0 DESC, name COLLATE NOCASE", params).fetchall()
    return render_template("clientes.html", clientes=filas, q=q)


@app.get("/cliente/<int:client_id>")
@requiere_ingreso
def cliente(client_id):
    conn = db()
    c = conn.execute("""SELECT id, name, phone, address, credit_limit, total_debt, notes
                          FROM clients WHERE id = ?""", (client_id,)).fetchone()
    if c is None:
        abort(404)
    todo = request.args.get("todo") == "1"
    movimientos = conn.execute("""
        SELECT t.created_at, t.transaction_type, t.amount, t.description, t.sale_id,
               EXISTS (SELECT 1 FROM sales s WHERE s.id = t.sale_id) AS venta_existe
          FROM client_transactions t
         WHERE t.client_id = ? ORDER BY t.created_at DESC, t.id DESC""" + ("" if todo else " LIMIT 26"),
                               (client_id,)).fetchall()
    hay_mas = not todo and len(movimientos) > 25
    return render_template("cliente.html", c=c, movimientos=movimientos[:None if todo else 25],
                           hay_mas=hay_mas, aviso=session.pop("aviso", None),
                           aviso_cliente=session.pop("aviso_cliente", None),
                           perfil=perfil_clientes.perfil(conn, client_id))


@app.get("/clientes/por-pedir")
@requiere_ingreso
def clientes_por_pedir():
    """A quién escribirle antes de la ruta: suelen pedir y no han pedido."""
    hoy = date.today()
    lista = perfil_clientes.perfiles(db(), hoy)
    toca = [p for p in lista if p["estado"] == "toca"]
    lejos = [p for p in lista if p["estado"] == "lejos"]
    ruta = perfil_clientes.proxima_ruta(hoy)
    return render_template(
        "por_pedir.html", toca=toca, lejos=lejos, ruta=ruta.isoformat(),
        ruta_texto="hoy" if ruta == hoy else _dia_largo(ruta),
        al_dia=sum(p["estado"] == "normal" for p in lista),
        pocas=sum(p["estado"] == "pocas" for p in lista),
        si_todos=sum(p["tipica"] for p in toca))


@app.get("/cliente/<int:client_id>/estado-de-cuenta.pdf")
@requiere_ingreso
def estado_de_cuenta(client_id):
    try:
        datos = estado_cuenta.calcular(db(), client_id)
    except ValueError as e:
        return render_template("aviso.html", titulo="No se pudo generar", mensaje=str(e)), 409
    pdf = io.BytesIO()
    estado_cuenta.exportar_pdf(datos, pdf)
    pdf.seek(0)
    return send_file(pdf, mimetype="application/pdf",
                     download_name=estado_cuenta.nombre_archivo(datos) + ".pdf",
                     as_attachment=request.args.get("descargar") == "1")


# ── Abonos ───────────────────────────────────────────────────────────────────
def _leer_monto(texto):
    """'50.000', '$50000' o '50 000' → 50000. En Colombia el punto separa
    miles; no se usan centavos."""
    limpio = "".join(c for c in (texto or "") if c.isdigit())
    return int(limpio) if limpio else 0


def _reparto_abono(conn, client_id, monto):
    """A qué compras pendientes se aplicaría el abono, de la más vieja a la
    más nueva: la misma regla del estado de cuenta y del PC."""
    try:
        datos = estado_cuenta.calcular(conn, client_id)
    except ValueError:
        return []
    reparto, restante = [], monto
    for m in datos["movimientos"]:
        if m["tipo"] != "debit" or m["queda"] <= 0.5 or restante <= 0:
            continue
        aplicado = min(restante, m["queda"])
        restante -= aplicado
        reparto.append({"fecha": m["fecha"], "debe": m["queda"], "aplicado": aplicado,
                        "queda": m["queda"] - aplicado})
    return reparto


def _cliente_o_404(conn, client_id):
    c = conn.execute("SELECT id, name, total_debt FROM clients WHERE id = ?", (client_id,)).fetchone()
    if c is None:
        abort(404)
    return c


@app.route("/cliente/<int:client_id>/abono", methods=["GET", "POST"])
@requiere_ingreso
def abono(client_id):
    conn = db()
    c = _cliente_o_404(conn, client_id)
    if request.method == "GET":
        return render_template("abono.html", c=c, monto="", nota="abono", error=None)

    _revisar_csrf()
    monto, nota = _leer_monto(request.form.get("monto")), request.form.get("nota", "").strip()
    deuda = float(c["total_debt"] or 0)
    pago_total = deuda > 0 and monto >= round(deuda)
    # Si paga todo no es un abono: la nota por defecto se corrige sola
    if pago_total and nota.lower() == "abono":
        nota = "pago total"
    error = None
    if monto <= 0:
        error = "Escriba el monto del abono."
    elif not nota:
        error = "Escriba una nota (por ejemplo: abono en efectivo)."
    if error:
        return render_template("abono.html", c=c, monto=request.form.get("monto", ""),
                               nota=nota, error=error)

    # Un código de un solo uso: si se toca dos veces "Confirmar" o se recarga
    # la página, el abono no se registra dos veces.
    codigo = secrets.token_urlsafe(16)
    session["abono_pendiente"] = {"codigo": codigo, "cliente": client_id,
                                  "monto": monto, "nota": nota, "pago_total": pago_total}
    return render_template(
        "abono_confirmar.html", c=c, monto=monto, nota=nota, codigo=codigo, pago_total=pago_total,
        deuda=deuda, queda=max(0.0, deuda - monto), exceso=max(0.0, monto - max(deuda, 0)),
        reparto=_reparto_abono(conn, client_id, monto))


@app.post("/cliente/<int:client_id>/abono/confirmar")
@requiere_ingreso
def abono_confirmar(client_id):
    _revisar_csrf()
    pendiente = session.pop("abono_pendiente", None)
    if (not pendiente or pendiente["cliente"] != client_id
            or not secrets.compare_digest(pendiente["codigo"], request.form.get("codigo", ""))):
        # Ya se registró (doble toque o recarga) o la confirmación caducó
        return redirect(url_for("cliente", client_id=client_id))

    conn = db()
    try:
        resumen = registrar_abono(conn, client_id, pendiente["monto"], pendiente["nota"])
        conn.commit()
    except Exception as e:
        conn.rollback()
        return render_template("aviso.html", titulo="No se registró el abono",
                               mensaje=f"No se guardó nada. Detalle: {e}"), 500
    session["aviso"] = {"monto": pendiente["monto"], "deuda_nueva": resumen["deuda_nueva"],
                        "exceso": resumen["exceso"], "pago_total": pendiente.get("pago_total")}
    return redirect(url_for("cliente", client_id=client_id))


# ── Clientes: crear, editar, eliminar, deuda manual ──────────────────────────
def _form_cliente():
    f = request.form
    return (f.get("nombre"), f.get("telefono"), f.get("direccion"),
            _leer_monto(f.get("limite")), f.get("notas"))


@app.route("/cliente/nuevo", methods=["GET", "POST"])
@requiere_ingreso
def cliente_nuevo():
    volver = request.args.get("volver")
    if request.method == "GET":
        return render_template("cliente_form.html", c=None, error=None, volver=volver)
    _revisar_csrf()
    conn = db()
    try:
        client_id = crear_cliente(conn, *_form_cliente())
        conn.commit()
    except ValueError as e:
        conn.rollback()
        return render_template("cliente_form.html", c=request.form, error=str(e), volver=volver)
    if volver == "venta":
        return redirect(url_for("venta_nueva", cliente=client_id, audio=request.args.get("audio")))
    return redirect(url_for("cliente", client_id=client_id))


@app.route("/cliente/<int:client_id>/editar", methods=["GET", "POST"])
@requiere_ingreso
def cliente_editar(client_id):
    conn = db()
    c = conn.execute("SELECT id, name, phone, address, credit_limit, notes FROM clients WHERE id = ?",
                     (client_id,)).fetchone()
    if c is None:
        abort(404)
    if request.method == "GET":
        datos = {"id": c["id"], "nombre": c["name"], "telefono": c["phone"] or "",
                 "direccion": c["address"] or "", "limite": int(c["credit_limit"] or 0),
                 "notas": c["notes"] or ""}
        return render_template("cliente_form.html", c=datos, error=None, volver=None)
    _revisar_csrf()
    try:
        editar_cliente(conn, client_id, *_form_cliente())
        conn.commit()
    except ValueError as e:
        conn.rollback()
        return render_template("cliente_form.html", c={**request.form, "id": client_id},
                               error=str(e), volver=None)
    return redirect(url_for("cliente", client_id=client_id))


@app.route("/cliente/<int:client_id>/eliminar", methods=["GET", "POST"])
@requiere_ingreso
def cliente_eliminar(client_id):
    conn = db()
    c = _cliente_o_404(conn, client_id)
    error = None
    if request.method == "POST":
        _revisar_csrf()
        try:
            eliminar_cliente(conn, client_id)
            conn.commit()
            return redirect(url_for("clientes"))
        except ValueError as e:
            conn.rollback()
            error = str(e)
    return render_template("cliente_eliminar.html", c=c, error=error)


@app.route("/cliente/<int:client_id>/deuda", methods=["GET", "POST"])
@requiere_ingreso
def cliente_deuda(client_id):
    conn = db()
    c = _cliente_o_404(conn, client_id)
    disponible = credito_disponible(conn, client_id)
    error, monto, nota = None, "", ""
    if request.method == "POST":
        _revisar_csrf()
        monto, nota = request.form.get("monto", ""), request.form.get("nota", "")
        codigo = session.pop("deuda_codigo", None)
        if not codigo or not secrets.compare_digest(codigo, request.form.get("codigo", "")):
            return redirect(url_for("cliente", client_id=client_id))   # doble envío
        try:
            agregar_deuda(conn, client_id, _leer_monto(monto), nota)
            conn.commit()
            session["aviso_cliente"] = f"Deuda de {pesos(_leer_monto(monto))} agregada."
            return redirect(url_for("cliente", client_id=client_id))
        except ValueError as e:
            conn.rollback()
            error = str(e)
    session["deuda_codigo"] = secrets.token_urlsafe(16)
    return render_template("cliente_deuda.html", c=c, disponible=disponible, error=error,
                           monto=monto, nota=nota, codigo=session["deuda_codigo"])


# ── Ventas: nueva, detalle, editar, eliminar ─────────────────────────────────
def _leer_decimal(texto):
    """'1,5' o '1.5' → 1.5 (cantidades: aquí la coma es decimal)."""
    try:
        return float(str(texto or "").replace(",", ".").strip() or 0)
    except ValueError:
        return 0.0


def _datos_venta_nueva(conn):
    productos = [{"id": f[0], "n": f[1], "p": f[2], "s": f[3]} for f in conn.execute(
        "SELECT id, name, price, stock FROM products WHERE stock > 0 ORDER BY name COLLATE NOCASE")]
    clientes = [{"id": f[0], "n": f[1], "d": f[2] or 0} for f in conn.execute(
        "SELECT id, name, total_debt FROM clients ORDER BY name COLLATE NOCASE")]
    return productos, clientes


def _json_seguro(datos):
    # "</" dentro de <script> cerraría la etiqueta antes de tiempo
    return json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")


def _id_audio(texto):
    try:
        return int(texto or 0) or None
    except (TypeError, ValueError):
        return None


@app.route("/venta/nueva", methods=["GET", "POST"])
@requiere_ingreso
def venta_nueva():
    from web.audios import contexto_para_venta
    conn = db()
    productos, clientes = _datos_venta_nueva(conn)
    if request.method == "GET":
        # Desde "Ventas por audio": el carrito llega armado con lo que se entendió
        audio_id = _id_audio(request.args.get("audio"))
        audio = contexto_para_venta(audio_id) if audio_id else None
        if audio_id and audio is None:
            return redirect(url_for("audios"))   # ya se registró o se descartó
        return render_template("venta_nueva.html", productos=_json_seguro(productos),
                               clientes=_json_seguro(clientes), audio=audio,
                               borrador=_json_seguro(audio["borrador"]) if audio else "null",
                               error=None)

    _revisar_csrf()
    borrador = request.form.get("borrador", "")
    try:
        audio_id = _id_audio(json.loads(borrador).get("audio")) if borrador else None
    except (ValueError, AttributeError):
        audio_id = None
    def de_nuevo(error):
        return render_template("venta_nueva.html", productos=_json_seguro(productos),
                               clientes=_json_seguro(clientes),
                               audio=contexto_para_venta(audio_id) if audio_id else None,
                               borrador=_json_seguro(json.loads(borrador)) if borrador else "null",
                               error=error)
    if request.form.get("corregir"):
        return de_nuevo(None)   # desde la confirmación: volver al carrito tal cual
    try:
        venta = json.loads(borrador)
        pedidos = [(int(l["id"]), _leer_decimal(l.get("q")), _leer_monto(str(l.get("m") or "")))
                   for l in venta.get("lineas", [])]
        items = preparar_items(conn, pedidos)
    except ValueError as e:
        return de_nuevo(str(e))
    except (KeyError, TypeError, json.JSONDecodeError):
        return de_nuevo("No se pudo leer la venta; vuelva a intentarlo.")

    fiada = venta.get("fiada") is True
    cliente, ajuste, motivo = None, 0.0, None
    if fiada:
        cliente = conn.execute("SELECT id, name, total_debt FROM clients WHERE id = ?",
                               (int(venta.get("cliente") or 0),)).fetchone()
        if cliente is None:
            return de_nuevo("Elija el cliente de la venta fiada.")
        ajuste = float(_leer_monto(str(venta.get("ajuste") or "")))
        if venta.get("signo") == "-":
            ajuste = -ajuste
        motivo = (venta.get("motivo") or "").strip() or None

    subtotal = sum(i["subtotal"] for i in items)
    if subtotal + ajuste <= 0:
        return de_nuevo("El total de la venta debe ser mayor a cero.")
    momento = None
    if audio_id:
        # Las ventas por audio se guardan con el día y la hora en que se
        # hicieron (los del audio, o los que escriba quien revisa); nunca se
        # inventan
        try:
            momento = datetime.strptime(f"{venta.get('fecha') or ''} {venta.get('hora') or ''}",
                                        "%Y-%m-%d %H:%M")
        except ValueError:
            return de_nuevo("Escriba el día y la hora de la venta.")
        if momento > datetime.now():
            return de_nuevo("La venta no puede ser de después de este momento.")
    codigo = secrets.token_urlsafe(16)
    session["venta_pendiente"] = {
        "codigo": codigo, "pedidos": pedidos, "fiada": fiada,
        "cliente": cliente["id"] if cliente else None, "ajuste": ajuste, "motivo": motivo,
        "audio": audio_id,
        "fecha": momento.strftime("%Y-%m-%d %H:%M:%S") if momento else None}
    return render_template("venta_confirmar.html", items=items, fiada=fiada, cliente=cliente,
                           ajuste=ajuste, motivo=motivo, subtotal=subtotal,
                           total=subtotal + ajuste, codigo=codigo, borrador=borrador,
                           momento=fecha(momento.strftime("%Y-%m-%d %H:%M:%S")) if momento else None)


@app.post("/venta/confirmar")
@requiere_ingreso
def venta_confirmar():
    _revisar_csrf()
    p = session.pop("venta_pendiente", None)
    if not p or not secrets.compare_digest(p["codigo"], request.form.get("codigo", "")):
        return redirect(url_for("ventas"))   # ya se guardó (doble toque) o caducó
    conn = db()
    audio_id = p.get("audio")
    try:
        # Se vuelve a validar: el stock pudo cambiar desde la confirmación
        items = preparar_items(conn, p["pedidos"])
        sale_id, total = registrar_venta(conn, items, _usuario_admin(conn), p["cliente"],
                                         p["fiada"], p["ajuste"], p["motivo"], p.get("fecha"))
        if audio_id:
            from web.audios import marcar_registrado
            if not marcar_registrado(conn, audio_id, sale_id):
                raise ValueError("Ese audio ya se había registrado como venta.")
        conn.commit()
    except ValueError as e:
        conn.rollback()
        return render_template("aviso.html", titulo="No se guardó la venta", mensaje=str(e)), 409
    except Exception as e:
        conn.rollback()
        return render_template("aviso.html", titulo="No se guardó la venta",
                               mensaje=f"No se guardó nada. Detalle: {e}"), 500
    if audio_id:
        # De vuelta a la lista, para seguir con el siguiente audio
        session["aviso_audios"] = {"texto": f"Venta #{sale_id} guardada por {pesos(total)}.",
                                   "sale_id": sale_id}
        return redirect(url_for("audios"))
    session["aviso_venta"] = {"texto": f"Venta #{sale_id} guardada por {pesos(total)}."}
    return redirect(url_for("venta", sale_id=sale_id))


def _usuario_admin(conn):
    """Las ventas guardan quién las hizo; desde el celular es el dueño."""
    fila = conn.execute("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1").fetchone()
    return fila[0] if fila else None


def _venta_o_aviso(conn, sale_id):
    return conn.execute("""
        SELECT s.id, s.created_at, s.total, s.status, s.payment_method, s.client_id,
               s.adjustment, s.adjustment_reason, s.notes, c.name AS cliente, c.total_debt AS deuda
          FROM sales s LEFT JOIN clients c ON c.id = s.client_id WHERE s.id = ?""",
                        (sale_id,)).fetchone()


@app.get("/venta/<int:sale_id>")
@requiere_ingreso
def venta(sale_id):
    conn = db()
    v = _venta_o_aviso(conn, sale_id)
    if v is None:
        return render_template("aviso.html", titulo=f"Venta #{sale_id}",
                               mensaje="Esta venta no existe o fue eliminada."), 404
    productos = conn.execute("""
        SELECT d.quantity, COALESCE(p.name, 'Producto'), d.sale_price, d.subtotal
          FROM sale_details d LEFT JOIN products p ON p.id = d.product_id
         WHERE d.sale_id = ? ORDER BY d.id""", (sale_id,)).fetchall()
    return render_template("venta.html", v=v, productos=productos,
                           aviso=session.pop("aviso_venta", None))


@app.route("/venta/<int:sale_id>/editar", methods=["GET", "POST"])
@requiere_ingreso
def venta_editar(sale_id):
    conn = db()
    v = _venta_o_aviso(conn, sale_id)
    if v is None:
        abort(404)
    clientes = conn.execute("SELECT id, name FROM clients ORDER BY name COLLATE NOCASE").fetchall()
    error = None
    if request.method == "POST":
        _revisar_csrf()
        total = _leer_monto(request.form.get("total"))
        fiada = request.form.get("tipo") == "fiado"
        client_id = int(request.form.get("cliente") or 0) or None
        try:
            editar_venta(conn, sale_id, total, fiada, client_id)
            conn.commit()
            session["aviso_venta"] = {"texto": "Venta actualizada."}
            return redirect(url_for("venta", sale_id=sale_id))
        except ValueError as e:
            conn.rollback()
            error = str(e)
    return render_template("venta_editar.html", v=v, clientes=clientes, error=error)


@app.route("/venta/<int:sale_id>/eliminar", methods=["GET", "POST"])
@requiere_ingreso
def venta_eliminar(sale_id):
    conn = db()
    v = _venta_o_aviso(conn, sale_id)
    if v is None:
        return redirect(url_for("ventas"))
    if request.method == "GET":
        return render_template("venta_eliminar.html", v=v)
    _revisar_csrf()
    dia = str(v["created_at"])[:10]
    try:
        eliminar_venta(conn, sale_id)
        conn.commit()
    except ValueError as e:
        conn.rollback()
        return render_template("aviso.html", titulo="No se eliminó", mensaje=str(e)), 409
    return redirect(url_for("ventas", dia=dia))


@app.get("/inventario")
@requiere_ingreso
def inventario():
    q = request.args.get("q", "").strip()
    sql = "SELECT id, name, price, stock FROM products"
    params = ()
    if q:
        sql += " WHERE name LIKE ?"
        params = (f"%{q}%",)
    conn = db()
    filas = conn.execute(sql + " ORDER BY stock > 0, name COLLATE NOCASE", params).fetchall()
    # Mismo resumen que la ventana de inventario del PC
    r = conn.execute("""
        SELECT COUNT(*), COALESCE(SUM(price * stock), 0),
               SUM(CASE WHEN stock > 0 AND stock <= 5 THEN 1 ELSE 0 END),
               SUM(CASE WHEN stock <= 0 THEN 1 ELSE 0 END) FROM products""").fetchone()
    resumen = {"productos": r[0], "valor": r[1], "bajo": r[2] or 0, "agotados": r[3] or 0}
    return render_template("inventario.html", productos=filas, q=q, resumen=resumen)


@app.get("/ventas")
@requiere_ingreso
def ventas():
    try:
        dia = date.fromisoformat(request.args.get("dia", ""))
    except ValueError:
        dia = date.today()
    conn = db()
    filas = conn.execute("""
        SELECT s.id, s.created_at, s.total, s.status, s.payment_method, c.name AS cliente
          FROM sales s LEFT JOIN clients c ON c.id = s.client_id
         WHERE date(s.created_at) = ? ORDER BY s.created_at DESC, s.id DESC""",
                         (dia.isoformat(),)).fetchall()
    productos = {}
    for sale_id, q, nombre, subtotal in conn.execute("""
            SELECT d.sale_id, d.quantity, COALESCE(p.name, 'Producto'), d.subtotal
              FROM sale_details d LEFT JOIN products p ON p.id = d.product_id
             WHERE d.sale_id IN (SELECT id FROM sales WHERE date(created_at) = ?)
             ORDER BY d.id""", (dia.isoformat(),)):
        productos.setdefault(sale_id, []).append((q, nombre, subtotal))
    total = sum(f["total"] for f in filas)
    fiado = sum(f["total"] for f in filas if f["payment_method"] == "credit")
    return render_template(
        "ventas.html", ventas=filas, productos=productos, total=total, fiado=fiado,
        dia=_dia_largo(dia), es_hoy=dia == date.today(),
        anterior=(dia - timedelta(days=1)).isoformat(),
        siguiente=(dia + timedelta(days=1)).isoformat() if dia < date.today() else None)


@app.get("/manifest.webmanifest")
def manifiesto():
    datos = {
        "name": "Charcutería HYE", "short_name": "HYE", "start_url": "/", "display": "standalone",
        "background_color": "#f4f5f7", "theme_color": "#2c3e50", "lang": "es",
        "icons": [{"src": url_for("static", filename=f"icono-{n}.png"), "sizes": f"{n}x{n}",
                   "type": "image/png"} for n in (192, 512)],
    }
    return app.response_class(json.dumps(datos), mimetype="application/manifest+json")


@app.errorhandler(404)
def _no_existe(_e):
    return render_template("aviso.html", titulo="No existe", mensaje="Esa página no existe."), 404


# Inventario, compras, gastos, pérdidas y caja; ventas por audio; historial
import web.operaciones  # noqa: E402,F401
import web.audios  # noqa: E402,F401
import web.historial  # noqa: E402,F401


if __name__ == "__main__":
    # Con "python -m web.app" este archivo corre como __main__ y
    # web.operaciones se engancha a web.app (otra copia): se usa esa.
    from web.app import app
    app.run(host="0.0.0.0" if os.environ.get("TIENDA_EN_RED") else "127.0.0.1",
            port=int(os.environ.get("PORT", 8080)), debug=DESARROLLO)
