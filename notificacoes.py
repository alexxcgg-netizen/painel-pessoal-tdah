"""Verificacoes proativas - cada funcao decide sozinha, em Python puro (sem
IA), se ha algo notavel o bastante pra mandar uma notificacao push. A
orquestracao (deduplicar por dia, mandar o push, marcar como enviado) fica
em app.py."""

import json
import logging
import re
import unicodedata
from datetime import date, datetime, timedelta

import aprendizado
import db
import gastos
import vida

log = logging.getLogger(__name__)

# Leva 08/11: expenses.created_at e tasks.completed_at sao datetime('now') do sqlite (UTC). O gasto
# das 21h30 e a tarefa feita as 22h ja caem no dia seguinte em UTC; `date(coluna)` cru jogava eles
# pra "amanha". Estas expressoes devolvem o dia de Brasilia (so data, legado/teste, fica como esta).
_DIA_GASTO = db.dia_local_sql("created_at")
_DIA_CONCLUSAO = db.dia_local_sql("completed_at")


def _dias_txt(n: int) -> str:
    """'1 dia' / '3 dias' - leva 08/11: push com plural errado ("1 dias") nao passa."""
    return f"{n} dia" if n == 1 else f"{n} dias"


def dentro_do_horario_silencioso(agora: datetime, inicio: str, fim: str) -> bool:
    """Janela de horario em que os avisos "soft" (nao urgentes) ficam
    represados em vez de tocar o celular - respeita o timing de quem esta do
    outro lado em vez de cutucar em qualquer hora so porque a condicao ficou
    verdadeira. 'inicio'/'fim' no formato 'HH:MM'; lida com a janela cruzando
    a meia-noite (ex: 22:00-07:00). inicio == fim desativa (nunca silencioso)."""
    if inicio == fim:
        return False
    hora_atual = agora.strftime("%H:%M")
    if inicio < fim:
        return inicio <= hora_atual < fim
    return hora_atual >= inicio or hora_atual < fim


def tarefas_aguardando_bom_tempo(conn) -> list[dict]:
    """Tarefas pendentes marcadas como 'depende do tempo' (ex: 'limpar o
    quarto se nao chover') - so identifica QUAIS tarefas checar; buscar a
    previsao de verdade (que pede rede) e decidir se ja tem um dia bom fica
    em app.py, pra esta funcao continuar pura e testavel so com SQLite."""
    rows = conn.execute(
        "SELECT id, title FROM tasks WHERE completed_at IS NULL AND depende_do_tempo = 1 "
        "AND recorrencia IS NULL"
    ).fetchall()
    return [dict(r) for r in rows]


def tarefas_atrasadas(conn) -> str | None:
    hoje = date.today().isoformat()
    n = conn.execute(
        """SELECT COUNT(*) AS n FROM tasks
           WHERE completed_at IS NULL AND due_date IS NOT NULL AND due_date < ?""",
        (hoje,),
    ).fetchone()["n"]
    if n == 0:
        return None
    if n == 1:
        return "Tu tem 1 tarefa atrasada."
    return f"Tu tem {n} tarefas atrasadas."


def tarefas_paradas(conn, dias_minimo: int = 3, hoje: date | None = None) -> list[tuple[int, str]]:
    """Cobranca por tarefa (nao so a contagem generica de tarefas_atrasadas): uma
    tarefa parada ha `dias_minimo` dias ou mais vira um check-in pelo nome, uma vez
    so (a deduplicacao fica em app.py via ja_notificado_alguma_vez, nao
    ja_notificou_hoje - senao voltaria a cobrar todo santo dia enquanto continuar
    atrasada, o que vira ruido em vez de ajuda)."""
    hoje = hoje or date.today()
    limite = (hoje - timedelta(days=dias_minimo)).isoformat()
    rows = conn.execute(
        """SELECT id, title, due_date FROM tasks
           WHERE completed_at IS NULL AND due_date IS NOT NULL AND due_date <= ?""",
        (limite,),
    ).fetchall()
    avisos = []
    for r in rows:
        dias = (hoje - date.fromisoformat(r["due_date"])).days
        avisos.append(
            (r["id"], f"\"{r['title']}\" está parada há {_dias_txt(dias)}. Ainda precisa fazer isso?")
        )
    return avisos


def esperas_paradas(conn, dias_minimo: int = 5, hoje: date | None = None) -> list[tuple[int, str]]:
    """Cobranca de resposta pendente de TERCEIROS (fornecedor, corretora,
    quem for) - diferente de tarefas_paradas, que cobra voce mesmo de volta,
    essa acompanha quem ainda nao te respondeu. Mesma logica de disparo unico
    (ver ja_notificado_alguma_vez em app.py): nao vale cobrar todo dia
    enquanto a espera continuar em aberto."""
    hoje = hoje or date.today()
    avisos = []
    rows = conn.execute(
        "SELECT id, quem, sobre, criado_em FROM esperas WHERE resolvido_em IS NULL"
    ).fetchall()
    for r in rows:
        # leva 08/11: criado_em e UTC - a espera criada as 22h de Brasilia ja e "amanha" em UTC e
        # contava 1 dia a menos. Dia local primeiro, depois a conta.
        dia = db.dia_local(r["criado_em"])
        try:
            criado = date.fromisoformat(dia or "")
        except ValueError:
            log.warning("esperas_paradas: criado_em invalido na espera %s: %r", r["id"], r["criado_em"])
            continue
        dias = (hoje - criado).days
        if dias < dias_minimo:
            continue
        avisos.append(
            (
                r["id"],
                f"Ainda esperando resposta de {r['quem']} sobre \"{r['sobre']}\" - já faz {_dias_txt(dias)}.",
            )
        )
    return avisos


# Avisos importantes que INSISTEM (2026-10-13, pedido do Alex: "avisa uma ou duas vezes so e
# se eu nao ver passa em branco"). Minutos depois do 1o envio em que cada repeticao sai, se ele
# nao tocou na notificacao (aberto_em) e o aviso ainda vale (tarefa nao concluida). O resto dos
# avisos continua indo uma vez so - insistir em tudo vira barulho.
INSISTENCIA = {
    "tarefa_horario": (10, 30),
    "compromisso_chegando": (5,),
    "se_arrumar": (10,),
    "hora_de_sair": (5,),
    "voo_sair": (5, 15),
    "conta_a_vencer": (180,),
    "conta_pessoal": (180,),
}
# tipos cujo ref_id e o id da tarefa: concluiu = para de insistir
INSISTENCIA_DE_TAREFA = {"tarefa_horario", "se_arrumar", "hora_de_sair"}


def repeticoes_devidas(pendentes: list[dict], agora: datetime) -> tuple[list[dict], list[dict]]:
    """(repetir_agora, encerrar) a partir das linhas abertas de avisos_insistentes. Puro.
    Encerra o que e de outro dia, de tipo que nao insiste mais ou que ja usou todas as
    repeticoes; repete o que chegou na hora da proxima."""
    repetir, encerrar = [], []
    hoje = agora.date().isoformat()
    for a in pendentes:
        passos = INSISTENCIA.get(a["tipo"])
        feitas = int(a.get("tentativas") or 1) - 1  # tentativas conta o 1o envio
        if not passos or a.get("data") != hoje or feitas >= len(passos):
            encerrar.append(a)
            continue
        try:
            enviado = datetime.fromisoformat(a["enviado_em"])
        except (TypeError, ValueError):
            encerrar.append(a)
            continue
        if agora >= enviado + timedelta(minutes=passos[feitas]):
            repetir.append(a)
    return repetir, encerrar


def texto_repeticao(tipo: str, titulo: str, corpo: str, repeticao: int) -> tuple[str, str]:
    """Repeticao `repeticao` (1, 2...) do aviso: mesmo assunto, tom um pouco mais direto na
    ultima. Sem cobranca nem drama (mesmo espirito de tarefas_horario_passou)."""
    ultima = repeticao >= len(INSISTENCIA.get(tipo, ()))
    prefixo = "Última chamada" if ultima else "De novo"
    return f"{prefixo} · {titulo}", corpo


def tarefas_com_horario_chegando(
    conn, agora: datetime | None = None, antecedencia_minutos: int = 10, caminho_min=None,
) -> list[tuple[int, str]]:
    """Tarefas pendentes com horario marcado pra hoje que estao chegando -
    pedido explicito do Alex (TDAH): avisar ANTES ("daqui 10 minutos voce tem
    que fazer tal coisa, ja va se arrumando"), nao so bem na hora, pra dar
    tempo de reagir em vez de so registrar que passou. A janela cobre de
    `antecedencia_minutos` antes ate a propria hora (inclusive) - quem ja
    passou do horario (ex: scheduler ficou fora do ar um tempo) ainda cai
    aqui com a mensagem "na hora", nunca fica sem aviso nenhum so porque o
    tick certo de heads-up foi perdido. A deduplicacao (uma vez por tarefa
    por dia, em app.py) garante que so um dos dois formatos de mensagem sai,
    mesmo com varios ticks do scheduler caindo dentro da janela.
    08/11 (frente A): depois da hora, compromisso de SAIR (e_saida) ganha texto de saida ("Ainda em casa?
    Saindo agora tu chega as 20:15"), nunca "toca em Feito"; `caminho_min(task_row) -> int | None` vem de
    fora (rede) pra dizer a chegada certa (sem ele: o ultimo trajeto guardado ou a folga). Tarefa comum que
    chega mais de ATRASO_LONGO_MIN atrasada (servidor voltou de parada) diz o atraso real, uma mensagem so."""
    agora = agora or datetime.now()
    hoje = agora.date().isoformat()
    hora_atual = agora.strftime("%H:%M")
    limite_futuro = (agora + timedelta(minutes=antecedencia_minutos)).strftime("%H:%M")
    rows = conn.execute(
        """SELECT * FROM tasks
           WHERE completed_at IS NULL AND due_date = ? AND hora IS NOT NULL AND hora <= ?""",
        (hoje, limite_futuro),
    ).fetchall()
    avisos = []
    for r in rows:
        chave = f"tarefa_horario-{r['id']}-{hoje}"
        antes = r["hora"] > hora_atual
        atraso = None if antes else _min_desde(r["hora"], agora)
        if not antes and e_saida(r):
            # ja avisado hoje: o texto nem sai (dedup em app.py), entao nao gasta Maps com ele
            ja = _notificado_em(conn, "tarefa_horario", r["id"], agora.date()) is not None
            msg = texto_saida_depois(conn, r, agora, None if ja else caminho_min, chave=chave)
        elif atraso is not None and atraso > ATRASO_LONGO_MIN:
            msg = texto_tarefa_atrasada(r["hora"], atraso, conn=conn, chave=chave, agora=agora)
        else:
            # 07/11 (frente C): com conn, o texto varia pelo catalogo (avisos_texto.py), estavel por tarefa/dia
            msg = texto_tarefa_chegando(r["hora"], antes=antes, conn=conn, chave=chave, agora=agora)
        avisos.append((r["id"], msg))
    return avisos


