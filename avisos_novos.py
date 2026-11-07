"""avisos_novos.py - os 4 assuntos novos do catalogo que so tinham texto (leva 07/11/2026 (2), ver
docs/briefings/2026-11-07-lugar-certo-e-avisos.md, "Leva 07/11 (2): avisos novos ligados").

  - `transito_piorou`: tarefa de hoje com lugar, na janela de ~60 min antes da hora de sair: o transito de
    agora (casa -> lugar) ficou >= 10 min pior que a base do plano -> nova hora de sair. No maximo 1 consulta
    ao Maps por tarefa a cada 15 min, so dentro da janela, so com ele em casa e fora do silencio; 1x por tarefa
    por dia. (tick de 5 min: `avisos_transito`)
  - `chegou_casa`: visita reconhecida como casa depois de >= 30 min fora, com tarefa de hoje que era FORA ainda
    aberta -> "marca o que fez". Uma fala de casa por chegada (mesma chave do `casa_tarefa` do hora_certa: quem
    chegar primeiro fala, o outro nao repete) e no maximo 1 a cada 3 h. (gancho em onde_estou.reagir:
    `chegou_casa`)
  - `meta_batida`: agua do dia (1x por dia), horas de voo (total e requisitos do RBAC, 1x por meta) e as metas
    de dinheiro guardado (goals, 1x por meta). O que ja estava batido quando isto foi ligado nao avisa.
    (tick: `avisos_meta`)
  - `sequencia`: N dias seguidos (treino, cada remedio diario, cada habito diario, tarefas do dia todas
    feitas) nos marcos 3/5/7/10/14/21/30 -> 1x por marco de cada sequencia. (tick: `avisos_sequencia`)

Texto sempre do catalogo (`avisos_texto`, estilo C, "tu"; o emoji entra no despacho por com_emoji). O tick
(app.verificar_e_notificar) faz liga/desliga, silencio, hiperfoco, fila do app e marcar_notificado como nos
outros; o `chegou_casa` nasce fora do tick e entrega por `avisos_pendentes.entregar`. Nada aqui levanta.
"""
from __future__ import annotations

import json
import logging
import os
import re
import zlib
from datetime import date, datetime, timedelta

import db

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- transito_piorou
TIPO_TRANSITO = "transito_piorou"
TRANSITO_JANELA_MIN = 60  # comeca a olhar 60 min antes da hora de sair
TRANSITO_INTERVALO_MIN = 15  # no maximo 1 consulta por tarefa a cada 15 min
TRANSITO_PIOROU_MIN = 10
TRANSITO_MARGEM_MIN = 5  # a mesma margem do plano (app._saida_pro_compromisso)
TRANSITO_SEM_BASE_MIN = 15  # sem trajeto conhecido: a folga de sempre (app.FOLGA_SEM_TRAJETO_MIN)
CHAVE_EXTRAS = "transito_aviso"
_RE_HORA = re.compile(r"^(\d{1,2}):(\d{2})$")

# ---------------------------------------------------------------- chegou_casa
TIPO_CASA = "chegou_casa"
FORA_MIN = 30
CASA_INTERVALO_H = 3
CHEGADA_RECENTE_MIN = 45  # = onde_estou.CHEGADA_RECENTE_MIN
CHAVE_ULTIMO_CASA = "chegou_casa_ultimo"

# ---------------------------------------------------------------- meta_batida / sequencia
TIPO_META = "meta_batida"
TIPO_SEQUENCIA = "sequencia"
CHAVE_META_BASE = "meta_batida_base"  # 1a passada: o que ja estava batido vira "ja avisado"
MARCOS = (3, 5, 7, 10, 14, 21, 30)
SEQ_OLHA_DIAS = 31
REF_AGUA = 1
REF_VOO_TOTAL = 1_000_000  # + meta de horas (meta nova = aviso novo)
REF_VOO_REQ = {"navegacao": 2_000_001, "noturno": 2_000_002, "instrumentos": 2_000_003}
REF_GOAL = 3_000_000  # + id da meta de dinheiro
NOME_VOO_REQ = {"navegacao": "{m} h de navegação", "noturno": "{m} h de voo noturno",
                "instrumentos": "{m} h de instrumentos"}


