"""Aba Tarefas nova (leva 06/11, docs/briefings/2026-11-06-painel-esperto.md, frente 6): a folha de
acoes que abre no toque da tarefa e a regua do dia.

- POST /api/tasks/<id>/mover   {data?: "AAAA-MM-DD", hora?: "HH:MM" | null}
  muda o dia e/ou a hora (hora null = tira a hora). Tarefa feita nao muda.
- POST /api/tasks/<id>/titulo  {titulo}  (1-200 caracteres, sem espaco nas pontas)

As duas devolvem {ok, tarefa, token}: a tarefa como ficou e o token do Desfazer de sempre
(acoes_desfazer + POST /api/desfazer/<token>, item "edicao" com os valores de antes - o mesmo
que a IA usa ao editar tarefa). Nada mudou = token null. Mudar hora/dia de date, balada ou tarefa com
lugar refaz o plano de saida (app.replanejar_saida, a mesma do chat) e a resposta traz `plano`.
"""

from __future__ import annotations

import re
from datetime import date

from flask import Blueprint, jsonify

import db
from rotas._base import app_modulo

bp = Blueprint("tarefas_acoes", __name__)

TITULO_MAX = 200
_DATA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _data_valida(valor) -> str | None:
    """"AAAA-MM-DD" que existe de verdade (nada de 2026-02-30); senao None."""
    if not isinstance(valor, str) or not _DATA_RE.match(valor.strip()):
        return None
    try:
        return date.fromisoformat(valor.strip()).isoformat()
    except ValueError:
        return None


def _tarefa(conn, task_id):
    # o MODELO de uma rotina (recorrencia sem dia) nao e tarefa da lista - igual ao DELETE
    return conn.execute(
        "SELECT * FROM tasks WHERE id = ? AND NOT (recorrencia IS NOT NULL AND due_date IS NULL)", (task_id,)
    ).fetchone()


def _aplicar(conn, tarefa, novos: dict) -> dict | None:
    """UPDATE so das colunas que mudaram de fato + o item "edicao" do Desfazer com os valores
    de antes (mesma forma do _editar do chat, app.py). Sem commit."""
    colunas = db.EDICAO_COLUNAS["tasks"]
    mudou = {c: v for c, v in novos.items() if c in colunas and tarefa[c] != v}
    if not mudou:
        return None
    conn.execute(
        f"UPDATE tasks SET {', '.join(c + ' = ?' for c in mudou)} WHERE id = ?",  # nomes da lista fechada
        [*mudou.values(), tarefa["id"]],
    )
    return {
        "entidade": "edicao", "tabela": "tasks", "id": tarefa["id"], "rotulo": "Tarefa",
        "titulo": tarefa["title"], "antes": {c: tarefa[c] for c in mudou}, "depois": mudou,
    }


def _resposta(conn, task_id, efeito, saida=None):
    token = db.criar_acao_desfazer(conn, [efeito]) if efeito else None
    linha = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    corpo = {"ok": True, "tarefa": dict(linha) if linha else None, "token": token, "mudou": bool(efeito)}
    corpo.update(saida or {})  # {"plano": {"sair_de_casa", ...}, "parada"?} quando a saida foi refeita
    return jsonify(corpo)


def _replanejar(app, conn, task_id, efeito) -> dict:
    """Mudou hora/dia de date, balada ou tarefa com lugar: refaz o plano de saida com a MESMA funcao do
    chat (app.replanejar_saida). Maps fora/sem rede = folga de 15 min, nunca derruba a rota."""
    if not efeito:
        return {}
    try:
        saida = app.replanejar_saida(conn, task_id, efeito["depois"])
        conn.commit()
        return saida
    except Exception:  # plano e extra: a mudanca ja foi gravada
        conn.rollback()
        return {}


@bp.route("/api/tasks/<int:task_id>/mover", methods=["POST"])
def mover_tarefa(task_id):
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    corpo = app._corpo_json()
    if not isinstance(corpo, dict) or ("data" not in corpo and "hora" not in corpo):
        return jsonify({"error": "diz o dia (data) e/ou a hora"}), 400
    novos = {}
    if "data" in corpo:
        data = _data_valida(corpo.get("data"))
        if not data:
            return jsonify({"error": "data inválida (use AAAA-MM-DD)"}), 400
        novos["due_date"] = data
    if "hora" in corpo:
        if corpo.get("hora") is None:
            novos["hora"] = None
        else:
            hora = app._normalizar_hora(corpo.get("hora"))
            if not hora:
                return jsonify({"error": "hora inválida (use HH:MM)"}), 400
            novos["hora"] = hora
    conn = db.get_db()
    try:
        tarefa = _tarefa(conn, task_id)
        if not tarefa:
            return jsonify({"error": "tarefa não encontrada"}), 404
        if tarefa["completed_at"]:
            return jsonify({"error": "tarefa já feita não muda de dia nem de hora"}), 409
        hoje = app._agora_brasilia().date().isoformat()
        # hora sem dia nao aparece no dia nem chama na hora (mesma regra do chat, ajustar_tarefa)
        if novos.get("hora") and "due_date" not in novos and not tarefa["due_date"]:
            novos["due_date"] = hoje
        efeito = _aplicar(conn, tarefa, novos)
        if efeito and "due_date" in efeito["depois"]:
            de, para = tarefa["due_date"], efeito["depois"]["due_date"]
            # dia de rotina saindo do dia dele: sem o "pulo", materializar_tarefas_recorrentes
            # recriava a de hoje no proximo GET /api/tasks (mesmo cuidado do apagar)
            if tarefa["recorrente_origem_id"] and de:
                conn.execute(
                    "INSERT OR IGNORE INTO tarefas_puladas (origem_id, data) VALUES (?, ?)",
                    (tarefa["recorrente_origem_id"], de),
                )
            # empurrou pra frente uma de hoje/atrasada: conta como adiamento (dia_ruim, igual ao
            # "pra amanha" do fechamento do dia)
            if de and de <= hoje and para > hoje:
                import dia_ruim

                dia_ruim.registrar_adiamento(conn, [tarefa["id"]], de, para)
        conn.commit()
        return _resposta(conn, task_id, efeito, _replanejar(app, conn, task_id, efeito))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@bp.route("/api/tasks/<int:task_id>/titulo", methods=["POST"])
def renomear_tarefa(task_id):
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    corpo = app._corpo_json()
    titulo = corpo.get("titulo") if isinstance(corpo, dict) else None
    if not isinstance(titulo, str):
        return jsonify({"error": "escreve o nome da tarefa"}), 400
    titulo = " ".join(titulo.split())  # tira espaco das pontas e quebra de linha do meio
    if not titulo:
        return jsonify({"error": "o nome não pode ficar vazio"}), 400
    if len(titulo) > TITULO_MAX:
        return jsonify({"error": f"nome grande demais (máximo {TITULO_MAX} letras)"}), 400
    conn = db.get_db()
    try:
        tarefa = _tarefa(conn, task_id)
        if not tarefa:
            return jsonify({"error": "tarefa não encontrada"}), 404
        efeito = _aplicar(conn, tarefa, {"title": titulo})
        conn.commit()
        return _resposta(conn, task_id, efeito)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
