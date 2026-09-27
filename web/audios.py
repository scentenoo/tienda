"""Ventas por audio: las notas de voz de WhatsApp se suben a la página (desde
el atajo del iPhone o eligiéndolas a mano), Gemini las escucha y arma la
venta, y aquí se revisan una por una antes de guardarlas con la pantalla de
venta de siempre. Nada se guarda como venta sin que alguien lo confirme.

Necesita GEMINI_API_KEY (se saca gratis en aistudio.google.com). Con
GEMINI_MODELO se pueden cambiar los modelos (separados por comas, en orden).
Con GROQ_API_KEY (gratis en console.groq.com), si Gemini falla o se queda sin
cupo, el audio lo escucha Groq: primero lo pasa a texto con Whisper y luego
arma la venta (GROQ_MODELO, igual que GEMINI_MODELO).
"""
import base64
import hashlib
import hmac
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime

from flask import abort, redirect, render_template, request, session, url_for

from web.app import DESARROLLO, _revisar_csrf, app, db, pesos, requiere_ingreso

# Si uno está saturado (Google responde 503) o se acabó su cupo gratis del
# día (429), se prueba el siguiente.
MODELOS = [m.strip() for m in os.environ.get(
    "GEMINI_MODELO", "gemini-3.8-flash,gemini-3.7-flash,gemini-2.5-flash,"
                     "gemini-3.1-flash-lite,gemini-2.5-flash-lite").split(",") if m.strip()]
PASAR_AL_SIGUIENTE = {404, 429, 500, 503, 504}
# Un modelo sin cupo (429) o que no existe (404) no se vuelve a pedir en un
# rato: cada intento gastaría más cupo o tiempo. modelo → hasta cuándo.
_en_pausa = {}
PAUSA = {429: 15 * 60, 404: 6 * 60 * 60}
GROQ_MODELOS = [m.strip() for m in os.environ.get(
    "GROQ_MODELO", "openai/gpt-oss-120b,openai/gpt-oss-20b").split(",") if m.strip()]
GROQ_WHISPER = "whisper-large-v3"
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
    """Lo que se entendió del audio (dict con la forma de ESQUEMA, más
    "motor": quién lo escuchó). Primero Gemini, que oye el audio directo; si
    falla o no tiene cupo, Groq. Lanza RuntimeError con un mensaje para
    mostrar."""
    gemini, groq = os.environ.get("GEMINI_API_KEY"), os.environ.get("GROQ_API_KEY")
    if not (gemini or groq):
        raise RuntimeError("Falta la clave de Gemini (GEMINI_API_KEY) en el servidor.")
    # Todo debe caber en los 60 s de gunicorn, para poder mostrar el error
    limite = time.monotonic() + 50
    error_gemini = None
    if gemini:
        try:
            # Con Groq de respaldo, a Gemini se le dejan 25 s menos para Groq
            resultado = _escuchar_gemini(gemini, audio, tipo, catalogo,
                                         limite - 25 if groq else limite)
            return {**resultado, "motor": "Gemini"}
        except RuntimeError as e:
            if not groq:
                raise
            error_gemini = e
    try:
        resultado = _escuchar_groq(groq, audio, tipo, catalogo, limite)
    except RuntimeError as e:
        if error_gemini:
            raise RuntimeError(f"{error_gemini} Groq tampoco pudo: {e}") from e
        raise
    return {**resultado, "motor": "Groq"}


