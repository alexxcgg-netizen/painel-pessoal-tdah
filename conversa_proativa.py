"""Painel puxando assunto (2026-10-13): a IA abre a conversa no chat sozinha.

  - FECHAR O DIA (21h): mensagem no chat com o que ele fez, o que ficou pendurado e um
    card vivo com botao "passar pra amanha" (move de verdade, POST /api/tarefas/adiar).
  - PADROES DA SEMANA (domingo a noite): grafico animado dos 7 dias (tarefas feitas,
    agua, gasto, voo) e 2-3 observacoes tiradas dos numeros.

Texto por TEMPLATE (zero chamada de IA, zero custo de cota) mas escrito como gente:
variacao por dia pra nao soar repetido, frase curta, nada de "Resumo do dia:". Toda
observacao e um fato calculado aqui - nunca palpite.

Publicar = gravar como mensagem do assistente em chat_mensagens (o chat abre com ela
no historico) + o push avisa (app.verificar_e_notificar). Dedupe pelo mesmo
notificacoes_enviadas dos outros avisos, entao sai uma vez por dia/semana mesmo com o
tick de 5 em 5 min e o PC ligado tarde.
"""

import json
from datetime import date, datetime, time, timedelta

import cards
import db

DIAS_CURTOS = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
DIAS_LONGOS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
JANELA_FECHAR_DIA = (time(21, 0), time(23, 30))
JANELA_SEMANA = (time(19, 30), time(23, 30))  # domingo
LIMITE_PENDENTES_CARD = 8

# completed_at e datetime('now') do SQLite (UTC); o dia dele e o de Brasilia
_DIA_CONCLUSAO = "date(completed_at, '-3 hours')"
_SO_TAREFA_REAL = "recorrencia IS NULL"


def _agua_meta(conn) -> int:
    m = db.obter_configuracao(conn, "agua_meta_copos")
    return int(m) if m and str(m).isdigit() else 8


def _feitas_no_dia(conn, dia: date) -> int:
    return conn.execute(
        f"SELECT COUNT(*) n FROM tasks WHERE completed_at IS NOT NULL AND {_DIA_CONCLUSAO} = ?",
        (dia.isoformat(),),
    ).fetchone()["n"]


def pendentes_ate(conn, dia: date) -> list[dict]:
    """Abertas com data ate `dia` (as atrasadas inclusive), na ordem da agenda."""
    linhas = conn.execute(
        f"SELECT id, title, hora, due_date FROM tasks WHERE completed_at IS NULL AND {_SO_TAREFA_REAL} "
        "AND due_date IS NOT NULL AND due_date != '' AND due_date <= ? "
        "ORDER BY due_date, (hora IS NULL OR hora = ''), hora, id",
        (dia.isoformat(),),
    ).fetchall()
    return [{"id": r["id"], "titulo": r["title"], "hora": r["hora"] or None, "data": r["due_date"],
             "atrasada": r["due_date"] < dia.isoformat()} for r in linhas]


def _gasto_no_dia(conn, dia: date) -> float:
    return float(conn.execute(
        "SELECT COALESCE(SUM(amount), 0) t FROM expenses WHERE date(created_at) = ? AND tipo = 'real'",
        (dia.isoformat(),),
    ).fetchone()["t"] or 0)


def _voo_horas_no_dia(conn, dia: date) -> float:
    return float(conn.execute(
        "SELECT COALESCE(SUM(horas), 0) h FROM voos WHERE data = ?", (dia.isoformat(),)
    ).fetchone()["h"] or 0)


def _quiz_no_dia(conn, dia: date) -> dict:
    try:
        r = conn.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(ultimo_acerto), 0) a FROM estudo_perguntas WHERE date(respondida_em) = ?",
            (dia.isoformat(),),
        ).fetchone()
    except Exception:  # tabela ainda nao existe (quiz nunca usado)
        return {"respondidas": 0, "acertos": 0}
    return {"respondidas": r["n"], "acertos": r["a"]}


def _horas_txt(h: float) -> str:
    h = round(h, 1)
    return f"{h:g}".replace(".", ",") + " h"


