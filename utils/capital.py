"""
Capital de trabajo: responde a por qué, habiendo utilidad, no hay efectivo.

La utilidad no es dinero disponible. Una parte se queda atrapada en el
inventario y en el fiado por cobrar, y lo que sobra es lo único que se puede
girar. Este módulo hace esa cuenta con los datos reales.
"""
from utils.metricas import meses_disponibles, utilidad_neta

DIAS_COBERTURA = 14        # criterio del negocio: stock para dos semanas
COLCHON_MINIMO = 1_000_000  # efectivo que conviene no tocar


def _limites(mes):
    anio, num = int(mes[:4]), int(mes[5:7])
    siguiente = f"{anio + 1}-01-01" if num == 12 else f"{anio}-{num + 1:02d}-01"
    return f"{anio}-{num:02d}-01", siguiente


def situacion(conn) -> dict:
    """Foto de hoy: dónde está el capital y cuánto queda libre.

    El efectivo se toma de la conciliación de caja, que es la verdad: dinero
    que entró menos dinero que salió. El capital disponible se deriva de ahí
    sumando lo inmovilizado, para que ambas pantallas no puedan discrepar.

    Las reinversiones NO suman capital aparte: son utilidad que el socio no
    retiró, así que ya están dentro de la utilidad acumulada y fuera de los
    giros. Contarlas otra vez las duplicaría.
    """
    from utils.conciliacion import calcular

    def escalar(sql, params=()):
        f = conn.execute(sql, params).fetchone()
        return float(f[0] or 0) if f else 0.0

    inventario = escalar("SELECT SUM(stock * cost_price) FROM products")
    cartera    = escalar("SELECT SUM(total_debt) FROM clients WHERE total_debt > 0")
    aportes    = escalar("SELECT SUM(monto) FROM conciliacion_manual WHERE concepto LIKE 'Inicio%'")
    reinver    = escalar("SELECT SUM(monto) FROM giros_socios WHERE tipo = 'reinversion'")
    giros      = escalar("SELECT SUM(monto) FROM giros_socios WHERE tipo = 'giro'")
    utilidad   = utilidad_neta(conn)

    efectivo = calcular(conn)["acumulado"]["EFECTIVO NETO QUE DEBERÍA EXISTIR"]

    return {
        "inventario": inventario,
        "cartera": cartera,
        "inmovilizado": inventario + cartera,
        "aportes": aportes,
        "reinversiones": reinver,
        "utilidad": utilidad,
        "giros": giros,
        "efectivo_libre": efectivo,
        "disponible": efectivo + inventario + cartera,
    }


def inventario_objetivo(conn, dias=DIAS_COBERTURA):
    """Cuánto inventario hace falta para aguantar `dias` de venta, y qué falta."""
    periodo = conn.execute(
        "SELECT julianday(MAX(created_at)) - julianday(MIN(created_at)) FROM sales"
    ).fetchone()[0] or 1

    filas = conn.execute("""
        SELECT p.id, p.name, p.stock, p.cost_price, COALESCE(SUM(sd.quantity), 0)
          FROM products p
          LEFT JOIN sale_details sd ON sd.product_id = p.id
         GROUP BY p.id""").fetchall()

    objetivo = actual = 0.0
    faltantes = []
    for _, nombre, stock, costo, vendidas in filas:
        stock, costo = stock or 0, costo or 0
        diaria = vendidas / periodo
        meta = diaria * dias
        objetivo += meta * costo
        actual += stock * costo
        if meta > stock and diaria > 0.05:
            faltantes.append({
                "producto": nombre, "stock": stock, "objetivo": meta,
                "faltan_unidades": meta - stock,
                "faltan_pesos": (meta - stock) * costo,
            })

    faltantes.sort(key=lambda f: -f["faltan_pesos"])
    return {"objetivo": objetivo, "actual": actual,
            "brecha": objetivo - actual, "faltantes": faltantes}


