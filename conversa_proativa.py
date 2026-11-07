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
import coincidencias
import db
import diario_bordo
import neste_dia
import dia_ruim
import foco
import foco_ideias
import recomeco
import vida

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
    # leva 22/10: inegociavel (cadeado) nunca e empurrada; todo adiamento fica registrado (dia_ruim)
    alvo = [r["id"] for r in conn.execute(
        f"SELECT id FROM tasks WHERE id IN ({marcas}) AND completed_at IS NULL AND {_SO_TAREFA_REAL} "
        "AND due_date IS NOT NULL AND due_date != '' AND due_date <= ? AND inegociavel = 0",
        [*limpos, hoje.isoformat()],
    ).fetchall()]
    cur = conn.execute(
        f"UPDATE tasks SET due_date = ? WHERE id IN ({','.join('?' for _ in alvo) or 'NULL'})", [amanha, *alvo]
    )
    dia_ruim.registrar_adiamento(conn, alvo, hoje.isoformat(), amanha)
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


PEDIDO_VOO = {"navegacao": "uma navegação", "noturno": "um voo noturno", "instrumentos": "instrução por instrumentos"}


def sugestao_semana(conn, hoje: date, melhor: dict | None, agua_dias: list[int], meta_agua: int, atrasadas: int) -> str | None:
    """Leva 22/10: um passo concreto pra semana que vem, tirado do padrao (nunca generico). A primeira regra que
    vale: atrasadas acumulando > categoria do diario de bordo mais atrasada > dia que mais rendeu > agua."""
    if atrasadas >= 3:
        return f"Separa 30 min na segunda pra zerar as {atrasadas} atrasadas. Se quiser, eu escolho o horário."
    prog = diario_bordo.progresso(conn, hoje)
    pior = next((c for c in prog["cats"] if c["chave"] == prog["pior"]), None)
    if pior and prog["cats"][0]["h"] > 0:
        falta = f"{pior['meta'] - pior['h']:.1f}".replace(".", ",")
        return (f"{pior['nome']} é a categoria mais atrasada pro comercial (faltam {falta} h): "
                f"vale pedir {PEDIDO_VOO[pior['chave']]} no próximo voo.")
    if melhor and melhor["tarefas"] >= 2:
        nome = DIAS_LONGOS[date.fromisoformat(melhor["dia"]).weekday()]
        return f"Põe o que for mais pesado da semana que vem na {nome}, que foi quando tu mais rendeu."
    if any(agua_dias) and sum(1 for c in agua_dias if c >= meta_agua) <= 2:
        return "Água ficou abaixo da meta quase a semana toda: deixa a garrafa cheia à vista logo de manhã."
    return None


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
    sugestao = sugestao_semana(conn, hoje, melhor, agua_dias, atual["meta_agua"], atrasadas)
    if sugestao:
        texto += f" Pra semana que vem: {sugestao}"
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
        "sugestao": sugestao,
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
    "Pousou? Só 3 perguntas rápidas e eu somo no diário de bordo.",
    "E aí, como foi o voo? Me diz o tipo, dia ou noite e o tempo que eu já somo.",
    "Voo feito! Confere o tempo aqui embaixo e diz que tipo de voo foi.",
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


# ------------------------------------------------ 4a leva (2026-10-15): automacoes
JANELA_VESPERA = (time(20, 0), time(23, 30))
INICIO_MANHA_VOO = time(6, 30)
ANTES_DE_SAIR_MANHA_MIN = 90
JANELA_DIA = (time(9, 0), time(21, 0))  # documentos, compras, assinatura: nada de madrugada


def _app():
    """app.py ja carregado (Maps do voo) - None fora do servidor."""
    try:
        from rotas._base import app_modulo

        return app_modulo()
    except Exception:
        return None


def _saida_maps(conn, v) -> dict | None:
    import rota_voo
    import vida_assistente

    app = _app()
    if app is None:
        return None
    try:
        return app._saida_pro_voo(conn, v["data"], v["hora"], v["origem"] or rota_voo.ORIGEM_PADRAO,
                                  vida_assistente.voo_briefing_min(conn))
    except Exception:
        return None


def _voos_com_hora(conn, dia: date):
    return conn.execute(
        "SELECT id, data, hora, origem, destino, escalas FROM voos WHERE data = ? AND hora IS NOT NULL "
        "AND horas IS NULL AND COALESCE(tipo, '') != 'simulador' ORDER BY hora",
        (dia.isoformat(),),
    ).fetchall()


