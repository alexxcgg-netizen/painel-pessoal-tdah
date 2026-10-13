"""Briefing meteorologico do voo (2026-10-13) - o "professor de aviacao" no dia de voo.

Junta, pra UM aerodromo, o METAR e o TAF oficiais (metar.buscar_metar_taf) ja
decodificados, a categoria padrao FAA/AIM (metar.categoria_voo), os fenomenos de
tempo traduzidos (-DZ -> "chuvisco fraco"), as horas em horario de Brasilia e um
link pro Windy (vento/nuvem em camadas, mapa). Mesma regra do metar.py: so
CONVERSAO de codigo pra texto/numero, nunca "pode voar / nao pode" - a decisao e
sempre do Alex (e do instrutor), o card diz isso.

SSBL (Blumenau, base dele) nao publica METAR: cai no aerodromo com METAR mais perto
(SBNF, Navegantes) e o card avisa a troca. Sem aerodromo pedido usa o do proximo voo
marcado (hoje/amanha) ou ICAO_PADRAO do .env (padrao SSBL).

Windy: so link (abre o app/site). A API de previsao pontual deles e paga e a chave
de teste devolve dado embaralhado - nao serve pra briefing de verdade.
"""

import os
import re
from datetime import date, datetime, timedelta, timezone

import metar

FUSO_BRASILIA = timezone(timedelta(hours=-3))

# aerodromos da regiao dele: nome curto + coordenada (pro link do Windy)
AERODROMOS = {
    "SSBL": ("Blumenau", -26.8325, -49.0906),
    "SBNF": ("Navegantes", -26.8800, -48.6514),
    "SBJV": ("Joinville", -26.2245, -48.7974),
    "SBFL": ("Florianópolis", -27.6703, -48.5525),
    "SBCT": ("Curitiba", -25.5285, -49.1758),
    "SBBI": ("Bacacheri", -25.4051, -49.2320),
    "SBJA": ("Jaguaruna", -28.6753, -49.0596),
    "SBCH": ("Chapecó", -27.1342, -52.6566),
    "SBLJ": ("Lages", -27.7821, -50.2815),
    "SBSP": ("Congonhas", -23.6261, -46.6564),
    "SBGR": ("Guarulhos", -23.4356, -46.4731),
}
# aerodromo sem METAR -> o mais perto que tem
SEM_METAR = {"SSBL": "SBNF"}

_RE_ICAO = re.compile(r"^[A-Z]{4}$")
_RE_HORA_OBS = re.compile(r"\b(\d{2})(\d{2})(\d{2})Z\b")
_RE_PERIODO_TXT = re.compile(r"dia (\d{2}) (\d{2})Z até dia (\d{2}) (\d{2})Z")
_RE_FM_TXT = re.compile(r"A partir do dia (\d{2}) as (\d{2}):(\d{2})Z")
_RE_FENOMENO = re.compile(r"^(\+|-|VC)?(MI|BC|PR|DR|BL|SH|TS|FZ)?((?:DZ|RA|SN|SG|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PO|SQ|FC|SS|DS)+)?$")

_FENOMENOS = {
    "DZ": ("chuvisco", "m"), "RA": ("chuva", "f"), "SN": ("neve", "f"), "SG": ("grãos de neve", "m"),
    "PL": ("pelotas de gelo", "f"), "GR": ("granizo", "m"), "GS": ("granizo pequeno", "m"),
    "UP": ("precipitação desconhecida", "f"), "BR": ("névoa úmida", "f"), "FG": ("nevoeiro", "m"),
    "FU": ("fumaça", "f"), "VA": ("cinzas vulcânicas", "f"), "DU": ("poeira", "f"), "SA": ("areia", "f"),
    "HZ": ("névoa seca", "f"), "PO": ("redemoinhos de poeira", "m"), "SQ": ("tempestade de vento", "f"),
    "FC": ("tornado/tromba", "m"), "SS": ("tempestade de areia", "f"), "DS": ("tempestade de poeira", "f"),
}
_DESCRITOR = {"MI": "baixo", "BC": "em bancos", "PR": "parcial", "DR": "soprado baixo", "BL": "soprado",
              "FZ": "congelante"}


def _limpar_icao(icao) -> str | None:
    s = str(icao or "").strip().upper()
    return s if _RE_ICAO.match(s) else None