def _lista_curta(titulos: list[str], maximo: int = 3) -> str:
    t = [f"“{x}”" for x in titulos[:maximo]]
    resto = len(titulos) - len(t)
    if resto > 0:
        return ", ".join(t) + f" e mais {resto}"
    if len(t) > 1:
        return ", ".join(t[:-1]) + " e " + t[-1]
    return t[0] if t else ""


# ---------------------------------------------------------------- fechar o dia

_ABERTURAS = ("Fechando o dia:", "Bora fechar o dia.", "Fim de dia, rapidinho:", "Fechando as contas de hoje:")


def fechar_dia(conn, hoje: date) -> tuple[str, list[dict]] | None:
    """(texto, cards) pro chat - None quando o dia nao teve nada pra fechar."""
    feitas = _feitas_no_dia(conn, hoje)
    pendentes = pendentes_ate(conn, hoje)
    copos = db.contar_hidratacao_dia(conn, hoje.isoformat())
    meta_agua = _agua_meta(conn)
    gasto = _gasto_no_dia(conn, hoje)
    voo_h = _voo_horas_no_dia(conn, hoje)
    quiz = _quiz_no_dia(conn, hoje)
    if not feitas and not pendentes and not copos and not voo_h and not quiz["respondidas"]:
        return None

    frases = []
    abertura = _ABERTURAS[hoje.toordinal() % len(_ABERTURAS)]
    if pendentes:
        feitas_txt = f"{feitas} {'feita' if feitas == 1 else 'feitas'}" if feitas else "nada riscado"
        atrasadas = sum(1 for p in pendentes if p["atrasada"])
        resto = f" ({atrasadas} já vinham de antes)" if atrasadas else ""
        frases.append(f"{abertura} {feitas_txt} hoje, e ficaram {len(pendentes)}{resto}: "
                      f"{_lista_curta([p['titulo'] for p in pendentes])}.")
        frases.append("Quer que eu passe pra amanhã? É um toque no card.")
    else:
        frases.append(f"Dia fechado limpo: {feitas} {'tarefa' if feitas == 1 else 'tarefas'} e nada pendurado. "
                      "Pode desligar a cabeça.")
    if voo_h:
        frases.append(f"E teve voo: {_horas_txt(voo_h)} no diário.")
    if quiz["respondidas"]:
        frases.append(f"No quiz, {quiz['acertos']} de {quiz['respondidas']}.")
    if copos < meta_agua and (copos or feitas):
        frases.append(f"Água ficou em {copos} de {meta_agua}, amanhã começa com um copo.")

    card = cards.novo_card("fechar_dia", {
        "dia": hoje.isoformat(),
        "feitas": feitas,
        "pendentes": pendentes[:LIMITE_PENDENTES_CARD],
        "mais": max(0, len(pendentes) - LIMITE_PENDENTES_CARD),
        "ids_adiar": [p["id"] for p in pendentes],
        "amanha": (hoje + timedelta(days=1)).isoformat(),
        "agua": {"copos": copos, "meta": meta_agua},
        "gasto": round(gasto, 2),
        "voo_horas": round(voo_h, 1),
        "quiz": quiz,
    })
    return " ".join(frases), [card]


def resumo_push_fechar_dia(texto: str, card: dict) -> str:
    d = card["data"]
    if d["pendentes"] or d["mais"]:
        n = len(d["ids_adiar"])
        return f"{d['feitas']} feitas, {n} {'ficou' if n == 1 else 'ficaram'}. Passo pra amanhã?"
    return "Dia fechado limpo. Dá uma olhada no resumo."


def adiar_para_amanha(conn, ids, hoje: date) -> dict:
    """Move as tarefas abertas (com data ate hoje) pra amanha, mantendo o horario.
    So mexe no que ainda faz sentido mover - concluida/futura/recorrente fica."""
    limpos = sorted({i for i in (ids or []) if isinstance(i, int) and not isinstance(i, bool) and i > 0})[:200]
    if not limpos:
        return {"movidas": 0, "para": (hoje + timedelta(days=1)).isoformat()}
    amanha = (hoje + timedelta(days=1)).isoformat()
    marcas = ",".join("?" for _ in limpos)
    cur = conn.execute(
        f"UPDATE tasks SET due_date = ? WHERE id IN ({marcas}) AND completed_at IS NULL AND {_SO_TAREFA_REAL} "
        "AND due_date IS NOT NULL AND due_date != '' AND due_date <= ?",
        [amanha, *limpos, hoje.isoformat()],
    )
    conn.commit()
    return {"movidas": cur.rowcount, "para": amanha}


