"""Previsao do tempo generica (chuva/temperatura) por cidade, via Open-Meteo -
gratuito, sem chave, sem cadastro (https://open-meteo.com). Usado tanto pra
avisar sobre um voo agendado num destino especifico ("vai chover em Blumenau
nesse dia") quanto pra previsao do dia a dia na cidade padrao (CIDADE_PADRAO
no .env) - "vai chover, que horas". Nunca decide nada sozinho - so busca o
dado bruto e resume em Python puro, quem interpreta e sempre o Alex.

Erro de rede ou cidade nao encontrada nunca derruba quem chamou - devolve
None e quem usa decide o que fazer (normalmente: so nao mostra o aviso)."""

from datetime import datetime

import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

_cache_geocodificacao: dict[str, dict | None] = {}

# codigos WMO (weathercode) que indicam chuva/tempestade - usado so pra
# decidir se vale destacar o dia como "atencao", a temperatura/percentual
# real sempre vem da API, nunca inventado aqui
_CODIGOS_CHUVA = set(range(51, 68)) | set(range(80, 100))

LIMITE_ALERTA_CHUVA = 50


def geocodificar_cidade(nome: str) -> dict | None:
    nome = (nome or "").strip()
    if not nome:
        return None
    if nome in _cache_geocodificacao:
        return _cache_geocodificacao[nome]

    resultado = None
    try:
        resp = requests.get(
            GEOCODING_URL,
            params={"name": nome, "count": 1, "language": "pt", "format": "json"},
            timeout=8,
        )
        resp.raise_for_status()
        achados = resp.json().get("results") or []
        if achados:
            r = achados[0]
            resultado = {"lat": r["latitude"], "lon": r["longitude"], "nome": r["name"]}
    except (requests.RequestException, ValueError, KeyError):
        resultado = None

    _cache_geocodificacao[nome] = resultado
    return resultado


def previsao_para_data(lat: float, lon: float, data_iso: str) -> dict | None:
    """Previsao diaria (chuva/temperatura) pra uma data especifica - so
    funciona pra datas dentro da janela de previsao (Open-Meteo cobre ate
    16 dias a frente); fora disso ou em caso de erro, devolve None."""
    try:
        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "America/Sao_Paulo",
                "forecast_days": 16,
            },
            timeout=8,
        )
        resp.raise_for_status()
        dados = resp.json().get("daily") or {}
        datas = dados.get("time") or []
        if data_iso not in datas:
            return None
        i = datas.index(data_iso)
        codigo = dados["weathercode"][i]
        return {
            "chuva_pct": dados["precipitation_probability_max"][i],
            "temp_max": dados["temperature_2m_max"][i],
            "temp_min": dados["temperature_2m_min"][i],
            "codigo": codigo,
            "alerta_chuva": codigo in _CODIGOS_CHUVA,
        }
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


def previsao_para_cidade_e_data(cidade: str, data_iso: str) -> dict | None:
    local = geocodificar_cidade(cidade)
    if not local:
        return None
    previsao = previsao_para_data(local["lat"], local["lon"], data_iso)
    if not previsao:
        return None
    return {**previsao, "cidade": local["nome"], "lat": local["lat"], "lon": local["lon"]}


def previsao_proximos_dias(lat: float, lon: float, dias: int = 7) -> list[dict] | None:
    """Previsao diaria dos proximos `dias` dias (incluindo hoje) numa chamada
    so - usado pra achar o melhor dia pra uma tarefa que depende do tempo
    (ex: "limpar o quarto se nao chover"), sem precisar de uma chamada por
    dia. None so em caso de erro de rede/resposta - `dias` e limitado a 16
    (janela maxima do Open-Meteo)."""
    dias = min(max(dias, 1), 16)
    try:
        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "America/Sao_Paulo",
                "forecast_days": dias,
            },
            timeout=8,
        )
        resp.raise_for_status()
        dados = resp.json().get("daily") or {}
        datas = dados.get("time") or []
        previsoes = []
        for i, data_iso in enumerate(datas):
            codigo = dados["weathercode"][i]
            previsoes.append(
                {
                    "data": data_iso,
                    "chuva_pct": dados["precipitation_probability_max"][i],
                    "temp_max": dados["temperature_2m_max"][i],
                    "temp_min": dados["temperature_2m_min"][i],
                    "codigo": codigo,
                    "alerta_chuva": codigo in _CODIGOS_CHUVA,
                }
            )
        return previsoes
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