def traduzir_fenomeno(token: str) -> str | None:
    """'-DZ' -> 'chuvisco fraco', 'TSRA' -> 'trovoada com chuva', 'VCSH' ->
    'pancadas nas proximidades'. None = nao e grupo de fenomeno."""
    if not token or token in ("NSW",):
        return "fim do tempo significativo" if token == "NSW" else None
    m = _RE_FENOMENO.match(token)
    if not m or not (m.group(2) or m.group(3)):
        return None
    intens, desc, corpo = m.group(1), m.group(2), m.group(3) or ""
    codigos = [corpo[i:i + 2] for i in range(0, len(corpo), 2)]
    nomes = [_FENOMENOS[c][0] for c in codigos if c in _FENOMENOS]
    genero = _FENOMENOS[codigos[0]][1] if codigos and codigos[0] in _FENOMENOS else "f"
    if desc == "TS":
        txt = "trovoada" + (f" com {' e '.join(nomes)}" if nomes else "")
        genero = "f"
    elif desc == "SH":
        txt = "pancadas" + (f" de {' e '.join(nomes)}" if nomes else "")
        genero = "fp"
    else:
        txt = " e ".join(nomes) if nomes else ""
        if desc and txt:
            txt += f" {_DESCRITOR[desc]}"
    if not txt:
        return None
    if intens == "-":
        txt += {"m": " fraco", "f": " fraca", "fp": " fracas"}[genero]
    elif intens == "+":
        txt += {"m": " forte", "f": " forte", "fp": " fortes"}[genero]
    elif intens == "VC":
        txt += " nas proximidades"
    return txt


def fenomenos(tokens: list[str]) -> list[str]:
    saida = []
    for t in tokens or []:
        if t == "RMK":
            break
        f = traduzir_fenomeno(t)
        if f and f not in saida:
            saida.append(f)
    return saida


def _hora_local(dia: int, hh: int, mm: int, agora_utc: datetime) -> datetime | None:
    """Dia/hora Z do boletim -> datetime em Brasilia. O mes vem do 'agora' (boletim
    do dia 31 lido no dia 1 volta um mes)."""
    try:
        base = agora_utc.replace(day=dia, hour=hh % 24, minute=mm, second=0, microsecond=0)
    except ValueError:
        return None
    if hh == 24:
        base += timedelta(days=1)
    if base - agora_utc > timedelta(days=15):
        mes_ant = (agora_utc.replace(day=1) - timedelta(days=1))
        try:
            base = base.replace(year=mes_ant.year, month=mes_ant.month)
        except ValueError:
            return None
    return base.astimezone(FUSO_BRASILIA)


def _hhmm(dt: datetime | None, hoje: date | None = None) -> str | None:
    """'09:00'; quando cai em outro dia que nao `hoje` (local): 'amanhã 09:00' / '15/10 09:00'."""
    if not dt:
        return None
    if hoje is None or dt.date() == hoje:
        return dt.strftime("%H:%M")
    if dt.date() == hoje + timedelta(days=1):
        return dt.strftime("amanhã %H:%M")
    return dt.strftime("%d/%m %H:%M")


def _periodo_segmento(seg: dict, agora_utc: datetime) -> tuple[str | None, str | None]:
    hoje = agora_utc.astimezone(FUSO_BRASILIA).date()
    tipo = seg.get("tipo") or ""
    m = _RE_FM_TXT.match(tipo)
    if m:
        return _hhmm(_hora_local(int(m.group(1)), int(m.group(2)), int(m.group(3)), agora_utc), hoje), None
    m = _RE_PERIODO_TXT.search(seg.get("periodo") or "")
    if m:
        de = _hora_local(int(m.group(1)), int(m.group(2)), 0, agora_utc)
        ate = _hora_local(int(m.group(3)), int(m.group(4)), 0, agora_utc)
        return _hhmm(de, hoje), _hhmm(ate, hoje)
    return None, None


def _rotulo_segmento(tipo: str) -> str:
    if tipo.startswith("A partir"):
        return "A partir de"
    return tipo or "Previsão"


def _resumo_tempo(dec: dict, fen: list[str]) -> str:
    partes = []
    if dec.get("teto_ft") is not None:
        partes.append(f"teto {dec['teto_ft']} pés")
    vis = dec.get("visibilidade_m")
    if vis is not None:
        partes.append("visibilidade 10 km ou mais" if vis >= 9999 else
                      f"visibilidade {vis / 1000:g} km" if vis >= 1000 else f"visibilidade {vis} m")
    partes.extend(fen)
    return ", ".join(partes)


def _vento_txt(v: dict | None) -> str | None:
    if not v:
        return None
    if v.get("velocidade_kt") == 0:
        return "vento calmo"
    base = f"vento variável {v['velocidade_kt']} kt" if v.get("variavel") else \
        f"vento {v['direcao']:03d}° com {v['velocidade_kt']} kt"
    if v.get("rajada_kt"):
        base += f", rajada {v['rajada_kt']}"
    return base


def windy_url(icao: str) -> str:
    a = AERODROMOS.get(icao)
    if not a:
        return "https://www.windy.com/"
    return f"https://www.windy.com/?{a[1]:.3f},{a[2]:.3f},10"


