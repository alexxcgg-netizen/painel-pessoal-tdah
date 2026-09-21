import hashlib
import json
import os
from datetime import date, datetime, timedelta

import anthropic
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session

load_dotenv()

import agenda
import auth
import bank_ofx
import caldav_client
import claude_client
import clima
import estudo
import gastos
import maps_client
import metar
import notificacoes
import pluggy_client
import push_client
import streak
import uber_client
import viagem
import voos as voos_module
from db import (
    CAMPOS_SAUDE,
    add_to_goal,
    atualizar_uber_pedido,
    cotacao_por_titulo_aproximado,
    create_goal,
    create_lembrete,
    create_memoria,
    create_voo,
    criar_cotacao,
    criar_item_cotacao,
    criar_uber_pedido,
    definir_configuracao,
    delete_cotacao,
    delete_item_cotacao,
    delete_lembrete,
    delete_memoria,
    delete_push_subscription,
    delete_voo,
    get_cotacao,
    get_db,
    get_or_create_bank_account,
    get_saude_dia,
    init_db,
    insert_bank_transactions,
    ja_notificou_hoje,
    list_chat_mensagens,
    list_cotacoes,
    list_dias_ativos,
    list_goal_deposits,
    list_goals,
    list_itens_cotacao,
    list_lembretes,
    list_memorias,
    list_push_subscriptions,
    list_voos,
    marcar_notificado,
    media_passos_ultimos_dias,
    obter_configuracao,
    record_usage,
    registrar_atividade,
    salvar_mensagem_chat,
    save_push_subscription,
    total_cost_usd,
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
    # Integracao maquina-a-maquina (Atalho do iPhone) - cada uma tem o proprio
    # token (SAUDE_WEBHOOK_TOKEN / PAINEL_ATALHOS_TOKEN) checado dentro da
    # rota, nao usa sessao de login (o iPhone nao guarda cookie de sessao
    # entre execucoes do Atalho).
    if path in (
        "/api/saude/importar",
        "/api/atalho/capturar",
        "/api/atalho/cotacao-pdf",
        "/api/atalho/resumo",
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

        corpo = request.json or {}
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

        corpo = request.json or {}
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


def _executar_captura(text: str, clarificacao: str):
    """Classifica e grava um texto de captura (tarefa/gasto/meta) - usado
    tanto por /api/capture (sessao normal) quanto por /api/atalho/capturar
    (Atalho do iPhone, autenticado por token). Devolve (jsonify(...), status)."""
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
        return jsonify({"duvida": parsed["duvida"], "texto_original": text}), 200

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

    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify(parsed), 201


@app.route("/api/capture", methods=["POST"])
def capture():
    body = request.json or {}
    text = body.get("text", "").strip()
    clarificacao = body.get("clarificacao", "").strip()
    if not text:
        return jsonify({"error": "texto vazio"}), 400
    return _executar_captura(text, clarificacao)


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


@app.route("/api/expenses", methods=["GET"])
def list_expenses():
    conn = get_db()
    rows = conn.execute("SELECT * FROM expenses ORDER BY created_at DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/expenses/historico", methods=["GET"])
def expenses_historico():
    dias = request.args.get("dias", default=14, type=int)
    dias = min(max(dias, 1), 90)
    conn = get_db()
    rows = conn.execute("SELECT amount, created_at FROM expenses WHERE tipo = 'real'").fetchall()
    conn.close()
    historico = gastos.historico_diario([dict(r) for r in rows], dias, date.today())
    return jsonify(historico)


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


def _buscar_resumo_construtora() -> dict | None:
    """Busca o resumo financeiro na API da construtora - None se nao configurado ou
    se a chamada falhar por qualquer motivo (nunca quebra quem chamar)."""
    base_url = os.environ.get("CONSTRUTORA_API_URL")
    api_key = os.environ.get("CONSTRUTORA_API_KEY")
    if not base_url or not api_key:
        return None
    try:
        resp = requests.get(f"{base_url}/api/resumo", headers={"X-API-Key": api_key}, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


def _buscar_contas_a_vencer_construtora(dias: int = 30) -> dict | None:
    """Busca as contas a pagar a vencer/vencidas na API da construtora - None se nao
    configurado ou se a chamada falhar por qualquer motivo (nunca quebra quem chamar)."""
    base_url = os.environ.get("CONSTRUTORA_API_URL")
    api_key = os.environ.get("CONSTRUTORA_API_KEY")
    if not base_url or not api_key:
        return None
    try:
        resp = requests.get(
            f"{base_url}/api/contas_a_vencer",
            headers={"X-API-Key": api_key},
            params={"dias": dias},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


def _id_estavel_conta(conta: dict) -> int:
    """ID estavel (mesmos dados -> mesmo numero) pra dar pra `notificacoes_enviadas`
    deduplicar - a API externa da construtora nao expoe o id real da linha no banco dela
    (decisao deles: 'so o essencial'), entao deriva um a partir dos campos que a
    identificam. Muda se a conta for editada do lado da construtora, o que so faz a
    notificacao repetir, nunca sumir - comportamento seguro."""
    chave = f"{conta.get('vencimento')}|{conta.get('valor')}|{conta.get('fornecedor')}|{conta.get('descricao')}"
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


def _tarefas_com_horario_hoje(conn) -> list[dict]:
    """Tarefas pendentes com horario marcado pra hoje, no mesmo formato dos
    eventos do iCloud - pra virarem ancoras de horario fixo junto com eles."""
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


@app.route("/api/summary/today", methods=["GET"])
def summary_today():
    today = date.today().isoformat()
    conn = get_db()
    done = conn.execute("SELECT title FROM tasks WHERE date(completed_at) = ?", (today,)).fetchall()
    pending = conn.execute("SELECT title FROM tasks WHERE completed_at IS NULL").fetchall()
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
        "SELECT title FROM tasks WHERE completed_at IS NULL "
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
    configurado = caldav_client.configurado()
    erro = None
    icloud_eventos = []
    if configurado:
        try:
            icloud_eventos = caldav_client.eventos_do_dia(date.today())
        except Exception:
            erro = "Nao consegui falar com o iCloud agora."
    eventos = _compromissos_de_hoje(conn, icloud_eventos)
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
                resultado["sugestao_dia"] = agenda.sugerir_dia_menos_corrido(carga, dias)
        return resultado

    def exec_registrar_gasto(entrada):
        status_gasto = entrada.get("status") if entrada.get("status") in ("real", "planejado") else "real"
        conn.execute(
            "INSERT INTO expenses (amount, category, description, source_text, tipo) VALUES (?, ?, ?, ?, ?)",
            (entrada["valor"], entrada.get("categoria") or "outros", entrada["titulo"], texto, status_gasto),
        )
        conn.commit()
        return {"ok": True}

    def exec_registrar_meta(entrada):
        create_goal(conn, entrada["titulo"], entrada["valor"], entrada.get("prazo"))
        return {"ok": True}

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

    def exec_registrar_memoria(entrada):
        create_memoria(conn, entrada["fato"], texto)
        return {"ok": True}

    def exec_registrar_voo(entrada):
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
        "registrar_meta": exec_registrar_meta,
        "gerar_plano_do_dia": exec_gerar_plano,
        "registrar_lembrete": exec_registrar_lembrete,
        "registrar_memoria": exec_registrar_memoria,
        "registrar_voo": exec_registrar_voo,
        "sugerir_horario_livre": exec_sugerir_horario_livre,
        "calcular_gasto_viagem": exec_calcular_gasto_viagem,
        "sugerir_posto_no_caminho": exec_sugerir_posto_no_caminho,
        "agendar_uber": exec_agendar_uber,
        "sugerir_tema_estudo": exec_sugerir_tema_estudo,
        "registrar_item_cotacao": exec_registrar_item_cotacao,
        "comparar_cotacao": exec_comparar_cotacao,
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
    _marcar_atividade(conn)
    conn.close()
    return jsonify({"resposta": resposta, "acoes": acoes})


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

    for tarefa_id, msg in notificacoes.tarefas_com_horario_chegando(conn):
        if not ja_notificou_hoje(conn, "tarefa_horario", tarefa_id):
            avisos.append(("tarefa_horario", tarefa_id, "Lembrete", msg))

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
        avisos.append(
            (
                "hora_de_dormir",
                0,
                "Hora de desacelerar",
                "22h - comeca a desacelerar pro sono.",
            )
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

    enviados = 0
    for tipo, ref_id, titulo, corpo in avisos:
        for s in subs:
            sub_dict = json.loads(s["subscription_json"])
            ok = push_client.enviar(sub_dict, titulo, corpo)
            if not ok:
                delete_push_subscription(conn, s["endpoint"])
        marcar_notificado(conn, tipo, ref_id)
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
                    for s in subs:
                        sub_dict = json.loads(s["subscription_json"])
                        push_client.enviar(
                            sub_dict,
                            "Hora do Uber",
                            f"Uber pra {atualizado['destino']}: {atualizado['preco_texto']}. "
                            "Abre o painel pra confirmar.",
                        )
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


@app.route("/api/lembretes", methods=["POST"])
def criar_lembrete():
    body = request.json or {}
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
    body = request.json or {}
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

    try:
        resp = requests.get(
            f"{base_url}/api/resumo", headers={"X-API-Key": api_key}, timeout=5
        )
        resp.raise_for_status()
    except requests.RequestException:
        return jsonify({"configurado": True, "erro": "Nao consegui falar com a API da construtora agora."}), 502

    dados_contas = _buscar_contas_a_vencer_construtora(dias=30)
    contas = dados_contas.get("contas") if dados_contas and dados_contas.get("status") == "ok" else None

    return jsonify({"configurado": True, "dados": resp.json(), "contas": contas})


TAMANHO_MAX_PDF_BYTES = 15 * 1024 * 1024  # 15MB - cabe folgado num orcamento escaneado


@app.route("/api/cotacoes", methods=["GET"])
def listar_cotacoes():
    conn = get_db()
    resultado = list_cotacoes(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/cotacoes", methods=["POST"])
def criar_cotacao_rota():
    titulo = ((request.json or {}).get("titulo") or "").strip()
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

    body = request.json or {}
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


def _token_atalho_valido() -> bool:
    """Mesma logica do SAUDE_WEBHOOK_TOKEN: se PAINEL_ATALHOS_TOKEN nao
    estiver configurado, a rota fica aberta (uso local); se estiver, o
    Atalho do iPhone precisa mandar o header X-Webhook-Token batendo."""
    token_esperado = os.environ.get("PAINEL_ATALHOS_TOKEN")
    if not token_esperado:
        return True
    return request.headers.get("X-Webhook-Token") == token_esperado


@app.route("/api/atalho/capturar", methods=["POST"])
def atalho_capturar():
    """Pro Atalho "Ei Siri, anota" do iPhone - mesma logica de /api/capture,
    so que autenticado por token em vez de sessao de login (o app Atalhos
    nao guarda cookie entre execucoes)."""
    if not _token_atalho_valido():
        return jsonify({"error": "token invalido"}), 401

    body = request.json or {}
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
        "SELECT COUNT(*) AS n FROM tasks WHERE completed_at IS NULL"
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
        # 5 min pra tarefa-com-horario (ver notificacoes.tarefas_com_horario_chegando)
        # virar push perto da hora certa - as outras checagens (atrasada, meta, gasto,
        # lembrete) sao lentas por natureza e nao se importam com a checagem ser mais
        # frequente, o dedup em notificacoes_enviadas ja evita reenvio.
        scheduler.add_job(verificar_e_notificar, "interval", minutes=5)
        scheduler.start()


if __name__ == "__main__":
    iniciar_scheduler()
    app.run(debug=True, port=5001)
