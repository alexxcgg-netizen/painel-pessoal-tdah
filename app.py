import base64
import binascii
import csv
import hashlib
import hmac
import io
import json
import math
import os
import re
import sqlite3
import tempfile
import threading
import time
import zipfile
from datetime import date, datetime, timedelta

import anthropic
import requests
from dotenv import load_dotenv
from flask import Flask, Response, has_request_context, jsonify, redirect, render_template, request, send_file, session
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

import agenda
import aprendizado
import auth
import caldav_client
import calculos
import cards
import claude_client
import classificador_local
import clima
import construtora_cliente
import criptografia
import estudo
import gastos
import geocode_nominatim
import leitura
import maps_client
import metar
import noticias
import notificacoes
import pluggy_client
import push_client
import rotas
import streak
import telegram_bot
import telegram_captura
import uber_client
import viagem
import vida
import voo_status
import voos as voos_module
import db
import ia.core
import ia.historico
import ia.teto
from assistente import avisos as avisos_assistente
from db import (
    CAMPOS_SAUDE,
    cards_de_mensagem_chat,
    CATEGORIAS_MEMORIA,
    add_to_goal,
    adicionar_compra,
    adicionar_etapa_projeto,
    ajustar_saldo_conta,
    alternar_habito_dia,
    alternar_ideia_presente_comprada,
    alternar_item_viagem,
    alternar_rotina_item,
    apagar_brain_dump,
    apagar_diario_decisao,
    apagar_espera,
    apagar_etapa_projeto,
    apagar_nota,
    atualizar_categoria_gasto,
    atualizar_saldo_conta,
    atualizar_uber_pedido,
    buscar_conta_por_nome,
    buscar_habito_por_nome,
    buscar_notas,
    buscar_projeto_por_nome,
    complete_task,
    concluir_etapa_projeto,
    conta_paga,
    contar_hidratacao_dia,
    cotacao_por_titulo_aproximado,
    create_aprender,
    create_brain_dump,
    create_conta_pessoal,
    create_decisao,
    create_diario_decisao,
    create_espera,
    create_garantia,
    create_goal,
    create_habito,
    create_ideia_presente,
    create_income,
    create_lembrete,
    create_lugar,
    create_manutencao,
    create_medicamento,
    create_medida_corporal,
    create_memoria,
    create_nota,
    create_pessoa,
    create_projeto,
    create_responder,
    create_rotina_item,
    create_salvo,
    create_viagem,
    create_voo,
    criar_cotacao,
    criar_gasto_de_brain_dump,
    criar_item_cotacao,
    criar_tarefa_de_brain_dump,
    criar_uber_pedido,
    definir_apelido_gasto,
    definir_configuracao,
    definir_esforco_tarefa,
    definir_limite_conta,
    definir_numero_voo_viagem,
    definir_orcamento,
    definir_status_projeto,
    definir_teto_mensal_ia,
    delete_aprender,
    delete_compra,
    delete_conta_pessoal,
    delete_cotacao,
    delete_ficha_treino,
    delete_garantia,
    delete_habito,
    delete_ideia_presente,
    delete_item_cotacao,
    delete_lembrete,
    delete_lugar,
    delete_manutencao,
    delete_medicamento,
    delete_medida_corporal,
    delete_memoria,
    delete_pessoa,
    delete_projeto,
    delete_push_subscription,
    delete_rotina_item,
    delete_salvo,
    delete_viagem,
    delete_voo,
    descriptografar_linhas_export,
    esquecer_evento_criado,
    espera_pendente_por_quem_aproximado,
    evento_criado_pelo_painel,
    gasto_mes_conta,
    gasto_mes_por_categoria,
    get_checkin,
    get_cotacao,
    get_db,
    get_essencial,
    get_habito,
    get_projeto,
    estatisticas_conta,
    get_manutencao,
    get_or_create_bank_account,
    get_saude_dia,
    habito_marcado,
    init_db,
    insert_bank_transactions,
    km_atual_veiculo,
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
    list_brain_dump_pendentes,
    list_cotacoes,
    list_decisoes,
    list_diario_decisoes,
    list_dias_ativos,
    list_esperas_pendentes,
    list_etapas_projeto,
    list_eventos_app,
    list_eventos_criados,
    list_fichas_treino,
    list_garantias,
    list_goal_deposits,
    list_goals,
    list_habitos,
    list_ideias_presente,
    list_incomes,
    list_itens_cotacao,
    list_itens_viagem,
    list_lembretes,
    list_lugares,
    lugares_sem_geocode,
    proximo_lugar_para_geocodificar,
    list_manutencoes,
    list_medicamentos_ativos,
    list_medidas_corporais,
    list_memorias,
    list_notas,
    list_orcamentos,
    list_pessoas,
    list_projetos,
    list_push_subscriptions,
    list_responder_pendentes,
    list_rotina_itens,
    list_salvos,
    list_treinos,
    list_viagens_futuras,
    list_voos,
    marcacoes_habito_no_periodo,
    marcar_aprender,
    marcar_brain_dump_processado,
    marcar_comprado,
    marcar_conta_paga,
    marcar_espera_importante,
    marcar_garantia_notificada,
    marcar_manutencao_feita,
    marcar_notificado,
    marcar_ou_criar_feito,
    marcar_respondido,
    marcar_salvo_lido,
    media_passos_ultimos_dias,
    obter_brain_dump,
    obter_configuracao,
    obter_resumo_dia_cache,
    obter_status_voo_cache,
    reclassificar_gasto_para_tarefa,
    reclassificar_tarefa_para_gasto,
    record_usage,
    registrar_atividade,
    registrar_conversa,
    registrar_correcao_classificacao,
    registrar_evento_app,
    registrar_evento_criado,
    registrar_hidratacao,
    registrar_interacao_aprendizado,
    registrar_resultado_diario_decisao,
    registrar_treino,
    resolver_espera,
    responder_assinatura,
    respostas_assinaturas,
    resumo_custo_api,
    rotina_marcadas,
    salvar_checkin,
    salvar_essencial,
    salvar_ficha_treino,
    salvar_geocode_lugar,
    salvar_mensagem_chat,
    salvar_resumo_dia_cache,
    salvar_status_voo_cache,
    save_push_subscription,
    substituir_itens_viagem,
    total_cost_usd,
    total_gastos_bancarios_mes,
    total_gastos_mes,
    total_incomes_mes,
    uber_pedido,
    uber_pedidos_aguardando_confirmacao,
    uber_pedidos_para_disparar,
    update_memoria,
    upsert_saude_dia,
)

app = Flask(__name__)
init_db()


def _aplicar_pin_inicial(conn, pin_inicial: str | None) -> bool:
    """PAINEL_PIN_INICIAL (hospedagem tipo Render, sem terminal pra rodar
    scripts/resetar_pin.py): sem isso, quem abrir a URL nova primeiro escolhe
    o PIN. So age se ainda nao houver PIN - nunca sobrescreve um existente.
    PIN invalido derruba o boot de proposito: subir com /configurar-pin
    aberto seria pior que nao subir."""
    if not pin_inicial or auth.pin_configurado(conn):
        return False
    try:
        auth.definir_pin(conn, pin_inicial, pin_inicial)
    except ValueError as e:
        raise RuntimeError(f"PAINEL_PIN_INICIAL invalido: {e}") from e
    conn.commit()
    return True


def _exigir_pin_em_hospedagem_publica(conn, environ) -> None:
    """Revisao da Fase 6 (achado 11): no Render (que define RENDER sozinho em
    todo servico) a URL e publica desde o primeiro segundo - subir sem PIN
    deixaria /configurar-pin aberto pra quem chegar primeiro. Mesma
    filosofia do PIN inicial invalido: melhor nao subir do que subir aberto.
    (O plano gratis do Render zera o SQLite a cada deploy, entao na pratica
    PAINEL_PIN_INICIAL e obrigatorio la.)"""
    if environ.get("RENDER") and not auth.pin_configurado(conn):
        raise RuntimeError(
            "Hospedado no Render sem PIN configurado: defina PAINEL_PIN_INICIAL (6 digitos) nas "
            "variaveis de ambiente do servico - sem isso /configurar-pin ficaria aberto pra quem "
            "abrir a URL primeiro. Ver deploy/RENDER.md."
        )


_conn_inicial = get_db()
app.secret_key = auth.obter_ou_criar_secret_key(_conn_inicial)
_aplicar_pin_inicial(_conn_inicial, os.environ.get("PAINEL_PIN_INICIAL"))
_exigir_pin_em_hospedagem_publica(_conn_inicial, os.environ)
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


def _configurar_proxy(wsgi_app, environ):
    """Revisao da Fase 6 (achado 7): atras de proxy reverso (Render, Caddy na
    VPS), request.remote_addr e o IP do PROXY - 5 PINs errados de qualquer
    pessoa trancavam o Alex tambem. ProxyFix (1 salto) passa a usar o IP que
    o proxy anotou em X-Forwarded-For. SO liga com PAINEL_ATRAS_DE_PROXY
    explicito: sem proxy na frente, confiar nesse cabecalho deixaria qualquer
    um inventar um IP novo a cada tentativa e fugir do bloqueio."""
    if (environ.get("PAINEL_ATRAS_DE_PROXY") or "").strip().lower() in ("1", "true", "t", "yes", "sim"):
        return ProxyFix(wsgi_app, x_for=1, x_proto=1)
    return wsgi_app


app.wsgi_app = _configurar_proxy(app.wsgi_app, os.environ)

# Revisao da Fase 6 (achado 4): teto do corpo de qualquer requisicao. Os
# maiores envios legitimos sao a foto de nota fiscal em base64 dentro do JSON
# (TAMANHO_MAX_IMAGEM_BYTES = 10MB de imagem ~ 13,4MB em base64) e o PDF de
# cotacao em multipart (TAMANHO_MAX_PDF_BYTES = 15MB) - 20MB cobre os dois
# com folga; acima disso o Flask corta com 413 antes de ler o corpo.
TAMANHO_MAX_REQUISICAO_BYTES = 20 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = TAMANHO_MAX_REQUISICAO_BYTES

# Texto livre que vai pra IA (chat, brain dump, Telegram) - 4000 caracteres
# e mais que qualquer despejo real e segura custo/abuso por mensagem.
TAMANHO_MAX_TEXTO_CHAT = 4000
MSG_TEXTO_LONGO = (
    f"mensagem longa demais (maximo {TAMANHO_MAX_TEXTO_CHAT} caracteres) - divide em partes menores"
)
TETO_IA_MSG = (
    "teto mensal de gasto com IA estourado - tente de novo mes que vem ou ajuste o teto no card financeiro"
)


@app.errorhandler(413)
def _corpo_grande_demais(_erro):
    return jsonify({"error": "envio grande demais (maximo 20MB por vez) - manda um arquivo menor"}), 413

CLAUDE_ERROR_MSG = "Erro ao falar com a IA. Tenta de novo em instantes."
CLAUDE_FORMAT_ERROR_MSG = "A IA respondeu em um formato inesperado. Tenta de novo."


def _log_usage(conn, usage: dict, feature: str = "outro"):
    record_usage(
        conn, usage["model"], usage["input_tokens"], usage["output_tokens"], usage["cost_usd"], feature
    )


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


# Serializa checar-o-teto -> chamar a IA -> gravar o gasto (US-A6) nos dois
# pontos que respeitam o teto mensal (_classificar_intent e
# extrair_nota_fiscal) - sem isso, duas requisicoes concorrentes podiam
# ambas ler "abaixo do teto" antes de qualquer uma logar o custo (TOCTOU,
# achado na revisao de seguranca da Fase 5). App de usuario unico, entao o
# lock nunca fica sob disputa real - so fecha a janela teorica.
_TETO_IA_LOCK = threading.Lock()


def _teto_ia_estourado(funcao: str = "chat") -> bool:
    """Fase 7 (C1): teto UNICO de IA pra todo o app - ia.teto.teto_permite
    (R$40/mes por padrao, ou o teto configurado no card financeiro), sobre o
    gasto do mes de ia.medicao.gasto_mes_atual (fonte unica: cada chamada
    conta uma vez). Substitui o teto antigo (resumo_custo_api, so api_usage e
    so quando configurado). Erro no calculo bloqueia (mesma regra do ia.core)."""
    try:
        return not ia.teto.teto_permite(funcao)
    except Exception:  # noqa: BLE001
        app.logger.exception("teto de IA: falha ao consultar (bloqueando por seguranca)")
        return True


def _call_claude(fn, *args):
    """Chama uma funcao do claude_client e traduz falhas em uma resposta de erro pronta pra devolver.

    Fase 7 (C1): as funcoes migradas pro ia.core levantam excecoes dedicadas
    (todas subclasses de ValueError) - teto estourado vira TETO_IA_MSG (402),
    rede/provedor vira CLAUDE_ERROR_MSG (502) e so JSON/schema ruim continua
    CLAUDE_FORMAT_ERROR_MSG (502)."""
    try:
        return fn(*args), None
    except ia.core.TetoEstourado:
        return None, (jsonify({"error": TETO_IA_MSG}), 402)
    except ia.core.ErroProvedor:
        return None, (jsonify({"error": CLAUDE_ERROR_MSG}), 502)
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
        "/api/atalho/comando-voz",
    ):
        return None
    # Fase 7: rota maquina-a-maquina declarada por um blueprint de rotas/
    # (ROTAS_COM_TOKEN / PREFIXOS_COM_TOKEN) - a propria rota checa o token.
    if rotas.rota_com_token(path):
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


def _modo_visitante_ativo() -> bool:
    """Fase 5 (US-C19): mecanismo generico que outras rotas (US-C20) chamam
    pra decidir se mandam o dado real ou um estado neutro. Estado fica so na
    sessao do Flask (cookie assinado pelo servidor, nunca no banco) - nao
    precisa sobreviver a reinicio do processo nem ser visto por outra sessao/
    aparelho, e some sozinho no logout (session.clear() acima)."""
    return bool(session.get("modo_visitante"))


def _recusar_no_modo_visitante():
    """Revisao da Fase 6: rota que ESCREVE algo com efeito fora da tela
    (desfazer, memoria que entra no prompt da IA, padrao aprendido do
    classificador, agenda do iCloud, conversao do brain dump) nunca roda no
    modo visitante - devolve a resposta 403 pronta, ou None pra seguir."""
    if _modo_visitante_ativo():
        return jsonify({"error": "indisponivel no modo visitante"}), 403
    return None


@app.route("/api/modo-visitante", methods=["GET"])
def modo_visitante_rota():
    return jsonify({"ativo": _modo_visitante_ativo()})


@app.route("/api/modo-visitante", methods=["POST"])
def alternar_modo_visitante_rota():
    """Ativar e livre (1 toque, pra dar tempo de esconder a tela antes de
    passar o celular pra alguem). Desativar exige o PIN de verdade - senao
    quem ja esta com o celular desbloqueado (a propria pessoa de quem voce
    esta escondendo o dado) conseguiria desligar sozinha so cutucando um
    botao."""
    body = _corpo_json()
    if bool(body.get("ativar")):
        session["modo_visitante"] = True
        return jsonify({"ativo": True})

    ip = request.remote_addr or "desconhecido"
    conn = get_db()
    try:
        pode_tentar, msg_bloqueio = auth.verificar_bloqueio(conn, ip)
        if not pode_tentar:
            return jsonify({"error": msg_bloqueio}), 429
        pin_ok = auth.verificar_pin(conn, body.get("pin"))
        auth.registrar_tentativa(conn, ip, sucesso=pin_ok)
    finally:
        conn.close()
    if not pin_ok:
        return jsonify({"error": "PIN incorreto"}), 403
    session["modo_visitante"] = False
    return jsonify({"ativo": False})


def _modo_teste_ia_ativo(conn) -> bool:
    """Config persistida (tabela `configuracoes`, nao sessao - ao contrario
    do modo visitante): o Alex liga antes de testar o visual no celular pelo
    Render e o estado continua ligado entre sessoes/logins ate ele desligar
    de volta. So essa pessoa ve o toggle (fica dentro do login por PIN, igual
    o resto do app - nao ha usuario nenhum alem dela)."""
    return (obter_configuracao(conn, "modo_teste_ia") or "0") == "1"


@app.route("/api/configuracoes/teste-ia", methods=["GET"])
def obter_teste_ia():
    conn = get_db()
    try:
        return jsonify({"ativo": _modo_teste_ia_ativo(conn)})
    finally:
        conn.close()


@app.route("/api/configuracoes/teste-ia", methods=["POST"])
def definir_teste_ia():
    body = _corpo_json()
    ativo = bool(body.get("ativo"))
    conn = get_db()
    try:
        definir_configuracao(conn, "modo_teste_ia", "1" if ativo else "0")
    finally:
        conn.close()
    return jsonify({"ativo": ativo})


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
    return jsonify(_resposta_contrato(json.loads(row["response_json"]))), row["status"]


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

    # Fase 7 (Etapa 0): regra local (classificador_local/regras/) resolve sem
    # IA - casou e executou, a resposta e so o envelope de cards da regra.
    local = classificador_local.casar(text)
    if local:
        conn = get_db()
        envelope_local = classificador_local.executar(conn, local, _criar_token_desfazer(conn))
        if envelope_local is not None:
            corpo = {"acao": local["acao"], "regra_local": local["regra"]}
            corpo.update(envelope_local)
            if client_id:
                _gravar_resposta_capture(conn, client_id, corpo, 201)
            _marcar_atividade(conn)
            conn.commit()
            conn.close()
            return jsonify(_resposta_contrato(corpo)), 201
        conn.close()

    inicio_captura = time.perf_counter()

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

    _log_usage(conn, usage, "captura")

    # Se a IA ainda ficou em duvida, so pede esclarecimento uma vez (quando a
    # clarificacao ja foi enviada, seguimos com o melhor palpite mesmo assim).
    ms_classificar = int(round((time.perf_counter() - inicio_captura) * 1000))
    passo_classificar = {"modulo": "Captura", "descricao": "Classificou o texto", "ms": ms_classificar}

    if parsed.get("duvida") and not clarificacao:
        corpo = {"duvida": parsed["duvida"], "texto_original": text}
        # contrato de cards (docs/CARDS.md): duvida nao cria nada - sem card,
        # a pergunta vai no resumo_texto.
        corpo.update(cards.envelope([], parsed["duvida"], [passo_classificar]))
        if client_id:
            _gravar_resposta_capture(conn, client_id, corpo, 200)
        conn.commit()
        conn.close()
        return jsonify(_resposta_contrato(corpo)), 200

    inicio_gravar = time.perf_counter()
    if parsed["tipo"] == "gasto":
        status_gasto = parsed.get("status") if parsed.get("status") in ("real", "planejado") else "real"
        cur = conn.execute(
            "INSERT INTO expenses (amount, category, description, source_text, tipo) VALUES (?, ?, ?, ?, ?)",
            (parsed["valor"], parsed.get("categoria") or "outros", parsed["titulo"], full_text, status_gasto),
        )
        efeito = {"entidade": "gasto", "id": cur.lastrowid}
        passo_gravar = {"modulo": "Finanças", "descricao": f'Registrou o gasto "{parsed["titulo"]}"'}
        resumo_texto = "Gasto registrado."
    elif parsed["tipo"] == "meta":
        goal_id = create_goal(conn, parsed["titulo"], parsed["valor"], parsed.get("prazo"))
        efeito = {"entidade": "meta", "id": goal_id}
        passo_gravar = {"modulo": "Metas", "descricao": f'Criou a meta "{parsed["titulo"]}"'}
        resumo_texto = "Meta criada."
    else:
        cur = conn.execute(
            "INSERT INTO tasks (title, due_at, due_date, hora, source_text) VALUES (?, ?, ?, ?, ?)",
            (parsed["titulo"], parsed.get("quando"), parsed.get("quando_data"), _normalizar_hora(parsed.get("hora")), full_text),
        )
        efeito = {"entidade": "tarefa", "id": cur.lastrowid}
        passo_gravar = {"modulo": "Tarefas", "descricao": f'Criou a tarefa "{parsed["titulo"]}"'}
        resumo_texto = "Tarefa criada."
    passo_gravar["ms"] = int(round((time.perf_counter() - inicio_gravar) * 1000))

    if parsed.get("memoria"):
        create_memoria(conn, parsed["memoria"], full_text)

    # Contrato de cards (Fase 6, docs/CARDS.md) - ADITIVO: os campos da
    # classificacao (tipo/titulo/valor/...) continuam no topo do JSON pro
    # frontend antigo e pro Atalho do iPhone que ja leem esse formato.
    corpo = dict(parsed)
    corpo.update(
        cards.montar_resposta(
            conn, [efeito], resumo_texto, [passo_classificar, passo_gravar], _criar_token_desfazer(conn)
        )
    )

    if client_id:
        _gravar_resposta_capture(conn, client_id, corpo, 201)

    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify(_resposta_contrato(corpo)), 201


@app.route("/api/capture", methods=["POST"])
def capture():
    body = _corpo_json()
    text = _texto_seguro(body.get("text"))
    clarificacao = _texto_seguro(body.get("clarificacao"))
    client_id = _texto_seguro(body.get("client_id"))[:64]  # UUID cabe sobra; so um teto de sanidade
    if not text:
        return jsonify({"error": "texto vazio"}), 400
    return _executar_captura(text, clarificacao, client_id)


# Lista fechada de acoes do classificador de intent (Fase 5, ver docs/INTENT.md).
# Contrato estavel: um valor novo so pode ser ADICIONADO aqui, nunca renomeado/removido,
# senao quebra quem ja integrou contra o formato (Grupo B - navegacao por voz). Fonte
# unica: claude_client.ACOES_INTENT (US-A2) - so um alias aqui pra nao quebrar quem ja
# importava app.ACOES_INTENT (ex: testes da US-A1).
ACOES_INTENT = claude_client.ACOES_INTENT


