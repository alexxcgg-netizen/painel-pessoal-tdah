"""Manchetes recentes por assunto/lugar, via o feed RSS publico do Google
News - gratuito, sem chave, sem cadastro. So usado sob demanda (o Alex
pergunta no chat, ex: "tem noticia de Brusque?") - nunca notificacao
proativa, decisao dele pra nao virar ruido automatico.

Erro de rede ou resposta invalida nunca derruba quem chamou - devolve lista
vazia e quem usa (a IA, na resposta) decide o que dizer."""

import xml.etree.ElementTree as ET

import requests

URL_BUSCA = "https://news.google.com/rss/search"


def buscar_manchetes(termo: str, limite: int = 5) -> list[dict]:
    """Busca as manchetes mais recentes pro termo (ex: "Brusque SC") - devolve
    ate `limite` itens, mais recente primeiro (ordem que o proprio feed ja
    devolve): [{"titulo", "fonte", "link", "publicado_em"}, ...]. Lista
    vazia se o termo for vazio, a rede falhar, ou a resposta vier
    malformada - nunca levanta excecao."""
    termo = (termo or "").strip()
    if not termo:
        return []
    try:
        resposta = requests.get(
            URL_BUSCA,
            params={"q": termo, "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"},
            timeout=10,
        )
        resposta.raise_for_status()
        raiz = ET.fromstring(resposta.content)
    except (requests.RequestException, ET.ParseError):
        return []

    itens = []
    for item in raiz.findall(".//item")[:limite]:
        titulo = (item.findtext("title") or "").strip()
        if not titulo:
            continue
        link = (item.findtext("link") or "").strip()
        publicado_em = (item.findtext("pubDate") or "").strip()
        fonte_el = item.find("source")
        fonte = fonte_el.text.strip() if fonte_el is not None and fonte_el.text else None
        # o titulo do feed vem como "Manchete - Nome da Fonte" (redundante
        # com o proprio elemento <source>) - tira o sufixo repetido
        if fonte and titulo.endswith(f" - {fonte}"):
            titulo = titulo[: -(len(fonte) + 3)].strip()
        itens.append({"titulo": titulo, "fonte": fonte, "link": link, "publicado_em": publicado_em})
    return itens
