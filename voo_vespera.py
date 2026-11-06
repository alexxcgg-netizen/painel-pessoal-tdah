"""Voo decidido na vespera (leva 06/11 "painel mais esperto", frente 7 -
docs/briefings/2026-11-06-painel-esperto.md).

Na noite antes do voo (20h, a mesma janela do card da vespera - conversa_proativa.vespera_do_voo) cruza:
  - o TAF do aerodromo NA HORA do voo (briefing_voo.previsao_na_hora: so conversao do boletim);
  - os limites que o app ja usa: categoria de voo (metar.categoria_voo - teto/visibilidade, FAA/AIM, a mesma
    VFR/MVFR/IFR dos cards) e o limite de traves PESSOAL dele na pista de SSBL (aviacao_lab.pista_config);
  - o sono: 8 h antes de acordar (docs/CARDS.md "Sono: 8 h antes de acordar pra voo"), com a hora de acordar do
    proprio card da vespera, e o que tem na noite anterior (balada com hora de volta, "(ate HH:MM)" no titulo).

Veredito: "Amanha voa." / "Amanha nao da." / "Amanha da, no limite." / "Ainda nao da pra saber." (TAF que nao
cobre a hora: diz ate quando vai e quando confere de novo - nunca inventa). Reconfere de manha (06:30, ou 2 h
antes se o voo for cedo) e so avisa de novo se MUDOU. No "nao da": procura um horario mais tarde no mesmo dia que
o TAF cobre, sem tarefa nem outro voo perto; achou -> "Remarco pras 13:00?" (1 toque, com Desfazer); nao achou ->
so a pergunta.

Push: pela fila de hora_certa.py (o mesmo caminho do aviso local do app). Na mesma rodada do card da vespera, o
push "Amanha tem voo" vira um so com o veredito (nao chegam dois as 20h).

Nada aqui e liberacao: e a conversao do boletim + as contas dele. A decisao e dele e do instrutor (o card diz).
"""
from __future__ import annotations

import json
import logging
import re
import time as _time
from datetime import datetime, time, timedelta, timezone

import cards
import db

log = logging.getLogger(__name__)

TIPO = "voo_decisao"
TIPO_CHAT = "voo_decisao_chat"
VESPERA = (time(20, 0), time(23, 30))  # = conversa_proativa.JANELA_VESPERA
RECONFERE_PADRAO = time(6, 30)  # = conversa_proativa.INICIO_MANHA_VOO
RECONFERE_ANTES_H = 2
RECONFERE_MAIS_CEDO = time(5, 0)
ULTIMA_CHECAGEM_NOITE = time(23, 0)
SONO_H = 8
VOLTA_PADRAO_BALADA = "03:00"  # = cards.VOLTA_PADRAO_BALADA
ULTIMA_DECOLAGEM_REMARCAR = "16:00"  # remarcacao so ate aqui (pousar de dia, com folga)
REMARCAR_PASSO_MIN = 30
REMARCAR_DEPOIS_MIN = 60
FOLGA_TAREFA_MIN = 90  # tarefa com hora mais perto que isso do horario novo = nao ta livre
FOLGA_OUTRO_VOO_MIN = 180
CACHE_TAF_S = 20 * 60
FUSO_BR = timezone(timedelta(hours=-3))
CHAVE_ESTADO = "voo_decisao_{}"
_RE_ATE = re.compile(r"\(at[eé] (\d{1,2}):(\d{2})\)")
_RE_EMISSAO = re.compile(r"\b(\d{2})(\d{2})(\d{2})Z\b")
_RE_VALIDADE = re.compile(r"^(\d{2})(\d{2})/(\d{2})(\d{2})$")
_CACHE: dict = {}

FRASE = {
    "voa": "{dia} voa.",
    "nao": "{dia} não dá.",
    "limite": "{dia} dá, no limite.",
    "incerto": "Ainda não dá pra saber.",
}


# ------------------------------------------------------------------ utilidades

def _buscar(icao: str) -> dict:
    """metar.buscar_metar_taf com cache de 20 min (a vespera e a manha consultam o mesmo TAF varias vezes)."""
    import metar

    agora = _time.monotonic()
    g = _CACHE.get(icao)
    if g and agora - g[0] < CACHE_TAF_S:
        return g[1]
    bruto = metar.buscar_metar_taf(icao)
    _CACHE[icao] = (agora, bruto)
    return bruto