# ---- 08/11 (frente A): texto de saida depois da hora e atraso longo
ATRASO_LONGO_MIN = 60  # aviso "e agora" que sai mais atrasado que isso (servidor parado) diz o atraso real
FOLGA_SAIDA_MIN = 15  # mesma folga do plano_se_arrumar quando nao ha trajeto (Brusque e pequena)
CAMINHO_GUARDADO = "saida_caminho_min"  # configuracoes: ultimo trajeto real de cada saida do dia


def _min_desde(hora: str | None, agora: datetime) -> int | None:
    """Minutos de `hora` (HH:MM de hoje) ate agora; negativo se ainda nao chegou. None se hora invalida."""
    try:
        quando = datetime.combine(agora.date(), datetime.strptime(hora or "", "%H:%M").time())
    except ValueError:
        return None
    return int((agora - quando).total_seconds() // 60)


def texto_atraso(minutos: int) -> str:
    """75 -> "1 h 15 min"; 120 -> "2 h"; 40 -> "40 min"."""
    h, m = divmod(max(0, int(minutos)), 60)
    if not h:
        return f"{m} min"
    return f"{h} h {m} min" if m else f"{h} h"


def _utc_para_local(texto: str | None) -> datetime | None:
    """criado_em do SQLite (datetime('now'), UTC) -> hora local sem fuso (a do tick)."""
    from datetime import timezone

    try:
        return datetime.fromisoformat(str(texto)).replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _notificado_em(conn, tipo: str, referencia_id: int, dia: date) -> datetime | None:
    """Quando (hora local) o aviso `tipo` daquela tarefa saiu no dia; None se nao saiu."""
    try:
        r = conn.execute(
            "SELECT criado_em FROM notificacoes_enviadas WHERE tipo = ? AND referencia_id = ? AND data = ?",
            (tipo, referencia_id, dia.isoformat()),
        ).fetchone()
    except Exception:  # noqa: BLE001 - banco antigo/teste sem a tabela
        return None
    if not r:
        return None
    return _utc_para_local(r["criado_em"]) or datetime.combine(dia, datetime.min.time())


def _estado_saida(conn, task_id: int, dia: date) -> tuple[str, str | None]:
    """('chegou' | 'indo' | '', chegada prevista HH:MM) de uma saida hoje, pelo GPS (onde_estou/onde_vou)."""
    try:
        if conn.execute(
            "SELECT 1 FROM notificacoes_enviadas WHERE tipo = 'saida_chegou' AND referencia_id = ? AND data = ?",
            (task_id, dia.isoformat()),
        ).fetchone():
            return "chegou", None
        r = conn.execute(
            "SELECT saiu_em, chegou_em, chegada_prevista FROM indo_pra WHERE dia = ? AND tarefa_id = ? "
            "AND COALESCE(resposta, '') != 'outro' ORDER BY id DESC LIMIT 1",
            (dia.isoformat(), task_id),
        ).fetchone()
    except Exception:  # noqa: BLE001 - sem indo_pra (banco antigo): sem estado
        return "", None
    if not r:
        return "", None
    if r["chegou_em"]:
        return "chegou", None
    if r["saiu_em"]:
        prev = str(r["chegada_prevista"] or "")
        return "indo", (prev[11:16] if len(prev) >= 16 else None)
    return "", None


def _caminho_guardado(conn, task_id: int, dia: date) -> int | None:
    try:
        d = json.loads(db.obter_configuracao(conn, CAMINHO_GUARDADO) or "{}")
    except (TypeError, ValueError):
        return None
    if not isinstance(d, dict) or d.get("dia") != dia.isoformat():
        return None
    return _min_valido((d.get("min") or {}).get(str(task_id)))


def _guardar_caminho(conn, task_id: int, dia: date, minutos: int) -> None:
    """Guarda o trajeto real usado no aviso: a repeticao (aviso_cara, sem rede) diz a mesma chegada."""
    try:
        d = json.loads(db.obter_configuracao(conn, CAMINHO_GUARDADO) or "{}")
        if not isinstance(d, dict) or d.get("dia") != dia.isoformat():
            d = {"dia": dia.isoformat(), "min": {}}
        d.setdefault("min", {})[str(task_id)] = int(minutos)
        db.definir_configuracao(conn, CAMINHO_GUARDADO, json.dumps(d))
        conn.commit()
    except Exception:  # noqa: BLE001 - guardar e extra, o aviso sai igual
        pass


def texto_saida_depois(conn, r, agora: datetime, caminho_min=None, passou: bool = False,
                       chave: str | None = None) -> str:
    """Corpo do aviso de um compromisso de SAIR depois da hora (08/11, frente A). Sem "toca em Feito", sem
    "primeiro passo", sem "ainda da tempo de resolver hoje":
      - GPS viu que ele chegou: "Chegou bem. Aproveita!"; saiu e esta a caminho: "Ta a caminho, ne?...";
      - senao: "Ainda em casa? Saindo agora tu chega as HH:MM" (agora + trajeto; atraso longo diz o atraso).
    `passou=True` e o 2o aviso (tarefa_horario_passou, titulo generico): o corpo leva o nome."""
    import avisos_texto

    dia = agora.date()
    nome = " ".join(str(_coluna(r, "title") or "").split()) or "O compromisso"
    estado, chega_prevista = _estado_saida(conn, r["id"], dia) if conn is not None else ("", None)
    if estado:
        assunto = "saida_chegou" if estado == "chegou" else "saida_indo"
        corpo = avisos_texto.par(assunto, {"hora": r["hora"], "chega": chega_prevista}, conn=conn, chave=chave,
                                 agora=agora)[1]
        return f"{avisos_texto._curto(nome)}: {corpo}" if passou else corpo
    caminho = None
    if callable(caminho_min):
        try:
            caminho = _min_valido(caminho_min(r))
        except Exception:  # noqa: BLE001 - rede/Maps: segue com o guardado ou a folga
            caminho = None
    if caminho is not None and conn is not None:
        _guardar_caminho(conn, r["id"], dia, caminho)
    elif conn is not None:
        caminho = _caminho_guardado(conn, r["id"], dia)
    if caminho is None:
        caminho = FOLGA_SAIDA_MIN
    chega = (agora + timedelta(minutes=caminho)).strftime("%H:%M")
    atraso = _min_desde(r["hora"], agora) or 0
    dados = {"nome": nome, "hora": r["hora"], "chega": chega, "atraso": texto_atraso(atraso)}
    if passou:
        assunto = "saida_passou"
    elif atraso > ATRASO_LONGO_MIN:
        assunto = "saida_atrasada"
    else:
        assunto = "saida_depois"
    return avisos_texto.par(assunto, dados, conn=conn, chave=chave, agora=agora)[1]


TITULO_SAIDA_PASSOU = "Hora de sair já passou"  # o mesmo de app.TITULO_SAIDA_PASSOU


def titulo_saida_passou(conn, r, agora: datetime) -> str:
    """Titulo do 2o aviso de um compromisso de SAIR (tarefa_horario_passou). 08/11 (rodada 3): com o GPS
    dizendo que ele ja saiu ou ja chegou, "Hora de sair ja passou" em cima de "Chegou bem" nao combina -
    o titulo vira o nome do compromisso."""
    estado = _estado_saida(conn, r["id"], agora.date())[0] if conn is not None else ""
    return titulo_tarefa(_coluna(r, "title") or "") if estado else TITULO_SAIDA_PASSOU


def texto_agora_da_tarefa(r, conn=None, chave: str | None = None, agora=None) -> str:
    """Corpo do "e agora" na hora exata (aviso local do app, avisos_app.montar) olhando a linha da tarefa:
    compromisso de sair ganha texto de sair (nunca "toca em Feito"); o resto, o texto_tarefa_agora de sempre."""
    import avisos_texto

    if e_saida(r):
        # 08/11 (rodada 3): "tem alguem te esperando" so com gente esperando (banco, consulta: nao)
        return avisos_texto.par("saida_agora", {"hora": r["hora"]}, conn=conn, chave=chave, agora=agora,
                                pessoa=com_pessoa(r))[1]
    return texto_tarefa_agora(r["hora"], conn=conn, chave=chave, agora=agora)


def texto_tarefa_atrasada(hora: str, atraso_min: int, conn=None, chave: str | None = None, agora=None) -> str:
    """Aviso "e agora" que saiu bem atrasado (servidor voltou de parada, A6): diz o atraso real, sem
    "passou um pouquinho"."""
    import avisos_texto

    return avisos_texto.par("tarefa_atrasada", {"hora": hora, "atraso": texto_atraso(atraso_min)},
                            conn=conn, chave=chave, agora=agora)[1]


# ---- Texto dos avisos (06/11/2026, voto do Alex no artefato "Avisos do Painel": estilo C "Amigo",
# com "tu", leve, sem cobranca, e 1 emoji por assunto no titulo). O titulo da tarefa vai no TITULO
# da notificacao (a tela bloqueada mostra ele primeiro); o corpo nao repete o nome.
EMOJI_DO_AVISO = {
    "se_arrumar": "🪞", "saida_preparo": "🪞",
    "hora_de_sair": "🚗", "saida_porta": "🚗",
    "tarefa_horario": "⏰", "tarefa_preparo": "⏰", "tarefa_horario_passou": "⏰", "tarefa_agora": "⏰",
    "tarefa_inegociavel": "🔒",
    "compromisso_chegando": "📅",
    "voo_sair": "✈️",
    "indo_pra": "🚗", "atraso_recado": "⏰",  # pra onde vou + recado pronto (06/11, onde_vou.py)
    "agua_pausa": "💧",
    "tarefa_parada": "🧹",
    "voo_decisao": "✈️", "casa_tarefa": "🏠", "treino_pergunta": "💪", "rotina_descoberta": "🔁",  # frente 7 (06/11)
    "tarefa_adiada": "🧹",
    "rotina_manha": "☀️",
    "fechamento_noturno": "🌙", "fechar_dia_chat": "🌙",
    # catalogo novo (07/11, frente C, avisos_texto.py): assuntos novos + a IA mandando aviso
    "lugar_fechado": "🚪", "transito_piorou": "🚦", "chegou_casa": "🏠", "meta_batida": "🎯",
    "sequencia": "🔥", "saida_previsao": "☔", "aviso_ia": "💬",
    # leva 08/11 (frente A): o aviso da manha que repete quando ele acorda; a saida que o GPS fechou sozinha
    "tarefa_manha": "\u23f0", "saida_feita": "\u2705",
}
EMOJI_REFEICAO = "🍽️"
TITULO_REFEICAO = "Hora de comer"
TITULO_VOO_SAIR = "Bora pro voo"
TITULO_MAX = 60


def com_emoji(tipo: str, titulo: str) -> str:
    """Titulo com o emoji do assunto na frente, so na hora de mandar (o banco guarda sem). Nunca dobra."""
    if not titulo:
        return titulo
    emoji = EMOJI_REFEICAO if TITULO_REFEICAO in titulo else EMOJI_DO_AVISO.get(tipo)
    if not emoji or titulo.startswith(emoji):
        return titulo
    return f"{emoji} {titulo}"


def titulo_tarefa(titulo: str) -> str:
    """Nome da tarefa como titulo do aviso (curto pra caber na tela bloqueada)."""
    t = " ".join((titulo or "").split()) or "Tarefa"
    return t if len(t) <= TITULO_MAX else t[: TITULO_MAX - 1].rstrip() + "…"


# 07/11 (frente C): os textos abaixo saem do catalogo avisos_texto.py. Sem conn = a variacao classica
# (o texto de antes); com conn = variacao por contexto, sem repetir a ultima, estavel pela `chave`.
def texto_tarefa_chegando(hora: str, antes: bool, conn=None, chave: str | None = None, agora=None) -> str:
    import avisos_texto

    return avisos_texto.par("tarefa_horario" if antes else "tarefa_na_hora", {"hora": hora},
                            conn=conn, chave=chave, agora=agora)[1]


def texto_tarefa_agora(hora: str, conn=None, chave: str | None = None, agora=None) -> str:
    """Aviso na hora exata (so pelo app do iPhone, leva 06/11)."""
    import avisos_texto

    return avisos_texto.par("tarefa_agora", {"hora": hora}, conn=conn, chave=chave, agora=agora)[1]


def texto_tarefa_preparo(hora: str, falta_min: int, conn=None, chave: str | None = None, agora=None) -> str:
    import avisos_texto

    return avisos_texto.par("tarefa_preparo", {"hora": hora, "falta": falta_min},
                            conn=conn, chave=chave, agora=agora)[1]


def texto_refeicao(titulo: str) -> str:
    """"Comer: almoco - arroz, feijao" -> "Almoco - arroz, feijao" (o titulo do aviso e "Hora de comer")."""
    corpo = re.sub(r"^\s*comer\s*:?\s*", "", titulo or "", flags=re.I) or "Bora comer."
    return corpo[:1].upper() + corpo[1:]


# Compromisso de SAIR (date, festa...) - o Alex leva bem mais tempo pra se arrumar pra
# esses (pedido dele, 2026-10-11: "demoro 40 minutos pra me arrumar" pra date/festa).
_PALAVRAS_SAIR = re.compile(
    r"\b(date|encontro|jantar|janta|festa|festinha|balada|aniversario|niver|casamento|formatura|"
    r"show|churrasco|happy hour|boate|role|barzinho|bar|pub|sair com|saida com)\b"
)
_ARRUMAR = re.compile(r"\b(se arrumar|me arrumar|arrumar pra|banho e arrumar)\b")


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in base if not unicodedata.combining(c))


