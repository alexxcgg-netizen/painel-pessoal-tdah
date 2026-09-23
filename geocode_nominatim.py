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
   nova consulta. So uma falha de REDE (timeout/erro de conexao) deixa
   `geocode_status` None de proposito, pra poder tentar de novo mais tarde
   (isso nao e "repetir a mesma consulta que já deu certo", e simplesmente
   nunca ter conseguido perguntar)."""

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


def geocodificar(nome: str, cidade: str | None) -> dict:
    """Devolve {"status": "ok", "lat":..., "lng":...} | {"status": "nao_encontrado"}
    | {"status": "erro"} (erro = falha de rede/timeout - NAO persistir isso como
    definitivo, ver docstring do modulo). Nunca lanca excecao."""
    consulta = ", ".join(p for p in [nome, cidade] if p)
    if not consulta.strip():
        return {"status": "nao_encontrado"}

    _throttle()
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": consulta, "format": "jsonv2", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=8,
        )
        resp.raise_for_status()
        resultados = resp.json()
    except (requests.RequestException, ValueError):
        return {"status": "erro"}

    if not resultados:
        return {"status": "nao_encontrado"}
    primeiro = resultados[0]
    try:
        return {"status": "ok", "lat": float(primeiro["lat"]), "lng": float(primeiro["lon"])}
    except (KeyError, TypeError, ValueError):
        return {"status": "nao_encontrado"}
