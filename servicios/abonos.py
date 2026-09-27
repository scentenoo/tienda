"""Registrar un abono de un cliente.

Hace en un solo commit lo que antes hacían cuatro pasos con su propio commit
cada uno (Client.pay_debt, sync_client_sales_status_on_payment,
handle_excess_credit y update_sales_status_after_payment), con el mismo
resultado en la base.
"""
from datetime import datetime


def estados_segun_deuda(ventas, deuda):
    """Qué ventas deben quedar pagadas y cuáles pendientes para una deuda dada.

    Misma regla que sync_client_sales_status_on_payment: lo pagado (todas las
    ventas menos la deuda) cubre las ventas de la más vieja a la más nueva; la
    primera que no alcanza a cubrirse queda pendiente y ahí se detiene.
    ventas: (id, total, status) en orden cronológico. Devuelve {id: status}
    solo de las que cambian.
    """
    cambios = {}
    if deuda <= 0:
        for sale_id, _total, status in ventas:
            if status == "pending":
                cambios[sale_id] = "paid"
        return cambios

    restante = sum(float(t) for _i, t, _s in ventas) - deuda
    for sale_id, total, status in ventas:
        total = float(total)
        if restante >= total:
            if status != "paid":
                cambios[sale_id] = "paid"
            restante -= total
        else:
            if status == "paid":
                cambios[sale_id] = "pending"
            break
    return cambios


def registrar_abono(conn, client_id, monto, descripcion):
    """Aplica el pago a la deuda; lo que sobre queda como crédito a favor.
    No hace commit. Devuelve un resumen para mostrarle al usuario."""
    if monto <= 0:
        raise ValueError("El monto debe ser mayor a cero")

    fila = conn.execute("SELECT total_debt FROM clients WHERE id = ?", (client_id,)).fetchone()
    if fila is None:
        raise ValueError("Cliente no encontrado")
    deuda = float(fila[0] or 0)
    aplicado = min(monto, deuda) if deuda > 0 else 0.0
    exceso = monto - aplicado

    # Se lee antes de escribir: con la base en la nube, las lecturas previas a
    # la primera escritura salen de la copia local y no cuestan un viaje.
    ventas = [tuple(v) for v in conn.execute("""
        SELECT id, total, status FROM sales
         WHERE client_id = ? ORDER BY datetime(created_at) ASC
    """, (client_id,)).fetchall()]

    cursor = conn.cursor()
    if aplicado > 0:
        cursor.execute("UPDATE clients SET total_debt = MAX(0, total_debt - ?) WHERE id = ?",
                       (aplicado, client_id))
        cursor.execute("""
            INSERT INTO client_transactions (client_id, transaction_type, amount, description, created_at)
            VALUES (?, 'credit', ?, ?, datetime('now', 'localtime'))
        """, (client_id, aplicado, descripcion))
    if exceso > 0:
        cursor.execute("""
            INSERT INTO client_transactions (client_id, transaction_type, amount, description, created_at)
            VALUES (?, 'credit_balance', ?, ?, datetime('now', 'localtime'))
        """, (client_id, exceso, f"Crédito a favor por exceso en pago de ${exceso:,.2f}"))

    deuda_nueva = max(0.0, deuda - aplicado)
    if aplicado > 0:
        cambios = estados_segun_deuda(ventas, deuda_nueva)
        if cambios:
            pagadas = [i for i, s in cambios.items() if s == "paid"]
            cursor.execute(
                "UPDATE sales SET status = CASE WHEN id IN ("
                + (", ".join("?" * len(pagadas)) or "NULL")
                + ") THEN 'paid' ELSE 'pending' END WHERE id IN ("
                + ", ".join("?" * len(cambios)) + ")",
                tuple(pagadas) + tuple(cambios))
    elif deuda <= 0:
        # Sin deuda no se recalculaba nada, solo se saldaban las pendientes
        # que hubieran quedado, dejando nota
        marca = datetime.now().strftime('%Y-%m-%d %H:%M')
        cursor.execute(f"""
            UPDATE sales SET status = 'paid',
                   notes = COALESCE(notes, '') || ' [SALDADA el {marca}]'
             WHERE client_id = ? AND status = 'pending'
        """, (client_id,))

    return {"deuda_anterior": deuda, "aplicado": aplicado, "exceso": exceso,
            "deuda_nueva": deuda_nueva}
