"""Contraseña de la página del celular.

Se guarda solo su huella (PBKDF2 con sal), nunca la contraseña. Para crear la
huella de una contraseña nueva:

    python -m web.clave
"""
import getpass
import hashlib
import hmac
import secrets

ITERACIONES = 600_000


def huella(clave: str, sal: str = None) -> str:
    sal = sal or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(sal), ITERACIONES)
    return f"pbkdf2_sha256${ITERACIONES}${sal}${h.hex()}"


def verificar(clave: str, guardada: str) -> bool:
    try:
        _algoritmo, iteraciones, sal, esperado = guardada.split("$")
        h = hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(sal), int(iteraciones))
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(h.hex(), esperado)


if __name__ == "__main__":
    primera = getpass.getpass("Contraseña nueva: ")
    if len(primera) < 8:
        raise SystemExit("Use al menos 8 caracteres.")
    if getpass.getpass("Repítala: ") != primera:
        raise SystemExit("No coinciden.")
    print(huella(primera))
