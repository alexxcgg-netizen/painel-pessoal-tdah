"""Conta pura (sem IA, sem rede) do custo de combustivel de um trajeto -
litros e reais, a partir da distancia real (vinda do maps_client) e do
consumo/preco que o Alex informar. Nunca estima distancia sozinho - isso
sempre vem do Google Maps, pra nao inventar numero de viagem."""


def custo_combustivel(distancia_km: float, km_por_litro: float, preco_por_litro: float) -> dict:
    litros = distancia_km / km_por_litro
    return {"litros": round(litros, 1), "custo": round(litros * preco_por_litro, 2)}
