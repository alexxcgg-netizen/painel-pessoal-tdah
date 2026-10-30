"""Memoria sob demanda (2026-10-18, pedido do Alex: "ter memoria, mas ele so ver quando eu
perguntar - quando foi o dia que eu arrumei o quartinho?").

Regra de ouro: NADA aqui vai sozinho pro contexto do chat. A IA chama `buscar_na_memoria` so
quando o Alex pergunta do passado ("quando foi", "quando eu fiz", "ja falei de...", "a ultima vez").

Procura um assunto no que o painel ja guarda, sem IA e sem tabela nova: tarefas (feitas e nao
feitas), o que o Alex escreveu no chat, resumo e anotacoes do diario, notas, esperas, decisoes e
descricao dos gastos. Devolve acertos datados (dia de Brasilia + dia da semana), do mais recente
pro mais antigo. Casamento sem acento e por inicio de palavra ("arrumei" acha "arrumar").
"""

from __future__ import annotations

import unicodedata
from datetime import date, datetime

import diario

LIMITE_PADRAO = 12
LIMITE_MAXIMO = 30
TAMANHO_TRECHO = 160
# palavras que nao dizem nada sobre o assunto
_VAZIAS = {
    "a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos", "em", "na", "no", "nas", "nos",
    "que", "q", "e", "eu", "meu", "minha", "pra", "para", "com", "por", "foi", "dia", "quando", "ultima",
    "ultimo", "vez", "qual", "ja", "se", "ao", "la", "lá",
}


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def raizes(termo: str) -> list[str]:
    """'arrumei o quartinho' -> ['arrum', 'quart']. Palavra curta fica inteira."""
    saida = []
    for palavra in _sem_acento(termo).replace(",", " ").replace(".", " ").replace("?", " ").split():
        if palavra in _VAZIAS or len(palavra) < 2:
            continue
        saida.append(palavra if len(palavra) < 6 else palavra[:5])
    return list(dict.fromkeys(saida))


def _casa(texto: str, rs: list[str]) -> bool:
    alvo = _sem_acento(texto)
    return all(r in alvo for r in rs)


def _trecho(texto: str) -> str:
    t = " ".join(str(texto or "").split())
    return t if len(t) <= TAMANHO_TRECHO else t[: TAMANHO_TRECHO - 1] + "…"


def _dia_local(utc_texto) -> date | None:
    dt = diario.utc_para_local(utc_texto)
    return dt.date() if dt else None


def _dia_iso(texto) -> date | None:
    try:
        return date.fromisoformat(str(texto)[:10])
    except ValueError:
        return None


def _coletar(conn, rs: list[str]) -> list[tuple[date, str, str]]:
    achados: list[tuple[date, str, str]] = []

    def add(dia, tipo, texto):
        if dia and _casa(texto, rs):
            achados.append((dia, tipo, _trecho(texto)))

    for r in conn.execute(
        "SELECT title, due_date, completed_at FROM tasks WHERE recorrencia IS NULL"
    ):
        if r["completed_at"]:
            add(_dia_local(r["completed_at"]), "tarefa feita", r["title"])
        else:
            add(_dia_iso(r["due_date"]), "tarefa que ficou sem fazer", r["title"])

    # a ultima mensagem dele e a propria pergunta ("quando arrumei o quartinho?") - nao conta como lembranca
    for r in conn.execute(
        "SELECT texto, criado_em FROM chat_mensagens WHERE papel = 'user' "
        "AND id < COALESCE((SELECT MAX(id) FROM chat_mensagens WHERE papel = 'user'), 0)"
    ):
        add(_dia_local(r["criado_em"]), "voce falou no chat", r["texto"])

    if diario._tabela_existe(conn, "diario_dias"):
        for r in conn.execute("SELECT dia, resumo FROM diario_dias WHERE resumo IS NOT NULL"):
            add(_dia_iso(r["dia"]), "resumo do dia", r["resumo"])
    if diario._tabela_existe(conn, "diario_anotacoes"):
        for r in conn.execute("SELECT dia, texto FROM diario_anotacoes"):
            add(_dia_iso(r["dia"]), "anotacao tua no diario", r["texto"])

    if diario._tabela_existe(conn, "notas"):
        for r in conn.execute("SELECT titulo, corpo, criado_em FROM notas"):
            add(_dia_local(r["criado_em"]), "nota", f"{r['titulo']}: {r['corpo']}")
    if diario._tabela_existe(conn, "esperas"):
        for r in conn.execute("SELECT quem, sobre, criado_em FROM esperas"):
            add(_dia_local(r["criado_em"]), "espera", f"{r['quem']} - {r['sobre']}")
    if diario._tabela_existe(conn, "diario_decisoes"):
        for r in conn.execute("SELECT decisao, contexto, data FROM diario_decisoes"):
            add(_dia_iso(r["data"]), "decisao", f"{r['decisao']} {r['contexto'] or ''}")
    for r in conn.execute("SELECT description, amount, created_at FROM expenses WHERE tipo = 'real'"):
        add(_dia_local(r["created_at"]), "gasto", f"{r['description'] or '?'} (R$ {float(r['amount'] or 0):.2f})")
    return achados


