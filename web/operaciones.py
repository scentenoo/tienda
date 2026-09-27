"""Pantallas de inventario, compras, gastos, pérdidas y caja de la página
del celular. Se registran en la misma app de web/app.py (que las importa al
final); guardan con los mismos servicios que el PC."""
import json
import secrets
from datetime import date, timedelta

from flask import abort, redirect, render_template, request, session, url_for

from servicios.compras import editar_compra, eliminar_compra, registrar_lote
from servicios.gastos import (TIPOS_PERDIDA, crear_gasto, editar_gasto, eliminar_gasto,
                              eliminar_perdida, registrar_perdida)
from servicios.inventario import (crear_producto, editar_producto, eliminar_producto,
                                  usos_del_producto)
from utils.conciliacion import MESES_ES
from web.app import (_dia_largo, _json_seguro, _leer_decimal, _leer_monto, _revisar_csrf,
                     _usuario_admin, app, db, pesos, requiere_ingreso)


def _fecha_form(nombre, por_defecto=None):
    try:
        return date.fromisoformat(request.form.get(nombre, ""))
    except ValueError:
        return por_defecto


def _codigo_unico(clave):
    """Código de un solo uso contra el doble envío de un formulario."""
    session[clave] = secrets.token_urlsafe(16)
    return session[clave]


def _codigo_valido(clave):
    esperado = session.pop(clave, None)
    return bool(esperado) and secrets.compare_digest(esperado, request.form.get("codigo", ""))


def _mes_de(texto):
    """'2026-09' → (date(2026, 9, 1), 'septiembre 2026'); mes actual si no sirve."""
    try:
        inicio = date.fromisoformat((texto or "") + "-01")
    except ValueError:
        inicio = date.today().replace(day=1)
    return inicio, f"{MESES_ES[inicio.month - 1]} {inicio.year}"


def _navegacion_mes(inicio):
    anterior = (inicio - timedelta(days=1)).strftime("%Y-%m")
    siguiente = (inicio + timedelta(days=32)).replace(day=1)
    return anterior, (siguiente.strftime("%Y-%m") if siguiente <= date.today() else None)


# ── Inventario ───────────────────────────────────────────────────────────────
@app.route("/producto/nuevo", methods=["GET", "POST"])
@requiere_ingreso
def producto_nuevo():
    if request.method == "GET":
        return render_template("producto_form.html", p=None, error=None, usos=None)
    _revisar_csrf()
    conn = db()
    try:
        crear_producto(conn, request.form.get("nombre"), _leer_monto(request.form.get("precio")),
                       _leer_decimal(request.form.get("stock")))
        conn.commit()
    except ValueError as e:
        conn.rollback()
        return render_template("producto_form.html", p=request.form, error=str(e), usos=None)
    return redirect(url_for("inventario", q=request.form.get("nombre", "").strip()))


@app.route("/producto/<int:product_id>", methods=["GET", "POST"])
@requiere_ingreso
def producto_editar(product_id):
    conn = db()
    p = conn.execute("SELECT id, name, price, stock, cost_price FROM products WHERE id = ?",
                     (product_id,)).fetchone()
    if p is None:
        abort(404)
    usos = usos_del_producto(conn, product_id)
    if request.method == "GET":
        datos = {"id": p["id"], "nombre": p["name"], "precio": round(p["price"] or 0),
                 "stock": f"{p['stock']:g}".replace(".", ","), "costo": p["cost_price"]}
        return render_template("producto_form.html", p=datos, error=None, usos=usos)
    _revisar_csrf()
    texto_stock = request.form.get("stock", "").strip()
    try:
        editar_producto(conn, product_id, request.form.get("nombre"),
                        _leer_monto(request.form.get("precio")),
                        _leer_decimal(texto_stock) if texto_stock else None)
        conn.commit()
    except ValueError as e:
        conn.rollback()
        return render_template("producto_form.html", p={**request.form, "id": product_id,
                               "costo": p["cost_price"]}, error=str(e), usos=usos)
    return redirect(url_for("inventario", q=request.form.get("nombre", "").strip()))


@app.post("/producto/<int:product_id>/eliminar")
@requiere_ingreso
def producto_eliminar(product_id):
    _revisar_csrf()
    conn = db()
    try:
        eliminar_producto(conn, product_id)
        conn.commit()
    except ValueError:
        conn.rollback()
    return redirect(url_for("inventario"))


