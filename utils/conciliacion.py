"""
Conciliación de caja: reproduce en la aplicación el cuadro que antes vivía en
la hoja ConciliacionCaja del Excel.

Casi todo sale de la base. Solo dos filas se teclean a mano ("Inicio - Venta
Mobiliario - Ajustes" y "Ajuste"), que se guardan en conciliacion_manual, y los
giros a socios, que viven en su propia tabla.
"""
from datetime import date

# Conceptos que el usuario escribe a mano, no calculados
MANUAL_INICIO = "Inicio - Venta Mobiliario - Ajustes"
MANUAL_AJUSTE = "Ajuste"

MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def nombre_mes(mes: str) -> str:
    """'2026-02' → 'Febrero 2026'"""
    anio, num = mes.split("-")
    return f"{MESES_ES[int(num) - 1].capitalize()} {anio}"


def _limites(mes: str):
    """Devuelve el rango [inicio, fin) del mes, como texto comparable en SQLite."""
    anio, num = int(mes[:4]), int(mes[5:7])
    siguiente = f"{anio + 1}-01-01" if num == 12 else f"{anio}-{num + 1:02d}-01"
    return f"{anio}-{num:02d}-01", siguiente


def meses_con_datos(conn) -> list:
    """Meses que van desde la primera venta hasta hoy, sin huecos."""
    fila = conn.execute("SELECT MIN(created_at), MAX(created_at) FROM sales").fetchone()
    if not fila or not fila[0]:
        hoy = date.today()
        return [f"{hoy.year}-{hoy.month:02d}"]

    anio, num = int(str(fila[0])[:4]), int(str(fila[0])[5:7])
    fin_anio, fin_num = int(str(fila[1])[:4]), int(str(fila[1])[5:7])

    meses = []
    while (anio, num) <= (fin_anio, fin_num):
        meses.append(f"{anio}-{num:02d}")
        num += 1
        if num == 13:
            anio, num = anio + 1, 1
    return meses


def _suma(conn, sql, mes, extra=()):
    desde, hasta = _limites(mes)
    fila = conn.execute(sql, (*extra, desde, hasta)).fetchone()
    return float(fila[0] or 0)


def _manual(conn, mes, concepto):
    fila = conn.execute(
        "SELECT monto FROM conciliacion_manual WHERE mes = ? AND concepto = ?",
        (mes, concepto),
    ).fetchone()
    return float(fila[0]) if fila and fila[0] is not None else 0.0


def calcular(conn, meses=None) -> dict:
    """Devuelve el cuadro completo: filas, meses y totales acumulados."""
    if meses is None:
        meses = meses_con_datos(conn)

    valores = {}

    valores["Ventas en efectivo (contado)"] = [
        _suma(conn, """SELECT SUM(total) FROM sales
                        WHERE payment_method = 'cash'
                          AND created_at >= ? AND created_at < ?""", m)
        for m in meses]

    valores[MANUAL_INICIO] = [_manual(conn, m, MANUAL_INICIO) for m in meses]

    valores["Abonos"] = [
        _suma(conn, """SELECT SUM(amount) FROM client_transactions
                        WHERE transaction_type = 'credit'
                          AND created_at >= ? AND created_at < ?""", m)
        for m in meses]

    valores["Compras de inventario"] = [
        _suma(conn, """SELECT SUM(total) FROM purchases
                        WHERE date >= ? AND date < ?""", m)
        for m in meses]

    valores["Gastos operativos"] = [
        _suma(conn, """SELECT SUM(amount) FROM expenses
                        WHERE date >= ? AND date < ?""", m)
        for m in meses]

    valores[MANUAL_AJUSTE] = [_manual(conn, m, MANUAL_AJUSTE) for m in meses]

    valores["Giros a socios"] = [
        _suma(conn, """SELECT SUM(monto) FROM giros_socios
                        WHERE tipo = 'giro'
                          AND fecha >= ? AND fecha < ?""", m)
        for m in meses]

    def sumar(*conceptos):
        return [sum(valores[c][i] for c in conceptos) for i in range(len(meses))]

    valores["TOTAL ENTRADAS"] = sumar(
        "Ventas en efectivo (contado)", MANUAL_INICIO, "Abonos")
    valores["TOTAL SALIDAS"] = sumar(
        "Compras de inventario", "Gastos operativos", MANUAL_AJUSTE, "Giros a socios")
    valores["EFECTIVO NETO QUE DEBERÍA EXISTIR"] = [
        valores["TOTAL ENTRADAS"][i] - valores["TOTAL SALIDAS"][i]
        for i in range(len(meses))]

    # Estructura de presentación: (tipo, concepto)
    filas = [
        ("seccion", "ENTRADAS DE DINERO"),
        ("dato",    "Ventas en efectivo (contado)"),
        ("manual",  MANUAL_INICIO),
        ("dato",    "Abonos"),
        ("total",   "TOTAL ENTRADAS"),
        ("seccion", "SALIDAS DE DINERO"),
        ("dato",    "Compras de inventario"),
        ("dato",    "Gastos operativos"),
        ("manual",  MANUAL_AJUSTE),
        ("dato",    "Giros a socios"),
        ("total",   "TOTAL SALIDAS"),
        ("neto",    "EFECTIVO NETO QUE DEBERÍA EXISTIR"),
    ]

    return {
        "meses": meses,
        "encabezados": [nombre_mes(m) for m in meses],
        "filas": filas,
        "valores": valores,
        "acumulado": {c: sum(v) for c, v in valores.items()},
    }