def girable_por_mes(conn) -> list:
    """Lo que de verdad se podía repartir cada mes, frente a lo que se giró.

    Girable = utilidad del mes − lo que creció la cartera ese mes. Si el fiado
    crece, esa utilidad todavía está en la calle y no se puede repartir. La
    cartera crece con lo fiado y baja con los abonos y las ventas anuladas.
    """
    resultado = []
    for mes in meses_disponibles(conn):
        desde, hasta = _limites(mes)
        util = utilidad_neta(conn, mes)

        delta = conn.execute("""
            SELECT COALESCE(SUM(CASE WHEN transaction_type = 'debit'  THEN amount ELSE 0 END), 0)
                 - COALESCE(SUM(CASE WHEN transaction_type IN ('credit', 'debit_reversal')
                                     THEN amount ELSE 0 END), 0)
              FROM client_transactions WHERE created_at >= ? AND created_at < ?""",
            (desde, hasta)).fetchone()[0]

        girado = conn.execute("""
            SELECT COALESCE(SUM(monto), 0) FROM giros_socios
             WHERE tipo = 'giro' AND fecha >= ? AND fecha < ?""",
            (desde, hasta)).fetchone()[0]

        girable = max(util - delta, 0)
        resultado.append({
            "mes": mes, "utilidad": util, "delta_cartera": delta,
            "girable": girable, "girado": girado, "exceso": girado - girable,
        })
    return resultado


def girable_ahora(conn, socios=3) -> dict:
    """Cuánto se puede sacar en este momento, no en el mes.

    Parte del efectivo real de la conciliación —que solo cuenta ventas de
    contado y abonos cobrados, nunca lo fiado— y le descuenta lo que el
    negocio necesita para seguir funcionando: reponer el inventario que falta
    y conservar el colchón de operación.
    """
    s = situacion(conn)
    inv = inventario_objetivo(conn)
    reponer = max(inv["brecha"], 0)

    disponible = s["efectivo_libre"] - reponer - COLCHON_MINIMO
    return {
        "efectivo": s["efectivo_libre"],
        "reponer_inventario": reponer,
        "colchon": COLCHON_MINIMO,
        "disponible": max(disponible, 0),
        "faltante": max(-disponible, 0),
        "por_socio": max(disponible, 0) / socios,
        "socios": socios,
    }


def diagnostico(conn) -> list:
    """Avisos en lenguaje llano, para saber qué hacer sin interpretar tablas."""
    s = situacion(conn)
    inv = inventario_objetivo(conn)
    meses = girable_por_mes(conn)
    avisos = []

    ahora = girable_ahora(conn)
    if ahora["disponible"] > 0:
        avisos.append(("success",
            f"Ahora mismo se puede girar {ahora['disponible']:,.0f} en total, "
            f"o sea {ahora['por_socio']:,.0f} por socio, sin descuidar el negocio."))
    else:
        avisos.append(("danger",
            f"Ahora mismo no hay nada que girar: faltan {ahora['faltante']:,.0f} "
            f"para cubrir la reposición de inventario y el colchón de operación."))

    if s["efectivo_libre"] < COLCHON_MINIMO:
        avisos.append(("danger",
            f"Efectivo libre en {s['efectivo_libre']:,.0f}: por debajo del colchón "
            f"recomendado de {COLCHON_MINIMO:,.0f}. No hay margen para giros."))
    else:
        avisos.append(("success",
            f"Efectivo libre de {s['efectivo_libre']:,.0f}, por encima del colchón."))

    if inv["brecha"] > 0:
        avisos.append(("warning",
            f"Faltan {inv['brecha']:,.0f} de inventario para cubrir "
            f"{DIAS_COBERTURA} días de venta ({len(inv['faltantes'])} productos por debajo)."))

    exceso = sum(m["exceso"] for m in meses if m["exceso"] > 0)
    if exceso > 0:
        avisos.append(("danger",
            f"Se ha girado {exceso:,.0f} por encima de lo que el negocio liberó. "
            f"Ese dinero salió del capital, no de la ganancia."))

    ultimo = meses[-1] if meses else None
    if ultimo:
        avisos.append(("info",
            f"Este mes se puede girar hasta {ultimo['girable']:,.0f} "
            f"(utilidad {ultimo['utilidad']:,.0f} menos {ultimo['delta_cartera']:,.0f} "
            f"que se quedó en fiado). Ya se giró {ultimo['girado']:,.0f}."))

    necesario = inv["objetivo"] + s["cartera"] + COLCHON_MINIMO
    avisos.append(("info" if s["disponible"] >= necesario else "warning",
        f"El negocio necesita unos {necesario:,.0f} de capital "
        f"(inventario + fiado + colchón) y dispone de {s['disponible']:,.0f}."))

    return avisos
