import base64
import binascii
import csv
import hashlib
import hmac
import io
import json
import math
import os
import sqlite3
import tempfile
import zipfile
from datetime import date, datetime, timedelta

import anthropic
import requests
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, render_template, request, send_file, session

load_dotenv()

import agenda
import aprendizado
import auth
import bank_ofx
import caldav_client
import claude_client
import clima
import criptografia
import estudo
import gastos
import leitura
import maps_client
import metar
import noticias
import notificacoes
import pluggy_client
import push_client
import streak
import telegram_bot
import uber_client
import viagem
import vida
import voos as voos_module
import db
from db import (
    CAMPOS_SAUDE,
    add_to_goal,
    adicionar_compra,
    ajustar_saldo_conta,
    alternar_item_viagem,
    alternar_rotina_item,
    apagar_espera,
    apagar_nota,
    atualizar_categoria_gasto,
    atualizar_saldo_conta,
    atualizar_uber_pedido,
    buscar_conta_por_nome,
    buscar_notas,
    complete_task,
    conta_paga,
    contar_hidratacao_dia,
    cotacao_por_titulo_aproximado,
    create_aprender,
    create_conta_pessoal,
    create_decisao,
    create_espera,
    create_goal,
    create_income,
    create_lembrete,
    create_lugar,
    create_manutencao,
    create_medicamento,
    create_medida_corporal,
    create_memoria,
    create_nota,
    create_pessoa,
    create_responder,
    create_rotina_item,
    create_salvo,
    create_viagem,
    create_voo,
    criar_cotacao,
    criar_item_cotacao,
    criar_uber_pedido,
    definir_apelido_gasto,
    definir_configuracao,
    definir_orcamento,
    delete_aprender,
    delete_compra,
    delete_conta_pessoal,
    delete_cotacao,
    delete_ficha_treino,
    delete_item_cotacao,
    delete_lembrete,
    delete_lugar,
    delete_manutencao,
    delete_medicamento,
    delete_medida_corporal,
    delete_memoria,
    delete_pessoa,
    delete_push_subscription,
    delete_rotina_item,
    delete_salvo,
    delete_viagem,
    delete_voo,
    descriptografar_linhas_export,
    espera_pendente_por_quem_aproximado,
    gasto_mes_por_categoria,
    get_checkin,
    get_cotacao,
    get_db,
    get_essencial,
    estatisticas_conta,
    get_or_create_bank_account,
    get_saude_dia,
    init_db,
    insert_bank_transactions,
    list_all_bank_transactions,
    list_bank_accounts,
    list_bank_transactions,
    list_saude_dados,
    ja_notificado_alguma_vez,
    ja_notificou_hoje,
    list_apelidos_gasto,
    list_aprender,
    list_chat_mensagens,
    list_checkins,
    list_compras_pendentes,
    list_contas_pessoais,
    list_conversas,
    list_cotacoes,
    list_decisoes,
    list_dias_ativos,
    list_esperas_pendentes,
    list_eventos_app,
    list_fichas_treino,
    list_goal_deposits,
    list_goals,
    list_incomes,
    list_itens_cotacao,
    list_itens_viagem,
    list_lembretes,
    list_lugares,
    list_manutencoes,
    list_medicamentos_ativos,
    list_medidas_corporais,
    list_memorias,
    list_notas,
    list_orcamentos,
    list_pessoas,
    list_push_subscriptions,
    list_responder_pendentes,
    list_rotina_itens,
    list_salvos,
    list_treinos,
    list_viagens_futuras,
    list_voos,
    marcar_aprender,
    marcar_comprado,
    marcar_conta_paga,
    marcar_manutencao_feita,
    marcar_notificado,
    marcar_ou_criar_feito,
    marcar_respondido,
    marcar_salvo_lido,
    media_passos_ultimos_dias,
    obter_configuracao,
    reclassificar_gasto_para_tarefa,
    reclassificar_tarefa_para_gasto,
    record_usage,
    registrar_atividade,
    registrar_conversa,
    registrar_correcao_classificacao,
    registrar_evento_app,
    registrar_hidratacao,
    registrar_interacao_aprendizado,
    registrar_treino,
    resolver_espera,
    responder_assinatura,
    respostas_assinaturas,
    rotina_marcadas,
    salvar_checkin,
    salvar_essencial,
    salvar_ficha_treino,
    salvar_mensagem_chat,
    save_push_subscription,
    substituir_itens_viagem,
    total_cost_usd,
    total_gastos_bancarios_mes,
    total_gastos_mes,
    total_incomes_mes,
    uber_pedido,
    uber_pedidos_aguardando_confirmacao,
    uber_pedidos_para_disparar,
    upsert_saude_dia,
)

app = Flask(__name__)
init_db()

_conn_inicial = get_db()
app.secret_key = auth.obter_ou_criar_secret_key(_conn_inicial)
_conn_inicial.close()
app.permanent_session_lifetime = timedelta(days=90)

# HttpOnly: JavaScript (mesmo em caso de XSS) nao consegue ler o cookie de sessao.
# SameSite=Lax: o cookie nao vai em requisicoes vindas de outro site (mitiga CSRF).
# Secure liga sozinho quando SECURE_COOKIES=true no .env (hospedado atras de HTTPS
# de verdade - ver deploy/DEPLOY.md) - forcar isso sempre quebraria o acesso local
# em HTTP puro (o navegador simplesmente nao envia cookie "Secure" fora de HTTPS).
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SECURE_COOKIES", "false").lower() in ("true", "1", "t", "yes")

CLAUDE_ERROR_MSG = "Erro ao falar com a IA. Tenta de novo em instantes."
CLAUDE_FORMAT_ERROR_MSG = "A IA respondeu em um formato inesperado. Tenta de novo."


def _log_usage(conn, usage: dict):
    record_usage(conn, usage["model"], usage["input_tokens"], usage["output_tokens"], usage["cost_usd"])


def _marcar_atividade(conn):
    registrar_atividade(conn, date.today().isoformat())


def _normalizar_hora(hora) -> str | None:
    """Valida e zero-preenche um horario "HH:MM" vindo da IA - nunca confia
    cegamente no formato (pode vir "9:00" em vez de "09:00", por exemplo),
    porque um horario sem zero a esquerda quebra a ordenacao por texto da
    agenda (comparado como string, "9:00" fica depois de "10:00")."""
    if not hora or not isinstance(hora, str):
        return None
    try:
        h, m = hora.strip().split(":")
        h, m = int(h), int(m)
    except (ValueError, AttributeError):
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return f"{h:02d}:{m:02d}"


def _corpo_json() -> dict:
    """request.json, mas sempre um dict - um JSON valido porem do tipo errado (lista,
    string, numero) faria qualquer `.get()` mais adiante derrubar a rota com um 500
    cru (AttributeError). Corpo malformado deve virar 400 controlado no maximo, nunca
    excecao nao tratada."""
    corpo = request.json
    return corpo if isinstance(corpo, dict) else {}


def _texto_seguro(valor, padrao: str = "") -> str:
    """Coage um campo de texto vindo do corpo da requisicao pra string, com
    seguranca - um numero/lista/bool/None no lugar de texto (corpo malformado,
    ex: {"text": 123}) vira o padrao em vez de derrubar a rota no .strip()."""
    return valor.strip() if isinstance(valor, str) else padrao


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
    dias = None
    if goal["prazo"]:
        hoje = date.today()
        prazo = date.fromisoformat(goal["prazo"])
        dias = (prazo - hoje).days
        meses = (prazo.year - hoje.year) * 12 + (prazo.month - hoje.month)
        if prazo.day < hoje.day:
            meses -= 1
        meses = max(meses, 1)
        por_mes = max(falta, 0) / meses
    return {**goal, "falta": falta, "meses_restantes": meses, "dias_restantes": dias, "por_mes": por_mes}


ROTAS_PUBLICAS = {"/login", "/configurar-pin", "/logout"}


@app.before_request
def _verificar_autenticacao():
    """Roda em TODA requisicao antes da rota de verdade - e aqui, no
    servidor, que a decisao "entra ou nao" e tomada. Abrir o Inspecionar/
    Console do navegador nao muda nada disso: o cookie de sessao e assinado
    (Flask usa `app.secret_key`) e HttpOnly (JS nem consegue ler ele), entao
    forjar acesso exigiria adivinhar o PIN de verdade, nao mexer no
    navegador."""
    path = request.path
    if path.startswith("/static/"):
        return None
    if path == "/healthz":
        return None
    # Integracao maquina-a-maquina (Atalho do iPhone) - cada uma tem o proprio
    # token (SAUDE_WEBHOOK_TOKEN / PAINEL_ATALHOS_TOKEN) checado dentro da
    # rota, nao usa sessao de login (o iPhone nao guarda cookie de sessao
    # entre execucoes do Atalho).
    if path in (
        "/api/saude/importar",
        "/api/atalho/capturar",
        "/api/atalho/cotacao-pdf",
        "/api/atalho/resumo",
        "/api/atalho/local",
        "/api/atalho/app",
    ):
        return None

    conn = get_db()
    try:
        pin_ja_configurado = auth.pin_configurado(conn)
    finally:
        conn.close()

    if not pin_ja_configurado:
        if path == "/configurar-pin":
            return None
        if path.startswith("/api/"):
            return jsonify({"error": "PIN de acesso ainda nao configurado."}), 401
        return redirect("/configurar-pin")

    if path in ROTAS_PUBLICAS:
        return None

    if not session.get("autenticado"):
        if path.startswith("/api/"):
            return jsonify({"error": "nao autenticado"}), 401
        return redirect("/login")
    return None


@app.route("/healthz", methods=["GET"])
def healthz():
    """Healthcheck pra monitoramento externo - sem autenticacao, sem dado
    sensivel, sem tocar no banco (nao pode falhar por causa de lock do
    SQLite nem depender do PIN estar configurado)."""
    return jsonify({"status": "ok"})


@app.route("/configurar-pin", methods=["GET", "POST"])
def configurar_pin():
    conn = get_db()
    try:
        if auth.pin_configurado(conn):
            if request.method == "POST":
                return jsonify({"error": "O PIN ja foi configurado."}), 400
            return redirect("/login")

        if request.method == "GET":
            return render_template("configurar_pin.html")

        corpo = _corpo_json()
        try:
            auth.definir_pin(conn, corpo.get("pin", ""), corpo.get("confirmacao", ""))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        session["autenticado"] = True
        session.permanent = True
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("autenticado"):
            return redirect("/")
        return render_template("login.html")

    ip = request.remote_addr or "desconhecido"
    conn = get_db()
    try:
        pode_tentar, msg_bloqueio = auth.verificar_bloqueio(conn, ip)
        if not pode_tentar:
            return jsonify({"error": msg_bloqueio}), 429

        corpo = _corpo_json()
        pin = corpo.get("pin", "")
        if auth.verificar_pin(conn, pin):
            auth.registrar_tentativa(conn, ip, sucesso=True)
            session["autenticado"] = True
            session.permanent = True
            return jsonify({"ok": True})

        auth.registrar_tentativa(conn, ip, sucesso=False)
        return jsonify({"error": "PIN incorreto."}), 401
    finally:
        conn.close()


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/")
def index():
    return render_template("index.html")


def _resposta_capture_cacheada(conn, client_id: str):
    """Devolve a resposta ja gravada pra esse client_id (ou None se nunca foi
    processado). So consultado quando o cliente manda client_id - o Atalho do
    iPhone nao manda, entao segue direto pro fluxo normal."""
    row = conn.execute(
        "SELECT response_json, status FROM capture_idempotency WHERE client_id = ?", (client_id,)
    ).fetchone()
    if not row:
        return None
    return jsonify(json.loads(row["response_json"])), row["status"]


def _gravar_resposta_capture(conn, client_id: str, corpo: dict, status: int):
    conn.execute(
        "INSERT OR REPLACE INTO capture_idempotency (client_id, response_json, status) VALUES (?, ?, ?)",
        (client_id, json.dumps(corpo), status),
    )
    # limpeza leve: nao deixa a tabela crescer pra sempre com o historico todo -
    # so precisa lembrar entradas recentes o bastante pra cobrir um reenvio da
    # fila offline (minutos/horas depois de voltar a conexao, nunca dias).
    conn.execute("DELETE FROM capture_idempotency WHERE criado_em < datetime('now', '-7 days')")


def _formatar_contexto_correcao(correcao: dict) -> str:
    """Traduz uma linha de correcoes_classificacao (aprendizado.correcao_semelhante)
    numa frase curta pra injetar no prompt de classificacao - texto puro, a
    decisao de usar isso ou nao continua sendo da IA, nunca um override
    silencioso aqui no Python."""
    de = correcao["tipo_errado"] or "algo"
    if correcao["categoria_errada"]:
        de += f' (categoria "{correcao["categoria_errada"]}")'
    para = correcao["tipo_certo"]
    if correcao["categoria_certa"]:
        para += f' (categoria "{correcao["categoria_certa"]}")'
    return (
        f'Um texto parecido ("{correcao["texto_original"]}") foi classificado como {de} '
        f"e o Alex corrigiu manualmente pra {para}."
    )


def _executar_captura(text: str, clarificacao: str, client_id: str = ""):
    """Classifica e grava um texto de captura (tarefa/gasto/meta) - usado
    tanto por /api/capture (sessao normal) quanto por /api/atalho/capturar
    (Atalho do iPhone, autenticado por token). Devolve (jsonify(...), status).

    client_id (opcional, so vem de /api/capture): id gerado no navegador pra
    cada captura enviada pela fila offline (IndexedDB, ver app.js). Se a mesma
    captura for reenviada (ex: a fila nao sabia se a primeira tentativa chegou
    a processar no servidor antes da conexao cair), devolve a resposta ja
    gravada em vez de duplicar a tarefa/gasto/meta."""
    if client_id:
        conn = get_db()
        cache = _resposta_capture_cacheada(conn, client_id)
        conn.close()
        if cache:
            return cache

    full_text = f"{text}. Contexto adicional: {clarificacao}" if clarificacao else text

    conn = get_db()
    # Aprendizado leve (aprendizado.py, estatistica pura sobre o proprio
    # historico - ver correcoes_classificacao): se um texto parecido ja foi
    # corrigido manualmente antes, isso vira contexto extra no prompt da IA,
    # que continua sendo quem decide - nunca um override silencioso aqui.
    correcao = aprendizado.correcao_semelhante(conn, full_text)
    contexto_correcao = _formatar_contexto_correcao(correcao) if correcao else None

    result, error = _call_claude(claude_client.classify_capture, full_text, contexto_correcao)
    if error:
        conn.close()
        return error
    parsed, usage = result

    _log_usage(conn, usage)

    # Se a IA ainda ficou em duvida, so pede esclarecimento uma vez (quando a
    # clarificacao ja foi enviada, seguimos com o melhor palpite mesmo assim).
    if parsed.get("duvida") and not clarificacao:
        corpo = {"duvida": parsed["duvida"], "texto_original": text}
        if client_id:
            _gravar_resposta_capture(conn, client_id, corpo, 200)
        conn.commit()
        conn.close()
        return jsonify(corpo), 200

    if parsed["tipo"] == "gasto":
        status_gasto = parsed.get("status") if parsed.get("status") in ("real", "planejado") else "real"
        conn.execute(
            "INSERT INTO expenses (amount, category, description, source_text, tipo) VALUES (?, ?, ?, ?, ?)",
            (parsed["valor"], parsed.get("categoria") or "outros", parsed["titulo"], full_text, status_gasto),
        )
    elif parsed["tipo"] == "meta":
        create_goal(conn, parsed["titulo"], parsed["valor"], parsed.get("prazo"))
    else:
        conn.execute(
            "INSERT INTO tasks (title, due_at, due_date, hora, source_text) VALUES (?, ?, ?, ?, ?)",
            (parsed["titulo"], parsed.get("quando"), parsed.get("quando_data"), _normalizar_hora(parsed.get("hora")), full_text),
        )

    if parsed.get("memoria"):
        create_memoria(conn, parsed["memoria"], full_text)

    if client_id:
        _gravar_resposta_capture(conn, client_id, parsed, 201)

    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify(parsed), 201


@app.route("/api/capture", methods=["POST"])
def capture():
    body = _corpo_json()
    text = _texto_seguro(body.get("text"))
    clarificacao = _texto_seguro(body.get("clarificacao"))
    client_id = _texto_seguro(body.get("client_id"))[:64]  # UUID cabe sobra; so um teto de sanidade
    if not text:
        return jsonify({"error": "texto vazio"}), 400
    return _executar_captura(text, clarificacao, client_id)