def e_refeicao(titulo: str) -> bool:
    """Bloco de comida do planejar_dia ("Comer: almoco - arroz, feijao, frango")."""
    return _sem_acento(titulo).startswith("comer")


def e_compromisso_de_sair(titulo: str) -> bool:
    return not e_refeicao(titulo) and bool(_PALAVRAS_SAIR.search(_sem_acento(titulo)))


# ---- compromisso de sair x tarefa comum (leva 08/11, frente A, docs/briefings/2026-11-08-leva-conversa-inteira.md)
# Date, balada, buscar alguem: nao e tarefa de "marcar Feito". Nunca "primeiro passo", nunca "ta na tua lista ha N
# dias", nunca empurrado pela cascata do atraso, e o recado de atraso so existe quando tem alguem esperando.
_PESSOA_PALAVRA = re.compile(
    r"\b(?:com|buscar|pegar|encontrar|levar|ver)\s+(?:a |o |as |os |minha |meu |minhas |meus )?"
    r"(mae|pai|vo|avo|avos|irma|irmao|irmaos|namorada|namorado|guri|guria|filho|filha|tio|tia|primo|prima|"
    r"amigo|amiga|amigos|amigas|galera|pessoal|sogra|sogro|crush|ficante)\b"
)
_PESSOA_NOME = re.compile(r"\b(?i:com|buscar|pegar|encontrar|levar)\s+(?i:a |o |as |os )?(\w{3,})")
# nome com maiuscula depois de "com/buscar" que NAO e gente esperando (orgao, banco, consultorio, coisa)
_NAO_PESSOA = frozenset({
    "banco", "caixa", "cartorio", "prefeitura", "detran", "receita", "inss", "correios", "clinica", "hospital",
    "posto", "mercado", "shopping", "aeroclube", "oficina", "mecanico", "dentista", "medico", "medica", "doutor",
    "doutora", "dra", "farmacia", "uber", "carro", "moto", "chave", "nubank", "itau", "bradesco", "santander",
    "sicredi", "unimed", "forum", "anac", "policia", "escola", "faculdade", "empresa", "construtora",
    "pix", "cartao", "dinheiro", "boleto", "google", "zoom", "meet", "teams",
    # leva 08/11 (rodada 3): documento, sigla e coisa com inicial maiuscula ("Buscar Remedio", "Pegar Passaporte")
    "cnh", "crlv", "cma", "rg", "cpf", "pf", "revisao", "documento", "documentos", "passaporte", "remedio",
    "remedios", "exame", "exames", "encomenda", "encomendas", "pacote", "pedido", "ifood", "notebook", "celular",
    "computador", "roupa", "roupas", "presente", "oculos", "laudo", "resultado", "certidao", "carteira", "chaves",
    # profissional de servico nao e "alguem te esperando" pra recado de atraso
    "instrutor", "instrutora", "professor", "professora", "personal", "corretor", "corretora", "vendedor",
    "vendedora", "contador", "contadora", "advogado", "advogada", "tecnico", "tecnica",
})
# palavra no titulo que diz que o "nome" e de coisa (carro na revisao): "Levar o Onix na revisao"
_COISA_NO_TITULO = frozenset({"revisao", "conserto", "manutencao", "lavacao", "lavagem", "vistoria", "emplacamento",
                              "assistencia", "funilaria", "borracharia"})
_VERBO_DE_IR = re.compile(r"\b(buscar|pegar|levar|encontrar|visitar|ir)\b")


def _extras_de(r) -> dict:
    v = _coluna(r, "extras")
    if isinstance(v, dict):
        return v
    try:
        e = json.loads(v) if v else {}
    except (TypeError, ValueError):
        return {}
    return e if isinstance(e, dict) else {}


def com_pessoa(r) -> bool:
    """Tem alguem esperando (leva 08/11): date/balada, `extras.com_quem`, palavra de sair (festa, jantar, niver...)
    ou "com/buscar <pessoa>" no titulo ("buscar a Ana", "almoco com a mae"). Banco, cartorio, consulta: nao."""
    titulo = _coluna(r, "title") or ""
    if e_refeicao(titulo):
        return False
    if _coluna(r, "estilo") in ("date", "balada") or _extras_de(r).get("com_quem"):
        return True
    if e_compromisso_de_sair(titulo) or _PESSOA_PALAVRA.search(_sem_acento(titulo)):
        return True
    # leva 08/11 (rodada 3): o nome com maiuscula so vale se parece nome de gente - sigla toda maiuscula (CNH,
    # CRLV, PF) nao e; carro na revisao nao e; e titulo Todo Com Maiuscula nao diz nada pela maiuscula, entao
    # la so vale o que nao for palavra comum (_NAO_PESSOA cobre as dos dois casos)
    palavras = set(re.findall(r"\w+", _sem_acento(titulo)))
    if palavras & _COISA_NO_TITULO:
        return False

    def _parece_nome(palavra: str) -> bool:
        return (palavra[:1].isupper() and not palavra.isupper()
                and _sem_acento(palavra) not in _NAO_PESSOA)

    return any(_parece_nome(m.group(1)) for m in _PESSOA_NOME.finditer(titulo))


def e_saida(r) -> bool:
    """Compromisso de SAIR (leva 08/11): date/balada/festa, hora de sair (`sai_na_hora`), parada no caminho ou
    alguem esperando num lugar ("buscar a Ana", "almoco com a mae" com local). "Estudar com o Pedro" sem
    lugar nem verbo de ir nao e saida (pode ser em casa). `r` = linha de tasks (sqlite3.Row ou dict)."""
    titulo = _coluna(r, "title") or ""
    if sai_na_hora(r) or (_coluna(r, "parada") or "").strip() or _coluna(r, "estilo") in ("date", "balada"):
        return True
    if e_compromisso_de_sair(titulo):
        return True
    return com_pessoa(r) and bool((_coluna(r, "local") or "").strip() or _VERBO_DE_IR.search(_sem_acento(titulo)))


PARADA_MIN = 5  # parado na parada do caminho ("passo na casa do guri antes"), briefing 04/11
# 08/11 (A4): perna da parada acima disso e engano do Google ("casa da Fulana" virou uma cidade com o nome: 2158 min)
PARADA_TETO_MIN = 180
ADIANTAR_MAX_MIN = 60


def _min_valido(v) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None


def _perna(v, folga: int) -> int:
    """Perna da parada: o Maps, se veio e nao e absurda (> PARADA_TETO_MIN); senao a folga."""
    m = _min_valido(v)
    return m if m is not None and m <= PARADA_TETO_MIN else folga


