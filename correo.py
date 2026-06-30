"""
Alerta diaria de stock - Charcuteria HYE
==========================================

Que hace:
  Revisa la base de datos de la tienda, calcula cuantos dias de stock
  le quedan a cada producto segun su velocidad de venta de los ultimos
  30 dias, y te manda un correo con lo que hay que reponer HOY.

Como usarlo:
  1. Llena la seccion CONFIGURACION mas abajo (rutas y datos de correo).
  2. Pruebalo a mano una vez: python stock_alert.py
  3. Si llega el correo bien, prográmalo para que corra solo cada
     mañana con el Programador de Tareas de Windows (instrucciones
     al final de este archivo, en el bloque de comentarios).

IMPORTANTE - seguridad:
  Este archivo va a tener la clave de aplicacion de tu correo.
  NO lo subas a GitHub. Si tu proyecto tienda ya esta en GitHub,
  agrega "stock_alert.py" o el nombre que le pongas a tu .gitignore,
  o mejor aun, mueve EMAIL_PASSWORD a una variable de entorno.
"""

import sqlite3
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ======================= CONFIGURACION =======================

# Ruta a tu base de datos real (la del proyecto tienda en tu PC)
DB_PATH = r"C:\Users\samir\Documents\GitHub\tienda\data\tienda.db"

# Cuenta de Gmail desde la que se va a enviar el correo
EMAIL_FROM = "centenosamir8@gmail.com"
EMAIL_PASSWORD = "lujw dyfv nvyr aqwc"  # NO tu clave normal de Gmail

# A donde llega la alerta (puede ser el mismo correo)
EMAIL_TO = "centenosamir8@gmail.com"

# Que tan adelante calcular el pedido sugerido (en dias de cobertura)
DIAS_COBERTURA_PEDIDO = 14

# Umbral de dias restantes para considerar "urgente"
UMBRAL_DIAS_URGENTE = 3

# ===============================================================


