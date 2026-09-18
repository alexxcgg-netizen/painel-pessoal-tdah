"""Previsao do tempo generica (chuva/temperatura) por cidade, via Open-Meteo -
gratuito, sem chave, sem cadastro (https://open-meteo.com). Usado pra avisar
sobre um voo agendado num destino especifico ("vai chover em Blumenau nesse
dia"). Nunca decide nada sozinho - so busca o dado bruto, quem interpreta
(voar ou nao) e sempre o Alex.

Erro de rede ou cidade nao encontrada nunca derruba quem chamou - devolve
None e quem usa decide o que fazer (normalmente: so nao mostra o aviso)."""

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
