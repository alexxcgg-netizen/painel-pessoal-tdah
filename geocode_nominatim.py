"""US-F13 (Fase 6 F3): geocodificacao de "Lugares que Gostei" via Nominatim
(OpenStreetMap) - decisao do Alex: OSM agora, sem chave nem cartao (ver
tasks/fase6/progress-f3.txt).

Politica de uso do Nominatim (https://operations.osmfoundation.org/policies/nominatim/,
conferida via WebSearch em 2026-09-23) tem 3 exigencias e as 3 sao seguidas aqui:
1. Maximo 1 requisicao por segundo - `_throttle()` abaixo espera o que faltar
   desde a ultima chamada (processo unico do Flask dev server: um contador em
   memoria de modulo basta, sem precisar de lock entre processos).
2. User-Agent proprio identificando o app (nao o default da lib HTTP) -
   `USER_AGENT` abaixo. Sem email nem qualquer dado pessoal do Alex (nao e
   necessario pra cumprir a politica - so precisa identificar QUE app esta
   chamando, nao QUEM e o dono).
3. Cachear o resultado, nunca repetir a mesma consulta - por isso o
   geocode e feito UMA VEZ por lugar e o resultado (ou a falta dele) fica
   salvo em `lugares.lat/lng/geocode_status` (db.salvar_geocode_lugar) -
   `geocode_status` preenchido (mesmo que "nao_encontrado") nunca dispara
   nova consulta. Falha TEMPORARIA (rede/timeout, 429, 5xx) vira status
   "erro" com um "tentar de novo depois de" (app.GEOCODE_ESPERA_APOS_ERRO) -
   revisao da Fase 6: antes nao gravava nada e cada GET /api/lugares tentava
   de novo na hora, sincrono, no unico worker. Recusa 4xx (ex: 400/403) vira
   "recusado", definitivo (nao ha rota de renomear lugar; um lugar novo com
   outro nome e outra consulta)."""

import os
import time

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "PainelPessoalTDAH/1.0 (app pessoal de produtividade, uso nao comercial)"

_INTERVALO_MIN_SEGUNDOS = 1.0
_ultima_chamada = 0.0


def _throttle():
    global _ultima_chamada
    agora = time.monotonic()
    falta = _INTERVALO_MIN_SEGUNDOS - (agora - _ultima_chamada)
    if falta > 0:
        time.sleep(falta)
    _ultima_chamada = time.monotonic()


# Curto de proposito: roda dentro de uma requisicao HTTP (criar lugar /
# backfill em GET /api/lugares) no unico worker do gunicorn.
TIMEOUT_SEGUNDOS = 4


def geocodificar(nome: str, cidade: str | None) -> dict:
    """Devolve {"status": "ok", "lat":..., "lng":...} | {"status": "nao_encontrado"}
    | {"status": "erro"} (temporario: rede/timeout/429/5xx - tenta de novo mais
    tarde) | {"status": "recusado"} (4xx exceto 429 - definitivo). Nunca lanca
    excecao."""
    consulta = ", ".join(p for p in [nome, cidade] if p)
    if not consulta.strip():
        return {"status": "nao_encontrado"}

    _throttle()
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": consulta, "format": "jsonv2", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SEGUNDOS,
        )
        resp.raise_for_status()
        resultados = resp.json()
    except requests.HTTPError as e:
        codigo = getattr(e.response, "status_code", None)
        if isinstance(codigo, int) and 400 <= codigo < 500 and codigo != 429:
            return {"status": "recusado"}
        return {"status": "erro"}
    except (requests.RequestException, ValueError):
        return {"status": "erro"}

    if not resultados:
        return {"status": "nao_encontrado"}
    primeiro = resultados[0]
    try:
        return {"status": "ok", "lat": float(primeiro["lat"]), "lng": float(primeiro["lon"])}
    except (KeyError, TypeError, ValueError):
        return {"status": "nao_encontrado"}