def _silencio(conn, agora: datetime) -> bool:
    import notificacoes

    return notificacoes.dentro_do_horario_silencioso(
        agora, db.obter_configuracao(conn, "silencio_inicio") or "22:00",
        db.obter_configuracao(conn, "silencio_fim") or "07:00")


def _dt(v) -> datetime | None:
    try:
        return datetime.fromisoformat(v) if v else None
    except (TypeError, ValueError):
        return None


def _hora_do_dia(dia: date, hhmm: str | None) -> datetime | None:
    m = _RE_HORA.match((hhmm or "").strip())
    if not m or not (0 <= int(m.group(1)) <= 23 and 0 <= int(m.group(2)) <= 59):
        return None
    return datetime.combine(dia, datetime.min.time()) + timedelta(hours=int(m.group(1)), minutes=int(m.group(2)))


def _texto(assunto: str, dados: dict, conn, chave: str, agora: datetime, **ctx) -> tuple[str, str]:
    import avisos_texto

    return avisos_texto.par(assunto, dados, conn=conn, chave=chave, agora=agora, **ctx)


# ================================================================ transito_piorou

def _tempo_padrao(conn, local: str) -> int | None:
    """Minutos de carro casa -> lugar com o transito de agora (Routes, cota "transito" do maps_client)."""
    import maps_client
    import vida_assistente

    casa = os.environ.get("ENDERECO_CASA", "").strip()
    if not casa or not maps_client.configurado():
        return None
    try:
        return int(maps_client.tempo_de_viagem(casa, vida_assistente.resolver_lugar(conn, local))["duracao_minutos"])
    except Exception as e:  # noqa: BLE001 - rede/cota/sem rota: so nao compara
        log.warning("transito_piorou: trajeto falhou: %s", e)
        return None


def _base_do_plano(extras: dict) -> int | None:
    saida = extras.get("saida") if isinstance(extras.get("saida"), dict) else {}
    v = saida.get("trajeto_min")
    return v if isinstance(v, int) and v > 0 else None


def avisos_transito(conn, agora: datetime | None = None, tempo_fn=None) -> list[tuple[int, str, str]]:
    """[(task_id, titulo, corpo)] das tarefas de hoje cujo caminho piorou >= 10 min. `tempo_fn(conn, local)`
    -> minutos (teste injeta; padrao = Maps). O dedup final (1x por dia) e do tick; aqui tambem nao repete."""
    try:
        return _avisos_transito(conn, agora or datetime.now(), tempo_fn or _tempo_padrao)
    except Exception:  # noqa: BLE001 - nunca derruba o tick
        log.exception("transito_piorou falhou")
        return []


