"""Recomeco (ideia `recomeco` do Laboratorio v4, 30/10/2026) - docs/briefings/2026-10-30-lab-v4-foco.md.

A lista de atrasadas fica vermelha, da vergonha e ele para de abrir o app. Na segunda, no dia 1 ou quando passam
de 10 atrasadas aparece o card Recomeco: 1 toque ARQUIVA o que venceu ha mais de 7 dias, sem culpa. Conta,
documento com multa e coisa travada (cadeado/inegociavel) nunca sao arquivados sozinhos. Depois ele escolhe ate
3 pra manter (vao pra hoje). Nada se perde: `tasks.arquivada_em` esconde a tarefa das listas e o "Desfazer" (ou
devolver uma so) traz de volta com o prazo antigo (`arquivada_de`).
"""

from __future__ import annotations

import re
from datetime import date, datetime

import db

DIAS_VELHA = 7  # venceu ha MAIS de 7 dias
LIMITE_ATRASADAS = 10  # passou disso o card aparece em qualquer dia
MAX_MANTER = 3
CONFIG_LOTE = "recomeco_lote"
CONFIG_AVISO = "recomeco_aviso"
# conta/documento com multa: nunca arquivada sozinha
_PROTEGIDA = re.compile(
    r"\b(pagar|pagamento|conta|fatura|boleto|parcela|mensalidade|multa|imposto|iptu|ipva|irpf|detran|cnh|cma|"
    r"renovar|renovacao|renovação|vencimento|documento|passaporte|certid\w+|enel|aluguel)\b", re.IGNORECASE)


def protegida(titulo: str, inegociavel, estilo=None) -> bool:
    return bool(inegociavel) or estilo == "documentos" or bool(_PROTEGIDA.search(titulo or ""))


def atrasadas(conn, hoje: date) -> list[dict]:
    itens = []
    for r in conn.execute(
        """SELECT id, title, due_date, inegociavel, estilo FROM tasks
           WHERE completed_at IS NULL AND recorrencia IS NULL AND arquivada_em IS NULL
             AND due_date IS NOT NULL AND due_date != '' AND due_date < ?
           ORDER BY due_date, id""", (hoje.isoformat(),)).fetchall():
        try:
            dias = (hoje - date.fromisoformat(r["due_date"])).days
        except ValueError:
            continue
        prot = protegida(r["title"], r["inegociavel"], r["estilo"])
        itens.append({"id": r["id"], "titulo": r["title"], "dias": dias, "protegido": prot,
                      "velho": dias > DIAS_VELHA and not prot})
    return itens


def deve_aparecer(conn, hoje: date) -> bool:
    itens = atrasadas(conn, hoje)
    if not itens:
        return False
    return hoje.weekday() == 0 or hoje.day == 1 or len(itens) > LIMITE_ATRASADAS


def estado(conn, hoje: date) -> dict:
    itens = atrasadas(conn, hoje)
    arquivadas = [{"id": r["id"], "titulo": r["title"]} for r in conn.execute(
        "SELECT id, title FROM tasks WHERE arquivada_em IS NOT NULL AND completed_at IS NULL ORDER BY arquivada_em DESC, id LIMIT 12"
    ).fetchall()]
    n_arq = conn.execute("SELECT COUNT(*) n FROM tasks WHERE arquivada_em IS NOT NULL AND completed_at IS NULL").fetchone()["n"]
    return {
        "data": hoje.isoformat(), "total": len(itens), "itens": itens[-30:] if len(itens) > 30 else itens,
        "velhas": sum(1 for i in itens if i["velho"]), "arquivadas_n": n_arq, "arquivo": arquivadas,
        "lote": db.obter_configuracao(conn, CONFIG_LOTE) or "",
    }


def arquivar(conn, hoje: date, agora: datetime | None = None) -> dict:
    """1 toque: arquiva o que venceu ha mais de 7 dias (menos as protegidas). Idempotente."""
    lote = (agora or datetime.now()).isoformat(timespec="seconds")
    ids = [i["id"] for i in atrasadas(conn, hoje) if i["velho"]]
    for tid in ids:
        conn.execute("UPDATE tasks SET arquivada_de = due_date, arquivada_em = ?, due_date = NULL WHERE id = ?", (lote, tid))
    if ids:
        db.definir_configuracao(conn, CONFIG_LOTE, lote)
    conn.commit()
    return {**estado(conn, hoje), "arquivadas": len(ids)}


def _restaurar(conn, where: str, args: tuple) -> int:
    cur = conn.execute(
        f"UPDATE tasks SET due_date = arquivada_de, arquivada_em = NULL, arquivada_de = NULL "
        f"WHERE arquivada_em IS NOT NULL AND completed_at IS NULL AND {where}", args)
    conn.commit()
    return cur.rowcount


def desfazer(conn, hoje: date) -> dict:
    """Volta o ultimo arquivamento inteiro (ou, sem lote guardado, tudo que estiver no arquivo)."""
    lote = db.obter_configuracao(conn, CONFIG_LOTE) or ""
    n = _restaurar(conn, "arquivada_em = ?", (lote,)) if lote else _restaurar(conn, "1 = 1", ())
    db.definir_configuracao(conn, CONFIG_LOTE, "")
    conn.commit()
    return {**estado(conn, hoje), "voltaram": n}


def devolver(conn, hoje: date, task_id: int) -> dict | None:
    if not _restaurar(conn, "id = ?", (task_id,)):
        return None
    return estado(conn, hoje)


def manter(conn, hoje: date, ids) -> dict | None:
    """Ate 3 atrasadas ficam pra hoje (prazo vira hoje). So quem esta mesmo atrasada entra."""
    if not isinstance(ids, list) or not ids or len(ids) > MAX_MANTER:
        return None
    validos = {i["id"] for i in atrasadas(conn, hoje)}
    escolhidos = [i for i in ids if isinstance(i, int) and not isinstance(i, bool) and i in validos]
    if not escolhidos:
        return None
    for tid in escolhidos:
        conn.execute("UPDATE tasks SET due_date = ? WHERE id = ?", (hoje.isoformat(), tid))
    conn.commit()
    return {**estado(conn, hoje), "mantidas": len(escolhidos)}


def card(conn, hoje: date) -> dict:
    import cards

    return cards.novo_card("recomeco", estado(conn, hoje))
