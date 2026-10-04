"""Conexión a la base en la nube (Turso), con la misma cara que sqlite3.

El programa se escribió para sqlite3: lee columnas por nombre (fila['name']),
recorre cursores con for, atrapa sqlite3.IntegrityError, abre y cierra una
conexión en cada operación... La librería de Turso (libsql) no hace nada de
eso, así que aquí se envuelve para que el resto del código no note el cambio.

Se usan dos conexiones:
- una réplica local de la base, para leer: las lecturas no salen del PC;
- una directa a la nube, para escribir. Escribir a través de la réplica es
  más del doble de lento (medido: ~440 ms por instrucción contra ~190 ms).
En cuanto una transacción escribe, todo lo que sigue hasta el commit va a la
nube, para que sus propias lecturas vean lo que acaba de escribir. Al hacer
commit se sincroniza la réplica.

Se activa con data/nube.json:  {"url": "libsql://…", "token": "…"}
Sin ese archivo, el programa sigue usando el tienda.db local de siempre.
"""
import json
import os
import re
import sqlite3
import time
from datetime import date, datetime

# Cada cuánto traer de la nube lo que se anotó desde otro lado (el celular)
SEGUNDOS_ENTRE_SINCRONIZACIONES = 15


def leer_configuracion(carpeta_datos):
    ruta = os.path.join(carpeta_datos, "nube.json")
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as f:
        config = json.load(f)
    if not config.get("url") or not config.get("token"):
        return None
    return config


def _traducir_error(e):
    """libsql lanza ValueError para todo; el programa espera los de sqlite3."""
    mensaje = str(e)
    if "constraint" in mensaje.lower():
        return sqlite3.IntegrityError(mensaje)
    return sqlite3.OperationalError(mensaje)


def _valor(v):
    """sqlite3 convierte solo las fechas de Python a texto; libsql las
    rechaza ("Unsupported parameter type"). Se convierten igual que sqlite3:
    datetime → '2026-09-26 12:30:05', date → '2026-09-26'."""
    if isinstance(v, datetime):
        return v.isoformat(" ")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, bool):
        return int(v)
    return v


def _parametros(params):
    if params is None:
        return ()
    if isinstance(params, (list, tuple)):
        return tuple(_valor(v) for v in params)
    if isinstance(params, dict):
        raise sqlite3.ProgrammingError("La base en la nube no admite parámetros con nombre")
    return (_valor(params),)


_AHORA_LOCAL = re.compile(r"'now'\s*,\s*'localtime'", re.IGNORECASE)


def con_hora_local(sql):
    """El servidor de Turso vive en UTC: datetime('now', 'localtime') daría 5
    horas de más y una venta de las 9 p. m. quedaría al día siguiente. Se
    reemplaza por la hora de este equipo, que es lo que devolvía sqlite3."""
    if "localtime" not in sql.lower():
        return sql
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return _AHORA_LOCAL.sub(f"'{ahora}'", sql)


_CREAR_SI_NO_EXISTE = re.compile(
    r"^\s*CREATE\s+(?:UNIQUE\s+)?(TABLE|INDEX|VIEW|TRIGGER)\s+IF\s+NOT\s+EXISTS\s+"
    r"[\"`\[]?(\w+)", re.IGNORECASE)


def objeto_a_crear(sql):
    """('table', 'clients') si es un CREATE … IF NOT EXISTS; si no, None."""
    m = _CREAR_SI_NO_EXISTE.match(sql)
    return (m.group(1).lower(), m.group(2)) if m else None


def es_lectura(sql):
    """¿La instrucción solo lee? Lo que no se sabe con seguridad cuenta como
    escritura: mandarlo a la nube es más lento, pero nunca incorrecto."""
    palabras = sql.lstrip().split(None, 1)
    if not palabras:
        return True
    primera = palabras[0].upper()
    if primera in ("SELECT", "EXPLAIN"):
        return True
    if primera == "PRAGMA":
        return "=" not in sql
    if primera == "WITH":
        cuerpo = sql.upper()
        return not any(p in cuerpo for p in ("INSERT", "UPDATE", "DELETE", "REPLACE"))
    return False


def dividir_guion(script):
    """Parte un guion SQL en instrucciones completas (respeta los ';' que van
    dentro de textos, como hace sqlite3)."""
    instrucciones, actual = [], ""
    for caracter in script:
        actual += caracter
        if caracter == ";" and sqlite3.complete_statement(actual):
            if actual.strip().strip(";").strip():
                instrucciones.append(actual.strip())
            actual = ""
    if actual.strip().strip(";").strip():
        instrucciones.append(actual.strip())
    return instrucciones