def _min(hhmm) -> int | None:
    try:
        h, m = str(hhmm).split(":")
        h, m = int(h), int(m)
    except (TypeError, ValueError):
        return None
    return h * 60 + m if 0 <= h <= 23 and 0 <= m <= 59 else None


def _hm(minutos: int) -> str:
    minutos %= 24 * 60
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def hora_fala(hhmm: str | None) -> str:
    """'23:00' -> '23h'; '22:30' -> '22h30'."""
    m = _min(hhmm)
    if m is None:
        return hhmm or ""
    return f"{m // 60}h" if m % 60 == 0 else f"{m // 60}h{m % 60:02d}"


def _milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _utc(agora: datetime) -> datetime:
    return (agora if agora.tzinfo else agora.replace(tzinfo=FUSO_BR)).astimezone(timezone.utc)


def _quando(v) -> datetime | None:
    try:
        return datetime.fromisoformat(f"{v['data']}T{v['hora']}")
    except (TypeError, ValueError):
        return None


def hora_reconfere(hora_voo: str) -> str:
    """06:30, ou 2 h antes do voo se ele for cedo (nunca antes das 05:00)."""
    m = _min(hora_voo)
    base = RECONFERE_PADRAO.hour * 60 + RECONFERE_PADRAO.minute
    if m is not None:
        base = min(base, m - RECONFERE_ANTES_H * 60)
    return _hm(max(base, RECONFERE_MAIS_CEDO.hour * 60 + RECONFERE_MAIS_CEDO.minute))


# ------------------------------------------------------------------ o TAF

def _validade_e_emissao(bruto: dict, agora_utc: datetime) -> tuple[datetime | None, datetime | None, datetime | None]:
    """(inicio, fim, emissao) do TAF em Brasilia, None no que nao der pra ler."""
    import briefing_voo

    tokens = (bruto.get("taf") or "").split()
    ini = fim = emi = None
    for t in tokens:
        m = _RE_VALIDADE.match(t)
        if m and ini is None:
            ini = briefing_voo._hora_local(int(m.group(1)), int(m.group(2)), 0, agora_utc)
            fim = briefing_voo._hora_local(int(m.group(3)), int(m.group(4)), 0, agora_utc)
        m = _RE_EMISSAO.match(t)
        if m and emi is None:
            emi = briefing_voo._hora_local(int(m.group(1)), int(m.group(2)), int(m.group(3)), agora_utc)
    return ini, fim, emi


def _fmt_vis(vis_m: int) -> str:
    if vis_m >= 9999:
        return "10 km+"
    if vis_m >= 1000:
        return f"{vis_m / 1000:g} km".replace(".", ",")
    return f"{vis_m} m"


def _fmt_vento(v: dict) -> str:
    vel = v.get("velocidade_kt")
    if vel == 0:
        return "calmo"
    raj = f" G{v['rajada_kt']}" if v.get("rajada_kt") else ""
    if v.get("variavel") or v.get("direcao") is None:
        return f"variável {vel}{raj} kt"
    return f"{v['direcao']:03d}° {vel}{raj} kt"


def _tom_teto(teto_ft) -> str:
    """Mesmos cortes de metar.categoria_voo: < 1000 ft = IFR/LIFR, ate 3000 = MVFR."""
    if teto_ft is None:
        return "ok"
    if teto_ft < 1000:
        return "ruim"
    return "limite" if teto_ft <= 3000 else "ok"


def _tom_vis(vis_m) -> str:
    """< 3 SM = IFR/LIFR, ate 5 SM = MVFR (metar.categoria_voo)."""
    sm = vis_m / 1609.34
    if sm < 3:
        return "ruim"
    return "limite" if sm <= 5 else "ok"


_CAT_RUIM = ("IFR", "LIFR")


