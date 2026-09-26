"""P5 - sugestao automatica das 14h: se houver tarefa atrasada, propoe
"Quer replanejar a tarde?" na Caixa do assistente.

Flag `replanejar_auto` **DESLIGADA por padrao** (pedido explicito desta
historia - foge do padrao geral "ligado" de
`docs/agentes/fase7-assistente.md` ("Flags"), que a propria doc permite
quando o prompt da faixa disser outra coisa).

Segue `docs/agentes/fase7-assistente.md`:
- roda a partir do tick (`POST /api/tick`, faixa P1a) via `executar(conn,
  agora)` - `agora` e' sempre injetado, nunca `datetime.now()` aqui dentro,
  pra dar pra testar.
- import tardio de `assistente.caixa.enfileirar` (a P1a pode nao existir
  ainda nesta integracao).
- idempotente via `chave_unica` datada - se o tick rodar varias vezes
  dentro da mesma hora/dia, `enfileirar` sozinho evita duplicar o item
  (contrato em `assistente/contrato.py`).
"""

from __future__ import annotations

from datetime import datetime

import db
import notificacoes

FLAG_CHAVE = "replanejar_auto"
CAIXA_TIPO = "sugestao"
CAIXA_TITULO = "Quer replanejar a tarde?"
CAIXA_CORPO = "Você tem tarefas atrasadas hoje - da pra reorganizar o resto do dia."
CAIXA_ORIGEM = "p5_replanejar"

# So dispara nessa hora do dia (14h) - o tick pode rodar varias vezes
# dentro da mesma hora; `chave_unica` (abaixo) e' quem evita duplicar.
HORA_SUGESTAO = 14


def flag_ativa(conn) -> bool:
    """Padrao DESLIGADO - diferente do padrao geral "ligado" das faixas P
    (pedido explicito desta historia, ver docstring do modulo)."""
    return db.obter_configuracao(conn, FLAG_CHAVE) == "1"


def definir_flag(conn, ativo: bool) -> None:
    db.definir_configuracao(conn, FLAG_CHAVE, "1" if ativo else "0")


def executar(conn, agora: datetime) -> None:
    if agora.hour != HORA_SUGESTAO:
        return
    if not flag_ativa(conn):
        return
    if not notificacoes.tarefas_atrasadas(conn):
        return

    from assistente.caixa import enfileirar  # tardio (P1a pode nao existir ainda)

    enfileirar(
        CAIXA_TIPO,
        CAIXA_TITULO,
        CAIXA_CORPO,
        origem=CAIXA_ORIGEM,
        chave_unica=f"{CAIXA_ORIGEM}_14h:{agora.date().isoformat()}",
    )


def _agora_atual() -> datetime:
    """Seam pra teste (o contrato de `ao_resolver` nao recebe `agora` -
    ver docs/agentes/fase7-assistente.md, "API" - entao aqui e' o unico
    lugar deste modulo que chama `datetime.now()`, e so nesse ponto de
    entrada especifico)."""
    return datetime.now()


def ao_resolver(conn, item: dict, resposta: str, texto: str = "") -> None:
    """Chamado pela P1a (`assistente/caixa.py`) quando o Alex responde a
    sugestao das 14h (mecanismo descrito em
    docs/agentes/fase7-assistente.md, "API" - `origem` do item aponta de
    volta pra este modulo). "sim"/"aceitar" dispara o mesmo replanejamento
    da frase de chat; qualquer outra resposta ("nao"/"adiar"/"recusar")
    nao faz nada aqui - adiar/repetir e' todo mecanismo da propria P1a."""
    if resposta not in ("sim", "aceitar"):
        return

    from classificador_local.regras.p5_replanejar import executar as executar_replanejamento

    executar_replanejamento(conn, {"agora": _agora_atual()})
