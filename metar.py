"""METAR/TAF oficiais via aviationweather.gov (NOAA) - gratuito, sem chave,
cobre aerodromos no mundo todo, nao so EUA (https://aviationweather.gov/data/api/).

Importante: isso so repassa o texto BRUTO oficial, exatamente como a fonte
manda - nunca interpreta teto, base de nuvem, categoria de voo (VFR/IFR) nem
nada do tipo aqui. Decisao de voar e sempre do Alex, com a licenca dele -
esse app nunca vira fonte de decisao meteorologica por conta propria."""

import requests

METAR_URL = "https://aviationweather.gov/api/data/metar"
TAF_URL = "https://aviationweather.gov/api/data/taf"


def buscar_metar_taf(icao: str) -> dict:
    icao = (icao or "").strip().upper()
    if not icao:
        return {"metar": None, "taf": None, "erro": "informe o codigo ICAO do aerodromo"}

    metar, taf, erro = None, None, None
    try:
        resp = requests.get(METAR_URL, params={"ids": icao, "format": "raw"}, timeout=8)
        resp.raise_for_status()
        metar = resp.text.strip() or None
    except requests.RequestException:
        erro = "nao consegui buscar o METAR agora"

    try:
        resp = requests.get(TAF_URL, params={"ids": icao, "format": "raw"}, timeout=8)
        resp.raise_for_status()
        taf = resp.text.strip() or None
    except requests.RequestException:
        if not erro:
            erro = "nao consegui buscar o TAF agora"

    if not metar and not taf and not erro:
        erro = f"nenhum dado encontrado pra {icao} - confere o codigo ICAO"

    return {"metar": metar, "taf": taf, "erro": erro}