def _avisos_transito(conn, agora: datetime, tempo_fn) -> list[tuple[int, str, str]]:
    hoje = agora.date()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    extra_cols = "".join(f", {c}" for c in ("sai_na_hora", "parada") if c in cols)
    linhas = conn.execute(
        f"SELECT id, title, hora, local{extra_cols} FROM tasks WHERE due_date = ? AND completed_at IS NULL "
        "AND hora IS NOT NULL AND local IS NOT NULL AND TRIM(local) != '' ORDER BY hora LIMIT 12",
        (hoje.isoformat(),),
    ).fetchall()
    saida = []
    silencio = None
    na_rua_estado = "?"
    for t in linhas:
        if "sai_na_hora" in t.keys() and t["sai_na_hora"]:
            continue  # a hora dita e a de sair: o transito nao muda a saida
        if "parada" in t.keys() and (t["parada"] or "").strip():
            continue  # casa -> parada -> destino: o plano e outro (tempo.py)
        if db.ja_notificou_hoje(conn, TIPO_TRANSITO, t["id"]):
            continue
        hora = _hora_do_dia(hoje, t["hora"])
        if hora is None or hora <= agora:
            continue
        local = " ".join(t["local"].split())
        extras = db.extras_tarefa(conn, t["id"])
        est = extras.get(CHAVE_EXTRAS) if isinstance(extras.get(CHAVE_EXTRAS), dict) else {}
        if est.get("dia") != hoje.isoformat() or est.get("hora") != t["hora"] or est.get("local") != local:
            est = {"dia": hoje.isoformat(), "hora": t["hora"], "local": local, "base_min": _base_do_plano(extras)}
        if isinstance(est.get("piorou"), dict):  # ja achou; o tick ainda nao conseguiu mandar (silencio/foco)
            saida.append((t["id"], est["piorou"]["titulo"], est["piorou"]["corpo"]))
            continue
        base = est.get("base_min") if isinstance(est.get("base_min"), int) else None
        sair_plano = hora - timedelta(minutes=(base or TRANSITO_SEM_BASE_MIN) + TRANSITO_MARGEM_MIN)
        if not (sair_plano - timedelta(minutes=TRANSITO_JANELA_MIN) <= agora < sair_plano):
            continue
        checado = _dt(est.get("checado_em"))
        if checado and agora - checado < timedelta(minutes=TRANSITO_INTERVALO_MIN):
            continue
        if silencio is None:
            silencio = _silencio(conn, agora)
        if silencio:
            continue
        if na_rua_estado == "?":
            try:
                import na_rua

                na_rua_estado = na_rua.estado(conn, agora)
            except Exception:  # noqa: BLE001
                na_rua_estado = None
        if na_rua_estado:
            continue  # ja esta na rua: o plano "de casa" nao vale (na_rua/onde_estou cuidam)
        atual = tempo_fn(conn, local)
        est["checado_em"] = agora.isoformat(timespec="seconds")
        if not isinstance(atual, int) or atual <= 0:
            _guardar_estado(conn, t["id"], est)
            continue
        est["ult_min"] = atual
        if base is None:
            est["base_min"] = atual  # 1a medida vira a base do plano
            _guardar_estado(conn, t["id"], est)
            continue
        mais = atual - base
        if mais >= TRANSITO_PIOROU_MIN:
            sai = max(hora - timedelta(minutes=atual + TRANSITO_MARGEM_MIN), agora)
            chuva = False
            plano_chuva = extras.get("plano_chuva")
            if isinstance(plano_chuva, dict) and isinstance(plano_chuva.get("pct"), (int, float)):
                chuva = plano_chuva["pct"] >= 60
            titulo, corpo = _texto(TIPO_TRANSITO, {"hora": t["hora"], "mais": mais, "sai": sai.strftime("%H:%M")},
                                   conn, f"{TIPO_TRANSITO}-{t['id']}-{hoje.isoformat()}", agora, chuva=chuva or None)
            est["piorou"] = {"mais": mais, "sai": sai.strftime("%H:%M"), "titulo": titulo, "corpo": corpo}
            saida.append((t["id"], titulo, corpo))
        _guardar_estado(conn, t["id"], est)
    return saida


def _guardar_estado(conn, task_id: int, est: dict) -> None:
    extras = db.extras_tarefa(conn, task_id)  # rele: outro passo pode ter gravado no meio
    extras[CHAVE_EXTRAS] = est
    db.salvar_extras_tarefa(conn, task_id, extras)


# ================================================================ chegou_casa

def _eh_casa(texto: str, casa_end: str) -> bool:
    import onde_estou

    t = onde_estou._sem_acento(" ".join((texto or "").split()))
    return bool(t) and (t == "casa" or (casa_end and t == onde_estou._sem_acento(casa_end)))


def tarefas_de_fora(conn, agora: datetime) -> list:
    """Tarefas de hoje abertas que eram FORA de casa (lugar ou apelido de lugar no titulo) e cuja hora ja
    passou (ou sem hora): o que ele provavelmente resolveu na rua. Remedio nunca."""
    import onde_estou

    dia = agora.date().isoformat()
    casa_end = os.environ.get("ENDERECO_CASA", "").strip()
    lugares = [x for x in onde_estou._lugares(conn, dia) if x["apelido"] != "casa"]
    agora_hm = agora.strftime("%H:%M")
    saida = []
    for t in onde_estou._tarefas_de_hoje(conn, dia):
        if t["hora"] and t["hora"] > agora_hm:
            continue
        if onde_estou._e_remedio(conn, t):
            continue
        local = (t["local"] or "").strip()
        if local:
            fora = not _eh_casa(local, casa_end)
        else:
            fora = any(onde_estou._bate(x["apelido"], t["title"]) for x in lugares)
        if fora:
            saida.append(t)
    return saida


