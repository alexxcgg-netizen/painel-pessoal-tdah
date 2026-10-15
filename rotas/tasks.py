"""Blueprint tasks - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from rotas._base import app_modulo
from db import complete_task, criar_tarefa_de_brain_dump, definir_esforco_tarefa, get_db, list_fichas_treino, reclassificar_tarefa_para_gasto, registrar_correcao_classificacao
import db
import maps_client
import math
import vida
import vida_assistente

bp = Blueprint("tasks", __name__)

@bp.route("/api/tasks", methods=["GET"])
def list_tasks():
    app = app_modulo()
    date = app.date
    materializar_tarefas_recorrentes = app.materializar_tarefas_recorrentes
    conn = get_db()
    materializar_tarefas_recorrentes(conn)
    # M3 (uso diario): "Ver concluidas" na aba Tarefas - concluida NUNCA e apagada
    # (so sai da lista padrao por esse filtro completed_at IS NULL), so busca as
    # ultimas quando o dono pedir explicitamente via ?estado=concluidas (a UI so
    # chama isso ao tocar no botao - preguicoso, nunca no carregamento normal).
    # Qualquer outro valor (ou nenhum) cai no comportamento padrao de sempre.
    estado = request.args.get("estado", "")
    if estado == "concluidas":
        rows = conn.execute(
            "SELECT * FROM tasks WHERE completed_at IS NOT NULL AND recorrencia IS NULL "
            "ORDER BY completed_at DESC LIMIT 50"
        ).fetchall()
    else:
        # Ordem de agenda (pedido do Alex, 2026-10-13): por dia (atrasada/hoje primeiro),
        # dentro do dia por horario; sem horario fecha o dia dela; sem data vai pro fim
        # (a mais nova primeiro, como era antes).
        rows = conn.execute(
            "SELECT * FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL "
            "ORDER BY (due_date IS NULL OR due_date = ''), due_date, "
            "(hora IS NULL OR hora = ''), hora, created_at DESC, id DESC"
        ).fetchall()
    # Uma query so pras subtarefas de todas as tasks (em vez de uma query por task -
    # nao pesava nada com poucas tarefas, mas escala mal conforme o historico cresce).
    task_ids = [row["id"] for row in rows]
    subtasks_por_task = {}
    if task_ids:
        placeholders = ",".join("?" for _ in task_ids)
        subtask_rows = conn.execute(
            f"SELECT * FROM subtasks WHERE task_id IN ({placeholders}) ORDER BY position",
            task_ids,
        ).fetchall()
        for s in subtask_rows:
            subtasks_por_task.setdefault(s["task_id"], []).append(dict(s))
    fichas = list_fichas_treino(conn)
    # 2026-10-15: tarefa com lugar ganha "Waze" nas acoes (o toque no aviso "hora de sair" abre a
    # tarefa com as acoes abertas -> um toque e o Waze navega). Apelido ("obra") vira o endereco.
    waze_por_local = {}
    if estado != "concluidas":
        for row in rows:
            local = (row["local"] or "").strip() if "local" in row.keys() else ""
            if local and local not in waze_por_local:
                waze_por_local[local] = maps_client.link_waze(None, vida_assistente.resolver_lugar(conn, local))
    conn.close()

    hoje = date.today()
    tasks = []
    for row in rows:
        task = dict(row)
        task["subtasks"] = subtasks_por_task.get(task["id"], [])
        task["empacada_dias"] = vida.dias_empacada(task, task["subtasks"], hoje)
        task["fichas_treino"] = [f["id"] for f in vida.ficha_para_titulo(fichas, task["title"])]
        task["waze"] = waze_por_local.get((task.get("local") or "").strip())
        tasks.append(task)
    return jsonify(tasks)

@bp.route("/api/tasks", methods=["POST"])
def criar_tarefa_direta():
    """Fase 6 (US-F10): formulario direto na aba Tarefas, sem passar pela
    classificacao por IA (essa ja existe via chat/captura, /api/capture e
    registrar_tarefa) - so titulo + prazo OPCIONAL. Reusa o mesmo insert
    minimo de criar_tarefa_de_brain_dump (Fase 5, US-C6) em vez de duplicar
    o INSERT numa terceira funcao."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    _marcar_atividade = app._marcar_atividade
    date = app.date
    body = _corpo_json()
    titulo = (body.get("titulo") or "").strip()
    if not titulo:
        return jsonify({"error": "informe um titulo"}), 400
    if len(titulo) > 200:
        return jsonify({"error": "titulo muito longo (max 200 caracteres)"}), 400

    due_date_bruto = body.get("due_date")
    due_date = due_date_bruto.strip() if isinstance(due_date_bruto, str) else None
    if due_date:
        try:
            date.fromisoformat(due_date)
        except ValueError:
            return jsonify({"error": "prazo precisa estar em formato AAAA-MM-DD"}), 400
    else:
        due_date = None

    conn = get_db()
    task_id = criar_tarefa_de_brain_dump(conn, titulo, due_date)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"id": task_id, "ok": True}), 201

