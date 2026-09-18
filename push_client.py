"""Notificacao push via Web Push (VAPID) - funciona em qualquer navegador
que suporte PWA (Chrome/Edge no Android e desktop, Safari 16.4+ no iOS
apos "Adicionar a Tela de Inicio").

So fica ativo quando VAPID_PUBLIC_KEY existe no .env E o arquivo
vapid_private.pem existe. Gere os dois com:
    python scripts/gerar_chaves_push.py

Enviar uma notificacao AGORA funciona mesmo sem hospedagem fixa (basta
o app estar rodando no momento do envio - o navegador entrega assim que
o aparelho estiver online). So notificacao AGENDADA (tipo "todo dia as
8h") precisa de algo rodando o tempo todo pra disparar o envio na hora
certa - isso ainda nao esta implementado, ver README.
"""

import json
import os
from pathlib import Path

from pywebpush import WebPushException, webpush

PRIVATE_KEY_PATH = Path(__file__).parent / "vapid_private.pem"


def configurado() -> bool:
    return bool(os.environ.get("VAPID_PUBLIC_KEY")) and PRIVATE_KEY_PATH.exists()


def public_key() -> str:
    return os.environ.get("VAPID_PUBLIC_KEY", "")


def enviar(subscription_info: dict, titulo: str, corpo: str) -> bool:
    """Manda uma notificacao. Retorna False se a inscricao morreu
    (usuario desinstalou/bloqueou) - nesse caso o chamador deve apagar
    essa inscricao do banco."""
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({"titulo": titulo, "corpo": corpo}),
            vapid_private_key=str(PRIVATE_KEY_PATH),
            vapid_claims={"sub": os.environ.get("VAPID_SUBJECT", "mailto:voce@exemplo.com")},
        )
        return True
    except WebPushException:
        return False
