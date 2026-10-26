"""Cobros por WhatsApp a los clientes que deben, cada semana o cada quincena.

A cada cliente se le marca cómo paga: semanal o quincenal. Le toca cobro una
vez por periodo:
  semanal    desde el día de cobro de la semana (sábado, se puede cambiar)
  quincenal  desde el 15 y desde el último día del mes
Si no se le envió ese día, sigue saliendo hasta que se le envíe o empiece el
periodo siguiente. Quien debe y no tiene frecuencia sale aparte, para marcarlo.

Cada mensaje tiene dos partes: la de arriba la escriben ellos (se cambia
cuando quieran y queda guardada); la de abajo la pone la página y no se edita:
el saldo, el enlace al estado de cuenta y el número de cuenta, que se pone en
otra pantalla. Lo envía quien usa la página, desde su WhatsApp.
Lo que se cobró, el número de cuenta y el mensaje quedan en la base. Como el
resto de servicios, nada aquí hace commit.
"""
import calendar
from datetime import timedelta

FRECUENCIAS = {"semanal": "Semanal", "quincenal": "Quincenal"}
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
DIA_SEMANAL = 5             # sábado
LARGO_MAXIMO = 1000

# La parte que se edita. Sin el nombre: muchos están guardados con apodos
# ("cuñada de Emily"); quien lo quiera puede escribir {nombre}.
MENSAJE = ("¡Hola! ¿Cómo estás? Te escribimos de la Charcutería HYE para recordarte "
           "el saldo pendiente que tienes con nosotros. ¡Muchas gracias!")
CAMPOS = ("{nombre}", "{deuda}")
# La parte fija, que va siempre debajo
SALDO = "Saldo pendiente: {deuda}"
ENLACE = "Aquí está el detalle de tu estado de cuenta: {enlace}"
CUENTA = "Puedes pagarnos a: {cuenta}"


