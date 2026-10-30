"""Grupo B, Tempo (leva do Laboratorio v4, 30/10/2026 - docs/briefings/2026-10-30-lab-v4-tempo.md).

Cinco ideias que o Alex aprovou no prototipo, todas sobre o relogio:

  - fita        : o proximo compromisso do dia como uma fita fina no topo do app (`fita()`).
  - espera      : "livre ate 13:50" antes de um compromisso que trava o dia + "eu te chamo" (`card_espera`,
                  `modo_espera`, `chamar_na_hora`).
  - calibrador  : quanto ele achou x quanto levou de verdade -> o fator dele (x1,7) (`registrar_calibragem`,
                  `fator`, `card_calibrador`). A IA usa o fator (`linha_contexto`).
  - disjuntor   : foco seguido (hiperfoco/Parceiro de foco) por 90 min -> agua, comida ou alongar (`disjuntor`).
  - porta       : o que levar ao sair, por lugar; o que ele esquece uma vez entra sozinho (`card_porta`, `porta`).

Regras desta area:
  - Nada de rede aqui por conta propria: Maps/iCloud entram pelo `app.py` ja carregado (`_app()`), com cache curto,
    e qualquer falha cai na folga de 15 min (mesma do aviso "hora de sair").
  - Relogio na hora local do servidor (igual ao resto do painel). O front recebe SEGUNDOS ate o evento, nunca a
    hora absoluta, porque o servidor pode estar em outro fuso que o celular.
  - Um compromisso so entra na fita/espera/porta se for coisa que trava o dia (voo, agenda, saida, local, ou titulo
    de academia/aula/consulta...). Remedio, comer e tarefa solta com hora ficam de fora.
"""

from __future__ import annotations

import json
import re
import time as _time
import unicodedata
import zlib
from datetime import date, datetime, timedelta, timezone

import cards
import db
import notificacoes

FOLGA_MIN = 15  # sem Maps: mesma folga do aviso "hora de sair" (notificacoes.plano_se_arrumar)
JANELA_AVISO_SAIR_MIN = 25  # o aviso "hora de ir pro voo" (app._aviso_voo_sair) ja fala nessa janela antes da saida
JANELA_FITA_MIN = 180  # a fita esta cheia quando faltam 3 h ou mais
ESPERA_MIN_LIVRE = 60  # janela menor que isso nao vira card
ESPERA_ANTES_DE_COMECAR_MIN = 30  # o card sai ate 30 min antes de comecar a se arrumar
INICIO_ESPERA = (6, 30)  # nada de card de madrugada
FIM_ESPERA = (20, 0)

MIN_AMOSTRAS = 3  # fator so existe com 3 tarefas medidas
MAX_HISTORICO = 60
JANELA_FATOR = 10

DISJUNTOR_MIN = 90
DISJUNTOR_LACUNA_MIN = 12  # buraco maior que isso (2 ticks) quebra o "foco seguido"
DISJUNTOR_REFEICAO_MIN = 45
DISJUNTOR_REFEICAO_JANELA = ((13, 30), (19, 0))

LISTAS_PADRAO = {
    "Voo": list(cards.MOCHILA_VOO),
    "Academia": ["Garrafa d'água", "Toalha", "Fone", "Creatina"],
    "Faculdade": ["Notebook", "Carregador", "Crachá"],
}
LUGARES = tuple(LISTAS_PADRAO)


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in base if not unicodedata.combining(c))


# ----------------------------------------------------------------- utilidades
def _json(conn, chave: str, padrao):
    try:
        v = json.loads(db.obter_configuracao(conn, chave) or "null")
    except ValueError:
        return padrao
    return v if isinstance(v, type(padrao)) else padrao


def _guardar(conn, chave: str, valor):
    db.definir_configuracao(conn, chave, json.dumps(valor, ensure_ascii=False))


def _hhmm(dt: datetime) -> str:
    return f"{dt:%H:%M}"


def _app():
    try:
        from rotas._base import app_modulo

        return app_modulo()
    except Exception:
        return None


_CACHE: dict = {}


def _cache(chave, ttl_s: int, fn):
    """Maps/iCloud sao rede: a fita pergunta a cada poucos minutos, o resultado vale ~20 min."""
    agora = _time.monotonic()
    ent = _CACHE.get(chave)
    if ent and agora - ent[0] < ttl_s:
        return ent[1]
    try:
        valor = fn()
    except Exception:
        valor = None
    _CACHE[chave] = (agora, valor)
    return valor