def _ficou_fora_min(conn, v) -> float | None:
    """Quanto tempo ele ficou fora antes desta chegada em casa, pelas visitas. None = sem base."""
    chegada = _dt(v["chegada"])
    if not chegada:
        return None
    ant = conn.execute(
        "SELECT * FROM visitas WHERE id != ? AND chegada IS NOT NULL AND chegada < ? ORDER BY chegada DESC, id DESC LIMIT 1",
        (v["id"], v["chegada"]),
    ).fetchone()
    if ant is None:
        return None
    if ant["lugar"] == "casa":
        desde = _dt(ant["saida"])
    else:
        casa_ant = conn.execute(
            "SELECT saida FROM visitas WHERE id != ? AND lugar = 'casa' AND saida IS NOT NULL AND saida <= ? "
            "ORDER BY saida DESC LIMIT 1", (v["id"], v["chegada"]),
        ).fetchone()
        desde = _dt(casa_ant["saida"]) if casa_ant else _dt(ant["chegada"])
    if not desde:
        return None
    return (chegada - desde).total_seconds() / 60


def chegou_casa(conn, visita_id: int, agora: datetime, enviar=None) -> bool:
    """Gancho do onde_estou.reagir: visita aberta e recente reconhecida como casa. True = avisou."""
    try:
        return _chegou_casa(conn, visita_id, agora, enviar)
    except Exception:  # noqa: BLE001 - nunca derruba a chegada
        log.exception("chegou_casa falhou")
        return False


def _chegou_casa(conn, visita_id: int, agora: datetime, enviar) -> bool:
    import hora_certa
    from assistente import avisos as avisos_assistente

    v = conn.execute("SELECT * FROM visitas WHERE id = ?", (visita_id,)).fetchone()
    if not v or v["lugar"] != "casa" or v["saida"] is not None:
        return False
    chegada = _dt(v["chegada"])
    if not chegada or not timedelta(0) <= agora - chegada <= timedelta(minutes=CHEGADA_RECENTE_MIN):
        return False
    chave = f"casa:{visita_id}"  # a mesma do casa_tarefa (hora_certa._casa): uma fala de casa por chegada
    if hora_certa.ja_tem(conn, chave):
        return False
    if not avisos_assistente.esta_ligado(TIPO_CASA, conn=conn) or _silencio(conn, agora):
        return False  # silencio: tenta de novo nos proximos 5 min enquanto a chegada for recente
    ultimo = _dt(db.obter_configuracao(conn, CHAVE_ULTIMO_CASA))
    if ultimo and timedelta(0) <= agora - ultimo < timedelta(hours=CASA_INTERVALO_H):
        return False
    fora = _ficou_fora_min(conn, v)
    if fora is None or fora < FORA_MIN:
        return False
    tarefas = tarefas_de_fora(conn, agora)
    if not tarefas:
        return False
    import avisos_texto

    titulo, corpo = _texto(TIPO_CASA, {}, conn, f"{TIPO_CASA}-{visita_id}", agora)
    ref = 0
    url = "/?aba=tarefas"
    if len(tarefas) == 1:  # uma so: Feito / Amanha valem pra ela (categoria "casa")
        ref = int(tarefas[0]["id"])
        url = f"/?aba=tarefas&tarefa={ref}"
        nome = avisos_texto._curto(hora_certa.titulo_frase(tarefas[0]["title"]), 20)
        if len(f"{titulo} · {nome}") <= avisos_texto.TITULO_LIM:
            titulo = f"{titulo} · {nome}"
    hora_certa.marcar_chave(conn, chave, agora)
    db.definir_configuracao(conn, CHAVE_ULTIMO_CASA, agora.isoformat(timespec="seconds"))
    db.marcar_notificado(conn, TIPO_CASA, ref)
    (enviar or entregar_evento)(conn, TIPO_CASA, ref, titulo, corpo, agora, url=url,
                               categoria="casa" if ref else "")
    return True


