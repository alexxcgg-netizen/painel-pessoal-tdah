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

# 'DRIVE' (carro), 'WALK' (a pe), 'BICYCLE', 'TRANSIT' (transporte publico)
MODOS_VALIDOS = {"DRIVE", "WALK", "BICYCLE", "TRANSIT"}


def configurado() -> bool:
    return bool(os.environ.get("GOOGLE_MAPS_API_KEY"))


def tempo_de_viagem(origem: str, destino: str, modo: str = "DRIVE") -> dict:
    if modo not in MODOS_VALIDOS:
        modo = "DRIVE"

    body = {
        "origin": {"address": origem},
        "destination": {"address": destino},
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
