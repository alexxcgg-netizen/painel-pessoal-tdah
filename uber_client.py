"""Integracao com a Uber Ride Requests API (v1.2) - pede uma corrida de
verdade pra propria conta do Alex, nunca pra outra pessoa.

So fica ativo quando UBER_CLIENT_ID/UBER_CLIENT_SECRET existem no .env E ha
um token OAuth valido guardado (tabela 'configuracoes' do banco, chaves
uber_access_token/uber_refresh_token/uber_token_expira_em - ver app.py pra
onde isso e lido/renovado). O fluxo de autorizacao (login do Alex na conta
Uber dele) fica nas rotas /uber/conectar e /uber/callback, em app.py.

IMPORTANTE sobre risco: este modulo nunca decide sozinho pedir uma corrida.
`estimar_corrida` e so leitura (mostra preco, nao gasta nada) - a corrida so
sai de fato com `pedir_corrida`, chamada em app.py apenas depois do Alex
confirmar explicitamente o preco mostrado (ver fluxo de uber_pedidos). O
"fare_id" devolvido pela estimativa trava o preco cobrado - pedir a corrida
com esse fare_id nao pode cobrar um valor diferente do que foi mostrado.

Os nomes de campo abaixo vem da documentacao/SDK oficial da Uber (Ride
Requests API v1.2) conferidos antes de escrever - mas como nao havia uma
chave de API real disponivel pra testar contra o servico de verdade nesta
sessao, isso precisa de uma verificacao rapida assim que o Alex conectar a
conta real dele (rode os testes de novo depois, e confira o primeiro pedido
de verdade com cuidado antes de confiar de olhos fechados)."""

import os
from urllib.parse import urlencode

import requests

AUTHORIZE_URL = "https://login.uber.com/oauth/v2/authorize"
TOKEN_URL = "https://login.uber.com/oauth/v2/token"
API_BASE = "https://api.uber.com/v1.2"

# 'request' e o scope privilegiado que permite pedir corrida de verdade -
# em desenvolvimento (antes do Alex publicar o app pra outros usuarios, o
# que nunca vai acontecer aqui - e uso pessoal) isso funciona pra propria
# conta do Alex sem precisar de aprovacao de producao da Uber.
SCOPES = "request profile"


def configurado() -> bool:
    return bool(os.environ.get("UBER_CLIENT_ID")) and bool(os.environ.get("UBER_CLIENT_SECRET"))


def url_autorizacao(redirect_uri: str) -> str:
    """Monta o link que o Alex abre pra logar na propria conta Uber e
    autorizar o app - primeiro passo do OAuth, feito manualmente uma vez."""
    params = {
        "client_id": os.environ["UBER_CLIENT_ID"],
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def trocar_codigo_por_token(codigo: str, redirect_uri: str) -> dict:
    """Segundo passo do OAuth: troca o codigo que a Uber manda de volta (no
    redirect_uri) por um access_token + refresh_token de verdade."""
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": os.environ["UBER_CLIENT_ID"],
            "client_secret": os.environ["UBER_CLIENT_SECRET"],
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": codigo,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def renovar_token(refresh_token: str) -> dict:
    """O access_token expira depois de um tempo - usa o refresh_token (esse
    dura bem mais) pra pegar um novo sem o Alex precisar logar de novo."""
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": os.environ["UBER_CLIENT_ID"],
            "client_secret": os.environ["UBER_CLIENT_SECRET"],
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def produto_padrao(lat: float, lng: float, access_token: str) -> str:
    """Pega o primeiro produto Uber disponivel nesse local (tipicamente o
    mais simples/barato, tipo UberX) - usado como padrao quando o Alex nao
    especifica qual tipo de carro quer."""
    resp = requests.get(
        f"{API_BASE}/products",
        params={"latitude": lat, "longitude": lng},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    resp.raise_for_status()
    produtos = resp.json().get("products", [])
    if not produtos:
        raise ValueError("nenhum produto Uber disponível nesse local")
    return produtos[0]["product_id"]


def estimar_corrida(
    origem_lat: float,
    origem_lng: float,
    destino_lat: float,
    destino_lng: float,
    product_id: str,
    access_token: str,
) -> dict:
    """So leitura - nao pede corrida, nao gasta nada. Devolve o fare_id (o
    "cupom" que trava o preco) junto com o preco em texto e a previsao de
    quanto tempo o carro demora pra chegar."""
    resp = requests.post(
        f"{API_BASE}/requests/estimate",
        json={
            "product_id": product_id,
            "start_latitude": origem_lat,
            "start_longitude": origem_lng,
            "end_latitude": destino_lat,
            "end_longitude": destino_lng,
        },
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    dados = resp.json()
    fare = dados.get("fare") or {}
    return {
        "fare_id": fare.get("fare_id"),
        "preco_texto": fare.get("display") or "preço não informado",
        "eta_minutos": dados.get("pickup_estimate"),
    }


def pedir_corrida(
    origem_lat: float,
    origem_lng: float,
    destino_lat: float,
    destino_lng: float,
    product_id: str,
    fare_id: str,
    access_token: str,
) -> dict:
    """Pede a corrida de verdade - so chame isso depois de confirmacao
    explicita do Alex sobre o preco mostrado por `estimar_corrida`. O
    fare_id trava o preco cobrado no valor ja mostrado."""
    resp = requests.post(
        f"{API_BASE}/requests",
        json={
            "product_id": product_id,
            "start_latitude": origem_lat,
            "start_longitude": origem_lng,
            "end_latitude": destino_lat,
            "end_longitude": destino_lng,
            "fare_id": fare_id,
        },
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    dados = resp.json()
    return {"request_id": dados.get("request_id"), "status": dados.get("status")}
