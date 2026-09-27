"""Ventas por audio: las notas de voz de WhatsApp se suben a la página (desde
el atajo del iPhone o eligiéndolas a mano), Gemini las escucha y arma la
venta, y aquí se revisan una por una antes de guardarlas con la pantalla de
venta de siempre. Nada se guarda como venta sin que alguien lo confirme.

Necesita GEMINI_API_KEY (se saca gratis en aistudio.google.com). Con
GEMINI_MODELO se puede cambiar el modelo.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import urllib.error
import urllib.request
from datetime import date, datetime

from flask import abort, redirect, render_template, request, session, url_for

from web.app import DESARROLLO, _revisar_csrf, app, db, pesos, requiere_ingreso

MODELO = os.environ.get("GEMINI_MODELO", "gemini-3.8-flash")
TAMANO_MAXIMO = 15 * 1024 * 1024        # una nota de voz de un minuto pesa ~100 KB

# extensión → (tipo para el navegador, tipo para Gemini)
TIPOS = {
    "opus": ("audio/ogg", "audio/ogg"), "ogg": ("audio/ogg", "audio/ogg"),
    "oga": ("audio/ogg", "audio/ogg"), "m4a": ("audio/mp4", "audio/aac"),
    "aac": ("audio/aac", "audio/aac"), "mp4": ("audio/mp4", "audio/aac"),
    "mp3": ("audio/mpeg", "audio/mp3"), "wav": ("audio/wav", "audio/wav"),
    "webm": ("audio/webm", "audio/webm"), "flac": ("audio/flac", "audio/flac"),
}


# ── La tabla ─────────────────────────────────────────────────────────────────
_tabla_lista = False


def _conn():
    """La conexión de la visita, con la tabla creada (una vez por proceso)."""
    global _tabla_lista
    conn = db()
    if not _tabla_lista:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audios_venta (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recibido_en TEXT NOT NULL,
                nombre TEXT,
                tipo TEXT,
                audio BLOB,
                grabado_en TEXT,              -- del nombre del archivo, si lo trae
                estado TEXT NOT NULL DEFAULT 'nuevo',   -- nuevo, listo, error, registrado
                resultado TEXT,               -- lo que entendió Gemini (JSON)
                error TEXT,
                sale_id INTEGER)""")
        conn.commit()
        _tabla_lista = True
    return conn


# ── Recibir ──────────────────────────────────────────────────────────────────
_FECHA = re.compile(r"(20\d\d)[-_.]?(\d\d)[-_.]?(\d\d)")
_HORA = re.compile(r"(\d{1,2})[.:](\d\d)[.:](\d\d)")


def fecha_del_nombre(nombre):
    """WhatsApp pone la fecha en el nombre: 'PTT-20260926-WA0003.opus' o
    'WhatsApp Audio 2026-09-26 at 17.03.12.opus'. Devuelve '2026-09-26' o
    '2026-09-26 17:03:12', o None si no la trae (o no tiene sentido)."""
    m = _FECHA.search(nombre or "")
    if not m:
        return None
    try:
        dia = date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None
    if dia > date.today():
        return None
    h = _HORA.search(nombre[m.end():])
    if h and int(h[1]) < 24 and int(h[2]) < 60 and int(h[3]) < 60:
        return f"{dia.isoformat()} {int(h[1]):02d}:{h[2]}:{h[3]}"
    return dia.isoformat()


def _guardar(conn, archivo):
    """Guarda un archivo subido; devuelve un texto de error o None."""
    nombre = os.path.basename((archivo.filename or "audio").replace("\\", "/"))[:120]
    extension = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if extension in TIPOS:
        tipo = TIPOS[extension][0]
    elif (archivo.mimetype or "").startswith("audio/"):
        tipo = archivo.mimetype
    else:
        return f"'{nombre}' no es un audio"
    datos = archivo.read(TAMANO_MAXIMO + 1)
    if not datos:
        return f"'{nombre}' está vacío"
    if len(datos) > TAMANO_MAXIMO:
        return f"'{nombre}' es demasiado grande"
    conn.execute("""INSERT INTO audios_venta (recibido_en, nombre, tipo, audio, grabado_en)
                    VALUES (datetime('now', 'localtime'), ?, ?, ?, ?)""",
                 (nombre, tipo, datos, fecha_del_nombre(nombre)))
    return None


