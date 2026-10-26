"""Cobros por WhatsApp (la regla está en utils/cobros.py) y el enlace al
estado de cuenta que va en cada mensaje. Se registran en la misma app de
web/app.py, que las importa al final.

El enlace es la única página de aquí que se abre sin contraseña: lo abre el
cliente. Lleva el número del cliente firmado con SECRETO, así que no se puede
adivinar ni cambiar por el de otro, y vence a los DIAS_ENLACE días. Si se
cambia SECRETO, todos los enlaces enviados dejan de servir."""
import io
from datetime import date

from flask import abort, redirect, render_template, request, send_file, session, url_for
from itsdangerous import BadSignature, URLSafeTimedSerializer

from utils import cobros, estado_cuenta
from web.app import (DESARROLLO, _db_cobros, _dia_largo, _revisar_csrf, app, db, requiere_gastos,
                     requiere_ingreso)

DIAS_ENLACE = 30


def _firmas():
    return URLSafeTimedSerializer(app.secret_key, salt="estado-de-cuenta")


def enlace_estado(client_id):
    base = request.host_url
    if not DESARROLLO:
        base = base.replace("http://", "https://", 1)
    return base.rstrip("/") + url_for("estado_publico", token=_firmas().dumps(client_id))


@app.get("/cobros")
@requiere_ingreso
def cobros_pagina():
    hoy = date.today()
    conn = _db_cobros()
    ajustes = cobros.ajustes(conn)
    toca, cobrados, sin_frecuencia = cobros.clientes(conn, hoy, ajustes["dia_semanal"])
    for c in toca:
        c["mensaje"] = cobros.mensaje(ajustes["mensaje"], c["nombre"], c["deuda"],
                                      enlace_estado(c["id"]), ajustes["cuenta"])
    ejemplo = cobros.parte_fija(toca[0]["deuda"] if toca else 50000, "(enlace a su estado de cuenta)",
                                ajustes["cuenta"], con_saldo="{deuda}" not in ajustes["mensaje"])
    semanal = cobros.inicio_periodo("semanal", hoy, ajustes["dia_semanal"])
    quincenal = cobros.inicio_periodo("quincenal", hoy)
    return render_template(
        "cobros.html", toca=toca, cobrados=cobrados, sin_frecuencia=sin_frecuencia,
        ajustes=ajustes, ejemplo=ejemplo, dias=cobros.DIAS, largo_maximo=cobros.LARGO_MAXIMO,
        desde_semanal=_dia_largo(semanal), desde_quincenal=_dia_largo(quincenal),
        dias_enlace=DIAS_ENLACE, aviso=session.pop("aviso_cobros", None),
        error=session.pop("error_cobros", None))


@app.post("/cobros/frecuencia")
@requiere_ingreso
def cobros_frecuencia():
    _revisar_csrf()
    conn = _db_cobros()
    try:
        cobros.poner_frecuencia(conn, int(request.form.get("client_id", "")), request.form.get("cobro"))
        conn.commit()
    except ValueError:
        abort(400)
    return redirect(url_for("cobros_pagina") + "#sin-frecuencia")


@app.post("/cobros/enviado")
@requiere_ingreso
def cobros_enviado():
    """Lo llama la página al tocar Enviar, sin salir de ella."""
    _revisar_csrf()
    conn = _db_cobros()
    try:
        cobros.marcar_cobrado(conn, int(request.form.get("client_id", "")), date.today(),
                              cobros.ajustes(conn)["dia_semanal"])
        conn.commit()
    except ValueError:
        abort(400)
    return "", 204


@app.post("/cobros/mensaje")
@requiere_ingreso
def cobros_mensaje():
    """La parte de arriba del mensaje: queda guardada hasta que la cambien."""
    _revisar_csrf()
    conn = _db_cobros()
    try:
        cobros.guardar_mensaje(conn, cobros.MENSAJE if request.form.get("restaurar")
                               else request.form.get("mensaje"))
        conn.commit()
        session["aviso_cobros"] = ("Volvió el mensaje de siempre." if request.form.get("restaurar")
                                   else "✓ Mensaje guardado: es el que les llega a todos.")
    except ValueError as e:
        conn.rollback()
        session["error_cobros"] = str(e)
    return redirect(url_for("cobros_pagina"))


@app.route("/cobros/cuenta", methods=["GET", "POST"])
@requiere_ingreso
@requiere_gastos        # el número de cuenta solo lo cambia el dueño
def cobros_cuenta():
    conn = _db_cobros()
    error = None
    if request.method == "POST":
        _revisar_csrf()
        try:
            cobros.guardar_cuenta(conn, request.form.get("cuenta"), request.form.get("dia_semanal"))
            conn.commit()
            session["aviso_cobros"] = "✓ Número de cuenta y día de cobro guardados."
            return redirect(url_for("cobros_pagina"))
        except ValueError as e:
            conn.rollback()
            error = str(e)
    ajustes = cobros.ajustes(conn)
    if request.method == "POST":
        ajustes.update(cuenta=request.form.get("cuenta", ""))
    return render_template("cobros_cuenta.html", ajustes=ajustes, dias=cobros.DIAS, error=error)


@app.get("/cuenta/<token>")
def estado_publico(token):
    """El estado de cuenta que abre el cliente desde el mensaje de cobro."""
    try:
        client_id = _firmas().loads(token, max_age=DIAS_ENLACE * 24 * 3600)
    except BadSignature:
        return render_template("aviso.html", titulo="Este enlace ya no sirve",
                               mensaje="Escríbenos por WhatsApp y te mandamos tu estado de cuenta."), 404
    try:
        datos = estado_cuenta.calcular(db(), client_id)
    except ValueError:
        return render_template("aviso.html", titulo="Estado de cuenta",
                               mensaje="Escríbenos por WhatsApp y te mandamos tu estado de cuenta."), 404
    pdf = io.BytesIO()
    estado_cuenta.exportar_pdf(datos, pdf)
    pdf.seek(0)
    return send_file(pdf, mimetype="application/pdf",
                     download_name=estado_cuenta.nombre_archivo(datos) + ".pdf")