@bp.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def excluir_tarefa(task_id):
    """Arrastar-pra-excluir da aba Tarefas (2026-10-11): apaga sem concluir e devolve o token
    do Desfazer (o mesmo /api/desfazer/<token> dos cards). Dia de rotina = pula so hoje."""
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    conn = get_db()
    try:
        tarefa = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND NOT (recorrencia IS NOT NULL AND due_date IS NULL)", (task_id,)
        ).fetchone()
        if not tarefa:
            return jsonify({"error": "tarefa não encontrada"}), 404
        efeito = app.apagar_tarefa_com_desfazer(conn, tarefa)
        conn.commit()
        token = db.criar_acao_desfazer(conn, [efeito])
        return jsonify({"ok": True, "titulo": tarefa["title"], "token": token, "pulada": bool(efeito.get("pulo"))})
    finally:
        conn.close()


@bp.route("/api/tasks/<int:task_id>/hora", methods=["POST"])
def mudar_hora_tarefa(task_id):
    """Botao "Passar X pras 8h30" do card de tarefa com aperto (2026-10-14, docs/CARDS.md):
    so troca a hora de uma tarefa pendente de dia marcado."""
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    hora = app._normalizar_hora(app._corpo_json().get("hora"))
    if not hora:
        return jsonify({"error": "hora inválida"}), 400
    conn = get_db()
    try:
        cur = conn.execute(
            "UPDATE tasks SET hora = ? WHERE id = ? AND completed_at IS NULL AND due_date IS NOT NULL", (hora, task_id)
        )
        conn.commit()
        if not cur.rowcount:
            return jsonify({"error": "tarefa não encontrada"}), 404
        return jsonify({"ok": True, "hora": hora})
    finally:
        conn.close()


@bp.route("/api/tasks/estado", methods=["GET"])
def estado_tarefas():
    """Concluida ou nao, por id - os cards do chat (foto do momento em que a IA respondeu)
    acertam as caixinhas com o estado de agora (2026-10-14). ?ids=1,2,3 (ate 200, so
    numeros); id que nao existe mais nao volta."""
    ids = []
    for parte in (request.args.get("ids") or "").split(",")[:200]:
        parte = parte.strip()
        if parte.isdigit():
            ids.append(int(parte))
    if not ids:
        return jsonify({"estados": {}})
    conn = get_db()
    try:
        marcas = ",".join("?" * len(ids))
        rows = conn.execute(f"SELECT id, completed_at, estilo FROM tasks WHERE id IN ({marcas})", ids).fetchall()
        # cards de compromisso (2026-10-14): o que ja foi marcado/escolhido nele
        extras = {str(r["id"]): _estado_extras(db.extras_tarefa(conn, r["id"])) for r in rows if r["estilo"]}
    finally:
        conn.close()
    resposta = {"estados": {str(r["id"]): r["completed_at"] is not None for r in rows}}
    if extras:  # so quando tem card de compromisso - o formato antigo continua igual
        resposta["extras"] = extras
    return jsonify(resposta)


def _estado_extras(extras: dict) -> dict:
    import cards

    return {
        "lista": [bool(i.get("feito")) for i in extras.get("lista") or [] if isinstance(i, dict)],
        "escolha": extras.get("escolha") if isinstance(extras.get("escolha"), int) else None,
        "volta_modo": cards.modo_volta(extras),
    }


def _tarefa_com_estilo(conn, task_id, estilos):
    row = conn.execute(
        "SELECT id, title, due_date, estilo FROM tasks WHERE id = ? AND due_date IS NOT NULL", (task_id,)
    ).fetchone()
    return row if row and row["estilo"] in estilos else None