def clave_atajo():
    """La clave que manda el atajo del iPhone. Sale del SECRETO de la página,
    así que no hay que guardar otra; si se cambia el SECRETO, cambia esta."""
    return hmac.new(app.config["SECRET_KEY"].encode(), b"audios-venta",
                    hashlib.sha256).hexdigest()[:32]


@app.post("/audios/recibir")
def audios_recibir():
    """Para el atajo del iPhone: sin sesión, con la clave."""
    enviada = request.headers.get("X-Clave") or request.args.get("clave") or ""
    if not hmac.compare_digest(enviada, clave_atajo()):
        abort(403)
    if (request.content_length or 0) > TAMANO_MAXIMO * 5:
        abort(413)
    archivos = [a for campo in request.files for a in request.files.getlist(campo)]
    if not archivos:
        return "No llegó ningún audio", 400
    conn = _conn()
    errores = [e for e in (_guardar(conn, a) for a in archivos) if e]
    conn.commit()
    recibidos = len(archivos) - len(errores)
    texto = f"{recibidos} audio{'s' if recibidos != 1 else ''} recibido{'s' if recibidos != 1 else ''}"
    return app.response_class("\n".join([texto] + errores), mimetype="text/plain",
                              status=200 if recibidos else 400)


@app.post("/audios")
@requiere_ingreso
def audios_subir():
    _revisar_csrf()
    if (request.content_length or 0) > TAMANO_MAXIMO * 5:
        abort(413)
    conn = _conn()
    errores = [e for e in (_guardar(conn, a) for a in request.files.getlist("audios")
                           if a.filename) if e]
    conn.commit()
    if errores:
        session["aviso_audios_error"] = "; ".join(errores)
    return redirect(url_for("audios"))


# ── Escuchar (Gemini) ────────────────────────────────────────────────────────
INSTRUCCIONES = """Eres el asistente de una charcutería venezolana en Colombia.
Recibes una nota de voz en la que la vendedora cuenta UNA venta, y la
conviertes en datos para registrarla. Debajo tienes el catálogo de productos
y la lista de clientes, con sus números (id).

- transcripcion: lo que dice el audio, tal cual.
- Cliente: si nombra a la persona a quien le vendió, busca el cliente que
  corresponde en la lista. Los nombres pueden venir con apodos, sin apellido,
  como "la vecina", "el papá de Natalia", o mal pronunciados. Pon su id en
  cliente_id y lo que dijo en cliente_dicho. Si no lo encuentras o hay más de
  uno posible, cliente_id = 0 y explícalo en dudas (nombra los candidatos).
- tipo: "fiado" si la venta es a nombre de un cliente, salvo que diga que
  pagó, que fue de contado o en efectivo. "contado" si no nombra a nadie o
  dice que pagó. Si no está claro, elige lo más probable y anótalo en dudas.
- lineas: una por cada producto vendido. producto_id es el del catálogo (0 si
  no lo encuentras; explícalo en dudas). producto_dicho es lo que dijo.
  cantidad va en la unidad del catálogo: si el producto es "Queso Costeño 1k"
  y dice "medio kilo", la cantidad es 0.5; "un cuarto" es 0.25. Si en vez de
  la cantidad dice cuánta plata fue ("diez mil de jamón"), pon cantidad 0 y
  el valor en dinero (en pesos, 10000). Si dice la cantidad, dinero = 0.
- Si menciona un precio distinto al del catálogo, o algo que no entiendes,
  anótalo en dudas. Las dudas van cortas y en español.
- No inventes productos ni clientes: si no están en la lista, usa 0."""

