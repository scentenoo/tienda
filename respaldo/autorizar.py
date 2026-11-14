"""Da permiso, una sola vez, para que el respaldo entre a Google Drive.

    python -m respaldo.autorizar CLIENTE_ID CLIENTE_SECRETO

Se corre en el computador. Abre Google en el navegador; se entra con la
cuenta dueña de la carpeta Emprendimiento y se toca «Permitir». Al final
imprime el GOOGLE_REFRESH_TOKEN, que va como secreto en GitHub (ver
respaldo/LEEME.md), y comprueba que ve la carpeta.

Ese token sirve para entrar al Drive de esa cuenta: no se comparte ni se
pega en ningún otro lado.
"""
import http.server
import json
import secrets
import sys
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from respaldo.drive import ALCANCE, Drive, token_de_acceso  # noqa: E402


def _esperar_codigo(estado):
    """Abre un servidor en este equipo y espera a que Google vuelva con el código."""
    recibido = {}

    class Respuesta(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            datos = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if datos.get("state", [""])[0] != estado:
                self.send_response(400)
                self.end_headers()
                return
            recibido.update({k: v[0] for k, v in datos.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            texto = ("Listo, ya puede cerrar esta ventana y volver a la terminal." if "code" in recibido
                     else "No se dio el permiso. Vuelva a la terminal.")
            self.wfile.write(f"<p style='font:20px system-ui'>{texto}</p>".encode())

        def log_message(self, *args):
            pass

    servidor = http.server.HTTPServer(("127.0.0.1", 0), Respuesta)
    return servidor, recibido


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    cliente_id, cliente_secreto = sys.argv[1].strip(), sys.argv[2].strip()
    estado = secrets.token_urlsafe(16)
    servidor, recibido = _esperar_codigo(estado)
    redireccion = f"http://127.0.0.1:{servidor.server_port}"
    enlace = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cliente_id, "redirect_uri": redireccion, "response_type": "code",
        "scope": ALCANCE, "access_type": "offline", "prompt": "consent", "state": estado})
    print("Se abre Google en el navegador. Si no se abre, copie este enlace:\n\n" + enlace + "\n")
    webbrowser.open(enlace)
    while not recibido:
        servidor.handle_request()
    servidor.server_close()
    if "code" not in recibido:
        raise SystemExit(f"Google no dio el permiso: {recibido.get('error', 'sin motivo')}")

    datos = urllib.parse.urlencode({
        "code": recibido["code"], "client_id": cliente_id, "client_secret": cliente_secreto,
        "redirect_uri": redireccion, "grant_type": "authorization_code"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=datos, timeout=30) as r:
        tokens = json.loads(r.read())
    if "refresh_token" not in tokens:
        raise SystemExit("Google no devolvió el refresh token; vuelva a intentarlo.")

    drive = Drive(token_de_acceso(cliente_id, cliente_secreto, tokens["refresh_token"]))
    hay = drive.buscar("Emprendimiento", "root", carpeta=True)
    print("✓ Permiso dado. " + ("Se ve la carpeta Emprendimiento en Mi unidad." if hay else
          "OJO: no se ve la carpeta Emprendimiento en Mi unidad; ¿se entró con la cuenta correcta?"))
    print("\nEste es el GOOGLE_REFRESH_TOKEN (cópielo entero, va como secreto en GitHub):\n")
    print(tokens["refresh_token"])


if __name__ == "__main__":
    main()
