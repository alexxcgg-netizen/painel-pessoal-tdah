"""Tempo AO LONGO da rota (pedido do Alex, 2026-10-21): numa viagem de 200 km chove num trecho e
no outro nao; subindo a serra pra Curitiba pega neblina. Em vez de olhar so a cidade de destino,
pega pontos do caminho real (polyline do Google) a cada ~20 km, calcula a HORA em que ele passa
em cada um e pergunta ao Open-Meteo (gratis, sem chave) o tempo daquela hora naquele ponto - tudo
numa chamada so (a API aceita varias coordenadas).

Resultado: trechos "do km X ao km Y" com o que vai pegar (granizo, trovoada, neblina, chuva forte,
chuva, vento forte). Nunca inventa: so classifica o que a API devolveu. Sem rede = None e o card
da rota sai sem a parte do tempo."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

ROTA_MINIMA_KM = 25  # trajeto curto: o consultar_clima da cidade ja diz tudo
PASSO_KM = 20
MAX_AMOSTRAS = 12

CHUVA_PCT = 50
CHUVA_FORTE_MM = 4.0  # mm na hora
VISIBILIDADE_NEBLINA_M = 1000
RAJADA_FORTE_KMH = 60
SERRA_M = 600  # acima disso o trecho ganha "na serra"

# do pior pro mais leve: num ponto com chuva e neblina, vale a neblina (e o que mais pesa dirigindo)
ORDEM = ("granizo", "trovoada", "neblina", "chuva_forte", "chuva", "vento", "ok")
ROTULO = {
    "granizo": "granizo", "trovoada": "trovoada", "neblina": "neblina", "chuva_forte": "chuva forte",
    "chuva": "chuva", "vento": "vento forte", "ok": "tempo firme",
}
_CODIGOS_CHUVA = set(range(51, 68)) | set(range(80, 83))


def _km(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(h)))


def amostrar(pontos: list, passo_km: float = PASSO_KM, maximo: int = MAX_AMOSTRAS) -> list[dict]:
    """Pontos do caminho a cada ~passo_km (sempre com o inicio e o fim), cada um com o km
    acumulado e o indice no caminho. Rota longa demais: o passo cresce pra caber em `maximo`."""
    if len(pontos) < 2:
        return []
    acumulado = [0.0]
    for a, b in zip(pontos, pontos[1:]):
        acumulado.append(acumulado[-1] + _km(a, b))
    total = acumulado[-1]
    if total <= 0:
        return []
    passo = max(passo_km, total / (maximo - 1))
    alvos = [min(total, k * passo) for k in range(int(total // passo) + 1)]
    if total - alvos[-1] > passo * 0.35:
        alvos.append(total)
    else:
        alvos[-1] = total
    amostras, j = [], 0
    for alvo in alvos:
        while j < len(acumulado) - 1 and acumulado[j] < alvo:
            j += 1
        amostras.append({"i": j, "lat": pontos[j][0], "lon": pontos[j][1], "km": round(acumulado[j], 1)})
    return amostras


def classificar(hora: dict) -> str:
    """Uma hora de previsao num ponto -> o pior tipo (ver ORDEM)."""
    codigo = hora.get("codigo")
    mm = hora.get("mm") or 0
    pct = hora.get("chuva_pct") or 0
    vis = hora.get("visibilidade_m")
    rajada = hora.get("rajada_kmh") or 0
    if codigo in (96, 99):
        return "granizo"
    if codigo == 95:
        return "trovoada"
    if codigo in (45, 48) or (isinstance(vis, (int, float)) and vis < VISIBILIDADE_NEBLINA_M):
        return "neblina"
    if mm >= CHUVA_FORTE_MM or codigo in (65, 82):
        return "chuva_forte"
    if pct >= CHUVA_PCT or (codigo in _CODIGOS_CHUVA and mm > 0):
        return "chuva"
    if rajada >= RAJADA_FORTE_KMH:
        return "vento"
    return "ok"


def juntar_trechos(amostras: list[dict], total_km: float) -> list[dict]:
    """Amostras ja com `tipo`/`hora` -> trechos continuos do mesmo tipo. Cada amostra "vale" da
    metade do caminho ate a anterior ate a metade ate a seguinte."""
    trechos = []
    for n, a in enumerate(amostras):
        de = 0.0 if n == 0 else (amostras[n - 1]["km"] + a["km"]) / 2
        ate = total_km if n == len(amostras) - 1 else (a["km"] + amostras[n + 1]["km"]) / 2
        # mesmos limites em indice do caminho (pro mapa pintar o trecho)
        i0 = 0 if n == 0 else (amostras[n - 1]["i"] + a["i"]) // 2
        i1 = a["i"] if n == len(amostras) - 1 else (a["i"] + amostras[n + 1]["i"]) // 2
        if trechos and trechos[-1]["tipo"] == a["tipo"]:
            t = trechos[-1]
            t["ate_km"] = ate
            t["i1"] = i1
            t["hora_fim"] = a["hora"]
            t["_amostras"].append(a)
        else:
            trechos.append({"tipo": a["tipo"], "de_km": de, "ate_km": ate, "i0": i0, "i1": i1,
                            "hora_ini": a["hora"], "hora_fim": a["hora"], "_amostras": [a]})
    for t in trechos:
        amos = t.pop("_amostras")
        t["de_km"] = round(t["de_km"])
        t["ate_km"] = round(t["ate_km"])
        t["chuva_pct"] = max((x.get("chuva_pct") or 0) for x in amos)
        vis = [x["visibilidade_m"] for x in amos if isinstance(x.get("visibilidade_m"), (int, float))]
        t["visibilidade_m"] = round(min(vis)) if vis else None
        t["rajada_kmh"] = round(max((x.get("rajada_kmh") or 0) for x in amos))
        alt = [x["altitude_m"] for x in amos if isinstance(x.get("altitude_m"), (int, float))]
        t["serra"] = bool(alt) and max(alt) >= SERRA_M
        t["meio"] = amos[len(amos) // 2]
    return trechos


def _hora_txt(hhmm: str) -> str:
    h, m = hhmm.split(":")
    return f"{int(h)}h" if m == "00" else f"{int(h)}h{m}"


def frase(t: dict) -> str:
    """'Neblina na serra (BR-277, São José dos Pinhais) do km 150 ao 175, por volta das 9h -
    visibilidade 300 m'."""
    partes = [ROTULO[t["tipo"]].capitalize()]
    if t.get("serra"):
        partes[0] += " na serra"
    if t.get("nome"):
        partes[0] += f" ({t['nome']})"
    partes[0] += f" do km {t['de_km']} ao {t['ate_km']}"
    hi, hf = _hora_txt(t["hora_ini"]), _hora_txt(t["hora_fim"])
    partes.append(f"por volta das {hi}" if hi == hf else f"entre {hi} e {hf}")
    extra = ""
    if t["tipo"] == "neblina" and t.get("visibilidade_m") is not None:
        extra = f" - visibilidade {t['visibilidade_m']} m"
    elif t["tipo"] in ("chuva", "chuva_forte", "trovoada", "granizo") and t.get("chuva_pct"):
        extra = f" - {t['chuva_pct']}% de chance"
    elif t["tipo"] == "vento" and t.get("rajada_kmh"):
        extra = f" - rajadas de {t['rajada_kmh']} km/h"
    return ", ".join(partes) + extra