class Fila:
    """Igual que sqlite3.Row: fila[0], fila['columna'], keys(), tuple(fila)."""
    __slots__ = ("_valores", "_indices", "_nombres")

    def __init__(self, nombres, indices, valores):
        self._nombres, self._indices, self._valores = nombres, indices, tuple(valores)

    def __getitem__(self, clave):
        if isinstance(clave, str):
            try:
                return self._valores[self._indices[clave.lower()]]
            except KeyError:
                raise IndexError("No item with that key") from None
        return self._valores[clave]

    def keys(self):
        return list(self._nombres)

    def __iter__(self):
        return iter(self._valores)

    def __len__(self):
        return len(self._valores)

    def __eq__(self, otra):
        if isinstance(otra, Fila):
            return self._nombres == otra._nombres and self._valores == otra._valores
        return NotImplemented

    def __hash__(self):
        return hash((self._nombres, self._valores))

    def __repr__(self):
        return f"<Fila {self._valores!r}>"


class Cursor:
    def __init__(self, conexion):
        self._conexion, self._cursor = conexion, None
        self._nombres, self._indices = (), {}

    def _preparar(self):
        descripcion = self._cursor.description or ()
        self._nombres = tuple(d[0] for d in descripcion)
        self._indices = {}
        for i, n in enumerate(self._nombres):
            self._indices.setdefault(n.lower(), i)   # como sqlite3: gana la primera

    def _fila(self, valores):
        return None if valores is None else Fila(self._nombres, self._indices, valores)

    def execute(self, sql, params=None):
        sql = con_hora_local(sql)
        self._cursor = self._conexion._cursor_para(sql)
        try:
            self._cursor.execute(sql, _parametros(params))
        except ValueError as e:
            raise _traducir_error(e) from e
        self._preparar()
        return self

    def executemany(self, sql, secuencia):
        sql = con_hora_local(sql)
        self._cursor = self._conexion._cursor_para(sql)
        try:
            self._cursor.executemany(sql, [_parametros(p) for p in secuencia])
        except ValueError as e:
            raise _traducir_error(e) from e
        self._preparar()
        return self

    def executescript(self, script):
        # Contra la nube, libsql ejecuta solo la primera instrucción del guion
        # y descarta el resto sin avisar: se mandan una por una.
        for instruccion in dividir_guion(script):
            self.execute(instruccion)
        return self

    def fetchone(self):
        return self._fila(self._cursor.fetchone()) if self._cursor else None

    def fetchall(self):
        return [self._fila(v) for v in self._cursor.fetchall()] if self._cursor else []

    def fetchmany(self, size=None):
        if not self._cursor:
            return []
        filas = self._cursor.fetchmany(size) if size else self._cursor.fetchmany()
        return [self._fila(v) for v in filas]

    def __iter__(self):
        return iter(self.fetchall())

    @property
    def description(self):
        return self._cursor.description if self._cursor else None

    @property
    def lastrowid(self):
        return self._cursor.lastrowid if self._cursor else None

    @property
    def rowcount(self):
        return self._cursor.rowcount if self._cursor else -1

    def close(self):
        pass


class _NoHacerNada:
    """Cursor de una instrucción que no necesita ejecutarse."""
    description, lastrowid, rowcount = None, None, -1

    def execute(self, sql, params=()):
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def fetchmany(self, size=None):
        return []