@bp.route("/api/tasks/<int:task_id>/lista", methods=["POST"])
def marcar_item_lista(task_id):
    """Caixinha da lista do card (o que levar no cartorio, o que fazer antes do date) - 2026-10-14."""
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    corpo = app._corpo_json()
    i = corpo.get("i")
    if not isinstance(i, int) or isinstance(i, bool):
        return jsonify({"error": "item inválido"}), 400
    conn = get_db()
    try:
        if not _tarefa_com_estilo(conn, task_id, ("date", "documentos")):
            return jsonify({"error": "tarefa não encontrada"}), 404
        extras = db.extras_tarefa(conn, task_id)
        lista = extras.get("lista") or []
        if not 0 <= i < len(lista):
            return jsonify({"error": "item inválido"}), 400
        lista[i]["feito"] = bool(corpo.get("feito"))
        db.salvar_extras_tarefa(conn, task_id, extras)
        return jsonify({"ok": True, "feitos": sum(1 for x in lista if x.get("feito")), "total": len(lista)})
    finally:
        conn.close()


@bp.route("/api/tasks/<int:task_id>/presente", methods=["POST"])
def escolher_presente(task_id):
    """Tocar numa ideia do card de presente (2026-10-14, pedido do Alex): guarda a escolha e
    cria (ou troca) o lembrete de comprar 4 dias antes da data - margem de entrega."""
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    i = app._corpo_json().get("i")
    if not isinstance(i, int) or isinstance(i, bool):
        return jsonify({"error": "ideia inválida"}), 400
    conn = get_db()
    try:
        row = _tarefa_com_estilo(conn, task_id, ("presente",))
        if not row:
            return jsonify({"error": "tarefa não encontrada"}), 404
        extras = db.extras_tarefa(conn, task_id)
        ideias = extras.get("ideias") or []
        if not 0 <= i < len(ideias):
            return jsonify({"error": "ideia inválida"}), 400
        hoje = app._agora_brasilia().date()
        compra = max(hoje, date.fromisoformat(row["due_date"]) - timedelta(days=app.DIAS_ENTREGA_PRESENTE))
        titulo = f"Comprar presente: {ideias[i]['titulo']} ({row['title']})"[:200]
        lembrete_id = extras.get("lembrete_id")
        existe = isinstance(lembrete_id, int) and conn.execute(
            "SELECT 1 FROM lembretes WHERE id = ?", (lembrete_id,)).fetchone()
        if existe:
            conn.execute("UPDATE lembretes SET titulo = ?, data = ? WHERE id = ?", (titulo, compra.isoformat(), lembrete_id))
        else:
            lembrete_id = db.create_lembrete(conn, titulo, compra.isoformat())
        extras["escolha"] = i
        extras["lembrete_id"] = lembrete_id
        db.salvar_extras_tarefa(conn, task_id, extras)
        return jsonify({"ok": True, "escolha": i, "compra_ate": compra.isoformat()})
    finally:
        conn.close()


@bp.route("/api/tasks/<int:task_id>/volta", methods=["POST"])
def modo_volta(task_id):
    """Como volta da balada (3a leva, 2026-10-14 - "dificilmente volto de Uber, geralmente
    dirigindo ou de carona"): dirigindo (padrao) / carona / uber. Uber = tarefa "Chamar Uber pra
    voltar" 30 min antes da volta (o aviso de tarefa com hora faz o resto); os outros apagam."""
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    import cards

    modo = app._corpo_json().get("modo")
    if modo not in cards.VOLTA_MODOS:
        return jsonify({"error": "modo inválido"}), 400
    ligada = modo == "uber"
    conn = get_db()
    try:
        row = _tarefa_com_estilo(conn, task_id, ("balada",))
        if not row:
            return jsonify({"error": "tarefa não encontrada"}), 404
        extras = db.extras_tarefa(conn, task_id)
        volta = extras.get("volta") or cards.VOLTA_PADRAO_BALADA
        hora = cards._hhmm_menos(volta, 30)
        dia = date.fromisoformat(row["due_date"])
        if cards._min_do_dia(volta) < 12 * 60:  # volta de madrugada = dia seguinte
            dia += timedelta(days=1)
        antiga = extras.pop("uber_tarefa_id", None)
        if isinstance(antiga, int):
            conn.execute("DELETE FROM tasks WHERE id = ? AND completed_at IS NULL", (antiga,))
        if ligada:
            cur = conn.execute(
                "INSERT INTO tasks (title, due_date, hora, source_text) VALUES (?, ?, ?, ?)",
                ("Chamar Uber pra voltar", dia.isoformat(), hora, f"card da balada #{task_id}"),
            )
            extras["uber_tarefa_id"] = cur.lastrowid
        extras.pop("uber", None)
        extras["volta_modo"] = modo
        db.salvar_extras_tarefa(conn, task_id, extras)
        return jsonify({"ok": True, "modo": modo, "hora": hora if ligada else None})
    finally:
        conn.close()


