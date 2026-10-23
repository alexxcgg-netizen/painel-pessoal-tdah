"""De onde parei (leva 22/10, ideia 6 do prototipo aprovado "Ideias do Painel" -
docs/briefings/2026-10-22-leva-ideias-v3.md).

Ao abrir o app depois de mais de 2 h parado, se tem tarefa pela metade (quebrada em passos, com pelo menos
um feito e um faltando), a IA deixa no chat um card curto: a tarefa, a barra ate onde ele parou e o proximo
passo. "Deixar pra la" faz o card nao voltar hoje. Uma vez por tarefa por dia.

O "abriu o app" vem do batimento que ja existia (`POST /api/push/visto`, init.js): o servidor guarda a
ultima vez que viu o app na tela e compara com a anterior.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import db

CONFIG_VISTO = "ultimo_visto_em"
CONFIG_HOJE = "de_onde_parei_hoje"  # {"data": iso, "tarefas": [ids ja mostradas ou deixadas]}
PARADO_MIN = timedelta(hours=2)
RECENTE_DIAS = 3  # passo feito ha mais que isso nao e "pela metade", e esquecida (vida.dias_empacada cuida)
FRASES = (
    "Tu tava no meio disso. Falta pouco.",
    "Ficou pela metade. O próximo passo é curto.",
)


def _utc(texto):
    try:
        return datetime.fromisoformat(texto) if texto else None
    except (TypeError, ValueError):
        return None


def _hoje_registro(conn, hoje_iso: str) -> dict:
    try:
        r = json.loads(db.obter_configuracao(conn, CONFIG_HOJE) or "{}")
    except ValueError:
        r = {}
    if not isinstance(r, dict) or r.get("data") != hoje_iso:
        r = {"data": hoje_iso, "tarefas": []}
    return r


def _guardar_hoje(conn, registro: dict, task_id: int):
    if task_id not in registro["tarefas"]:
        registro["tarefas"].append(task_id)
    db.definir_configuracao(conn, CONFIG_HOJE, json.dumps(registro))


def tarefa_pela_metade(conn, agora_utc: datetime, pular=()) -> dict | None:
    """A tarefa aberta com passo feito mais recente (e ainda passo faltando)."""
    limite = (agora_utc - timedelta(days=RECENTE_DIAS)).strftime("%Y-%m-%d %H:%M:%S")
    linhas = conn.execute(
        """SELECT t.id, t.title, MAX(s.completed_at) AS ultimo,
                  SUM(s.completed_at IS NOT NULL) AS feitos, COUNT(*) AS total
           FROM tasks t JOIN subtasks s ON s.task_id = t.id
           WHERE t.completed_at IS NULL
           GROUP BY t.id
           HAVING feitos > 0 AND feitos < total AND ultimo >= ?
           ORDER BY ultimo DESC""",
        (limite,),
    ).fetchall()
    for l in linhas:
        if l["id"] not in pular:
            return dict(l)
    return None


def card(conn, task_id: int, agora_utc: datetime) -> dict | None:
    import cards

    t = conn.execute("SELECT id, title FROM tasks WHERE id = ? AND completed_at IS NULL", (task_id,)).fetchone()
    if not t:
        return None
    passos = conn.execute(
        "SELECT id, title, completed_at FROM subtasks WHERE task_id = ? ORDER BY position, id", (task_id,)
    ).fetchall()
    ultimo = max((_utc(p["completed_at"]) for p in passos if p["completed_at"]), default=None)
    horas = int((agora_utc - ultimo).total_seconds() // 3600) if ultimo else None
    return cards.novo_card("de_onde_parei", {
        "task_id": t["id"],
        "titulo": t["title"],
        "passos": [{"id": p["id"], "titulo": p["title"], "feito": bool(p["completed_at"])} for p in passos],
        "parado_h": horas,
    })


def ao_ver(conn, agora_utc: datetime, hoje_iso: str) -> bool:
    """Chamado a cada batimento do app na tela. Devolve True quando publicou o card no chat."""
    import conversa_proativa

    anterior = _utc(db.obter_configuracao(conn, CONFIG_VISTO))
    db.definir_configuracao(conn, CONFIG_VISTO, agora_utc.isoformat(timespec="seconds"))
    if anterior is None or agora_utc - anterior < PARADO_MIN:
        return False
    registro = _hoje_registro(conn, hoje_iso)
    achada = tarefa_pela_metade(conn, agora_utc, pular=registro["tarefas"])
    if not achada:
        return False
    c = card(conn, achada["id"], agora_utc)
    if not c:
        return False
    texto = FRASES[achada["id"] % len(FRASES)]
    conversa_proativa.publicar(conn, "de_onde_parei", texto, [c])
    _guardar_hoje(conn, registro, achada["id"])
    return True


def deixar(conn, task_id: int, hoje_iso: str):
    """"Deixar pra la": nao volta hoje (amanha, se ainda estiver pela metade, volta)."""
    _guardar_hoje(conn, _hoje_registro(conn, hoje_iso), task_id)


def marcar_passo(conn, subtask_id: int, feito: bool) -> dict | None:
    """Caixinha do card: marca ou desmarca o passo. None se o passo nao existe."""
    s = conn.execute("SELECT id, task_id FROM subtasks WHERE id = ?", (subtask_id,)).fetchone()
    if not s:
        return None
    conn.execute(
        "UPDATE subtasks SET completed_at = " + ("datetime('now')" if feito else "NULL") + " WHERE id = ?",
        (subtask_id,),
    )
    conn.commit()
    linhas = conn.execute("SELECT completed_at FROM subtasks WHERE task_id = ?", (s["task_id"],)).fetchall()
    return {"task_id": s["task_id"], "feitos": sum(1 for l in linhas if l["completed_at"]), "total": len(linhas)}
