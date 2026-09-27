"""Productos: crear, editar y eliminar, con las reglas de la pantalla de
inventario del PC. Ninguna función hace commit."""


def _validar(conn, nombre, precio, stock, excluir_id=None):
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre del producto es obligatorio")
    if precio is None:
        raise ValueError("El precio es obligatorio")
    if precio < 0:
        raise ValueError("El precio no puede ser negativo")
    if stock is not None and stock < 0:
        raise ValueError("El stock no puede ser negativo")
    sql = "SELECT id FROM products WHERE LOWER(name) = LOWER(?)"
    params = (nombre,)
    if excluir_id is not None:
        sql += " AND id != ?"
        params += (excluir_id,)
    if conn.execute(sql, params).fetchone():
        raise ValueError("Ya existe " + ("otro producto" if excluir_id else "un producto")
                         + " con ese nombre")
    return nombre


def crear_producto(conn, nombre, precio, stock=0):
    nombre = _validar(conn, nombre, precio, stock or 0)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
                   (nombre, precio, stock or 0))
    return cursor.lastrowid


def editar_producto(conn, product_id, nombre, precio, stock=None):
    """Sin stock (None) se conserva el que tiene, como en el PC."""
    nombre = _validar(conn, nombre, precio, stock, excluir_id=product_id)
    if stock is None:
        conn.execute("UPDATE products SET name = ?, price = ? WHERE id = ?",
                     (nombre, precio, product_id))
    else:
        conn.execute("UPDATE products SET name = ?, price = ?, stock = ? WHERE id = ?",
                     (nombre, precio, stock, product_id))


def usos_del_producto(conn, product_id):
    """Cuántas ventas, compras y pérdidas lo mencionan: el PC advierte que
    borrar un producto con movimientos deja registros sin nombre."""
    uno = lambda sql: conn.execute(sql, (product_id,)).fetchone()[0]
    return {"ventas": uno("SELECT COUNT(*) FROM sale_details WHERE product_id = ?"),
            "compras": uno("SELECT COUNT(*) FROM purchase_details WHERE product_id = ?"),
            "perdidas": uno("SELECT COUNT(*) FROM losses WHERE product_id = ?")}


def eliminar_producto(conn, product_id):
    if conn.execute("SELECT 1 FROM products WHERE id = ?", (product_id,)).fetchone() is None:
        raise ValueError("El producto no existe")
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
