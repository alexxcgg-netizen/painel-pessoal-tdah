"""Gera o par de chaves VAPID necessario pra notificacao push.

Roda uma unica vez:
    python scripts/gerar_chaves_push.py

Salva a chave privada em vapid_private.pem (fica de fora do git) e imprime
o que colar no .env.
"""

import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid02 as Vapid

PRIVATE_KEY_PATH = Path(__file__).parent.parent / "vapid_private.pem"


def main():
    if PRIVATE_KEY_PATH.exists():
        print(f"Ja existe uma chave em {PRIVATE_KEY_PATH} - apagando ela vai invalidar")
        print("qualquer inscricao de notificacao que ja tenha sido feita. Cancele com Ctrl+C")
        print("se nao tiver certeza, ou Enter pra gerar uma nova mesmo assim.")
        input()

    vapid = Vapid()
    vapid.generate_keys()
    vapid.save_key(str(PRIVATE_KEY_PATH))

    chave_publica = (
        base64.urlsafe_b64encode(
            vapid.public_key.public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.UncompressedPoint,
            )
        )
        .decode()
        .rstrip("=")
    )

    print(f"\nChave privada salva em {PRIVATE_KEY_PATH}")
    print("\nAdicione isso ao seu .env:\n")
    print(f"VAPID_PUBLIC_KEY={chave_publica}")
    print("VAPID_SUBJECT=mailto:seu-email@exemplo.com")


if __name__ == "__main__":
    main()
