"""Calculo de tempo de deslocamento via Google Routes API - usado pra
responder "que horas eu preciso sair pra chegar a tempo?", considerando
transito em tempo real (nao so distancia).

So fica ativo quando GOOGLE_MAPS_API_KEY existe no .env. Uso pessoal cabe
tranquilo nos $200/mes de credito gratuito da Google Cloud (cada calculo
custa fracao de centavo).

Endpoint e formato conferidos direto na documentacao oficial da Routes API
antes de escrever, nao inventados.
"""

import os
from datetime import datetime, timedelta

import requests

URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
PLACES_URL = "https://places.googleapis.com/v1/places:searchNearby"

# 'DRIVE' (carro), 'WALK' (a pe), 'BICYCLE', 'TRANSIT' (transporte publico)
MODOS_VALIDOS = {"DRIVE", "WALK", "BICYCLE", "TRANSIT"}


def configurado() -> bool:
    return bool(os.environ.get("GOOGLE_MAPS_API_KEY"))


PLACES_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
# vies de busca: ~50 km em volta de Brusque (raio maximo que a API aceita) -
# so prioriza, nao restringe ("Aeroclube de Blumenau" acha o certo, mas um
# lugar em Curitiba continua achavel)
_CENTRO_BUSCA = {"latitude": -27.098, "longitude": -48.913}
_cache_lugares: dict[str, dict | None] = {}


def resolver_lugar(texto: str) -> dict | None:
    """Nome livre ("Aeroclube de Blumenau", "Havan Brusque") -> lugar exato do
    Google (place_id, nome, endereco). None se nao achar ou se a busca falhar -
    quem chama cai no endereco em texto."""
    chave = texto.strip().lower()
    if chave in _cache_lugares:
        return _cache_lugares[chave]
    lugar = None
    try:
        resp = requests.post(
            PLACES_TEXT_URL,
            json={
                "textQuery": texto,
                "languageCode": "pt-BR",
                "regionCode": "BR",
                "locationBias": {"circle": {"center": _CENTRO_BUSCA, "radius": 50000.0}},
            },
            headers={
                "X-Goog-Api-Key": os.environ["GOOGLE_MAPS_API_KEY"],
                "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress",
            },
            timeout=10,
        )
        resp.raise_for_status()
        achados = resp.json().get("places") or []
        if achados:
            p = achados[0]
            lugar = {
                "place_id": p["id"],
                "nome": p.get("displayName", {}).get("text", texto),
                "endereco": p.get("formattedAddress", ""),
            }
    except (requests.RequestException, ValueError, KeyError):
        return None  # nao cacheia falha de rede
    _cache_lugares[chave] = lugar
    return lugar


def _ponto(texto: str, lugar: dict | None) -> dict:
    return {"placeId": lugar["place_id"]} if lugar else {"address": texto}


def tempo_de_viagem(origem: str, destino: str, modo: str = "DRIVE", _lugares=(None, None)) -> dict:
    if modo not in MODOS_VALIDOS:
        modo = "DRIVE"

    body = {
        "origin": _ponto(origem, _lugares[0]),
        "destination": _ponto(destino, _lugares[1]),
        "travelMode": modo,
        "languageCode": "pt-BR",
        "units": "METRIC",
    }
    if modo == "DRIVE":
        body["routingPreference"] = "TRAFFIC_AWARE"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": os.environ["GOOGLE_MAPS_API_KEY"],
        "X-Goog-FieldMask": "routes.duration,routes.distanceMeters",
    }
    resp = requests.post(URL, json=body, headers=headers, timeout=15)
    resp.raise_for_status()
    rotas = resp.json().get("routes", [])
    if not rotas:
        raise ValueError("nenhuma rota encontrada entre esses enderecos")

    rota = rotas[0]
    duracao_segundos = int(str(rota["duration"]).rstrip("s"))
    return {
        "duracao_minutos": round(duracao_segundos / 60),
        "distancia_km": round(rota["distanceMeters"] / 1000, 1),
    }


def trajeto(pontos: list[str]) -> dict:
    """Soma os trechos de um trajeto com varias paradas (A -> B -> C), cada
    trecho calculado pela Routes API. Levanta ValueError/RequestException
    como tempo_de_viagem."""
    lugares = [resolver_lugar(p) for p in pontos]
    trechos = []
    for i, (origem, destino) in enumerate(zip(pontos, pontos[1:])):
        t = tempo_de_viagem(origem, destino, _lugares=(lugares[i], lugares[i + 1]))
        trechos.append({"de": origem, "para": destino, **t})
    return {
        "lugares": [
            {"pedido": p, "nome": l["nome"], "endereco": l["endereco"]} if l else {"pedido": p, "endereco": p}
            for p, l in zip(pontos, lugares)
        ],
        "trechos": trechos,
        "distancia_total_km": round(sum(t["distancia_km"] for t in trechos), 1),
        "duracao_total_minutos": sum(t["duracao_minutos"] for t in trechos),
    }


def horario_de_saida(
    origem: str, destino: str, chegar_ate: datetime, margem_minutos: int = 15, modo: str = "DRIVE"
) -> dict:
    """Conta pra tras a partir do horario que precisa chegar: tempo de viagem
    (com transito real) + margem de seguranca."""
    viagem = tempo_de_viagem(origem, destino, modo)
    sair_ate = chegar_ate - timedelta(minutes=viagem["duracao_minutos"] + margem_minutos)
    return {
        "sair_ate": sair_ate.isoformat(),
        "duracao_minutos": viagem["duracao_minutos"],
        "distancia_km": viagem["distancia_km"],
        "margem_minutos": margem_minutos,
    }


def geocodificar(endereco: str) -> tuple[float, float]:
    resp = requests.get(
        GEOCODE_URL,
        params={"address": endereco, "key": os.environ["GOOGLE_MAPS_API_KEY"]},
        timeout=10,
    )
    resp.raise_for_status()
    resultados = resp.json().get("results") or []
    if not resultados:
        raise ValueError(f"não encontrei o endereço: {endereco}")
    loc = resultados[0]["geometry"]["location"]
    return loc["lat"], loc["lng"]


def posto_no_meio_do_caminho(origem: str, destino: str) -> dict | None:
    """Geocodifica origem e destino, acha o ponto geografico no meio do
    caminho (linha reta entre os dois pontos - aproximacao, nao segue o
    contorno exato da estrada) e procura o posto de gasolina mais proximo
    desse ponto. So localizacao: a Google Places API nao tem preco de
    combustivel confiavel pro Brasil, entao isso nunca compara preco entre
    postos, so aponta onde parar. None se nao achar nenhum por perto."""
    lat1, lng1 = geocodificar(origem)
    lat2, lng2 = geocodificar(destino)
    lat_meio, lng_meio = (lat1 + lat2) / 2, (lng1 + lng2) / 2

    body = {
        "includedTypes": ["gas_station"],
        "maxResultCount": 3,
        "locationRestriction": {
            "circle": {"center": {"latitude": lat_meio, "longitude": lng_meio}, "radius": 15000.0}
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": os.environ["GOOGLE_MAPS_API_KEY"],
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress",
    }
    resp = requests.post(PLACES_URL, json=body, headers=headers, timeout=10)
    resp.raise_for_status()
    lugares = resp.json().get("places", [])
    if not lugares:
        return None

    posto = lugares[0]
    return {
        "nome": posto.get("displayName", {}).get("text", "posto de gasolina"),
        "endereco": posto.get("formattedAddress", ""),
    }
