"""Ventas: registrar (la venta, sus productos, el stock y, si es fiada, la
deuda del cliente y su movimiento), editar y eliminar."""
from servicios.abonos import estados_segun_deuda


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


def preparar_items(conn, pedidos):
    """De [(product_id, cantidad, dinero), ...] a los items de
    registrar_venta, con el precio y el costo de la base (no los que mande el
    celular). Con dinero (vender "$10.000 de queso") la cantidad es dinero ÷
    precio y el subtotal es el dinero exacto, como en la pantalla de ventas.
    Aplica sus mismas reglas: producto existente, con stock, y sin vender más
    de lo que hay contando todas las líneas del producto."""
    if not pedidos:
        raise ValueError("Debe agregar al menos un producto a la venta")
    ids = sorted({int(p[0]) for p in pedidos})
    productos = {f[0]: tuple(f) for f in conn.execute(
        f"SELECT id, name, price, stock, cost_price FROM products "
        f"WHERE id IN ({', '.join('?' * len(ids))})", tuple(ids)).fetchall()}
    pedido_total, items = {}, []
    for pedido in pedidos:
        pid, cantidad = int(pedido[0]), float(pedido[1] or 0)
        dinero = float(pedido[2]) if len(pedido) > 2 and pedido[2] else 0.0
        p = productos.get(pid)
        if p is None:
            raise ValueError(f"El producto {pid} no existe")
        if dinero > 0:
            if not p[2] or p[2] <= 0:
                raise ValueError(f"'{p[1]}' no tiene precio")
            cantidad = dinero / p[2]
        if cantidad <= 0:
            raise ValueError(f"La cantidad de '{p[1]}' debe ser mayor a 0")
        if (p[3] or 0) <= 0:
            raise ValueError(f"'{p[1]}' no tiene stock disponible")
        pedido_total[pid] = pedido_total.get(pid, 0) + cantidad
        if pedido_total[pid] > p[3] + 1e-9:
            raise ValueError(f"Stock insuficiente de '{p[1]}'. Disponible: {p[3]:g}, "
                             f"en la venta: {pedido_total[pid]:g}")
        items.append({"product_id": pid, "product_name": p[1], "quantity": cantidad,
                      "unit_price": p[2], "subtotal": dinero if dinero > 0 else p[2] * cantidad,
                      "cost_price": p[4] or 0})
    return items


def _recalcular_estados(cursor, client_id):
    """Deja pagadas/pendientes las ventas del cliente según su deuda, con la
    misma regla que al registrar un abono."""
    fila = cursor.execute("SELECT total_debt FROM clients WHERE id = ?", (client_id,)).fetchone()
    if fila is None:
        return
    ventas = [tuple(v) for v in cursor.execute(
        "SELECT id, total, status FROM sales WHERE client_id = ? ORDER BY datetime(created_at) ASC",
        (client_id,)).fetchall()]
    cambios = estados_segun_deuda(ventas, float(fila[0] or 0))
    if cambios:
        pagadas = [i for i, st in cambios.items() if st == "paid"]
        cursor.execute(
            "UPDATE sales SET status = CASE WHEN id IN ("
            + (", ".join("?" * len(pagadas)) or "NULL")
            + ") THEN 'paid' ELSE 'pending' END WHERE id IN ("
            + ", ".join("?" * len(cambios)) + ")",
            tuple(pagadas) + tuple(cambios))


