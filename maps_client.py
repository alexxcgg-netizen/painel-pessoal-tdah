"""Calculo de tempo de deslocamento via Google Routes API - usado pra
responder "que horas eu preciso sair pra chegar a tempo?", considerando
transito em tempo real (nao so distancia).

So fica ativo quando GOOGLE_MAPS_API_KEY existe no .env. Desde 03/2025 o Google da uma cota
gratis POR SKU por mes (Routes com transito: 5.000; trecho lento no caminho: faixa mais cara,
1.000; Geocoding: 10.000). O painel conta as proprias chamadas (tabela uso_maps) e trava antes
de passar da cota - pedido do Alex (2026-10-15): "tem que ser gratis". Ver COTA_MES.

Endpoint e formato conferidos direto na documentacao oficial da Routes API
antes de escrever, nao inventados.
"""

import math
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

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


# Trava da cota gratis (por mes, por faixa de preco do Google). Margem abaixo da cota de
# verdade - o contador do painel nao enxerga chamada feita por fora (teste manual no console).
COTA_MES = {"lentidao": 800, "transito": 4000, "basico": 8000, "lugar_nome": 8000}
_NIVEL_ABAIXO = {"lentidao": "transito", "transito": "basico"}


class CotaEsgotada(requests.RequestException):
    """A cota gratis do mes acabou. E um RequestException de proposito: todo lugar que chama
    o Maps ja trata "Google fora do ar" (card/aviso seguem com a folga) - cota acabada e igual."""


def usar_cota(nivel: str) -> bool:
    """Conta 1 chamada da faixa `nivel` no mes; False = ja bateu a trava (e nao conta).
    Sem banco/tabela (banco ainda nao criado) nao trava."""
    try:
        import db

        conn = db.get_db()
    except Exception:
        return True
    try:
        mes = datetime.now().strftime("%Y-%m")
        conn.execute("INSERT OR IGNORE INTO uso_maps (mes, nivel, chamadas) VALUES (?, ?, 0)", (mes, nivel))
        cur = conn.execute(
            "UPDATE uso_maps SET chamadas = chamadas + 1 WHERE mes = ? AND nivel = ? AND chamadas < ?",
            (mes, nivel, COTA_MES.get(nivel, 0)),
        )
        conn.commit()
        return cur.rowcount == 1
    except sqlite3.Error:
        return True
    finally:
        conn.close()


def _partida_rfc3339(partida) -> str | None:
    """departureTime do Google: so no futuro (passado = erro 400). Hora local sem fuso -> UTC."""
    if not isinstance(partida, datetime):
        return None
    agora = datetime.now(partida.tzinfo) if partida.tzinfo else datetime.now()
    if partida <= agora + timedelta(minutes=1):
        return None
    return partida.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _segundos(valor) -> int:
    return int(float(str(valor).rstrip("s")))


