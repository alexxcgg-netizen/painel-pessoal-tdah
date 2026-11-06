"""Viagem planejada (leva "painel mais esperto", 2026-11-06, docs/briefings/2026-11-06-painel-esperto.md,
frentes 2 e 5).

"Sabado vou de carro pra Dourados, saio umas 6" / "vou pra Curitiba agora" -> ferramenta `planejar_viagem`:

  - rota com transito PREVISTO pra hora real de sair (Routes, departureTime) e trechos lentos/parados;
  - tempo por trecho na hora em que ele passa (clima_rota, Open-Meteo gratis);
  - paradas pra abastecer onde o tanque estimado (combustivel.py) chega na reserva (60 km de folga):
    posto AO LONGO da rota (maps_client.postos_ao_longo), ABERTO na hora que ele passa, no maximo ~2 min
    fora da rota, preferindo posto 24 h / de rodovia. Uma busca por parada (cota Enterprise, 1.000/mes);
  - chegada contando as paradas, litros e custo (preco do ultimo abastecimento, se tiver);
  - 3 horarios de saida comparados (o pedido + vizinhos) com a frase de qual e melhor (menos chuva,
    menos transito, chegar antes de escurecer - por do sol calculado aqui, sem API);
  - salva em `viagens_planejadas` e vira o card `viagem` (o MESMO card de rota, com o mapa, mais coisas).

Viagem curta (ate 300 km): se o tanque estimado nao da ida E volta com folga, entra a parada no posto ja na
rota. Nada inventado: sem dado do Google/Open-Meteo, a parte some (nunca "~" de exemplo).

CONTRATO (o GPS/ao vivo do iPhone importa isto - nao mudar os nomes):
    plano_ativo(conn, agora) -> dict | None   (viagem nao encerrada com saida-2h <= agora <= chegada+2h)
    encerrar(conn, id)
    dict: id, destino, saida_em (iso), chegada_em (iso), total_km, traco (formato do card rota),
          pontos_km [[lat, lng, km], ...] (~1 ponto a cada 2-5 km), postos [{km, nome, lat, lng, passa_em}],
          chuva [{de_km, ate_km, tipo, inicio_em}]
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
from datetime import date, datetime, timedelta

import clima_rota
import combustivel
import maps_client

PARADA_MIN = 15  # minutos parado abastecendo (banheiro incluso)
DESVIO_MAX_MIN = 2
DESVIO_MAX_KM_SEM_RESUMO = 0.5  # sem o resumo de desvio do Google: posto a no maximo 500 m da linha
JANELA_KM = 150  # o posto e procurado nos 150 km antes do ponto em que o tanque chega na reserva
VIAGEM_CURTA_KM = 300
MAX_PARADAS = 4
ABERTO_FOLGA_MIN = 15  # posto que fecha 5 min depois de ele passar nao serve
ANTES_SAIDA = timedelta(hours=2)
DEPOIS_CHEGADA = timedelta(hours=2)
FUSO_BRASILIA_MIN = -180
DIAS_SEMANA = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
ORIGEM_AQUI = ("aqui", "daqui", "onde estou", "minha localizacao", "minha localização")
ORIGEM_CASA = ("casa", "minha casa", "em casa", "de casa")
_CHUVOSOS = {"granizo": 2.0, "trovoada": 2.0, "neblina": 2.0, "chuva_forte": 2.0, "chuva": 1.0, "vento": 0.5}
_RODOVIA = ("br-", "rodovia", "rod.", "km ", "graal", "frango assado", "posto da serra")


# ---------------------------------------------------------------- sol (NOAA, sem API)

def sol(lat: float, lon: float, dia: date) -> tuple[datetime, datetime] | None:
    """Nascer e por do sol (hora de Brasilia, sem fuso) naquele ponto e dia - formula da NOAA
    (gml.noaa.gov/grad/solcalc), erro de ~1-2 min. None em dia polar (nao acontece no Brasil)."""
    n = dia.timetuple().tm_yday
    g = 2 * math.pi / 365 * (n - 1)
    eq = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                   - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    dec = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
           + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    la = math.radians(lat)
    x = math.cos(math.radians(90.833)) / (math.cos(la) * math.cos(dec)) - math.tan(la) * math.tan(dec)
    if not -1 <= x <= 1:
        return None
    ha = math.degrees(math.acos(x))
    base = datetime(dia.year, dia.month, dia.day)
    nascer = base + timedelta(minutes=720 - 4 * (lon + ha) - eq + FUSO_BRASILIA_MIN)
    por = base + timedelta(minutes=720 - 4 * (lon - ha) - eq + FUSO_BRASILIA_MIN)
    return nascer, por


# ---------------------------------------------------------------- geometria do caminho

def _acumulado(pontos) -> list[float]:
    acum = [0.0]
    for a, b in zip(pontos, pontos[1:]):
        acum.append(acum[-1] + maps_client._km(a, b))
    return acum


def _indice_do_km(acum: list[float], km: float) -> int:
    for i, k in enumerate(acum):
        if k >= km:
            return i
    return len(acum) - 1


def reduzir(pontos, acum: list[float], total_km: float) -> list[list[float]]:
    """Polyline reduzida pro GPS: [lat, lng, km] a cada ~2-5 km (passo cresce com a viagem, max ~300)."""
    if not pontos:
        return []
    passo = min(5.0, max(2.0, total_km / 300))
    saida, ultimo = [], -passo
    for (lat, lon), k in zip(pontos, acum):
        if k - ultimo >= passo:
            saida.append([round(lat, 5), round(lon, 5), round(k, 1)])
            ultimo = k
    fim = [round(pontos[-1][0], 5), round(pontos[-1][1], 5), round(acum[-1], 1)]
    if saida[-1] != fim:
        saida.append(fim)
    return saida


def _posicao_no_caminho(pontos, acum, lat, lng, i0: int, i1: int) -> tuple[float, float]:
    """(km ao longo do caminho, distancia em km ate a linha) do ponto mais perto entre i0 e i1."""
    melhor_i, melhor_d = i0, float("inf")
    for i in range(max(0, i0), min(len(pontos), i1 + 1)):
        d = maps_client._km(pontos[i], (lat, lng))
        if d < melhor_d:
            melhor_i, melhor_d = i, d
    return acum[melhor_i], melhor_d


# ---------------------------------------------------------------- horarios

def _hhmm(d: datetime) -> str:
    return d.strftime("%H:%M")


class Linha:
    """Hora em que ele passa em cada km, numa saida: proporcional ao tempo do Google + paradas antes."""

    def __init__(self, saida: datetime, duracao_min: float, total_km: float, paradas: list[dict]):
        self.saida, self.dur, self.total = saida, float(duracao_min), max(0.1, float(total_km))
        self.paradas = sorted(paradas, key=lambda p: p["km"])

    def quando(self, km: float) -> datetime:
        extra = sum(PARADA_MIN + (p.get("desvio_min") or 0) for p in self.paradas if p["km"] < km)
        return self.saida + timedelta(minutes=self.dur * min(km, self.total) / self.total + extra)

    def chegada(self) -> datetime:
        return self.quando(self.total + 1)


def candidatas(pedida: datetime, agora: datetime, duracao_min: float) -> list[datetime]:
    """O horario pedido + 2 vizinhos (-1 h / +1 h; viagem longa: -1 h / +2 h). Nunca no passado."""
    longe = duracao_min > 240
    depois = 120 if longe else 60
    if pedida - timedelta(minutes=60) < agora + timedelta(minutes=5):
        return [pedida, pedida + timedelta(minutes=60), pedida + timedelta(minutes=60 + depois)]
    return [pedida - timedelta(minutes=60), pedida, pedida + timedelta(minutes=depois)]


# ---------------------------------------------------------------- postos

def _eh_rodovia(p: dict) -> bool:
    txt = f"{p.get('nome', '')} {p.get('endereco', '')}".lower()
    return any(m in txt for m in _RODOVIA)


def preparar_postos(achados: list[dict], pontos, acum, fator: float, janela: tuple[float, float]) -> list[dict]:
    """Resultado do Google -> postos dentro da janela (km), no maximo ~2 min fora da rota.
    Desvio = (inicio -> posto -> fim do pedaco) menos o melhor de todos (o que fica na beira da rota)."""
    a, b = janela
    i0 = _indice_do_km(acum, a / fator) - 2
    i1 = _indice_do_km(acum, b / fator) + 2
    vias = [p["via_s"] for p in achados if isinstance(p.get("via_s"), (int, float))]
    base = min(vias) if vias else None
    saida = []
    for p in achados:
        km, dist = _posicao_no_caminho(pontos, acum, p["lat"], p["lng"], i0, i1)
        km *= fator
        if not (a - 1 <= km <= b + 1):
            continue
        if base is not None and isinstance(p.get("via_s"), (int, float)):
            desvio = max(0, round((p["via_s"] - base) / 60))
            if desvio > DESVIO_MAX_MIN:
                continue
        else:
            if dist > DESVIO_MAX_KM_SEM_RESUMO:
                continue
            desvio = None
        saida.append({**p, "km": round(km), "desvio_min": desvio, "rodovia": _eh_rodovia(p)})
    return saida


def escolher_posto(postos: list[dict], quando_passa, curta: bool) -> dict | None:
    """O melhor posto ABERTO na hora em que ele passa (e ainda 15 min depois). Viagem longa: 24 h,
    de rodovia, o mais adiante (aproveita o tanque). Curta: o que menos desvia."""
    abertos = []
    for p in postos:
        t = quando_passa(p["km"])
        a1 = maps_client.aberto_em(p.get("periodos"), t)
        a2 = maps_client.aberto_em(p.get("periodos"), t + timedelta(minutes=ABERTO_FOLGA_MIN))
        if not (a1 and a1["aberto"] and a2 and a2["aberto"]):
            continue  # fechado ou sem horario no Google: nao manda ele pra la
        abertos.append({**p, "passa": t, "h24": a1["24h"], "ate": a1["ate"]})
    if not abertos:
        return None
    if curta:
        return min(abertos, key=lambda p: (p["desvio_min"] or 0, not p["h24"], p["km"]))
    return max(abertos, key=lambda p: (p["h24"], p["rodovia"], p["km"]))


def janelas_de_parada(total_km: float, litros_ini: float, tanque_l: float, kml: float, reserva_km: float,
                      curta: bool) -> list[tuple[float, float]]:
    """Onde procurar posto: cada janela termina onde o tanque estimado chega na reserva."""
    alcance = litros_ini * kml - reserva_km
    precisa = total_km * (2 if curta else 1)
    if alcance >= precisa:
        return []
    if alcance < 10:  # ja na reserva: o primeiro posto que aparecer
        alcance = min(total_km, max(10.0, litros_ini * kml * 0.7))
    if curta:
        return [(2.0, min(total_km, alcance))]
    janelas, pos = [], 0.0
    cheio = tanque_l * kml - reserva_km
    while pos + alcance < total_km and len(janelas) < MAX_PARADAS:
        fim = pos + alcance
        janelas.append((max(pos + 5, fim - JANELA_KM), fim))
        pos, alcance = fim, cheio  # conta como se parasse no fim da janela (o posto real fica antes)
    return janelas


# ---------------------------------------------------------------- comparacao das saidas

def _km_chuvoso(chuva: list[dict]) -> float:
    return sum((c["ate_km"] - c["de_km"]) * _CHUVOSOS.get(c["tipo"], 0) for c in chuva)


def _pontuar(s: dict) -> float:
    noite = sum(n["ate_km"] - n["de_km"] for n in s["noite"])
    return _km_chuvoso(s["chuva"]) * 0.5 + noite * 0.3 + (s.get("transito_min") or 0)


def dica(s: dict) -> str:
    """Uma frase do que essa saida pega."""
    partes = []
    ruins = [c for c in s["chuva"] if c["tipo"] in _CHUVOSOS]
    if ruins:
        pior = max(ruins, key=lambda c: (_CHUVOSOS[c["tipo"]], c["ate_km"] - c["de_km"]))
        partes.append(f"Pega {clima_rota.ROTULO[pior['tipo']]} do km {pior['de_km']} ao {pior['ate_km']}")
    else:
        partes.append("Sem chuva no caminho")
    t = s.get("transito_min")
    if isinstance(t, int) and t >= 5:
        partes.append(f"+{t} min de trânsito")
    noite = sum(n["ate_km"] - n["de_km"] for n in s["noite"])
    if noite <= 0:
        partes.append("chega com luz do dia" if s.get("por_do_sol") else "")
    elif s["noite"][-1]["ate_km"] >= s["total_km"] - 1:
        partes.append(f"os últimos {round(noite)} km já são de noite")
    else:
        partes.append(f"{round(noite)} km de noite")
    partes = [p for p in partes if p]
    return (", ".join(partes[:-1]) + " e " + partes[-1] if len(partes) > 1 else partes[0]) + "."


def frase_melhor(saidas: list[dict], pedida: int) -> tuple[int, str]:
    pontos = [_pontuar(s) for s in saidas]
    melhor = min(range(len(saidas)), key=lambda i: (round(pontos[i], 1), i != pedida))
    if len(saidas) == 1:
        return pedida, ""
    if melhor == pedida:
        return pedida, f"Saindo {saidas[pedida]['hora']} é o melhor dos {len(saidas)} horários."
    if pontos[pedida] - pontos[melhor] < 8:
        return pedida, f"Os horários dão parecido: saindo {saidas[pedida]['hora']} tá bom."
    a, b = saidas[melhor], saidas[pedida]
    porque = []
    if _km_chuvoso(b["chuva"]) - _km_chuvoso(a["chuva"]) >= 20:
        porque.append("pega menos chuva")
    noite_a = sum(n["ate_km"] - n["de_km"] for n in a["noite"])
    noite_b = sum(n["ate_km"] - n["de_km"] for n in b["noite"])
    if noite_a <= 0 < noite_b:
        porque.append("chega antes de escurecer")
    elif noite_b - noite_a >= 30:
        porque.append("dirige menos de noite")
    if (b.get("transito_min") or 0) - (a.get("transito_min") or 0) >= 5:
        diff = (b.get("transito_min") or 0) - (a.get("transito_min") or 0)
        porque.append(f"pega {diff} min a menos de trânsito")
    if not porque:
        porque.append("o caminho fica mais tranquilo")
    texto = " e ".join([", ".join(porque[:-1]), porque[-1]] if len(porque) > 1 else porque)
    return melhor, f"Melhor sair {a['hora']}: {texto}."


# ---------------------------------------------------------------- uma saida

def _noite(linha: Linha, amostras: list[list[float]]) -> tuple[list[dict], datetime | None, datetime | None]:
    """Trechos (km) que ele passa de noite + a hora do por do sol / nascer em que isso muda."""
    trechos, escurece, amanhece = [], None, None
    noite_ant, cache = None, {}
    for lat, lng, km in amostras:
        t = linha.quando(km)
        chave = (round(lat), round(lng), t.date())
        if chave not in cache:
            cache[chave] = sol(lat, lng, t.date())
        s = cache[chave]
        if not s:
            continue
        nascer, por = s
        noite = t < nascer or t >= por
        if noite and (not trechos or trechos[-1]["ate_km"] is not None):
            trechos.append({"de_km": km, "ate_km": None})
            if noite_ant is False and t >= por and escurece is None:
                escurece = por
        if not noite and trechos and trechos[-1]["ate_km"] is None:
            trechos[-1]["ate_km"] = km
            if amanhece is None:
                amanhece = nascer
        noite_ant = noite
    if trechos and trechos[-1]["ate_km"] is None:
        trechos[-1]["ate_km"] = amostras[-1][2]
    return [{"de_km": round(t["de_km"]), "ate_km": round(t["ate_km"])} for t in trechos if t["ate_km"] > t["de_km"]], \
        escurece, amanhece


def _chuva(tempo: dict | None, fator: float, linha: Linha) -> list[dict]:
    if not tempo:
        return []
    saida = []
    for t in tempo.get("trechos") or []:
        if t.get("tipo") == "ok":
            continue
        de, ate = round(t["de_km"] * fator), round(t["ate_km"] * fator)
        saida.append({
            "tipo": t["tipo"], "de_km": de, "ate_km": ate, "hora": t.get("hora_ini") or "",
            "inicio_em": linha.quando(de).isoformat(timespec="minutes"),
            "frase": clima_rota.frase({**t, "de_km": de, "ate_km": ate})[:200],
            "nome": t.get("nome"), "serra": bool(t.get("serra")),
        })
    return saida


def _lentos(lentidao: list[dict], fator_proprio: float) -> list[dict]:
    saida = []
    for x in lentidao or []:
        if not isinstance(x, dict) or x.get("nivel") not in ("lento", "parado"):
            continue
        de = float(x.get("de_km") or 0) * fator_proprio
        saida.append({"nivel": x["nivel"], "de_km": round(de, 1),
                      "ate_km": round(de + float(x.get("extensao_km") or 0) * fator_proprio, 1),
                      "frase": maps_client.frase_trecho(x)[:160]})
    return saida[:4]


def _eventos(s: dict, origem_nome: str, destino_nome: str, texto_tanque_ini: str, linha: Linha) -> list[dict]:
    ev = [{"t": linha.saida, "tipo": "", "titulo": f"Sai de {origem_nome}", "sub": texto_tanque_ini}]
    for c in s["chuva"]:
        rot = clima_rota.ROTULO.get(c["tipo"], c["tipo"]).capitalize()
        sub = ", ".join(p for p in (c.get("nome"), "na serra" if c.get("serra") else "") if p)
        ev.append({"t": linha.quando(c["de_km"]), "tipo": "chuva", "titulo": f"{rot} por {c['ate_km'] - c['de_km']} km",
                   "sub": sub})
    for x in s["lentos"]:
        ev.append({"t": linha.quando(x["de_km"]), "tipo": "lento", "titulo": x["frase"].split(" - ")[0],
                   "sub": "pode ser acidente ou blitz" if x["nivel"] == "parado" else ""})
    for p in s["postos"]:
        if p.get("nome"):
            aberto = "aberto 24 h" if p.get("h24") else (f"aberto até {p['ate']}" if p.get("ate") else "")
            extra = [aberto, f"~{p['litros']:g} L" if p.get("litros") else "",
                     f"+{p['desvio_min']} min fora da rota" if p.get("desvio_min") else ""]
            ev.append({"t": linha.quando(p["km"]), "tipo": "posto", "titulo": f"Abastece em {p['nome']} (km {p['km']})",
                       "sub": " · ".join(x for x in extra if x)})
        else:
            ev.append({"t": linha.quando(p["km"]), "tipo": "alerta", "titulo": f"Abastece até o km {p['km']}",
                       "sub": "não achei posto aberto nessa hora perto da rota - para no primeiro que vir"})
    if s.get("_escurece"):
        noite_fim = sum(n["ate_km"] - n["de_km"] for n in s["noite"] if n["ate_km"] >= s["total_km"] - 1)
        ev.append({"t": s["_escurece"], "tipo": "alerta", "titulo": "Escurece",
                   "sub": f"pôr do sol {_hhmm(s['_escurece'])}" + (f" · últimos {round(noite_fim)} km de noite" if noite_fim else "")})
    fim_sub = ""
    if not s["noite"] and s.get("por_do_sol"):
        fim_sub = f"antes de escurecer (pôr do sol {s['por_do_sol']})"
    ev.append({"t": linha.chegada(), "tipo": "fim", "titulo": f"Chega em {destino_nome}", "sub": fim_sub})
    ev.sort(key=lambda e: (e["t"], e["tipo"] == "fim"))
    return [{"hora": _hhmm(e["t"]), "tipo": e["tipo"], "titulo": e["titulo"][:90], "sub": (e["sub"] or "")[:120]} for e in ev]


# ---------------------------------------------------------------- plano inteiro

def _rotulo_dia(saida: datetime, agora: datetime) -> str:
    if saida <= agora + timedelta(minutes=10):
        return "agora"
    dif = (saida.date() - agora.date()).days
    if dif == 0:
        return "hoje"
    if dif == 1:
        return "amanhã"
    if dif < 7:
        return DIAS_SEMANA[saida.weekday()]
    return saida.strftime("%d/%m")


def _nome_curto(texto: str) -> str:
    return (texto or "").split(",")[0].strip()[:40] or texto


def planejar(conn, origem: str, destino: str, pedida: datetime | None, agora: datetime, *,
             origem_nome: str | None = None, tanque=None, preco_litro=None, maps=maps_client, clima=clima_rota) -> dict:
    """Monta o plano (sem gravar). -> {"erro"} ou o plano com as 3 saidas."""
    pedida = (pedida or agora).replace(second=0, microsecond=0)
    if pedida < agora - timedelta(minutes=30):
        return {"erro": "essa hora de saída já passou"}
    if pedida > agora + timedelta(days=16):
        return {"erro": "dá pra planejar até 16 dias antes (limite da previsão do tempo)"}
    futuro = pedida if pedida > agora + timedelta(minutes=2) else None
    base = maps.trajeto([origem, destino], partida=futuro)
    desenho = base.get("_desenho")
    if not desenho or len(desenho[0]) < 2:
        return {"erro": "não consegui desenhar a rota"}
    caminho = desenho[0]
    acum = _acumulado(caminho)
    total = float(base["distancia_total_km"])
    fator = total / acum[-1] if acum[-1] > 0 else 1.0
    km_pontos = [k * fator for k in acum]
    amostras = reduzir(caminho, km_pontos, total)
    traco = maps.traco_desenhavel(caminho, desenho[1], km=km_pontos)
    lugares = base["lugares"]
    destino_nome = _nome_curto(lugares[-1].get("nome") or lugares[-1].get("endereco") or destino)
    origem_nome = origem_nome or _nome_curto(lugares[0].get("nome") or lugares[0].get("endereco") or origem)

    # tanque e consumo
    v = combustivel.veiculo(conn)
    kml = combustivel.consumo(conn, "estrada")
    est = combustivel.estimativa_tanque(conn, agora)
    assumido = False
    litros_ini = combustivel.litros_do_texto(tanque, conn) if tanque not in (None, "") else None
    if litros_ini is None:
        if est:
            litros_ini = est["litros"]
        else:
            litros_ini, assumido = v["tanque_l"], True
    curta = total <= VIAGEM_CURTA_KM
    janelas = janelas_de_parada(total, litros_ini, v["tanque_l"], kml["km_l"], v["reserva_km"], curta)
    preco = combustivel._num(preco_litro)
    if not (preco and 0 < preco < 30):
        preco = combustivel.preco_litro_recente(conn, agora)

    # saidas: a pedida (ja calculada) + vizinhas
    horas = candidatas(pedida, agora, base["duracao_total_minutos"])
    rotas = {}
    for h in horas:
        if h == pedida:
            rotas[h] = base
            continue
        try:
            rotas[h] = maps.trajeto([origem, destino], partida=h if h > agora + timedelta(minutes=2) else None)
        except Exception:  # noqa: BLE001 - cota/rede: essa vizinha fica de fora
            continue
    horas = [h for h in horas if h in rotas]
    i_pedida = horas.index(pedida)

    # postos: uma busca por janela (na hora da saida pedida decide qual; as outras escolhem do mesmo lote)
    lotes = []
    for a, b in janelas:
        i0, i1 = _indice_do_km(km_pontos, a), _indice_do_km(km_pontos, b)
        trecho = caminho[max(0, i0 - 1): i1 + 2]
        try:
            achados = maps.postos_ao_longo(trecho)
        except Exception:  # noqa: BLE001 - cota/rede: parada sem nome de posto
            achados = []
        lotes.append(((a, b), preparar_postos(achados, caminho, acum, fator, (a, b))))

    saidas = []
    for h in horas:
        r = rotas[h]
        dur = float(r["duracao_total_minutos"])
        proprio = total / r["distancia_total_km"] if r.get("distancia_total_km") else 1.0
        linha = Linha(h, dur, total, [])
        paradas, tanque_l, pos = [], litros_ini, 0.0
        for (a, b), postos in lotes:
            escolhido = escolher_posto(postos, linha.quando, curta)
            if escolhido:
                p = {k: escolhido[k] for k in ("km", "nome", "lat", "lng", "desvio_min", "h24", "ate", "place_id")}
            else:
                p = {"km": round(b), "nome": None, "lat": None, "lng": None, "desvio_min": None, "h24": False,
                     "ate": None, "place_id": None}
            gasto = (p["km"] - pos) / kml["km_l"]
            p["litros"] = round(min(v["tanque_l"], max(0.0, v["tanque_l"] - (tanque_l - gasto))))
            tanque_l, pos = v["tanque_l"], p["km"]
            paradas.append(p)
            linha = Linha(h, dur, total, paradas)
        for p in paradas:
            p["passa_em"] = linha.quando(p["km"]).isoformat(timespec="minutes")
        tempo = None
        try:
            tempo = clima.tempo_na_rota(caminho, dur + sum(PARADA_MIN for _ in paradas), h, nomear=maps.nome_do_trecho)
        except Exception:  # noqa: BLE001 - sem rede: sem a parte do tempo
            tempo = None
        s = {"hora": _hhmm(h), "saida_em": h.isoformat(timespec="minutes"), "total_km": total,
             "duracao_min": round(dur), "transito_min": r.get("transito_total_min"),
             "lentos": _lentos(r.get("lentidao"), proprio), "chuva": _chuva(tempo, fator, linha),
             "postos": paradas}
        s["noite"], s["_escurece"], _ = _noite(linha, amostras)
        fim = amostras[-1]
        sol_fim = sol(fim[0], fim[1], linha.chegada().date())
        s["por_do_sol"] = _hhmm(sol_fim[1]) if sol_fim else None
        chegada = linha.chegada()
        s["chegada_em"] = chegada.isoformat(timespec="minutes")
        s["chega"] = _hhmm(chegada) + ("" if chegada.date() == h.date() else " (+1)")
        s["duracao_total_min"] = round((chegada - h).total_seconds() / 60)
        litros_total = total / kml["km_l"]
        s["litros"] = round(litros_total)
        s["custo"] = round(litros_total * preco) if preco else None
        txt_ini = ("tanque cheio" if litros_ini >= v["tanque_l"] - 0.5 else f"~{litros_ini:g} L no tanque") + \
            (" (contei cheio: sem abastecimento registrado)" if assumido else " (estimativa)" if not tanque else "")
        s["eventos"] = _eventos(s, origem_nome, destino_nome, txt_ini, linha)
        s["dica"] = dica(s)
        pontos_link = [{"pedido": origem, "nome": lugares[0].get("nome"), "endereco": lugares[0].get("endereco") or origem}]
        ids = [base.get("_place_ids", [None, None])[0]]
        for p in paradas:
            if p.get("lat") is not None:
                pontos_link.append({"nome": "", "endereco": f"{p['lat']},{p['lng']}"})
                ids.append(p.get("place_id"))
        pontos_link.append(lugares[-1])
        ids.append((base.get("_place_ids") or [None, None])[-1])
        s["maps_url"] = maps.link_rota(pontos_link, ids)
        primeiro = next((p for p in paradas if p.get("lat") is not None), None)
        s["waze_url"] = maps.link_waze([primeiro["lat"], primeiro["lng"]]) if primeiro else base.get("_waze")
        s["waze_para"] = primeiro["nome"] if primeiro else None
        saidas.append(s)

    melhor, frase = frase_melhor(saidas, i_pedida)
    for s in saidas:
        s.pop("_escurece", None)
    pedida_s = saidas[i_pedida]
    aviso_noite = None
    noite_km = sum(n["ate_km"] - n["de_km"] for n in pedida_s["noite"])
    if noite_km >= 10:
        aviso_noite = f"{round(noite_km)} km de noite" + (f" (pôr do sol {pedida_s['por_do_sol']})" if pedida_s.get("por_do_sol") else "")
    texto_tanque = combustivel.texto_tanque(est if not tanque else None, kml, v)
    return {
        "destino": destino_nome,
        "origem": origem_nome,
        "quando": _rotulo_dia(pedida, agora),
        "total_km": round(total),
        "traco": traco,
        "pontos_km": amostras,
        "saidas": saidas,
        "escolhida": i_pedida,
        "pedida": i_pedida,
        "melhor": melhor,
        "frase_melhor": frase,
        "aviso_noite": aviso_noite,
        "curta": curta,
        "tanque": {
            "litros": round(litros_ini, 1), "fracao": round(min(1.0, litros_ini / v["tanque_l"]), 2),
            "tanque_l": v["tanque_l"], "conferido": bool(v["tanque_conferido"]), "assumido": assumido,
            "estimativa": True, "km_l": kml["km_l"], "fonte_consumo": kml["fonte"], "reserva_km": v["reserva_km"],
            "autonomia_km": round(litros_ini * kml["km_l"]), "texto": texto_tanque,
            "informado": tanque not in (None, ""),
        },
        "preco_litro": preco,
        "lentidao_resumo": maps_client.resumo_transito({"transito_min": pedida_s.get("transito_min"),
                                                        "lentidao": base.get("lentidao") or []}),
    }


# ---------------------------------------------------------------- banco

def salvar(conn, plano: dict) -> int:
    """Grava e encerra as outras viagens abertas que se sobrepoem (planejou de novo = vale a nova)."""
    s = plano["saidas"][plano["escolhida"]]
    for r in conn.execute("SELECT id, saida_em, chegada_em FROM viagens_planejadas WHERE encerrada_em IS NULL").fetchall():
        try:
            a, b = datetime.fromisoformat(r["saida_em"]), datetime.fromisoformat(r["chegada_em"])
        except ValueError:
            continue
        nova_a, nova_b = datetime.fromisoformat(s["saida_em"]), datetime.fromisoformat(s["chegada_em"])
        if a - ANTES_SAIDA <= nova_b + DEPOIS_CHEGADA and nova_a - ANTES_SAIDA <= b + DEPOIS_CHEGADA:
            encerrar(conn, r["id"])
    cur = conn.execute(
        "INSERT INTO viagens_planejadas (destino, saida_em, chegada_em, plano_json) VALUES (?, ?, ?, ?)",
        (plano["destino"], s["saida_em"], s["chegada_em"], json.dumps(plano, ensure_ascii=False)),
    )
    conn.commit()
    return cur.lastrowid


def _ler(conn, id_: int) -> tuple[dict, dict] | None:
    try:
        row = conn.execute("SELECT * FROM viagens_planejadas WHERE id = ?", (id_,)).fetchone()
    except sqlite3.Error:
        return None
    if not row:
        return None
    try:
        plano = json.loads(row["plano_json"])
    except (TypeError, ValueError):
        return None
    if not isinstance(plano, dict) or not plano.get("saidas"):
        return None
    return dict(row), plano


def escolher_saida(conn, id_: int, indice: int) -> dict | None:
    """O chip de outra saida no card: so troca qual vale (nada de API). -> {saida_em, chegada_em}."""
    lido = _ler(conn, id_)
    if not lido or isinstance(indice, bool) or not isinstance(indice, int):
        return None
    row, plano = lido
    if not 0 <= indice < len(plano["saidas"]) or row["encerrada_em"]:
        return None
    plano["escolhida"] = indice
    s = plano["saidas"][indice]
    conn.execute("UPDATE viagens_planejadas SET saida_em = ?, chegada_em = ?, plano_json = ? WHERE id = ?",
                 (s["saida_em"], s["chegada_em"], json.dumps(plano, ensure_ascii=False), id_))
    conn.commit()
    return {"saida_em": s["saida_em"], "chegada_em": s["chegada_em"]}


def encerrar(conn, id) -> bool:  # noqa: A002 - nome do contrato
    """Fim da viagem (chegou, cancelou). True se encerrou agora."""
    cur = conn.execute("UPDATE viagens_planejadas SET encerrada_em = ? WHERE id = ? AND encerrada_em IS NULL",
                       (datetime.now().isoformat(timespec="seconds"), id))
    conn.commit()
    # posicoes da viagem acompanhada (frente 3, GPS do iPhone) somem junto com o fim da viagem
    try:
        import viagem_acompanhada

        viagem_acompanhada.apagar_viagem(conn, id)
    except Exception:  # noqa: BLE001 - modulo ausente/erro nao impede encerrar
        pass
    return cur.rowcount == 1


def _contrato(row: dict, plano: dict) -> dict:
    s = plano["saidas"][plano.get("escolhida", 0)]
    return {
        "id": row["id"],
        "destino": plano.get("destino") or row["destino"],
        "saida_em": s["saida_em"],
        "chegada_em": s["chegada_em"],
        "total_km": plano.get("total_km"),
        "traco": plano.get("traco"),
        "pontos_km": plano.get("pontos_km") or [],
        "postos": [{"km": p["km"], "nome": p["nome"], "lat": p["lat"], "lng": p["lng"], "passa_em": p.get("passa_em")}
                   for p in s.get("postos") or [] if p.get("lat") is not None],
        "chuva": [{"de_km": c["de_km"], "ate_km": c["ate_km"], "tipo": c["tipo"], "inicio_em": c.get("inicio_em")}
                  for c in s.get("chuva") or []],
    }


def plano_ativo(conn, agora: datetime) -> dict | None:
    """A viagem nao encerrada com saida - 2 h <= agora <= chegada + 2 h (a de saida mais perto, se tiver 2)."""
    try:
        rows = conn.execute("SELECT * FROM viagens_planejadas WHERE encerrada_em IS NULL").fetchall()
    except sqlite3.Error:
        return None
    if agora.tzinfo is not None:
        agora = agora.replace(tzinfo=None)
    achadas = []
    for r in rows:
        try:
            a, b = datetime.fromisoformat(r["saida_em"]), datetime.fromisoformat(r["chegada_em"])
        except ValueError:
            continue
        if a - ANTES_SAIDA <= agora <= b + DEPOIS_CHEGADA:
            achadas.append((abs((a - agora).total_seconds()), r))
    for _, r in sorted(achadas, key=lambda x: x[0]):
        lido = _ler(conn, r["id"])
        if lido:
            return _contrato(*lido)
    return None


# ---------------------------------------------------------------- card

def card(conn, id_: int) -> dict | None:
    """Card `viagem`: o card de rota (mapa) + postos, chuva/lento/noite por saida, 3 saidas, linha do tempo,
    tanque (estimativa), gasolina/custo/chegada, Maps/Waze com as paradas."""
    import cards

    lido = _ler(conn, id_)
    if not lido:
        return None
    row, plano = lido
    data = {k: plano.get(k) for k in ("destino", "origem", "quando", "total_km", "traco", "saidas", "escolhida",
                                     "pedida", "melhor", "frase_melhor", "aviso_noite", "tanque", "preco_litro", "curta")}
    data["id"] = row["id"]
    data["encerrada"] = bool(row["encerrada_em"])
    data["custos"] = []
    for s in data["saidas"] or []:
        data["custos"].append(s.pop("custo", None))  # dinheiro no topo: o modo visitante tira (CAMPOS_SENSIVEIS)
        for p in s.get("postos") or []:
            p.pop("place_id", None)
    s = (data["saidas"] or [{}])[data.get("escolhida") or 0]
    acoes = []
    if isinstance(s.get("maps_url"), str) and s["maps_url"].startswith("https://www.google.com/maps/"):
        acoes.append({"tipo": "abrir_link", "rotulo": "Abrir no Maps", "url": s["maps_url"]})
    waze = cards.acao_waze(s.get("waze_url"), s.get("waze_para"))
    if waze:
        acoes.append(waze)
    return cards.novo_card("viagem", data, acoes)


# ---------------------------------------------------------------- ferramenta do chat

def executar(conn, entrada: dict, *, local_gps: dict | None = None, agora: datetime | None = None,
             maps=maps_client, clima=clima_rota) -> dict:
    """planejar_viagem: resolve origem (casa/GPS/apelido), planeja, salva e devolve o resumo pra IA."""
    import vida_assistente

    agora = agora or datetime.now()
    destino = str(entrada.get("destino") or "").strip()[:200]
    if not destino:
        return {"erro": "preciso do destino"}
    if not maps.configurado():
        return {"erro": "Google Maps nao configurado (falta GOOGLE_MAPS_API_KEY no .env) - diga isso ao Alex, nao estime"}
    casa = os.environ.get("ENDERECO_CASA", "").strip()
    origem = str(entrada.get("origem") or "").strip()[:200]
    origem_nome = None
    if not origem or origem.lower() in ORIGEM_AQUI:
        if origem and local_gps:
            origem, origem_nome = f"{local_gps['lat']},{local_gps['lon']}", "onde tu está"
        elif casa:
            origem, origem_nome = casa, "casa"
        elif local_gps:
            origem, origem_nome = f"{local_gps['lat']},{local_gps['lon']}", "onde tu está"
        else:
            return {"erro": "preciso saber de onde voce sai"}
    elif origem.lower() in ORIGEM_CASA:
        if not casa:
            return {"erro": "endereco de casa nao configurado - pergunte de onde ele sai"}
        origem, origem_nome = casa, "casa"
    else:
        origem = vida_assistente.resolver_lugar(conn, origem)
    destino_resolvido = casa if destino.lower() in ORIGEM_CASA and casa else vida_assistente.resolver_lugar(conn, destino)
    pedida = clima_rota.interpretar_saida(entrada.get("saida"), agora) if entrada.get("saida") else None
    if entrada.get("saida") and pedida is None:
        return {"erro": "nao entendi a hora de saida - use 'HH:MM' ou 'AAAA-MM-DD HH:MM'"}
    try:
        plano = planejar(conn, origem, destino_resolvido, pedida, agora, origem_nome=origem_nome,
                         tanque=entrada.get("tanque"), preco_litro=entrada.get("preco_litro"), maps=maps, clima=clima)
    except maps_client.CotaEsgotada:
        return {"erro": "a cota gratis do Google Maps do mes acabou - nao da pra planejar agora"}
    except Exception:  # noqa: BLE001 - rede / sem rota
        return {"erro": "nao consegui calcular a rota agora"}
    if plano.get("erro"):
        return plano
    id_ = salvar(conn, plano)
    s = plano["saidas"][plano["escolhida"]]
    m = plano["saidas"][plano["melhor"]]
    return {
        "destino": plano["destino"],
        "distancia_km": plano["total_km"],
        "saida": s["hora"],
        "chegada": s["chega"],
        "tempo_total_min": s["duracao_total_min"],
        "transito": plano["lentidao_resumo"],
        "paradas_abastecer": [
            {"km": p["km"], "posto": p["nome"], "passa_as": p["passa_em"][11:16],
             "aberto": "24 h" if p.get("h24") else (f"ate {p['ate']}" if p.get("ate") else None)}
            if p.get("nome") else {"km": p["km"], "posto": None, "obs": "nao achei posto aberto perto da rota nessa hora"}
            for p in s["postos"]
        ],
        "chuva_no_caminho": [c["frase"] for c in s["chuva"]][:4] or "tempo firme (ou sem previsao pra essa hora)",
        "noite": plano["aviso_noite"],
        "melhor_saida": plano["frase_melhor"] or None,
        "melhor_horario": m["hora"],
        "tanque": plano["tanque"]["texto"],
        "litros_estimados": s["litros"],
        "custo_estimado": s["custo"],
        "obs": "km, tempo e transito do Google; chuva do Open-Meteo; tanque e litros sao ESTIMATIVA - diga isso. "
               "O card ja mostra mapa, saidas e postos: nao repita tudo, so o essencial.",
        "_efeito": {"entidade": "viagem_planejada", "id": id_},
    }
