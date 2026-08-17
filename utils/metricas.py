"""
Medidas para el panel de análisis, equivalentes a las del informe de Power BI.

Cada función acepta un filtro de mes ('AAAA-MM' o None para todo el histórico).
Las que reproducen una medida DAX del informe lo indican en su docstring.
"""


def _rango(mes):
    if not mes:
        return None
    anio, num = int(mes[:4]), int(mes[5:7])
    siguiente = f"{anio + 1}-01-01" if num == 12 else f"{anio}-{num + 1:02d}-01"
    return f"{anio}-{num:02d}-01", siguiente


def _filtro(campo, mes, alias=""):
    """Devuelve (fragmento SQL, parámetros) para acotar por mes."""
    r = _rango(mes)
    if not r:
        return "", []
    col = f"{alias}.{campo}" if alias else campo
    return f" AND {col} >= ? AND {col} < ?", list(r)


def _escalar(conn, sql, params=()):
    fila = conn.execute(sql, params).fetchone()
    return float(fila[0] or 0) if fila else 0.0


# ── Ventas ───────────────────────────────────────────────────────────────────
def total_ingresos(conn, mes=None):
    """DAX «Total Ingresos»: todo lo facturado, contado y fiado."""
    f, p = _filtro("created_at", mes)
    return _escalar(conn, f"SELECT SUM(total) FROM sales WHERE 1=1{f}", p)


def ingresos_por_producto(conn, mes=None, limite=12):
    """DAX «Ingresos por Producto»."""
    f, p = _filtro("created_at", mes, "s")
    return conn.execute(f"""
        SELECT p.name, SUM(sd.subtotal)
          FROM sale_details sd
          JOIN sales s   ON s.id = sd.sale_id
          JOIN products p ON p.id = sd.product_id
         WHERE 1=1{f}
         GROUP BY p.name ORDER BY 2 DESC LIMIT {limite}""", p).fetchall()


def unidades_vendidas(conn, mes=None, limite=12):
    """DAX «Unidades vendidas»."""
    f, p = _filtro("created_at", mes, "s")
    return conn.execute(f"""
        SELECT p.name, SUM(sd.quantity)
          FROM sale_details sd
          JOIN sales s    ON s.id = sd.sale_id
          JOIN products p ON p.id = sd.product_id
         WHERE 1=1{f}
         GROUP BY p.name ORDER BY 2 DESC LIMIT {limite}""", p).fetchall()


def ingresos_por_mes(conn):
    return conn.execute("""
        SELECT strftime('%Y-%m', created_at) AS mes, SUM(total)
          FROM sales GROUP BY mes ORDER BY mes""").fetchall()


# ── Compras ──────────────────────────────────────────────────────────────────
def total_compras(conn, mes=None):
    """DAX «Total Compras». Usa purchases.total, que es lo que cuadra con la
    conciliación; purchase_details.subtotal deja fuera fletes e IVA."""
    f, p = _filtro("date", mes)
    return _escalar(conn, f"SELECT SUM(total) FROM purchases WHERE 1=1{f}", p)


def compras_por_producto(conn, mes=None, limite=12):
    f, p = _filtro("date", mes, "c")
    return conn.execute(f"""
        SELECT pr.name, SUM(pd.subtotal)
          FROM purchase_details pd
          JOIN purchases c ON c.id = pd.purchase_id
          JOIN products pr ON pr.id = pd.product_id
         WHERE 1=1{f}
         GROUP BY pr.name ORDER BY 2 DESC LIMIT {limite}""", p).fetchall()


def unidades_compradas(conn, mes=None, limite=12):
    """DAX «Unidades Compradas»."""
    f, p = _filtro("date", mes, "c")
    return conn.execute(f"""
        SELECT pr.name, SUM(pd.quantity)
          FROM purchase_details pd
          JOIN purchases c ON c.id = pd.purchase_id
          JOIN products pr ON pr.id = pd.product_id
         WHERE 1=1{f}
         GROUP BY pr.name ORDER BY 2 DESC LIMIT {limite}""", p).fetchall()


# ── Egresos ──────────────────────────────────────────────────────────────────
def total_gastos(conn, mes=None):
    """DAX «Total Gastos»."""
    f, p = _filtro("date", mes)
    return _escalar(conn, f"SELECT SUM(amount) FROM expenses WHERE 1=1{f}", p)


def total_perdidas(conn, mes=None):
    """DAX «Total Pérdidas»."""
    f, p = _filtro("created_at", mes)
    return _escalar(conn, f"SELECT SUM(total_cost) FROM losses WHERE 1=1{f}", p)


def total_iva(conn, mes=None):
    """DAX «Total IVA»."""
    f, p = _filtro("date", mes)
    return _escalar(conn, f"SELECT SUM(iva) FROM purchases WHERE 1=1{f}", p)