def _escuchar_gemini(clave, audio, tipo, catalogo, limite):
    cuerpo = {
        "systemInstruction": {"parts": [{"text": INSTRUCCIONES}]},
        "contents": [{"role": "user", "parts": [
            {"text": catalogo},
            {"inlineData": {"mimeType": tipo, "data": base64.b64encode(audio).decode()}},
        ]}],
        "generationConfig": {"responseMimeType": "application/json",
                             "responseJsonSchema": ESQUEMA},
    }
    datos = json.dumps(cuerpo).encode()
    # Dos vueltas por la lista: una saturación suele durar segundos
    respuesta, codigos, intentos = None, [], []
    for modelo in MODELOS + [None] + MODELOS:
        quedan = limite - time.monotonic()
        if quedan < 5:
            break
        if modelo is None:          # entre vuelta y vuelta, una pausa
            if not intentos or all(c in PAUSA for c in codigos):
                break               # nada saturado: otra vuelta no sirve
            time.sleep(min(3, quedan - 5))
            continue
        if _en_pausa.get(modelo, 0) > time.monotonic():
            if f"{modelo}: en pausa" not in intentos:
                intentos.append(f"{modelo}: en pausa")
            continue
        try:
            respuesta = _pedir(modelo, datos, clave, quedan)
            break
        except urllib.error.HTTPError as e:
            if e.code not in PASAR_AL_SIGUIENTE:
                try:
                    detalle = json.load(e).get("error", {}).get("message", "")
                except ValueError:
                    detalle = ""
                raise RuntimeError(f"Gemini respondió con error {e.code}. {detalle}".strip()) from e
            codigos.append(e.code)
            intentos.append(f"{modelo}: {e.code}")
            if e.code in PAUSA:
                _en_pausa[modelo] = time.monotonic() + PAUSA[e.code]
        except (urllib.error.URLError, TimeoutError) as e:
            raise RuntimeError("No se pudo hablar con Gemini (sin conexión o tardó "
                               "demasiado). Vuelva a intentar.") from e
    if respuesta is None:
        if codigos and all(c == 404 for c in codigos):
            raise RuntimeError(f"Ninguno de los modelos de Gemini está disponible ({', '.join(MODELOS)}). "
                               "Revise GEMINI_MODELO en el servidor.")
        if not {500, 503, 504} & set(codigos) and (429 in codigos or not codigos):
            raise RuntimeError("Se acabó por ahora el cupo gratis de Gemini. "
                               "Espere un rato (o hasta mañana) y vuelva a intentar.")
        raise RuntimeError("Gemini está saturado en este momento. Vuelva a intentar en "
                           "unos minutos. (" + ", ".join(intentos) + ")")
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


# ── Escuchar (Groq, de respaldo) ─────────────────────────────────────────────
# Groq no oye el audio: Whisper lo pasa a texto y otro modelo arma la venta
# con las mismas instrucciones.
NOTA_GROQ = """

La nota de voz ya viene pasada a texto, y ese paso pudo equivocarse con los
nombres (de clientes y productos): búscalos por cómo suenan. En transcripcion
devuelve el mismo texto que recibes."""

EXTENSION_GROQ = {"audio/ogg": "ogg", "audio/aac": "m4a", "audio/mp3": "mp3",
                  "audio/mpeg": "mp3", "audio/wav": "wav", "audio/webm": "webm",
                  "audio/flac": "flac"}


def _estricto(esquema):
    """El esquema con additionalProperties: false en cada objeto, como pide
    el modo estricto de Groq."""
    if isinstance(esquema, dict):
        copia = {k: _estricto(v) for k, v in esquema.items()}
        if copia.get("type") == "object":
            copia["additionalProperties"] = False
        return copia
    return esquema


def _groq(ruta, clave, datos, tipo, espera):
    pedido = urllib.request.Request(
        f"https://api.groq.com/openai/v1/{ruta}", data=datos, method="POST",
        headers={"Content-Type": tipo, "Authorization": f"Bearer {clave}",
                 "User-Agent": "charcuteria-hye/1.0"})
    with urllib.request.urlopen(pedido, timeout=espera) as r:
        return json.load(r)