def avaliar_tempo(prev: dict, pedido: str, pista: dict | None) -> dict:
    """Quadradinhos de Teto/Visibilidade/Vento + o que pesa no veredito. `pista` = aviacao_lab.pista_config (so
    pra SSBL, a unica pista configurada) - sem ela o vento aparece mas nao vira limite."""
    conds, motivos = [], []  # motivos: (tom, frase)
    cat = prev.get("categoria")
    teto = prev.get("teto_ft")
    nuvens_ok = teto is None and (prev.get("visibilidade_m") is not None)
    if teto is not None or nuvens_ok:
        tom = _tom_teto(teto)
        conds.append({"rotulo": "Teto", "valor": f"{_milhar(teto)} ft" if teto is not None else "livre", "tom": tom})
        if tom != "ok":
            motivos.append((tom, f"Teto {_milhar(teto)} ft na hora do voo ({cat or ('IFR' if tom == 'ruim' else 'MVFR')})"))
    fen = [f for f in (prev.get("fenomenos") or []) if f != "fim do tempo significativo"]
    vis = prev.get("visibilidade_m")
    if vis is not None:
        tom = _tom_vis(vis)
        valor = _fmt_vis(vis) + (f", {fen[0]}" if fen else "")
        trovoada = any("trovoada" in f for f in fen)
        if trovoada:
            tom = "ruim"
        conds.append({"rotulo": "Visibilidade", "valor": valor, "tom": tom})
        if trovoada:
            motivos.append(("ruim", f"Previsão de {next(f for f in fen if 'trovoada' in f)} na hora do voo"))
        elif tom != "ok":
            motivos.append((tom, f"Visibilidade {_fmt_vis(vis)} na hora do voo ({cat or ('IFR' if tom == 'ruim' else 'MVFR')})"))
    elif any("trovoada" in f for f in fen):
        motivos.append(("ruim", f"Previsão de {next(f for f in fen if 'trovoada' in f)} na hora do voo"))
    vento = prev.get("vento")
    if vento:
        tom = "ok"
        if pista and pedido == "SSBL" and not vento.get("variavel") and vento.get("direcao") is not None:
            import aviacao_lab

            c = aviacao_lab.calcular_vento(vento["direcao"], vento.get("velocidade_kt"), pista, vento.get("rajada_kt"))
            if not c.get("variavel"):
                tom = {"ok": "ok", "alerta": "limite", "perigo": "ruim"}[c["tom"]]
                t = max(c["traves"], c.get("traves_rajada") or 0)
                if tom == "ruim":
                    motivos.append((tom, f"Través de {t} kt na {c['cabeceira']:02d}, teu limite é {pista['limite_kt']}"))
                elif tom == "limite":
                    motivos.append((tom, f"Través de {t} kt na {c['cabeceira']:02d}, perto do teu limite de {pista['limite_kt']}"))
        conds.append({"rotulo": "Vento", "valor": _fmt_vento(vento), "tom": tom})
    for p in prev.get("pode_ter") or []:
        if p.get("categoria") in _CAT_RUIM or "trovoada" in (p.get("resumo") or ""):
            rotulo = (p.get("rotulo") or "pode ter").strip()
            resumo = p.get("resumo") or "piora rápida"
            frase = f"Pode ter {resumo} nessa hora" if rotulo.startswith("pode") else \
                f"{rotulo[:1].upper()}{rotulo[1:]} de {resumo} nessa hora"
            motivos.append(("limite", frase))
            break
    return {"conds": conds, "motivos": motivos}


# ------------------------------------------------------------------ sono e vespera

def acordar_do_voo(conn, voo_id: int) -> str | None:
    """A hora de acordar do card da vespera que ja saiu no chat (com o trajeto do Maps); sem ele, a conta do
    proprio card sem Maps (folga de 15 min)."""
    try:
        for m in db.list_chat_mensagens(conn, 40):
            for c in db.cards_de_mensagem_chat(m):
                d = (c or {}).get("data") or {}
                if c.get("type") == "vespera_voo" and d.get("id") == voo_id and _min(d.get("acordar")) is not None:
                    return d["acordar"]
    except Exception:  # noqa: BLE001 - historico ilegivel: cai na conta
        pass
    try:
        card = cards.card_vespera_voo(conn, voo_id, None)
    except Exception:  # noqa: BLE001
        card = None
    return (card or {}).get("data", {}).get("acordar")


def _rel(minutos: int) -> int:
    """Minutos do dia da vespera; madrugada (antes do meio-dia) conta como depois da meia-noite."""
    return minutos + 24 * 60 if minutos < 12 * 60 else minutos