def caminho_com_parada(trajeto, folga: int, parada: str | None = None, ate_parada=None, parada_destino=None,
                       ate_parada_dito=None):
    """Minutos de casa ate o destino e o dado da parada (contrato do card de saida, briefing 04/11):
    (caminho_min, {"nome", "min_ate"} | None). Sem parada: o trajeto (ou a folga). Com parada:
    casa -> parada + 5 min parado + parada -> destino; cada perna sem resposta do Maps, ou absurda
    (acima de PARADA_TETO_MIN, 08/11), usa a folga - ou, na perna ate a parada, os minutos que ele
    disse (`ate_parada_dito`, extras.parada_min), se disse."""
    parada = (parada or "").strip()
    if not parada:
        t = _min_valido(trajeto)
        return (t if t is not None else folga), None
    dito = _min_valido(ate_parada_dito)
    ate = _perna(ate_parada, dito if dito is not None and dito <= PARADA_TETO_MIN else folga)
    resto = _perna(parada_destino, folga)
    return ate + PARADA_MIN + resto, {"nome": parada[:60], "min_ate": ate}


def _casa_de_sem_apelido(conn, texto: str | None) -> bool:
    try:
        import vida_assistente

        return bool((texto or "").strip()) and vida_assistente.casa_de_alguem_sem_apelido(conn, texto)
    except Exception:  # noqa: BLE001
        return False


def adiantar_min(extras_json) -> int:
    """Quanto a saida ja foi adiantada (previsao que piorou, tempo.previsao_que_piora). 0 sem nada."""
    try:
        e = json.loads(extras_json) if extras_json else {}
    except (TypeError, ValueError):
        return 0
    v = e.get("adiantar_min") if isinstance(e, dict) else None
    return v if isinstance(v, int) and not isinstance(v, bool) and 0 < v <= ADIANTAR_MAX_MIN else 0


def _coluna(r, nome: str):
    return r[nome] if nome in r.keys() else None


def meu_tempo_min(conn, evento, so_saida: bool = False) -> int:
    """Aprende teus tempos reais (06/11, onde_vou.ajuste): quantos min a mais adiantar a saida pelo jeito
    dele (3+ amostras, "Meu tempo" ligado). 0 sem amostra, com "Padrao" ou se der qualquer erro."""
    try:
        import onde_vou

        return int(onde_vou.ajuste(conn, evento, so_saida)["min"])
    except Exception:
        return 0


def sai_na_hora(r) -> bool:
    """A hora da tarefa e a de SAIR de casa (05/11, coluna tasks.sai_na_hora): "o date comeca as 19, so
    saio de casa as 19". Ai a saida e a propria hora e a chegada vira hora + trajeto."""
    return bool(_coluna(r, "sai_na_hora"))


def plano_se_arrumar(
    conn, agora: datetime | None = None, minutos_arrumar: int = 40, trajeto_min=None, folga_sem_trajeto: int = 15,
    trajeto_parada=None,
) -> list[dict]:
    """Compromissos de sair de HOJE (pendentes, com hora, ainda nao comecados) com a conta
    de tras pra frente: evento - trajeto = saida; saida - tempo de se arrumar = comecar.
    `trajeto_min(local) -> int | None` vem de fora (rede) pra esta funcao continuar pura;
    sem local/sem resposta usa `folga_sem_trajeto` (Brusque e pequena). Se o Alex ja tem
    uma tarefa "se arrumar" marcada hoje, o aviso de se arrumar fica com ela (nao duplica).
    Parada no caminho (04/11): `trajeto_parada(parada, local) -> (casa->parada, parada->destino)`
    e a conta vira casa -> parada -> destino (caminho_com_parada). Saida adiantada pela previsao
    (extras.adiantar_min) entra aqui tambem, pra todos os avisos baterem."""
    agora = agora or datetime.now()
    hoje = agora.date().isoformat()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE due_date = ? AND hora IS NOT NULL",
        (hoje,),
    ).fetchall()
    ja_tem_arrumar = any(_ARRUMAR.search(_sem_acento(r["title"])) for r in rows)
    planos = []
    for r in rows:
        # date/balada (card proprio, 2026-10-14) sao saida mesmo sem a palavra no titulo
        if r["completed_at"] or not (e_compromisso_de_sair(r["title"]) or r["estilo"] in ("date", "balada")):
            continue
        try:
            evento = datetime.combine(agora.date(), datetime.strptime(r["hora"], "%H:%M").time())
        except ValueError:
            continue
        if evento <= agora:
            continue
        trajeto = None
        perto = (evento - agora) <= timedelta(hours=4)
        parada = (_coluna(r, "parada") or "").strip()
        ate = resto = None
        if parada:
            if trajeto_parada and perto:
                ate, resto = trajeto_parada(parada, r["local"])
        elif r["local"] and trajeto_min and perto and not _casa_de_sem_apelido(conn, r["local"]):
            # 08/11 (A4): "casa da Fulana" sem apelido nao vai pro Google (achava uma cidade): fica a folga
            trajeto = trajeto_min(r["local"])
        caminho, info_parada = caminho_com_parada(trajeto, folga_sem_trajeto, parada, ate, resto,
                                                  _extras_de(r).get("parada_min"))
        adiantado = adiantar_min(_coluna(r, "extras"))
        meu = meu_tempo_min(conn, evento, sai_na_hora(r))  # 06/11: o jeito dele (onde_vou), 0 sem amostra
        if sai_na_hora(r):
            saida = evento - timedelta(minutes=adiantado + meu)
        else:
            saida = evento - timedelta(minutes=caminho + adiantado + meu)
        planos.append({
            "id": r["id"], "titulo": r["title"], "hora": r["hora"], "local": r["local"],
            "trajeto_min": trajeto if _min_valido(trajeto) is not None else None, "caminho_min": caminho,
            "evento": evento, "saida": saida, "comecar": saida - timedelta(minutes=minutos_arrumar),
            "minutos_arrumar": minutos_arrumar, "ja_tem_tarefa_arrumar": ja_tem_arrumar,
            "parada": info_parada, "adiantado_min": adiantado, "estilo": r["estilo"],
            "meu_tempo_min": meu, "sai_na_hora": sai_na_hora(r),
        })
    return planos


def avisos_se_arrumar(planos: list[dict], agora: datetime | None = None, conn=None,
                      chuva: bool | None = None) -> list[tuple[str, int, str, str]]:
    """(tipo, id, titulo, corpo) - 'se_arrumar' ~na hora de comecar e 'hora_de_sair' ~na hora
    de sair. Tick de 5 min: dispara a partir de 4 min antes (nunca atrasa mais que o tick).
    07/11 (frente C): titulo e corpo do catalogo avisos_texto.py; com `conn` variam por contexto (chuva,
    noite...) sem repetir a ultima, estaveis por compromisso/dia. Sem conn = o texto classico de antes."""
    import avisos_texto

    agora = agora or datetime.now()
    margem = timedelta(minutes=4)
    avisos = []
    for p in planos:
        nome, hora = p["titulo"], p["hora"]
        sai = p["saida"].strftime("%H:%M")
        dia = p["evento"].date().isoformat() if isinstance(p.get("evento"), datetime) else agora.date().isoformat()
        if not p["ja_tem_tarefa_arrumar"] and p["comecar"] - margem <= agora < p["saida"]:
            atrasado = agora > p["comecar"] + timedelta(minutes=10)
            assunto = "se_arrumar_tarde" if atrasado else "se_arrumar"
            titulo, corpo = avisos_texto.par(
                assunto, {"nome": nome, "hora": hora, "sai": sai, "min": p["minutos_arrumar"]},
                conn=conn, chave=f"se_arrumar-{p['id']}-{dia}", agora=agora, chuva=chuva)
            avisos.append(("se_arrumar", p["id"], titulo, corpo))
        if p["saida"] - margem <= agora < p["evento"]:
            if p.get("parada"):
                # briefing 04/11: "Hora de sair. 10 min até a casa do guri."
                assunto, dados = "hora_de_sair_parada", {"parada_min": p["parada"]["min_ate"], "parada": p["parada"]["nome"]}
            elif p["trajeto_min"] is not None:
                assunto, dados = "hora_de_sair", {"trajeto": p["trajeto_min"]}
            else:
                assunto, dados = "hora_de_sair_folga", {}
            titulo, corpo = avisos_texto.par(assunto, {"nome": nome, "hora": hora, **dados}, conn=conn,
                                             chave=f"hora_de_sair-{p['id']}-{dia}", agora=agora, chuva=chuva)
            if p.get("meu_tempo_min"):
                corpo += f" Avisei {p['meu_tempo_min']} min antes: é o teu jeito."
            avisos.append(("hora_de_sair", p["id"], titulo, corpo))
    return avisos


def tarefas_preparo(
    conn, agora: datetime | None = None, de_min: int = 15, ate_min: int = 34, ignorar: set | None = None,
) -> list[tuple[int, str]]:
    """Aviso ANTES do 'daqui a pouco' de 10 min (TDAH: 10 min e pouco pra largar o que esta
    fazendo): tarefa de hoje com hora entre 15 e ~30 min a frente. Compromisso de sair fica
    de fora (`ignorar`) - esses ja tem 'se arrumar' e 'hora de sair'."""
    agora = agora or datetime.now()
    ignorar = ignorar or set()
    rows = conn.execute(
        "SELECT id, title, hora FROM tasks WHERE completed_at IS NULL AND due_date = ? AND hora IS NOT NULL",
        (agora.date().isoformat(),),
    ).fetchall()
    avisos = []
    for r in rows:
        if r["id"] in ignorar or e_refeicao(r["title"]):  # comer: o aviso na hora basta
            continue
        try:
            quando = datetime.combine(agora.date(), datetime.strptime(r["hora"], "%H:%M").time())
        except ValueError:
            continue
        falta = (quando - agora).total_seconds() / 60
        if de_min <= falta < ate_min:
            avisos.append((r["id"], texto_tarefa_preparo(r["hora"], round(falta), conn=conn, agora=agora,
                                                         chave=f"tarefa_preparo-{r['id']}-{agora.date().isoformat()}")))
    return avisos


def metas_fora_do_ritmo(conn, tolerancia: float = 0.7) -> list[tuple[int, str]]:
    """Compara o quanto ja devia ter guardado (proporcional ao tempo passado
    desde a criacao ate o prazo) com o que realmente guardou. So considera
    metas com prazo definido."""
    hoje = date.today()
    avisos = []
    metas = conn.execute("SELECT * FROM goals WHERE prazo IS NOT NULL").fetchall()
    for m in metas:
        # leva 08/11: um prazo cru ("dezembro", "31/12") derrubava a lista inteira a cada tick de 5 min
        try:
            prazo = date.fromisoformat(m["prazo"])
            criado = datetime.fromisoformat(m["criado_em"]).date()
        except (TypeError, ValueError):
            log.warning("metas_fora_do_ritmo: data invalida na meta %s: prazo=%r criado_em=%r",
                        m["id"], m["prazo"], m["criado_em"])
            continue
        total_dias = (prazo - criado).days
        dias_passados = (hoje - criado).days
        if total_dias <= 0 or dias_passados <= 0 or hoje >= prazo:
            continue
        fracao = min(dias_passados / total_dias, 1)
        esperado = m["valor_alvo"] * fracao
        if esperado > 0 and m["valor_guardado"] < esperado * tolerancia:
            avisos.append(
                (m["id"], f"Meta \"{m['titulo']}\" está atrás do ritmo pra bater o prazo.")
            )
    return avisos


