"""Regra local (Fase 7, faixa A10): "tomei um copo de agua" (e variacoes)
registra hidratacao SEM IA, pela MESMA funcao que o botao "+1 copo de agua"
usa (`db.registrar_hidratacao` - ver `POST /api/hidratacao` em `app.py`).

Casa frases como: "tomei um copo de agua", "bebi agua", "tomei um copo
d'agua", "mais um copo", "mais um copo de agua", "+1 agua", "+1 copo",
"tomei 2 copos", "bebi 3 copos de agua", "tomei mais um copo" - e as mesmas
em maiusculo/com acento/sem acento/com pontuacao final (".", "!").

NAO casa frases que so mencionam "agua" sem acao de beber: "conta de agua",
"agua sanitaria", "agua mineral" (produto), "tomei um copo de suco" (bebida
diferente) - o `casar` e estrito de proposito (fullmatch, nunca so um
`search`) pra nao "roubar" essas frases da IA ou de outra regra.

"tomei N copos" registra N linhas em `hidratacao_registros` (N chamadas de
`registrar_hidratacao`, mesma funcao do botao) - cada uma vira o proprio
efeito `{"entidade": "hidratacao", "id": ...}`, e o contrato do
classificador (`classificador_local/__init__.py`) transforma isso em N
cards `saude_dia`, cada um com o proprio Desfazer independente (mesmo
espirito de "brain dump" de docs/CARDS.md: cards da mesma resposta tem
tokens de Desfazer proprios). `N` e limitado a `_QUANTIDADE_MAXIMA` (guarda
contra typo/fuzzing tipo "tomei 9999 copos" virar 9999 linhas no banco).
"""

from __future__ import annotations

import re
from datetime import date

from db import registrar_hidratacao

_NUM_PALAVRA = {
    "um": 1,
    "uma": 1,
    "dois": 2,
    "duas": 2,
    "tres": 3,
    "três": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
    "dez": 10,
}

_QUANTIDADE_MAXIMA = 20

_NUM = r"(?P<num>\d{1,4}|um|uma|dois|duas|tr[eê]s|quatro|cinco|seis|sete|oito|nove|dez)"
_VERBO = r"(?:tomei|bebi)"
_AGUA = r"[aá]gua"
# "copo de agua" / "copo d'agua" / so "copo" (contexto ja e hidratacao -
# "tomei 2 copos" sozinho tambem conta, mesma decisao do exemplo da faixa)
_DE_AGUA_OPC = rf"(?:\s+(?:de\s+|d['’]?\s*){_AGUA})?"
_COPOS = rf"copos?{_DE_AGUA_OPC}"

# Ordem nao importa aqui (cada padrao e fullmatch da frase inteira) - so a
# primeira que bater decide a quantidade.
_PADROES = [
    re.compile(rf"{_VERBO}\s+(?:mais\s+)?{_NUM}\s+{_COPOS}", re.IGNORECASE),  # tomei um copo (de agua); tomei 2 copos
    re.compile(rf"mais\s+{_NUM}\s+{_COPOS}", re.IGNORECASE),  # mais um copo; mais 2 copos de agua
    re.compile(rf"\+\s*{_NUM}\s+{_COPOS}", re.IGNORECASE),  # +1 copo; +1 copo de agua
    re.compile(rf"\+\s*{_NUM}\s+{_AGUA}", re.IGNORECASE),  # +1 agua; +2 agua
    re.compile(rf"{_VERBO}\s+(?:mais\s+)?{_AGUA}", re.IGNORECASE),  # bebi agua; tomei agua; bebi mais agua
    re.compile(r"mais\s+" + _AGUA, re.IGNORECASE),  # mais agua
]


def _extrair_quantidade(texto_normalizado: str) -> int | None:
    """None = a frase nao e sobre beber agua. Senao a quantidade de copos
    (>=1, clampada em _QUANTIDADE_MAXIMA)."""
    for padrao in _PADROES:
        m = padrao.fullmatch(texto_normalizado)
        if not m:
            continue
        bruto = m.groupdict().get("num")
        if bruto is None:
            return 1  # padrao sem numero explicito ("bebi agua") = 1 copo
        quantidade = int(bruto) if bruto.isdigit() else _NUM_PALAVRA.get(bruto.lower())
        if not quantidade or quantidade < 1:
            return None  # "tomei 0 copos" nao e uma acao de verdade
        return min(quantidade, _QUANTIDADE_MAXIMA)
    return None


def casar(texto):
    """Rapido e sem efeito colateral: so texto, nunca banco nem rede."""
    if not isinstance(texto, str):
        return None
    normalizado = " ".join(texto.split()).rstrip(".!")
    if not normalizado:
        return None
    quantidade = _extrair_quantidade(normalizado)
    if quantidade is None:
        return None
    return {
        "acao": "registrar_hidratacao_a10",
        "confianca": 1.0,
        "parametros": {"quantidade": quantidade},
    }


def executar(conn, parametros):
    """Faz a acao SEM commit (quem chama commita) - mesma funcao
    `db.registrar_hidratacao` do botao "+1 copo de agua". Devolve os
    efeitos no formato `_efeito` de docs/CARDS.md (um por copo registrado),
    viram os mesmos cards `saude_dia` do chat, cada um com Desfazer."""
    quantidade = parametros.get("quantidade") if isinstance(parametros, dict) else None
    if not isinstance(quantidade, int) or isinstance(quantidade, bool) or quantidade < 1:
        quantidade = 1
    quantidade = min(quantidade, _QUANTIDADE_MAXIMA)

    hoje = date.today().isoformat()
    efeitos = []
    total_hoje = None
    for _ in range(quantidade):
        total_hoje = registrar_hidratacao(conn, hoje)
        registro_id = conn.execute(
            "SELECT MAX(id) AS id FROM hidratacao_registros WHERE data = ?", (hoje,)
        ).fetchone()["id"]
        efeitos.append({"entidade": "hidratacao", "id": registro_id})

    resumo_texto = (
        f"+1 copo de água. {total_hoje} hoje."
        if quantidade == 1
        else f"+{quantidade} copos de água. {total_hoje} hoje."
    )
    return {"efeitos": efeitos, "resumo_texto": resumo_texto}
