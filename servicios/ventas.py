"""Registrar una venta: la venta, sus productos, el stock y, si es fiada, la
deuda del cliente y su movimiento."""


def descripcion_fiado(sale_id, ajuste, motivo):
    """Texto del movimiento del cliente; el estado de cuenta y el historial lo
    muestran, así que se conserva el formato de siempre."""
    texto = f"Venta fiada #{sale_id}"
    if ajuste > 0:
        texto += f" (+ cargo: ${ajuste:,.2f})"
    elif ajuste < 0:
        texto += f" (descuento: ${abs(ajuste):,.2f})"
    if motivo:
        texto += f" - {motivo}"
    return texto


def registrar_venta(conn, items, user_id, client_id=None, fiada=False,
                    ajuste=0.0, motivo_ajuste=None):
    """Guarda la venta y devuelve (sale_id, total). No hace commit.

    items: dicts con product_id, quantity, unit_price, subtotal y cost_price.
    El ajuste (cargo o descuento) solo aplica a las fiadas, como en la
    pantalla de ventas.
    """
    if not items:
        raise ValueError("Debe agregar al menos un producto a la venta")
    if fiada and not client_id:
        raise ValueError("Debe seleccionar un cliente válido para ventas fiadas")
    if not fiada:
        ajuste, motivo_ajuste = 0.0, None

    total = sum(i["subtotal"] for i in items) + ajuste
    status = "pending" if fiada else "paid"
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO sales (client_id, total, status, payment_method, adjustment,
                           adjustment_reason, created_at, user_id)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), ?)
    """, (client_id if fiada else None, total, status, "credit" if fiada else "cash",
          ajuste, motivo_ajuste, user_id))
    sale_id = cursor.lastrowid

    # Todos los productos en una sola instrucción
    cursor.execute(
        "INSERT INTO sale_details (sale_id, product_id, quantity, unit_price, "
        "sale_price, subtotal, cost_price) VALUES "
        + ", ".join(["(?, ?, ?, ?, ?, ?, ?)"] * len(items)),
        tuple(v for i in items for v in (
            sale_id, i["product_id"], i["quantity"], i["unit_price"],
            i["unit_price"], i["subtotal"], i.get("cost_price", 0) or 0)))

    # Y todo el stock en otra; un producto repetido descuenta la suma
    cantidades = {}
    for i in items:
        cantidades[i["product_id"]] = cantidades.get(i["product_id"], 0) + i["quantity"]
    casos = " ".join("WHEN ? THEN ?" for _ in cantidades)
    cursor.execute(
        f"UPDATE products SET stock = stock - CASE id {casos} END "
        f"WHERE id IN ({', '.join('?' * len(cantidades))})",
        tuple(v for par in cantidades.items() for v in par) + tuple(cantidades))

    if fiada:
        cursor.execute("UPDATE clients SET total_debt = total_debt + ? WHERE id = ?",
                       (total, client_id))
        cursor.execute("""
            INSERT INTO client_transactions
                (client_id, transaction_type, amount, description, sale_id, created_at)
            VALUES (?, 'debit', ?, ?, ?, datetime('now', 'localtime'))
        """, (client_id, total, descripcion_fiado(sale_id, ajuste, motivo_ajuste), sale_id))

    return sale_id, total
