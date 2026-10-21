"""Treino ao vivo (2026-10-21, pedido do Alex): "vou treinar peito" abre a ficha no chat com
caixinha por exercicio; quando tudo e marcado o treino fica registrado; depois ele conta
"o supino foi pra 25" e so aquele exercicio muda na ficha.

Funcoes puras (sem banco): ler/escrever a linha do exercicio, achar a ficha pelo que ele
falou, escolher a proxima da rotacao, trocar a carga de um exercicio.

Formato da linha na ficha (o mesmo do menu, `static/js/secoes/vida/treino.js`):
"nome|series|reps|carga". Ficha antiga/colada no chat e texto livre ("supino reto 4x10
com 20kg") - `ler_exercicio` tira series/reps/carga do texto quando da.
"""

from __future__ import annotations

import re

import vida

_RE_SERIES_REPS = re.compile(r"(\d{1,2})\s*[x×]\s*(\d{1,3}(?:\s*[-a/]\s*\d{1,3})?)", re.I)
_RE_CARGA = re.compile(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*(kg|quilos?|kilos?|lbs?|placas?)\b", re.I)
_RE_SOBRA = re.compile(r"^[\s,;:\-–—]+|[\s,;:\-–—]+$")
_RE_LIGACAO = re.compile(r"\s+(com|de|a)\s*$", re.I)
_PALAVRAS_VAZIAS = {"treino", "de", "do", "da", "e", "o", "a", "hoje", "meu", "minha", "dia"}
_SEP = "|"
MAX_EXERCICIOS = 20


def _limpo(texto) -> str:
    return " ".join(str(texto or "").replace(_SEP, "/").split())


def ler_exercicio(linha: str) -> dict | None:
    """{"nome", "series", "reps", "carga"} (strings, "" quando nao tem). None = linha vazia."""
    linha = (linha or "").strip()
    if not linha:
        return None
    partes = linha.split(_SEP)
    if len(partes) == 4 and partes[0].strip():
        nome, series, reps, carga = (p.strip() for p in partes)
        return {"nome": nome, "series": series, "reps": reps, "carga": carga}
    resto, series, reps, carga = linha, "", "", ""
    m = _RE_SERIES_REPS.search(resto)
    if m:
        series, reps = m.group(1), re.sub(r"\s+", "", m.group(2)).replace("a", "-").replace("/", "-")
        resto = resto[: m.start()] + " " + resto[m.end():]
    m = _RE_CARGA.search(resto)
    if m:
        unidade = m.group(2).lower()
        unidade = "kg" if unidade.startswith(("kg", "quilo", "kilo")) else unidade
        carga = f"{m.group(1).replace(',', '.')} {unidade}"
        resto = resto[: m.start()] + " " + resto[m.end():]
    nome = _RE_LIGACAO.sub("", _RE_SOBRA.sub("", " ".join(resto.split())))
    nome = _RE_SOBRA.sub("", nome)
    if not nome:
        nome = linha
    return {"nome": nome[:1].upper() + nome[1:], "series": series, "reps": reps, "carga": carga}


def escrever_exercicio(ex: dict) -> str:
    return _SEP.join(_limpo(ex.get(c)) for c in ("nome", "series", "reps", "carga"))


def exercicios_da_ficha(texto: str) -> list[dict]:
    saida = []
    for linha in (texto or "").split("\n"):
        ex = ler_exercicio(linha)
        if ex:
            saida.append(ex)
    return saida[:MAX_EXERCICIOS]


def normalizar_ficha(linhas) -> str:
    """Ficha colada no chat -> linhas no formato do menu (assim o menu mostra series/reps/carga
    e a troca de carga acha o exercicio)."""
    if isinstance(linhas, str):
        linhas = linhas.split("\n")
    return "\n".join(escrever_exercicio(ex) for ex in (ler_exercicio(str(l)) for l in linhas or []) if ex)


def _palavras(texto: str) -> set[str]:
    return {p for p in re.split(r"[^a-z0-9]+", vida.normalizar_nome(texto)) if p and p not in _PALAVRAS_VAZIAS}


def achar_ficha(fichas: list[dict], pedido: str | None) -> dict | None:
    """Ficha cujo grupo bate com o que ele falou ("peito", "treino A", "peito e triceps").
    Igual > o grupo inteiro dentro do pedido (ou o contrario) > mais palavras em comum."""
    alvo = vida.normalizar_nome(pedido)
    if not alvo or not fichas:
        return None
    for f in fichas:
        if vida.normalizar_nome(f["grupo"]) == alvo:
            return f
    sem_treino = re.sub(r"^treino\s+", "", alvo)
    for f in fichas:
        g = re.sub(r"^treino\s+", "", vida.normalizar_nome(f["grupo"]))
        if g == sem_treino:
            return f
    pedidas = _palavras(alvo)
    melhor, pontos = None, 0
    for f in fichas:
        comuns = len(pedidas & _palavras(f["grupo"]))
        if comuns > pontos:
            melhor, pontos = f, comuns
    return melhor


def proxima_da_rotacao(fichas: list[dict], ultimo_por_grupo: dict[str, str]) -> dict | None:
    """'Hoje e qual treino?': a ficha feita ha mais tempo (nunca feita vem primeiro, na ordem
    em que aparecem). `ultimo_por_grupo`: {grupo normalizado: data ISO do ultimo treino}."""
    if not fichas:
        return None
    return min(fichas, key=lambda f: ultimo_por_grupo.get(vida.normalizar_nome(f["grupo"])) or "")


def achar_exercicio(exercicios: list[dict], pedido: str | None) -> int | None:
    alvo = vida.normalizar_nome(pedido)
    if not alvo:
        return None
    nomes = [vida.normalizar_nome(e["nome"]) for e in exercicios]
    if alvo in nomes:
        return nomes.index(alvo)
    contem = [i for i, n in enumerate(nomes) if alvo in n or n in alvo]
    if len(contem) == 1:
        return contem[0]
    pedidas = _palavras(alvo)
    pontos = [len(pedidas & _palavras(n)) for n in nomes]
    melhor = max(pontos, default=0)
    if melhor and pontos.count(melhor) == 1:
        return pontos.index(melhor)
    return None


def carga_texto(carga) -> str:
    """'25' -> '25 kg'; '25kg' / '25 kg' / '3 placas' ficam como ele falou (limpo)."""
    if isinstance(carga, bool) or carga is None:
        return ""
    if isinstance(carga, (int, float)):
        carga = f"{carga:g}"
    texto = _limpo(carga)[:20]
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{1,2})?", texto):
        return f"{texto.replace(',', '.')} kg"
    m = re.fullmatch(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*(kg|quilos?|kilos?)", texto, re.I)
    if m:
        return f"{m.group(1).replace(',', '.')} kg"
    return texto


def numero_da_carga(carga: str) -> float | None:
    m = re.match(r"\s*(\d{1,3}(?:[.,]\d{1,2})?)", carga or "")
    return float(m.group(1).replace(",", ".")) if m else None