def limpar_cache():
    _CACHE.clear()


# ------------------------------------------------------------ compromissos do dia
_E_COMPROMISSO = re.compile(
    r"\b(academia|treino|musculacao|aula|faculdade|prova|consulta|dentista|medico|medica|reuniao|entrevista|"
    r"exame|fisioterapia|terapia|psicologo|simulador|voo)\b"
)
_NAO_E = re.compile(r"\b(remedio|medicamento|vitamina|agua|tomar|comer|almoco|janta|cafe)\b")
_LUGAR_DO_TITULO = (
    ("Academia", re.compile(r"\b(academia|treino|musculacao)\b")),
    ("Faculdade", re.compile(r"\b(aula|faculdade|prova)\b")),
    ("Voo", re.compile(r"\b(voo|simulador)\b")),
)


def lugar_do_titulo(titulo: str) -> str | None:
    t = _sem_acento(titulo)
    for nome, rx in _LUGAR_DO_TITULO:
        if rx.search(t):
            return nome
    return None


def _e_compromisso_de_tarefa(r) -> bool:
    t = _sem_acento(r["title"])
    if notificacoes.e_refeicao(r["title"]) or notificacoes._ARRUMAR.search(t) or _NAO_E.search(t):
        return False
    return bool(
        notificacoes.e_compromisso_de_sair(r["title"]) or r["estilo"] in ("date", "balada")
        or (r["local"] or "").strip() or _E_COMPROMISSO.search(t)
    )


def _evento_hora(dia: date, hora: str | None) -> datetime | None:
    try:
        return datetime.combine(dia, datetime.strptime(hora or "", "%H:%M").time())
    except ValueError:
        return None


def _saida_voo(conn, v) -> dict | None:
    import conversa_proativa

    return _cache(("voo", v["data"], v["hora"], v["origem"]), 1200, lambda: conversa_proativa._saida_maps(conn, v))


def _trajeto_local(conn, local: str):
    app = _app()
    if app is None:
        return None
    import vida_assistente

    return _cache(("local", local), 1200,
                  lambda: app._trajeto_min_aviso(vida_assistente.resolver_lugar(conn, local)))


def _item(kind, ref, titulo, evento, sair, comecar, **extra) -> dict:
    return {"kind": kind, "ref": ref, "titulo": titulo, "hora": _hhmm(evento), "evento": evento, "sair": sair,
            "comecar": comecar, "arrumar_min": round((sair - comecar).total_seconds() / 60),
            "ir_min": round((evento - sair).total_seconds() / 60), **extra}