def tempo_de_viagem(origem: str, destino: str, modo: str = "DRIVE", _lugares=(None, None),
                    partida: datetime | None = None, lentidao: bool = False) -> dict:
    """Tempo de carro com transito. `partida` (futuro) = transito previsto pra essa hora, nao o
    de agora. `lentidao` = tambem os trechos lentos/parados do caminho (faixa mais cara do
    Google - so onde aparece pro Alex). Sem cota da faixa pedida, cai pra de baixo; sem
    nenhuma, CotaEsgotada. Levanta ValueError (sem rota) / RequestException (rede)."""
    if modo not in MODOS_VALIDOS:
        modo = "DRIVE"
    carro = modo == "DRIVE"
    nivel = "lentidao" if (carro and lentidao) else ("transito" if carro else "basico")
    while not usar_cota(nivel):
        nivel = _NIVEL_ABAIXO.get(nivel)
        if nivel is None:
            raise CotaEsgotada("cota gratis do Google Maps do mes acabou")

    body = {
        "origin": _ponto(origem, _lugares[0]),
        "destination": _ponto(destino, _lugares[1]),
        "travelMode": modo,
        "languageCode": "pt-BR",
        "units": "METRIC",
    }
    mascara = ["routes.duration", "routes.distanceMeters", "routes.polyline.encodedPolyline"]
    if nivel in ("transito", "lentidao"):
        body["routingPreference"] = "TRAFFIC_AWARE"
        mascara.append("routes.staticDuration")
        quando = _partida_rfc3339(partida)
        if quando:
            body["departureTime"] = quando
    if nivel == "lentidao":
        body["extraComputations"] = ["TRAFFIC_ON_POLYLINE"]
        mascara.append("routes.travelAdvisory.speedReadingIntervals")

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": os.environ["GOOGLE_MAPS_API_KEY"],
        "X-Goog-FieldMask": ",".join(mascara),
    }
    resp = requests.post(URL, json=body, headers=headers, timeout=15)
    resp.raise_for_status()
    rotas = resp.json().get("routes", [])
    if not rotas:
        raise ValueError("nenhuma rota encontrada entre esses enderecos")

    rota = rotas[0]
    duracao_segundos = _segundos(rota["duration"])
    codigo = (rota.get("polyline") or {}).get("encodedPolyline")
    pontos = decodificar_polyline(codigo) if codigo else []
    transito = None
    if nivel != "basico" and rota.get("staticDuration"):
        transito = max(0, round((duracao_segundos - _segundos(rota["staticDuration"])) / 60))
    lentos = []
    if nivel == "lentidao":
        intervalos = (rota.get("travelAdvisory") or {}).get("speedReadingIntervals") or []
        lentos = nomear_lentidao(trechos_lentos(pontos, intervalos))
    return {
        "duracao_minutos": round(duracao_segundos / 60),
        "distancia_km": round(rota["distanceMeters"] / 1000, 1),
        "transito_min": transito,
        "lentidao": lentos,
        "destino_ll": [round(pontos[-1][0], 5), round(pontos[-1][1], 5)] if pontos else None,
        "_polyline": codigo,
    }


def _km(a, b) -> float:
    """Distancia em km entre dois (lat, lon) - haversine."""
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(h)))


LENTO_MINIMO_KM = 1.0  # "lento" curto e semaforo/rotatoria - nao vale aviso
PARADO_MINIMO_KM = 0.3


def trechos_lentos(pontos: list, intervalos: list) -> list[dict]:
    """speedReadingIntervals (indices do polyline + NORMAL/SLOW/TRAFFIC_JAM) -> trechos com
    km do inicio, extensao, nivel e o ponto do meio. Vizinhos se juntam; parado ganha de lento."""
    if len(pontos) < 2:
        return []
    acum = [0.0]
    for a, b in zip(pontos, pontos[1:]):
        acum.append(acum[-1] + _km(a, b))
    ultimo = len(pontos) - 1
    brutos = []
    for iv in intervalos or []:
        if not isinstance(iv, dict) or iv.get("speed") not in ("SLOW", "TRAFFIC_JAM"):
            continue
        try:
            i0 = min(max(int(iv.get("startPolylinePointIndex", 0)), 0), ultimo)
            i1 = min(max(int(iv.get("endPolylinePointIndex", ultimo)), 0), ultimo)
        except (TypeError, ValueError):
            continue
        if i1 > i0:
            brutos.append([i0, i1, iv["speed"] == "TRAFFIC_JAM"])
    juntos = []
    for b in sorted(brutos):
        if juntos and b[0] <= juntos[-1][1]:
            juntos[-1][1] = max(juntos[-1][1], b[1])
            juntos[-1][2] = juntos[-1][2] or b[2]
        else:
            juntos.append(b)
    saida = []
    for i0, i1, parado in juntos:
        extensao = acum[i1] - acum[i0]
        if extensao < (PARADO_MINIMO_KM if parado else LENTO_MINIMO_KM):
            continue
        meio = (acum[i0] + acum[i1]) / 2
        im = next(i for i in range(i0, i1 + 1) if acum[i] >= meio)
        saida.append({
            "nivel": "parado" if parado else "lento",
            "de_km": round(acum[i0], 1),
            "extensao_km": round(extensao, 1),
            "ponto": [round(pontos[im][0], 5), round(pontos[im][1], 5)],
            "_i": [i0, i1],
        })
    return saida


_cache_nome_trecho: dict = {}


