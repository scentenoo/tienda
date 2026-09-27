"""Estado de cuenta de un cliente en PDF, para mandárselo cuando pregunta
"¿y yo de qué te debo?".

Arranca en la última vez que el cliente quedó en ceros y de ahí en adelante
muestra cada compra con sus productos, cada abono y el saldo que va quedando.

Las ventas no guardan cuánto les queda por pagar (remaining_debt no se
mantiene), así que todo sale de client_transactions, que sí cuadra con
clients.total_debt. Los abonos se reparten a las compras más viejas primero,
igual que al registrar un pago.
"""
import os
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from utils.conciliacion import MESES_ES
from utils.pdf import _moneda, _ruta

NEGOCIO = "Charcutería HYE"
PAGO_NEQUI = "Puede pagar por Nequi al 311 875 8761 a nombre de Samir Centeno."


def _fecha(texto, corta=False) -> str:
    f = datetime.strptime(str(texto)[:10], "%Y-%m-%d")
    mes = MESES_ES[f.month - 1]
    return f"{f.day} {mes[:3]} {f.year}" if corta else f"{f.day} de {mes} de {f.year}"


def _cantidad(q) -> str:
    return str(int(q)) if float(q).is_integer() else f"{q:.2f}".rstrip("0").replace(".", ",")


def _productos(conn, sale_id):
    """(cantidad, producto, precio, subtotal) de una venta; si la venta se
    eliminó, se buscan en la copia que queda al eliminarla."""
    filas = conn.execute("""
        SELECT d.quantity, COALESCE(p.name, 'Producto'), d.sale_price, d.subtotal
          FROM sale_details d LEFT JOIN products p ON p.id = d.product_id
         WHERE d.sale_id = ? ORDER BY d.id""", (sale_id,)).fetchall()
    if not filas:
        filas = conn.execute("""
            SELECT quantity, COALESCE(product_name, 'Producto'), sale_price, subtotal
              FROM sale_details_eliminados WHERE sale_id = ? ORDER BY id""",
                             (sale_id,)).fetchall()
    return [tuple(f) for f in filas]


def calcular(conn, client_id) -> dict:
    cliente = conn.execute("SELECT name, total_debt FROM clients WHERE id = ?",
                           (client_id,)).fetchone()
    if cliente is None:
        raise ValueError("No se encontró el cliente")
    nombre, deuda_app = cliente[0], float(cliente[1] or 0)

    filas = conn.execute("""
        SELECT id, transaction_type, amount, description, sale_id, created_at
          FROM client_transactions
         WHERE client_id = ? AND transaction_type IN ('debit', 'credit', 'debit_reversal')
         ORDER BY created_at, id""", (client_id,)).fetchall()

    # Una venta revertida se anuló: ni ella ni su reversión le importan al
    # cliente. Se empareja cada reversión con su cargo; algunos cargos quedaron
    # sin sale_id y solo dicen "Venta fiada #1246" en la descripción.
    anulados = set()
    for f in filas:
        if f[1] != "debit_reversal":
            continue
        pareja = next((g for g in filas if g[1] == "debit" and g[0] not in anulados
                       and f[4] is not None and g[4] == f[4]), None)
        if pareja is None and f[4] is not None:
            pareja = next((g for g in filas if g[1] == "debit" and g[0] not in anulados
                           and g[4] is None and abs(g[2] - f[2]) < 0.5
                           and f"#{f[4]}" in (g[3] or "")), None)
        if pareja is not None:
            anulados.update((f[0], pareja[0]))

    movimientos, saldo, inicio = [], 0.0, 0
    for _id, tipo, monto, descripcion, sale_id, fecha in filas:
        if _id in anulados:
            continue
        if tipo == "debit_reversal":
            # Reversión sin cargo que anular: cuenta como un saldo a favor
            tipo, descripcion = "credit", "Anulación de venta"
        monto = float(monto)
        saldo += monto if tipo == "debit" else -monto
        movimientos.append({"tipo": tipo, "monto": monto, "descripcion": descripcion or "",
                            "sale_id": sale_id, "fecha": fecha, "saldo": saldo})
        if saldo <= 0.5:
            inicio = len(movimientos)   # quedó en ceros: se empieza después de aquí

    en_ceros = movimientos[inicio - 1]["fecha"] if inicio else None
    movimientos = movimientos[inicio:]

    if abs(saldo - deuda_app) > 1 and not (saldo <= 0.5 and deuda_app <= 0.5):
        raise ValueError(
            f"Los movimientos de {nombre} suman {_moneda(saldo)}, pero la deuda "
            f"registrada es {_moneda(deuda_app)}. Revise el historial antes de enviarlo.")

    # Abonos a las compras más viejas primero, para decir cuánto queda de cada una
    abonado = sum(m["monto"] for m in movimientos if m["tipo"] == "credit")
    for m in movimientos:
        if m["tipo"] != "debit":
            continue
        aplicado = min(abonado, m["monto"])
        abonado -= aplicado
        m["abonado"], m["queda"] = aplicado, m["monto"] - aplicado
        m["productos"] = _productos(conn, m["sale_id"]) if m["sale_id"] else []

    return {"nombre": nombre, "deuda": max(saldo, 0.0), "en_ceros": en_ceros,
            "movimientos": movimientos}