def vespera(conn, dia_vespera: str, acordar: str | None, agora: datetime | None = None) -> dict | None:
    """O quadradinho Sono/Vespera. None sem hora de acordar."""
    a = _min(acordar)
    if a is None:
        return None
    acordar_rel = a + 24 * 60  # acorda no dia seguinte a vespera
    deitar_rel = acordar_rel - SONO_H * 60
    livre_rel, quem = None, None
    try:
        linhas = conn.execute(
            "SELECT id, title, hora, estilo, extras FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL "
            "AND due_date = ? AND hora IS NOT NULL AND hora != '' ORDER BY hora",
            (dia_vespera,),
        ).fetchall()
    except Exception:  # noqa: BLE001 - banco velho sem estilo/extras
        linhas = []
    for r in linhas:
        inicio = _min(r["hora"])
        if inicio is None:
            continue
        try:
            extras = json.loads(r["extras"]) if r["extras"] else {}
        except (TypeError, ValueError):
            extras = {}
        fim = None
        m = _RE_ATE.search(r["title"] or "")
        if m:
            fim = _min(f"{m.group(1)}:{m.group(2)}")
        elif r["estilo"] == "balada":
            fim = _min((extras or {}).get("volta") or VOLTA_PADRAO_BALADA)
        ini_rel = _rel(inicio) if inicio < 6 * 60 else inicio
        if fim is not None:
            fim_rel = _rel(fim) if fim <= inicio or fim < 12 * 60 else fim
        elif ini_rel >= deitar_rel:
            fim_rel = ini_rel  # comeca depois da hora de deitar: no minimo ate la
        else:
            continue
        if fim_rel > deitar_rel and (livre_rel is None or fim_rel > livre_rel):
            nome = r["estilo"] if r["estilo"] in ("balada", "date") else _curto(r["title"])
            livre_rel, quem = fim_rel, (nome, _hm(fim_rel))
    agora_rel = None
    if agora is not None and agora.date().isoformat() == dia_vespera:
        agora_rel = agora.hour * 60 + agora.minute
    elif agora is not None and agora.date().isoformat() > dia_vespera:
        return None  # ja e o dia do voo: o sono ja foi
    inicio_sono = max(x for x in (deitar_rel, livre_rel, agora_rel) if x is not None)
    sono = max(0, acordar_rel - inicio_sono)
    deitar = _hm(deitar_rel)
    if quem:
        return {"rotulo": "Véspera", "valor": f"{quem[0]} até {hora_fala(quem[1])}", "tom": "ruim" if sono < SONO_H * 60 else "ok",
                "sono_min": sono, "motivo": f"{quem[0][0].upper() + quem[0][1:]} até {hora_fala(quem[1])}: dá só {_dur(sono)} de sono",
                "deitar": deitar}
    if sono >= SONO_H * 60:
        return {"rotulo": "Sono", "valor": f"8 h · deita {hora_fala(deitar)}", "tom": "ok", "sono_min": sono,
                "deitar": deitar}
    return {"rotulo": "Sono", "valor": f"{_dur(sono)} · deita agora", "tom": "limite", "sono_min": sono,
            "motivo": f"Sono: dá só {_dur(sono)} se deitar agora", "deitar": deitar}


def _dur(minutos: int) -> str:
    h, m = divmod(int(minutos), 60)
    return f"{h} h" if not m else f"{h}h{m:02d}"


def _curto(titulo: str, n: int = 14) -> str:
    t = _RE_ATE.sub("", titulo or "").strip()
    t = t[:1].lower() + t[1:] if len(t) > 1 and not t[1:2].isupper() else t
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


# ------------------------------------------------------------------ remarcar

def _livre(conn, voo_id: int, data: str, hora: str) -> bool:
    h = _min(hora)
    for r in conn.execute(
        "SELECT hora FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL AND due_date = ? AND hora IS NOT NULL",
        (data,),
    ).fetchall():
        m = _min(r["hora"])
        if m is not None and abs(m - h) < FOLGA_TAREFA_MIN:
            return False
    for r in conn.execute("SELECT id, hora FROM voos WHERE data = ? AND hora IS NOT NULL AND id != ?", (data, voo_id)).fetchall():
        m = _min(r["hora"])
        if m is not None and abs(m - h) < FOLGA_OUTRO_VOO_MIN:
            return False
    return True