def compromissos(conn, agora: datetime, rede: bool = True) -> list[dict]:
    """Os compromissos de hoje que travam o dia, ordenados pela hora. `rede=False` pula Maps/iCloud (testes)."""
    import rota_voo
    import vida_assistente

    dia = agora.date()
    itens: list[dict] = []
    arrumar = vida_assistente.se_arrumar_min(conn)
    antes = vida_assistente.voo_briefing_min(conn)
    # voos
    for v in conn.execute(
        "SELECT id, data, hora, origem, destino, escalas FROM voos WHERE data = ? AND hora IS NOT NULL "
        "AND horas IS NULL AND COALESCE(tipo, '') != 'simulador' ORDER BY hora", (dia.isoformat(),),
    ).fetchall():
        ev = _evento_hora(dia, v["hora"])
        if not ev:
            continue
        maps = _saida_voo(conn, v) if rede else None
        sair_hm = (maps or {}).get("sair")
        sair = _evento_hora(dia, sair_hm) if sair_hm else ev - timedelta(minutes=antes + FOLGA_MIN)
        itens.append(_item("voo", v["id"], "Voo", ev, sair, sair - timedelta(minutes=arrumar), tem_saida=True,
                           lugar="Voo", chegar_min=antes, trajeto_min=(maps or {}).get("trajeto_min")))
    # tarefas
    for r in conn.execute(
        "SELECT id, title, hora, local, estilo FROM tasks WHERE due_date = ? AND hora IS NOT NULL "
        "AND completed_at IS NULL AND recorrencia IS NULL ORDER BY hora", (dia.isoformat(),),
    ).fetchall():
        ev = _evento_hora(dia, r["hora"])
        if not ev or not _e_compromisso_de_tarefa(r):
            continue
        sair_tipo = notificacoes.e_compromisso_de_sair(r["title"]) or r["estilo"] in ("date", "balada")
        tem_saida = bool(sair_tipo or (r["local"] or "").strip())
        caminho = 0
        trajeto = None
        if tem_saida:
            trajeto = _trajeto_local(conn, r["local"]) if (rede and (r["local"] or "").strip()
                                                           and (ev - agora) <= timedelta(hours=4)) else None
            caminho = trajeto if isinstance(trajeto, int) and trajeto >= 0 else FOLGA_MIN
        sair = ev - timedelta(minutes=caminho)
        arr = arrumar if sair_tipo else 0
        itens.append(_item("tarefa", r["id"], r["title"].strip()[:60], ev, sair, sair - timedelta(minutes=arr),
                           tem_saida=tem_saida, lugar=lugar_do_titulo(r["title"]), trajeto_min=trajeto,
                           sair_tipo=bool(sair_tipo)))
    # habitos com hora (ex.: Academia as 18:30), ainda nao marcados
    app = _app()
    if app is not None:
        try:
            for h in app._habitos_do_dia_com_horario(conn, dia):
                if h.get("concluido") or not _E_COMPROMISSO.search(_sem_acento(h["titulo"])) \
                        or _NAO_E.search(_sem_acento(h["titulo"])):
                    continue
                ev = datetime.fromisoformat(h["inicio"])
                itens.append(_item("habito", h["id"], h["titulo"], ev, ev, ev, tem_saida=False,
                                   lugar=lugar_do_titulo(h["titulo"])))
        except Exception:
            pass
    # agenda do iCloud
    if app is not None and rede:
        eventos = _cache(("agenda", dia.isoformat()), 600,
                         lambda: [e for e in app._eventos_de_hoje_com_seguranca(conn) if e.get("origem") == "calendario"])
        for e in eventos or []:
            if e.get("dia_inteiro"):
                continue
            try:
                ev = datetime.fromisoformat(e["inicio"])
            except (KeyError, ValueError, TypeError):
                continue
            if ev.tzinfo is not None:
                ev = ev.astimezone().replace(tzinfo=None)
            sair = ev - timedelta(minutes=FOLGA_MIN)
            itens.append(_item("agenda", zlib.crc32(f"{e.get('titulo')}{ev}".encode()), str(e.get("titulo") or "Compromisso").strip()[:60],
                               ev, sair, sair, tem_saida=True, lugar=lugar_do_titulo(str(e.get("titulo") or ""))))
    itens.sort(key=lambda i: i["evento"])
    return itens


# ----------------------------------------------------------------------- fita
def fita(conn, agora: datetime, rede: bool = True) -> dict | None:
    """O proximo compromisso (que ainda nao passou) em segundos - o front conta daqui."""
    for i in compromissos(conn, agora, rede):
        em = (i["evento"] - agora).total_seconds()
        if em < -300:
            continue
        if em > 12 * 3600:
            return None
        return {
            "titulo": i["titulo"], "hora": i["hora"], "tem_saida": bool(i.get("tem_saida")),
            "sair_em_s": int((i["sair"] - agora).total_seconds()), "evento_em_s": int(em),
            "janela_min": JANELA_FITA_MIN,
        }
    return None


# --------------------------------------------------------------- calibrador
def registrar_calibragem(conn, titulo: str, est_min, real_s, agora: datetime) -> bool:
    """Guarda 1 par (achou, levou). Chamado pelo Parceiro de foco quando ele termina uma tarefa com palpite."""
    try:
        est = int(est_min)
        real = max(1, round(float(real_s) / 60))
    except (TypeError, ValueError):
        return False
    if not 1 <= est <= 600 or real > 900:
        return False
    hist = _json(conn, "calibrador_historico", [])
    hist.append({"titulo": (titulo or "Tarefa").strip()[:60], "est": est, "real": real, "em": agora.date().isoformat()})
    _guardar(conn, "calibrador_historico", hist[-MAX_HISTORICO:])
    return True


def historico(conn) -> list[dict]:
    return [h for h in _json(conn, "calibrador_historico", [])
            if isinstance(h, dict) and isinstance(h.get("est"), int) and isinstance(h.get("real"), int)]


def fator(conn) -> dict | None:
    """Soma do que levou / soma do que achou nas ultimas 10 (a media das medias esconderia a tarefa grande)."""
    h = historico(conn)[-JANELA_FATOR:]
    if len(h) < MIN_AMOSTRAS:
        return None
    est, real = sum(x["est"] for x in h), sum(x["real"] for x in h)
    f = max(0.5, min(4.0, real / est))
    return {"fator": round(f, 1), "n": len(h), "est_media": round(est / len(h)), "real_media": round(real / len(h))}


