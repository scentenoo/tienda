"""Compras por lote, con las reglas de la pantalla de compras del PC.
Ninguna función hace commit.

Cada producto del lote queda como una compra propia (una fila en purchases
con su detalle), todas con el mismo lote_id. El IVA total se reparte por
igual entre los productos; el flete total va completo en el primero.
"""
from datetime import datetime


def registrar_lote(conn, items, iva_total, flete_total, factura, user_id):
    """items: dicts con product_id, quantity y unit_price (costo). Devuelve
    el lote_id. Actualiza el costo del producto y suma el stock."""
    if not items:
        raise ValueError("No hay artículos en el lote")
    for i in items:
        if i["quantity"] <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        if i["unit_price"] <= 0:
            raise ValueError("El precio debe ser mayor a 0")
    if iva_total < 0 or flete_total < 0:
        raise ValueError("El IVA y el flete no pueden ser negativos")
    ids = sorted({i["product_id"] for i in items})
    existentes = {f[0] for f in conn.execute(
        f"SELECT id FROM products WHERE id IN ({', '.join('?' * len(ids))})", tuple(ids))}
    if set(ids) - existentes:
        raise ValueError("Uno de los productos del lote ya no existe")

    ahora = datetime.now()
    lote_id, fecha = ahora.strftime("%Y%m%d%H%M%S"), ahora.strftime("%Y-%m-%d %H:%M:%S")
    iva_por_item = iva_total / len(items)
    factura = (factura or "").strip()
    cursor = conn.cursor()

    # Todas las compras del lote en una instrucción; sus id salen en orden
    filas = []
    for n, i in enumerate(items):
        subtotal = i["quantity"] * i["unit_price"]
        flete = flete_total if n == 0 else 0.0
        filas.append((user_id, subtotal + flete + iva_por_item, iva_por_item, flete, fecha,
                      factura, "Sin proveedor", lote_id, flete_total))
    cursor.execute(
        "INSERT INTO purchases (user_id, total, iva, shipping, date, invoice_number, supplier, "
        "lote_id, shipping_total) VALUES " + ", ".join(["(?, ?, ?, ?, ?, ?, ?, ?, ?)"] * len(filas)),
        tuple(v for f in filas for v in f))
    compras = [f[0] for f in conn.execute(
        "SELECT id FROM purchases WHERE lote_id = ? ORDER BY id", (lote_id,)).fetchall()][-len(items):]

    cursor.execute(
        "INSERT INTO purchase_details (purchase_id, product_id, quantity, unit_cost, unit_price, subtotal) "
        "VALUES " + ", ".join(["(?, ?, ?, ?, ?, ?)"] * len(items)),
        tuple(v for pid, i in zip(compras, items) for v in (
            pid, i["product_id"], i["quantity"], i["unit_price"], i["unit_price"],
            i["quantity"] * i["unit_price"])))

    costo, suma = {}, {}
    for i in items:                 # si un producto se repite, gana el último costo
        costo[i["product_id"]] = i["unit_price"]
        suma[i["product_id"]] = suma.get(i["product_id"], 0) + i["quantity"]
    for valores, sql in ((costo, "cost_price = CASE id {c} END"),
                         (suma, "stock = stock + CASE id {c} END")):
        casos = " ".join("WHEN ? THEN ?" for _ in valores)
        cursor.execute(f"UPDATE products SET {sql.format(c=casos)} "
                       f"WHERE id IN ({', '.join('?' * len(valores))})",
                       tuple(v for par in valores.items() for v in par) + tuple(valores))
    return lote_id


def editar_compra(conn, purchase_id, total, iva, flete, factura):
    """Como "Editar compra" en el PC: solo total, IVA, flete y factura."""
    if not total or total <= 0:
        raise ValueError("El total debe ser mayor a cero")
    if conn.execute("SELECT 1 FROM purchases WHERE id = ?", (purchase_id,)).fetchone() is None:
        raise ValueError("La compra no existe")
    conn.execute("UPDATE purchases SET total = ?, iva = ?, shipping = ?, invoice_number = ? WHERE id = ?",
                 (total, iva or 0.0, flete or 0.0, (factura or "").strip(), purchase_id))


def eliminar_compra(conn, purchase_id):
    """Como "Eliminar compra" en el PC: resta del stock lo que se había
    sumado y borra la compra con sus detalles."""
    if conn.execute("SELECT 1 FROM purchases WHERE id = ?", (purchase_id,)).fetchone() is None:
        raise ValueError("La compra no existe")
    restar = {}
    for pid, q in conn.execute("""
            SELECT pd.product_id, pd.quantity FROM purchase_details pd
              JOIN products p ON p.id = pd.product_id WHERE pd.purchase_id = ?""", (purchase_id,)):
        restar[pid] = restar.get(pid, 0) + q
    cursor = conn.cursor()
    if restar:
        casos = " ".join("WHEN ? THEN ?" for _ in restar)
        cursor.execute(f"UPDATE products SET stock = stock - CASE id {casos} END "
                       f"WHERE id IN ({', '.join('?' * len(restar))})",
                       tuple(v for par in restar.items() for v in par) + tuple(restar))
    cursor.execute("DELETE FROM purchase_details WHERE purchase_id = ?", (purchase_id,))
    cursor.execute("DELETE FROM purchases WHERE id = ?", (purchase_id,))