def buscar(conn, termo: str, de: date | None = None, ate: date | None = None,
           limite: int = LIMITE_PADRAO, hoje: date | None = None) -> dict:
    """Acertos datados do assunto, do mais recente pro mais antigo."""
    hoje = hoje or diario.hoje_local()
    rs = raizes(termo)
    if not rs:
        return {"erro": "faltou o assunto da busca (ex: 'quartinho', 'dentista')"}
    try:
        limite = max(1, min(int(limite), LIMITE_MAXIMO))
    except (TypeError, ValueError):
        limite = LIMITE_PADRAO

    achados = _coletar(conn, rs)
    if de:
        achados = [a for a in achados if a[0] >= de]
    if ate:
        achados = [a for a in achados if a[0] <= ate]
    achados.sort(key=lambda a: (a[0], a[1]), reverse=True)
    # a mesma frase no mesmo dia (chat + tarefa) aparece uma vez por tipo
    vistos, unicos = set(), []
    for a in achados:
        chave = (a[0], a[1], _sem_acento(a[2]))
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(a)

    resultado = {
        "assunto": termo,
        "total_achados": len(unicos),
        "acertos": [
            {"dia": d.isoformat(), "quando": diario.rotulo_dia(d, hoje), "tipo": tipo, "texto": texto}
            for d, tipo, texto in unicos[:limite]
        ],
    }
    if len(unicos) > limite:
        resultado["obs"] = f"mostrando os {limite} mais recentes de {len(unicos)}; refine com 'de'/'ate' se precisar"
    if not unicos:
        resultado["obs"] = (
            "nada no painel sobre isso (so existe o que foi anotado, falado no chat ou riscado como feito); "
            "diga isso ao Alex sem inventar data"
        )
    return resultado


# ---- "O que eu falei sobre..." (Laboratorio v4, Grupo D, 2026-10-30) -------------------------
# So o que ELE disse ou escreveu (chat, anotacao do diario, nota, decisao, espera): a frase original
# datada. Nao entra tarefa, gasto nem resumo gerado. Vira card `o_que_falei`; o resumo em prosa e
# a resposta do proprio chat (que so ve estes trechos - nunca a conversa inteira).
TIPOS_FALAS = ("voce falou no chat", "anotacao tua no diario", "nota", "decisao", "espera")
LIMITE_FALAS = 8


def buscar_falas(conn, termo: str, hoje: date | None = None, limite: int = LIMITE_FALAS) -> dict:
    hoje = hoje or diario.hoje_local()
    rs = raizes(termo)
    if not rs:
        return {"erro": "faltou o assunto (ex: 'pouso', 'creatina')"}
    try:
        limite = max(1, min(int(limite), LIMITE_MAXIMO))
    except (TypeError, ValueError):
        limite = LIMITE_FALAS
    achados = [a for a in _coletar(conn, rs) if a[1] in TIPOS_FALAS]
    achados.sort(key=lambda a: (a[0], a[1]), reverse=True)
    vistos, unicos = set(), []
    for a in achados:
        chave = (a[0], _sem_acento(a[2]))
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(a)
    res = {
        "assunto": termo,
        "total_achados": len(unicos),
        "falas": [
            {"dia": d.isoformat(), "quando": diario.rotulo_dia(d, hoje), "onde": tipo, "texto": texto}
            for d, tipo, texto in unicos[:limite]
        ],
    }
    if len(unicos) > limite:
        res["obs"] = f"mostrando as {limite} mais recentes de {len(unicos)}"
    if not unicos:
        res["obs"] = "nada que ele tenha dito ou escrito sobre isso; diga isso sem inventar"
    return res


def card_falas(res: dict):
    """Card `o_que_falei` a partir do resultado de buscar_falas (so a frase original e a data)."""
    import cards

    if not isinstance(res, dict) or res.get("erro"):
        return None
    itens = [
        {"dia": f["dia"], "texto": f["texto"], "onde": f["onde"]}
        for f in res.get("falas") or [] if isinstance(f, dict)
    ]
    return cards.novo_card("o_que_falei", {
        "assunto": cards._titulo_curto(res.get("assunto"), 50),
        "total": int(res.get("total_achados") or 0),
        "itens": itens,
    })