def total_flete(conn, mes=None):
    """DAX «Total Flete».

    Se usa purchases.shipping, no shipping_total: esta última guarda el flete
    del lote completo repetido en cada compra del lote, así que sumarla
    multiplica el flete por el número de compras (8,2 M en vez de 1,86 M).
    """
    f, p = _filtro("date", mes)
    return _escalar(conn, f"SELECT SUM(shipping) FROM purchases WHERE 1=1{f}", p)


def total_mercancia(conn, mes=None):
    """Compras sin flete ni IVA, tomado de las líneas de compra."""
    f, p = _filtro("date", mes, "c")
    return _escalar(conn, f"""
        SELECT SUM(pd.subtotal) FROM purchase_details pd
          JOIN purchases c ON c.id = pd.purchase_id
         WHERE 1=1{f}""", p)


def valor_inventario(conn, mes=None):
    """DAX «Valor Inventario»: existencias valoradas a precio de costo."""
    return _escalar(conn, "SELECT SUM(stock * cost_price) FROM products")


def costo_mercancia_vendida(conn, mes=None):
    """COGS: costo de lo efectivamente vendido, desde las líneas de venta."""
    f, p = _filtro("created_at", mes, "s")
    return _escalar(conn, f"""
        SELECT SUM(sd.quantity * sd.cost_price)
          FROM sale_details sd JOIN sales s ON s.id = sd.sale_id
         WHERE 1=1{f}""", p)


def composicion_egresos(conn, mes=None):
    """Reparto de los egresos sin duplicar nada.

    Ojo: purchases.total ya incluye flete e IVA (total = detalle + shipping +
    iva, identidad comprobada sobre los datos). Por eso aquí las compras se
    desglosan en mercancía, flete e IVA en vez de sumarse encima.
    """
    return [
        ("Mercancía", total_mercancia(conn, mes)),
        ("Flete",     total_flete(conn, mes)),
        ("IVA",       total_iva(conn, mes)),
        ("Gastos",    total_gastos(conn, mes)),
        ("Pérdidas",  total_perdidas(conn, mes)),
    ]


def meses_disponibles(conn):
    filas = conn.execute("""
        SELECT DISTINCT strftime('%Y-%m', created_at) FROM sales
         WHERE created_at IS NOT NULL ORDER BY 1""").fetchall()
    return [f[0] for f in filas]


# ── Medidas de rentabilidad (traducidas del DAX del informe) ─────────────────
def cogs(conn, mes=None):
    """DAX «COGS»: unidades vendidas por el precio de compra del producto.

    Se usa products.cost_price, que es el equivalente de inventario[p.compra]
    del modelo. La base guarda además el costo histórico en cada línea de
    venta; da un 0,7 % menos, pero no es lo que calculaba el informe.
    """
    f, p = _filtro("created_at", mes, "s")
    return _escalar(conn, f"""
        SELECT SUM(sd.quantity * pr.cost_price)
          FROM sale_details sd
          JOIN sales s     ON s.id = sd.sale_id
          JOIN products pr ON pr.id = sd.product_id
         WHERE 1=1{f}""", p)


def utilidad_neta(conn, mes=None):
    """DAX «Utilidad Neta»:
       Total Ingresos - COGS - Flete - IVA - Pérdidas - Gastos"""
    return (total_ingresos(conn, mes) - cogs(conn, mes) - total_flete(conn, mes)
            - total_iva(conn, mes) - total_perdidas(conn, mes) - total_gastos(conn, mes))


def utilidad_neta_pagada(conn, mes=None):
    """DAX «Utilidad Neta Pagada»: igual que la anterior, pero contando solo
    las ventas ya cobradas. Lo fiado no entra hasta que se paga."""
    f, p = _filtro("created_at", mes)
    ingresos = _escalar(conn, f"""
        SELECT SUM(total) FROM sales WHERE status = 'paid'{f}""", p)

    f2, p2 = _filtro("created_at", mes, "s")
    costo = _escalar(conn, f"""
        SELECT SUM(sd.quantity * pr.cost_price)
          FROM sale_details sd
          JOIN sales s     ON s.id = sd.sale_id
          JOIN products pr ON pr.id = sd.product_id
         WHERE s.status = 'paid'{f2}""", p2)

    return (ingresos - costo - total_flete(conn, mes) - total_iva(conn, mes)
            - total_gastos(conn, mes) - total_perdidas(conn, mes))


def egresos_con_cogs(conn, mes=None):
    """DAX «Egresos con COGS»: COGS + Flete + IVA + Pérdidas + Gastos.
    Cuenta el costo de lo vendido en vez de todo lo comprado."""
    return (cogs(conn, mes) + total_flete(conn, mes) + total_iva(conn, mes)
            + total_perdidas(conn, mes) + total_gastos(conn, mes))


def rubro_a_cada_uno(conn, mes=None, socios=3):
    """DAX «RubroAcadaUno»: la utilidad neta repartida entre los socios."""
    return utilidad_neta(conn, mes) / socios


def serie_mensual(conn, funcion):
    """Aplica una medida mes a mes, para las gráficas de evolución."""
    return [(m, funcion(conn, m)) for m in meses_disponibles(conn)]