def orcamentos_perto_ou_estourados(conn, hoje: date | None = None) -> list[tuple[str, str, str]]:
    """Pra cada categoria com orcamento definido (`orcamentos`), compara o
    gasto REAL do mes atual com o limite - devolve (categoria, nivel,
    mensagem) pra cada categoria que bateu 90% ("quase") ou 100%+
    ("estourado") do limite agora. So gastos ja acontecidos contam (mesma
    regra de _total_gasto_entre - gasto planejado nao deveria disparar
    alerta de orcamento, pode nem vir a acontecer). A deduplicacao
    (uma vez por categoria+mes+nivel) fica em app.py."""
    hoje = hoje or date.today()
    ano_mes = hoje.strftime("%Y-%m")
    avisos = []
    for orc in conn.execute("SELECT categoria, valor_limite FROM orcamentos").fetchall():
        categoria = orc["categoria"]
        limite = orc["valor_limite"]
        if limite <= 0:
            continue
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses "
            f"WHERE category = ? AND tipo = 'real' AND substr({_DIA_GASTO}, 1, 7) = ?",
            (categoria, ano_mes),
        ).fetchone()
        gasto = row["total"]
        if gasto <= 0:
            continue
        fracao = gasto / limite
        if fracao >= 1:
            avisos.append((
                categoria,
                "estourado",
                f"Tu já passou do orçamento de {categoria} esse mês: "
                f"R$ {gasto:.2f} de um limite de R$ {limite:.2f}.",
            ))
        elif fracao >= 0.9:
            avisos.append((
                categoria,
                "quase",
                f"Tu já gastou R$ {gasto:.2f} em {categoria} esse mês - "
                f"perto do limite de R$ {limite:.2f}.",
            ))
    return avisos


def teto_ia_perto_ou_estourado(conn) -> tuple[str, str] | None:
    """US-A6 (Fase 5): compara o gasto do mes com a API da Anthropic
    (db.resumo_custo_api) contra o teto configurado (db.obter_teto_mensal_ia)
    - devolve (nivel, mensagem) quando passar de 80% ("quase") ou 100%+
    ("estourado"), None sem teto configurado ou dentro dos 80%. Mesma
    logica de orcamentos_perto_ou_estourados (dedup por mes+nivel fica em
    app.py)."""
    resumo = db.resumo_custo_api(conn)
    teto = resumo["teto_mensal_usd"]
    if not teto:
        return None
    gasto = resumo["mes_atual_usd"]
    if resumo["teto_estourado"]:
        return (
            "estourado",
            f"Tu já passou do teto mensal de IA: ${gasto:.2f} de um limite de ${teto:.2f}. "
            "O classificador de intent vai preferir resolver por padrao aprendido (sem "
            "chamar a API) até o mês virar.",
        )
    if resumo["teto_perto"]:
        return (
            "quase",
            f"Tu já gastou ${gasto:.2f} com a API da IA esse mês - perto do teto de ${teto:.2f}.",
        )
    return None


def cobrancas_genericas_sem_rotulo(conn) -> list[tuple[str, float, str]]:
    """Acha cobrancas com padrao generico (ex: "apple.com/bill") - tanto no
    que foi digitado no chat quanto no extrato bancario sincronizado - que
    ainda nao tem apelido definido (apelidos_gasto), candidatas a perguntar
    pro Alex o que cada uma e (zero custo de IA - so reconhecimento de
    texto). Devolve (descricao_normalizada, valor, mensagem) unicos - mesma
    descricao+valor nao repete, mesmo aparecendo varias vezes no
    historico."""
    ja_com_apelido = {
        (a["descricao_normalizada"], a["valor"])
        for a in conn.execute("SELECT descricao_normalizada, valor FROM apelidos_gasto").fetchall()
    }

    candidatos: dict[tuple[str, float], str] = {}

    rows_expenses = conn.execute(
        "SELECT amount AS valor, description, source_text FROM expenses WHERE tipo = 'real'"
    ).fetchall()
    for r in rows_expenses:
        descricao = (r["description"] or r["source_text"] or "").strip()
        if gastos.e_cobranca_generica(descricao):
            chave = (descricao.lower(), r["valor"])
            if chave not in ja_com_apelido:
                candidatos[chave] = descricao

    # valor/descricao sao criptografados em repouso - db.list_all_bank_transactions
    # ja descriptografa; o filtro "valor < 0" (antes no SQL) fica em Python.
    for r in db.list_all_bank_transactions(conn):
        if r["valor"] is None or r["valor"] >= 0:
            continue
        valor = -r["valor"]
        descricao = (r["descricao"] or "").strip()
        if gastos.e_cobranca_generica(descricao):
            chave = (descricao.lower(), valor)
            if chave not in ja_com_apelido:
                candidatos[chave] = descricao

    avisos = []
    for (descricao_norm, valor), descricao_original in candidatos.items():
        avisos.append((
            descricao_norm,
            valor,
            f"Cobrança de R$ {valor:.2f} em \"{descricao_original}\" - qual assinatura e essa?",
        ))
    return avisos


def _gastos_reais_unificados_para_deteccao(conn) -> list[dict]:
    """Mesma unificacao de expenses (digitado no chat) + bank_transactions
    (extrato sincronizado) que app.py._gastos_reais_unificados ja usa pra
    detectar_gastos_recorrentes - reaproveitada aqui pra nao ter dois
    conceitos diferentes de "todo gasto real" no projeto. Fica em
    notificacoes.py (nao importa de app.py, que importa notificacoes - ver
    de fato o mesmo formato de dict que gastos.py espera)."""
    repetidos = db.gastos_chat_repetidos_no_banco(conn)
    expenses_reais = conn.execute(
        "SELECT id, amount, category, description, source_text, created_at FROM expenses WHERE tipo = 'real'"
    ).fetchall()
    unificado = [
        {k: r[k] for k in ("amount", "category", "description", "source_text", "created_at")}
        for r in expenses_reais
        if r["id"] not in repetidos
    ]
    for r in db.list_all_bank_transactions(conn):
        if r["valor"] is None or r["valor"] >= 0:
            continue
        unificado.append(
            {
                "amount": -r["valor"],
                "category": r["categoria"] or "outros",
                "description": r["descricao"],
                "source_text": None,
                "created_at": r["data"],
            }
        )
    apelidos = {(a["descricao_normalizada"], a["valor"]): a["apelido"] for a in db.list_apelidos_gasto(conn)}
    return gastos.aplicar_apelidos(unificado, apelidos)


def assinaturas_aumento_preco(conn, hoje: date | None = None) -> list[tuple[str, float, str]]:
    """Reaproveita gastos.detectar_aumento_assinatura (que por sua vez
    reaproveita o mesmo agrupamento de detectar_gastos_recorrentes, ja usado
    na aba Gastos pra achar assinaturas fixas) - so acrescenta o aviso
    quando uma assinatura ja conhecida vier com o valor mais recente bem
    acima do que sempre foi. Devolve (descricao_normalizada, valor_novo,
    mensagem) - mesma forma de cobrancas_genericas_sem_rotulo, pra app.py
    deduplicar por descricao+valor (um aumento novo, com valor diferente do
    ultimo aviso, vira um aviso novo sozinho se a assinatura subir de novo)."""
    hoje = hoje or date.today()
    unificado = _gastos_reais_unificados_para_deteccao(conn)

    avisos = []
    for a in gastos.detectar_aumento_assinatura(unificado, hoje):
        msg = (
            f"\"{a['descricao']}\" ficou mais cara: de R$ {a['valor_anterior_medio']:.2f} pra "
            f"R$ {a['valor_novo']:.2f} ({a['aumento_pct']:.0f}% a mais)."
        )
        avisos.append((a["descricao"].strip().lower(), a["valor_novo"], msg))
    return avisos


def _total_gasto_entre(conn, inicio: date, fim: date) -> float:
    """So conta gasto 'real' (ja aconteceu) - um gasto so cogitado/planejado
    nao deveria disparar alerta de "gastou demais essa semana", ja que pode
    nem chegar a acontecer."""
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses "
        f"WHERE {_DIA_GASTO} BETWEEN ? AND ? AND tipo = 'real'",
        (inicio.isoformat(), fim.isoformat()),
    ).fetchone()
    return row["total"]


def gasto_semana_elevado(conn, limiar: float = 1.4) -> str | None:
    """Compara o gasto da semana atual (ate hoje) com a media das 3 semanas
    anteriores completas."""
    hoje = date.today()
    inicio_semana_atual = hoje - timedelta(days=hoje.weekday())
    total_atual = _total_gasto_entre(conn, inicio_semana_atual, hoje)

    totais_anteriores = []
    for i in range(1, 4):
        fim = inicio_semana_atual - timedelta(days=1 + 7 * (i - 1))
        inicio = fim - timedelta(days=6)
        totais_anteriores.append(_total_gasto_entre(conn, inicio, fim))

    media = sum(totais_anteriores) / len(totais_anteriores) if totais_anteriores else 0
    if media <= 0 or total_atual < limiar * media:
        return None
    return (
        f"Gasto dessa semana já esta em R$ {total_atual:.2f}, "
        f"acima da media das últimas semanas (R$ {media:.2f})."
    )


_DIA_SEMANA_COM_ARTIGO = {
    0: "numa segunda-feira",
    1: "numa terca-feira",
    2: "numa quarta-feira",
    3: "numa quinta-feira",
    4: "numa sexta-feira",
    5: "num sabado",
    6: "num domingo",
}