@bp.route("/api/tasks/<int:task_id>/complete", methods=["POST"])
def complete_task_rota(task_id):
    app = app_modulo()
    _marcar_atividade = app._marcar_atividade
    conn = get_db()
    complete_task(conn, task_id)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/tasks/<int:task_id>/reabrir", methods=["POST"])
def reabrir_task_rota(task_id):
    """Fase 6 (US-E3): desmarcar o checkbox de uma tarefa no card
    tarefas_criadas volta ela pra pendente (o par do /complete)."""
    conn = get_db()
    ok = db.reabrir_tarefa(conn, task_id)
    conn.close()
    if not ok:
        return jsonify({"error": "tarefa não encontrada"}), 404
    return jsonify({"ok": True})

@bp.route("/api/tasks/<int:task_id>/esforco", methods=["POST"])
def definir_esforco_tarefa_rota(task_id):
    """Fase 5 (US-C7)."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    body = _corpo_json()
    esforco = body.get("esforco")
    if esforco not in vida.NIVEIS_ENERGIA:
        return jsonify({"error": "esforco precisa ser baixa, media ou alta"}), 400
    conn = get_db()
    ok = definir_esforco_tarefa(conn, task_id, esforco)
    conn.close()
    if not ok:
        return jsonify({"error": "tarefa não encontrada"}), 404
    return jsonify({"ok": True, "esforco": esforco})

@bp.route("/api/tarefas/sugestao-energia", methods=["GET"])
def sugestao_por_energia():
    """Fase 5 (US-C7): sugere tarefas pendentes compativeis com o nivel de
    energia atual informado (baixa/media/alta) - so filtra as ja listadas
    por /api/tasks (mesma fonte, sem duplicar a query)."""
    nivel = request.args.get("nivel", "")
    if nivel not in vida.NIVEIS_ENERGIA:
        return jsonify({"error": "nivel precisa ser baixa, media ou alta"}), 400
    conn = get_db()
    tasks = conn.execute(
        "SELECT * FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL "
        "ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    compativeis = vida.tarefas_compativeis_com_energia([dict(t) for t in tasks], nivel)
    return jsonify(compativeis)

@bp.route("/api/tasks/<int:task_id>/breakdown", methods=["POST"])
def breakdown_task(task_id):
    app = app_modulo()
    _call_claude = app._call_claude
    _log_usage = app._log_usage
    claude_client = app.claude_client
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify({"error": "tarefa não encontrada"}), 404

    result, error = _call_claude(claude_client.break_down_task, task["title"])
    if error:
        conn.close()
        return error
    steps, usage = result

    _log_usage(conn, usage, "quebra_tarefa")
    for i, step in enumerate(steps):
        conn.execute(
            "INSERT INTO subtasks (task_id, title, position) VALUES (?, ?, ?)",
            (task_id, step, i),
        )
    conn.commit()
    subtasks = conn.execute(
        "SELECT * FROM subtasks WHERE task_id = ? ORDER BY position", (task_id,)
    ).fetchall()
    conn.close()
    return jsonify({"subtasks": [dict(s) for s in subtasks]})

@bp.route("/api/tasks/<int:task_id>/subtasks", methods=["DELETE"])
def desfazer_quebra(task_id):
    """Desfazer o "quebrar em passos" (pedido do Alex, 2026-10-13): a tarefa volta a ser
    uma so - apaga todos os passos dela (feitos ou nao). A tarefa em si nao muda."""
    app = app_modulo()
    recusa = app._recusar_no_modo_visitante()
    if recusa:
        return recusa
    conn = get_db()
    try:
        if not conn.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone():
            return jsonify({"error": "tarefa não encontrada"}), 404
        apagados = conn.execute("DELETE FROM subtasks WHERE task_id = ?", (task_id,)).rowcount
        conn.commit()
        return jsonify({"ok": True, "removidos": apagados})
    finally:
        conn.close()

@bp.route("/api/subtasks/<int:subtask_id>/complete", methods=["POST"])
def complete_subtask(subtask_id):
    app = app_modulo()
    _marcar_atividade = app._marcar_atividade
    conn = get_db()
    conn.execute("UPDATE subtasks SET completed_at = datetime('now') WHERE id = ?", (subtask_id,))
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/tasks/<int:task_id>/reclassificar", methods=["POST"])
def reclassificar_tarefa_rota(task_id):
    """Correcao rapida: a IA classificou como tarefa algo que na verdade era
    gasto. "valor" e obrigatorio - o texto original pode nao ter um numero
    claro, entao quem esta corrigindo (o Alex, nao a IA de novo) informa."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    _marcar_atividade = app._marcar_atividade
    corpo = _corpo_json()
    valor = corpo.get("valor")
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or valor <= 0:
        return jsonify({"error": "informe um valor valido"}), 400
    categoria = corpo.get("categoria") if isinstance(corpo.get("categoria"), str) else None
    tipo = corpo.get("tipo") if corpo.get("tipo") in ("real", "planejado") else "real"

    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify({"error": "tarefa não encontrada"}), 404

    resultado = reclassificar_tarefa_para_gasto(conn, task_id, float(valor), categoria, tipo)
    novo_id, subtasks_removidas = resultado
    registrar_correcao_classificacao(
        conn, task["source_text"] or task["title"], "tarefa", None, "gasto", categoria
    )
    _marcar_atividade(conn)
    conn.close()
    return jsonify({"ok": True, "novo_id": novo_id, "subtasks_removidas": subtasks_removidas})