def _classificar_intent(conn, texto: str, somente_local: bool = False):
    """Fonte unica da logica de classificacao de intent (contrato em
    docs/INTENT.md) - usada tanto por /api/intent/classificar (sessao,
    navegacao por voz no navegador, US-B1) quanto por /api/atalho/comando-voz
    (token, Atalho/Siri, US-B4). NUNCA duplicar essa logica num dos dois
    lugares - qualquer regra nova de classificacao nasce aqui.

    Antes de chamar a IA (US-A2, Haiku), tenta resolver localmente por
    padrao aprendido (US-A3, aprendizado.padrao_intent_confiavel) - so cai
    pra API se nao achar um padrao confiavel o bastante. Se o teto mensal de
    gasto com IA (US-A6, db.obter_teto_mensal_ia) ja estourou, NAO cai pra
    API mesmo sem padrao - fica so no que o padrao aprendido resolver, ate o
    mes virar (documentado no card financeiro, /api/ia/custo).

    Devolve (resultado_dict, None) no caminho feliz, ou (None, erro) onde
    `erro` e a tupla (jsonify(...), status) ja pronta pra devolver - o
    caller decide se repassa esse erro cru (US-B1) ou traduz numa fala curta
    (US-B4).

    Fase 6 (US-E7): entre o padrao aprendido e a IA entra o banco "pergunta
    -> onde buscar" (aprendizado.consulta_conhecida) - consulta de formato
    conhecido resolve local, sem API. `somente_local=True` (usado pelo chat,
    que ja tem a propria IA com tool-use depois) para aqui e devolve
    (None, None) quando nenhuma camada local resolveu - nunca chama a API.

    Fase 7 (Etapa 0): a PRIMEIRA camada e classificador_local (regras por
    arquivo em classificador_local/regras/) - so classifica aqui, com o
    campo aditivo "regra_local"; quem executa e chat/captura."""
    local = classificador_local.casar(texto)
    if local:
        return {
            "acao": local["acao"],
            "confianca": local["confianca"],
            "parametros": local["parametros"],
            "precisa_confirmacao": local["precisa_confirmacao"],
            "regra_local": local["regra"],
        }, None

    padrao = aprendizado.padrao_intent_confiavel(conn, texto)
    conhecida = aprendizado.consulta_conhecida(texto)
    if padrao:
        parametros = padrao["parametros"]
        # padrao "consultar" gravado sem dizer onde buscar (ex: pela IA de
        # voz, {"pergunta": ...}) ganha as fontes da regra conhecida - mesma
        # acao, parametro mais util; qualquer outra acao aprendida (inclusive
        # correcao manual do Alex) vale como esta.
        if (
            padrao["acao"] == "consultar"
            and conhecida
            and conhecida["acao"] == "consultar"
            and not aprendizado.fontes_validas(parametros)
        ):
            parametros = {**(parametros if isinstance(parametros, dict) else {}), **conhecida["parametros"]}
        return {
            "acao": padrao["acao"],
            "confianca": aprendizado.CONFIANCA_PADRAO_INTENT,
            "parametros": parametros,
            "precisa_confirmacao": False,
        }, None

    if conhecida:
        return {
            "acao": conhecida["acao"],
            "confianca": aprendizado.CONFIANCA_PADRAO_INTENT,
            "parametros": conhecida["parametros"],
            "precisa_confirmacao": False,
        }, None

    if somente_local:
        return None, None

    with _TETO_IA_LOCK:
        if _teto_ia_estourado("classify_intent"):
            return {
                "acao": "desconhecido",
                "confianca": 0.0,
                "parametros": {},
                "precisa_confirmacao": True,
                "teto_ia_estourado": True,
            }, None

        result, error = _call_claude(claude_client.classify_intent, texto)
        if error:
            return None, error
        resultado, usage = result

        _log_usage(conn, usage, "intent")
    # So reforca o padrao com classificacoes em que a propria IA confiou -
    # nao vale a pena aprender de algo que ja veio com precisa_confirmacao.
    if not resultado["precisa_confirmacao"]:
        aprendizado.confirmar_padrao_intent(conn, texto, resultado["acao"], resultado["parametros"])
    return resultado, None


@app.route("/api/intent/classificar", methods=["POST"])
def intent_classificar():
    """Classifica um comando de voz/texto numa acao (contrato em
    docs/INTENT.md) - ver _classificar_intent pra logica de verdade."""
    body = _corpo_json()
    texto = _texto_seguro(body.get("texto"))
    if not texto:
        return jsonify({"error": "texto vazio"}), 400

    conn = get_db()
    resultado, error = _classificar_intent(conn, texto)
    if error:
        conn.close()
        return error
    conn.commit()
    conn.close()
    return jsonify(resultado)


@app.route("/api/intent/corrigir", methods=["POST"])
def intent_corrigir():
    """US-B3: quando o dialogo de voz de 2 turnos (UI, voz-comando.js) tem uma
    correcao confirmada pelo Alex pro texto original, isso alimenta o mesmo
    banco de padroes aprendidos do resto do intent (US-A3/US-A4) - reusa
    aprendizado.confirmar_padrao_intent com forcar_confianca_alta=True (mesmo
    espirito de uma correcao manual de captura, US-A4): uma correcao vale
    como sinal forte na hora, sem precisar repetir o erro 3x.

    Modo visitante: 403 (revisao da Fase 6) - um padrao aprendido muda como
    o chat responde depois (envenenamento do banco local)."""
    recusa = _recusar_no_modo_visitante()
    if recusa:
        return recusa
    body = _corpo_json()
    texto = _texto_seguro(body.get("texto"))
    acao_correta = body.get("acao_correta")
    parametros = body.get("parametros")
    if not isinstance(parametros, dict):
        parametros = {}

    if not texto:
        return jsonify({"error": "texto vazio"}), 400
    if acao_correta not in ACOES_INTENT:
        return jsonify({"error": "acao_correta invalida"}), 400

    conn = get_db()
    aprendizado.confirmar_padrao_intent(conn, texto, acao_correta, parametros, forcar_confianca_alta=True)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/tasks", methods=["GET"])
def list_tasks():
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


@app.route("/api/tasks", methods=["POST"])
def criar_tarefa_direta():
    """Fase 6 (US-F10): formulario direto na aba Tarefas, sem passar pela
    classificacao por IA (essa ja existe via chat/captura, /api/capture e
    registrar_tarefa) - so titulo + prazo OPCIONAL. Reusa o mesmo insert
    minimo de criar_tarefa_de_brain_dump (Fase 5, US-C6) em vez de duplicar
    o INSERT numa terceira funcao."""
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


@app.route("/api/tasks/<int:task_id>/complete", methods=["POST"])
def complete_task_rota(task_id):
    conn = get_db()
    complete_task(conn, task_id)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/tasks/<int:task_id>/reabrir", methods=["POST"])
def reabrir_task_rota(task_id):
    """Fase 6 (US-E3): desmarcar o checkbox de uma tarefa no card
    tarefas_criadas volta ela pra pendente (o par do /complete)."""
    conn = get_db()
    ok = db.reabrir_tarefa(conn, task_id)
    conn.close()
    if not ok:
        return jsonify({"error": "tarefa nao encontrada"}), 404
    return jsonify({"ok": True})


@app.route("/api/tasks/<int:task_id>/esforco", methods=["POST"])
def definir_esforco_tarefa_rota(task_id):
    """Fase 5 (US-C7)."""
    body = _corpo_json()
    esforco = body.get("esforco")
    if esforco not in vida.NIVEIS_ENERGIA:
        return jsonify({"error": "esforco precisa ser baixa, media ou alta"}), 400
    conn = get_db()
    ok = definir_esforco_tarefa(conn, task_id, esforco)
    conn.close()
    if not ok:
        return jsonify({"error": "tarefa nao encontrada"}), 404
    return jsonify({"ok": True, "esforco": esforco})


@app.route("/api/tarefas/sugestao-energia", methods=["GET"])
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
    if _modo_visitante_ativo():
        return jsonify([])
    conn = get_db()
    rows = conn.execute("SELECT * FROM expenses ORDER BY created_at DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/incomes", methods=["GET"])
def list_incomes_rota():
    if _modo_visitante_ativo():
        return jsonify([])
    conn = get_db()
    rows = list_incomes(conn, limit=50)
    conn.close()
    return jsonify(rows)


@app.route("/api/orcamentos", methods=["GET"])
def list_orcamentos_rota():
    if _modo_visitante_ativo():
        return jsonify([])
    conn = get_db()
    orcamentos = list_orcamentos(conn)
    ano_mes = date.today().strftime("%Y-%m")
    for o in orcamentos:
        o["gasto_mes"] = gasto_mes_por_categoria(conn, o["categoria"], ano_mes)
    conn.close()
    return jsonify(orcamentos)


@app.route("/api/gastos-fixos", methods=["GET"])
def gastos_fixos_rota():
    if _modo_visitante_ativo():
        return jsonify([])
    conn = get_db()
    resultado = _gastos_fixos(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/sobra-do-mes", methods=["GET"])
def sobra_do_mes_rota():
    if _modo_visitante_ativo():
        hoje = date.today()
        return jsonify(
            {**gastos.sobra_do_mes(0, 0, 0), "projecao": vida.projecao_fim_do_mes(0, 0, 0, hoje)}
        )
    conn = get_db()
    resultado = _sobra_do_mes(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/expenses/historico", methods=["GET"])
def expenses_historico():
    if _modo_visitante_ativo():
        return jsonify([])
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
    if _modo_visitante_ativo():
        return jsonify({"error": "desative o modo visitante pra exportar dados"}), 403
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
    if _modo_visitante_ativo():
        return jsonify({"error": "desative o modo visitante pra exportar dados"}), 403
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
    if _modo_visitante_ativo():
        return jsonify({"error": "desative o modo visitante pra exportar dados"}), 403
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
    if _modo_visitante_ativo():
        return jsonify({"error": "desative o modo visitante pra exportar dados"}), 403
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
    if _modo_visitante_ativo():
        return jsonify(gastos.resumo_semanal([], date.today()))
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


# Fase 7 (C1): toda leitura da construtora passa por construtora_cliente.py
# (faixa A10, contrato em docs/contrato-api-construtora.md) - cache/throttle de
# 60s, timeout de 5s, nunca levanta, modo mock (CONSTRUTORA_API_MOCK=1). A
# instancia e a padrao do modulo (mesmo cache de gastos_do_mes/proxima_conta),
# buscada a cada uso (se alguem trocar a instancia padrao, o app acompanha).
def _cliente_construtora() -> "construtora_cliente.ClienteConstrutora":
    return construtora_cliente.cliente_padrao()


class _CacheConstrutoraCompat:
    """Testes antigos fazem app._CACHE_CONSTRUTORA.clear() entre casos -
    continua valendo: limpa o cache do cliente padrao."""

    def clear(self) -> None:
        construtora_cliente.limpar_cache_padrao()


_CACHE_CONSTRUTORA = _CacheConstrutoraCompat()

# O que o painel pessoal pode mostrar da construtora (decisao do Alex, A10):
# so gastos, entradas e o tempo ate a proxima conta. Nunca lucro, margem nem
# VGV - esses campos sao descartados aqui, logo na entrada.
CAMPOS_RESUMO_CONSTRUTORA_PERMITIDOS = ("status", "tot_entradas", "tot_saidas")
CAMPOS_CONTA_CONSTRUTORA_PERMITIDOS = ("vencimento", "valor", "fornecedor", "descricao", "dias_ate_vencer")


def _filtrar_resumo_construtora(dados) -> dict | None:
    if not isinstance(dados, dict):
        return None
    return {k: dados[k] for k in CAMPOS_RESUMO_CONSTRUTORA_PERMITIDOS if k in dados}


def _filtrar_contas_construtora(dados) -> dict | None:
    """Mantem o envelope {"status", "contas"} e so os campos permitidos de
    cada conta; conta malformada (sem dias_ate_vencer numerico) sai da lista
    - melhor nao mostrar do que quebrar quem ordena/compara por dias."""
    if not isinstance(dados, dict):
        return None
    contas = []
    for conta in dados.get("contas") or []:
        if not isinstance(conta, dict):
            continue
        dias = conta.get("dias_ate_vencer")
        if isinstance(dias, bool) or not isinstance(dias, (int, float)):
            continue
        contas.append({k: conta.get(k) for k in CAMPOS_CONTA_CONSTRUTORA_PERMITIDOS})
    return {"status": dados.get("status"), "contas": contas}


def _buscar_resumo_construtora() -> dict | None:
    """Resumo da construtora ja filtrado (so status/tot_entradas/tot_saidas) -
    None se nao configurado ou se a chamada falhar. Via construtora_cliente."""
    return _filtrar_resumo_construtora(_cliente_construtora().resumo())


def _buscar_contas_a_vencer_construtora(dias: int = 30) -> dict | None:
    """Contas a pagar a vencer/vencidas da construtora - None se nao
    configurado ou se a chamada falhar. Via construtora_cliente (cache por
    `dias`)."""
    return _filtrar_contas_construtora(_cliente_construtora().contas_a_vencer(dias=dias))


def _quando_conta_construtora(dias_ate: int, passado: str = "vencida ha") -> str:
    if dias_ate < 0:
        return f"{passado} {abs(int(dias_ate))} dia(s)"
    if dias_ate == 0:
        return "vence hoje"
    return f"vence em {int(dias_ate)} dia(s)"


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


def _id_estavel_teto_ia(nivel: str, ano_mes: str) -> int:
    """Mesma ideia de _id_estavel_orcamento (US-A6) - uma vez por nivel+mes."""
    chave = f"teto_ia|{nivel}|{ano_mes}"
    digest = hashlib.sha1(chave.encode("utf-8")).digest()[:8]
    return int.from_bytes(digest, "big") % (2**62)


def _construtora_contexto_contas() -> str | None:
    """Frase factual sobre a proxima conta a pagar da construtora (vencendo ou ja
    vencida) pro resumo do dia / chat - so nome e tempo ate vencer (Fase 7 C1:
    decisao do Alex, A10 - valor de conta nunca vai de bandeja)."""
    dados = _buscar_contas_a_vencer_construtora(dias=30)
    if not dados or dados.get("status") != "ok":
        return None
    contas = dados.get("contas") or []
    if not contas:
        return None
    proxima = contas[0]
    quando = _quando_conta_construtora(proxima["dias_ate_vencer"])
    quem = proxima.get("fornecedor") or proxima.get("descricao") or "fornecedor nao informado"
    extra = f", mais {len(contas) - 1} outra(s) conta(s) em aberto" if len(contas) > 1 else ""
    return f"proxima conta a pagar da construtora: {quem}, {quando}{extra}"


def _construtora_contexto_resumo() -> str | None:
    """Frase factual pro resumo do dia / chat - so gastos (saidas), entradas e
    tempo ate a proxima conta, que ja vieram prontos da API da construtora
    (nenhuma conta feita aqui nem pela IA; nunca lucro, margem nem VGV)."""
    dados = _buscar_resumo_construtora()
    if not dados or dados.get("status") != "ok":
        return None
    entradas, saidas = dados.get("tot_entradas"), dados.get("tot_saidas")
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (entradas, saidas)):
        return None
    texto = f"entradas R$ {entradas:.2f}, saidas R$ {saidas:.2f}"
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
    notificacoes - nao pode ver trabalho ja feito como se ainda faltasse).
    'id' (Fase 6, US-E9) e so pra visao do dia poder oferecer o check de
    concluir sem duplicar consulta - os outros consumidores (plano do dia,
    notificacoes) ja ignoravam chave que nao usam."""
    hoje = date.today().isoformat()
    rows = conn.execute(
        "SELECT id, title, hora FROM tasks WHERE completed_at IS NULL AND due_date = ? AND hora IS NOT NULL",
        (hoje,),
    ).fetchall()
    return [
        {
            "id": r["id"],
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
    dependem de ver so o que ainda falta. So o endpoint da agenda e a visao
    do dia (consumo puramente visual) usam esta aqui."""
    hoje = date.today().isoformat()
    rows = conn.execute(
        "SELECT id, title, hora FROM tasks WHERE completed_at IS NOT NULL AND due_date = ? AND hora IS NOT NULL",
        (hoje,),
    ).fetchall()
    return [
        {
            "id": r["id"],
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


# ---- Fase 6 (US-E14): criar/apagar evento no calendario "Painel" (CalDAV) -
# Decisao do Alex: SO escreve no calendario "Painel" (nunca em outro
# calendario do iCloud) e SO apaga um evento cujo UID esteja registrado em
# `eventos_criados` (db.py) como tendo sido criado pelo proprio painel -
# ver caldav_client.py pro porque disso morar la e nao aqui.

def _criar_evento_agenda(conn, titulo, data, hora_inicio, hora_fim, lembrar_min_antes) -> dict:
    titulo = _texto_curto(titulo, 120)
    data_iso = _data_iso_valida(data) if isinstance(data, str) else None
    hora_i = _normalizar_hora(hora_inicio)
    hora_f = _normalizar_hora(hora_fim)
    if not titulo or not data_iso or not hora_i or not hora_f:
        return {"erro": "informe titulo, data (AAAA-MM-DD) e hora de inicio/fim (HH:MM)"}
    inicio = datetime.fromisoformat(f"{data_iso}T{hora_i}")
    fim = datetime.fromisoformat(f"{data_iso}T{hora_f}")
    if fim <= inicio:
        return {"erro": "a hora de fim tem que ser depois da hora de inicio"}
    lembrar = None
    if lembrar_min_antes not in (None, ""):
        lembrar = _inteiro_no_intervalo(lembrar_min_antes, 0, 1440)
        if lembrar is None:
            return {"erro": "lembrar_min_antes precisa ser entre 0 e 1440 minutos"}
    try:
        resultado = caldav_client.criar_evento(titulo, inicio, fim, lembrar)
    except caldav_client.NaoConfiguradoError as erro:
        return {"erro": str(erro)}
    except Exception:
        return {"erro": "nao consegui criar o evento no iCloud agora - tenta de novo"}
    registrar_evento_criado(conn, resultado["uid"], titulo, resultado["inicio"], resultado["fim"])
    return {"ok": True, **resultado}


@app.route("/api/agenda/eventos", methods=["POST"])
def criar_evento_agenda_rota():
    recusa = _recusar_no_modo_visitante()  # escreve no iCloud real do Alex
    if recusa:
        return recusa
    body = _corpo_json()
    conn = get_db()
    resultado = _criar_evento_agenda(
        conn, body.get("titulo"), body.get("data"), body.get("hora_inicio"), body.get("hora_fim"),
        body.get("lembrar_min_antes"),
    )
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201


def _apagar_evento_agenda(conn, uid: str) -> dict:
    # A guarda de verdade e essa: SO apaga se o painel registrou que foi ele
    # quem criou. Nunca chega a chamar o iCloud se o uid nao estiver aqui.
    if not evento_criado_pelo_painel(conn, uid):
        return {"erro": "esse evento nao foi criado pelo painel - nunca mexo em evento que eu nao criei"}
    try:
        caldav_client.apagar_evento(uid)
    except caldav_client.NaoConfiguradoError as erro:
        return {"erro": str(erro)}
    except Exception:
        return {"erro": "nao consegui apagar o evento no iCloud agora - tenta de novo"}
    esquecer_evento_criado(conn, uid)
    return {"ok": True}


@app.route("/api/agenda/eventos/<uid>", methods=["DELETE"])
def apagar_evento_agenda_rota(uid):
    recusa = _recusar_no_modo_visitante()  # apaga no iCloud real do Alex
    if recusa:
        return recusa
    conn = get_db()
    resultado = _apagar_evento_agenda(conn, uid)
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado)


@app.route("/api/agenda/eventos-criados", methods=["GET"])
def eventos_criados_rota():
    conn = get_db()
    resultado = list_eventos_criados(conn)
    conn.close()
    return jsonify(resultado)


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


# Faixa M4 (uso diario): o texto da IA do resumo do dia so precisa ser gerado
# de novo quando algo relevante muda - nao a cada carregamento da pagina.
# "Relevante" = tarefa importante (prioridade alta/urgente) nova/concluida
# hoje, ou gasto real de hoje acima deste limiar (R$100). Abaixo disso (ex.:
# marcar uma tarefa comum, um cafe de R$8), o cache de hoje continua valendo.
GASTO_GRANDE_LIMIAR_RESUMO = 100.0


def _impressao_resumo_dia(conn, today: str, n_eventos: int) -> str:
    """Fingerprint barata do que e relevante pro resumo do dia - se nao
    mudou desde a ultima geracao, o texto de antes ainda serve. So ids (nao
    o conteudo inteiro), e pendente/concluida hoje ficam em dois grupos
    separados (nao so um OR) pra uma tarefa importante que MUDA de pendente
    pra concluida hoje tambem contar como mudanca relevante, mesmo que o id
    ja aparecesse antes."""
    tarefas_pendentes = conn.execute(
        "SELECT id FROM tasks WHERE prioridade IN ('alta', 'urgente') AND completed_at IS NULL ORDER BY id"
    ).fetchall()
    tarefas_concluidas_hoje = conn.execute(
        "SELECT id FROM tasks WHERE prioridade IN ('alta', 'urgente') AND date(completed_at) = ? ORDER BY id",
        (today,),
    ).fetchall()
    gastos_grandes = conn.execute(
        "SELECT id FROM expenses WHERE tipo = 'real' AND date(created_at) = ? AND amount >= ? ORDER BY id",
        (today, GASTO_GRANDE_LIMIAR_RESUMO),
    ).fetchall()
    return "|".join(
        [
            today,
            "tp:" + ",".join(str(r["id"]) for r in tarefas_pendentes),
            "tc:" + ",".join(str(r["id"]) for r in tarefas_concluidas_hoje),
            "g:" + ",".join(str(r["id"]) for r in gastos_grandes),
            f"e:{n_eventos}",
        ]
    )


@app.route("/api/summary/today", methods=["GET"])
def summary_today():
    today = date.today().isoformat()
    conn = get_db()
    materializar_tarefas_recorrentes(conn)
    done = conn.execute("SELECT title FROM tasks WHERE date(completed_at) = ?", (today,)).fetchall()
    pending = conn.execute(
        "SELECT title FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL"
    ).fetchall()
    if _modo_visitante_ativo():
        # US-C20: nem chama a IA - o resumo em texto livre poderia mencionar
        # valor gasto ou dado de saude, e nao da pra garantir que um prompt
        # "sem esses dados" nunca vaze nada por inferencia. Mais seguro nao
        # gerar o texto nenhum enquanto o modo visitante estiver ativo.
        eventos = _eventos_de_hoje_com_seguranca(conn)
        conn.close()
        return jsonify(
            {
                "summary": "Resumo oculto no modo visitante.",
                "gasto_hoje": None,
                "gasto_planejado": None,
                "tarefas_concluidas": len(done),
                "eventos_hoje": len(eventos),
            }
        )
    expenses = conn.execute(
        "SELECT amount, category FROM expenses WHERE date(created_at) = ? AND tipo = 'real'", (today,)
    ).fetchall()
    gasto_hoje = sum(r["amount"] for r in expenses)
    gasto_planejado = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE date(created_at) = ? AND tipo = 'planejado'",
        (today,),
    ).fetchone()["total"]
    eventos = _eventos_de_hoje_com_seguranca(conn)

    # Faixa M4: so o texto (summary) vem do cache - gasto_hoje/gasto_planejado/
    # tarefas_concluidas/eventos_hoje acima sao recalculados sempre, frescos.
    forcar = request.args.get("forcar") == "1"
    impressao = _impressao_resumo_dia(conn, today, len(eventos))
    cache = None if forcar else obter_resumo_dia_cache(conn, today)
    if cache and cache["impressao"] == impressao:
        conn.close()
        return jsonify(
            {
                "summary": json.loads(cache["resposta_json"])["summary"],
                "gasto_hoje": gasto_hoje,
                "gasto_planejado": gasto_planejado,
                "tarefas_concluidas": len(done),
                "eventos_hoje": len(eventos),
            }
        )

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

    _log_usage(conn, usage, "resumo_dia")
    salvar_resumo_dia_cache(conn, today, impressao, json.dumps({"summary": text}))
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


