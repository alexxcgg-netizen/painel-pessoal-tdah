# ia/historico.py — faixa A5 (Fase 7): "resumo fixo + reconstrucao" do
# historico do chat. So esta faixa mexe neste arquivo.
#
# Por que: o chat e 85-95% do custo de IA porque reenvia o historico inteiro
# a cada mensagem. A ideia (igual ao contexto_fixo de ia/contrato.py, pensado
# pro cache de prompt do provedor): montar_contexto() devolve
#   - contexto_fixo: um resumo TEXTO, que fica IDENTICO entre chamadas
#     seguidas do chat (mesmo texto, byte a byte) ate a proxima reconstrucao -
#     e o que o provedor pode cachear.
#   - mensagens: so as ultimas interacoes, na integra, que mudam a cada turno
#     (isso sim precisa ser reenviado sempre, mas e pequeno).
#
# As mensagens originais NUNCA saem do banco (tabela `chat_mensagens`, ver
# db.py) - o resumo e so uma "lente" mais barata sobre elas pra IA. Quem quer
# o historico de verdade (tela do chat, export, etc.) continua lendo
# `chat_mensagens` direto.
#
# Estado do resumo: uma linha so (id=1) em `chat_resumo_historico`
# (migracoes/202609241100_a5_historico.sql), com ate onde o resumo cobre
# (`ultimo_mensagem_id`) e o dia em que foi gerado (`dia`, pra saber quando a
# virada de dia forca reconstrucao mesmo sem o historico ter crescido muito).
#
# A faixa A6 (chat) e quem consome isto:
#   ctx = ia.historico.montar_contexto(conn)
#   resp = ia.core.chamar_ia("chat", ctx["mensagens"] + [nova_mensagem_do_usuario],
#                             contexto_fixo=ctx["contexto_fixo"], ...)
# Nao mexe no chat em si (ia/funcoes/chat.py, claude_client.py - isso e da A6).

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Optional

from ia import core

log = logging.getLogger(__name__)

# Nome da "funcao de IA" (ia/config.d/resumo_historico.json) usada pra
# reconstruir o resumo via ia.core.chamar_ia.
FUNCAO_IA = "resumo_historico"

# Estimativa grosseira de tokens (~4 chars/token, mesmo criterio grosseiro
# usado em ia/adapters/anthropic.py:_estimar_tokens) - nao e contagem real,
# so o suficiente pra decidir quando reconstruir.
CHARS_POR_TOKEN = 4

# Acima disso (estimativa len//4 do historico ALEM do resumo atual, ou seja,
# tudo que ainda nao foi "dobrado" pra dentro do contexto_fixo), reconstroi.
LIMITE_TOKENS_RECONSTRUCAO = 6000

# Quantas mensagens ficam sempre na integra (nunca resumidas), alvo antes do
# alinhamento de papel (ver _cortar_para_verbatim): 6 interacoes de 2
# mensagens (user + assistant) cada = topo da faixa pedida ("4 a 6
# interacoes"). Se precisar afinar pra baixo, mexa so aqui.
MENSAGENS_VERBATIM = 12

# Teto de mensagens na integra por chamada (C1). Entre reconstrucoes, tudo que
# ainda nao foi resumido vai literal, ate este limite (mesmo numero que o app
# mandava antes da A5) - protege o custo se a reconstrucao falhar varias
# vezes seguidas (ex.: teto de IA estourado).
MENSAGENS_LITERAIS_MAX = 20

_ESTADO_VAZIO = {"resumo": "", "ultimo_mensagem_id": 0, "dia": ""}

# 08/11 (leva conversa inteira, A8): mensagem automatica do painel (aviso proativo, "como foi o treino?",
# fechamento do dia...) e uma 'assistant' que nao responde a nenhuma 'user' - vem logo depois de outra
# 'assistant'. Ela NAO conta na janela de mensagens literais (num dia cheio de avisos, as 20 vagas iam quase
# todas pra eles e a conversa de verdade sumia). Fica so a(s) ultima(s) antes de uma fala dele (ele pode
# estar respondendo a ela) e as do fim (a mensagem nova pode ser a resposta).
PROATIVAS_ANTES_DE_FALA = 2