def reservar(minutos: int, f: float) -> int:
    """Quanto reservar de verdade: palpite x fator, arredondado pra 5 min (nunca menos de 5)."""
    return max(5, int(round(minutos * f / 5.0)) * 5)


def linha_contexto(conn) -> str | None:
    f = fator(conn)
    if not f or abs(f["fator"] - 1) < 0.15:
        return None
    return (f"Fator de tempo do Alex (medido pelo painel em {f['n']} tarefas): ele costuma levar x{str(f['fator']).replace('.', ',')} "
            f"do que estima. Quando ele disser quanto tempo uma tarefa leva, reserve esse tempo vezes {str(f['fator']).replace('.', ',')} "
            "na agenda (arredonde pra 5 min) e avise isso em uma frase curta.")


def palpite_da_tarefa(conn, task_id: int) -> int | None:
    t = conn.execute("SELECT extras FROM tasks WHERE id = ?", (task_id,)).fetchone()
    try:
        e = json.loads(t["extras"]) if t and t["extras"] else {}
    except (TypeError, ValueError):
        return None
    v = e.get("estimativa_min") if isinstance(e, dict) else None
    return v if isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 600 else None


def guardar_palpite(conn, task_id: int, minutos: int) -> bool:
    t = conn.execute("SELECT extras FROM tasks WHERE id = ? AND completed_at IS NULL", (task_id,)).fetchone()
    if not t or not 1 <= minutos <= 600:
        return False
    try:
        e = json.loads(t["extras"]) if t["extras"] else {}
    except (TypeError, ValueError):
        e = {}
    if not isinstance(e, dict):
        e = {}
    e["estimativa_min"] = minutos
    conn.execute("UPDATE tasks SET extras = ? WHERE id = ?", (json.dumps(e, ensure_ascii=False), task_id))
    conn.commit()
    return True


def _tarefa_sem_palpite(conn, hoje: date) -> dict | None:
    for r in conn.execute(
        "SELECT id, title, extras FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL AND hora IS NULL "
        "AND (due_date IS NULL OR due_date <= ?) ORDER BY id DESC LIMIT 12", (hoje.isoformat(),),
    ).fetchall():
        if palpite_da_tarefa(conn, r["id"]) is None and not (r["extras"] and '"foco_s"' in r["extras"]):
            return {"id": r["id"], "titulo": r["title"].strip()[:60]}
    return None


def card_calibrador(conn, agora: datetime) -> dict | None:
    f = fator(conn)
    if not f:
        return None
    h = historico(conn)[-5:]
    return cards.novo_card("calibrador", {
        **f, "historico": [{"titulo": x["titulo"], "est": x["est"], "real": x["real"]} for x in h],
        "nova": _tarefa_sem_palpite(conn, agora.date()), "padrao_min": 20,
    })


def calibrador_novo(conn, agora: datetime) -> list[tuple[str, str, str]]:
    """Publica o card quando o fator nasce (3 tarefas) e de novo a cada 5 medidas novas, no maximo 1x por semana."""
    from conversa_proativa import JANELA_DIA, _na_janela, publicar

    if not _na_janela(agora, JANELA_DIA):
        return []
    n = len(historico(conn))
    pub = _json(conn, "calibrador_pub", {})
    if n < MIN_AMOSTRAS or (pub and (n - int(pub.get("n", 0)) < 5
                                      or (agora.date() - date.fromisoformat(pub.get("em", "2000-01-01"))).days < 7)):
        return []
    card = card_calibrador(conn, agora)
    if not card:
        return []
    d = card["data"]
    _guardar(conn, "calibrador_pub", {"n": n, "em": agora.date().isoformat()})
    f = str(d["fator"]).replace(".", ",")
    publicar(conn, "calibrador_chat", f"Já deu pra medir teu relógio: tu leva x{f} do que acha. "
             "Daqui pra frente eu reservo isso na agenda.", [card])
    return []


# ------------------------------------------------------------------ espera
def _chave_espera(i: dict) -> tuple[str, int]:
    return f"espera_{i['kind']}_chat", int(i["ref"])