# ── Compras ──────────────────────────────────────────────────────────────────
@app.get("/compras")
@requiere_ingreso
def compras():
    inicio, titulo = _mes_de(request.args.get("mes"))
    fin = (inicio + timedelta(days=32)).replace(day=1)
    conn = db()
    filas = conn.execute("""
        SELECT pu.id, pu.date, pu.total, pu.iva, pu.shipping, pu.invoice_number,
               COALESCE(pu.lote_id, 'c' || pu.id) AS lote,
               pd.quantity, pd.unit_price, COALESCE(p.name, 'Producto') AS producto
          FROM purchases pu
          LEFT JOIN purchase_details pd ON pd.purchase_id = pu.id
          LEFT JOIN products p ON p.id = pd.product_id
         WHERE pu.date >= ? AND pu.date < ?
         ORDER BY pu.date DESC, pu.id""", (inicio.isoformat(), fin.isoformat())).fetchall()
    lotes = []
    for f in filas:
        if not lotes or lotes[-1]["lote"] != f["lote"]:
            lotes.append({"lote": f["lote"], "fecha": f["date"], "factura": f["invoice_number"],
                          "total": 0.0, "items": []})
        lotes[-1]["total"] += f["total"] or 0
        lotes[-1]["items"].append(f)
    anterior, siguiente = _navegacion_mes(inicio)
    return render_template("compras.html", lotes=lotes, titulo=titulo,
                           total=sum(l["total"] for l in lotes), anterior=anterior,
                           siguiente=siguiente, aviso=session.pop("aviso_compra", None))


@app.route("/compra/nueva", methods=["GET", "POST"])
@requiere_ingreso
def compra_nueva():
    conn = db()
    productos = [{"id": f[0], "n": f[1], "c": f[2] or 0, "s": f[3] or 0} for f in conn.execute(
        "SELECT id, name, cost_price, stock FROM products ORDER BY name COLLATE NOCASE")]
    if request.method == "GET":
        return render_template("compra_nueva.html", productos=_json_seguro(productos),
                               borrador="null", error=None, codigo=_codigo_unico("compra_codigo"))
    _revisar_csrf()
    borrador = request.form.get("borrador", "")
    try:
        lote = json.loads(borrador)
    except json.JSONDecodeError:
        abort(400)
    if not _codigo_valido("compra_codigo"):
        return redirect(url_for("compras"))       # doble envío: ya se guardó
    try:
        # Productos nuevos del lote: se crean con su precio de venta
        ids_nuevos = {}
        for l in lote.get("lineas", []):
            if l.get("nuevo") and l["nombre"] not in ids_nuevos:
                ids_nuevos[l["nombre"]] = crear_producto(
                    conn, l["nombre"], float(_leer_monto(str(l.get("venta") or ""))), 0)
        items = [{"product_id": ids_nuevos[l["nombre"]] if l.get("nuevo") else int(l["id"]),
                  "quantity": _leer_decimal(l.get("q")),
                  "unit_price": float(_leer_monto(str(l.get("costo") or "")))}
                 for l in lote.get("lineas", [])]
        registrar_lote(conn, items, float(_leer_monto(str(lote.get("iva") or ""))),
                       float(_leer_monto(str(lote.get("flete") or ""))), lote.get("factura"),
                       _usuario_admin(conn))
        conn.commit()
    except (ValueError, KeyError, TypeError) as e:
        conn.rollback()
        return render_template("compra_nueva.html", productos=_json_seguro(productos),
                               borrador=_json_seguro(lote), error=str(e),
                               codigo=_codigo_unico("compra_codigo"))
    session["aviso_compra"] = f"Compra de {len(items)} producto{'s' if len(items) != 1 else ''} guardada."
    return redirect(url_for("compras"))


@app.route("/compra/<int:purchase_id>", methods=["GET", "POST"])
@requiere_ingreso
def compra(purchase_id):
    conn = db()
    c = conn.execute("""
        SELECT pu.id, pu.date, pu.total, pu.iva, pu.shipping, pu.invoice_number, pu.lote_id,
               pd.quantity, pd.unit_price, pd.subtotal, COALESCE(p.name, 'Producto') AS producto
          FROM purchases pu LEFT JOIN purchase_details pd ON pd.purchase_id = pu.id
          LEFT JOIN products p ON p.id = pd.product_id WHERE pu.id = ?""", (purchase_id,)).fetchone()
    if c is None:
        abort(404)
    error = None
    if request.method == "POST":
        _revisar_csrf()
        try:
            editar_compra(conn, purchase_id, _leer_monto(request.form.get("total")),
                          _leer_monto(request.form.get("iva")), _leer_monto(request.form.get("flete")),
                          request.form.get("factura"))
            conn.commit()
            session["aviso_compra"] = "Compra actualizada."
            return redirect(url_for("compras", mes=str(c["date"])[:7]))
        except ValueError as e:
            conn.rollback()
            error = str(e)
    return render_template("compra.html", c=c, error=error)