def melhor_dia_sem_chuva(previsoes: list[dict], limite_pct: int = LIMITE_ALERTA_CHUVA) -> dict | None:
    """Entre os dias de previsao (em ordem cronologica), acha o primeiro cuja
    chance de chuva fica abaixo do limite - a primeira "janela boa" pra uma
    atividade ao ar livre, nao necessariamente o dia com a MENOR chuva de
    todos (prefere o mais proximo que ja serve, pra nao empurrar demais).
    None se nenhum dia bater o limite."""
    for p in previsoes:
        if p["chuva_pct"] < limite_pct:
            return p
    return None


CHUVA_QUASE_CERTA_PCT = 80
CHUVA_MM_CONTA = 0.3  # menos que isso na hora e respingo


def previsao_horaria(lat: float, lon: float, dias: int = 3) -> list[dict] | None:
    """Hora a hora dos proximos `dias` dias: [{'quando': 'AAAA-MM-DDTHH:MM', 'chuva_pct', 'mm',
    'codigo', 'temp'}]. None em erro de rede/resposta. `temp` (04/11/2026, card de saida hora a
    hora em cards.py) e None se a resposta nao trouxer temperatura."""
    try:
        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "precipitation_probability,precipitation,weathercode,temperature_2m",
                "timezone": "America/Sao_Paulo",
                "forecast_days": min(max(dias, 1), 16),
            },
            timeout=8,
        )
        resp.raise_for_status()
        h = resp.json()["hourly"]
        temps = h.get("temperature_2m") or []
        return [
            {"quando": t, "chuva_pct": h["precipitation_probability"][i] or 0,
             "mm": h["precipitation"][i] or 0, "codigo": h["weathercode"][i],
             "temp": temps[i] if i < len(temps) else None}
            for i, t in enumerate(h["time"])
        ]
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        return None


def analisar_janela(horas: list[dict], inicio: datetime, janela_h: int,
                    limite_pct: int = LIMITE_ALERTA_CHUVA) -> dict:
    """Pedido do Alex (2026-10-21): "vou lavar o carro as 14" - chove nas `janela_h` horas a
    partir do inicio (a atividade + o tempo que ela precisa ficar seca)? Devolve a PRIMEIRA hora
    com chuva (chance >= limite ou mm que conta), em quantas horas depois do inicio, e quao certo
    e ('quase_certa' >= 80% e com mm previsto; senao 'provavel'). Funcao pura."""
    ini = inicio.replace(minute=0, second=0, microsecond=0)
    alvo = [h for h in horas if 0 <= (datetime.fromisoformat(h["quando"]) - ini).total_seconds() / 3600 < janela_h]
    if not alvo:
        return {"coberto": False}
    pior = max(alvo, key=lambda h: (h["chuva_pct"], h["mm"]))
    for h in alvo:
        if h["chuva_pct"] >= limite_pct or h["mm"] >= CHUVA_MM_CONTA:
            em = round((datetime.fromisoformat(h["quando"]) - ini).total_seconds() / 3600)
            mm_total = round(sum(x["mm"] for x in alvo if x["quando"] >= h["quando"]), 1)
            certeza = "quase_certa" if h["chuva_pct"] >= CHUVA_QUASE_CERTA_PCT and h["mm"] > 0 else "provavel"
            return {
                "coberto": True, "chove": True, "quando": h["quando"], "em_horas": em,
                "chuva_pct": h["chuva_pct"], "mm_na_janela": mm_total, "certeza": certeza,
                "condicao": descricao_codigo(h["codigo"]),
            }
    return {"coberto": True, "chove": False, "pior_pct": pior["chuva_pct"]}