def chamada(conn, i: dict) -> str:
    """ligado | desligado | garantido (compromisso de sair: o aviso 'hora de se arrumar' ja existe)."""
    if i.get("sair_tipo"):
        return "garantido"
    return "desligado" if db.obter_configuracao(conn, f"espera_chama_{i['kind']}_{i['ref']}") == "0" else "ligado"


def definir_chamada(conn, kind: str, ref: int, ligado: bool):
    db.definir_configuracao(conn, f"espera_chama_{kind}_{int(ref)}", "1" if ligado else "0")


def _cabe(conn, hoje: date, livre_min: int, f: float) -> list[dict]:
    """Tarefas sem hora com palpite dele que cabem na janela (palpite x fator). Sem palpite nao entra: duracao
    inventada seria mentira."""
    saida, soma = [], 0
    rows = conn.execute(
        "SELECT id, title, due_date, extras FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL AND hora IS NULL "
        "AND (due_date IS NULL OR due_date <= ?) ORDER BY due_date IS NULL, due_date, id", (hoje.isoformat(),),
    ).fetchall()
    for r in rows:
        palpite = palpite_da_tarefa(conn, r["id"])
        if palpite is None:
            continue
        m = reservar(palpite, f)
        if soma + m > livre_min:
            continue
        saida.append({"id": r["id"], "titulo": r["title"].strip()[:60], "min": m})
        soma += m
        if len(saida) == 3:
            break
    return saida


def card_espera(conn, i: dict, agora: datetime) -> dict:
    fa = fator(conn)
    livre = max(0, round((i["comecar"] - agora).total_seconds() / 60))
    return cards.novo_card("espera", {
        "kind": i["kind"], "ref": i["ref"], "titulo": i["titulo"], "hora": i["hora"], "livre_ate": _hhmm(i["comecar"]),
        "sair": _hhmm(i["sair"]), "livre_min": livre, "arrumar_min": i["arrumar_min"], "ir_min": i["ir_min"],
        "chamar": chamada(conn, i), "cabe": _cabe(conn, agora.date(), livre, fa["fator"] if fa else 1.0),
        "dia": agora.date().isoformat(),
    })


def modo_espera(conn, agora: datetime) -> list[tuple[str, str, str]]:
    """Dia com compromisso que trava: card 'livre ate HH:MM' no chat, 1x por compromisso. Sem push (o 'eu te
    chamo' e que avisa na hora)."""
    from conversa_proativa import publicar

    if not ((INICIO_ESPERA <= (agora.hour, agora.minute) <= FIM_ESPERA)):
        return []
    for i in compromissos(conn, agora):
        if not i.get("tem_saida") or i["evento"] <= agora:
            continue
        livre = (i["comecar"] - agora).total_seconds() / 60
        if livre < ESPERA_MIN_LIVRE:
            continue
        tipo, ref = _chave_espera(i)
        if db.ja_notificado_alguma_vez(conn, tipo, ref):
            continue
        db.marcar_notificado(conn, tipo, ref)
        card = card_espera(conn, i, agora)
        d = card["data"]
        nome = i["titulo"][:1].lower() + i["titulo"][1:] if i["titulo"][:2].upper() != i["titulo"][:2] else i["titulo"]
        publicar(conn, "espera_chat", f"Tu tá livre até {d['livre_ate']} (depois vem {nome} às {d['hora']}). "
                 + ("Eu te chamo na hora, pode esquecer do relógio." if d["chamar"] != "desligado"
                    else "Deixei o chamado desligado."), [card])
        return []  # um card por tick
    return []


def chamar_na_hora(conn, agora: datetime) -> list[tuple[str, str, str]]:
    """O 'eu te chamo': na hora de comecar a se arrumar, push (1x por compromisso). Compromisso de sair ja tem o
    aviso 'se_arrumar'; nao duplica."""
    saida = []
    for i in compromissos(conn, agora):
        if not i.get("tem_saida") or chamada(conn, i) != "ligado":
            continue
        if not (i["comecar"] - timedelta(minutes=4) <= agora < i["evento"]):
            continue
        # ja na janela do aviso de sair (voo_sair, compromisso_chegando, hora_de_sair): ele que fala, sem push duplo
        if agora >= i["sair"] - timedelta(minutes=JANELA_AVISO_SAIR_MIN):
            continue
        if db.ja_notificado_alguma_vez(conn, f"espera_chama_{i['kind']}", int(i["ref"])):
            continue
        db.marcar_notificado(conn, f"espera_chama_{i['kind']}", int(i["ref"]))
        nome = i["titulo"][:1].lower() + i["titulo"][1:] if i["titulo"][:2].upper() != i["titulo"][:2] else i["titulo"]
        corpo = (f"{i['arrumar_min']} min pra arrumar e sair às {_hhmm(i['sair'])}." if i["arrumar_min"]
                 else f"Sai às {_hhmm(i['sair'])} pra chegar às {i['hora']}.")
        saida.append(("espera_chama", f"Hora de ir pro {nome}" if i["kind"] == "voo" else f"Já dá pra ir se preparando: {nome}", corpo))
    return saida