def trazer_para_hoje(conn, ids, hoje: date, agora_hm: str) -> dict:
    """Atrasada -> hoje (2026-10-14, Alex: "dormi, acordei e tava atrasada; botei pra amanha mas
    era pra hoje"). So mexe em aberta com data ANTES de hoje. Horario que ainda vem hoje fica;
    o que ja passou sai (senao o aviso "ta na hora" + insistencia disparava na hora de mover)."""
    limpos = sorted({i for i in (ids or []) if isinstance(i, int) and not isinstance(i, bool) and i > 0})[:200]
    if not limpos:
        return {"movidas": 0, "para": hoje.isoformat()}
    marcas = ",".join("?" for _ in limpos)
    cur = conn.execute(
        f"UPDATE tasks SET due_date = ?, hora = CASE WHEN hora IS NOT NULL AND hora > ? THEN hora ELSE NULL END "
        f"WHERE id IN ({marcas}) AND completed_at IS NULL AND {_SO_TAREFA_REAL} "
        "AND due_date IS NOT NULL AND due_date != '' AND due_date < ?",
        [hoje.isoformat(), agora_hm, *limpos, hoje.isoformat()],
    )
    conn.commit()
    return {"movidas": cur.rowcount, "para": hoje.isoformat()}


# ----------------------------------------------------------- padroes da semana


def _semana(conn, ate: date) -> dict:
    dias = [ate - timedelta(days=6 - i) for i in range(7)]
    meta = _agua_meta(conn)
    linhas = []
    for d in dias:
        linhas.append({
            "dia": d.isoformat(),
            "rotulo": DIAS_CURTOS[d.weekday()],
            "tarefas": _feitas_no_dia(conn, d),
            "agua": db.contar_hidratacao_dia(conn, d.isoformat()),
            "gasto": round(_gasto_no_dia(conn, d), 2),
            "voo_h": round(_voo_horas_no_dia(conn, d), 1),
        })
    return {"dias": linhas, "meta_agua": meta}


def padroes_semana(conn, hoje: date) -> tuple[str, list[dict]] | None:
    atual = _semana(conn, hoje)
    anterior = _semana(conn, hoje - timedelta(days=7))
    dias = atual["dias"]
    tarefas = sum(d["tarefas"] for d in dias)
    agua_dias = [d["agua"] for d in dias]
    gasto = round(sum(d["gasto"] for d in dias), 2)
    gasto_ant = round(sum(d["gasto"] for d in anterior["dias"]), 2)
    tarefas_ant = sum(d["tarefas"] for d in anterior["dias"])
    voo = round(sum(d["voo_h"] for d in dias), 1)
    if not tarefas and not any(agua_dias) and not gasto and not voo:
        return None

    obs = []
    melhor = max(dias, key=lambda d: (d["tarefas"], d["dia"])) if tarefas else None
    if melhor and melhor["tarefas"] >= 2:
        nome = DIAS_LONGOS[date.fromisoformat(melhor["dia"]).weekday()]
        obs.append(f"{nome.capitalize()} foi teu dia mais produtivo, {melhor['tarefas']} tarefas riscadas.")
    if tarefas_ant and tarefas:
        dif = tarefas - tarefas_ant
        if abs(dif) >= 2:
            obs.append(f"No total foram {tarefas}, {abs(dif)} {'a mais' if dif > 0 else 'a menos'} que na semana passada.")
    if any(agua_dias):
        bateu = sum(1 for c in agua_dias if c >= atual["meta_agua"])
        media = f"{sum(agua_dias) / 7:.1f}".replace(".", ",")
        obs.append(f"Água bateu a meta em {bateu} de 7 dias." if bateu else
                   f"Água não bateu a meta nenhum dia (média de {media} copos).")
    if gasto and gasto_ant:
        pct = round((gasto - gasto_ant) / gasto_ant * 100)
        if abs(pct) >= 10:
            obs.append(f"Gastou {abs(pct)}% {'a mais' if pct > 0 else 'a menos'} que na semana anterior.")
    if voo:
        obs.append(f"Voou {_horas_txt(voo)} na semana.")
    atrasadas = sum(1 for p in pendentes_ate(conn, hoje) if p["atrasada"])
    if atrasadas >= 3:
        obs.append(f"Tem {atrasadas} tarefas atrasadas acumulando; se quiser, eu reorganizo a semana que vem com você.")

    texto = "Teus padrões da semana: " + " ".join(obs[:3]) if obs else "Fechei tua semana em números, tá no card."
    melhor_dia = melhor["dia"] if melhor and melhor["tarefas"] else None
    card = cards.novo_card("semana", {
        "de": dias[0]["dia"], "ate": dias[-1]["dia"],
        "dias": [{k: d[k] for k in ("dia", "rotulo", "tarefas", "voo_h")} for d in dias],
        "agua_dia": agua_dias,
        "meta_agua": atual["meta_agua"],
        "gastos_dia": [d["gasto"] for d in dias],
        "gasto": gasto,
        "gasto_ant": gasto_ant,
        "tarefas": tarefas,
        "tarefas_ant": tarefas_ant,
        "voo_horas": voo,
        "melhor_dia": melhor_dia,
        "observacoes": obs[:3],
    })
    return texto, [card]


