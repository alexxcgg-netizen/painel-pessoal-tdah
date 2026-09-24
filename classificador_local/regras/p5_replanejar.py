"""P5 - Replanejar o dia: reconhece frases como "replaneja meu dia",
"atrasei", "perdi a manha" (sem IA nenhuma - so regex sobre texto
normalizado) e monta o card do contrato (`docs/CARDS.md`:
`{cards, resumo_texto, passos}`) com o novo plano e as acoes Aplicar/
Desfazer.

`casar(texto)` / `executar(conn, parametros)` seguem o contrato de
`docs/agentes/fase7-regras-faixa.md` ("Frase resolvida sem IA"). O motor
que descobre e chama esses dois automaticamente
(`classificador_local/*`, fora dos arquivos desta faixa) ainda nao existe
nesta integracao - chega pela Etapa 0 (X1); ate la, quem quiser usar isto
chama `casar`/`executar` direto (e' o que os testes desta faixa fazem).

A logica de coleta/persistencia mora em `assistente/replanejar.py` - este
modulo so cuida de reconhecer a frase e montar o card."""

from __future__ import annotations

import re
import time
import unicodedata
from datetime import datetime

import cards

from assistente import replanejar


def _normalizar(texto: str) -> str:
    """minusculas + sem acento, pra "perdi a manhã" e "perdi a manha"
    caírem no mesmo padrão."""
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower().strip()


# Frases comuns em pt-BR pra pedir o replanejamento do dia - cada padrao e'
# testado contra o texto ja normalizado (minusculo, sem acento). Aditivo:
# variacao nova de frase entra como um padrao novo na tupla, nunca edita um
# existente (mesma regra de evolucao do docs/CARDS.md/INTENT.md).
_PADROES = (
    re.compile(r"\breplaneja\w*\s+(o\s+|meu\s+)?dia\b"),
    re.compile(r"\breplaneja\w*\s+(a\s+)?tarde\b"),
    re.compile(r"\breorganiz\w*\s+(o\s+|meu\s+)?dia\b"),
    re.compile(r"\breordena\w*\s+(o\s+que\s+resta\s+d[oe]\s+|o\s+|meu\s+)?dia\b"),
    re.compile(r"\bmexer\s+na\s+ordem\s+do\s+dia\b"),
    re.compile(r"\bmuda\w*\s+a\s+ordem\s+do\s+dia\b"),
    re.compile(r"\bme\s+atrasei\b"),
    re.compile(r"\batrasei\b"),
    re.compile(r"\bfiquei\s+atrasad[oa]\b"),
    re.compile(r"\bestou\s+atrasad[oa]\b"),
    re.compile(r"\bto\s+atrasad[oa]\b"),
    re.compile(r"\bperdi\s+a\s+manha\b"),
    re.compile(r"\bperdi\s+o\s+dia\b"),
    re.compile(r"\bperdi\s+a\s+hora\b"),
    re.compile(r"\bbaguncou\s+(o\s+|meu\s+)?dia\b"),
    re.compile(r"\bdia\s+baguncou\b"),
    re.compile(r"\bmeu\s+dia\s+virou\s+bagunca\b"),
    re.compile(r"\brecomec\w*\s+(o\s+|meu\s+)?dia\b"),
)


def casar(texto: str) -> dict | None:
    """None se nao reconhecer nada; um dict de parametros (vazio, hoje -
    `executar` injeta `agora` sozinho quando quem chamou nao mandou) se
    reconhecer um pedido de replanejamento."""
    normalizado = _normalizar(texto)
    if not normalizado:
        return None
    for padrao in _PADROES:
        if padrao.search(normalizado):
            return {}
    return None


def _resumo(proposta: dict) -> str:
    n_tarefas = len(proposta["tarefas"])
    if n_tarefas == 0:
        return "Reorganizei o resto do seu dia."
    if n_tarefas == 1:
        return "Reorganizei o resto do seu dia - sobrou 1 tarefa pra encaixar."
    return f"Reorganizei o resto do seu dia - sobraram {n_tarefas} tarefas pra encaixar."


def executar(conn, parametros: dict | None = None) -> dict:
    """Monta e ja aplica o replanejamento (a frase reconhecida - "replaneja
    meu dia", "atrasei" - ja e' um pedido imperativo, nao so uma pergunta;
    mesmo espirito de outras acoes do chat que escrevem na hora e devolvem
    Desfazer). `parametros["agora"]` e' opcional (injetado por quem chama
    testes/gatilho; sem ele cai em `datetime.now()`, unico ponto deste
    modulo que faz isso - inevitavel aqui, ja que `casar` nao tem como
    saber a hora sozinho)."""
    parametros = parametros or {}
    agora = parametros.get("agora") or datetime.now()

    if not replanejar.teto_permite(replanejar.NOME_FUNCAO_IA):
        return cards.envelope(
            [],
            "O teto mensal de gasto com IA estourou esse mes - nao consigo montar um novo plano agora "
            "(da pra ajustar o teto no card financeiro).",
            [
                {
                    "modulo": "Assistente",
                    "descricao": "Replanejar bloqueado pelo teto de IA",
                    "ms": 0,
                    "erro": True,
                }
            ],
        )

    inicio = time.perf_counter()
    proposta = replanejar.propor_plano(conn, agora)
    dia_iso = agora.date().isoformat()
    token = replanejar.aplicar_plano(conn, dia_iso, proposta["plano_texto"])
    ms = int(round((time.perf_counter() - inicio) * 1000))

    card = cards.novo_card(
        "replanejamento",
        {
            "dia": dia_iso,
            "agora": proposta["agora"],
            "plano_texto": proposta["plano_texto"],
            "tarefas": proposta["tarefas"],
            "eventos": [
                {
                    "titulo": e.get("titulo"),
                    "inicio": e.get("inicio"),
                    "dia_inteiro": bool(e.get("dia_inteiro")),
                }
                for e in proposta["eventos"]
            ],
            "aplicado": True,
        },
        actions=[
            # "Aplicar" fica aqui por pedido explicito da historia mesmo o
            # executar() ja tendo aplicado sozinho (frase = pedido
            # imperativo) - front/rota que ligar este botao pode tratar
            # como "reaplicar o mesmo plano" (chamando de novo
            # replanejar.aplicar_plano com este plano_texto) sem duplicar
            # logica. Ver scripts/ralph-p5-replanejar/APRENDIZADOS.md.
            {"tipo": "aplicar_replanejamento", "rotulo": "Aplicar", "dia": dia_iso, "ja_aplicado": True},
            {"tipo": "desfazer_replanejamento", "rotulo": "Desfazer", "token": token, "dia": dia_iso},
        ],
    )
    passos = [
        {
            "modulo": "Assistente",
            "descricao": f"Replanejou o resto do dia a partir das {proposta['agora']}",
            "ms": ms,
        }
    ]
    return cards.envelope([card], _resumo(proposta), passos)