# 08/11 (C5): o resumo nao carrega pendencia - a lista viva (tarefas/esperas abertas) vem do banco a cada
# mensagem; pendencia que ficava no resumo virava "em aberto" dias depois de resolvida.
SISTEMA_RESUMO = (
    "Voce resume o historico de uma conversa entre o Alex e o assistente "
    "pessoal dele (TDAH: tarefas, gastos, agenda, saude, estudo, viagens, "
    "rotina). Vai receber, se houver, o resumo anterior da conversa e um "
    "trecho novo de mensagens (formato 'papel: texto', uma por linha).\n\n"
    "Devolva UM UNICO resumo atualizado, em portugues, em texto corrido "
    "(sem JSON, sem marcacao, sem cabecalho), curto (poucos paragrafos). "
    "Mantenha: fatos e decisoes que ainda importam (nomes, valores, datas, "
    "combinados, preferencias e correcoes reveladas pelo Alex). NAO guarde "
    "tarefa, compromisso, lembrete ou espera como pendente/em aberto/falta fazer: "
    "o que esta aberto de verdade vem do banco a cada mensagem, e pendencia "
    "copiada aqui fica velha. Se vier a lista 'Abertos agora no banco', ela e a "
    "verdade: algo que nao esta nela ja foi feito ou cancelado. Tire do resumo "
    "anterior qualquer pendencia que nao esteja nessa lista. Descarte saudacao, "
    "small talk, aviso automatico do painel que ele nao respondeu e qualquer "
    "coisa ja resolvida ou sem relevancia futura. Nunca invente informacao "
    "que nao apareceu no historico. Cada mensagem vem com [dia dd/mm hh:mm]: "
    "SEMPRE escreva a data de cada compromisso/fato (ex: 'sab 10/10: teve date as 20h') "
    "- compromisso de um dia que ja passou nao e pendencia."
)


def _obter_estado(conn) -> dict:
    """Le a linha unica (id=1) de chat_resumo_historico. Tabela ainda
    ausente (migracao nao aplicada) ou sem linha ainda -> estado vazio, nunca
    levanta - quem chama (montar_contexto) precisa continuar funcionando
    mesmo sem resumo algum (equivale a "so mensagens na integra, sempre")."""
    try:
        linha = conn.execute(
            "SELECT resumo, ultimo_mensagem_id, dia FROM chat_resumo_historico WHERE id = 1"
        ).fetchone()
    except sqlite3.OperationalError:
        log.warning("ia.historico: tabela chat_resumo_historico ausente (migracao ainda nao aplicada)")
        return dict(_ESTADO_VAZIO)
    if linha is None:
        return dict(_ESTADO_VAZIO)
    resumo, ultimo_mensagem_id, dia = linha
    return {
        "resumo": resumo or "",
        "ultimo_mensagem_id": ultimo_mensagem_id or 0,
        "dia": dia or "",
    }


def _salvar_estado(conn, resumo: str, ultimo_mensagem_id: int, dia: str) -> None:
    conn.execute(
        """
        INSERT INTO chat_resumo_historico (id, resumo, ultimo_mensagem_id, dia, atualizado_em)
        VALUES (1, ?, ?, ?, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            resumo = excluded.resumo,
            ultimo_mensagem_id = excluded.ultimo_mensagem_id,
            dia = excluded.dia,
            atualizado_em = excluded.atualizado_em
        """,
        (resumo, ultimo_mensagem_id, dia),
    )
    conn.commit()


def _mensagens_desde(conn, desde_id: int) -> list[dict]:
    """Mensagens (id > desde_id) em ordem cronologica (mais antiga primeiro -
    o oposto de db.list_chat_mensagens, que e pra tela). desde_id=0 pega tudo."""
    linhas = conn.execute(
        "SELECT id, papel, texto, criado_em FROM chat_mensagens WHERE id > ? ORDER BY id ASC",
        (desde_id or 0,),
    ).fetchall()
    return [{"id": r[0], "papel": r[1], "texto": r[2] or "", "criado_em": r[3]} for r in linhas]