@app.route("/api/tasks", methods=["GET"])
def list_tasks():
    conn = get_db()
    materializar_tarefas_recorrentes(conn)
    rows = conn.execute(
        "SELECT * FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL "
        "ORDER BY created_at DESC"
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
    conn.close()

    hoje = date.today()
    tasks = []
    for row in rows:
        task = dict(row)
        task["subtasks"] = subtasks_por_task.get(task["id"], [])
        task["empacada_dias"] = vida.dias_empacada(task, task["subtasks"], hoje)
        task["fichas_treino"] = [f["id"] for f in vida.ficha_para_titulo(fichas, task["title"])]
        tasks.append(task)
    return jsonify(tasks)


@app.route("/api/tasks/<int:task_id>/complete", methods=["POST"])
def complete_task_rota(task_id):
    conn = get_db()
    complete_task(conn, task_id)
    _marcar_atividade(conn)
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
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/tasks/<int:task_id>/reclassificar", methods=["POST"])
def reclassificar_tarefa_rota(task_id):
    """Correcao rapida: a IA classificou como tarefa algo que na verdade era
    gasto. "valor" e obrigatorio - o texto original pode nao ter um numero
    claro, entao quem esta corrigindo (o Alex, nao a IA de novo) informa."""
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
        return jsonify({"error": "tarefa nao encontrada"}), 404

    resultado = reclassificar_tarefa_para_gasto(conn, task_id, float(valor), categoria, tipo)
    novo_id, subtasks_removidas = resultado
    registrar_correcao_classificacao(
        conn, task["source_text"] or task["title"], "tarefa", None, "gasto", categoria
    )
    _marcar_atividade(conn)
    conn.close()
    return jsonify({"ok": True, "novo_id": novo_id, "subtasks_removidas": subtasks_removidas})


@app.route("/api/expenses/<int:expense_id>/reclassificar", methods=["POST"])
def reclassificar_gasto_rota(expense_id):
    """Correcao rapida: a IA classificou como gasto algo que na verdade era
    tarefa. Campos de prazo sao opcionais (o corpo do gasto raramente tem
    essa informacao - fica null, como uma tarefa sem prazo definido)."""
    corpo = _corpo_json()
    due_at = corpo.get("quando") if isinstance(corpo.get("quando"), str) else None
    due_date = corpo.get("quando_data") if isinstance(corpo.get("quando_data"), str) else None
    hora = _normalizar_hora(corpo.get("hora"))

    conn = get_db()
    expense = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    if not expense:
        conn.close()
        return jsonify({"error": "gasto nao encontrado"}), 404

    novo_id = reclassificar_gasto_para_tarefa(conn, expense_id, due_at, due_date, hora)
    registrar_correcao_classificacao(
        conn, expense["source_text"] or expense["description"], "gasto", expense["category"], "tarefa", None
    )
    _marcar_atividade(conn)
    conn.close()
    return jsonify({"ok": True, "novo_id": novo_id})


@app.route("/api/expenses/<int:expense_id>/categoria", methods=["POST"])
def corrigir_categoria_gasto_rota(expense_id):
    """Correcao rapida: so a categoria do gasto saiu errada, tipo continua
    certo - nao precisa mover linha nenhuma entre tabelas."""
    corpo = _corpo_json()
    categoria = _texto_seguro(corpo.get("categoria"))
    if not categoria:
        return jsonify({"error": "categoria vazia"}), 400

    conn = get_db()
    expense = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    if not expense:
        conn.close()
        return jsonify({"error": "gasto nao encontrado"}), 404

    categoria_antiga = expense["category"]
    atualizar_categoria_gasto(conn, expense_id, categoria)
    if categoria_antiga != categoria:
        registrar_correcao_classificacao(
            conn,
            expense["source_text"] or expense["description"],
            "gasto",
            categoria_antiga,
            "gasto",
            categoria,
        )
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/expenses", methods=["GET"])
def list_expenses():
    conn = get_db()
    rows = conn.execute("SELECT * FROM expenses ORDER BY created_at DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/incomes", methods=["GET"])
def list_incomes_rota():
    conn = get_db()
    rows = list_incomes(conn, limit=50)
    conn.close()
    return jsonify(rows)


@app.route("/api/orcamentos", methods=["GET"])
def list_orcamentos_rota():
    conn = get_db()
    orcamentos = list_orcamentos(conn)
    ano_mes = date.today().strftime("%Y-%m")
    for o in orcamentos:
        o["gasto_mes"] = gasto_mes_por_categoria(conn, o["categoria"], ano_mes)
    conn.close()
    return jsonify(orcamentos)


@app.route("/api/gastos-fixos", methods=["GET"])
def gastos_fixos_rota():
    conn = get_db()
    resultado = _gastos_fixos(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/sobra-do-mes", methods=["GET"])
def sobra_do_mes_rota():
    conn = get_db()
    resultado = _sobra_do_mes(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/expenses/historico", methods=["GET"])
def expenses_historico():
    dias = request.args.get("dias", default=14, type=int)
    dias = min(max(dias, 1), 90)
    conn = get_db()
    rows = conn.execute("SELECT amount, created_at FROM expenses WHERE tipo = 'real'").fetchall()
    conn.close()
    historico = gastos.historico_diario([dict(r) for r in rows], dias, date.today())
    return jsonify(historico)


@app.route("/api/expenses/exportar-csv", methods=["GET"])
def exportar_expenses_csv():
    """CSV de todos os gastos (real e planejado) - sem limite de 50 como o
    /api/expenses normal, essa e feita pra abrir na planilha, nao pra tela."""
    conn = get_db()
    rows = conn.execute(
        "SELECT created_at, amount, category, tipo, description FROM expenses ORDER BY created_at"
    ).fetchall()
    conn.close()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["data", "valor", "categoria", "tipo", "descricao"])
    for r in rows:
        writer.writerow([r["created_at"], r["amount"], r["category"], r["tipo"], r["description"] or ""])

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=gastos.csv"},
    )


@app.route("/api/backup/exportar", methods=["GET"])
def exportar_backup():
    """Baixa uma copia consistente do banco inteiro - usa a API de backup do
    proprio sqlite3 (nao uma copia de arquivo crua), que tira um snapshot
    seguro mesmo com o banco em uso, sem lock nem risco de arquivo pela
    metade. Mesmo habito de backup do financeiro-construtora (AGENTS.md de
    la), aqui como export manual sob demanda em vez de automatico antes de
    escrita."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    origem = sqlite3.connect(db.DB_PATH)
    destino = sqlite3.connect(tmp.name)
    try:
        origem.backup(destino)
    finally:
        destino.close()
        origem.close()

    nome_arquivo = f"painel-backup-{date.today().isoformat()}.db"
    resposta = send_file(tmp.name, as_attachment=True, download_name=nome_arquivo, mimetype="application/octet-stream")
    resposta.call_on_close(lambda: os.unlink(tmp.name))
    return resposta


VERSAO_EXPORT_JSON = 1  # versao do FORMATO do export, nao da versao do app - so sobe se a
# estrutura do {"versao": ..., "tabelas": {...}} mudar de um jeito que quebre um import antigo


def _listar_tabelas(conn) -> list[str]:
    """Lista as tabelas de verdade do schema via introspeccao (sqlite_master),
    nunca uma lista hardcoded - assim uma tabela nova criada em db.py entra
    automaticamente no proximo export, sem precisar lembrar de atualizar isso
    aqui. Exclui tabelas internas do sqlite (sqlite_sequence etc)."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]


def _exportar_tabelas_dict(conn) -> dict:
    """Le todas as tabelas do banco pra um dict {nome_tabela: [linha, ...]} -
    usado tanto pelo export JSON quanto pelo CSV zipado, pra nao duplicar a
    logica de introspeccao/leitura entre os dois."""
    tabelas = {}
    for nome in _listar_tabelas(conn):
        # nome vem da propria introspeccao do sqlite_master, nunca de entrada
        # externa - seguro interpolar no SQL (nao da pra parametrizar nome de
        # tabela com "?" no sqlite3)
        linhas = conn.execute(f'SELECT * FROM "{nome}"').fetchall()
        # tabelas do escopo de criptografia (docs/SEGURANCA.md) saem
        # descriptografadas aqui - senao o export "legivel/pra planilha"
        # sairia com saldo/sono/etc como token cifrado ilegivel (achado de
        # revisao independente). O backup .db bruto continua cifrado.
        tabelas[nome] = descriptografar_linhas_export(nome, [dict(r) for r in linhas])
    return tabelas


@app.route("/api/backup/exportar-json", methods=["GET"])
def exportar_backup_json():
    """Export completo em JSON de TODAS as tabelas do banco (nao so gastos) -
    pensado pra restaurar o painel inteiro depois, diferente do
    /api/expenses/exportar-csv (so gastos, pra planilha) e do
    /api/backup/exportar (.db bruto, so restaura via SQLite direto)."""
    conn = get_db()
    try:
        tabelas = _exportar_tabelas_dict(conn)
    finally:
        conn.close()

    corpo = {
        "versao": VERSAO_EXPORT_JSON,
        "exportado_em": datetime.now().isoformat(timespec="seconds"),
        "tabelas": tabelas,
    }
    nome_arquivo = f"painel-backup-{date.today().isoformat()}.json"
    return Response(
        json.dumps(corpo, ensure_ascii=False, default=str),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"},
    )


@app.route("/api/backup/exportar-csv-completo", methods=["GET"])
def exportar_backup_csv_completo():
    """Export completo em CSV de TODAS as tabelas, um .csv por tabela dentro
    de um .zip - diferente do JSON (uma estrutura relacional so faz sentido
    achatada em varios arquivos, nao um CSV unico) e do
    /api/expenses/exportar-csv (so gastos)."""
    conn = get_db()
    try:
        tabelas = _exportar_tabelas_dict(conn)
    finally:
        conn.close()

    buffer_zip = io.BytesIO()
    with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for nome, linhas in tabelas.items():
            buffer_csv = io.StringIO()
            writer = csv.writer(buffer_csv)
            if linhas:
                colunas = list(linhas[0].keys())
                writer.writerow(colunas)
                for linha in linhas:
                    writer.writerow([linha[c] for c in colunas])
            # tabela vazia ainda gera um .csv (sem cabecalho, ja que sem
            # linhas nao da pra saber as colunas so pelo select) - melhor um
            # arquivo vazio presente do que a tabela sumir silenciosamente
            # do zip
            zf.writestr(f"{nome}.csv", buffer_csv.getvalue())
    buffer_zip.seek(0)

    nome_arquivo = f"painel-backup-csv-{date.today().isoformat()}.zip"
    resposta = send_file(
        buffer_zip,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype="application/zip",
    )
    return resposta


def gerar_backup_arquivo(destino: str) -> None:
    """Salva uma copia consistente do banco em `destino` via sqlite3.backup()
    (mesma tecnica do /api/backup/exportar) - nunca uma copia de arquivo
    crua, que podia pegar o banco no meio de uma escrita. Compartilhada pelo
    endpoint manual futuro e pelo job semanal do scheduler."""
    origem = sqlite3.connect(db.DB_PATH)
    dest_conn = sqlite3.connect(destino)
    try:
        origem.backup(dest_conn)
    finally:
        dest_conn.close()
        origem.close()


def _diretorio_backups() -> str:
    return os.environ.get("BACKUP_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "backups")


BACKUP_AUTOMATICO_MANTER = 8  # ~2 meses de backups semanais


def rodar_backup_automatico_semanal():
    """Job do scheduler (ver iniciar_scheduler): tira uma copia semanal do
    banco pra BACKUP_DIR, apaga os mais antigos alem de
    BACKUP_AUTOMATICO_MANTER, e manda copia pro Telegram do Alex se
    configurado (copia fora do disco do servidor - se o disco morrer, o
    Telegram ainda tem uma copia recente). Resiliente de proposito: qualquer
    erro (disco cheio, permissao, rede do Telegram fora do ar) e' logado e
    engolido aqui, nunca derruba o scheduler nem o resto do app - um backup
    automatico que falha silenciosamente e' melhor que travar o painel
    inteiro por causa dele."""
    try:
        diretorio = _diretorio_backups()
        os.makedirs(diretorio, exist_ok=True)
        carimbo = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        caminho = os.path.join(diretorio, f"painel-backup-{carimbo}.db")
        gerar_backup_arquivo(caminho)

        # rotacao: mantem so os N mais recentes (ordenados por nome, que ja
        # carrega o carimbo de data/hora - nao depende de mtime do
        # filesystem, que pode ser preservado errado em alguma copia/restore)
        existentes = sorted(
            f for f in os.listdir(diretorio) if f.startswith("painel-backup-") and f.endswith(".db")
        )
        for antigo in existentes[:-BACKUP_AUTOMATICO_MANTER]:
            try:
                os.unlink(os.path.join(diretorio, antigo))
            except OSError as e:
                app.logger.error("backup automatico: falha ao apagar backup antigo %s: %s", antigo, e)

        if telegram_bot.configurado():
            try:
                telegram_bot.enviar_documento(
                    caminho, legenda=f"Backup automatico semanal do painel - {date.today().isoformat()}"
                )
            except Exception as e:  # nunca deixa uma falha do Telegram derrubar o backup local
                app.logger.error("backup automatico: falha ao enviar pro Telegram: %s", e)
    except Exception as e:
        # ultima rede de seguranca - qualquer coisa inesperada aqui (disco
        # cheio, permissao negada, etc.) fica so no log, o scheduler segue
        # rodando normalmente na proxima semana
        app.logger.error("backup automatico semanal falhou: %s", e)


@app.route("/api/gastos/resumo-semanal", methods=["GET"])
def gastos_resumo_semanal():
    conn = get_db()
    rows = conn.execute(
        "SELECT amount, category, created_at FROM expenses WHERE tipo = 'real'"
    ).fetchall()
    conn.close()
    return jsonify(gastos.resumo_semanal([dict(r) for r in rows], date.today()))


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


_CACHE_CONSTRUTORA = {}  # chave -> (timestamp, dados)
_CACHE_CONSTRUTORA_TTL_SEGUNDOS = 60


def _cache_construtora_get(chave: str):
    """None tanto pra 'nunca guardado' quanto pra 'expirou' - o chamador trata os
    dois igual (vai buscar de novo)."""
    entrada = _CACHE_CONSTRUTORA.get(chave)
    if not entrada:
        return None
    timestamp, dados = entrada
    if datetime.now().timestamp() - timestamp > _CACHE_CONSTRUTORA_TTL_SEGUNDOS:
        return None
    return dados


def _cache_construtora_set(chave: str, dados):
    _CACHE_CONSTRUTORA[chave] = (datetime.now().timestamp(), dados)


def _buscar_resumo_construtora() -> dict | None:
    """Busca o resumo financeiro na API da construtora - None se nao configurado ou
    se a chamada falhar por qualquer motivo (nunca quebra quem chamar). Cacheado por
    60s (mesmo processo) - o resumo do dia, o chat e a aba Construtora podem pedir
    isso tudo em sequencia rapida, e o lado da construtora tem rate limit de 20
    req/min por IP na integracao externa."""
    base_url = os.environ.get("CONSTRUTORA_API_URL")
    api_key = os.environ.get("CONSTRUTORA_API_KEY")
    if not base_url or not api_key:
        return None
    cacheado = _cache_construtora_get("resumo")
    if cacheado is not None:
        return cacheado
    try:
        resp = requests.get(f"{base_url}/api/resumo", headers={"X-API-Key": api_key}, timeout=5)
        resp.raise_for_status()
        dados = resp.json()
        _cache_construtora_set("resumo", dados)
        return dados
    except requests.RequestException:
        return None


def _buscar_contas_a_vencer_construtora(dias: int = 30) -> dict | None:
    """Busca as contas a pagar a vencer/vencidas na API da construtora - None se nao
    configurado ou se a chamada falhar por qualquer motivo (nunca quebra quem chamar).
    Mesmo cache de 60s de `_buscar_resumo_construtora`, por chave separada (o `dias`
    pedido pode variar)."""
    base_url = os.environ.get("CONSTRUTORA_API_URL")
    api_key = os.environ.get("CONSTRUTORA_API_KEY")
    if not base_url or not api_key:
        return None
    cache_chave = f"contas:{dias}"
    cacheado = _cache_construtora_get(cache_chave)
    if cacheado is not None:
        return cacheado
    try:
        resp = requests.get(
            f"{base_url}/api/contas_a_vencer",
            headers={"X-API-Key": api_key},
            params={"dias": dias},
            timeout=5,
        )
        resp.raise_for_status()
        dados = resp.json()
        _cache_construtora_set(cache_chave, dados)
        return dados
    except requests.RequestException:
        return None


def _ajustar_saldo_se_banco_citado(conn, banco: str | None, delta: float) -> dict | None:
    """Se o Alex citou um banco no chat E aquela conta ja tem saldo sincronizado
    (via Pluggy), aplica o ajuste otimista e devolve {"banco", "antes", "depois"}
    pra entrar na resposta. Devolve None em qualquer outro caso - sem banco
    citado, sem conta parecida, ou conta sem saldo conhecido ainda - nunca
    inventa um saldo."""
    if not banco:
        return None
    conta = buscar_conta_por_nome(conn, banco)
    if not conta:
        return None
    ajuste = ajustar_saldo_conta(conn, conta["id"], delta)
    if ajuste is None:
        return None
    saldo_antes, saldo_depois = ajuste
    return {"banco": conta["banco"], "antes": saldo_antes, "depois": saldo_depois}


def _id_estavel_conta(conta: dict) -> int:
    """ID estavel (mesmos dados -> mesmo numero) pra dar pra `notificacoes_enviadas`
    deduplicar - a API externa da construtora nao expoe o id real da linha no banco dela
    (decisao deles: 'so o essencial'), entao deriva um a partir dos campos que a
    identificam. Muda se a conta for editada do lado da construtora, o que so faz a
    notificacao repetir, nunca sumir - comportamento seguro."""
    chave = f"{conta.get('vencimento')}|{conta.get('valor')}|{conta.get('fornecedor')}|{conta.get('descricao')}"
    digest = hashlib.sha1(chave.encode("utf-8")).digest()[:8]
    return int.from_bytes(digest, "big") % (2**62)


def _id_estavel_evento_calendario(evento: dict) -> int:
    """Mesma ideia de _id_estavel_conta - evento do iCloud nao tem id
    numerico exposto pra gente (so o objeto do CalDAV), entao deriva um a
    partir do titulo+inicio pra deduplicar o aviso de "daqui a pouco"."""
    chave = f"{evento.get('titulo')}|{evento.get('inicio')}"
    digest = hashlib.sha1(chave.encode("utf-8")).digest()[:8]
    return int.from_bytes(digest, "big") % (2**62)


def _gastos_reais_unificados(conn) -> list[dict]:
    """Todo gasto real que a gente sabe que aconteceu - tanto o que foi
    digitado no chat (expenses) quanto o que veio sozinho do extrato
    bancario sincronizado (bank_transactions, OFX ou Pluggy) - normalizado
    num formato so. Sem isso, deteccao de recorrencia e sobra do mes
    enxergariam so o que foi digitado na mao, perdendo a maior parte do
    gasto de quem usa a sincronizacao bancaria pra nao precisar digitar
    nada. Risco conhecido: se o Alex as vezes digita no chat uma compra que
    TAMBEM vai aparecer no banco depois, ela conta duas vezes - nao tem
    reconciliacao entre as duas fontes ainda (mesma ressalva que a aba
    Bancos ja tem sobre confiar cegamente no total importado)."""
    expenses_reais = conn.execute(
        "SELECT amount, category, description, source_text, created_at FROM expenses WHERE tipo = 'real'"
    ).fetchall()
    unificado = [dict(r) for r in expenses_reais]
    # valor/descricao sao criptografados em repouso - list_all_bank_transactions
    # ja devolve descriptografado, entao o filtro "valor < 0" (que era WHERE no
    # SQL) precisa vir depois, em Python.
    for r in list_all_bank_transactions(conn):
        if r["valor"] is None or r["valor"] >= 0:
            continue
        unificado.append(
            {
                "amount": -r["valor"],
                "category": r["categoria"] or "outros",
                "description": r["descricao"],
                "source_text": None,
                "created_at": r["data"],
            }
        )
    return unificado


def _gastos_fixos(conn) -> dict:
    reais = _gastos_reais_unificados(conn)
    apelidos = {(a["descricao_normalizada"], a["valor"]): a["apelido"] for a in list_apelidos_gasto(conn)}
    reais = gastos.aplicar_apelidos(reais, apelidos)
    recorrentes = gastos.detectar_gastos_recorrentes(reais, date.today())
    return {"recorrentes": recorrentes, "total_mensal": gastos.total_gasto_fixo_mensal(recorrentes)}


def _sobra_do_mes(conn) -> dict:
    hoje = date.today()
    ano_mes = hoje.strftime("%Y-%m")
    renda = total_incomes_mes(conn, ano_mes)
    gasto_real = total_gastos_mes(conn, ano_mes, "real") + total_gastos_bancarios_mes(conn, ano_mes)
    gasto_planejado = total_gastos_mes(conn, ano_mes, "planejado")
    contas_pendentes = sum(
        c["valor"]
        for c in _contas_pessoais_com_status(conn, hoje)
        # vencida e ainda nao paga (ate 10 dias) tambem vai sair do bolso
        if c["valor"] is not None and not c["paga"]
        and (c["dias_ate_vencer"] < 0 or c["proximo_vencimento"][:7] == ano_mes)
    )
    return {
        **gastos.sobra_do_mes(renda, gasto_real, gasto_planejado),
        "projecao": vida.projecao_fim_do_mes(renda, gasto_real, contas_pendentes, hoje),
    }


def _id_estavel_orcamento(categoria: str, nivel: str, ano_mes: str) -> int:
    """Mesma ideia de _id_estavel_conta - o aviso de orcamento e "uma vez por
    categoria+nivel+mes" (nao por dia), entao o mes entra na chave: o mes
    seguinte, com o gasto zerado de novo, ganha uma chave nova sozinho, sem
    precisar resetar nada manualmente."""
    chave = f"{categoria}|{nivel}|{ano_mes}"
    digest = hashlib.sha1(chave.encode("utf-8")).digest()[:8]
    return int.from_bytes(digest, "big") % (2**62)


def _id_estavel_cobranca_generica(descricao_normalizada: str, valor: float) -> int:
    """Mesma ideia de _id_estavel_orcamento - identifica uma cobranca
    generica pela descricao+valor (nao ha id de linha unico, ja que a
    cobranca pode vir tanto de expenses quanto de bank_transactions)."""
    chave = f"{descricao_normalizada}|{valor}"
    digest = hashlib.sha1(chave.encode("utf-8")).digest()[:8]
    return int.from_bytes(digest, "big") % (2**62)


def _construtora_contexto_contas() -> str | None:
    """Frase factual sobre a proxima conta a pagar da construtora (vencendo ou ja
    vencida) pro resumo do dia / chat - so numeros que ja vieram prontos da API,
    nenhuma conta feita aqui nem pela IA."""
    dados = _buscar_contas_a_vencer_construtora(dias=30)
    if not dados or dados.get("status") != "ok":
        return None
    contas = dados.get("contas") or []
    if not contas:
        return None
    proxima = contas[0]
    dias_ate = proxima["dias_ate_vencer"]
    if dias_ate < 0:
        quando = f"vencida ha {abs(dias_ate)} dia(s)"
    elif dias_ate == 0:
        quando = "vence hoje"
    else:
        quando = f"vence em {dias_ate} dia(s)"
    quem = proxima.get("fornecedor") or proxima.get("descricao") or "fornecedor nao informado"
    extra = f", mais {len(contas) - 1} outra(s) conta(s) em aberto" if len(contas) > 1 else ""
    return f"proxima conta a pagar da construtora: {quem}, R$ {proxima['valor']:.2f}, {quando}{extra}"


def _construtora_contexto_resumo() -> str | None:
    """Frase factual pro resumo do dia / chat - so numeros que ja vieram prontos da
    API da construtora, nenhuma conta feita aqui nem pela IA."""
    dados = _buscar_resumo_construtora()
    if not dados or dados.get("status") != "ok":
        return None
    texto = (
        f"entradas R$ {dados['tot_entradas']:.2f}, saidas R$ {dados['tot_saidas']:.2f}, "
        f"lucro liquido R$ {dados['lucro_liquido']:.2f}, margem {dados['margem']:.1f}%"
    )
    contas_texto = _construtora_contexto_contas()
    if contas_texto:
        texto += f"; {contas_texto}"
    return texto


def _clima_contexto_resumo() -> str | None:
    """Frase factual sobre risco de chuva hoje na cidade padrao (CIDADE_PADRAO)
    pro resumo do dia / chat - so aparece se a cidade estiver configurada;
    nunca decide nada, so relata o que o Open-Meteo devolveu."""
    cidade = os.environ.get("CIDADE_PADRAO", "").strip()
    if not cidade:
        return None
    resumo = clima.resumo_chuva_hoje_para_cidade(cidade)
    if not resumo:
        return None
    return resumo["texto"]


def materializar_tarefas_recorrentes(conn, hoje: date | None = None) -> int:
    """Cria a instancia de HOJE pra cada tarefa-modelo recorrente cujo padrao
    bate com o dia da semana de hoje e que ainda nao tem instancia criada.
    Modelo = linha com `recorrencia` preenchida e `due_date` sempre NULL -
    nunca aparece ela mesma em lista nenhuma (todas as queries de listagem
    de tarefa excluem `recorrencia IS NOT NULL`), so a instancia gerada
    (due_date=hoje, recorrencia NULL, recorrente_origem_id apontando de
    volta pro modelo) e que e uma tarefa de verdade, completavel como
    qualquer outra.

    Idempotente de proposito - seguro chamar em varios pontos (scheduler,
    /api/tasks, /api/calendario/hoje) sem risco de duplicar, ja que sempre
    confere se a instancia de hoje ja existe antes de criar."""
    hoje = hoje or date.today()
    hoje_iso = hoje.isoformat()
    modelos = conn.execute(
        "SELECT id, title, hora, depende_do_tempo, recorrencia FROM tasks "
        "WHERE recorrencia IS NOT NULL AND due_date IS NULL"
    ).fetchall()
    criadas = 0
    for m in modelos:
        if not agenda.recorrencia_bate_no_dia(m["recorrencia"], hoje):
            continue
        ja_existe = conn.execute(
            "SELECT 1 FROM tasks WHERE recorrente_origem_id = ? AND due_date = ?",
            (m["id"], hoje_iso),
        ).fetchone()
        if ja_existe:
            continue
        conn.execute(
            "INSERT INTO tasks (title, due_date, hora, depende_do_tempo, recorrente_origem_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (m["title"], hoje_iso, m["hora"], m["depende_do_tempo"], m["id"]),
        )
        criadas += 1
    if criadas:
        conn.commit()
    return criadas


def _tarefas_com_horario_hoje(conn) -> list[dict]:
    """Tarefas pendentes com horario marcado pra hoje, no mesmo formato dos
    eventos do iCloud - pra virarem ancoras de horario fixo junto com eles.
    So pendentes de proposito (quem consome isso - plano do dia, resumo,
    notificacoes - nao pode ver trabalho ja feito como se ainda faltasse)."""
    hoje = date.today().isoformat()
    rows = conn.execute(
        "SELECT title, hora FROM tasks WHERE completed_at IS NULL AND due_date = ? AND hora IS NOT NULL",
        (hoje,),
    ).fetchall()
    return [
        {
            "titulo": r["title"],
            "inicio": f"{hoje}T{r['hora']}:00",
            "fim": f"{hoje}T{r['hora']}:00",
            "dia_inteiro": False,
            "origem": "tarefa",
            "concluido": False,
        }
        for r in rows
    ]


def _tarefas_concluidas_com_horario_hoje(conn) -> list[dict]:
    """So pra bolinha da agenda poder ficar verde (pedido explicito: "se
    fossem concluidas, ja ficassem verdes"). Deliberadamente SEPARADA de
    _tarefas_com_horario_hoje (que so devolve pendentes, de proposito) -
    misturar concluidas ali afetaria plano do dia/notificacoes/resumo, que
    dependem de ver so o que ainda falta. So o endpoint da agenda (consumo
    puramente visual) usa esta aqui."""
    hoje = date.today().isoformat()
    rows = conn.execute(
        "SELECT title, hora FROM tasks WHERE completed_at IS NOT NULL AND due_date = ? AND hora IS NOT NULL",
        (hoje,),
    ).fetchall()
    return [
        {
            "titulo": r["title"],
            "inicio": f"{hoje}T{r['hora']}:00",
            "fim": f"{hoje}T{r['hora']}:00",
            "dia_inteiro": False,
            "origem": "tarefa",
            "concluido": True,
        }
        for r in rows
    ]


def _compromissos_de_hoje(conn, eventos_icloud: list[dict]) -> list[dict]:
    """Junta os eventos do iCloud com as tarefas que tem horario marcado pra
    hoje, tudo ordenado por horario - assim um compromisso mencionado depois
    numa conversa (mas mais cedo no dia) nao fica fora de ordem na agenda."""
    compromissos = [dict(e, origem="calendario") for e in eventos_icloud]
    compromissos += _tarefas_com_horario_hoje(conn)
    compromissos.sort(key=lambda e: e["inicio"])
    return compromissos


def _eventos_de_hoje_com_seguranca(conn) -> list[dict]:
    """A agenda do iCloud via CalDAV e instavel (ver caldav_client.py) - se
    falhar, o resumo do dia nao pode quebrar por causa disso. Combina o que
    conseguir buscar do iCloud com as tarefas com horario marcado pra hoje."""
    icloud = []
    if caldav_client.configurado():
        try:
            icloud = caldav_client.eventos_do_dia(date.today())
        except Exception:
            icloud = []
    return _compromissos_de_hoje(conn, icloud)


def _resumo_falado_manha(conn) -> str:
    """Texto curto pro resumo falado da manha (US-C11) - agenda de hoje
    (_eventos_de_hoje_com_seguranca, ja existente, resiliente a falha do
    iCloud) + gasto de ontem/tarefas pendentes
    (notificacoes.resumo_manha_gastos_pendentes, sem rede). So monta texto
    factual, sem IA - mesmo espirito de mensagem_fechamento_noturno. O TTS
    em si (converter esse texto em audio) reaproveita o mecanismo ja
    existente no navegador (falarTexto/SpeechSynthesis, o mesmo botao
    "ouvir" ja usado no METAR/TAF e nas respostas do chat) - nada novo pro
    servidor gerar aqui."""
    eventos = [e for e in _eventos_de_hoje_com_seguranca(conn) if not e.get("dia_inteiro")]
    if not eventos:
        agenda_texto = "Nenhum compromisso marcado pra hoje."
    elif len(eventos) == 1:
        agenda_texto = f"1 compromisso hoje: \"{eventos[0]['titulo']}\" as {eventos[0]['inicio'][11:16]}."
    else:
        agenda_texto = f"{len(eventos)} compromissos hoje."
    return f"Bom dia. {agenda_texto} {notificacoes.resumo_manha_gastos_pendentes(conn)}"


@app.route("/api/resumo-manha", methods=["GET"])
def resumo_manha_rota():
    conn = get_db()
    texto = _resumo_falado_manha(conn)
    conn.close()
    return jsonify({"texto": texto})


@app.route("/api/summary/today", methods=["GET"])
def summary_today():
    today = date.today().isoformat()
    conn = get_db()
    materializar_tarefas_recorrentes(conn)
    done = conn.execute("SELECT title FROM tasks WHERE date(completed_at) = ?", (today,)).fetchall()
    pending = conn.execute(
        "SELECT title FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL"
    ).fetchall()
    expenses = conn.execute(
        "SELECT amount, category FROM expenses WHERE date(created_at) = ? AND tipo = 'real'", (today,)
    ).fetchall()
    gasto_hoje = sum(r["amount"] for r in expenses)
    gasto_planejado = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE date(created_at) = ? AND tipo = 'planejado'",
        (today,),
    ).fetchone()["total"]
    eventos = _eventos_de_hoje_com_seguranca(conn)
    memorias = list_memorias(conn)
    saude = _saude_contexto_resumo(conn)
    construtora = _construtora_contexto_resumo()
    clima_hoje = _clima_contexto_resumo()

    result, error = _call_claude(
        claude_client.summarize_day,
        [r["title"] for r in done],
        [r["title"] for r in pending],
        [dict(r) for r in expenses],
        [e["titulo"] for e in eventos],
        [m["texto"] for m in memorias],
        saude,
        construtora,
        clima_hoje,
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
            "gasto_planejado": gasto_planejado,
            "tarefas_concluidas": len(done),
            "eventos_hoje": len(eventos),
        }
    )


def _tarefas_pendentes_sem_horario_hoje(conn):
    """Tarefas pendentes que NAO viram ancora de horario fixo hoje - ou
    porque nao tem hora marcada, ou porque a hora e de outro dia. Evita
    listar a mesma tarefa duas vezes (como compromisso e como tarefa solta)
    pro plano do dia."""
    hoje = date.today().isoformat()
    return conn.execute(
        "SELECT title FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL "
        "AND NOT (due_date = ? AND hora IS NOT NULL)",
        (hoje,),
    ).fetchall()


@app.route("/api/fechamento-do-dia", methods=["GET"])
def fechamento_do_dia():
    """Ritual de fechamento (inspirado no 'shutdown' do Sunsama): o que foi
    concluido hoje e o que ainda ficou marcado pra hoje e nao foi feito -
    sem cobranca, a tarefa continua pendente naturalmente e reaparece
    amanha, isso aqui e so uma fotografia pra fechar o dia com a cabeca
    tranquila."""
    hoje = date.today().isoformat()
    conn = get_db()
    concluidas = conn.execute(
        "SELECT title FROM tasks WHERE date(completed_at) = ? ORDER BY completed_at", (hoje,)
    ).fetchall()
    pendentes_hoje = conn.execute(
        "SELECT title FROM tasks WHERE completed_at IS NULL AND due_date = ? "
        "ORDER BY hora IS NULL, hora",
        (hoje,),
    ).fetchall()
    conn.close()
    return jsonify(
        {
            "concluidas": [r["title"] for r in concluidas],
            "pendentes_hoje": [r["title"] for r in pendentes_hoje],
        }
    )


@app.route("/api/calendario/hoje", methods=["GET"])
def calendario_hoje():
    conn = get_db()
    materializar_tarefas_recorrentes(conn)
    configurado = caldav_client.configurado()
    erro = None
    icloud_eventos = []
    if configurado:
        try:
            icloud_eventos = caldav_client.eventos_do_dia(date.today())
        except Exception:
            erro = "Nao consegui falar com o iCloud agora."
    eventos = _compromissos_de_hoje(conn, icloud_eventos)
    eventos += _tarefas_concluidas_com_horario_hoje(conn)
    eventos.sort(key=lambda e: e["inicio"])
    conn.close()
    resposta = {"configurado": configurado, "eventos": eventos}
    if erro:
        resposta["erro"] = erro
    return jsonify(resposta)


