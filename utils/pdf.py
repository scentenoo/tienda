"""Exportación de informes a PDF."""
import sys
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from utils.conciliacion import MANUAL_AJUSTE, MANUAL_INICIO


def _carpeta_documentos() -> Path:
    """Carpeta "Documentos" real del usuario.

    Path.home() / "Documentos" asume que está en la ubicación por defecto,
    pero si el usuario tiene OneDrive sincronizando esa carpeta (algo muy
    común en Windows), la carpeta que se abre desde "Documentos" en el
    Explorador vive en otro lado, y guardar ahí crea una carpeta distinta
    que el usuario nunca ve. En Windows se resuelve con la API de carpetas
    del shell, que sí conoce la ubicación real aunque esté redirigida.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            CSIDL_PERSONAL = 5       # "Mis documentos"
            SHGFP_TYPE_CURRENT = 0   # ruta actual, no la de por defecto
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.shell32.SHGetFolderPathW(
                0, CSIDL_PERSONAL, 0, SHGFP_TYPE_CURRENT, buf)
            if buf.value:
                return Path(buf.value)
        except Exception:
            pass
    return Path.home() / "Documentos"


CARPETA = _carpeta_documentos() / "Informes"


def _ruta(nombre: str) -> Path:
    CARPETA.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y-%m-%d_%H-%M")
    return CARPETA / f"{nombre}_{marca}.pdf"


def _moneda(valor) -> str:
    return f"${valor:,.0f}".replace(",", ".")


def exportar_conciliacion(datos: dict, ocultas=()) -> Path:
    """Genera el PDF del cuadro de conciliación, en horizontal."""
    ruta = _ruta("conciliacion_caja")
    doc = SimpleDocTemplate(str(ruta), pagesize=landscape(A4),
                            leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm)
    estilos = getSampleStyleSheet()

    contenido = [
        Paragraph("Conciliación de Caja", estilos["Title"]),
        Paragraph(datetime.now().strftime("Generado el %d/%m/%Y a las %H:%M"),
                  estilos["Normal"]),
        Spacer(1, 8 * mm),
    ]

    tabla = [["CONCEPTO"] + datos["encabezados"] + ["ACUMULADO"]]
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#bdc3c7")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]

    for tipo, concepto in datos["filas"]:
        if concepto in ocultas:
            continue
        i = len(tabla)
        if tipo == "seccion":
            tabla.append([concepto] + [""] * (len(datos["meses"]) + 1))
            estilo += [("BACKGROUND", (0, i), (-1, i), colors.HexColor("#d6eaf8")),
                       ("FONTNAME", (0, i), (-1, i), "Helvetica-Bold")]
            continue

        fila = datos["valores"][concepto]
        tabla.append([concepto] + [_moneda(v) for v in fila]
                     + [_moneda(datos["acumulado"][concepto])])

        if tipo == "total":
            estilo += [("BACKGROUND", (0, i), (-1, i), colors.HexColor("#eaeded")),
                       ("FONTNAME", (0, i), (-1, i), "Helvetica-Bold")]
        elif tipo == "neto":
            verde = datos["acumulado"][concepto] >= 0
            estilo += [("BACKGROUND", (0, i), (-1, i),
                        colors.HexColor("#d4edda" if verde else "#f8d7da")),
                       ("FONTNAME", (0, i), (-1, i), "Helvetica-Bold")]
        elif concepto in (MANUAL_INICIO, MANUAL_AJUSTE):
            estilo += [("BACKGROUND", (0, i), (-1, i), colors.HexColor("#fff3cd"))]

    ancho_mes = min(28 * mm, (250 * mm) / max(len(datos["meses"]) + 1, 1))
    anchos = [60 * mm] + [ancho_mes] * len(datos["meses"]) + [ancho_mes]
    t = Table(tabla, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle(estilo))
    contenido.append(t)

    doc.build(contenido)
    return ruta


# Mismos umbrales y colores que la pantalla
COLORES_MORA = [(60, "#f8d7da"), (30, "#ffe0b2"), (15, "#fff3cd")]


def _color_mora(dias):
    for limite, color in COLORES_MORA:
        if (dias or 0) >= limite:
            return colors.HexColor(color)
    return None


def exportar_pendientes(filas, total) -> Path:
    """Genera el PDF de la lista de deudores, en el mismo orden y con los
    mismos colores de mora que se ven en pantalla."""
    ruta = _ruta("pendientes")
    doc = SimpleDocTemplate(str(ruta), pagesize=A4,
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm)
    estilos = getSampleStyleSheet()

    contenido = [
        Paragraph("Clientes con deuda pendiente", estilos["Title"]),
        Paragraph(datetime.now().strftime("Generado el %d/%m/%Y a las %H:%M"),
                  estilos["Normal"]),
        Spacer(1, 6 * mm),
    ]

    tabla = [["Cliente", "Deuda", "Debe desde", "Días"]]
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#bdc3c7")),
    ]

    for nombre, deuda, desde, dias in filas:
        i = len(tabla)
        tabla.append([nombre, _moneda(deuda), desde or "", str(dias) if dias is not None else ""])
        color = _color_mora(dias)
        if color is not None:
            estilo.append(("BACKGROUND", (0, i), (-1, i), color))

    i = len(tabla)
    tabla.append(["TOTAL", _moneda(total), "", ""])
    estilo += [("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"),
               ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#eaeded"))]

    t = Table(tabla, colWidths=[75 * mm, 35 * mm, 40 * mm, 20 * mm], repeatRows=1)
    t.setStyle(TableStyle(estilo))
    contenido.append(t)

    contenido.append(Spacer(1, 5 * mm))
    contenido.append(Paragraph(
        "Mora: 15+ días amarillo · 30+ naranja · 60+ rojo", estilos["Normal"]))

    doc.build(contenido)
    return ruta


def exportar_capital(situacion, meses, inventario, ahora=None) -> Path:
    """Informe de capital de trabajo: dónde está el dinero y cuánto se puede girar."""
    ruta = _ruta("capital_de_trabajo")
    doc = SimpleDocTemplate(str(ruta), pagesize=A4,
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm)
    estilos = getSampleStyleSheet()
    contenido = [
        Paragraph("Capital de Trabajo", estilos["Title"]),
        Paragraph(datetime.now().strftime("Generado el %d/%m/%Y a las %H:%M"),
                  estilos["Normal"]),
        Spacer(1, 6 * mm),
    ]

    if ahora:
        contenido.append(Paragraph("¿Cuánto se puede girar ahora?", estilos["Heading2"]))
        tabla = [
            ["Efectivo real (contado y abonos cobrados)", _moneda(ahora["efectivo"])],
            ["(−) Reponer inventario", _moneda(-ahora["reponer_inventario"])],
            ["(−) Colchón de operación", _moneda(-ahora["colchon"])],
            ["DISPONIBLE PARA GIRAR", _moneda(ahora["disponible"])],
            [f"Por cada uno de los {ahora['socios']} socios", _moneda(ahora["por_socio"])],
        ]
        t = Table(tabla, colWidths=[95 * mm, 45 * mm])
        t.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#bdc3c7")),
            ("FONTNAME", (0, 3), (-1, 4), "Helvetica-Bold"),
            ("BACKGROUND", (0, 3), (-1, 4), colors.HexColor(
                "#d4edda" if ahora["disponible"] > 0 else "#f8d7da")),
        ]))
        contenido += [t, Spacer(1, 7 * mm)]

    contenido.append(Paragraph("Dónde está el dinero", estilos["Heading2"]))

    resumen = [
        ["Efectivo libre (de la conciliación)", _moneda(situacion["efectivo_libre"])],
        ["(+) Inventario en bodega", _moneda(situacion["inventario"])],
        ["(+) Fiado por cobrar", _moneda(situacion["cartera"])],
        ["CAPITAL DISPONIBLE", _moneda(situacion["disponible"])],
        ["", ""],
        ["Aportes iniciales", _moneda(situacion["aportes"])],
        ["Utilidad acumulada", _moneda(situacion["utilidad"])],
        ["(−) Giros a socios", _moneda(-situacion["giros"])],
    ]
    t = Table(resumen, colWidths=[95 * mm, 45 * mm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#bdc3c7")),
        ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
        ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#eaeded")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0),
         colors.HexColor("#d4edda" if situacion["efectivo_libre"] >= 0 else "#f8d7da")),
    ]))
    contenido += [t, Spacer(1, 7 * mm),
                  Paragraph("Cuánto se podía girar cada mes", estilos["Heading2"])]

    tabla = [["Mes", "Utilidad", "Se fue a fiado", "Girable", "Girado", "Exceso"]]
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#bdc3c7")),
    ]
    for m in meses:
        i = len(tabla)
        tabla.append([m["mes"], _moneda(m["utilidad"]), _moneda(m["delta_cartera"]),
                      _moneda(m["girable"]), _moneda(m["girado"]),
                      _moneda(m["exceso"]) if m["exceso"] > 0 else "—"])
        if m["exceso"] > 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f8d7da")))
    t = Table(tabla, colWidths=[24 * mm, 26 * mm, 30 * mm, 26 * mm, 26 * mm, 26 * mm],
              repeatRows=1)
    t.setStyle(TableStyle(estilo))
    contenido += [t, Spacer(1, 7 * mm)]

    contenido.append(Paragraph(
        f"Inventario: objetivo {_moneda(inventario['objetivo'])} · "
        f"actual {_moneda(inventario['actual'])} · "
        f"faltan {_moneda(inventario['brecha'])}", estilos["Heading2"]))

    if inventario["faltantes"]:
        tabla = [["Producto", "Stock", "Objetivo", "Faltan"]]
        for f in inventario["faltantes"][:15]:
            tabla.append([f["producto"], f"{f['stock']:.1f}",
                          f"{f['objetivo']:.1f}", _moneda(f["faltan_pesos"])])
        t = Table(tabla, colWidths=[80 * mm, 25 * mm, 25 * mm, 30 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#bdc3c7")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f8f9fa")]),
        ]))
        contenido.append(t)

    contenido += [Spacer(1, 6 * mm), Paragraph(
        "<b>Regla:</b> lo repartible cada mes es la utilidad menos lo que creció "
        "el fiado y el inventario. La utilidad a secas no es efectivo: buena parte "
        "está en la calle o en la bodega.", estilos["Normal"])]

    doc.build(contenido)
    return ruta
