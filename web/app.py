"""Página del celular (Flask).

Configuración por variables de entorno (en Cloud Run van como secretos):
  TURSO_URL, TURSO_TOKEN   la base en la nube
  CLAVE_HUELLA             huella de la contraseña (python -m web.clave)
  SECRETO                  clave para firmar la sesión (cualquier texto largo al azar)
  TZ=America/Bogota        para que "hoy" sea el día de Colombia

Para probarla en el PC:  TIENDA_DESARROLLO=1 python -m web.app
(usa data/nube_prueba.json y acepta la contraseña de TIENDA_CLAVE_PRUEBA).
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
from utils import estado_cuenta
from utils.conciliacion import MESES_ES, deudores, telefonos_clientes
from utils.informe_movil import html_pendientes
from web.clave import huella, verificar

RAIZ = Path(__file__).resolve().parent.parent
DESARROLLO = os.environ.get("TIENDA_DESARROLLO") == "1"

app = Flask(__name__, template_folder="plantillas", static_folder="estatico",
            static_url_path="/estatico")


def _configurar():
    url, token = os.environ.get("TURSO_URL"), os.environ.get("TURSO_TOKEN")
    clave = os.environ.get("CLAVE_HUELLA")
    secreto = os.environ.get("SECRETO")
    if DESARROLLO:
        if not url:
            prueba = json.loads((RAIZ / "data" / "nube_prueba.json").read_text(encoding="utf-8"))
            url, token = prueba["url"], prueba["token"]
        clave = clave or huella(os.environ.get("TIENDA_CLAVE_PRUEBA", "prueba1234"))
        secreto = secreto or "solo-para-desarrollo"
    if not (url and token and clave and secreto):
        raise RuntimeError("Faltan TURSO_URL, TURSO_TOKEN, CLAVE_HUELLA o SECRETO")
    app.config.update(
        TURSO_URL=url, TURSO_TOKEN=token, CLAVE_HUELLA=clave, SECRET_KEY=secreto,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=not DESARROLLO,
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    )


_configurar()


# ── Base de datos: una conexión por visita ───────────────────────────────────
def db():
    if "db" not in g:
        g.db = conexion_directa(app.config["TURSO_URL"], app.config["TURSO_TOKEN"])
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
        if _bloqueado():
            error = "Demasiados intentos. Espere 15 minutos."
        elif verificar(request.form.get("clave", ""), app.config["CLAVE_HUELLA"]):
            _fallos.clear()
            session.clear()
            session.permanent = True
            session["ingreso"] = True
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
    f = datetime.strptime(str(texto)[:19], "%Y-%m-%d %H:%M:%S" if len(str(texto)) >= 19 else "%Y-%m-%d")
    base = f"{f.day} {MESES_ES[f.month - 1][:3]}"
    if f.year != date.today().year:
        base += f" {f.year}"
    return base + (f.strftime(" · %I:%M %p").lower().replace(" 0", " ") if con_hora and len(str(texto)) >= 16 else "")


def _dia_largo(d: date) -> str:
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    return f"{dias[d.weekday()]} {d.day} de {MESES_ES[d.month - 1]}"


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
    abonos_hoy = conn.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM client_transactions
         WHERE transaction_type = 'credit' AND date(created_at) = ?""", (hoy,)).fetchone()[0]
    ventas_mes = conn.execute(
        "SELECT COALESCE(SUM(total), 0) FROM sales WHERE strftime('%Y-%m', created_at) = ?",
        (mes,)).fetchone()[0]
    agotados = conn.execute("SELECT COUNT(*) FROM products WHERE stock <= 0").fetchone()[0]
    return render_template(
        "inicio.html", hoy=_dia_largo(date.today()), mes=MESES_ES[int(mes[5:]) - 1],
        clientes_deben=cobrar[0], por_cobrar=cobrar[1],
        ventas_hoy=ventas_hoy[0], vendido_hoy=ventas_hoy[1], fiado_hoy=ventas_hoy[2],
        abonos_hoy=abonos_hoy, vendido_mes=ventas_mes, agotados=agotados)


@app.get("/pendientes")
@requiere_ingreso
def pendientes():
    conn = db()
    ids = {n: i for i, n in conn.execute("SELECT id, name FROM clients WHERE total_debt > 0")}
    enlaces = {n: url_for("cliente", client_id=i) for n, i in ids.items()}
    return html_pendientes(deudores(conn), telefonos_clientes(conn), enlaces,
                           f'<a class="volver" href="{url_for("inicio")}">‹ Inicio</a>')


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
    c = conn.execute("SELECT id, name, phone, total_debt, notes FROM clients WHERE id = ?",
                     (client_id,)).fetchone()
    if c is None:
        abort(404)
    movimientos = conn.execute("""
        SELECT created_at, transaction_type, amount, description FROM client_transactions
         WHERE client_id = ? ORDER BY created_at DESC, id DESC LIMIT 25""", (client_id,)).fetchall()
    return render_template("cliente.html", c=c, movimientos=movimientos)


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


@app.get("/inventario")
@requiere_ingreso
def inventario():
    q = request.args.get("q", "").strip()
    sql = "SELECT id, name, price, stock FROM products"
    params = ()
    if q:
        sql += " WHERE name LIKE ?"
        params = (f"%{q}%",)
    filas = db().execute(sql + " ORDER BY stock > 0, name COLLATE NOCASE", params).fetchall()
    return render_template("inventario.html", productos=filas, q=q)


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


if __name__ == "__main__":
    app.run(host="0.0.0.0" if os.environ.get("TIENDA_EN_RED") else "127.0.0.1",
            port=int(os.environ.get("PORT", 8080)), debug=DESARROLLO)
