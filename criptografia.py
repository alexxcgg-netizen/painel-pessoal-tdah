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

import binascii
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_aviso_sem_chave_ja_logado = False
_aviso_chave_invalida_ja_logado = False


def configurada() -> bool:
    """True so quando ENCRYPTION_KEY esta presente E e uma chave Fernet
    valida. Uma chave malformada (colada errada no .env, truncada, aspas
    sobrando) e tratada como "sem criptografia" por `_fernet()` - entao
    tambem nao conta aqui como "configurada", pra quem decide se roda a
    migracao de dado existente (db.py) nao marcar como concluido um trabalho
    que na verdade nao aconteceu (ver achado da revisao independente
    abaixo)."""
    return _fernet() is not None


def _fernet() -> Fernet | None:
    """Nao usa cache (lru_cache) de proposito - testes trocam ENCRYPTION_KEY
    via os.environ/monkeypatch no meio da suite, e um cache preso a primeira
    leitura ficaria com a chave errada dali pra frente.

    Nunca levanta: ENCRYPTION_KEY ausente OU malformada (nao e uma chave
    Fernet valida de 32 bytes urlsafe-base64) devolvem None do mesmo jeito -
    achado de revisao independente: antes, uma chave malformada com dado
    sensivel ja gravado derrubava o app inteiro na subida (a migracao em
    db.py chamava criptografar() dentro de um loop sem try/except em volta).
    Preferir continuar funcionando com um aviso bem visivel a um app pessoal
    que nunca mais sobe por causa de um erro de copiar/colar no .env."""
    chave = os.environ.get("ENCRYPTION_KEY")
    if not chave:
        return None
    try:
        return Fernet(chave.encode())
    except (ValueError, TypeError, binascii.Error):
        _avisar_chave_invalida()
        return None


def _avisar_sem_chave():
    global _aviso_sem_chave_ja_logado
    if _aviso_sem_chave_ja_logado:
        return
    _aviso_sem_chave_ja_logado = True
    logger.warning(
        "ENCRYPTION_KEY nao configurada - dado do Open Finance (saldo/extrato) e de saude "
        "esta sendo gravado em TEXTO PLANO no banco. Rode "
        "'python scripts/gerar_chave_criptografia.py' e adicione ENCRYPTION_KEY ao .env pra "
        "ligar a criptografia em repouso. Ver docs/SEGURANCA.md."
    )


def _avisar_chave_invalida():
    global _aviso_chave_invalida_ja_logado
    if _aviso_chave_invalida_ja_logado:
        return
    _aviso_chave_invalida_ja_logado = True
    logger.warning(
        "ENCRYPTION_KEY configurada mas INVALIDA (nao e uma chave Fernet de 32 bytes "
        "urlsafe-base64 - confere se nao colou faltando/sobrando caractere no .env). "
        "Tratando como se nao tivesse chave nenhuma: dado do Open Finance e de saude "
        "esta sendo gravado em TEXTO PLANO no banco. Gere uma chave nova com "
        "'python scripts/gerar_chave_criptografia.py'. Ver docs/SEGURANCA.md."
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
