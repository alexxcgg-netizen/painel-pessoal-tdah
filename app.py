import json
import os
from datetime import date, datetime

import anthropic
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

import bank_ofx
import caldav_client
import claude_client
import maps_client
import notificacoes
import pluggy_client
import push_client
from db import (
    CAMPOS_SAUDE,
    add_to_goal,
    create_goal,
    create_lembrete,
    create_memoria,
    delete_lembrete,
    delete_memoria,
    delete_push_subscription,
    get_db,
    get_or_create_bank_account,
    get_saude_dia,
    init_db,
    insert_bank_transactions,
    ja_notificou_hoje,
    list_chat_mensagens,
    list_goals,
    list_lembretes,
    list_memorias,
    list_push_subscriptions,
    marcar_notificado,
    media_passos_ultimos_dias,
    record_usage,
    salvar_mensagem_chat,
    save_push_subscription,
    total_cost_usd,
    upsert_saude_dia,
)

app = Flask(__name__)
init_db()

CLAUDE_ERROR_MSG = "Erro ao falar com a IA. Tenta de novo em instantes."
CLAUDE_FORMAT_ERROR_MSG = "A IA respondeu em um formato inesperado. Tenta de novo."


def _log_usage(conn, usage: dict):
    record_usage(conn, usage["model"], usage["input_tokens"], usage["output_tokens"], usage["cost_usd"])


def _call_claude(fn, *args):
    """Chama uma funcao do claude_client e traduz falhas em uma resposta de erro pronta pra devolver."""
    try:
        return fn(*args), None
    except anthropic.APIError:
        return None, (jsonify({"error": CLAUDE_ERROR_MSG}), 502)
    except (ValueError, KeyError):
        return None, (jsonify({"error": CLAUDE_FORMAT_ERROR_MSG}), 502)


def _calculo_meta(goal: dict) -> dict:
    """Faz a conta de quanto falta guardar por mes - em Python puro, nao pela IA."""
    falta = goal["valor_alvo"] - goal["valor_guardado"]
    por_mes = None
    meses = None
    if goal["prazo"]:
        hoje = date.today()
        prazo = date.fromisoformat(goal["prazo"])
        meses = (prazo.year - hoje.year) * 12 + (prazo.month - hoje.month)
        if prazo.day < hoje.day:
            meses -= 1
        meses = max(meses, 1)
        por_mes = max(falta, 0) / meses
    return {**goal, "falta": falta, "meses_restantes": meses, "por_mes": por_mes}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/capture", methods=["POST"])
def capture():
    body = request.json or {}
    text = body.get("text", "").strip()
    clarificacao = body.get("clarificacao", "").strip()
    if not text:
        return jsonify({"error": "texto vazio"}), 400

    full_text = f"{text}. Contexto adicional: {clarificacao}" if clarificacao else text

    result, error = _call_claude(claude_client.classify_capture, full_text)
    if error:
        return error
    parsed, usage = result

    conn = get_db()
    _log_usage(conn, usage)

    # Se a IA ainda ficou em duvida, so pede esclarecimento uma vez (quando a
    # clarificacao ja foi enviada, seguimos com o melhor palpite mesmo assim).
    if parsed.get("duvida") and not clarificacao:
        conn.close()
        return jsonify({"duvida": parsed["duvida"], "texto_original": text})

    if parsed["tipo"] == "gasto":
        conn.execute(
            "INSERT INTO expenses (amount, category, description, source_text) VALUES (?, ?, ?, ?)",
            (parsed["valor"], parsed.get("categoria") or "outros", parsed["titulo"], full_text),
        )
    elif parsed["tipo"] == "meta":
        create_goal(conn, parsed["titulo"], parsed["valor"], parsed.get("prazo"))
    else:
        conn.execute(
            "INSERT INTO tasks (title, due_at, due_date, source_text) VALUES (?, ?, ?, ?)",
            (parsed["titulo"], parsed.get("quando"), parsed.get("quando_data"), full_text),
        )

    if parsed.get("memoria"):
        create_memoria(conn, parsed["memoria"], full_text)

    conn.commit()
    conn.close()
    return jsonify(parsed), 201