def vespera_do_voo(conn, agora: datetime) -> list[tuple[str, str, str]]:
    """So em vespera de voo (pedido do Alex: "apenas nos dias que tenho voo"): 20h-23h30."""
    saida = []
    if not _na_janela(agora, JANELA_VESPERA):
        return saida
    for v in _voos_com_hora(conn, agora.date() + timedelta(days=1)):
        if db.ja_notificado_alguma_vez(conn, "vespera_voo_chat", v["id"]):
            continue
        card = cards.card_vespera_voo(conn, v["id"], _saida_maps(conn, v))
        db.marcar_notificado(conn, "vespera_voo_chat", v["id"])
        if not card:
            continue
        d = card["data"]
        rota = f" ({d['rota']})" if d["rota"] else ""
        texto = (f"Amanhã tem voo às {d['hora']}{rota}. Acorda {d['acordar']} e sai {d['sair']} — "
                 f"separei a mochila e a previsão aqui embaixo.")
        publicar(conn, "vespera_voo_chat", texto, [card])
        saida.append(("vespera_voo", "Amanhã tem voo", f"Acorda {d['acordar']}, sai {d['sair']}. Previsão e mochila no chat."))
    conn.commit()
    return saida


def manha_do_voo(conn, agora: datetime, montar_briefing=None) -> list[tuple[str, str, str]]:
    """Dia do voo: METAR atualizado + hora de sair, a partir de max(06h30, sair - 1h30)."""
    import briefing_voo
    import rota_voo
    import vida_assistente

    saida = []
    agora_hhmm = agora.strftime("%H:%M")
    for v in _voos_com_hora(conn, agora.date()):
        if db.ja_notificado_alguma_vez(conn, "manha_voo_chat", v["id"]) or agora_hhmm >= v["hora"]:
            continue
        chegar = rota_voo.menos_minutos(v["hora"], vida_assistente.voo_briefing_min(conn))
        sair_estimado = rota_voo.menos_minutos(chegar, cards.FOLGA_SAIDA_MIN)
        inicio = max(INICIO_MANHA_VOO.strftime("%H:%M"), rota_voo.menos_minutos(sair_estimado, ANTES_DE_SAIR_MANHA_MIN))
        if sair_estimado < inicio:  # voo de madrugada: sem "bom dia"
            inicio = INICIO_MANHA_VOO.strftime("%H:%M")
        if agora_hhmm < inicio:
            continue
        db.marcar_notificado(conn, "manha_voo_chat", v["id"])
        maps = _saida_maps(conn, v)
        sair = (maps or {}).get("sair") or sair_estimado
        lista = []
        try:
            b = (montar_briefing or briefing_voo.montar)(conn, v["origem"] or rota_voo.ORIGEM_PADRAO)
            card = cards.card_briefing_voo({"dados": b}) if not b.get("erro") else None
        except Exception:
            card = None
        if card:
            lista.append(card)
            cd = card["data"]
            das = f" das {cd['observado']}" if cd.get("observado") else ""
            tempo = f" METAR de {cd['icao']}{das}: {cd['categoria']}." if cd.get("categoria") else ""
        else:
            tempo = " Não consegui puxar o METAR agora — pede \"como tá o tempo\" daqui a pouco."
        trajeto = f" ({maps['trajeto_min']} min de carro)" if maps and maps.get("trajeto_min") else ""
        # Lab v4 (vento na pista): a conta do traves sai do vento que o briefing ja trouxe (sem rede nova)
        vento_linha = ""
        try:
            import aviacao_lab

            dados_b = (b or {}) if isinstance(b, dict) else {}
            if card and not dados_b.get("erro"):
                vento_linha = aviacao_lab.linha_vento(conn, dados_b.get("icao"), dados_b.get("vento")) or ""
        except Exception:
            vento_linha = ""
        texto = f"Bom dia! Voo hoje às {v['hora']}. Sai às {sair}{trajeto} pra chegar {chegar}.{tempo}"
        if vento_linha:
            texto += f" {vento_linha}"
        publicar(conn, "manha_voo_chat", texto, lista)
        saida.append(("manha_voo", "Voo hoje", f"Sai às {sair}.{tempo}".strip()))
    conn.commit()
    return saida


