"""Faixa N1 (Fase 7): classificador local (sem IA) pra assinaturas e compras
parceladas. Contrato de `classificador_local/__init__.py` (Etapa 0/X1, ja
mesclada em `fase7/integracao`, ver `classificador_local/README.md`):

- `casar(texto) -> {"acao": str, "parametros": dict} | None`: so
  regex/texto, nunca banco nem rede. `casar` desta faixa resolve VARIAS
  frases (7 acoes diferentes) - como so `parametros` (nao `acao`) e
  repassado pro `executar` desta faixa pelo despachante generico
  (`classificador_local.executar`), a sub-acao interna vai DENTRO de
  `parametros["acao"]` tambem (ver `_resultado` abaixo).
- `executar(conn, parametros) -> {"cards": [...], "resumo_texto": str,
  "passos": [...]}` (formato "cards ja montados" aceito pelo contrato - o
  outro formato, `{"efeitos": [...]}`, pede um builder em
  `cards.cards_dos_efeitos` pros tipos `assinatura`/`compra_parcelada`, que
  nao existe ainda porque `cards.py` nao e desta faixa; ver
  `docs/contrato-assinaturas.md`). Nunca commita (`fr.criar_assinatura` e
  companhia ja commitam sozinhos, mesmo padrao do resto de `db.py`).

Frases cobertas (ver `docs/contrato-assinaturas.md` pro contrato completo):
- "assinei <nome> <valor>[ por mes]" / "assinei o/a <nome> por <valor>"
- "comprei <descricao> em <n>x de <valor>[ no/na <cartao>]"
- "comprei <descricao> <valor_total> em <n> vezes[ no/na <cartao>]"
- "cancelei a/o <nome>"
- "quanto tenho de parcelas?" / variantes
- "quais assinaturas eu tenho" / variantes
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation

import cards
import financas_recorrentes as fr

# ---- valor em dinheiro no texto livre ---------------------------------------
# Aceita "55", "21,90", "R$ 21,90", "3.000,00", "3000" e "21,90 reais". O
# ponto so vira separador de milhar quando aparece em grupos de 3 digitos
# (ex: "3.000") - sozinho ("21.9") seria ambiguo com decimal em ingles, mas
# o app e pt-BR, entao trata como parte de um numero inteiro grande mesmo
# (nunca decimal por ponto).
_VALOR_NUM = r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?"
VALOR_RE = rf"(?:r\$\s*)?({_VALOR_NUM})(?:\s*reais)?"


def _parse_valor(bruto: str) -> float | None:
    """Devolve `float` (nunca `Decimal`) - `parametros` desta faixa passa
    por `jsonify` sem alteracao em `/api/intent/classificar` (app.py, nao e
    meu arquivo) e no encoder JSON padrao do Flask `Decimal` nao serializa.
    `fr._d` (financas_recorrentes.py) converte de volta pra Decimal via
    `str(valor)` na hora de gravar, entao a precisao do texto original nao
    se perde por esse meio de campo."""
    texto = (bruto or "").strip()
    if not texto:
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", texto):
        texto = texto.replace(".", "")
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        return None
    if valor <= 0:
        return None
    return float(valor)


def _limpar_nome(bruto: str) -> str:
    """Tira artigo/preposicao que sobrou nas bordas do nome capturado (o
    regex e permissivo de proposito, pra achar o valor mesmo quando o nome
    tem "por"/"de" dentro, ex: "Clube de Assinatura")."""
    nome = (bruto or "").strip(" .")
    nome = re.sub(r"^(?:o|a)\s+", "", nome, flags=re.IGNORECASE)
    nome = re.sub(r"\s+por$", "", nome, flags=re.IGNORECASE)
    return nome.strip(" .")


# ---- padroes -----------------------------------------------------------

_ASSINAR_RE = re.compile(
    rf"assinei\s+(?P<nome>.+?)\s+{VALOR_RE}\s*"
    r"(?:por\s+m[eê]s|/\s*m[eê]s|mensal\w*)?",
    re.IGNORECASE,
)

_COMPRA_VALOR_TOTAL_RE = re.compile(
    rf"comprei\s+(?:o\s+|a\s+)?(?P<descricao>.+?)\s+{VALOR_RE}\s+em\s+"
    r"(?P<parcelas>\d{1,2})\s*(?:x|vezes)\s*"
    r"(?:(?:no|na)\s+(?P<cartao>.+?))?",
    re.IGNORECASE,
)

_COMPRA_VALOR_PARCELA_RE = re.compile(
    r"comprei\s+(?:o\s+|a\s+)?(?P<descricao>.+?)\s+em\s+"
    rf"(?P<parcelas>\d{{1,2}})\s*(?:x|vezes)\s+de\s+{VALOR_RE}\s*"
    r"(?:(?:no|na)\s+(?P<cartao>.+?))?",
    re.IGNORECASE,
)

_CANCELAR_RE = re.compile(r"cancelei\s+(?:a\s+|o\s+)?(?P<nome>.+?)", re.IGNORECASE)

_CONSULTA_PARCELAS_RE = re.compile(
    r"quant[oa]s?\s+(?:eu\s+)?tenho\s+de\s+(?:compras?\s+)?parcelas?\??"
    r"|quantas?\s+parcelas?\s+(?:eu\s+)?tenho\??"
    r"|(?:e\s+)?(?:minhas?\s+)?parcelas?\??",
    re.IGNORECASE,
)

_CONSULTA_ASSINATURAS_RE = re.compile(
    r"quais\s+assinaturas?\s+(?:eu\s+)?tenho\??"
    r"|quanto\s+(?:eu\s+)?gasto\s+(?:com|de)\s+assinaturas?\??"
    r"|(?:minhas?\s+)?assinaturas?\??",
    re.IGNORECASE,
)


def _resultado(acao: str, **campos) -> dict:
    """Formato exigido por `classificador_local.__init__.executar`: so
    `parametros` (nao `acao`) e repassado pro `executar` desta faixa, entao
    a sub-acao vai dentro dele tambem, pra dar pra despachar la."""
    parametros = {"acao": acao, **campos}
    return {"acao": acao, "parametros": parametros}


def casar(texto: str) -> dict | None:
    """`re.fullmatch` na frase INTEIRA (menos pontuacao solta no fim) - regra
    estrita, pra nunca roubar frase de outra faixa. Devolve `None` se nada
    daqui bateu."""
    if not isinstance(texto, str):
        return None
    texto_norm = texto.strip().rstrip(".!")
    if not texto_norm:
        return None

    m = _CANCELAR_RE.fullmatch(texto_norm)
    if m:
        nome = _limpar_nome(m.group("nome"))
        if nome:
            return _resultado("cancelar_assinatura", nome=nome)

    m = _ASSINAR_RE.fullmatch(texto_norm)
    if m:
        valor = _parse_valor(m.group(2))
        nome = _limpar_nome(m.group("nome"))
        if valor is not None and nome:
            return _resultado("criar_assinatura", nome=nome, valor=valor)

    m = _COMPRA_VALOR_TOTAL_RE.fullmatch(texto_norm)
    if m:
        valor = _parse_valor(m.group(2))
        n_parcelas = int(m.group("parcelas"))
        descricao = _limpar_nome(m.group("descricao"))
        if valor is not None and descricao and n_parcelas > 0:
            return _resultado(
                "criar_compra_parcelada",
                descricao=descricao,
                valor_total=valor,
                n_parcelas=n_parcelas,
                cartao=(m.group("cartao") or "").strip(" .") or None,
            )

    m = _COMPRA_VALOR_PARCELA_RE.fullmatch(texto_norm)
    if m:
        valor = _parse_valor(m.group(3))
        n_parcelas = int(m.group("parcelas"))
        descricao = _limpar_nome(m.group("descricao"))
        if valor is not None and descricao and n_parcelas > 0:
            return _resultado(
                "criar_compra_parcelada",
                descricao=descricao,
                valor_parcela=valor,
                n_parcelas=n_parcelas,
                cartao=(m.group("cartao") or "").strip(" .") or None,
            )

    if _CONSULTA_PARCELAS_RE.fullmatch(texto_norm):
        return _resultado("consultar_parcelas")

    if _CONSULTA_ASSINATURAS_RE.fullmatch(texto_norm):
        return _resultado("consultar_assinaturas")

    return None


# ---- execucao ------------------------------------------------------------


# C1: os builders moram em cards.py (fonte unica dos tipos de card); aqui so
# repassa, pra este arquivo e o resto do app montarem o card do mesmo jeito.
def _card_assinatura(a: dict, hoje: date, *, consulta: bool = False, actions: list | None = None) -> dict:
    return cards.assinatura_para_card(a, hoje, consulta=consulta, actions=actions)


def _card_compra_parcelada(c: dict, hoje: date, *, consulta: bool = False, actions: list | None = None) -> dict:
    return cards.compra_parcelada_para_card(c, hoje, consulta=consulta, actions=actions)


def _card_resumo(conn: sqlite3.Connection, hoje: date) -> dict:
    return cards.card_resumo_financeiro_recorrente(conn, hoje)


def _fmt_valor(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def executar(conn: sqlite3.Connection, parametros: dict, hoje: date | None = None) -> dict:
    """`hoje` e sempre injetavel (nunca `date.today()` direto aqui dentro -
    mesma regra dos gatilhos do assistente, pra dar pra testar)."""
    hoje = hoje or date.today()
    acao = (parametros or {}).get("acao")

    if acao == "criar_assinatura":
        return _executar_criar_assinatura(conn, parametros, hoje)
    if acao == "cancelar_assinatura":
        return _executar_cancelar_assinatura(conn, parametros, hoje)
    if acao == "criar_compra_parcelada":
        return _executar_criar_compra_parcelada(conn, parametros, hoje)
    if acao == "consultar_parcelas":
        return _executar_consultar_parcelas(conn, hoje)
    if acao == "consultar_assinaturas":
        return _executar_consultar_assinaturas(conn, hoje)
    return cards.envelope([], "Não entendi esse comando de assinatura/parcela.", [])


def _executar_criar_assinatura(conn, parametros: dict, hoje: date) -> dict:
    aid = fr.criar_assinatura(
        conn,
        parametros["nome"],
        parametros["valor"],
        hoje.day,
        cartao_ou_forma=parametros.get("cartao_ou_forma"),
        categoria=parametros.get("categoria"),
        hoje=hoje,
    )
    a = fr.obter_assinatura(conn, aid)
    token = fr.criar_token_desfazer(conn, "assinatura", "criar", aid)
    actions = [cards.acao_desfazer(token, [{"entidade": "assinatura", "id": aid}])]
    card = _card_assinatura(a, hoje, actions=actions)
    resumo_texto = f'Assinatura "{a["nome"]}" criada: {_fmt_valor(a["valor"])} por mês.'
    return cards.envelope([card], resumo_texto, [])


def _executar_cancelar_assinatura(conn, parametros: dict, hoje: date) -> dict:
    a = fr.buscar_assinatura_por_nome(conn, parametros["nome"], apenas_ativas=True)
    if not a:
        return cards.envelope(
            [], f'Não encontrei nenhuma assinatura ativa chamada "{parametros["nome"]}".', []
        )
    fr.cancelar_assinatura(conn, a["id"], hoje)
    a = fr.obter_assinatura(conn, a["id"])
    token = fr.criar_token_desfazer(conn, "assinatura", "cancelar", a["id"])
    actions = [cards.acao_desfazer(token, [{"entidade": "assinatura", "id": a["id"]}])]
    card = _card_assinatura(a, hoje, actions=actions)
    resumo_texto = f'Assinatura "{a["nome"]}" cancelada.'
    return cards.envelope([card], resumo_texto, [])


def _executar_criar_compra_parcelada(conn, parametros: dict, hoje: date) -> dict:
    cid = fr.criar_compra_parcelada(
        conn,
        parametros["descricao"],
        parametros["n_parcelas"],
        valor_total=parametros.get("valor_total"),
        valor_parcela=parametros.get("valor_parcela"),
        cartao=parametros.get("cartao"),
        hoje=hoje,
    )
    c = fr.obter_compra_parcelada(conn, cid)
    token = fr.criar_token_desfazer(conn, "compra_parcelada", "criar", cid)
    actions = [cards.acao_desfazer(token, [{"entidade": "compra_parcelada", "id": cid}])]
    card = _card_compra_parcelada(c, hoje, actions=actions)
    resumo_texto = (
        f'Compra "{c["descricao"]}" em {c["n_parcelas"]}x de {_fmt_valor(c["valor_parcela"])} registrada.'
    )
    return cards.envelope([card], resumo_texto, [])


def _executar_consultar_parcelas(conn, hoje: date) -> dict:
    compras = fr.listar_compras_parceladas(conn, apenas_em_andamento=True, hoje=hoje)
    lista_cards = [_card_compra_parcelada(c, hoje, consulta=True) for c in compras]
    resumo_card = _card_resumo(conn, hoje)
    total = resumo_card["data"]["parcelas_total"]
    if not compras:
        resumo_texto = "Você não tem nenhuma compra parcelada em andamento."
    else:
        plural = "s" if len(compras) != 1 else ""
        resumo_texto = f"Você tem {len(compras)} compra{plural} parcelada{plural} em andamento, {_fmt_valor(total)} por mês."
    return cards.envelope([resumo_card, *lista_cards], resumo_texto, [])


def _executar_consultar_assinaturas(conn, hoje: date) -> dict:
    assinaturas = fr.listar_assinaturas(conn, apenas_ativas=True)
    lista_cards = [_card_assinatura(a, hoje, consulta=True) for a in assinaturas]
    resumo_card = _card_resumo(conn, hoje)
    total = resumo_card["data"]["assinaturas_total"]
    if not assinaturas:
        resumo_texto = "Você não tem nenhuma assinatura ativa."
    else:
        plural = "s" if len(assinaturas) != 1 else ""
        resumo_texto = f"Você tem {len(assinaturas)} assinatura{plural} ativa{plural}, {_fmt_valor(total)} por mês."
    return cards.envelope([resumo_card, *lista_cards], resumo_texto, [])