def sugerir_remarcacao(conn, v, agora: datetime, previsao, pedido: str, pista) -> dict | None:
    """Primeiro horario mais tarde no mesmo dia (de 30 em 30 min, ate 16:00) que o TAF cobre com tudo ok e que
    esta livre. None quando nao tem dado ou nada serve."""
    base = _min(v["hora"])
    ultima = _min(ULTIMA_DECOLAGEM_REMARCAR)
    if base is None:
        return None
    m = base + REMARCAR_DEPOIS_MIN
    m += (-m) % REMARCAR_PASSO_MIN
    while m <= ultima:
        hora = _hm(m)
        prev = previsao(datetime.fromisoformat(f"{v['data']}T{hora}"))
        if prev is None:
            return None  # o TAF acabou: daqui pra frente nao tem dado
        av = avaliar_tempo(prev, pedido, pista)
        if not av["motivos"] and _livre(conn, v["id"], v["data"], hora):
            return {"data": v["data"], "hora": hora}
        m += REMARCAR_PASSO_MIN
    return None


# ------------------------------------------------------------------ a decisao

def decidir(conn, v, agora: datetime, buscar=None, fase: str = "vespera") -> dict:
    """Dado do card `voo_decisao`. `v` = linha de voos (id, data, hora, origem, destino, escalas)."""
    import aviacao_lab
    import briefing_voo
    import rota_voo

    buscar = buscar or _buscar
    agora_utc = _utc(agora)
    pedido = (v["origem"] or rota_voo.ORIGEM_PADRAO).strip().upper()
    alvo = briefing_voo.SEM_METAR.get(pedido, pedido)
    quando = _quando(v)
    amanha = v["data"] > agora.date().isoformat()
    dia = "Amanhã" if amanha else "Hoje"
    try:
        rota = rota_voo.montar(v["origem"], v["escalas"], v["destino"], v["hora"])
        sub = f"{pedido} · local" if rota["local"] else " → ".join(p["icao"] for p in rota["paradas"])
    except Exception:  # noqa: BLE001
        sub = pedido
    reconfere = hora_reconfere(v["hora"]) if fase == "vespera" else None
    dados = {
        "voo_id": v["id"], "data": v["data"], "hora": v["hora"], "quando": "amanha" if amanha else "hoje",
        "icao": alvo, "pedido": pedido, "nome": briefing_voo.AERODROMOS.get(alvo, (alvo,))[0],
        "substituto_de": pedido if alvo != pedido else None, "sub": sub,
        "conds": [], "veredito": "incerto", "frase": FRASE["incerto"], "porque": None, "nota": None,
        "reconfere": reconfere, "remarcar": None, "perguntar_remarcar": False, "emissao": None,
        "gerado_ts": int(_time.time()),
    }
    try:
        bruto = buscar(alvo) or {}
    except Exception:  # noqa: BLE001 - rede/fonte fora: nao inventa
        bruto = {}
    _, fim, emi = _validade_e_emissao(bruto, agora_utc) if bruto.get("taf") else (None, None, None)

    def previsao(q):
        return briefing_voo.previsao_na_hora(pedido, q, agora_utc, lambda _i: bruto)

    prev = previsao(quando) if (bruto.get("taf") and quando) else None
    if emi:
        dados["emissao"] = emi.strftime("%H:%M")
    if prev is None:
        if bruto.get("taf") and fim is not None:
            fim_txt = fim.strftime("%H:%M") if fim.date() == agora.date() else (
                "amanhã " + fim.strftime("%H:%M") if fim.date() == agora.date() + timedelta(days=1) else fim.strftime("%d/%m %H:%M"))
            dados["porque"] = f"O TAF de agora vai até {fim_txt} e o voo é às {v['hora']}"
        else:
            dados["porque"] = f"Não consegui o TAF de {alvo} agora"
        return dados

    pista = aviacao_lab.pista_config(conn) if pedido == aviacao_lab.AERODROMO_VENTO else None
    av = avaliar_tempo(prev, pedido, pista)
    dados["conds"] = av["conds"]
    motivos = list(av["motivos"])
    if fase == "vespera":
        sono = vespera(conn, (datetime.fromisoformat(v["data"]) - timedelta(days=1)).date().isoformat(),
                       acordar_do_voo(conn, v["id"]), agora)
        if sono:
            dados["conds"].append({k: sono[k] for k in ("rotulo", "valor", "tom")})
            dados["sono"] = {"deitar": sono["deitar"], "min": sono["sono_min"]}
            if sono.get("motivo"):
                motivos.append(("limite", sono["motivo"]))
    tons_tempo = [t for t, _ in av["motivos"]]
    if "ruim" in tons_tempo:
        veredito = "nao"
    elif motivos:
        veredito = "limite"
    else:
        veredito = "voa"
    dados["veredito"] = veredito
    dados["frase"] = FRASE[veredito].format(dia=dia)
    ruins = [f for t, f in motivos if t == "ruim"]
    limites = [f for t, f in motivos if t == "limite"]
    dados["porque"] = (ruins or limites or [None])[0]
    if veredito == "voa":
        dados["porque"] = "Teto, visibilidade e vento bons na hora do voo"
    if veredito == "nao":
        sug = sugerir_remarcacao(conn, v, agora, previsao, pedido, pista)
        dados["remarcar"] = sug
        dados["perguntar_remarcar"] = sug is None
    dados["nota"] = _nota(dados)
    return dados