def dia_seco_pra(previsoes: list[dict], a_partir: str, dias_secos: int = 1,
                 limite_pct: int = LIMITE_ALERTA_CHUVA) -> dict | None:
    """Primeiro dia (>= a_partir, AAAA-MM-DD) que fica abaixo do limite e cujos `dias_secos - 1`
    dias seguintes tambem - lavar o carro e ele amanhecer limpo. None se nenhum serve."""
    lista = [p for p in previsoes if p["data"] >= a_partir]
    for i, p in enumerate(lista):
        seguidos = lista[i:i + dias_secos]
        if len(seguidos) == dias_secos and all(x["chuva_pct"] < limite_pct for x in seguidos):
            return p
    return None


def previsao_na_hora(lat: float, lon: float, data_iso: str, hora: str) -> dict | None:
    """Temperatura e chance de chuva previstas pra UMA hora de um dia (ate 16 dias a frente) -
    card do date/balada (2026-10-14): "14 graus a noite, leva jaqueta". None fora da janela ou
    se a rede falhar."""
    try:
        h = int(str(hora)[:2])
        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "precipitation_probability,temperature_2m,weathercode",
                "timezone": "America/Sao_Paulo",
                "start_date": data_iso,
                "end_date": data_iso,
            },
            timeout=8,
        )
        resp.raise_for_status()
        dados = resp.json().get("hourly") or {}
        i = next(i for i, t in enumerate(dados["time"]) if int(t[11:13]) == h)
        return {
            "temp": dados["temperature_2m"][i],
            "chuva_pct": dados["precipitation_probability"][i],
            "codigo": dados["weathercode"][i],
        }
    except (requests.RequestException, ValueError, KeyError, IndexError, StopIteration, TypeError):
        return None


def previsao_horaria_hoje(lat: float, lon: float) -> list[dict] | None:
    """Previsao hora a hora do dia de hoje (fuso America/Sao_Paulo) - lista
    de {'hora': 0-23, 'chuva_pct': int, 'temp': float, 'codigo': int}."""
    try:
        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "precipitation_probability,temperature_2m,weathercode",
                "timezone": "America/Sao_Paulo",
                "forecast_days": 1,
            },
            timeout=8,
        )
        resp.raise_for_status()
        dados = resp.json().get("hourly") or {}
        tempos = dados["time"]
        chuvas = dados["precipitation_probability"]
        temps = dados["temperature_2m"]
        codigos = dados["weathercode"]
        return [
            {"hora": int(t[11:13]), "chuva_pct": chuvas[i], "temp": temps[i], "codigo": codigos[i]}
            for i, t in enumerate(tempos)
        ]
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


