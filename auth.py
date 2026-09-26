"""Login por PIN de 6 digitos - unico jeito de acessar o painel quando ele
sai do localhost. Nada aqui e client-side: a sessao e verificada no
`before_request` do app.py em toda requisicao, entao abrir o Inspecionar/
Console do navegador nao adianta nada, quem decide "autenticado ou nao" e
sempre o servidor.

Padrao portado (com ajustes) do painel_web da A.N Construtora, ja auditado
la: chave de sessao aleatoria persistida no banco (nunca fixa no codigo -
uma chave fixa e visivel pra qualquer um com acesso ao repositorio, que
poderia forjar um cookie de sessao valido e pular o PIN inteiro), hash do
PIN (nunca o PIN puro), e bloqueio por forca bruta persistido no banco
(sobrevive a reinicio do processo).
"""

import secrets
import time

from werkzeug.security import check_password_hash, generate_password_hash

from db import definir_configuracao, obter_configuracao

TENTATIVAS_PARA_BLOQUEAR = 5
DURACAO_BLOQUEIO_SEGUNDOS = 5 * 60


def obter_ou_criar_secret_key(conn) -> str:
    existente = obter_configuracao(conn, "secret_key_sessao")
    if existente:
        return existente
    nova = secrets.token_hex(32)
    definir_configuracao(conn, "secret_key_sessao", nova)
    return nova


def pin_configurado(conn) -> bool:
    return obter_configuracao(conn, "pin_hash") is not None


def definir_pin(conn, pin: str, confirmacao: str):
    """Levanta ValueError com uma mensagem pronta pra mostrar ao usuario se
    o PIN nao for valido - o chamador (rota Flask) so precisa decidir o
    status code."""
    pin = (pin or "").strip()
    confirmacao = (confirmacao or "").strip()
    if not pin.isdigit() or len(pin) != 6:
        raise ValueError("O PIN precisa ter exatamente 6 dígitos numericos.")
    if pin != confirmacao:
        raise ValueError("O PIN e a confirmação não são iguais.")
    definir_configuracao(conn, "pin_hash", generate_password_hash(pin))


def verificar_pin(conn, pin: str) -> bool:
    hash_salvo = obter_configuracao(conn, "pin_hash")
    if not hash_salvo:
        return False
    return check_password_hash(hash_salvo, (pin or "").strip())


def verificar_bloqueio(conn, ip: str, agora: float | None = None) -> tuple[bool, str | None]:
    """Retorna (pode_tentar, mensagem). Quando bloqueado, pode_tentar e
    False e mensagem explica quanto tempo falta - checado ANTES de
    comparar o PIN, entao uma tentativa durante o bloqueio nem chega a
    gastar um `check_password_hash`."""
    agora = agora if agora is not None else time.time()
    row = conn.execute(
        "SELECT bloqueado_ate FROM login_tentativas WHERE ip = ?", (ip,)
    ).fetchone()
    if row and row["bloqueado_ate"] > agora:
        segundos_restantes = int(row["bloqueado_ate"] - agora)
        minutos = max(1, segundos_restantes // 60 + (1 if segundos_restantes % 60 else 0))
        return False, f"Muitas tentativas erradas. Tenta de novo em {minutos} minuto(s)."
    return True, None


def registrar_tentativa(conn, ip: str, sucesso: bool, agora: float | None = None):
    agora = agora if agora is not None else time.time()
    if sucesso:
        conn.execute(
            "INSERT INTO login_tentativas (ip, tentativas, bloqueado_ate) VALUES (?, 0, 0) "
            "ON CONFLICT(ip) DO UPDATE SET tentativas = 0, bloqueado_ate = 0",
            (ip,),
        )
    else:
        row = conn.execute(
            "SELECT tentativas FROM login_tentativas WHERE ip = ?", (ip,)
        ).fetchone()
        tentativas = (row["tentativas"] if row else 0) + 1
        bloqueado_ate = agora + DURACAO_BLOQUEIO_SEGUNDOS if tentativas >= TENTATIVAS_PARA_BLOQUEAR else 0
        conn.execute(
            "INSERT INTO login_tentativas (ip, tentativas, bloqueado_ate) VALUES (?, ?, ?) "
            "ON CONFLICT(ip) DO UPDATE SET tentativas = excluded.tentativas, bloqueado_ate = excluded.bloqueado_ate",
            (ip, tentativas, bloqueado_ate),
        )
    conn.commit()
