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


LIMITE_ALERTA_CHUVA = 50


def resumo_chuva_do_dia(horas: list[dict], hora_atual: int, limite_pct: int = LIMITE_ALERTA_CHUVA) -> dict:
    """Acha a janela continua de horas (a partir de agora) com maior risco de
    chuva do resto do dia - pura funcao, sem rede, facil de testar isolada.
    'horas': lista de {'hora': 0-23, 'chuva_pct': int} de UM dia (pode vir
    fora de ordem ou com horas ja passadas - so as de agora em diante contam)."""
    futuras = sorted((h for h in horas if h["hora"] >= hora_atual), key=lambda h: h["hora"])
    if not futuras:
        return {"alerta": False, "chovendo_agora": False, "texto": "Sem mais previsao pra hoje."}

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
        "texto": f"Risco de chuva entre {hora_inicio}h e {fim_txt} (ate {pico['chuva_pct']}% de chance).",
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