def resumo(trechos: list[dict]) -> str:
    ruins = [t for t in trechos if t["tipo"] != "ok"]
    if not ruins:
        return "Tempo firme no caminho todo."
    texto = "; ".join(frase(t) for t in ruins[:4])
    if any(t["tipo"] == "ok" for t in trechos):
        texto += ". O resto do caminho, tempo firme."
    return texto + ("" if texto.endswith(".") else ".")


def interpretar_saida(texto, agora: datetime | None = None) -> datetime | None:
    """'07:30' (hoje; se ja passou faz mais de 1 h, amanha) ou 'AAAA-MM-DD HH:MM' / com 'T'.
    Qualquer outra coisa = None (sai agora)."""
    agora = agora or datetime.now()
    texto = str(texto or "").strip().replace("T", " ")
    try:
        if len(texto) == 5:
            h, m = int(texto[:2]), int(texto[3:])
            quando = agora.replace(hour=h, minute=m, second=0, microsecond=0)
            return quando + timedelta(days=1) if quando < agora - timedelta(hours=1) else quando
        if len(texto) >= 16:
            return datetime.strptime(texto[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return None


def _buscar(amostras: list[dict], dias: int) -> list[dict] | None:
    """Uma chamada pra todas as amostras. Devolve, por amostra, a serie horaria + altitude."""
    try:
        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": ",".join(f"{a['lat']:.4f}" for a in amostras),
                "longitude": ",".join(f"{a['lon']:.4f}" for a in amostras),
                "hourly": "precipitation_probability,precipitation,weathercode,visibility,wind_gusts_10m",
                "timezone": "America/Sao_Paulo",
                "forecast_days": dias,
            },
            timeout=10,
        )
        resp.raise_for_status()
        dados = resp.json()
    except (requests.RequestException, ValueError):
        return None
    if isinstance(dados, dict):
        dados = [dados]
    if not isinstance(dados, list) or len(dados) != len(amostras):
        return None
    return dados