@app.route("/api/plano-do-dia", methods=["POST"])
def plano_do_dia():
    conn = get_db()
    pending = _tarefas_pendentes_sem_horario_hoje(conn)
    eventos = _eventos_de_hoje_com_seguranca(conn)
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
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"plano": texto})


def _contexto_chat(conn) -> str:
    """Resumo factual do agora pro chat usar como contexto - mesma logica
    do resumo do dia, so que em formato de linhas pro system prompt."""
    hoje = date.today().isoformat()
    pendentes = _tarefas_pendentes_sem_horario_hoje(conn)
    gasto_hoje = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE date(created_at) = ? AND tipo = 'real'",
        (hoje,),
    ).fetchone()["total"]
    gasto_planejado = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE date(created_at) = ? AND tipo = 'planejado'",
        (hoje,),
    ).fetchone()["total"]
    eventos = _eventos_de_hoje_com_seguranca(conn)
    saude = _saude_contexto_resumo(conn)
    construtora = _construtora_contexto_resumo()
    clima_hoje = _clima_contexto_resumo()
    proximos_voos = voos_module.proximos_voos(list_voos(conn), date.today())

    eventos_txt = ", ".join(
        f"{e['titulo']} as {e['inicio'][11:16]}" if not e.get("dia_inteiro") else f"{e['titulo']} (dia todo)"
        for e in eventos
    )
    linhas = [
        f"Tarefas pendentes: {', '.join(r['title'] for r in pendentes) or 'nenhuma'}",
        f"Gasto de hoje (ja realizado): R$ {gasto_hoje:.2f}",
        f"Gasto planejado/cogitado hoje (ainda nao decidido): R$ {gasto_planejado:.2f}",
        f"Compromissos de hoje (em ordem de horario): {eventos_txt or 'nenhum'}",
    ]
    if saude:
        linhas.append(f"Saude hoje: {saude}")
    if construtora:
        linhas.append(f"Construtora (financeiro geral): {construtora}")
    if clima_hoje:
        linhas.append(f"Previsao do tempo hoje: {clima_hoje}")
    if proximos_voos:
        voos_txt = ", ".join(
            f"{v['data']} pra {v['destino']}" + (f" ({v['horas']}h)" if v.get("horas") else "")
            for v in proximos_voos
        )
        linhas.append(f"Proximos voos agendados: {voos_txt}")
    esperas_pendentes = list_esperas_pendentes(conn)
    if esperas_pendentes:
        esperas_txt = ", ".join(f"{e['quem']} sobre \"{e['sobre']}\"" for e in esperas_pendentes)
        linhas.append(f"Esperando resposta de: {esperas_txt}")
    plano_pendente_bruto = obter_configuracao(conn, "plano_semana_pendente")
    if plano_pendente_bruto:
        try:
            plano_pendente = json.loads(plano_pendente_bruto)
        except ValueError:
            plano_pendente = []
        if plano_pendente:
            plano_txt = ", ".join(f"{p['titulo']} ({p['dia']} as {p['hora']})" for p in plano_pendente)
            linhas.append(
                f"Plano de semana proposto AGUARDANDO confirmacao do Alex (ainda NAO foi criado "
                f"no banco): {plano_txt}. Se ele confirmar, chame confirmar_plano_semana; se "
                f"rejeitar/pedir pra esquecer, chame cancelar_plano_semana."
            )
    return "\n".join(linhas)


def _carga_por_dia(conn, dias: list[date]) -> dict[str, int]:
    """Quantas tarefas pendentes ja estao marcadas em cada dia (entre os
    'dias' dados) - usado so pra decidir qual dia esta mais livre pra
    sugerir uma tarefa nova sem data fixa, nunca pra nada critico."""
    if not dias:
        return {}
    rows = conn.execute(
        "SELECT due_date, COUNT(*) AS n FROM tasks WHERE completed_at IS NULL "
        "AND due_date BETWEEN ? AND ? GROUP BY due_date",
        (dias[0].isoformat(), dias[-1].isoformat()),
    ).fetchall()
    return {r["due_date"]: r["n"] for r in rows}


def _resolver_cotacao_por_titulo(conn, titulo: str) -> int:
    """Acha a cotacao existente com titulo parecido, ou cria uma nova - usado
    tanto pelo chat (registrar_item_cotacao) quanto pelo Atalho do iPhone que
    manda PDF direto, pra nao precisar saber o ID numerico da cotacao."""
    cotacao = cotacao_por_titulo_aproximado(conn, titulo)
    return cotacao["id"] if cotacao else criar_cotacao(conn, titulo)


def _processar_mensagem_chat(conn, texto: str) -> tuple[str | None, list[str], str | None]:
    """Roda o pipeline inteiro de chat (contexto + tool-use + persistencia) -
    fonte unica de verdade da conversa, usada tanto pela rota HTTP /api/chat
    quanto pelo bot do Telegram, pra nenhum dos dois canais reimplementar a
    logica de tool-use (nem arriscar os dois divergirem). Devolve
    (resposta, acoes, None) no sucesso, ou (None, [], mensagem_de_erro)."""
    materializar_tarefas_recorrentes(conn)
    historico = list(reversed(list_chat_mensagens(conn, limit=20)))
    mensagens = [{"role": r["papel"], "content": r["texto"]} for r in historico]
    mensagens.append({"role": "user", "content": texto})

    memorias_texto = [m["texto"] for m in list_memorias(conn)]
    contexto = _contexto_chat(conn)

    def exec_registrar_tarefa(entrada):
        recorrencia = entrada.get("recorrencia")
        if recorrencia:
            if not agenda.recorrencia_valida(recorrencia):
                return {"erro": f"recorrencia mal formatada: {recorrencia!r}"}
            # Rotina recorrente vira um MODELO (due_date/due_at sempre NULL,
            # nunca some da tela mesmo apos "completar" a instancia do dia -
            # ver materializar_tarefas_recorrentes). 'quando'/'quando_data'
            # nao fazem sentido aqui (nao e um item de um dia so) - ignorados
            # de proposito mesmo se vierem preenchidos.
            conn.execute(
                "INSERT INTO tasks (title, hora, source_text, depende_do_tempo, recorrencia) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    entrada["titulo"],
                    _normalizar_hora(entrada.get("hora")),
                    texto,
                    int(bool(entrada.get("depende_do_tempo"))),
                    recorrencia,
                ),
            )
            conn.commit()
            materializar_tarefas_recorrentes(conn)
            return {"ok": True, "recorrente": True}

        quando_data = entrada.get("quando_data")
        conn.execute(
            "INSERT INTO tasks (title, due_at, due_date, hora, source_text, depende_do_tempo) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                entrada["titulo"],
                entrada.get("quando"),
                quando_data,
                _normalizar_hora(entrada.get("hora")),
                texto,
                int(bool(entrada.get("depende_do_tempo"))),
            ),
        )
        conn.commit()
        resultado = {"ok": True}
        # so oferece sugestao de dia quando a tarefa ficou com data vaga
        # ("essa semana") - com dia certo (quando_data) ou sem nenhuma pista
        # de tempo (entrada.get("quando") vazio) nao ha nada útil a sugerir
        if entrada.get("quando") and not quando_data:
            dias = agenda.dias_ate_o_fim_da_semana(date.today())
            if len(dias) > 1:
                carga = _carga_por_dia(conn, dias)
                produtividade = aprendizado.produtividade_por_dia_semana(conn)
                resultado["sugestao_dia"] = agenda.sugerir_dia_menos_corrido(carga, dias, produtividade)
        return resultado

    def exec_registrar_gasto(entrada):
        status_gasto = entrada.get("status") if entrada.get("status") in ("real", "planejado") else "real"
        conn.execute(
            "INSERT INTO expenses (amount, category, description, source_text, tipo) VALUES (?, ?, ?, ?, ?)",
            (entrada["valor"], entrada.get("categoria") or "outros", entrada["titulo"], texto, status_gasto),
        )
        conn.commit()
        resultado = {"ok": True}
        if status_gasto == "real":
            saldo_banco = _ajustar_saldo_se_banco_citado(conn, entrada.get("banco"), -entrada["valor"])
            if saldo_banco:
                resultado["saldo_banco"] = saldo_banco
        return resultado

    def exec_registrar_meta(entrada):
        create_goal(conn, entrada["titulo"], entrada["valor"], entrada.get("prazo"))
        return {"ok": True}

    def exec_definir_orcamento(entrada):
        definir_orcamento(conn, entrada["categoria"], entrada["valor_limite"])
        return {"ok": True}

    def exec_registrar_renda(entrada):
        create_income(conn, entrada["valor"], entrada["categoria"], entrada.get("descricao"), texto)
        resultado = {"ok": True}
        saldo_banco = _ajustar_saldo_se_banco_citado(conn, entrada.get("banco"), entrada["valor"])
        if saldo_banco:
            resultado["saldo_banco"] = saldo_banco
        return resultado

    def exec_gerar_plano(_entrada):
        pendentes = _tarefas_pendentes_sem_horario_hoje(conn)
        eventos = _eventos_de_hoje_com_seguranca(conn)
        plano_texto, usage_plano = claude_client.plano_do_dia(
            [r["title"] for r in pendentes], eventos, memorias_texto
        )
        _log_usage(conn, usage_plano)
        return {"plano": plano_texto}

    def exec_registrar_lembrete(entrada):
        create_lembrete(conn, entrada["titulo"], entrada["data"], entrada.get("recorrente", False))
        return {"ok": True}

    def exec_registrar_medicamento(entrada):
        return _criar_medicamento(
            conn,
            entrada["nome"],
            entrada.get("dosagem"),
            entrada["horario"],
            entrada.get("recorrencia") or "diaria",
            texto,
        )

    def exec_registrar_hidratacao(entrada):
        total = registrar_hidratacao(conn, date.today().isoformat())
        return {"ok": True, "total_hoje": total}

    def exec_registrar_medida(entrada):
        tipo = (entrada.get("tipo") or "").strip().lower()
        if not tipo:
            return {"erro": "informe o tipo da medida (ex: peso, biceps, cintura)"}
        try:
            valor = float(entrada["valor"])
        except (KeyError, TypeError, ValueError):
            return {"erro": "valor invalido"}
        unidade = (entrada.get("unidade") or "").strip() or ("kg" if tipo == "peso" else "cm")
        medida_id = create_medida_corporal(conn, tipo, valor, unidade, date.today().isoformat())
        return {"ok": True, "medida_id": medida_id}

    def exec_registrar_checkin(entrada):
        campos = {c: vida.valor_checkin(entrada.get(c)) for c in vida.CAMPOS_CHECKIN}
        campos = {c: v for c, v in campos.items() if v is not None}
        if not campos:
            return {"erro": "nada pra registrar - use 'ruim', 'ok' ou 'bom'"}
        salvar_checkin(conn, date.today().isoformat(), campos)
        return {"ok": True}

    def exec_iniciar_hiperfoco(entrada):
        minutos = entrada.get("minutos") or 50
        if minutos not in vida.DURACOES_HIPERFOCO:
            minutos = 50
        estado = _iniciar_hiperfoco(conn, minutos)
        return {"ok": True, "ate": estado["ate"], "minutos": minutos}

    def exec_registrar_conversa(entrada):
        pessoa = (entrada.get("pessoa") or "").strip()
        if not pessoa:
            return {"erro": "faltou com quem foi a conversa"}
        sobre = (entrada.get("sobre") or "").strip() or None
        return _registrar_conversa_por_nome(conn, pessoa, sobre, texto)

    def exec_cadastrar_pessoa(entrada):
        nome = (entrada.get("nome") or "").strip()
        if not nome:
            return {"erro": "faltou o nome"}
        freq = _inteiro_no_intervalo(entrada.get("frequencia_dias") or 14, 1, 365) or 14
        _, atualizada = _salvar_pessoa(conn, nome, freq)
        return {"ok": True, "atualizada": atualizada, "frequencia_dias": freq}

    def exec_registrar_conta_pessoal(entrada):
        nome = (entrada.get("nome") or "").strip()
        dia = _inteiro_no_intervalo(entrada.get("dia_vencimento"), 1, 31)
        if not nome or dia is None:
            return {"erro": "preciso do nome e do dia de vencimento (1 a 31)"}
        valor = entrada.get("valor")
        valida = isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor) and valor >= 0
        conta_id = create_conta_pessoal(conn, nome, dia, float(valor) if valida else None)
        return {"ok": True, "conta_id": conta_id}

    def exec_adicionar_compras(entrada):
        return _adicionar_compras(conn, entrada.get("itens"))

    def exec_salvar_ficha_treino(entrada):
        grupo = _texto_curto(entrada.get("grupo"), 40)
        exercicios = entrada.get("exercicios")
        if isinstance(exercicios, list):
            exercicios = "\n".join(str(e).strip() for e in exercicios if str(e).strip())
        exercicios = _texto_curto(exercicios, 3000)
        if not grupo or not exercicios:
            return {"erro": "preciso do grupo e dos exercicios"}
        return {"ok": True, "ficha_id": salvar_ficha_treino(conn, grupo, exercicios)}

    def exec_registrar_treino(entrada):
        duracao = entrada.get("duracao_min")
        duracao = _inteiro_no_intervalo(duracao, 1, 600) if duracao not in (None, "") else None
        treino_id = registrar_treino(
            conn, date.today().isoformat(), _texto_curto(entrada.get("grupo"), 40), duracao,
            _texto_curto(entrada.get("nota"), 300),
        )
        return {"ok": True, "treino_id": treino_id}

    def exec_registrar_viagem(entrada):
        return _criar_viagem(
            conn, entrada.get("destino"), entrada.get("data_ida"), entrada.get("data_volta"), entrada.get("motivo")
        )

    def exec_registrar_lugar(entrada):
        return _criar_lugar(conn, entrada.get("nome"), entrada.get("cidade"), entrada.get("tipo"), entrada.get("nota"))

    def exec_registrar_manutencao(entrada):
        return _criar_manutencao(conn, entrada.get("item"), entrada.get("intervalo_meses"), entrada.get("ultima_vez"))

    def exec_registrar_responder(entrada):
        quem = _texto_curto(entrada.get("quem"), 60)
        if not quem:
            return {"erro": "faltou pra quem"}
        return {"ok": True, "id": create_responder(conn, quem, _texto_curto(entrada.get("sobre"), 200))}

    def exec_registrar_aprender(entrada):
        return _criar_aprender(conn, entrada.get("tema"), entrada.get("nota"))

    def exec_salvar_link(entrada):
        resultado = _salvar_link(conn, entrada.get("url"))
        if "erro" in resultado:
            return resultado
        return {"ok": True, "titulo": resultado["titulo"], "resumo": resultado["resumo"], "aviso": resultado["aviso"]}

    def exec_marcar_saida_noite(entrada):
        definir_configuracao(conn, "saida_noite_data", date.today().isoformat())
        return {"ok": True}

    def exec_registrar_memoria(entrada):
        create_memoria(conn, entrada["fato"], texto)
        return {"ok": True}

    def exec_registrar_espera(entrada):
        espera_id = create_espera(conn, entrada["quem"], entrada["sobre"], texto)
        return {"ok": True, "espera_id": espera_id}

    def exec_resolver_espera(entrada):
        espera = espera_pendente_por_quem_aproximado(conn, entrada["quem"])
        if not espera:
            return {"erro": f"nao achei nenhuma espera em aberto de \"{entrada['quem']}\""}
        resolver_espera(conn, espera["id"])
        return {"ok": True, "quem": espera["quem"], "sobre": espera["sobre"]}

    def exec_registrar_feito(entrada):
        return marcar_ou_criar_feito(conn, entrada["titulo"], texto)

    def exec_registrar_voo(entrada):
        # Contar como foi um voo ja agendado (resposta ao "Como foi o voo?")
        # completa o registro existente em vez de criar um voo duplicado.
        existente = next(
            (v for v in list_voos(conn)
             if v["data"] == entrada["data"]
             and vida.normalizar_nome(v["destino"]) == vida.normalizar_nome(entrada["destino"])
             and not (v.get("observacao") or "").strip()),
            None,
        )
        if existente:
            conn.execute(
                """UPDATE voos SET observacao = COALESCE(?, observacao), horas = COALESCE(?, horas),
                   origem = COALESCE(?, origem), hora = COALESCE(?, hora) WHERE id = ?""",
                (entrada.get("observacao"), entrada.get("horas"), entrada.get("origem"),
                 _normalizar_hora(entrada.get("hora")), existente["id"]),
            )
            conn.commit()
            return {"ok": True, "atualizado": True}
        create_voo(
            conn,
            entrada["data"],
            entrada["destino"],
            entrada.get("origem"),
            entrada.get("horas"),
            entrada.get("observacao"),
            _normalizar_hora(entrada.get("hora")),
        )
        return {"ok": True}

    def exec_rotular_cobranca_generica(entrada):
        candidatos = notificacoes.cobrancas_genericas_sem_rotulo(conn)
        correspondente = next((c for c in candidatos if abs(c[1] - entrada["valor"]) < 0.01), None)
        if not correspondente:
            return {"erro": f"nao achei nenhuma cobranca generica de R$ {entrada['valor']:.2f} pra identificar"}
        descricao_norm, valor, _msg = correspondente
        definir_apelido_gasto(conn, descricao_norm, valor, entrada["apelido"])
        return {"ok": True, "apelido": entrada["apelido"]}

    def exec_consultar_gastos_fixos(_entrada):
        return _gastos_fixos(conn)

    def exec_consultar_sobra_do_mes(_entrada):
        return _sobra_do_mes(conn)

    def exec_consultar_noticias(entrada):
        return {"manchetes": noticias.buscar_manchetes(entrada["termo"])}

    def exec_salvar_nota(entrada):
        nota_id = create_nota(conn, entrada["titulo"], entrada["corpo"], entrada.get("tags"), texto)
        return {"ok": True, "nota_id": nota_id}

    def exec_consultar_notas(entrada):
        return {"notas": buscar_notas(conn, entrada["termo"])}

    def exec_distribuir_tarefas_na_semana(entrada):
        titulos = [t.strip() for t in entrada.get("titulos", []) if t and t.strip()]
        if not titulos:
            return {"erro": "nao veio nenhum titulo de tarefa pra distribuir"}
        dias = agenda.proximos_n_dias(date.today() + timedelta(days=1), 14)
        carga = _carga_por_dia(conn, dias)
        produtividade = aprendizado.produtividade_por_dia_semana(conn)
        propostas = agenda.distribuir_tarefas_na_semana(carga, dias, titulos, produtividade)
        definir_configuracao(conn, "plano_semana_pendente", json.dumps(propostas, ensure_ascii=False))
        return {"ok": True, "propostas": propostas}

    def exec_confirmar_plano_semana(_entrada):
        bruto = obter_configuracao(conn, "plano_semana_pendente")
        if not bruto:
            return {"erro": "nao tem nenhum plano de semana pendente pra confirmar"}
        propostas = json.loads(bruto)
        for item in propostas:
            conn.execute(
                "INSERT INTO tasks (title, due_date, hora, source_text) VALUES (?, ?, ?, ?)",
                (item["titulo"], item["dia"], item["hora"], texto),
            )
        conn.commit()
        definir_configuracao(conn, "plano_semana_pendente", "")
        return {"ok": True, "quantidade": len(propostas), "titulos": [p["titulo"] for p in propostas]}

    def exec_cancelar_plano_semana(_entrada):
        definir_configuracao(conn, "plano_semana_pendente", "")
        return {"ok": True}

    def exec_sugerir_tarefa_para_agora(_entrada):
        hoje = date.today().isoformat()
        # prioriza uma tarefa com dia marcado mais pra frente (adiantar de
        # verdade, o pedido especifico do Alex) - a mais proxima primeiro,
        # pra nao pular direto pra semana que vem enquanto tem algo de
        # amanha esperando.
        futura = conn.execute(
            "SELECT id, title, due_date FROM tasks "
            "WHERE completed_at IS NULL AND due_date IS NOT NULL AND due_date > ? "
            "ORDER BY due_date ASC LIMIT 1",
            (hoje,),
        ).fetchone()
        if futura:
            return {
                "encontrada": True,
                "tipo": "adiantada",
                "tarefa_id": futura["id"],
                "titulo": futura["title"],
                "dia_original": futura["due_date"],
            }
        # nada com dia marcado pra frente - ainda assim tenta oferecer algo
        # (tarefa solta sem data), pra "to sem nada pra fazer" nunca virar
        # uma resposta vazia quando existe trabalho pendente de qualquer jeito.
        solta = conn.execute(
            "SELECT title FROM tasks WHERE completed_at IS NULL AND due_date IS NULL "
            "AND recorrencia IS NULL ORDER BY id ASC LIMIT 1"
        ).fetchone()
        if solta:
            return {"encontrada": True, "tipo": "solta", "titulo": solta["title"]}
        return {"encontrada": False}

    def exec_sugerir_horario_livre(entrada):
        eventos = _eventos_de_hoje_com_seguranca(conn)
        compromissos = [(e["inicio"][11:16], e["fim"][11:16]) for e in eventos if not e.get("dia_inteiro")]
        inicio_dia = entrada.get("depois_das") or "06:00"
        fim_dia = entrada.get("antes_das") or "22:00"
        janela = agenda.maior_janela_livre(compromissos, inicio_dia, fim_dia, entrada["duracao_minutos"])
        if not janela:
            return {"encontrado": False}
        return {"encontrado": True, **janela}

    def exec_calcular_gasto_viagem(entrada):
        if not maps_client.configurado():
            return {"erro": "Google Maps nao configurado"}
        origem = entrada.get("origem") or os.environ.get("ENDERECO_CASA", "").strip()
        if not origem:
            return {"erro": "preciso saber de onde voce sai (endereco padrao nao configurado)"}
        try:
            trajeto = maps_client.tempo_de_viagem(origem, entrada["destino"])
        except (ValueError, requests.RequestException):
            return {"erro": "nao consegui calcular a rota agora"}
        custo = viagem.custo_combustivel(
            trajeto["distancia_km"], entrada["km_por_litro"], entrada["preco_por_litro"]
        )
        return {
            "distancia_km": trajeto["distancia_km"],
            "duracao_minutos": trajeto["duracao_minutos"],
            "litros_gastos": custo["litros"],
            "custo_combustivel": custo["custo"],
        }

    def exec_sugerir_posto_no_caminho(entrada):
        if not maps_client.configurado():
            return {"erro": "Google Maps nao configurado"}
        origem = entrada.get("origem") or os.environ.get("ENDERECO_CASA", "").strip()
        if not origem:
            return {"erro": "preciso saber de onde voce sai (endereco padrao nao configurado)"}
        try:
            posto = maps_client.posto_no_meio_do_caminho(origem, entrada["destino"])
        except (ValueError, requests.RequestException):
            return {"erro": "nao consegui buscar postos agora"}
        if not posto:
            return {"erro": "nao achei nenhum posto perto do meio do caminho"}
        return posto

    def exec_agendar_uber(entrada):
        if not uber_client.configurado():
            return {"erro": "Uber nao conectado ainda"}
        minutos = max(entrada.get("minutos", 0), 0)
        disparar_em = (datetime.now() + timedelta(minutes=minutos)).isoformat()
        pedido_id = criar_uber_pedido(conn, entrada.get("origem"), entrada["destino"], disparar_em)
        return {"ok": True, "pedido_id": pedido_id, "minutos": minutos}

    def exec_sugerir_tema_estudo(_entrada):
        indice_atual = int(obter_configuracao(conn, "estudo_proximo_indice") or 0)
        tema, proximo_indice = estudo.proximo_tema(indice_atual)
        definir_configuracao(conn, "estudo_proximo_indice", str(proximo_indice))
        return {"tema": tema}

    def exec_registrar_item_cotacao(entrada):
        cotacao_id = _resolver_cotacao_por_titulo(conn, entrada["titulo_cotacao"])
        criar_item_cotacao(
            conn,
            cotacao_id,
            entrada["fornecedor"],
            entrada["valor"],
            entrada.get("prazo_texto"),
            entrada.get("observacao"),
            origem="texto",
        )
        return {"ok": True, "cotacao_id": cotacao_id}

    def exec_comparar_cotacao(entrada):
        cotacao = cotacao_por_titulo_aproximado(conn, entrada["titulo_cotacao"])
        if not cotacao:
            return {"erro": f"nao achei nenhuma cotacao com o titulo \"{entrada['titulo_cotacao']}\""}
        itens = list_itens_cotacao(conn, cotacao["id"])
        if not itens:
            return {"titulo": cotacao["titulo"], "itens": []}
        return {
            "titulo": cotacao["titulo"],
            "itens": [
                {
                    "fornecedor": i["fornecedor"],
                    "valor": i["valor"],
                    "prazo_texto": i["prazo_texto"],
                }
                for i in itens
            ],
        }

    executores = {
        "registrar_tarefa": exec_registrar_tarefa,
        "registrar_gasto": exec_registrar_gasto,
        "registrar_renda": exec_registrar_renda,
        "definir_orcamento": exec_definir_orcamento,
        "registrar_meta": exec_registrar_meta,
        "gerar_plano_do_dia": exec_gerar_plano,
        "registrar_lembrete": exec_registrar_lembrete,
        "registrar_medicamento": exec_registrar_medicamento,
        "registrar_hidratacao": exec_registrar_hidratacao,
        "registrar_medida": exec_registrar_medida,
        "registrar_checkin": exec_registrar_checkin,
        "iniciar_hiperfoco": exec_iniciar_hiperfoco,
        "registrar_conversa": exec_registrar_conversa,
        "cadastrar_pessoa": exec_cadastrar_pessoa,
        "registrar_conta_pessoal": exec_registrar_conta_pessoal,
        "adicionar_compras": exec_adicionar_compras,
        "salvar_ficha_treino": exec_salvar_ficha_treino,
        "registrar_treino": exec_registrar_treino,
        "registrar_viagem": exec_registrar_viagem,
        "registrar_lugar": exec_registrar_lugar,
        "registrar_manutencao": exec_registrar_manutencao,
        "registrar_responder": exec_registrar_responder,
        "marcar_saida_noite": exec_marcar_saida_noite,
        "registrar_aprender": exec_registrar_aprender,
        "salvar_link": exec_salvar_link,
        "registrar_memoria": exec_registrar_memoria,
        "registrar_espera": exec_registrar_espera,
        "resolver_espera": exec_resolver_espera,
        "registrar_feito": exec_registrar_feito,
        "registrar_voo": exec_registrar_voo,
        "consultar_noticias": exec_consultar_noticias,
        "salvar_nota": exec_salvar_nota,
        "consultar_notas": exec_consultar_notas,
        "sugerir_horario_livre": exec_sugerir_horario_livre,
        "distribuir_tarefas_na_semana": exec_distribuir_tarefas_na_semana,
        "confirmar_plano_semana": exec_confirmar_plano_semana,
        "cancelar_plano_semana": exec_cancelar_plano_semana,
        "sugerir_tarefa_para_agora": exec_sugerir_tarefa_para_agora,
        "rotular_cobranca_generica": exec_rotular_cobranca_generica,
        "consultar_gastos_fixos": exec_consultar_gastos_fixos,
        "consultar_sobra_do_mes": exec_consultar_sobra_do_mes,
        "calcular_gasto_viagem": exec_calcular_gasto_viagem,
        "sugerir_posto_no_caminho": exec_sugerir_posto_no_caminho,
        "agendar_uber": exec_agendar_uber,
        "sugerir_tema_estudo": exec_sugerir_tema_estudo,
        "registrar_item_cotacao": exec_registrar_item_cotacao,
        "comparar_cotacao": exec_comparar_cotacao,
    }

    try:
        resposta, acoes, usage = claude_client.chat(mensagens, contexto, memorias_texto, executores)
    except anthropic.APIError:
        return None, [], CLAUDE_ERROR_MSG
    except (ValueError, KeyError):
        return None, [], CLAUDE_FORMAT_ERROR_MSG

    _log_usage(conn, usage)
    salvar_mensagem_chat(conn, "user", texto)
    salvar_mensagem_chat(conn, "assistant", resposta)
    _marcar_atividade(conn)
    return resposta, acoes, None