def documentos_vencendo(conn, agora: datetime) -> list[tuple[str, str, str]]:
    """Documento (CMA, CNH, passaporte... - vida.eh_burocracia) em 60/30/7 dias: card no chat +
    push, uma vez por marco por vencimento. Substitui o aviso unico de 8-30 dias."""
    import notificacoes

    saida = []
    if not _na_janela(agora, JANELA_DIA):
        return saida
    hoje = agora.date()
    for lem in db.list_lembretes(conn):
        if not vida.eh_burocracia(lem["titulo"]):
            continue
        try:
            base = date.fromisoformat(lem["data"])
        except (TypeError, ValueError):
            continue
        vence = notificacoes.proxima_ocorrencia_lembrete(base, bool(lem["recorrente"]), hoje)
        card = cards.card_documento_validade(lem, vence, hoje)
        if not card:
            continue
        ref = vida.id_estavel("doc_validade", lem["id"], vence.isoformat(), card["data"]["marco"])
        if db.ja_notificado_alguma_vez(conn, "documento_validade", ref):
            continue
        db.marcar_notificado(conn, "documento_validade", ref)
        d = card["data"]
        quando = "hoje" if d["dias"] == 0 else "amanhã" if d["dias"] == 1 else f"em {d['dias']} dias"
        dica = {60: "dá tempo de sobra, mas já dá pra marcar.", 30: "bom marcar essa semana.",
                7: "última semana — se ainda não marcou, é agora."}[d["marco"]]
        texto = f"\"{d['titulo']}\" vence {quando} ({vence.strftime('%d/%m')}): {dica}"
        publicar(conn, "documento_validade_chat", texto, [card])
        saida.append(("documento_validade", "Documento vencendo", texto))
    conn.commit()
    return saida


# compras que se repetem: so com historico de verdade (3+ compras, intervalo regular)
COMPRAS_MIN_VEZES = 3
COMPRAS_INTERVALO = (3, 120)
COMPRAS_AVISAR_DIAS = 3