def _hora_do_ponto(local: dict, quando: datetime) -> dict | None:
    try:
        h = local["hourly"]
        alvo = quando.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")
        i = h["time"].index(alvo)
        return {
            "chuva_pct": h["precipitation_probability"][i],
            "mm": h["precipitation"][i],
            "codigo": h["weathercode"][i],
            "visibilidade_m": h["visibility"][i],
            "rajada_kmh": h["wind_gusts_10m"][i],
            "altitude_m": local.get("elevation"),
        }
    except (KeyError, ValueError, IndexError, TypeError):
        return None


def tempo_na_rota(pontos: list, duracao_min: float, partida: datetime | None = None,
                  nomear=None) -> dict | None:
    """Caminho [(lat, lon)...] + duracao total + hora de saida (padrao: agora) -> trechos com o
    tempo de cada um. `nomear(lat, lon)` (opcional) da nome aos trechos ruins (maximo 3).
    None = rota curta, fora da janela de previsao ou sem rede."""
    partida = partida or datetime.now()
    amostras = amostrar(pontos)
    if len(amostras) < 2 or amostras[-1]["km"] < ROTA_MINIMA_KM:
        return None
    total = amostras[-1]["km"]
    chegada = partida + timedelta(minutes=duracao_min or 0)
    dias = (chegada.date() - datetime.now().date()).days + 1
    if dias > 16 or chegada < datetime.now() - timedelta(hours=1):
        return None
    locais = _buscar(amostras, max(1, dias))
    if locais is None:
        return None
    for a, local in zip(amostras, locais):
        quando = partida + timedelta(minutes=(duracao_min or 0) * a["km"] / total)
        hora = _hora_do_ponto(local, quando)
        if hora is None:
            return None
        a.update(hora)
        a["hora"] = quando.strftime("%H:%M")
        a["tipo"] = classificar(hora)
    trechos = juntar_trechos(amostras, total)
    if nomear:
        for t in [t for t in trechos if t["tipo"] != "ok"][:3]:
            try:
                t["nome"] = nomear(t["meio"]["lat"], t["meio"]["lon"])
            except Exception:
                t["nome"] = None
    for t in trechos:
        t.pop("meio", None)
    return {"total_km": round(total), "saida": partida.strftime("%H:%M"), "trechos": trechos,
            "resumo": resumo(trechos)}
