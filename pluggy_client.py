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


def get_transactions(account_id: str) -> list[dict]:
    transacoes = []
    pagina = 1
    while True:
        resp = requests.get(
            f"{BASE_URL}/transactions",
            headers=_headers(),
            params={"accountId": account_id, "page": pagina, "pageSize": 500},
            timeout=20,
        )
        resp.raise_for_status()
        body = resp.json()
        transacoes.extend(body.get("results", []))
        if pagina >= body.get("totalPages", 1):
            break
        pagina += 1
    return transacoes


def normalizar_transacoes(transacoes_pluggy: list[dict]) -> list[dict]:
    """Converte pro mesmo formato que bank_ofx.parse_transactions ja produz,
    pra reaproveitar db.insert_bank_transactions sem duplicar logica."""
    normalizadas = []
    for t in transacoes_pluggy:
        normalizadas.append(
            {
                "external_id": t["id"],
                "data": str(t["date"])[:10],
                "valor": t["amount"],
                "descricao": t.get("description") or "",
            }
        )
    return normalizadas