def _previa_noite_anterior(conn, hoje: date) -> dict:
    """Fase 5 (US-C21): resumo factual (sem IA) de como foi a noite anterior,
    a partir de dado ja existente - sono (saude_dados, se o Atalho mandou;
    checkin, se foi so o 1-toque da manha), hidratacao do dia anterior e
    quantos dos medicamentos ativos foram marcados como tomados ontem
    (usa a mesma materializacao de tarefa recorrente que ja rastreia isso -
    nao cria sistema novo de "tomei o remedio")."""
    ontem = hoje - timedelta(days=1)
    ontem_iso = ontem.isoformat()
    dia = get_saude_dia(conn, ontem_iso)
    checkin = get_checkin(conn, ontem_iso)
    copos = contar_hidratacao_dia(conn, ontem_iso)

    total_meds = 0
    meds_tomados = 0
    for m in list_medicamentos_ativos(conn):
        row = conn.execute(
            "SELECT completed_at FROM tasks WHERE recorrente_origem_id = ? AND due_date = ?",
            (m["tarefa_modelo_id"], ontem_iso),
        ).fetchone()
        if row is None:
            continue  # remedio nao caia nesse dia (recorrencia nao diaria)
        total_meds += 1
        if row["completed_at"]:
            meds_tomados += 1

    return {
        "data": ontem_iso,
        "sono_horas": dia["sono_horas"] if dia else None,
        "sono_checkin": checkin["sono"] if checkin else None,
        "copos_agua": copos,
        "medicamentos_tomados": meds_tomados,
        "medicamentos_total": total_meds,
    }


@app.route("/api/previa-noite", methods=["GET"])
def previa_noite_rota():
    if _modo_visitante_ativo():
        return jsonify({"oculto": True})
    conn = get_db()
    resultado = _previa_noite_anterior(conn, date.today())
    conn.close()
    return jsonify(resultado)


def _sinal_sobrecarga_hoje(conn) -> dict:
    """Fase 5 (US-C22): monta os sinais de hoje e chama notificacoes.
    sinal_sobrecarga pra combinar. semana_pesada usa a mesma deteccao da
    US-C13 (aprendizado.semana_pesada, ja integrada na main) - mesmo
    calculo de notificacoes.semana_pesada_aviso, so que aqui so importa o
    booleano "sobrecarregada", nao a mensagem pronta."""
    hoje = date.today()
    n_atrasadas = conn.execute(
        "SELECT COUNT(*) AS n FROM tasks WHERE completed_at IS NULL AND due_date IS NOT NULL AND due_date < ?",
        (hoje.isoformat(),),
    ).fetchone()["n"]
    sono = {
        l["data"]: l["sono_horas"]
        for l in list_saude_dados(conn, desde=(hoje - timedelta(days=14)).isoformat())
        if l["sono_horas"] is not None
    }
    checkin_sono = {
        c["data"]: c["sono"] for c in list_checkins(conn, (hoje - timedelta(days=14)).isoformat()) if c["sono"]
    }
    seguidas, _ = vida.sequencia_noites_ruins(sono, checkin_sono, hoje)
    inicio_proxima = hoje - timedelta(days=hoje.weekday()) + timedelta(days=7)
    fim_proxima = inicio_proxima + timedelta(days=6)
    contagem_proxima = aprendizado.contagem_itens_semana(conn, inicio_proxima, fim_proxima)
    historico = aprendizado.carga_semanal_historica(conn, hoje)
    semana_pesada = aprendizado.semana_pesada(contagem_proxima, historico)["sobrecarregada"]
    return notificacoes.sinal_sobrecarga(n_atrasadas, seguidas >= 3, semana_pesada=semana_pesada)


@app.route("/api/sobrecarga", methods=["GET"])
def sobrecarga_rota():
    conn = get_db()
    resultado = _sinal_sobrecarga_hoje(conn)
    conn.close()
    return jsonify(resultado)


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


# ---- Fase 6, US-E9: visao do dia (aba Hoje, abaixo do chat) ----------------
# Reusa o MESMO eixo de agenda+tarefas de _eventos_de_hoje_com_seguranca (que
# /api/calendario/hoje ja usa) em vez de duplicar essa busca - so acrescenta
# habitos com horario. O front reusa a MESMA classe visual da linha do tempo
# que a agenda de hoje ja tinha (.linha-do-tempo, ver style.css) - so estende,
# nao duplica.

def _semana_de(dia: date) -> tuple[str, str]:
    inicio = dia - timedelta(days=dia.weekday())
    return inicio.isoformat(), (inicio + timedelta(days=6)).isoformat()


def _habitos_do_dia_com_horario(conn, dia: date) -> list[dict]:
    """Habitos com horario definido e devidos no dia, no mesmo formato dos
    itens de agenda/tarefa - habito sem horario nao tem como entrar na linha
    do tempo (nao ha posicao pra desenhar), continua so na aba Vida."""
    dia_iso = dia.isoformat()
    ini_semana, fim_semana = _semana_de(dia)
    itens = []
    for h in list_habitos(conn):
        if not h["horario"]:
            continue
        vezes_feitas_semana = len(marcacoes_habito_no_periodo(conn, h["id"], ini_semana, fim_semana))
        if not vida.habito_devido_em(h, dia, vezes_feitas_semana):
            continue
        itens.append(
            {
                "id": h["id"],
                "titulo": h["nome"],
                "inicio": f"{dia_iso}T{h['horario']}:00",
                "fim": f"{dia_iso}T{h['horario']}:00",
                "dia_inteiro": False,
                "origem": "habito",
                "concluido": habito_marcado(conn, dia_iso, h["id"]),
            }
        )
    return itens


def _visao_do_dia_itens(conn, hoje: date) -> list[dict]:
    itens = [dict(e) for e in _eventos_de_hoje_com_seguranca(conn)]
    itens += _tarefas_concluidas_com_horario_hoje(conn)
    for item in itens:
        item.setdefault("id", None)
    itens += _habitos_do_dia_com_horario(conn, hoje)
    itens.sort(key=lambda e: e["inicio"])
    return itens


def _item_concluivel(item: dict) -> bool:
    """So tarefa/habito sao completaveis pelo painel - compromisso de
    calendario (iCloud) nao tem como confirmar presenca."""
    return item.get("origem") in ("tarefa", "habito") and item.get("id") is not None


def _status_do_dia(itens: list[dict], agora: datetime) -> str:
    """Linha de status do topo - direto, sem julgamento: so constata quantos
    itens completaveis (tarefa/habito) ja passaram do horario sem
    confirmacao. Compromisso de calendario passado nunca conta aqui (mesmo
    criterio visual que a linha do tempo ja usa pra classe 'passado', que
    nunca julga presenca)."""
    passados_sem_confirmar = 0
    for item in itens:
        if item.get("dia_inteiro") or item.get("concluido") or not _item_concluivel(item):
            continue
        try:
            fim = datetime.fromisoformat(item["fim"])
        except (KeyError, ValueError, TypeError):
            continue
        if fim < agora:
            passados_sem_confirmar += 1
    if passados_sem_confirmar == 0:
        return "tudo sob controle"
    if passados_sem_confirmar == 1:
        return "1 item passou do horario sem confirmar"
    return f"{passados_sem_confirmar} itens passaram do horario sem confirmar"


def _proximo_item_em_foco(itens: list[dict], agora: datetime) -> dict | None:
    """O item EM FOCO AGORA: o proximo (ou, sem nenhum futuro, o que passou
    do horario mais recentemente - o miss mais fresco, nao o mais antigo)
    tarefa/habito pendente com horario - compromisso de calendario fica de
    fora (nao tem check de concluir nem faz sentido 'comecar foco' nele).
    Sem nenhum item completavel com horario hoje, None (o front mostra o
    estado vazio)."""
    pendentes = [i for i in itens if not i.get("dia_inteiro") and not i.get("concluido") and _item_concluivel(i)]
    if not pendentes:
        return None
    futuros = [i for i in pendentes if datetime.fromisoformat(i["inicio"]) >= agora]
    escolhido = min(futuros, key=lambda i: i["inicio"]) if futuros else max(pendentes, key=lambda i: i["inicio"])
    inicio = datetime.fromisoformat(escolhido["inicio"])
    return {
        "origem": escolhido["origem"],
        "id": escolhido["id"],
        "titulo": escolhido["titulo"],
        "em_texto": vida.formatar_em_quanto_tempo(inicio, agora),
    }


@app.route("/api/visao-dia/hoje", methods=["GET"])
def visao_dia_hoje():
    conn = get_db()
    materializar_tarefas_recorrentes(conn)
    hoje = date.today()
    agora = datetime.now()
    itens = _visao_do_dia_itens(conn, hoje)
    conn.close()
    concluidas = sum(1 for i in itens if i.get("concluido"))
    return jsonify(
        {
            "status": _status_do_dia(itens, agora),
            "em_foco": _proximo_item_em_foco(itens, agora),
            "total_itens": len(itens),
            "total_concluidas": concluidas,
            "timeline": itens,
        }
    )


def _contagem_dia(conn, dia: date) -> dict:
    """Contagem agregada simples de um dia (tarefas + habitos devidos +
    eventos criados no calendario Painel, que sao locais - a agenda do
    iCloud em si NAO entra aqui: buscar dia a dia por uma semana/mes inteiro
    faria N chamadas de rede instaveis so pra uma contagem, custo que o "sem
    virar outro app" da US-E9 nao pede). 'concluidas' conta so tarefa/habito
    (evento de calendario nao tem conclusao)."""
    dia_iso = dia.isoformat()
    total_tarefas = conn.execute("SELECT COUNT(*) AS n FROM tasks WHERE due_date = ?", (dia_iso,)).fetchone()["n"]
    concluidas_tarefas = conn.execute(
        "SELECT COUNT(*) AS n FROM tasks WHERE due_date = ? AND completed_at IS NOT NULL", (dia_iso,)
    ).fetchone()["n"]
    total_eventos = conn.execute(
        "SELECT COUNT(*) AS n FROM eventos_criados WHERE date(inicio) = ?", (dia_iso,)
    ).fetchone()["n"]
    ini_semana, fim_semana = _semana_de(dia)
    total_habitos = 0
    concluidos_habitos = 0
    for h in list_habitos(conn):
        vezes_feitas_semana = len(marcacoes_habito_no_periodo(conn, h["id"], ini_semana, fim_semana))
        if not vida.habito_devido_em(h, dia, vezes_feitas_semana):
            continue
        total_habitos += 1
        if habito_marcado(conn, dia_iso, h["id"]):
            concluidos_habitos += 1
    return {
        "data": dia_iso,
        "total": total_tarefas + total_eventos + total_habitos,
        "concluidas": concluidas_tarefas + concluidos_habitos,
    }


@app.route("/api/visao-dia/periodo", methods=["GET"])
def visao_dia_periodo():
    tipo = request.args.get("tipo", "semana")
    hoje = date.today()
    if tipo == "mes":
        inicio = hoje.replace(day=1)
        fim = vida.somar_meses(inicio, 1) - timedelta(days=1)
    else:
        tipo = "semana"
        inicio, fim_iso = _semana_de(hoje)
        inicio = date.fromisoformat(inicio)
        fim = date.fromisoformat(fim_iso)
    conn = get_db()
    dias = []
    d = inicio
    while d <= fim:
        dias.append(_contagem_dia(conn, d))
        d += timedelta(days=1)
    conn.close()
    return jsonify({"tipo": tipo, "dias": dias})


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

    _log_usage(conn, usage, "plano_dia")
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


# ---- Fase 6 (US-E7): consultas que viram card + caminho local do chat -------
# Tudo aqui e chamado pelos executores de tool do chat (_processar_mensagem_chat)
# - o MESMO codigo atende a IA (tool-use) e o classificador local
# (_plano_local_chat -> _classificar_intent(somente_local=True)), entao o card
# e o mesmo nos dois caminhos. Nenhuma funcao aqui devolve valor em dinheiro
# pra IA (o card de meta leva o valor; a prosa nao precisa repetir).


def _agora() -> datetime:
    """Relogio do "a partir de agora" da sugestao de horario - separado pra
    teste fixar a hora sem mockar datetime inteiro."""
    return datetime.now()


def _hhmm_proximo_quarto(momento: datetime) -> str:
    minutos = momento.hour * 60 + momento.minute
    minutos = -(-minutos // 15) * 15
    if minutos >= 24 * 60:
        return "23:59"
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


_SINONIMOS_ROTINA = {"academia": "treino", "treino": "academia", "malhar": "treino", "correr": "treino"}


def _porque_sugestao(conn, titulo: str, janela: dict) -> str:
    """Texto da caixa "Com a sua rotina em mente" (card sugestao): o fato
    real da agenda de hoje + a memoria de rotina (US-E10, categoria
    sua_rotina) que fala do mesmo assunto, quando existir. Nunca inventa."""
    partes = [f"Hoje o maior espaço livre na sua agenda vai das {janela['inicio']} às {janela['fim']}."]
    palavras = [p for p in aprendizado.normalizar_consulta(titulo).split() if len(p) >= 4]
    palavras += [_SINONIMOS_ROTINA[p] for p in palavras if p in _SINONIMOS_ROTINA]
    if palavras:
        for memoria in db.contexto_memorias_categorizadas(conn).get("sua_rotina", []):
            texto_mem = aprendizado.normalizar_consulta(memoria["texto"])
            if any(p[:5] in texto_mem for p in palavras):
                partes.append(f"Da sua rotina: {_texto_curto(memoria['texto'], 200)}")
                break
    return " ".join(partes)


def _sugerir_horario_livre(conn, entrada: dict) -> dict:
    """Maior espaco livre de HOJE a partir de agora (tool sugerir_horario_livre
    e pergunta "como encaixo X hoje?"). Com resultado, vira card `sugestao`."""
    eventos = _eventos_de_hoje_com_seguranca(conn)
    compromissos = [(e["inicio"][11:16], e["fim"][11:16]) for e in eventos if not e.get("dia_inteiro")]
    duracao = _inteiro_no_intervalo(entrada.get("duracao_minutos"), 5, 720) or 60
    inicio_dia = max(_normalizar_hora(entrada.get("depois_das")) or "06:00", _hhmm_proximo_quarto(_agora()))
    fim_dia = _normalizar_hora(entrada.get("antes_das")) or "22:00"
    janela = agenda.maior_janela_livre(compromissos, inicio_dia, fim_dia, duracao) if inicio_dia < fim_dia else None
    if not janela:
        return {"encontrado": False}
    titulo = _texto_curto(entrada.get("titulo"), 80) or "Horário livre"
    return {
        "encontrado": True,
        **janela,
        "_efeito": {
            "entidade": "sugestao",
            "consulta": True,
            "titulo": titulo[:1].upper() + titulo[1:],
            "inicio": f"{date.today().isoformat()}T{janela['inicio']}",
            "duracao_min": duracao,
            "porque": _porque_sugestao(conn, titulo, janela),
        },
    }


def _duracao_tipica(conn, titulo: str | None) -> int:
    """Duracao pra sugestao local: treino usa a media dos ultimos treinos
    registrados (quando houver), o resto 60 min (mesmo padrao da tool)."""
    t = aprendizado.normalizar_consulta(titulo or "")
    if re.search(r"trein|academia|malh|corr", t):
        row = conn.execute(
            "SELECT AVG(duracao_min) AS media FROM (SELECT duracao_min FROM treinos "
            "WHERE duracao_min IS NOT NULL ORDER BY data DESC, id DESC LIMIT 10)"
        ).fetchone()
        if row and row["media"]:
            return max(10, min(int(round(row["media"] / 5) * 5), 240))
    return 60


def _casa_termo(termo_normalizado: str, nome) -> bool:
    """Busca aproximada por palavra (prefixo de 5 letras) - "reforma do
    quarto" acha "Reformar o quarto"; sem termo, tudo casa."""
    palavras = [p for p in termo_normalizado.split() if len(p) >= 3 and p not in ("dos", "das", "pra", "para", "com")]
    if not palavras:
        return True
    alvo = aprendizado.normalizar_consulta(str(nome or ""))
    return all(p[:5] in alvo for p in palavras)


def _consultar_projeto(conn, termo) -> dict:
    hoje = date.today()
    termo_n = aprendizado.normalizar_consulta(termo if isinstance(termo, str) else "")
    projetos = list_projetos(conn)
    viagens = list_viagens_futuras(conn, hoje.isoformat())
    if termo_n:
        quer_viagem = bool(re.search(r"\bviage", termo_n))
        termo_sem_viagem = re.sub(r"\bviage(m|ns)\b", "", termo_n).strip()
        viag = [v for v in viagens if termo_sem_viagem and _casa_termo(termo_sem_viagem, v["destino"])]
        if not viag and quer_viagem:
            viag = viagens[:1]
        proj = [p for p in projetos if _casa_termo(termo_n, p["nome"])]
    else:
        viag = viagens[:1]
        proj = [p for p in projetos if p["status"] != "pausado"] or projetos
    efeitos = [{"entidade": "viagem", "id": v["id"], "consulta": True} for v in viag]
    efeitos += [{"entidade": "projeto", "id": p["id"], "consulta": True} for p in proj]
    efeitos = efeitos[:3]
    itens = []
    for ef in efeitos:
        if ef["entidade"] == "viagem":
            v = next(x for x in viag if x["id"] == ef["id"])
            itens.append({"tipo": "viagem", "nome": v["destino"], "ida": v["data_ida"]})
        else:
            p = next(x for x in proj if x["id"] == ef["id"])
            d = _projeto_detalhado(conn, p, hoje)
            itens.append({"tipo": "projeto", "nome": p["nome"], "percentual": d["percentual"], "status": d["status"]})
    return {"encontrados": len(itens), "itens": itens, "_efeito": efeitos}


def _consultar_meta(conn, termo) -> dict:
    termo_n = aprendizado.normalizar_consulta(termo if isinstance(termo, str) else "")
    metas = [g for g in list_goals(conn) if not termo_n or _casa_termo(termo_n, g["titulo"])][:3]
    itens = []
    for g in metas:
        # C1: mesma funcao do card de meta (calculos.percentual_meta_exibicao)
        pct = calculos.percentual_meta_exibicao(g["valor_guardado"], g["valor_alvo"])
        itens.append({"titulo": g["titulo"], "percentual": pct, "prazo": g["prazo"]})
    return {
        "encontradas": len(itens),
        "metas": itens,
        "_efeito": [{"entidade": "meta", "id": g["id"], "consulta": True} for g in metas],
    }


def _consultar_treinos(conn, dias) -> dict:
    dias = _inteiro_no_intervalo(dias, 1, 90) or 7
    desde = (date.today() - timedelta(days=dias - 1)).isoformat()
    row = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(duracao_min), 0) AS m FROM treinos WHERE data >= ?", (desde,)
    ).fetchone()
    return {
        "dias": dias,
        "sessoes": row["n"],
        "minutos": int(row["m"]),
        "_efeito": {"entidade": "treinos", "dias": dias, "consulta": True},
    }


def _consultar_habitos(conn, nome) -> dict:
    termo_n = aprendizado.normalizar_consulta(nome if isinstance(nome, str) else "")
    habitos = [h for h in list_habitos(conn) if not termo_n or _casa_termo(termo_n, h["nome"])][:4]
    hoje_iso = date.today().isoformat()
    itens = [{"nome": h["nome"], "feito_hoje": db.habito_marcado(conn, hoje_iso, h["id"])} for h in habitos]
    return {
        "encontrados": len(itens),
        "habitos": itens,
        "_efeito": [{"entidade": "habito", "id": h["id"], "consulta": True} for h in habitos],
    }


def _consultar_saude_dia(conn) -> dict:
    hoje_iso = date.today().isoformat()
    return {
        "agua_copos_hoje": contar_hidratacao_dia(conn, hoje_iso),
        "_efeito": {"entidade": "saude_dia", "consulta": True},
    }


def _plano_local_chat(conn, texto: str) -> list[tuple[str, dict]] | None:
    """Traduz o que o classificador LOCAL resolveu (_classificar_intent com
    somente_local=True - padrao aprendido ou banco "pergunta -> onde
    buscar") em chamadas das tools do chat. None = a IA responde.

    Revisao da Fase 6: frase com verbo de acao ou assunto fora do banco
    local (aprendizado.exige_ia - os MESMOS filtros de consulta_conhecida)
    nunca vira consulta local, nem por padrao aprendido - senao um padrao
    "gastei 80 no mercado" -> consultar/habitos (correcao manual errada ou
    envenenada) fazia o chat responder sem registrar o gasto. So a regra
    fixa do copo de agua (consulta_conhecida) continua valendo nesse caso."""
    if aprendizado.exige_ia(texto) and not aprendizado.consulta_conhecida(texto):
        return None
    resultado, _erro = _classificar_intent(conn, texto, somente_local=True)
    if not resultado:
        return None
    parametros = resultado.get("parametros") if isinstance(resultado.get("parametros"), dict) else {}
    if resultado["acao"] == "registrar_checkin" and parametros.get("campo") == "hidratacao":
        return [("registrar_hidratacao", {})]
    if resultado["acao"] != "consultar":
        return None
    plano = []
    for f in aprendizado.fontes_validas(parametros):
        fonte = f["fonte"]
        if fonte == "projeto":
            plano.append(("consultar_projeto", {"termo": f.get("termo")}))
        elif fonte == "meta":
            plano.append(("consultar_meta", {"termo": f.get("termo")}))
        elif fonte == "treinos":
            plano.append(("consultar_treinos", {"dias": f.get("dias")}))
        elif fonte == "habitos":
            plano.append(("consultar_habitos", {"nome": f.get("termo")}))
        elif fonte == "saude_dia":
            plano.append(("consultar_saude_dia", {}))
        elif fonte == "sugestao":
            titulo = f.get("titulo") if isinstance(f.get("titulo"), str) else None
            duracao = f.get("duracao_min") if isinstance(f.get("duracao_min"), int) else _duracao_tipica(conn, titulo)
            plano.append(("sugerir_horario_livre", {"titulo": titulo, "duracao_minutos": duracao}))
    return plano or None


def _frase_local(chamada: dict) -> str:
    tool = chamada["tool"]
    res = chamada["resultado"] if isinstance(chamada.get("resultado"), dict) else {}
    entrada = chamada.get("entrada") if isinstance(chamada.get("entrada"), dict) else {}
    if res.get("erro"):
        return "Não consegui buscar isso agora."
    if tool == "consultar_projeto":
        n = res.get("encontrados", 0)
        if not n:
            return "Não achei projeto nem viagem com esse nome." if entrada.get("termo") else "Você ainda não tem projeto nem viagem cadastrados."
        return "Aqui está o projeto." if n == 1 else f"Aqui estão {n} projetos."
    if tool == "consultar_meta":
        n = res.get("encontradas", 0)
        return "Não achei nenhuma meta." if not n else ("Aqui está a meta." if n == 1 else f"Aqui estão {n} metas.")
    if tool == "consultar_treinos":
        dias = res.get("dias", 7)
        periodo = "hoje" if dias == 1 else f"nos últimos {dias} dias"
        return f"Seus treinos {periodo}." if res.get("sessoes") else f"Nenhum treino registrado {periodo}."
    if tool == "consultar_habitos":
        return "Seus hábitos." if res.get("encontrados") else "Você ainda não tem hábito cadastrado."
    if tool == "consultar_saude_dia":
        return "Sua saúde hoje."
    if tool == "sugerir_horario_livre":
        if res.get("encontrado"):
            return f"Dá pra encaixar às {res['inicio']}."
        return "Hoje não sobrou um espaço livre desse tamanho na agenda."
    if tool == "registrar_hidratacao":
        total = res.get("total_hoje")
        return f"+1 copo de água. {total} hoje." if total else "+1 copo de água."
    return "Feito."


