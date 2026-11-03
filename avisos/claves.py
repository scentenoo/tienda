"""Crea el par de claves de los avisos (VAPID). Se corre una sola vez:

    python -m avisos.claves

La pública va en la página (VAPID_PUBLICA) y en GitHub como variable; la
privada solo en GitHub, como secreto (VAPID_PRIVADA). Si se cambian, cada
celular tiene que volver a activar los avisos."""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64(datos):
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def main():
    privada = ec.generate_private_key(ec.SECP256R1())
    publica = privada.public_key().public_bytes(serialization.Encoding.X962,
                                                serialization.PublicFormat.UncompressedPoint)
    print("VAPID_PUBLICA =", _b64(publica))
    print("VAPID_PRIVADA =", _b64(privada.private_numbers().private_value.to_bytes(32, "big")))
    print("\nLa privada no se comparte ni se sube al repositorio.")


if __name__ == "__main__":
    main()