def _quando(m: dict) -> str:
    """'[sab 10/10 21:54] ' (horario de Brasilia) - o resumo precisa saber de QUE dia e cada fato
    (2026-10-12: sem isso o "date as 20h" de sabado virava compromisso de segunda)."""
    try:
        import diario
        dt = diario.utc_para_local(m.get("criado_em"))
    except Exception:  # noqa: BLE001
        dt = None
    return f"[{diario.DIAS_SEMANA[dt.weekday()][:3]} {dt:%d/%m %H:%M}] " if dt else ""


def _estimar_tokens(pool: list[dict]) -> int:
    total_chars = sum(len(m["texto"]) for m in pool)
    return total_chars // CHARS_POR_TOKEN


def _cortar_para_verbatim(pool: list[dict], alvo: int) -> int:
    """Indice (em pool) de onde comeca o trecho que fica na integra. Anda pra
    tras a partir do alvo ate cair numa mensagem 'user', pra nao cortar um
    par user/assistant ao meio (a API de chat exige comecar por 'user')."""
    if len(pool) <= alvo:
        return 0
    corte = len(pool) - alvo
    while corte > 0 and pool[corte]["papel"] != "user":
        corte -= 1
    return corte


def _papel_antes(conn, primeiro_id: int) -> Optional[str]:
    """Papel da mensagem logo antes do pool (a que ja entrou no resumo) - decide se a 1a do pool responde
    a uma fala dele. Sem nada antes -> None."""
    try:
        linha = conn.execute(
            "SELECT papel FROM chat_mensagens WHERE id < ? ORDER BY id DESC LIMIT 1", (primeiro_id,)
        ).fetchone()
    except sqlite3.Error:
        return None
    return linha[0] if linha else None


def marcar_proativas(mensagens: list[dict], papel_anterior: Optional[str] = None, chave: str = "papel") -> list[bool]:
    """Pra cada mensagem (ordem cronologica): True se e automatica do painel - 'assistant' que nao vem logo
    depois de uma 'user'. A resposta do chat e sempre gravada colada na pergunta (user + assistant juntos),
    entao o que sobra de 'assistant' seguida e aviso/pergunta que o painel mandou sozinho."""
    marcas, anterior = [], papel_anterior
    for m in mensagens:
        papel = m.get(chave)
        marcas.append(papel == "assistant" and anterior is not None and anterior != "user")
        anterior = papel
    return marcas


def _inicio_da_janela(pool: list[dict], proativas: list[bool], alvo: int) -> int:
    """Indice de onde comeca o trecho literal com `alvo` mensagens de CONVERSA (as automaticas nao contam),
    recuado ate uma 'user' (a API exige comecar por 'user', e nao corta um par ao meio)."""
    conversa = [i for i, p in enumerate(proativas) if not p]
    if len(conversa) <= alvo:
        return 0
    corte = conversa[-alvo]
    while corte > 0 and pool[corte]["papel"] != "user":
        corte -= 1
    return corte


def _sem_proativas_soltas(pool: list[dict], proativas: list[bool]) -> list[dict]:
    """Tira as automaticas que ele nao respondeu: de cada sequencia delas fica so as ultimas
    PROATIVAS_ANTES_DE_FALA, e so se vem uma fala dele depois (ou se e o fim - a mensagem nova pode ser a
    resposta)."""
    saida = []
    for i, m in enumerate(pool):
        if not proativas[i]:
            saida.append(m)
            continue
        j = i + 1
        while j < len(pool) and proativas[j]:
            j += 1
        respondida = j >= len(pool) or pool[j]["papel"] == "user"
        if respondida and j - i <= PROATIVAS_ANTES_DE_FALA:
            saida.append(m)
    return saida


