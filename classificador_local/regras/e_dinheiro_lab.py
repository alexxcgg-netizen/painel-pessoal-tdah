"""Regras locais do Grupo E (Dinheiro, Laboratorio v4, 30/10/2026). Sem IA.

1. Cupom vira itens: o Alex cola (ou o Atalho do iPhone manda por /api/atalho/capturar) o LINK que o QR do
   cupom fiscal abre (https + *.gov.br) -> `nfce.ler_do_texto` -> card `cupom_itens`.
2. "olha as contas do e-mail" / "varre meu e-mail": roda o cacador de contas agora (`email_contas`) e
   mostra o card `contas_email`. Desligado sem EMAIL_IMAP_* no .env.
3. "quanto eu gasto com besteira" (so besteira/suplemento/limpeza - "comida" fica com a IA): soma por
   categoria dos cupons lidos nos ultimos 30 dias.

`casar` so olha texto (regex) - a rede (SEFAZ/IMAP) so acontece no `executar`.
Dinheiro PESSOAL do Alex. Nunca toca a construtora.
"""

from __future__ import annotations

import re
import time
from datetime import datetime

import cards
import email_contas
import nfce

_RE_EMAIL = re.compile(
    r"(?:\b(?:contas?|boletos?|faturas?)\b.{0,40}\b(?:e-?mail|gmail|caixa de entrada)\b|"
    r"\b(?:varre|varrer|olha|v[eê]|confere|checa)\b.{0,25}\b(?:e-?mail|gmail)\b.{0,25}\b(?:contas?|boletos?|faturas?)\b|"
    r"\b(?:varre|varrer)\b.{0,15}\b(?:o\s+)?(?:meu\s+)?e-?mail\b)",
    re.I | re.S,
)
_RE_QUANTO = re.compile(
    r"quanto\s+(?:eu\s+)?(?:gast(?:ei|o|amos)|sa[ií]u)\s+(?:com|em|de|na|no)\s+(besteiras?|suplementos?|limpeza)\b", re.I
)
_CATEGORIA = {"besteira": "Besteira", "besteiras": "Besteira", "suplemento": "Suplemento", "suplementos": "Suplemento", "limpeza": "Limpeza"}


def casar(texto: str) -> dict | None:
    if nfce.extrair(texto):
        return {"acao": "ler_cupom", "parametros": {"texto": texto[:2000]}}
    m = _RE_QUANTO.search(texto)
    if m and len(texto) < 160:
        return {"acao": "gasto_por_categoria", "parametros": {"categoria": _CATEGORIA[m.group(1).lower()]}}
    if _RE_EMAIL.search(texto) and len(texto) < 160:
        return {"acao": "contas_do_email", "parametros": {}}
    return None


def _ms(t0: float) -> int:
    return int(round((time.perf_counter() - t0) * 1000))


def executar(conn, parametros: dict) -> dict | None:
    if "texto" in parametros:
        return _cupom(conn, parametros["texto"])
    if "categoria" in parametros:
        return _por_categoria(conn, parametros["categoria"])
    return _contas(conn)


def _cupom(conn, texto: str) -> dict:
    t0 = time.perf_counter()
    try:
        cupom = nfce.ler_do_texto(conn, texto)
    except nfce.NfceErro as e:
        return {"cards": [], "resumo_texto": str(e), "passos": [
            {"modulo": "Finanças", "descricao": "Tentou ler o cupom fiscal", "ms": _ms(t0), "erro": True}]}
    card = cards.card_cupom_itens(cupom)
    if not card:
        return {"cards": [], "resumo_texto": "Li a nota, mas não achei itens nela.", "passos": [
            {"modulo": "Finanças", "descricao": "Leu o cupom fiscal", "ms": _ms(t0), "erro": True}]}
    n = card["data"]["qtd_itens"]
    return {
        "cards": [card],
        "resumo_texto": f"Li o cupom: {n} {'item' if n == 1 else 'itens'}, separei por categoria. Quer registrar como gasto?",
        "passos": [{"modulo": "Finanças", "descricao": f"Leu o cupom fiscal ({n} itens)", "ms": _ms(t0)}],
    }


def _por_categoria(conn, categoria: str) -> dict:
    t0 = time.perf_counter()
    r = nfce.total_por_categoria(conn, categoria, 30)
    if not r["cupons"]:
        texto = f"Ainda não li nenhum cupom com {categoria.lower()} nos últimos 30 dias. Me manda o link do QR dos cupons que eu vou separando."
    else:
        v = f"{r['total']:.2f}".replace(".", ",")
        texto = (f"Nos cupons que li dos últimos 30 dias: R$ {v} em {categoria.lower()} "
                 f"({r['itens']} {'item' if r['itens'] == 1 else 'itens'} em {r['cupons']} {'cupom' if r['cupons'] == 1 else 'cupons'}).")
    return {"cards": [], "resumo_texto": texto, "passos": [
        {"modulo": "Finanças", "descricao": f"Somou {categoria.lower()} nos cupons", "ms": _ms(t0)}]}


def _contas(conn) -> dict:
    t0 = time.perf_counter()
    agora = datetime.now()
    if not email_contas.configurado():
        return {"cards": [], "resumo_texto": "O caçador de contas está desligado: falta ligar o e-mail no .env do painel (o passo a passo tá no briefing do Grupo E).",
                "passos": [{"modulo": "Contas", "descricao": "Caçador de contas desligado", "ms": _ms(t0)}]}
    r = email_contas.varrer(conn, agora, forcar=True)
    if r["erro"]:
        return {"cards": [], "resumo_texto": r["erro"], "passos": [
            {"modulo": "Contas", "descricao": "Varreu o e-mail", "ms": _ms(t0), "erro": True}]}
    card = cards.card_contas_email(email_contas.pendentes(conn), agora.date(), r["lidos"], agora.strftime("%H:%M"))
    if not card:
        return {"cards": [], "resumo_texto": "Varri o e-mail e não tem conta nova pra pagar.", "passos": [
            {"modulo": "Contas", "descricao": f"Varreu {r['lidos']} e-mails", "ms": _ms(t0)}]}
    n = len(card["data"]["contas"])
    return {"cards": [card], "resumo_texto": f"Achei {n} {'coisa' if n == 1 else 'coisas'} no teu e-mail.", "passos": [
        {"modulo": "Contas", "descricao": f"Varreu {r['lidos']} e-mails", "ms": _ms(t0)}]}