def compras_previstas(conn, hoje: date) -> list[dict]:
    """Itens que ele compra de tempos em tempos e que devem estar acabando (mediana dos
    intervalos entre compras). Ja na lista ou adiado ("ainda tem") = fora."""
    import statistics

    datas: dict = {}
    nomes: dict = {}
    for r in conn.execute(
        "SELECT item, item_normalizado, comprado_em FROM compras WHERE comprado_em IS NOT NULL ORDER BY comprado_em"
    ).fetchall():
        chave = r["item_normalizado"] or vida.normalizar_item_compra(r["item"])
        try:
            dia = date.fromisoformat(str(r["comprado_em"])[:10])
        except ValueError:
            continue
        if not chave:
            continue
        if dia not in datas.setdefault(chave, []):
            datas[chave].append(dia)
        nomes[chave] = vida.limpar_item_compra(r["item"]) or r["item"]
    pendentes = {c["item_normalizado"] or vida.normalizar_item_compra(c["item"]) for c in db.list_compras_pendentes(conn)}
    saida = []
    for chave, dias in datas.items():
        if len(dias) < COMPRAS_MIN_VEZES or chave in pendentes:
            continue
        dias.sort()
        intervalo = round(statistics.median([(b - a).days for a, b in zip(dias, dias[1:])]))
        if not COMPRAS_INTERVALO[0] <= intervalo <= COMPRAS_INTERVALO[1]:
            continue
        prevista = dias[-1] + timedelta(days=intervalo)
        adiado = db.obter_configuracao(conn, f"compra_adiada_{chave}")
        if adiado and adiado > hoje.isoformat():
            continue
        falta = (prevista - hoje).days
        # longe ainda, ou atrasado mais de meio ciclo (comprou fora e nao anotou): nao insiste
        if falta > COMPRAS_AVISAR_DIAS or falta < -max(COMPRAS_AVISAR_DIAS, intervalo // 2):
            continue
        saida.append({"item": nomes[chave], "chave": chave, "intervalo_dias": intervalo,
                      "ultima": dias[-1].isoformat(), "prevista": prevista.isoformat(), "dias": falta})
    return sorted(saida, key=lambda i: i["dias"])


def adiar_compra(conn, item: str, hoje: date) -> str | None:
    """"Ainda tem": nao pergunta de novo ate a previsao + metade do intervalo."""
    chave = vida.normalizar_item_compra(item)
    prev = next((c for c in compras_previstas(conn, hoje) if c["chave"] == chave), None)
    folga = max(2, (prev["intervalo_dias"] if prev else 14) // 2)
    base = max(hoje, date.fromisoformat(prev["prevista"])) if prev else hoje
    ate = (base + timedelta(days=folga)).isoformat()
    if not chave:
        return None
    db.definir_configuracao(conn, f"compra_adiada_{chave}", ate)
    conn.commit()
    return ate


def avisar_compras(conn, agora: datetime) -> list[tuple[str, str, str]]:
    if not _na_janela(agora, JANELA_DIA) or db.ja_notificou_hoje(conn, "compras_previsao_chat"):
        return []
    itens = [i for i in compras_previstas(conn, agora.date())
             if not db.ja_notificado_alguma_vez(conn, "compra_prevista", vida.id_estavel("compra", i["chave"], i["ultima"]))]
    db.marcar_notificado(conn, "compras_previsao_chat")
    if not itens:
        conn.commit()
        return []
    for i in itens[:4]:
        db.marcar_notificado(conn, "compra_prevista", vida.id_estavel("compra", i["chave"], i["ultima"]))
    nomes = [i["item"] for i in itens[:4]]
    lista = nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]
    verbo = "deve acabar" if len(nomes) == 1 else "devem acabar"
    texto = f"Pelo teu ritmo de compra, {lista} {verbo} nos próximos dias. Ponho na lista?"
    publicar(conn, "compras_previsao_chat", texto, [cards.card_compras_previsao(itens)])
    return [("compras_previsao", "Lista de compras", texto)]


def contas_do_email(conn, agora: datetime) -> list[tuple[str, str, str]]:
    """Cacador de contas (Grupo E, 30/10/2026): a cada 30 min le o e-mail (IMAP so leitura, so se o .env
    tiver EMAIL_IMAP_*) e, se achou conta nova, poe o card `contas_email` no chat. Desligado = nao faz nada."""
    import email_contas

    if not email_contas.configurado() or not _na_janela(agora, JANELA_DIA):
        return []
    r = email_contas.varrer(conn, agora)
    novas = r["novas"]
    if not novas:
        return []
    card = cards.card_contas_email(novas, agora.date(), r["lidos"], agora.strftime("%H:%M"))
    if not card:
        return []
    n = len(card["data"]["contas"])
    texto = (f"Achei {n} coisa{'s' if n != 1 else ''} no teu e-mail. O código já tá pronto pra copiar "
             "e as contas com vencimento viraram tarefa no dia.")
    publicar(conn, "contas_email_chat", texto, [card])
    return [("contas_email", "Achei conta no e-mail", texto)]


def assinaturas_que_subiram(conn, agora: datetime) -> list[tuple[str, str, str]]:
    """Mesmo detector do push "Assinatura ficou mais cara" - aqui vira card no chat com
    "Mantém" / "Me lembra de cancelar". O push continua sendo o de sempre (sem duplicar)."""
    import gastos
    import notificacoes

    if not _na_janela(agora, JANELA_DIA):
        return []
    try:
        aumentos = gastos.detectar_aumento_assinatura(notificacoes._gastos_reais_unificados_para_deteccao(conn), agora.date())
    except Exception:
        return []
    for a in aumentos:
        ref = vida.id_estavel("assinatura_subiu", a["descricao"].strip().lower(), a["valor_novo"])
        if db.ja_notificado_alguma_vez(conn, "assinatura_subiu_chat", ref):
            continue
        db.marcar_notificado(conn, "assinatura_subiu_chat", ref)
        card = cards.card_assinatura_subiu(a)
        if card:
            texto = f"\"{card['data']['descricao']}\" ficou {card['data']['pct']}% mais cara. Mantém ou quer que eu te lembre de cancelar?"
            publicar(conn, "assinatura_subiu_chat", texto, [card])
    conn.commit()
    return []


def perguntar_horas_agora(conn, voo_id: int, agora: datetime) -> bool:
    """Saiu do aeroclube depois do voo: pergunta ja (o tick nao pergunta de novo)."""
    if db.ja_notificou_hoje(conn, "pos_voo_chat", voo_id):
        return False
    card = diario_bordo.card(conn, voo_id, agora.date())
    db.marcar_notificado(conn, "pos_voo_chat", voo_id)
    if card:
        publicar(conn, "pos_voo_chat", FRASES_POS_VOO[(agora.toordinal() + voo_id) % len(FRASES_POS_VOO)], [card])
    conn.commit()
    return bool(card)


# ------------------------------------------- como tu ta hoje (leva 22/10)
JANELA_COMO_ESTA = (time(7, 0), time(11, 0))
FRASES_COMO_ESTA = (
    "Bom dia! Como tu tá hoje? Um toque em cada e eu ajusto o dia.",
    "E aí, como acordou? Me diz aqui embaixo, é um toque só.",
    "Bom dia. Antes de tudo: como tá a energia, o sono e o humor hoje?",
)


def perguntar_como_esta(conn, agora: datetime) -> list[tuple[str, str, str]]:
    """De manha, uma vez por dia: o card do check-in no chat (o Alex nao achava onde dizer como
    esta). So pergunta se ele ainda nao respondeu nada hoje (pelo card, pela tela ou pelo chat)."""
    if not _na_janela(agora, JANELA_COMO_ESTA) or db.ja_notificou_hoje(conn, "como_esta_chat"):
        return []
    atual = db.get_checkin(conn, agora.date().isoformat()) or {}
    if any(atual.get(c) for c in vida.CAMPOS_CHECKIN):
        db.marcar_notificado(conn, "como_esta_chat")
        conn.commit()
        return []
    texto = FRASES_COMO_ESTA[agora.toordinal() % len(FRASES_COMO_ESTA)]
    publicar(conn, "como_esta_chat", texto, [cards.card_checkin(conn, agora.date())])
    return [("como_esta", "Como tu tá hoje?", "Um toque no chat: energia, sono e humor.")]


# ------------------------------------- dia que vai dar errado (leva 22/10)
JANELA_ALERTA_DIA = (time(7, 0), time(10, 30))
MINIMO_SINAIS = 2


def alerta_do_dia(conn, agora: datetime) -> list[tuple[str, str, str]]:
    """Manha, 1x por dia, nunca a noite: 2 sinais (sono curto, tarefas empurradas, gasto de ontem fora
    do padrao) = card pra travar o que nao pode falhar e aliviar o resto (dia_ruim)."""
    if not _na_janela(agora, JANELA_ALERTA_DIA) or db.ja_notificou_hoje(conn, "alerta_dia_chat"):
        return []
    hoje = agora.date()
    if dia_ruim.ativo(conn, hoje):  # ja aliviou o dia: nao precisa avisar
        return []
    sinais = dia_ruim.sinais_do_dia(conn, hoje)
    if len(sinais) < MINIMO_SINAIS or not dia_ruim.tarefas_do_dia(conn, hoje):
        return []
    texto = "Hoje tem sinal de dia difícil. Trava o que não pode falhar e eu alivio o resto."
    publicar(conn, "alerta_dia_chat", texto, [dia_ruim.card_alerta(conn, hoje, sinais)])
    return [("alerta_dia", "Hoje pede mais cuidado", f"{sinais[0]['texto']} e mais {len(sinais) - 1}. Abre pra ver.")]


JANELA_TRAVOU = (time(9, 0), time(18, 0))
JANELA_RECOMECO = (time(7, 30), time(11, 0))
DIAS_ENTRE_RECOMECOS = 6


def perguntar_por_que_travou(conn, agora: datetime) -> list[tuple[str, str, str]]:
    """Lab v4 (Por que travou?): tarefa empurrada 3+ vezes -> 1 card no chat, 1 vez por dia e UMA vez por tarefa,
    sem bronca. Nao pergunta se ja tem sessao de foco correndo nem em dia ruim."""
    if not _na_janela(agora, JANELA_TRAVOU) or db.ja_notificou_hoje(conn, "travou_chat"):
        return []
    if foco.segurando_avisos(conn, agora) or dia_ruim.ativo(conn, agora.date()):
        return []
    import cobranca  # 07/11: tarefa_adiada ganha (adiada 3+) e nada repete a mesma tarefa em 48 h

    pend = [t for t in foco_ideias.pendentes_travou(conn) if cobranca.pode(conn, t["id"], "travou", agora)]
    if not pend:
        return []
    t = pend[0]
    cobranca.registrar(conn, t["id"], "travou", agora)
    foco_ideias.marcar_perguntada(conn, t["id"])
    card = cards.novo_card("travou", foco_ideias.dados_travou(conn, t["id"]))
    publicar(conn, "travou_chat", "Essa tarefa já foi empurrada 3 vezes. Sem bronca: o que pega?", [card])
    return [("travou", "Essa travou?", f"\"{t['titulo']}\" foi empurrada {t['adiadas']} vezes. Um toque e eu ajudo.")]


def recomeco_do_dia(conn, agora: datetime) -> list[tuple[str, str, str]]:
    """Lab v4 (Recomeco): segunda, dia 1 ou mais de 10 atrasadas -> card no chat (no maximo 1 a cada 6 dias)."""
    if not _na_janela(agora, JANELA_RECOMECO) or db.ja_notificou_hoje(conn, "recomeco_chat"):
        return []
    hoje = agora.date()
    ultimo = db.obter_configuracao(conn, recomeco.CONFIG_AVISO)
    try:
        if ultimo and (hoje - date.fromisoformat(ultimo)).days < DIAS_ENTRE_RECOMECOS:
            return []
    except ValueError:
        pass
    if not recomeco.deve_aparecer(conn, hoje):
        return []
    est = recomeco.estado(conn, hoje)
    if not est["velhas"]:  # nada pra arquivar: o card nao ajudaria
        return []
    db.definir_configuracao(conn, recomeco.CONFIG_AVISO, hoje.isoformat())
    publicar(conn, "recomeco_chat", "Hora de recomeçar. Sem culpa: um toque e a lista respira.", [recomeco.card(conn, hoje)])
    return [("recomeco", "Recomeço", f"{est['total']} atrasadas. Um toque arquiva as velhas, sem culpa.")]


def verificar(conn, agora: datetime) -> list[tuple[str, str, str]]:
    """Chamado a cada tick do agendador. Publica no chat o que estiver na hora e
    devolve [(tipo_do_aviso, titulo, corpo)] pro push. Nunca levanta."""
    saida = []
    try:
        if _na_janela(agora, JANELA_FECHAR_DIA) and not db.ja_notificou_hoje(conn, "fechar_dia_chat"):
            # lab v4 (Grupo G): o fechamento das 21h agora e o Placar do feito + o Pouso do dia
            # (fechamento_dia.py). `fechar_dia` segue aqui, intacto, pra historico e pra quem o chama.
            import fechamento_dia

            r = fechamento_dia.pouso_do_dia(conn, agora.date(), agora.strftime("%H:%M"))
            db.marcar_notificado(conn, "fechar_dia_chat")
            if r:
                texto, lista = r
                publicar(conn, "fechar_dia_chat", texto, lista)
                saida.append(("fechamento_noturno", "Pousa o dia", fechamento_dia.resumo_push_pouso(lista[0], lista[1])))
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
            card = diario_bordo.card(conn, voo_id, agora.date())
            db.marcar_notificado(conn, "pos_voo_chat", voo_id)
            if card:
                texto = FRASES_POS_VOO[(agora.toordinal() + voo_id) % len(FRASES_POS_VOO)]
                publicar(conn, "pos_voo_chat", texto, [card])
                saida.append(("pos_voo", "Pousou?", "3 perguntas rápidas no chat e eu somo no diário de bordo."))
            conn.commit()
        if not db.ja_notificou_hoje(conn, "presentes_anuais"):
            renovar_presentes_anuais(conn, agora.date())
            db.marcar_notificado(conn, "presentes_anuais")
            conn.commit()
    except Exception:
        import logging
        logging.getLogger(__name__).exception("conversa proativa falhou")
    # 4a leva: cada automacao isolada - uma que quebra nao derruba as outras
    import aviacao_lab
    import manha
    import onde_estou  # leva "onde eu estou" (04/11): parado num lugar e ficando atrasado
    import retrospectiva
    import se_entao
    import tempo  # Grupo B (Tempo): espera, "eu te chamo", calibrador, disjuntor, porta
    import rotinas_esperto  # painel esperto, frente 7 (06/11): descobre rotinas / adiada 3x
    import voo_vespera  # painel esperto, frente 7 (06/11): voo decidido na vespera

    # Laboratorio v4 (30/10): cada grupo acrescenta os seus passos numa linha propria
    for passo in (vespera_do_voo, voo_vespera.verificar, manha_do_voo, documentos_vencendo, avisar_compras, assinaturas_que_subiram, contas_do_email,
                  perguntar_como_esta, alerta_do_dia, foco.aviso_do_meio,
                  rotinas_esperto.verificar, perguntar_por_que_travou, recomeco_do_dia,
                  manha.verificar, se_entao.verificar,
                  neste_dia.na_manha, coincidencias.na_semana,
                  aviacao_lab.chair_da_vespera, aviacao_lab.avisos_prazos,
                  tempo.modo_espera, tempo.chamar_na_hora, tempo.calibrador_novo, tempo.disjuntor, tempo.porta,
                  tempo.previsao_que_piora,  # assistente passo a passo (04/11): chuva >= 70% adianta a saida 1x
                  retrospectiva.avisar_mes,
                  onde_estou.verificar):
        try:
            saida.extend(passo(conn, agora))
        except Exception:
            import logging
            logging.getLogger(__name__).exception("conversa proativa: %s falhou", passo.__name__)
    return saida