@app.route("/api/chat", methods=["POST"])
def chat():
    body = _corpo_json()
    texto = _texto_seguro(body.get("mensagem"))
    if not texto:
        return jsonify({"error": "mensagem vazia"}), 400

    conn = get_db()
    resposta, acoes, erro = _processar_mensagem_chat(conn, texto)
    conn.close()
    if erro:
        return jsonify({"error": erro}), 502
    return jsonify({"resposta": resposta, "acoes": acoes})


def _telegram_chat_fn(texto: str) -> str:
    """Ponte entre o bot do Telegram e o mesmo pipeline de conversa do
    /api/chat - roda numa thread separada (ver telegram_bot.iniciar_thread),
    entao abre e fecha a propria conexao com o banco em vez de compartilhar
    uma conexao do request HTTP."""
    conn = get_db()
    try:
        resposta, _acoes, erro = _processar_mensagem_chat(conn, _texto_seguro(texto))
        return erro or resposta
    finally:
        conn.close()


def _telegram_callback_fn(dados: str) -> str:
    """Ponte entre um toque de botao inline no Telegram e a acao de verdade -
    hoje so entende "completar_tarefa:<id>" (o botao que acompanha a
    cobranca de tarefa_parada), mas o formato "acao:id" deixa dar pra
    estender pra outros tipos de botao no futuro sem mudar o protocolo."""
    if not dados.startswith("completar_tarefa:"):
        return "Nao reconheci essa acao."
    try:
        task_id = int(dados.split(":", 1)[1])
    except ValueError:
        return "Nao reconheci essa acao."
    conn = get_db()
    try:
        row = conn.execute("SELECT title, completed_at FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return "Essa tarefa nao existe mais."
        if row["completed_at"]:
            return "Ja estava marcada como feita."
        complete_task(conn, task_id)
        _marcar_atividade(conn)
        conn.commit()
        return f"Marquei \"{row['title']}\" como feita!"
    finally:
        conn.close()


def iniciar_telegram():
    """So roda quando o app sobe de verdade (mesma guarda de iniciar_scheduler,
    nao duplica a thread na recarga do Flask em modo debug)."""
    if not telegram_bot.configurado():
        return
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        telegram_bot.iniciar_thread(_telegram_chat_fn, callback_fn=_telegram_callback_fn)


@app.route("/api/chat/historico", methods=["GET"])
def chat_historico():
    conn = get_db()
    mensagens = list(reversed(list_chat_mensagens(conn, limit=30)))
    conn.close()
    return jsonify(mensagens)


def _aviso_bom_tempo_pra_tarefa(tarefa: dict) -> str | None:
    """Se a cidade padrao estiver configurada e a previsao achar um dia com
    chance de chuva baixa dentro da janela, devolve a mensagem de push pra
    essa tarefa que depende do tempo. None se nao configurado, erro de rede,
    ou nenhum dia bom na janela ainda."""
    cidade = os.environ.get("CIDADE_PADRAO", "").strip()
    if not cidade:
        return None
    local = clima.geocodificar_cidade(cidade)
    if not local:
        return None
    previsoes = clima.previsao_proximos_dias(local["lat"], local["lon"], dias=7)
    if not previsoes:
        return None
    melhor = clima.melhor_dia_sem_chuva(previsoes)
    if not melhor:
        return None

    dia_str = datetime.fromisoformat(melhor["data"]).strftime("%d/%m")
    hoje_str = date.today().isoformat()
    quando = "Hoje" if melhor["data"] == hoje_str else f"Dia {dia_str}"
    return f"{quando} parece um dia bom (pouca chance de chuva) pra: {tarefa['title']}."


def _aviso_voo_sair(voo: dict, janela_minutos: int = 25) -> str | None:
    """Se o voo tem horario hoje e a hora de sair de casa (calculada com
    transito real) ja esta dentro da janela de aviso, devolve a mensagem
    de push. None se nao configurado, a rota nao puder ser calculada, ou
    ainda nao for hora de avisar. Sem rede/erro nunca derruba o scheduler -
    so pula esse voo nessa rodada (tenta de novo daqui a 5min)."""
    if not maps_client.configurado():
        return None
    origem = os.environ.get("ENDERECO_CASA", "").strip()
    if not origem:
        return None
    try:
        chegar_ate = datetime.fromisoformat(f"{voo['data']}T{voo['hora']}")
        resultado = maps_client.horario_de_saida(origem, voo["destino"], chegar_ate, margem_minutos=60)
    except (ValueError, requests.RequestException):
        return None

    sair_ate = datetime.fromisoformat(resultado["sair_ate"])
    minutos_pra_sair = (sair_ate - datetime.now()).total_seconds() / 60
    if not (0 <= minutos_pra_sair <= janela_minutos):
        return None

    hora_txt = sair_ate.strftime("%H:%M")
    return (
        f"Saia ate as {hora_txt} pra chegar a tempo do voo das {voo['hora']} "
        f"pra {voo['destino']} (trajeto de {resultado['duracao_minutos']}min)."
    )


def _uber_token_valido(conn) -> str | None:
    """Devolve um access_token utilizavel pra API da Uber, renovando com o
    refresh_token guardado se o atual ja expirou. None se a conta nunca foi
    conectada ainda (ver rota /uber/conectar)."""
    access_token = obter_configuracao(conn, "uber_access_token")
    refresh_token = obter_configuracao(conn, "uber_refresh_token")
    expira_em = obter_configuracao(conn, "uber_token_expira_em")
    if not access_token or not refresh_token:
        return None
    if expira_em and datetime.fromisoformat(expira_em) > datetime.now():
        return access_token

    try:
        dados = uber_client.renovar_token(refresh_token)
    except requests.RequestException:
        return None
    novo_token = dados.get("access_token")
    if not novo_token:
        return None
    definir_configuracao(conn, "uber_access_token", novo_token)
    definir_configuracao(conn, "uber_refresh_token", dados.get("refresh_token", refresh_token))
    nova_expiracao = datetime.now() + timedelta(seconds=dados.get("expires_in", 2592000))
    definir_configuracao(conn, "uber_token_expira_em", nova_expiracao.isoformat())
    return novo_token


def _disparar_estimativa_uber(conn, pedido: dict, access_token: str) -> None:
    """Busca o preco de verdade (com fare_id, que trava o valor cobrado) e
    deixa o pedido pronto pro push de confirmacao - NUNCA pede a corrida
    sozinho aqui. So depois do Alex confirmar explicitamente (endpoint
    /api/uber/pedidos/<id>/confirmar) e que o dinheiro entra em jogo."""
    origem = pedido.get("origem") or os.environ.get("ENDERECO_CASA", "").strip()
    if not origem:
        atualizar_uber_pedido(conn, pedido["id"], status="erro", erro="sem endereco de origem")
        return
    try:
        origem_lat, origem_lng = maps_client.geocodificar(origem)
        destino_lat, destino_lng = maps_client.geocodificar(pedido["destino"])
        product_id = uber_client.produto_padrao(origem_lat, origem_lng, access_token)
        estimativa = uber_client.estimar_corrida(
            origem_lat, origem_lng, destino_lat, destino_lng, product_id, access_token
        )
    except (ValueError, requests.RequestException) as e:
        atualizar_uber_pedido(conn, pedido["id"], status="erro", erro=str(e))
        return

    if not estimativa.get("fare_id"):
        atualizar_uber_pedido(conn, pedido["id"], status="erro", erro="nao consegui obter o preco")
        return

    atualizar_uber_pedido(
        conn,
        pedido["id"],
        status="aguardando_confirmacao",
        origem_lat=origem_lat,
        origem_lng=origem_lng,
        destino_lat=destino_lat,
        destino_lng=destino_lng,
        product_id=product_id,
        fare_id=estimativa["fare_id"],
        preco_texto=estimativa["preco_texto"],
    )


# Avisos presos a um instante especifico (a informacao perde o sentido se
# adiada pro fim do horario silencioso) - esses sempre disparam na hora, os
# outros respeitam o modo silencioso (ver verificar_e_notificar).
NOTIFICACOES_URGENTES = {
    "tarefa_horario", "compromisso_chegando", "voo_sair", "hora_de_dormir", "rotina_manha", "hiperfoco_fim",
    "adiado_hiperfoco",
}


def _adiar_aviso(conn, tipo: str, titulo: str, corpo: str):
    """Guarda um aviso de janela curta segurado pelo hiperfoco pra sair quando
    o foco acabar (so vale no mesmo dia - aviso de ontem nao faz mais sentido)."""
    hoje = date.today().isoformat()
    try:
        guardados = json.loads(obter_configuracao(conn, "avisos_adiados") or "{}")
    except ValueError:
        guardados = {}
    itens = guardados.get("itens", []) if guardados.get("data") == hoje else []
    itens.append([tipo, titulo, corpo])
    definir_configuracao(conn, "avisos_adiados", json.dumps({"data": hoje, "itens": itens[-10:]}))


def _liberar_avisos_adiados(conn, hoje: date) -> list[tuple[str, int, str, str]]:
    try:
        guardados = json.loads(obter_configuracao(conn, "avisos_adiados") or "{}")
    except ValueError:
        guardados = {}
    if not guardados.get("itens"):
        return []
    definir_configuracao(conn, "avisos_adiados", "{}")
    if guardados.get("data") != hoje.isoformat():
        return []
    # O tipo original decide se o aviso respeita o modo silencioso na hora de
    # sair ("Fechando o dia" segurado ate 22h25 nao deve tocar no silencio).
    liberados = []
    for item in guardados["itens"]:
        tipo_original, titulo, corpo = item if len(item) == 3 else ("", *item)
        tipo = "adiado_hiperfoco" if tipo_original in NOTIFICACOES_URGENTES else "adiado_hiperfoco_leve"
        liberados.append((tipo, vida.id_estavel("adiado", hoje.isoformat(), titulo, corpo), titulo, corpo))
    return liberados


def _avisos_assistente_vida(conn, agora: datetime) -> list[tuple[str, int, str, str]]:
    """Avisos do BRIEFING.md Fase 1: rotina da manha, fim do hiperfoco,
    contas pessoais, pessoas sem contato e revisao mensal de assinaturas.
    Cada um com dedup proprio pra nunca virar cobranca repetida."""
    avisos = []
    hoje = agora.date()

    hora_manha = obter_configuracao(conn, "rotina_manha_hora") or "07:00"
    if vida.rotina_manha_devida(agora, hora_manha) and not ja_notificou_hoje(conn, "rotina_manha"):
        itens = ", ".join(i["texto"].lower() for i in list_rotina_itens(conn, "manha"))
        corpo = f"Bom dia. Rotina da manha: {itens}." if itens else "Bom dia. Da uma olhada no essencial de hoje."
        avisos.append(("rotina_manha", 0, "Bom dia", corpo))

    ate = obter_configuracao(conn, "hiperfoco_ate")
    if ate and not vida.hiperfoco_ativo(ate, agora):
        try:
            terminou_ha = (agora - datetime.fromisoformat(ate)).total_seconds() / 60
        except ValueError:
            terminou_ha = None
        if terminou_ha is not None and terminou_ha <= 30:
            minutos = obter_configuracao(conn, "hiperfoco_minutos") or ""
            duracao = f" de {minutos} min" if minutos else ""
            avisos.append(
                ("hiperfoco_fim", vida.id_estavel("hiperfoco", ate), "Fim do foco",
                 f"Seu bloco de foco{duracao} acabou. Levanta, bebe agua, e ve se continua ou para.")
            )
        conn.execute(
            "UPDATE configuracoes SET valor = '' WHERE chave = 'hiperfoco_ate' AND valor = ?", (ate,)
        )
        conn.commit()
    if not vida.hiperfoco_ativo(obter_configuracao(conn, "hiperfoco_ate"), agora):
        avisos.extend(_liberar_avisos_adiados(conn, hoje))

    for conta in _contas_pessoais_com_status(conn, hoje):
        dias = conta["dias_ate_vencer"]
        if conta["paga"] or dias > 3 or dias < 0:
            continue
        fase = "dia" if dias == 0 else "antes"
        ref = vida.id_estavel("conta_pessoal", conta["id"], conta["proximo_vencimento"], fase)
        if ja_notificado_alguma_vez(conn, "conta_pessoal", ref):
            continue
        valor = f" (R$ {conta['valor']:.2f})" if conta["valor"] is not None else ""
        quando = "vence hoje" if dias == 0 else f"vence em {dias} dia(s)"
        avisos.append(("conta_pessoal", ref, "Conta chegando", f"{conta['nome']}{valor} {quando}."))

    for pessoa, dias in vida.pessoas_sem_contato(list_pessoas(conn), hoje):
        base = pessoa["ultimo_contato"] or (pessoa["criado_em"] or "")[:10]
        ref = vida.id_estavel("pessoa", pessoa["id"], base)
        if ja_notificado_alguma_vez(conn, "pessoa_sem_contato", ref):
            continue
        texto = (
            f"Faz {dias} dias que voce nao fala com {pessoa['nome']}."
            if pessoa["ultimo_contato"]
            else f"Ainda nao tem conversa registrada com {pessoa['nome']}."
        )
        avisos.append(("pessoa_sem_contato", ref, "Faz tempo", texto))

    if agora.hour >= 10:
        ref = vida.id_estavel("assinaturas", hoje.strftime("%Y-%m"))
        if not ja_notificado_alguma_vez(conn, "revisao_assinaturas", ref):
            pendentes = _assinaturas_pendentes_revisao(conn, hoje)
            if pendentes:
                avisos.append(
                    ("revisao_assinaturas", ref, "Revisao do mes",
                     f"{len(pendentes)} assinatura(s) pra confirmar se voce ainda usa - 1 toque cada no painel.")
                )
    return avisos


def _avisos_fase2(conn, agora: datetime) -> list[tuple[str, int, str, str]]:
    """Avisos do BRIEFING.md Fase 2: agua/pausa, sono ruim seguido, chuva em
    cima de compromisso, pre-voo, viagem (documento), manutencao e mensagem
    pra responder."""
    avisos = []
    hoje = agora.date()
    hoje_iso = hoje.isoformat()

    slot = vida.slot_agua_pausa(agora)
    if slot is not None and not ja_notificou_hoje(conn, "agua_pausa", slot):
        bebeu_agora = conn.execute(
            "SELECT 1 FROM hidratacao_registros WHERE criado_em >= datetime('now', '-60 minutes')"
        ).fetchone()
        if not bebeu_agora:
            copos = contar_hidratacao_dia(conn, hoje_iso)
            avisos.append(
                ("agua_pausa", slot, "Pausa rapida",
                 f"Bebe um copo de agua e levanta 2 minutos ({copos} copo(s) hoje).")
            )

    if agora.hour >= 8:
        # sono_horas e criptografado - list_saude_dados ja descriptografa
        # (filtro de data continua no SQL, "IS NOT NULL" agora e em Python)
        sono = {
            l["data"]: l["sono_horas"]
            for l in list_saude_dados(conn, desde=(hoje - timedelta(days=14)).isoformat())
            if l["sono_horas"] is not None
        }
        checkin_sono = {
            c["data"]: c["sono"] for c in list_checkins(conn, (hoje - timedelta(days=14)).isoformat()) if c["sono"]
        }
        seguidas, inicio = vida.sequencia_noites_ruins(sono, checkin_sono, hoje)
        if seguidas >= 3:
            ref = vida.id_estavel("sono_ruim", inicio.isoformat())
            if not ja_notificado_alguma_vez(conn, "sono_ruim", ref):
                avisos.append(
                    ("sono_ruim", ref, "Sono ruim seguido",
                     f"{seguidas} noites seguidas dormindo mal. Hoje tenta desacelerar mais cedo - "
                     "se continuar assim, vale falar com um medico.")
                )

    cidade = os.environ.get("CIDADE_PADRAO", "").strip()
    if cidade and vida.rotina_manha_devida(agora, "07:30") and not ja_notificou_hoje(conn, "clima_compromisso"):
        try:
            resumo = clima.resumo_chuva_hoje_para_cidade(cidade)
        except requests.RequestException:
            resumo = None
        afetados = vida.compromissos_na_chuva(_agenda_pendente_de_hoje(conn), resumo)
        if afetados:
            nomes = ", ".join(
                f"{a['titulo']} as {datetime.fromisoformat(a['inicio']).strftime('%H:%M')}" for a in afetados[:2]
            )
            avisos.append(
                ("clima_compromisso", 0, "Chuva no seu horario",
                 f"{resumo['texto']} Pega {nomes} - sai mais cedo ou leva guarda-chuva.")
            )

    checklist_voo = ", ".join(vida.CHECKLIST_PRE_VOO).lower()
    for voo in list_voos(conn):
        try:
            data_voo = date.fromisoformat(voo["data"])
        except (TypeError, ValueError):
            continue
        destino = voo.get("destino") or "o voo"
        if data_voo == hoje + timedelta(days=1) and agora.hour >= 19:
            ref = vida.id_estavel("pre_voo", voo["id"], "vespera")
            if not ja_notificado_alguma_vez(conn, "pre_voo", ref):
                avisos.append(("pre_voo", ref, "Voo amanha", f"Voo amanha pra {destino}. Separa hoje: {checklist_voo}."))
        if data_voo == hoje and agora.hour >= 6:
            ainda_antes = not voo.get("hora") or agora.strftime("%H:%M") < voo["hora"]
            ref = vida.id_estavel("pre_voo", voo["id"], "dia")
            if ainda_antes and not ja_notificado_alguma_vez(conn, "pre_voo", ref):
                avisos.append(("pre_voo", ref, "Pre-voo", f"Voo hoje pra {destino}. Confere: {checklist_voo}."))

    for v in list_viagens_futuras(conn, hoje_iso):
        dias = (date.fromisoformat(v["data_ida"]) - hoje).days
        fase = "antes" if 0 < dias <= 3 else "dia" if dias == 0 and agora.hour >= 6 else None
        if not fase:
            continue
        ref = vida.id_estavel("v", v["id"], fase)
        if ja_notificado_alguma_vez(conn, "viagem_documento", ref):
            continue
        faltando = sum(1 for i in list_itens_viagem(conn, v["id"]) if not i["feito"])
        mala = f" Faltam {faltando} item(ns) da mala." if faltando else ""
        quando = "hoje" if fase == "dia" else f"em {dias} dia(s)"
        avisos.append(
            ("viagem_documento", ref, "Viagem chegando",
             f"Viagem pra {v['destino']} {quando}. Confere documento com foto, cartoes e reservas.{mala}")
        )

    for m in _manutencoes_com_status(conn, hoje):
        if m["dias_ate"] > 7:
            continue
        ref = vida.id_estavel("manutencao", m["id"], m["proxima"])
        if ja_notificado_alguma_vez(conn, "manutencao", ref):
            continue
        quando = "ja passou do prazo" if m["dias_ate"] < 0 else "vence hoje" if m["dias_ate"] == 0 else f"vence em {m['dias_ate']} dia(s)"
        avisos.append(("manutencao", ref, "Manutencao", f"{m['item']}: {quando}."))

    if agora.hour >= 10 and not ja_notificou_hoje(conn, "responder"):
        antigas = [
            r for r in list_responder_pendentes(conn) if datetime.fromisoformat(r["criado_em"]).date() < hoje
        ]
        if antigas:
            nomes = ", ".join(r["quem"] + (f" ({r['sobre']})" if r["sobre"] else "") for r in antigas[:3])
            resto = f" e mais {len(antigas) - 3}" if len(antigas) > 3 else ""
            avisos.append(("responder", 0, "Pra responder", f"Ainda falta responder: {nomes}{resto}."))
    return avisos


def _avisos_fase3(conn, agora: datetime) -> list[tuple[str, int, str, str]]:
    """Avisos do BRIEFING.md Fase 3: revisao do mes, prazo de burocracia com
    30 dias, tema de estudo parado, diario pos-voo e uso semanal do celular."""
    avisos = []
    hoje = agora.date()

    if hoje.day <= 3 and agora.hour >= 9:
        primeiro, ultimo = vida.mes_anterior(hoje)
        ref = vida.id_estavel("revisao_mensal", primeiro.isoformat())
        if not ja_notificado_alguma_vez(conn, "revisao_mensal", ref):
            avisos.append(("revisao_mensal", ref, "Como foi o mes", _revisao_do_mes(conn, primeiro, ultimo)["texto"]))

    for lembrete in list_lembretes(conn):
        if not vida.eh_burocracia(lembrete["titulo"]):
            continue
        try:
            base = date.fromisoformat(lembrete["data"])
        except (TypeError, ValueError):
            continue
        proxima = notificacoes.proxima_ocorrencia_lembrete(base, bool(lembrete["recorrente"]), hoje)
        dias = (proxima - hoje).days
        if not 8 <= dias <= 30:
            continue
        ref = vida.id_estavel("burocracia", lembrete["id"], proxima.isoformat())
        if not ja_notificado_alguma_vez(conn, "burocracia", ref):
            avisos.append(
                ("burocracia", ref, "Prazo chegando",
                 f"\"{lembrete['titulo']}\" vence em {dias} dias ({proxima.strftime('%d/%m')}) - ja da pra agendar.")
            )

    if agora.weekday() == 6 and agora.hour >= 10:
        semana = hoje.isocalendar()
        ref = vida.id_estavel("aprender", semana[0], semana[1])
        if not ja_notificado_alguma_vez(conn, "aprender", ref):
            for a in list_aprender(conn):
                parado = (hoje - date.fromisoformat(a["ultima_vez"] or a["criado_em"][:10])).days
                if parado >= 7:
                    avisos.append(
                        ("aprender", ref, "Quer retomar?",
                         f"Faz {parado} dias que voce nao mexe em \"{a['tema']}\". 20 minutos hoje?")
                    )
                    break

    ontem = (hoje - timedelta(days=1)).isoformat()
    for voo in list_voos(conn):
        if voo.get("data") not in (hoje.isoformat(), ontem) or (voo.get("observacao") or "").strip():
            continue
        if voo["data"] == ontem:
            # voo das 20h+ cai no silencio da noite: pergunta de manha, ate o meio-dia
            pronto = agora.hour < 12
        elif voo.get("hora"):
            try:
                h, m = (int(x) for x in voo["hora"].split(":"))
                decolagem = agora.replace(hour=h, minute=m, second=0, microsecond=0)
            except ValueError:
                continue
            pronto = agora >= decolagem + timedelta(hours=2)
        else:
            pronto = agora.hour >= 19
        ref = vida.id_estavel("pos_voo", voo["id"])
        if pronto and not ja_notificado_alguma_vez(conn, "pos_voo", ref):
            destino = voo.get("destino") or "o voo"
            avisos.append(
                ("pos_voo", ref, "Como foi o voo?",
                 f"Como foi o voo pra {destino}? Conta no chat que eu guardo no diario de bordo.")
            )

    if agora.weekday() == 6 and agora.hour >= 19:
        semana = hoje.isocalendar()
        ref = vida.id_estavel("uso_apps", semana[0], semana[1])
        if not ja_notificado_alguma_vez(conn, "uso_apps", ref):
            uso = _uso_apps(conn, 7)
            if uso["apps"]:
                lista = ", ".join(f"{a['app']} {a['texto']}" for a in uso["apps"][:4])
                avisos.append(("uso_apps", ref, "Sua semana no celular", f"Semana no celular: {lista}."))
    return avisos


def verificar_e_notificar():
    """Roda as verificacoes proativas e manda pra quem tiver canal configurado
    (push web e/ou Telegram) - cada tipo de aviso so dispara uma vez por dia
    (dedup em notificacoes_enviadas). Chamado pelo scheduler (ver
    iniciar_scheduler) e pelo endpoint manual."""
    # Materializa ANTES de qualquer early-return de canal - rotina recorrente
    # (remedio, academia) tem que aparecer mesmo se push/Telegram nao
    # estiverem configurados ainda, nao pode ficar refem de notificacao.
    conn_materializar = get_db()
    materializar_tarefas_recorrentes(conn_materializar)
    conn_materializar.close()

    push_ok = push_client.configurado()
    telegram_ok = telegram_bot.configurado()
    if not push_ok and not telegram_ok:
        return 0

    conn = get_db()
    subs = list_push_subscriptions(conn) if push_ok else []
    if not subs and not telegram_ok:
        conn.close()
        return 0

    avisos = []  # (tipo, referencia_id, titulo, corpo)

    msg = notificacoes.tarefas_atrasadas(conn)
    if msg and not ja_notificou_hoje(conn, "tarefas_atrasadas"):
        avisos.append(("tarefas_atrasadas", 0, "Tarefas atrasadas", msg))

    # Cobranca individual (fecha o loop) - diferente do aviso generico acima
    # (que so soma quantas estao atrasadas), essa aqui nomeia a tarefa parada
    # e cobra uma vez so, nunca todo dia (ja_notificado_alguma_vez, nao
    # ja_notificou_hoje) - senao vira ruido em vez de ajuda. O numero de dias
    # pra cobrar e' personalizado POR TAREFA (aprendizado.limiar_tarefa: primeiro
    # tenta o historico de titulos parecidos, senao o aprendizado global,
    # senao o padrao) - busca ampla (dias_minimo=1, o piso de qualquer limiar
    # possivel) e filtra item a item, ja que cada uma pode ter um limiar diferente.
    hoje = date.today()
    candidatos_tarefa = notificacoes.tarefas_paradas(conn, dias_minimo=1, hoje=hoje)
    if candidatos_tarefa:
        ids = [tarefa_id for tarefa_id, _ in candidatos_tarefa]
        placeholders = ",".join("?" * len(ids))
        detalhe_por_id = {
            r["id"]: r
            for r in conn.execute(
                f"SELECT id, title, due_date FROM tasks WHERE id IN ({placeholders})", ids
            ).fetchall()
        }
        for tarefa_id, msg in candidatos_tarefa:
            row = detalhe_por_id.get(tarefa_id)
            if not row:
                continue
            dias_atraso_atual = (hoje - date.fromisoformat(row["due_date"])).days
            limiar, _ = aprendizado.limiar_tarefa(conn, row["title"], task_id=tarefa_id)
            if dias_atraso_atual < limiar:
                continue
            if not ja_notificado_alguma_vez(conn, "tarefa_parada", tarefa_id):
                msg = f"{msg} Se travou, abre o painel que eu te ajudo a quebrar de outro jeito."
                avisos.append(("tarefa_parada", tarefa_id, "Isso ainda ta pendente?", msg))

    # Mesma ideia, mas pra resposta que voce esta esperando de TERCEIROS
    # (fornecedor, corretora) - o painel acompanha o thread em aberto por
    # voce, nao so as suas proprias tarefas. Tambem personalizado por quem
    # (aprendizado.limiar_espera), mesmo padrao de busca ampla + filtro item a item.
    candidatos_espera = notificacoes.esperas_paradas(conn, dias_minimo=1, hoje=hoje)
    if candidatos_espera:
        ids = [espera_id for espera_id, _ in candidatos_espera]
        placeholders = ",".join("?" * len(ids))
        detalhe_por_id = {
            r["id"]: r
            for r in conn.execute(
                f"SELECT id, quem, criado_em FROM esperas WHERE id IN ({placeholders})", ids
            ).fetchall()
        }
        for espera_id, msg in candidatos_espera:
            row = detalhe_por_id.get(espera_id)
            if not row:
                continue
            dias_atual = (hoje - datetime.fromisoformat(row["criado_em"]).date()).days
            limiar, _ = aprendizado.limiar_espera(conn, row["quem"], espera_id=espera_id)
            if dias_atual < limiar:
                continue
            if not ja_notificado_alguma_vez(conn, "espera_parada", espera_id):
                avisos.append(("espera_parada", espera_id, "Ainda sem resposta", msg))

    for meta_id, msg in notificacoes.metas_fora_do_ritmo(conn):
        if not ja_notificou_hoje(conn, "meta_atrasada", meta_id):
            avisos.append(("meta_atrasada", meta_id, "Meta fora do ritmo", msg))

    # Orcamento por categoria - uma vez por categoria+nivel+mes (nunca todo
    # dia enquanto continuar no mesmo nivel), pra nao virar ruido.
    ano_mes_atual = date.today().strftime("%Y-%m")
    for categoria, nivel, msg in notificacoes.orcamentos_perto_ou_estourados(conn):
        ref_id = _id_estavel_orcamento(categoria, nivel, ano_mes_atual)
        if not ja_notificado_alguma_vez(conn, "orcamento", ref_id):
            titulo = "Orcamento estourado" if nivel == "estourado" else "Orcamento quase no limite"
            avisos.append(("orcamento", ref_id, titulo, msg))

    # Cobranca generica (ex: "apple.com/bill") sem apelido ainda - pergunta
    # uma vez so, nunca todo dia enquanto o Alex nao responder qual e.
    for descricao_norm, valor, msg in notificacoes.cobrancas_genericas_sem_rotulo(conn):
        ref_id = _id_estavel_cobranca_generica(descricao_norm, valor)
        if not ja_notificado_alguma_vez(conn, "cobranca_generica", ref_id):
            avisos.append(("cobranca_generica", ref_id, "Cobranca sem identificar", msg))

    # Assinatura ja conhecida que subiu de preco (US-C10) - uma vez por
    # descricao+valor novo (mesma chave de dedup de cobranca_generica acima);
    # se subir de novo depois, o valor novo muda a chave e avisa de novo.
    for descricao_norm, valor, msg in notificacoes.assinaturas_aumento_preco(conn):
        ref_id = _id_estavel_cobranca_generica(descricao_norm, valor)
        if not ja_notificado_alguma_vez(conn, "assinatura_aumento_preco", ref_id):
            avisos.append(("assinatura_aumento_preco", ref_id, "Assinatura ficou mais cara", msg))

    msg = notificacoes.gasto_semana_elevado(conn)
    if msg and not ja_notificou_hoje(conn, "gasto_elevado"):
        avisos.append(("gasto_elevado", 0, "Gasto da semana", msg))

    # Complementa o alerta acima: pega um dia especifico fora do padrao mesmo
    # quando a semana inteira ainda nao estourou a media.
    msg = notificacoes.gasto_dia_semana_atipico(conn)
    if msg and not ja_notificou_hoje(conn, "gasto_dia_atipico"):
        avisos.append(("gasto_dia_atipico", 0, "Gasto fora do padrao hoje", msg))

    for lembrete_id, msg in notificacoes.lembretes_proximos(conn):
        if not ja_notificou_hoje(conn, "lembrete_proximo", lembrete_id):
            avisos.append(("lembrete_proximo", lembrete_id, "Data importante chegando", msg))

    for tarefa_id, msg in notificacoes.tarefas_com_horario_chegando(conn):
        if not ja_notificou_hoje(conn, "tarefa_horario", tarefa_id):
            avisos.append(("tarefa_horario", tarefa_id, "Lembrete", msg))

    # Compromisso do calendario do iCloud chegando (so origem="calendario" -
    # tarefa com horario ja tem o aviso acima, senao duplicaria). Pedido
    # explicito do Alex: "se eu marquei alguma coisa na agenda, daqui 10
    # minutos tu tem que fazer tal coisa, ja vai se arrumar". A busca do
    # iCloud ja vem protegida contra falha/instabilidade (ver
    # _eventos_de_hoje_com_seguranca) - um erro de rede so faz esse tipo de
    # aviso nao disparar nesse tick, nunca derruba o resto do scheduler.
    agora_dt = datetime.now()
    for evento in _eventos_de_hoje_com_seguranca(conn):
        if evento.get("origem") != "calendario" or evento.get("dia_inteiro"):
            continue
        try:
            inicio_evento = datetime.fromisoformat(evento["inicio"])
        except (ValueError, TypeError):
            continue
        minutos_pra_comecar = (inicio_evento - agora_dt).total_seconds() / 60
        if not (0 <= minutos_pra_comecar <= 10):
            continue
        ref_id = _id_estavel_evento_calendario(evento)
        if ja_notificou_hoje(conn, "compromisso_chegando", ref_id):
            continue
        hora_txt = inicio_evento.strftime("%H:%M")
        avisos.append(
            (
                "compromisso_chegando",
                ref_id,
                "Daqui a pouco",
                f"Daqui a pouco: \"{evento['titulo']}\" as {hora_txt} - ja va se preparando.",
            )
        )

    for voo in notificacoes.voos_de_hoje_com_horario(conn):
        if ja_notificou_hoje(conn, "voo_sair", voo["id"]):
            continue
        msg = _aviso_voo_sair(voo)
        if msg:
            avisos.append(("voo_sair", voo["id"], "Hora de ir pro voo", msg))

    if notificacoes.planejamento_semanal_devido() and not ja_notificou_hoje(conn, "planejamento_semanal"):
        avisos.append(
            (
                "planejamento_semanal",
                0,
                "Como fica sua semana?",
                "Ja sabe sua agenda dessa semana? Manda pra mim que eu registro tudo.",
            )
        )

    if notificacoes.hora_de_dormir_devida() and not ja_notificou_hoje(conn, "hora_de_dormir"):
        itens_noite = ", ".join(i["texto"].lower() for i in list_rotina_itens(conn, "noite"))
        corpo_noite = "22h - comeca a desacelerar pro sono."
        if itens_noite:
            corpo_noite += f" Rotina da noite: {itens_noite}."
        avisos.append(("hora_de_dormir", 0, "Hora de desacelerar", corpo_noite))

    avisos.extend(_avisos_assistente_vida(conn, datetime.now()))
    avisos.extend(_avisos_fase2(conn, datetime.now()))
    avisos.extend(_avisos_fase3(conn, datetime.now()))

    # Fechamento ativo do dia (21h, uma hora antes da hora_de_dormir) - manda
    # o fechamento sozinho em vez de esperar o Alex abrir a aba Painel.
    if notificacoes.fechamento_noturno_devido() and not ja_notificou_hoje(conn, "fechamento_noturno"):
        avisos.append(
            ("fechamento_noturno", 0, "Fechando o dia", notificacoes.mensagem_fechamento_noturno(conn))
        )

    msg = notificacoes.currency_voo_baixa(conn, limiar_dias=21)
    if msg and not ja_notificou_hoje(conn, "currency_voo"):
        avisos.append(("currency_voo", 0, "Faz tempo que voce nao voa", msg))

    # Contas a pagar da construtora vencendo/vencidas (v3.99.16 do outro lado):
    # so avisa o que realmente precisa de atencao agora - vencida ou vencendo nos
    # proximos 3 dias - pra nao virar ruido com toda conta em aberto todo dia.
    dados_contas = _buscar_contas_a_vencer_construtora(dias=30)
    if dados_contas and dados_contas.get("status") == "ok":
        for conta in dados_contas.get("contas", []):
            dias_ate = conta["dias_ate_vencer"]
            if dias_ate > 3:
                continue
            ref_id = _id_estavel_conta(conta)
            if ja_notificou_hoje(conn, "conta_a_vencer", ref_id):
                continue
            quem = conta.get("fornecedor") or conta.get("descricao") or "fornecedor nao informado"
            if dias_ate < 0:
                quando = f"venceu ha {abs(dias_ate)} dia(s)"
            elif dias_ate == 0:
                quando = "vence hoje"
            else:
                quando = f"vence em {dias_ate} dia(s)"
            avisos.append((
                "conta_a_vencer",
                ref_id,
                "Conta a pagar (construtora)",
                f"{quem}: R$ {conta['valor']:.2f} - {quando}.",
            ))

    for tarefa in notificacoes.tarefas_aguardando_bom_tempo(conn):
        if ja_notificou_hoje(conn, "clima_tarefa", tarefa["id"]):
            continue
        msg = _aviso_bom_tempo_pra_tarefa(tarefa)
        if msg:
            avisos.append(("clima_tarefa", tarefa["id"], "Dia bom pra tarefa pendente", msg))

    # Modo silencioso: avisos "soft" (nao presos a um instante especifico) ficam
    # represados fora do horario configurado (padrao 22:00-07:00, mesma janela
    # da hora_de_dormir) em vez de tocar o celular. Nao marca como notificado -
    # o proximo tick (5min) tenta de novo, entao o aviso so atrasa ate o
    # silencio acabar, nunca se perde. hora_de_dormir fica de fora de proposito
    # (senao ela mesma seria silenciada bem no horario que ela avisa).
    silencioso = notificacoes.dentro_do_horario_silencioso(
        datetime.now(),
        obter_configuracao(conn, "silencio_inicio") or "22:00",
        obter_configuracao(conn, "silencio_fim") or "07:00",
    )

    em_hiperfoco = vida.hiperfoco_ativo(obter_configuracao(conn, "hiperfoco_ate"), datetime.now())

    enviados = 0
    for tipo, ref_id, titulo, corpo in avisos:
        if em_hiperfoco and tipo not in vida.CRITICOS_HIPERFOCO:
            if tipo in vida.AVISOS_JANELA_CURTA:
                _adiar_aviso(conn, tipo, titulo, corpo)
                marcar_notificado(conn, tipo, ref_id)
            continue
        if silencioso and tipo not in NOTIFICACOES_URGENTES:
            continue
        for s in subs:
            sub_dict = json.loads(s["subscription_json"])
            ok = push_client.enviar(sub_dict, titulo, corpo)
            if not ok:
                delete_push_subscription(conn, s["endpoint"])
        if telegram_ok:
            # tarefa_parada ganha um botao de acao direto na notificacao -
            # marca como feita com um toque, sem precisar abrir o app nem
            # digitar nada (o pedido especifico do Alex pra esse canal).
            botoes = [("Marcar como feito", f"completar_tarefa:{ref_id}")] if tipo == "tarefa_parada" else None
            telegram_bot.enviar_mensagem(f"{titulo}\n{corpo}", botoes=botoes)
        marcar_notificado(conn, tipo, ref_id)
        if tipo in ("tarefa_parada", "espera_parada"):
            registrar_interacao_aprendizado(conn, tipo, ref_id)
        enviados += 1

    # Uber agendado: passou o tempo de espera, busca o preco de verdade
    # (trava com fare_id) e avisa - a corrida so sai com confirmacao
    # explicita do Alex, nunca automatica daqui.
    if uber_client.configurado():
        access_token = _uber_token_valido(conn)
        if access_token:
            for pedido in uber_pedidos_para_disparar(conn, datetime.now().isoformat()):
                _disparar_estimativa_uber(conn, pedido, access_token)
                atualizado = uber_pedido(conn, pedido["id"])
                if atualizado and atualizado["status"] == "aguardando_confirmacao":
                    corpo_uber = (
                        f"Uber pra {atualizado['destino']}: {atualizado['preco_texto']}. "
                        "Abre o painel pra confirmar."
                    )
                    for s in subs:
                        sub_dict = json.loads(s["subscription_json"])
                        push_client.enviar(sub_dict, "Hora do Uber", corpo_uber)
                    if telegram_ok:
                        telegram_bot.enviar_mensagem(f"Hora do Uber\n{corpo_uber}")
                    enviados += 1

    conn.close()
    return enviados


@app.route("/api/notificacoes/verificar-agora", methods=["POST"])
def notificacoes_verificar_agora():
    enviados = verificar_e_notificar()
    return jsonify({"avisos_enviados": enviados})


@app.route("/uber/conectar", methods=["GET"])
def uber_conectar():
    """Passo 1 do OAuth - so o Alex, ja logado no painel, clica nisso pra
    autorizar o app com a propria conta Uber dele."""
    if not uber_client.configurado():
        return "Uber ainda nao configurado - defina UBER_CLIENT_ID e UBER_CLIENT_SECRET no .env.", 400
    redirect_uri = request.host_url.rstrip("/") + "/uber/callback"
    return redirect(uber_client.url_autorizacao(redirect_uri))


@app.route("/uber/callback", methods=["GET"])
def uber_callback():
    """Passo 2 do OAuth - a Uber manda o Alex de volta pra ca com um codigo,
    trocado aqui por um token de verdade (guardado na tabela configuracoes)."""
    erro = request.args.get("error")
    if erro:
        return f"Autorizacao da Uber cancelada ou negada ({erro}).", 400
    codigo = request.args.get("code")
    if not codigo:
        return "Codigo de autorizacao nao recebido.", 400

    redirect_uri = request.host_url.rstrip("/") + "/uber/callback"
    try:
        dados = uber_client.trocar_codigo_por_token(codigo, redirect_uri)
    except requests.RequestException:
        return "Nao consegui trocar o codigo por um token - tenta de novo.", 502

    conn = get_db()
    definir_configuracao(conn, "uber_access_token", dados["access_token"])
    definir_configuracao(conn, "uber_refresh_token", dados.get("refresh_token", ""))
    expira_em = datetime.now() + timedelta(seconds=dados.get("expires_in", 2592000))
    definir_configuracao(conn, "uber_token_expira_em", expira_em.isoformat())
    conn.close()
    return "Uber conectado! Pode fechar essa aba e voltar pro painel."


@app.route("/api/uber/pedidos", methods=["GET"])
def uber_pedidos_pendentes():
    conn = get_db()
    pedidos = uber_pedidos_aguardando_confirmacao(conn)
    conn.close()
    return jsonify(pedidos)


@app.route("/api/uber/pedidos/<int:pedido_id>/confirmar", methods=["POST"])
def uber_confirmar(pedido_id):
    conn = get_db()
    pedido = uber_pedido(conn, pedido_id)
    if not pedido or pedido["status"] != "aguardando_confirmacao":
        conn.close()
        return jsonify({"error": "pedido nao encontrado ou ja tratado"}), 404

    access_token = _uber_token_valido(conn)
    if not access_token:
        conn.close()
        return jsonify({"error": "Uber nao conectado"}), 400

    try:
        resultado = uber_client.pedir_corrida(
            pedido["origem_lat"],
            pedido["origem_lng"],
            pedido["destino_lat"],
            pedido["destino_lng"],
            pedido["product_id"],
            pedido["fare_id"],
            access_token,
        )
    except requests.RequestException as e:
        atualizar_uber_pedido(conn, pedido_id, status="erro", erro=str(e))
        conn.close()
        return jsonify({"error": "nao consegui pedir a corrida agora"}), 502

    atualizar_uber_pedido(
        conn, pedido_id, status="confirmado", request_id=resultado.get("request_id") or ""
    )
    conn.close()
    return jsonify({"ok": True, "request_id": resultado.get("request_id")})


@app.route("/api/uber/pedidos/<int:pedido_id>/cancelar", methods=["POST"])
def uber_cancelar(pedido_id):
    conn = get_db()
    pedido = uber_pedido(conn, pedido_id)
    if not pedido:
        conn.close()
        return jsonify({"error": "pedido nao encontrado"}), 404
    atualizar_uber_pedido(conn, pedido_id, status="cancelado")
    conn.close()
    return jsonify({"ok": True})


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

    body = _corpo_json()
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


@app.route("/api/notas", methods=["GET"])
def notas():
    conn = get_db()
    resultado = list_notas(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/notas/<int:nota_id>", methods=["DELETE"])
def apagar_nota_rota(nota_id):
    conn = get_db()
    apagar_nota(conn, nota_id)
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/lembretes", methods=["GET"])
def lembretes():
    conn = get_db()
    resultado = list_lembretes(conn)
    conn.close()
    # Pedido do Alex ("datas importantes" parecia simples demais): manda a
    # PROXIMA ocorrencia + dias restantes calculados, nao so a data crua -
    # sem isso um lembrete recorrente mostrava o ano ORIGINAL de criacao pra
    # sempre, nunca o proximo aniversario de verdade.
    hoje = date.today()
    for item in resultado:
        proxima = notificacoes.proxima_ocorrencia_lembrete(
            date.fromisoformat(item["data"]), bool(item["recorrente"]), hoje
        )
        item["proxima_ocorrencia"] = proxima.isoformat()
        item["dias_restantes"] = (proxima - hoje).days
        item["sugestao"] = vida.sugestao_acao_data(item["titulo"])
    return jsonify(resultado)


@app.route("/api/lembretes", methods=["POST"])
def criar_lembrete():
    body = _corpo_json()
    titulo = (body.get("titulo") or "").strip()
    data_str = (body.get("data") or "").strip()
    recorrente = bool(body.get("recorrente", False))
    if not titulo:
        return jsonify({"error": "informe um titulo"}), 400
    try:
        date.fromisoformat(data_str)
    except (ValueError, TypeError):
        return jsonify({"error": "data precisa estar em formato AAAA-MM-DD"}), 400

    conn = get_db()
    lembrete_id = create_lembrete(conn, titulo, data_str, recorrente)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"id": lembrete_id, "ok": True}), 201