@bp.route("/api/tasks/<int:task_id>/requebrar", methods=["POST"])
def requebrar_task(task_id):
    """Tarefa empacada: pede um jeito DIFERENTE de atacar (primeiro passo
    ridiculamente facil). Passos ja feitos ficam; os nao feitos sao trocados."""
    app = app_modulo()
    CLAUDE_FORMAT_ERROR_MSG = app.CLAUDE_FORMAT_ERROR_MSG
    _call_claude = app._call_claude
    _log_usage = app._log_usage
    claude_client = app.claude_client
    date = app.date
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify({"error": "tarefa não encontrada"}), 404
    subtasks = [
        dict(s)
        for s in conn.execute(
            "SELECT * FROM subtasks WHERE task_id = ? ORDER BY position", (task_id,)
        ).fetchall()
    ]
    dias = vida.dias_empacada(dict(task), subtasks, date.today()) or 0
    antigos = [s["title"] for s in subtasks if not s["completed_at"]]
    result, error = _call_claude(claude_client.requebrar_tarefa, task["title"], dias, antigos)
    if error:
        conn.close()
        return error
    passos, usage = result
    passos = [p.strip() for p in passos if isinstance(p, str) and p.strip()] if isinstance(passos, list) else []
    if not passos:
        conn.close()
        return jsonify({"error": CLAUDE_FORMAT_ERROR_MSG}), 502
    _log_usage(conn, usage, "requebrar_tarefa")
    conn.execute("DELETE FROM subtasks WHERE task_id = ? AND completed_at IS NULL", (task_id,))
    inicio = max((s["position"] for s in subtasks if s["completed_at"]), default=-1) + 1
    for i, passo in enumerate(passos):
        conn.execute(
            "INSERT INTO subtasks (task_id, title, position) VALUES (?, ?, ?)",
            (task_id, passo, inicio + i),
        )
    conn.commit()
    novas = conn.execute(
        "SELECT * FROM subtasks WHERE task_id = ? ORDER BY position", (task_id,)
    ).fetchall()
    conn.close()
    return jsonify({"subtasks": [dict(s) for s in novas]})


@bp.route("/api/tarefas/adiar", methods=["POST"])
def tarefas_adiar():
    """Botao "passar pra amanha" do card fechar_dia (conversa_proativa): move as abertas
    de hoje/atrasadas pra amanha mantendo o horario. Ids fora disso sao ignorados."""
    app = app_modulo()
    import conversa_proativa

    corpo = app._corpo_json()
    ids = corpo.get("ids")
    if not isinstance(ids, list) or not ids or len(ids) > 200:
        return jsonify({"error": "ids inválidos"}), 400
    conn = get_db()
    try:
        r = conversa_proativa.adiar_para_amanha(conn, ids, app._agora_brasilia().date())
    finally:
        conn.close()
    return jsonify(r)


@bp.route("/api/tarefas/pra-hoje", methods=["POST"])
def tarefas_pra_hoje():
    """Botao "pra hoje" da tarefa atrasada (aba Tarefas): traz pra hoje em vez de empurrar
    pra amanha. Ids que nao sao atrasados sao ignorados."""
    app = app_modulo()
    import conversa_proativa

    corpo = app._corpo_json()
    ids = corpo.get("ids")
    if not isinstance(ids, list) or not ids or len(ids) > 200:
        return jsonify({"error": "ids inválidos"}), 400
    agora = app._agora_brasilia()
    conn = get_db()
    try:
        r = conversa_proativa.trazer_para_hoje(conn, ids, agora.date(), agora.strftime("%H:%M"))
    finally:
        conn.close()
    return jsonify(r)