# ------------------------------------------------------------------ publicar


def _na_janela(agora: datetime, janela: tuple[time, time]) -> bool:
    return janela[0] <= agora.time() <= janela[1]


def publicar(conn, tipo: str, texto: str, lista_cards: list[dict]) -> dict:
    env = cards.envelope(lista_cards, texto, [])
    db.salvar_mensagem_chat(conn, "assistant", texto, env["cards"])
    db.marcar_notificado(conn, tipo)
    conn.commit()
    return env


# ------------------------------------------------- pos-voo (3a leva, 2026-10-14)
POS_VOO_FOLGA_MIN = 20  # depois do pouso estimado: tempo de cortar o motor e sair do avião
POS_VOO_SEM_ESTIMATIVA_MIN = 90  # voo local / rota sem NM: hora + 1h30
FIM_POS_VOO = time(23, 30)
FRASES_POS_VOO = (
    "Pousou? Quanto deu o voo de hoje? Um toque aqui e eu somo nas tuas horas.",
    "E aí, como foi o voo? Me diz quanto deu que eu já somo no diário.",
    "Voo feito! Quanto marcou o horímetro? Toca no valor aqui embaixo.",
)


def _min(hhmm: str | None) -> int | None:
    try:
        h, m = str(hhmm).split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def voos_pra_perguntar(conn, agora: datetime) -> list[int]:
    """Voos de hoje com hora, ainda sem horas, que ja deviam ter pousado (estimativa da rota +
    folga) - e ainda nao perguntados."""
    import rota_voo

    ids = []
    agora_min = agora.hour * 60 + agora.minute
    if agora.time() > FIM_POS_VOO:
        return ids
    for v in conn.execute(
        "SELECT id, origem, destino, escalas, hora FROM voos WHERE data = ? AND hora IS NOT NULL "
        "AND horas IS NULL AND COALESCE(tipo, '') != 'simulador' ORDER BY hora",
        (agora.date().isoformat(),),
    ).fetchall():
        rota = rota_voo.montar(v["origem"], v["escalas"], v["destino"], v["hora"])
        pouso = _min(rota["pouso"]) if rota["pouso"] else None
        decola = _min(v["hora"])
        if decola is None:
            continue
        fim = pouso if pouso is not None else decola + POS_VOO_SEM_ESTIMATIVA_MIN
        if agora_min >= fim + POS_VOO_FOLGA_MIN and not db.ja_notificou_hoje(conn, "pos_voo_chat", v["id"]):
            ids.append(v["id"])
    return ids


# ------------------------------------------- presente que volta todo ano (3a leva)
def _mais_um_ano(d: date) -> date:
    try:
        return d.replace(year=d.year + 1)
    except ValueError:  # 29/02
        return d.replace(year=d.year + 1, day=28)