def gasto_dia_semana_atipico(
    conn, hoje: date | None = None, semanas: int = 4, limiar: float = 1.6
) -> str | None:
    """Pega um padrao que o total da semana (gasto_semana_elevado) esconde:
    uma semana pode fechar dentro da media e ainda assim ter um dia
    especifico bem fora do normal - ex: sexta sempre foi baixa e hoje veio
    3x mais alta, mesmo que o resto da semana compense. Compara o gasto de
    hoje com a media do MESMO dia da semana nas ultimas `semanas`
    ocorrencias (nao com a semana inteira)."""
    hoje = hoje or date.today()
    total_hoje = _total_gasto_entre(conn, hoje, hoje)
    if total_hoje <= 0:
        return None

    amostras = []
    for i in range(1, semanas + 1):
        dia = hoje - timedelta(days=7 * i)
        total_dia = _total_gasto_entre(conn, dia, dia)
        if total_dia > 0:
            amostras.append(total_dia)
    if len(amostras) < 2:
        return None  # historico curto demais desse dia da semana pra comparar direito

    media = sum(amostras) / len(amostras)
    if media <= 0 or total_hoje < limiar * media:
        return None

    dia_semana = _DIA_SEMANA_COM_ARTIGO[hoje.weekday()]
    return (
        f"Gasto de hoje (R$ {total_hoje:.2f}) esta bem acima do que costuma ser "
        f"{dia_semana} (media de R$ {media:.2f})."
    )


def gastos_fora_do_padrao_categoria(
    conn, hoje: date | None = None, meses_historico: int = 3, desvios: float = 2.0, minimo_amostras: int = 5
) -> list[tuple[int, str]]:
    """Fase 5 (US-C17): extensao de gasto_dia_semana_atipico (mesmo mecanismo
    - "isso hoje esta fora do padrao?" - so que olhando por outro angulo).
    Em vez do TOTAL do dia vs o mesmo dia da semana, compara CADA gasto
    individual registrado hoje com a media + desvio-padrao (aprendizado.py)
    dos gastos historicos da MESMA categoria - pega um gasto pontual fora do
    normal mesmo quando o dia inteiro nao chama atencao (ex: 1 gasto de
    R$800 em "mercado", categoria que raramente passa de R$150). Categoria
    com historico curto demais (`minimo_amostras`) e ignorada - sem dado
    suficiente pra saber o que e "normal" ainda."""
    hoje = hoje or date.today()
    inicio_historico = (hoje - timedelta(days=30 * meses_historico)).isoformat()
    gastos_hoje = conn.execute(
        f"SELECT id, category, amount FROM expenses WHERE tipo = 'real' AND {_DIA_GASTO} = ?",
        (hoje.isoformat(),),
    ).fetchall()
    avisos = []
    for g in gastos_hoje:
        historico = conn.execute(
            f"""SELECT amount FROM expenses
               WHERE tipo = 'real' AND category = ? AND id != ?
                 AND {_DIA_GASTO} >= ? AND {_DIA_GASTO} < ?""",
            (g["category"], g["id"], inicio_historico, hoje.isoformat()),
        ).fetchall()
        valores = [h["amount"] for h in historico]
        if len(valores) < minimo_amostras:
            continue
        media, desvio_padrao = aprendizado.media_e_desvio_padrao(valores)
        # Categoria sem variacao historica (ex: sempre a mesma assinatura de
        # R$30) tem desvio-padrao 0 - "X desvios acima da media" nao faz
        # sentido nesse caso (qualquer valor diferente seria "infinitos
        # desvios"), entao usa 50% acima da media constante como limiar.
        limiar = media + desvios * desvio_padrao if desvio_padrao > 0 else media * 1.5
        if g["amount"] <= limiar:
            continue
        avisos.append(
            (
                g["id"],
                f"Gasto de R$ {g['amount']:.2f} em \"{g['category']}\" está bem acima do "
                f"normal pra essa categoria (média de R$ {media:.2f}).",
            )
        )
    return avisos


def garantias_vencendo(conn, hoje: date | None = None, dias_aviso: int = 15) -> list[tuple[int, str]]:
    """Fase 5 (US-C18): garantia cujo prazo vence em ate `dias_aviso` dias (ou
    ja venceu). Dedup e pela propria coluna `notificado` da garantia (nao
    pela tabela generica notificacoes_enviadas) - o pedido explicito da
    historia e um flag por garantia, entao so filtra o que ainda nao foi
    avisado; quem chama marca `notificado=1` depois de mandar de verdade."""
    hoje = hoje or date.today()
    avisos = []
    for g in db.list_garantias(conn):
        if g["notificado"]:
            continue
        compra = date.fromisoformat(g["data_compra"])
        vencimento = vida.somar_meses(compra, g["prazo_garantia_meses"])
        dias_ate = (vencimento - hoje).days
        if dias_ate > dias_aviso:
            continue
        # 08/11 (rodada 3): plural de verdade, "ha" com acento, "amanha" (nada de "dia(s)")
        if dias_ate < 0:
            quando = f"venceu há {_dias_txt(-dias_ate)}"
        elif dias_ate == 0:
            quando = "vence hoje"
        elif dias_ate == 1:
            quando = "vence amanhã"
        else:
            quando = f"vence em {_dias_txt(dias_ate)}"
        avisos.append((g["id"], f"Garantia de \"{g['produto']}\" {quando} ({vencimento.strftime('%d/%m/%Y')})."))
    return avisos


def sinal_sobrecarga(tarefas_atrasadas: int, sono_ruim: bool, semana_pesada: bool) -> dict:
    """Fase 5 (US-C22): combina sinais independentes numa pontuacao simples
    de sobrecarga - 1 ponto por sinal presente. `tarefas_atrasadas` so conta
    como sinal a partir de 3 (uma unica tarefa atrasada e vida normal, nao
    sobrecarga). Limiar padrao de "sobrecarregado" e 2 de 3 sinais - um
    sinal isolado ainda e dia normal, dois ou mais juntos que indicam
    sobrecarga de verdade.

    `semana_pesada` e o sinal de deteccao de "semana que vem esta cheia"
    (US-C13, historia de outro agente do mesmo grupo/leva - nao integrada
    neste branch ainda). O chamador passa False ate isso ser mesclado; ver
    a nota em progress-grupo-c.txt. Quando integrado, o score passa a valer
    com os 3 sinais automaticamente, sem mudar nada aqui."""
    sinais = []
    if tarefas_atrasadas >= 3:
        sinais.append("tarefas atrasadas")
    if sono_ruim:
        sinais.append("sono ruim")
    if semana_pesada:
        sinais.append("semana pesada")
    pontuacao = len(sinais)
    return {"pontuacao": pontuacao, "sinais": sinais, "sobrecarregado": pontuacao >= 2}


def proxima_ocorrencia_lembrete(data_base: date, recorrente: bool, hoje: date) -> date:
    """Pra lembrete unico, a proxima ocorrencia e a propria data. Pra
    recorrente (anual - tipo validade de licenca, exame medico, seguro),
    acha o proximo aniversario dessa data a partir de hoje. Publica (nao so
    interna) porque /api/lembretes tambem usa pra mostrar a proxima data +
    dias restantes na tela, nao so lembretes_proximos aqui embaixo."""
    if not recorrente:
        return data_base
    for ano in (hoje.year, hoje.year + 1):
        try:
            candidata = date(ano, data_base.month, data_base.day)
        except ValueError:
            candidata = date(ano, data_base.month, 28)  # 29 de fevereiro em ano nao bissexto
        if candidata >= hoje:
            return candidata
    return data_base


def lembretes_proximos(conn, dias: int = 7) -> list[tuple[int, str]]:
    """Lembretes (unicos ou recorrentes) cuja proxima ocorrencia cai dentro
    da janela de `dias` a partir de hoje."""
    hoje = date.today()
    avisos = []
    for row in conn.execute("SELECT * FROM lembretes").fetchall():
        # leva 08/11: uma data crua ("15/03", vazia) derrubava a lista inteira a cada tick de 5 min
        try:
            # rodada 3: lembrete antigo gravado com hora ("2026-11-15T09:00") vale pelo dia (db.data_iso)
            data_base = date.fromisoformat(db.data_iso(row["data"]))
        except (TypeError, ValueError):
            log.warning("lembretes_proximos: data invalida no lembrete %s: %r", row["id"], row["data"])
            continue
        proxima = proxima_ocorrencia_lembrete(data_base, bool(row["recorrente"]), hoje)
        dias_restantes = (proxima - hoje).days
        if not (0 <= dias_restantes <= dias):
            continue
        if dias_restantes == 0:
            quando = "e hoje"
        elif dias_restantes == 1:
            quando = "e amanhã"
        else:
            quando = f"e em {dias_restantes} dias"
        msg = f"\"{row['titulo']}\" {quando} ({proxima.strftime('%d/%m')})."
        sugestao = vida.sugestao_acao_data(row["titulo"])
        if sugestao:
            msg = f"{msg} {sugestao}"
        avisos.append((row["id"], msg))
    return avisos


HORA_PADRAO_DESPERTAR = "09:00"


def lembretes_para_despertar(conn, agora: datetime | None = None) -> list[tuple[int, str]]:
    """Fase 6 (US-E3): lembretes com "Desperta voce" ligado (coluna
    `despertar`) cuja proxima ocorrencia e HOJE e cujo horario (coluna `hora`
    se existir, senao HORA_PADRAO_DESPERTAR) ja chegou. A deduplicacao por
    dia fica com quem chama (ja_notificou_hoje)."""
    agora = agora or datetime.now()
    hoje = agora.date()
    avisos = []
    for row in conn.execute("SELECT * FROM lembretes WHERE despertar = 1").fetchall():
        try:
            # leva 08/11 (rodada 3): lembrete antigo com hora ("2026-11-15T09:00") vale pelo dia (db.data_iso)
            base = date.fromisoformat(db.data_iso(row["data"]))
        except (TypeError, ValueError):
            log.warning("lembretes_para_despertar: data invalida no lembrete %s: %r", row["id"], row["data"])
            continue
        if proxima_ocorrencia_lembrete(base, bool(row["recorrente"]), hoje) != hoje:
            continue
        hora_txt = (row["hora"] if "hora" in row.keys() else None) or HORA_PADRAO_DESPERTAR
        try:
            h, m = (int(x) for x in str(hora_txt).split(":")[:2])
        except ValueError:
            h, m = 9, 0
        if (agora.hour, agora.minute) < (h, m):
            continue
        avisos.append((row["id"], f"Hoje: \"{row['titulo']}\"."))
    return avisos