@app.route("/api/lembretes/<int:lembrete_id>", methods=["DELETE"])
def apagar_lembrete(lembrete_id):
    conn = get_db()
    delete_lembrete(conn, lembrete_id)
    conn.close()
    return jsonify({"ok": True})


def _criar_medicamento(conn, nome: str, dosagem: str | None, horario: str, recorrencia: str, texto: str | None):
    """Orquestra as duas insercoes (a tarefa recorrente que de verdade
    aparece na agenda/dispara aviso, e o metadado estruturado em
    medicamentos) - compartilhado entre a rota HTTP do form e o executor do
    chat tool, pra nunca divergir. Devolve {"erro": ...} se horario/
    recorrencia vierem invalidos, nunca deixa criar um medicamento quebrado."""
    hora_normalizada = _normalizar_hora(horario)
    if not hora_normalizada:
        return {"erro": "horario invalido - use HH:MM"}
    if not agenda.recorrencia_valida(recorrencia):
        return {"erro": f"recorrencia mal formatada: {recorrencia!r}"}
    titulo_tarefa = f"Tomar {nome}" + (f" ({dosagem})" if dosagem else "")
    cur = conn.execute(
        "INSERT INTO tasks (title, hora, source_text, recorrencia) VALUES (?, ?, ?, ?)",
        (titulo_tarefa, hora_normalizada, texto, recorrencia),
    )
    conn.commit()
    medicamento_id = create_medicamento(conn, nome, dosagem, hora_normalizada, recorrencia, cur.lastrowid)
    materializar_tarefas_recorrentes(conn)
    return {"ok": True, "medicamento_id": medicamento_id}


@app.route("/api/medicamentos", methods=["GET"])
def medicamentos():
    conn = get_db()
    resultado = list_medicamentos_ativos(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/medicamentos", methods=["POST"])
def criar_medicamento_rota():
    body = _corpo_json()
    nome = (body.get("nome") or "").strip()
    if not nome:
        return jsonify({"error": "informe o nome do remedio"}), 400
    dosagem = (body.get("dosagem") or "").strip() or None
    horario = (body.get("horario") or "").strip()
    recorrencia = (body.get("recorrencia") or "diaria").strip()

    conn = get_db()
    resultado = _criar_medicamento(conn, nome, dosagem, horario, recorrencia, None)
    if "erro" in resultado:
        conn.close()
        return jsonify({"error": resultado["erro"]}), 400
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify(resultado), 201


@app.route("/api/medicamentos/<int:medicamento_id>", methods=["DELETE"])
def apagar_medicamento(medicamento_id):
    conn = get_db()
    delete_medicamento(conn, medicamento_id)
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/esperas", methods=["GET"])
def esperas():
    conn = get_db()
    resultado = list_esperas_pendentes(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/esperas", methods=["POST"])
def criar_espera():
    body = _corpo_json()
    quem = _texto_seguro(body.get("quem"))
    sobre = _texto_seguro(body.get("sobre"))
    if not quem or not sobre:
        return jsonify({"error": "informe quem e sobre o que"}), 400

    conn = get_db()
    espera_id = create_espera(conn, quem, sobre)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"id": espera_id, "ok": True}), 201


@app.route("/api/esperas/<int:espera_id>/resolver", methods=["POST"])
def resolver_espera_rota(espera_id):
    conn = get_db()
    ok = resolver_espera(conn, espera_id)
    conn.close()
    if not ok:
        return jsonify({"error": "espera nao encontrada ou ja resolvida"}), 404
    return jsonify({"ok": True})


@app.route("/api/esperas/<int:espera_id>", methods=["DELETE"])
def apagar_espera_rota(espera_id):
    conn = get_db()
    apagar_espera(conn, espera_id)
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/streak", methods=["GET"])
def streak_atual():
    conn = get_db()
    dias_ativos = list_dias_ativos(conn)
    conn.close()
    hoje = date.today()
    dias = streak.calcular_streak(dias_ativos, hoje)
    return jsonify({"dias": dias, "ativo_hoje": hoje.isoformat() in dias_ativos})


