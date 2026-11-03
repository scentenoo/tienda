"""Qué pedir, el conteo del martes, los pedidos en camino y los avisos al
celular.

Cada producto que se repone tiene un grupo (de dónde viene) y una caja (de a
cuánto se pide: 6, 12, 24...):
  cucuta    el mayorista: llega a la casa una semana después de pedirlo y
            cobra un flete casi fijo, por eso el pedido es de mínimo $200.000
  medellin  masa y charcutería: los trae el dueño en su viaje de la semana
            (el día lo ponen ellos), sin flete
  queso     lo compra el dueño el domingo; el lunes es el día de domicilios

Cuánto pedir: lo que se vende en una semana, más un colchón, menos lo que va
a quedar cuando llegue el pedido. Lo que se vende se mide solo en los días
en que había: si un producto pasó medio mes agotado, contar esos días como
"no se vendió" haría pedir cada vez menos.

El conteo del martes se hace a ciegas (la página no muestra lo que dice la
app hasta guardar). Lo que falta queda como pérdida "Faltante en el conteo",
con su valor; si después aparece a quién se le fió, se anota la venta y se
devuelve el faltante. Lo que sobra se suma al stock.

Como el resto de servicios, nada aquí hace commit.
"""
import json
import math
from datetime import date, datetime, timedelta

GRUPOS = {
    "cucuta": {"nombre": "Cúcuta", "colchon": 0.5, "minimo": 200_000, "entrega": 7},
    "medellin": {"nombre": "Medellín", "colchon": 0.5, "minimo": 0},
    "queso": {"nombre": "Queso", "colchon": 0.2, "minimo": 0},
}
VENTANA = 56            # días hacia atrás para medir lo que se vende
MARTES = 1
DOMINGO = 6
MOTIVO_FALTANTE = "Faltante en el conteo"
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# Los grupos y las cajas que se ven en las compras de 2026; se ponen solos la
# primera vez y después se cambian en el formulario de cada producto.
GRUPOS_INICIALES = {
    "queso costeño 1k": ("queso", 1),
    "mayonesa mavesa": ("cucuta", 12), "mantequilla mavesa": ("cucuta", 6),
    "riquesa": ("cucuta", 6), "malta 1.5": ("cucuta", 6), "galleta maria": ("cucuta", 12),
    "diablito grande": ("cucuta", 12), "samba": ("cucuta", 20), "savoy chocolate": ("cucuta", 12),
    "cri-cri": ("cucuta", 12), "fororo": ("cucuta", 12), "toddy": ("cucuta", 6),
    "chimu azul": ("cucuta", 12), "anis": ("cucuta", 6), "caroreña sangria": ("cucuta", 6),
    "cacique": ("cucuta", 6), "pepitona": ("cucuta", 17), "marilu": ("cucuta", 12),
    "mantequilla 1 kilo": ("cucuta", 6), "crema de arroz 900gr": ("cucuta", 12),
    "masa facil": ("medellin", 5), "chuleta ahumada 500gr aprox": ("medellin", 10),
    "mortadela vnzla 1k": ("medellin", 1), "bandeja de jamon": ("medellin", 1),
    "bandeja de queso amarrillo": ("medellin", 1), "queso de año": ("medellin", 1),
    "palitos de chocolate": ("medellin", 4), "ovomaltina": ("medellin", 6),
}


