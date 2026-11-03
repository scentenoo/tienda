"""Manda a los celulares los avisos que tocan hoy (ver utils/reposicion.py).

Lo corre la tarea de GitHub .github/workflows/avisos.yml dos veces al día
(mañana y tarde, hora de Colombia). Cada aviso se manda una sola vez: queda
anotado en la tabla avisos_enviados.

    python -m avisos.enviar            los avisos de ahora
    python -m avisos.enviar --prueba   uno de prueba a todos los celulares
    python -m avisos.enviar --ver      solo dice cuáles tocan, sin mandar nada

Variables de entorno:
  TURSO_URL, TURSO_TOKEN   la base (con permiso de escribir: anota lo enviado
                           y borra los celulares que ya no reciben)
  VAPID_PRIVADA            la clave privada de los avisos (ver avisos/LEEME.md)
  TZ=America/Bogota        para que "hoy" sea el de Colombia
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.nube import conexion_directa  # noqa: E402
from utils import reposicion  # noqa: E402

# Quién manda los avisos, para los servicios de notificaciones del navegador
CONTACTO = "https://github.com/scentenoo/tienda"


def mandar(conn, aviso, clave_privada):
    """Manda un aviso a todos los celulares. Devuelve a cuántos llegó."""
    from pywebpush import WebPushException, webpush
    llegaron = 0
    for sub in reposicion.suscripciones(conn):
        try:
            webpush(subscription_info=sub["datos"], data=json.dumps(aviso, ensure_ascii=False),
                    vapid_private_key=clave_privada,
                    vapid_claims={"sub": CONTACTO},       # uno nuevo cada vez: webpush lo modifica
                    ttl=12 * 3600, timeout=20)
            llegaron += 1
        except WebPushException as e:
            estado = getattr(e.response, "status_code", None)
            if estado in (404, 410):    # el celular desactivó los avisos o borró la página
                reposicion.quitar_suscripcion(conn, sub["endpoint"])
                print(f"  quitado un celular que ya no recibe ({sub['equipo']})")
            else:
                print(f"  no llegó a {sub['equipo']}: {e}")
    return llegaron


def main():
    opciones = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    opciones.add_argument("--prueba", action="store_true")
    opciones.add_argument("--ver", action="store_true")
    args = opciones.parse_args()

    url, token = os.environ.get("TURSO_URL"), os.environ.get("TURSO_TOKEN")
    clave = os.environ.get("VAPID_PRIVADA", "").strip()
    if not (url and token):
        raise SystemExit("Faltan TURSO_URL y TURSO_TOKEN")
    if not clave and not args.ver:
        raise SystemExit("Falta VAPID_PRIVADA (ver avisos/LEEME.md)")

    conn = conexion_directa(url, token)
    reposicion.preparar(conn)
    conn.commit()
    ahora = datetime.now()
    momento = "manana" if ahora.hour < 12 else "tarde"
    if args.prueba:
        avisos = [{"clave": f"prueba:{ahora:%Y-%m-%d %H:%M:%S}", "titulo": "Aviso de prueba",
                   "cuerpo": "Si ve esto, a este celular le llegan los avisos de la Charcutería HYE.",
                   "url": "/avisos"}]
    else:
        avisos = [a for a in reposicion.avisos_de_hoy(conn, ahora.date(), momento)
                  if not reposicion.ya_enviado(conn, a["clave"])]
    print(f"{ahora:%Y-%m-%d %H:%M} ({momento}): {len(avisos)} aviso(s), "
          f"{len(reposicion.suscripciones(conn))} celular(es)")
    for aviso in avisos:
        print(f"- {aviso['titulo']}: {aviso['cuerpo']}")
        if args.ver:
            continue
        llegaron = mandar(conn, aviso, clave)
        print(f"  llegó a {llegaron}")
        if llegaron:
            reposicion.marcar_enviado(conn, aviso["clave"])
        conn.commit()


if __name__ == "__main__":
    main()
