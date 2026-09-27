"""Historial de la página del celular: quién entró y a qué hora, qué
pantallas abrió, qué guardó, cambió o borró (con el antes y el después), lo
que intentó y no se guardó, y lo que dejó sin confirmar.

Solo lo ve el dueño: con la contraseña de la hermana la página del historial
responde como si no existiera (igual que los gastos), y no hay nada que le
avise que se anota lo que hace.

Nada de lo de aquí puede dañar una venta o un abono: si anotar falla, se
deja pasar sin decir nada."""
import json
import re
import time
from datetime import date, datetime, timedelta

from flask import g, render_template, request, session, template_rendered

from web.app import (_dia_largo, _leer_decimal, _leer_monto, app, cantidad, db, fecha,
                     pesos, requiere_gastos, requiere_ingreso)

# ── La tabla ─────────────────────────────────────────────────────────────────
_tabla_lista = False


def _preparar(conn):
    global _tabla_lista
    if not _tabla_lista:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                momento TEXT NOT NULL,
                quien TEXT NOT NULL,     -- dueño, hermana o ? (contraseña equivocada)
                clase TEXT NOT NULL,     -- visita, ingreso, nuevo, cambio, borrado, paso, fallido
                accion TEXT NOT NULL,
                detalle TEXT,            -- lo que escribió; en los cambios, el antes y el después
                resultado TEXT,          -- vacío si se hizo; si no, por qué no
                equipo TEXT,
                ruta TEXT)""")
        conn.execute("CREATE INDEX IF NOT EXISTS historial_momento ON historial (momento)")
        conn._conn.commit()
        _tabla_lista = True


def _quien():
    if not session.get("ingreso"):
        return None
    return "hermana" if session.get("sin_gastos") else "dueño"


def _equipo():
    ua = request.headers.get("User-Agent", "")
    sistema = next((n for clave, n in (("iPhone", "iPhone"), ("iPad", "iPad"),
                                       ("Android", "Android"), ("Windows", "Windows"),
                                       ("Mac OS", "Mac")) if clave in ua), "Otro")
    ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()
    return f"{sistema} · {ip}" if ip else sistema


# ── Fotos: cómo estaba algo antes (y después) de tocarlo ─────────────────────
def _nombre(conn, tabla, id_):
    fila = conn.execute(f"SELECT name FROM {tabla} WHERE id = ?", (id_,)).fetchone()
    return fila[0] if fila else f"#{id_}"


def _foto_cliente(conn, i):
    c = conn.execute("SELECT name, phone, address, credit_limit, notes, total_debt "
                     "FROM clients WHERE id = ?", (i,)).fetchone()
    return c and {"Nombre": c["name"], "Teléfono": c["phone"] or "", "Dirección": c["address"] or "",
                  "Límite de crédito": pesos(c["credit_limit"]), "Notas": c["notes"] or "",
                  "Deuda": pesos(c["total_debt"])}


def _foto_venta(conn, i):
    v = conn.execute("""SELECT s.created_at, s.total, s.payment_method, s.status, c.name
                          FROM sales s LEFT JOIN clients c ON c.id = s.client_id
                         WHERE s.id = ?""", (i,)).fetchone()
    if v is None:
        return None
    productos = ", ".join(f"{cantidad(q)} × {n}" for q, n in conn.execute("""
        SELECT d.quantity, COALESCE(p.name, 'Producto') FROM sale_details d
          LEFT JOIN products p ON p.id = d.product_id WHERE d.sale_id = ? ORDER BY d.id""", (i,)))
    return {"Venta": f"#{i} del {fecha(v['created_at'])}", "Total": pesos(v["total"]),
            "Tipo": "Fiada" if v["payment_method"] == "credit" else "Contado",
            "Cliente": v["name"] or "—", "Productos": productos or "—"}


def _foto_producto(conn, i):
    p = conn.execute("SELECT name, price, stock, cost_price FROM products WHERE id = ?",
                     (i,)).fetchone()
    return p and {"Nombre": p["name"], "Precio": pesos(p["price"]), "Stock": cantidad(p["stock"]),
                  "Costo": pesos(p["cost_price"])}


def _foto_compra(conn, i):
    c = conn.execute("""
        SELECT pu.date, pu.total, pu.iva, pu.shipping, pu.invoice_number, pd.quantity,
               COALESCE(p.name, 'Producto') AS producto
          FROM purchases pu LEFT JOIN purchase_details pd ON pd.purchase_id = pu.id
          LEFT JOIN products p ON p.id = pd.product_id WHERE pu.id = ?""", (i,)).fetchone()
    return c and {"Compra": f"#{i} del {fecha(c['date'], False)}",
                  "Producto": f"{cantidad(c['quantity'])} × {c['producto']}",
                  "Total": pesos(c["total"]), "IVA": pesos(c["iva"]), "Flete": pesos(c["shipping"]),
                  "Factura": c["invoice_number"] or ""}


def _foto_perdida(conn, i):
    p = conn.execute("""
        SELECT l.quantity, l.total_cost, l.loss_date, l.reason, l.loss_type,
               COALESCE(p.name, 'Producto eliminado') AS producto
          FROM losses l LEFT JOIN products p ON p.id = l.product_id WHERE l.id = ?""",
                     (i,)).fetchone()
    return p and {"Producto": f"{cantidad(p['quantity'])} × {p['producto']}",
                  "Costo": pesos(p["total_cost"]), "Fecha": fecha(p["loss_date"], False),
                  "Tipo": p["loss_type"] or "", "Motivo": p["reason"] or ""}


def _foto_gasto(conn, i):
    e = conn.execute("SELECT description, amount, date FROM expenses WHERE id = ?", (i,)).fetchone()
    return e and {"Descripción": e["description"], "Monto": pesos(e["amount"]),
                  "Fecha": fecha(e["date"], False)}


def _foto_audio(conn, i):
    a = conn.execute("SELECT nombre, resultado FROM audios_venta WHERE id = ?", (i,)).fetchone()
    if a is None:
        return None
    try:
        dicho = json.loads(a["resultado"]).get("transcripcion", "") if a["resultado"] else ""
    except (ValueError, AttributeError):
        dicho = ""
    return {"Audio": a["nombre"] or f"#{i}", "Decía": dicho or "(sin escuchar)"}


# vista → (argumento de la dirección, foto)
FOTOS = {
    "cliente_editar": ("client_id", _foto_cliente),
    "cliente_eliminar": ("client_id", _foto_cliente),
    "venta_editar": ("sale_id", _foto_venta),
    "venta_eliminar": ("sale_id", _foto_venta),
    "producto_editar": ("product_id", _foto_producto),
    "producto_eliminar": ("product_id", _foto_producto),
    "compra": ("purchase_id", _foto_compra),
    "compra_eliminar": ("purchase_id", _foto_compra),
    "perdida_eliminar": ("loss_id", _foto_perdida),
    "gasto": ("expense_id", _foto_gasto),
    "audio_descartar": ("audio_id", _foto_audio),
}


def _foto():
    arg, foto = FOTOS[request.endpoint]
    i = (request.view_args or {}).get(arg)
    return foto(db(), i) if i is not None else None


def _como_texto(foto):
    return "\n".join(f"{k}: {v}" for k, v in (foto or {}).items() if v not in ("", None))


def _cambios(antes, despues):
    if not antes or not despues:
        return _como_texto(antes)
    lineas = [f"{k}: {antes[k] or '—'} → {despues.get(k) or '—'}"
              for k in antes if antes[k] != despues.get(k)]
    return "\n".join(lineas) or "Guardó sin cambiar nada"


# ── Qué se hizo, en palabras ─────────────────────────────────────────────────
def _escrito(*campos):
    """Lo que escribió en el formulario: ('nota', 'Nota'), ..."""
    f = request.form
    return "\n".join(f"{etiqueta}: {f.get(c).strip()}" for c, etiqueta in campos
                     if (f.get(c) or "").strip())


def _id(nombre):
    return (request.view_args or {}).get(nombre)


def _visita(conn):
    """Texto de una pantalla abierta (GET), o None si no vale la pena anotarla."""
    a = request.args
    ep = request.endpoint
    buscado = f' (buscó "{a["q"]}")' if a.get("q") else ""
    cliente = lambda: _nombre(conn, "clients", _id("client_id"))  # noqa: E731

    def dia(clave="dia"):
        try:
            return " del " + fecha(date.fromisoformat(a.get(clave, "")).isoformat(), False)
        except ValueError:
            return " de hoy"

    textos = {
        "inicio": lambda: "Abrió Inicio",
        "mas": lambda: "Abrió el menú Más",
        "pendientes": lambda: "Abrió Pendientes",
        "pendientes_informe": lambda: "Descargó el informe de pendientes",
        "clientes": lambda: "Abrió Clientes" + buscado,
        "cliente": lambda: f"Abrió el cliente {cliente()}" + (" (todo el historial)" if a.get("todo") else ""),
        "estado_de_cuenta": lambda: f"Abrió el estado de cuenta de {cliente()}",
        "abono": lambda: f"Abrió el formulario de abono de {cliente()}",
        "cliente_nuevo": lambda: "Abrió el formulario de cliente nuevo",
        "cliente_editar": lambda: f"Abrió editar el cliente {cliente()}",
        "cliente_eliminar": lambda: f"Abrió eliminar el cliente {cliente()}",
        "cliente_deuda": lambda: f"Abrió agregar deuda a {cliente()}",
        "venta_nueva": lambda: "Abrió Vender" + (" desde un audio" if a.get("audio") else ""),
        "venta": lambda: f"Abrió la venta #{_id('sale_id')}",
        "venta_editar": lambda: f"Abrió editar la venta #{_id('sale_id')}",
        "venta_eliminar": lambda: f"Abrió eliminar la venta #{_id('sale_id')}",
        "ventas": lambda: "Abrió Ventas" + dia(),
        "inventario": lambda: "Abrió Inventario" + buscado,
        "producto_nuevo": lambda: "Abrió el formulario de producto nuevo",
        "producto_editar": lambda: f"Abrió el producto {_nombre(conn, 'products', _id('product_id'))}",
        "compras": lambda: "Abrió Compras" + (f" de {a['mes']}" if a.get("mes") else ""),
        "compra_nueva": lambda: "Abrió el formulario de compra nueva",
        "compra": lambda: f"Abrió la compra #{_id('purchase_id')}",
        "gastos": lambda: "Abrió Gastos" + (f" de {a['mes']}" if a.get("mes") else ""),
        "gasto": lambda: (f"Abrió el gasto #{_id('expense_id')}" if _id("expense_id")
                          else "Abrió el formulario de gasto nuevo"),
        "perdidas": lambda: "Abrió Pérdidas" + (f" de {a['mes']}" if a.get("mes") else ""),
        "perdida_nueva": lambda: "Abrió el formulario de pérdida nueva",
        "caja": lambda: "Abrió Caja" + dia(),
        "audios": lambda: "Abrió Ventas por audio",
        "audio_archivo": lambda: f"Escuchó el audio #{_id('audio_id')}",
        "audios_diagnostico": lambda: "Abrió el diagnóstico de audios",
        "historial": lambda: "Intentó abrir el Historial",
    }
    return textos[ep]() if ep in textos else f"Abrió {request.path}"


def _resultado(conn, plantillas):
    """'' si se guardó; si no, por qué no."""
    if conn.guardo:
        return ""
    for nombre, ctx in reversed(plantillas):
        if ctx.get("error"):
            return f"No se guardó: {ctx['error']}"
        if nombre == "aviso.html":
            return f"No se guardó: {ctx.get('mensaje') or ctx.get('titulo')}"
    return "No se guardó nada"


def _accion(conn, plantillas, resp):
    """(clase, acción, detalle, resultado) de un envío de formulario (POST)."""
    ep, f = request.endpoint, request.form
    ctx = plantillas[-1][1] if plantillas else {}
    plantilla = plantillas[-1][0] if plantillas else ""
    resultado = _resultado(conn, plantillas)
    antes = g.get("antes")

    if ep == "ingresar":
        if session.get("ingreso"):
            return "ingreso", "Entró a la página", "", ""
        return "fallido", "Intentó entrar con una contraseña equivocada", "", ctx.get("error") or ""
    if ep == "salir":
        return "ingreso", "Salió de la página", "", ""

    # ── Clientes y abonos
    if ep == "abono":
        nombre = _nombre(conn, "clients", _id("client_id"))
        if plantilla == "abono_confirmar.html":
            que = "un pago total" if ctx.get("pago_total") else "un abono"
            return ("paso", f"Empezó {que} de {pesos(ctx.get('monto'))} a {nombre}",
                    f"Nota: {ctx.get('nota')}", "Falta tocar Confirmar")
        return "fallido", f"Intentó un abono a {nombre}", _escrito(("monto", "Monto"), ("nota", "Nota")), resultado
    if ep == "abono_confirmar":
        p = g.pendiente.get("abono_pendiente") or {}
        nombre = _nombre(conn, "clients", _id("client_id"))
        if conn.guardo:
            deuda = conn.execute("SELECT total_debt FROM clients WHERE id = ?",
                                 (_id("client_id"),)).fetchone()
            que = "un pago total" if p.get("pago_total") else "un abono"
            return ("nuevo", f"Registró {que} de {pesos(p.get('monto'))} a {nombre}",
                    f"Nota: {p.get('nota')}\nLa deuda quedó en {pesos(deuda[0] if deuda else 0)}", "")
        return ("fallido", f"Tocó Confirmar en un abono a {nombre}", "",
                resultado if resultado != "No se guardó nada"
                else "No se guardó: ya estaba guardado (doble toque) o la confirmación caducó")
    if ep == "cliente_nuevo":
        return ("nuevo" if conn.guardo else "fallido", f"Creó el cliente {f.get('nombre', '').strip()}",
                _escrito(("telefono", "Teléfono"), ("direccion", "Dirección"),
                         ("limite", "Límite de crédito"), ("notas", "Notas")), resultado)
    if ep == "cliente_editar":
        nombre = (antes or {}).get("Nombre") or _nombre(conn, "clients", _id("client_id"))
        despues = _foto_cliente(conn, _id("client_id")) if conn.guardo else None
        return ("cambio" if conn.guardo else "fallido", f"Editó el cliente {nombre}",
                _cambios(antes, despues) if conn.guardo else _escrito(
                    ("nombre", "Nombre"), ("telefono", "Teléfono"), ("direccion", "Dirección"),
                    ("limite", "Límite de crédito"), ("notas", "Notas")), resultado)
    if ep == "cliente_eliminar":
        nombre = (antes or {}).get("Nombre", "")
        return ("borrado" if conn.guardo else "fallido", f"Eliminó el cliente {nombre}",
                _como_texto(antes), resultado)
    if ep == "cliente_deuda":
        nombre = _nombre(conn, "clients", _id("client_id"))
        if not conn.guardo and not ctx.get("error"):
            resultado = "No se guardó: ya estaba guardado (doble toque)"
        return ("nuevo" if conn.guardo else "fallido",
                f"Le agregó una deuda de {pesos(_leer_monto(f.get('monto')))} a {nombre}",
                _escrito(("nota", "Nota")), resultado)

    # ── Ventas
    if ep == "venta_nueva":
        if f.get("corregir"):
            return "visita", "Volvió al carrito para corregir la venta", "", ""
        if plantilla == "venta_confirmar.html":
            lineas = [f"{cantidad(i['quantity'])} × {i['product_name']} = {pesos(i['subtotal'])}"
                      for i in ctx.get("items", [])]
            if ctx.get("fiada") and ctx.get("cliente"):
                lineas.append(f"Fiada a {ctx['cliente']['name']}")
            if ctx.get("ajuste"):
                lineas.append(f"Ajuste: {pesos(ctx['ajuste'])} ({ctx.get('motivo') or 'sin motivo'})")
            if ctx.get("momento"):
                lineas.append(f"Fecha de la venta: {ctx['momento']}")
            return ("paso", f"Armó una venta de {pesos(ctx.get('total'))}", "\n".join(lineas),
                    "Falta tocar Confirmar")
        return "fallido", "Intentó armar una venta", "", resultado
    if ep == "venta_confirmar":
        if conn.guardo:
            m = re.search(r"/venta/(\d+)$", resp.location or "")
            sale_id = int(m[1]) if m else (session.get("aviso_audios") or {}).get("sale_id")
            foto = _foto_venta(conn, sale_id) if sale_id else None
            return ("nuevo", f"Guardó la venta #{sale_id} por {(foto or {}).get('Total', '')}"
                    + (" (de un audio)" if (g.pendiente.get("venta_pendiente") or {}).get("audio") else ""),
                    _como_texto(foto), "")
        return ("fallido", "Tocó Confirmar en una venta", "",
                resultado if resultado != "No se guardó nada"
                else "No se guardó: ya estaba guardada (doble toque) o la confirmación caducó")
    if ep == "venta_editar":
        despues = _foto_venta(conn, _id("sale_id")) if conn.guardo else None
        return ("cambio" if conn.guardo else "fallido", f"Editó la venta #{_id('sale_id')}",
                _cambios(antes, despues) if conn.guardo else _como_texto(antes), resultado)
    if ep == "venta_eliminar":
        return ("borrado" if conn.guardo else "fallido", f"Eliminó la venta #{_id('sale_id')}",
                _como_texto(antes), resultado)

    # ── Inventario, compras, gastos, pérdidas
    if ep == "producto_nuevo":
        return ("nuevo" if conn.guardo else "fallido", f"Creó el producto {f.get('nombre', '').strip()}",
                _escrito(("precio", "Precio"), ("stock", "Stock")), resultado)
    if ep == "producto_editar":
        nombre = (antes or {}).get("Nombre", "")
        despues = _foto_producto(conn, _id("product_id")) if conn.guardo else None
        return ("cambio" if conn.guardo else "fallido", f"Editó el producto {nombre}",
                _cambios(antes, despues) if conn.guardo else _escrito(
                    ("nombre", "Nombre"), ("precio", "Precio"), ("stock", "Stock")), resultado)
    if ep == "producto_eliminar":
        return ("borrado" if conn.guardo else "fallido",
                f"Eliminó el producto {(antes or {}).get('Nombre', '')}", _como_texto(antes),
                resultado if conn.guardo else "No se eliminó (se ha usado en ventas o compras)")
    if ep == "compra_nueva":
        try:
            lote = json.loads(f.get("borrador") or "{}")
        except ValueError:
            lote = {}
        lineas = []
        for l in lote.get("lineas", []):
            producto = (f"{l.get('nombre')} (nuevo)" if l.get("nuevo")
                        else _nombre(conn, "products", l.get("id")))
            lineas.append(f"{cantidad(_leer_decimal(l.get('q')))} × {producto} a "
                          f"{pesos(_leer_monto(str(l.get('costo') or '')))}")
        for clave, etiqueta in (("iva", "IVA"), ("flete", "Flete")):
            if _leer_monto(str(lote.get(clave) or "")):
                lineas.append(f"{etiqueta}: {pesos(_leer_monto(str(lote.get(clave))))}")
        if lote.get("factura"):
            lineas.append(f"Factura: {lote['factura']}")
        n = len(lote.get("lineas", []))
        return ("nuevo" if conn.guardo else "fallido",
                f"Registró una compra de {n} producto{'s' if n != 1 else ''}", "\n".join(lineas), resultado)
    if ep == "compra":
        despues = _foto_compra(conn, _id("purchase_id")) if conn.guardo else None
        return ("cambio" if conn.guardo else "fallido", f"Editó la compra #{_id('purchase_id')}",
                _cambios(antes, despues) if conn.guardo else _escrito(
                    ("total", "Total"), ("iva", "IVA"), ("flete", "Flete"), ("factura", "Factura")),
                resultado)
    if ep == "compra_eliminar":
        return ("borrado" if conn.guardo else "fallido", f"Eliminó la compra #{_id('purchase_id')}",
                _como_texto(antes), resultado)
    if ep == "gasto":
        if f.get("eliminar"):
            return ("borrado" if conn.guardo else "fallido", f"Eliminó el gasto #{_id('expense_id')}",
                    _como_texto(antes), resultado)
        if _id("expense_id"):
            despues = _foto_gasto(conn, _id("expense_id")) if conn.guardo else None
            return ("cambio" if conn.guardo else "fallido", f"Editó el gasto #{_id('expense_id')}",
                    _cambios(antes, despues) if conn.guardo else "", resultado)
        return ("nuevo" if conn.guardo else "fallido", f"Registró el gasto {f.get('descripcion', '').strip()}",
                _escrito(("monto", "Monto"), ("fecha", "Fecha")), resultado)
    if ep == "perdida_nueva":
        producto = _nombre(conn, "products", int(f.get("producto") or 0))
        return ("nuevo" if conn.guardo else "fallido",
                f"Registró una pérdida de {cantidad(_leer_decimal(f.get('cantidad')))} × {producto}",
                _escrito(("tipo", "Tipo"), ("motivo", "Motivo"), ("costo", "Costo"),
                         ("fecha", "Fecha"), ("notas", "Notas")), resultado)
    if ep == "perdida_eliminar":
        return ("borrado" if conn.guardo else "fallido", "Eliminó una pérdida",
                _como_texto(antes), resultado if conn.guardo else (session.get("aviso_perdida") or resultado))

    # ── Audios
    if ep == "audios_subir":
        nombres = [a.filename for a in request.files.getlist("audios") if a.filename]
        error = session.get("aviso_audios_error")
        return ("nuevo", f"Subió {len(nombres)} audio{'s' if len(nombres) != 1 else ''}",
                "\n".join(nombres), f"Con problemas: {error}" if error else "")
    if ep == "audio_procesar":
        return "cambio", f"Mandó a escuchar el audio #{_id('audio_id')}", "", ""
    if ep == "audio_descartar":
        return ("borrado" if conn.guardo else "fallido", f"Descartó el audio #{_id('audio_id')}",
                _como_texto(antes), resultado)

    return ("cambio" if conn.guardo else "fallido", f"Envió {request.path}", "", resultado)


# ── Los ganchos ──────────────────────────────────────────────────────────────
NO_ANOTAR = {None, "static", "manifiesto", "audios_recibir"}
# Una recarga o un audio que el navegador pide por partes no se anotan dos veces
_ultima_visita = {}
REPETIDA = 20


def _guardar_plantilla(_app, template, context, **_extra):
    if "historial_plantillas" in g:
        g.historial_plantillas.append((template.name, dict(context)))


template_rendered.connect(_guardar_plantilla, app)


@app.before_request
def _antes_de_la_visita():
    g.historial_plantillas = []
    # Al salir se borra la sesión antes de anotar: se recuerda quién era
    g.quien = _quien()
    try:
        g.pendiente = {k: session.get(k) for k in ("venta_pendiente", "abono_pendiente")}
        if request.method == "POST" and _quien() and request.endpoint in FOTOS:
            g.antes = _foto()
    except Exception:
        app.logger.exception("historial: no se pudo tomar la foto de antes")


@app.after_request
def _anotar(resp):
    try:
        _anotar_visita(resp)
    except Exception:
        app.logger.exception("historial: no se pudo anotar")
    return resp


def _anotar_visita(resp):
    ep = request.endpoint
    quien = g.get("quien") if ep == "salir" else _quien()
    if ep in NO_ANOTAR or request.method not in ("GET", "POST"):
        return
    if not quien and ep != "ingresar":
        return
    if ep == "historial" and quien == "dueño":
        return      # el dueño mirando el historial no se anota a sí mismo
    if ep == "ingresar" and request.method == "GET":
        return

    conn = db()
    if resp.status_code >= 500 and not conn.guardo:
        conn.rollback()
    if request.method == "GET":
        ahora = time.time()
        if _ultima_visita.get(quien) == (request.full_path, int(ahora // REPETIDA)):
            return
        _ultima_visita[quien] = (request.full_path, int(ahora // REPETIDA))
        if resp.status_code == 404 and ep in ("gastos", "gasto", "historial"):
            clase, accion, detalle, resultado = ("fallido", _visita(conn), "",
                                                 "No tiene permiso: le salió «Esa página no existe»")
        else:
            clase, accion, detalle, resultado = "visita", _visita(conn), "", ""
    else:
        if request.endpoint == "gasto" and resp.status_code == 404:
            clase, accion, detalle, resultado = ("fallido", "Intentó guardar un gasto", "",
                                                 "No tiene permiso")
        else:
            clase, accion, detalle, resultado = _accion(conn, g.historial_plantillas, resp)
        quien = quien or "?"

    _preparar(conn)
    conn.execute("""INSERT INTO historial (momento, quien, clase, accion, detalle, resultado, equipo, ruta)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), quien, clase, accion,
                  detalle or None, resultado or None, _equipo(), request.path))
    conn._conn.commit()


