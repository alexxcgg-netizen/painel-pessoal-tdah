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
import re
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


_cache_horarios: dict[str, dict | None] = {}


def horario_funcionamento(texto: str, dia) -> dict | None:
    """Horario de funcionamento do lugar NAQUELE dia da semana (card de documentos,
    2026-10-14: "abre 9h-17h, almoco 12h-13h"). -> {"nome", "faixas": [["09:00","12:00"], ...]}
    ou {"nome", "fechado": True}; None se nao achar, se o Google nao tiver o horario ou a
    rede falhar. Uma busca por lugar (cache em memoria)."""
    chave = texto.strip().lower()
    if chave not in _cache_horarios:
        dados = None
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
                    "X-Goog-FieldMask": "places.displayName,places.regularOpeningHours",
                },
                timeout=10,
            )
            resp.raise_for_status()
            achados = resp.json().get("places") or []
            if achados and (achados[0].get("regularOpeningHours") or {}).get("periods"):
                dados = {
                    "nome": achados[0].get("displayName", {}).get("text", texto),
                    "periodos": achados[0]["regularOpeningHours"]["periods"],
                }
        except (requests.RequestException, ValueError, KeyError):
            return None  # nao cacheia falha de rede
        _cache_horarios[chave] = dados
    dados = _cache_horarios[chave]
    if not dados:
        return None
    dia_google = (dia.weekday() + 1) % 7  # Google: 0 = domingo
    faixas = []
    for p in dados["periodos"]:
        ab, fe = p.get("open") or {}, p.get("close") or {}
        if ab.get("day") != dia_google:
            continue
        if not fe:  # aberto 24h
            return {"nome": dados["nome"], "faixas": [["00:00", "24:00"]]}
        fim = "24:00" if fe.get("day") != dia_google else f"{fe.get('hour', 0):02d}:{fe.get('minute', 0):02d}"
        faixas.append([f"{ab.get('hour', 0):02d}:{ab.get('minute', 0):02d}", fim])
    if not faixas:
        return {"nome": dados["nome"], "fechado": True}
    return {"nome": dados["nome"], "faixas": sorted(faixas)}


_RE_COORD = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$")


def coordenada(texto: str) -> tuple[float, float] | None:
    """'-26.91,-49.06' -> (lat, lon); qualquer outra coisa -> None."""
    m = _RE_COORD.match(texto or "")
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None


def resolver_lugar(texto: str) -> dict | None:
    """Nome livre ("Aeroclube de Blumenau", "Havan Brusque") -> lugar exato do
    Google (place_id, nome, endereco). None se nao achar ou se a busca falhar -
    quem chama cai no endereco em texto."""
    if coordenada(texto):
        return None  # GPS ja e o lugar exato
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
    if lugar:
        return {"placeId": lugar["place_id"]}
    c = coordenada(texto)
    if c:
        return {"location": {"latLng": {"latitude": c[0], "longitude": c[1]}}}
    return {"address": texto}


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
        "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline",
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
        "_polyline": (rota.get("polyline") or {}).get("encodedPolyline"),
    }


def decodificar_polyline(codigo: str) -> list[tuple[float, float]]:
    """Formato 'encoded polyline' do Google -> [(lat, lon), ...]."""
    pontos, i, lat, lon = [], 0, 0, 0
    while i < len(codigo):
        for eixo in (0, 1):
            resultado, desloc = 0, 0
            while True:
                b = ord(codigo[i]) - 63
                i += 1
                resultado |= (b & 0x1F) << desloc
                desloc += 5
                if b < 0x20:
                    break
            delta = ~(resultado >> 1) if resultado & 1 else resultado >> 1
            if eixo == 0:
                lat += delta
            else:
                lon += delta
        pontos.append((lat / 1e5, lon / 1e5))
    return pontos


