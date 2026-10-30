"""Onde guardei (Laboratorio v4, Grupo D, 2026-10-30): "passaporte na gaveta azul do quarto" vira
memoria e "cadê o passaporte?" responde com o lugar e quando foi guardado.

Tabela `guardados` (migracoes/202610301000_md_guardados.sql): um registro por objeto. Guardar de
novo o mesmo objeto atualiza o lugar (e lembra o lugar de antes). Achar por inicio de palavra, sem
acento ("passaporte" acha "Passaporte do Alex"). Sem IA aqui: quem entende a frase e a ferramenta
do chat; este modulo so grava e le. Privacidade: so o objeto e o lugar vao pra IA, e so quando ele
pergunta ou guarda.
"""

from __future__ import annotations

from datetime import date

import cards
import diario
import memoria
import vida

# palavras da pergunta ("cadê o passaporte?", "onde deixei o carregador?") que nao fazem parte do nome
_PERGUNTA = {"cade", "onde", "esta", "ta", "estao", "guard", "deixe", "puse", "pus", "fica"}
LIMITE_LISTA = 5
MAX_OBJETO = 60
MAX_LUGAR = 120


def _limpo(texto, maximo: int) -> str:
    return " ".join(str(texto or "").split())[:maximo].strip()


def _rotulo_curto(d: date, hoje: date) -> str:
    delta = (hoje - d).days
    if delta == 0:
        return "hoje"
    if delta == 1:
        return "ontem"
    if 1 < delta < 7:
        return f"{diario.DIAS_SEMANA[d.weekday()]} {d:%d/%m}"
    return f"{d:%d/%m/%Y}" if d.year != hoje.year else f"{d:%d/%m}"


def _item(r, hoje: date | None = None) -> dict:
    hoje = hoje or diario.hoje_local()
    dt = diario.utc_para_local(r["atualizado_em"])
    quando = ""
    if dt:
        rotulo = _rotulo_curto(dt.date(), hoje)
        quando = f"hoje às {dt:%H:%M}" if rotulo == "hoje" else rotulo
    return {
        "id": r["id"], "objeto": r["objeto"], "lugar": r["lugar"], "quando": quando,
        "dia": dt.date().isoformat() if dt else None,
    }


def guardar(conn, objeto, lugar, hoje: date | None = None) -> dict:
    """Grava (ou atualiza) onde o objeto esta. Devolve o item + `anterior` quando mudou de lugar."""
    objeto, lugar = _limpo(objeto, MAX_OBJETO), _limpo(lugar, MAX_LUGAR)
    if not objeto or not lugar:
        return {"erro": "faltou o objeto ou o lugar (ex: objeto 'passaporte', lugar 'gaveta azul do quarto')"}
    chave = vida.normalizar_nome(objeto)
    atual = conn.execute("SELECT * FROM guardados WHERE chave = ?", (chave,)).fetchone()
    anterior = None
    if atual:
        if vida.normalizar_nome(atual["lugar"]) != vida.normalizar_nome(lugar):
            anterior = atual["lugar"]
        conn.execute(
            "UPDATE guardados SET objeto = ?, lugar = ?, lugar_anterior = ?, atualizado_em = datetime('now') WHERE id = ?",
            (objeto, lugar, anterior or atual["lugar_anterior"], atual["id"]),
        )
        id_ = atual["id"]
    else:
        id_ = conn.execute("INSERT INTO guardados (chave, objeto, lugar) VALUES (?, ?, ?)", (chave, objeto, lugar)).lastrowid
    conn.commit()
    r = conn.execute("SELECT * FROM guardados WHERE id = ?", (id_,)).fetchone()
    item = _item(r, hoje)
    item["anterior"] = anterior
    item["novo"] = atual is None
    return item


def achar(conn, termo, hoje: date | None = None) -> list[dict]:
    """Objetos cujo nome casa com TODAS as palavras do termo (mais recente primeiro)."""
    rs = [r for r in memoria.raizes(termo) if r not in _PERGUNTA]
    if not rs:
        return []
    saida = []
    for r in conn.execute("SELECT * FROM guardados ORDER BY atualizado_em DESC, id DESC"):
        if memoria._casa(r["objeto"], rs):
            saida.append(_item(r, hoje))
    return saida


def listar(conn, limite: int = LIMITE_LISTA, hoje: date | None = None) -> list[dict]:
    return [
        _item(r, hoje)
        for r in conn.execute("SELECT * FROM guardados ORDER BY atualizado_em DESC, id DESC LIMIT ?", (int(limite),))
    ]


def total(conn) -> int:
    return conn.execute("SELECT COUNT(*) n FROM guardados").fetchone()["n"]


def apagar(conn, id_: int) -> bool:
    cur = conn.execute("DELETE FROM guardados WHERE id = ?", (id_,))
    conn.commit()
    return cur.rowcount > 0


def card(conn, ef: dict, hoje: date | None = None):
    """Card `guardados`. modo: 'guardado' (acabou de guardar), 'achei' (respondeu onde esta),
    'nao_achei' (sem registro) ou 'lista'."""
    modo = ef.get("modo") if ef.get("modo") in ("guardado", "achei", "nao_achei", "lista") else "lista"
    destaque = ef.get("item") if isinstance(ef.get("item"), dict) else None
    itens = listar(conn, LIMITE_LISTA + 1, hoje)
    # o item em destaque sempre aparece na lista (mesmo se for mais antigo que os recentes)
    if destaque and not any(i["id"] == destaque.get("id") for i in itens):
        itens = [destaque] + itens
    itens = itens[:LIMITE_LISTA]
    if modo != "nao_achei" and not destaque and not itens:
        return None
    data = {
        "modo": modo,
        "busca": cards._titulo_curto(ef.get("busca"), 60) if modo == "nao_achei" else None,
        "destaque": {k: destaque.get(k) for k in ("id", "objeto", "lugar", "quando", "anterior", "novo")} if destaque else None,
        "itens": itens,
        "total": total(conn),
    }
    return cards.novo_card("guardados", data)