def nombre_archivo(datos) -> str:
    return "estado_cuenta_" + "".join(
        c if c.isalnum() else "_" for c in datos["nombre"]).strip("_")


def exportar_pdf(datos, destino=None):
    """Genera el PDF en `destino` (una ruta o un archivo en memoria, como
    io.BytesIO, que usa la página del celular); sin destino, en Informes."""
    ruta = destino if destino is not None else _ruta(nombre_archivo(datos))
    doc = SimpleDocTemplate(ruta if hasattr(ruta, "write") else str(ruta), pagesize=A4,
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"Estado de cuenta - {datos['nombre']}")
    estilos = getSampleStyleSheet()
    normal = estilos["Normal"]
    pequeno = ParagraphStyle("pequeno", parent=normal, fontSize=8.5, leading=11)
    gris = colors.HexColor("#6b7580")

    contenido = [
        Paragraph(NEGOCIO, estilos["Title"]),
        Paragraph("<b>Estado de cuenta</b>", ParagraphStyle(
            "sub", parent=normal, fontSize=13, alignment=1, spaceAfter=8)),
        Table([[f"Cliente: {datos['nombre']}",
                datetime.now().strftime("Fecha: %d/%m/%Y")]],
              colWidths=[120 * mm, 60 * mm],
              style=[("ALIGN", (1, 0), (1, 0), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 10.5)]),
        Spacer(1, 4 * mm),
    ]

    primer_nombre = datos["nombre"].split()[0] if datos["nombre"].split() else ""
    contenido += [Paragraph(f"Hola, {escape(primer_nombre)}. Aquí le compartimos el detalle de su "
                            "cuenta con nosotros.", normal), Spacer(1, 3 * mm)]

    caja = Table([["Saldo pendiente", _moneda(datos["deuda"])]], colWidths=[110 * mm, 70 * mm])
    caja.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 16),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    contenido += [caja, Spacer(1, 3 * mm)]

    if not datos["movimientos"]:
        contenido.append(Paragraph("Su cuenta está al día. ¡Muchas gracias!", normal))
        doc.build(contenido)
        return ruta

    # Lo primero que pregunta el cliente: ¿de qué compras es lo que debo?
    pendientes = []
    for m in datos["movimientos"]:
        if m["tipo"] == "debit" and m["queda"] > 0.5:
            parte = f"compra del {_fecha(m['fecha'], True)}: {_moneda(m['queda'])}"
            if m["abonado"] > 0.5:
                parte += f" (de {_moneda(m['monto'])}, ya abonó {_moneda(m['abonado'])})"
            pendientes.append(parte)
    contenido += [Paragraph("<b>Corresponde a:</b> " + " · ".join(pendientes), normal),
                  Spacer(1, 4 * mm)]

    if datos["en_ceros"]:
        desde = (f"Su cuenta quedó en $0 el {_fecha(datos['en_ceros'])}. "
                 "Desde entonces, estas son sus compras y abonos:")
    else:
        desde = "Estas son sus compras y abonos desde la primera compra:"
    contenido += [Paragraph(desde, normal), Spacer(1, 3 * mm)]

    tabla = [["Fecha", "Detalle", "Cant.", "Precio", "Valor", "Saldo"]]
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#2c3e50")),
    ]

    for m in datos["movimientos"]:
        i = len(tabla)
        if i > 1:
            estilo.append(("LINEABOVE", (0, i), (-1, i), 0.4, colors.HexColor("#bdc3c7")))

        if m["tipo"] == "credit":
            texto = "Ajuste a su favor" if "ajuste" in m["descripcion"].lower() else "Abono"
            tabla.append([_fecha(m["fecha"], True), texto, "", "",
                          "-" + _moneda(m["monto"]), _moneda(m["saldo"])])
            estilo += [("BACKGROUND", (0, i), (-1, i), colors.HexColor("#d4edda")),
                       ("FONTNAME", (0, i), (-1, i), "Helvetica-Bold")]
            continue

        titulo = "Compra" if m["sale_id"] else (m["descripcion"] or "Cargo")
        tabla.append([_fecha(m["fecha"], True), titulo, "", "",
                      _moneda(m["monto"]), _moneda(m["saldo"])])
        estilo.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))

        suma = 0.0
        for cant, producto, precio, subtotal in m["productos"]:
            suma += subtotal
            tabla.append(["", Paragraph(escape(producto), pequeno), _cantidad(cant),
                          _moneda(precio), _moneda(subtotal), ""])
        if m["productos"] and abs(m["monto"] - suma) > 0.5:
            dif = m["monto"] - suma
            tabla.append(["", "Ajuste de precio", "", "",
                          ("+" if dif > 0 else "-") + _moneda(abs(dif)), ""])

        if m["queda"] <= 0.5:
            estado = "Ya quedó pagada con sus abonos"
        elif m["abonado"] > 0.5:
            estado = (f"De esta compra ya abonó {_moneda(m['abonado'])}; "
                      f"quedan {_moneda(m['queda'])} pendientes")
        else:
            estado = "Pendiente por pagar"
        j = len(tabla)
        tabla.append(["", estado, "", "", "", ""])
        estilo += [("SPAN", (1, j), (5, j)), ("TEXTCOLOR", (1, j), (1, j), gris),
                   ("FONTNAME", (1, j), (1, j), "Helvetica-Oblique")]

    t = Table(tabla, colWidths=[22 * mm, 68 * mm, 14 * mm, 25 * mm, 26 * mm, 25 * mm],
              repeatRows=1)
    t.setStyle(TableStyle(estilo))
    contenido += [t, Spacer(1, 5 * mm)]

    compras = sum(m["monto"] for m in datos["movimientos"] if m["tipo"] == "debit")
    abonos = sum(m["monto"] for m in datos["movimientos"] if m["tipo"] == "credit")
    resumen = Table([
        ["Total de compras", _moneda(compras)],
        ["(-) Total abonado", "-" + _moneda(abonos)],
        ["Saldo pendiente", _moneda(datos["deuda"])],
    ], colWidths=[50 * mm, 35 * mm], hAlign="RIGHT")
    resumen.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("LINEABOVE", (0, 2), (-1, 2), 0.8, colors.black),
    ]))
    contenido += [resumen, Spacer(1, 6 * mm)]

    pago = Table([[Paragraph(f"<b>{PAGO_NEQUI}</b>", normal)]], colWidths=[180 * mm])
    pago.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f3e8ff")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#7b2cbf")),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    contenido += [pago, Spacer(1, 5 * mm), Paragraph(
        "¡Gracias por su confianza! Cualquier duda con gusto se la aclaramos.",
        ParagraphStyle("gracias", parent=normal, alignment=1, textColor=gris))]

    doc.build(contenido)
    return ruta


def generar_y_abrir(client_id):
    """Botón "Estado de cuenta": genera el PDF y lo abre para mandarlo."""
    from tkinter import messagebox
    from config.database import get_connection
    try:
        conn = get_connection()
        try:
            datos = calcular(conn, client_id)
        finally:
            conn.close()
        ruta = exportar_pdf(datos)
    except Exception as e:
        messagebox.showerror("Estado de cuenta", f"No se pudo generar:\n{e}")
        return
    if hasattr(os, "startfile"):
        os.startfile(ruta)
    else:
        messagebox.showinfo("Estado de cuenta", f"Guardado en:\n{ruta}")
