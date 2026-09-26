"""P5 - Replanejar o dia (Fase 7, faixa `p5-replanejar`).

Logica pura de coleta e persistencia do replanejamento: junta o que resta
do dia (tarefas de hoje ainda nao feitas + agenda restante a partir da hora
atual), chama a funcao de IA `plano_do_dia` pra montar o novo plano, e
grava/desfaz esse plano como a "ordem do dia" vigente.

O reconhecimento de frase ("replaneja meu dia", "atrasei"...) e a montagem
do card do contrato ficam em
`classificador_local/regras/p5_replanejar.py`, que importa deste modulo -
nunca o contrario (este modulo nao sabe nada de card/texto de usuario).

Onde `plano_do_dia` mora: hoje em `claude_client.plano_do_dia`. A Etapa 0
(fase7-regras-faixa.md) promete mover as funcoes de IA pra
`ia/funcoes/{chat,captura,planejamento,visao}.py` e reexportar em
`claude_client` como fachada - por isso chamamos sempre via
`claude_client.plano_do_dia` (funciona nos dois casos, antes e depois
dessa migracao futura).

Teto de IA: a rota `POST /api/plano-do-dia` de hoje (`app.py`) NAO checa o
teto mensal de IA antes de chamar `claude_client.plano_do_dia` (conferido:
nenhum `resumo_custo_api`/`_TETO_IA_LOCK`/`ia.teto` por perto daquela rota -
so os outros caminhos de IA do app checam isso). Por isso `propor_plano`
abaixo checa explicitamente via `ia.teto.teto_permite("plano_do_dia")`
antes de gastar uma chamada - anotado tambem em
`scripts/ralph-p5-replanejar/APRENDIZADOS.md` pro integrador avaliar se
vale corrigir a rota antiga tambem (fora dos arquivos desta faixa).

Onde a "ordem do dia" fica guardada: nao existe (ainda) uma tabela/coluna
de ordem ou horario replanejado por tarefa em `db.py` - so due_date/hora
por tarefa, sem nocao de posicao relativa entre elas nem de "plano do dia
aplicado". Por isso usamos a tabela generica `configuracoes`
(`db.obter_configuracao`/`db.definir_configuracao`, ja existentes), com uma
chave por dia (`p5_ordem_dia:AAAA-MM-DD`). Anotado pro integrador: se uma
faixa futura criar uma forma de verdade de guardar ordem/horario por
tarefa, migrar o que estiver aqui pra la.
"""

from __future__ import annotations

import json
import secrets
import time
from datetime import date, datetime

import claude_client  # plano_do_dia mora aqui hoje (fachada apos a Etapa 0)
import db

try:
    import caldav_client
except ImportError:  # pragma: no cover - so falta em ambiente minimo de teste
    caldav_client = None

try:
    from ia.teto import teto_permite
except ImportError:  # pragma: no cover - infra da Etapa 0 (faixa A4) ainda
    # nao mergeada nesta branch - sem teto nenhum configurado, nunca bloqueia
    # (mesmo comportamento de "sem teto" que o restante do app tinha antes
    # da A4 existir).
    def teto_permite(_funcao: str) -> bool:
        return True


class TetoEstouradoError(RuntimeError):
    """Levantada por `propor_plano` quando o teto mensal de IA ja estourou
    pra funcoes caras (mesmo texto de `ia.teto.TETO_IA_MSG`/`app.TETO_IA_MSG`,
    copiado aqui pelo mesmo motivo dos dois: nao criar import circular)."""


NOME_FUNCAO_IA = "plano_do_dia"

TETO_ESTOURADO_MSG = (
    "teto mensal de gasto com IA estourado - tente de novo mês que vem ou ajuste o teto no card financeiro"
)

_CHAVE_ORDEM_PREFIXO = "p5_ordem_dia"
_CHAVE_DESFAZER_PREFIXO = "p5_desfazer"


def _chave_ordem(dia_iso: str) -> str:
    return f"{_CHAVE_ORDEM_PREFIXO}:{dia_iso}"


def _chave_desfazer(token: str) -> str:
    return f"{_CHAVE_DESFAZER_PREFIXO}:{token}"


def tarefas_pendentes_hoje(conn, hoje: date) -> list[dict]:
    """Tarefas de hoje (due_date == hoje) ainda nao concluidas, com ou sem
    hora marcada - inclui as que ja passaram do horario de proposito (e'
    justamente o que 'atrasei'/'perdi a manha' precisa achar pra reencaixar
    no resto do dia). Rotina recorrente (linha-modelo, due_date sempre
    NULL) nunca aparece sozinha aqui, so a instancia materializada do dia
    (mesmo criterio de `app._tarefas_com_horario_hoje`)."""
    dia_iso = hoje.isoformat()
    rows = conn.execute(
        "SELECT id, title, hora FROM tasks WHERE completed_at IS NULL AND due_date = ? "
        "ORDER BY hora IS NULL, hora",
        (dia_iso,),
    ).fetchall()
    return [{"id": r["id"], "titulo": r["title"], "hora": r["hora"]} for r in rows]