ESQUEMA = {
    "type": "object",
    "properties": {
        "transcripcion": {"type": "string"},
        "tipo": {"type": "string", "enum": ["contado", "fiado"]},
        "cliente_id": {"type": "integer"},
        "cliente_dicho": {"type": "string"},
        "lineas": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "producto_id": {"type": "integer"},
                "producto_dicho": {"type": "string"},
                "cantidad": {"type": "number"},
                "dinero": {"type": "integer"},
            },
            "required": ["producto_id", "producto_dicho", "cantidad", "dinero"],
        }},
        "dudas": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["transcripcion", "tipo", "cliente_id", "cliente_dicho", "lineas", "dudas"],
}


def _catalogo(conn):
    productos = conn.execute(
        "SELECT id, name, price FROM products ORDER BY name COLLATE NOCASE").fetchall()
    clientes = conn.execute("SELECT id, name FROM clients ORDER BY name COLLATE NOCASE").fetchall()
    return ("PRODUCTOS (id | nombre | precio):\n"
            + "\n".join(f"{p[0]} | {p[1]} | {pesos(p[2])}" for p in productos)
            + "\n\nCLIENTES (id | nombre):\n"
            + "\n".join(f"{c[0]} | {c[1]}" for c in clientes))


def escuchar(audio, tipo, catalogo):
    """Manda el audio a Gemini y devuelve lo que entendió (dict con la forma
    de ESQUEMA). Lanza RuntimeError con un mensaje para mostrar."""
    clave = os.environ.get("GEMINI_API_KEY")
    if not clave:
        raise RuntimeError("Falta la clave de Gemini (GEMINI_API_KEY) en el servidor.")
    cuerpo = {
        "systemInstruction": {"parts": [{"text": INSTRUCCIONES}]},
        "contents": [{"role": "user", "parts": [
            {"text": catalogo},
            {"inlineData": {"mimeType": tipo, "data": base64.b64encode(audio).decode()}},
        ]}],
        "generationConfig": {"responseMimeType": "application/json",
                             "responseJsonSchema": ESQUEMA},
    }
    pedido = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent",
        data=json.dumps(cuerpo).encode(), method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": clave})
    try:
        # Menos que los 60 s de gunicorn, para poder mostrar el error
        with urllib.request.urlopen(pedido, timeout=50) as r:
            respuesta = json.load(r)
    except urllib.error.HTTPError as e:
        try:
            detalle = json.load(e).get("error", {}).get("message", "")
        except ValueError:
            detalle = ""
        if e.code == 429:
            raise RuntimeError("Gemini dice que se pasó el límite de uso por ahora. "
                               "Espere un rato y vuelva a intentar.") from e
        raise RuntimeError(f"Gemini respondió con error {e.code}. {detalle}".strip()) from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError("No se pudo hablar con Gemini (sin conexión o tardó demasiado). "
                           "Vuelva a intentar.") from e
    try:
        partes = respuesta["candidates"][0]["content"]["parts"]
        texto = "".join(p.get("text", "") for p in partes if not p.get("thought"))
        resultado = json.loads(texto)
    except (KeyError, IndexError, ValueError) as e:
        raise RuntimeError("Gemini no devolvió una respuesta que se pueda leer. "
                           "Vuelva a intentar.") from e
    if not isinstance(resultado, dict) or not isinstance(resultado.get("lineas"), list):
        raise RuntimeError("Gemini devolvió algo incompleto. Vuelva a intentar.")
    return resultado


def _tipo_gemini(fila):
    extension = (fila["nombre"] or "").rsplit(".", 1)[-1].lower()
    return TIPOS[extension][1] if extension in TIPOS else fila["tipo"]


@app.post("/audios/<int:audio_id>/procesar")
@requiere_ingreso
def audio_procesar(audio_id):
    _revisar_csrf()
    conn = _conn()
    fila = conn.execute("SELECT id, nombre, tipo, audio, estado FROM audios_venta WHERE id = ?",
                        (audio_id,)).fetchone()
    if fila is None or fila["estado"] == "registrado":
        return _respuesta_procesar(audio_id)
    try:
        resultado = escuchar(bytes(fila["audio"]), _tipo_gemini(fila), _catalogo(conn))
        conn.execute("UPDATE audios_venta SET estado = 'listo', resultado = ?, error = NULL "
                     "WHERE id = ?", (json.dumps(resultado, ensure_ascii=False), audio_id))
    except RuntimeError as e:
        conn.execute("UPDATE audios_venta SET estado = 'error', error = ? WHERE id = ?",
                     (str(e), audio_id))
    conn.commit()
    return _respuesta_procesar(audio_id)