def planejamento_semanal_devido(agora: datetime | None = None) -> bool:
    """Verdadeiro na janela de 5min em torno de domingo as 20:30 - o momento
    que o Alex escolheu pra parar e pensar na semana que comeca, puxando um
    push que pergunta se ele ja sabe a agenda da semana. A deduplicacao por
    dia (ja_notificou_hoje, em app.py) garante que so dispara uma vez mesmo
    rodando a cada 5min dentro dessa janela."""
    agora = agora or datetime.now()
    if agora.weekday() != 6:  # segunda=0 ... domingo=6
        return False
    alvo = agora.replace(hour=20, minute=30, second=0, microsecond=0)
    return alvo <= agora < alvo + timedelta(minutes=5)


def semana_pesada_aviso(conn, hoje: date | None = None) -> str | None:
    """US-C13: compara quantos itens a proxima semana ja tem marcados com a
    mediana das ultimas semanas do proprio usuario (aprendizado.
    semana_pesada - estatistica pura sobre o historico, reaproveitada em vez
    de um numero fixo arbitrario). Pensado pra disparar junto do
    planejamento semanal de domingo (planejamento_semanal_devido acima,
    TODO #15) - app.py decide O QUANDO, essa funcao so decide O QUE dizer."""
    hoje = hoje or date.today()
    inicio_proxima = hoje - timedelta(days=hoje.weekday()) + timedelta(days=7)
    fim_proxima = inicio_proxima + timedelta(days=6)
    contagem_proxima = aprendizado.contagem_itens_semana(conn, inicio_proxima, fim_proxima)
    historico = aprendizado.carga_semanal_historica(conn, hoje)
    resultado = aprendizado.semana_pesada(contagem_proxima, historico)
    if not resultado["sobrecarregada"]:
        return None
    return (
        # 08/11 (rodada 3): sem "(s)" - so chega aqui com 3+ itens (aprendizado.semana_pesada: mediana >= 1, +2)
        f"A semana que vem já está com {contagem_proxima} compromissos e tarefas marcados, "
        f"bem acima do teu normal (mediana de {resultado['mediana_historica']:.0f} nas últimas "
        f"{resultado['amostras']} semanas). Vale se planejar com folga."
    )


def hora_de_dormir_devida(agora: datetime | None = None) -> bool:
    """Verdadeiro na janela de 5min em torno das 22h - o horario que o Alex
    escolheu pra comecar a desacelerar pro sono, todo dia."""
    agora = agora or datetime.now()
    alvo = agora.replace(hour=22, minute=0, second=0, microsecond=0)
    return alvo <= agora < alvo + timedelta(minutes=5)


def fechamento_noturno_devido(agora: datetime | None = None) -> bool:
    """Verdadeiro na janela de 5min em torno das 21h - fecha o dia de forma
    ATIVA (manda push sozinho) em vez de esperar o Alex abrir a aba Painel
    pra ver o fechamento. Uma hora antes da hora_de_dormir de proposito, pra
    nao empilhar dois avisos no mesmo minuto."""
    agora = agora or datetime.now()
    alvo = agora.replace(hour=21, minute=0, second=0, microsecond=0)
    return alvo <= agora < alvo + timedelta(minutes=5)


def _total_gasto_dia(conn, dia: date) -> float:
    row = conn.execute(
        f"SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE {_DIA_GASTO} = ? AND tipo = 'real'",
        (dia.isoformat(),),
    ).fetchone()
    return row["total"]


def mensagem_fechamento_noturno(conn, hoje: date | None = None) -> str:
    """Monta o texto do fechamento ativo - deterministico, sem IA (roda
    sozinho todo dia, nao vale gastar chamada de IA nisso). O mesmo par
    concluidas/pendentes que a aba Painel ja mostra, mais o gasto do dia,
    resumido numa mensagem so."""
    hoje = hoje or date.today()
    concluidas = conn.execute(
        f"SELECT COUNT(*) AS n FROM tasks WHERE completed_at IS NOT NULL AND {_DIA_CONCLUSAO} = ?",
        (hoje.isoformat(),),
    ).fetchone()["n"]
    pendentes = conn.execute(
        "SELECT title FROM tasks WHERE completed_at IS NULL AND due_date = ? "
        "ORDER BY hora IS NULL, hora",
        (hoje.isoformat(),),
    ).fetchall()
    gasto = _total_gasto_dia(conn, hoje)

    partes = []
    if concluidas == 0:
        partes.append("Nenhuma tarefa concluída hoje.")
    elif concluidas == 1:
        partes.append("1 tarefa concluída hoje.")
    else:
        partes.append(f"{concluidas} tarefas concluídas hoje.")

    if pendentes:
        titulos = ", ".join(r["title"] for r in pendentes)
        partes.append(f"Ficou pendente: {titulos}.")

    if gasto > 0:
        partes.append(f"Gasto do dia: R$ {gasto:.2f}.")

    return " ".join(partes)


def resumo_manha_gastos_pendentes(conn, hoje: date | None = None) -> str:
    """Parte do resumo falado da manha (US-C11, TTS ja existente no chat -
    ver falarTexto em app.js) que NAO depende de rede - gasto de ontem +
    quantas tarefas ficaram pendentes. A parte de agenda (iCloud via CalDAV,
    instavel) fica em app.py, que ja tem o padrao de buscar com seguranca
    (_eventos_de_hoje_com_seguranca) - notificacoes.py de proposito nunca
    faz chamada de rede, pra ficar testavel isolado como o resto do modulo."""
    hoje = hoje or date.today()
    ontem = hoje - timedelta(days=1)
    gasto_ontem = _total_gasto_dia(conn, ontem)
    pendentes = conn.execute(
        "SELECT COUNT(*) AS n FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL"
    ).fetchone()["n"]

    partes = []
    if gasto_ontem > 0:
        partes.append(f"Ontem tu gastou R$ {gasto_ontem:.2f}.")
    else:
        partes.append("Ontem tu não registrou gasto nenhum.")
    if pendentes == 0:
        partes.append("Nenhuma tarefa pendente.")
    elif pendentes == 1:
        partes.append("1 tarefa ainda pendente.")
    else:
        partes.append(f"{pendentes} tarefas ainda pendentes.")
    return " ".join(partes)


def currency_voo_baixa(conn, limiar_dias: int = 21) -> str | None:
    """Faz tempo demais desde o ultimo voo REALIZADO (com horas registradas -
    um voo so agendado nao conta) - um lembrete gentil pra nao perder o
    ritmo do curso. None se nunca voou ainda ou se ainda esta dentro do
    limiar."""
    hoje = date.today()
    ultima = conn.execute(
        "SELECT MAX(data) AS ultima FROM voos WHERE horas IS NOT NULL AND data <= ? "
        "AND COALESCE(tipo, '') <> 'simulador'",
        (hoje.isoformat(),),
    ).fetchone()["ultima"]
    if not ultima:
        return None
    try:
        dia_voo = date.fromisoformat(str(ultima)[:10])
    except ValueError:
        log.warning("currency_voo_baixa: data invalida no ultimo voo: %r", ultima)
        return None
    dias = (hoje - dia_voo).days
    if dias < limiar_dias:
        return None
    # leva 08/11: "Faz 383 dias que voce nao voa" assusta e soa robo - a data do ultimo voo diz o mesmo
    quando = dia_voo.strftime("%d/%m") if dia_voo.year == hoje.year else dia_voo.strftime("%d/%m/%Y")
    return f"Teu último voo foi em {quando}. Bora marcar o próximo pra não perder o ritmo?"


def montar_mensagem_agrupada(itens: list[tuple[str, str]]) -> tuple[str, str]:
    """Fase 5 (US-C4): junta varios avisos (titulo, corpo) numa unica
    mensagem - usado pelo modo de notificacao agrupada (nao-urgentes numa
    janela curta viram um push/Telegram so, em vez de um por aviso), pra nao
    virar 5 notificacoes separadas em 2 minutos. Com um item so, devolve ele
    sem alterar (mesmo formato de sempre - a rota so agrupa de verdade
    quando ha mais de um pra juntar)."""
    if not itens:
        return "", ""
    if len(itens) == 1:
        return itens[0]
    titulo = f"{len(itens)} avisos"
    corpo = "\n".join(f"• {t}: {c}" for t, c in itens)
    return titulo, corpo


def voos_de_hoje_com_horario(conn, hoje: date | None = None) -> list[dict]:
    """Voos de hoje com horario marcado que ainda nao aconteceram (sem
    'horas' voadas registradas ainda) - candidatos pra calcular a hora de
    sair de casa. So identifica QUAIS voos checar; o calculo em si (trajeto
    via Maps, que pede rede) e a decisao de "esta perto o bastante pra
    avisar" ficam em app.py (verificar_e_notificar), pra esta funcao
    continuar pura e testavel so com SQLite, como as outras deste modulo."""
    hoje = hoje or date.today()
    rows = conn.execute(
        "SELECT id, destino, data, hora FROM voos WHERE data = ? AND hora IS NOT NULL AND horas IS NULL",
        (hoje.isoformat(),),
    ).fetchall()
    return [dict(r) for r in rows]


# ---- Fase 6, US-E8: proatividade unificada ---------------------------------
# Cada checagem abaixo reusa o MESMO calculo que a tela/API correspondente ja
# usa (vida.habito_passou_batido, vida.fracao_limite_cartao,
# vida.calcular_projeto) - nunca recalcula do zero. app.py so decide dedup
# (ja_notificado_alguma_vez/ja_notificou_hoje) e despacha pelo pipeline
# unico de verificar_e_notificar (silencioso/hiperfoco/viagem/agrupamento) -
# nenhum caminho paralelo de envio.

def habitos_passaram_batido(conn, agora: datetime | None = None) -> list[tuple[int, str]]:
    """Usa vida.habito_passou_batido (mesmo calculo que /api/habitos ja
    expoe em 'passou_batido' por habito) pra achar habitos com horario
    definido que passaram 1h do horario sem serem marcados hoje. So
    identifica e monta o texto - dedup (uma vez por dia) fica com quem
    chama (ja_notificou_hoje)."""
    agora = agora or datetime.now()
    hoje = agora.date()
    hoje_iso = hoje.isoformat()
    inicio_semana = (hoje - timedelta(days=hoje.weekday())).isoformat()
    fim_semana = (hoje + timedelta(days=6 - hoje.weekday())).isoformat()
    avisos = []
    for row in db.list_habitos(conn):
        habito = dict(row)
        marcado_hoje = db.habito_marcado(conn, hoje_iso, habito["id"])
        vezes_feitas_semana = len(db.marcacoes_habito_no_periodo(conn, habito["id"], inicio_semana, fim_semana))
        if not vida.habito_passou_batido(habito, agora, marcado_hoje, vezes_feitas_semana):
            continue
        avisos.append(
            (habito["id"], f"{habito['horario']} já foi e o hábito {habito['nome']} segue intocado.")
        )
    return avisos