def preparar(conn):
    """La columna de la frecuencia y las tablas, la primera vez."""
    columnas = {f[1] for f in conn.execute("PRAGMA table_info(clients)").fetchall()}
    if "cobro" not in columnas:
        conn.execute("ALTER TABLE clients ADD COLUMN cobro TEXT")     # semanal, quincenal o NULL
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cobros_envios (
            client_id INTEGER NOT NULL,
            periodo TEXT NOT NULL,       -- semanal:AAAA-MM-DD o quincenal:AAAA-MM-DD (cuándo empezó)
            deuda REAL NOT NULL,         -- lo que debía cuando se le cobró
            enviado TEXT NOT NULL,
            PRIMARY KEY (client_id, periodo))""")
    conn.execute("CREATE TABLE IF NOT EXISTS ajustes (clave TEXT PRIMARY KEY, valor TEXT)")


# ── Ajustes: mensaje, número de cuenta y día de cobro semanal ────────────────
def _ajuste(conn, clave):
    fila = conn.execute("SELECT valor FROM ajustes WHERE clave = ?", (clave,)).fetchone()
    return fila[0] if fila else None


def _poner(conn, clave, valor):
    conn.execute("INSERT INTO ajustes (clave, valor) VALUES (?, ?) "
                 "ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor", (clave, valor))


def ajustes(conn):
    dia = _ajuste(conn, "cobro_dia_semanal")
    mensaje = _ajuste(conn, "cobro_mensaje")
    return {"cuenta": _ajuste(conn, "cobro_cuenta") or "",
            "mensaje": mensaje or MENSAJE,
            "personalizado": mensaje is not None,
            "dia_semanal": int(dia) if dia and dia.isdigit() and int(dia) < 7 else DIA_SEMANAL}


def guardar_mensaje(conn, mensaje):
    """La parte de arriba del mensaje. Si queda igual al de siempre, se borra
    lo guardado (y vuelve a ser el de siempre)."""
    mensaje = (mensaje or "").strip()
    if not mensaje:
        raise ValueError("El mensaje no puede quedar vacío")
    if len(mensaje) > LARGO_MAXIMO:
        raise ValueError(f"El mensaje es muy largo (máximo {LARGO_MAXIMO} letras)")
    if mensaje == MENSAJE:
        conn.execute("DELETE FROM ajustes WHERE clave = 'cobro_mensaje'")
    else:
        _poner(conn, "cobro_mensaje", mensaje)
    return mensaje


def guardar_cuenta(conn, cuenta, dia_semanal):
    cuenta = (cuenta or "").strip()
    if len(cuenta) > 300:
        raise ValueError("El número de cuenta es muy largo")
    try:
        dia_semanal = int(dia_semanal)
    except (TypeError, ValueError):
        dia_semanal = -1
    if not 0 <= dia_semanal <= 6:
        raise ValueError("Elija el día del cobro semanal")
    _poner(conn, "cobro_cuenta", cuenta)
    _poner(conn, "cobro_dia_semanal", str(dia_semanal))


# ── Periodos ─────────────────────────────────────────────────────────────────
def _ultimo_del_mes(d):
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def inicio_periodo(frecuencia, hoy, dia_semanal=DIA_SEMANAL):
    """El día en que empezó el periodo de cobro en el que está hoy."""
    if frecuencia == "semanal":
        return hoy - timedelta(days=(hoy.weekday() - dia_semanal) % 7)
    if hoy == _ultimo_del_mes(hoy):
        return hoy
    if hoy.day >= 15:
        return hoy.replace(day=15)
    return _ultimo_del_mes(hoy.replace(day=1) - timedelta(days=1))


def periodo(frecuencia, hoy, dia_semanal=DIA_SEMANAL):
    return f"{frecuencia}:{inicio_periodo(frecuencia, hoy, dia_semanal).isoformat()}"


# ── El mensaje ───────────────────────────────────────────────────────────────
def _pesos(v):
    return "$" + f"{round(v or 0):,.0f}".replace(",", ".")


def parte_fija(deuda, enlace, cuenta, con_saldo=True):
    """Lo que va debajo del mensaje y no se edita. El saldo sobra si el
    mensaje ya lo dice con {deuda}."""
    lineas = [SALDO.replace("{deuda}", _pesos(deuda))] if con_saldo else []
    lineas.append(ENLACE.replace("{enlace}", enlace))
    if cuenta:
        lineas.append(CUENTA.replace("{cuenta}", cuenta))
    return "\n".join(lineas)


def mensaje(plantilla, nombre, deuda, enlace, cuenta):
    """El mensaje completo: lo escrito, con {nombre} y {deuda} llenos, y la parte fija."""
    texto = plantilla.strip()
    for campo, valor in zip(CAMPOS, (nombre.strip(), _pesos(deuda))):
        texto = texto.replace(campo, valor)
    return texto + "\n\n" + parte_fija(deuda, enlace, cuenta, con_saldo="{deuda}" not in plantilla)


# ── Quién ────────────────────────────────────────────────────────────────────
def poner_frecuencia(conn, client_id, frecuencia):
    frecuencia = frecuencia or None
    if frecuencia is not None and frecuencia not in FRECUENCIAS:
        raise ValueError("Frecuencia de cobro no válida")
    if conn.execute("SELECT 1 FROM clients WHERE id = ?", (client_id,)).fetchone() is None:
        raise ValueError("El cliente no existe")
    conn.execute("UPDATE clients SET cobro = ? WHERE id = ?", (frecuencia, client_id))


def frecuencia(conn, client_id):
    fila = conn.execute("SELECT cobro FROM clients WHERE id = ?", (client_id,)).fetchone()
    return fila[0] if fila else None


def clientes(conn, hoy, dia_semanal=DIA_SEMANAL):
    """Los que deben, del que más debe al que menos, repartidos en: a quién
    toca cobrar, a quién ya se le cobró en este periodo y quién no tiene
    frecuencia. Los que tocan y no tienen teléfono van con whatsapp None."""
    from utils.perfil_clientes import enlace_whatsapp
    enviados = {(cid, p): enviado for cid, p, enviado in conn.execute(
        "SELECT client_id, periodo, enviado FROM cobros_envios").fetchall()}
    toca, cobrados, sin_frecuencia = [], [], []
    for cid, nombre, telefono, deuda, cobro in conn.execute("""
            SELECT id, name, phone, total_debt, cobro FROM clients
             WHERE total_debt > 0.5 ORDER BY total_debt DESC""").fetchall():
        c = {"id": cid, "nombre": nombre, "deuda": deuda, "frecuencia": cobro,
             "whatsapp": enlace_whatsapp(telefono)}
        if cobro not in FRECUENCIAS:
            sin_frecuencia.append(c)
            continue
        c["periodo"] = periodo(cobro, hoy, dia_semanal)
        c["enviado"] = enviados.get((cid, c["periodo"]))
        (cobrados if c["enviado"] else toca).append(c)
    return toca, cobrados, sin_frecuencia


def marcar_cobrado(conn, client_id, hoy, dia_semanal=DIA_SEMANAL):
    fila = conn.execute("SELECT total_debt, cobro FROM clients WHERE id = ?", (client_id,)).fetchone()
    if fila is None or fila[1] not in FRECUENCIAS:
        raise ValueError("El cliente no existe o no tiene frecuencia de cobro")
    conn.execute("""
        INSERT OR IGNORE INTO cobros_envios (client_id, periodo, deuda, enviado)
        VALUES (?, ?, ?, datetime('now', 'localtime'))""",
                 (client_id, periodo(fila[1], hoy, dia_semanal), fila[0] or 0))