def proximo_voo(conn, hoje: date) -> dict | None:
    """Proximo voo marcado (hoje ou amanha) - o briefing usa a origem dele."""
    try:
        r = conn.execute(
            "SELECT data, hora, origem, destino FROM voos WHERE data IN (?, ?) "
            "ORDER BY data, COALESCE(hora, '99:99') LIMIT 1",
            (hoje.isoformat(), (hoje + timedelta(days=1)).isoformat()),
        ).fetchone()
    except Exception:
        return None
    if not r:
        return None
    return {"data": r["data"], "hora": r["hora"], "origem": r["origem"], "destino": r["destino"]}


def montar(conn=None, icao=None, agora_utc: datetime | None = None, buscar=None) -> dict:
    """Briefing pronto pro card e pra IA. Nunca levanta: erro vira {"erro": ...}."""
    agora_utc = agora_utc or datetime.now(timezone.utc)
    buscar = buscar or metar.buscar_metar_taf
    voo = proximo_voo(conn, agora_utc.astimezone(FUSO_BRASILIA).date()) if conn is not None else None
    pedido = _limpar_icao(icao) or _limpar_icao((voo or {}).get("origem")) or \
        _limpar_icao(os.environ.get("ICAO_PADRAO")) or "SSBL"
    alvo = SEM_METAR.get(pedido, pedido)
    try:
        bruto = buscar(alvo)
    except Exception:
        return {"erro": "não consegui buscar o METAR agora", "icao": alvo}
    if not bruto.get("metar") and not bruto.get("taf"):
        return {"erro": bruto.get("erro") or f"sem METAR/TAF pra {alvo}", "icao": alvo}

    dec = bruto.get("metar_decodificado") or {}
    tokens_metar = (bruto.get("metar") or "").split()
    fen = fenomenos(tokens_metar[2:])
    obs = None
    m = _RE_HORA_OBS.search(bruto.get("metar") or "")
    if m:
        obs = _hora_local(int(m.group(1)), int(m.group(2)), int(m.group(3)), agora_utc)
    idade = int((agora_utc - obs).total_seconds() // 60) if obs else None

    taf = []
    for seg in bruto.get("taf_segmentos") or []:
        de, ate = _periodo_segmento(seg, agora_utc)
        fen_seg = fenomenos(seg.get("tokens") or [])
        taf.append({
            "rotulo": _rotulo_segmento(seg.get("tipo") or ""),
            "de": de, "ate": ate,
            "categoria": seg.get("categoria_voo"),
            "resumo": _resumo_tempo(seg.get("decodificado") or {}, fen_seg) or "sem mudança significativa",
            "vento": _vento_txt((seg.get("decodificado") or {}).get("vento")),
        })

    nome = AERODROMOS.get(alvo, (alvo,))[0]
    cat = bruto.get("metar_categoria")
    hora_txt = f" às {obs.strftime('%Hh%M').replace('h00', 'h')}" if obs else ""
    frase = [f"{alvo} ({nome}){hora_txt}: {cat or 'sem categoria'}"]
    tempo = _resumo_tempo(dec, fen)
    if tempo:
        frase.append(tempo)
    if _vento_txt(dec.get("vento")):
        frase.append(_vento_txt(dec.get("vento")))
    if dec.get("qnh_hpa"):
        frase.append(f"QNH {dec['qnh_hpa']}")
    resumo = ", ".join(frase) + "."
    mudancas = [t for t in taf[1:] if t["categoria"] and t["categoria"] != cat]
    if mudancas:
        t = mudancas[0]
        quando = f" {t['de']}–{t['ate']}" if t["de"] and t["ate"] else (f" a partir de {t['de']}" if t["de"] else "")
        resumo += f" TAF: {t['rotulo'].lower()}{quando} {t['categoria']} ({t['resumo']})."

    return {
        "icao": alvo,
        "nome": nome,
        "pedido": pedido,
        "substituto_de": pedido if alvo != pedido else None,
        "categoria": cat,
        "observado": _hhmm(obs),
        "idade_min": idade,
        "vento": dec.get("vento"),
        "visibilidade_m": dec.get("visibilidade_m"),
        "teto_ft": dec.get("teto_ft"),
        "nuvens": dec.get("nuvens") or [],
        "temp": dec.get("temp"),
        "orvalho": dec.get("ponto_orvalho"),
        "qnh": dec.get("qnh_hpa"),
        "fenomenos": fen,
        "taf": taf[:6],
        "metar_bruto": bruto.get("metar"),
        "taf_bruto": bruto.get("taf"),
        "windy_url": windy_url(alvo),
        "voo": voo,
        "resumo": resumo,
        "aviso": "Conversão do boletim oficial, não é liberação: a decisão de voar é sua e do instrutor.",
    }
