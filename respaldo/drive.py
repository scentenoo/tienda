"""Google Drive por su API, sin librerías: lo justo para el respaldo.

Entra con la cuenta del dueño (un "refresh token" que se saca una vez con
python -m respaldo.autorizar) y escribe en las mismas carpetas que el
programa del computador: Mi unidad/<carpeta>/backups_db y db_actual.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ALCANCE = "https://www.googleapis.com/auth/drive"
API = "https://www.googleapis.com/drive/v3/files"
SUBIDA = "https://www.googleapis.com/upload/drive/v3/files"
CARPETA = "application/vnd.google-apps.folder"


class ErrorDrive(RuntimeError):
    pass


def _pedir(solicitud, intentos=3):
    """Hace la petición y devuelve el JSON. Reintenta lo que suele ser pasajero."""
    for intento in range(intentos):
        try:
            with urllib.request.urlopen(solicitud, timeout=120) as r:
                cuerpo = r.read()
            return json.loads(cuerpo) if cuerpo else {}
        except urllib.error.HTTPError as e:
            detalle = e.read().decode("utf-8", "replace")[:300]
            if e.code in (429, 500, 502, 503, 504) and intento < intentos - 1:
                time.sleep(3 * (intento + 1))
                continue
            raise ErrorDrive(f"Google Drive respondió {e.code}: {detalle}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if intento < intentos - 1:
                time.sleep(3 * (intento + 1))
                continue
            raise ErrorDrive(f"No se pudo hablar con Google Drive: {e}") from None


def token_de_acceso(cliente_id, cliente_secreto, refresh_token):
    """El refresh token no vence mientras no se revoque; este dura una hora."""
    datos = urllib.parse.urlencode({
        "client_id": cliente_id, "client_secret": cliente_secreto,
        "refresh_token": refresh_token, "grant_type": "refresh_token"}).encode()
    try:
        return _pedir(urllib.request.Request("https://oauth2.googleapis.com/token", data=datos))["access_token"]
    except ErrorDrive as e:
        if "invalid_grant" in str(e):
            raise ErrorDrive("Google ya no acepta el permiso: hay que volver a correr "
                             "python -m respaldo.autorizar (ver respaldo/LEEME.md)") from None
        raise


class Drive:
    def __init__(self, token):
        self.token = token

    def _solicitud(self, url, datos=None, metodo=None, tipo="application/json"):
        cabeceras = {"Authorization": f"Bearer {self.token}"}
        if datos is not None:
            cabeceras["Content-Type"] = tipo
        return urllib.request.Request(url, data=datos, method=metodo, headers=cabeceras)

    def buscar(self, nombre, padre, carpeta=False):
        """Los archivos (o carpetas) con ese nombre dentro de padre, sin la papelera."""
        nombre = nombre.replace("\\", "\\\\").replace("'", "\\'")
        q = f"name = '{nombre}' and '{padre}' in parents and trashed = false"
        q += f" and mimeType {'=' if carpeta else '!='} '{CARPETA}'"
        url = API + "?" + urllib.parse.urlencode({"q": q, "fields": "files(id,name)", "pageSize": 10})
        return _pedir(self._solicitud(url))["files"]

    def carpeta(self, nombre, padre="root"):
        """El id de la carpeta; si no existe, la crea."""
        encontradas = self.buscar(nombre, padre, carpeta=True)
        if encontradas:
            return encontradas[0]["id"]
        datos = json.dumps({"name": nombre, "mimeType": CARPETA, "parents": [padre]}).encode()
        return _pedir(self._solicitud(API + "?fields=id", datos, "POST"))["id"]

    def listar(self, padre):
        """Los nombres e ids de lo que hay en la carpeta, de todas las páginas."""
        archivos, pagina = [], None
        while True:
            parametros = {"q": f"'{padre}' in parents and trashed = false",
                          "fields": "nextPageToken,files(id,name)", "pageSize": 1000}
            if pagina:
                parametros["pageToken"] = pagina
            r = _pedir(self._solicitud(API + "?" + urllib.parse.urlencode(parametros)))
            archivos += r["files"]
            pagina = r.get("nextPageToken")
            if not pagina:
                return archivos

    def subir(self, nombre, padre, contenido):
        """Crea un archivo nuevo. Devuelve su id."""
        limite = uuid.uuid4().hex
        metadatos = json.dumps({"name": nombre, "parents": [padre]}).encode()
        cuerpo = (f"--{limite}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
                  + metadatos
                  + f"\r\n--{limite}\r\nContent-Type: application/octet-stream\r\n\r\n".encode()
                  + contenido + f"\r\n--{limite}--".encode())
        return _pedir(self._solicitud(SUBIDA + "?uploadType=multipart&fields=id", cuerpo, "POST",
                                      f"multipart/related; boundary={limite}"))["id"]

    def reemplazar(self, archivo_id, contenido):
        """Cambia el contenido de un archivo que ya existe (conserva su id)."""
        _pedir(self._solicitud(f"{SUBIDA}/{archivo_id}?uploadType=media&fields=id", contenido,
                               "PATCH", "application/octet-stream"))

    def a_la_papelera(self, archivo_id):
        """Como rclone en el computador: a la papelera, no borrado del todo."""
        _pedir(self._solicitud(f"{API}/{archivo_id}?fields=id", json.dumps({"trashed": True}).encode(),
                               "PATCH"))