@app.route("/api/voos", methods=["GET"])
def voos():
    conn = get_db()
    resultado = list_voos(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/voos", methods=["POST"])
def criar_voo():
    body = _corpo_json()
    data_str = (body.get("data") or "").strip()
    destino = (body.get("destino") or "").strip()
    origem = (body.get("origem") or "").strip() or None
    observacao = (body.get("observacao") or "").strip() or None
    horas = body.get("horas")
    hora = _normalizar_hora(body.get("hora"))

    if not destino:
        return jsonify({"error": "informe o destino"}), 400
    try:
        date.fromisoformat(data_str)
    except (ValueError, TypeError):
        return jsonify({"error": "data precisa estar em formato AAAA-MM-DD"}), 400
    if horas is not None:
        if not isinstance(horas, (int, float)) or horas <= 0:
            return jsonify({"error": "horas precisa ser um numero positivo, ou omitido pra voo agendado"}), 400

    conn = get_db()
    voo_id = create_voo(conn, data_str, destino, origem, horas, observacao, hora)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"id": voo_id, "ok": True}), 201


@app.route("/api/voos/<int:voo_id>", methods=["DELETE"])
def apagar_voo(voo_id):
    conn = get_db()
    delete_voo(conn, voo_id)
    conn.close()
    return jsonify({"ok": True})


def _voo_com_clima(voo: dict) -> dict:
    """Anexa previsao do tempo (se der) pro destino/data do voo - nunca
    quebra se a cidade nao for encontrada ou a data estiver fora da janela
    de previsao, so nao inclui o campo 'clima'."""
    previsao = clima.previsao_para_cidade_e_data(voo["destino"], voo["data"])
    return {**voo, "clima": previsao}


@app.route("/api/voos/resumo", methods=["GET"])
def voos_resumo():
    conn = get_db()
    todos = list_voos(conn)
    conn.close()
    hoje = date.today()
    resumo = voos_module.resumo_horas(todos, hoje)
    proximos = [_voo_com_clima(v) for v in voos_module.proximos_voos(todos, hoje)]
    dias_sem_voar = voos_module.dias_desde_ultimo_voo(todos, hoje)
    return jsonify({**resumo, "proximos": proximos, "dias_desde_ultimo_voo": dias_sem_voar})


@app.route("/api/voos/historico", methods=["GET"])
def voos_historico():
    conn = get_db()
    todos = list_voos(conn)
    conn.close()
    return jsonify(voos_module.historico_horas_acumuladas(todos, date.today()))


@app.route("/api/clima/metar", methods=["GET"])
def clima_metar():
    icao = (request.args.get("icao") or "").strip()
    resultado = metar.buscar_metar_taf(icao)
    return jsonify(resultado)


@app.route("/api/clima/hoje", methods=["GET"])
def clima_hoje_rota():
    cidade = os.environ.get("CIDADE_PADRAO", "").strip()
    if not cidade:
        return jsonify({"configurado": False})
    resumo = clima.resumo_chuva_hoje_para_cidade(cidade)
    if not resumo:
        return jsonify({"configurado": True, "erro": "nao consegui buscar a previsao agora"})
    return jsonify({"configurado": True, **resumo})


@app.route("/api/saude/importar", methods=["POST"])
def saude_importar():
    token_esperado = os.environ.get("SAUDE_WEBHOOK_TOKEN")
    if token_esperado and request.headers.get("X-Webhook-Token") != token_esperado:
        return jsonify({"error": "token invalido"}), 401

    body = _corpo_json()
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
    hidratacao_hoje = contar_hidratacao_dia(conn, date.today().isoformat())
    dica_sono = aprendizado.dica_sono_produtividade(conn)
    dica_humor = aprendizado.dica_sono_humor(conn)
    conn.close()
    return jsonify(
        {"dados": dia, "hidratacao_hoje": hidratacao_hoje, "dica_sono": dica_sono, "dica_humor": dica_humor}
    )


@app.route("/api/hidratacao", methods=["POST"])
def registrar_hidratacao_rota():
    conn = get_db()
    total = registrar_hidratacao(conn, date.today().isoformat())
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "total_hoje": total}), 201


@app.route("/api/medidas", methods=["GET"])
def medidas():
    tipo = request.args.get("tipo") or None
    conn = get_db()
    resultado = list_medidas_corporais(conn, tipo=tipo)
    conn.close()
    return jsonify(resultado)


@app.route("/api/medidas", methods=["POST"])
def criar_medida_rota():
    body = _corpo_json()
    tipo = (body.get("tipo") or "").strip().lower()
    unidade = (body.get("unidade") or "").strip()
    data_medida = (body.get("data") or date.today().isoformat()).strip()
    if not tipo:
        return jsonify({"error": "informe o tipo da medida (ex: peso, biceps)"}), 400
    try:
        valor = float(body.get("valor"))
    except (TypeError, ValueError):
        return jsonify({"error": "valor invalido"}), 400
    if not math.isfinite(valor):
        return jsonify({"error": "valor invalido"}), 400
    try:
        date.fromisoformat(data_medida)
    except ValueError:
        return jsonify({"error": "data invalida - use AAAA-MM-DD"}), 400

    if not unidade:
        unidade = "kg" if tipo == "peso" else "cm"

    conn = get_db()
    medida_id = create_medida_corporal(conn, tipo, valor, unidade, data_medida)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "medida_id": medida_id}), 201


@app.route("/api/medidas/<int:medida_id>", methods=["DELETE"])
def apagar_medida(medida_id):
    conn = get_db()
    delete_medida_corporal(conn, medida_id)
    conn.close()
    return jsonify({"ok": True})


# ---- Assistente de vida (BRIEFING.md, Fase 1) ----

def _checkin_com_rotulos(checkin: dict | None) -> dict | None:
    if not checkin:
        return None
    return {c: vida.ROTULO_CHECKIN.get(checkin.get(c)) for c in vida.CAMPOS_CHECKIN}


@app.route("/api/checkin/hoje", methods=["GET"])
def checkin_hoje():
    conn = get_db()
    checkin = get_checkin(conn, date.today().isoformat())
    conn.close()
    return jsonify({"checkin": _checkin_com_rotulos(checkin)})


@app.route("/api/checkin", methods=["POST"])
def salvar_checkin_rota():
    body = _corpo_json()
    campos = {c: vida.valor_checkin(body.get(c)) for c in vida.CAMPOS_CHECKIN if c in body}
    campos = {c: v for c, v in campos.items() if v is not None}
    if not campos:
        return jsonify({"error": "mande energia, sono ou humor como 'ruim', 'ok' ou 'bom'"}), 400
    conn = get_db()
    checkin = salvar_checkin(conn, date.today().isoformat(), campos)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"checkin": _checkin_com_rotulos(checkin)})


def _rotina_do_dia(conn, momento: str, dia: str) -> dict:
    itens = list_rotina_itens(conn, momento)
    feitos = rotina_marcadas(conn, dia)
    lista = [{"id": i["id"], "texto": i["texto"], "feito": i["id"] in feitos} for i in itens]
    return {
        "momento": momento,
        "itens": lista,
        "feitos": sum(1 for i in lista if i["feito"]),
        "total": len(lista),
    }


@app.route("/api/rotina", methods=["GET"])
def rotina():
    momento = request.args.get("momento") or vida.momento_rotina(datetime.now())
    if momento not in vida.ITENS_ROTINA_PADRAO:
        return jsonify({"error": "momento deve ser 'manha' ou 'noite'"}), 400
    conn = get_db()
    resultado = _rotina_do_dia(conn, momento, vida.dia_da_rotina(momento, datetime.now()).isoformat())
    conn.close()
    return jsonify(resultado)


@app.route("/api/rotina/<int:item_id>/alternar", methods=["POST"])
def alternar_rotina(item_id):
    conn = get_db()
    existe = conn.execute("SELECT momento FROM rotina_itens WHERE id = ? AND ativo = 1", (item_id,)).fetchone()
    if not existe:
        conn.close()
        return jsonify({"error": "item nao encontrado"}), 404
    dia = vida.dia_da_rotina(existe["momento"], datetime.now())
    feito = alternar_rotina_item(conn, dia.isoformat(), item_id)
    if feito:
        _marcar_atividade(conn)
        conn.commit()
    conn.close()
    return jsonify({"feito": feito})


@app.route("/api/rotina/itens", methods=["POST"])
def criar_item_rotina():
    body = _corpo_json()
    momento = (body.get("momento") or "").strip()
    texto = (body.get("texto") or "").strip()
    if momento not in vida.ITENS_ROTINA_PADRAO:
        return jsonify({"error": "momento deve ser 'manha' ou 'noite'"}), 400
    if not texto or len(texto) > 120:
        return jsonify({"error": "escreva o item (ate 120 caracteres)"}), 400
    conn = get_db()
    item_id = create_rotina_item(conn, momento, texto)
    conn.close()
    return jsonify({"ok": True, "id": item_id}), 201


@app.route("/api/rotina/itens/<int:item_id>", methods=["DELETE"])
def apagar_item_rotina(item_id):
    conn = get_db()
    delete_rotina_item(conn, item_id)
    conn.close()
    return jsonify({"ok": True})


def _estado_hiperfoco(conn) -> dict:
    ate = obter_configuracao(conn, "hiperfoco_ate")
    agora = datetime.now()
    ativo = vida.hiperfoco_ativo(ate, agora)
    return {
        "ativo": ativo,
        "ate": ate if ativo else None,
        "minutos_restantes": vida.minutos_restantes_hiperfoco(ate, agora),
        "segundos_restantes": int((datetime.fromisoformat(ate) - agora).total_seconds()) if ativo else 0,
    }


def _iniciar_hiperfoco(conn, minutos: int) -> dict:
    ate = datetime.now() + timedelta(minutes=minutos)
    definir_configuracao(conn, "hiperfoco_ate", ate.isoformat(timespec="seconds"))
    definir_configuracao(conn, "hiperfoco_minutos", str(minutos))
    return _estado_hiperfoco(conn)


@app.route("/api/hiperfoco", methods=["GET"])
def hiperfoco():
    conn = get_db()
    estado = _estado_hiperfoco(conn)
    conn.close()
    return jsonify(estado)


@app.route("/api/hiperfoco", methods=["POST"])
def iniciar_hiperfoco_rota():
    minutos = _corpo_json().get("minutos")
    if isinstance(minutos, bool) or minutos not in vida.DURACOES_HIPERFOCO:
        return jsonify({"error": "duracao deve ser 25, 50 ou 90 minutos"}), 400
    conn = get_db()
    estado = _iniciar_hiperfoco(conn, minutos)
    conn.close()
    return jsonify(estado)


@app.route("/api/hiperfoco", methods=["DELETE"])
def encerrar_hiperfoco():
    conn = get_db()
    definir_configuracao(conn, "hiperfoco_ate", "")
    conn.close()
    return jsonify({"ativo": False, "ate": None, "minutos_restantes": 0, "segundos_restantes": 0})


def _candidatas_essencial(conn, hoje: date) -> list[dict]:
    materializar_tarefas_recorrentes(conn, hoje)
    rows = conn.execute(
        "SELECT id, title, due_date, hora, recorrente_origem_id FROM tasks "
        "WHERE completed_at IS NULL AND recorrencia IS NULL AND (due_date IS NULL OR due_date <= ?) "
        "AND NOT (recorrente_origem_id IS NOT NULL AND due_date < ?)",
        (hoje.isoformat(), hoje.isoformat()),
    ).fetchall()
    candidatas = [dict(r) for r in rows]
    candidatas.sort(key=lambda t: (-vida.pontuar_tarefa_essencial(t, hoje), t["id"]))
    return candidatas[:30]


def _gerar_essencial(conn, hoje: date) -> list[tuple[int, str | None]]:
    """A IA escolhe (Haiku, barato) - se falhar ou devolver id que nao existe,
    cai na heuristica local, nunca deixa a lista vazia por erro de rede."""
    candidatas = _candidatas_essencial(conn, hoje)
    if not candidatas:
        salvar_essencial(conn, hoje.isoformat(), [])
        return []
    ids_validos = {t["id"] for t in candidatas}
    escolhas: list[tuple[int, str | None]] = []
    resultado, erro = _call_claude(claude_client.escolher_essencial, candidatas)
    if not erro:
        itens, usage = resultado
        _log_usage(conn, usage)
        for item in itens if isinstance(itens, list) else []:
            if not isinstance(item, dict) or item.get("id") not in ids_validos:
                continue
            if item["id"] in {e[0] for e in escolhas} or len(escolhas) >= 3:
                continue
            motivo = item.get("motivo")
            escolhas.append((item["id"], motivo if isinstance(motivo, str) and motivo.strip() else None))
    if not escolhas:
        escolhas = [(tid, None) for tid in vida.escolher_essencial_heuristica(candidatas, hoje)]
    salvar_essencial(conn, hoje.isoformat(), escolhas)
    return escolhas


def _essencial_detalhado(conn, hoje: date) -> list[dict]:
    escolhas = get_essencial(conn, hoje.isoformat())
    if not escolhas:
        return []
    ids = [e["task_id"] for e in escolhas]
    placeholders = ",".join("?" * len(ids))
    tarefas = {
        r["id"]: dict(r)
        for r in conn.execute(
            f"SELECT id, title, due_date, hora, completed_at FROM tasks WHERE id IN ({placeholders})", ids
        ).fetchall()
    }
    resultado = []
    for e in escolhas:
        t = tarefas.get(e["task_id"])
        if t:
            resultado.append({**t, "motivo": e["motivo"], "feita": bool(t["completed_at"])})
    return resultado


@app.route("/api/essencial", methods=["GET"])
def essencial():
    hoje = date.today()
    conn = get_db()
    if obter_configuracao(conn, "essencial_gerado_em") != hoje.isoformat():
        _gerar_essencial(conn, hoje)
        definir_configuracao(conn, "essencial_gerado_em", hoje.isoformat())
    resultado = {
        "modo_ativo": obter_configuracao(conn, "modo_essencial_data") == hoje.isoformat(),
        "tarefas": _essencial_detalhado(conn, hoje),
    }
    conn.close()
    return jsonify(resultado)


@app.route("/api/essencial/gerar", methods=["POST"])
def regerar_essencial():
    hoje = date.today()
    conn = get_db()
    _gerar_essencial(conn, hoje)
    definir_configuracao(conn, "essencial_gerado_em", hoje.isoformat())
    tarefas = _essencial_detalhado(conn, hoje)
    conn.close()
    return jsonify({"tarefas": tarefas})


@app.route("/api/essencial/trocar", methods=["POST"])
def trocar_essencial():
    task_id = _corpo_json().get("task_id")
    hoje = date.today()
    conn = get_db()
    atuais = get_essencial(conn, hoje.isoformat())
    ja_usadas = {e["task_id"] for e in atuais}
    if isinstance(task_id, bool) or task_id not in ja_usadas:
        conn.close()
        return jsonify({"error": "essa tarefa nao esta no essencial de hoje"}), 400
    restantes = [(e["task_id"], e["motivo"]) for e in atuais if e["task_id"] != task_id]
    try:
        rejeitadas = json.loads(obter_configuracao(conn, "essencial_rejeitadas") or "{}")
    except ValueError:
        rejeitadas = {}
    ids_rejeitados = set(rejeitadas.get("ids", [])) if rejeitadas.get("data") == hoje.isoformat() else set()
    ids_rejeitados.add(task_id)
    definir_configuracao(
        conn, "essencial_rejeitadas", json.dumps({"data": hoje.isoformat(), "ids": sorted(ids_rejeitados)})
    )
    for t in _candidatas_essencial(conn, hoje):
        if t["id"] not in ja_usadas and t["id"] not in ids_rejeitados:
            restantes.append((t["id"], None))
            break
    salvar_essencial(conn, hoje.isoformat(), restantes)
    tarefas = _essencial_detalhado(conn, hoje)
    conn.close()
    return jsonify({"tarefas": tarefas})


@app.route("/api/essencial/modo", methods=["POST"])
def modo_essencial():
    ativo = _corpo_json().get("ativo") is True
    conn = get_db()
    definir_configuracao(conn, "modo_essencial_data", date.today().isoformat() if ativo else "")
    conn.close()
    return jsonify({"modo_ativo": ativo})


@app.route("/api/tasks/<int:task_id>/requebrar", methods=["POST"])
def requebrar_task(task_id):
    """Tarefa empacada: pede um jeito DIFERENTE de atacar (primeiro passo
    ridiculamente facil). Passos ja feitos ficam; os nao feitos sao trocados."""
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify({"error": "tarefa nao encontrada"}), 404
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
    _log_usage(conn, usage)
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


def _vencimento_em_aberto(conn, conta, hoje: date) -> date:
    """O vencimento que ainda precisa ser pago: o que passou ha ate 10 dias sem
    marcar como paga (pagar com atraso marca ESSE, nao o do mes seguinte), senao
    o proximo. Conta cadastrada depois do vencimento passado comeca no proximo."""
    anterior = vida.vencimento_anterior(conta["dia_vencimento"], hoje)
    cadastro = (conta["criado_em"] or "")[:10]
    if (
        anterior < hoje
        and (hoje - anterior).days <= 10
        and cadastro <= anterior.isoformat()
        and not conta_paga(conn, conta["id"], anterior.isoformat())
    ):
        return anterior
    return vida.proximo_vencimento(conta["dia_vencimento"], hoje)


def _contas_pessoais_com_status(conn, hoje: date) -> list[dict]:
    resultado = []
    for c in list_contas_pessoais(conn):
        venc = _vencimento_em_aberto(conn, c, hoje)
        resultado.append(
            {
                **c,
                "proximo_vencimento": venc.isoformat(),
                "dias_ate_vencer": (venc - hoje).days,
                "paga": conta_paga(conn, c["id"], venc.isoformat()),
            }
        )
    return resultado


def _inteiro_no_intervalo(valor, minimo: int, maximo: int) -> int | None:
    if isinstance(valor, bool):
        return None
    try:
        numero = int(valor)
    except (TypeError, ValueError, OverflowError):
        return None
    if isinstance(valor, float) and valor != numero:
        return None
    return numero if minimo <= numero <= maximo else None


@app.route("/api/contas-pessoais", methods=["GET"])
def contas_pessoais():
    conn = get_db()
    resultado = _contas_pessoais_com_status(conn, date.today())
    conn.close()
    return jsonify(resultado)


@app.route("/api/contas-pessoais", methods=["POST"])
def criar_conta_pessoal():
    body = _corpo_json()
    nome = (body.get("nome") or "").strip()
    dia = _inteiro_no_intervalo(body.get("dia_vencimento"), 1, 31)
    if not nome or len(nome) > 80:
        return jsonify({"error": "informe o nome da conta (ate 80 caracteres)"}), 400
    if dia is None:
        return jsonify({"error": "dia de vencimento deve ser de 1 a 31"}), 400
    valor = body.get("valor")
    if valor in ("", None):
        valor = None
    else:
        try:
            valor = float(valor)
        except (TypeError, ValueError):
            return jsonify({"error": "valor invalido"}), 400
        if isinstance(body.get("valor"), bool) or valor < 0 or not math.isfinite(valor):
            return jsonify({"error": "valor invalido"}), 400
    conn = get_db()
    conta_id = create_conta_pessoal(conn, nome, dia, valor)
    conn.close()
    return jsonify({"ok": True, "id": conta_id}), 201


@app.route("/api/contas-pessoais/<int:conta_id>", methods=["DELETE"])
def apagar_conta_pessoal(conta_id):
    conn = get_db()
    delete_conta_pessoal(conn, conta_id)
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/contas-pessoais/<int:conta_id>/paga", methods=["POST"])
def pagar_conta_pessoal(conta_id):
    conn = get_db()
    conta = conn.execute("SELECT * FROM contas_pessoais WHERE id = ?", (conta_id,)).fetchone()
    if not conta:
        conn.close()
        return jsonify({"error": "conta nao encontrada"}), 404
    venc = _vencimento_em_aberto(conn, conta, date.today())
    marcar_conta_paga(conn, conta_id, venc.isoformat())
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "vencimento": venc.isoformat()})


def _assinaturas_pendentes_revisao(conn, hoje: date) -> list[dict]:
    """Recorrentes detectadas que ainda nao foram confirmadas neste mes. Quem
    ja respondeu 'nao uso' alguma vez nunca mais e perguntado (virou tarefa
    de cancelar)."""
    ano_mes = hoje.strftime("%Y-%m")
    respostas = respostas_assinaturas(conn)
    nunca_mais = {r["descricao_normalizada"] for r in respostas if r["resposta"] == "nao_usa"}
    respondidas_mes = {r["descricao_normalizada"] for r in respostas if r["ano_mes"] == ano_mes}
    pendentes = []
    for r in _gastos_fixos(conn)["recorrentes"]:
        chave = gastos._normalizar_descricao(r["descricao"])
        if not chave or chave in nunca_mais or chave in respondidas_mes:
            continue
        pendentes.append({"descricao": r["descricao"], "valor": r["valor_medio"], "categoria": r["categoria"]})
    return pendentes


@app.route("/api/assinaturas/revisao", methods=["GET"])
def assinaturas_revisao():
    conn = get_db()
    resultado = _assinaturas_pendentes_revisao(conn, date.today())
    conn.close()
    return jsonify(resultado)


@app.route("/api/assinaturas/revisao", methods=["POST"])
def responder_assinatura_rota():
    body = _corpo_json()
    descricao = (body.get("descricao") or "").strip() if isinstance(body.get("descricao"), str) else ""
    resposta = body.get("resposta")
    if not descricao or len(descricao) > 200 or resposta not in ("usa", "nao_usa"):
        return jsonify({"error": "mande descricao e resposta ('usa' ou 'nao_usa')"}), 400
    valor = body.get("valor")
    valor = valor if isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor) else None
    conn = get_db()
    responder_assinatura(
        conn, gastos._normalizar_descricao(descricao), date.today().strftime("%Y-%m"), descricao, valor, resposta
    )
    tarefa_id = None
    if resposta == "nao_usa":
        cur = conn.execute("INSERT INTO tasks (title) VALUES (?)", (f"Cancelar assinatura: {descricao}",))
        tarefa_id = cur.lastrowid
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "tarefa_id": tarefa_id})


def _pessoas_com_status(conn, hoje: date) -> list[dict]:
    pessoas = list_pessoas(conn)
    atrasadas = {p["id"] for p, _ in vida.pessoas_sem_contato(pessoas, hoje)}
    resultado = []
    for p in pessoas:
        dias = None
        if p["ultimo_contato"]:
            try:
                dias = (hoje - date.fromisoformat(p["ultimo_contato"])).days
            except ValueError:
                dias = None
        ultima = list_conversas(conn, pessoa_id=p["id"], limite=1)
        resultado.append(
            {
                **p,
                "dias_sem_falar": dias,
                "atrasada": p["id"] in atrasadas,
                "ultima_conversa": ultima[0]["sobre"] if ultima else None,
            }
        )
    resultado.sort(key=lambda x: (not x["atrasada"], x["nome"].lower()))
    return resultado


@app.route("/api/pessoas", methods=["GET"])
def pessoas():
    conn = get_db()
    resultado = _pessoas_com_status(conn, date.today())
    conn.close()
    return jsonify(resultado)


def _salvar_pessoa(conn, nome: str, freq: int) -> tuple[int, bool]:
    """Mesmo nome (sem acento/caixa) atualiza a frequencia em vez de duplicar
    a pessoa. Devolve (id, atualizada)."""
    alvo = vida.normalizar_nome(nome)
    existente = next((p for p in list_pessoas(conn) if vida.normalizar_nome(p["nome"]) == alvo), None)
    if existente:
        conn.execute("UPDATE pessoas SET frequencia_dias = ? WHERE id = ?", (freq, existente["id"]))
        conn.commit()
        return existente["id"], True
    return create_pessoa(conn, nome, freq), False


@app.route("/api/pessoas", methods=["POST"])
def criar_pessoa_rota():
    body = _corpo_json()
    nome = (body.get("nome") or "").strip() if isinstance(body.get("nome"), str) else ""
    freq_bruta = body.get("frequencia_dias")
    freq = 14 if freq_bruta in (None, "") else _inteiro_no_intervalo(freq_bruta, 1, 365)
    if not nome or len(nome) > 60:
        return jsonify({"error": "informe o nome (ate 60 caracteres)"}), 400
    if freq is None:
        return jsonify({"error": "frequencia deve ser de 1 a 365 dias"}), 400
    conn = get_db()
    pessoa_id, atualizada = _salvar_pessoa(conn, nome, freq)
    conn.close()
    return jsonify({"ok": True, "id": pessoa_id, "atualizada": atualizada}), 200 if atualizada else 201


@app.route("/api/pessoas/<int:pessoa_id>", methods=["DELETE"])
def apagar_pessoa(pessoa_id):
    conn = get_db()
    delete_pessoa(conn, pessoa_id)
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/pessoas/<int:pessoa_id>/falei", methods=["POST"])
def falei_com_pessoa(pessoa_id):
    sobre_bruto = _corpo_json().get("sobre")
    sobre = sobre_bruto.strip()[:300] if isinstance(sobre_bruto, str) and sobre_bruto.strip() else None
    conn = get_db()
    pessoa = conn.execute("SELECT * FROM pessoas WHERE id = ?", (pessoa_id,)).fetchone()
    if not pessoa:
        conn.close()
        return jsonify({"error": "pessoa nao encontrada"}), 404
    registrar_conversa(conn, pessoa_id, pessoa["nome"], sobre, date.today().isoformat())
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/conversas", methods=["GET"])
def conversas():
    pessoa_id = request.args.get("pessoa_id", type=int)
    conn = get_db()
    resultado = list_conversas(conn, pessoa_id=pessoa_id, limite=30)
    conn.close()
    return jsonify(resultado)


def _registrar_conversa_por_nome(conn, nome: str, sobre: str | None, texto: str | None) -> dict:
    pessoa = vida.achar_pessoa(list_pessoas(conn), nome)
    registrar_conversa(
        conn,
        pessoa["id"] if pessoa else None,
        pessoa["nome"] if pessoa else nome.strip(),
        sobre,
        date.today().isoformat(),
        texto,
    )
    return {"ok": True, "pessoa_da_lista": pessoa["nome"] if pessoa else None}


