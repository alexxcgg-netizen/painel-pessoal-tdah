"""Conta pura (sem IA, sem rede) do custo de combustivel de um trajeto -
litros e reais, a partir da distancia real (vinda do maps_client) e do
consumo/preco que o Alex informar. Nunca estima distancia sozinho - isso
sempre vem do Google Maps, pra nao inventar numero de viagem."""

from datetime import date


def custo_combustivel(distancia_km: float, km_por_litro: float, preco_por_litro: float) -> dict:
    litros = distancia_km / km_por_litro
    return {"litros": round(litros, 1), "custo": round(litros * preco_por_litro, 2)}


def modo_viagem_ativo(estado: dict | None, hoje: date) -> bool:
    """Fase 5 (US-C16): o toggle "ativo" liga o modo viagem manualmente; se
    tambem tiver data_inicio/data_fim, o modo so vale dentro dessa janela
    (liga um pouco antes/depois automaticamente sem precisar desligar na
    mao) - fora da janela, mesmo com "ativo" ainda marcado, conta como
    desligado (mesmo espirito do hiperfoco_ate: expira sozinho)."""
    if not estado or not estado.get("ativo"):
        return False
    hoje_iso = hoje.isoformat()
    inicio = estado.get("data_inicio")
    fim = estado.get("data_fim")
    if inicio and hoje_iso < inicio:
        return False
    if fim and hoje_iso > fim:
        return False
    return True