def _nota(d: dict) -> str:
    fonte = ""
    if d.get("substituto_de"):
        fonte = f" É o TAF de {d['nome']} ({d['icao']}): {d['substituto_de']} não tem."
    reconf = f" Confiro de novo às {d['reconfere']} e te aviso se mudar." if d.get("reconfere") else ""
    if d["veredito"] == "incerto":
        return f"{d['porque']}.{reconf or ''}{fonte}".strip()
    emi = f"TAF das {hora_fala(d['emissao'])}" if d.get("emissao") else "O TAF"
    if d["veredito"] == "nao":
        if d.get("remarcar"):
            pergunta = (f" Às {hora_fala(d['remarcar']['hora'])} o TAF já fica bom e tu tá livre. "
                        f"Remarco pras {d['remarcar']['hora']}?")
        else:
            pergunta = " Quer remarcar?"
        return f"{d['porque']}.{pergunta}{fonte}".strip()
    extra = f" {d['porque']}." if d["veredito"] == "limite" and d.get("porque") else ""
    return f"{emi} cobre a hora do voo.{extra}{reconf}{fonte}".strip()


def card(dados: dict) -> dict:
    return cards.novo_card(TIPO, dados, [cards.acao_abrir_aba("aviacao", "Abrir Aviação")])


# ------------------------------------------------------------------ estado e o passo de 5 em 5 min

def _estado(conn, voo_id: int) -> dict | None:
    try:
        e = json.loads(db.obter_configuracao(conn, CHAVE_ESTADO.format(voo_id)) or "null")
    except ValueError:
        return None
    return e if isinstance(e, dict) else None


def _salvar_estado(conn, voo_id: int, estado: dict) -> None:
    db.definir_configuracao(conn, CHAVE_ESTADO.format(voo_id), json.dumps(estado, ensure_ascii=False))


def _na_janela(agora: datetime, janela) -> bool:
    return janela[0] <= agora.time() <= janela[1]


def _voos(conn, dia: str):
    return conn.execute(
        "SELECT id, data, hora, origem, destino, escalas FROM voos WHERE data = ? AND hora IS NOT NULL "
        "AND horas IS NULL AND COALESCE(tipo, '') != 'simulador' ORDER BY hora",
        (dia,),
    ).fetchall()


