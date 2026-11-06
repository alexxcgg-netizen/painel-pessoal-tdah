"""Pergunta na hora certa (leva 06/11 "painel mais esperto", frente 7 - docs/briefings/2026-11-06-painel-esperto.md).

Alem dos avisos de hora fixa (que continuam TODOS - memoria "avisos: nao reduzir"), lembra pelo contexto:
  - chegou em casa depois das 18h com tarefa de hoje aberta -> "Chegou em casa / Ainda falta 'X' hoje. Da 15 min."
    (Feito / Amanha). Pega a inegociavel, senao a mais curta; tarefa com hora ainda por vir fica de fora (ela tem o
    aviso dela). No maximo 1 por chegada e nunca a mesma tarefa 2x no dia. Se o onde_estou.py ja falou na chegada
    ("Chegou em casa. Proxima: ..."), nao fala de novo.
  - saiu da academia -> "Como foi o treino?" e a ficha do treino ao vivo (card `treino_agora`) no chat. Ja
    registrou o treino de hoje: nao pergunta.

Fila unica de avisos de EVENTO (tambem usada pelo voo da vespera e pelas rotinas descobertas), que sai pelos dois
caminhos que os outros avisos ja usam:
  - push do servidor: `para_push` entra na lista de app.verificar_e_notificar (liga/desliga, silencio, hiperfoco e
    o "ja mandei" de sempre);
  - aviso local do app do iPhone: `para_app` entra em avisos_app.montar com hora = agora + 1 min. O app conta de
    volta o que agendou (avisos_app.carregar_agendados): o que ele ja agendou o servidor nao manda de novo, e depois
    que tocou sai da fila.

Localizacao: so le a tabela `visitas` (onde_estou.py grava). Texto por template, zero IA.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime, time, timedelta

import db
import notificacoes

log = logging.getLogger(__name__)

TIPO_CASA = "casa_tarefa"
TIPO_TREINO = "treino_pergunta"
TIPOS_QUE_PASSAM_SILENCIO = {"voo_decisao"}  # hora do voo nao espera o fim do silencio (app.NOTIFICACOES_URGENTES)
CASA_A_PARTIR = time(18, 0)
CHEGADA_RECENTE_MIN = 45  # = onde_estou.CHEGADA_RECENTE_MIN
SAIDA_RECENTE_MIN = 60
VALE_CASA_MIN = 30
VALE_TREINO_MIN = 90
APP_ANTECEDENCIA_S = 60
FILA = "hora_certa_fila"
CHAVES = "hora_certa_chaves"
SEQ = "hora_certa_seq"
GUARDA_CHAVES_DIAS = 3
URL_CHAT = "/?aba=assistente"
ACOES_CASA = [{"action": "feito", "title": "Feito"}, {"action": "adiar", "title": "Amanhã"}]
_RE_VOO = re.compile(r"\b(voo|simulador)\b")
_RE_ATE = re.compile(r"\s*\((at[eé]) \d{1,2}:\d{2}\)")


def _sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def _json(conn, chave: str, padrao):
    try:
        v = json.loads(db.obter_configuracao(conn, chave) or "null")
    except ValueError:
        return padrao
    return v if isinstance(v, type(padrao)) else padrao


def _salvar(conn, chave: str, valor) -> None:
    db.definir_configuracao(conn, chave, json.dumps(valor, ensure_ascii=False))


def _dt(txt) -> datetime | None:
    try:
        return datetime.fromisoformat(txt) if txt else None
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ a fila

def proximo_ref(conn) -> int:
    n = int(db.obter_configuracao(conn, SEQ) or 0) + 1
    db.definir_configuracao(conn, SEQ, str(n))
    return n


def ja_tem(conn, chave: str) -> bool:
    return chave in _json(conn, CHAVES, {})


def marcar_chave(conn, chave: str, agora: datetime) -> None:
    chaves = _json(conn, CHAVES, {})
    corte = (agora.date() - timedelta(days=GUARDA_CHAVES_DIAS)).isoformat()
    chaves = {k: d for k, d in chaves.items() if isinstance(d, str) and d >= corte}
    chaves[chave] = agora.date().isoformat()
    _salvar(conn, CHAVES, chaves)


def enfileirar(conn, tipo: str, ref: int, titulo: str, corpo: str, agora: datetime, ate: datetime,
               chave: str | None = None, push_apos: datetime | None = None) -> dict | None:
    """Aviso de evento pra sair pelo push e/ou pelo app. `chave` evita criar o mesmo evento 2x. None = ja tinha."""
    if chave and ja_tem(conn, chave):
        return None
    if ate <= agora:
        return None
    item = {"tipo": tipo, "ref": int(ref), "titulo": titulo, "corpo": corpo,
            "desde": agora.isoformat(timespec="seconds"), "ate": ate.isoformat(timespec="seconds")}
    if push_apos:
        item["push_apos"] = push_apos.isoformat(timespec="seconds")
    fila = [i for i in _json(conn, FILA, []) if isinstance(i, dict) and (_dt(i.get("ate")) or agora) > agora]
    fila.append(item)
    _salvar(conn, FILA, fila[-30:])
    if chave:
        marcar_chave(conn, chave, agora)
    return item


def pendentes(conn, agora: datetime) -> list[dict]:
    """Na validade e ainda nao mandados hoje. Limpa o que venceu."""
    fila = [i for i in _json(conn, FILA, []) if isinstance(i, dict)]
    vivos, saida = [], []
    for i in fila:
        desde, ate = _dt(i.get("desde")), _dt(i.get("ate"))
        if not desde or not ate or ate <= agora:
            continue
        vivos.append(i)
        if desde <= agora + timedelta(minutes=1) and not db.ja_notificou_hoje(conn, i["tipo"], i["ref"]):
            saida.append(i)
    if len(vivos) != len(fila):
        _salvar(conn, FILA, vivos)
    return saida


def _silencio(conn, quando: datetime) -> bool:
    return notificacoes.dentro_do_horario_silencioso(
        quando, db.obter_configuracao(conn, "silencio_inicio") or "22:00",
        db.obter_configuracao(conn, "silencio_fim") or "07:00")


def para_push(conn, agora: datetime, agendados: dict | None = None) -> list[tuple]:
    """(tipo, ref, titulo, corpo) pro loop de app.verificar_e_notificar. O que o app do iPhone ja agendou fica de
    fora (e sai da fila depois que tocou)."""
    if agendados is None:
        import avisos_app

        agendados = avisos_app.carregar_agendados(conn, agora)
    try:
        detectar(conn, agora)
    except Exception:
        log.exception("hora_certa: detectar falhou")
    saida = []
    for i in pendentes(conn, agora):
        tag = f"{i['tipo']}-{i['ref']}"
        if agendados.get(tag):
            if min(agendados[tag]) <= agora.timestamp():
                db.marcar_notificado(conn, i["tipo"], i["ref"])  # o app ja tocou
            continue
        espera = _dt(i.get("push_apos"))
        if espera and agora < espera:
            continue  # o app do iPhone tem uns minutos pra pegar e agendar (avisar_evento)
        saida.append((i["tipo"], i["ref"], i["titulo"], i["corpo"]))
    return saida


def para_app(conn, agora: datetime, agendados: dict | None = None) -> list[tuple]:
    """(tipo, ref, quando, titulo, corpo) pra avisos_app.montar: o app agenda pra daqui a 1 min (ou mantem a hora
    que ja tinha agendado). O que ja tocou no app sai da fila."""
    agendados = agendados or {}
    try:
        detectar(conn, agora)
    except Exception:
        log.exception("hora_certa: detectar falhou (app)")
    saida = []
    for i in pendentes(conn, agora):
        tag = f"{i['tipo']}-{i['ref']}"
        ja = sorted(agendados.get(tag) or [])
        if ja and ja[0] <= agora.timestamp():
            db.marcar_notificado(conn, i["tipo"], i["ref"])
            continue
        quando = datetime.fromtimestamp(ja[0]) if ja else \
            (agora + timedelta(seconds=APP_ANTECEDENCIA_S + 59)).replace(second=0, microsecond=0)
        if quando > _dt(i["ate"]):
            continue
        if i["tipo"] not in TIPOS_QUE_PASSAM_SILENCIO and _silencio(conn, quando):
            continue
        saida.append((i["tipo"], i["ref"], quando, i["titulo"], i["corpo"]))
    return saida


# ------------------------------------------------------------------ aviso de evento vindo de outro modulo

APP_ATIVO_MIN = 20  # o app contou o que agendou ha menos que isso: ele esta sincronizando (GPS ~5 min)
ESPERA_APP_MIN = 3  # quanto o push espera o app pegar o aviso antes de sair pelo navegador
VALE_EVENTO_MIN = 20


def app_ativo(conn, agora: datetime) -> bool:
    """O app do iPhone sincronizou os avisos ha pouco (avisos_app.gravar_agendados grava `em`)."""
    try:
        import avisos_app

        dados = json.loads(db.obter_configuracao(conn, avisos_app.CHAVE) or "null")
        return isinstance(dados, dict) and agora.timestamp() - float(dados.get("em") or 0) <= APP_ATIVO_MIN * 60
    except (TypeError, ValueError):
        return False


def avisar_evento(conn, tipo: str, titulo: str, corpo: str, agora: datetime, ref_legado: int = 0,
                  vale_min: int = VALE_EVENTO_MIN) -> int:
    """Aviso de evento que nasce fora do tick (onde_vou.py: "Indo pro X?", recado de atraso). Entra na fila
    (aviso local do app + push do tick, sem repetir o que o app agendou). Sem o app sincronizando: manda o push
    na hora como antes (onde_estou._avisar, com `ref_legado`) e marca como mandado, pra o tick nao repetir.
    Devolve o ref da fila (tag `<tipo>-<ref>`; o toque abre o chat, onde esta o card)."""
    ref = proximo_ref(conn)
    ativo = app_ativo(conn, agora)
    enfileirar(conn, tipo, ref, titulo, corpo, agora, agora + timedelta(minutes=vale_min),
               push_apos=agora + timedelta(minutes=ESPERA_APP_MIN) if ativo else None)
    if not ativo:
        import onde_estou

        onde_estou._avisar(conn, tipo, ref_legado or ref, notificacoes.com_emoji(tipo, titulo), corpo, agora)
        db.marcar_notificado(conn, tipo, ref)
    return ref


# ------------------------------------------------------------------ eventos (visitas do iPhone)

def detectar(conn, agora: datetime) -> None:
    """Cria os avisos de chegada em casa / saida da academia que ainda nao existem. Idempotente."""
    try:
        conn.execute("SELECT 1 FROM visitas LIMIT 1")
    except Exception:  # noqa: BLE001 - banco sem a tabela (teste velho)
        return
    _casa(conn, agora)
    _academia(conn, agora)


def _min_estimado(t) -> int | None:
    """So com esforco marcado (sem chute): 5/12/25 min, menos se ja tem passos abertos (foco_ideias)."""
    if not t["esforco"]:
        return None
    import foco_ideias

    return foco_ideias._estimar_min(t["esforco"], t["abertas"] or 0)


def escolher_tarefa(conn, agora: datetime):
    """A tarefa de hoje pra lembrar na chegada: inegociavel primeiro, depois a mais curta. Fica de fora: com hora
    ainda por vir (tem aviso proprio), compromisso (date/balada), voo e o que ja foi lembrado hoje."""
    try:
        linhas = conn.execute(
            """SELECT t.id, t.title, t.hora, t.esforco, COALESCE(t.inegociavel, 0) AS inegociavel, t.estilo,
                      (SELECT COUNT(*) FROM subtasks s WHERE s.task_id = t.id AND s.completed_at IS NULL) AS abertas
               FROM tasks t WHERE t.completed_at IS NULL AND t.recorrencia IS NULL AND t.due_date = ?
                 AND t.arquivada_em IS NULL""",
            (agora.date().isoformat(),),
        ).fetchall()
    except Exception:  # noqa: BLE001 - banco velho sem as colunas novas
        return None
    agora_hm = agora.strftime("%H:%M")
    candidatas = []
    for t in linhas:
        if t["hora"] and t["hora"] > agora_hm:
            continue
        if t["estilo"] in ("date", "balada") or _RE_VOO.search(_sem_acento(t["title"])):
            continue
        if db.ja_notificou_hoje(conn, TIPO_CASA, t["id"]):
            continue
        est = _min_estimado(t)
        candidatas.append((-int(t["inegociavel"] or 0), est if est is not None else 12, t["id"], t))
    if not candidatas:
        return None
    return min(candidatas, key=lambda c: c[:3])[3]


def titulo_frase(titulo: str) -> str:
    t = _RE_ATE.sub("", titulo or "").strip().rstrip(".")
    return t if len(t) <= 60 else t[:59].rstrip() + "…"


def texto_casa(t) -> str:
    est = _min_estimado(t)
    corpo = f"Ainda falta “{titulo_frase(t['title'])}” hoje."
    if est:
        corpo += f" Dá {est} min."
    return corpo


def _casa(conn, agora: datetime) -> None:
    inicio = (agora - timedelta(minutes=CHEGADA_RECENTE_MIN)).isoformat(timespec="seconds")
    linhas = conn.execute(
        "SELECT * FROM visitas WHERE lugar = 'casa' AND saida IS NULL AND chegada IS NOT NULL "
        "AND chegada >= ? AND chegada <= ? ORDER BY chegada DESC",
        (inicio, (agora + timedelta(minutes=10)).isoformat(timespec="seconds")),
    ).fetchall()
    for v in linhas:
        chave = f"casa:{v['id']}"
        if ja_tem(conn, chave):
            continue
        chegada = _dt(v["chegada"])
        if not chegada or chegada.date() != agora.date() or chegada.time() < CASA_A_PARTIR:
            continue
        if _silencio(conn, agora):
            continue
        try:
            import onde_estou

            if onde_estou.mensagem_chegada(conn, v, agora):
                marcar_chave(conn, chave, agora)  # o onde_estou ja falou nessa chegada: um aviso por chegada
                continue
        except Exception:  # noqa: BLE001
            pass
        t = escolher_tarefa(conn, agora)
        if not t:
            marcar_chave(conn, chave, agora)
            continue
        enfileirar(conn, TIPO_CASA, t["id"], "Chegou em casa", texto_casa(t), agora,
                   agora + timedelta(minutes=VALE_CASA_MIN), chave=chave)


def _treino_hoje(conn, hoje: str) -> tuple[bool, int | None]:
    """(ja registrou o treino de hoje, id da sessao aberta de hoje)."""
    try:
        feito = conn.execute("SELECT 1 FROM treinos WHERE data = ? LIMIT 1", (hoje,)).fetchone() is not None
    except Exception:  # noqa: BLE001
        feito = False
    try:
        r = conn.execute(
            "SELECT id, concluido_em FROM treino_sessoes WHERE data = ? ORDER BY concluido_em IS NULL DESC, id DESC LIMIT 1",
            (hoje,),
        ).fetchone()
    except Exception:  # noqa: BLE001
        r = None
    if r and r["concluido_em"]:
        return True, None
    return feito and not r, (r["id"] if r else None)


def _academia(conn, agora: datetime) -> None:
    linhas = conn.execute(
        "SELECT * FROM visitas WHERE lugar IS NOT NULL AND saida IS NOT NULL AND saida >= ? AND saida <= ? "
        "ORDER BY saida DESC",
        ((agora - timedelta(minutes=SAIDA_RECENTE_MIN)).isoformat(timespec="seconds"),
         (agora + timedelta(minutes=10)).isoformat(timespec="seconds")),
    ).fetchall()
    for v in linhas:
        if "academia" not in _sem_acento(v["lugar"]):
            continue
        chave = f"academia:{v['id']}"
        if ja_tem(conn, chave):
            continue
        hoje = agora.date().isoformat()
        if db.ja_notificou_hoje(conn, "treino_pergunta_chat"):
            marcar_chave(conn, chave, agora)  # uma pergunta por dia (saiu e voltou na academia)
            continue
        feito, sessao_id = _treino_hoje(conn, hoje)
        if feito:
            marcar_chave(conn, chave, agora)
            continue
        card, grupo = None, None
        try:
            import cards

            if sessao_id is None:
                import treino_vivo

                fichas = db.list_fichas_treino(conn)
                if fichas:
                    ficha = treino_vivo.proxima_da_rotacao(fichas, db.ultimo_treino_por_grupo(conn))
                    if ficha:
                        sessao_id = db.abrir_sessao_treino(conn, ficha["id"], hoje)
                        card = cards.card_treino_agora(conn, sessao_id, "rotacao")
            else:
                card = cards.card_treino_agora(conn, sessao_id)
            grupo = (card or {}).get("data", {}).get("grupo")
        except Exception:  # noqa: BLE001 - sem ficha/sessao: pergunta so com texto
            log.exception("hora_certa: ficha do treino falhou")
            card = None
        if card:
            texto = f"Saiu da academia. Como foi? Marca o que tu fez de {grupo.lower()} que eu registro." if grupo else \
                "Saiu da academia. Como foi? Marca o que tu fez que eu registro."
            corpo = f"Marca na ficha de {grupo.lower()} o que tu fez." if grupo else "Marca na ficha o que tu fez."
        else:
            texto = "Saiu da academia. Como foi o treino? Me conta o que tu fez que eu registro."
            corpo = "Me conta no chat o que tu fez que eu registro."
        import cards as _cards

        env = _cards.envelope([card] if card else [], texto, [])
        db.salvar_mensagem_chat(conn, "assistant", texto, env["cards"])
        db.marcar_notificado(conn, "treino_pergunta_chat")
        enfileirar(conn, TIPO_TREINO, proximo_ref(conn), "Como foi o treino?", corpo, agora,
                   agora + timedelta(minutes=VALE_TREINO_MIN), chave=chave)


# ------------------------------------------------------------------ botoes do aviso de chegada

def acao_casa(conn, task_id: int, acao: str, agora: datetime) -> dict | None:
    """Feito / Amanha (botao do push "Chegou em casa"). None = tarefa nao existe."""
    t = conn.execute("SELECT id, title, due_date, hora, completed_at FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not t:
        return None
    db.marcar_aviso_aberto(conn, f"{TIPO_CASA}-{task_id}")
    if t["completed_at"]:
        return {"ok": True, "titulo": t["title"], "ja_feita": True}
    if acao == "feito":
        db.complete_task(conn, task_id)
        conn.commit()
        return {"ok": True, "titulo": t["title"], "mensagem": "Feito. Boa."}
    amanha = (agora.date() + timedelta(days=1)).isoformat()
    de = t["due_date"] or agora.date().isoformat()
    conn.execute("UPDATE tasks SET due_date = ? WHERE id = ?", (amanha, task_id))
    if de != amanha:
        import dia_ruim

        dia_ruim.registrar_adiamento(conn, [task_id], de, amanha)
    conn.commit()
    quando = f" às {t['hora']}" if t["hora"] else ""
    return {"ok": True, "titulo": t["title"], "due_date": amanha, "mensagem": f"Passei pra amanhã{quando}."}
