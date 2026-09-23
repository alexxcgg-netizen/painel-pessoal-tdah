"""Busca segura de link salvo pelo Alex (artigo/video pra ver depois) pra
extrair titulo e texto e mandar resumir. Como e o SERVIDOR que busca a URL,
so aceita http/https pra endereco publico - nunca rede interna/localhost (senao
um link malicioso faria o painel acessar coisa da propria maquina).

Defesas (achadas numa revisao independente):
- o host e resolvido UMA vez, validado, e a conexao vai direto pro IP validado
  (com SNI e certificado conferidos no nome original) - DNS que responde
  publico na checagem e 127.0.0.1 na conexao nao passa;
- URL com usuario/senha ou barra invertida e recusada (parsers diferentes
  enxergam hosts diferentes nelas);
- prazo total de leitura (servidor que pinga 1 byte/s nao prende o painel),
  sem compressao (nada de "bomba" gzip) e tudo linear no parsing do HTML."""

import html
import ipaddress
import re
import socket
import time
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import parse_url

TAMANHO_MAXIMO = 1_500_000
MAX_REDIRECIONAMENTOS = 3
TIMEOUT = (5, 10)  # conectar, cada leitura
PRAZO_TOTAL = 20  # segundos pra pagina inteira
VERIFICAR_TLS = True  # testes apontam pra um CA proprio

_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_IPV4_COMPATIVEL = ipaddress.ip_network("::/96")


class LinkInvalido(ValueError):
    pass


def _ip_permitido(ip: ipaddress._BaseAddress) -> bool:
    if ip.version == 6 and (ip.ipv4_mapped or ip in _NAT64 or ip in _IPV4_COMPATIVEL):
        return False
    return ip.is_global and not ip.is_multicast


def _resolver(host: str) -> list[str]:
    """IPs do host, TODOS publicos - senao LinkInvalido."""
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, ValueError, OSError):
        raise LinkInvalido("nao achei esse endereco")
    ips = []
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0].split("%")[0])
        except ValueError:
            raise LinkInvalido("esse endereco nao e publico")
        if not _ip_permitido(ip):
            raise LinkInvalido("esse endereco nao e publico")
        ips.append(str(ip))
    if not ips:
        raise LinkInvalido("nao achei esse endereco")
    return ips


def _host_publico(host: str) -> bool:
    try:
        _resolver(host)
    except LinkInvalido:
        return False
    return True


def _idna(host: str | None) -> str:
    try:
        return (host or "").lower().encode("idna").decode("ascii")
    except UnicodeError:
        raise LinkInvalido("link invalido")


def _alvo(url) -> tuple:
    """(partes do urllib3, ip validado) - ou LinkInvalido."""
    if not isinstance(url, str) or len(url) > 2000:
        raise LinkInvalido("link invalido")
    url = url.strip()
    if "\\" in url or any(ord(c) < 33 for c in url):
        raise LinkInvalido("link invalido")
    try:
        partes = parse_url(url)
        padrao = urlparse(url)
        porta_padrao = padrao.port
    except ValueError:
        raise LinkInvalido("link invalido")
    if partes.scheme not in ("http", "https") or not partes.host:
        raise LinkInvalido("so link http ou https")
    if partes.auth or padrao.username is not None:
        raise LinkInvalido("link com usuario/senha nao")
    host = partes.host.strip("[]").lower()
    # os dois parsers tem que concordar sobre o host e a porta (dominio com
    # acento comparado em punycode, que e o que vai pro DNS)
    if porta_padrao != partes.port or _idna(padrao.hostname) != _idna(host):
        raise LinkInvalido("link invalido")
    return partes, _resolver(host)[0]


def validar_url(url) -> str:
    _alvo(url)
    return url.strip()


class _AdaptadorIpFixo(HTTPAdapter):
    """Conecta no IP ja validado mas faz o TLS (SNI + certificado) no nome
    original do site."""

    def __init__(self, host: str):
        self._host = host
        super().__init__(max_retries=0)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        pool_kwargs.update(server_hostname=self._host, assert_hostname=self._host)
        super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)


def _pedir(partes, ip: str):
    host = partes.host.strip("[]")
    alvo_ip = f"[{ip}]" if ":" in ip else ip
    porta = f":{partes.port}" if partes.port else ""
    sessao = requests.Session()
    sessao.trust_env = False  # proxy do ambiente resolveria o nome por conta propria
    sessao.mount("https://", _AdaptadorIpFixo(host))
    cabecalho_host = f"[{host}]" if ":" in host else host
    resposta = sessao.get(
        f"{partes.scheme}://{alvo_ip}{porta}{partes.request_uri}",
        timeout=TIMEOUT,
        stream=True,
        allow_redirects=False,
        verify=VERIFICAR_TLS,
        headers={
            "Host": cabecalho_host + porta,
            "User-Agent": "Mozilla/5.0 (painel pessoal)",
            "Accept-Language": "pt-BR,pt;q=0.9",
            "Accept-Encoding": "identity",
        },
    )
    return sessao, resposta


