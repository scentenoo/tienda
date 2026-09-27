"""Clientes: crear, editar, eliminar y agregar deuda manual, con las mismas
reglas que la pantalla de clientes del PC. Ninguna función hace commit."""
import sqlite3


def _pesos(v):
    return "$" + f"{round(v or 0):,.0f}".replace(",", ".")


def _datos(nombre, telefono, direccion, limite, notas):
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre del cliente es obligatorio")
    limite = float(limite or 0)
    if limite < 0:
        raise ValueError("El límite de crédito no puede ser negativo")
    vacio = lambda t: (t or "").strip() or None
    return nombre, vacio(telefono), vacio(direccion), limite, vacio(notas)


def crear_cliente(conn, nombre, telefono=None, direccion=None, limite=0.0, notas=None):
    datos = _datos(nombre, telefono, direccion, limite, notas)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO clients (name, phone, address, credit_limit, total_debt, notes)
            VALUES (?, ?, ?, ?, 0.0, ?)""", datos)
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("Ya existe un cliente con ese nombre") from None


def editar_cliente(conn, client_id, nombre, telefono=None, direccion=None, limite=0.0, notas=None):
    datos = _datos(nombre, telefono, direccion, limite, notas)
    try:
        conn.execute("""
            UPDATE clients SET name = ?, phone = ?, address = ?, credit_limit = ?, notes = ?
             WHERE id = ?""", datos + (client_id,))
    except sqlite3.IntegrityError:
        raise ValueError("Ya existe un cliente con ese nombre") from None


def eliminar_cliente(conn, client_id):
    fila = conn.execute("SELECT name, total_debt FROM clients WHERE id = ?", (client_id,)).fetchone()
    if fila is None:
        raise ValueError("El cliente no existe")
    if (fila[1] or 0) > 0:
        raise ValueError(f"'{fila[0]}' tiene una deuda de {_pesos(fila[1])}. "
                         "Debe saldarla antes de eliminar el cliente.")
    conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))


def credito_disponible(conn, client_id):
    fila = conn.execute("SELECT credit_limit, total_debt FROM clients WHERE id = ?",
                        (client_id,)).fetchone()
    if fila is None:
        raise ValueError("El cliente no existe")
    return max(0.0, (fila[0] or 0.0) - (fila[1] or 0.0))


def agregar_deuda(conn, client_id, monto, descripcion):
    """Deuda a mano (sin venta). Como en el PC, no puede pasar del crédito
    disponible (límite de crédito menos lo que ya debe)."""
    descripcion = (descripcion or "").strip()
    if monto <= 0:
        raise ValueError("El monto debe ser mayor a cero")
    if not descripcion:
        raise ValueError("Escriba una descripción")
    disponible = credito_disponible(conn, client_id)
    if monto > disponible:
        raise ValueError(f"El monto excede el crédito disponible ({_pesos(disponible)}). "
                         "Súbale el límite de crédito al cliente si hace falta.")
    conn.execute("UPDATE clients SET total_debt = total_debt + ? WHERE id = ?", (monto, client_id))
    conn.execute("""
        INSERT INTO client_transactions (client_id, transaction_type, amount, description, created_at)
        VALUES (?, 'debit', ?, ?, datetime('now', 'localtime'))""", (client_id, monto, descripcion))