LIMITE_ABERTAS = 40
LIMITE_ESPERAS = 15


def _abertos_no_banco(conn) -> str:
    """'Abertos agora no banco' pro resumo conferir (C5): tarefas sem concluir e esperas sem resolver.
    Tabela ausente (banco de teste so com o chat) -> texto vazio."""
    consulta = ("SELECT title FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL {arquivada}"
                f"ORDER BY due_date IS NULL, due_date, id DESC LIMIT {LIMITE_ABERTAS + 1}")
    try:  # 08/11 (revisao): tarefa arquivada no Recomeco nao esta "aberta"
        tarefas = [r[0] for r in conn.execute(consulta.format(arquivada="AND arquivada_em IS NULL ")).fetchall()]
    except sqlite3.OperationalError:
        try:  # banco antigo/teste sem a coluna
            tarefas = [r[0] for r in conn.execute(consulta.format(arquivada="")).fetchall()]
        except sqlite3.Error:
            return ""
    except sqlite3.Error:
        return ""
    cortada = len(tarefas) > LIMITE_ABERTAS
    tarefas = tarefas[:LIMITE_ABERTAS]
    try:
        esperas = [f"{r[0]}: {r[1]}" for r in conn.execute(
            f"SELECT quem, sobre FROM esperas WHERE resolvido_em IS NULL ORDER BY id DESC LIMIT {LIMITE_ESPERAS + 1}"
        ).fetchall()]
    except sqlite3.Error:
        esperas = []
    cortada = cortada or len(esperas) > LIMITE_ESPERAS
    esperas = esperas[:LIMITE_ESPERAS]
    if cortada:
        # com a lista cortada nao da pra afirmar que o que ficou de fora foi resolvido
        cabeca = ("Abertos agora no banco (lista CORTADA nos primeiros - o que estiver aqui esta aberto; pendencia "
                  "que nao aparece pode estar aberta tambem, entao so tire do resumo o que a conversa mostrar "
                  "que foi feito):")
    else:
        cabeca = "Abertos agora no banco (fonte da verdade - pendencia fora daqui ja foi resolvida):"
    partes = [cabeca, "tarefas: " + ("; ".join(tarefas) if tarefas else "nenhuma")]
    if esperas:
        partes.append("esperando de alguem: " + "; ".join(esperas))
    return "\n".join(partes)


def precisa_reconstruir(conn, agora: Optional[datetime] = None) -> bool:
    """True quando o historico ALEM do resumo atual (tudo que ainda nao foi
    dobrado pra dentro do contexto_fixo - inclui o que vai ficar na integra e
    o que vai ser resumido) passa de LIMITE_TOKENS_RECONSTRUCAO tokens
    (estimativa len//4), OU o dia mudou desde a ultima reconstrucao."""
    agora = agora or datetime.now()
    estado = _obter_estado(conn)
    pool = _mensagens_desde(conn, estado["ultimo_mensagem_id"])
    if not pool:
        return False
    dia_atual = agora.date().isoformat()
    if estado["dia"] and estado["dia"] != dia_atual:
        return True
    return _estimar_tokens(pool) > LIMITE_TOKENS_RECONSTRUCAO


