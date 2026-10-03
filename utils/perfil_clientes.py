"""Cómo compra cada cliente, para escribirle antes de la ruta a quien suele
pedir y todavía no ha pedido, y saber cuánto ofrecerle.

Se cuenta por visita (todo lo que un cliente compró en un mismo día), no por
venta: si se anotó en dos ventas, para él fue una sola compra. La compra
típica es la mediana, no el promedio: un pedido grande de una vez no la mueve.
Las ventas anuladas se borran de la tabla de ventas, así que no hay que
filtrarlas.

Los domicilios se hacen una vez a la semana, el fin de semana. Por eso "le
toca" se mide contra el próximo domingo y no contra hoy: el jueves ya hay que
escribirle a quien pide cada semana, aunque su última compra sea de hace 4 días.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import median

DIAS_MIRADOS = 120          # lo de hace más tiempo ya no dice cómo compra hoy
MIN_PAREJAS = 8             # veces juntos para sugerir un producto con otro
NO_SUGERIR = ("ajuste",)    # productos que no son mercancía
DE_SIEMPRE = 0.4            # lo lleva en al menos 4 de cada 10 compras


def proxima_ruta(hoy):
    """El domingo que viene (hoy mismo si es domingo)."""
    return hoy + timedelta(days=(6 - hoy.weekday()) % 7)


def _desde(hoy):
    return (hoy - timedelta(days=DIAS_MIRADOS)).isoformat()


def _visitas(conn, desde, client_id=None):
    """{cliente: {día: {"total", "productos": {producto: cantidad}}}}."""
    filtro, params = "", [desde]
    if client_id is not None:
        filtro, params = " AND s.client_id = ?", [desde, client_id]
    visitas = defaultdict(lambda: defaultdict(lambda: {"total": 0.0, "productos": Counter()}))
    for cid, dia, total in conn.execute(f"""
            SELECT s.client_id, date(s.created_at), s.total FROM sales s
             WHERE s.client_id IS NOT NULL AND date(s.created_at) >= ?{filtro}""", params):
        visitas[cid][dia]["total"] += total or 0
    for cid, dia, producto, cantidad in conn.execute(f"""
            SELECT s.client_id, date(s.created_at), d.product_id, d.quantity
              FROM sale_details d JOIN sales s ON s.id = d.sale_id
             WHERE s.client_id IS NOT NULL AND date(s.created_at) >= ?{filtro}""", params):
        visitas[cid][dia]["productos"][producto] += cantidad or 0
    return visitas


def _parejas(conn, desde):
    """{producto: [(otro, veces juntos), ...]}, de todas las ventas del periodo."""
    juntos = defaultdict(Counter)
    for a, b, n in conn.execute("""
            SELECT x.product_id, y.product_id, COUNT(*)
              FROM sale_details x
              JOIN sale_details y ON y.sale_id = x.sale_id AND y.product_id <> x.product_id
              JOIN sales s ON s.id = x.sale_id
             WHERE date(s.created_at) >= ?
             GROUP BY 1, 2""", (desde,)):
        if n >= MIN_PAREJAS:
            juntos[a][b] = n
    return juntos


def _productos(conn):
    return {pid: {"nombre": nombre, "precio": precio or 0, "stock": stock or 0}
            for pid, nombre, precio, stock in conn.execute(
                "SELECT id, name, price, stock FROM products")}


def _sugerencia(veces, n_visitas, parejas, productos):
    """Lo que más se vende junto con lo que él lleva, que él casi nunca
    compra y que hay en tienda."""
    puntaje = Counter()
    for pid, _ in veces.most_common(3):
        for otro, n in parejas.get(pid, {}).items():
            p = productos.get(otro)
            if (not p or p["stock"] <= 0 or p["precio"] <= 0
                    or p["nombre"].strip().lower() in NO_SUGERIR
                    or veces[otro] / n_visitas > 0.25):     # ya lo lleva seguido
                continue
            puntaje[otro] += n
    if not puntaje:
        return None
    otro = puntaje.most_common(1)[0][0]
    return {"producto": productos[otro]["nombre"], "precio": productos[otro]["precio"]}


def _cantidad(q):
    return str(int(q)) if float(q).is_integer() else f"{q:g}".replace(".", ",")


def _mensaje(de_siempre, sugerencia):
    # Sin el nombre: muchos están guardados con apodos ("cuñada de Emily")
    texto = "¡Hola! ¿Te llevamos lo de siempre este fin de semana?"
    if de_siempre:
        texto += " " + ", ".join(f"{_cantidad(q)} {p}" for p, q in de_siempre) + "."
    if sugerencia:
        texto += f" También tenemos {sugerencia['producto']}, por si quieres agregarlo."
    return texto


def _perfil(cid, nombre, telefono, dias, parejas, productos, hoy):
    fechas = sorted(dias)
    totales = [dias[d]["total"] for d in fechas]
    distintas = [date.fromisoformat(d) for d in fechas]
    huecos = [(b - a).days for a, b in zip(distintas, distintas[1:])]
    # Con menos de 3 compras no hay ritmo que valga
    ritmo = max(1, round(median(huecos))) if len(huecos) >= 2 else None
    ultima = distintas[-1]
    dias_sin_venir = (hoy - ultima).days
    dias_a_la_ruta = (proxima_ruta(hoy) - ultima).days

    veces, cantidades = Counter(), defaultdict(list)
    for d in fechas:
        for p, q in dias[d]["productos"].items():
            veces[p] += 1
            cantidades[p].append(q)
    de_siempre = [(productos.get(p, {}).get("nombre", "Producto"), median(cantidades[p]))
                  for p, n in veces.most_common(4) if n / len(fechas) >= DE_SIEMPRE]

    if ritmo is None:
        estado = "pocas"
    elif dias_sin_venir >= max(21, ritmo * 2, ritmo + 7):
        estado = "lejos"
    elif dias_a_la_ruta >= ritmo:
        estado = "toca"
    else:
        estado = "normal"

    tipica = median(totales)
    sugerencia = _sugerencia(veces, len(fechas), parejas, productos)
    return {
        "id": cid,
        "nombre": nombre,
        "telefono": telefono,
        "whatsapp": enlace_whatsapp(telefono),
        "visitas": len(fechas),
        "tipica": tipica,
        "promedio": sum(totales) / len(totales),
        "por_mes": sum(totales) / (DIAS_MIRADOS / 30),
        "ritmo": ritmo,
        "ultima": ultima.isoformat(),
        "ultima_total": totales[-1],
        "dias_sin_venir": dias_sin_venir,
        "estado": estado,
        "de_siempre": de_siempre,
        "sugerencia": sugerencia,
        "con_sugerencia": tipica + sugerencia["precio"] if sugerencia else None,
        "mensaje": _mensaje(de_siempre, sugerencia),
    }


def perfiles(conn, hoy=None):
    """Un perfil por cliente que compró en los últimos DIAS_MIRADOS días,
    del que más compra al mes al que menos."""
    hoy = hoy or date.today()
    desde = _desde(hoy)
    parejas, productos = _parejas(conn, desde), _productos(conn)
    clientes = {cid: (nombre, telefono) for cid, nombre, telefono in conn.execute(
        "SELECT id, name, phone FROM clients")}
    lista = [_perfil(cid, *clientes.get(cid, ("Cliente", None)), dias, parejas, productos, hoy)
             for cid, dias in _visitas(conn, desde).items()]
    lista.sort(key=lambda p: -p["por_mes"])
    return lista


def perfil(conn, client_id, hoy=None):
    """El perfil de un solo cliente, o None si no compró en el periodo."""
    hoy = hoy or date.today()
    desde = _desde(hoy)
    dias = _visitas(conn, desde, client_id).get(client_id)
    if not dias:
        return None
    nombre, telefono = conn.execute(
        "SELECT name, phone FROM clients WHERE id = ?", (client_id,)).fetchone()
    return _perfil(client_id, nombre, telefono, dias, _parejas(conn, desde), _productos(conn), hoy)


def enlace_whatsapp(telefono):
    """wa.me con el número en formato internacional (Colombia si tiene 10 dígitos)."""
    digitos = "".join(ch for ch in str(telefono or "") if ch.isdigit())
    if len(digitos) < 7:
        return None
    if len(digitos) == 10:
        digitos = "57" + digitos
    return f"https://wa.me/{digitos}"