@app.route("/api/decisao", methods=["POST"])
def decisao():
    bruto = _corpo_json().get("pergunta")
    pergunta = bruto.strip() if isinstance(bruto, str) else ""
    if not pergunta or len(pergunta) > 1000:
        return jsonify({"error": "escreva a decisao (ate 1000 caracteres)"}), 400
    conn = get_db()
    memorias = [m["texto"] for m in list_memorias(conn)]
    result, error = _call_claude(claude_client.analisar_decisao, pergunta, memorias)
    if error:
        conn.close()
        return error
    analise, usage = result
    if not isinstance(analise, dict):
        conn.close()
        return jsonify({"error": CLAUDE_FORMAT_ERROR_MSG}), 502
    _log_usage(conn, usage)
    decisao_id = create_decisao(conn, pergunta, json.dumps(analise, ensure_ascii=False))
    conn.close()
    return jsonify({"id": decisao_id, "pergunta": pergunta, "analise": analise})


@app.route("/api/decisoes", methods=["GET"])
def decisoes():
    conn = get_db()
    resultado = [
        {
            "id": d["id"],
            "pergunta": d["pergunta"],
            "analise": json.loads(d["analise_json"]),
            "criado_em": d["criado_em"],
        }
        for d in list_decisoes(conn)
    ]
    conn.close()
    return jsonify(resultado)


# ---- Assistente de vida (BRIEFING.md, Fase 2) ----

def _texto_curto(valor, maximo: int) -> str | None:
    """String aparada e nao vazia com ate `maximo` caracteres, senao None."""
    if not isinstance(valor, str):
        return None
    texto = valor.strip()
    return texto if texto and len(texto) <= maximo else None


def _data_iso_valida(valor) -> str | None:
    if not isinstance(valor, str):
        return None
    try:
        return date.fromisoformat(valor.strip()).isoformat()
    except ValueError:
        return None