def _reconstruir(conn, agora: datetime) -> None:
    """Dobra tudo em `pool` menos o trecho verbatim mais recente pra dentro
    do resumo (1 chamada de IA), e avanca o marcador `ultimo_mensagem_id`.
    Se a chamada de IA falhar, mantem o resumo/marcador antigos (tenta de
    novo na proxima vez que precisa_reconstruir() disparar) - nunca derruba
    o chat por causa disso."""
    estado = _obter_estado(conn)
    pool = _mensagens_desde(conn, estado["ultimo_mensagem_id"])
    dia_atual = agora.date().isoformat()
    if not pool:
        return

    proativas = marcar_proativas(pool, _papel_antes(conn, pool[0]["id"]))
    # A8: as automaticas nao contam no trecho que fica na integra (alvo = so mensagem de conversa)
    corte = _inicio_da_janela(pool, proativas, MENSAGENS_VERBATIM)
    dobrar = pool[:corte]
    if not dobrar:
        # So o dia mudou, mas nao ha nada alem do trecho que ja fica na
        # integra - nao vale chamar IA. So atualiza o marcador de dia pra
        # nao ficar tentando reconstruir de novo a cada chamada hoje.
        _salvar_estado(conn, estado["resumo"], estado["ultimo_mensagem_id"], dia_atual)
        return
    # aviso automatico que ele nao respondeu nao vira "pendencia" no resumo (C5)
    dobrar_texto = _sem_proativas_soltas(dobrar, proativas[:corte])
    if not dobrar_texto:
        _salvar_estado(conn, estado["resumo"], dobrar[-1]["id"], dia_atual)
        return

    transcript = "\n".join(f"{_quando(m)}{m['papel']}: {m['texto']}" for m in dobrar_texto)
    abertos = _abertos_no_banco(conn)
    if abertos:
        transcript += "\n\n" + abertos
    contexto_fixo = f"Resumo anterior da conversa:\n{estado['resumo']}" if estado["resumo"] else ""

    resp = core.chamar_ia(
        FUNCAO_IA,
        [{"role": "user", "content": transcript}],
        sistema=SISTEMA_RESUMO,
        contexto_fixo=contexto_fixo,
    )
    if not resp.ok or not (resp.texto or "").strip():
        log.warning("ia.historico: falha ao reconstruir resumo (%s) - mantendo o anterior",
                    resp.erro if resp else "sem resposta")
        return

    novo_resumo = resp.texto.strip()
    novo_ultimo_id = dobrar[-1]["id"]
    _salvar_estado(conn, novo_resumo, novo_ultimo_id, dia_atual)


def montar_contexto(conn, agora: Optional[datetime] = None) -> dict:
    """Ponto de entrada da faixa A6. Reconstroi o resumo se precisar e
    devolve {"contexto_fixo": str, "mensagens": list[{"role","content"}]}
    prontos pra ia.core.chamar_ia("chat", ..., contexto_fixo=..., mensagens=
    ctx["mensagens"] + [mensagem nova do usuario]).

    `contexto_fixo` fica byte-a-byte identico entre chamadas seguidas
    enquanto nao houver reconstrucao (e por isso que o provedor consegue
    cachear) - so muda quando precisa_reconstruir() for True."""
    agora = agora or datetime.now()
    if precisa_reconstruir(conn, agora):
        _reconstruir(conn, agora)

    estado = _obter_estado(conn)
    pool = _mensagens_desde(conn, estado["ultimo_mensagem_id"])
    # C1: vai na integra TUDO que ainda nao entrou no resumo (id >
    # ultimo_mensagem_id), limitado a MENSAGENS_LITERAIS_MAX. Antes ia so o
    # alvo de MENSAGENS_VERBATIM (12): entre uma reconstrucao e outra, as
    # mensagens 13+ nao estavam nem no resumo nem no trecho literal (sumiam
    # do contexto). Nunca duplica: o resumo cobre so ate ultimo_mensagem_id.
    # A8 (08/11): o limite conta so mensagem de conversa; aviso automatico solto (sem resposta dele) sai
    proativas = marcar_proativas(pool, _papel_antes(conn, pool[0]["id"])) if pool else []
    corte = _inicio_da_janela(pool, proativas, MENSAGENS_LITERAIS_MAX)
    verbatim = _sem_proativas_soltas(pool[corte:], proativas[corte:])

    mensagens = [{"role": m["papel"], "content": m["texto"]} for m in verbatim]
    # `meta` (2026-10-12): id/criado_em de cada mensagem, na mesma ordem - quem consome marca a
    # data das que nao sao de hoje (app._historico_chat_para_ia).
    meta = [{"id": m["id"], "criado_em": m.get("criado_em")} for m in verbatim]
    return {"contexto_fixo": estado["resumo"], "mensagens": mensagens, "meta": meta}