def _formulario(campos, nombre, tipo, contenido):
    """Cuerpo multipart/form-data (urllib no lo arma solo)."""
    borde = uuid.uuid4().hex
    partes = [f'--{borde}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
              for k, v in campos.items()]
    partes.append(f'--{borde}\r\nContent-Disposition: form-data; name="file"; '
                  f'filename="{nombre}"\r\nContent-Type: {tipo}\r\n\r\n'.encode()
                  + contenido + b"\r\n")
    partes.append(f"--{borde}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={borde}"


def _error_groq(e, que):
    if e.code == 401:
        return RuntimeError("La clave de Groq (GROQ_API_KEY) no es válida.")
    if e.code == 429:
        return RuntimeError("Se acabó por ahora el cupo gratis de Groq.")
    return RuntimeError(f"Groq respondió con error {e.code} al {que}. {_detalle(e)}".strip())


def _escuchar_groq(clave, audio, tipo, catalogo, limite):
    # Los nombres del catálogo ayudan a Whisper a escribirlos bien
    nombres = [l.split(" | ")[1] for l in catalogo.splitlines() if l[:1].isdigit() and " | " in l]
    pista = ("Venta en una charcutería. " + ", ".join(nombres))[:600]
    cuerpo, formato = _formulario(
        {"model": GROQ_WHISPER, "language": "es", "response_format": "json", "prompt": pista},
        "audio." + EXTENSION_GROQ.get(tipo, "ogg"), tipo, audio)
    try:
        texto = _groq("audio/transcriptions", clave, cuerpo, formato,
                      max(5, limite - time.monotonic()))["text"].strip()
    except urllib.error.HTTPError as e:
        raise _error_groq(e, "pasar el audio a texto") from e
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
        raise RuntimeError("No se pudo pasar el audio a texto con Groq.") from e
    if not texto:
        raise RuntimeError("Groq no entendió nada en el audio.")

    datos = json.dumps({
        "messages": [
            {"role": "system", "content": INSTRUCCIONES + NOTA_GROQ},
            {"role": "user", "content": catalogo + "\n\nNOTA DE VOZ (pasada a texto):\n" + texto},
        ],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "venta", "strict": True, "schema": _estricto(ESQUEMA)}},
    })
    ultimo = None
    for modelo in GROQ_MODELOS:
        if _en_pausa.get("groq:" + modelo, 0) > time.monotonic():
            continue
        quedan = limite - time.monotonic()
        if quedan < 3:
            break
        try:
            respuesta = _groq("chat/completions", clave,
                              json.dumps({"model": modelo, **json.loads(datos)}).encode(),
                              "application/json", quedan)
            resultado = json.loads(respuesta["choices"][0]["message"]["content"])
        except urllib.error.HTTPError as e:
            ultimo = _error_groq(e, "armar la venta")
            if e.code in PAUSA:
                _en_pausa["groq:" + modelo] = time.monotonic() + PAUSA[e.code]
            if e.code in PASAR_AL_SIGUIENTE:
                continue
            raise ultimo from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise RuntimeError("No se pudo hablar con Groq (sin conexión o tardó demasiado).") from e
        except (KeyError, IndexError, ValueError) as e:
            ultimo = RuntimeError("Groq no devolvió una respuesta que se pueda leer.")
            continue
        if isinstance(resultado, dict) and isinstance(resultado.get("lineas"), list):
            resultado["transcripcion"] = texto
            return resultado
        ultimo = RuntimeError("Groq devolvió algo incompleto.")
    raise ultimo or RuntimeError("Se acabó por ahora el cupo gratis de Groq.")


def _pedir(modelo, datos, clave, espera):
    pedido = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
        data=datos, method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": clave})
    with urllib.request.urlopen(pedido, timeout=espera) as r:
        return json.load(r)