def agenda_restante_hoje(conn, agora: datetime) -> list[dict]:
    """Compromissos de hoje que ainda nao comecaram (inicio >= agora, ou
    dia inteiro). Resiliente a falha/ausencia do iCloud - mesmo espirito de
    `app._eventos_de_hoje_com_seguranca`, nao pode quebrar o replanejamento
    por causa de uma instabilidade do CalDAV."""
    eventos = []
    if caldav_client is not None:
        try:
            if caldav_client.configurado():
                eventos = caldav_client.eventos_do_dia(agora.date())
        except Exception:
            eventos = []
    agora_hhmm = agora.strftime("%H:%M")
    restantes = []
    for evento in eventos:
        if evento.get("dia_inteiro"):
            restantes.append(evento)
            continue
        inicio = evento.get("inicio") or ""
        hora_inicio = inicio[11:16] if len(inicio) >= 16 else None
        if hora_inicio is None or hora_inicio >= agora_hhmm:
            restantes.append(evento)
    return restantes


def coletar_restante_do_dia(conn, agora: datetime) -> dict:
    """O que resta do dia a partir de `agora`: tarefas de hoje nao feitas +
    agenda restante (so o que ainda vai comecar) + a propria hora atual."""
    return {
        "agora": agora.strftime("%H:%M"),
        "tarefas": tarefas_pendentes_hoje(conn, agora.date()),
        "eventos": agenda_restante_hoje(conn, agora),
    }


def propor_plano(conn, agora: datetime) -> dict:
    """Monta o texto do novo plano via IA (`claude_client.plano_do_dia`),
    SEM gravar nada ainda (so propoe - quem decide aplicar chama
    `aplicar_plano` depois). Levanta `TetoEstouradoError` se o teto mensal
    de IA ja estourou pra essa funcao."""
    if not teto_permite(NOME_FUNCAO_IA):
        raise TetoEstouradoError(TETO_ESTOURADO_MSG)
    restante = coletar_restante_do_dia(conn, agora)
    memorias = db.list_memorias(conn)
    plano_texto, usage = claude_client.plano_do_dia(
        [t["titulo"] for t in restante["tarefas"]],
        restante["eventos"],
        [m["texto"] for m in memorias],
    )
    db.record_usage(
        conn, usage["model"], usage["input_tokens"], usage["output_tokens"], usage["cost_usd"], "p5_replanejar"
    )
    return {**restante, "plano_texto": plano_texto}


def aplicar_plano(conn, dia_iso: str, plano_texto: str) -> str:
    """Grava `plano_texto` como a ordem do dia vigente (chave por dia em
    `configuracoes`) e devolve um token de desfazer (guarda o valor
    anterior, se houver, pra poder restaurar). Um token so pode ser usado
    uma vez (mesmo espirito do `desfazer` generico do resto do app -
    `db.criar_acao_desfazer`/`obter_acao_desfazer` -, so que sem entrar em
    `ENTIDADES_DESFAZIVEIS`, que este modulo nao pode editar)."""
    anterior = db.obter_configuracao(conn, _chave_ordem(dia_iso))
    token = secrets.token_urlsafe(16)
    db.definir_configuracao(
        conn, _chave_desfazer(token), json.dumps({"dia": dia_iso, "anterior": anterior})
    )
    db.definir_configuracao(
        conn,
        _chave_ordem(dia_iso),
        json.dumps(
            {"plano_texto": plano_texto, "aplicado_em": datetime.now().isoformat(timespec="seconds")}
        ),
    )
    return token


def desfazer_plano(conn, token: str) -> bool:
    """Restaura a ordem do dia anterior a aplicacao marcada por `token`.
    Devolve False se o token nao existe ou ja foi usado (o token e'
    apagado apos o uso - equivalente ao 404/409 do desfazer generico, so
    que aqui os dois casos colapsam num unico False pra quem chama tratar
    como preferir)."""
    bruto = db.obter_configuracao(conn, _chave_desfazer(token))
    if not bruto:
        return False
    dados = json.loads(bruto)
    if dados.get("anterior"):
        db.definir_configuracao(conn, _chave_ordem(dados["dia"]), dados["anterior"])
    else:
        db.definir_configuracao(conn, _chave_ordem(dados["dia"]), "")
    db.definir_configuracao(conn, _chave_desfazer(token), "")
    return True


def ordem_do_dia(conn, dia_iso: str) -> dict | None:
    """Le a ordem/plano vigente pro dia, ou None se nunca foi aplicado ou
    se foi desfeito."""
    bruto = db.obter_configuracao(conn, _chave_ordem(dia_iso))
    if not bruto:
        return None
    return json.loads(bruto)


def replanejar_e_aplicar(conn, agora: datetime) -> dict:
    """Atalho usado pelo classificador local (frase reconhecida = pedido
    explicito e imperativo do Alex, "replaneja meu dia" ja significa
    aplicar, nao so sugerir): propoe e aplica na mesma chamada, cronometra
    (pra virar `passos` do card) e devolve tudo que o card precisa."""
    inicio = time.perf_counter()
    proposta = propor_plano(conn, agora)
    dia_iso = agora.date().isoformat()
    token = aplicar_plano(conn, dia_iso, proposta["plano_texto"])
    ms = int(round((time.perf_counter() - inicio) * 1000))
    return {**proposta, "dia": dia_iso, "token_desfazer": token, "ms": ms}