def preparar(conn):
    """Las columnas y tablas, la primera vez."""
    columnas = {f[1] for f in conn.execute("PRAGMA table_info(products)").fetchall()}
    if "grupo" not in columnas:
        conn.execute("ALTER TABLE products ADD COLUMN grupo TEXT")      # cucuta, medellin, queso o NULL
        conn.execute("ALTER TABLE products ADD COLUMN caja REAL")       # de a cuánto se pide
        for pid, nombre in conn.execute("SELECT id, name FROM products").fetchall():
            inicial = GRUPOS_INICIALES.get((nombre or "").strip().lower())
            if inicial:
                conn.execute("UPDATE products SET grupo = ?, caja = ? WHERE id = ?", (*inicial, pid))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conteos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hecho TEXT NOT NULL,
            quien TEXT,
            faltante REAL NOT NULL DEFAULT 0,    -- a costo
            sobrante REAL NOT NULL DEFAULT 0)""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conteo_filas (
            conteo_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            esperado REAL NOT NULL,              -- lo que decía la app
            contado REAL NOT NULL,
            costo REAL NOT NULL DEFAULT 0,
            loss_id INTEGER,                     -- la pérdida del faltante
            aparecio REAL NOT NULL DEFAULT 0,    -- lo que después se supo a quién se le dio
            PRIMARY KEY (conteo_id, product_id))""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grupo TEXT NOT NULL,
            creado TEXT NOT NULL,
            llega TEXT NOT NULL,                 -- AAAA-MM-DD
            estado TEXT NOT NULL DEFAULT 'en_camino',   -- en_camino, recibido, cancelado
            cerrado TEXT,
            lote_id TEXT)""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pedido_filas (
            pedido_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            cantidad REAL NOT NULL,
            PRIMARY KEY (pedido_id, product_id))""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS avisos_suscripciones (
            endpoint TEXT PRIMARY KEY,
            datos TEXT NOT NULL,                 -- la suscripción del navegador, en JSON
            quien TEXT,
            equipo TEXT,
            creado TEXT NOT NULL)""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS avisos_enviados (
            clave TEXT PRIMARY KEY,
            enviado TEXT NOT NULL)""")
    conn.execute("CREATE TABLE IF NOT EXISTS ajustes (clave TEXT PRIMARY KEY, valor TEXT)")


def _ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def dia_corto(d):
    """date o 'AAAA-MM-DD' → 'martes 10 nov'."""
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return f"{DIAS[d.weekday()]} {d.day} {MESES[d.month - 1]}"


def martes_de_la_semana(hoy):
    """El martes más reciente (hoy, si es martes): ahí empieza la semana del
    conteo y de los pedidos."""
    return hoy - timedelta(days=(hoy.weekday() - MARTES) % 7)


def proximo_domingo(hoy):
    return hoy + timedelta(days=(DOMINGO - hoy.weekday()) % 7)


# ── Grupo y caja de cada producto ────────────────────────────────────────────
def poner_grupo(conn, product_id, grupo, caja):
    grupo = grupo if grupo in GRUPOS else None
    texto = str(caja if caja is not None else "").strip()
    try:
        caja = float(texto.replace(",", ".")) if texto else None
    except ValueError:
        raise ValueError("La caja debe ser un número, por ejemplo 12")
    if caja is not None and caja <= 0:
        raise ValueError("La caja debe ser mayor a 0")
    conn.execute("UPDATE products SET grupo = ?, caja = ? WHERE id = ?", (grupo, caja, product_id))


def grupo_del_producto(conn, product_id):
    fila = conn.execute("SELECT grupo, caja FROM products WHERE id = ?", (product_id,)).fetchone()
    return {"grupo": fila[0] or "", "caja": fila[1]} if fila else {"grupo": "", "caja": None}


# ── El viaje a Medellín ──────────────────────────────────────────────────────
def viaje_medellin(conn, hoy):
    """La fecha del viaje de esta semana, o None si no la han puesto (o ya pasó)."""
    fila = conn.execute("SELECT valor FROM ajustes WHERE clave = 'viaje_medellin'").fetchone()
    try:
        viaje = date.fromisoformat(fila[0]) if fila and fila[0] else None
    except ValueError:
        return None
    return viaje if viaje and viaje >= hoy else None


def poner_viaje(conn, viaje, hoy):
    if viaje is not None and viaje < hoy:
        raise ValueError("El viaje no puede ser en un día que ya pasó")
    conn.execute("INSERT INTO ajustes (clave, valor) VALUES ('viaje_medellin', ?) "
                 "ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor",
                 (viaje.isoformat() if viaje else "",))


def llegada(grupo, hoy, viaje=None):
    """Cuándo llegaría lo que se pida hoy."""
    if grupo == "cucuta":
        return hoy + timedelta(days=GRUPOS["cucuta"]["entrega"])
    if grupo == "medellin":
        return viaje or hoy + timedelta(days=2)
    return proximo_domingo(hoy)


# ── Lo que se vende ──────────────────────────────────────────────────────────
def demanda(conn, hoy, ids):
    """{product_id: unidades por semana}, contando solo los días en que había.

    Las existencias de cada día se reconstruyen hacia atrás desde el stock de
    hoy, con las ventas, las compras y las pérdidas."""
    if not ids:
        return {}
    desde = hoy - timedelta(days=VENTANA)
    marcas = ", ".join("?" * len(ids))
    stock = {f[0]: f[1] or 0 for f in conn.execute(
        f"SELECT id, stock FROM products WHERE id IN ({marcas})", tuple(ids))}
    movimiento, vendido, llego = {}, {}, set()
    consultas = (
        (-1, f"""SELECT d.product_id, date(s.created_at), SUM(d.quantity) FROM sale_details d
                   JOIN sales s ON s.id = d.sale_id
                  WHERE date(s.created_at) > ? AND d.product_id IN ({marcas}) GROUP BY 1, 2"""),
        (1, f"""SELECT d.product_id, date(p.date), SUM(d.quantity) FROM purchase_details d
                  JOIN purchases p ON p.id = d.purchase_id
                 WHERE date(p.date) > ? AND d.product_id IN ({marcas}) GROUP BY 1, 2"""),
        (-1, f"""SELECT product_id, date(loss_date), SUM(quantity) FROM losses
                  WHERE date(loss_date) > ? AND product_id IN ({marcas}) GROUP BY 1, 2"""),
    )
    for n, (signo, sql) in enumerate(consultas):
        for pid, dia, q in conn.execute(sql, (desde.isoformat(), *ids)).fetchall():
            if dia > hoy.isoformat():
                continue
            movimiento[(pid, dia)] = movimiento.get((pid, dia), 0) + signo * (q or 0)
            if n == 0:
                vendido[pid] = vendido.get(pid, 0) + (q or 0)
            if n == 1:
                llego.add((pid, dia))
    resultado = {}
    for pid in ids:
        al_cierre = stock.get(pid, 0)
        con_stock = 0
        for k in range(VENTANA):
            dia = (hoy - timedelta(days=k)).isoformat()
            al_empezar = al_cierre - movimiento.get((pid, dia), 0)
            if al_empezar > 0 or (pid, dia) in llego:
                con_stock += 1
            al_cierre = al_empezar
        # Con muy pocos días con stock (se acaba el mismo día que llega) se
        # cuenta al menos una semana, para no inflar la cuenta
        resultado[pid] = vendido.get(pid, 0) / max(con_stock, 7) * 7
    return resultado


# ── Pedidos en camino ────────────────────────────────────────────────────────
def en_camino(conn, grupo=None):
    """Los pedidos que todavía no llegan, con sus productos."""
    sql = "SELECT id, grupo, creado, llega FROM pedidos WHERE estado = 'en_camino'"
    pedidos = [dict(id=f[0], grupo=f[1], creado=f[2], llega=f[3], items=[])
               for f in conn.execute(sql + (" AND grupo = ?" if grupo else "") + " ORDER BY llega, id",
                                     (grupo,) if grupo else ()).fetchall()]
    por_id = {p["id"]: p for p in pedidos}
    if por_id:
        for pedido_id, pid, nombre, q, costo in conn.execute(f"""
                SELECT f.pedido_id, f.product_id, COALESCE(p.name, 'Producto'), f.cantidad,
                       COALESCE(p.cost_price, 0)
                  FROM pedido_filas f LEFT JOIN products p ON p.id = f.product_id
                 WHERE f.pedido_id IN ({', '.join('?' * len(por_id))})
                 ORDER BY p.name COLLATE NOCASE""", tuple(por_id)).fetchall():
            por_id[pedido_id]["items"].append({"id": pid, "nombre": nombre, "cantidad": q, "costo": costo})
    for p in pedidos:
        p["total"] = sum(i["cantidad"] * i["costo"] for i in p["items"])
        p["nombre_grupo"] = GRUPOS.get(p["grupo"], {}).get("nombre", p["grupo"])
    return pedidos


def crear_pedido(conn, grupo, cantidades, llega, hoy):
    """cantidades: {product_id: cantidad}. Devuelve el id del pedido."""
    if grupo not in GRUPOS:
        raise ValueError("Grupo desconocido")
    cantidades = {pid: q for pid, q in cantidades.items() if q and q > 0}
    if not cantidades:
        raise ValueError("Escriba la cantidad de al menos un producto")
    if llega < hoy:
        raise ValueError("La fecha de llegada no puede ser en un día que ya pasó")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO pedidos (grupo, creado, llega) VALUES (?, ?, ?)",
                   (grupo, _ahora(), llega.isoformat()))
    pedido_id = cursor.lastrowid
    cursor.execute("INSERT INTO pedido_filas (pedido_id, product_id, cantidad) VALUES "
                   + ", ".join(["(?, ?, ?)"] * len(cantidades)),
                   tuple(v for pid, q in cantidades.items() for v in (pedido_id, pid, q)))
    return pedido_id


def pedido(conn, pedido_id):
    fila = conn.execute("SELECT id, grupo, creado, llega, estado FROM pedidos WHERE id = ?",
                        (pedido_id,)).fetchone()
    if fila is None:
        return None
    items = [{"id": f[0], "nombre": f[1], "cantidad": f[2], "costo": f[3] or 0}
             for f in conn.execute("""
                SELECT f.product_id, p.name, f.cantidad, p.cost_price FROM pedido_filas f
                  JOIN products p ON p.id = f.product_id WHERE f.pedido_id = ?
                 ORDER BY p.name COLLATE NOCASE""", (pedido_id,)).fetchall()]
    return {"id": fila[0], "grupo": fila[1], "creado": fila[2], "llega": fila[3], "estado": fila[4],
            "nombre_grupo": GRUPOS.get(fila[1], {}).get("nombre", fila[1]), "items": items}


def cerrar_pedido(conn, pedido_id, estado, lote_id=None):
    if estado not in ("recibido", "cancelado"):
        raise ValueError("Estado desconocido")
    conn.execute("UPDATE pedidos SET estado = ?, cerrado = ?, lote_id = ? "
                 "WHERE id = ? AND estado = 'en_camino'", (estado, _ahora(), lote_id, pedido_id))


# ── Qué pedir ────────────────────────────────────────────────────────────────
def sugerencias(conn, hoy):
    """Por grupo: cuándo llegaría, qué pedir y cuánto vale."""
    filas = conn.execute("""
        SELECT id, name, stock, COALESCE(cost_price, 0), grupo, caja FROM products
         WHERE grupo IS NOT NULL AND grupo != '' ORDER BY name COLLATE NOCASE""").fetchall()
    semanal = demanda(conn, hoy, [f[0] for f in filas])
    pedidos = en_camino(conn)
    viene = {}
    for p in pedidos:
        for i in p["items"]:
            viene[i["id"]] = viene.get(i["id"], 0) + i["cantidad"]
    viaje = viaje_medellin(conn, hoy)
    resultado = {}
    for clave, g in GRUPOS.items():
        llega = llegada(clave, hoy, viaje)
        dias = (llega - hoy).days
        items = []
        for pid, nombre, stock, costo, grupo, caja in filas:
            if grupo != clave:
                continue
            stock, caja, v = max(stock or 0, 0), caja or 1, semanal.get(pid, 0)
            camino = viene.get(pid, 0)
            al_llegar = max(0.0, stock + camino - v * dias / 7)
            falta = v * (1 + g["colchon"]) - al_llegar
            pedir = math.ceil(falta / caja - 1e-9) * caja if falta > 0 and v > 0 else 0
            items.append({
                "id": pid, "nombre": nombre, "stock": stock, "camino": camino, "semanal": v,
                "caja": caja, "costo": costo, "pedir": pedir, "subtotal": pedir * costo,
                # Se acaba antes de que llegue lo que se pida hoy
                "urgente": v > 0 and stock + camino < v * dias / 7,
                "agotado": stock <= 0,
            })
        items.sort(key=lambda i: (not i["urgente"], not i["pedir"], i["nombre"].lower()))
        total = sum(i["subtotal"] for i in items)
        resultado[clave] = {
            **g, "clave": clave, "llega": llega, "items": items, "total": total,
            "por_pedir": [i for i in items if i["pedir"]],
            "urgentes": [i for i in items if i["urgente"]],
            "alcanza_minimo": total >= g["minimo"],
            "en_camino": [p for p in pedidos if p["grupo"] == clave],
            "pedido_esta_semana": any(p["grupo"] == clave and p["creado"][:10] >= martes_de_la_semana(hoy).isoformat()
                                      for p in pedidos),
        }
    resultado["medellin"]["viaje"] = viaje
    return resultado


def lista_para_mandar(grupo, cantidades):
    """El texto para mandarle al proveedor por WhatsApp."""
    lineas = [f"• {_numero(q)} {nombre}" for nombre, q in cantidades if q > 0]
    return f"Pedido Charcutería HYE ({GRUPOS[grupo]['nombre']}):\n" + "\n".join(lineas)


def _numero(q):
    return str(int(q)) if float(q).is_integer() else f"{q:g}".replace(".", ",")


# ── El conteo del martes ─────────────────────────────────────────────────────
def para_contar(conn):
    """Los productos que se reponen, por grupo, sin decir cuánto dice la app."""
    filas = conn.execute("""
        SELECT id, name, grupo FROM products WHERE grupo IS NOT NULL AND grupo != ''
         ORDER BY name COLLATE NOCASE""").fetchall()
    return {clave: [{"id": f[0], "nombre": f[1]} for f in filas if f[2] == clave] for clave in GRUPOS}


def ultimo_conteo(conn):
    fila = conn.execute("SELECT id, hecho, quien, faltante, sobrante FROM conteos "
                        "ORDER BY hecho DESC, id DESC LIMIT 1").fetchone()
    return dict(zip(("id", "hecho", "quien", "faltante", "sobrante"), fila)) if fila else None


def conteo_hecho(conn, hoy):
    """¿Ya se contó esta semana (desde el martes)?"""
    u = ultimo_conteo(conn)
    return bool(u) and u["hecho"][:10] >= martes_de_la_semana(hoy).isoformat()


def guardar_conteo(conn, contados, hoy, quien, user_id):
    """contados: {product_id: lo que se contó}. Lo que falta queda como
    pérdida (y baja el stock); lo que sobra sube el stock. Devuelve el id."""
    from servicios.gastos import registrar_perdida
    contados = {pid: q for pid, q in contados.items() if q is not None}
    if not contados:
        raise ValueError("No se contó ningún producto")
    if any(q < 0 for q in contados.values()):
        raise ValueError("Lo contado no puede ser negativo")
    productos = {f[0]: f for f in conn.execute(
        f"SELECT id, name, stock, COALESCE(cost_price, 0), price FROM products "
        f"WHERE id IN ({', '.join('?' * len(contados))})", tuple(contados)).fetchall()}
    cursor = conn.cursor()
    cursor.execute("INSERT INTO conteos (hecho, quien) VALUES (?, ?)", (_ahora(), quien))
    conteo_id = cursor.lastrowid
    faltante = sobrante = 0.0
    for pid, contado in contados.items():
        if pid not in productos:
            continue
        _, nombre, esperado, costo, precio = productos[pid]
        esperado = esperado or 0
        costo = costo or 0
        loss_id = None
        diferencia = round(esperado - contado, 3)
        if diferencia > 0 and costo > 0:
            loss_id = registrar_perdida(
                conn, pid, diferencia, costo, hoy, MOTIVO_FALTANTE, "Otro",
                f"Conteo #{conteo_id}: la app decía {_numero(esperado)}, se contaron {_numero(contado)}",
                user_id)
            faltante += diferencia * costo
        elif diferencia != 0:
            conn.execute("UPDATE products SET stock = ? WHERE id = ?", (contado, pid))
            if diferencia < 0:
                sobrante += -diferencia * costo
            else:
                faltante += diferencia * costo
        conn.execute("""INSERT INTO conteo_filas (conteo_id, product_id, esperado, contado, costo, loss_id)
                        VALUES (?, ?, ?, ?, ?, ?)""", (conteo_id, pid, esperado, contado, costo, loss_id))
    conn.execute("UPDATE conteos SET faltante = ?, sobrante = ? WHERE id = ?",
                 (faltante, sobrante, conteo_id))
    return conteo_id


def conteo(conn, conteo_id):
    cabeza = conn.execute("SELECT id, hecho, quien, faltante, sobrante FROM conteos WHERE id = ?",
                          (conteo_id,)).fetchone()
    if cabeza is None:
        return None
    filas = [dict(zip(("id", "nombre", "esperado", "contado", "costo", "loss_id", "aparecio", "grupo"), f))
             for f in conn.execute("""
                SELECT f.product_id, COALESCE(p.name, 'Producto'), f.esperado, f.contado, f.costo,
                       f.loss_id, f.aparecio, p.grupo
                  FROM conteo_filas f LEFT JOIN products p ON p.id = f.product_id
                 WHERE f.conteo_id = ? ORDER BY p.name COLLATE NOCASE""", (conteo_id,)).fetchall()]
    for f in filas:
        f["diferencia"] = round(f["contado"] - f["esperado"], 3)
        f["pendiente"] = max(0.0, -f["diferencia"] - f["aparecio"])     # faltante sin explicar
    datos = dict(zip(("id", "hecho", "quien", "faltante", "sobrante"), cabeza))
    datos["filas"] = filas
    datos["faltan"] = [f for f in filas if f["diferencia"] < 0]
    datos["sobran"] = [f for f in filas if f["diferencia"] > 0]
    datos["cuadran"] = [f for f in filas if f["diferencia"] == 0]
    datos["sin_explicar"] = sum(f["pendiente"] * f["costo"] for f in datos["faltan"])
    return datos


def aparecio(conn, conteo_id, product_id, cantidad):
    """Se supo a quién se le dio parte del faltante (y se anotó la venta):
    esa parte deja de ser pérdida y vuelve al stock, porque la venta ya la
    descuenta."""
    fila = conn.execute("""SELECT esperado, contado, aparecio, loss_id FROM conteo_filas
                            WHERE conteo_id = ? AND product_id = ?""", (conteo_id, product_id)).fetchone()
    if fila is None:
        raise ValueError("Ese producto no está en el conteo")
    esperado, contado, ya, loss_id = fila
    pendiente = esperado - contado - ya
    if not cantidad or cantidad <= 0:
        raise ValueError("Escriba cuántos aparecieron")
    if cantidad > pendiente + 1e-9:
        raise ValueError(f"Solo faltaban {_numero(round(pendiente, 3))}")
    perdida = conn.execute("SELECT quantity, unit_cost FROM losses WHERE id = ?", (loss_id,)).fetchone() \
        if loss_id else None
    if perdida:
        if cantidad >= perdida[0] - 1e-9:
            conn.execute("DELETE FROM losses WHERE id = ?", (loss_id,))
        else:
            conn.execute("UPDATE losses SET quantity = quantity - ?, total_cost = (quantity - ?) * unit_cost "
                         "WHERE id = ?", (cantidad, cantidad, loss_id))
    conn.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (cantidad, product_id))
    conn.execute("UPDATE conteo_filas SET aparecio = aparecio + ? WHERE conteo_id = ? AND product_id = ?",
                 (cantidad, conteo_id, product_id))


def pistas(conn, conteo_id, desde):
    """{product_id: [clientes]}: quién suele llevar cada producto que falta y
    no tiene una venta de él desde `desde`. Primero a quienes se les escribió
    para el domicilio en esos días: lo más probable es que se les haya llevado
    y no se anotó."""
    faltan = [f[0] for f in conn.execute(
        "SELECT product_id FROM conteo_filas WHERE conteo_id = ? AND contado < esperado - aparecio",
        (conteo_id,)).fetchall()]
    if not faltan:
        return {}
    hay_domicilio = conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'domicilio_envios'").fetchone()
    escritos = {f[0] for f in conn.execute(
        "SELECT DISTINCT client_id FROM domicilio_envios WHERE dia >= ?", (desde.isoformat(),))} \
        if hay_domicilio else set()
    hace_90 = (desde - timedelta(days=90)).isoformat()
    resultado = {}
    for pid in faltan:
        candidatos = []
        for cid, nombre, veces, ultima in conn.execute("""
                SELECT s.client_id, c.name, COUNT(DISTINCT s.id), MAX(date(s.created_at))
                  FROM sale_details d JOIN sales s ON s.id = d.sale_id
                  JOIN clients c ON c.id = s.client_id
                 WHERE d.product_id = ? AND date(s.created_at) >= ?
                 GROUP BY s.client_id HAVING COUNT(DISTINCT s.id) >= 2""", (pid, hace_90)).fetchall():
            if ultima >= desde.isoformat():
                continue        # ya tiene una venta de este producto en estos días
            candidatos.append({"id": cid, "nombre": nombre, "veces": veces, "ultima": ultima,
                               "domicilio": cid in escritos})
        candidatos.sort(key=lambda c: (not c["domicilio"], -c["veces"]))
        resultado[pid] = candidatos[:6]
    return resultado


def desde_para_pistas(conn, conteo_id, hoy):
    """Desde el conteo anterior (si fue hace menos de 3 semanas), o hace 7 días."""
    fila = conn.execute("SELECT hecho FROM conteos WHERE id < ? ORDER BY id DESC LIMIT 1",
                        (conteo_id,)).fetchone()
    if fila:
        anterior = date.fromisoformat(fila[0][:10])
        if (hoy - anterior).days <= 21:
            return anterior
    return hoy - timedelta(days=7)


# ── Avisos al celular ────────────────────────────────────────────────────────
def guardar_suscripcion(conn, datos, quien, equipo):
    try:
        sub = json.loads(datos) if isinstance(datos, str) else datos
        endpoint = sub["endpoint"]
        sub["keys"]["p256dh"], sub["keys"]["auth"]
    except (ValueError, KeyError, TypeError):
        raise ValueError("La suscripción no sirve")
    if not str(endpoint).startswith("https://"):
        raise ValueError("La suscripción no sirve")
    conn.execute("""INSERT INTO avisos_suscripciones (endpoint, datos, quien, equipo, creado)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT (endpoint) DO UPDATE SET datos = excluded.datos, quien = excluded.quien,
                                                         equipo = excluded.equipo""",
                 (endpoint, json.dumps(sub), quien, equipo, _ahora()))


def quitar_suscripcion(conn, endpoint):
    conn.execute("DELETE FROM avisos_suscripciones WHERE endpoint = ?", (endpoint,))


def suscripciones(conn):
    return [{"endpoint": f[0], "datos": json.loads(f[1]), "quien": f[2], "equipo": f[3]}
            for f in conn.execute("SELECT endpoint, datos, quien, equipo FROM avisos_suscripciones")]


def ya_enviado(conn, clave):
    return conn.execute("SELECT 1 FROM avisos_enviados WHERE clave = ?", (clave,)).fetchone() is not None


def marcar_enviado(conn, clave):
    conn.execute("INSERT OR IGNORE INTO avisos_enviados (clave, enviado) VALUES (?, ?)", (clave, _ahora()))


def _plural(n, uno, varios):
    return f"{n} {uno if n == 1 else varios}"


def avisos_de_hoy(conn, hoy, momento):
    """Los avisos que tocan hoy, cada uno con una clave para no mandarlo dos
    veces. momento: 'manana' o 'tarde' (la tarea corre dos veces al día)."""
    avisos = []
    hecho = conteo_hecho(conn, hoy)
    dia = hoy.weekday()

    # 1. El conteo: martes y, si se pasó, miércoles
    if dia in (MARTES, MARTES + 1) and not hecho:
        avisos.append({
            "clave": f"conteo:{hoy}:{momento}",
            "titulo": "Hoy toca el conteo" if dia == MARTES else "Quedó pendiente el conteo del martes",
            "cuerpo": "Son 5 minutos: contar lo que hay de verdad. Después sale la lista de lo que hay que pedir.",
            "url": "/conteo"})

    s = None
    # 2. El pedido a Cúcuta: después del conteo, de martes a jueves, si no se ha pedido
    if dia in (MARTES, MARTES + 1, MARTES + 2) and hecho:
        s = sugerencias(conn, hoy)
        c = s["cucuta"]
        if not c["pedido_esta_semana"] and c["por_pedir"] and (c["alcanza_minimo"] or c["urgentes"]):
            n = len(c["por_pedir"])
            cuerpo = f"{_plural(n, 'producto', 'productos')} por unos ${round(c['total']):,}".replace(",", ".")
            cuerpo += f". Llegaría el {dia_corto(c['llega'])}."
            if c["urgentes"]:
                cuerpo += " Se acaban antes: " + ", ".join(i["nombre"] for i in c["urgentes"][:3]) + "."
            avisos.append({"clave": f"cucuta:{hoy}", "titulo": "Hoy hay que pedir a Cúcuta",
                           "cuerpo": cuerpo, "url": "/pedidos#cucuta"})

    # 3. Medellín: que pongan el día del viaje, y el día antes, lo que hay que pedir
    viaje = viaje_medellin(conn, hoy)
    if viaje is None and (dia == MARTES and momento == "tarde" or dia == MARTES + 1 and momento == "manana"):
        avisos.append({"clave": f"viaje:{hoy}:{momento}", "titulo": "¿Qué día bajan a Medellín?",
                       "cuerpo": "Pongan el día del viaje para armar el pedido de masa y charcutería.",
                       "url": "/pedidos#medellin"})
    if viaje is not None and (viaje - hoy).days in (0, 1):
        s = s or sugerencias(conn, hoy)
        m = s["medellin"]
        ya = any(p["llega"] == viaje.isoformat() for p in m["en_camino"])
        if not ya and m["por_pedir"]:
            cuando = "Hoy" if viaje == hoy else "Mañana"
            avisos.append({"clave": f"medellin:{viaje}:{hoy}",
                           "titulo": f"{cuando} bajan a Medellín: hay que hacer el pedido",
                           "cuerpo": f"{_plural(len(m['por_pedir']), 'producto', 'productos')}: "
                                     + ", ".join(i["nombre"] for i in m["por_pedir"][:4]) + ".",
                           "url": "/pedidos#medellin"})

    # 4. El queso: el domingo en la mañana
    if dia == DOMINGO and momento == "manana":
        s = s or sugerencias(conn, hoy)
        q = next((i for i in s["queso"]["items"] if i["pedir"]), None)
        if q:
            avisos.append({"clave": f"queso:{hoy}", "titulo": "Hoy se compra el queso",
                           "cuerpo": f"Unos {_numero(q['pedir'])} kg (quedan {_numero(round(q['stock'], 1))} y "
                                     f"se venden {_numero(round(q['semanal']))} por semana).",
                           "url": "/pedidos#queso"})

    # 5. Pedidos que ya debían haber llegado
    if momento == "manana":
        for p in en_camino(conn):
            if p["llega"] < hoy.isoformat() and p["grupo"] != "queso":
                avisos.append({"clave": f"atraso:{p['id']}:{hoy}",
                               "titulo": f"¿Ya llegó el pedido de {p['nombre_grupo']}?",
                               "cuerpo": "Cuando llegue, regístrelo como compra con un toque.",
                               "url": "/pedidos#en-camino"})
    return avisos