def _resposta_local_chat(chamadas: list[dict]) -> str:
    """Frase curta que acompanha os cards no caminho local (sem IA) - o dado
    esta no card; a frase nunca carrega valor em dinheiro."""
    return " ".join(_frase_local(c) for c in chamadas) or "Feito."


def _fonte_da_chamada(chamada: dict) -> dict | None:
    tool = chamada["tool"]
    entrada = chamada.get("entrada") if isinstance(chamada.get("entrada"), dict) else {}

    def com_termo(fonte, chave):
        termo = entrada.get(chave)
        return {"fonte": fonte, **({"termo": termo} if isinstance(termo, str) and termo.strip() else {})}

    if tool == "consultar_projeto":
        return com_termo("projeto", "termo")
    if tool == "consultar_meta":
        return com_termo("meta", "termo")
    if tool == "consultar_habitos":
        return com_termo("habitos", "nome")
    if tool == "consultar_treinos":
        dias = _inteiro_no_intervalo(entrada.get("dias"), 1, 90)
        return {"fonte": "treinos", **({"dias": dias} if dias else {})}
    if tool == "consultar_saude_dia":
        return {"fonte": "saude_dia"}
    if tool == "sugerir_horario_livre" and not entrada.get("depois_das") and not entrada.get("antes_das"):
        fonte = {"fonte": "sugestao"}
        if isinstance(entrada.get("titulo"), str) and entrada["titulo"].strip():
            fonte["titulo"] = entrada["titulo"].strip()
        duracao = _inteiro_no_intervalo(entrada.get("duracao_minutos"), 5, 720)
        if duracao:
            fonte["duracao_min"] = duracao
        return fonte
    return None


def _padrao_das_chamadas(chamadas: list[dict]) -> dict | None:
    """US-E7: o que a IA fez vira "pergunta -> onde buscar" SO quando ela
    respondeu usando exclusivamente ferramentas de consulta (ou so o copo de
    agua) sem erro - qualquer ferramenta que cria/muda outra coisa (ou
    nenhuma ferramenta) nao ensina nada."""
    if not chamadas:
        return None
    if any(isinstance(c.get("resultado"), dict) and c["resultado"].get("erro") for c in chamadas):
        return None
    if len(chamadas) == 1 and chamadas[0]["tool"] == "registrar_hidratacao":
        return {"acao": "registrar_checkin", "parametros": {"campo": "hidratacao"}}
    fontes = [_fonte_da_chamada(c) for c in chamadas]
    if not all(fontes):
        return None
    return {"acao": "consultar", "parametros": {"fontes": fontes[:6]}}


def _resposta_exemplo_teste_ia() -> tuple[str, list[str], dict]:
    """Modo teste de IA (config `modo_teste_ia`): envelope de cards FIXO,
    montado direto com `cards.novo_card`/`cards.envelope` (os mesmos
    primitivos puros que os `card_*` de verdade usam por baixo) - nunca toca
    o banco nem chama `card_*`/executor nenhum, entao nao existe id de
    verdade nenhum ids negativos (-1) so pra deixar claro no DOM que e
    exemplo, e as actions ficam vazias de proposito (um `abrir_aba`/
    `desfazer` apontando pra um id que nao existe so confundiria ao clicar).
    So serve pra conferir o FORMATO visual (docs/CARDS.md) sem gastar
    chamada real nem gravar nada."""
    hoje = date.today().isoformat()
    cards_lista = [
        cards.novo_card(
            "tarefas_criadas",
            {
                "tarefas": [
                    {
                        "id": -1,
                        "titulo": "Exemplo: revisar contrato (modo teste)",
                        "data": hoje,
                        "hora": "14:00",
                        "quando": None,
                        "recorrencia": None,
                        "concluida": False,
                    }
                ]
            },
        ),
        cards.novo_card(
            "transacao",
            {
                "id": -1,
                "entidade": "gasto",
                "sentido": "saida",
                "titulo": "Exemplo: mercado (modo teste)",
                "valor": 87.5,
                "categoria": "mercado",
                "status": "real",
                "data": hoje,
                "meio": None,
                "saldo": None,
                "oculto": False,
            },
        ),
        cards.novo_card(
            "lembrete",
            {
                "id": -1,
                "titulo": "Exemplo: ligar pro dentista (modo teste)",
                "data": hoje,
                "hora": None,
                "recorrente": False,
                "despertar": False,
            },
        ),
    ]
    passos = [
        {"modulo": "Tarefas", "descricao": 'Criou a tarefa "Exemplo: revisar contrato (modo teste)"', "ms": 0},
        {"modulo": "Finanças", "descricao": 'Registrou o gasto "Exemplo: mercado (modo teste)"', "ms": 0},
        {"modulo": "Assistente", "descricao": 'Criou o lembrete "Exemplo: ligar pro dentista (modo teste)"', "ms": 0},
    ]
    resposta = (
        "Modo teste de IA ligado - isso é um exemplo fixo, sem chamar nenhuma IA de "
        "verdade. Dá uma olhada no formato dos cards abaixo; desliga em Painel > "
        "Custo de IA pra voltar ao chat normal."
    )
    return resposta, [], cards.envelope(cards_lista, resposta, passos)


def _processar_mensagem_chat(
    conn, texto: str, detalhes: dict | None = None
) -> tuple[str | None, list[str], str | None]:
    """Roda o pipeline inteiro de chat (contexto + tool-use + persistencia) -
    fonte unica de verdade da conversa, usada tanto pela rota HTTP /api/chat
    quanto pelo bot do Telegram, pra nenhum dos dois canais reimplementar a
    logica de tool-use (nem arriscar os dois divergirem). Devolve
    (resposta, acoes, None) no sucesso, ou (None, [], mensagem_de_erro).

    `detalhes` (Fase 6, opcional - so /api/chat passa): dict que recebe o
    envelope do contrato de cards (docs/CARDS.md: cards, resumo_texto,
    passos). O Telegram nao passa e continua recebendo so o texto."""
    # Modo teste de IA: bypass total, ANTES de qualquer coisa (nem regra
    # local, nem materializar tarefa recorrente) - de proposito 100% sem
    # efeito e SEM salvar no historico (chat_mensagens), porque
    # _historico_chat_para_ia manda o historico de volta pra IA numa chamada
    # real futura - se essa mensagem de exemplo entrasse ali, contaminaria o
    # contexto da proxima conversa real com dado falso.
    if _modo_teste_ia_ativo(conn):
        resposta, acoes, envelope_cards = _resposta_exemplo_teste_ia()
        if detalhes is not None:
            detalhes.update(envelope_cards)
        return resposta, acoes, None

    materializar_tarefas_recorrentes(conn)

    # Fase 7 (Etapa 0): regra local (classificador_local/regras/) antes de
    # qualquer IA - casou e executou, responde so com os cards da regra.
    local = classificador_local.casar(texto)
    if local:
        envelope_local = classificador_local.executar(conn, local, _criar_token_desfazer(conn))
        if envelope_local is not None:
            resposta = envelope_local["resumo_texto"] or "Feito."
            envelope_local["resumo_texto"] = resposta
            salvar_mensagem_chat(conn, "user", texto)
            salvar_mensagem_chat(conn, "assistant", resposta, envelope_local["cards"])
            _marcar_atividade(conn)
            if detalhes is not None:
                detalhes.update(envelope_local)
            return resposta, [local["acao"]], None

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
            cur = conn.execute(
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
            # "_efeito" (Fase 6, docs/CARDS.md): chave privada - vira card e
            # token de desfazer, e cards.RegistroExecucao tira antes da IA ver.
            return {"ok": True, "recorrente": True, "_efeito": {"entidade": "tarefa", "id": cur.lastrowid}}

        # Fase 7 (A6): data relativa ("sexta", "amanha") resolvida em codigo;
        # o quando_data do modelo so vale como transicao (docs/calculos.md).
        quando_data = claude_client.resolver_quando_data(entrada, date.today())
        cur = conn.execute(
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
        resultado = {"ok": True, "_efeito": {"entidade": "tarefa", "id": cur.lastrowid}}
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
        cur = conn.execute(
            "INSERT INTO expenses (amount, category, description, source_text, tipo) VALUES (?, ?, ?, ?, ?)",
            (entrada["valor"], entrada.get("categoria") or "outros", entrada["titulo"], texto, status_gasto),
        )
        conn.commit()
        efeito = {"entidade": "gasto", "id": cur.lastrowid, "meio": entrada.get("banco")}
        resultado = {"ok": True, "_efeito": efeito}
        if status_gasto == "real":
            saldo_banco = _ajustar_saldo_se_banco_citado(conn, entrada.get("banco"), -entrada["valor"])
            if saldo_banco:
                resultado["saldo_banco"] = saldo_banco
                efeito["saldo"] = saldo_banco
        return resultado

    def exec_registrar_meta(entrada):
        goal_id = create_goal(conn, entrada["titulo"], entrada["valor"], entrada.get("prazo"))
        return {"ok": True, "_efeito": {"entidade": "meta", "id": goal_id}}

    def exec_definir_orcamento(entrada):
        definir_orcamento(conn, entrada["categoria"], entrada["valor_limite"])
        return {"ok": True}

    def exec_registrar_renda(entrada):
        income_id = create_income(conn, entrada["valor"], entrada["categoria"], entrada.get("descricao"), texto)
        efeito = {"entidade": "renda", "id": income_id, "meio": entrada.get("banco")}
        resultado = {"ok": True, "_efeito": efeito}
        saldo_banco = _ajustar_saldo_se_banco_citado(conn, entrada.get("banco"), entrada["valor"])
        if saldo_banco:
            resultado["saldo_banco"] = saldo_banco
            efeito["saldo"] = saldo_banco
        return resultado

    def exec_gerar_plano(_entrada):
        pendentes = _tarefas_pendentes_sem_horario_hoje(conn)
        eventos = _eventos_de_hoje_com_seguranca(conn)
        try:
            plano_texto, usage_plano = claude_client.plano_do_dia(
                [r["title"] for r in pendentes], eventos, memorias_texto
            )
        except ia.core.TetoEstourado:
            # C1: falha da IA dentro de uma ferramenta vira resultado de erro
            # pro modelo explicar, em vez de derrubar a conversa inteira.
            return {"erro": TETO_IA_MSG}
        except ia.core.FalhaChamadaIA:
            return {"erro": "nao consegui gerar o plano agora - tenta de novo em instantes"}
        _log_usage(conn, usage_plano, "plano_dia")
        return {"plano": plano_texto}

    def exec_registrar_lembrete(entrada):
        lembrete_id = create_lembrete(conn, entrada["titulo"], entrada["data"], entrada.get("recorrente", False))
        return {"ok": True, "_efeito": {"entidade": "lembrete", "id": lembrete_id}}

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
        hoje_iso = date.today().isoformat()
        total = registrar_hidratacao(conn, hoje_iso)
        registro_id = conn.execute(
            "SELECT MAX(id) AS id FROM hidratacao_registros WHERE data = ?", (hoje_iso,)
        ).fetchone()["id"]
        # card saude_dia (US-E7) com Desfazer desse copo exato
        return {"ok": True, "total_hoje": total, "_efeito": {"entidade": "hidratacao", "id": registro_id}}

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
        return {"ok": True, "treino_id": treino_id, "_efeito": {"entidade": "treino", "id": treino_id}}

    def exec_registrar_viagem(entrada):
        resultado = _criar_viagem(
            conn, entrada.get("destino"), entrada.get("data_ida"), entrada.get("data_volta"), entrada.get("motivo")
        )
        if resultado.get("ok"):
            resultado["_efeito"] = {"entidade": "viagem", "id": resultado["viagem_id"]}
        return resultado

    def exec_registrar_lugar(entrada):
        return _criar_lugar(conn, entrada.get("nome"), entrada.get("cidade"), entrada.get("tipo"), entrada.get("nota"))

    def exec_registrar_manutencao(entrada):
        # Chat tool (contrato fechado, ver claude_client.ACOES_INTENT/tools) nao
        # manda tipo - so cria manutencao por tempo (casa/equipamento/outro),
        # nunca carro (essa so tem UI, por precisar de km/data especificos).
        return _criar_manutencao(conn, {
            "tipo": "outro",
            "item": entrada.get("item"),
            "intervalo_meses": entrada.get("intervalo_meses"),
            "ultima_vez": entrada.get("ultima_vez"),
        })

    def exec_registrar_ideia_presente(entrada):
        return _criar_ideia_presente(conn, entrada.get("pessoa"), entrada.get("ideia"), entrada.get("ocasiao"))

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

    def exec_registrar_decisao(entrada):
        decisao_id = create_diario_decisao(
            conn, entrada["decisao"], entrada.get("contexto"), entrada.get("revisao_em"), texto
        )
        return {"ok": True, "decisao_id": decisao_id}

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
        return _sugerir_horario_livre(conn, entrada)

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

    def exec_registrar_habito(entrada):
        ativos_antes = len(list_habitos(conn))
        resultado = _criar_habito(
            conn, entrada.get("nome"), entrada.get("meta"), entrada.get("frequencia_tipo"),
            entrada.get("dias_semana"), entrada.get("vezes_por_semana"), entrada.get("horario"),
        )
        if resultado.get("ok"):
            resultado["_efeito"] = {
                "entidade": "habito", "id": resultado["habito_id"],
                "ativos_antes": ativos_antes, "ativos_depois": ativos_antes + 1,
            }
        return resultado

    def exec_marcar_habito(entrada):
        habito = buscar_habito_por_nome(conn, entrada.get("nome"))
        if not habito:
            return {"erro": f"nao achei nenhum habito chamado \"{entrada.get('nome')}\""}
        hoje_iso = date.today().isoformat()
        feito = alternar_habito_dia(conn, hoje_iso, habito["id"])
        return {
            "ok": True, "nome": habito["nome"], "feito": feito,
            "_efeito": {"entidade": "habito_marcacao", "id": habito["id"], "data": hoje_iso, "feito": feito},
        }

    def exec_criar_projeto(entrada):
        resultado = _criar_projeto(conn, entrada.get("nome"), entrada.get("prazo_final"))
        if resultado.get("ok"):
            resultado["_efeito"] = {"entidade": "projeto", "id": resultado["projeto_id"]}
        return resultado

    def exec_adicionar_etapa(entrada):
        projeto = buscar_projeto_por_nome(conn, entrada.get("nome_projeto"))
        if not projeto:
            return {"erro": f"nao achei nenhum projeto chamado \"{entrada.get('nome_projeto')}\""}
        resultado = _adicionar_etapa(conn, projeto["id"], entrada.get("texto"), entrada.get("data_prevista"))
        if resultado.get("ok"):
            resultado["_efeito"] = {"entidade": "projeto_etapa", "id": resultado["etapa_id"], "projeto_id": projeto["id"]}
        return resultado

    def exec_concluir_etapa(entrada):
        projeto = buscar_projeto_por_nome(conn, entrada.get("nome_projeto"))
        if not projeto:
            return {"erro": f"nao achei nenhum projeto chamado \"{entrada.get('nome_projeto')}\""}
        etapas = list_etapas_projeto(conn, projeto["id"])
        proxima = next((e for e in etapas if not e["feita"]), None)
        if not proxima:
            return {"erro": f"o projeto \"{projeto['nome']}\" nao tem etapa pendente"}
        concluir_etapa_projeto(conn, proxima["id"])
        return {
            "ok": True, "projeto": projeto["nome"], "etapa": proxima["texto"],
            "_efeito": {"entidade": "etapa_concluida", "id": proxima["id"], "projeto_id": projeto["id"]},
        }

    def exec_agendar_evento(entrada):
        # modo visitante (so existe com request HTTP - o Telegram nao tem):
        # nunca cria evento no iCloud real (revisao da Fase 6).
        if has_request_context() and _modo_visitante_ativo():
            return {"erro": "agenda indisponivel no modo visitante"}
        resultado = _criar_evento_agenda(
            conn, entrada.get("titulo"), entrada.get("data"), entrada.get("hora_inicio"), entrada.get("hora_fim"),
            entrada.get("lembrar_min_antes"),
        )
        if resultado.get("ok") and resultado.get("uid"):
            lembrar = _inteiro_no_intervalo(entrada.get("lembrar_min_antes"), 0, 1440) \
                if entrada.get("lembrar_min_antes") not in (None, "") else None
            resultado["_efeito"] = {"entidade": "evento", "uid": resultado["uid"], "lembrar_min_antes": lembrar}
        return resultado

    # ---- consultas que viram card (US-E7) - mesmas funcoes pro caminho da
    # IA (tool-use) e pro classificador local (_plano_local_chat) ----
    def exec_consultar_projeto(entrada):
        return _consultar_projeto(conn, entrada.get("termo"))

    def exec_consultar_meta(entrada):
        return _consultar_meta(conn, entrada.get("termo"))

    def exec_consultar_treinos(entrada):
        return _consultar_treinos(conn, entrada.get("dias"))

    def exec_consultar_habitos(entrada):
        return _consultar_habitos(conn, entrada.get("nome"))

    def exec_consultar_saude_dia(_entrada):
        return _consultar_saude_dia(conn)

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
        "registrar_ideia_presente": exec_registrar_ideia_presente,
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
        "registrar_decisao": exec_registrar_decisao,
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
        "registrar_habito": exec_registrar_habito,
        "marcar_habito": exec_marcar_habito,
        "criar_projeto": exec_criar_projeto,
        "adicionar_etapa": exec_adicionar_etapa,
        "concluir_etapa": exec_concluir_etapa,
        "agendar_evento": exec_agendar_evento,
        "consultar_projeto": exec_consultar_projeto,
        "consultar_meta": exec_consultar_meta,
        "consultar_treinos": exec_consultar_treinos,
        "consultar_habitos": exec_consultar_habitos,
        "consultar_saude_dia": exec_consultar_saude_dia,
    }

    # Fase 6 (docs/CARDS.md): cronometra cada tool (passos) e recolhe o
    # "_efeito" de cada executor pra montar os cards - sem mudar o que a IA
    # ve (chaves com "_" saem do resultado antes de voltar pro tool-use).
    registro = cards.RegistroExecucao()
    executores = registro.envolver(executores)

    # US-E7: consulta de padrao conhecido (e "tomei um copo de agua") resolve
    # no classificador LOCAL (_classificar_intent, somente_local) e chama os
    # MESMOS executores que a IA chamaria - sem API, mesmos cards/passos.
    plano = _plano_local_chat(conn, texto)
    if plano:
        for tool, entrada in plano:
            executores[tool](entrada)
        resposta = _resposta_local_chat(registro.chamadas)
        acoes = [c["tool"] for c in registro.chamadas]
    else:
        # Revisao da Fase 6 (achado 4): mesmo teto mensal (e mesmo lock) de
        # _classificar_intent/extrair_nota_fiscal - vale pro /api/chat, pro
        # brain dump "assistente" e pro Telegram (todos passam por aqui).
        # O caminho local acima (sem IA) continua funcionando com o teto
        # estourado.
        with _TETO_IA_LOCK:
            if _teto_ia_estourado("chat"):
                return None, [], TETO_IA_MSG
            # Fase 7 (C1): historico da A5 (resumo fixo + so o que ainda nao
            # foi resumido, na integra - nunca os dois) e medicao nova
            # (medir_uso=True grava cada rodada em uso_ia; o _log_usage
            # abaixo so alimenta a tabela antiga do card antigo).
            mensagens_ia, contexto_fixo = _historico_chat_para_ia(conn, texto, mensagens)
            try:
                # opcoes_chat == passar contexto_fixo/conn/medir_uso=True como
                # kwargs (ver ia/funcoes/chat.py: dubles de teste tem a
                # assinatura antiga de 4 argumentos).
                with claude_client.opcoes_chat(contexto_fixo=contexto_fixo, conn=conn, medir_uso=True):
                    resposta, acoes, usage = claude_client.chat(mensagens_ia, contexto, memorias_texto, executores)
            except ia.core.TetoEstourado:
                return None, [], TETO_IA_MSG
            except anthropic.APIError:
                return None, [], CLAUDE_ERROR_MSG
            except ia.core.ErroProvedor:
                return None, [], CLAUDE_ERROR_MSG
            except (ValueError, KeyError):
                return None, [], CLAUDE_FORMAT_ERROR_MSG

            _log_usage(conn, usage, "chat")
        # cresce o banco "pergunta -> onde buscar": resposta da IA feita SO
        # com ferramentas de consulta vira padrao (vale local depois de
        # LIMIAR_CONFIRMACOES_PADRAO_INTENT repeticoes da mesma frase).
        aprendido = _padrao_das_chamadas(registro.chamadas)
        if aprendido:
            aprendizado.confirmar_padrao_intent(conn, texto, aprendido["acao"], aprendido["parametros"])
    envelope_cards = cards.montar_resposta(
        conn, registro.efeitos(), resposta, registro.passos(), _criar_token_desfazer(conn)
    )
    salvar_mensagem_chat(conn, "user", texto)
    salvar_mensagem_chat(conn, "assistant", resposta, envelope_cards["cards"])
    _marcar_atividade(conn)
    if detalhes is not None:
        detalhes.update(envelope_cards)
    return resposta, acoes, None


def _historico_chat_para_ia(conn, texto: str, mensagens_antigas: list) -> tuple[list, str]:
    """(mensagens, contexto_fixo) pro claude_client.chat - Fase 7 (C1).

    Usa ia.historico.montar_contexto (A5): o resumo das mensagens antigas vai
    em `contexto_fixo` e SO as mensagens que ainda nao entraram no resumo vao
    na integra (as mesmas mensagens nunca aparecem nos dois). A mensagem nova
    ainda nao foi salva em chat_mensagens (e salva depois da resposta), entao
    entra aqui no fim. Qualquer falha da A5 cai no historico antigo (ultimas
    20 mensagens, sem resumo) - o chat nunca quebra por causa disso."""
    try:
        ctx = ia.historico.montar_contexto(conn)
        mensagens = list(ctx["mensagens"]) + [{"role": "user", "content": texto}]
        return mensagens, ctx["contexto_fixo"] or ""
    except Exception:  # noqa: BLE001
        app.logger.exception("chat: montar_contexto (A5) falhou - usando historico antigo")
        return mensagens_antigas, ""


def _criar_token_desfazer(conn):
    """Fabrica do `criar_token` que cards.montar_resposta usa pra por o botao
    Desfazer num card (US-E5, docs/CARDS.md "Desfazer"): grava os ids EXATOS
    do que o card criou em acoes_desfazer e devolve o token. Ajuste otimista
    de saldo (gasto/renda com banco citado) vira conta_id + delta, pra o
    desfazer devolver o saldo tambem."""

    def criar(itens: list[dict]) -> str | None:
        traduzidos = []
        for ef in itens:
            item = {"entidade": ef.get("entidade"), "id": ef.get("id"), "uid": ef.get("uid"),
                    "data": ef.get("data"), "feito": ef.get("feito")}
            saldo = ef.get("saldo")
            if ef.get("entidade") in ("gasto", "renda") and isinstance(saldo, dict):
                antes, depois = saldo.get("antes"), saldo.get("depois")
                conta = buscar_conta_por_nome(conn, saldo.get("banco"))
                if conta and isinstance(antes, (int, float)) and isinstance(depois, (int, float)):
                    item["conta_id"] = conta["id"]
                    item["delta"] = depois - antes
            traduzidos.append(item)
        return db.criar_acao_desfazer(conn, traduzidos)

    return criar


class _DesfazerRecusado(Exception):
    def __init__(self, mensagem: str, status: int):
        super().__init__(mensagem)
        self.status = status


def _verificar_desfazer_evento(conn, uid) -> None:
    """Regra da US-E14: evento da agenda so se desfaz se o painel o criou
    (uid registrado em eventos_criados). Evento de fora NUNCA e apagado."""
    tabela = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'eventos_criados'"
    ).fetchone()
    registrado = bool(
        tabela and isinstance(uid, str) and uid
        and conn.execute("SELECT 1 FROM eventos_criados WHERE uid = ?", (uid,)).fetchone()
    )
    if not registrado:
        raise _DesfazerRecusado("esse evento nao foi criado pelo painel - nao da pra desfazer por aqui", 403)
    if not caldav_client.configurado():
        raise _DesfazerRecusado("agenda do iCloud nao configurada - nao da pra desfazer o evento agora", 503)