def _tarefa_horario_ligado(conn) -> bool:
    try:
        from assistente import avisos as avisos_assistente

        return avisos_assistente.esta_ligado("tarefa_horario", conn=conn)
    except Exception:  # noqa: BLE001
        return True


def tarefas_horario_passou(conn, agora: datetime | None = None, minutos_depois: int = 30,
                           caminho_min=None) -> list[tuple[int, str]]:
    """Complementa tarefas_com_horario_chegando (aviso ANTES/na hora): um
    segundo aviso, `minutos_depois` apos o horario marcado, se a tarefa
    continuar pendente - so constata o fato (ainda da tempo hoje), sem
    cobranca nem diminutivo. O titulo entra entre aspas no comeco do corpo
    (mesmo padrao de tarefas_paradas acima) - o exemplo do PRD ("a tarefa
    era 14:00...") fica intacto depois das aspas, so identifica QUAL tarefa
    quando ha mais de uma pendente. Dedup (uma vez por dia) fica com quem
    chama.
    08/11 (frente A): sai `minutos_depois` depois do aviso da hora (tarefa_horario), nunca no mesmo tick
    dele (servidor voltando de parada mandava os dois juntos) - mesma quantidade, so espaca. Compromisso
    de SAIR ganha texto de saida (sem "ainda da tempo de resolver hoje")."""
    agora = agora or datetime.now()
    hoje = agora.date().isoformat()
    limite = (agora - timedelta(minutes=minutos_depois)).strftime("%H:%M")
    rows = conn.execute(
        """SELECT * FROM tasks
           WHERE completed_at IS NULL AND due_date = ? AND hora IS NOT NULL AND hora <= ?""",
        (hoje, limite),
    ).fetchall()
    # aviso da hora desligado na tela Avisos: ele nunca sai, entao nao segura este
    esperar_o_da_hora = bool(rows) and _tarefa_horario_ligado(conn)
    # 08/11 (rodada 3): a insistencia do aviso da hora manda "Ultima chamada" no ultimo passo (30 min): este
    # sai 5 min depois dela, nunca no mesmo tick. So espaca: a tarefa continua tendo os mesmos avisos.
    espera = max(minutos_depois, max(INSISTENCIA.get("tarefa_horario") or (0,)) + 5)
    avisos = []
    for r in rows:
        if esperar_o_da_hora:
            enviado = _notificado_em(conn, "tarefa_horario", r["id"], agora.date())
            if enviado is None or agora < enviado + timedelta(minutes=espera):
                continue
        if e_saida(r):
            # 08/11 (rodada 3): ja avisado hoje = o texto nem sai (dedup em app.py): sem Maps nem commit a cada
            # tick ate a meia-noite (mesmo jeito do tarefas_com_horario_chegando)
            ja = _notificado_em(conn, "tarefa_horario_passou", r["id"], agora.date()) is not None
            msg = texto_saida_depois(conn, r, agora, None if ja else caminho_min, passou=True,
                                     chave=f"tarefa_horario_passou-{r['id']}-{hoje}")
        else:
            msg = f"\"{r['title']}\" - a tarefa era {r['hora']}, ainda dá tempo de resolver hoje."
        avisos.append((r["id"], msg))
    return avisos


def cartoes_perto_ou_estourados(conn, hoje: date | None = None) -> list[tuple[int, str, str, str]]:
    """US-E15: reusa vida.fracao_limite_cartao (o MESMO calculo que
    /api/bancos ja expoe em 'limite_info') pra achar cartao perto (>=90%)
    ou ja estourando (>=100%) do limite manual. So cartoes com limite
    configurado entram - sem limite, fracao_limite_cartao ja devolve None
    (nunca inventa um limite). Devolve (conta_id, nivel, titulo, corpo)."""
    hoje = hoje or date.today()
    ano_mes = hoje.strftime("%Y-%m")
    avisos = []
    for c in db.list_bank_accounts(conn):
        if c["tipo"] != "cartao":
            continue
        gasto_ciclo = db.gasto_mes_conta(conn, c["id"], ano_mes)
        info = vida.fracao_limite_cartao(gasto_ciclo, c.get("limite"))
        if not info:
            continue
        if info["fracao"] >= 1:
            nivel, titulo = "estourado", "Cartão estourou o limite"
        elif info["fracao"] >= 0.9:
            pct = round(info["fracao"] * 100)
            nivel, titulo = "quase", f"Cartão em {pct}% do limite"
        else:
            continue
        if info["sobra"] >= 0:
            corpo = f"{c['banco']}: sobram R$ {info['sobra']:.2f}."
        else:
            corpo = f"{c['banco']}: passou R$ {-info['sobra']:.2f} do limite."
        avisos.append((c["id"], nivel, titulo, corpo))
    return avisos


def renda_perto_de_acabar(conn, hoje: date | None = None, limiar: float = 0.7) -> tuple[str, str, str] | None:
    """Fracao da renda do mes ja gasta (mesma soma de expenses reais +
    extrato bancario que _sobra_do_mes/app.py ja usa) - avisa a partir de
    70% comprometido (nivel 'atencao') ou 100%+ ('estourado'). Sem renda
    registrada no mes, None - nao ha base pra calcular fracao nenhuma."""
    hoje = hoje or date.today()
    ano_mes = hoje.strftime("%Y-%m")
    renda_mes = db.total_incomes_mes(conn, ano_mes)
    if renda_mes <= 0:
        return None
    gasto_mes = db.total_gasto_real_mes(conn, ano_mes)
    fracao = gasto_mes / renda_mes
    if fracao < limiar:
        return None
    pct = round(fracao * 100)
    sobra = renda_mes - gasto_mes
    nivel = "estourado" if fracao >= 1 else "atencao"
    titulo = f"{pct}% da renda já foi"
    corpo = f"sobram R$ {sobra:.2f}." if sobra >= 0 else f"passou R$ {-sobra:.2f} da renda."
    return (nivel, titulo, corpo)


def projetos_juntando_poeira(conn, hoje: date | None = None, dias_aviso: int = 21) -> list[tuple[int, str, str]]:
    """US-E13: projeto ativo (nao pausado, nao concluido) sem NENHUM toque
    ha `dias_aviso` dias ou mais - reusa vida.calcular_projeto (mesmo
    'dias_sem_toque' que /api/projetos ja expoe). Projeto que nunca teve
    etapa concluida usa a propria data de criacao como referencia
    (calcular_projeto devolve None nesse caso - sem esse fallback, um
    projeto criado e esquecido nunca avisaria). O ref de dedup muda quando
    o projeto e tocado de novo (referencia = data do ultimo toque ou
    criacao), entao volta a valer sozinho se ficar parado de novo depois.
    Devolve (ref_dedup, titulo, corpo)."""
    hoje = hoje or date.today()
    avisos = []
    for p in db.list_projetos(conn):
        etapas = db.list_etapas_projeto(conn, p["id"])
        calculo = vida.calcular_projeto(etapas, p["prazo_final"], p["criado_em"], hoje)
        status = vida.status_projeto_calculado(p["status"], p["prazo_final"], calculo["percentual"], hoje)
        if status == "pausado" or calculo["percentual"] >= 100:
            continue
        dias = calculo["dias_sem_toque"]
        if dias is None:
            try:
                referencia = date.fromisoformat((p["criado_em"] or "")[:10])
            except ValueError:
                continue
            dias = (hoje - referencia).days
        else:
            datas_feitas = [e["feita_em"] for e in etapas if e.get("feita_em")]
            try:
                referencia = max(date.fromisoformat(d[:10]) for d in datas_feitas)
            except ValueError:
                continue
        if dias < dias_aviso:
            continue
        ref = vida.id_estavel("projeto_poeira", p["id"], referencia.isoformat())
        avisos.append(
            (
                ref,
                "Tem projeto criando poeira",
                f"\"{p['nome']}\": {dias} dias sem um toque, abre e derruba a menor etapa.",
            )
        )
    return avisos


def _renda_media_mensal(conn, hoje: date, meses: int = 3) -> float:
    """Media da renda registrada nos ultimos `meses` meses fechados - so
    entram meses com renda > 0 (mes sem nenhum lancamento pode so estar
    sem digitar ainda, nao vale puxar a media pra baixo por isso)."""
    valores = []
    for i in range(1, meses + 1):
        ref = vida.somar_meses(hoje.replace(day=1), -i)
        total = db.total_incomes_mes(conn, ref.strftime("%Y-%m"))
        if total > 0:
            valores.append(total)
    return sum(valores) / len(valores) if valores else 0.0


def projecao_mes_seguinte_devida(hoje: date | None = None) -> bool:
    """Verdadeiro nos ultimos 3 dias do mes - a janela em que faz sentido
    projetar como o mes que vem chega, perto o bastante pra reagir (revisar
    assinatura, adiar compra) mas nao cedo demais pro dado do mes atual
    ainda estar mudando muito."""
    hoje = hoje or date.today()
    ultimo_dia_mes = vida.somar_meses(hoje.replace(day=1), 1) - timedelta(days=1)
    return hoje >= ultimo_dia_mes - timedelta(days=2)


def mes_seguinte_apertado(conn, hoje: date | None = None, limiar: float = 0.8) -> tuple[str, float] | None:
    """Projeta o mes seguinte comparando os custos fixos ja conhecidos
    (mesma deteccao de gastos.detectar_gastos_recorrentes que a aba Gastos
    usa) com a media de renda dos ultimos 3 meses - sem renda OU sem custo
    fixo identificado ainda, nao ha base pra projetar nada (None). `limiar`
    e a fracao (custos_fixos/renda_media) a partir da qual vale avisar
    (0.8 = 80% comprometido)."""
    hoje = hoje or date.today()
    renda_media = _renda_media_mensal(conn, hoje)
    if renda_media <= 0:
        return None
    recorrentes = gastos.detectar_gastos_recorrentes(_gastos_reais_unificados_para_deteccao(conn), hoje)
    custos_fixos = gastos.total_gasto_fixo_mensal(recorrentes)
    if custos_fixos <= 0:
        return None
    fracao = custos_fixos / renda_media
    if fracao < limiar:
        return None
    proximo_mes = vida.somar_meses(hoje.replace(day=1), 1)
    nome_mes = vida.NOMES_MES[proximo_mes.month - 1].capitalize()
    return (nome_mes, round(fracao, 4))