def entregar_evento(conn, tipo: str, ref: int, titulo: str, corpo: str, agora: datetime, url: str = "/",
                    categoria: str = "") -> str:
    """Aviso que nasce fora do tick: app vivo -> fila dele (avisos_pendentes.entregar); senao push do navegador
    na hora (com Feito/Amanha quando e de uma tarefa) + Telegram. Devolve "fila"/"push"/""."""
    import avisos_pendentes
    import hora_certa
    import notificacoes
    import push_client
    import telegram_bot

    titulo = notificacoes.com_emoji(tipo, titulo)
    tag = f"{tipo}-{int(ref)}"

    def _push():
        if not push_client.configurado():
            return
        kw = {"acoes": hora_certa.ACOES_CASA} if categoria == "casa" and ref else {}
        for s in db.list_push_subscriptions(conn):
            if not push_client.enviar(json.loads(s["subscription_json"]), titulo, corpo, url=url, tag=tag, **kw):
                db.delete_push_subscription(conn, s["endpoint"])

    como = avisos_pendentes.entregar(conn, tipo=tipo, ref=int(ref), titulo=titulo, corpo=corpo, agora=agora,
                                     enviar_push=_push, url=url, categoria=categoria)
    try:
        if telegram_bot.configurado():
            telegram_bot.enviar_mensagem(f"{titulo}\n{corpo}")
    except Exception:  # noqa: BLE001
        log.exception("chegou_casa: telegram falhou")
    return como


# ================================================================ meta_batida

def _metas_batidas(conn, hoje: date) -> list[tuple[int, str, bool]]:
    """[(ref, nome da meta, diaria)] de tudo que esta batido agora."""
    batidas = []
    try:
        cfg = db.obter_configuracao(conn, "agua_meta_copos")
        meta_agua = int(cfg) if cfg and str(cfg).isdigit() and int(cfg) > 0 else 8
        if db.contar_hidratacao_dia(conn, hoje.isoformat()) >= meta_agua:
            batidas.append((REF_AGUA, f"{meta_agua} copos de água", True))
    except Exception:  # noqa: BLE001
        log.exception("meta_batida: agua")
    try:
        import diario_bordo

        prog = diario_bordo.progresso(conn, hoje)
        for c in prog.get("cats", []):
            meta = c.get("meta")
            if not meta or float(c.get("h") or 0) < float(meta):
                continue
            m = int(meta)
            if c["chave"] == "total":
                batidas.append((REF_VOO_TOTAL + m, f"{m} horas de voo", False))
            elif c["chave"] in REF_VOO_REQ:
                batidas.append((REF_VOO_REQ[c["chave"]], NOME_VOO_REQ[c["chave"]].format(m=m), False))
    except Exception:  # noqa: BLE001
        log.exception("meta_batida: voo")
    try:
        for g in conn.execute("SELECT id, titulo, valor_alvo, valor_guardado FROM goals").fetchall():
            if g["valor_alvo"] and float(g["valor_alvo"]) > 0 and float(g["valor_guardado"] or 0) >= float(g["valor_alvo"]):
                batidas.append((REF_GOAL + int(g["id"]), (g["titulo"] or "Meta").strip() or "Meta", False))
    except Exception:  # noqa: BLE001
        log.exception("meta_batida: goals")
    return batidas


def avisos_meta(conn, agora: datetime | None = None) -> list[tuple[int, str, str]]:
    """[(ref, titulo, corpo)] das metas recem batidas que ainda nao avisaram (agua: hoje; o resto: nunca).
    Na 1a passada o que ja estava batido (metas de vida inteira) fica marcado sem avisar."""
    try:
        agora = agora or datetime.now()
        batidas = _metas_batidas(conn, agora.date())
        if db.obter_configuracao(conn, CHAVE_META_BASE) is None:
            for ref, _, diaria in batidas:
                if not diaria:
                    db.marcar_notificado(conn, TIPO_META, ref)
            db.definir_configuracao(conn, CHAVE_META_BASE, agora.isoformat(timespec="seconds"))
            conn.commit()
            batidas = [b for b in batidas if b[2]]
        saida = []
        for ref, nome, diaria in batidas:
            ja = db.ja_notificou_hoje(conn, TIPO_META, ref) if diaria else db.ja_notificado_alguma_vez(conn, TIPO_META, ref)
            if ja:
                continue
            titulo, corpo = _texto(TIPO_META, {"meta": nome}, conn, f"{TIPO_META}-{ref}-{agora.date().isoformat()}", agora)
            saida.append((ref, titulo, corpo))
        return saida
    except Exception:  # noqa: BLE001
        log.exception("meta_batida falhou")
        return []


def ja_avisou_meta(conn, ref: int) -> bool:
    """Dedup do tick: agua e por dia, o resto e por vida."""
    if ref == REF_AGUA:
        return db.ja_notificou_hoje(conn, TIPO_META, ref)
    return db.ja_notificado_alguma_vez(conn, TIPO_META, ref)


# ================================================================ sequencia