def _desfazer_itens(conn, itens: list[dict]) -> int:
    """Reverte exatamente os itens gravados no token, SEM commit (quem chama
    faz tudo numa transacao so). Item que ja nao existe e pulado."""
    for item in itens:
        if item.get("entidade") == "evento":
            _verificar_desfazer_evento(conn, item.get("uid"))  # recusa antes de apagar qualquer coisa

    desfeitos = 0
    for item in itens:
        entidade, id_ = item.get("entidade"), item.get("id")
        if entidade == "evento":
            try:
                caldav_client.apagar_evento(item["uid"])
            except Exception as e:
                raise _DesfazerRecusado("nao consegui apagar o evento no iCloud agora - tenta de novo", 502) from e
            conn.execute("DELETE FROM eventos_criados WHERE uid = ?", (item["uid"],))
            desfeitos += 1
            continue
        if not isinstance(id_, int):
            continue
        if entidade == "tarefa":
            # rotina recorrente: o modelo + as instancias materializadas dele
            ids = [id_] + [
                r["id"] for r in conn.execute("SELECT id FROM tasks WHERE recorrente_origem_id = ?", (id_,)).fetchall()
            ]
            marcadores = ",".join("?" for _ in ids)
            conn.execute(f"DELETE FROM subtasks WHERE task_id IN ({marcadores})", ids)
            cur = conn.execute(f"DELETE FROM tasks WHERE id IN ({marcadores})", ids)
        elif entidade in ("gasto", "renda"):
            tabela = "expenses" if entidade == "gasto" else "incomes"
            cur = conn.execute(f"DELETE FROM {tabela} WHERE id = ?", (id_,))
            if cur.rowcount and isinstance(item.get("conta_id"), int) and isinstance(item.get("delta"), (int, float)):
                db.reverter_ajuste_saldo(conn, item["conta_id"], item["delta"])
        elif entidade == "lembrete":
            cur = conn.execute("DELETE FROM lembretes WHERE id = ?", (id_,))
        elif entidade == "meta":
            conn.execute("DELETE FROM goal_deposits WHERE goal_id = ?", (id_,))
            cur = conn.execute("DELETE FROM goals WHERE id = ?", (id_,))
        # ---- Fase 6 (US-E7): modulos ligados aos cards ----
        elif entidade == "habito":
            conn.execute("DELETE FROM habito_marcacoes WHERE habito_id = ?", (id_,))
            cur = conn.execute("DELETE FROM habitos WHERE id = ?", (id_,))
        elif entidade == "habito_marcacao":
            # volta o dia exato pro estado anterior a acao (feito -> nao feito e vice-versa)
            if item.get("feito"):
                cur = conn.execute(
                    "DELETE FROM habito_marcacoes WHERE habito_id = ? AND data = ?", (id_, item.get("data"))
                )
            else:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO habito_marcacoes (data, habito_id) "
                    "SELECT ?, id FROM habitos WHERE id = ?",
                    (item.get("data"), id_),
                )
        elif entidade == "projeto":
            conn.execute("DELETE FROM projeto_etapas WHERE projeto_id = ?", (id_,))
            cur = conn.execute("DELETE FROM projetos WHERE id = ?", (id_,))
        elif entidade == "projeto_etapa":
            cur = conn.execute("DELETE FROM projeto_etapas WHERE id = ?", (id_,))
        elif entidade == "etapa_concluida":
            cur = conn.execute(
                "UPDATE projeto_etapas SET feita = 0, feita_em = NULL WHERE id = ? AND feita = 1", (id_,)
            )
        elif entidade == "viagem":
            conn.execute("DELETE FROM viagem_itens WHERE viagem_id = ?", (id_,))
            cur = conn.execute("DELETE FROM viagens WHERE id = ?", (id_,))
        elif entidade == "hidratacao":
            cur = conn.execute("DELETE FROM hidratacao_registros WHERE id = ?", (id_,))
        elif entidade == "treino":
            cur = conn.execute("DELETE FROM treinos WHERE id = ?", (id_,))
        # ---- Fase 7 (N1, ligado na C1): o Desfazer geral tambem entende os
        # tokens da N1 (financas_recorrentes.criar_token_desfazer grava
        # {"entidade", "acao", "id"} na mesma tabela) - antes a rota geral
        # marcava o token como desfeito sem reverter nada. Mesma transacao.
        elif entidade == "assinatura" and item.get("acao") == "cancelar":
            cur = conn.execute(
                "UPDATE assinatura SET ativa = 1, cancelada_em = NULL WHERE id = ? AND ativa = 0", (id_,)
            )
        elif entidade == "assinatura":
            cur = conn.execute("DELETE FROM assinatura WHERE id = ?", (id_,))
        elif entidade == "compra_parcelada":
            cur = conn.execute("DELETE FROM compra_parcelada WHERE id = ?", (id_,))
        else:
            continue
        if cur.rowcount:
            desfeitos += 1
    return desfeitos


@app.route("/api/desfazer/<token>", methods=["POST"])
def desfazer_acao(token):
    """US-E5: botao Desfazer de um card. Reverte EXATAMENTE o que foi criado
    junto com aquele token (ids gravados no momento da acao) - nunca "o
    ultimo item". Tudo ou nada numa transacao so.

    Modo visitante: 403 (revisao da Fase 6) - e o botao nem aparece
    (cards.mascarar_cards tira a action `desfazer`)."""
    recusa = _recusar_no_modo_visitante()
    if recusa:
        return recusa
    token = (token or "")[:64]
    conn = get_db()
    try:
        acao = db.obter_acao_desfazer(conn, token)
        if not acao:
            return jsonify({"error": "nada pra desfazer com esse codigo"}), 404
        if acao["desfeito_em"]:
            return jsonify({"error": "isso ja foi desfeito"}), 409
        try:
            desfeitos = _desfazer_itens(conn, acao["itens"])
        except _DesfazerRecusado as e:
            conn.rollback()
            return jsonify({"error": str(e)}), e.status
        cur = conn.execute(
            "UPDATE acoes_desfazer SET desfeito_em = datetime('now') WHERE token = ? AND desfeito_em IS NULL", (token,)
        )
        if not cur.rowcount:  # dois toques ao mesmo tempo: so um vale
            conn.rollback()
            return jsonify({"error": "isso ja foi desfeito"}), 409
        conn.commit()
        return jsonify({"ok": True, "desfeitos": desfeitos})
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _resposta_contrato(corpo: dict) -> dict:
    """Aplica o modo visitante (Fase 5, US-C19) no corpo final de chat/
    captura: o valor em dinheiro nao sai na resposta (nao so escondido no
    front) - ver cards.mascarar_visitante."""
    return cards.mascarar_visitante(corpo) if _modo_visitante_ativo() else corpo


@app.route("/api/chat", methods=["POST"])
def chat():
    body = _corpo_json()
    texto = _texto_seguro(body.get("mensagem"))
    if not texto:
        return jsonify({"error": "mensagem vazia"}), 400
    if len(texto) > TAMANHO_MAX_TEXTO_CHAT:
        return jsonify({"error": MSG_TEXTO_LONGO}), 400

    conn = get_db()
    detalhes: dict = {}
    resposta, acoes, erro = _processar_mensagem_chat(conn, texto, detalhes)
    conn.close()
    if erro:
        return jsonify({"error": erro}), 402 if erro == TETO_IA_MSG else 502
    # `resposta`/`acoes` = campos legados (frontend antigo em cache do PWA);
    # cards/resumo_texto/passos = contrato da Fase 6 (docs/CARDS.md).
    corpo = {"resposta": resposta, "acoes": acoes}
    corpo.update(detalhes or cards.envelope([], resposta, []))
    return jsonify(_resposta_contrato(corpo))


def _telegram_chat_fn(texto: str) -> str:
    """Ponte entre o bot do Telegram e o mesmo pipeline de conversa do
    /api/chat - roda numa thread separada (ver telegram_bot.iniciar_thread),
    entao abre e fecha a propria conexao com o banco em vez de compartilhar
    uma conexao do request HTTP."""
    texto = _texto_seguro(texto)
    if len(texto) > TAMANHO_MAX_TEXTO_CHAT:
        return MSG_TEXTO_LONGO
    conn = get_db()
    try:
        resposta, _acoes, erro = _processar_mensagem_chat(conn, texto)
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
    # Fase 7 (C1): polling (este bot) e webhook da N2 nunca juntos no mesmo
    # bot - telegram_captura.modo_telegram decide (flag TELEGRAM_MODO).
    modo = telegram_captura.modo_telegram()
    if not modo["polling"]:
        app.logger.info("Telegram: polling antigo desligado (%s)", modo["motivo"])
        return
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        telegram_bot.iniciar_thread(_telegram_chat_fn, callback_fn=_telegram_callback_fn)


@app.route("/api/chat/historico", methods=["GET"])
def chat_historico():
    conn = get_db()
    mensagens = list(reversed(list_chat_mensagens(conn, limit=30)))
    conn.close()
    visitante = _modo_visitante_ativo()
    for m in mensagens:
        m["cards"] = cards_de_mensagem_chat(m)
    # US-E5: card cujo Desfazer ja foi usado volta marcado como desfeito
    # (campo aditivo `desfeito` no card, docs/CARDS.md).
    tokens = [
        a.get("token")
        for m in mensagens
        for c in m["cards"]
        for a in (c.get("actions") or [])
        if isinstance(a, dict) and a.get("tipo") == "desfazer"
    ]
    conn = get_db()
    desfeitos = db.tokens_desfeitos(conn, tokens)
    conn.close()
    for m in mensagens:
        for c in m["cards"]:
            if any(isinstance(a, dict) and a.get("token") in desfeitos for a in (c.get("actions") or [])):
                c["desfeito"] = True
        # Fase 6: os cards da resposta ficam gravados junto da mensagem
        # (cards_json, criptografado em repouso como o resto do dado
        # financeiro) - recarregar a pagina nao perde os cards.
        m.pop("cards_json", None)
        if visitante and m["papel"] == "assistant":
            m["cards"] = cards.mascarar_cards(m["cards"])
            m["texto"] = cards.ocultar_valores_texto(m["texto"])
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

# Fase 5 (US-C16): avisos de rotina DOMESTICA (casa) que nao fazem sentido
# enquanto o Alex esta viajando - continuam sendo calculados normalmente,
# so nao saem enquanto o modo viagem estiver ativo (mesmo espirito do
# horario silencioso: represado, nunca marcado como notificado, entao volta
# a valer sozinho quando o modo viagem acabar).
NOTIFICACOES_ROTINA_DOMESTICA = {"rotina_manha", "hora_de_dormir", "fechamento_noturno", "manutencao"}


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


# ---- Notificacao agrupada (Fase 5, US-C4) - mesmo espirito de
# _adiar_aviso/_liberar_avisos_adiados acima (fila persistida em
# `configuracoes`), so que o gatilho pra liberar e o tempo passado
# (`agrupar_janela_min`, nao o fim do hiperfoco) e so entra na fila quem ja
# passou pelos filtros de hiperfoco/silencioso e nao e urgente - urgente
# nunca agrupa (ver verificar_e_notificar).
def _enfileirar_para_agrupar(conn, tipo: str, ref_id, titulo: str, corpo: str):
    agora_iso = datetime.now().isoformat()
    try:
        guardado = json.loads(obter_configuracao(conn, "notificacoes_agrupadas_fila") or "{}")
    except ValueError:
        guardado = {}
    itens = guardado.get("itens", [])
    if any(i[0] == tipo and i[1] == ref_id for i in itens):
        return
    inicio = guardado.get("inicio") or agora_iso
    itens.append([tipo, ref_id, titulo, corpo])
    definir_configuracao(
        conn, "notificacoes_agrupadas_fila", json.dumps({"inicio": inicio, "itens": itens[-20:]})
    )


def _fila_agrupamento_pronta(conn, janela_min: int, agora: datetime) -> list[list]:
    try:
        guardado = json.loads(obter_configuracao(conn, "notificacoes_agrupadas_fila") or "{}")
    except ValueError:
        guardado = {}
    itens = guardado.get("itens") or []
    if not itens:
        return []
    try:
        inicio = datetime.fromisoformat(guardado.get("inicio"))
    except (TypeError, ValueError):
        inicio = agora
    if (agora - inicio).total_seconds() / 60 < janela_min:
        return []
    definir_configuracao(conn, "notificacoes_agrupadas_fila", "{}")
    return itens


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
        if m["tipo"] == "carro" or m["dias_ate"] > 7:
            continue
        ref = vida.id_estavel("manutencao", m["id"], m["proxima"])
        if ja_notificado_alguma_vez(conn, "manutencao", ref):
            continue
        quando = "ja passou do prazo" if m["dias_ate"] < 0 else "vence hoje" if m["dias_ate"] == 0 else f"vence em {m['dias_ate']} dia(s)"
        avisos.append(("manutencao", ref, "Manutencao", f"{m['item']}: {quando}."))

    # Manutencao de carro por km ou data (US-C14/Fase 6 US-E1a) - mesma
    # secao/tabela unificada acima, so que tipo='carro' e HISTORICO (uma
    # linha nova a cada vez), nao edicao no lugar - por isso o aviso e
    # calculado separado (so o registro mais recente de cada item importa).
    for m in _manutencoes_carro_proximas(conn, hoje):
        ref = vida.id_estavel("manutencao_veiculo", m["id"], m["proxima_em_km"], m["proxima_em_data"])
        if ja_notificado_alguma_vez(conn, "manutencao_veiculo", ref):
            continue
        avisos.append(("manutencao_veiculo", ref, "Manutencao do veiculo", f"{m['item']}: {m['motivo']}."))

    # Garantia perto de vencer (US-C18) - dedup pela propria coluna
    # `notificado` da garantia (ver notificacoes.garantias_vencendo), marcada
    # depois de mandar de verdade (ver o loop de envio em verificar_e_notificar).
    for garantia_id, msg in notificacoes.garantias_vencendo(conn):
        avisos.append(("garantia_vencendo", garantia_id, "Garantia vencendo", msg))

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


def _avisos_proatividade_e8(conn, agora: datetime) -> list[tuple[str, int, str, str]]:
    """Fase 6 (US-E8): proatividade unificada - so MONTA (tipo, ref, titulo,
    corpo) a partir do que notificacoes.py ja calculou (cada checagem la
    reusa o mesmo calculo que a tela/API correspondente ja usa - nada
    recalculado aqui). O despacho de verdade (silencioso/hiperfoco/modo
    viagem/agrupamento) continua so em verificar_e_notificar, nao existe
    caminho paralelo de envio pra esses avisos."""
    avisos = []
    hoje = agora.date()

    for habito_id, msg in notificacoes.habitos_passaram_batido(conn, agora):
        if not ja_notificou_hoje(conn, "habito_passou_batido", habito_id):
            avisos.append(("habito_passou_batido", habito_id, "Passou batido", msg))

    for tarefa_id, msg in notificacoes.tarefas_horario_passou(conn, agora):
        if not ja_notificou_hoje(conn, "tarefa_horario_passou", tarefa_id):
            avisos.append(("tarefa_horario_passou", tarefa_id, "Passou da hora", msg))

    for conta_id, nivel, titulo, corpo in notificacoes.cartoes_perto_ou_estourados(conn, hoje):
        ref = vida.id_estavel("cartao_limite", conta_id, nivel, hoje.strftime("%Y-%m"))
        if not ja_notificado_alguma_vez(conn, "cartao_limite", ref):
            avisos.append(("cartao_limite", ref, titulo, corpo))

    renda_aviso = notificacoes.renda_perto_de_acabar(conn, hoje)
    if renda_aviso:
        nivel, titulo, corpo = renda_aviso
        ref = vida.id_estavel("renda_comprometida", nivel, hoje.strftime("%Y-%m"))
        if not ja_notificado_alguma_vez(conn, "renda_comprometida", ref):
            avisos.append(("renda_comprometida", ref, titulo, corpo))

    for ref, titulo, corpo in notificacoes.projetos_juntando_poeira(conn, hoje):
        if not ja_notificado_alguma_vez(conn, "projeto_poeira", ref):
            avisos.append(("projeto_poeira", ref, titulo, corpo))

    if notificacoes.projecao_mes_seguinte_devida(hoje):
        resultado = notificacoes.mes_seguinte_apertado(conn, hoje)
        if resultado:
            nome_mes, fracao = resultado
            pct = round(fracao * 100)
            ref = vida.id_estavel("mes_seguinte_apertado", nome_mes, hoje.year)
            if not ja_notificado_alguma_vez(conn, "mes_seguinte_apertado", ref):
                avisos.append(
                    (
                        "mes_seguinte_apertado",
                        ref,
                        f"{nome_mes} vem apertado",
                        f"custos fixos ja comprometem {pct}%.",
                    )
                )

    return avisos