def renovar_presentes_anuais(conn, hoje: date) -> list[int]:
    """Passou a data de um presente anual: cria o do proximo ano com as ideias que nao foram
    usadas e guarda o que ele deu em `historico`. Idempotente (renovado_id)."""
    novos = []
    for r in conn.execute(
        "SELECT id, title, due_date, extras FROM tasks WHERE estilo = 'presente' AND due_date < ?",
        (hoje.isoformat(),),
    ).fetchall():
        ex = db.extras_tarefa(conn, r["id"])
        if not ex.get("anual") or ex.get("renovado_id"):
            continue
        dia = date.fromisoformat(r["due_date"])
        prox = _mais_um_ano(dia)
        while prox < hoje:
            prox = _mais_um_ano(prox)
        ideias = [i for i in ex.get("ideias") or [] if isinstance(i, dict)]
        escolha = ex.get("escolha") if isinstance(ex.get("escolha"), int) else None
        historico = [h for h in ex.get("historico") or [] if isinstance(h, dict)]
        if escolha is not None and 0 <= escolha < len(ideias):
            historico.append({"ano": dia.year, "presente": ideias[escolha].get("titulo")})
        novo_ex = {"anual": True, "historico": historico[-5:],
                   "ideias": [i for k, i in enumerate(ideias) if k != escolha]}
        if ex.get("com_quem"):
            novo_ex["com_quem"] = ex["com_quem"]
        cur = conn.execute(
            "INSERT INTO tasks (title, due_date, source_text, estilo, extras) VALUES (?, ?, ?, 'presente', ?)",
            (r["title"], prox.isoformat(), f"presente anual #{r['id']}", json.dumps(novo_ex, ensure_ascii=False)),
        )
        ex["renovado_id"] = cur.lastrowid
        db.salvar_extras_tarefa(conn, r["id"], ex)
        novos.append(cur.lastrowid)
    if novos:
        conn.commit()
    return novos


def verificar(conn, agora: datetime) -> list[tuple[str, str, str]]:
    """Chamado a cada tick do agendador. Publica no chat o que estiver na hora e
    devolve [(tipo_do_aviso, titulo, corpo)] pro push. Nunca levanta."""
    saida = []
    try:
        if _na_janela(agora, JANELA_FECHAR_DIA) and not db.ja_notificou_hoje(conn, "fechar_dia_chat"):
            r = fechar_dia(conn, agora.date())
            db.marcar_notificado(conn, "fechar_dia_chat")
            if r:
                texto, lista = r
                publicar(conn, "fechar_dia_chat", texto, lista)
                saida.append(("fechamento_noturno", "Fechando o dia", resumo_push_fechar_dia(texto, lista[0])))
            conn.commit()
        if agora.weekday() == 6 and _na_janela(agora, JANELA_SEMANA) and not db.ja_notificou_hoje(conn, "padroes_semana_chat"):
            r = padroes_semana(conn, agora.date())
            db.marcar_notificado(conn, "padroes_semana_chat")
            if r:
                texto, lista = r
                publicar(conn, "padroes_semana_chat", texto, lista)
                corpo = (lista[0]["data"]["observacoes"] or ["Tua semana em números tá no chat."])[0]
                saida.append(("padroes_semana", "Teus padrões da semana", corpo))
            conn.commit()
        for voo_id in voos_pra_perguntar(conn, agora):
            card = cards.card_voo_horas(conn, voo_id, agora.date())
            db.marcar_notificado(conn, "pos_voo_chat", voo_id)
            if card:
                texto = FRASES_POS_VOO[(agora.toordinal() + voo_id) % len(FRASES_POS_VOO)]
                publicar(conn, "pos_voo_chat", texto, [card])
                saida.append(("pos_voo", "Pousou?", "Quanto deu o voo de hoje? Um toque no chat e eu somo nas horas."))
            conn.commit()
        if not db.ja_notificou_hoje(conn, "presentes_anuais"):
            renovar_presentes_anuais(conn, agora.date())
            db.marcar_notificado(conn, "presentes_anuais")
            conn.commit()
    except Exception:
        import logging
        logging.getLogger(__name__).exception("conversa proativa falhou")
    return saida
