"""Inegociavel + Botao dia ruim + Dia que vai dar errado (leva 22/10, ideias 3 e 8 do prototipo aprovado
"Ideias do Painel" - docs/briefings/2026-10-22-leva-ideias-v3.md).

  - INEGOCIAVEL (`tasks.inegociavel`): o cadeado. Tarefa travada nunca e empurrada (aqui, no "passar pra
    amanha" do fechar o dia e no mover_tarefas), nunca some no dia ruim e ganha o aviso de 5 min antes
    (`tarefa_inegociavel`, passa ate no hiperfoco).
  - DIA RUIM (`aliviar`): o dia so com o essencial. Inegociavel fica; treino/estudo ficam em versao curta
    (`extras.reduzido`); o resto vai pra amanha, cada um com "Trazer de volta". Desfazer volta tudo.
  - DIA QUE VAI DAR ERRADO (`sinais_do_dia`): de manha, 2 sinais (sono curto, tarefas empurradas na
    semana, gasto de ontem fora do padrao) acendem um aviso suave com o card pra travar o que nao pode
    falhar e aliviar o resto. Uma vez por dia, nunca a noite (conversa_proativa.alerta_do_dia).

Todo adiamento fica em `tarefas_adiadas` - e dele que sai o sinal "empurradas na semana".
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta

import db

CONFIG_DIA = "dia_ruim_data"
CONFIG_MOVIDAS = "dia_ruim_movidas"
# treino e estudo nao somem no dia ruim: viram versao curta (mesmo horario, so menos)
_TREINO = re.compile(r"\b(trein\w*|academia|muscula\w*|corr(er|ida))\b", re.IGNORECASE)
_REDUZIVEL = re.compile(r"\b(trein\w*|academia|muscula\w*|corr(er|ida)|estud\w*|revis\w*|aula|ler|leitura|simulado|quiz)\b",
                        re.IGNORECASE)
_SO_TAREFA_REAL = "recorrencia IS NULL"
LIMITE_EMPURRADAS = 3  # na semana: vira sinal
SONO_CURTO_H = 6


def _extras(valor) -> dict:
    try:
        e = json.loads(valor) if valor else {}
    except (TypeError, ValueError):
        e = {}
    return e if isinstance(e, dict) else {}


def registrar_adiamento(conn, ids, de: str, para: str) -> None:
    for i in ids:
        conn.execute("INSERT INTO tarefas_adiadas (task_id, de, para) VALUES (?, ?, ?)", (i, de, para))


def empurradas_na_semana(conn, hoje: date) -> int:
    return conn.execute(
        "SELECT COUNT(*) n FROM tarefas_adiadas WHERE date(em, '-3 hours') > ?",
        ((hoje - timedelta(days=7)).isoformat(),),
    ).fetchone()["n"]


def empurradas_demais(conn, limite: int = LIMITE_EMPURRADAS) -> list[str]:
    """Tarefas abertas empurradas `limite`+ vezes (Parceiro de foco: essas ganham o primeiro passo de 2 min)."""
    return [r["title"] for r in conn.execute(
        """SELECT t.title FROM tarefas_adiadas a JOIN tasks t ON t.id = a.task_id
           WHERE t.completed_at IS NULL GROUP BY t.id HAVING COUNT(*) >= ? ORDER BY COUNT(*) DESC LIMIT 3""",
        (limite,),
    ).fetchall()]


def travar(conn, task_id: int, valor: bool) -> dict | None:
    cur = conn.execute("UPDATE tasks SET inegociavel = ? WHERE id = ?", (1 if valor else 0, task_id))
    conn.commit()
    if not cur.rowcount:
        return None
    return {"id": task_id, "inegociavel": bool(valor)}


def inegociaveis_chegando(conn, agora) -> list[tuple[int, str]]:
    """Tarefa travada de hoje com hora daqui a ate ~6 min (o tick do agendador e de 5 em 5)."""
    from datetime import datetime

    avisos = []
    for r in conn.execute(
        "SELECT id, title, hora FROM tasks WHERE completed_at IS NULL AND inegociavel = 1 AND due_date = ? AND hora IS NOT NULL",
        (agora.date().isoformat(),),
    ).fetchall():
        try:
            quando = datetime.combine(agora.date(), datetime.strptime(r["hora"], "%H:%M").time())
        except ValueError:
            continue
        falta = (quando - agora).total_seconds() / 60
        if 0 < falta <= 6:
            avisos.append((r["id"], f"{r['title']} às {r['hora']} - é a que não pode falhar. Faltam {max(1, round(falta))} min."))
    return avisos


def tarefas_do_dia(conn, hoje: date) -> list[dict]:
    """Abertas de hoje e atrasadas (as do dia que importam pro alivio), na ordem da agenda."""
    rows = conn.execute(
        f"SELECT id, title, hora, due_date, inegociavel, extras FROM tasks WHERE completed_at IS NULL AND {_SO_TAREFA_REAL} "
        "AND due_date IS NOT NULL AND due_date != '' AND due_date <= ? "
        "ORDER BY (hora IS NULL OR hora = ''), hora, due_date, id",
        (hoje.isoformat(),),
    ).fetchall()
    return [{"id": r["id"], "titulo": r["title"], "hora": r["hora"] or None, "atrasada": r["due_date"] < hoje.isoformat(),
             "inegociavel": bool(r["inegociavel"]), "reduzido": bool(_extras(r["extras"]).get("reduzido"))} for r in rows]


def ativo(conn, hoje: date) -> bool:
    return (db.obter_configuracao(conn, CONFIG_DIA) or "") == hoje.isoformat()


def _marcar_reduzido(conn, task_id: int, valor: bool) -> None:
    row = conn.execute("SELECT extras FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        return
    e = _extras(row["extras"])
    if valor:
        e["reduzido"] = True
    else:
        e.pop("reduzido", None)
    conn.execute("UPDATE tasks SET extras = ? WHERE id = ?", (json.dumps(e, ensure_ascii=False) if e else None, task_id))


def _movidas(conn, hoje: date) -> list[int]:
    if not ativo(conn, hoje):
        return []
    try:
        ids = json.loads(db.obter_configuracao(conn, CONFIG_MOVIDAS) or "[]")
    except ValueError:
        return []
    return [i for i in ids if isinstance(i, int)]


def versao_curta(titulo: str) -> str:
    return "versão leve · 25 min" if _TREINO.search(titulo or "") else "versão curta · 20 min"


def estado(conn, hoje: date) -> dict:
    """O que o card mostra (prototipo "Botao dia ruim"): inegociavel (fica igual, com aviso extra), reduzido
    (versao curta), fica hoje (o que ele trouxe de volta ou entrou depois) e o que foi pra amanha."""
    amanha = (hoje + timedelta(days=1)).isoformat()
    movidas = _movidas(conn, hoje)
    foram = []
    if movidas:
        marcas = ",".join("?" for _ in movidas)
        foram = [{"id": r["id"], "titulo": r["title"], "hora": r["hora"] or None} for r in conn.execute(
            f"SELECT id, title, hora FROM tasks WHERE id IN ({marcas}) AND completed_at IS NULL AND due_date = ? "
            "ORDER BY (hora IS NULL OR hora = ''), hora, id", [*movidas, amanha]).fetchall()]
    hoje_lista = tarefas_do_dia(conn, hoje)
    for t in hoje_lista:
        if t["reduzido"]:
            t["curta"] = versao_curta(t["titulo"])
    return {
        "data": hoje.isoformat(),
        "ativo": ativo(conn, hoje),
        "inegociavel": [t for t in hoje_lista if t["inegociavel"]],
        "reduzido": [t for t in hoje_lista if t["reduzido"] and not t["inegociavel"]],
        "fica": [t for t in hoje_lista if not t["inegociavel"] and not t["reduzido"]],
        "amanha": foram,
    }


def aliviar(conn, hoje: date) -> dict:
    """Botao dia ruim. Idempotente: apertar de novo so alivia o que entrou depois."""
    amanha = (hoje + timedelta(days=1)).isoformat()
    mover, ja = [], _movidas(conn, hoje)
    for t in tarefas_do_dia(conn, hoje):
        if t["inegociavel"]:
            continue
        if _REDUZIVEL.search(t["titulo"]):
            _marcar_reduzido(conn, t["id"], True)
            continue
        mover.append(t["id"])
    if mover:
        marcas = ",".join("?" for _ in mover)
        conn.execute(f"UPDATE tasks SET due_date = ? WHERE id IN ({marcas})", [amanha, *mover])
        registrar_adiamento(conn, mover, hoje.isoformat(), amanha)
    db.definir_configuracao(conn, CONFIG_DIA, hoje.isoformat())
    db.definir_configuracao(conn, CONFIG_MOVIDAS, json.dumps(sorted(set(ja) | set(mover))))
    db.definir_configuracao(conn, "modo_essencial_data", hoje.isoformat())
    conn.commit()
    return estado(conn, hoje)


def trazer_de_volta(conn, task_id: int, hoje: date) -> dict | None:
    movidas = _movidas(conn, hoje)
    if task_id not in movidas:
        return None
    conn.execute("UPDATE tasks SET due_date = ? WHERE id = ? AND completed_at IS NULL", (hoje.isoformat(), task_id))
    db.definir_configuracao(conn, CONFIG_MOVIDAS, json.dumps([i for i in movidas if i != task_id]))
    conn.commit()
    return estado(conn, hoje)


def empurrar(conn, task_id: int, hoje: date) -> dict | None:
    """'Empurrar' no card: uma que ficou (ou voltou) vai pra amanha. Inegociavel nunca."""
    if not ativo(conn, hoje):
        return None
    amanha = (hoje + timedelta(days=1)).isoformat()
    cur = conn.execute(
        f"UPDATE tasks SET due_date = ? WHERE id = ? AND completed_at IS NULL AND inegociavel = 0 AND {_SO_TAREFA_REAL} "
        "AND due_date IS NOT NULL AND due_date <= ?", (amanha, task_id, hoje.isoformat()))
    if not cur.rowcount:
        return None
    registrar_adiamento(conn, [task_id], hoje.isoformat(), amanha)
    db.definir_configuracao(conn, CONFIG_MOVIDAS, json.dumps(sorted(set(_movidas(conn, hoje)) | {task_id})))
    conn.commit()
    return estado(conn, hoje)


def desfazer(conn, hoje: date) -> dict:
    """Volta o dia como estava: o que foi pra amanha volta, versao curta volta ao normal, modo sai."""
    for i in _movidas(conn, hoje):
        conn.execute("UPDATE tasks SET due_date = ? WHERE id = ? AND completed_at IS NULL", (hoje.isoformat(), i))
    for t in tarefas_do_dia(conn, hoje):
        if t["reduzido"]:
            _marcar_reduzido(conn, t["id"], False)
    db.definir_configuracao(conn, CONFIG_DIA, "")
    db.definir_configuracao(conn, CONFIG_MOVIDAS, "[]")
    db.definir_configuracao(conn, "modo_essencial_data", "")
    conn.commit()
    return estado(conn, hoje)


# ---- dia que vai dar errado ------------------------------------------------------------------
def sinais_do_dia(conn, hoje: date) -> list[dict]:
    """Os sinais que acendem o alerta da manha. Cada um e um fato calculado, nunca palpite."""
    sinais = []
    sono_h = (db.get_saude_dia(conn, hoje.isoformat()) or {}).get("sono_horas")
    checkin = db.get_checkin(conn, hoje.isoformat()) or {}
    if isinstance(sono_h, (int, float)) and 0 < sono_h < SONO_CURTO_H:
        sinais.append({"tipo": "sono", "texto": f"Dormiu {str(round(sono_h, 1)).replace('.', ',')} h essa noite"})
    elif checkin.get("sono") == 1:
        sinais.append({"tipo": "sono", "texto": "Tu disse que dormiu mal"})
    n = empurradas_na_semana(conn, hoje)
    if n >= LIMITE_EMPURRADAS:
        sinais.append({"tipo": "empurradas", "texto": f"{n} tarefas empurradas nos últimos 7 dias"})
    import notificacoes

    if notificacoes.gasto_dia_semana_atipico(conn, hoje - timedelta(days=1)):
        sinais.append({"tipo": "gasto", "texto": "Gasto de ontem bem acima do normal"})
    if checkin.get("energia") == 1 and not any(s["tipo"] == "sono" for s in sinais):
        sinais.append({"tipo": "energia", "texto": "Tu disse que tá sem energia"})
    return sinais


def card_alerta(conn, hoje: date, sinais: list[dict]) -> dict:
    import cards

    return cards.novo_card("alerta_dia", {
        "data": hoje.isoformat(),
        "sinais": sinais,
        "tarefas": [{k: t[k] for k in ("id", "titulo", "hora", "inegociavel")} for t in tarefas_do_dia(conn, hoje)][:8],
        "aliviado": ativo(conn, hoje),
    })


def card_dia_ruim(conn, hoje: date) -> dict:
    import cards

    return cards.novo_card("dia_ruim", estado(conn, hoje))
