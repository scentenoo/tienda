"""Genera el catálogo para clientes: una página estática (HTML) con los
productos, sus precios y si hay o van por encargo, lista para GitHub Pages.

Lo corre solo la tarea de GitHub (.github/workflows/catalogo.yml) cada media
hora. Lee la base con un token de SOLO LECTURA y nada más toca la tabla de
productos y las fechas de compra (ver servicios/catalogo.py).

    python -m catalogo.generar --salida sitio

Variables de entorno:
  TURSO_URL             la base en la nube
  TURSO_TOKEN_LECTURA   token de solo lectura (turso db tokens create <base> --read-only)
  WHATSAPP_NEGOCIO      el número al que llegan los pedidos (10 dígitos)
  CATALOGO_URL          la dirección pública del catálogo (opcional: para la
                        vista previa cuando se comparte el enlace)

Para probarlo en el PC con una copia de la base, sin internet:

    python -m catalogo.generar --db copia.db --whatsapp 3001234567 --salida sitio

Las fotos van en catalogo/fotos/ con el id del producto como nombre
(29.jpg, 42.webp…). Mientras no haya ninguna, las tarjetas salen sin recuadro
de foto; cuando haya algunas, el producto que no tenga sale con su inicial.
"""
import argparse
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from servicios import catalogo as reglas

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
ZONA = ZoneInfo("America/Bogota")
EXTENSIONES_FOTO = (".webp", ".jpg", ".jpeg", ".png")
ETIQUETAS = {"disponible": "Disponible", "pocas": "Últimas unidades", "encargo": "Por encargo"}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def pesos(valor):
    return "$" + f"{round(valor or 0):,.0f}".replace(",", ".")


def numero_whatsapp(texto):
    """Solo dígitos, en formato internacional (Colombia si tiene 10)."""
    digitos = "".join(ch for ch in str(texto or "") if ch.isdigit())
    if len(digitos) == 10:
        digitos = "57" + digitos
    if len(digitos) < 11:
        raise SystemExit("Falta el número de WhatsApp del negocio (WHATSAPP_NEGOCIO o --whatsapp).")
    return digitos


def momento_en_texto(momento):
    """'4 de octubre a las 11:30 a. m.' (la página lo cambia por 'hoy a las…')."""
    hora = momento.hour % 12 or 12
    return (f"{momento.day} de {MESES[momento.month - 1]} "
            f"{'a la' if hora == 1 else 'a las'} {hora}:{momento.minute:02d} "
            f"{'a. m.' if momento.hour < 12 else 'p. m.'}")


def fotos_disponibles(carpeta):
    """{id del producto: nombre del archivo} con las fotos que hay."""
    fotos = {}
    if carpeta.is_dir():
        for archivo in sorted(carpeta.iterdir()):
            if archivo.suffix.lower() in EXTENSIONES_FOTO and archivo.stem.isdigit():
                fotos.setdefault(int(archivo.stem), archivo.name)
    return fotos


def conectar(db=None):
    if db:
        return sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    url, token = os.environ.get("TURSO_URL"), os.environ.get("TURSO_TOKEN_LECTURA")
    if not (url and token):
        raise SystemExit("Faltan TURSO_URL y TURSO_TOKEN_LECTURA (un token de solo lectura: "
                         "turso db tokens create <base> --read-only).")
    from config.nube import conexion_directa
    return conexion_directa(url, token, solo_lectura=True)


def construir(conn, whatsapp, url_publica="", ahora=None, fotos=None):
    """El HTML del catálogo."""
    ahora = ahora or datetime.now(ZONA)
    fotos = fotos or {}
    productos = reglas.productos_visibles(conn, ahora.date())
    if not productos:
        # Mejor dejar publicado el catálogo anterior que uno vacío
        raise SystemExit("No hay ningún producto para mostrar: no se genera el catálogo.")
    for p in productos:
        p["precio_texto"] = pesos(p["precio"])
        p["etiqueta"] = ETIQUETAS[p["estado"]]
        p["inicial"] = p["nombre"].strip()[:1].upper()
        p["foto"] = f"fotos/{fotos[p['id']]}" if p["id"] in fotos else None
    entorno = Environment(loader=FileSystemLoader(AQUI), autoescape=select_autoescape(["html"]),
                          trim_blocks=True, lstrip_blocks=True)
    return entorno.get_template("plantilla.html").render(
        secciones=reglas.secciones(productos), whatsapp=numero_whatsapp(whatsapp),
        hay_fotos=any(p["foto"] for p in productos),
        url_publica=(url_publica or "").rstrip("/"),
        generado_iso=ahora.isoformat(timespec="seconds"), generado_texto=momento_en_texto(ahora))


def generar(salida, conn, whatsapp, url_publica="", ahora=None):
    salida = Path(salida)
    fotos = fotos_disponibles(AQUI / "fotos")
    html = construir(conn, whatsapp, url_publica, ahora, fotos)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "index.html").write_text(html, encoding="utf-8")
    for nombre in ("logo-he.png", "icono-192.png"):
        shutil.copyfile(RAIZ / "web" / "estatico" / nombre, salida / nombre)
    if fotos:
        (salida / "fotos").mkdir(exist_ok=True)
        for nombre in fotos.values():
            shutil.copyfile(AQUI / "fotos" / nombre, salida / "fotos" / nombre)
    return salida / "index.html"


def main():
    opciones = argparse.ArgumentParser(description="Genera el catálogo para clientes.")
    opciones.add_argument("--salida", default="sitio", help="carpeta donde queda la página")
    opciones.add_argument("--db", help="un archivo .db local, en vez de la base en la nube")
    opciones.add_argument("--whatsapp", default=os.environ.get("WHATSAPP_NEGOCIO"))
    opciones.add_argument("--url", default=os.environ.get("CATALOGO_URL", ""))
    args = opciones.parse_args()
    conn = conectar(args.db)
    try:
        print("Catálogo generado en", generar(args.salida, conn, args.whatsapp, args.url))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