def proxima_checagem(dados: dict, v, agora: datetime, fase: str) -> str | None:
    quando = _quando(v)
    if fase == "vespera":
        if dados["veredito"] == "incerto":
            prox = (agora + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            if prox.time() <= ULTIMA_CHECAGEM_NOITE and prox.date() == agora.date():
                return prox.isoformat(timespec="minutes")
        return f"{v['data']}T{hora_reconfere(v['hora'])}"
    if dados["veredito"] == "incerto" and quando:
        prox = (agora + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        if prox <= quando - timedelta(hours=1):
            return prox.isoformat(timespec="minutes")
    return None


def _publicar(conn, texto: str, dados: dict) -> None:
    env = cards.envelope([card(dados)], texto, [])
    db.salvar_mensagem_chat(conn, "assistant", texto, env["cards"])
    db.marcar_notificado(conn, TIPO_CHAT, dados["voo_id"])


def _linha_vespera(conn, v) -> str:
    """"Acorda 06:15, sai 07:00." do card da vespera (junta o push "Amanha tem voo" com o veredito)."""
    try:
        for m in db.list_chat_mensagens(conn, 40):
            for c in db.cards_de_mensagem_chat(m):
                d = (c or {}).get("data") or {}
                if c.get("type") == "vespera_voo" and d.get("id") == v["id"]:
                    return f" Acorda {d['acordar']}, sai {d['sair']}. Mochila no chat."
    except Exception:  # noqa: BLE001
        pass
    return ""


def verificar(conn, agora: datetime, buscar=None) -> list:
    """Passo de conversa_proativa.verificar (depois de vespera_do_voo). Publica no chat e poe o aviso na fila
    de hora_certa; devolve [] (o push sai pela fila)."""
    import hora_certa
    from assistente import avisos as avisos_assistente

    hoje = agora.date()
    for dia, fase in (((hoje + timedelta(days=1)).isoformat(), "vespera"), (hoje.isoformat(), "manha")):
        for v in _voos(conn, dia):
            quando = _quando(v)
            if not quando or agora >= quando:
                continue
            st = _estado(conn, v["id"])
            if st and st.get("hora") != v["hora"]:
                st = None  # remarcou: decide de novo pro horario novo
            if st is None:
                if fase == "vespera" and not _na_janela(agora, VESPERA):
                    continue
                if fase == "manha" and (agora.strftime("%H:%M") < hora_reconfere(v["hora"])
                                        or agora > quando - timedelta(minutes=30)):
                    continue
            else:
                prox = st.get("proxima")
                if not prox or agora < datetime.fromisoformat(prox):
                    continue
            try:
                dados = decidir(conn, v, agora, buscar, fase)
            except Exception:
                log.exception("voo_vespera: decidir falhou (voo %s)", v["id"])
                continue
            anterior = (st or {}).get("veredito")
            novo = {"hora": v["hora"], "veredito": dados["veredito"], "em": agora.isoformat(timespec="minutes"),
                    "proxima": proxima_checagem(dados, v, agora, fase)}
            _salvar_estado(conn, v["id"], novo)
            if anterior is not None and anterior == dados["veredito"]:
                continue  # nada mudou: fica quieto (a promessa e "te aviso se mudar")
            mudou = anterior is not None
            texto = dados["frase"] if not mudou else f"Mudou: {dados['frase'][0].lower()}{dados['frase'][1:]}"
            if dados.get("porque") and dados["veredito"] != "voa":
                texto += f" {dados['porque']}."
            _publicar(conn, texto, dados)
            titulo = dados["frase"].rstrip(".")
            if dados["veredito"] == "incerto":
                titulo = f"Voo de {'amanhã' if dados['quando'] == 'amanha' else 'hoje'}: ainda não dá pra saber"
            elif mudou:
                titulo = f"Mudou: {titulo[0].lower()}{titulo[1:]}"
            corpo = (dados.get("porque") or "") + "."
            if dados["veredito"] == "nao":
                corpo += f" Remarco pras {dados['remarcar']['hora']}?" if dados.get("remarcar") else " Quer remarcar?"
            elif dados["veredito"] == "incerto" and novo["proxima"]:
                corpo += f" Confiro de novo às {novo['proxima'][11:16]}."
            if (fase == "vespera" and not mudou and avisos_assistente.esta_ligado(TIPO, conn=conn)
                    and db.ja_notificado_alguma_vez(conn, "vespera_voo_chat", v["id"])
                    and not db.ja_notificou_hoje(conn, "vespera_voo")):
                # mesma rodada do card da vespera: um push so (veredito + acorda/sai), nao dois
                corpo += _linha_vespera(conn, v)
                db.marcar_notificado(conn, "vespera_voo")
            ate = quando - timedelta(minutes=30)
            hora_certa.enfileirar(conn, TIPO, hora_certa.proximo_ref(conn), titulo, corpo.strip(), agora, ate,
                                  chave=f"voo:{v['id']}:{v['hora']}:{novo['em']}")
    return []


def remarcar(conn, voo_id: int, hora: str) -> dict | None:
    """Muda a hora do voo (botao "Remarcar pras 13:00") com Desfazer (edicao em voos). None = voo nao existe,
    ja voado ou hora invalida."""
    if _min(hora) is None:
        return None
    v = conn.execute("SELECT id, data, hora, horas FROM voos WHERE id = ?", (voo_id,)).fetchone()
    if not v or v["horas"] is not None:
        return None
    antes = {"hora": v["hora"]}
    conn.execute("UPDATE voos SET hora = ? WHERE id = ?", (hora, voo_id))
    conn.commit()
    token = db.criar_acao_desfazer(conn, [{"entidade": "edicao", "tabela": "voos", "id": voo_id, "antes": antes}])
    return {"ok": True, "hora": hora, "hora_antes": v["hora"], "token": token}
