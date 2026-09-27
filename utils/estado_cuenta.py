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
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from utils.conciliacion import MESES_ES
from utils.pdf import _moneda, _ruta

NEGOCIO = "Charcutería HYE"
PAGO_NEQUI = "Puede pagar por Nequi al 311 875 8761 a nombre de Samir Centeno."
# Notas que se ponen solas al registrar un pago y no le dicen nada al cliente
NOTAS_VACIAS = {"abono", "pago", "pago total", "pago parcial", "abono parcial"}


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
        anulacion = tipo == "debit_reversal"
        if anulacion:
            # Reversión sin cargo que anular: baja la deuda como un abono, pero
            # no es plata que el cliente pagó
            tipo, descripcion = "credit", "Venta anulada"
        monto = float(monto)
        saldo += monto if tipo == "debit" else -monto
        movimientos.append({"tipo": tipo, "monto": monto, "descripcion": descripcion or "",
                            "sale_id": sale_id, "fecha": fecha, "saldo": saldo,
                            "anulacion": anulacion})
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
    io.BytesIO, que usa la página del celular); sin destino, en Informes.

    Es para clientes que no saben de contabilidad y lo leen en el celular:
    primero cuánto debe y cómo pagar, luego la cuenta en tres renglones, de
    qué compras es lo que debe, sus pagos en una lista para comparar con sus
    comprobantes y al final las compras mes por mes, cada una como un recibo
    con su número de venta para buscarla en la aplicación."""
    ruta = destino if destino is not None else _ruta(nombre_archivo(datos))
    doc = SimpleDocTemplate(ruta if hasattr(ruta, "write") else str(ruta), pagesize=A4,
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"Su cuenta - {datos['nombre']}")
    ancho = 180 * mm
    azul, gris = colors.HexColor("#2c3e50"), colors.HexColor("#6b7580")
    verde, rojo, naranja = (colors.HexColor("#1e7e34"), colors.HexColor("#c0392b"),
                            colors.HexColor("#b9770e"))
    fondo_verde, borde = colors.HexColor("#e3f4e8"), colors.HexColor("#bdc3c7")
    normal = ParagraphStyle("normal", parent=getSampleStyleSheet()["Normal"],
                            fontSize=12, leading=16)
    titulo = ParagraphStyle("titulo", parent=normal, fontName="Helvetica-Bold",
                            fontSize=15, leading=19, spaceBefore=4, spaceAfter=6)
    derecha = ParagraphStyle("derecha", parent=normal, alignment=2)
    centro = ParagraphStyle("centro", parent=normal, alignment=1)

    primer_nombre = datos["nombre"].split()[0] if datos["nombre"].split() else ""
    encabezado = Table([[Paragraph(f"<b>{NEGOCIO}</b>", normal),
                         Paragraph(datetime.now().strftime("%d/%m/%Y"), derecha)]],
                       colWidths=[ancho / 2] * 2)
    encabezado.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.8, azul),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    contenido = [encabezado, Spacer(1, 6 * mm),
                 Paragraph(f"Hola, <b>{escape(primer_nombre)}</b>. Este es el resumen "
                           "de su cuenta con nosotros.", normal), Spacer(1, 4 * mm)]

    if not datos["movimientos"] or datos["deuda"] <= 0.5:
        caja = Table([[Paragraph("<b>Su cuenta está al día.</b> ¡Muchas gracias!",
                                 ParagraphStyle("aldia", parent=centro, fontSize=16,
                                                leading=20, textColor=verde))]],
                     colWidths=[ancho])
        caja.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), fondo_verde),
                                  ("TOPPADDING", (0, 0), (-1, -1), 14),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 14)]))
        doc.build(contenido + [caja])
        return ruta

    # Lo primero: cuánto debe y cómo pagarlo
    caja = Table([
        [Paragraph("Usted debe", ParagraphStyle("debe", parent=centro, fontSize=14,
                                                 leading=18, textColor=colors.white))],
        [Paragraph(f"<b>{_moneda(datos['deuda'])}</b>", ParagraphStyle(
            "monto", parent=centro, fontSize=32, leading=38, textColor=colors.white))],
        [Paragraph(PAGO_NEQUI, ParagraphStyle("nequi", parent=centro, fontSize=11.5,
                                              leading=15, textColor=colors.white))],
    ], colWidths=[ancho])
    caja.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), azul),
        ("TOPPADDING", (0, 0), (-1, 0), 12), ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
        ("TOPPADDING", (0, -1), (-1, -1), 8),
    ]))
    contenido += [caja, Spacer(1, 7 * mm)]

    # Si hubo ventas anuladas, lo descontado no fue todo abonos
    anulaciones = any(m.get("anulacion") for m in datos["movimientos"])
    ya = "ya se descontaron" if anulaciones else "ya abonó"
    compras = [m for m in datos["movimientos"] if m["tipo"] == "debit"]
    pagos = [m for m in datos["movimientos"] if m["tipo"] == "credit"]

    def _nombre_compra(m, corta=False):
        if m["sale_id"]:
            return f"Compra del {_fecha(m['fecha'], corta)}"
        return f"{escape(m['descripcion'] or 'Deuda anotada')} ({_fecha(m['fecha'], corta)})"

    # 1. La cuenta en tres renglones: compró, pagó, falta
    abonos = sum(m["monto"] for m in pagos if not m.get("anulacion"))
    anuladas = sum(m["monto"] for m in pagos if m.get("anulacion"))
    n = len(compras)
    filas = [[Paragraph(f"Lo que ha comprado ({n} {'compra' if n == 1 else 'compras'})", normal),
              _moneda(sum(m["monto"] for m in compras))]]
    if abonos:
        filas.append([Paragraph("Lo que ya pagó", normal), "- " + _moneda(abonos)])
    if anuladas:
        filas.append([Paragraph("Ventas anuladas (no se cobran)", normal),
                      "- " + _moneda(anuladas)])
    filas.append([Paragraph("<b>Lo que falta por pagar</b>", normal), _moneda(datos["deuda"])])
    cuenta = Table(filas, colWidths=[ancho - 45 * mm, 45 * mm])
    cuenta.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (1, 0), (1, -1), 12),
        ("FONTNAME", (1, -1), (1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (1, -1), (1, -1), rojo),
        ("LINEABOVE", (0, -1), (-1, -1), 1, azul),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    if datos["en_ceros"]:
        desde = (f"Su cuenta quedó en $0 el <b>{_fecha(datos['en_ceros'])}</b>. "
                 "Aquí está todo lo que ha pasado desde ese día.")
    else:
        desde = "Aquí está todo lo que ha pasado desde su primera compra."
    contenido += [Paragraph("¿De dónde sale esta cuenta?", titulo),
                  Paragraph(desde, normal), Spacer(1, 2 * mm), cuenta, Spacer(1, 7 * mm)]

    # 2. De qué compras es lo que debe hoy (los abonos pagan las más viejas primero)
    pendientes = []
    for m in compras:
        if m["queda"] <= 0.5:
            continue
        if m["abonado"] > 0.5:
            detalle = (f"faltan <b>{_moneda(m['queda'])}</b> "
                       f"<font color='#6b7580'>(era de {_moneda(m['monto'])} y {ya} "
                       f"{_moneda(m['abonado'])})</font>")
        else:
            detalle = f"<b>{_moneda(m['queda'])}</b>"
        pendientes.append([Paragraph(f"• {_nombre_compra(m)}: {detalle}", normal)])
    lista = Table(pendientes, colWidths=[ancho])
    lista.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 2),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    contenido += [Paragraph("Lo que debe hoy es de estas compras", titulo), lista,
                  Spacer(1, 7 * mm)]

    # 3. Sus pagos, en una lista corta para compararla con sus comprobantes
    contenido.append(Paragraph("Sus pagos", titulo))
    if pagos:
        filas = []
        for m in pagos:
            nota = m["descripcion"].strip()
            if m.get("anulacion"):
                texto = "Venta anulada (se descontó)"
            elif "ajuste" in nota.lower():
                texto = "Ajuste a su favor"
            else:
                texto = "Pago recibido"
            if nota and not m.get("anulacion") and nota.lower().rstrip(".") not in NOTAS_VACIAS:
                texto += f"<br/><font size=10.5 color='#4a5560'><i>Nota: {escape(nota)}</i></font>"
            filas.append([_fecha(m["fecha"], True), Paragraph(texto, normal),
                          Paragraph(f"<b>- {_moneda(m['monto'])}</b>", derecha)])
        filas.append(["", Paragraph("<b>Total</b>", normal),
                      Paragraph(f"<b>- {_moneda(abonos + anuladas)}</b>", derecha)])
        t = Table(filas, colWidths=[30 * mm, ancho - 70 * mm, 40 * mm], repeatRows=0)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -2), fondo_verde),
            ("LINEBELOW", (0, 0), (-1, -3), 0.5, colors.white),
            ("LINEABOVE", (0, -1), (-1, -1), 1, azul),
            ("FONTSIZE", (0, 0), (0, -1), 11), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        contenido.append(t)
    else:
        contenido.append(Paragraph("Todavía no ha hecho pagos desde entonces.", normal))
    contenido.append(Spacer(1, 7 * mm))

    # 4. Sus compras mes por mes, cada una como un recibo con su número de venta
    contenido.append(Paragraph("Sus compras, mes por mes", titulo))
    meses = {}
    for m in compras:
        meses.setdefault(str(m["fecha"])[:7], []).append(m)
    for clave, del_mes in meses.items():
        anio, mes = clave.split("-")
        cuantas = len(del_mes)
        barra = Table([[Paragraph(f"<b>{MESES_ES[int(mes) - 1].capitalize()} {anio}</b> "
                                  f"· {cuantas} {'compra' if cuantas == 1 else 'compras'}",
                                  ParagraphStyle("mes", parent=normal, textColor=colors.white)),
                        Paragraph(f"<b>{_moneda(sum(m['monto'] for m in del_mes))}</b>",
                                  ParagraphStyle("mesd", parent=derecha, textColor=colors.white))]],
                      colWidths=[ancho - 40 * mm, 40 * mm])
        barra.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), azul),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        # La barra del mes va pegada a su primera compra, nunca sola al final de una hoja
        cabeza = [Spacer(1, 2 * mm), barra, Spacer(1, 3 * mm)]

        for m in del_mes:
            numero = (f" <font size=10 color='#6b7580'>· Venta #{m['sale_id']}</font>"
                      if m["sale_id"] else "")
            recibo = [[Paragraph(f"<b>{_nombre_compra(m)}</b>{numero}", normal),
                       Paragraph(f"<b>{_moneda(m['monto'])}</b>", derecha)]]
            suma = 0.0
            for cant, producto, precio, subtotal in m["productos"]:
                suma += subtotal
                detalle = f"{_cantidad(cant)} × {escape(producto)}"
                if abs(cant - 1) > 0.001:
                    detalle += f" <font size=9.5 color='#6b7580'>(a {_moneda(precio)} c/u)</font>"
                recibo.append([Paragraph(detalle, normal), Paragraph(_moneda(subtotal), derecha)])
            if m["productos"] and abs(m["monto"] - suma) > 0.5:
                dif = m["monto"] - suma
                recibo.append([Paragraph("Ajuste de precio" if dif > 0 else "Descuento", normal),
                               Paragraph(("+ " if dif > 0 else "- ") + _moneda(abs(dif)), derecha)])

            if m["queda"] <= 0.5:
                estado, color = ("Ya quedó saldada" if anulaciones else "Ya está pagada"), verde
            elif m["abonado"] > 0.5:
                estado = (f"De esta compra {ya} {_moneda(m['abonado'])}. "
                          f"<b>Faltan {_moneda(m['queda'])}</b>")
                color = naranja
            else:
                estado, color = f"<b>Falta pagarla completa: {_moneda(m['queda'])}</b>", rojo
            recibo.append([Paragraph(estado, ParagraphStyle("estado", parent=normal,
                                                             textColor=color)), ""])
            ultima = len(recibo) - 1
            t = Table(recibo, colWidths=[ancho - 40 * mm, 40 * mm])
            t.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.6, borde),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef1f4")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, borde),
                ("LINEABOVE", (0, ultima), (-1, ultima), 0.4, colors.HexColor("#dfe3e6")),
                ("SPAN", (0, ultima), (1, ultima)), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, 0), 7), ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
                ("TOPPADDING", (0, ultima), (-1, ultima), 6),
                ("BOTTOMPADDING", (0, ultima), (-1, ultima), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]))
            contenido += [KeepTogether(cabeza + [t]), Spacer(1, 3 * mm)]
            cabeza = []

    contenido += [Spacer(1, 4 * mm), Paragraph(
        "¡Gracias por su confianza! Cualquier duda con gusto se la aclaramos.",
        ParagraphStyle("gracias", parent=centro, textColor=gris))]

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
