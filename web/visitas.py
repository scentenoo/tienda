"""Visitas al catálogo: quién entró, qué buscó, qué agregó y si envió el
pedido (la cuenta está en utils/visitas_catalogo.py; cómo se anota, en
visitas/LEEME.md). Se registra en la misma app de web/app.py, que la importa
al final.

Lee la base de visitas, que es aparte de la de la tienda:
  VISITAS_TURSO_URL     libsql://visitas-<usuario>.turso.io
  VISITAS_TURSO_TOKEN   un token de SOLO LECTURA de esa base
Sin ellas, la página explica qué falta."""
import os

from flask import render_template, request

from config.nube import conexion_directa
from utils import visitas_catalogo
from web.app import app, db, requiere_ingreso

PERIODOS = {1: "Hoy", 7: "7 días", 30: "30 días"}


def _base_visitas():
    url, token = os.environ.get("VISITAS_TURSO_URL"), os.environ.get("VISITAS_TURSO_TOKEN")
    if not (url and token):
        return None
    return conexion_directa(url, token, solo_lectura=True)


@app.get("/catalogo/visitas")
@requiere_ingreso
def visitas_catalogo_pagina():
    dias = request.args.get("dias", type=int)
    dias = dias if dias in PERIODOS else 7
    conn = _base_visitas()
    if conn is None:
        return render_template("visitas.html", falta_configurar=True, periodos=PERIODOS, dias=dias)
    try:
        try:
            lista = visitas_catalogo.eventos(conn, visitas_catalogo.desde_hace(dias))
        except Exception as e:
            # Si nadie ha entrado todavía, la tabla ni existe: el recibidor la crea con la primera visita
            if "no such table" not in str(e).lower():
                raise
            lista = []
    finally:
        conn.close()
    clientes = visitas_catalogo.nombres_por_codigo(db(), app.secret_key)
    return render_template("visitas.html", falta_configurar=False, periodos=PERIODOS, dias=dias,
                           r=visitas_catalogo.resumen(lista, clientes))
