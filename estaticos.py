"""Versão de cada arquivo de /static/ e gzip das respostas de texto (2026-11-05, leva "perfeição").

Por quê: medido nessa data (tests/medir_tempos.py, banco de verdade copiado), as 131 rotas GET somam ~650 ms
quentes; o código do servidor já é rápido. O que pesava ao abrir o app era a REDE: ~220 arquivos de CSS/JS
(106 <script>, 15 <link> e 99 @import no fase7.css) revalidados um a um a cada abertura (o Flask serve
/static/ com "no-cache" + ETag e o service worker ia à rede primeiro), cada um uma ida e volta pelo Tailscale.
No app nativo (WKWebView sem App-Bound Domains) o service worker nem roda, então só o cache HTTP ajuda lá.

O que este módulo faz (tudo ligado por `instalar(app)`, no fim de app.py):
1. Página HTML: todo src/href="/static/..." ganha "?v=<impressão do conteúdo>".
2. /static/<arquivo>?v=<impressão ATUAL> sai com "immutable" de 1 ano: Safari, PWA e WKWebView nem perguntam
   de novo. Mudou o arquivo, muda a impressão, muda a URL - nada fica velho. Sem ?v (ou com ?v que não é o
   atual), igual antes: no-cache + ETag.
3. CSS com @import (o fase7.css) sai reescrito com o ?v de cada camada, e a impressão dele inclui a das
   camadas: mexer numa camada muda a URL do fase7.css também.
4. Cabeçalho X-Versao em toda resposta de /static/ que existe: o service worker compara com o ?v pedido e
   serve a cópia guardada sem ir à rede (static/service-worker.js, v102).
5. gzip em resposta de texto de 1 KB pra cima quando o navegador aceita (a página tem ~180 KB e vira ~25 KB).
   Fluxo (SSE do chat, /api/eventos) e download de arquivo fora de /static/ nunca passam pelo gzip.

Impressão = 12 primeiros hex do sha1 do conteúdo, refeita só quando muda data/tamanho do arquivo; a versão de
cada URL vale 2 s em memória (editar um CSS com o painel no ar aparece na próxima abertura).
"""

import gzip
import hashlib
import os
import posixpath
import re
import time

from flask import current_app, request
from werkzeug.security import safe_join

UM_ANO = 31536000
VALIDADE_S = 2.0
MINIMO_GZIP = 1024
COMPRIMIVEIS = {
    "text/html",
    "text/css",
    "text/plain",
    "text/csv",
    "text/javascript",
    "application/javascript",
    "application/json",
    "application/manifest+json",
    "image/svg+xml",
}

RE_ATRIBUTO = re.compile(r'(\b(?:src|href)=")(/static/[^"?#]+)(")')
RE_IMPORT = re.compile(r"""@import\s+url\(\s*(["']?)([^"')]+)\1\s*\)""")

_impressoes = {}  # caminho -> ((mtime_ns, tamanho), impressão)
_fontes_css = {}  # caminho -> ((mtime_ns, tamanho), texto ou None quando não tem @import)
_gzip_arquivos = {}  # caminho -> ((mtime_ns, tamanho), bytes gzip ou None quando não compensa)
_versoes = {}  # url -> (instante, versão ou None)


def limpar():
    """Esquece tudo o que foi calculado (testes que trocam arquivo e precisam da versão nova na hora)."""
    for memo in (_impressoes, _fontes_css, _gzip_arquivos, _versoes):
        memo.clear()


def _assinatura(caminho):
    st = os.stat(caminho)
    return (st.st_mtime_ns, st.st_size)


def _caminho(url):
    """/static/css/x.css -> caminho no disco (None se sai da pasta ou não existe)."""
    if not url.startswith("/static/"):
        return None
    caminho = safe_join(current_app.static_folder, url[len("/static/") :])
    if not caminho or not os.path.isfile(caminho):
        return None
    return caminho


def impressao_arquivo(caminho):
    try:
        assinatura = _assinatura(caminho)
    except OSError:
        return None
    guardada = _impressoes.get(caminho)
    if guardada and guardada[0] == assinatura:
        return guardada[1]
    h = hashlib.sha1()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 16), b""):
            h.update(bloco)
    impressao = h.hexdigest()[:12]
    _impressoes[caminho] = (assinatura, impressao)
    return impressao


def _fonte_css(caminho):
    """Texto do CSS se ele tem @import; None se não tem (a maioria)."""
    assinatura = _assinatura(caminho)
    guardada = _fontes_css.get(caminho)
    if guardada and guardada[0] == assinatura:
        return guardada[1]
    with open(caminho, encoding="utf-8") as f:
        texto = f.read()
    fonte = texto if "@import" in texto else None
    _fontes_css[caminho] = (assinatura, fonte)
    return fonte