def resumo_chuva_do_dia(horas: list[dict], hora_atual: int, limite_pct: int = LIMITE_ALERTA_CHUVA) -> dict:
    """Acha a janela continua de horas (a partir de agora) com maior risco de
    chuva do resto do dia - pura funcao, sem rede, facil de testar isolada.
    'horas': lista de {'hora': 0-23, 'chuva_pct': int} de UM dia (pode vir
    fora de ordem ou com horas ja passadas - so as de agora em diante contam)."""
    futuras = sorted((h for h in horas if h["hora"] >= hora_atual), key=lambda h: h["hora"])
    if not futuras:
        return {"alerta": False, "chovendo_agora": False, "texto": "Sem mais previsão pra hoje."}

    chovendo_agora = futuras[0]["hora"] == hora_atual and futuras[0]["chuva_pct"] >= limite_pct

    pico_idx = max(range(len(futuras)), key=lambda i: futuras[i]["chuva_pct"])
    pico = futuras[pico_idx]
    if pico["chuva_pct"] < limite_pct:
        return {
            "alerta": False,
            "chovendo_agora": False,
            "chuva_pct_max": pico["chuva_pct"],
            "texto": "Sem risco significativo de chuva no resto do dia.",
        }

    # expande a partir do pico enquanto a hora seguinte/anterior continuar
    # consecutiva E acima do limite - assim pega so o bloco continuo em
    # volta do pico, nao qualquer hora esparsa com chuva em outro momento
    inicio = pico_idx
    while (
        inicio > 0
        and futuras[inicio - 1]["chuva_pct"] >= limite_pct
        and futuras[inicio - 1]["hora"] == futuras[inicio]["hora"] - 1
    ):
        inicio -= 1
    fim = pico_idx
    while (
        fim < len(futuras) - 1
        and futuras[fim + 1]["chuva_pct"] >= limite_pct
        and futuras[fim + 1]["hora"] == futuras[fim]["hora"] + 1
    ):
        fim += 1

    hora_inicio = futuras[inicio]["hora"]
    hora_fim = futuras[fim]["hora"] + 1
    fim_txt = "o fim do dia" if hora_fim >= 24 else f"{hora_fim}h"
    return {
        "alerta": True,
        "chovendo_agora": chovendo_agora,
        "hora_inicio": hora_inicio,
        "hora_fim": hora_fim,
        "chuva_pct_max": pico["chuva_pct"],
        "texto": f"Risco de chuva entre {hora_inicio}h e {fim_txt} (até {pico['chuva_pct']}% de chance).",
    }


def resumo_chuva_hoje_para_cidade(cidade: str) -> dict | None:
    local = geocodificar_cidade(cidade)
    if not local:
        return None
    horas = previsao_horaria_hoje(local["lat"], local["lon"])
    if not horas:
        return None
    resumo = resumo_chuva_do_dia(horas, datetime.now().hour)
    return {**resumo, "cidade": local["nome"]}


# descricao curta dos codigos WMO mais comuns - so traduz o codigo que a API
# devolveu, nunca deduz nada
_DESCRICAO_WMO = {
    0: "céu limpo", 1: "quase limpo", 2: "parcialmente nublado", 3: "nublado",
    45: "neblina", 48: "neblina", 51: "garoa fraca", 53: "garoa", 55: "garoa forte",
    61: "chuva fraca", 63: "chuva", 65: "chuva forte", 66: "chuva congelante", 67: "chuva congelante",
    80: "pancadas fracas", 81: "pancadas de chuva", 82: "pancadas fortes",
    95: "trovoada", 96: "trovoada com granizo", 99: "trovoada com granizo",
}


def descricao_codigo(codigo) -> str:
    return _DESCRICAO_WMO.get(codigo, "condição desconhecida")


def tempo_agora(lat: float, lon: float) -> dict | None:
    """Condicao ATUAL (medida/estimada a cada 15 min pelo Open-Meteo) + a
    chance de chuva das proximas horas de hoje. None em erro de rede."""
    try:
        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,apparent_temperature,precipitation,weathercode,"
                "relative_humidity_2m,wind_speed_10m",
                "timezone": "America/Sao_Paulo",
            },
            timeout=8,
        )
        resp.raise_for_status()
        atual = resp.json()["current"]
        codigo = atual.get("weathercode")
        return {
            "medido_em": atual.get("time"),
            "condicao": descricao_codigo(codigo),
            "chovendo_agora": (atual.get("precipitation") or 0) > 0 or codigo in _CODIGOS_CHUVA,
            "precipitacao_mm": atual.get("precipitation"),
            "temperatura": atual.get("temperature_2m"),
            "sensacao": atual.get("apparent_temperature"),
            "umidade_pct": atual.get("relative_humidity_2m"),
            "vento_kmh": atual.get("wind_speed_10m"),
        }
    except (requests.RequestException, ValueError, KeyError):
        return None