@app.post("/compra/<int:purchase_id>/eliminar")
@requiere_ingreso
def compra_eliminar(purchase_id):
    _revisar_csrf()
    conn = db()
    fila = conn.execute("SELECT date FROM purchases WHERE id = ?", (purchase_id,)).fetchone()
    try:
        eliminar_compra(conn, purchase_id)
        conn.commit()
        session["aviso_compra"] = "Compra eliminada; su cantidad se restó del stock."
    except ValueError:
        conn.rollback()
    return redirect(url_for("compras", mes=str(fila["date"])[:7] if fila else None))


# ── Gastos ───────────────────────────────────────────────────────────────────
@app.get("/gastos")
@requiere_ingreso
def gastos():
    inicio, titulo = _mes_de(request.args.get("mes"))
    fin = (inicio + timedelta(days=32)).replace(day=1)
    filas = db().execute("""
        SELECT id, description, amount, date FROM expenses
         WHERE date >= ? AND date < ? ORDER BY date DESC, id DESC""",
                         (inicio.isoformat(), fin.isoformat())).fetchall()
    anterior, siguiente = _navegacion_mes(inicio)
    return render_template("gastos.html", gastos=filas, titulo=titulo,
                           total=sum(f["amount"] for f in filas), anterior=anterior,
                           siguiente=siguiente, aviso=session.pop("aviso_gasto", None))


@app.route("/gasto/nuevo", methods=["GET", "POST"])
@app.route("/gasto/<int:expense_id>", methods=["GET", "POST"])
@requiere_ingreso
def gasto(expense_id=None):
    conn = db()
    g = None
    if expense_id is not None:
        g = conn.execute("SELECT id, description, amount, date FROM expenses WHERE id = ?",
                         (expense_id,)).fetchone()
        if g is None:
            abort(404)
    if request.method == "GET":
        datos = ({"descripcion": g["description"], "monto": round(g["amount"]),
                  "fecha": str(g["date"])[:10]} if g else {"fecha": date.today().isoformat()})
        return render_template("gasto_form.html", g=g, d=datos, error=None,
                               codigo=_codigo_unico("gasto_codigo"))
    _revisar_csrf()
    if request.form.get("eliminar") and g:
        eliminar_gasto(conn, expense_id)
        conn.commit()
        session["aviso_gasto"] = "Gasto eliminado."
        return redirect(url_for("gastos", mes=str(g["date"])[:7]))
    if not _codigo_valido("gasto_codigo"):
        return redirect(url_for("gastos"))
    fecha = _fecha_form("fecha")
    try:
        if g:
            editar_gasto(conn, expense_id, request.form.get("descripcion"),
                         _leer_monto(request.form.get("monto")), fecha)
        else:
            crear_gasto(conn, request.form.get("descripcion"), _leer_monto(request.form.get("monto")),
                        fecha, _usuario_admin(conn))
        conn.commit()
    except ValueError as e:
        conn.rollback()
        return render_template("gasto_form.html", g=g, d=request.form, error=str(e),
                               codigo=_codigo_unico("gasto_codigo"))
    session["aviso_gasto"] = "Gasto actualizado." if g else "Gasto guardado."
    return redirect(url_for("gastos", mes=fecha.strftime("%Y-%m")))


# ── Pérdidas ─────────────────────────────────────────────────────────────────
@app.get("/perdidas")
@requiere_ingreso
def perdidas():
    inicio, titulo = _mes_de(request.args.get("mes"))
    fin = (inicio + timedelta(days=32)).replace(day=1)
    filas = db().execute("""
        SELECT l.id, l.quantity, l.unit_cost, l.total_cost, l.loss_date, l.reason, l.loss_type,
               l.notes, COALESCE(p.name, 'Producto eliminado') AS producto
          FROM losses l LEFT JOIN products p ON p.id = l.product_id
         WHERE l.loss_date >= ? AND l.loss_date < ? ORDER BY l.loss_date DESC, l.id DESC""",
                         (inicio.isoformat(), fin.isoformat())).fetchall()
    por_tipo = {}
    for f in filas:
        por_tipo[f["loss_type"]] = por_tipo.get(f["loss_type"], 0) + (f["total_cost"] or 0)
    anterior, siguiente = _navegacion_mes(inicio)
    return render_template("perdidas.html", perdidas=filas, titulo=titulo, por_tipo=por_tipo,
                           total=sum(f["total_cost"] or 0 for f in filas), anterior=anterior,
                           siguiente=siguiente, aviso=session.pop("aviso_perdida", None))


