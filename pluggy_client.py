"""Integracao com a API da Pluggy (agregador de Open Finance Brasil).

So fica ativa quando PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET estao configurados no .env.
Cadastro gratuito para uso pessoal em https://meu.pluggy.ai - veja o README pra mais detalhes.

Endpoints e formatos verificados contra o codigo-fonte do SDK oficial
(github.com/pluggyai/pluggy-node), nao inventados.
"""

import os
import time

import requests

BASE_URL = "https://api.pluggy.ai"

_api_key_cache = {"chave": None, "expira_em": 0}


def configurado() -> bool:
    return bool(os.environ.get("PLUGGY_CLIENT_ID") and os.environ.get("PLUGGY_CLIENT_SECRET"))


def _api_key() -> str:
    agora = time.time()
    if _api_key_cache["chave"] and agora < _api_key_cache["expira_em"]:
        return _api_key_cache["chave"]

    resp = requests.post(
        f"{BASE_URL}/auth",
        json={
            "clientId": os.environ["PLUGGY_CLIENT_ID"],
            "clientSecret": os.environ["PLUGGY_CLIENT_SECRET"],
        },
        timeout=15,
    )
    resp.raise_for_status()
    chave = resp.json()["apiKey"]
    _api_key_cache["chave"] = chave
    # a chave vale ~2h; renova um pouco antes por seguranca
    _api_key_cache["expira_em"] = agora + 100 * 60
    return chave


def _headers() -> dict:
    return {"X-API-KEY": _api_key()}


def create_connect_token() -> str:
    """Token de curta duracao (30min) usado pelo widget PluggyConnect no frontend."""
    resp = requests.post(f"{BASE_URL}/connect_token", headers=_headers(), json={}, timeout=15)
    resp.raise_for_status()
    return resp.json()["accessToken"]


def get_item(item_id: str) -> dict:
    resp = requests.get(f"{BASE_URL}/items/{item_id}", headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_accounts(item_id: str) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}/accounts", headers=_headers(), params={"itemId": item_id}, timeout=15
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


def get_transactions(account_id: str) -> tuple[list[dict], bool]:
    """Devolve (transacoes, truncado). `truncado=True` quando o laco bateu
    no teto de paginas (100) sem a Pluggy parar de mandar `next` - sinal de
    que a busca nao terminou e a lista devolvida NAO e o historico completo
    da conta. Quem chama usa isso pra decidir se pode confiar na lista como
    fonte da verdade pra reconciliar (apagar) transacoes que sumiram - uma
    busca truncada nunca pode apagar nada (ver rotas/f8_banco.py)."""
    # /transactions (page/pageSize) responde 410 ENDPOINT_DEPRECATED desde
    # 2026-09: a Pluggy so aceita /v2/transactions com cursor em `next`.
    transacoes = []
    truncado = False
    url, params = f"{BASE_URL}/v2/transactions", {"accountId": account_id}
    for _ in range(100):
        resp = requests.get(url, headers=_headers(), params=params, timeout=20)
        resp.raise_for_status()
        body = resp.json()
        transacoes.extend(body.get("results", []))
        cursor = body.get("next")
        if not cursor:
            break
        # `next` pode vir como URL pronta ou so o cursor
        if str(cursor).startswith("http"):
            url, params = cursor, None
        else:
            params = {"accountId": account_id, "cursor": cursor}
    else:
        truncado = True
    return transacoes, truncado


def normalizar_transacoes(transacoes_pluggy: list[dict]) -> list[dict]:
    """Converte pro mesmo formato que bank_ofx.parse_transactions ja produz
    (external_id = id da transacao na Pluggy - chave de idempotencia da
    sincronizacao), mais os campos ricos que a Fase 9 passou a guardar
    (estabelecimento/categoria da Pluggy/descricao crua/tipo de operacao/
    estorno). Nao inventa nome de exibicao - isso e financas_descricao.py."""
    normalizadas = []
    for t in transacoes_pluggy:
        merchant = t.get("merchant") or {}
        estabelecimento = merchant.get("businessName") or merchant.get("name")
        descricao = t.get("description") or ""
        normalizadas.append(
            {
                "external_id": t["id"],
                "data": str(t["date"])[:10],
                "valor": t["amount"],
                "descricao": descricao,
                "estabelecimento": estabelecimento,
                "categoria_pluggy": t.get("category"),
                "descricao_original": descricao,
                "tipo_operacao": t.get("type") or t.get("operationType"),
                # A Pluggy nao documenta um campo estavel ligando um estorno
                # a transacao original em /v2/transactions; se um dia vier
                # (ex: "originalTransactionId"), so entao deixa de ser NULL.
                "estorno_de_external_id": t.get("originalTransactionId"),
            }
        )
    return normalizadas