def nome_do_trecho(lat: float, lon: float) -> str | None:
    """'BR-470, Gaspar' (estrada + cidade) pelo Geocoding reverso. None se nao achar, sem
    cota ou sem rede. Cache por ~100 m."""
    chave = (round(lat, 3), round(lon, 3))
    if chave in _cache_nome_trecho:
        return _cache_nome_trecho[chave]
    if not usar_cota("lugar_nome"):
        return None
    try:
        resp = requests.get(
            GEOCODE_URL,
            params={"latlng": f"{lat},{lon}", "result_type": "route", "language": "pt-BR",
                    "key": os.environ["GOOGLE_MAPS_API_KEY"]},
            timeout=10,
        )
        resp.raise_for_status()
        resultados = resp.json().get("results") or []
    except (requests.RequestException, ValueError, KeyError):
        return None  # nao cacheia falha de rede
    nome = None
    if resultados:
        estrada = cidade = None
        for c in resultados[0].get("address_components") or []:
            tipos = c.get("types") or []
            if "route" in tipos and not estrada:
                estrada = c.get("short_name") or c.get("long_name")
            if ("administrative_area_level_2" in tipos or "locality" in tipos) and not cidade:
                cidade = c.get("long_name")
        nome = ", ".join(p for p in (estrada, cidade) if p) or None
    _cache_nome_trecho[chave] = nome
    return nome


def nomear_lentidao(lentos: list[dict], maximo: int = 2) -> list[dict]:
    """Ordena (parado primeiro, depois o maior) e da nome aos `maximo` piores."""
    lentos = sorted(lentos, key=lambda x: (x["nivel"] != "parado", -x["extensao_km"]))
    for trecho in lentos[:maximo]:
        nome = nome_do_trecho(*trecho["ponto"])
        if nome:
            trecho["nome"] = nome
    return lentos


def _km_texto(km: float) -> str:
    return f"{km:.1f}".replace(".0", "").replace(".", ",") + " km"


def frase_trecho(trecho: dict) -> str:
    """'Parado na BR-470, Gaspar (2 km) - pode ser acidente ou blitz'. Nunca afirma a causa."""
    onde = f"na {trecho['nome']}" if trecho.get("nome") else f"a {_km_texto(trecho['de_km'])} da saída"
    if trecho["nivel"] == "parado":
        return f"Parado {onde} ({_km_texto(trecho['extensao_km'])}) - pode ser acidente ou blitz"
    return f"Lento {onde} ({_km_texto(trecho['extensao_km'])})"


TRANSITO_RELEVANTE_MIN = 3  # menos que isso nao vale falar


def resumo_transito(viagem: dict) -> str:
    """Frase curta pro aviso: '+12 min de trânsito. Parado na BR-470, ...'. '' se nada."""
    partes = []
    t = viagem.get("transito_min")
    if isinstance(t, int) and t >= TRANSITO_RELEVANTE_MIN:
        partes.append(f"+{t} min de trânsito")
    lentos = [x for x in viagem.get("lentidao") or [] if isinstance(x, dict) and x.get("nivel")]
    if lentos:
        partes.append(frase_trecho(lentos[0]))
    return ". ".join(partes)


WAZE_URL = "https://waze.com/ul"