# ── La pantalla (solo el dueño) ──────────────────────────────────────────────
CLASES = {
    "ingreso": "Entradas", "nuevo": "Guardó", "cambio": "Cambió", "borrado": "Borró",
    "paso": "Sin confirmar", "fallido": "No se hizo", "visita": "Pantallas",
}


def _confirma(paso, ruta):
    """¿La ruta es la confirmación de ese paso 1? /venta/nueva → /venta/confirmar;
    /cliente/5/abono → /cliente/5/abono/confirmar."""
    return ruta == ("/venta/confirmar" if paso == "/venta/nueva" else paso + "/confirmar")


def _sin_confirmar(filas):
    """Los 'paso 1' (armó una venta, empezó un abono) que nunca confirmó."""
    abiertos = {}                      # (quien, ruta del paso) → id de la fila
    for f in sorted(filas, key=lambda f: (f["momento"], f["id"])):
        if f["clase"] == "paso":
            abiertos[(f["quien"], f["ruta"])] = f["id"]
        elif f["clase"] == "nuevo":
            for clave in [c for c in abiertos if c[0] == f["quien"] and _confirma(c[1], f["ruta"])]:
                del abiertos[clave]
    return set(abiertos.values())


@app.get("/historial")
@requiere_ingreso
@requiere_gastos        # la contraseña de la hermana no lo ve: le sale "no existe"
def historial():
    try:
        dia = date.fromisoformat(request.args.get("dia", ""))
    except ValueError:
        dia = date.today()
    quien = request.args.get("quien", "hermana" if app.config["CLAVE_HUELLA_HERMANA"] else "todos")
    ver = request.args.get("ver", "todo")
    conn = db()
    _preparar(conn)
    sql = "SELECT * FROM historial WHERE date(momento) = ?"
    params = [dia.isoformat()]
    if quien in ("hermana", "dueño"):
        sql += " AND quien IN (?, '?')"
        params.append(quien)
    filas = conn.execute(sql + " ORDER BY momento DESC, id DESC", params).fetchall()
    sin_confirmar = _sin_confirmar(filas)
    cuenta = {c: sum(1 for f in filas if f["clase"] == c) for c in CLASES}
    cuenta["paso"] = len(sin_confirmar)
    primera = next((f["momento"] for f in reversed(filas)), None)
    ultima = next((f["momento"] for f in filas), None)
    if ver == "cambios":
        filas = [f for f in filas if f["clase"] != "visita"]
    return render_template(
        "historial.html", filas=filas, dia=_dia_largo(dia), es_hoy=dia == date.today(),
        quien=quien, ver=ver, cuenta=cuenta, clases=CLASES, sin_confirmar=sin_confirmar,
        primera=primera, ultima=ultima, anterior=(dia - timedelta(days=1)).isoformat(),
        dia_iso=dia.isoformat(),
        siguiente=(dia + timedelta(days=1)).isoformat() if dia < date.today() else None)