@app.get("/audios/diagnostico")
@requiere_ingreso
def audios_diagnostico():
    """Qué modelos ve la clave de Gemini y cómo responde cada uno a un
    mensaje corto de texto. Para cuando todo sale "saturado"."""
    clave = os.environ.get("GEMINI_API_KEY")
    lineas = _diagnostico_gemini(clave) if clave else ["Gemini: sin clave (GEMINI_API_KEY)."]
    groq = os.environ.get("GROQ_API_KEY")
    lineas.append("")
    if not groq:
        lineas.append("Groq (respaldo): sin clave (GROQ_API_KEY).")
    else:
        try:
            pedido = urllib.request.Request(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {groq}", "User-Agent": "charcuteria-hye/1.0"})
            with urllib.request.urlopen(pedido, timeout=10) as r:
                ids = {m["id"] for m in json.load(r).get("data", [])}
            lineas.append("Groq (respaldo): la clave funciona.")
            for m in [GROQ_WHISPER] + GROQ_MODELOS:
                lineas.append(f"  {m}: {'disponible' if m in ids else 'NO disponible'}")
        except urllib.error.HTTPError as e:
            lineas.append(f"Groq (respaldo): error {e.code} {_detalle(e)}")
        except (urllib.error.URLError, TimeoutError):
            lineas.append("Groq (respaldo): no respondió")
    return _texto("\n".join(lineas))


def _diagnostico_gemini(clave):
    lineas = []
    try:
        pedido = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",
            headers={"x-goog-api-key": clave})
        with urllib.request.urlopen(pedido, timeout=15) as r:
            modelos = [m["name"].split("/", 1)[1] for m in json.load(r).get("models", [])
                       if "generateContent" in m.get("supportedGenerationMethods", [])]
        lineas.append(f"La clave ve {len(modelos)} modelos. Los 'flash':")
        lineas += ["  " + m for m in modelos if "flash" in m]
    except urllib.error.HTTPError as e:
        modelos = []
        lineas.append(f"Listar modelos: error {e.code} {_detalle(e)}")
    except (urllib.error.URLError, TimeoutError) as e:
        modelos = []
        lineas.append(f"Listar modelos: sin conexión ({e})")
    lineas.append("")
    lineas.append("Prueba con texto (sin audio):")
    probar = MODELOS + [m for m in modelos if "flash" in m and m not in MODELOS
                        and "image" not in m and "tts" not in m and "live" not in m][:4]
    datos = json.dumps({"contents": [{"parts": [{"text": "Responde solo: ok"}]}]}).encode()
    limite = time.monotonic() + 45
    for modelo in probar:
        quedan = limite - time.monotonic()
        if quedan < 3:
            lineas.append(f"  {modelo}: sin tiempo para probarlo")
            continue
        inicio = time.monotonic()
        try:
            _pedir(modelo, datos, clave, min(quedan, 15))
            lineas.append(f"  {modelo}: BIEN ({time.monotonic() - inicio:.1f} s)")
        except urllib.error.HTTPError as e:
            lineas.append(f"  {modelo}: error {e.code} {_detalle(e)}")
        except (urllib.error.URLError, TimeoutError):
            lineas.append(f"  {modelo}: no respondió a tiempo")
    return lineas


def _detalle(error):
    try:
        return json.load(error).get("error", {}).get("message", "")[:200]
    except ValueError:
        return ""


def _texto(contenido):
    return app.response_class(contenido, mimetype="text/plain; charset=utf-8")


def _tipo_gemini(fila):
    extension = (fila["nombre"] or "").rsplit(".", 1)[-1].lower()
    return TIPOS[extension][1] if extension in TIPOS else fila["tipo"]


# Los audios que Gemini está escuchando ahora. La página corre en un solo
# proceso (ver Dockerfile), así que basta con tenerlos en memoria.
_escuchando = set()
_candado = threading.Lock()


@app.post("/audios/<int:audio_id>/procesar")
@requiere_ingreso
def audio_procesar(audio_id):
    _revisar_csrf()
    conn = _conn()
    fila = conn.execute("SELECT id, nombre, tipo, audio, estado FROM audios_venta WHERE id = ?",
                        (audio_id,)).fetchone()
    if fila is None or fila["estado"] == "registrado":
        return _respuesta_procesar(audio_id)
    # Un toque repetido mientras Gemini escucha no lo manda otra vez
    with _candado:
        if audio_id in _escuchando:
            return _respuesta_procesar(audio_id)
        _escuchando.add(audio_id)
    try:
        resultado = escuchar(bytes(fila["audio"]), _tipo_gemini(fila), _catalogo(conn))
        conn.execute("UPDATE audios_venta SET estado = 'listo', resultado = ?, error = NULL "
                     "WHERE id = ?", (json.dumps(resultado, ensure_ascii=False), audio_id))
    except RuntimeError as e:
        conn.execute("UPDATE audios_venta SET estado = 'error', error = ? WHERE id = ?",
                     (str(e), audio_id))
    finally:
        with _candado:
            _escuchando.discard(audio_id)
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
            "lineas": lineas, "total": total, "dudas": resultado.get("dudas") or [],
            "motor": resultado.get("motor")}


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
                           "escuchando": f["id"] in _escuchando,
                           "r": resumen(conn, json.loads(f["resultado"])) if f["resultado"] else None})
    registrados = conn.execute("""
        SELECT a.sale_id, s.total, s.created_at, c.name AS cliente
          FROM audios_venta a LEFT JOIN sales s ON s.id = a.sale_id
          LEFT JOIN clients c ON c.id = s.client_id
         WHERE a.estado = 'registrado' ORDER BY a.id DESC LIMIT 10""").fetchall()
    return render_template(
        "audios.html", pendientes=pendientes, registrados=registrados,
        sin_clave=not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GROQ_API_KEY")),
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