def _respuesta_procesar(audio_id):
    # La página los procesa uno por uno con fetch; sin JavaScript, el botón
    # vuelve a la lista.
    if request.headers.get("X-Fetch"):
        return "", 204
    return redirect(url_for("audios") + f"#audio-{audio_id}")


@app.post("/audios/<int:audio_id>/descartar")
@requiere_ingreso
def audio_descartar(audio_id):
    _revisar_csrf()
    conn = _conn()
    conn.execute("DELETE FROM audios_venta WHERE id = ? AND estado != 'registrado'", (audio_id,))
    conn.commit()
    return redirect(url_for("audios"))


@app.get("/audios/<int:audio_id>/archivo")
@requiere_ingreso
def audio_archivo(audio_id):
    fila = _conn().execute("SELECT tipo, audio FROM audios_venta WHERE id = ?",
                           (audio_id,)).fetchone()
    if fila is None or fila["audio"] is None:
        abort(404)
    return app.response_class(bytes(fila["audio"]), mimetype=fila["tipo"] or "audio/ogg")


# ── Revisar ──────────────────────────────────────────────────────────────────
def resumen(conn, resultado):
    """Lo que entendió Gemini, con los nombres y precios de la base, para
    mostrarlo y para armar el carrito de la venta."""
    ids = {int(l.get("producto_id") or 0) for l in resultado.get("lineas", [])}
    productos = {f[0]: f for f in conn.execute(
        f"SELECT id, name, price, stock FROM products WHERE id IN ({', '.join('?' * len(ids))})",
        tuple(ids)).fetchall()} if ids else {}
    cliente = None
    if resultado.get("cliente_id"):
        cliente = conn.execute("SELECT id, name, total_debt FROM clients WHERE id = ?",
                               (int(resultado["cliente_id"]),)).fetchone()
    lineas, total = [], 0.0
    for l in resultado.get("lineas", []):
        p = productos.get(int(l.get("producto_id") or 0))
        dinero = int(l.get("dinero") or 0)
        cantidad = float(l.get("cantidad") or 0)
        if p is not None and dinero > 0 and p["price"]:
            cantidad = dinero / p["price"]
        subtotal = dinero if dinero > 0 else (p["price"] * cantidad if p is not None else 0)
        problema = ("no está en el inventario" if p is None
                    else "sin cantidad" if cantidad <= 0
                    else "sin stock en el sistema" if (p["stock"] or 0) <= 0
                    else f"solo hay {p['stock']:g} en el sistema" if cantidad > p["stock"] + 1e-9
                    else None)
        lineas.append({"id": p["id"] if p is not None else None,
                       "nombre": p["name"] if p is not None else l.get("producto_dicho") or "¿?",
                       "dicho": l.get("producto_dicho") or "", "cantidad": cantidad,
                       "dinero": dinero, "subtotal": subtotal, "problema": problema})
        total += subtotal
    return {"transcripcion": resultado.get("transcripcion") or "",
            "fiada": resultado.get("tipo") == "fiado", "cliente": cliente,
            "cliente_dicho": resultado.get("cliente_dicho") or "",
            "lineas": lineas, "total": total, "dudas": resultado.get("dudas") or []}


def fecha_sugerida(fila):
    return (fila["grabado_en"] or fila["recibido_en"] or date.today().isoformat())[:10]