def _ler(resposta, prazo: float) -> bytes:
    ler = getattr(resposta.raw, "read1", None)
    pedacos, total = [], 0
    while total <= TAMANHO_MAXIMO:
        if time.monotonic() > prazo:
            raise LinkInvalido("a pagina demorou demais")
        pedaco = ler(65536) if ler else resposta.raw.read(8192)
        if not pedaco:
            break
        pedacos.append(pedaco)
        total += len(pedaco)
    return b"".join(pedacos)[:TAMANHO_MAXIMO]


def _decodificar(corpo: bytes, content_type: str) -> str:
    achado = re.search(r"charset=[\"']?([\w.:-]{1,40})", content_type or "", re.IGNORECASE)
    if not achado:
        achado = re.search(rb"<meta[^<>]{0,200}?charset=[\"']?([\w.:-]{1,40})", corpo[:8192], re.IGNORECASE)
    codificacao = achado.group(1) if achado else "utf-8"
    if isinstance(codificacao, bytes):
        codificacao = codificacao.decode("ascii", "replace")
    try:
        return corpo.decode(codificacao, errors="replace")
    except LookupError:
        return corpo.decode("utf-8", errors="replace")


def baixar_pagina(url: str) -> str:
    """HTML da pagina (ate 1,5MB, no maximo 20s), seguindo no maximo 3
    redirecionamentos e validando o destino de cada um."""
    atual = url
    prazo = time.monotonic() + PRAZO_TOTAL
    for _ in range(MAX_REDIRECIONAMENTOS + 1):
        partes, ip = _alvo(atual)
        sessao, resposta = _pedir(partes, ip)
        try:
            if resposta.is_redirect:
                try:
                    atual = urljoin(atual, resposta.headers.get("Location", ""))
                except ValueError:
                    raise LinkInvalido("redirecionamento invalido")
                continue
            resposta.raise_for_status()
            if resposta.headers.get("Content-Encoding", "identity").strip().lower() not in ("", "identity"):
                raise LinkInvalido("pagina compactada")
            return _decodificar(_ler(resposta, prazo), resposta.headers.get("Content-Type", ""))
        finally:
            resposta.close()
            sessao.close()
    raise LinkInvalido("redirecionamentos demais")


# ---- extracao (tudo linear: HTML malicioso sem fechar tag nao trava a CPU) ----

_TAG_META = re.compile(r"<meta\b[^<>]{0,2000}>", re.IGNORECASE)
_ATRIBUTO = re.compile(r"([\w:-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')")
_ABRE_BLOCO = re.compile(r"<(script|style|noscript|svg)\b", re.IGNORECASE)


def _metas(pagina: str) -> dict:
    achados = {}
    for tag in _TAG_META.finditer(pagina):
        atributos = {m.group(1).lower(): m.group(2) if m.group(2) is not None else m.group(3)
                     for m in _ATRIBUTO.finditer(tag.group(0))}
        nome = (atributos.get("property") or atributos.get("name") or "").lower()
        if nome and "content" in atributos and nome not in achados:
            achados[nome] = html.unescape(atributos["content"]).strip()
    return achados


def _meta(pagina: str, nome: str) -> str | None:
    return _metas(pagina).get(nome.lower()) or None


def _sem_blocos(pagina: str) -> str:
    """Tira script/style/noscript/svg. Bloco sem fechamento corta o resto."""
    baixa = pagina.lower()
    partes, pos = [], 0
    while True:
        achado = _ABRE_BLOCO.search(pagina, pos)
        if not achado:
            partes.append(pagina[pos:])
            break
        partes.append(pagina[pos:achado.start()])
        fim = baixa.find(f"</{achado.group(1).lower()}", achado.end())
        if fim == -1:
            break
        fecha = baixa.find(">", fim)
        pos = len(pagina) if fecha == -1 else fecha + 1
    return " ".join(partes)


def extrair(pagina: str) -> dict:
    """Titulo e texto legivel (sem script/style/tags), cortado em 8 mil
    caracteres - suficiente pro resumo, barato pro modelo."""
    metas = _metas(pagina)
    titulo = metas.get("og:title")
    if not titulo:
        achado = re.search(r"<title\b[^<>]{0,200}>([^<]{0,500})", pagina, re.IGNORECASE)
        titulo = html.unescape(achado.group(1)).strip() if achado else None
    descricao = metas.get("og:description") or metas.get("description") or ""
    corpo = re.sub(r"<[^<>]*>", " ", _sem_blocos(pagina))
    texto = re.sub(r"\s+", " ", html.unescape(corpo)).strip()
    return {
        "titulo": (titulo or "")[:200] or None,
        "texto": f"{descricao}\n\n{texto}".strip()[:8000],
    }
