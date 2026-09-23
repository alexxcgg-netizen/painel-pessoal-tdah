"""Busca segura de link salvo pelo Alex (artigo/video pra ver depois) pra
extrair titulo e texto e mandar resumir. Como e o SERVIDOR que busca a URL,
so aceita http/https pra endereco publico - nunca rede interna/localhost (senao
um link malicioso faria o painel acessar coisa da propria maquina)."""

import html
import ipaddress
import re
import socket
from urllib.parse import urljoin, urlparse

import requests

TAMANHO_MAXIMO = 1_500_000
MAX_REDIRECIONAMENTOS = 3
TIMEOUT = 10


class LinkInvalido(ValueError):
    pass


def _host_publico(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global or ip.is_multicast:
            return False
    return bool(infos)


def validar_url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 2000:
        raise LinkInvalido("link invalido")
    url = url.strip()
    partes = urlparse(url)
    if partes.scheme not in ("http", "https") or not partes.hostname:
        raise LinkInvalido("so link http ou https")
    if not _host_publico(partes.hostname):
        raise LinkInvalido("esse endereco nao e publico")
    return url


def baixar_pagina(url: str) -> str:
    """HTML da pagina (ate 1,5MB), seguindo no maximo 3 redirecionamentos e
    validando o destino de cada um."""
    atual = validar_url(url)
    for _ in range(MAX_REDIRECIONAMENTOS + 1):
        resposta = requests.get(
            atual,
            timeout=TIMEOUT,
            stream=True,
            allow_redirects=False,
            headers={"User-Agent": "Mozilla/5.0 (painel pessoal)", "Accept-Language": "pt-BR,pt;q=0.9"},
        )
        if resposta.is_redirect:
            destino = resposta.headers.get("Location", "")
            resposta.close()
            atual = validar_url(urljoin(atual, destino))
            continue
        resposta.raise_for_status()
        corpo = b""
        for pedaco in resposta.iter_content(65536):
            corpo += pedaco
            if len(corpo) > TAMANHO_MAXIMO:
                break
        resposta.close()
        return corpo.decode(resposta.encoding or "utf-8", errors="replace")
    raise LinkInvalido("redirecionamentos demais")


def _meta(pagina: str, nome: str) -> str | None:
    padrao = rf'<meta[^>]+(?:property|name)=["\']{re.escape(nome)}["\'][^>]*content=["\']([^"\']*)["\']'
    achado = re.search(padrao, pagina, re.IGNORECASE)
    if not achado:
        padrao = rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']{re.escape(nome)}["\']'
        achado = re.search(padrao, pagina, re.IGNORECASE)
    return html.unescape(achado.group(1)).strip() if achado else None


def extrair(pagina: str) -> dict:
    """Titulo e texto legivel (sem script/style/tags), cortado em 8 mil
    caracteres - suficiente pro resumo, barato pro modelo."""
    titulo = _meta(pagina, "og:title")
    if not titulo:
        achado = re.search(r"<title[^>]*>(.*?)</title>", pagina, re.IGNORECASE | re.DOTALL)
        titulo = html.unescape(achado.group(1)).strip() if achado else None
    descricao = _meta(pagina, "og:description") or _meta(pagina, "description") or ""
    corpo = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", pagina, flags=re.IGNORECASE | re.DOTALL)
    corpo = re.sub(r"<[^>]+>", " ", corpo)
    texto = re.sub(r"\s+", " ", html.unescape(corpo)).strip()
    return {
        "titulo": (titulo or "")[:200] or None,
        "texto": f"{descricao}\n\n{texto}".strip()[:8000],
    }
