"""Productos: crear, editar y eliminar, con las reglas de la pantalla de
inventario del PC. Ninguna función hace commit.

La categoría y el modo del catálogo (ver servicios/catalogo.py) son
opcionales: si no se pasan, no se tocan, y así nada de esto falla en una base
que todavía no tenga esas columnas."""
from servicios.catalogo import normalizar_categoria, normalizar_modo


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


def _campos_catalogo(categoria, catalogo):
    """Las columnas del catálogo que hay que escribir, con su valor."""
    campos = {}
    if categoria is not None:
        campos["categoria"] = normalizar_categoria(categoria)
    if catalogo is not None:
        campos["catalogo"] = normalizar_modo(catalogo)
    return campos


def crear_producto(conn, nombre, precio, stock=0, categoria=None, catalogo=None):
    nombre = _validar(conn, nombre, precio, stock or 0)
    campos = {"name": nombre, "price": precio, "stock": stock or 0,
              **_campos_catalogo(categoria, catalogo)}
    cursor = conn.cursor()
    cursor.execute(f"INSERT INTO products ({', '.join(campos)}) "
                   f"VALUES ({', '.join('?' * len(campos))})", tuple(campos.values()))
    return cursor.lastrowid


def editar_producto(conn, product_id, nombre, precio, stock=None, categoria=None, catalogo=None):
    """Sin stock (None) se conserva el que tiene, como en el PC. Lo mismo la
    categoría y el modo del catálogo."""
    nombre = _validar(conn, nombre, precio, stock, excluir_id=product_id)
    campos = {"name": nombre, "price": precio}
    if stock is not None:
        campos["stock"] = stock
    campos.update(_campos_catalogo(categoria, catalogo))
    conn.execute(f"UPDATE products SET {', '.join(c + ' = ?' for c in campos)} WHERE id = ?",
                 (*campos.values(), product_id))


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