def traco_desenhavel(pontos: list[tuple[float, float]], marcos: list[int], largura=320, altura=200,
                     margem=22, maximo=90) -> dict | None:
    """Projeta o caminho num quadro largura x altura (norte pra cima, proporcao
    real corrigida pela latitude) e reduz pra no maximo `maximo` pontos.
    `marcos` = indice de cada parada dentro de `pontos`."""
    import math

    if len(pontos) < 2:
        return None
    lat_med = sum(p[0] for p in pontos) / len(pontos)
    fx = math.cos(math.radians(lat_med))
    xs = [p[1] * fx for p in pontos]
    ys = [-p[0] for p in pontos]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    escala = min((largura - 2 * margem) / max(maxx - minx, 1e-9), (altura - 2 * margem) / max(maxy - miny, 1e-9))
    offx = (largura - (maxx - minx) * escala) / 2
    offy = (altura - (maxy - miny) * escala) / 2

    def proj(i):
        return [round(offx + (xs[i] - minx) * escala, 1), round(offy + (ys[i] - miny) * escala, 1)]

    passo = max(1, len(pontos) // maximo)
    indices = sorted(set(range(0, len(pontos), passo)) | {len(pontos) - 1} | set(marcos))
    return {
        "w": largura, "h": altura,
        "pontos": [proj(i) for i in indices],
        "paradas": [proj(i) for i in marcos],
    }


def trajeto(pontos: list[str]) -> dict:
    """Soma os trechos de um trajeto com varias paradas (A -> B -> C), cada
    trecho calculado pela Routes API. Levanta ValueError/RequestException
    como tempo_de_viagem."""
    lugares = [resolver_lugar(p) for p in pontos]
    trechos, caminho, marcos = [], [], [0]
    for i, (origem, destino) in enumerate(zip(pontos, pontos[1:])):
        t = tempo_de_viagem(origem, destino, _lugares=(lugares[i], lugares[i + 1]))
        codigo = t.pop("_polyline", None)
        if codigo:
            pts = decodificar_polyline(codigo)
            caminho.extend(pts if not caminho else pts[1:])
            marcos.append(len(caminho) - 1)
        trechos.append({"de": origem, "para": destino, **t})
    return {
        "lugares": [
            {"pedido": p, "nome": l["nome"], "endereco": l["endereco"]} if l else {"pedido": p, "endereco": p}
            for p, l in zip(pontos, lugares)
        ],
        # chave "_" = so pro servidor (o card), a IA nao ve
        "_place_ids": [l["place_id"] if l else None for l in lugares],
        "_traco": traco_desenhavel(caminho, marcos) if len(marcos) == len(pontos) else None,
        "trechos": trechos,
        "distancia_total_km": round(sum(t["distancia_km"] for t in trechos), 1),
        "duracao_total_minutos": sum(t["duracao_minutos"] for t in trechos),
    }


MAPS_DIR_URL = "https://www.google.com/maps/dir/"


def _rotulo_lugar(lugar: dict) -> str:
    nome = (lugar.get("nome") or "").strip()
    endereco = (lugar.get("endereco") or lugar.get("pedido") or "").strip()
    if nome and endereco and not endereco.lower().startswith(nome.lower()[:12]):
        return f"{nome}, {endereco}"
    return endereco or nome


def link_rota(lugares: list[dict], place_ids: list | None = None, partir_de_onde_estou: bool = False) -> str:
    """Link universal do Google Maps (Maps URLs, api=1) com a rota de carro ja
    montada - no iPhone abre o app do Google Maps se instalado, senao o site.
    partir_de_onde_estou: sem origem no link, o Maps usa a localizacao real."""
    from urllib.parse import urlencode

    ids = list(place_ids or [None] * len(lugares))
    rotulos = [_rotulo_lugar(l) for l in lugares]
    if partir_de_onde_estou:
        rotulos, ids = rotulos[1:], ids[1:]
        origem, origem_id = None, None
    else:
        origem, origem_id = rotulos[0], ids[0]
        rotulos, ids = rotulos[1:], ids[1:]
    params = {"api": "1", "travelmode": "driving", "destination": rotulos[-1]}
    if ids[-1]:
        params["destination_place_id"] = ids[-1]
    if origem:
        params["origin"] = origem
        if origem_id:
            params["origin_place_id"] = origem_id
    meio, meio_ids = rotulos[:-1], ids[:-1]
    if meio:
        params["waypoints"] = "|".join(meio)
        if all(meio_ids):
            params["waypoint_place_ids"] = "|".join(meio_ids)
    return MAPS_DIR_URL + "?" + urlencode(params)


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