@app.route("/perdida/nueva", methods=["GET", "POST"])
@requiere_ingreso
def perdida_nueva():
    conn = db()
    productos = [{"id": f[0], "n": f[1], "c": f[2] or 0, "s": f[3] or 0} for f in conn.execute(
        "SELECT id, name, cost_price, stock FROM products WHERE stock > 0 ORDER BY name COLLATE NOCASE")]
    def formulario(error=None, datos=None):
        return render_template("perdida_form.html", productos=_json_seguro(productos), tipos=TIPOS_PERDIDA,
                               d=datos or {"fecha": date.today().isoformat(), "tipo": "Vencimiento"},
                               error=error, codigo=_codigo_unico("perdida_codigo"))
    if request.method == "GET":
        return formulario()
    _revisar_csrf()
    if not _codigo_valido("perdida_codigo"):
        return redirect(url_for("perdidas"))
    f = request.form
    try:
        registrar_perdida(conn, int(f.get("producto") or 0), _leer_decimal(f.get("cantidad")),
                          float(_leer_monto(f.get("costo"))), _fecha_form("fecha", date.today()),
                          f.get("motivo"), f.get("tipo"), f.get("notas"), _usuario_admin(conn))
        conn.commit()
    except ValueError as e:
        conn.rollback()
        return formulario(str(e), f)
    session["aviso_perdida"] = "Pérdida registrada; se descontó del stock."
    return redirect(url_for("perdidas"))


@app.post("/perdida/<int:loss_id>/eliminar")
@requiere_ingreso
def perdida_eliminar(loss_id):
    _revisar_csrf()
    conn = db()
    try:
        eliminar_perdida(conn, loss_id)
        conn.commit()
        session["aviso_perdida"] = "Pérdida eliminada; la cantidad volvió al stock."
    except ValueError as e:
        conn.rollback()
        session["aviso_perdida"] = str(e)
    return redirect(url_for("perdidas", mes=request.form.get("mes")))


# ── Caja ─────────────────────────────────────────────────────────────────────
@app.get("/caja")
@requiere_ingreso
def caja():
    """Lo mismo que la ventana de caja del PC: ventas de contado pagadas y
    abonos de clientes, por día, y el historial de los últimos 30 días."""
    try:
        dia = date.fromisoformat(request.args.get("dia", ""))
    except ValueError:
        dia = date.today()
    conn = db()
    movimientos = [
        {"tipo": "Venta contado", "texto": f"Venta #{f['id']}", "monto": f["total"],
         "hora": f["created_at"], "venta": f["id"]}
        for f in conn.execute("""
            SELECT id, total, created_at FROM sales
             WHERE DATE(created_at) = ? AND payment_method = 'cash' AND status = 'paid'""",
                              (dia.isoformat(),))]
    movimientos += [
        {"tipo": "Abono cliente", "texto": f"{f['nombre']} — {f['description']}",
         "monto": abs(f["amount"]), "hora": f["created_at"], "cliente": f["client_id"]}
        for f in conn.execute("""
            SELECT ct.amount, ct.description, ct.created_at, ct.client_id, c.name AS nombre
              FROM client_transactions ct LEFT JOIN clients c ON c.id = ct.client_id
             WHERE DATE(ct.created_at) = ? AND ct.transaction_type = 'credit'""", (dia.isoformat(),))]
    movimientos.sort(key=lambda m: m["hora"])
    contado = sum(m["monto"] for m in movimientos if m["tipo"] == "Venta contado")
    abonos = sum(m["monto"] for m in movimientos if m["tipo"] == "Abono cliente")

    desde = (date.today() - timedelta(days=30)).isoformat()
    por_dia = {}
    for fecha, monto in conn.execute("""
            SELECT DATE(created_at), SUM(total) FROM sales
             WHERE payment_method = 'cash' AND status = 'paid' AND DATE(created_at) >= ?
             GROUP BY DATE(created_at)""", (desde,)):
        por_dia.setdefault(fecha, [0.0, 0.0])[0] = monto or 0
    for fecha, monto in conn.execute("""
            SELECT DATE(created_at), SUM(ABS(amount)) FROM client_transactions
             WHERE transaction_type = 'credit' AND DATE(created_at) >= ?
             GROUP BY DATE(created_at)""", (desde,)):
        por_dia.setdefault(fecha, [0.0, 0.0])[1] = monto or 0
    historial = [{"fecha": f, "contado": v[0], "abonos": v[1], "total": v[0] + v[1]}
                 for f, v in sorted(por_dia.items(), reverse=True)]
    return render_template(
        "caja.html", dia=_dia_largo(dia), es_hoy=dia == date.today(), movimientos=movimientos,
        contado=contado, abonos=abonos, anterior=(dia - timedelta(days=1)).isoformat(),
        siguiente=(dia + timedelta(days=1)).isoformat() if dia < date.today() else None,
        historial=historial)