# ----------------------------------------------------------------- disjuntor
def _foco_desde(conn, agora: datetime) -> datetime | None:
    """Inicio do foco que esta rodando agora: hiperfoco (ate - minutos) ou Parceiro de foco (`desde`)."""
    import foco

    inicios = []
    ate = db.obter_configuracao(conn, "hiperfoco_ate")
    import vida

    if vida.hiperfoco_ativo(ate, agora):
        try:
            minutos = int(db.obter_configuracao(conn, "hiperfoco_minutos") or 0)
            inicios.append(datetime.fromisoformat(ate) - timedelta(minutes=minutos))
        except (TypeError, ValueError):
            inicios.append(agora)
    s = foco.estado(conn, agora)
    if s and s["fase"] == "rodando":
        inicios.append(agora - timedelta(seconds=s["decorrido_s"]))
    return min(inicios) if inicios else None


def estado_disjuntor(conn, agora: datetime) -> dict | None:
    """Atualiza e devolve o episodio de foco seguido ({desde, ultimo, avisos, feitas}) - so avanca com foco ativo."""
    ativo = _foco_desde(conn, agora)
    e = _json(conn, "disjuntor_estado", {})
    ultimo = None
    try:
        ultimo = datetime.fromisoformat(e["ultimo"]) if e.get("ultimo") else None
    except (KeyError, ValueError):
        pass
    if ativo is None:
        return e if e and ultimo and (agora - ultimo) <= timedelta(minutes=DISJUNTOR_LACUNA_MIN) else None
    emenda = e and ultimo and (agora - ultimo) <= timedelta(minutes=DISJUNTOR_LACUNA_MIN) and e.get("desde")
    if emenda:
        e["desde"] = min(e["desde"], ativo.isoformat(timespec="seconds"))
    else:
        e = {"desde": ativo.isoformat(timespec="seconds"), "avisos": 0, "refeicao": False, "feitas": []}
    e["ultimo"] = agora.isoformat(timespec="seconds")
    _guardar(conn, "disjuntor_estado", e)
    return e


def _ultima_agua(conn, dia: date) -> str | None:
    r = conn.execute("SELECT criado_em FROM hidratacao_registros WHERE data = ? ORDER BY id DESC LIMIT 1",
                     (dia.isoformat(),)).fetchone()
    return db.utc_para_hora_local(r["criado_em"]) if r else None