def css_reescrito(url, caminho, _pilha=()):
    """(texto com ?v em cada @import local, impressão que inclui as camadas) - None se o CSS não tem @import."""
    texto = _fonte_css(caminho)
    if texto is None:
        return None
    pasta_url = posixpath.dirname(url)
    camadas = []

    def trocar(m):
        alvo = m.group(2).strip()
        if alvo.startswith(("http:", "https:", "//", "data:")):
            return m.group(0)
        absoluto = alvo if alvo.startswith("/") else posixpath.normpath(posixpath.join(pasta_url, alvo))
        absoluto = absoluto.split("?", 1)[0].split("#", 1)[0]
        versao = None if absoluto in _pilha else versao_url(absoluto, _pilha + (url,))
        if not versao:
            return m.group(0)
        camadas.append(versao)
        return f'@import url("{absoluto}?v={versao}")'

    novo = RE_IMPORT.sub(trocar, texto)
    propria = impressao_arquivo(caminho) or ""
    junta = hashlib.sha1((propria + "|" + ",".join(camadas)).encode()).hexdigest()[:12]
    return novo, junta


def versao_url(url, _pilha=()):
    """Impressão atual de /static/... (None se o arquivo não existe)."""
    agora = time.monotonic()
    guardada = _versoes.get(url)
    if guardada and agora - guardada[0] < VALIDADE_S:
        return guardada[1]
    caminho = _caminho(url)
    versao = None
    if caminho:
        reescrito = css_reescrito(url, caminho, _pilha) if caminho.endswith(".css") else None
        versao = reescrito[1] if reescrito else impressao_arquivo(caminho)
    _versoes[url] = (agora, versao)
    return versao


def versionar_html(html):
    """Todo src/href="/static/..." ganha ?v=<impressão> (o que não existe fica como está)."""

    def trocar(m):
        versao = versao_url(m.group(2))
        if not versao:
            return m.group(0)
        return f"{m.group(1)}{m.group(2)}?v={versao}{m.group(3)}"

    return RE_ATRIBUTO.sub(trocar, html)


def _gzip_do_arquivo(caminho):
    assinatura = _assinatura(caminho)
    guardado = _gzip_arquivos.get(caminho)
    if guardado and guardado[0] == assinatura:
        return guardado[1]
    with open(caminho, "rb") as f:
        dados = f.read()
    gz = gzip.compress(dados, compresslevel=6, mtime=0) if len(dados) >= MINIMO_GZIP else None
    if gz is not None and len(gz) >= len(dados):
        gz = None
    _gzip_arquivos[caminho] = (assinatura, gz)
    return gz


def _servir_estatico(original):
    def static_versionado(filename):
        res = original(filename=filename)
        url = "/static/" + filename
        caminho = _caminho(url)
        if not caminho or res.status_code not in (200, 304):
            return res
        reescrito = css_reescrito(url, caminho) if caminho.endswith(".css") else None
        if reescrito:
            texto, versao = reescrito
            res.close()
            res = current_app.response_class(texto, mimetype="text/css")
            res.set_etag(versao)
            res = res.make_conditional(request)
        else:
            versao = versao_url(url)
        if not versao:
            return res
        res.headers["X-Versao"] = versao
        if request.args.get("v") == versao:
            res.headers["Cache-Control"] = f"public, max-age={UM_ANO}, immutable"
        return res

    return static_versionado


def _depois(res):
    """Versiona a página e comprime o que é texto. Nunca derruba a resposta: erro aqui devolve ela intacta."""
    try:
        return _acabar(res)
    except Exception:  # noqa: BLE001 - otimização; a resposta sem ela continua certa
        current_app.logger.warning("estaticos: resposta sem versão/gzip em %s", request.path, exc_info=True)
        return res


def _acabar(res):
    if request.method != "GET" or res.status_code != 200:
        return res
    tipo = res.mimetype or ""
    arquivo_estatico = request.endpoint == "static"
    if res.direct_passthrough or res.is_streamed:
        if not arquivo_estatico:
            return res  # fluxo (SSE do chat, eventos) ou download: passa direto
    elif tipo == "text/html":
        html = res.get_data(as_text=True)
        if "/static/" in html:
            novo = versionar_html(html)
            if novo != html:
                res.set_data(novo)
    if tipo not in COMPRIMIVEIS or "Content-Encoding" in res.headers:
        return res
    if "gzip" not in (request.headers.get("Accept-Encoding") or "").lower():
        return res
    if res.direct_passthrough or res.is_streamed:
        caminho = _caminho(request.path)
        gz = _gzip_do_arquivo(caminho) if caminho else None
        if gz is None:
            return res
        res.close()
        res.direct_passthrough = False
        res.set_data(gz)
    else:
        dados = res.get_data()
        if len(dados) < MINIMO_GZIP:
            return res
        gz = gzip.compress(dados, compresslevel=6, mtime=0)
        if len(gz) >= len(dados):
            return res
        res.set_data(gz)
    res.headers["Content-Encoding"] = "gzip"
    res.headers.pop("Accept-Ranges", None)
    res.vary.add("Accept-Encoding")
    etag, fraca = res.get_etag()
    if etag and not fraca:
        res.set_etag(etag, weak=True)
    return res


def instalar(app):
    app.view_functions["static"] = _servir_estatico(app.view_functions["static"])
    app.after_request(_depois)
