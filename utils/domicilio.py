"""El domicilio de la semana: a quién escribirle para que haga su pedido.

El día del domicilio (casi siempre domingo o lunes) se le manda a cada
cliente un WhatsApp con el enlace al catálogo para que diga qué necesita: el
mensaje dice que los pedidos se entregan hoy. Aquí solo se arma la lista y el mensaje: lo envía quien usa la página,
uno por uno y desde su propio WhatsApp.

Se le escribe a quien compró en los últimos 4 meses (los mismos que mira
perfil_clientes) y tiene teléfono, menos a quien debe mucho o desde hace mucho.
"Desde hace mucho" se cuenta desde la venta sin pagar más vieja, igual que en
Pendientes.

El mensaje que se edita queda guardado hasta que lo cambien; a quién ya se le
envió se anota por día (el día en que se envía). Todo queda en la base, para
que se vea igual desde cualquier celular. Como el resto de servicios, nada aquí hace commit.
"""
import os
from datetime import date

from utils import perfil_clientes

TOPE_DEUDA = 150_000        # debe más de esto: no se le ofrece domicilio
TOPE_DIAS = 21              # o tiene una venta sin pagar de hace más de esto
LARGO_MAXIMO = 1000         # del mensaje: WhatsApp corta los enlaces muy largos


def url_catalogo():
    """La dirección pública del catálogo: CATALOGO_URL o, si no está, la de
    GitHub Pages que sale de CATALOGO_REPO. Vacía si no hay ninguna."""
    url = os.environ.get("CATALOGO_URL", "").strip()
    if url:
        return url
    repo = os.environ.get("CATALOGO_REPO", "").strip()
    if repo.count("/") == 1:
        usuario, nombre = repo.split("/")
        return f"https://{usuario.lower()}.github.io/{nombre}/"
    return ""


def mensaje(url=""):
    """El de siempre. Sin el nombre: muchos están guardados con apodos
    ("cuñada de Emily")."""
    texto = "¡Hola! Hoy en la tarde-noche hacemos domicilios."
    if url:
        texto += f" Mira lo que tenemos y los precios aquí: {url}"
    return texto + " Escríbenos por aquí lo que necesitas y te lo llevamos."


def preparar(conn):
    """Crea las tablas la primera vez."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS domicilio_mensajes (
            dia TEXT PRIMARY KEY,        -- cuándo se guardó, AAAA-MM-DD; vale el último
            mensaje TEXT NOT NULL,
            guardado TEXT NOT NULL)""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS domicilio_envios (
            dia TEXT NOT NULL,
            client_id INTEGER NOT NULL,
            enviado TEXT NOT NULL,       -- cuándo se tocó Enviar
            PRIMARY KEY (dia, client_id))""")


def mensaje_guardado(conn):
    """El último mensaje guardado, o None si se usa el de siempre."""
    fila = conn.execute("SELECT mensaje FROM domicilio_mensajes "
                        "ORDER BY guardado DESC, dia DESC LIMIT 1").fetchone()
    return fila[0] if fila else None


def restaurar_mensaje(conn):
    conn.execute("DELETE FROM domicilio_mensajes")


def guardar_mensaje(conn, dia, texto):
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("El mensaje no puede quedar vacío")
    if len(texto) > LARGO_MAXIMO:
        raise ValueError(f"El mensaje es muy largo (máximo {LARGO_MAXIMO} letras)")
    conn.execute("""
        INSERT INTO domicilio_mensajes (dia, mensaje, guardado)
        VALUES (?, ?, datetime('now', 'localtime'))
        ON CONFLICT (dia) DO UPDATE SET mensaje = excluded.mensaje, guardado = excluded.guardado""",
                 (dia.isoformat(), texto))
    return texto


def enviados(conn, dia):
    """Los clientes a los que ya se les envió para ese día."""
    return {cid for (cid,) in conn.execute(
        "SELECT client_id FROM domicilio_envios WHERE dia = ?", (dia.isoformat(),))}


def marcar_enviado(conn, dia, client_id):
    if conn.execute("SELECT 1 FROM clients WHERE id = ?", (client_id,)).fetchone() is None:
        raise ValueError("El cliente no existe")
    conn.execute("""
        INSERT OR IGNORE INTO domicilio_envios (dia, client_id, enviado)
        VALUES (?, ?, datetime('now', 'localtime'))""", (dia.isoformat(), client_id))


def _deudas(conn, hoy):
    """{cliente: (deuda, días desde la venta sin pagar más vieja o None)}."""
    deudas = {}
    for cid, deuda, desde in conn.execute("""
            SELECT c.id, c.total_debt,
                   (SELECT MIN(date(s.created_at)) FROM sales s
                     WHERE s.client_id = c.id AND s.status = 'pending')
              FROM clients c WHERE c.total_debt > 0"""):
        dias = (hoy - date.fromisoformat(str(desde)[:10])).days if desde else None
        deudas[cid] = (deuda or 0, dias)
    return deudas


def motivo(deuda, dias):
    """Por qué no se le escribe, o None si sí."""
    if deuda > TOPE_DEUDA:
        return "monto"
    if dias is not None and dias > TOPE_DIAS:
        return "dias"
    return None


def clientes(conn, hoy):
    """Los clientes de los últimos 4 meses, del que más compra al que menos,
    repartidos en: a quién escribir, quién debe y quién no tiene teléfono."""
    deudas = _deudas(conn, hoy)
    escribir, deben, sin_telefono = [], [], []
    for p in perfil_clientes.perfiles(conn, hoy):
        deuda, dias = deudas.get(p["id"], (0, None))
        c = {"id": p["id"], "nombre": p["nombre"], "whatsapp": p["whatsapp"],
             "ritmo": p["ritmo"], "dias_sin_venir": p["dias_sin_venir"],
             "deuda": deuda, "dias_debe": dias, "motivo": motivo(deuda, dias)}
        if c["motivo"]:
            deben.append(c)
        elif not c["whatsapp"]:
            sin_telefono.append(c)
        else:
            escribir.append(c)
    deben.sort(key=lambda c: -c["deuda"])
    return escribir, deben, sin_telefono