@app.route("/api/tasks", methods=["GET"])
def list_tasks():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE completed_at IS NULL ORDER BY created_at DESC"
    ).fetchall()
    tasks = []
    for row in rows:
        task = dict(row)
        subtasks = conn.execute(
            "SELECT * FROM subtasks WHERE task_id = ? ORDER BY position", (task["id"],)
        ).fetchall()
        task["subtasks"] = [dict(s) for s in subtasks]
        tasks.append(task)
    conn.close()
    return jsonify(tasks)


@app.route("/api/tasks/<int:task_id>/complete", methods=["POST"])
def complete_task(task_id):
    conn = get_db()
    conn.execute("UPDATE tasks SET completed_at = datetime('now') WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/tasks/<int:task_id>/breakdown", methods=["POST"])
def breakdown_task(task_id):
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify({"error": "tarefa nao encontrada"}), 404

    result, error = _call_claude(claude_client.break_down_task, task["title"])
    if error:
        conn.close()
        return error
    steps, usage = result

    _log_usage(conn, usage)
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


@app.route("/api/subtasks/<int:subtask_id>/complete", methods=["POST"])
def complete_subtask(subtask_id):
    conn = get_db()
    conn.execute("UPDATE subtasks SET completed_at = datetime('now') WHERE id = ?", (subtask_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/expenses", methods=["GET"])
def list_expenses():
    conn = get_db()
    rows = conn.execute("SELECT * FROM expenses ORDER BY created_at DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


def _saude_contexto_resumo(conn) -> str | None:
    """Monta uma frase factual sobre a saude de hoje pro resumo do dia -
    a comparacao com a media e feita em Python, a IA so recebe o resultado
    pronto (nunca calcula tendencia sozinha)."""
    hoje = date.today().isoformat()
    dia = get_saude_dia(conn, hoje)
    if not dia or dia.get("passos") is None:
        return None

    partes = [f"{dia['passos']} passos hoje"]
    media = media_passos_ultimos_dias(conn, hoje)
    if media:
        diff_pct = (dia["passos"] - media) / media * 100
        if diff_pct <= -20:
            partes.append(f"bem abaixo da media dos ultimos dias ({round(media)} passos)")
        elif diff_pct >= 20:
            partes.append(f"bem acima da media dos ultimos dias ({round(media)} passos)")
    if dia.get("sono_horas"):
        partes.append(f"{dia['sono_horas']}h de sono")
    return ", ".join(partes)


def _eventos_de_hoje_com_seguranca() -> list[dict]:
    """A agenda do iCloud via CalDAV e instavel (ver caldav_client.py) - se
    falhar, o resumo do dia nao pode quebrar por causa disso."""
    if not caldav_client.configurado():
        return []
    try:
        return caldav_client.eventos_do_dia(date.today())
    except Exception:
        return []


@app.route("/api/summary/today", methods=["GET"])
def summary_today():
    today = date.today().isoformat()
    conn = get_db()
    done = conn.execute("SELECT title FROM tasks WHERE date(completed_at) = ?", (today,)).fetchall()
    pending = conn.execute("SELECT title FROM tasks WHERE completed_at IS NULL").fetchall()
    expenses = conn.execute(
        "SELECT amount, category FROM expenses WHERE date(created_at) = ?", (today,)
    ).fetchall()
    gasto_hoje = sum(r["amount"] for r in expenses)
    eventos = _eventos_de_hoje_com_seguranca()
    memorias = list_memorias(conn)
    saude = _saude_contexto_resumo(conn)

    result, error = _call_claude(
        claude_client.summarize_day,
        [r["title"] for r in done],
        [r["title"] for r in pending],
        [dict(r) for r in expenses],
        [e["titulo"] for e in eventos],
        [m["texto"] for m in memorias],
        saude,
    )
    if error:
        conn.close()
        return error
    text, usage = result

    _log_usage(conn, usage)
    conn.close()
    return jsonify(
        {
            "summary": text,
            "gasto_hoje": gasto_hoje,
            "tarefas_concluidas": len(done),
            "eventos_hoje": len(eventos),
        }
    )


@app.route("/api/calendario/hoje", methods=["GET"])
def calendario_hoje():
    if not caldav_client.configurado():
        return jsonify({"configurado": False, "eventos": []})
    try:
        eventos = caldav_client.eventos_do_dia(date.today())
    except Exception:
        return jsonify(
            {"configurado": True, "eventos": [], "erro": "Nao consegui falar com o iCloud agora."}
        )
    return jsonify({"configurado": True, "eventos": eventos})


@app.route("/api/plano-do-dia", methods=["POST"])
def plano_do_dia():
    conn = get_db()
    pending = conn.execute("SELECT title FROM tasks WHERE completed_at IS NULL").fetchall()
    eventos = _eventos_de_hoje_com_seguranca()
    memorias = list_memorias(conn)

    result, error = _call_claude(
        claude_client.plano_do_dia,
        [r["title"] for r in pending],
        eventos,
        [m["texto"] for m in memorias],
    )
    if error:
        conn.close()
        return error
    texto, usage = result

    _log_usage(conn, usage)
    conn.close()
    return jsonify({"plano": texto})


def _contexto_chat(conn) -> str:
    """Resumo factual do agora pro chat usar como contexto - mesma logica
    do resumo do dia, so que em formato de linhas pro system prompt."""
    hoje = date.today().isoformat()
    pendentes = conn.execute("SELECT title FROM tasks WHERE completed_at IS NULL").fetchall()
    gasto_hoje = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE date(created_at) = ?",
        (hoje,),
    ).fetchone()["total"]
    eventos = _eventos_de_hoje_com_seguranca()
    saude = _saude_contexto_resumo(conn)

    linhas = [
        f"Tarefas pendentes: {', '.join(r['title'] for r in pendentes) or 'nenhuma'}",
        f"Gasto de hoje: R$ {gasto_hoje:.2f}",
        f"Compromissos de hoje: {', '.join(e['titulo'] for e in eventos) or 'nenhum'}",
    ]
    if saude:
        linhas.append(f"Saude hoje: {saude}")
    return "\n".join(linhas)


@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.json or {}
    texto = (body.get("mensagem") or "").strip()
    if not texto:
        return jsonify({"error": "mensagem vazia"}), 400

    conn = get_db()

    historico = list(reversed(list_chat_mensagens(conn, limit=20)))
    mensagens = [{"role": r["papel"], "content": r["texto"]} for r in historico]
    mensagens.append({"role": "user", "content": texto})

    memorias_texto = [m["texto"] for m in list_memorias(conn)]
    contexto = _contexto_chat(conn)

    def exec_registrar_tarefa(entrada):
        conn.execute(
            "INSERT INTO tasks (title, due_at, source_text) VALUES (?, ?, ?)",
            (entrada["titulo"], entrada.get("quando"), texto),
        )
        conn.commit()
        return {"ok": True}

    def exec_registrar_gasto(entrada):
        conn.execute(
            "INSERT INTO expenses (amount, category, description, source_text) VALUES (?, ?, ?, ?)",
            (entrada["valor"], entrada.get("categoria") or "outros", entrada["titulo"], texto),
        )
        conn.commit()
        return {"ok": True}

    def exec_registrar_meta(entrada):
        create_goal(conn, entrada["titulo"], entrada["valor"], entrada.get("prazo"))
        return {"ok": True}

    def exec_gerar_plano(_entrada):
        pendentes = conn.execute("SELECT title FROM tasks WHERE completed_at IS NULL").fetchall()
        eventos = _eventos_de_hoje_com_seguranca()
        plano_texto, usage_plano = claude_client.plano_do_dia(
            [r["title"] for r in pendentes], eventos, memorias_texto
        )
        _log_usage(conn, usage_plano)
        return {"plano": plano_texto}

    def exec_registrar_lembrete(entrada):
        create_lembrete(conn, entrada["titulo"], entrada["data"], entrada.get("recorrente", False))
        return {"ok": True}

    executores = {
        "registrar_tarefa": exec_registrar_tarefa,
        "registrar_gasto": exec_registrar_gasto,
        "registrar_meta": exec_registrar_meta,
        "gerar_plano_do_dia": exec_gerar_plano,
        "registrar_lembrete": exec_registrar_lembrete,
    }

    result, error = _call_claude(
        claude_client.chat, mensagens, contexto, memorias_texto, executores
    )
    if error:
        conn.close()
        return error
    resposta, acoes, usage = result

    _log_usage(conn, usage)
    salvar_mensagem_chat(conn, "user", texto)
    salvar_mensagem_chat(conn, "assistant", resposta)
    conn.close()
    return jsonify({"resposta": resposta, "acoes": acoes})


@app.route("/api/chat/historico", methods=["GET"])
def chat_historico():
    conn = get_db()
    mensagens = list(reversed(list_chat_mensagens(conn, limit=30)))
    conn.close()
    return jsonify(mensagens)


def verificar_e_notificar():
    """Roda as verificacoes proativas e manda push pra quem tiver inscrito -
    cada tipo de aviso so dispara uma vez por dia (dedup em notificacoes_enviadas).
    Chamado pelo scheduler (ver iniciar_scheduler) e pelo endpoint manual."""
    if not push_client.configurado():
        return 0

    conn = get_db()
    subs = list_push_subscriptions(conn)
    if not subs:
        conn.close()
        return 0

    avisos = []  # (tipo, referencia_id, titulo, corpo)

    msg = notificacoes.tarefas_atrasadas(conn)
    if msg and not ja_notificou_hoje(conn, "tarefas_atrasadas"):
        avisos.append(("tarefas_atrasadas", 0, "Tarefas atrasadas", msg))

    for meta_id, msg in notificacoes.metas_fora_do_ritmo(conn):
        if not ja_notificou_hoje(conn, "meta_atrasada", meta_id):
            avisos.append(("meta_atrasada", meta_id, "Meta fora do ritmo", msg))

    msg = notificacoes.gasto_semana_elevado(conn)
    if msg and not ja_notificou_hoje(conn, "gasto_elevado"):
        avisos.append(("gasto_elevado", 0, "Gasto da semana", msg))

    for lembrete_id, msg in notificacoes.lembretes_proximos(conn):
        if not ja_notificou_hoje(conn, "lembrete_proximo", lembrete_id):
            avisos.append(("lembrete_proximo", lembrete_id, "Data importante chegando", msg))

    enviados = 0
    for tipo, ref_id, titulo, corpo in avisos:
        for s in subs:
            sub_dict = json.loads(s["subscription_json"])
            ok = push_client.enviar(sub_dict, titulo, corpo)
            if not ok:
                delete_push_subscription(conn, s["endpoint"])
        marcar_notificado(conn, tipo, ref_id)
        enviados += 1

    conn.close()
    return enviados


@app.route("/api/notificacoes/verificar-agora", methods=["POST"])
def notificacoes_verificar_agora():
    enviados = verificar_e_notificar()
    return jsonify({"avisos_enviados": enviados})


@app.route("/api/viagem/status", methods=["GET"])
def viagem_status():
    return jsonify(
        {
            "configurado": maps_client.configurado(),
            "origem_padrao": os.environ.get("ENDERECO_CASA", ""),
        }
    )


@app.route("/api/viagem/quando-sair", methods=["POST"])
def viagem_quando_sair():
    if not maps_client.configurado():
        return jsonify({"error": "calculadora de deslocamento nao configurada - veja o README"}), 400

    body = request.json or {}
    destino = (body.get("destino") or "").strip()
    chegar_ate_str = body.get("chegar_ate")
    origem = (body.get("origem") or "").strip() or os.environ.get("ENDERECO_CASA", "").strip()
    margem = body.get("margem_minutos", 15)
    modo = (body.get("modo") or "DRIVE").strip().upper()

    if not destino or not chegar_ate_str or not origem:
        return (
            jsonify({"error": "informe destino e horario de chegada (e origem, se nao tiver ENDERECO_CASA configurado)"}),
            400,
        )

    try:
        chegar_ate = datetime.fromisoformat(chegar_ate_str)
    except ValueError:
        return jsonify({"error": "chegar_ate precisa estar em formato AAAA-MM-DDTHH:MM"}), 400

    try:
        margem = int(margem)
    except (TypeError, ValueError):
        margem = 15

    try:
        resultado = maps_client.horario_de_saida(origem, destino, chegar_ate, margem, modo)
    except requests.RequestException:
        return jsonify({"error": "nao consegui calcular a rota agora"}), 502
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(resultado)


@app.route("/api/memorias", methods=["GET"])
def memorias():
    conn = get_db()
    resultado = list_memorias(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/memorias/<int:memoria_id>", methods=["DELETE"])
def apagar_memoria(memoria_id):
    conn = get_db()
    delete_memoria(conn, memoria_id)
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/lembretes", methods=["GET"])
def lembretes():
    conn = get_db()
    resultado = list_lembretes(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/lembretes/<int:lembrete_id>", methods=["DELETE"])
def apagar_lembrete(lembrete_id):
    conn = get_db()
    delete_lembrete(conn, lembrete_id)
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/saude/importar", methods=["POST"])
def saude_importar():
    token_esperado = os.environ.get("SAUDE_WEBHOOK_TOKEN")
    if token_esperado and request.headers.get("X-Webhook-Token") != token_esperado:
        return jsonify({"error": "token invalido"}), 401

    body = request.json or {}
    data = body.get("data") or date.today().isoformat()
    try:
        date.fromisoformat(data)
    except ValueError:
        return jsonify({"error": "data precisa estar em formato AAAA-MM-DD"}), 400

    campos = {c: body[c] for c in CAMPOS_SAUDE if body.get(c) is not None}
    if not campos:
        return (
            jsonify({"error": "informe ao menos um campo: " + ", ".join(CAMPOS_SAUDE)}),
            400,
        )

    conn = get_db()
    upsert_saude_dia(conn, data, campos)
    conn.close()
    return jsonify({"ok": True, "data": data, **campos})


@app.route("/api/saude/hoje", methods=["GET"])
def saude_hoje():
    conn = get_db()
    dia = get_saude_dia(conn, date.today().isoformat())
    conn.close()
    return jsonify({"dados": dia})


@app.route("/api/uso/total", methods=["GET"])
def uso_total():
    conn = get_db()
    total = total_cost_usd(conn)
    conn.close()
    return jsonify({"custo_usd": round(total, 4)})


@app.route("/api/bancos/importar", methods=["POST"])
def importar_extrato():
    banco = request.form.get("banco", "").strip().lower()
    tipo = request.form.get("tipo", "conta").strip().lower()
    if tipo not in ("conta", "cartao"):
        tipo = "conta"
    arquivo = request.files.get("arquivo")
    if not banco or not arquivo:
        return jsonify({"error": "informe o banco e o arquivo OFX"}), 400

    texto = bank_ofx.decode_ofx(arquivo.read())
    try:
        transacoes = bank_ofx.parse_transactions(texto)
    except ValueError:
        return jsonify({"error": "nao consegui ler as datas/valores desse arquivo OFX"}), 400

    if not transacoes:
        return jsonify({"error": "nenhuma transacao encontrada nesse arquivo"}), 400

    conn = get_db()
    conta_id = get_or_create_bank_account(conn, banco, tipo)
    novas = insert_bank_transactions(conn, conta_id, transacoes)
    conn.close()
    return jsonify(
        {
            "conta_id": conta_id,
            "encontradas": len(transacoes),
            "novas": novas,
            "duplicadas": len(transacoes) - novas,
        }
    )


@app.route("/api/bancos", methods=["GET"])
def listar_bancos():
    conn = get_db()
    contas = conn.execute("SELECT * FROM bank_accounts ORDER BY banco, tipo").fetchall()
    resultado = []
    for c in contas:
        stats = conn.execute(
            """SELECT COUNT(*) AS total, MAX(data) AS ultima,
                      COALESCE(SUM(CASE WHEN valor < 0 THEN -valor ELSE 0 END), 0) AS total_gasto
               FROM bank_transactions WHERE bank_account_id = ?""",
            (c["id"],),
        ).fetchone()
        resultado.append(
            {
                **dict(c),
                "total_transacoes": stats["total"],
                "ultima_transacao": stats["ultima"],
                "total_gasto": stats["total_gasto"],
            }
        )
    conn.close()
    return jsonify(resultado)


@app.route("/api/bancos/<int:conta_id>/transacoes", methods=["GET"])
def transacoes_banco(conta_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM bank_transactions WHERE bank_account_id = ? ORDER BY data DESC LIMIT 100",
        (conta_id,),
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/bancos/sync-status", methods=["GET"])
def bancos_sync_status():
    configurado = pluggy_client.configurado()
    return jsonify(
        {
            "sincronizacao_automatica": configurado,
            "info": (
                "Conecte um banco automaticamente pra sincronizar sem precisar exportar OFX."
                if configurado
                else "Sincronizacao automatica ainda nao configurada - veja o README (integracao com Pluggy)."
            ),
        }
    )


@app.route("/api/bancos/conectar/token", methods=["POST"])
def bancos_conectar_token():
    if not pluggy_client.configurado():
        return jsonify({"error": "sincronizacao automatica nao configurada"}), 400
    try:
        token = pluggy_client.create_connect_token()
    except requests.RequestException:
        return jsonify({"error": "nao consegui falar com a Pluggy agora"}), 502
    return jsonify({"connect_token": token})


@app.route("/api/bancos/conectar/finalizar", methods=["POST"])
def bancos_conectar_finalizar():
    if not pluggy_client.configurado():
        return jsonify({"error": "sincronizacao automatica nao configurada"}), 400

    item_id = (request.json or {}).get("item_id")
    if not item_id:
        return jsonify({"error": "item_id obrigatorio"}), 400

    try:
        item = pluggy_client.get_item(item_id)
        contas_pluggy = pluggy_client.get_accounts(item_id)
    except requests.RequestException:
        return jsonify({"error": "nao consegui buscar os dados na Pluggy agora"}), 502

    banco = item.get("connector", {}).get("name", "banco").lower()

    conn = get_db()
    resumo = []
    for conta_pluggy in contas_pluggy:
        tipo = "cartao" if conta_pluggy.get("type") == "CREDIT" else "conta"
        conta_id = get_or_create_bank_account(conn, banco, tipo)
        try:
            transacoes_pluggy = pluggy_client.get_transactions(conta_pluggy["id"])
        except requests.RequestException:
            conn.close()
            return jsonify({"error": "nao consegui buscar as transacoes na Pluggy agora"}), 502
        transacoes = pluggy_client.normalizar_transacoes(transacoes_pluggy)
        novas = insert_bank_transactions(conn, conta_id, transacoes)
        resumo.append({"conta_id": conta_id, "tipo": tipo, "novas": novas})
    conn.close()

    return jsonify({"banco": banco, "contas": resumo})


@app.route("/api/metas", methods=["GET"])
def metas():
    conn = get_db()
    goals = list_goals(conn)
    conn.close()
    return jsonify([_calculo_meta(g) for g in goals])


@app.route("/api/metas/<int:goal_id>/guardar", methods=["POST"])
def guardar_meta(goal_id):
    valor = (request.json or {}).get("valor")
    if not isinstance(valor, (int, float)) or valor <= 0:
        return jsonify({"error": "informe um valor positivo"}), 400

    conn = get_db()
    add_to_goal(conn, goal_id, valor)
    goal = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    conn.close()
    if not goal:
        return jsonify({"error": "meta nao encontrada"}), 404
    return jsonify(_calculo_meta(dict(goal)))


@app.route("/api/construtora/resumo", methods=["GET"])
def construtora_resumo():
    base_url = os.environ.get("CONSTRUTORA_API_URL")
    api_key = os.environ.get("CONSTRUTORA_API_KEY")
    if not base_url or not api_key:
        return jsonify({"configurado": False})

    try:
        resp = requests.get(
            f"{base_url}/api/resumo", headers={"X-API-Key": api_key}, timeout=5
        )
        resp.raise_for_status()
    except requests.RequestException:
        return jsonify({"configurado": True, "erro": "Nao consegui falar com a API da construtora agora."}), 502

    return jsonify({"configurado": True, "dados": resp.json()})


@app.route("/api/push/status", methods=["GET"])
def push_status():
    return jsonify({"configurado": push_client.configurado(), "public_key": push_client.public_key()})


@app.route("/api/push/inscrever", methods=["POST"])
def push_inscrever():
    subscription = request.json or {}
    endpoint = subscription.get("endpoint")
    if not endpoint:
        return jsonify({"error": "inscricao invalida"}), 400
    conn = get_db()
    save_push_subscription(conn, endpoint, json.dumps(subscription))
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/push/testar", methods=["POST"])
def push_testar():
    if not push_client.configurado():
        return jsonify({"error": "notificacao push nao configurada - veja o README"}), 400

    conn = get_db()
    subscriptions = list_push_subscriptions(conn)
    enviados = 0
    for s in subscriptions:
        sub_dict = json.loads(s["subscription_json"])
        ok = push_client.enviar(
            sub_dict,
            "Painel Pessoal",
            "Notificacao de teste - se voce esta vendo isso, esta tudo funcionando!",
        )
        if ok:
            enviados += 1
        else:
            delete_push_subscription(conn, s["endpoint"])
    conn.close()
    return jsonify({"enviados": enviados, "total": len(subscriptions)})


def iniciar_scheduler():
    """So roda quando o app sobe de verdade (nao na chamada de recarga do
    Flask em modo debug, que sobe o processo duas vezes)."""
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(verificar_e_notificar, "interval", hours=3)
        scheduler.start()


if __name__ == "__main__":
    iniciar_scheduler()
    app.run(debug=True, port=5001)