def contexto_para_venta(audio_id):
    """Para la pantalla de nueva venta: el audio, lo que se entendió y el
    carrito ya armado. None si el audio no existe o ya se registró."""
    conn = _conn()
    fila = conn.execute("SELECT * FROM audios_venta WHERE id = ?", (audio_id,)).fetchone()
    if fila is None or fila["estado"] != "listo":
        return None
    r = resumen(conn, json.loads(fila["resultado"]))
    borrador = {
        # Las líneas con problema no entran al carrito: se muestran aparte
        "lineas": [{"id": l["id"], "m": str(l["dinero"])} if l["dinero"] > 0
                   else {"id": l["id"], "q": f"{l['cantidad']:g}"}
                   for l in r["lineas"] if not l["problema"]],
        "fiada": r["fiada"], "cliente": r["cliente"]["id"] if r["cliente"] else None,
        "ajuste": "", "signo": "+", "motivo": "",
        "audio": audio_id, "fecha": fecha_sugerida(fila),
    }
    return {"id": audio_id, "resumen": r, "borrador": borrador,
            "fuera": [l for l in r["lineas"] if l["problema"]],
            "fecha_en_nombre": bool(fila["grabado_en"]), "hoy": date.today().isoformat()}


def fecha_de_venta(conn, audio_id, dia):
    """El momento con que se guarda la venta: hoy → ahora; otro día → la hora
    del audio si la trae y es de ese día, si no el mediodía."""
    if dia == date.today():
        return None
    fila = conn.execute("SELECT grabado_en FROM audios_venta WHERE id = ?", (audio_id,)).fetchone()
    grabado = fila["grabado_en"] if fila else None
    if grabado and len(grabado) > 10 and grabado[:10] == dia.isoformat():
        return grabado
    return f"{dia.isoformat()} 12:00:00"


def marcar_registrado(conn, audio_id, sale_id):
    """Dentro de la transacción de la venta. El audio se borra (la
    transcripción queda); devuelve False si ya estaba registrado."""
    fila = conn.execute("SELECT estado FROM audios_venta WHERE id = ?", (audio_id,)).fetchone()
    if fila is None or fila["estado"] == "registrado":
        return False
    conn.execute("UPDATE audios_venta SET estado = 'registrado', sale_id = ?, audio = NULL "
                 "WHERE id = ?", (sale_id, audio_id))
    return True


@app.get("/audios")
@requiere_ingreso
def audios():
    conn = _conn()
    filas = conn.execute("""
        SELECT id, recibido_en, nombre, grabado_en, estado, resultado, error
          FROM audios_venta WHERE estado != 'registrado'
         ORDER BY COALESCE(grabado_en, recibido_en), id""").fetchall()
    pendientes = []
    for f in filas:
        pendientes.append({"id": f["id"], "nombre": f["nombre"], "estado": f["estado"],
                           "error": f["error"], "fecha": fecha_sugerida(f),
                           "hora": (f["grabado_en"] or "")[11:16],
                           "fecha_en_nombre": bool(f["grabado_en"]),
                           "r": resumen(conn, json.loads(f["resultado"])) if f["resultado"] else None})
    registrados = conn.execute("""
        SELECT a.sale_id, s.total, s.created_at, c.name AS cliente
          FROM audios_venta a LEFT JOIN sales s ON s.id = a.sale_id
          LEFT JOIN clients c ON c.id = s.client_id
         WHERE a.estado = 'registrado' ORDER BY a.id DESC LIMIT 10""").fetchall()
    return render_template(
        "audios.html", pendientes=pendientes, registrados=registrados,
        sin_clave=not os.environ.get("GEMINI_API_KEY"),
        aviso=session.pop("aviso_audios", None), error=session.pop("aviso_audios_error", None),
        url_atajo=_url_atajo())


def _url_atajo():
    # Render recibe https y le pasa http a la página: la dirección pública es https
    raiz = request.url_root if DESARROLLO else request.url_root.replace("http://", "https://", 1)
    return raiz.rstrip("/") + url_for("audios_recibir") + "?clave=" + clave_atajo()


@app.template_filter("dia_corto")
def dia_corto(texto):
    dias = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
    d = datetime.strptime(texto[:10], "%Y-%m-%d").date()
    return f"{dias[d.weekday()]} {d.day}/{d.month}"
