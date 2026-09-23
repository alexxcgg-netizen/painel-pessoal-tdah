"""Criptografia de campo, pra dado sensivel em repouso no banco.

Escopo exato (ver docs/SEGURANCA.md pra decisao completa e o porque): saldo/
transacao do Open Finance (bank_accounts.saldo, bank_transactions.descricao
e .valor) e dado de saude (saude_dados, medidas_corporais.valor,
medicamentos.nome/dosagem/horario). O resto do banco (tarefas, notas,
gastos digitados a mao, etc) fica em texto plano - decisao documentada em
docs/SEGURANCA.md, nao um esquecimento.

Usa Fernet (`cryptography`) - AES simetrico com autenticacao (HMAC), API de
duas funcoes, biblioteca bem auditada. Uma chave so, em ENCRYPTION_KEY no
ambiente (gere com scripts/gerar_chave_criptografia.py).

Decisao de design: SEM ENCRYPTION_KEY configurada, o app continua
funcionando normalmente (app pessoal do Alex, nunca deve travar por causa
disso) - os campos sensiveis ficam em texto plano, com um aviso (uma vez por
processo) no log. `configurada()` existe pra quem quiser expor isso numa
rota de diagnostico ou avisar na interface (ver /api/seguranca/status em
app.py)."""

import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_aviso_ja_logado = False


def configurada() -> bool:
    """True se ENCRYPTION_KEY estiver setada (mesmo que invalida - nesse
    caso `_fernet()` levanta na primeira tentativa de uso, o que e
    preferivel a mascarar uma chave quebrada como "sem criptografia")."""
    return bool(os.environ.get("ENCRYPTION_KEY"))


def _fernet() -> Fernet | None:
    """Nao usa cache (lru_cache) de proposito - testes trocam ENCRYPTION_KEY
    via os.environ/monkeypatch no meio da suite, e um cache preso a primeira
    leitura ficaria com a chave errada dali pra frente."""
    chave = os.environ.get("ENCRYPTION_KEY")
    if not chave:
        return None
    return Fernet(chave.encode())


def _avisar_sem_chave():
    global _aviso_ja_logado
    if _aviso_ja_logado:
        return
    _aviso_ja_logado = True
    logger.warning(
        "ENCRYPTION_KEY nao configurada - dado do Open Finance (saldo/extrato) e de saude "
        "esta sendo gravado em TEXTO PLANO no banco. Rode "
        "'python scripts/gerar_chave_criptografia.py' e adicione ENCRYPTION_KEY ao .env pra "
        "ligar a criptografia em repouso. Ver docs/SEGURANCA.md."
    )


def criptografar(texto: str | None) -> str | None:
    """None passa direto (campo vazio no banco, ex: dosagem nao informada -
    nao ha nada pra criptografar). Sem chave, devolve o texto como veio."""
    if texto is None:
        return None
    f = _fernet()
    if f is None:
        _avisar_sem_chave()
        return texto
    return f.encrypt(texto.encode("utf-8")).decode("ascii")


def descriptografar(valor: str | None) -> str | None:
    """None passa direto. Sem chave configurada, devolve como veio (pode ser
    texto plano legado, ou pode ser um token cifrado que so vai virar texto
    de novo quando a chave voltar a estar configurada). Um valor que nao e
    um token Fernet valido (texto plano gravado antes da chave existir, ou
    gravado direto por um script/teste que bateu no banco sem passar por
    aqui) tambem e devolvido como esta, nunca derruba a leitura - preferir
    mostrar o dado "estranho" a quebrar a tela."""
    if valor is None:
        return None
    f = _fernet()
    if f is None:
        return valor
    try:
        return f.decrypt(valor.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError):
        return valor
