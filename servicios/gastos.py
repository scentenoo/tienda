"""Gastos operativos y pérdidas/mermas, con las reglas de sus pantallas en
el PC. Ninguna función hace commit."""
from datetime import date

TIPOS_PERDIDA = ["Vencimiento", "Daño", "Robo", "Otro"]


# ── Gastos ───────────────────────────────────────────────────────────────────
def _validar_gasto(descripcion, monto, fecha):
    descripcion = (descripcion or "").strip()
    if not descripcion:
        raise ValueError("La descripción no puede estar vacía")
    if not monto or monto <= 0:
        raise ValueError("El monto debe ser mayor a 0")
    if not isinstance(fecha, date):
        raise ValueError("Fecha inválida")
    # El PC guarda la fecha elegida a medianoche en formato ISO
    return descripcion, f"{fecha.isoformat()}T00:00:00"


def crear_gasto(conn, descripcion, monto, fecha, user_id):
    descripcion, fecha = _validar_gasto(descripcion, monto, fecha)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO expenses (description, amount, date, user_id) VALUES (?, ?, ?, ?)",
                   (descripcion, monto, fecha, user_id))
    return cursor.lastrowid


def editar_gasto(conn, expense_id, descripcion, monto, fecha):
    descripcion, fecha = _validar_gasto(descripcion, monto, fecha)
    conn.execute("UPDATE expenses SET description = ?, amount = ?, date = ? WHERE id = ?",
                 (descripcion, monto, fecha, expense_id))


def eliminar_gasto(conn, expense_id):
    conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))


# ── Pérdidas ─────────────────────────────────────────────────────────────────
def registrar_perdida(conn, product_id, cantidad, costo_unitario, fecha, motivo, tipo,
                      notas, user_id):
    """Guarda la pérdida y descuenta el stock, como Loss.save()."""
    if not cantidad or cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor a 0")
    if not costo_unitario or costo_unitario <= 0:
        raise ValueError("El costo unitario debe ser mayor a 0")
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError("Debe ingresar un motivo")
    if tipo not in TIPOS_PERDIDA:
        raise ValueError("Tipo de pérdida inválido")
    p = conn.execute("SELECT name, stock FROM products WHERE id = ?", (product_id,)).fetchone()
    if p is None:
        raise ValueError("El producto no existe")
    if cantidad > (p[1] or 0) + 1e-9:
        raise ValueError(f"Stock insuficiente. Disponible: {p[1]:g}")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO losses (product_id, quantity, unit_cost, total_cost, loss_date, reason,
                            loss_type, notes, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                   (product_id, cantidad, costo_unitario, cantidad * costo_unitario,
                    f"{fecha.isoformat()} 00:00:00", motivo, tipo, (notas or "").strip(), user_id))
    cursor.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (cantidad, product_id))
    return cursor.lastrowid


def eliminar_perdida(conn, loss_id):
    """Borra la pérdida y devuelve la cantidad al stock, como Loss.delete()."""
    fila = conn.execute("SELECT product_id, quantity FROM losses WHERE id = ?", (loss_id,)).fetchone()
    if fila is None:
        raise ValueError("La pérdida no existe")
    if conn.execute("SELECT 1 FROM products WHERE id = ?", (fila[0],)).fetchone() is None:
        raise ValueError("El producto de esta pérdida ya no existe; no se puede devolver al stock")
    conn.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (fila[1], fila[0]))
    conn.execute("DELETE FROM losses WHERE id = ?", (loss_id,))