def card_disjuntor(conn, agora: datetime, e: dict, motivo: str) -> dict:
    import refeicoes

    desde = datetime.fromisoformat(e["desde"])
    return cards.novo_card("disjuntor", {
        "desde": _hhmm(desde), "minutos": max(1, int((agora - desde).total_seconds() // 60)), "motivo": motivo,
        "ultima_agua": _ultima_agua(conn, agora.date()), "copos": db.contar_hidratacao_dia(conn, agora.date().isoformat()),
        "refeicoes": refeicoes.do_dia(conn, agora.date())["refeicoes"], "dia": agora.date().isoformat(),
    })


def disjuntor(conn, agora: datetime) -> list[tuple[str, str, str]]:
    """Foco seguido por 90 min (ou 45 min passada a hora do almoco sem refeicao registrada): card + push. Nao
    interrompe: o card so oferece, e cada 90 min de foco novo avisa de novo."""
    from conversa_proativa import publicar
    import refeicoes

    e = estado_disjuntor(conn, agora)
    if not e or _foco_desde(conn, agora) is None:
        return []
    desde = datetime.fromisoformat(e["desde"])
    min_foco = (agora - desde).total_seconds() / 60
    motivo = None
    if min_foco >= DISJUNTOR_MIN * (int(e.get("avisos", 0)) + 1):
        motivo = "tempo"
    elif (not e.get("refeicao") and min_foco >= DISJUNTOR_REFEICAO_MIN
          and DISJUNTOR_REFEICAO_JANELA[0] <= (agora.hour, agora.minute) <= DISJUNTOR_REFEICAO_JANELA[1]
          and refeicoes.do_dia(conn, agora.date())["refeicoes"] == 0):
        motivo = "refeicao"
    if not motivo:
        return []
    if motivo == "tempo":
        e["avisos"] = int(e.get("avisos", 0)) + 1
    e["refeicao"] = True if motivo == "refeicao" else e.get("refeicao", False)
    _guardar(conn, "disjuntor_estado", e)
    card = card_disjuntor(conn, agora, e, motivo)
    h, m = divmod(card["data"]["minutos"], 60)
    tempo = f"{h}h{m:02d}" if h else f"{m} min"
    texto = (f"{tempo} direto no foco. Água, comida ou alongar? Um toque registra e tu volta." if motivo == "tempo"
             else f"{tempo} no foco e ainda sem refeição hoje. Come algo? Um toque registra e tu volta.")
    publicar(conn, "disjuntor_chat", texto, [card])
    return [("disjuntor", "Corpo em dia?", f"{tempo} no foco sem pausa. Água, comida ou alongar? Um toque no chat.")]


def responder_disjuntor(conn, acao: str, agora: datetime) -> dict:
    """Um toque do card: registra de verdade (copo / refeicao) e, com os 3 feitos, zera o foco seguido."""
    import refeicoes

    out = {"acao": acao}
    if acao == "agua":
        out["copos"] = db.registrar_hidratacao(conn, agora.date().isoformat())
    elif acao == "comer":
        refeicoes.registrar(conn, [{"nome": "Comi algo (sem foto)", "gramas": 0, "kcal": 0, "proteina_g": 0,
                                    "carbo_g": 0, "gordura_g": 0}], None, agora)
    elif acao != "alongar":
        return {"error": "acao invalida"}
    e = _json(conn, "disjuntor_estado", {})
    if e:
        feitas = set(e.get("feitas") or [])
        feitas.add(acao)
        e["feitas"] = sorted(feitas)
        if len(feitas) == 3:
            e = {"desde": agora.isoformat(timespec="seconds"), "ultimo": agora.isoformat(timespec="seconds"),
                 "avisos": 0, "refeicao": True, "feitas": []}
            out["zerou"] = True
        _guardar(conn, "disjuntor_estado", e)
    return out


# ----------------------------------------------------------------------- porta
def listas(conn) -> dict:
    """Padrao + o que ele acrescentou (esquecimentos). {lugar: {"base": [...], "extras": [...]}}"""
    ex = _json(conn, "porta_extras", {})
    return {l: {"base": list(b), "extras": [x for x in (ex.get(l) or []) if isinstance(x, str)][:20]}
            for l, b in LISTAS_PADRAO.items()}


def adicionar_item(conn, lugar: str, item: str) -> bool:
    item = re.sub(r"\s+", " ", (item or "")).strip()[:40]
    if lugar not in LISTAS_PADRAO or not item:
        return False
    ex = _json(conn, "porta_extras", {})
    atual = [x for x in (ex.get(lugar) or []) if isinstance(x, str)]
    ja = {_sem_acento(x) for x in LISTAS_PADRAO[lugar] + atual}
    if _sem_acento(item) in ja:
        return True
    ex[lugar] = (atual + [item])[:20]
    _guardar(conn, "porta_extras", ex)
    return True


def remover_item(conn, lugar: str, item: str) -> bool:
    ex = _json(conn, "porta_extras", {})
    atual = [x for x in (ex.get(lugar) or []) if isinstance(x, str)]
    if item not in atual:
        return False
    ex[lugar] = [x for x in atual if x != item]
    _guardar(conn, "porta_extras", ex)
    return True


def _marcas(conn, lugar: str, dia: str, voo_id: int | None, n: int) -> list[bool]:
    """Voo reaproveita a mochila da vespera (os itens padrao); o resto fica em `porta_marcas`."""
    todo = _json(conn, "porta_marcas", {})
    guard = todo.get(dia, {}).get(lugar, []) if isinstance(todo.get(dia), dict) else []
    m = [bool(guard[i]) if i < len(guard) else False for i in range(n)]
    if lugar == "Voo" and voo_id:
        base = cards.mochila_feita(conn, voo_id)
        for i, v in enumerate(base[:n]):
            m[i] = v or m[i]
    return m


def marcar_item(conn, lugar: str, i: int, feito: bool, dia: str, voo_id: int | None = None) -> list[bool] | None:
    L = listas(conn).get(lugar)
    if not L:
        return None
    n = len(L["base"]) + len(L["extras"])
    if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < n:
        return None
    m = _marcas(conn, lugar, dia, voo_id, n)
    m[i] = bool(feito)
    todo = {d: v for d, v in _json(conn, "porta_marcas", {}).items() if d >= (date.fromisoformat(dia) - timedelta(days=3)).isoformat()}
    todo.setdefault(dia, {})[lugar] = m
    _guardar(conn, "porta_marcas", todo)
    if lugar == "Voo" and voo_id and i < len(cards.MOCHILA_VOO):
        base = cards.mochila_feita(conn, voo_id)
        base[i] = bool(feito)
        db.definir_configuracao(conn, f"mochila_voo_{voo_id}", json.dumps(base))
    return m


def card_porta(conn, lugar_atual: str, dia: str, sai: str | None = None, titulo: str | None = None,
               voo_id: int | None = None, vespera: bool = False) -> dict:
    ls = listas(conn)
    lugares = []
    for nome in LUGARES:
        itens = ls[nome]["base"] + ls[nome]["extras"]
        marcas = _marcas(conn, nome, dia, voo_id if nome == "Voo" else None, len(itens))
        lugares.append({"nome": nome, "itens": [{"texto": t, "feito": f, "meu": k >= len(ls[nome]["base"])}
                                                for k, (t, f) in enumerate(zip(itens, marcas))]})
    return cards.novo_card("porta", {"lugar": lugar_atual if lugar_atual in LUGARES else LUGARES[0], "lugares": lugares,
                                     "sai": sai, "titulo": titulo, "dia": dia, "voo_id": voo_id, "vespera": vespera})


def porta(conn, agora: datetime) -> list[tuple[str, str, str]]:
    """Na hora de comecar a se arrumar (ou 20 min antes de sair, sem tempo de arrumar): a lista do lugar, no chat.
    Na vespera (20h-23h30), a lista dos compromissos de amanha que nao sao voo (voo tem a mochila da vespera)."""
    from conversa_proativa import JANELA_VESPERA, _na_janela, publicar

    for i in compromissos(conn, agora):
        if not i.get("lugar") or i["evento"] <= agora:
            continue
        comeca = i["comecar"] if i["arrumar_min"] else i["sair"] - timedelta(minutes=20)
        if not (comeca - timedelta(minutes=4) <= agora):
            continue
        ref = int(i["ref"]) if i["kind"] != "agenda" else int(i["ref"])
        tipo = f"porta_{i['kind']}_chat"
        if db.ja_notificado_alguma_vez(conn, tipo, ref):
            continue
        db.marcar_notificado(conn, tipo, ref)
        card = card_porta(conn, i["lugar"], agora.date().isoformat(), _hhmm(i["sair"]), i["titulo"],
                          i["ref"] if i["kind"] == "voo" else None)
        faltam = sum(1 for x in next(l for l in card["data"]["lugares"] if l["nome"] == i["lugar"])["itens"] if not x["feito"])
        if not faltam:
            continue
        publicar(conn, "porta_chat", f"Antes de sair pra {i['titulo'].lower()} ({_hhmm(i['sair'])}): {faltam} "
                 f"{'coisa' if faltam == 1 else 'coisas'} pra pegar na porta.", [card])
        return []
    if _na_janela(agora, JANELA_VESPERA):
        amanha = agora.date() + timedelta(days=1)
        for r in conn.execute(
            "SELECT id, title, hora, local, estilo FROM tasks WHERE due_date = ? AND hora IS NOT NULL AND completed_at IS NULL "
            "AND recorrencia IS NULL ORDER BY hora", (amanha.isoformat(),),
        ).fetchall():
            lugar = lugar_do_titulo(r["title"])
            if not lugar or lugar == "Voo" or not _e_compromisso_de_tarefa(r):
                continue
            if db.ja_notificado_alguma_vez(conn, "porta_vespera_chat", r["id"]):
                continue
            db.marcar_notificado(conn, "porta_vespera_chat", r["id"])
            card = card_porta(conn, lugar, amanha.isoformat(), None, r["title"], None, vespera=True)
            publicar(conn, "porta_vespera_chat", f"Amanhã tem {r['title'].strip().lower()} às {r['hora']}. "
                     "Deixa a mochila pronta agora?", [card])
            return []
    return []