def calcular_alertas(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT MAX(created_at) FROM sales")
    max_date_row = cur.fetchone()[0]
    if not max_date_row:
        conn.close()
        return [], []

    fecha_ref = datetime.strptime(max_date_row[:10], "%Y-%m-%d")
    cutoff = (fecha_ref - timedelta(days=30)).strftime("%Y-%m-%d")

    cur.execute(
        """
        SELECT p.id, p.name, p.stock,
               COALESCE(SUM(sd.quantity), 0) AS unidades_30d
        FROM products p
        LEFT JOIN sale_details sd ON sd.product_id = p.id
        LEFT JOIN sales s ON s.id = sd.sale_id AND date(s.created_at) >= ?
        GROUP BY p.id
        """,
        (cutoff,),
    )
    rows = cur.fetchall()
    conn.close()

    urgentes = []   # tienen demanda activa y se van a quedar sin stock
    sin_movimiento = []  # estan en cero pero no se han vendido en 30 dias

    for pid, name, stock, unidades_30d in rows:
        avg_diario = unidades_30d / 30.0

        if avg_diario > 0:
            dias_restantes = stock / avg_diario if stock > 0 else 0
        else:
            dias_restantes = None

        es_critico = stock <= 0 or (
            dias_restantes is not None and dias_restantes < UMBRAL_DIAS_URGENTE
        )

        if not es_critico:
            continue

        cantidad_sugerida = max(1, round(avg_diario * DIAS_COBERTURA_PEDIDO))

        if avg_diario >= 0.1:
            urgentes.append(
                {
                    "nombre": name,
                    "stock": stock,
                    "venta_diaria": round(avg_diario, 1),
                    "dias_restantes": round(dias_restantes, 1)
                    if dias_restantes is not None
                    else 0,
                    "cantidad_sugerida": cantidad_sugerida,
                }
            )
        elif stock <= 0:
            sin_movimiento.append(name)

    urgentes.sort(key=lambda x: x["dias_restantes"])
    return urgentes, sin_movimiento


def construir_mensaje(urgentes, sin_movimiento):
    hoy = datetime.now().strftime("%d/%m/%Y")
    lineas = [f"Alerta de stock - {hoy}", ""]

    if not urgentes and not sin_movimiento:
        lineas.append("Todo el stock esta en buen nivel. No hay nada que pedir hoy.")
        return "\n".join(lineas)

    if urgentes:
        lineas.append("PEDIR HOY (tienen venta activa y se estan agotando):")
        lineas.append("-" * 55)
        for item in urgentes:
            lineas.append(
                f"- {item['nombre']}: quedan {item['stock']} u. "
                f"(se vende ~{item['venta_diaria']}/dia, "
                f"alcanza para {item['dias_restantes']} dias) "
                f"-> pedir aprox. {item['cantidad_sugerida']} u."
            )
        lineas.append("")

    if sin_movimiento:
        lineas.append("EN CERO PERO SIN VENTAS EN 30 DIAS (revisar si reponer o descontinuar):")
        lineas.append("-" * 55)
        for nombre in sin_movimiento:
            lineas.append(f"- {nombre}")

    return "\n".join(lineas)


def construir_mensaje_html(urgentes, sin_movimiento):
    hoy = datetime.now().strftime("%d/%m/%Y")

    if not urgentes and not sin_movimiento:
        return f"""
        <html>
        <head><meta charset="utf-8"></head>
        <body style="font-family: Arial, sans-serif;">
        <h2>Alerta de stock - {hoy}</h2>
        <p style="color: #2e7d32;">✅ Todo el stock esta en buen nivel. No hay nada que pedir hoy.</p>
        </body></html>
        """

    filas_urgentes = ""
    for item in urgentes:
        dias = item["dias_restantes"]
        if dias == 0:
            color = "#c62828"   # rojo - ya se acabo
            etiqueta = "AGOTADO"
        elif dias < 1:
            color = "#d84315"  # rojo-naranja - se acaba hoy/mañana
            etiqueta = f"{dias} dias"
        elif dias < 2:
            color = "#ef6c00"  # naranja
            etiqueta = f"{dias} dias"
        else:
            color = "#f9a825"  # amarillo
            etiqueta = f"{dias} dias"

        filas_urgentes += f"""
        <tr>
            <td style="padding:8px; border-bottom:1px solid #eee;"><b>{item['nombre']}</b></td>
            <td style="padding:8px; border-bottom:1px solid #eee; text-align:center;">{item['stock']} u.</td>
            <td style="padding:8px; border-bottom:1px solid #eee; text-align:center;">~{item['venta_diaria']}/dia</td>
            <td style="padding:8px; border-bottom:1px solid #eee; text-align:center; color:{color}; font-weight:bold;">{etiqueta}</td>
            <td style="padding:8px; border-bottom:1px solid #eee; text-align:center;"><b>{item['cantidad_sugerida']} u.</b></td>
        </tr>
        """

    tabla_urgentes = ""
    if urgentes:
        tabla_urgentes = f"""
        <h3 style="color:#c62828;">⚠ Pedir hoy ({len(urgentes)})</h3>
        <table style="width:100%; border-collapse:collapse; font-size:14px;">
            <tr style="background:#fafafa; text-align:center;">
                <th style="padding:8px; text-align:left;">Producto</th>
                <th style="padding:8px;">Stock</th>
                <th style="padding:8px;">Venta diaria</th>
                <th style="padding:8px;">Alcanza para</th>
                <th style="padding:8px;">Pedir aprox.</th>
            </tr>
            {filas_urgentes}
        </table>
        """

    lista_sin_mov = ""
    if sin_movimiento:
        items_html = "".join(f"<li>{n}</li>" for n in sin_movimiento)
        lista_sin_mov = f"""
        <h3 style="color:#757575; margin-top:24px;">En cero, sin ventas en 30 dias ({len(sin_movimiento)})</h3>
        <p style="color:#757575; font-size:13px;">Revisar si reponer o descontinuar:</p>
        <ul style="color:#616161; font-size:14px;">{items_html}</ul>
        """

    return f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; color:#212121;">
    <h2>Alerta de stock - {hoy}</h2>
    {tabla_urgentes}
    {lista_sin_mov}
    </body></html>
    """


def enviar_correo(cuerpo_texto, cuerpo_html, asunto):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    msg.attach(MIMEText(cuerpo_texto, "plain", _charset="utf-8"))
    msg.attach(MIMEText(cuerpo_html, "html", _charset="utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.send_message(msg)


def main():
    urgentes, sin_movimiento = calcular_alertas(DB_PATH)
    cuerpo_texto = construir_mensaje(urgentes, sin_movimiento)
    cuerpo_html = construir_mensaje_html(urgentes, sin_movimiento)
    print(cuerpo_texto)  # queda en el log si lo corres por tarea programada

    total_alertas = len(urgentes) + len(sin_movimiento)
    asunto = (
        f"Stock OK - revision del dia"
        if total_alertas == 0
        else f"⚠ {len(urgentes)} producto(s) urgentes para pedir hoy"
    )
    enviar_correo(cuerpo_texto, cuerpo_html, asunto)


if __name__ == "__main__":
    main()


# ===================================================================
# PROGRAMAR PARA QUE CORRA SOLO CADA MAÑANA (Windows Task Scheduler)
# ===================================================================
#
# 1. Abre "Programador de tareas" (busca "Task Scheduler" en el menu
#    de inicio de Windows).
#
# 2. Click en "Crear tarea basica..." (Create Basic Task).
#
# 3. Nombre: "Alerta de stock tienda". Siguiente.
#
# 4. Desencadenador: "Diariamente" (Daily). Elige la hora en que
#    quieres recibir el correo, por ejemplo 7:00 AM. Siguiente.
#
# 5. Accion: "Iniciar un programa" (Start a program). Siguiente.
#
# 6. En "Programa o script" pon la ruta completa a tu python.exe,
#    por ejemplo:
#       C:\Users\samir\AppData\Local\Programs\Python\Python311\python.exe
#    (puedes confirmar la ruta corriendo "where python" en una
#    terminal de Windows).
#
# 7. En "Agregar argumentos" pon la ruta completa a este archivo:
#       C:\Users\samir\Documents\GitHub\tienda\stock_alert.py
#
# 8. Termina el asistente. Click derecho sobre la tarea creada ->
#    "Ejecutar" para probarla una vez sin esperar a mañana.
#
# ===================================================================