@app.route("/api/treino/fichas", methods=["GET"])
def fichas_treino():
    conn = get_db()
    resultado = list_fichas_treino(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/treino/fichas", methods=["POST"])
def salvar_ficha_treino_rota():
    body = _corpo_json()
    grupo = _texto_curto(body.get("grupo"), 40)
    exercicios = body.get("exercicios")
    if isinstance(exercicios, list):
        exercicios = "\n".join(str(e).strip() for e in exercicios if str(e).strip())
    exercicios = _texto_curto(exercicios, 3000)
    if not grupo or not exercicios:
        return jsonify({"error": "informe o grupo e os exercicios (um por linha)"}), 400
    conn = get_db()
    ficha_id = salvar_ficha_treino(conn, grupo, exercicios)
    conn.close()
    return jsonify({"ok": True, "id": ficha_id}), 201


@app.route("/api/treino/fichas/<int:ficha_id>", methods=["DELETE"])
def apagar_ficha_treino(ficha_id):
    conn = get_db()
    delete_ficha_treino(conn, ficha_id)
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/treino", methods=["GET"])
def treinos():
    conn = get_db()
    resultado = list_treinos(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/treino", methods=["POST"])
def registrar_treino_rota():
    body = _corpo_json()
    grupo = _texto_curto(body.get("grupo"), 40)
    nota = _texto_curto(body.get("nota"), 300)
    duracao = body.get("duracao_min")
    if duracao not in (None, ""):
        duracao = _inteiro_no_intervalo(duracao, 1, 600)
        if duracao is None:
            return jsonify({"error": "duracao deve ser de 1 a 600 minutos"}), 400
    else:
        duracao = None
    conn = get_db()
    treino_id = registrar_treino(conn, date.today().isoformat(), grupo, duracao, nota)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": treino_id}), 201


def _clima_texto_para(destino: str, data_iso: str) -> str | None:
    try:
        previsao = clima.previsao_para_cidade_e_data(destino, data_iso)
    except requests.RequestException:
        return None
    if not previsao:
        return None
    return (
        f"{previsao.get('temp_min')}-{previsao.get('temp_max')}C, "
        f"{previsao.get('chuva_pct')}% de chance de chuva"
    )


def _viagem_detalhada(conn, v: dict, hoje: date) -> dict:
    lugares = [
        l for l in list_lugares(conn)
        if vida.mesma_cidade(l["cidade"], v["destino"])
    ]
    ida = date.fromisoformat(v["data_ida"])
    return {
        **v,
        "dias_ate": (ida - hoje).days,
        "itens": list_itens_viagem(conn, v["id"]),
        "lugares": [{"nome": l["nome"], "tipo": l["tipo"], "nota": l["nota"]} for l in lugares],
    }


@app.route("/api/viagens", methods=["GET"])
def viagens():
    hoje = date.today()
    conn = get_db()
    resultado = [_viagem_detalhada(conn, v, hoje) for v in list_viagens_futuras(conn, hoje.isoformat())]
    conn.close()
    return jsonify(resultado)


def _criar_viagem(conn, destino, data_ida, data_volta, motivo) -> dict:
    destino = _texto_curto(destino, 80)
    ida = _data_iso_valida(data_ida)
    volta = _data_iso_valida(data_volta) if data_volta not in (None, "") else None
    if not destino or not ida:
        return {"erro": "informe o destino e a data de ida (AAAA-MM-DD)"}
    if data_volta not in (None, "") and (not volta or volta < ida):
        return {"erro": "data de volta invalida (tem que ser depois da ida)"}
    viagem_id = create_viagem(conn, destino, ida, volta, _texto_curto(motivo, 80))
    return {"ok": True, "viagem_id": viagem_id}


@app.route("/api/viagens", methods=["POST"])
def criar_viagem_rota():
    body = _corpo_json()
    conn = get_db()
    resultado = _criar_viagem(conn, body.get("destino"), body.get("data_ida"), body.get("data_volta"), body.get("motivo"))
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201


@app.route("/api/viagens/<int:viagem_id>", methods=["DELETE"])
def apagar_viagem(viagem_id):
    conn = get_db()
    delete_viagem(conn, viagem_id)
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/viagens/<int:viagem_id>/mala", methods=["POST"])
def gerar_mala_rota(viagem_id):
    conn = get_db()
    registro = conn.execute("SELECT * FROM viagens WHERE id = ?", (viagem_id,)).fetchone()
    if not registro:
        conn.close()
        return jsonify({"error": "viagem nao encontrada"}), 404
    ida = date.fromisoformat(registro["data_ida"])
    volta = date.fromisoformat(registro["data_volta"]) if registro["data_volta"] else ida
    dias = (volta - ida).days + 1
    clima_txt = _clima_texto_para(registro["destino"], registro["data_ida"])
    result, error = _call_claude(claude_client.gerar_mala, registro["destino"], dias, registro["motivo"], clima_txt)
    if error:
        conn.close()
        return error
    itens, usage = result
    itens = [i.strip()[:120] for i in itens if isinstance(i, str) and i.strip()][:20] if isinstance(itens, list) else []
    if not itens:
        conn.close()
        return jsonify({"error": CLAUDE_FORMAT_ERROR_MSG}), 502
    _log_usage(conn, usage)
    substituir_itens_viagem(conn, viagem_id, itens)
    resultado = _viagem_detalhada(conn, dict(registro), date.today())
    conn.close()
    return jsonify(resultado)


@app.route("/api/viagens/itens/<int:item_id>/alternar", methods=["POST"])
def alternar_item_viagem_rota(item_id):
    conn = get_db()
    feito = alternar_item_viagem(conn, item_id)
    conn.close()
    if feito is None:
        return jsonify({"error": "item nao encontrado"}), 404
    return jsonify({"feito": feito})


def _criar_lugar(conn, nome, cidade, tipo, nota) -> dict:
    nome = _texto_curto(nome, 80)
    if not nome:
        return {"erro": "informe o nome do lugar"}
    lugar_id = create_lugar(conn, nome, _texto_curto(cidade, 60), _texto_curto(tipo, 40), _texto_curto(nota, 300))
    return {"ok": True, "lugar_id": lugar_id}


@app.route("/api/lugares", methods=["GET"])
def lugares():
    conn = get_db()
    resultado = list_lugares(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/lugares", methods=["POST"])
def criar_lugar_rota():
    body = _corpo_json()
    conn = get_db()
    resultado = _criar_lugar(conn, body.get("nome"), body.get("cidade"), body.get("tipo"), body.get("nota"))
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201


@app.route("/api/lugares/<int:lugar_id>", methods=["DELETE"])
def apagar_lugar(lugar_id):
    conn = get_db()
    delete_lugar(conn, lugar_id)
    conn.close()
    return jsonify({"ok": True})


def _manutencoes_com_status(conn, hoje: date) -> list[dict]:
    resultado = []
    for m in list_manutencoes(conn):
        proxima = vida.proxima_data_manutencao(m["ultima_vez"], m["intervalo_meses"], m["criado_em"], hoje)
        resultado.append({**m, "proxima": proxima.isoformat(), "dias_ate": (proxima - hoje).days})
    resultado.sort(key=lambda x: x["dias_ate"])
    return resultado


def _criar_manutencao(conn, item, intervalo, ultima_vez) -> dict:
    item = _texto_curto(item, 80)
    intervalo = _inteiro_no_intervalo(intervalo, 1, 120)
    ultima = _data_iso_valida(ultima_vez) if ultima_vez not in (None, "") else None
    if not item or intervalo is None:
        return {"erro": "informe o item e o intervalo em meses (1 a 120)"}
    if ultima_vez not in (None, "") and (not ultima or ultima > date.today().isoformat()):
        return {"erro": "data da ultima vez invalida"}
    manutencao_id = create_manutencao(conn, item, intervalo, ultima)
    return {"ok": True, "manutencao_id": manutencao_id}


@app.route("/api/manutencoes", methods=["GET"])
def manutencoes():
    conn = get_db()
    resultado = _manutencoes_com_status(conn, date.today())
    conn.close()
    return jsonify(resultado)


@app.route("/api/manutencoes", methods=["POST"])
def criar_manutencao_rota():
    body = _corpo_json()
    conn = get_db()
    resultado = _criar_manutencao(conn, body.get("item"), body.get("intervalo_meses"), body.get("ultima_vez"))
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201


@app.route("/api/manutencoes/<int:manutencao_id>/feita", methods=["POST"])
def manutencao_feita(manutencao_id):
    conn = get_db()
    ok = marcar_manutencao_feita(conn, manutencao_id, date.today().isoformat())
    if ok:
        _marcar_atividade(conn)
        conn.commit()
    conn.close()
    if not ok:
        return jsonify({"error": "manutencao nao encontrada"}), 404
    return jsonify({"ok": True})


@app.route("/api/manutencoes/<int:manutencao_id>", methods=["DELETE"])
def apagar_manutencao(manutencao_id):
    conn = get_db()
    delete_manutencao(conn, manutencao_id)
    conn.close()
    return jsonify({"ok": True})


def _adicionar_compras(conn, itens) -> dict:
    if isinstance(itens, str):
        itens = [itens]
    if not isinstance(itens, list):
        return {"erro": "mande a lista de itens"}
    adicionados = []
    validos = 0
    for bruto in itens[:30]:
        item = _texto_curto(bruto, 60)
        if not item or not vida.normalizar_item_compra(item):
            continue
        validos += 1
        _, novo = adicionar_compra(conn, item)
        if novo:
            adicionados.append(vida.limpar_item_compra(item))
    if not validos:
        return {"erro": "nenhum item valido"}
    return {"ok": True, "adicionados": adicionados}


@app.route("/api/compras", methods=["GET"])
def compras():
    conn = get_db()
    resultado = list_compras_pendentes(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/compras", methods=["POST"])
def adicionar_compras_rota():
    body = _corpo_json()
    conn = get_db()
    resultado = _adicionar_compras(conn, body.get("itens", body.get("item")))
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201


@app.route("/api/compras/<int:compra_id>/comprado", methods=["POST"])
def compra_comprada(compra_id):
    conn = get_db()
    marcar_comprado(conn, compra_id)
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/compras/<int:compra_id>", methods=["DELETE"])
def apagar_compra(compra_id):
    conn = get_db()
    delete_compra(conn, compra_id)
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/responder", methods=["GET"])
def responder_pendentes():
    hoje = date.today()
    conn = get_db()
    resultado = []
    for r in list_responder_pendentes(conn):
        dias = (hoje - datetime.fromisoformat(r["criado_em"]).date()).days
        resultado.append({**r, "dias": dias})
    conn.close()
    return jsonify(resultado)


@app.route("/api/responder", methods=["POST"])
def criar_responder_rota():
    body = _corpo_json()
    quem = _texto_curto(body.get("quem"), 60)
    if not quem:
        return jsonify({"error": "informe pra quem voce precisa responder"}), 400
    conn = get_db()
    responder_id = create_responder(conn, quem, _texto_curto(body.get("sobre"), 200))
    conn.close()
    return jsonify({"ok": True, "id": responder_id}), 201


@app.route("/api/responder/<int:responder_id>/feito", methods=["POST"])
def responder_feito(responder_id):
    conn = get_db()
    marcar_respondido(conn, responder_id)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/mensagem-dificil", methods=["POST"])
def mensagem_dificil():
    body = _corpo_json()
    situacao = _texto_curto(body.get("situacao"), 1500)
    if not situacao:
        return jsonify({"error": "conte a situacao (ate 1500 caracteres)"}), 400
    para_quem = _texto_curto(body.get("para_quem"), 60)
    conn = get_db()
    result, error = _call_claude(claude_client.redigir_mensagem_dificil, situacao, para_quem)
    if error:
        conn.close()
        return error
    versoes, usage = result
    if not isinstance(versoes, dict) or not all(isinstance(versoes.get(k), str) for k in ("direta", "gentil")):
        conn.close()
        return jsonify({"error": CLAUDE_FORMAT_ERROR_MSG}), 502
    _log_usage(conn, usage)
    conn.close()
    return jsonify({"direta": versoes["direta"], "gentil": versoes["gentil"]})


def _agenda_pendente_de_hoje(conn) -> list[dict]:
    """Agenda de hoje (iCloud + tarefa com hora) sem dia inteiro e sem o que
    ja foi concluido - o que ainda pode ter horario pra cumprir. `inicio` sai
    sempre como hora local sem fuso (quem compara com datetime.now() nao quebra)."""
    resultado = []
    for e in _eventos_de_hoje_com_seguranca(conn):
        if e.get("dia_inteiro") or e.get("concluido") or not e.get("inicio"):
            continue
        try:
            inicio = datetime.fromisoformat(e["inicio"])
        except (TypeError, ValueError):
            continue
        if inicio.tzinfo is not None:
            inicio = inicio.astimezone().replace(tzinfo=None)
        resultado.append({**e, "inicio": inicio.isoformat(timespec="minutes")})
    return resultado


def _mensagem_local(conn, evento: str, lugar: str, bateria: int | None, agora: datetime) -> str | None:
    hoje = agora.date()
    if lugar == "casa" and evento == "chegou":
        proximo = next(
            (c for c in _agenda_pendente_de_hoje(conn) if datetime.fromisoformat(c["inicio"]) > agora), None
        )
        pendentes = [
            r["title"]
            for r in conn.execute(
                "SELECT title FROM tasks WHERE due_date = ? AND completed_at IS NULL ORDER BY hora", (hoje.isoformat(),)
            ).fetchall()
        ]
        return vida.mensagem_chegou_casa(agora, proximo, pendentes)
    if lugar == "casa" and evento == "saiu":
        compromissos = _agenda_pendente_de_hoje(conn)
        titulos = [c["titulo"] for c in compromissos] + [
            r["title"]
            for r in conn.execute(
                "SELECT title FROM tasks WHERE due_date = ? AND completed_at IS NULL", (hoje.isoformat(),)
            ).fetchall()
        ]
        saida_noite = obter_configuracao(conn, "saida_noite_data") == hoje.isoformat() or any(
            datetime.fromisoformat(c["inicio"]).hour >= 19 for c in compromissos
        )
        itens = vida.checklist_saida(agora, bateria, vida.eh_dia_de_academia(titulos), saida_noite)
        return "Pegou tudo? " + ", ".join(itens) + "."
    if lugar == "mercado" and evento == "chegou":
        pendentes = [c["item"] for c in list_compras_pendentes(conn)]
        if pendentes:
            return "Lista de compras: " + ", ".join(pendentes) + "."
    return None


@app.route("/api/atalho/local", methods=["POST"])
def atalho_local():
    """Automacao de localizacao do Atalhos (chegou/saiu de um lugar). Devolve
    a mensagem pro proprio Atalho mostrar - vazia quando nao ha nada a dizer
    (o Atalho so mostra notificacao se o texto nao estiver vazio). A mesma
    mensagem nao se repete em menos de 2h (geofence costuma disparar mais de
    uma vez quando o sinal oscila na porta de casa)."""
    if not _token_atalho_valido(obrigatorio=True):
        return jsonify({"error": "token invalido"}), 401
    body = _corpo_json()
    evento = body.get("evento")
    lugar = vida.normalizar_nome(body.get("lugar")) if isinstance(body.get("lugar"), str) else ""
    if evento not in ("chegou", "saiu") or not lugar:
        return jsonify({"error": "mande evento ('chegou' ou 'saiu') e lugar"}), 400
    bateria = body.get("bateria")
    # "Obter Nivel da Bateria" pode vir quebrado (47.5) ou como texto ("47")
    try:
        bateria = round(float(bateria)) if bateria not in (None, "") and not isinstance(bateria, bool) else None
    except (TypeError, ValueError, OverflowError):
        bateria = None
    bateria = _inteiro_no_intervalo(bateria, 0, 100) if bateria is not None else None

    agora = datetime.now()
    conn = get_db()
    mensagem = _mensagem_local(conn, evento, lugar, bateria, agora) or ""
    if mensagem:
        chave = f"local_{lugar}_{evento}"
        anterior = obter_configuracao(conn, chave)
        if anterior:
            try:
                dados = json.loads(anterior)
                recente = agora - datetime.fromisoformat(dados["em"]) < timedelta(hours=2)
                if recente and dados.get("texto") == mensagem:
                    mensagem = ""
            except (ValueError, KeyError, TypeError):
                pass
        if mensagem:
            definir_configuracao(conn, chave, json.dumps({"texto": mensagem, "em": agora.isoformat()}))
    conn.close()
    return jsonify({"mensagem": mensagem})


# ---- Assistente de vida (BRIEFING.md, Fase 3) ----

@app.route("/api/aprender", methods=["GET"])
def aprender():
    hoje = date.today()
    conn = get_db()
    resultado = []
    for a in list_aprender(conn):
        base = a["ultima_vez"] or a["criado_em"][:10]
        resultado.append({**a, "dias_parado": (hoje - date.fromisoformat(base)).days})
    conn.close()
    return jsonify(resultado)


def _criar_aprender(conn, tema, nota) -> dict:
    if isinstance(tema, str) and len(tema.strip()) > 80:
        return {"erro": "tema muito longo (ate 80 caracteres)"}
    tema = _texto_curto(tema, 80)
    if not tema:
        return {"erro": "informe o tema"}
    nota = nota.strip()[:300] or None if isinstance(nota, str) else None
    return {"ok": True, "id": create_aprender(conn, tema, nota)}


@app.route("/api/aprender", methods=["POST"])
def criar_aprender_rota():
    body = _corpo_json()
    conn = get_db()
    resultado = _criar_aprender(conn, body.get("tema"), body.get("nota"))
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201


@app.route("/api/aprender/<int:aprender_id>/<acao>", methods=["POST"])
def marcar_aprender_rota(aprender_id, acao):
    campo = {"retomei": "ultima_vez", "concluido": "concluido_em"}.get(acao)
    if not campo:
        return jsonify({"error": "acao invalida"}), 404
    conn = get_db()
    ok = marcar_aprender(conn, aprender_id, campo, date.today().isoformat())
    if ok:
        _marcar_atividade(conn)
        conn.commit()
    conn.close()
    if not ok:
        return jsonify({"error": "tema nao encontrado"}), 404
    return jsonify({"ok": True})


@app.route("/api/aprender/<int:aprender_id>", methods=["DELETE"])
def apagar_aprender(aprender_id):
    conn = get_db()
    delete_aprender(conn, aprender_id)
    conn.close()
    return jsonify({"ok": True})


def _salvar_link(conn, url) -> dict:
    """Valida, tenta ler a pagina e resumir. Link que nao deu pra ler fica
    salvo mesmo assim (so sem resumo) - o importante e nao perder o link."""
    try:
        url = leitura.validar_url(url)
    except leitura.LinkInvalido as e:
        return {"erro": str(e)}
    titulo, resumo, aviso = None, None, None
    try:
        pagina = leitura.extrair(leitura.baixar_pagina(url))
        titulo = pagina["titulo"]
        if len(pagina["texto"]) >= 80:
            resultado, erro = _call_claude(claude_client.resumir_link, titulo, pagina["texto"])
            if not erro and isinstance(resultado[0], str):
                resumo = resultado[0][:2000]
                _log_usage(conn, resultado[1])
    except (requests.RequestException, OSError, ValueError, LookupError):
        # LinkInvalido e ValueError; OSError cobre socket/SSL fora do requests
        aviso = "Nao consegui ler a pagina agora - o link ficou salvo."
    if resumo is None and aviso is None:
        aviso = "Salvei o link, mas nao deu pra resumir."
    salvo_id = create_salvo(conn, url, titulo, resumo)
    return {"ok": True, "id": salvo_id, "titulo": titulo, "resumo": resumo, "aviso": aviso}


@app.route("/api/salvos", methods=["GET"])
def salvos():
    conn = get_db()
    resultado = list_salvos(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/salvos", methods=["POST"])
def salvar_link_rota():
    conn = get_db()
    resultado = _salvar_link(conn, _corpo_json().get("url"))
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201


@app.route("/api/salvos/<int:salvo_id>/lido", methods=["POST"])
def salvo_lido(salvo_id):
    conn = get_db()
    ok = marcar_salvo_lido(conn, salvo_id)
    conn.close()
    if not ok:
        return jsonify({"error": "link nao encontrado"}), 404
    return jsonify({"ok": True})


@app.route("/api/salvos/<int:salvo_id>", methods=["DELETE"])
def apagar_salvo(salvo_id):
    conn = get_db()
    delete_salvo(conn, salvo_id)
    conn.close()
    return jsonify({"ok": True})


def _dias_com_rotina(conn, momento: str, inicio: date, fim: date) -> int:
    """Dias no periodo em que pelo menos metade da rotina foi marcada."""
    total = len(list_rotina_itens(conn, momento))
    if not total:
        return 0
    rows = conn.execute(
        """SELECT m.data, COUNT(*) AS n FROM rotina_marcacoes m
           JOIN rotina_itens i ON i.id = m.item_id
           WHERE i.momento = ? AND m.data BETWEEN ? AND ? GROUP BY m.data""",
        (momento, inicio.isoformat(), fim.isoformat()),
    ).fetchall()
    return sum(1 for r in rows if r["n"] * 2 >= total)


def _fatos_periodo(conn, inicio: date, fim: date) -> dict:
    ini, fim_iso = inicio.isoformat(), fim.isoformat()
    dias = (fim - inicio).days + 1
    tarefas = conn.execute(
        "SELECT COUNT(*) AS n FROM tasks WHERE date(completed_at) BETWEEN ? AND ?", (ini, fim_iso)
    ).fetchone()["n"]
    treinos = conn.execute("SELECT COUNT(*) AS n FROM treinos WHERE data BETWEEN ? AND ?", (ini, fim_iso)).fetchone()["n"]
    copos = conn.execute(
        "SELECT COUNT(*) AS n FROM hidratacao_registros WHERE data BETWEEN ? AND ?", (ini, fim_iso)
    ).fetchone()["n"]
    # sono_horas e criptografado - list_saude_dados ja descriptografa; AVG/COUNT
    # que eram feitos no SQL agora sao feitos aqui depois de ler as linhas
    # (BETWEEN ? AND ? vira desde/ate exclusivo com +1 dia, mesmo intervalo).
    _sono_valores = [
        l["sono_horas"]
        for l in list_saude_dados(conn, desde=ini, ate=(fim + timedelta(days=1)).isoformat())
        if l["sono_horas"] is not None
    ]
    sono = {"m": (sum(_sono_valores) / len(_sono_valores)) if _sono_valores else None, "n": len(_sono_valores)}
    checkins = conn.execute(
        "SELECT AVG(energia) AS e, AVG(humor) AS h, COUNT(*) AS n FROM checkins WHERE data BETWEEN ? AND ?",
        (ini, fim_iso),
    ).fetchone()
    gasto = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS t FROM expenses WHERE tipo = 'real' AND date(created_at) BETWEEN ? AND ?",
        (ini, fim_iso),
    ).fetchone()["t"]

    def rotulo(media):
        return vida.ROTULO_CHECKIN.get(round(media)) if media is not None else None

    return {
        "dias": dias,
        "tarefas_feitas": tarefas,
        "treinos": treinos,
        "treinos_por_semana": round(treinos / (dias / 7), 1) if dias >= 7 else treinos,
        "rotina_manha_dias": _dias_com_rotina(conn, "manha", inicio, fim),
        "rotina_noite_dias": _dias_com_rotina(conn, "noite", inicio, fim),
        "copos_por_dia": round(copos / dias, 1),
        "sono_medio": round(sono["m"], 1) if sono["n"] else None,
        "checkins": checkins["n"],
        "energia_media": rotulo(checkins["e"]),
        "humor_medio": rotulo(checkins["h"]),
        "gasto_total": round(gasto, 2),
    }


@app.route("/api/progresso", methods=["GET"])
def progresso():
    dias = min(max(request.args.get("dias", default=30, type=int), 7), 90)
    hoje = date.today()
    conn = get_db()
    fatos = _fatos_periodo(conn, hoje - timedelta(days=dias - 1), hoje)
    metas_lista = [
        {"titulo": g["titulo"], "pct": min(100, round(100 * g["valor_guardado"] / g["valor_alvo"])) if g["valor_alvo"] else 0}
        for g in list_goals(conn)
    ]
    conn.close()
    return jsonify({**fatos, "metas": metas_lista})


def _texto_revisao(mes_nome: str, fatos: dict) -> str:
    partes = [f"{fatos['tarefas_feitas']} tarefa(s) feita(s)"]
    if fatos["treinos"]:
        partes.append(f"{fatos['treinos']} treino(s)")
    if fatos["rotina_manha_dias"]:
        partes.append(f"rotina da manha em {fatos['rotina_manha_dias']} dia(s)")
    if fatos["sono_medio"] is not None:
        partes.append(f"sono medio de {fatos['sono_medio']}h")
    if fatos["humor_medio"]:
        partes.append(f"humor mais pra '{fatos['humor_medio']}'")
    if fatos["gasto_total"]:
        partes.append(f"R$ {fatos['gasto_total']:.2f} de gasto anotado")
    return f"{mes_nome.capitalize()} fechou: " + ", ".join(partes) + "."


def _revisao_do_mes(conn, primeiro: date, ultimo: date) -> dict:
    fatos = _fatos_periodo(conn, primeiro, ultimo)
    nome = vida.NOMES_MES[primeiro.month - 1]
    return {"mes": primeiro.strftime("%Y-%m"), "nome": nome, **fatos, "texto": _texto_revisao(nome, fatos)}


@app.route("/api/revisao-mensal", methods=["GET"])
def revisao_mensal():
    mes = request.args.get("mes")
    if mes:
        try:
            primeiro = date.fromisoformat(f"{mes}-01")
            if not 2000 <= primeiro.year <= 2100:
                raise ValueError
        except ValueError:
            return jsonify({"error": "mes deve ser AAAA-MM"}), 400
        proximo = date(primeiro.year + (primeiro.month == 12), primeiro.month % 12 + 1, 1)
        ultimo = proximo - timedelta(days=1)
    else:
        primeiro, ultimo = vida.mes_anterior(date.today())
    conn = get_db()
    resultado = _revisao_do_mes(conn, primeiro, ultimo)
    conn.close()
    return jsonify(resultado)


@app.route("/api/atalho/app", methods=["POST"])
def atalho_app():
    """Automacao 'App abriu/fechou' do Atalhos (uma por app) - o Screen Time
    nao e legivel pelo Atalhos, entao o tempo de uso e aproximado por aqui."""
    if not _token_atalho_valido(obrigatorio=True):
        return jsonify({"error": "token invalido"}), 401
    body = _corpo_json()
    nome = _texto_curto(body.get("app"), 40)
    evento = body.get("evento")
    if not nome or evento not in ("abriu", "fechou"):
        return jsonify({"error": "mande app e evento ('abriu' ou 'fechou')"}), 400
    conn = get_db()
    registrar_evento_app(conn, nome, evento, datetime.now().isoformat(timespec="seconds"))
    conn.close()
    return jsonify({"ok": True})


def _uso_apps(conn, dias: int) -> dict:
    desde = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")
    minutos = vida.uso_de_apps(list_eventos_app(conn, desde))
    return {
        "dias": dias,
        "apps": [{"app": a, "minutos": m, "texto": vida.formatar_minutos(m)} for a, m in minutos.items()],
        "total_minutos": sum(minutos.values()),
    }


@app.route("/api/uso-apps", methods=["GET"])
def uso_apps():
    dias = min(max(request.args.get("dias", default=7, type=int), 1), 30)
    conn = get_db()
    resultado = _uso_apps(conn, dias)
    conn.close()
    return jsonify(resultado)


@app.route("/api/uso/total", methods=["GET"])
def uso_total():
    conn = get_db()
    total = total_cost_usd(conn)
    conn.close()
    return jsonify({"custo_usd": round(total, 4)})


def _categorizar_transacoes_importadas(conn, transacoes: list[dict]) -> list[dict]:
    """Decide a categoria de cada transacao importada sozinho, com base no
    historico de gastos que voce ja categorizou manualmente - sem perguntar
    uma por uma. So marca 'categoria' quando o padrao e claro (ver
    gastos.sugerir_categoria); senao fica sem, pronta pra voce corrigir/
    completar depois se quiser."""
    historico = conn.execute(
        "SELECT category, description, source_text FROM expenses "
        "WHERE tipo = 'real' AND category IS NOT NULL"
    ).fetchall()
    historico = [dict(r) for r in historico]
    for t in transacoes:
        t["categoria"] = gastos.sugerir_categoria(t.get("descricao", ""), historico)
    return transacoes


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
    transacoes = _categorizar_transacoes_importadas(conn, transacoes)
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
    # saldo/valor sao criptografados em repouso - list_bank_accounts e
    # estatisticas_conta ja descriptografam e somam em Python (ver db.py).
    contas = list_bank_accounts(conn)
    resultado = []
    for c in contas:
        stats = estatisticas_conta(conn, c["id"])
        resultado.append(
            {
                **c,
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
    transacoes = list_bank_transactions(conn, conta_id, limite=100)
    conn.close()
    return jsonify(transacoes)


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
            "criptografia_ativa": criptografia.configurada(),
        }
    )


@app.route("/api/seguranca/status", methods=["GET"])
def seguranca_status():
    """Rota de diagnostico: diz se a criptografia em repouso (Open Finance +
    saude) esta ligada agora. Ver docs/SEGURANCA.md. Sem ENCRYPTION_KEY
    configurada, o app segue funcionando normalmente (decisao de design
    documentada) mas os campos sensiveis ficam em texto plano no banco -
    esta rota existe pra isso nunca ficar escondido, so silencioso no log."""
    ativa = criptografia.configurada()
    return jsonify(
        {
            "criptografia_ativa": ativa,
            "aviso": (
                None
                if ativa
                else (
                    "ENCRYPTION_KEY nao configurada - dado do Open Finance e de saude esta "
                    "em texto plano no banco. Rode python scripts/gerar_chave_criptografia.py."
                )
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

    item_id = _corpo_json().get("item_id")
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
        saldo_pluggy = conta_pluggy.get("balance")
        if saldo_pluggy is not None:
            atualizar_saldo_conta(conn, conta_id, saldo_pluggy)
        try:
            transacoes_pluggy = pluggy_client.get_transactions(conta_pluggy["id"])
        except requests.RequestException:
            conn.close()
            return jsonify({"error": "nao consegui buscar as transacoes na Pluggy agora"}), 502
        transacoes = pluggy_client.normalizar_transacoes(transacoes_pluggy)
        transacoes = _categorizar_transacoes_importadas(conn, transacoes)
        novas = insert_bank_transactions(conn, conta_id, transacoes)
        resumo.append({"conta_id": conta_id, "tipo": tipo, "novas": novas})
    conn.close()

    return jsonify({"banco": banco, "contas": resumo})


@app.route("/api/metas", methods=["GET"])
def metas():
    hoje = date.today()
    conn = get_db()
    resultado = []
    for g in list_goals(conn):
        meta = _calculo_meta(g)
        meta["previsao"] = vida.previsao_meta(
            g["valor_alvo"], g["valor_guardado"], list_goal_deposits(conn, g["id"]), hoje
        )
        resultado.append(meta)
    conn.close()
    return jsonify(resultado)


@app.route("/api/metas/<int:goal_id>/guardar", methods=["POST"])
def guardar_meta(goal_id):
    valor = _corpo_json().get("valor")
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or valor <= 0:
        return jsonify({"error": "informe um valor positivo"}), 400

    conn = get_db()
    goal = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    if not goal:
        conn.close()
        return jsonify({"error": "meta nao encontrada"}), 404
    add_to_goal(conn, goal_id, valor)
    goal = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify(_calculo_meta(dict(goal)))


@app.route("/api/metas/<int:goal_id>/historico", methods=["GET"])
def meta_historico(goal_id):
    conn = get_db()
    goal = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    if not goal:
        conn.close()
        return jsonify({"error": "meta nao encontrada"}), 404
    depositos = list_goal_deposits(conn, goal_id)
    conn.close()

    acumulado = 0.0
    pontos = [{"data": goal["criado_em"][:10], "acumulado": 0.0}]
    for d in depositos:
        acumulado += d["valor"]
        pontos.append({"data": d["criado_em"][:10], "acumulado": round(acumulado, 2)})
    return jsonify({"pontos": pontos, "valor_alvo": goal["valor_alvo"]})


@app.route("/api/construtora/resumo", methods=["GET"])
def construtora_resumo():
    base_url = os.environ.get("CONSTRUTORA_API_URL")
    api_key = os.environ.get("CONSTRUTORA_API_KEY")
    if not base_url or not api_key:
        return jsonify({"configurado": False})

    dados = _buscar_resumo_construtora()
    if dados is None:
        return jsonify({"configurado": True, "erro": "Nao consegui falar com a API da construtora agora."}), 502

    dados_contas = _buscar_contas_a_vencer_construtora(dias=30)
    contas = dados_contas.get("contas") if dados_contas and dados_contas.get("status") == "ok" else None

    return jsonify({"configurado": True, "dados": dados, "contas": contas})


TAMANHO_MAX_PDF_BYTES = 15 * 1024 * 1024  # 15MB - cabe folgado num orcamento escaneado


@app.route("/api/cotacoes", methods=["GET"])
def listar_cotacoes():
    conn = get_db()
    resultado = list_cotacoes(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/cotacoes", methods=["POST"])
def criar_cotacao_rota():
    titulo = (_corpo_json().get("titulo") or "").strip()
    if not titulo:
        return jsonify({"error": "informe o titulo da cotacao"}), 400
    conn = get_db()
    cotacao_id = criar_cotacao(conn, titulo)
    conn.close()
    return jsonify({"id": cotacao_id, "ok": True}), 201


@app.route("/api/cotacoes/<int:cotacao_id>", methods=["GET"])
def ver_cotacao(cotacao_id):
    conn = get_db()
    cotacao = get_cotacao(conn, cotacao_id)
    if not cotacao:
        conn.close()
        return jsonify({"error": "cotacao nao encontrada"}), 404
    itens = list_itens_cotacao(conn, cotacao_id)
    conn.close()
    return jsonify({**cotacao, "itens": itens})


@app.route("/api/cotacoes/<int:cotacao_id>", methods=["DELETE"])
def apagar_cotacao(cotacao_id):
    conn = get_db()
    delete_cotacao(conn, cotacao_id)
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/cotacoes/<int:cotacao_id>/itens", methods=["POST"])
def adicionar_item_cotacao(cotacao_id):
    conn = get_db()
    if not get_cotacao(conn, cotacao_id):
        conn.close()
        return jsonify({"error": "cotacao nao encontrada"}), 404

    body = _corpo_json()
    fornecedor = (body.get("fornecedor") or "").strip() or None
    valor = body.get("valor")
    if valor is not None and not isinstance(valor, (int, float)):
        conn.close()
        return jsonify({"error": "valor precisa ser um numero"}), 400

    item_id = criar_item_cotacao(
        conn,
        cotacao_id,
        fornecedor,
        valor,
        (body.get("prazo_texto") or "").strip() or None,
        (body.get("observacao") or "").strip() or None,
        origem="texto",
    )
    conn.close()
    return jsonify({"id": item_id, "ok": True}), 201


@app.route("/api/cotacoes/<int:cotacao_id>/itens/pdf", methods=["POST"])
def adicionar_item_cotacao_pdf(cotacao_id):
    """Le um PDF de orcamento de fornecedor e extrai fornecedor/valor/prazo
    automaticamente - o Alex so anexa o PDF que recebeu, sem digitar nada."""
    conn = get_db()
    if not get_cotacao(conn, cotacao_id):
        conn.close()
        return jsonify({"error": "cotacao nao encontrada"}), 404

    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename:
        conn.close()
        return jsonify({"error": "anexe um arquivo PDF"}), 400
    if not arquivo.filename.lower().endswith(".pdf"):
        conn.close()
        return jsonify({"error": "so aceito arquivo PDF"}), 400

    pdf_bytes = arquivo.read()
    if len(pdf_bytes) > TAMANHO_MAX_PDF_BYTES:
        conn.close()
        return jsonify({"error": "PDF maior que 15MB - manda um arquivo menor"}), 400

    result, error = _call_claude(claude_client.extrair_item_cotacao_pdf, pdf_bytes)
    if error:
        conn.close()
        return error
    dados, usage = result

    _log_usage(conn, usage)
    item_id = criar_item_cotacao(
        conn,
        cotacao_id,
        dados.get("fornecedor"),
        dados.get("valor"),
        dados.get("prazo_texto"),
        dados.get("observacao"),
        origem="pdf",
    )
    conn.commit()
    conn.close()
    return jsonify({"id": item_id, "ok": True, **dados}), 201


@app.route("/api/cotacoes/<int:cotacao_id>/itens/<int:item_id>", methods=["DELETE"])
def apagar_item_cotacao(cotacao_id, item_id):
    conn = get_db()
    delete_item_cotacao(conn, item_id)
    conn.close()
    return jsonify({"ok": True})


TAMANHO_MAX_IMAGEM_BYTES = 10 * 1024 * 1024  # 10MB - foto de celular cabe folgado


@app.route("/api/notas-fiscais/extrair", methods=["POST"])
def extrair_nota_fiscal():
    """Recebe a foto de uma nota fiscal (base64, nao multipart - de proposito:
    o corpo em JSON e o mesmo formato que /api/capture ja usa, entao a fila
    offline (fila-offline.js, generica pra qualquer url/method/headers/body)
    consegue reenfileirar essa chamada sem precisar de nenhum tratamento
    especial pra FormData/Blob quando a foto e tirada sem internet) e extrai
    valor/estabelecimento/data via claude_client (API de visao da Anthropic -
    decisao ja tomada com o Alex, sem OCR local). So extrai: NUNCA grava o
    gasto direto, porque a leitura por IA pode errar o valor - a confirmacao
    e o fluxo de registro ficam com /api/notas-fiscais/confirmar (US-C9)."""
    body = _corpo_json()
    imagem_b64 = body.get("imagem_base64")
    media_type = (body.get("media_type") or "").strip().lower()
    if not imagem_b64 or not isinstance(imagem_b64, str):
        return jsonify({"error": "anexe uma foto da nota fiscal"}), 400
    if media_type not in claude_client.MEDIA_TYPES_IMAGEM_VALIDOS:
        return jsonify({"error": "formato de imagem nao suportado (use jpeg, png, webp ou heic)"}), 400

    try:
        image_bytes = base64.b64decode(imagem_b64, validate=True)
    except (binascii.Error, ValueError):
        return jsonify({"error": "imagem invalida (base64 malformado)"}), 400
    if not image_bytes:
        return jsonify({"error": "imagem vazia"}), 400
    if len(image_bytes) > TAMANHO_MAX_IMAGEM_BYTES:
        return jsonify({"error": "foto maior que 10MB - manda uma foto menor"}), 400

    result, error = _call_claude(claude_client.extrair_nota_fiscal_foto, image_bytes, media_type)
    if error:
        return error
    dados, usage = result

    conn = get_db()
    # Registra o custo na tabela generica ja existente (api_usage/_log_usage,
    # a fonte de verdade atual de custo de IA neste projeto). Se a US-A5 (Grupo A,
    # tabela uso_api_ia dedicada por endpoint/feature) ja estiver integrada quando
    # este codigo for revisado, vale mover/duplicar esse registro pra la tambem -
    # documentado aqui em vez de assumir uma tabela que pode nao existir ainda
    # neste branch (agentes rodando em paralelo, ver tasks/fase5).
    _log_usage(conn, usage)
    conn.commit()
    conn.close()
    return jsonify(dados), 200


@app.route("/api/notas-fiscais/confirmar", methods=["POST"])
def confirmar_nota_fiscal():
    """Segundo passo do fluxo (US-C9): recebe o valor/estabelecimento/data
    que o Alex CONFIRMOU na tela (pode ter editado o que a IA leu errado -
    nunca salva o que veio de /extrair sem passar por aqui) e vira um gasto
    de verdade, com a MESMA sugestao automatica de categoria ja usada pro
    extrato bancario (gastos.sugerir_categoria, historico de gastos
    categorizados manualmente - nao um classificador novo e paralelo)."""
    body = _corpo_json()
    valor = body.get("valor")
    estabelecimento = _texto_seguro(body.get("estabelecimento")).strip()
    data_compra = _texto_seguro(body.get("data")).strip() or None
    categoria_informada = _texto_seguro(body.get("categoria")).strip() or None

    if not isinstance(valor, (int, float)) or isinstance(valor, bool) or valor <= 0:
        return jsonify({"error": "informe um valor valido (maior que zero)"}), 400
    if not estabelecimento:
        return jsonify({"error": "informe o estabelecimento"}), 400
    if data_compra:
        try:
            date.fromisoformat(data_compra)
        except ValueError:
            return jsonify({"error": "data invalida (use AAAA-MM-DD)"}), 400

    conn = get_db()
    categoria = categoria_informada
    if not categoria:
        historico = conn.execute(
            "SELECT category, description, source_text FROM expenses "
            "WHERE tipo = 'real' AND category IS NOT NULL"
        ).fetchall()
        categoria = gastos.sugerir_categoria(estabelecimento, [dict(r) for r in historico]) or "outros"

    created_at = f"{data_compra} 12:00:00" if data_compra else None
    if created_at:
        cur = conn.execute(
            "INSERT INTO expenses (amount, category, description, source_text, tipo, created_at) "
            "VALUES (?, ?, ?, ?, 'real', ?)",
            (valor, categoria, estabelecimento, f"Nota fiscal (foto): {estabelecimento}", created_at),
        )
    else:
        cur = conn.execute(
            "INSERT INTO expenses (amount, category, description, source_text, tipo) "
            "VALUES (?, ?, ?, ?, 'real')",
            (valor, categoria, estabelecimento, f"Nota fiscal (foto): {estabelecimento}"),
        )
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"id": cur.lastrowid, "ok": True, "categoria": categoria}), 201


def _token_atalho_valido(obrigatorio: bool = False) -> bool:
    """Mesma logica do SAUDE_WEBHOOK_TOKEN: se PAINEL_ATALHOS_TOKEN nao
    estiver configurado, a rota fica aberta (uso local); se estiver, o
    Atalho do iPhone precisa mandar o header X-Webhook-Token batendo.
    `obrigatorio`: rota que DEVOLVE dado pessoal (agenda, lista de compras)
    ou grava rastro de uso - sem token configurado, so aceita quem ja esta
    logado no painel (nunca fica aberta pra qualquer um que ache a URL)."""
    token_esperado = os.environ.get("PAINEL_ATALHOS_TOKEN")
    if not token_esperado:
        return not obrigatorio or bool(session.get("autenticado"))
    enviado = request.headers.get("X-Webhook-Token") or ""
    return hmac.compare_digest(enviado.encode(), token_esperado.encode())


@app.route("/api/atalho/capturar", methods=["POST"])
def atalho_capturar():
    """Pro Atalho "Ei Siri, anota" do iPhone - mesma logica de /api/capture,
    so que autenticado por token em vez de sessao de login (o app Atalhos
    nao guarda cookie entre execucoes)."""
    if not _token_atalho_valido():
        return jsonify({"error": "token invalido"}), 401

    body = _corpo_json()
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "texto vazio"}), 400
    return _executar_captura(text, "")


@app.route("/api/atalho/cotacao-pdf", methods=["POST"])
def atalho_cotacao_pdf():
    """Pro Atalho "Compartilhar PDF" do iPhone - aparece no menu de
    Compartilhar do iOS quando o Alex ta vendo o PDF de um orcamento
    (ex: recebido no WhatsApp). Recebe o PDF + o titulo da cotacao (o Alex
    fala/digita, ex: "portas") e acha ou cria a cotacao sozinho - assim nao
    precisa saber o ID numerico dela."""
    if not _token_atalho_valido():
        return jsonify({"error": "token invalido"}), 401

    titulo_cotacao = (request.form.get("titulo_cotacao") or "").strip()
    if not titulo_cotacao:
        return jsonify({"error": "informe o titulo da cotacao (ex: portas)"}), 400

    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename:
        return jsonify({"error": "anexe um arquivo PDF"}), 400
    if not arquivo.filename.lower().endswith(".pdf"):
        return jsonify({"error": "so aceito arquivo PDF"}), 400

    pdf_bytes = arquivo.read()
    if len(pdf_bytes) > TAMANHO_MAX_PDF_BYTES:
        return jsonify({"error": "PDF maior que 15MB - manda um arquivo menor"}), 400

    result, error = _call_claude(claude_client.extrair_item_cotacao_pdf, pdf_bytes)
    if error:
        return error
    dados, usage = result

    conn = get_db()
    _log_usage(conn, usage)
    cotacao_id = _resolver_cotacao_por_titulo(conn, titulo_cotacao)
    item_id = criar_item_cotacao(
        conn,
        cotacao_id,
        dados.get("fornecedor"),
        dados.get("valor"),
        dados.get("prazo_texto"),
        dados.get("observacao"),
        origem="pdf",
    )
    conn.commit()
    conn.close()
    return jsonify({"id": item_id, "cotacao_id": cotacao_id, "ok": True, **dados}), 201


@app.route("/api/atalho/resumo", methods=["GET"])
def atalho_resumo():
    """Resumo compacto pra widget externo (ex: Scriptable no iPhone) -
    autenticado por token, sem sessao, e sem chamar a IA (so leitura direta
    do banco) pra ficar rapido o bastante pra um widget de tela inicial."""
    if not _token_atalho_valido():
        return jsonify({"error": "token invalido"}), 401

    conn = get_db()
    hoje = date.today().isoformat()
    tarefas_pendentes = conn.execute(
        "SELECT COUNT(*) AS n FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL"
    ).fetchone()["n"]
    gasto_hoje = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE date(created_at) = ? AND tipo = 'real'",
        (hoje,),
    ).fetchone()["total"]

    eventos = _eventos_de_hoje_com_seguranca(conn)
    agora = datetime.now()
    proximo = next(
        (
            e
            for e in eventos
            if not e.get("dia_inteiro") and datetime.fromisoformat(e["inicio"]) >= agora
        ),
        None,
    )
    conn.close()

    return jsonify(
        {
            "tarefas_pendentes": tarefas_pendentes,
            "gasto_hoje": gasto_hoje,
            "proximo_titulo": proximo["titulo"] if proximo else None,
            "proximo_hora": proximo["inicio"][11:16] if proximo else None,
        }
    )


@app.route("/api/configuracoes/silencio", methods=["GET"])
def obter_silencio():
    conn = get_db()
    inicio = obter_configuracao(conn, "silencio_inicio") or "22:00"
    fim = obter_configuracao(conn, "silencio_fim") or "07:00"
    conn.close()
    return jsonify({"inicio": inicio, "fim": fim})


@app.route("/api/configuracoes/silencio", methods=["POST"])
def definir_silencio():
    corpo = _corpo_json()
    inicio = _normalizar_hora(corpo.get("inicio"))
    fim = _normalizar_hora(corpo.get("fim"))
    if not inicio or not fim:
        return jsonify({"error": "horario invalido - use HH:MM"}), 400
    conn = get_db()
    definir_configuracao(conn, "silencio_inicio", inicio)
    definir_configuracao(conn, "silencio_fim", fim)
    conn.close()
    return jsonify({"ok": True, "inicio": inicio, "fim": fim})


@app.route("/api/aprendizado", methods=["GET"])
def aprendizado_status():
    """Transparencia do que o painel aprendeu do seu historico - pra nunca
    virar caixa preta: mostra o limiar em uso hoje pra cada tipo de
    cutucada, se veio do padrao ou foi aprendido, quantas amostras
    embasaram isso, e o quanto (em media) voce demora pra resolver depois
    de ser cutucado."""
    conn = get_db()
    # titulo/quem vazio nao bate com nenhum historico especifico (nenhum
    # token pra comparar), entao cai direto no caminho global - o mesmo
    # limiar_tarefa/limiar_espera usados de verdade em cada cobranca, so que
    # aqui mostrando o valor "base" (sem o ajuste fino por titulo/quem
    # especifico de uma tarefa em particular).
    dias_tarefa, info_tarefa = aprendizado.limiar_tarefa(conn, "")
    dias_espera, info_espera = aprendizado.limiar_espera(conn, "")
    conn.close()
    return jsonify(
        {
            "tarefa_parada": {"dias_atual": dias_tarefa, **info_tarefa},
            "espera_parada": {"dias_atual": dias_espera, **info_espera},
        }
    )


@app.route("/api/push/status", methods=["GET"])
def push_status():
    return jsonify({"configurado": push_client.configurado(), "public_key": push_client.public_key()})


@app.route("/api/push/inscrever", methods=["POST"])
def push_inscrever():
    subscription = _corpo_json()
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
        # 5 min pra tarefa-com-horario (ver notificacoes.tarefas_com_horario_chegando)
        # virar push perto da hora certa - as outras checagens (atrasada, meta, gasto,
        # lembrete) sao lentas por natureza e nao se importam com a checagem ser mais
        # frequente, o dedup em notificacoes_enviadas ja evita reenvio.
        scheduler.add_job(verificar_e_notificar, "interval", minutes=5)
        # backup semanal (domingo 3h da manha - baixo uso), ver
        # rodar_backup_automatico_semanal pro que ele faz
        scheduler.add_job(rodar_backup_automatico_semanal, "cron", day_of_week="sun", hour=3, minute=0)
        scheduler.start()


if __name__ == "__main__":
    iniciar_scheduler()
    iniciar_telegram()
    app.run(debug=True, port=5001)
