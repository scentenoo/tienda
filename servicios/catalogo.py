"""Catálogo para clientes: qué productos se muestran y cómo.

Cada producto tiene dos datos para el catálogo (columnas de products):
  categoria   en qué sección sale (ver CATEGORIAS); vacío = "Otros"
  catalogo    'auto', 'siempre' o 'nunca' (ver MODOS); vacío = 'auto'

La regla de 'auto': aparece si hay stock; agotado, sale como "Por encargo"
mientras se haya comprado en los últimos MESES_SIN_COMPRA meses; después se
oculta solo.

Aquí solo se lee. Lo que sale de productos_visibles() es lo único que ve el
cliente: ni el costo, ni la cantidad en stock, ni nada de otras tablas.
"""
from datetime import date

# En el orden en que salen en el catálogo. La clave es lo que se guarda en la
# base: si se cambia un nombre visible, la clave se deja igual.
CATEGORIAS = [
    ("quesos", "Quesos y lácteos"),
    ("charcuteria", "Charcutería"),
    ("salsas", "Salsas y untables"),
    ("despensa", "Despensa"),
    ("bebidas", "Bebidas"),
    ("dulces", "Galletas y dulces"),
    ("licores", "Licores"),
    ("otros", "Otros"),
]
CATEGORIA_POR_DEFECTO = "otros"
# La publicidad de licor debe llevar esta leyenda (Ley 124 de 1994 y Ley 30 de 1986)
CATEGORIAS_CON_LEYENDA_DE_LICOR = {"licores"}

MODOS = [
    ("auto", "Automático",
     "Aparece si hay stock. Si se agota, sale como «Por encargo». Si pasa más de "
     "2 meses agotado y sin comprarse, se oculta solo."),
    ("siempre", "Siempre",
     "Aparece aunque lleve mucho tiempo agotado. Para lo que solo se trae bajo pedido."),
    ("nunca", "Nunca",
     "No aparece aunque haya stock. Para lo que no se le ofrece al público, como «Ajuste»."),
]
MODO_POR_DEFECTO = "auto"

MESES_SIN_COMPRA = 2      # agotado y sin comprarse en este tiempo: se oculta
POCAS_UNIDADES = 5        # con este stock o menos: "Últimas unidades"
# Los que se venden por kilo y también por medio kilo (por id: 29 es el
# Queso Costeño). En el catálogo se piden de medio en medio kilo.
POR_MEDIO_KILO = {29}

_CLAVES_CATEGORIA = {clave for clave, _ in CATEGORIAS}
_CLAVES_MODO = {clave for clave, _, _ in MODOS}


def normalizar_categoria(valor):
    valor = (valor or "").strip().lower()
    return valor if valor in _CLAVES_CATEGORIA else CATEGORIA_POR_DEFECTO


def normalizar_modo(valor):
    valor = (valor or "").strip().lower()
    return valor if valor in _CLAVES_MODO else MODO_POR_DEFECTO


def tiene_columnas(conn):
    """¿La base ya tiene las columnas del catálogo? Mientras no (antes de
    correr herramientas/preparar_catalogo.py o de abrir el programa del PC
    actualizado), todo lo demás sigue funcionando como antes."""
    try:
        conn.execute("SELECT categoria, catalogo FROM products LIMIT 0")
        return True
    except Exception:
        return False


def opciones_del_producto(conn, product_id):
    """La categoría y el modo de un producto, ya normalizados; None si la
    base todavía no tiene las columnas."""
    if not tiene_columnas(conn):
        return None
    fila = conn.execute("SELECT categoria, catalogo FROM products WHERE id = ?",
                        (product_id,)).fetchone()
    if fila is None:
        return None
    return {"categoria": normalizar_categoria(fila[0]), "catalogo": normalizar_modo(fila[1])}


def estado_del_producto(stock):
    if stock is None or stock <= 0:
        return "encargo"
    return "pocas" if stock <= POCAS_UNIDADES else "disponible"


def productos_visibles(conn, hoy=None):
    """Los productos del catálogo, en orden alfabético: dicts con id, nombre,
    precio, categoria (clave), estado ('disponible', 'pocas' o 'encargo') y
    medio_kilo (si también se vende por medio kilo)."""
    hoy = (hoy or date.today()).isoformat()
    filas = conn.execute(f"""
        SELECT p.id, p.name, p.price, p.stock, p.categoria
          FROM products p
         WHERE p.price > 0
           AND COALESCE(p.catalogo, 'auto') <> 'nunca'
           AND (p.stock > 0
                OR p.catalogo = 'siempre'
                OR EXISTS (SELECT 1 FROM purchase_details pd
                             JOIN purchases pu ON pu.id = pd.purchase_id
                            WHERE pd.product_id = p.id
                              AND date(pu.date) >= date(?, '-{int(MESES_SIN_COMPRA)} months')))
         ORDER BY p.name COLLATE NOCASE""", (hoy,)).fetchall()
    return [{"id": f[0], "nombre": f[1], "precio": round(f[2] or 0),
             "categoria": normalizar_categoria(f[4]), "estado": estado_del_producto(f[3]),
             "medio_kilo": f[0] in POR_MEDIO_KILO}
            for f in filas]


def secciones(productos):
    """Agrupa los productos por categoría, en el orden de CATEGORIAS. Dentro
    de cada una, primero lo que hay y al final lo que va por encargo."""
    resultado = []
    for clave, nombre in CATEGORIAS:
        suyos = [p for p in productos if p["categoria"] == clave]
        if not suyos:
            continue
        suyos.sort(key=lambda p: p["estado"] == "encargo")      # estable: conserva el alfabético
        resultado.append({"clave": clave, "nombre": nombre, "productos": suyos,
                          "leyenda_licor": clave in CATEGORIAS_CON_LEYENDA_DE_LICOR})
    return resultado