def _seguidos(dias_feitos: set[str], hoje: date) -> tuple[int, date | None]:
    """(dias seguidos terminando hoje, 1o dia da sequencia). Hoje precisa estar feito."""
    n, d = 0, hoje
    while d.isoformat() in dias_feitos and n < SEQ_OLHA_DIAS + 1:
        n += 1
        d -= timedelta(days=1)
    return n, (d + timedelta(days=1)) if n else None


def _desde(hoje: date) -> str:
    return (hoje - timedelta(days=SEQ_OLHA_DIAS)).isoformat()


def _sequencias(conn, hoje: date) -> list[tuple[str, str, int, date]]:
    """[(chave estavel, nome da coisa, dias seguidos, inicio)] terminando hoje."""
    out = []
    ate = hoje.isoformat()

    def add(chave, nome, dias):
        n, ini = _seguidos(dias, hoje)
        if n:
            out.append((chave, nome, n, ini))

    try:
        add("treino", "Treino", {r[0] for r in conn.execute(
            "SELECT DISTINCT data FROM treinos WHERE data >= ? AND data <= ?", (_desde(hoje), ate)).fetchall()})
    except Exception:  # noqa: BLE001
        log.exception("sequencia: treino")
    try:
        for m in conn.execute(
                "SELECT id, nome, tarefa_modelo_id FROM medicamentos WHERE ativo = 1 AND recorrencia = 'diaria'").fetchall():
            dias = {r[0] for r in conn.execute(
                "SELECT DISTINCT due_date FROM tasks WHERE recorrente_origem_id = ? AND completed_at IS NOT NULL "
                "AND due_date >= ? AND due_date <= ?", (m["tarefa_modelo_id"], _desde(hoje), ate)).fetchall()}
            add(f"remedio:{m['id']}", (m["nome"] or "Remédio").strip() or "Remédio", dias)
    except Exception:  # noqa: BLE001
        log.exception("sequencia: remedio")
    try:
        for h in conn.execute("SELECT id, nome FROM habitos WHERE ativo = 1 AND frequencia_tipo = 'diario'").fetchall():
            dias = {r[0] for r in conn.execute(
                "SELECT data FROM habito_marcacoes WHERE habito_id = ? AND data >= ? AND data <= ?",
                (h["id"], _desde(hoje), ate)).fetchall()}
            add(f"habito:{h['id']}", (h["nome"] or "Hábito").strip() or "Hábito", dias)
    except Exception:  # noqa: BLE001
        log.exception("sequencia: habito")
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()}
        arq = " AND arquivada_em IS NULL" if "arquivada_em" in cols else ""
        dias = {r[0] for r in conn.execute(
            f"SELECT due_date FROM tasks WHERE recorrencia IS NULL{arq} AND due_date >= ? AND due_date <= ? "
            "GROUP BY due_date HAVING COUNT(*) > 0 AND SUM(CASE WHEN completed_at IS NULL THEN 1 ELSE 0 END) = 0",
            (_desde(hoje), ate)).fetchall()}
        add("tarefas", "Tarefas em dia", dias)
    except Exception:  # noqa: BLE001
        log.exception("sequencia: tarefas")
    return out


def ref_sequencia(chave: str, inicio: date, marco: int) -> int:
    return zlib.crc32(f"{chave}|{inicio.isoformat()}|{marco}".encode()) & 0x7FFFFFFF


def avisos_sequencia(conn, agora: datetime | None = None) -> list[tuple[int, str, str]]:
    """[(ref, titulo, corpo)] das sequencias que chegaram hoje num marco (dias seguidos == marco). Uma
    sequencia que quebrou e recomecou vale de novo (o ref leva o 1o dia)."""
    try:
        agora = agora or datetime.now()
        saida = []
        for chave, nome, n, ini in _sequencias(conn, agora.date()):
            if n not in MARCOS:
                continue
            ref = ref_sequencia(chave, ini, n)
            if db.ja_notificado_alguma_vez(conn, TIPO_SEQUENCIA, ref):
                continue
            titulo, corpo = _texto(TIPO_SEQUENCIA, {"n": n, "coisa": nome}, conn,
                                   f"{TIPO_SEQUENCIA}-{ref}", agora)
            saida.append((ref, titulo, corpo))
        return saida
    except Exception:  # noqa: BLE001
        log.exception("sequencia falhou")
        return []
