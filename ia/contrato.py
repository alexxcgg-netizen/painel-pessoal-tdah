# ia/contrato.py — so a faixa A1 pode alterar (e so compativel com isto)
from dataclasses import dataclass
from typing import Optional


@dataclass
class Resposta:
    ok: bool
    texto: Optional[str] = None
    dados: Optional[dict] = None          # JSON validado, quando houver schema
    provedor: str = ""
    modelo: str = ""
    esforco: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cache_lido: int = 0
    tokens_cache_escrito: int = 0
    custo_usd: float = 0.0
    latencia_ms: int = 0
    fallback_usado: bool = False
    erro: Optional[str] = None


def chamar_ia(funcao: str, mensagens: list, *, sistema: str = "",
              contexto_fixo: str = "", schema: Optional[dict] = None,
              opcoes: Optional[dict] = None) -> Resposta:
    """Ponto unico de entrada. Implementado em ia/core.py (faixa A1)."""
    raise NotImplementedError


def registrar_uso(funcao: str, provedor: str, modelo: str, *, tokens_in: int = 0,
                  tokens_out: int = 0, tokens_cache_lido: int = 0,
                  tokens_cache_escrito: int = 0, custo_usd: float = 0.0,
                  latencia_ms: int = 0, ok: bool = True) -> None:
    """Grava em uso_ia (sem conteudo de prompt). Implementado em ia/medicao.py
    (faixa A4). Tambem serve a chamadas que nao passam por chamar_ia."""
    raise NotImplementedError


def teto_permite(funcao: str) -> bool:
    """True se o teto mensal de IA ainda permite esta funcao. Implementado em
    ia/teto.py (faixa A4)."""
    raise NotImplementedError


class Adapter:
    """Interface dos adapters. contexto_fixo e o prefixo cacheavel e deve ser
    identico entre chamadas seguidas."""

    def chamar(self, *, modelo: str, esforco: str, sistema: str,
               contexto_fixo: str, mensagens: list, schema: Optional[dict],
               max_tokens_saida: int, cache: dict, modo: str) -> Resposta:
        raise NotImplementedError