def link_waze(ll=None, endereco: str | None = None) -> str | None:
    """Deep link oficial do Waze ja navegando (developers.google.com/waze/deeplinks).
    Coordenada exata quando tem; senao o endereco em texto. Um destino so (o Waze nao aceita
    paradas no meio)."""
    if isinstance(ll, (list, tuple)) and len(ll) == 2 and all(isinstance(v, (int, float)) for v in ll):
        return f"{WAZE_URL}?ll={ll[0]:.5f},{ll[1]:.5f}&navigate=yes"
    c = coordenada(endereco or "")
    if c:
        return f"{WAZE_URL}?ll={c[0]:.5f},{c[1]:.5f}&navigate=yes"
    if isinstance(endereco, str) and endereco.strip():
        return f"{WAZE_URL}?" + urlencode({"q": endereco.strip()[:200], "navigate": "yes"})
    return None


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
                     margem=22, maximo=90, faixas=None) -> dict | None:
    """Projeta o caminho num quadro largura x altura (norte pra cima, proporcao
    real corrigida pela latitude) e reduz pra no maximo `maximo` pontos.
    `marcos` = indice de cada parada dentro de `pontos`; `faixas` = [(i0, i1, nivel)] dos
    trechos lentos/parados (viram "lentos", pintados por cima do caminho)."""
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
    lentos = []
    for i0, i1, nivel in faixas or []:
        if not (0 <= i0 < i1 < len(pontos)):
            continue
        passo_f = max(1, (i1 - i0) // 24)
        idx = sorted(set(range(i0, i1 + 1, passo_f)) | {i1})
        lentos.append({"nivel": nivel, "pontos": [proj(i) for i in idx]})
    return {
        "w": largura, "h": altura,
        "pontos": [proj(i) for i in indices],
        "paradas": [proj(i) for i in marcos],
        "lentos": lentos,
    }


def trajeto(pontos: list[str]) -> dict:
    """Soma os trechos de um trajeto com varias paradas (A -> B -> C), cada trecho
    calculado pela Routes API com transito e trechos lentos/parados. Levanta
    ValueError/RequestException/CotaEsgotada como tempo_de_viagem."""
    lugares = [resolver_lugar(p) for p in pontos]
    trechos, caminho, marcos, faixas, lentidao = [], [], [0], [], []
    waze = None
    for i, (origem, destino) in enumerate(zip(pontos, pontos[1:])):
        t = tempo_de_viagem(origem, destino, _lugares=(lugares[i], lugares[i + 1]), lentidao=True)
        codigo = t.pop("_polyline", None)
        destino_ll = t.pop("destino_ll", None)
        lentos = t.pop("lentidao", None) or []
        if i == 0:  # o Waze nao aceita paradas: vai ate a primeira
            waze = link_waze(destino_ll, (lugares[1] or {}).get("endereco") or destino)
        base = len(caminho) - 1 if caminho else 0
        if codigo:
            pts = decodificar_polyline(codigo)
            caminho.extend(pts if not caminho else pts[1:])
            marcos.append(len(caminho) - 1)
        for x in lentos:
            i0, i1 = x.pop("_i", (0, 0))
            if codigo:
                faixas.append((base + i0, base + i1, x["nivel"]))
            lentidao.append({"trecho": i, **x})
        trechos.append({"de": origem, "para": destino, **t})
    transitos = [t["transito_min"] for t in trechos if isinstance(t.get("transito_min"), int)]
    return {
        "lugares": [
            {"pedido": p, "nome": l["nome"], "endereco": l["endereco"]} if l else {"pedido": p, "endereco": p}
            for p, l in zip(pontos, lugares)
        ],
        # chave "_" = so pro servidor (o card), a IA nao ve
        "_place_ids": [l["place_id"] if l else None for l in lugares],
        "_traco": traco_desenhavel(caminho, marcos, faixas=faixas) if len(marcos) == len(pontos) else None,
        "_waze": waze,
        "trechos": trechos,
        "distancia_total_km": round(sum(t["distancia_km"] for t in trechos), 1),
        "duracao_total_minutos": sum(t["duracao_minutos"] for t in trechos),
        "transito_total_min": sum(transitos) if transitos else None,
        "lentidao": lentidao,
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


# Quanto antes da chegada ele mais ou menos sai - so pra pedir ao Google o transito previsto
# pra perto daquela hora (o tempo de verdade vem da propria resposta).
_ANTES_ESTIMADO_MIN = 30


def horario_de_saida(
    origem: str, destino: str, chegar_ate: datetime, margem_minutos: int = 15, modo: str = "DRIVE",
    lentidao: bool = False,
) -> dict:
    """Conta pra tras a partir do horario que precisa chegar: tempo de viagem (com o
    transito previsto pra hora de sair, nao o de agora) + margem de seguranca."""
    partida = chegar_ate - timedelta(minutes=margem_minutos + _ANTES_ESTIMADO_MIN)
    viagem = tempo_de_viagem(origem, destino, modo, partida=partida, lentidao=lentidao)
    sair_ate = chegar_ate - timedelta(minutes=viagem["duracao_minutos"] + margem_minutos)
    return {
        "sair_ate": sair_ate.isoformat(),
        "duracao_minutos": viagem["duracao_minutos"],
        "distancia_km": viagem["distancia_km"],
        "margem_minutos": margem_minutos,
        "transito_min": viagem.get("transito_min"),
        "lentidao": [{k: v for k, v in x.items() if k != "_i"} for x in viagem.get("lentidao") or []],
        "waze": link_waze(viagem.get("destino_ll"), destino),
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
