"""Custo em USD de uma chamada de IA, a partir de ia/precos.json (formato da faixa A4).

Fonte unica pros adapters: antes cada adapter supunha um formato diferente do
arquivo e, com o formato real, calculava custo 0 em silencio - o que deixaria o
teto mensal cego.
"""
import json
from pathlib import Path

CAMINHO_PRECOS = Path(__file__).resolve().parent / "precos.json"


def carregar_precos(caminho: Path | None = None) -> dict:
    try:
        with open(caminho or CAMINHO_PRECOS, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _preco(tabela: dict, *chaves: str) -> float:
    for chave in chaves:
        valor = tabela.get(chave)
        if isinstance(valor, (int, float)) and not isinstance(valor, bool) and valor >= 0:
            return float(valor)
    return 0.0


def custo_usd(modelo: str, tokens_in: int = 0, tokens_out: int = 0,
              tokens_cache_lido: int = 0, tokens_cache_escrito: int = 0,
              ttl_cache: str = "5m", precos: dict | None = None) -> float:
    """Modelo desconhecido ou arquivo ausente/corrompido -> 0.0 (nunca quebra a chamada)."""
    tabela = (precos if precos is not None else carregar_precos()).get("modelos", {})
    preco = tabela.get(modelo) if isinstance(tabela, dict) else None
    if not isinstance(preco, dict):
        return 0.0

    entrada = _preco(preco, "entrada")
    saida = _preco(preco, "saida")
    cache_leitura = _preco(preco, "cache_leitura")
    if ttl_cache == "1h":
        cache_escrita = _preco(preco, "cache_escrita_1h", "cache_escrita", "cache_escrita_5min")
    else:
        cache_escrita = _preco(preco, "cache_escrita_5min", "cache_escrita")

    # Faixa de preco por tamanho de entrada (ex: GPT-6 Sol acima de 272 mil tokens).
    limiar = preco.get("limiar_tokens_in")
    if isinstance(limiar, (int, float)) and tokens_in > limiar:
        entrada *= _preco(preco, "multiplicador_entrada_acima") or 1.0
        saida *= _preco(preco, "multiplicador_saida_acima") or 1.0
        # opcional: cache acima do limiar tambem muda de faixa (ex.: Haiku 5.5, 5x)
        mult_cache = _preco(preco, "multiplicador_cache_acima") or 1.0
        cache_leitura *= mult_cache
        cache_escrita *= mult_cache

    total = (
        max(tokens_in, 0) * entrada
        + max(tokens_out, 0) * saida
        + max(tokens_cache_lido, 0) * cache_leitura
        + max(tokens_cache_escrito, 0) * cache_escrita
    ) / 1_000_000
    return round(total, 8)