class Conexion:
    """Conexión compartida: lee de `local`, escribe en `remota` (None cuando se
    prueba contra un archivo, sin nube)."""

    def __init__(self, local, remota):
        self._local, self._remota = local, remota
        self._escribiendo = False
        self._ultima_sincronizacion = 0.0

    def _cursor_para(self, sql):
        if self._remota is None:
            return self._local.cursor()
        # Al arrancar, el programa "crea si no existe" cada tabla: si la copia
        # local ya la tiene, no hay nada que hacer y se ahorra el viaje (son
        # ~30 al abrir el programa).
        objeto = objeto_a_crear(sql)
        if objeto and self._local.execute(
                "SELECT 1 FROM sqlite_master WHERE type = ? AND name = ?", objeto).fetchone():
            return _NoHacerNada()
        if not self._escribiendo and not es_lectura(sql):
            self._escribiendo = True
        return (self._remota if self._escribiendo else self._local).cursor()

    # ── sincronización con la nube ──
    def sincronizar(self, forzar=False):
        if self._remota is None or self._escribiendo:
            return
        ahora = time.monotonic()
        if forzar or ahora - self._ultima_sincronizacion >= SEGUNDOS_ENTRE_SINCRONIZACIONES:
            self._local.sync()
            self._ultima_sincronizacion = ahora

    # ── API de sqlite3 ──
    def cursor(self):
        return Cursor(self)

    def execute(self, sql, params=None):
        return self.cursor().execute(sql, params)

    def executemany(self, sql, secuencia):
        return self.cursor().executemany(sql, secuencia)

    def executescript(self, script):
        return self.cursor().executescript(script)

    def commit(self):
        if self._remota is None:
            conn = self._local
        elif self._escribiendo:
            conn = self._remota
        else:
            return
        try:
            conn.commit()
        except ValueError as e:
            raise _traducir_error(e) from e
        if self._escribiendo:
            self._escribiendo = False
            self.sincronizar(forzar=True)   # que las lecturas vean lo escrito

    def rollback(self):
        if self._remota is not None and self._escribiendo:
            self._remota.rollback()
            self._escribiendo = False
        elif self._remota is None:
            self._local.rollback()

    @property
    def in_transaction(self):
        if self._remota is None:
            return self._local.in_transaction
        return self._escribiendo and self._remota.in_transaction

    def close(self):
        """Para las conexiones propias (conexion_directa); la compartida se
        cierra a través de su Manija."""
        if self.in_transaction:
            self.rollback()

    def __enter__(self):
        return self

    def __exit__(self, tipo, valor, traza):
        # Igual que sqlite3: confirma si todo salió bien, deshace si hubo error
        if tipo is None:
            self.commit()
        else:
            self.rollback()
        return False


class Manija:
    """Lo que recibe cada get_connection(). Todas comparten la misma conexión,
    y hay código que abre una, llama a otra función que abre y cierra la suya,
    y luego confirma la primera. Por eso lo que quedó sin confirmar solo se
    descarta cuando se cierra la última manija abierta, no la de adentro."""
    abiertas = 0

    def __init__(self, compartida):
        self._compartida, self._cerrada = compartida, False
        Manija.abiertas += 1

    def __getattr__(self, nombre):
        return getattr(self._compartida, nombre)

    def __setattr__(self, nombre, valor):
        if nombre in ("_compartida", "_cerrada"):
            object.__setattr__(self, nombre, valor)
        # row_factory y demás ajustes de sqlite3 no aplican aquí

    def close(self):
        if self._cerrada:
            return
        self._cerrada = True
        Manija.abiertas -= 1
        if Manija.abiertas == 0 and self._compartida.in_transaction:
            self._compartida.rollback()

    def __enter__(self):
        return self._compartida.__enter__()

    def __exit__(self, *info):
        return self._compartida.__exit__(*info)


_compartida = None


def conexion(ruta_local, url=None, token=None):
    """La conexión compartida. Con url y token lee de una réplica de la base
    en la nube guardada en ruta_local y escribe directo en la nube; sin ellos,
    abre ruta_local directamente (sirve para probar el adaptador sin internet)."""
    global _compartida
    if _compartida is None:
        import libsql
        if url:
            local = libsql.connect(ruta_local, sync_url=url, auth_token=token)
            remota = libsql.connect(url, auth_token=token)
            # Turso revisa las llaves foráneas y sqlite3 no; hay movimientos
            # que apuntan a ventas eliminadas, así que se deja como en sqlite3.
            remota.execute("PRAGMA foreign_keys=OFF")
        else:
            local, remota = libsql.connect(ruta_local), None
            local.execute("PRAGMA foreign_keys=OFF")
        _compartida = Conexion(local, remota)
        _compartida.sincronizar(forzar=True)
    elif Manija.abiertas == 0:
        _compartida.sincronizar()
    return Manija(_compartida)


def conexion_directa(url, token, solo_lectura=False):
    """Una conexión propia, solo a la nube y sin copia local, para el servidor
    de la página del celular: está en la misma región que la base, así que
    cada consulta tarda milisegundos. Quien la abre la cierra.

    solo_lectura: para un token de solo lectura (el catálogo), que Turso
    no deja ni cambiar las llaves foráneas; tampoco hace falta, si no escribe."""
    import libsql
    conn = libsql.connect(url, auth_token=token)
    if not solo_lectura:
        conn.execute("PRAGMA foreign_keys=OFF")
    return Conexion(conn, None)