def informacion_adicional(conn) -> dict:
    """Las dos líneas informativas del pie del cuadro."""
    clientes = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(total_debt), 0) FROM clients WHERE total_debt > 0"
    ).fetchone()
    perdidas = conn.execute("SELECT COALESCE(SUM(total_cost), 0) FROM losses").fetchone()
    return {
        "clientes_con_deuda": clientes[0],
        "cuentas_por_cobrar": float(clientes[1]),
        "perdidas": float(perdidas[0]),
    }


def deudores(conn) -> list:
    """Lista de clientes con deuda, con la fecha de su venta pendiente más
    antigua y los días transcurridos. Es lo que antes traía la hoja Pendientes."""
    from datetime import datetime

    filas = conn.execute("""
        SELECT c.name, c.total_debt,
               (SELECT DATE(s.created_at) FROM sales s
                 WHERE s.client_id = c.id AND s.status = 'pending'
                 ORDER BY s.created_at ASC LIMIT 1) AS desde
          FROM clients c
         WHERE c.total_debt > 0
         ORDER BY c.total_debt DESC
    """).fetchall()

    hoy = datetime.now().date()
    resultado = []
    for nombre, deuda, desde in filas:
        if desde:
            fecha = datetime.strptime(str(desde)[:10], "%Y-%m-%d").date()
            texto = f"{fecha.day} de {MESES_ES[fecha.month - 1]}"
            dias = (hoy - fecha).days
        else:
            texto, dias = "", None
        resultado.append((nombre, float(deuda), texto, dias))
    return resultado


def telefonos_clientes(conn) -> dict:
    """{nombre: teléfono} de los clientes con deuda que tienen teléfono."""
    filas = conn.execute("""
        SELECT name, phone FROM clients
         WHERE total_debt > 0 AND COALESCE(TRIM(phone), '') <> ''
    """).fetchall()
    return {nombre: telefono for nombre, telefono in filas}


# ── Giros a socios ───────────────────────────────────────────────────────────
def listar_giros(conn) -> list:
    """Todos los movimientos hacia socios, del más reciente al más antiguo."""
    return conn.execute("""
        SELECT id, fecha, socio, monto, COALESCE(concepto, ''), tipo
          FROM giros_socios
         ORDER BY fecha DESC, id DESC
    """).fetchall()


def resumen_socios(conn) -> list:
    """Total retirado e invertido por socio: giros + reinversiones."""
    return conn.execute("""
        SELECT socio,
               SUM(CASE WHEN tipo = 'giro'        THEN monto ELSE 0 END),
               SUM(CASE WHEN tipo = 'reinversion' THEN monto ELSE 0 END),
               SUM(monto)
          FROM giros_socios
         GROUP BY socio
         ORDER BY 4 DESC
    """).fetchall()


def socios_conocidos(conn) -> list:
    filas = conn.execute("SELECT DISTINCT socio FROM giros_socios ORDER BY socio").fetchall()
    return [f[0] for f in filas]


def guardar_giro(conn, giro_id, fecha, socio, monto, concepto, tipo):
    if giro_id:
        conn.execute("""UPDATE giros_socios
                           SET fecha = ?, socio = ?, monto = ?, concepto = ?, tipo = ?
                         WHERE id = ?""",
                     (fecha, socio, monto, concepto, tipo, giro_id))
    else:
        conn.execute("""INSERT INTO giros_socios (fecha, socio, monto, concepto, tipo)
                        VALUES (?,?,?,?,?)""", (fecha, socio, monto, concepto, tipo))
    conn.commit()


def borrar_giro(conn, giro_id):
    conn.execute("DELETE FROM giros_socios WHERE id = ?", (giro_id,))
    conn.commit()
