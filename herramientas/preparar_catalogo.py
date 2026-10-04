"""Preparar la base para el catálogo de clientes (se corre una sola vez).

Agrega a products las columnas categoria y catalogo, y le pone categoría a
los productos que ya existen (la lista de abajo). No toca nombres, precios
ni stock, ni ninguna otra tabla.

Primero se mira lo que haría, sin cambiar nada:

    python herramientas/preparar_catalogo.py dist/CharcuteriaHYE/data/nube.json

Y si está bien, se aplica:

    python herramientas/preparar_catalogo.py dist/CharcuteriaHYE/data/nube.json --aplicar

En vez de nube.json se puede pasar un archivo .db (una copia, para probar).
Se puede repetir sin problema: solo llena los productos que no tienen
categoría, y nunca cambia una que ya se haya puesto a mano.
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from servicios.catalogo import CATEGORIAS, tiene_columnas  # noqa: E402

# Los productos de octubre de 2026. Los que no estén aquí quedan sin
# categoría (salen en "Otros") hasta que se les ponga en el formulario.
PRODUCTOS = {
    "quesos": ["Queso Costeño 1k", "Queso De Año", "Bandeja De Queso Amarrillo", "Riquesa",
               "Riquesa pote", "Nata", "Suero", "Yogurt", "Mantequilla 1 kilo", "Mantequilla Mavesa"],
    "charcuteria": ["Bandeja de jamon", "Chuleta Ahumada 500gr aprox", "Huesos Ahumados 500gr aprox",
                    "Mortadela Tapara", "Mortadela Vnzla 1k", "Salchichon Bremen"],
    "salsas": ["Mayonesa Mavesa", "Salsa 57", "Salsa China Grande", "Salsa China Pequeña",
               "Salsa de Tomate", "Salsa Friz", "Salsa friz sobre", "Diablito Grande", "Pepitona", "Adobo"],
    "despensa": ["Masa Facil", "Harina de trigo", "Crema De Arroz 900gr", "Fororo", "Cerelac 400gr",
                 "Cerelac Kilo", "Leche en polvo", "Leche Condensada"],
    "bebidas": ["Malta 1.5", "Frescolita", "Frescolita 2L", "Chicha 500gr", "Chicha litro",
                "Chicha Medio litro", "Rikachicha", "Toddy", "Ovomaltina", "Chocomalt"],
    "dulces": ["Samba", "Pirulin", "Sobre de Pirulin", "Savoy Chocolate", "Cri-Cri", "Toronto",
               "Caja Toronto", "Galk", "Palitos de Chocolate", "Caja de Palitos de Chocolate",
               "Galleta Maria", "Galleta Dani", "Galletas de Guayaba", "Marilu", "Raketi", "Tip-Top"],
    "licores": ["Anis", "Cacique", "Cinco Estrellas", "Ron Superior", "Santa Teresa", "Ponche Crema",
                "Caroreña Sangria", "Cerveza Light", "Cerveza Pilsen", "Bajo Cero"],
    "otros": ["Chimu Amarillo", "Jarabe Berro", "Jarabe Parilla", "Wampol", "Cool-A-Ped", "Colonias",
              "compacto"],
}
# No son productos para el público: nunca salen en el catálogo
NUNCA = ["Ajuste"]

COLUMNAS = [("categoria", "TEXT"), ("catalogo", "TEXT DEFAULT 'auto'")]


def _conectar(origen: Path):
    if origen.suffix == ".json":
        from config.nube import conexion_directa
        credenciales = json.loads(origen.read_text(encoding="utf-8"))
        return conexion_directa(credenciales["url"], credenciales["token"])
    if not origen.exists():
        raise SystemExit(f"No existe {origen}")
    return sqlite3.connect(origen)


def _clave(nombre):
    return (nombre or "").strip().lower()


def preparar(conn, aplicar):
    """Devuelve las líneas del informe. Solo escribe si aplicar es True."""
    informe = []
    categoria_de = {_clave(n): cat for cat, nombres in PRODUCTOS.items() for n in nombres}
    nunca = {_clave(n) for n in NUNCA}
    nombre_categoria = dict(CATEGORIAS)

    listas = tiene_columnas(conn)
    if listas:
        informe.append("Las columnas categoria y catalogo ya existen.")
    else:
        informe.append("Se agregan a products las columnas categoria y catalogo.")
        if aplicar:
            for columna, definicion in COLUMNAS:
                try:
                    conn.execute(f"ALTER TABLE products ADD COLUMN {columna} {definicion}")
                except sqlite3.OperationalError:
                    pass    # esa ya estaba

    con_columnas = listas or aplicar
    sql = ("SELECT id, name, categoria, catalogo FROM products ORDER BY name COLLATE NOCASE"
           if con_columnas else
           "SELECT id, name, NULL, NULL FROM products ORDER BY name COLLATE NOCASE")
    sin_categoria, puestas = [], 0
    for product_id, nombre, categoria, catalogo in [tuple(f) for f in conn.execute(sql).fetchall()]:
        clave = _clave(nombre)
        if clave in nunca:
            if (catalogo or "auto") != "nunca":
                informe.append(f"  {nombre}: no sale en el catálogo (nunca)")
                if aplicar:
                    conn.execute("UPDATE products SET catalogo = 'nunca' WHERE id = ?", (product_id,))
            continue
        if (categoria or "").strip():
            continue                    # ya tiene: no se le cambia
        nueva = categoria_de.get(clave)
        if nueva is None:
            sin_categoria.append(nombre)
            continue
        puestas += 1
        informe.append(f"  {nombre}: {nombre_categoria[nueva]}")
        if aplicar:
            conn.execute("UPDATE products SET categoria = ? WHERE id = ?", (nueva, product_id))

    if aplicar:
        conn.commit()
    informe.append(f"{puestas} producto(s) {'quedaron' if aplicar else 'quedarían'} con categoría.")
    if sin_categoria:
        informe.append("Sin categoría (salen en «Otros» hasta que se les ponga en el formulario): "
                       + ", ".join(sin_categoria))
    if not aplicar:
        informe.append("No se cambió nada. Para aplicarlo, repita la orden con --aplicar al final.")
    return informe


def main(argumentos):
    aplicar = "--aplicar" in argumentos
    rutas = [a for a in argumentos if not a.startswith("--")]
    if len(rutas) != 1:
        raise SystemExit(__doc__)
    conn = _conectar(Path(rutas[0]))
    try:
        print("\n".join(preparar(conn, aplicar)))
    finally:
        conn.close()


if __name__ == "__main__":
    main(sys.argv[1:])
