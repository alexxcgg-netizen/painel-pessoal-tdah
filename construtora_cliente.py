"""Cliente limpo da API externa somente-leitura do `financeiro-construtora`
(Fase 7, faixa A10 - "decisoes da Fase 6").

Cobre so os dois endpoints que o outro sistema expoe pro painel pessoal
(ver `docs/contrato-api-construtora.md` pro contrato completo - campos,
exemplos e erros): `GET /api/resumo` e `GET /api/contas_a_vencer`,
autenticados por header `X-API-Key` contra `PAINEL_EXTERNO_API_KEY` do lado
de la (aqui: `CONSTRUTORA_API_KEY`).

Decisao do Alex (Fase 7 A10): o painel pessoal mostra SO gastos, entradas e
tempo ate a proxima conta a pagar da construtora - nada de faturamento/
margem/lucro/detalhamento por obra. Por isso a API publica deste modulo e
enxuta de proposito: `gastos_do_mes()`, `entradas_do_mes()`, `proxima_conta()`
- nada mais.

Este modulo e NOVO e ainda nao esta ligado a nada em `app.py`: as chamadas
antigas (`_buscar_resumo_construtora`, `_buscar_contas_a_vencer_construtora`,
`_cache_construtora_get/set`, `_construtora_contexto_*`) continuam existindo,
inalteradas, em `app.py` (compartilhado - faixa A10 nao edita esse arquivo).
Quem for consumir isto na UI (fora do escopo desta faixa) troca por conta
propria, seguindo a lista de pontos em `docs/contrato-api-construtora.md`.

Modo mock (`CONSTRUTORA_API_MOCK=1` no ambiente, ou `mock=True` no
construtor de `ClienteConstrutora`): nunca faz chamada de rede, devolve dados
sinteticos fixos (mesmo formato dos endpoints reais) - pra rodar/testar sem
a construtora disponivel. Nunca ativa sozinho: so com a flag explicita.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date, timedelta

import requests

log = logging.getLogger(__name__)

_TIMEOUT_SEGUNDOS_PADRAO = 5
_CACHE_TTL_SEGUNDOS_PADRAO = 60  # mesmo TTL de app._CACHE_CONSTRUTORA - a API
# de la tem rate limit de 20 req/min/IP (v3.99.14/16 do financeiro-construtora).

_MOCK_TOT_ENTRADAS = 185000.0
_MOCK_TOT_SAIDAS = 132500.0
_MOCK_RESUMO = {
    "status": "ok",
    "tot_entradas": _MOCK_TOT_ENTRADAS,
    "tot_saidas": _MOCK_TOT_SAIDAS,
    "lucro_liquido": _MOCK_TOT_ENTRADAS - _MOCK_TOT_SAIDAS,
    "margem": round((_MOCK_TOT_ENTRADAS - _MOCK_TOT_SAIDAS) / _MOCK_TOT_ENTRADAS * 100, 1),
    # campos da v3.99.90 do financeiro-construtora (valores de exemplo do mock)
    "saldo_caixa": 52300.0,
    "a_receber": 640000.0,
    "lucro_obras_fechadas": 120000.0,
    "obras_fechadas": 1,
    "estoque_a_venda": 900000.0,
    "unidades_a_venda": 3,
}

# candidatas sinteticas (pt-BR) pro mock de contas a vencer - "dias" e
# relativo a hoje, recalculado a cada chamada pra sempre fazer sentido
# (negativo = ja vencida, como o `dias_ate_vencer` real).
_MOCK_CONTAS_CANDIDATAS = [
    {"fornecedor": "Cimento Forte Materiais", "descricao": "Compra de cimento e areia", "valor": 8450.0, "dias": 2},
    {"fornecedor": "Eletrica Ideal Ltda", "descricao": "Fiacao e quadro de distribuicao", "valor": 3120.5, "dias": 9},
    {"fornecedor": None, "descricao": "Aluguel do container de obra", "valor": 1200.0, "dias": -3},
    {"fornecedor": "Madeireira Bom Corte", "descricao": "Forma de madeira", "valor": 640.9, "dias": 21},
]


def _mock_contas(dias: int) -> dict:
    hoje = date.today()
    contas = []
    for c in _MOCK_CONTAS_CANDIDATAS:
        if c["dias"] > dias:
            continue
        vencimento = hoje + timedelta(days=c["dias"])
        contas.append(
            {
                "vencimento": vencimento.isoformat(),
                "valor": c["valor"],
                "fornecedor": c["fornecedor"],
                "descricao": c["descricao"],
                "dias_ate_vencer": c["dias"],
            }
        )
    contas.sort(key=lambda c: c["dias_ate_vencer"])
    return {"status": "ok", "contas": contas}


def _mock_ativo_no_ambiente() -> bool:
    return os.environ.get("CONSTRUTORA_API_MOCK", "").strip().lower() in ("1", "true", "on", "yes")


class ClienteConstrutora:
    """Cliente HTTP da API externa do financeiro-construtora.

    Le `CONSTRUTORA_API_URL`/`CONSTRUTORA_API_KEY` do ambiente A CADA
    chamada (nunca guardado no `__init__`) - mesmo espirito das funcoes
    antigas em `app.py`, pra funcionar com `patch.dict(os.environ, ...)`
    nos testes e pra pegar uma troca de `.env` sem reiniciar o processo.
    Passe `base_url`/`api_key` pro construtor pra fixar (injecao de teste,
    ou pra apontar pra outro ambiente sem mexer em variavel global).

    Cache em memoria por instancia, TTL de 60s por padrao (mesmo cache que
    ja serve de throttle: dentro do TTL, devolve o que ja tem sem bater na
    rede de novo - a API de la tem rate limit de 20 req/min/IP).

    Nunca levanta excecao pro chamador: timeout, erro de rede, HTTP de erro,
    JSON invalido ou API nao configurada viram `None` (mesmo contrato das
    funcoes antigas de `app.py`).
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        mock: bool | None = None,
        timeout: float = _TIMEOUT_SEGUNDOS_PADRAO,
        cache_ttl: float = _CACHE_TTL_SEGUNDOS_PADRAO,
    ):
        self._base_url_fixo = base_url
        self._api_key_fixo = api_key
        self._mock_fixo = mock
        self._timeout = timeout
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, dict]] = {}

    # ---- infra -----------------------------------------------------------

    def _mock_ativo(self) -> bool:
        if self._mock_fixo is not None:
            return bool(self._mock_fixo)
        return _mock_ativo_no_ambiente()

    def _config(self) -> tuple[str | None, str | None]:
        base_url = self._base_url_fixo or os.environ.get("CONSTRUTORA_API_URL")
        api_key = self._api_key_fixo or os.environ.get("CONSTRUTORA_API_KEY")
        return base_url, api_key

    def _cache_get(self, chave: str):
        entrada = self._cache.get(chave)
        if not entrada:
            return None
        timestamp, dados = entrada
        if time.time() - timestamp > self._cache_ttl:
            return None
        return dados

    def _cache_set(self, chave: str, dados) -> None:
        self._cache[chave] = (time.time(), dados)

    def configurado(self) -> bool:
        """True se da pra consultar a API: modo mock ligado OU
        CONSTRUTORA_API_URL e CONSTRUTORA_API_KEY presentes (Fase 7, C1 -
        a rota /api/construtora/resumo do app usa isto)."""
        if self._mock_ativo():
            return True
        base_url, api_key = self._config()
        return bool(base_url and api_key)

    def limpar_cache(self) -> None:
        """So pra teste/depuracao - zera o cache desta instancia."""
        self._cache.clear()

    def _get_cacheado_ou_mock(self, chave: str, gerar_mock):
        """Throttle/cache comum aos dois endpoints, real ou mock."""
        cacheado = self._cache_get(chave)
        if cacheado is not None:
            return cacheado
        dados = gerar_mock() if self._mock_ativo() else None
        if dados is not None:
            self._cache_set(chave, dados)
        return dados

    def _get_real(self, caminho: str, params: dict | None, chave_cache: str) -> dict | None:
        base_url, api_key = self._config()
        if not base_url or not api_key:
            return None
        cacheado = self._cache_get(chave_cache)
        if cacheado is not None:
            return cacheado
        try:
            resp = requests.get(
                f"{base_url}{caminho}",
                headers={"X-API-Key": api_key},
                params=params,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            dados = resp.json()
        except requests.RequestException as exc:
            log.warning("construtora_cliente: falha ao chamar %s: %s", caminho, exc)
            return None
        except ValueError as exc:  # inclui json.JSONDecodeError
            log.warning("construtora_cliente: resposta invalida de %s: %s", caminho, exc)
            return None
        if not isinstance(dados, dict):
            log.warning("construtora_cliente: resposta de %s nao e um objeto JSON", caminho)
            return None
        self._cache_set(chave_cache, dados)
        return dados

    # ---- endpoints (contrato bruto, ver docs/contrato-api-construtora.md) --

    def resumo(self) -> dict | None:
        """`GET /api/resumo`. `None` = nao configurado (sem mock) ou a
        chamada falhou por qualquer motivo."""
        if self._mock_ativo():
            return self._get_cacheado_ou_mock("resumo", lambda: dict(_MOCK_RESUMO))
        return self._get_real("/api/resumo", None, "resumo")

    def contas_a_vencer(self, dias: int = 30) -> dict | None:
        """`GET /api/contas_a_vencer?dias=N`. `None` = nao configurado (sem
        mock) ou a chamada falhou por qualquer motivo. Cache por `dias`
        separado do de `resumo()` (mesmo espirito do `app.py` antigo)."""
        try:
            dias = int(dias)
        except (TypeError, ValueError):
            dias = 30
        chave = f"contas:{dias}"
        if self._mock_ativo():
            return self._get_cacheado_ou_mock(chave, lambda: _mock_contas(dias))
        return self._get_real("/api/contas_a_vencer", {"dias": dias}, chave)

    # ---- API de alto nivel (so o que a decisao do Alex autoriza mostrar) --

    def gastos_do_mes(self) -> float | None:
        """Total de saidas do mes corrente (`tot_saidas` do resumo) - `None`
        se indisponivel (nao configurado, erro de rede, resposta invalida)."""
        dados = self.resumo()
        if not dados or dados.get("status") != "ok":
            return None
        valor = dados.get("tot_saidas")
        return float(valor) if isinstance(valor, (int, float)) else None

    def entradas_do_mes(self) -> float | None:
        """Total de entradas do mes corrente (`tot_entradas` do resumo) -
        `None` se indisponivel."""
        dados = self.resumo()
        if not dados or dados.get("status") != "ok":
            return None
        valor = dados.get("tot_entradas")
        return float(valor) if isinstance(valor, (int, float)) else None

    def proxima_conta(self, com_valor: bool = False) -> dict | None:
        """A conta a pagar mais proxima de vencer (ou ja vencida, se houver
        uma) nos proximos 30 dias: `{"nome": str, "dias": int}` - e
        `"valor"` tambem, se `com_valor=True` (decisao do Alex: o painel
        pessoal so mostra valor de conta quando pedido explicitamente, nunca
        de bandeja). `None` se nao ha nenhuma conta em aberto ou a API esta
        indisponivel."""
        dados = self.contas_a_vencer(dias=30)
        if not dados or dados.get("status") != "ok":
            return None
        contas = dados.get("contas") or []
        if not contas:
            return None
        proxima = contas[0]
        dias_ate = proxima.get("dias_ate_vencer")
        resultado = {
            "nome": proxima.get("fornecedor") or proxima.get("descricao") or "fornecedor não informado",
            "dias": int(dias_ate) if isinstance(dias_ate, (int, float)) else None,
        }
        if com_valor:
            valor = proxima.get("valor")
            resultado["valor"] = float(valor) if isinstance(valor, (int, float)) else None
        return resultado


# ---- instancia padrao / funcoes de modulo (a API que o resto do painel usa) --

_padrao: ClienteConstrutora | None = None


def _cliente_padrao() -> ClienteConstrutora:
    global _padrao
    if _padrao is None:
        _padrao = ClienteConstrutora()
    return _padrao


def gastos_do_mes() -> float | None:
    return _cliente_padrao().gastos_do_mes()


def entradas_do_mes() -> float | None:
    return _cliente_padrao().entradas_do_mes()


def proxima_conta(com_valor: bool = False) -> dict | None:
    return _cliente_padrao().proxima_conta(com_valor=com_valor)


def cliente_padrao() -> ClienteConstrutora:
    """A instancia padrao (a mesma das funcoes de modulo acima) - o app usa
    ela pra compartilhar cache/throttle com gastos_do_mes/proxima_conta."""
    return _cliente_padrao()


def limpar_cache_padrao() -> None:
    """So pra teste - zera o cache da instancia padrao (module-level) entre
    casos, sem precisar recriar o modulo."""
    _cliente_padrao().limpar_cache()