def _briefing_noite_p3_substitui_fechamento(conn) -> bool:
    """Fase 7 (C1): True quando o briefing da noite da P3 (assistente/
    briefing.py, item "briefing" da Caixa, push pelo /api/tick) e quem fala
    com o Alex a noite - ai o push antigo `fechamento_noturno` fica calado pra
    nao chegar 2 pushes parecidos as 21h. Precisa das duas coisas: a flag
    `assistente.p3.ativo` ligada (padrao) E o tick configurado
    (PAINEL_TICK_TOKEN) - sem tick o briefing nunca sai, entao o fechamento
    antigo continua. Qualquer erro -> False (mantem o aviso antigo)."""
    if not os.environ.get("PAINEL_TICK_TOKEN"):
        return False
    try:
        from assistente import briefing as briefing_p3

        return bool(briefing_p3.ativo(conn))
    except Exception:  # noqa: BLE001
        app.logger.exception("C1: falha ao consultar a flag do briefing da P3")
        return False


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

    # Teto mensal de gasto com a API da IA (US-A6) - uma vez por nivel+mes,
    # mesma ideia do orcamento por categoria acima.
    teto_ia_aviso = notificacoes.teto_ia_perto_ou_estourado(conn)
    if teto_ia_aviso:
        nivel_ia, msg_ia = teto_ia_aviso
        ref_id = _id_estavel_teto_ia(nivel_ia, ano_mes_atual)
        if not ja_notificado_alguma_vez(conn, "teto_ia", ref_id):
            titulo_ia = "Teto de IA estourado" if nivel_ia == "estourado" else "Teto de IA quase no limite"
            avisos.append(("teto_ia", ref_id, titulo_ia, msg_ia))

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

    # Mesmo mecanismo acima, outro angulo: um gasto INDIVIDUAL bem acima da
    # media+desvio-padrao da propria categoria, mesmo que o dia inteiro nao
    # tenha estourado (US-C17). Dedup por gasto (ja_notificado_alguma_vez -
    # o mesmo gasto nunca precisa avisar de novo).
    for gasto_id, msg in notificacoes.gastos_fora_do_padrao_categoria(conn):
        if not ja_notificado_alguma_vez(conn, "gasto_categoria_atipico", gasto_id):
            avisos.append(("gasto_categoria_atipico", gasto_id, "Gasto fora do padrao da categoria", msg))

    for lembrete_id, msg in notificacoes.lembretes_proximos(conn):
        if not ja_notificou_hoje(conn, "lembrete_proximo", lembrete_id):
            avisos.append(("lembrete_proximo", lembrete_id, "Data importante chegando", msg))

    # Fase 6 (US-E3): "Desperta voce" ligado no card de lembrete - push no
    # horario do proprio dia (uma vez por dia; recorrente anual repete no
    # ano seguinte).
    for lembrete_id, msg in notificacoes.lembretes_para_despertar(conn):
        if not ja_notificou_hoje(conn, "lembrete_despertar", lembrete_id):
            avisos.append(("lembrete_despertar", lembrete_id, "Lembrete", msg))

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
        # Semana pesada (US-C13) - junto do mesmo momento de planejamento
        # semanal (domingo a noite), avisa com antecedencia se a semana que
        # vem ja esta bem acima do padrao historico do proprio usuario.
        msg_semana_pesada = notificacoes.semana_pesada_aviso(conn)
        if msg_semana_pesada and not ja_notificou_hoje(conn, "semana_pesada"):
            avisos.append(("semana_pesada", 0, "Semana pesada pela frente", msg_semana_pesada))

    if notificacoes.hora_de_dormir_devida() and not ja_notificou_hoje(conn, "hora_de_dormir"):
        itens_noite = ", ".join(i["texto"].lower() for i in list_rotina_itens(conn, "noite"))
        corpo_noite = "22h - comeca a desacelerar pro sono."
        if itens_noite:
            corpo_noite += f" Rotina da noite: {itens_noite}."
        avisos.append(("hora_de_dormir", 0, "Hora de desacelerar", corpo_noite))

    avisos.extend(_avisos_assistente_vida(conn, datetime.now()))
    avisos.extend(_avisos_fase2(conn, datetime.now()))
    avisos.extend(_avisos_fase3(conn, datetime.now()))
    avisos.extend(_avisos_proatividade_e8(conn, datetime.now()))

    # Fechamento ativo do dia (21h, uma hora antes da hora_de_dormir) - manda
    # o fechamento sozinho em vez de esperar o Alex abrir a aba Painel.
    # Fase 7 (C1): com o briefing da noite da P3 valendo (flag
    # assistente.p3.ativo + tick configurado), o fechamento antigo sai de cena
    # - o briefing da P3 ja traz o mesmo fechamento e sai por push pela Caixa.
    if (
        notificacoes.fechamento_noturno_devido()
        and not _briefing_noite_p3_substitui_fechamento(conn)
        and not ja_notificou_hoje(conn, "fechamento_noturno")
    ):
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
            quando = _quando_conta_construtora(dias_ate, passado="venceu ha")
            # C1: so nome e tempo ate vencer (valor nunca de bandeja no push).
            avisos.append((
                "conta_a_vencer",
                ref_id,
                "Conta a pagar (construtora)",
                f"{quem} - {quando}.",
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
    em_viagem = viagem.modo_viagem_ativo(_modo_viagem_estado(conn), date.today())

    # Fase 5 (US-C4): notificacao agrupada - desligada por padrao (ver
    # /api/configuracoes/silencio), pra nao mudar o comportamento de quem
    # nunca configurou isso. Urgente nunca agrupa, sempre vai na hora.
    agrupar_ligado = (obter_configuracao(conn, "notificacoes_agrupar") or "0") == "1"
    agrupar_janela_min = int(obter_configuracao(conn, "notificacoes_agrupar_janela_min") or "2")

    def _despachar(titulo: str, corpo: str, botoes=None):
        for s in subs:
            sub_dict = json.loads(s["subscription_json"])
            ok = push_client.enviar(sub_dict, titulo, corpo)
            if not ok:
                delete_push_subscription(conn, s["endpoint"])
        if telegram_ok:
            telegram_bot.enviar_mensagem(f"{titulo}\n{corpo}", botoes=botoes)

    enviados = 0
    for tipo, ref_id, titulo, corpo in avisos:
        # Fase 7 (P8): tipo desligado na tela Assistente > Avisos nao sai.
        # So o liga/desliga: o silencio continua sendo o de baixo (que deixa
        # passar urgente); aviso_permitido() completo calaria urgente a noite.
        if not avisos_assistente.esta_ligado(tipo, conn=conn):
            continue
        if em_hiperfoco and tipo not in vida.CRITICOS_HIPERFOCO:
            if tipo in vida.AVISOS_JANELA_CURTA:
                _adiar_aviso(conn, tipo, titulo, corpo)
                marcar_notificado(conn, tipo, ref_id)
            continue
        if silencioso and tipo not in NOTIFICACOES_URGENTES:
            continue
        if em_viagem and tipo in NOTIFICACOES_ROTINA_DOMESTICA:
            continue
        if agrupar_ligado and tipo not in NOTIFICACOES_URGENTES:
            _enfileirar_para_agrupar(conn, tipo, ref_id, titulo, corpo)
            continue
        # tarefa_parada ganha um botao de acao direto na notificacao - marca
        # como feita com um toque, sem precisar abrir o app nem digitar nada
        # (o pedido especifico do Alex pra esse canal).
        botoes = [("Marcar como feito", f"completar_tarefa:{ref_id}")] if tipo == "tarefa_parada" else None
        _despachar(titulo, corpo, botoes)
        marcar_notificado(conn, tipo, ref_id)
        if tipo == "garantia_vencendo":
            marcar_garantia_notificada(conn, ref_id)
        if tipo in ("tarefa_parada", "espera_parada"):
            registrar_interacao_aprendizado(conn, tipo, ref_id)
        enviados += 1

    if agrupar_ligado:
        prontos = _fila_agrupamento_pronta(conn, agrupar_janela_min, datetime.now())
        if prontos:
            titulo_agrupado, corpo_agrupado = notificacoes.montar_mensagem_agrupada(
                [(t, c) for _, _, t, c in prontos]
            )
            _despachar(titulo_agrupado, corpo_agrupado)
            for tipo_original, ref_id_original, _, _ in prontos:
                marcar_notificado(conn, tipo_original, ref_id_original)
                if tipo_original in ("tarefa_parada", "espera_parada"):
                    registrar_interacao_aprendizado(conn, tipo_original, ref_id_original)
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


@app.route("/api/memorias", methods=["POST"])
def criar_memoria_rota():
    """Fase 6 (US-E10): cria uma memoria - com `categoria` (um dos 3 grupos
    fixos de "O que eu lembro sobre voce": sua_rotina/seus_planos/
    fora_do_painel) quando adicionada por um dos formularios de grupo, ou
    sem categoria (generica, mesmo caminho que `registrar_memoria` do chat
    ja usava) quando omitida.

    Modo visitante: 403 (revisao da Fase 6) - memoria entra no system prompt
    do chat, seria uma injecao persistente."""
    recusa = _recusar_no_modo_visitante()
    if recusa:
        return recusa
    body = _corpo_json()
    texto = _texto_curto(body.get("texto"), 500)
    if not texto:
        return jsonify({"error": "informe o texto"}), 400
    categoria = body.get("categoria")
    if categoria is not None and categoria not in CATEGORIAS_MEMORIA:
        return jsonify({"error": "categoria invalida"}), 400
    conn = get_db()
    memoria_id = create_memoria(conn, texto, None, categoria)
    conn.close()
    return jsonify({"ok": True, "memoria_id": memoria_id}), 201


@app.route("/api/memorias/<int:memoria_id>", methods=["PUT"])
def editar_memoria_rota(memoria_id):
    """Fase 6 (US-E10): edicao no lugar do texto (categoria/source_text nao
    mudam) - os 3 grupos fixos e a lista generica sao editaveis na tela."""
    recusa = _recusar_no_modo_visitante()
    if recusa:
        return recusa
    body = _corpo_json()
    texto = _texto_curto(body.get("texto"), 500)
    if not texto:
        return jsonify({"error": "informe o texto"}), 400
    conn = get_db()
    ok = update_memoria(conn, memoria_id, texto)
    conn.close()
    if not ok:
        return jsonify({"error": "memoria nao encontrada"}), 404
    return jsonify({"ok": True})


@app.route("/api/memorias/<int:memoria_id>", methods=["DELETE"])
def apagar_memoria(memoria_id):
    recusa = _recusar_no_modo_visitante()
    if recusa:
        return recusa
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


# ---- Diario de decisao (Fase 5, US-C2) - NAO confundir com a tabela
# `decisoes` (Fase 1, "vale a pena?" com pros/contras da IA, efemera) - esta
# aqui e um diario persistente (decisao + contexto + resultado revisado
# depois), dai o nome diferente (diario_decisoes) em db.py e as rotas
# proprias abaixo.
@app.route("/api/diario-decisoes", methods=["GET"])
def diario_decisoes():
    if _modo_visitante_ativo():
        return jsonify([])
    conn = get_db()
    resultado = list_diario_decisoes(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/diario-decisoes", methods=["POST"])
def criar_diario_decisao():
    if _modo_visitante_ativo():
        return jsonify({"error": "desative o modo visitante pra usar o diario de decisao"}), 403
    body = _corpo_json()
    decisao = _texto_seguro(body.get("decisao"))
    if not decisao:
        return jsonify({"error": "informe a decisao"}), 400
    contexto = _texto_seguro(body.get("contexto")) or None
    revisao_em = _texto_seguro(body.get("revisao_em")) or None

    conn = get_db()
    decisao_id = create_diario_decisao(conn, decisao, contexto, revisao_em)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"id": decisao_id, "ok": True}), 201


@app.route("/api/diario-decisoes/<int:decisao_id>/resultado", methods=["POST"])
def registrar_resultado_diario_decisao_rota(decisao_id):
    if _modo_visitante_ativo():
        return jsonify({"error": "desative o modo visitante pra usar o diario de decisao"}), 403
    body = _corpo_json()
    resultado = _texto_seguro(body.get("resultado"))
    if not resultado:
        return jsonify({"error": "informe o resultado"}), 400

    conn = get_db()
    ok = registrar_resultado_diario_decisao(conn, decisao_id, resultado)
    conn.close()
    if not ok:
        return jsonify({"error": "decisao nao encontrada"}), 404
    return jsonify({"ok": True})


@app.route("/api/diario-decisoes/<int:decisao_id>", methods=["DELETE"])
def apagar_diario_decisao_rota(decisao_id):
    conn = get_db()
    apagar_diario_decisao(conn, decisao_id)
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


@app.route("/api/lembretes/<int:lembrete_id>/despertar", methods=["POST"])
def despertar_lembrete(lembrete_id):
    """Fase 6 (US-E3, botao "Desperta voce" do card de lembrete): liga/
    desliga um push NO HORARIO do lembrete (hora, ou 09:00 quando o lembrete
    e so por dia) - o PWA nao consegue tocar alarme de verdade, entao o
    "despertar" e a notificacao push (ver notificacoes.lembretes_para_despertar)."""
    ativo = _corpo_json().get("ativo", True)
    if not isinstance(ativo, bool):
        return jsonify({"error": "ativo deve ser true ou false"}), 400
    conn = get_db()
    ok = db.definir_despertar_lembrete(conn, lembrete_id, ativo)
    conn.close()
    if not ok:
        return jsonify({"error": "lembrete nao encontrado"}), 404
    return jsonify({"ok": True, "ativo": ativo})


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


@app.route("/api/esperas/<int:espera_id>/importante", methods=["POST"])
def marcar_espera_importante_rota(espera_id):
    """Fase 5 (US-C5): marca/desmarca uma espera pendente como importante -
    entra no calculo de prioridade de quem responder primeiro (ver
    /api/esperas/prioridade e vida.priorizar_esperas)."""
    body = _corpo_json()
    importante = bool(body.get("importante", True))
    conn = get_db()
    ok = marcar_espera_importante(conn, espera_id, importante)
    conn.close()
    if not ok:
        return jsonify({"error": "espera nao encontrada"}), 404
    return jsonify({"ok": True, "importante": importante})


@app.route("/api/esperas/prioridade", methods=["GET"])
def esperas_priorizadas():
    """Fase 5 (US-C5): quem responder primeiro entre as esperas pendentes -
    reaproveita a mesma tabela/logica de list_esperas_pendentes (TODO #76),
    so ordena por vida.priorizar_esperas (tempo parado + importancia) em vez
    da ordem de criacao que /api/esperas devolve."""
    conn = get_db()
    esperas = list_esperas_pendentes(conn)
    conn.close()
    return jsonify(vida.priorizar_esperas(esperas, date.today()))


# ---- Brain dump (Fase 5, US-C6) - despejo rapido de pensamento solto, sem
# classificar em tarefa/nota/gasto na hora; classifica depois com calma.
@app.route("/api/brain-dump", methods=["GET"])
def brain_dump_pendentes():
    conn = get_db()
    resultado = list_brain_dump_pendentes(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/brain-dump", methods=["POST"])
def capturar_brain_dump():
    body = _corpo_json()
    texto = _texto_seguro(body.get("texto"))
    if not texto:
        return jsonify({"error": "manda algum texto"}), 400
    if len(texto) > TAMANHO_MAX_TEXTO_CHAT:
        return jsonify({"error": MSG_TEXTO_LONGO}), 400

    conn = get_db()
    item_id = create_brain_dump(conn, texto)
    _marcar_atividade(conn)
    conn.commit()
    conn.close()
    return jsonify({"id": item_id, "ok": True}), 201


@app.route("/api/brain-dump/<int:item_id>/converter", methods=["POST"])
def converter_brain_dump(item_id):
    """Converte um item pendente em tarefa/nota/gasto de verdade -
    reaproveita create_nota (ja existente) e dois inserts minimos pra tarefa/
    gasto (criar_tarefa_de_brain_dump/criar_gasto_de_brain_dump, mesmo
    formato das rotas que ja existem pra cada tipo, so sem passar pela
    classificacao por IA - o Alex ja escolheu o tipo na hora de converter).

    Fase 6 (US-E6): tipo "assistente" manda o texto inteiro pro MESMO
    pipeline do chat (_processar_mensagem_chat - tool-use + cards), entao um
    despejo com viagem, gastos, salario, habito, lembrete e reuniao
    misturados vira um card por item + resumo_final, com Desfazer
    independente em cada card. Toda saida (qualquer tipo) segue o contrato
    de docs/CARDS.md, alem dos campos antigos (ok/tipo/id).

    Modo visitante: 403 (revisao da Fase 6) - cria gasto/tarefa/evento de
    uma vez."""
    recusa = _recusar_no_modo_visitante()
    if recusa:
        return recusa
    body = _corpo_json()
    tipo = body.get("tipo")
    if tipo not in ("tarefa", "nota", "gasto", "assistente"):
        return jsonify({"error": "tipo precisa ser tarefa, nota, gasto ou assistente"}), 400

    conn = get_db()
    item = obter_brain_dump(conn, item_id)
    if not item:
        conn.close()
        return jsonify({"error": "item nao encontrado"}), 404
    if item["processado"]:
        conn.close()
        return jsonify({"error": "item ja foi processado"}), 400

    if tipo == "assistente":
        # reserva o item ANTES da IA (dois toques ao mesmo tempo nao
        # processam o mesmo despejo duas vezes); devolve se a IA falhar.
        if not marcar_brain_dump_processado(conn, item_id):
            conn.close()
            return jsonify({"error": "item ja foi processado"}), 400
        detalhes: dict = {}
        resposta, acoes, erro = _processar_mensagem_chat(conn, item["texto"], detalhes)
        if erro:
            conn.execute("UPDATE brain_dump SET processado = 0 WHERE id = ?", (item_id,))
            conn.commit()
            conn.close()
            return jsonify({"error": erro}), 402 if erro == TETO_IA_MSG else 502
        _marcar_atividade(conn)
        conn.commit()
        conn.close()
        corpo = {"ok": True, "tipo": tipo, "resposta": resposta, "acoes": acoes}
        corpo.update(detalhes or cards.envelope([], resposta, []))
        return jsonify(_resposta_contrato(corpo))

    inicio = time.perf_counter()
    efeitos = []
    if tipo == "tarefa":
        titulo = _texto_seguro(body.get("titulo")) or item["texto"]
        novo_id = criar_tarefa_de_brain_dump(
            conn, titulo, body.get("due_date"), _normalizar_hora(body.get("hora")), item["texto"]
        )
        efeitos.append({"entidade": "tarefa", "id": novo_id})
        passo = {"modulo": "Tarefas", "descricao": f'Criou a tarefa "{cards._titulo_curto(titulo)}"'}
        resumo = "Virou tarefa."
    elif tipo == "nota":
        titulo = _texto_seguro(body.get("titulo")) or item["texto"][:60]
        novo_id = create_nota(conn, titulo, body.get("corpo") or item["texto"], source_text=item["texto"])
        passo = {"modulo": "Notas", "descricao": f'Salvou a nota "{cards._titulo_curto(titulo)}"'}
        resumo = "Virou nota."
    else:
        valor = body.get("valor")
        if not isinstance(valor, (int, float)) or isinstance(valor, bool) or not math.isfinite(valor) or valor <= 0:
            conn.close()
            return jsonify({"error": "informe um valor valido pro gasto"}), 400
        descricao = _texto_seguro(body.get("titulo")) or item["texto"]
        novo_id = criar_gasto_de_brain_dump(conn, valor, body.get("categoria"), descricao, item["texto"])
        efeitos.append({"entidade": "gasto", "id": novo_id})
        passo = {"modulo": "Finanças", "descricao": f'Registrou o gasto "{cards._titulo_curto(descricao)}"'}
        resumo = "Virou gasto."
    passo["ms"] = int(round((time.perf_counter() - inicio) * 1000))

    marcar_brain_dump_processado(conn, item_id)
    _marcar_atividade(conn)
    corpo = {"ok": True, "tipo": tipo, "id": novo_id}
    corpo.update(cards.montar_resposta(conn, efeitos, resumo, [passo], _criar_token_desfazer(conn)))
    conn.commit()
    conn.close()
    return jsonify(_resposta_contrato(corpo))


@app.route("/api/brain-dump/<int:item_id>", methods=["DELETE"])
def apagar_brain_dump_rota(item_id):
    conn = get_db()
    apagar_brain_dump(conn, item_id)
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
    if _modo_visitante_ativo():
        return jsonify(
            {"dados": None, "hidratacao_hoje": None, "dica_sono": None, "dica_humor": None, "oculto": True}
        )
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
    if _modo_visitante_ativo():
        return jsonify([])
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


# ---- Fase 6 (US-E12): modulo Habitos - NOVO, separado da Rotina guiada ----
# (rotina_itens/rotina_marcacoes acima e so a rotina manha/noite; decisao do
# Alex de nao misturar os dois conceitos). Habito NAO e dado financeiro nem
# sensivel -> decisao documentada: NAO respeita _modo_visitante_ativo() (ao
# contrario das rotas de bancos/cartao logo abaixo, que respeitam).

def _semana_atual_intervalo(hoje: date) -> tuple[str, str]:
    inicio = hoje - timedelta(days=hoje.weekday())
    return inicio.isoformat(), (inicio + timedelta(days=6)).isoformat()


def _habito_detalhado(conn, habito: dict, hoje: date) -> dict:
    dias = vida.ultimos_n_dias(hoje, 7)
    marcados_7 = marcacoes_habito_no_periodo(conn, habito["id"], dias[0].isoformat(), dias[-1].isoformat())
    ini_semana, fim_semana = _semana_atual_intervalo(hoje)
    vezes_feitas_semana = len(marcacoes_habito_no_periodo(conn, habito["id"], ini_semana, fim_semana))
    feito_hoje = hoje.isoformat() in marcados_7
    return {
        "id": habito["id"],
        "nome": habito["nome"],
        "meta": habito["meta"],
        "frequencia_tipo": habito["frequencia_tipo"],
        "dias_semana": sorted(vida.parse_dias_semana(habito["dias_semana"])),
        "vezes_por_semana": habito["vezes_por_semana"],
        "horario": habito["horario"],
        "ultimos_7": [
            {"data": d.isoformat(), "letra": vida.letra_dia_semana(d), "feito": d.isoformat() in marcados_7, "hoje": d == hoje}
            for d in dias
        ],
        "feito_hoje": feito_hoje,
        "vezes_feitas_semana": vezes_feitas_semana,
        "devido_hoje": vida.habito_devido_em(habito, hoje, vezes_feitas_semana),
        "passou_batido": vida.habito_passou_batido(habito, datetime.now(), feito_hoje, vezes_feitas_semana),
    }


@app.route("/api/habitos", methods=["GET"])
def habitos_rota():
    conn = get_db()
    resultado = [_habito_detalhado(conn, h, date.today()) for h in list_habitos(conn)]
    conn.close()
    return jsonify({"habitos": resultado, "ativos_total": len(resultado)})


def _criar_habito(conn, nome, meta, frequencia_tipo, dias_semana, vezes_por_semana, horario) -> dict:
    nome = _texto_curto(nome, 80)
    if not nome:
        return {"erro": "informe o nome do habito"}
    if frequencia_tipo not in ("diario", "dias_semana", "n_vezes_semana"):
        frequencia_tipo = "diario"
    dias_csv, vezes = None, None
    if frequencia_tipo == "dias_semana":
        if isinstance(dias_semana, list):
            candidatos = dias_semana
        elif isinstance(dias_semana, str):
            candidatos = dias_semana.split(",")
        else:
            candidatos = []
        validos = sorted({int(d) for d in candidatos if str(d).strip().lstrip("-").isdigit() and 0 <= int(d) <= 6})
        if not validos:
            return {"erro": "informe os dias da semana (0=segunda a 6=domingo)"}
        dias_csv = ",".join(str(d) for d in validos)
    elif frequencia_tipo == "n_vezes_semana":
        vezes = _inteiro_no_intervalo(vezes_por_semana, 1, 7)
        if vezes is None:
            return {"erro": "informe quantas vezes por semana (1 a 7)"}
    habito_id = create_habito(
        conn, nome, _texto_curto(meta, 60), frequencia_tipo, dias_csv, vezes, _normalizar_hora(horario)
    )
    return {"ok": True, "habito_id": habito_id}


@app.route("/api/habitos", methods=["POST"])
def criar_habito_rota():
    body = _corpo_json()
    conn = get_db()
    resultado = _criar_habito(
        conn, body.get("nome"), body.get("meta"), body.get("frequencia_tipo"),
        body.get("dias_semana"), body.get("vezes_por_semana"), body.get("horario"),
    )
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201


@app.route("/api/habitos/<int:habito_id>", methods=["DELETE"])
def apagar_habito_rota(habito_id):
    conn = get_db()
    delete_habito(conn, habito_id)
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/habitos/<int:habito_id>/marcar", methods=["POST"])
def marcar_habito_rota(habito_id):
    conn = get_db()
    if not get_habito(conn, habito_id):
        conn.close()
        return jsonify({"error": "habito nao encontrado"}), 404
    feito = alternar_habito_dia(conn, date.today().isoformat(), habito_id)
    conn.close()
    return jsonify({"feito": feito})


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
        _log_usage(conn, usage, "essencial_dia")
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
    if _modo_visitante_ativo():
        return jsonify({"error": "desative o modo visitante pra usar o diario de decisao"}), 403
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
    _log_usage(conn, usage, "decisao")
    decisao_id = create_decisao(conn, pergunta, json.dumps(analise, ensure_ascii=False))
    conn.close()
    return jsonify({"id": decisao_id, "pergunta": pergunta, "analise": analise})


@app.route("/api/decisoes", methods=["GET"])
def decisoes():
    if _modo_visitante_ativo():
        return jsonify([])
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


def _modo_viagem_estado(conn) -> dict:
    """Fase 5 (US-C16): estado persistido em `configuracoes` (mesmo padrao de
    `avisos_adiados`/`hiperfoco_ate`) - precisa sobreviver a reinicio do
    processo, ja que quem le esse estado e o scheduler (`verificar_e_notificar`),
    nao so uma sessao de navegador aberta."""
    padrao = {"ativo": False, "data_inicio": None, "data_fim": None}
    try:
        salvo = json.loads(obter_configuracao(conn, "modo_viagem") or "{}")
    except ValueError:
        salvo = {}
    return {**padrao, **salvo}


def _salvar_modo_viagem(conn, ativo: bool, data_inicio: str | None, data_fim: str | None) -> dict:
    estado = {"ativo": bool(ativo), "data_inicio": data_inicio, "data_fim": data_fim}
    definir_configuracao(conn, "modo_viagem", json.dumps(estado))
    return estado


@app.route("/api/modo-viagem", methods=["GET"])
def modo_viagem_rota():
    conn = get_db()
    estado = _modo_viagem_estado(conn)
    conn.close()
    return jsonify({**estado, "ativo_agora": viagem.modo_viagem_ativo(estado, date.today())})


@app.route("/api/modo-viagem", methods=["POST"])
def salvar_modo_viagem_rota():
    body = _corpo_json()
    ativo = bool(body.get("ativo"))
    data_inicio = _data_iso_valida(body.get("data_inicio")) if body.get("data_inicio") else None
    data_fim = _data_iso_valida(body.get("data_fim")) if body.get("data_fim") else None
    if body.get("data_inicio") and not data_inicio:
        return jsonify({"error": "data de inicio invalida (AAAA-MM-DD)"}), 400
    if body.get("data_fim") and not data_fim:
        return jsonify({"error": "data de fim invalida (AAAA-MM-DD)"}), 400
    if data_inicio and data_fim and data_fim < data_inicio:
        return jsonify({"error": "data de fim invalida (tem que ser depois do inicio)"}), 400
    conn = get_db()
    estado = _salvar_modo_viagem(conn, ativo, data_inicio, data_fim)
    conn.close()
    return jsonify({**estado, "ativo_agora": viagem.modo_viagem_ativo(estado, date.today())})


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
        # US-F11: linha do tempo de planejamento direto na lista (evita ida
        # extra ao /como-projeto so pra desenhar os marcos na tela de Viagens).
        "marcos_planejamento": vida.marcos_planejamento_viagem(ida, bool(v.get("internacional"))),
        "aviso_regra_pratica": vida.AVISO_REGRA_PRATICA,
    }


@app.route("/api/viagens", methods=["GET"])
def viagens():
    hoje = date.today()
    conn = get_db()
    resultado = [_viagem_detalhada(conn, v, hoje) for v in list_viagens_futuras(conn, hoje.isoformat())]
    conn.close()
    return jsonify(resultado)


def _criar_viagem(conn, destino, data_ida, data_volta, motivo, internacional=False) -> dict:
    destino = _texto_curto(destino, 80)
    ida = _data_iso_valida(data_ida)
    volta = _data_iso_valida(data_volta) if data_volta not in (None, "") else None
    if not destino or not ida:
        return {"erro": "informe o destino e a data de ida (AAAA-MM-DD)"}
    if data_volta not in (None, "") and (not volta or volta < ida):
        return {"erro": "data de volta invalida (tem que ser depois da ida)"}
    viagem_id = create_viagem(conn, destino, ida, volta, _texto_curto(motivo, 80), bool(internacional))
    return {"ok": True, "viagem_id": viagem_id}


@app.route("/api/viagens", methods=["POST"])
def criar_viagem_rota():
    body = _corpo_json()
    conn = get_db()
    resultado = _criar_viagem(
        conn,
        body.get("destino"),
        body.get("data_ida"),
        body.get("data_volta"),
        body.get("motivo"),
        body.get("internacional"),
    )
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201


@app.route("/api/viagens/<int:viagem_id>/numero-voo", methods=["POST"])
def definir_numero_voo_viagem_rota(viagem_id):
    """US-F12: o Alex preenche o numero do voo comprado (ex: "LA3251") depois
    da compra - so registra o numero, a consulta de status em si e
    GET /api/viagens/<id>/voo-status (voo_status.py, cacheada)."""
    body = _corpo_json()
    numero = _texto_curto(body.get("numero_voo"), 12)
    numero = numero.upper().replace(" ", "") if numero else None
    conn = get_db()
    ok = definir_numero_voo_viagem(conn, viagem_id, numero)
    conn.close()
    if not ok:
        return jsonify({"error": "viagem nao encontrada"}), 404
    return jsonify({"ok": True, "numero_voo": numero})


@app.route("/api/viagens/<int:viagem_id>/voo-status", methods=["GET"])
def viagem_voo_status_rota(viagem_id):
    """US-F12: status do voo comprado (voo_status.py, cacheado - nunca chama
    a API de novo dentro da janela de cache). Sem numero_voo cadastrado ou
    sem AVIATIONSTACK_API_KEY, volta so o suficiente pra tela mostrar o
    aviso certo, sem tentar rede nenhuma."""
    conn = get_db()
    registro = conn.execute("SELECT * FROM viagens WHERE id = ?", (viagem_id,)).fetchone()
    if not registro:
        conn.close()
        return jsonify({"error": "viagem nao encontrada"}), 404
    numero_voo = registro["numero_voo"]
    if not numero_voo:
        conn.close()
        return jsonify({"configurado": voo_status.configurado(), "erro": "informe o numero do voo primeiro"})
    resultado = voo_status.status_voo(
        numero_voo,
        registro["data_ida"],
        lambda nv, d: obter_status_voo_cache(conn, nv, d),
        lambda nv, d, j: salvar_status_voo_cache(conn, nv, d, j),
    )
    conn.close()
    return jsonify(resultado)


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
    _log_usage(conn, usage, "mala_viagem")
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


# ---- Fase 6 (US-E13): modulo Projetos generico -----------------------------
# Viagens NAO migram pra ca (decisao do Alex) - ver
# /api/viagens/<id>/como-projeto abaixo, que so EMPRESTA o formato via
# vida.converter_viagem_para_projeto pro card reaproveitar o visual, sem
# duplicar dado (le direto de viagens/viagem_itens toda vez).

def _projeto_detalhado(conn, projeto: dict, hoje: date) -> dict:
    return vida.projeto_detalhado(projeto, list_etapas_projeto(conn, projeto["id"]), hoje)


@app.route("/api/projetos", methods=["GET"])
def projetos_rota():
    conn = get_db()
    resultado = [_projeto_detalhado(conn, p, date.today()) for p in list_projetos(conn)]
    conn.close()
    return jsonify(resultado)


def _criar_projeto(conn, nome, prazo_final) -> dict:
    nome = _texto_curto(nome, 120)
    if not nome:
        return {"erro": "informe o nome do projeto"}
    prazo = None
    if prazo_final not in (None, ""):
        prazo = _data_iso_valida(prazo_final)
        if not prazo:
            return {"erro": "prazo invalido (AAAA-MM-DD)"}
    projeto_id = create_projeto(conn, nome, prazo)
    return {"ok": True, "projeto_id": projeto_id}


@app.route("/api/projetos", methods=["POST"])
def criar_projeto_rota():
    body = _corpo_json()
    conn = get_db()
    resultado = _criar_projeto(conn, body.get("nome"), body.get("prazo_final"))
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201


@app.route("/api/projetos/<int:projeto_id>", methods=["DELETE"])
def apagar_projeto_rota(projeto_id):
    conn = get_db()
    delete_projeto(conn, projeto_id)
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/projetos/<int:projeto_id>/status", methods=["POST"])
def definir_status_projeto_rota(projeto_id):
    status = _corpo_json().get("status")
    conn = get_db()
    ok = definir_status_projeto(conn, projeto_id, status)
    conn.close()
    if not ok:
        return jsonify({"error": "projeto nao encontrado ou status invalido (no_rumo/atrasado/pausado)"}), 400
    return jsonify({"ok": True})


def _adicionar_etapa(conn, projeto_id, texto, data_prevista) -> dict:
    texto = _texto_curto(texto, 200)
    if not texto:
        return {"erro": "informe o texto da etapa"}
    data_p = None
    if data_prevista not in (None, ""):
        data_p = _data_iso_valida(data_prevista)
        if not data_p:
            return {"erro": "data da etapa invalida (AAAA-MM-DD)"}
    etapa_id = adicionar_etapa_projeto(conn, projeto_id, texto, data_p)
    if etapa_id is None:
        return {"erro": "projeto nao encontrado"}
    return {"ok": True, "etapa_id": etapa_id}


@app.route("/api/projetos/<int:projeto_id>/etapas", methods=["POST"])
def adicionar_etapa_rota(projeto_id):
    body = _corpo_json()
    conn = get_db()
    resultado = _adicionar_etapa(conn, projeto_id, body.get("texto"), body.get("data_prevista"))
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201


@app.route("/api/projetos/etapas/<int:etapa_id>/concluir", methods=["POST"])
def concluir_etapa_rota(etapa_id):
    conn = get_db()
    projeto_id = concluir_etapa_projeto(conn, etapa_id)
    conn.close()
    if projeto_id is None:
        return jsonify({"error": "etapa nao encontrada"}), 404
    return jsonify({"ok": True, "projeto_id": projeto_id})


@app.route("/api/projetos/etapas/<int:etapa_id>", methods=["DELETE"])
def apagar_etapa_rota(etapa_id):
    conn = get_db()
    projeto_id = apagar_etapa_projeto(conn, etapa_id)
    conn.close()
    if projeto_id is None:
        return jsonify({"error": "etapa nao encontrada"}), 404
    return jsonify({"ok": True})


@app.route("/api/viagens/<int:viagem_id>/como-projeto", methods=["GET"])
def viagem_como_projeto_rota(viagem_id):
    conn = get_db()
    registro = conn.execute("SELECT * FROM viagens WHERE id = ?", (viagem_id,)).fetchone()
    if not registro:
        conn.close()
        return jsonify({"error": "viagem nao encontrada"}), 404
    itens = list_itens_viagem(conn, viagem_id)
    conn.close()
    return jsonify(vida.viagem_como_projeto_detalhada(dict(registro), itens, date.today()))


@app.route("/api/viagens/<int:viagem_id>/timeline-card", methods=["GET"])
def viagem_timeline_card_rota(viagem_id):
    """US-F11: mesmo `data` do card projeto_viagem (Fase 6, US-E13) que o chat
    ja usa (cards.card_viagem) - a tela de Viagens reaproveita o MESMO
    adaptador, sem recalcular etapas/progresso/marcos no front. Sem `actions`
    (a tela ja esta na aba Viagens - um botao "abrir aba Viagens" ali seria
    um link circular pro mesmo lugar)."""
    conn = get_db()
    card = cards.card_viagem(conn, viagem_id, date.today(), actions_extra=[])
    conn.close()
    if not card:
        return jsonify({"error": "viagem nao encontrada"}), 404
    card["actions"] = []
    return jsonify(card)


# Revisao da Fase 6 (achado 8): falha temporaria do Nominatim (rede, 429,
# 5xx) espera isso antes de tentar de novo - antes cada GET /api/lugares
# repetia a chamada na hora (1s de throttle + timeout) no unico worker.
GEOCODE_ESPERA_APOS_ERRO = timedelta(hours=6)


def _agora_utc() -> datetime:
    return datetime.utcnow()


def _fmt_utc(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%d %H:%M:%S")


def _geocodificar_lugar(conn, lugar_id: int, nome: str, cidade: str | None) -> None:
    """US-F13: 1 consulta ao Nominatim por lugar, NUNCA repetida depois que
    da uma resposta de verdade (ok/nao_encontrado/recusado). Falha temporaria
    grava "erro" + quando pode tentar de novo (GEOCODE_ESPERA_APOS_ERRO)."""
    resultado = geocode_nominatim.geocodificar(nome, cidade)
    status = resultado.get("status")
    if status == "ok":
        salvar_geocode_lugar(conn, lugar_id, resultado["lat"], resultado["lng"], "ok")
    elif status == "erro":
        depois = _fmt_utc(_agora_utc() + GEOCODE_ESPERA_APOS_ERRO)
        salvar_geocode_lugar(conn, lugar_id, None, None, "erro", tentar_depois=depois)
    elif status == "recusado":
        salvar_geocode_lugar(conn, lugar_id, None, None, "recusado")
    else:
        salvar_geocode_lugar(conn, lugar_id, None, None, "nao_encontrado")


def _criar_lugar(conn, nome, cidade, tipo, nota) -> dict:
    nome = _texto_curto(nome, 80)
    if not nome:
        return {"erro": "informe o nome do lugar"}
    cidade = _texto_curto(cidade, 60)
    lugar_id = create_lugar(conn, nome, cidade, _texto_curto(tipo, 40), _texto_curto(nota, 300))
    _geocodificar_lugar(conn, lugar_id, nome, cidade)
    return {"ok": True, "lugar_id": lugar_id}


@app.route("/api/lugares", methods=["GET"])
def lugares():
    conn = get_db()
    resultado = list_lugares(conn)
    # US-F13: backfill de lugares que ja existiam antes desta historia (ou
    # cuja falha temporaria ja esperou GEOCODE_ESPERA_APOS_ERRO) - no MAXIMO
    # 1 geocode por chamada, pra nunca estourar 1 req/s nem prender o worker.
    pendente = proximo_lugar_para_geocodificar(conn, _fmt_utc(_agora_utc()))
    if pendente:
        _geocodificar_lugar(conn, pendente["id"], pendente["nome"], pendente.get("cidade"))
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


TIPOS_MANUTENCAO = {"casa", "carro", "equipamento", "outro"}


def _numero_positivo_opcional(valor):
    """None e valido (campo opcional, ex: km ou proxima_em_km nao
    informados). Qualquer outra coisa que nao seja numero >= 0 devolve
    "invalido" (string, nunca confundivel com um float de verdade) pra quem
    chamou tratar como erro de validacao."""
    if valor in (None, ""):
        return None
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return "invalido"
    if valor < 0:
        return "invalido"
    return float(valor)


def _manutencoes_com_status(conn, hoje: date) -> list[dict]:
    """Secao unica de manutencao (Fase 6, US-E1a). tipo='carro' e HISTORICO
    (uma linha por manutencao feita, sem "proxima"/"dias_ate" por tempo - o
    aviso dela e por km/data, ver _manutencoes_carro_proximas) - os demais
    tipos sao EDICAO NO LUGAR (um item so, "proxima"/"dias_ate" calculados
    por vida.proxima_data_manutencao). `data` e um alias de `ultima_vez` pro
    tipo='carro', pro front-end nao precisar saber o nome interno da coluna."""
    resultado = []
    for m in list_manutencoes(conn):
        item = dict(m)
        if item["tipo"] == "carro":
            item["data"] = item["ultima_vez"]
            item["proxima"] = None
            item["dias_ate"] = None
        else:
            proxima = vida.proxima_data_manutencao(m["ultima_vez"], m["intervalo_meses"], m["criado_em"], hoje)
            item["proxima"] = proxima.isoformat()
            item["dias_ate"] = (proxima - hoje).days
        resultado.append(item)
    resultado.sort(key=lambda x: x["dias_ate"] if x["dias_ate"] is not None else 10**9)
    return resultado


def _validar_manutencao(body: dict) -> dict:
    """Valida o corpo de criacao de manutencao pros dois "modos" da secao
    unificada: tipo='carro' pede item + data (+ km/proxima_em_km/
    proxima_em_data opcionais, historico - ver create_manutencao); os
    demais tipos (casa/equipamento/outro) pedem item + intervalo_meses (+
    ultima_vez opcional, edicao no lugar - mesma validacao de antes da
    unificacao)."""
    tipo = _texto_curto(body.get("tipo"), 20) or "outro"
    if tipo not in TIPOS_MANUTENCAO:
        return {"erro": "tipo invalido (use casa, carro, equipamento ou outro)"}
    item = _texto_curto(body.get("item"), 80)
    if not item:
        return {"erro": "informe o item"}

    if tipo == "carro":
        data = _data_iso_valida(body.get("data") or body.get("ultima_vez"))
        if not data:
            return {"erro": "informe a data (AAAA-MM-DD)"}
        km = _numero_positivo_opcional(body.get("km"))
        if km == "invalido":
            return {"erro": "km invalido (numero maior ou igual a zero)"}
        proxima_em_km = _numero_positivo_opcional(body.get("proxima_em_km"))
        if proxima_em_km == "invalido":
            return {"erro": "proxima_em_km invalido (numero maior ou igual a zero)"}
        proxima_em_data = None
        if body.get("proxima_em_data") not in (None, ""):
            proxima_em_data = _data_iso_valida(body.get("proxima_em_data"))
            if not proxima_em_data:
                return {"erro": "proxima_em_data invalida (AAAA-MM-DD)"}
        return {
            "tipo": tipo, "item": item, "intervalo_meses": None, "ultima_vez": data,
            "km": km, "proxima_em_km": proxima_em_km, "proxima_em_data": proxima_em_data,
        }

    intervalo = _inteiro_no_intervalo(body.get("intervalo_meses"), 1, 120)
    if intervalo is None:
        return {"erro": "informe o item e o intervalo em meses (1 a 120)"}
    ultima_vez = body.get("ultima_vez")
    ultima = _data_iso_valida(ultima_vez) if ultima_vez not in (None, "") else None
    if ultima_vez not in (None, "") and (not ultima or ultima > date.today().isoformat()):
        return {"erro": "data da ultima vez invalida"}
    return {
        "tipo": tipo, "item": item, "intervalo_meses": intervalo, "ultima_vez": ultima,
        "km": None, "proxima_em_km": None, "proxima_em_data": None,
    }


def _criar_manutencao(conn, body: dict) -> dict:
    campos = _validar_manutencao(body)
    if "erro" in campos:
        return campos
    manutencao_id = create_manutencao(
        conn, campos["tipo"], campos["item"], campos["intervalo_meses"], campos["ultima_vez"],
        campos["km"], campos["proxima_em_km"], campos["proxima_em_data"],
    )
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
    resultado = _criar_manutencao(conn, body)
    if "ok" in resultado:
        _marcar_atividade(conn)
        conn.commit()
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201


@app.route("/api/manutencoes/<int:manutencao_id>/feita", methods=["POST"])
def manutencao_feita(manutencao_id):
    conn = get_db()
    existente = get_manutencao(conn, manutencao_id)
    if not existente:
        conn.close()
        return jsonify({"error": "manutencao nao encontrada"}), 404
    if existente["tipo"] == "carro":
        conn.close()
        return jsonify({"error": "manutencao de carro nao usa 'feita' - adicione um novo registro"}), 400
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


def _criar_ideia_presente(conn, pessoa, ideia, ocasiao) -> dict:
    pessoa = _texto_curto(pessoa, 80)
    ideia_txt = _texto_curto(ideia, 200)
    if not pessoa or not ideia_txt:
        return {"erro": "informe a pessoa e a ideia de presente"}
    ideia_id = create_ideia_presente(conn, pessoa, ideia_txt, _texto_curto(ocasiao, 60))
    return {"ok": True, "ideia_id": ideia_id}


@app.route("/api/ideias-presente", methods=["GET"])
def ideias_presente_rota():
    conn = get_db()
    resultado = list_ideias_presente(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/ideias-presente", methods=["POST"])
def criar_ideia_presente_rota():
    body = _corpo_json()
    conn = get_db()
    resultado = _criar_ideia_presente(conn, body.get("pessoa"), body.get("ideia"), body.get("ocasiao"))
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201


@app.route("/api/ideias-presente/<int:ideia_id>/comprado", methods=["POST"])
def alternar_ideia_presente_rota(ideia_id):
    conn = get_db()
    comprado = alternar_ideia_presente_comprada(conn, ideia_id)
    conn.close()
    if comprado is None:
        return jsonify({"error": "ideia nao encontrada"}), 404
    return jsonify({"comprado": comprado})


@app.route("/api/ideias-presente/<int:ideia_id>", methods=["DELETE"])
def apagar_ideia_presente_rota(ideia_id):
    conn = get_db()
    delete_ideia_presente(conn, ideia_id)
    conn.close()
    return jsonify({"ok": True})


# ---- Fase 5 (US-C18): cofre de garantia ----

TAMANHO_MAX_ANEXO_GARANTIA_BYTES = 5 * 1024 * 1024  # 5MB - nota fiscal (PDF ou foto), nao um orcamento escaneado
EXTENSOES_ANEXO_GARANTIA = (".pdf", ".jpg", ".jpeg", ".png")
# Assinatura real dos primeiros bytes por extensao aceita (US-C18) - a
# extensao do filename sozinha e so o nome que o navegador mandou, nao prova
# nada sobre o conteudo real (revisao de seguranca da Fase 5). Checar os
# magic bytes evita salvar um arquivo com conteudo arbitrario disfarcado de
# PDF/imagem no anexo da garantia.
_ASSINATURAS_ANEXO_GARANTIA = {
    ".pdf": (b"%PDF-",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
}


def _conteudo_bate_com_extensao(nome: str, dados: bytes) -> bool:
    for ext, assinaturas in _ASSINATURAS_ANEXO_GARANTIA.items():
        if nome.endswith(ext):
            return any(dados.startswith(sig) for sig in assinaturas)
    return False


def _garantia_com_status(g: dict, hoje: date) -> dict:
    compra = date.fromisoformat(g["data_compra"])
    vencimento = vida.somar_meses(compra, g["prazo_garantia_meses"])
    return {**g, "vencimento": vencimento.isoformat(), "dias_ate": (vencimento - hoje).days}


def _criar_garantia(conn, produto, data_compra, prazo_meses, nota_fiscal_anexo) -> dict:
    produto = _texto_curto(produto, 120)
    compra = _data_iso_valida(data_compra)
    prazo = _inteiro_no_intervalo(prazo_meses, 1, 600)
    if not produto or not compra:
        return {"erro": "informe o produto e a data de compra (AAAA-MM-DD)"}
    if prazo is None:
        return {"erro": "informe o prazo de garantia em meses (1 a 600)"}
    if compra > date.today().isoformat():
        return {"erro": "data de compra invalida (nao pode ser no futuro)"}
    garantia_id = create_garantia(conn, produto, compra, prazo, nota_fiscal_anexo)
    return {"ok": True, "garantia_id": garantia_id}


@app.route("/api/garantias", methods=["GET"])
def garantias_rota():
    conn = get_db()
    hoje = date.today()
    resultado = [_garantia_com_status(g, hoje) for g in list_garantias(conn)]
    conn.close()
    resultado.sort(key=lambda g: g["dias_ate"])
    return jsonify(resultado)


@app.route("/api/garantias", methods=["POST"])
def criar_garantia_rota():
    conn = get_db()
    anexo_b64 = None
    if request.content_type and "multipart/form-data" in request.content_type:
        produto = request.form.get("produto")
        data_compra = request.form.get("data_compra")
        prazo = request.form.get("prazo_garantia_meses")
        arquivo = request.files.get("nota_fiscal")
        if arquivo and arquivo.filename:
            nome = arquivo.filename.lower()
            if not nome.endswith(EXTENSOES_ANEXO_GARANTIA):
                conn.close()
                return jsonify({"error": "anexo precisa ser PDF, JPG ou PNG"}), 400
            dados = arquivo.read()
            if len(dados) > TAMANHO_MAX_ANEXO_GARANTIA_BYTES:
                conn.close()
                return jsonify({"error": "anexo maior que 5MB - manda um arquivo menor"}), 400
            if not _conteudo_bate_com_extensao(nome, dados):
                conn.close()
                return jsonify({"error": "conteudo do arquivo nao bate com a extensao (PDF, JPG ou PNG de verdade)"}), 400
            anexo_b64 = base64.b64encode(dados).decode("ascii")
    else:
        body = _corpo_json()
        produto = body.get("produto")
        data_compra = body.get("data_compra")
        prazo = body.get("prazo_garantia_meses")
    resultado = _criar_garantia(conn, produto, data_compra, prazo, anexo_b64)
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado), 201


@app.route("/api/garantias/<int:garantia_id>", methods=["DELETE"])
def apagar_garantia_rota(garantia_id):
    conn = get_db()
    delete_garantia(conn, garantia_id)
    conn.close()
    return jsonify({"ok": True})


def _ultima_manutencao_carro_por_item(conn) -> list[dict]:
    """So a manutencao de carro mais recente de cada item importa pra saber
    "quando vence a proxima" - um registro antigo do mesmo item (ex: troca
    de oleo de 2 revisoes atras) tem um proxima_em_km/proxima_em_data ja
    obsoleto, substituido pelo registro mais novo."""
    carros = [m for m in list_manutencoes(conn) if m["tipo"] == "carro"]
    carros.sort(key=lambda m: (m["ultima_vez"] or "", m["id"]), reverse=True)
    vistos = set()
    ultimas = []
    for m in carros:
        if m["item"] in vistos:
            continue
        vistos.add(m["item"])
        ultimas.append(m)
    return ultimas


def _manutencoes_carro_proximas(conn, hoje: date, dias_aviso: int = 15, km_aviso: float = 500) -> list[dict]:
    """Pra cada tipo de manutencao (so o registro mais recente), decide se
    esta perto do limite por DATA (dentro de `dias_aviso` dias, ou ja
    passou) ou por KM (km_atual_veiculo - o maior km ja registrado em
    qualquer manutencao, ja que nao ha odometro conectado - dentro de
    `km_aviso` do proximo, ou ja passou). Sem proxima_em_km/proxima_em_data
    definido, essa manutencao simplesmente nunca avisa (nada pra comparar)."""
    km_atual = km_atual_veiculo(conn)
    proximas = []
    for m in _ultima_manutencao_carro_por_item(conn):
        motivo = None
        if m["proxima_em_data"]:
            proxima = date.fromisoformat(m["proxima_em_data"])
            dias_ate = (proxima - hoje).days
            if dias_ate <= dias_aviso:
                motivo = (
                    "ja passou do prazo" if dias_ate < 0
                    else "vence hoje" if dias_ate == 0
                    else f"vence em {dias_ate} dia(s)"
                )
        if not motivo and m["proxima_em_km"] is not None and km_atual is not None:
            km_faltando = m["proxima_em_km"] - km_atual
            if km_faltando <= km_aviso:
                motivo = (
                    f"ja passou {abs(km_faltando):.0f}km do previsto" if km_faltando < 0
                    else f"faltam {km_faltando:.0f}km pro previsto"
                )
        if motivo:
            proximas.append({**m, "motivo": motivo})
    return proximas


def _adicionar_compras(conn, itens) -> dict:
    if isinstance(itens, str):
        itens = [itens]
    if not isinstance(itens, list):
        return {"erro": "mande a lista de itens"}
    adicionados = []
    validos = 0
    # Fase 6 (US-E1b): cada entrada bruta pode conter mais de um item junto
    # ("acabou cafe e acucar", "cafe, acucar e leite") - vida.dividir_itens_compra
    # e a UNICA funcao que separa isso, pra nao duplicar a logica em cada
    # caminho (chat tool ja manda um item por entrada normalmente, mas isso
    # tambem cobre o formulario/API mandando tudo junto numa string so).
    itens_separados = []
    for bruto in itens[:30]:
        if not isinstance(bruto, str):
            continue
        itens_separados.extend(vida.dividir_itens_compra(bruto))
    for item in itens_separados[:30]:
        item = _texto_curto(item, 60)
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
    _log_usage(conn, usage, "mensagem_dificil")
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
                _log_usage(conn, resultado[1], "resumo_link")
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
        {"titulo": g["titulo"], "pct": calculos.percentual_meta_exibicao(g["valor_guardado"], g["valor_alvo"])}
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


@app.route("/api/revisao-periodo", methods=["GET"])
def revisao_periodo():
    """Fase 5 (US-C3): revisao trimestral/anual - agrega financeiro, tarefas
    concluidas e saude reaproveitando _fatos_periodo (a mesma funcao ja usada
    pela revisao mensal em /api/revisao-mensal e por /api/progresso, nao
    duplica calculo), mais as decisoes do diario (US-C2) registradas no
    periodo."""
    tipo = request.args.get("tipo", "trimestre")
    if tipo not in ("trimestre", "ano"):
        return jsonify({"error": "tipo precisa ser trimestre ou ano"}), 400

    hoje = date.today()
    try:
        ano = int(request.args.get("ano", hoje.year))
        if tipo == "trimestre":
            trimestre = int(request.args.get("trimestre", vida.trimestre_de(hoje)))
            primeiro, ultimo = vida.intervalo_trimestre(ano, trimestre)
        else:
            trimestre = None
            primeiro, ultimo = vida.intervalo_ano(ano)
        if not 2000 <= ano <= 2100:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "ano/trimestre invalidos"}), 400

    conn = get_db()
    fatos = _fatos_periodo(conn, primeiro, ultimo)
    decisoes_periodo = [
        d for d in list_diario_decisoes(conn) if primeiro.isoformat() <= d["data"] <= ultimo.isoformat()
    ]
    conn.close()

    return jsonify(
        {
            "tipo": tipo,
            "ano": ano,
            "trimestre": trimestre,
            "inicio": primeiro.isoformat(),
            "fim": ultimo.isoformat(),
            **fatos,
            "decisoes": decisoes_periodo,
            "decisoes_com_resultado": sum(1 for d in decisoes_periodo if d["resultado"]),
        }
    )


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


@app.route("/api/ia/custo", methods=["GET"])
def ia_custo():
    """Resumo do gasto com a API da Anthropic pro card financeiro (US-A5) -
    mes atual e ultimos 30 dias, mais teto/fracao/estourado (US-A6). Ver
    db.resumo_custo_api."""
    conn = get_db()
    resumo = resumo_custo_api(conn)
    conn.close()
    return jsonify(resumo)


@app.route("/api/ia/teto", methods=["POST"])
def ia_definir_teto():
    """Define (ou remove, com null/0) o teto mensal de gasto com IA (US-A6) -
    editavel via UI no card financeiro."""
    body = _corpo_json()
    teto = body.get("teto_mensal_usd")
    if teto is not None:
        if isinstance(teto, bool) or not isinstance(teto, (int, float)) or not math.isfinite(teto):
            return jsonify({"error": "teto_mensal_usd precisa ser um numero"}), 400
        if teto < 0:
            return jsonify({"error": "teto_mensal_usd nao pode ser negativo"}), 400
    conn = get_db()
    definir_teto_mensal_ia(conn, teto)
    resumo = resumo_custo_api(conn)
    conn.close()
    return jsonify(resumo)


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


@app.route("/api/bancos", methods=["GET"])
def listar_bancos():
    if _modo_visitante_ativo():
        return jsonify([])
    conn = get_db()
    # saldo/valor sao criptografados em repouso - list_bank_accounts e
    # estatisticas_conta ja descriptografam e somam em Python (ver db.py).
    contas = list_bank_accounts(conn)
    ano_mes_atual = date.today().strftime("%Y-%m")
    resultado = []
    for c in contas:
        stats = estatisticas_conta(conn, c["id"])
        item = {
            **c,
            "total_transacoes": stats["total"],
            "ultima_transacao": stats["ultima"],
            "total_gasto": stats["total_gasto"],
        }
        # Fase 6 (US-E15): limite manual do cartao - so calcula fracao/sobra
        # quando o proprio Alex digitou um limite (Open Finance nao manda
        # isso); "ciclo" aqui e simplificado pro mes-calendario, ver
        # gasto_mes_conta em db.py.
        if c["tipo"] == "cartao":
            gasto_ciclo = gasto_mes_conta(conn, c["id"], ano_mes_atual)
            item["gasto_ciclo"] = round(gasto_ciclo, 2)
            item["limite_info"] = vida.fracao_limite_cartao(gasto_ciclo, c.get("limite"))
        resultado.append(item)
    conn.close()
    return jsonify(resultado)


def _definir_limite_cartao(conn, bank_account_id: int, limite) -> dict:
    if limite in (None, ""):
        ok = definir_limite_conta(conn, bank_account_id, None)
        return {"ok": True} if ok else {"erro": "conta nao encontrada"}
    valida = isinstance(limite, (int, float)) and not isinstance(limite, bool) and math.isfinite(limite) and limite > 0
    if not valida:
        return {"erro": "limite precisa ser um numero maior que zero (ou vazio pra apagar)"}
    ok = definir_limite_conta(conn, bank_account_id, float(limite))
    return {"ok": True} if ok else {"erro": "conta nao encontrada"}


@app.route("/api/bancos/<int:conta_id>/limite", methods=["POST"])
def definir_limite_cartao_rota(conta_id):
    if _modo_visitante_ativo():
        return jsonify({"error": "indisponivel no modo visitante"}), 403
    body = _corpo_json()
    conn = get_db()
    resultado = _definir_limite_cartao(conn, conta_id, body.get("limite"))
    conn.close()
    if "erro" in resultado:
        return jsonify({"error": resultado["erro"]}), 400
    return jsonify(resultado)


def _patrimonio_consolidado(conn) -> dict:
    """Soma tudo que o projeto ja sabe que tem valor monetario num so numero
    (US-C12, corrigido na Fase 9/f9-api): saldo das contas/cartoes
    (bank_accounts.saldo, ja criptografado em repouso desde a Fase 4 -
    list_bank_accounts descriptografa, nenhuma coluna nova pra proteger
    aqui) + o que ja foi guardado nas metas financeiras (goals.valor_guardado
    - dinheiro separado, entao conta como patrimonio tanto quanto o saldo em
    conta) - MENOS a fatura em aberto do cartao. bank_accounts.saldo pra
    tipo='cartao' e sempre gravado POSITIVO (= quanto se deve - ver
    AGENTS.md da faixa f9-api), nunca dinheiro disponivel, entao nunca entra
    como saldo bancario - so como divida, subtraindo do total."""
    contas = list_bank_accounts(conn)
    saldo_bancario = sum(c["saldo"] or 0 for c in contas if c["tipo"] == "conta")
    fatura_aberta = sum(c["saldo"] or 0 for c in contas if c["tipo"] == "cartao")
    metas = list_goals(conn)
    valor_guardado_metas = sum(g["valor_guardado"] or 0 for g in metas)
    return {
        "saldo_bancario": round(saldo_bancario, 2),
        "fatura_aberta": round(fatura_aberta, 2),
        "valor_guardado_metas": round(valor_guardado_metas, 2),
        "patrimonio_total": round(saldo_bancario + valor_guardado_metas - fatura_aberta, 2),
        "contas": [
            {"banco": c["banco"], "tipo": c["tipo"], "saldo": c["saldo"]}
            for c in contas
            if c["saldo"] is not None
        ],
        "metas": [
            {"titulo": g["titulo"], "valor_guardado": g["valor_guardado"]}
            for g in metas
            if g["valor_guardado"]
        ],
    }


@app.route("/api/patrimonio", methods=["GET"])
def patrimonio_rota():
    if _modo_visitante_ativo():
        return jsonify(
            {
                "saldo_bancario": 0,
                "fatura_aberta": 0,
                "valor_guardado_metas": 0,
                "patrimonio_total": 0,
                "contas": [],
                "metas": [],
                "oculto": True,
            }
        )
    conn = get_db()
    resultado = _patrimonio_consolidado(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/bancos/<int:conta_id>/transacoes", methods=["GET"])
def transacoes_banco(conta_id):
    if _modo_visitante_ativo():
        return jsonify([])
    conn = get_db()
    transacoes = list_bank_transactions(conn, conta_id, limite=100)
    conn.close()
    return jsonify(transacoes)


@app.route("/api/bancos/sync-status", methods=["GET"])
def bancos_sync_status():
    configurado = pluggy_client.configurado()
    info = (
        "Conecte um banco automaticamente pra sincronizar sem precisar exportar OFX."
        if configurado
        else "Sincronizacao automatica ainda nao configurada - veja o README (integracao com Pluggy)."
    )
    # uso/m2-sync: carimbo do ultimo sync bom (manual OU automatico de
    # madrugada, ver rodar_sincronizacao_nubank_automatica/iniciar_scheduler
    # abaixo - os dois gravam com a mesma chave em rotas/f8_banco.py) - so
    # acrescenta na mesma frase, sem lugar novo na tela.
    ultimo_sync = None
    if configurado:
        import rotas.f8_banco

        conn = get_db()
        try:
            ultimo_sync = obter_configuracao(conn, rotas.f8_banco.CHAVE_ULTIMO_SYNC_NUBANK_OK)
        finally:
            conn.close()
        if ultimo_sync:
            info += f" Ultima sincronizacao: {ultimo_sync[:16].replace('T', ' as ')}."
    return jsonify(
        {
            "sincronizacao_automatica": configurado,
            "info": info,
            "ultimo_sync_nubank_ok": ultimo_sync,
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
            # (Connect: primeira importacao do item, sem reconciliacao de
            # remocao - isso e so na sincronizacao recorrente do Nubank em
            # rotas/f8_banco.py.) `truncado` nao muda esse fluxo hoje.
            transacoes_pluggy, _truncado = pluggy_client.get_transactions(conta_pluggy["id"])
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
    """Aba Construtora. Fase 7 (C1): via construtora_cliente (vale o modo
    mock CONSTRUTORA_API_MOCK=1) e so com o que o painel pessoal pode mostrar:
    `dados` = status/tot_entradas/tot_saidas (nunca lucro, margem, VGV) e a
    lista de contas a vencer (que a propria aba pede)."""
    if not _cliente_construtora().configurado():
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
    # US-F14: cotacao compara preco de fornecedor - e dado financeiro,
    # mesmo tratamento que /api/expenses/etc em modo visitante (lista
    # inteira escondida, nao so o valor - achado real: essa rota nunca
    # tinha ganhado essa checagem antes desta historia).
    if _modo_visitante_ativo():
        return jsonify([])
    conn = get_db()
    resultado = list_cotacoes(conn)
    conn.close()
    return jsonify(resultado)


@app.route("/api/cotacoes", methods=["POST"])
def criar_cotacao_rota():
    if _modo_visitante_ativo():
        return jsonify({"error": "indisponivel no modo visitante"}), 403
    titulo = (_corpo_json().get("titulo") or "").strip()
    if not titulo:
        return jsonify({"error": "informe o titulo da cotacao"}), 400
    conn = get_db()
    cotacao_id = criar_cotacao(conn, titulo)
    conn.close()
    return jsonify({"id": cotacao_id, "ok": True}), 201


@app.route("/api/cotacoes/<int:cotacao_id>", methods=["GET"])
def ver_cotacao(cotacao_id):
    if _modo_visitante_ativo():
        return jsonify({"error": "indisponivel no modo visitante"}), 403
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
    if _modo_visitante_ativo():
        return jsonify({"error": "indisponivel no modo visitante"}), 403
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
    if _modo_visitante_ativo():
        return jsonify({"error": "indisponivel no modo visitante"}), 403
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

    _log_usage(conn, usage, "cotacao_pdf")
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

    conn = get_db()
    # Mesmo teto mensal da US-A6 (ver _classificar_intent) - extracao por
    # visao usa Sonnet, mais caro que o Haiku do classificador de intent,
    # entao e a chamada mais cara do app pra deixar sem controle de gasto.
    # Revisao de seguranca da Fase 5 achou que so o classificador de intent
    # respeitava o teto - corrigido aqui. Mesmo _TETO_IA_LOCK da
    # _classificar_intent (fecha a mesma janela TOCTOU nos dois pontos que
    # respeitam o teto).
    with _TETO_IA_LOCK:
        if _teto_ia_estourado("extrair_nota_fiscal_foto"):
            conn.close()
            return jsonify({"error": TETO_IA_MSG}), 402

        result, error = _call_claude(claude_client.extrair_nota_fiscal_foto, image_bytes, media_type)
        if error:
            conn.close()
            return error
        dados, usage = result

        _log_usage(conn, usage, "nota_fiscal")
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


# Rotulo curto de cada acao do contrato (docs/INTENT.md), usado so pra montar
# a fala de volta pro Atalho/Siri (US-B4) - nao e o formato de dado, so texto
# de UI/voz. "tela"/"pergunta"/"titulo" sao chaves de parametros que a IA PODE
# preencher (claude_client.INTENT_PROMPT), nunca garantidas - por isso todo
# .get() aqui tem um fallback plausivel.
_ROTULO_ACAO_INTENT = {
    "registrar_tarefa": "uma tarefa",
    "registrar_gasto": "um gasto",
    "registrar_checkin": "um check-in",
    "navegar_tela": "ir pra uma tela do painel",
    "consultar": "uma pergunta",
    "corrigir_ultimo": "uma correcao do ultimo item",
    "desconhecido": None,
}


def _texto_falado_intent(resultado: dict) -> str:
    """Frase curta pronta pro Atalho falar de volta (acao "Falar Texto"/
    "Mostrar Resultado" do app Atalhos) - nunca executa a acao aqui (fora do
    escopo da US-B4, ver docs/INTENT.md), so descreve o que foi entendido."""
    if resultado.get("teto_ia_estourado"):
        return "O limite mensal de IA ja estourou, nao consegui entender esse comando agora."

    acao = resultado.get("acao")
    rotulo = _ROTULO_ACAO_INTENT.get(acao)
    if not rotulo:
        return "Nao entendi esse comando. Tenta de novo com mais detalhe."

    parametros = resultado.get("parametros") or {}
    detalhe = ""
    if acao == "navegar_tela" and parametros.get("tela"):
        detalhe = f' ({parametros["tela"]})'
    elif acao in ("registrar_tarefa", "registrar_gasto") and parametros.get("titulo"):
        detalhe = f': {parametros["titulo"]}'
    elif acao == "consultar" and parametros.get("pergunta"):
        detalhe = f': {parametros["pergunta"]}'

    if resultado.get("precisa_confirmacao"):
        return f"Acho que entendi {rotulo}{detalhe}, mas nao tenho certeza. Confirma no painel antes de executar."
    return f"Entendi {rotulo}{detalhe}. Confirma no painel pra executar."


@app.route("/api/atalho/comando-voz", methods=["POST"])
def atalho_comando_voz():
    """US-B4: pro Atalho "Ei Siri, [comando]" do iPhone - mesmo padrao de
    autenticacao por token dos outros /api/atalho/*. Recebe o texto que o
    Siri ja transcreveu (acao "Ditar Texto" do app Atalhos) e reusa a MESMA
    logica de classificacao de /api/intent/classificar (_classificar_intent,
    fonte unica - nunca duplicada aqui). Devolve so uma frase curta ("fala")
    pronta pro Atalho falar de volta - NAO executa a acao classificada
    sozinho (fora do escopo desta historia; a execucao de verdade acontece
    no painel, US-B1/US-B2, com a confirmacao explicita do Alex)."""
    if not _token_atalho_valido():
        return jsonify({"error": "token invalido"}), 401

    body = _corpo_json()
    texto = (body.get("texto") or body.get("text") or "").strip()
    if not texto:
        return jsonify({"error": "texto vazio", "fala": "Nao entendi, pode repetir?"}), 400

    conn = get_db()
    resultado, error = _classificar_intent(conn, texto)
    if error:
        conn.close()
        status = error[1] if isinstance(error, tuple) else 502
        return jsonify({"error": "erro ao classificar", "fala": "Deu um erro ao tentar entender o comando."}), status
    conn.commit()
    conn.close()

    return jsonify({**resultado, "fala": _texto_falado_intent(resultado)})


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
    _log_usage(conn, usage, "cotacao_pdf")
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

    proximo_titulo = proximo["titulo"] if proximo else None
    proximo_hora = proximo["inicio"][11:16] if proximo else None

    return jsonify(
        {
            "tarefas_pendentes": tarefas_pendentes,
            "gasto_hoje": gasto_hoje,
            "proximo_titulo": proximo_titulo,
            "proximo_hora": proximo_hora,
            # Campos pensados pra widget de tela de BLOQUEIO (accessoryInline/
            # accessoryRectangular no Scriptable - ver scriptable/widget_lockscreen.js
            # e docs/WIDGET_TELA_BLOQUEIO.md): la o espaco e minimo (uma ou duas
            # linhas de texto, sem cor/layout customizado - o iOS renderiza
            # monocromatico sozinho), entao em vez de reaproveitar os campos crus
            # acima e fazer esse calculo de novo no JS do widget, ja manda pronto
            # daqui pra manter o Scriptable so na parte de exibir.
            "resumo_curto": vida.resumo_curto_lockscreen(tarefas_pendentes, gasto_hoje),
            "linha_extra": (
                f"{proximo_hora} {proximo_titulo}" if proximo_titulo else None
            ),
        }
    )


@app.route("/api/configuracoes/silencio", methods=["GET"])
def obter_silencio():
    conn = get_db()
    inicio = obter_configuracao(conn, "silencio_inicio") or "22:00"
    fim = obter_configuracao(conn, "silencio_fim") or "07:00"
    # Fase 5 (US-C4): notificacao agrupada mora no mesmo endpoint/mecanismo
    # do modo silencioso configuravel (mesma tabela `configuracoes`, mesmo
    # painel de ajustes de notificacao) em vez de um sistema paralelo -
    # desligada por padrao pra nao mudar o comportamento de quem nunca
    # mexeu nisso.
    agrupar = (obter_configuracao(conn, "notificacoes_agrupar") or "0") == "1"
    agrupar_janela_min = int(obter_configuracao(conn, "notificacoes_agrupar_janela_min") or "2")
    conn.close()
    return jsonify({"inicio": inicio, "fim": fim, "agrupar": agrupar, "agrupar_janela_min": agrupar_janela_min})


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

    resultado = {"ok": True, "inicio": inicio, "fim": fim}
    if "agrupar" in corpo:
        agrupar = bool(corpo.get("agrupar"))
        definir_configuracao(conn, "notificacoes_agrupar", "1" if agrupar else "0")
        resultado["agrupar"] = agrupar
    if "agrupar_janela_min" in corpo:
        try:
            janela = int(corpo.get("agrupar_janela_min"))
        except (TypeError, ValueError):
            conn.close()
            return jsonify({"error": "agrupar_janela_min precisa ser um numero inteiro"}), 400
        if janela < 1:
            conn.close()
            return jsonify({"error": "agrupar_janela_min precisa ser pelo menos 1"}), 400
        definir_configuracao(conn, "notificacoes_agrupar_janela_min", str(janela))
        resultado["agrupar_janela_min"] = janela

    conn.close()
    return jsonify(resultado)


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


def rodar_sincronizacao_nubank_automatica():
    """Job do scheduler (ver iniciar_scheduler, uso/m2-sync): sincroniza o
    Nubank de madrugada sem o Alex precisar abrir o painel e apertar o
    botao manual. Chama a MESMA `rotas.f8_banco.sincronizar_nubank(conn)`
    que a rota `POST /api/bancos/sincronizar-nubank` usa - a logica de sync
    (upsert por external_id + reconciliacao de removidas) mora so la,
    nunca duplicada aqui; esse job so abre conexao propria, chama e loga.

    So roda se a Pluggy JA estiver configurada (PLUGGY_CLIENT_ID/SECRET +
    PLUGGY_ITEM_ID_NUBANK) - senao sai em silencio (sem log nenhum): a
    maioria dos ambientes (dev, teste, primeiro deploy antes do Alex
    cadastrar o item) nao tem isso configurado, e isso NAO e uma falha.

    Resiliente de proposito: qualquer erro (rede fora do ar, credencial
    Pluggy expirada, item desconectado) fica so no log - o ultimo sync bom
    que ja estava salvo continua intacto (sincronizar_nubank nunca commita
    uma leva pela metade, ver comentario la), nunca apaga nada por causa de
    uma falha daqui. Nunca deixa uma excecao subir e derrubar o scheduler."""
    if not pluggy_client.configurado() or not os.environ.get("PLUGGY_ITEM_ID_NUBANK"):
        return

    import rotas.f8_banco

    conn = get_db()
    try:
        resultado = rotas.f8_banco.sincronizar_nubank(conn)
    except Exception as e:
        app.logger.error("sincronizacao automatica do Nubank: excecao inesperada: %s", e)
        return
    finally:
        conn.close()

    if resultado.get("ok"):
        app.logger.info("sincronizacao automatica do Nubank: %s", resultado.get("mensagem"))
    else:
        app.logger.error("sincronizacao automatica do Nubank falhou: %s", resultado.get("error"))


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
        # sync automatico do Nubank as 4h de Brasilia (uso/m2-sync). O
        # BackgroundScheduler usa o fuso local do processo, e nao existe TZ
        # configurado nem no .env nem no render.yaml - o Render (producao de
        # teste, ver render.yaml) sobe o container em UTC, e sem TZ setado
        # localmente o Python tambem cai em UTC. 4h em Brasilia (America/
        # Sao_Paulo, fixo em UTC-3 desde que o Brasil aboliu o horario de
        # verao em 2019, sem trocas de horario pra acompanhar) = 7h UTC.
        scheduler.add_job(rodar_sincronizacao_nubank_automatica, "cron", hour=7, minute=0)
        scheduler.start()


# Fase 7: rotas por Blueprint (rotas/*.py, carga automatica) - SEMPRE no fim,
# depois de todo helper que os blueprints usam via rotas._base.app_modulo().
rotas.registrar_todas(app)


if __name__ == "__main__":
    iniciar_scheduler()
    iniciar_telegram()
    app.run(debug=True, port=5001)