def editar_venta(conn, sale_id, total, fiada, client_id=None):
    """Cambia el total, contado/fiado o el cliente de una venta existente.
    No hace commit.

    Si la venta era fiada, su cargo se revierte (como al eliminarla) y, si
    queda fiada, se carga de nuevo con el total nuevo; así la deuda y el
    estado de cuenta siempre cuadran. Los productos no cambian: la diferencia
    con su suma queda como ajuste, igual que un cargo o descuento.
    (Antes, "Editar venta" creaba una venta nueva duplicada.)
    """
    if total <= 0:
        raise ValueError("El total debe ser mayor a cero")
    if fiada and not client_id:
        raise ValueError("Una venta fiada necesita un cliente")
    cursor = conn.cursor()
    v = cursor.execute("""
        SELECT client_id, total, payment_method, adjustment_reason,
               (SELECT COALESCE(SUM(subtotal), 0) FROM sale_details WHERE sale_id = sales.id)
          FROM sales WHERE id = ?""", (sale_id,)).fetchone()
    if v is None:
        raise ValueError("La venta no existe")
    cliente_antes, total_antes, metodo_antes, motivo, suma_productos = tuple(v)
    era_fiada = metodo_antes == "credit" and cliente_antes is not None
    if not fiada:
        client_id = None
    if (era_fiada, cliente_antes if era_fiada else None, round(total_antes, 2)) == \
            (fiada, client_id, round(total, 2)):
        return  # nada cambió

    if era_fiada:
        cursor.execute("UPDATE clients SET total_debt = total_debt - ? WHERE id = ?",
                       (total_antes, cliente_antes))
        cursor.execute("""
            INSERT INTO client_transactions
                (client_id, transaction_type, amount, description, created_at, sale_id)
            VALUES (?, 'debit_reversal', ?, ?, datetime('now', 'localtime'), ?)
        """, (cliente_antes, total_antes, f"Reversión de venta #{sale_id} (editada)", sale_id))

    ajuste = total - suma_productos if suma_productos else 0.0
    cursor.execute("""
        UPDATE sales SET total = ?, client_id = ?, payment_method = ?, status = ?, adjustment = ?
         WHERE id = ?""", (total, client_id, "credit" if fiada else "cash",
                           "pending" if fiada else "paid", ajuste, sale_id))

    if fiada:
        cursor.execute("UPDATE clients SET total_debt = total_debt + ? WHERE id = ?",
                       (total, client_id))
        cursor.execute("""
            INSERT INTO client_transactions
                (client_id, transaction_type, amount, description, sale_id, created_at)
            VALUES (?, 'debit', ?, ?, ?, datetime('now', 'localtime'))
        """, (client_id, total,
              descripcion_fiado(sale_id, ajuste, motivo) + " (editada)", sale_id))

    for cid in {c for c in ((cliente_antes if era_fiada else None), client_id) if c}:
        _recalcular_estados(cursor, cid)


def eliminar_venta(conn, sale_id):
    """Igual que "Eliminar venta" en el PC: devuelve el stock, revierte la
    deuda si la venta estaba pendiente, archiva la venta y sus productos en
    sales_eliminadas / sale_details_eliminados y la borra. No hace commit."""
    cursor = conn.cursor()
    v = cursor.execute("SELECT client_id, total, status FROM sales WHERE id = ?", (sale_id,)).fetchone()
    if v is None:
        raise ValueError("La venta no existe")
    client_id, total, status = tuple(v)
    detalles = [tuple(d) for d in cursor.execute(
        "SELECT product_id, quantity FROM sale_details WHERE sale_id = ?", (sale_id,)).fetchall()]

    if status == "pending" and client_id:
        cursor.execute("UPDATE clients SET total_debt = total_debt - ? WHERE id = ?", (total, client_id))
        cursor.execute("""
            INSERT INTO client_transactions
                (client_id, transaction_type, amount, description, created_at, sale_id)
            VALUES (?, 'debit_reversal', ?, ?, datetime('now', 'localtime'), ?)
        """, (client_id, total, f"Reversión de venta #{sale_id}", sale_id))

    cursor.execute("""
        INSERT OR REPLACE INTO sales_eliminadas
            (id, client_id, total, payment_method, notes, created_at,
             user_id, status, adjustment, adjustment_reason, eliminada_en)
        SELECT id, client_id, total, payment_method, notes, created_at,
               user_id, status, adjustment, adjustment_reason, datetime('now', 'localtime')
          FROM sales WHERE id = ?""", (sale_id,))
    cursor.execute("""
        INSERT OR REPLACE INTO sale_details_eliminados
            (id, sale_id, product_id, product_name, quantity, unit_price, sale_price, subtotal, cost_price)
        SELECT sd.id, sd.sale_id, sd.product_id, p.name, sd.quantity,
               sd.unit_price, sd.sale_price, sd.subtotal, sd.cost_price
          FROM sale_details sd LEFT JOIN products p ON p.id = sd.product_id
         WHERE sd.sale_id = ?""", (sale_id,))
    cursor.execute("DELETE FROM sale_details WHERE sale_id = ?", (sale_id,))
    cursor.execute("DELETE FROM sales WHERE id = ?", (sale_id,))

    devolver = {}
    for pid, q in detalles:
        devolver[pid] = devolver.get(pid, 0) + q
    if devolver:
        casos = " ".join("WHEN ? THEN ?" for _ in devolver)
        cursor.execute(
            f"UPDATE products SET stock = stock + CASE id {casos} END "
            f"WHERE id IN ({', '.join('?' * len(devolver))})",
            tuple(v for par in devolver.items() for v in par) + tuple(devolver))
