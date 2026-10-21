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
import sys
import tempfile
import threading
import time
import zipfile
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import anthropic
import requests
from dotenv import load_dotenv
from flask import Flask, Response, has_request_context, jsonify, redirect, render_template, request, send_file, session
from werkzeug.middleware.proxy_fix import ProxyFix

# Teste nunca le o .env real (regra do projeto): sob pytest/unittest o
# ambiente vem so do que o proprio teste define. Em producao (Render) as
# variaveis vem do painel do Render, entao isso nao muda nada la.
if not ({"pytest", "unittest"} & set(sys.modules)):
    load_dotenv()
else:
    # o app.run() do Flask tambem carrega o .env sozinho (testes de navegador
    # sobem o servidor com ele) - desliga isso sob teste.
    os.environ.setdefault("FLASK_SKIP_DOTENV", "1")

import agenda
import aprendizado
import auth
import backup_diario
import briefing_voo
import conversa_proativa
import estudo_quiz
import caldav_client
import calculos
import cards
import chat_consultas
import claude_client
import classificador_local
import clima
import clima_rota
import treino_vivo
import construtora_cliente
import criptografia
import estudo
import gastos
import geocode_nominatim
import leitura
import maps_client
import vida_assistente
import diario
import memoria
import feriados
import refeicoes
import rota_voo
import viagem_compras
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
    gastos_chat_repetidos_no_banco,
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
    total_gasto_real_mes,
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
import log_erros  # noqa: E402

log_erros.configurar(__import__("pathlib").Path(db.DB_PATH).parent)  # erros do servidor -> data/erros_servidor.log
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
            "Hospedado no Render sem PIN configurado: defina PAINEL_PIN_INICIAL (6 dígitos) nas "
            "variaveis de ambiente do serviço - sem isso /configurar-pin ficaria aberto pra quem "
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
    f"mensagem longa demais (máximo {TAMANHO_MAX_TEXTO_CHAT} caracteres) - divide em partes menores"
)
TETO_IA_MSG = (
    "teto mensal de gasto com IA estourado - tente de novo mês que vem ou ajuste o teto no card financeiro"
)


@app.errorhandler(413)
def _corpo_grande_demais(_erro):
    return jsonify({"error": "envio grande demais (máximo 20MB por vez) - manda um arquivo menor"}), 413

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


def _saida_do_maps(r: dict) -> dict:
    """horario_de_saida -> o que os cards usam: hora de sair, minutos de carro, quanto disso e
    transito (2026-10-15) e o link do Waze ate o lugar."""
    saida = {"sair": f"{datetime.fromisoformat(r['sair_ate']):%H:%M}", "trajeto_min": int(r["duracao_minutos"])}
    if isinstance(r.get("transito_min"), int):
        saida["transito_min"] = r["transito_min"]
    if isinstance(r.get("waze"), str):
        saida["waze"] = r["waze"]
    return saida


def _saida_pro_voo(conn, data_voo: str, hora: str | None, origem: str, antes_min: int) -> dict | None:
    """Hora de sair de casa pra chegar `antes_min` antes da decolagem no aerodromo de origem
    (trajeto com transito do Google, mesma conta do push "voo_sair"). None sem hora, sem
    Maps/ENDERECO_CASA ou se a rede falhar - o card mostra so a hora de chegar."""
    casa = os.environ.get("ENDERECO_CASA", "").strip()
    if not hora or not casa or not maps_client.configurado():
        return None
    try:
        chegar_ate = datetime.fromisoformat(f"{data_voo}T{hora}") - timedelta(minutes=antes_min)
        r = maps_client.horario_de_saida(casa, vida_assistente.resolver_lugar(conn, origem), chegar_ate,
                                         margem_minutos=10)
        return _saida_do_maps(r)
    except Exception:  # rede/formato: o card segue sem a hora de sair
        return None


DIAS_ENTREGA_PRESENTE = 4  # presente comprado pela internet: compra ate 4 dias antes
FOLGA_SEM_TRAJETO_MIN = 15  # mesma folga do aviso "hora de sair" (notificacoes.plano_se_arrumar)


def _saida_pro_compromisso(data_iso: str, hora: str | None, lugar: str | None) -> dict | None:
    """Card do date/balada (2026-10-14): hora de sair de casa pra chegar no lugar na hora
    (Maps com transito). None sem hora/lugar/Maps/ENDERECO_CASA ou se a rede falhar - o card
    usa a folga de 15 min, igual ao aviso."""
    casa = os.environ.get("ENDERECO_CASA", "").strip()
    if not hora or not lugar or not casa or not maps_client.configurado():
        return None
    try:
        chegar_ate = datetime.fromisoformat(f"{data_iso}T{hora}")
        r = maps_client.horario_de_saida(casa, lugar, chegar_ate, margem_minutos=5)
        return _saida_do_maps(r)
    except Exception:  # rede/formato: o card segue com a folga
        return None


def _clima_na_hora(data_iso: str, hora: str | None) -> dict | None:
    """Temperatura/chuva na hora do compromisso, na cidade padrao. None se nao der."""
    cidade = os.environ.get("CIDADE_PADRAO", "").strip()
    if not hora or not cidade:
        return None
    try:
        local = clima.geocodificar_cidade(cidade)
        if not local:
            return None
        prev = clima.previsao_na_hora(local["lat"], local["lon"], data_iso, hora)
        return {"temp": round(prev["temp"]), "chuva_pct": prev["chuva_pct"]} if prev else None
    except Exception:
        return None


def _primeiro_compromisso_do_dia(conn, dia_iso: str) -> dict | None:
    """Balada (2026-10-14): o que tem com HORA no dia seguinte (voo ou tarefa) e a que horas
    ele precisa acordar pra isso (sair - tempo de se arrumar; voo: chegar antes + trajeto).
    None se o dia seguinte nao tiver nada com hora - ai o card nao calcula sono (pedido dele)."""
    arrumar = vida_assistente.se_arrumar_min(conn)
    opcoes = []
    for v in conn.execute(
        "SELECT origem, hora FROM voos WHERE data = ? AND hora IS NOT NULL AND horas IS NULL", (dia_iso,)
    ).fetchall():
        hora = _normalizar_hora(v["hora"])
        if not hora:
            continue
        antes = vida_assistente.voo_briefing_min(conn)
        saida = _saida_pro_voo(conn, dia_iso, hora, v["origem"] or rota_voo.ORIGEM_PADRAO, antes)
        sair = saida["sair"] if saida else rota_voo.menos_minutos(hora, antes + FOLGA_SEM_TRAJETO_MIN)
        opcoes.append({"titulo": "voo", "hora": hora, "sair": sair})
    for t in conn.execute(
        "SELECT title, hora FROM tasks WHERE due_date = ? AND hora IS NOT NULL AND completed_at IS NULL "
        "AND NOT (recorrencia IS NOT NULL AND due_date IS NULL)",
        (dia_iso,),
    ).fetchall():
        hora = _normalizar_hora(t["hora"])
        if hora:
            opcoes.append({"titulo": t["title"], "hora": hora,
                           "sair": rota_voo.menos_minutos(hora, FOLGA_SEM_TRAJETO_MIN)})
    if not opcoes:
        return None
    primeiro = dict(min(opcoes, key=lambda o: o["sair"]))
    primeiro["acordar"] = rota_voo.menos_minutos(primeiro["sair"], arrumar)
    return primeiro


def _limpar_texto(valor, maximo: int) -> str | None:
    if not isinstance(valor, str):
        return None
    valor = " ".join(valor.split())[:maximo]
    return valor or None


def _extras_do_estilo(entrada: dict) -> dict:
    """So o que a IA mandou e faz sentido pro estilo, limpo e com tamanho limitado."""
    extras = {}
    com_quem = _limpar_texto(entrada.get("com_quem"), 60)
    if com_quem:
        extras["com_quem"] = com_quem
    lista = []
    for item in (entrada.get("lista") or [])[:8]:
        if isinstance(item, str):
            item = {"texto": item}
        if not isinstance(item, dict):
            continue
        texto_item = _limpar_texto(item.get("texto"), 80)
        if texto_item:
            lista.append({"texto": texto_item, "detalhe": _limpar_texto(item.get("detalhe"), 90),
                          "quando": _limpar_texto(item.get("quando"), 20), "feito": False})
    if lista:
        extras["lista"] = lista
    ideias = []
    for item in (entrada.get("ideias") or [])[:4]:
        if not isinstance(item, dict):
            continue
        titulo_ideia = _limpar_texto(item.get("titulo"), 50)
        if titulo_ideia:
            preco = item.get("preco")
            ok_preco = isinstance(preco, (int, float)) and not isinstance(preco, bool) and 0 < preco < 100000
            ideias.append({"titulo": titulo_ideia, "porque": _limpar_texto(item.get("porque"), 90),
                           "preco": round(float(preco)) if ok_preco else None})
    if ideias:
        extras["ideias"] = ideias
    volta = _normalizar_hora(entrada.get("volta"))
    if volta:
        extras["volta"] = volta
    if entrada.get("volta_modo") in cards.VOLTA_MODOS:
        extras["volta_modo"] = entrada["volta_modo"]
    return extras


# presente que se repete todo ano (3a leva): a IA marca `anual`; sem marcacao, o titulo decide
_RE_PRESENTE_ANUAL = re.compile(r"anivers|\bniver|natal|casamento|bodas", re.IGNORECASE)


def _presente_anual(entrada: dict) -> bool:
    if isinstance(entrada.get("anual"), bool):
        return entrada["anual"]
    return bool(_RE_PRESENTE_ANUAL.search(str(entrada.get("titulo") or "")))


def _tarefa_repetida(conn, titulo, dia):
    """Tarefa com o mesmo titulo (sem acento/caixa) no mesmo dia que ainda ta
    pendente, ou que foi concluida nas ultimas 12h - registrar de novo
    duplica. Caso real (2026-10-14): "Enviar a compra e venda pro Mikael"
    nasceu 2x, a segunda um minuto depois de ele concluir a primeira (a IA
    quis "mudar o horario" de uma tarefa ja feita e acabou criando outra).
    Assunto diferente com a mesma pessoa passa, porque o titulo e outro."""
    alvo = aprendizado.normalizar_consulta(titulo or "")
    if not alvo:
        return None
    linhas = conn.execute(
        "SELECT id, title, hora, completed_at FROM tasks WHERE recorrencia IS NULL "
        "AND COALESCE(due_date, '') = COALESCE(?, '') "
        "AND (completed_at IS NULL OR completed_at >= datetime('now', '-12 hours')) ORDER BY id DESC",
        (dia,),
    ).fetchall()
    return next((r for r in linhas if aprendizado.normalizar_consulta(r["title"]) == alvo), None)


def _aviso_tarefa_repetida(r) -> dict:
    """O que a IA recebe no lugar de criar a duplicata - sem _efeito (nao vira
    card) e com o caminho certo pra cada caso."""
    if r["completed_at"]:
        return {
            "nao_criei": True,
            "ja_concluida": {"id": r["id"], "titulo": r["title"]},
            "aviso": (
                f'Nao criei: "{r["title"]}" ja foi concluida ha pouco. Se a ideia era mudar o horario, '
                "conte ao Alex que ela ja ta feita. So registre de novo se ele disser que precisa fazer "
                "outra vez - ai com um titulo que diferencie (ex: o assunto)."
            ),
        }
    hora = f" as {r['hora']}" if r["hora"] else ""
    return {
        "nao_criei": True,
        "ja_existe": {"id": r["id"], "titulo": r["title"], "hora": r["hora"]},
        "aviso": (
            f'Nao criei: ja tem "{r["title"]}" pendente pro mesmo dia{hora}. Pra mudar hora/dia use '
            "ajustar_tarefa. Se for OUTRO assunto com a mesma pessoa, registre com o assunto no titulo "
            "(ex: 'Falar com o Mikael sobre o contrato')."
        ),
    }


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
    if path.startswith("/static/") or path == "/service-worker.js":
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
        "/api/atalho/despertador",
        "/api/atalho/app",
        "/api/atalho/comando-voz",
        "/api/atalho/perguntar",
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
            return jsonify({"error": "PIN de acesso ainda não configurado."}), 401
        return redirect("/configurar-pin")

    if path in ROTAS_PUBLICAS:
        return None

    if not session.get("autenticado"):
        if path.startswith("/api/"):
            return jsonify({"error": "não autenticado"}), 401
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
                return jsonify({"error": "O PIN já foi configurado."}), 400
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
    if not session.get("modo_visitante"):
        return False
    # 2026-10-12: o Alex ligou sem querer (1 toque, escondido em Configuracoes) e ficou 2 dias com
    # o chat recusando tudo. Agora desliga sozinho depois de MODO_VISITANTE_MINUTOS - visitante e
    # "passar o celular pra alguem", nao estado permanente. Sessao antiga sem a hora = ja expirou.
    desde = session.get("modo_visitante_desde")
    if not isinstance(desde, (int, float)) or time.time() - desde > MODO_VISITANTE_MINUTOS * 60:
        session["modo_visitante"] = False
        session.pop("modo_visitante_desde", None)
        return False
    return True


MODO_VISITANTE_MINUTOS = 60


def _recusar_no_modo_visitante():
    """Revisao da Fase 6: rota que ESCREVE algo com efeito fora da tela
    (desfazer, memoria que entra no prompt da IA, padrao aprendido do
    classificador, agenda do iCloud, conversao do brain dump) nunca roda no
    modo visitante - devolve a resposta 403 pronta, ou None pra seguir."""
    if _modo_visitante_ativo():
        return jsonify({"error": "indisponivel no modo visitante"}), 403
    return None


def _modo_teste_ia_ativo(conn) -> bool:
    """Config persistida (tabela `configuracoes`, nao sessao - ao contrario
    do modo visitante): o Alex liga antes de testar o visual no celular pelo
    Render e o estado continua ligado entre sessoes/logins ate ele desligar
    de volta. So essa pessoa ve o toggle (fica dentro do login por PIN, igual
    o resto do app - nao ha usuario nenhum alem dela)."""
    return (obter_configuracao(conn, "modo_teste_ia") or "0") == "1"


@app.route("/service-worker.js")
def service_worker_raiz():
    """O mesmo static/service-worker.js, mas servido da RAIZ (2026-10-10). Registrado de
    /static/, o alcance dele era so /static/ - nunca controlava a pagina principal, entao
    `serviceWorker.ready` nunca resolvia e o iPhone nunca deixava assinar as notificacoes
    (a linha ficava "Indisponivel")."""
    res = send_file(os.path.join(app.static_folder, "service-worker.js"), mimetype="application/javascript")
    res.headers["Cache-Control"] = "no-cache"
    res.headers["Service-Worker-Allowed"] = "/"
    return res


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
                    caminho, legenda=f"Backup automático semanal do painel - {date.today().isoformat()}"
                )
            except Exception as e:  # nunca deixa uma falha do Telegram derrubar o backup local
                app.logger.error("backup automatico: falha ao enviar pro Telegram: %s", e)
    except Exception as e:
        # ultima rede de seguranca - qualquer coisa inesperada aqui (disco
        # cheio, permissao negada, etc.) fica so no log, o scheduler segue
        # rodando normalmente na proxima semana
        app.logger.error("backup automatico semanal falhou: %s", e)


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
            partes.append(f"bem abaixo da media dos últimos dias ({round(media)} passos)")
        elif diff_pct >= 20:
            partes.append(f"bem acima da media dos últimos dias ({round(media)} passos)")
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
# Decisao do Alex (2026-10-10, substitui a regra A10 "nunca lucro/margem/VGV"): o card
# mostra Dinheiro hoje (saldo_caixa), A receber das vendas (a_receber), Lucro das obras
# prontas (lucro_obras_fechadas, so obra com tudo vendido e recebido) e A venda
# (estoque_a_venda + unidades_a_venda) - numeros prontos da construtora v3.99.90+,
# nada recalculado aqui. "Entradas x Gastos" parecia prejuizo e saiu da tela.
# lucro_liquido e margem (gerais) continuam descartados na entrada.
CAMPOS_RESUMO_CONSTRUTORA_PERMITIDOS = (
    "status", "tot_entradas", "tot_saidas", "saldo_caixa", "a_receber",
    "lucro_obras_fechadas", "obras_fechadas", "estoque_a_venda", "unidades_a_venda",
)
# pagador: "empresa" | "socio" ("socio" = o Ademir paga em especie, nao sai do caixa)
CAMPOS_CONTA_CONSTRUTORA_PERMITIDOS = ("vencimento", "valor", "fornecedor", "descricao", "dias_ate_vencer", "pagador")


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
    nada. Compra digitada no chat que TAMBEM veio no banco (mesmo valor, mesmo
    dia) conta uma vez so - fica a do banco (db.gastos_chat_repetidos_no_banco)."""
    repetidos = gastos_chat_repetidos_no_banco(conn)
    expenses_reais = conn.execute(
        "SELECT id, amount, category, description, source_text, created_at FROM expenses WHERE tipo = 'real'"
    ).fetchall()
    unificado = [
        {k: r[k] for k in ("amount", "category", "description", "source_text", "created_at")}
        for r in expenses_reais
        if r["id"] not in repetidos
    ]
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
    gasto_real = total_gasto_real_mes(conn, ano_mes)
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
    # proxima conta que sai do CAIXA da empresa (pagador "socio" = o Ademir paga em especie)
    da_empresa = [c for c in contas if c.get("pagador") != "socio"]
    proxima = (da_empresa or contas)[0]
    quando = _quando_conta_construtora(proxima["dias_ate_vencer"])
    quem = proxima.get("fornecedor") or proxima.get("descricao") or "fornecedor não informado"
    socio = " (o Ademir paga em espécie, não sai do caixa da empresa)" if proxima.get("pagador") == "socio" else ""
    extra = f", mais {len(contas) - 1} outra(s) conta(s) em aberto" if len(contas) > 1 else ""
    return f"próxima conta a pagar da construtora: {quem}, {quando}{socio}{extra}"


def _construtora_contexto_resumo() -> str | None:
    """Frase factual pro resumo do dia / chat com os 4 numeros do card (decisao do Alex
    10/10) e o tempo ate a proxima conta - tudo pronto da API da construtora, nenhuma
    conta feita aqui nem pela IA."""
    dados = _buscar_resumo_construtora()
    if not dados or dados.get("status") != "ok":
        return None
    def _num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    partes = []
    if _num(dados.get("saldo_caixa")):
        partes.append(f"dinheiro em caixa hoje R$ {dados['saldo_caixa']:.2f}")
    if _num(dados.get("a_receber")):
        partes.append(f"a receber das vendas ja feitas R$ {dados['a_receber']:.2f}")
    if _num(dados.get("lucro_obras_fechadas")):
        partes.append(f"lucro das obras prontas R$ {dados['lucro_obras_fechadas']:.2f}")
    if _num(dados.get("estoque_a_venda")):
        unid = dados.get("unidades_a_venda")
        partes.append(f"a venda R$ {dados['estoque_a_venda']:.2f}" + (f" ({int(unid)} unidades)" if _num(unid) else ""))
    contas_texto = _construtora_contexto_contas()
    if not partes:
        return contas_texto  # campo novo faltando: so a proxima conta (ou nada)
    texto = ", ".join(partes) + " (numeros prontos da construtora, nao recalcule)"
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
            "SELECT 1 FROM tasks WHERE recorrente_origem_id = ? AND due_date = ? "
            "UNION ALL SELECT 1 FROM tarefas_puladas WHERE origem_id = ? AND data = ?",
            (m["id"], hoje_iso, m["id"], hoje_iso),
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


def apagar_tarefa_com_desfazer(conn, tarefa) -> dict:
    """Apaga a tarefa (e os passos dela) e devolve o efeito `tarefa_apagada` com tudo que o
    Desfazer precisa pra devolver igual: a linha, os passos e - se for o dia de uma rotina - o
    "pulo" daquele dia (sem ele, materializar_tarefas_recorrentes recriava a tarefa no proximo
    tick). Sem commit: quem chama decide. Usado pela IA (apagar_tarefa) e pelo arrastar-pra-
    excluir da aba Tarefas (DELETE /api/tasks/<id>)."""
    linha = {c: tarefa[c] for c in db.TAREFA_RESTAURAVEL if c in tarefa.keys()}
    subtarefas = [
        {c: s[c] for c in db.SUBTAREFA_RESTAURAVEL}
        for s in conn.execute(
            "SELECT title, completed_at, position FROM subtasks WHERE task_id = ? ORDER BY position", (tarefa["id"],)
        ).fetchall()
    ]
    efeito = {
        "entidade": "tarefa_apagada", "id": tarefa["id"], "linha": linha, "subtarefas": subtarefas,
        "rotulo": "Tarefa", "titulo": tarefa["title"],
        "antes": {"situacao": "na lista"}, "depois": {"situacao": "apagada"},
    }
    origem = tarefa["recorrente_origem_id"] if "recorrente_origem_id" in tarefa.keys() else None
    if origem and tarefa["due_date"]:
        conn.execute("INSERT OR IGNORE INTO tarefas_puladas (origem_id, data) VALUES (?, ?)", (origem, tarefa["due_date"]))
        efeito["pulo"] = {"origem_id": origem, "data": tarefa["due_date"]}
        efeito["depois"] = {"situacao": "pulada hoje (a rotina continua)"}
    conn.execute("DELETE FROM subtasks WHERE task_id = ?", (tarefa["id"],))
    conn.execute("DELETE FROM tasks WHERE id = ?", (tarefa["id"],))
    return efeito


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
        return {"erro": "não consegui criar o evento no iCloud agora - tenta de novo"}
    registrar_evento_criado(conn, resultado["uid"], titulo, resultado["inicio"], resultado["fim"])
    return {"ok": True, **resultado}


def _apagar_evento_agenda(conn, uid: str) -> dict:
    # A guarda de verdade e essa: SO apaga se o painel registrou que foi ele
    # quem criou. Nunca chega a chamar o iCloud se o uid nao estiver aqui.
    if not evento_criado_pelo_painel(conn, uid):
        return {"erro": "esse evento não foi criado pelo painel - nunca mexo em evento que eu não criei"}
    try:
        caldav_client.apagar_evento(uid)
    except caldav_client.NaoConfiguradoError as erro:
        return {"erro": str(erro)}
    except Exception:
        return {"erro": "não consegui apagar o evento no iCloud agora - tenta de novo"}
    esquecer_evento_criado(conn, uid)
    return {"ok": True}


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
    import voz_premium  # saudacao pela hora (antes era "Bom dia" a qualquer hora)

    saudacao = voz_premium.saudacao_da_hora(datetime.now().hour)
    return f"{saudacao}. {agenda_texto} {notificacoes.resumo_manha_gastos_pendentes(conn)}"


# Faixa M4 (uso diario): o texto da IA do resumo do dia so precisa ser gerado
# de novo quando algo relevante muda - nao a cada carregamento da pagina.
# "Relevante" = tarefa importante (com data pra hoje ou atrasada - a tabela
# tasks nao tem campo de prioridade) nova/concluida hoje, ou gasto real de hoje acima deste limiar (R$100). Abaixo disso (ex.:
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
        "SELECT id FROM tasks WHERE due_date IS NOT NULL AND due_date <= ? AND completed_at IS NULL ORDER BY id",
        (today,),
    ).fetchall()
    tarefas_concluidas_hoje = conn.execute(
        "SELECT id FROM tasks WHERE due_date IS NOT NULL AND due_date <= ? AND date(completed_at) = ? ORDER BY id",
        (today, today),
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
        return "1 item passou do horário sem confirmar"
    return f"{passados_sem_confirmar} itens passaram do horário sem confirmar"


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


_DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


def _agora_brasilia() -> datetime:
    """Hora oficial de Brasilia independente do fuso da maquina."""
    return datetime.now(ZoneInfo("America/Sao_Paulo"))


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
    agora = _agora_brasilia()
    linhas = [
        f"Agora: {_DIAS_SEMANA[agora.weekday()]}, {agora:%d/%m/%Y}, {agora:%H:%M} (horário de Brasília)",
        f"Tarefas pendentes: {', '.join(r['title'] for r in pendentes) or 'nenhuma'}",
        f"Gasto de hoje (já realizado): R$ {gasto_hoje:.2f}",
        f"Gasto planejado/cogitado hoje (ainda não decidido): R$ {gasto_planejado:.2f}",
        f"Compromissos de hoje (em ordem de horário): {eventos_txt or 'nenhum'}",
    ]
    linhas.extend(vida_assistente.linhas_contexto(conn, agora.replace(tzinfo=None)))
    linhas.extend(feriados.linhas_contexto(agora.date()))
    comida_hoje = refeicoes.linha_contexto(conn, agora.date())
    if comida_hoje:
        linhas.append(comida_hoje)
    linhas.extend(diario.linhas_contexto(conn, agora.date()))
    quiz = estudo_quiz.linha_contexto(conn, agora.date())
    if quiz:
        linhas.append(quiz)
    if saude:
        linhas.append(f"Saúde hoje: {saude}")
    if construtora:
        linhas.append(f"Construtora (financeiro geral): {construtora}")
    if clima_hoje:
        linhas.append(f"Previsão do tempo hoje: {clima_hoje}")
    if proximos_voos:
        voos_txt = ", ".join(
            f"{v['data']} pra {v['destino']}" + (f" ({v['horas']}h)" if v.get("horas") else "")
            for v in proximos_voos
        )
        linhas.append(f"Próximos voos agendados: {voos_txt}")
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
                f"Plano de semana proposto AGUARDANDO confirmação do Alex (ainda NÃO foi criado "
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


MODO_VOZ_INSTRUCAO = (
    "MODO CONVERSA POR VOZ: o Alex esta FALANDO com voce e a sua resposta vai ser lida em voz "
    "alta. Fale como numa ligacao com um amigo: 2 a 4 frases naturais e completas (nunca so "
    "uma palavra seca), sem lista, sem markdown, sem emoji, sem setas '->', numeros e horarios "
    "escritos do jeito que se fala. Pontue pra voz soar humana: virgula onde a gente respira, "
    "frase curta depois de uma longa, uma reacao rapida no comeco quando cabe ('ah, boa', 'eita'). "
    "Pode fazer uma pergunta de volta quando fizer sentido."
)


# 2026-10-12: mensagem que veio de AUDIO (microfone do chat ou modo conversa). Ja passou pela
# limpeza (ia/funcoes/fala.py), mas o Whisper ainda pode ter trocado uma palavra por outra de
# som parecido - o chat interpreta pela intencao, como o ChatGPT/Gemini fazem.
AUDIO_INSTRUCAO = (
    "ESTA MENSAGEM VEIO DE AUDIO (transcrito automaticamente e ja limpo): pode ter sobrado palavra "
    "trocada por outra de som parecido ou frase meio torta. Entenda pela intencao e pelo contexto "
    "(tarefas, lugares, nomes que voce conhece), sem comentar a transcricao. Se ele se corrigiu no "
    "meio, vale o que ele disse por ultimo. So pergunte antes de agir quando algo CRITICO ficou "
    "ambiguo de verdade (valor em dinheiro, data/hora, nome de pessoa) - o resto, resolva sozinho."
)


def _vocabulario_do_alex(conn) -> str:
    """Grafia certa do que o Alex costuma falar (pro limpador da fala acertar nome): apelidos de
    lugar, aeronaves do diario, pessoas, e o titulo das tarefas abertas. Curto de proposito."""
    termos: list[str] = ["Brusque", "Blumenau", "Gaspar", "aeroclube", "CIV", "ANAC", "SSBL", "Fiorino",
                         "contabilidade", "notas fiscais", "CND", "construtora", "obra"]
    try:
        termos += list(vida_assistente.apelidos(conn).keys())
        termos += [r[0] for r in conn.execute(
            "SELECT DISTINCT aeronave FROM voos WHERE aeronave IS NOT NULL AND aeronave != '' LIMIT 8")]
        termos += [r[0] for r in conn.execute("SELECT nome FROM pessoas ORDER BY id DESC LIMIT 20")]
        termos += [r[0] for r in conn.execute(
            "SELECT title FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL ORDER BY id DESC LIMIT 25")]
    except Exception:  # noqa: BLE001 - vocabulario e ajuda, nunca bloqueia o audio
        pass
    vistos, saida = set(), []
    for t in termos:
        t = str(t or "").strip()
        if t and t.lower() not in vistos:
            vistos.add(t.lower())
            saida.append(t[:60])
    return "; ".join(saida)[:1800]


def _local_do_celular(local) -> dict | None:
    """Valida a localizacao que o front manda junto da mensagem ({lat, lon,
    precisao, idade_s}) e completa com o endereco aproximado (OpenStreetMap).
    Qualquer coisa estranha -> None (o chat segue sem localizacao)."""
    if not isinstance(local, dict):
        return None
    try:
        lat, lon = float(local.get("lat")), float(local.get("lon"))
        precisao = float(local.get("precisao") or 0)
        idade_s = max(0, int(float(local.get("idade_s") or 0)))
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
        return None
    if idade_s > 6 * 3600 or precisao > 5000:
        return None  # velha ou imprecisa demais pra valer como "onde estou"
    endereco = geocode_nominatim.reverso(lat, lon)
    return {
        "lat": round(lat, 5),
        "lon": round(lon, 5),
        "precisao_m": round(precisao),
        "idade_min": idade_s // 60,
        "rotulo": endereco["rotulo"] if endereco else None,
        "cidade": endereco["cidade"] if endereco else None,
    }


def _processar_mensagem_chat(
    conn, texto: str, detalhes: dict | None = None, modo_voz: bool = False, local_gps: dict | None = None,
    origem_audio: bool = False,
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
    mensagens = _historico_com_datas(
        conn, [{"role": r["papel"], "content": r["texto"], "criado_em": r.get("criado_em")} for r in historico]
    )
    mensagens.append({"role": "user", "content": texto})

    memorias_texto = [m["texto"] for m in list_memorias(conn)]
    contexto = _contexto_chat(conn)
    if modo_voz:
        contexto += "\n" + MODO_VOZ_INSTRUCAO
    if origem_audio or modo_voz:
        contexto += "\n" + AUDIO_INSTRUCAO
    local_gps = _local_do_celular(local_gps)
    if local_gps:
        onde = local_gps["rotulo"] or f"{local_gps['lat']}, {local_gps['lon']}"
        quando = "agora" if local_gps["idade_min"] < 2 else f"ha {local_gps['idade_min']} min"
        contexto += (
            f"\nLocalização atual do Alex (GPS do celular, {quando}, precisão ~{local_gps['precisao_m']} m): {onde}. "
            "Use pra 'aqui', 'perto', clima de onde ele está e rota 'daqui'."
        )

    def _rotulo_local_atual(entrada):
        """'no_local_atual' -> texto do endereco atual; sem GPS -> dict de erro."""
        if not entrada.get("no_local_atual"):
            return None
        if not local_gps:
            return {"erro": "nao recebi a localizacao do celular agora - pergunte o lugar ao Alex"}
        return local_gps["rotulo"] or f"{local_gps['lat']}, {local_gps['lon']}"

    def _plano_do_estilo(estilo, task_id, data_iso, hora, lugar, titulo):
        """O que precisa de rede vai no efeito (o card e montado sem rede) e o resumo volta pra
        IA - a frase dela tem que bater com o card."""
        efeito = {"entidade": "tarefa", "id": task_id, "estilo": estilo}
        pra_ia = {}
        if estilo in ("date", "balada") and hora:
            if lugar:
                claude_client.avisar_passo(f"Calculando o trajeto até {lugar[:40]}")
            saida = _saida_pro_compromisso(data_iso, hora, lugar)
            sair = saida["sair"] if saida else rota_voo.menos_minutos(hora, FOLGA_SEM_TRAJETO_MIN)
            efeito["saida"] = saida
            pra_ia["sair_de_casa"] = sair
            pra_ia["comecar_a_se_arrumar"] = rota_voo.menos_minutos(sair, vida_assistente.se_arrumar_min(conn))
            claude_client.avisar_passo(f"Vendo a previsão pras {hora.replace(':00', 'h').replace(':', 'h')}")
            tempo = _clima_na_hora(data_iso, hora)
            if tempo:
                efeito["clima"] = tempo
                pra_ia["temperatura_na_hora"] = tempo["temp"]
            if estilo == "balada":
                claude_client.avisar_passo("Conferindo o que tu tem no dia seguinte")
                seguinte = (date.fromisoformat(data_iso) + timedelta(days=1)).isoformat()
                amanha = _primeiro_compromisso_do_dia(conn, seguinte)
                if amanha:
                    efeito["amanha"] = amanha
                    pra_ia["dia_seguinte"] = f"{amanha['titulo']} as {amanha['hora']} - acordar ate {amanha['acordar']}"
        elif estilo == "documentos" and maps_client.configurado():
            claude_client.avisar_passo(f"Olhando o horário de {(lugar or titulo)[:40]} no Google")
            try:
                horario = maps_client.horario_funcionamento(lugar or titulo, date.fromisoformat(data_iso))
            except Exception:
                horario = None
            if horario:
                efeito["horario"] = horario
                pra_ia["horario_do_lugar"] = "fechado nesse dia" if horario.get("fechado") else ", ".join(
                    f"{a}-{b}" for a, b in horario["faixas"])
        elif estilo == "presente":
            dia = date.fromisoformat(data_iso)
            pra_ia["comprar_ate"] = max(date.today(), dia - timedelta(days=DIAS_ENTREGA_PRESENTE)).isoformat()
        return {"_efeito": efeito, **({"plano": pra_ia} if pra_ia else {})}

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
        local_tarefa = _rotulo_local_atual(entrada)
        if isinstance(local_tarefa, dict):
            return local_tarefa  # erro: pediu "aqui" sem GPS
        repetida = _tarefa_repetida(conn, entrada["titulo"], quando_data)
        if repetida:
            return _aviso_tarefa_repetida(repetida)
        # 2026-10-14 (cards da IA, 2a leva): compromisso com cara propria - so com dia marcado
        estilo = entrada.get("estilo") if entrada.get("estilo") in db.ESTILOS_TAREFA and quando_data else None
        lugar = local_tarefa or _limpar_texto(entrada.get("lugar"), 120)
        extras = _extras_do_estilo(entrada) if estilo else {}
        if estilo == "presente" and _presente_anual(entrada):
            extras["anual"] = True
        hora_tarefa = _normalizar_hora(entrada.get("hora"))
        cur = conn.execute(
            "INSERT INTO tasks (title, due_at, due_date, hora, source_text, depende_do_tempo, local, estilo, extras) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entrada["titulo"],
                entrada.get("quando"),
                quando_data,
                hora_tarefa,
                texto,
                int(bool(entrada.get("depende_do_tempo"))),
                lugar,
                estilo,
                json.dumps(extras, ensure_ascii=False) if extras else None,
            ),
        )
        conn.commit()
        resultado = {"ok": True, "_efeito": {"entidade": "tarefa", "id": cur.lastrowid}}
        if estilo:
            resultado.update(_plano_do_estilo(estilo, cur.lastrowid, quando_data, hora_tarefa, lugar, entrada["titulo"]))
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

    # ---- Edicao pela IA (2026-10-09): muda, nunca apaga, nunca mexe em valor de
    # dinheiro; cada mudanca vira um card "edicao" com Desfazer (volta os valores
    # antigos - db.EDICAO_COLUNAS). Achar o registro e SEMPRE por busca exata no
    # banco: 0 ou 2+ resultados = erro com as candidatas, nunca chute.
    def _recusa_visitante():
        if has_request_context() and _modo_visitante_ativo():
            return {"erro": (
                "o painel esta no MODO VISITANTE (ele liga isso quando passa o celular pra alguem) e nada "
                "pode ser alterado. Diga ao Alex: toque no selo 'Modo visitante' no topo da tela e digite o "
                "PIN pra sair (ou espere: desliga sozinho em ate 1 hora)."
            )}
        return None

    def _editar(tabela, id_, novos: dict, rotulo: str, titulo: str):
        """Aplica `novos` (coluna -> valor) e devolve o efeito do card com os
        valores antigos so das colunas que mudaram de fato."""
        colunas = db.EDICAO_COLUNAS[tabela]
        novos = {c: v for c, v in novos.items() if c in colunas}
        if not novos:
            return None
        atual = conn.execute(f"SELECT {', '.join(colunas)} FROM {tabela} WHERE id = ?", (id_,)).fetchone()
        if not atual:
            return None
        mudou = {c: v for c, v in novos.items() if atual[c] != v}
        if not mudou:
            return None
        conn.execute(f"UPDATE {tabela} SET {', '.join(c + ' = ?' for c in mudou)} WHERE id = ?", [*mudou.values(), id_])
        return {
            "entidade": "edicao", "tabela": tabela, "id": id_, "rotulo": rotulo, "titulo": titulo,
            "antes": {c: atual[c] for c in mudou}, "depois": mudou,
        }

    def _achar(tabela, sql_where, params, texto, coluna_titulo, extra_sql=""):
        """Acha UM registro pelo nome que a IA mandou. 1) igual; 2) contem o trecho;
        3) parecido por palavras (sem o/os/de/pra, plural, acento - "lavar o carro" acha
        "Lavar os carros por dentro"). So escolhe quando um ganha com folga; senao devolve
        erro COM a lista do que existe, pra IA tentar de novo com o nome certo (antes ela
        recebia "nenhum registro" e dizia ao Alex que nao conseguia renomear)."""
        alvo = aprendizado.normalizar_consulta(str(texto or ""))
        if not alvo:
            return None, {"erro": "faltou dizer qual registro (titulo ou um trecho dele)"}
        rows = conn.execute(f"SELECT * FROM {tabela} WHERE {sql_where} {extra_sql}", params).fetchall()
        norm = {r["id"]: aprendizado.normalizar_consulta(r[coluna_titulo] or "") for r in rows}
        exatas = [r for r in rows if norm[r["id"]] == alvo]
        if len(exatas) == 1:
            return exatas[0], None
        contem = [r for r in rows if alvo in norm[r["id"]] or (len(norm[r["id"]]) >= 4 and norm[r["id"]] in alvo)]
        if len(contem) == 1:
            return contem[0], None
        base = contem or rows
        notas = sorted(((_parecido(alvo, norm[r["id"]]), r) for r in base), key=lambda x: -x[0])
        if notas and notas[0][0] >= 0.6 and (len(notas) == 1 or notas[0][0] - notas[1][0] >= 0.2):
            return notas[0][1], None
        if contem:
            return None, {"erro": "mais de um registro combina - peça pro Alex dizer qual (ou use o titulo exato)",
                          "candidatas": [r[coluna_titulo] for r in contem][:8]}
        return None, {
            "erro": "nenhum registro com esse nome - tente de novo com um dos titulos de 'existentes'",
            "existentes": [r[coluna_titulo] for _, r in notas][:12],
        }

    _PALAVRAS_VAZIAS = {"o", "os", "a", "as", "um", "uma", "de", "do", "da", "dos", "das", "no", "na", "nos",
                        "nas", "pra", "pro", "para", "por", "com", "e", "em", "ao", "que", "meu", "minha"}

    def _palavras(texto_norm):
        saida = set()
        for p in re.findall(r"[a-z0-9]+", texto_norm):
            if p in _PALAVRAS_VAZIAS:
                continue
            saida.add(p[:-1] if len(p) > 4 and p.endswith("s") else p)  # carros ~ carro
        return saida

    def _parecido(alvo_norm, titulo_norm):
        """Fracao das palavras do pedido que aparecem no titulo (0..1)."""
        a, t = _palavras(alvo_norm), _palavras(titulo_norm)
        if not a or not t:
            return 0.0
        return len(a & t) / len(a)

    def _data_valida(valor):
        if valor in (None, ""):
            return None
        if not isinstance(valor, str):
            raise ValueError("data invalida")
        date.fromisoformat(valor)
        return valor

    def exec_ajustar_tarefa(entrada):
        recusa = _recusa_visitante()
        if recusa:
            return recusa
        status = entrada.get("status")
        cond = "completed_at IS NOT NULL" if status == "reabrir" else "completed_at IS NULL"
        tarefa, erro = _achar("tasks", f"{cond} AND NOT (recorrencia IS NOT NULL AND due_date IS NULL)", (),
                              entrada.get("titulo"), "title")
        if erro:
            return erro
        try:
            data = _data_valida(entrada.get("quando_data"))
        except ValueError:
            return {"erro": f"data invalida: {entrada.get('quando_data')!r}"}
        novos = {}
        if entrada.get("sem_hora"):
            novos["hora"] = None
        elif entrada.get("hora"):
            hora = _normalizar_hora(entrada.get("hora"))
            if not hora:
                return {"erro": f"hora invalida: {entrada.get('hora')!r}"}
            novos["hora"] = hora
        if data:
            novos["due_date"] = data
        novo_titulo = (entrada.get("novo_titulo") or "").strip()
        if novo_titulo:
            novos["title"] = novo_titulo[:200]
        if status == "concluir":
            novos["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        elif status == "reabrir":
            novos["completed_at"] = None
        if not novos:
            return {"erro": "nada pra mudar - informe hora, quando_data, novo_titulo ou status"}
        efeito = _editar("tasks", tarefa["id"], novos, "Tarefa", tarefa["title"])
        conn.commit()
        if not efeito:
            return {"ok": True, "titulo": tarefa["title"], "obs": "ja estava assim, nada mudou"}
        # titulo de DEPOIS (2026-10-16: devolvia o antigo e a IA achou que a troca nao pegou)
        resultado = {"ok": True, "titulo": novos.get("title", tarefa["title"]), "_efeito": efeito}
        if "title" in novos and novos["title"] != tarefa["title"]:
            resultado["titulo_antes"] = tarefa["title"]
        return resultado

    def exec_mover_tarefas(entrada):
        recusa = _recusa_visitante()
        if recusa:
            return recusa
        try:
            de = _data_valida(entrada.get("de_data")) or date.today().isoformat()
            para = _data_valida(entrada.get("para_data"))
        except ValueError:
            return {"erro": "data invalida"}
        if not para:
            return {"erro": "faltou para_data"}
        periodo = entrada.get("periodo") or "dia_todo"
        faixas = {"manha": ("00:00", "11:59"), "tarde": ("12:00", "17:59"), "noite": ("18:00", "23:59")}
        rows = conn.execute(
            "SELECT id, title, hora, due_date FROM tasks WHERE completed_at IS NULL AND due_date = ? "
            "AND NOT (recorrencia IS NOT NULL AND due_date IS NULL) AND recorrente_origem_id IS NULL ORDER BY hora, id",
            (de,),
        ).fetchall()
        if periodo in faixas:
            a, b = faixas[periodo]
            rows = [r for r in rows if r["hora"] and a <= r["hora"] <= b]
        if not rows:
            return {"erro": "nenhuma tarefa pendente nesse dia/periodo", "dia": de, "periodo": periodo}
        efeitos = []
        for r in rows[:30]:
            ef = _editar("tasks", r["id"], {"due_date": para}, "Tarefa", r["title"])
            if ef:
                efeitos.append(ef)
        conn.commit()
        return {"ok": True, "movidas": [r["title"] for r in rows[:30]], "para": para, "_efeito": efeitos}

    def exec_ajustar_lembrete(entrada):
        recusa = _recusa_visitante()
        if recusa:
            return recusa
        lembrete, erro = _achar("lembretes", "1 = 1", (), entrada.get("titulo"), "titulo")
        if erro:
            return erro
        try:
            data = _data_valida(entrada.get("data"))
        except ValueError:
            return {"erro": f"data invalida: {entrada.get('data')!r}"}
        novos = {}
        if data:
            novos["data"] = data
        if (entrada.get("novo_titulo") or "").strip():
            novos["titulo"] = entrada["novo_titulo"].strip()[:200]
        if isinstance(entrada.get("recorrente"), bool):
            novos["recorrente"] = int(entrada["recorrente"])
        if isinstance(entrada.get("despertar"), bool):
            novos["despertar"] = int(entrada["despertar"])
        if not novos:
            return {"erro": "nada pra mudar"}
        efeito = _editar("lembretes", lembrete["id"], novos, "Lembrete", lembrete["titulo"])
        conn.commit()
        return {"ok": True, "titulo": lembrete["titulo"], **({"_efeito": efeito} if efeito else {"obs": "ja estava assim"})}

    def exec_ajustar_voo(entrada):
        recusa = _recusa_visitante()
        if recusa:
            return recusa
        try:
            dia = _data_valida(entrada.get("data_do_voo"))
        except ValueError:
            return {"erro": "data_do_voo invalida"}
        if not dia:
            return {"erro": "faltou data_do_voo (AAAA-MM-DD)"}
        rows = conn.execute("SELECT * FROM voos WHERE data = ? ORDER BY id", (dia,)).fetchall()
        filtro_origem = (entrada.get("origem_atual") or "").strip().upper()
        filtro_destino = (entrada.get("destino_atual") or "").strip().upper()
        if filtro_origem:
            rows = [r for r in rows if (r["origem"] or "").upper() == filtro_origem]
        if filtro_destino:
            rows = [r for r in rows if (r["destino"] or "").upper() == filtro_destino]
        if len(rows) != 1:
            return {
                "erro": "nenhum voo nesse dia" if not rows else "mais de um voo nesse dia - informe origem_atual/destino_atual",
                "voos_do_dia": [f"{r['origem'] or '?'}-{r['destino']}" for r in rows][:6],
            }
        voo = rows[0]
        novos = {}
        for campo in ("aeronave", "funcao", "origem", "destino", "observacao"):
            valor = entrada.get(campo)
            if isinstance(valor, str) and valor.strip():
                v = valor.strip()[:300]
                novos[campo] = v.upper().replace("-", "") if campo == "aeronave" else v
        if entrada.get("horas") not in (None, ""):
            try:
                horas = float(entrada["horas"])
            except (TypeError, ValueError):
                return {"erro": "horas invalidas"}
            if not 0 < horas <= 24:
                return {"erro": "horas fora do razoavel (0 a 24)"}
            novos["horas"] = round(horas, 2)
        try:
            nova_data = _data_valida(entrada.get("nova_data"))
        except ValueError:
            return {"erro": "nova_data invalida"}
        if nova_data:
            novos["data"] = nova_data
        if not novos:
            return {"erro": "nada pra mudar"}
        efeito = _editar("voos", voo["id"], novos, "Voo", f"{dia} {voo['origem'] or ''}-{voo['destino']}".strip())
        conn.commit()
        return {"ok": True, **({"_efeito": [efeito, {"entidade": "voo_resumo", "consulta": True}]} if efeito else {"obs": "ja estava assim"})}

    def exec_ajustar_gasto(entrada):
        recusa = _recusa_visitante()
        if recusa:
            return recusa
        desde = (date.today() - timedelta(days=120)).isoformat()
        gasto, erro = _achar("expenses", "date(created_at) >= ?", (desde,), entrada.get("descricao_atual"), "description",
                             "ORDER BY id DESC")
        if erro:
            return erro
        return _ajustar_transacao("expenses", "Gasto", gasto, entrada)

    def _valor_corrigido(entrada):
        """Valor novo pedido pelo Alex ("errei, foi 45") - so numero positivo razoavel."""
        bruto = entrada.get("valor")
        if bruto in (None, ""):
            return None, None
        try:
            valor = round(float(bruto), 2)
        except (TypeError, ValueError):
            return None, {"erro": "valor invalido"}
        if not 0 < valor < 1_000_000:
            return None, {"erro": "valor fora do razoavel"}
        return valor, None

    def _ajustar_transacao(tabela, rotulo, registro, entrada):
        novos = {}
        if (entrada.get("categoria") or "").strip():
            novos["category"] = entrada["categoria"].strip().lower()[:60]
        if (entrada.get("nova_descricao") or "").strip():
            novos["description"] = entrada["nova_descricao"].strip()[:200]
        valor, erro = _valor_corrigido(entrada)
        if erro:
            return erro
        if valor is not None:
            novos["amount"] = valor
        if not novos:
            return {"erro": "nada pra mudar (valor, categoria ou descricao)"}
        efeito = _editar(tabela, registro["id"], novos, rotulo, registro["description"] or registro["category"])
        conn.commit()
        return {"ok": True, **({"_efeito": efeito} if efeito else {"obs": "ja estava assim"})}

    def exec_ajustar_renda(entrada):
        recusa = _recusa_visitante()
        if recusa:
            return recusa
        desde = (date.today() - timedelta(days=120)).isoformat()
        renda, erro = _achar("incomes", "date(created_at) >= ?", (desde,), entrada.get("descricao_atual"), "description",
                             "ORDER BY id DESC")
        if erro:
            return erro
        return _ajustar_transacao("incomes", "Renda", renda, entrada)

    def exec_apagar_tarefa(entrada):
        """Apaga uma tarefa errada/duplicada (pedido do Alex). Volta inteira no Desfazer."""
        recusa = _recusa_visitante()
        if recusa:
            return recusa
        tarefa, erro = _achar("tasks", "recorrencia IS NULL", (), entrada.get("titulo"), "title", "ORDER BY id DESC")
        if erro:
            return erro
        efeito = apagar_tarefa_com_desfazer(conn, tarefa)
        conn.commit()
        resultado = {"ok": True, "apagada": tarefa["title"], "_efeito": efeito}
        if efeito.get("pulo"):
            resultado["obs"] = "era o dia de hoje de uma rotina: so hoje foi pulado, a rotina continua nos outros dias"
        return resultado

    def exec_consultar_diario(entrada):
        """O que aconteceu num dia (diario.py). 'ontem', 'sabado' etc. viram data em codigo."""
        hoje_br = _agora_brasilia().date()
        dia_d = diario.resolver_dia_passado(entrada.get("data") or entrada.get("dia"), hoje_br)
        if not dia_d:
            return {"erro": "nao entendi o dia - mande 'ontem', 'sabado' ou AAAA-MM-DD"}
        return diario.consultar(conn, dia_d, hoje_br)

    def exec_buscar_na_memoria(entrada):
        """Memoria sob demanda (memoria.py): acha QUANDO algo aconteceu. So roda se a IA chamar."""
        def _dia_iso_ou_none(v):
            try:
                return date.fromisoformat(str(v)[:10]) if v else None
            except ValueError:
                return None

        return memoria.buscar(
            conn, entrada.get("assunto") or entrada.get("termo") or "",
            de=_dia_iso_ou_none(entrada.get("de")), ate=_dia_iso_ou_none(entrada.get("ate")),
            limite=entrada.get("limite") or memoria.LIMITE_PADRAO, hoje=_agora_brasilia().date(),
        )

    def exec_consultar_feriados(entrada):
        """Feriados/pontos facultativos de um ano inteiro ou de um mes (feriados.py, calculado)."""
        hoje_br = _agora_brasilia().date()
        ano = _inteiro_no_intervalo(entrada.get("ano"), 1900, 2200) or hoje_br.year
        mes = _inteiro_no_intervalo(entrada.get("mes"), 1, 12)
        lista = [f for f in feriados.do_ano(ano) if not mes or f["data"].month == mes]
        return {"ano": ano, "feriados": [
            {"data": f["data"].isoformat(), "dia_da_semana": diario.DIAS_SEMANA[f["data"].weekday()],
             "nome": f["nome"], "tipo": f["tipo"], **({"emenda": feriados.emenda(f)} if feriados.emenda(f) else {})}
            for f in lista
        ]}

    def exec_anotar_no_diario(entrada):
        recusa = _recusa_visitante()
        if recusa:
            return recusa
        hoje_br = _agora_brasilia().date()
        dia_d = diario.resolver_dia_passado(entrada.get("dia"), hoje_br)
        texto_anot = _texto_curto(entrada.get("texto"), 300)
        if not dia_d or not texto_anot:
            return {"erro": "faltou o dia ('ontem', 'sabado', AAAA-MM-DD) ou o texto"}
        diario.anotar(conn, dia_d, texto_anot)
        return {"ok": True, "dia": diario.rotulo_dia(dia_d, hoje_br), "anotado": texto_anot}

    def exec_registrar_acordei(entrada):
        recusa = _recusa_visitante()
        if recusa:
            return recusa
        agora = _agora_brasilia().replace(tzinfo=None, second=0, microsecond=0)
        hora = _normalizar_hora(entrada.get("hora"))
        quando = agora
        if hora:
            h, m = map(int, hora.split(":"))
            quando = agora.replace(hour=h, minute=m)
            if quando > agora:
                return {"erro": "essa hora ainda nao chegou - confirme com o Alex quando ele acordou"}
        vida_assistente.registrar_acordou(conn, quando)
        conn.commit()
        resultado = {"ok": True, "acordou": f"{quando:%H:%M}"}
        p = vida_assistente.perfil(conn, agora.date())
        if p["peso_kg"]:
            resultado["meta_comida"] = vida_assistente.metas_comida(p["peso_kg"], p["altura_cm"], p["idade"], p["objetivo"])
            resultado["primeira_refeicao_ate"] = f"{quando + timedelta(hours=1):%H:%M}"
        return resultado

    def exec_atualizar_perfil(entrada):
        recusa = _recusa_visitante()
        if recusa:
            return recusa
        feito = {}
        altura = entrada.get("altura_cm")
        if altura not in (None, ""):
            try:
                altura = float(altura)
            except (TypeError, ValueError):
                return {"erro": "altura invalida"}
            altura = altura * 100 if altura < 3 else altura  # "1,69" -> 169
            if not 120 <= altura <= 230:
                return {"erro": "altura fora do razoavel"}
            definir_configuracao(conn, "perfil_altura_cm", f"{altura:.0f}")
            feito["altura_cm"] = round(altura)
        objetivo = entrada.get("objetivo")
        if objetivo:
            if objetivo not in vida_assistente.OBJETIVOS:
                return {"erro": f"objetivo deve ser um de {list(vida_assistente.OBJETIVOS)}"}
            definir_configuracao(conn, "perfil_objetivo", objetivo)
            feito["objetivo"] = objetivo
        academia = (entrada.get("academia") or "").strip()[:80]
        if academia:
            definir_configuracao(conn, "perfil_academia", academia)
            feito["academia"] = academia
        peso = entrada.get("peso_kg")
        if peso not in (None, ""):
            try:
                peso = float(peso)
            except (TypeError, ValueError):
                return {"erro": "peso invalido"}
            if not 30 <= peso <= 250:
                return {"erro": "peso fora do razoavel"}
            create_medida_corporal(conn, "peso", peso, "kg", date.today().isoformat())
            feito["peso_kg"] = peso
        if not feito:
            return {"erro": "nada pra atualizar"}
        conn.commit()
        return {"ok": True, **feito}

    def exec_salvar_lugar_apelido(entrada):
        recusa = _recusa_visitante()
        if recusa:
            return recusa
        chave = vida_assistente.salvar_apelido(conn, entrada.get("apelido") or "", entrada.get("endereco") or "")
        if not chave:
            return {"erro": "apelido ou endereco vazio (casa ja usa o endereco de casa)"}
        conn.commit()
        return {"ok": True, "apelido": chave, "endereco": entrada["endereco"].strip()[:200]}

    def exec_planejar_dia(entrada):
        """Monta o dia inteiro de uma vez: cada bloco vira tarefa com hora (ou ajusta a hora de
        uma tarefa que ja existe com o mesmo nome) - um card so com a trilha do dia e Desfazer."""
        recusa = _recusa_visitante()
        if recusa:
            return recusa
        try:
            dia = _data_valida(entrada.get("data")) or _agora_brasilia().date().isoformat()
        except ValueError:
            return {"erro": "data invalida"}
        blocos = entrada.get("blocos")
        if not isinstance(blocos, list) or not blocos:
            return {"erro": "mande os blocos do dia (titulo + hora)"}
        if len(blocos) > 30:
            return {"erro": "blocos demais (maximo 30)"}
        pendentes = conn.execute(
            "SELECT id, title FROM tasks WHERE completed_at IS NULL AND recorrencia IS NULL "
            "AND (due_date = ? OR due_date IS NULL)", (dia,),
        ).fetchall()
        # feitas ha pouco (ultimas 12h): um bloco com o mesmo nome NAO vira tarefa nova - era
        # o caso do Mikael em 2026-10-14 (ja concluida, a IA "remarcou" e nasceu outra)
        feitas = conn.execute(
            "SELECT id, title FROM tasks WHERE completed_at >= datetime('now', '-12 hours') "
            "AND recorrencia IS NULL AND (due_date = ? OR due_date IS NULL)", (dia,),
        ).fetchall()
        normal = {r["id"]: aprendizado.normalizar_consulta(r["title"]) for r in [*pendentes, *feitas]}
        efeitos, ignorados, usados, ja_feitas = [], [], set(), []
        mapa = []  # (titulo normalizado, id da tarefa, hora) - pro plano B achar cada bloco
        for bloco in blocos:
            if not isinstance(bloco, dict):
                continue
            # o "(ate HH:MM)" quem poe e o codigo, a partir do `fim` validado (a IA as vezes
            # escrevia um "ate" errado direto no titulo)
            titulo = re.sub(r"\s*\(at[eé] \d{1,2}[:h]\d{2}\)", "", str(bloco.get("titulo") or "")).strip()[:150]
            hora = _normalizar_hora(bloco.get("hora"))
            if not titulo or not hora:
                ignorados.append(titulo or "(sem titulo)")
                continue
            fim = _normalizar_hora(bloco.get("fim"))
            if fim and fim > hora and f"até {fim}" not in titulo:
                titulo = f"{titulo} (até {fim})"
            local = str(bloco.get("local") or "").strip()[:200] or None
            if local:
                local = vida_assistente.resolver_lugar(conn, local)
            alvo = aprendizado.normalizar_consulta(str(bloco.get("titulo") or ""))
            palavras_alvo = _palavras(alvo)

            def _mesma(r):
                n = normal[r["id"]]
                if n == alvo:
                    return True
                if len(alvo) < 4:
                    return False
                if alvo in n or (len(n) >= 6 and n in alvo):
                    return True
                # todas as palavras de um lado no outro ("pegar cnd" ~ "pegar a cnd"), 2+ palavras
                p = _palavras(n)
                menor, maior = (palavras_alvo, p) if len(palavras_alvo) <= len(p) else (p, palavras_alvo)
                return len(menor) >= 2 and menor <= maior

            existente = next((r for r in pendentes if r["id"] not in usados and _mesma(r)), None)
            if existente:
                usados.add(existente["id"])
                novos = {"hora": hora, "due_date": dia}
                if local:
                    novos["local"] = local
                ef = _editar("tasks", existente["id"], novos, "Tarefa", existente["title"])
                if ef:
                    efeitos.append(ef)
                mapa.append((alvo, existente["id"], hora))
                continue
            # so nome igual (nao o casamento frouxo de _mesma): pular uma tarefa nova por
            # engano seria pior que a duplicata
            feita = next((r for r in feitas if normal[r["id"]] == alvo), None)
            if feita:
                ja_feitas.append(feita["title"])
                continue
            cur = conn.execute(
                "INSERT INTO tasks (title, due_date, hora, source_text, local) VALUES (?, ?, ?, ?, ?)",
                (titulo, dia, hora, texto, local),
            )
            efeitos.append({"entidade": "tarefa", "id": cur.lastrowid})
            mapa.append((alvo, cur.lastrowid, hora))
        conn.commit()
        planos = _planos_do_dia(mapa, entrada)
        if planos:
            alvo_ef = next((e for e in efeitos if e["entidade"] == "tarefa"), None)
            if alvo_ef:
                alvo_ef["planos"] = planos
            else:
                planos = None
        if not efeitos and ja_feitas:
            return {"ok": True, "dia": dia, "criadas": 0, "ja_feitas_nao_recriei": ja_feitas}
        if not efeitos:
            return {"erro": "nenhum bloco valido (cada um precisa de titulo e hora HH:MM)", "ignorados": ignorados}
        criadas = sum(1 for e in efeitos if e["entidade"] == "tarefa")
        resultado = {"ok": True, "dia": dia, "criadas": criadas, "horario_ajustado": len(efeitos) - criadas,
                     "_efeito": efeitos}
        if ignorados:
            resultado["ignorados_sem_hora"] = ignorados
        if ja_feitas:
            # a IA conta pro Alex que essas ja tavam feitas em vez de dizer "remarquei"
            resultado["ja_feitas_nao_recriei"] = ja_feitas
        if planos:
            resultado["plano_b_no_card"] = planos["b"]["nome"]
        return resultado

    def _planos_do_dia(mapa, entrada):
        """Plano B do planejar_dia (2026-10-21, prototipo aprovado): o A ja foi gravado; o B so
        vale se acha os mesmos blocos (pelo nome) e muda a hora de pelo menos um. Bloco do B que
        nao casa com nenhum do A e ignorado (o B so troca horas, nao cria tarefa)."""
        b = entrada.get("plano_b")
        if not mapa or not isinstance(b, dict) or not isinstance(b.get("blocos"), list):
            return None
        livres, itens_b = list(mapa), []
        for bloco in b["blocos"][:30]:
            if not isinstance(bloco, dict):
                continue
            hora_b = _normalizar_hora(bloco.get("hora"))
            alvo_b = aprendizado.normalizar_consulta(str(bloco.get("titulo") or ""))
            if not hora_b or not alvo_b:
                continue
            par = next((m for m in livres if m[0] == alvo_b), None) or next(
                (m for m in livres if len(alvo_b) >= 4 and len(m[0]) >= 4 and (alvo_b in m[0] or m[0] in alvo_b)), None)
            if par:
                livres.remove(par)
                itens_b.append({"id": par[1], "hora": hora_b})
        hora_a = {m[1]: m[2] for m in mapa}
        if not any(i["hora"] != hora_a[i["id"]] for i in itens_b):
            return None
        return {
            "a": {"nome": str(entrada.get("plano_a_nome") or "Plano A").strip()[:40],
                  "nota": str(entrada.get("plano_a_nota") or "").strip()[:140],
                  "itens": [{"id": m[1], "hora": m[2]} for m in mapa]},
            "b": {"nome": str(b.get("nome") or "Plano B").strip()[:40],
                  "nota": str(b.get("nota") or "").strip()[:140],
                  "itens": itens_b},
        }

    def exec_definir_meta_horas_voo(entrada):
        recusa = _recusa_visitante()
        if recusa:
            return recusa
        try:
            horas = int(float(entrada.get("horas")))
        except (TypeError, ValueError):
            return {"erro": "horas invalidas"}
        if not 1 <= horas <= 20000:
            return {"erro": "meta fora do razoavel"}
        definir_configuracao(conn, "aviacao_meta_horas", str(horas))
        return {"ok": True, "meta_horas": horas, "_efeito": {"entidade": "voo_resumo", "consulta": True}}

    def exec_ajustar_tempo_se_arrumar(entrada):
        recusa = _recusa_visitante()
        if recusa:
            return recusa
        try:
            minutos = int(float(entrada.get("minutos")))
        except (TypeError, ValueError):
            return {"erro": "minutos invalidos"}
        if not 5 <= minutos <= 180:
            return {"erro": "fora do razoavel (5 a 180 min)"}
        definir_configuracao(conn, "tempo_se_arrumar_min", str(minutos))
        conn.commit()
        return {"ok": True, "minutos": minutos}

    def exec_definir_despertador(entrada):
        """"Amanha quero acordar as 7": guarda o pedido; o Atalho do iPhone cria o alarme (despertador.py)."""
        import despertador

        recusa = _recusa_visitante()
        if recusa:
            return recusa
        if entrada.get("cancelar"):
            return {"ok": True, "cancelado": despertador.cancelar(conn)}
        hora = despertador.normalizar_hora(entrada.get("hora"))
        if not hora:
            return {"erro": f"hora invalida: {entrada.get('hora')!r}"}
        agora = _agora_brasilia().replace(tzinfo=None, second=0, microsecond=0)
        try:
            dia = _data_valida(entrada.get("quando_data")) or despertador.dia_alvo(agora, None)
        except ValueError:
            return {"erro": f"data invalida: {entrada.get('quando_data')!r}"}
        if dia < agora.date().isoformat():
            return {"erro": "essa data ja passou"}
        if dia == agora.date().isoformat() and hora <= f"{agora:%H:%M}":
            return {"erro": f"as {hora} de hoje ja passou - confirme com o Alex qual dia ele quis dizer"}
        despertador.guardar(conn, hora, dia)
        conn.commit()
        resultado = {"ok": True, "hora": hora, "data": dia,
                     "obs": "o painel nao toca o alarme sozinho: o Atalho do iPhone cria o alarme (automacao das 22h "
                            "ou o botao do card). Diga isso em uma frase."}
        p = _primeiro_compromisso_do_dia(conn, dia)
        if p and p["acordar"] < hora:
            resultado["aviso_compromisso"] = (
                f"ATENCAO: {p['titulo']} as {p['hora']} pede acordar as {p['acordar']}, antes das {hora} que ele "
                f"pediu. O alarme vai tocar as {p['acordar']}. Conte isso e pergunte se ele quer outra coisa."
            )
        resultado["_efeito"] = {"entidade": "despertador", "consulta": True, "data": dia, "pedida": hora,
                                "hora": despertador.mais_cedo(hora, p["acordar"] if p else None)}
        return resultado

    def exec_ajustar_antecedencia_voo(entrada):
        recusa = _recusa_visitante()
        if recusa:
            return recusa
        try:
            minutos = int(float(entrada.get("minutos")))
        except (TypeError, ValueError):
            return {"erro": "minutos invalidos"}
        if not 0 <= minutos <= 180:
            return {"erro": "fora do razoavel (0 a 180 min)"}
        definir_configuracao(conn, "voo_briefing_min", str(minutos))
        conn.commit()
        return {"ok": True, "minutos": minutos}

    def exec_planejar_compras_viagem(entrada):
        try:
            ida = date.fromisoformat(entrada["data_ida"]) if entrada.get("data_ida") else None
            mes = entrada.get("mes") if not ida else None
            if mes and not re.fullmatch(r"\d{4}-\d{2}", str(mes)):
                return {"erro": "mes deve ser AAAA-MM"}
            plano = viagem_compras.planejar(ida=ida, mes=mes, internacional=bool(entrada.get("internacional")),
                                            hoje=date.today())
        except (ValueError, KeyError) as e:
            return {"erro": f"nao consegui planejar: {e}"}
        destino = (entrada.get("destino") or "").strip()[:80] or None
        return {**plano, "destino": destino,
                "_efeito": {"entidade": "viagem_janelas", "consulta": True, "plano": plano, "destino": destino}}

    def _clima_pra_atividade(local_c, data, entrada):
        """"Vou lavar o carro as 14": chove na atividade ou nas horas seguintes que ela precisa
        ficar seca? Se chover, o primeiro dia seco dos proximos 7 (2026-10-21)."""
        agora = _agora_brasilia().replace(tzinfo=None)
        try:
            h, m = (int(x) for x in str(entrada["hora"]).strip()[:5].split(":"))
            dia = datetime.strptime(data, "%Y-%m-%d").date() if data else agora.date()
            inicio = datetime.combine(dia, datetime.min.time()).replace(hour=h, minute=m)
        except (ValueError, TypeError):
            return {"erro": "hora invalida (use HH:MM)"}
        try:
            janela = min(max(int(entrada.get("janela_horas") or 3), 1), 48)
        except (ValueError, TypeError):
            janela = 3
        dias = (inicio.date() - agora.date()).days + (janela // 24) + 2
        if dias > 16:
            return {"erro": "sem previsao pra essa data (o limite e 16 dias)"}
        horas = clima.previsao_horaria(local_c["lat"], local_c["lon"], dias)
        if not horas:
            return {"erro": "servico de clima fora do ar agora"}
        r = clima.analisar_janela(horas, inicio, janela)
        resultado = {"cidade": local_c["nome"], "inicio": inicio.strftime("%Y-%m-%d %H:%M"),
                     "janela_horas": janela, **r}
        if r.get("chove"):
            prev = clima.previsao_proximos_dias(local_c["lat"], local_c["lon"], 8)
            if prev:
                bom = clima.dia_seco_pra(prev, (inicio.date() + timedelta(days=1)).isoformat(),
                                         dias_secos=1 + janela // 24)
                resultado["proximo_dia_seco"] = {"data": bom["data"], "chuva_pct": bom["chuva_pct"]} if bom else None
        return resultado

    def exec_consultar_clima(entrada):
        pedida = (entrada.get("cidade") or "").strip()
        if not pedida and local_gps:
            # sem cidade = onde ele esta agora (GPS do celular)
            local_c = {"lat": local_gps["lat"], "lon": local_gps["lon"], "nome": local_gps["cidade"] or "onde você está"}
        else:
            cidade = pedida or os.environ.get("CIDADE_PADRAO", "").strip()
            if not cidade:
                return {"erro": "qual cidade? (cidade padrao nao configurada)"}
            local_c = clima.geocodificar_cidade(cidade)
            if not local_c:
                return {"erro": f"nao achei a cidade {cidade!r}"}
        data = entrada.get("data")
        if entrada.get("hora"):
            return _clima_pra_atividade(local_c, data, entrada)
        if data and data != _agora_brasilia().date().isoformat():
            prev = clima.previsao_para_data(local_c["lat"], local_c["lon"], data)
            return {"cidade": local_c["nome"], "data": data, **prev} if prev else {
                "erro": "sem previsao pra essa data (o limite e 16 dias)"}
        agora = clima.tempo_agora(local_c["lat"], local_c["lon"])
        if not agora:
            return {"erro": "servico de clima fora do ar agora"}
        resultado = {"cidade": local_c["nome"], "agora": agora}
        horas = clima.previsao_horaria_hoje(local_c["lat"], local_c["lon"])
        hora_agora = _agora_brasilia().hour
        if horas:
            resultado["resto_do_dia"] = clima.resumo_chuva_do_dia(horas, hora_agora)["texto"]
        bairro = local_gps["rotulo"].split(",")[1].strip() if (not pedida and local_gps and local_gps.get("rotulo")
                                                               and local_gps["rotulo"].count(",") >= 1) else None
        resultado["_efeito"] = {
            "entidade": "clima", "consulta": True, "lugar": bairro or local_c["nome"], "agora": agora,
            "proximas_horas": [
                {"hora": h["hora"], "chuva_pct": h["chuva_pct"], "temp": h["temp"]}
                for h in sorted(horas or [], key=lambda h: h["hora"]) if h["hora"] >= hora_agora
            ][:8],
        }
        return resultado

    def exec_briefing_meteo_voo(entrada):
        r = briefing_voo.montar(conn, entrada.get("icao"))
        if r.get("erro"):
            return r
        # pra IA vai o essencial (o bruto ja diz tudo); o card leva o resto
        return {k: r[k] for k in ("icao", "substituto_de", "categoria", "observado", "resumo", "metar_bruto",
                                  "taf_bruto", "voo", "aviso")} | {
            "_efeito": {"entidade": "briefing_voo", "consulta": True, "dados": r}}

    def exec_estimar_trajeto(entrada):
        pontos = [p.strip() for p in (entrada.get("pontos") or []) if isinstance(p, str) and p.strip()]
        if len(pontos) < 2:
            return {"erro": "preciso de pelo menos origem e destino"}
        if len(pontos) > 8:
            return {"erro": "paradas demais (maximo 8 pontos)"}
        casa = os.environ.get("ENDERECO_CASA", "").strip()
        # "daqui": com o GPS do celular a conta parte de onde ele esta; sem GPS,
        # parte de casa. O link do Google Maps sai sem origem nos dois casos (o
        # proprio Maps usa a localizacao real na hora de abrir).
        de_onde_estou = pontos[0].lower() in ("aqui", "daqui", "onde estou", "minha localizacao", "minha localização")
        gps_usado = False
        if de_onde_estou:
            if local_gps:
                pontos[0] = f"{local_gps['lat']},{local_gps['lon']}"
                gps_usado = True
            elif casa:
                pontos[0] = casa
            else:
                return {"erro": "preciso saber de onde voce sai"}
        if casa:
            pontos = [casa if p.lower() in ("casa", "minha casa", "em casa") else p for p in pontos]
        pontos = [vida_assistente.resolver_lugar(conn, p) for p in pontos]  # "obra", "aeroclube"...
        if not maps_client.configurado():
            return {"erro": "Google Maps nao configurado (falta GOOGLE_MAPS_API_KEY no .env) - diga isso ao Alex, nao estime"}
        try:
            resultado = maps_client.trajeto(pontos)
        except (ValueError, requests.RequestException):
            return {"erro": "nao consegui calcular a rota agora"}
        place_ids = resultado.pop("_place_ids", None)
        traco = resultado.pop("_traco", None)
        desenho = resultado.pop("_desenho", None)
        waze = resultado.pop("_waze", None)
        lentidao = resultado.get("lentidao") or []
        # 2026-10-21: tempo ao longo do caminho (chove num trecho e no outro nao, neblina na serra)
        tempo_rota = None
        if desenho:
            try:
                tempo_rota = clima_rota.tempo_na_rota(
                    desenho[0], resultado["duracao_total_minutos"], clima_rota.interpretar_saida(entrada.get("saida")),
                    nomear=maps_client.nome_do_trecho)
            except Exception:
                tempo_rota = None
        if tempo_rota:
            resultado["tempo_no_caminho"] = tempo_rota["resumo"]
            ruins = [(t["i0"], t["i1"], t["tipo"]) for t in tempo_rota["trechos"] if t["tipo"] != "ok"]
            if ruins:
                traco = maps_client.traco_desenhavel(desenho[0], desenho[1], faixas=desenho[2], tempo=ruins) or traco
        # pra IA: a frase pronta (nunca afirma a causa - "pode ser acidente ou blitz")
        resultado["transito"] = maps_client.resumo_transito(
            {"transito_min": resultado.get("transito_total_min"), "lentidao": lentidao})
        lugares = resultado["lugares"]
        if de_onde_estou:
            if gps_usado:
                lugares[0]["nome"] = "Onde você está"
                lugares[0]["endereco"] = local_gps["rotulo"] or "localização atual"
            else:
                resultado["obs"] = "sem GPS do celular: km e tempo calculados a partir de casa; o link do Maps parte da localizacao real"
        paradas = [{"nome": l.get("nome") or l["pedido"], "endereco": l["endereco"]} for l in lugares]
        if de_onde_estou and not gps_usado:
            paradas[0]["endereco"] = ""  # o card mostra "Onde você está", nao o endereco de casa
        resultado["_efeito"] = {
            "entidade": "rota",
            "consulta": True,
            "paradas": paradas,
            "partir_de_onde_estou": de_onde_estou,
            "distancia_km": resultado["distancia_total_km"],
            "duracao_min": resultado["duracao_total_minutos"],
            "url": maps_client.link_rota(lugares, place_ids, de_onde_estou),
            "traco": traco,
            "transito_min": resultado.get("transito_total_min"),
            "lentidao": [
                {"nivel": x["nivel"], "frase": maps_client.frase_trecho(x)} for x in lentidao[:3]
            ],
            "waze": waze,
            "waze_para": paradas[1]["nome"] if len(paradas) > 1 else None,
            "tempo": {
                "total_km": tempo_rota["total_km"],
                "saida": tempo_rota["saida"],
                "trechos": [{k: t.get(k) for k in ("tipo", "de_km", "ate_km", "hora_ini", "hora_fim", "serra",
                                                    "nome", "chuva_pct", "visibilidade_m", "rajada_kmh")}
                            | {"frase": clima_rota.frase(t)} for t in tempo_rota["trechos"]],
            } if tempo_rota else None,
        }
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
            return {"erro": "não consegui gerar o plano agora - tenta de novo em instantes"}
        _log_usage(conn, usage_plano, "plano_dia")
        return {"plano": plano_texto}

    def exec_registrar_lembrete(entrada):
        local_lembrete = _rotulo_local_atual(entrada)
        if isinstance(local_lembrete, dict):
            return local_lembrete
        lembrete_id = create_lembrete(conn, entrada["titulo"], entrada["data"], entrada.get("recorrente", False))
        if local_lembrete:
            conn.execute("UPDATE lembretes SET local = ? WHERE id = ?", (local_lembrete, lembrete_id))
            conn.commit()
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
            return {"erro": "valor inválido"}
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
        # "supino reto 4x10 com 20kg" -> "Supino reto|4|10|20 kg" (o formato do menu: la aparece
        # series/reps/carga e a troca de carga acha o exercicio)
        exercicios = _texto_curto(treino_vivo.normalizar_ficha(exercicios or ""), 3000)
        if not grupo or not exercicios:
            return {"erro": "preciso do grupo e dos exercicios"}
        return {"ok": True, "ficha_id": salvar_ficha_treino(conn, grupo, exercicios)}

    def exec_registrar_treino(entrada):
        duracao = entrada.get("duracao_min")
        duracao = _inteiro_no_intervalo(duracao, 1, 600) if duracao not in (None, "") else None
        grupo = _texto_curto(entrada.get("grupo"), 40)
        nota = _texto_curto(entrada.get("nota"), 300)
        hoje = date.today().isoformat()
        # treino ao vivo: a ficha marcada ate o fim ja registrou o treino de hoje - "treinei peito
        # 1h" depois disso completa aquele registro em vez de contar dois treinos
        if grupo:
            alvo = vida.normalizar_nome(grupo)
            for r in conn.execute(
                "SELECT id, grupo, duracao_min, nota FROM treinos WHERE data = ? AND origem = 'sessao'", (hoje,)
            ).fetchall():
                if vida.normalizar_nome(r["grupo"]) == alvo:
                    conn.execute(
                        "UPDATE treinos SET duracao_min = ?, nota = ? WHERE id = ?",
                        (duracao or r["duracao_min"], nota or r["nota"], r["id"]),
                    )
                    conn.commit()
                    return {"ok": True, "treino_id": r["id"], "ja_registrado_pela_ficha": True,
                            "_efeito": {"entidade": "treinos", "dias": 7, "consulta": True}}
        treino_id = registrar_treino(conn, hoje, grupo, duracao, nota)
        return {"ok": True, "treino_id": treino_id, "_efeito": {"entidade": "treino", "id": treino_id}}

    def _exercicio_texto(ex):
        partes = [ex["nome"]]
        if ex["series"] or ex["reps"]:
            partes.append("x".join(p for p in (ex["series"], ex["reps"]) if p))
        if ex["carga"]:
            partes.append(ex["carga"])
        return " ".join(partes)

    def exec_comecar_treino(entrada):
        recusa = _recusa_visitante()
        if recusa:
            return recusa
        fichas = list_fichas_treino(conn)
        if not fichas:
            return {"erro": (
                "ele ainda nao tem ficha de treino. Peca pra colar o treino aqui (salvar_ficha_treino) "
                "ou montar em Mais > Vida completa > Treino > Nova ficha."
            )}
        pedido = _texto_curto(entrada.get("grupo"), 60)
        if pedido:
            ficha, escolha = treino_vivo.achar_ficha(fichas, pedido), "pedida"
            if not ficha:
                return {"erro": f"nenhuma ficha bate com '{pedido}'", "fichas": [f["grupo"] for f in fichas]}
        else:
            ficha = treino_vivo.proxima_da_rotacao(fichas, db.ultimo_treino_por_grupo(conn))
            escolha = "rotacao"
        exercicios = treino_vivo.exercicios_da_ficha(ficha["exercicios"])
        sessao_id = db.abrir_sessao_treino(conn, ficha["id"], date.today().isoformat())
        sessao = db.sessao_treino(conn, sessao_id)
        return {
            "ok": True, "ficha": ficha["grupo"], "escolhida_por": escolha,
            "exercicios": [_exercicio_texto(e) for e in exercicios],
            "ja_marcados": len(sessao["feitos"]), "concluido": bool(sessao["concluido_em"]),
            "outras_fichas": [f["grupo"] for f in fichas if f["id"] != ficha["id"]],
            "_efeito": {"entidade": "treino_sessao", "id": sessao_id, "escolhida_por": escolha, "consulta": True},
        }

    def exec_atualizar_carga_treino(entrada):
        recusa = _recusa_visitante()
        if recusa:
            return recusa
        nome = _texto_curto(entrada.get("exercicio"), 80)
        nova = treino_vivo.carga_texto(entrada.get("carga"))
        if not nome or not nova:
            return {"erro": "preciso do exercicio e da carga nova"}
        fichas = list_fichas_treino(conn)
        grupo = _texto_curto(entrada.get("grupo"), 60)
        if grupo:
            ficha = treino_vivo.achar_ficha(fichas, grupo)
            if not ficha:
                return {"erro": f"nenhuma ficha bate com '{grupo}'", "fichas": [f["grupo"] for f in fichas]}
            fichas = [ficha]
        achados = []
        for f in fichas:
            exs = treino_vivo.exercicios_da_ficha(f["exercicios"])
            i = treino_vivo.achar_exercicio(exs, nome)
            if i is not None:
                achados.append((f, exs, i))
        if len(achados) > 1:
            # a ficha que ele abriu hoje desempata ("o supino foi pra 25" logo depois do treino de peito)
            hoje_ids = {r["ficha_id"] for r in conn.execute(
                "SELECT ficha_id FROM treino_sessoes WHERE data = ?", (date.today().isoformat(),))}
            de_hoje = [a for a in achados if a[0]["id"] in hoje_ids]
            if len(de_hoje) == 1:
                achados = de_hoje
            else:
                return {"erro": f"'{nome}' aparece em mais de uma ficha - pergunte qual",
                        "fichas": [a[0]["grupo"] for a in achados]}
        if not achados:
            return {"erro": f"nao achei '{nome}' na ficha", "exercicios_das_fichas": {
                f["grupo"]: [e["nome"] for e in treino_vivo.exercicios_da_ficha(f["exercicios"])] for f in fichas}}
        ficha, exs, i = achados[0]
        antes = exs[i]["carga"]
        exs[i]["carga"] = nova
        for campo in ("series", "reps"):
            valor = _texto_curto(str(entrada[campo]), 10) if entrada.get(campo) not in (None, "") else None
            if valor:
                exs[i][campo] = valor
        texto = "\n".join(treino_vivo.escrever_exercicio(e) for e in exs)
        if texto == ficha["exercicios"]:
            return {"ok": True, "sem_mudanca": True, "exercicio": exs[i]["nome"], "carga": nova}
        hoje = date.today().isoformat()
        # historico do grafico: a ficha de antes vale desde a ultima vez que foi salva (ficha
        # antiga, de antes do historico, ganha o ponto de partida aqui)
        base = str(ficha.get("atualizado_em") or "")[:10]
        db.registrar_cargas_da_ficha(conn, ficha["id"], ficha["exercicios"], base if base and base < hoje else hoje)
        conn.execute(
            "UPDATE treino_fichas SET exercicios = ?, atualizado_em = datetime('now') WHERE id = ?", (texto, ficha["id"])
        )
        novos = db.registrar_cargas_da_ficha(conn, ficha["id"], texto, hoje)
        conn.commit()
        return {
            "ok": True, "ficha": ficha["grupo"], "exercicio": exs[i]["nome"], "antes": antes or None, "depois": nova,
            "_efeito": {"entidade": "treino_carga", "id": ficha["id"], "antes": ficha["exercicios"],
                        "grupo": ficha["grupo"], "exercicio": exs[i]["nome"],
                        "carga_antes": antes, "carga_depois": nova, "historico_ids": novos},
        }

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
            return {"erro": f"não achei nenhuma espera em aberto de \"{entrada['quem']}\""}
        resolver_espera(conn, espera["id"])
        return {"ok": True, "quem": espera["quem"], "sobre": espera["sobre"]}

    def exec_registrar_feito(entrada):
        r = marcar_ou_criar_feito(conn, entrada["titulo"], texto)
        if r.get("ok"):
            # card tarefa_feita (2026-10-14); o Desfazer reabre a que ja existia ou apaga a
            # que nasceu concluida agora
            if r["acao"] == "marcada_concluida":
                feito_em = conn.execute("SELECT completed_at FROM tasks WHERE id = ?", (r["task_id"],)).fetchone()
                r["_efeito"] = {
                    "entidade": "edicao", "tabela": "tasks", "id": r["task_id"], "rotulo": "Tarefa",
                    "titulo": r["titulo"], "antes": {"completed_at": None},
                    "depois": {"completed_at": feito_em["completed_at"] if feito_em else None}, "feito": True,
                }
            else:
                r["_efeito"] = {"entidade": "tarefa", "id": r["task_id"], "feito": True}
        return r

    def exec_registrar_voo(entrada):
        # Contar como foi um voo ja agendado (resposta ao "Como foi o voo?")
        # completa o registro existente em vez de criar um voo duplicado.
        do_dia = [v for v in list_voos(conn) if v["data"] == entrada["data"]]
        existente = next(
            (v for v in do_dia
             if vida.normalizar_nome(v["destino"]) == vida.normalizar_nome(entrada["destino"])
             and not (v.get("observacao") or "").strip()),
            None,
        )
        if existente is None and entrada.get("horas"):
            # 3a leva: "voei 1,2 hoje" com UM voo agendado sem horas no dia = esse voo
            abertos = [v for v in do_dia if v.get("horas") is None and v.get("hora")]
            existente = abertos[0] if len(abertos) == 1 else None
        if existente:
            conn.execute(
                """UPDATE voos SET observacao = COALESCE(?, observacao), horas = COALESCE(?, horas),
                   origem = COALESCE(?, origem), hora = COALESCE(?, hora) WHERE id = ?""",
                (entrada.get("observacao"), entrada.get("horas"), entrada.get("origem"),
                 _normalizar_hora(entrada.get("hora")), existente["id"]),
            )
            conn.commit()
            return {"ok": True, "atualizado": True, "_efeito": {"entidade": "voo_resumo", "consulta": True}}
        hora = _normalizar_hora(entrada.get("hora"))
        # 2026-10-14 (pedido do Alex): voo sem origem dita sai de Blumenau (SSBL); navegacao
        # com escalas guarda a ordem ("SBNF,SBFL") - ver rota_voo.py
        origem = rota_voo.aerodromo(entrada.get("origem")) or rota_voo.ORIGEM_PADRAO
        escalas = rota_voo.escalas_texto(entrada.get("escalas"))
        voo_id = create_voo(
            conn,
            entrada["data"],
            rota_voo.aerodromo(entrada["destino"]) or entrada["destino"],
            origem,
            entrada.get("horas"),
            entrada.get("observacao"),
            hora,
            escalas,
        )
        if entrada.get("horas"):
            return {"ok": True, "_efeito": {"entidade": "voo_resumo", "consulta": True}}
        rota = rota_voo.montar(origem, escalas, entrada["destino"], hora)
        antes = vida_assistente.voo_briefing_min(conn)
        saida = _saida_pro_voo(conn, entrada["data"], hora, origem, antes)
        resposta = {
            "ok": True,
            "rota": " -> ".join(p["icao"] for p in rota["paradas"]),
            "milhas_nauticas": rota["total_nm"],
            "chegar_no_aeroclube": rota_voo.menos_minutos(hora, antes),
            "_efeito": {"entidade": "voo_agendado", "id": voo_id, "saida": saida},
        }
        if saida:
            resposta["sair_de_casa"] = saida["sair"]
            resposta["trajeto_min"] = saida["trajeto_min"]
        return resposta

    def exec_rotular_cobranca_generica(entrada):
        candidatos = notificacoes.cobrancas_genericas_sem_rotulo(conn)
        correspondente = next((c for c in candidatos if abs(c[1] - entrada["valor"]) < 0.01), None)
        if not correspondente:
            return {"erro": f"não achei nenhuma cobrança genérica de R$ {entrada['valor']:.2f} pra identificar"}
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
            return {"erro": "não veio nenhum titulo de tarefa pra distribuir"}
        dias = agenda.proximos_n_dias(date.today() + timedelta(days=1), 14)
        carga = _carga_por_dia(conn, dias)
        produtividade = aprendizado.produtividade_por_dia_semana(conn)
        propostas = agenda.distribuir_tarefas_na_semana(carga, dias, titulos, produtividade)
        definir_configuracao(conn, "plano_semana_pendente", json.dumps(propostas, ensure_ascii=False))
        return {"ok": True, "propostas": propostas}

    def exec_confirmar_plano_semana(_entrada):
        bruto = obter_configuracao(conn, "plano_semana_pendente")
        if not bruto:
            return {"erro": "não tem nenhum plano de semana pendente pra confirmar"}
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
            return {"erro": "Google Maps não configurado"}
        origem = entrada.get("origem") or os.environ.get("ENDERECO_CASA", "").strip()
        if not origem:
            return {"erro": "preciso saber de onde você sai (endereço padrao não configurado)"}
        try:
            trajeto = maps_client.tempo_de_viagem(origem, entrada["destino"])
        except (ValueError, requests.RequestException):
            return {"erro": "não consegui calcular a rota agora"}
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
            return {"erro": "Google Maps não configurado"}
        origem = entrada.get("origem") or os.environ.get("ENDERECO_CASA", "").strip()
        if not origem:
            return {"erro": "preciso saber de onde você sai (endereço padrao não configurado)"}
        try:
            posto = maps_client.posto_no_meio_do_caminho(origem, entrada["destino"])
        except (ValueError, requests.RequestException):
            return {"erro": "não consegui buscar postos agora"}
        if not posto:
            return {"erro": "não achei nenhum posto perto do meio do caminho"}
        return posto

    def exec_agendar_uber(entrada):
        if not uber_client.configurado():
            return {"erro": "Uber não conectado ainda"}
        minutos = max(entrada.get("minutos", 0), 0)
        disparar_em = (datetime.now() + timedelta(minutes=minutos)).isoformat()
        pedido_id = criar_uber_pedido(conn, entrada.get("origem"), entrada["destino"], disparar_em)
        return {"ok": True, "pedido_id": pedido_id, "minutos": minutos}

    def exec_sugerir_tema_estudo(_entrada):
        indice_atual = int(obter_configuracao(conn, "estudo_proximo_indice") or 0)
        tema, proximo_indice = estudo.proximo_tema(indice_atual)
        definir_configuracao(conn, "estudo_proximo_indice", str(proximo_indice))
        return {"tema": tema}

    def exec_fazer_pergunta_aviacao(entrada):
        p = estudo_quiz.criar(conn, entrada)
        if p.get("erro"):
            return p
        return {"pergunta_id": p["id"], "tema": p["tema"], "mostrada_no_card": True,
                "_efeito": {"entidade": "quiz_aviacao", "consulta": True, "dados": estudo_quiz.dados_card(p)}}

    def exec_revisar_pergunta_aviacao(entrada):
        p = estudo_quiz.revisar_pendente(conn, _agora_brasilia().date(), entrada.get("tema"))
        if not p:
            return {"nada_pra_revisar": True}
        return {"pergunta_id": p["id"], "tema": p["tema"], "enunciado": p["enunciado"],
                "alternativas": p["alternativas"], "vezes_que_errou": p["erros"], "mostrada_no_card": True,
                "_efeito": {"entidade": "quiz_aviacao", "consulta": True,
                            "dados": estudo_quiz.dados_card(p, revisao=True)}}

    def exec_responder_pergunta_aviacao(entrada):
        r = estudo_quiz.responder(conn, entrada.get("pergunta_id"), entrada.get("alternativa"),
                                  _agora_brasilia().date())
        if r.get("erro"):
            return r
        p = estudo_quiz._linha(conn, r["id"])
        r["_efeito"] = {"entidade": "quiz_aviacao", "consulta": True,
                        "dados": estudo_quiz.dados_card(p, resultado=r)}
        return r

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
            return {"erro": f"não achei nenhuma cotação com o titulo \"{entrada['titulo_cotacao']}\""}
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
            return {"erro": f"não achei nenhum hábito chamado \"{entrada.get('nome')}\""}
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
            return {"erro": f"não achei nenhum projeto chamado \"{entrada.get('nome_projeto')}\""}
        resultado = _adicionar_etapa(conn, projeto["id"], entrada.get("texto"), entrada.get("data_prevista"))
        if resultado.get("ok"):
            resultado["_efeito"] = {"entidade": "projeto_etapa", "id": resultado["etapa_id"], "projeto_id": projeto["id"]}
        return resultado

    def exec_concluir_etapa(entrada):
        projeto = buscar_projeto_por_nome(conn, entrada.get("nome_projeto"))
        if not projeto:
            return {"erro": f"não achei nenhum projeto chamado \"{entrada.get('nome_projeto')}\""}
        etapas = list_etapas_projeto(conn, projeto["id"])
        proxima = next((e for e in etapas if not e["feita"]), None)
        if not proxima:
            return {"erro": f"o projeto \"{projeto['nome']}\" não tem etapa pendente"}
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

    # Fonte unica (chat_consultas): a IA busca o dado no painel em vez de
    # responder de memoria. So texto (sem card), nunca levanta excecao.
    def exec_consultar_tarefas(entrada):
        r = chat_consultas.consultar_tarefas(conn, entrada, materializar=materializar_tarefas_recorrentes)
        if isinstance(r, dict) and not r.get("erro") and isinstance(r.get("periodo"), dict):
            r["_efeito"] = {"entidade": "tarefas_lista", "consulta": True, "de": r["periodo"].get("de"),
                            "ate": r["periodo"].get("ate"), "status": r.get("status")}
        return r

    def exec_consultar_gastos(entrada):
        if has_request_context() and _modo_visitante_ativo():
            return {"erro": "gastos indisponiveis no modo visitante"}
        r = chat_consultas.consultar_gastos(conn, entrada)
        if isinstance(r, dict) and not r.get("erro"):
            r["_efeito"] = {"entidade": "gastos_resumo", "consulta": True, "dados": r}
        return r

    def exec_consultar_voos(entrada):
        if has_request_context() and _modo_visitante_ativo():
            return {"erro": "voos indisponiveis no modo visitante"}
        r = chat_consultas.consultar_voos(conn, entrada)
        if isinstance(r, dict) and not r.get("erro"):
            r["_efeito"] = {"entidade": "voo_resumo", "consulta": True}
        return r

    def exec_consultar_agenda(entrada):
        icloud = None
        if caldav_client.configurado() and not (has_request_context() and _modo_visitante_ativo()):
            icloud = caldav_client.eventos_do_dia
        r = chat_consultas.consultar_agenda(conn, entrada, eventos_icloud=icloud)
        if isinstance(r, dict) and not r.get("erro"):
            r["_efeito"] = {"entidade": "dia", "consulta": True, "dados": r}
        return r

    executores = {
        "registrar_tarefa": exec_registrar_tarefa,
        "ajustar_tarefa": exec_ajustar_tarefa,
        "mover_tarefas": exec_mover_tarefas,
        "ajustar_lembrete": exec_ajustar_lembrete,
        "ajustar_voo": exec_ajustar_voo,
        "ajustar_gasto": exec_ajustar_gasto,
        "definir_meta_horas_voo": exec_definir_meta_horas_voo,
        "ajustar_tempo_se_arrumar": exec_ajustar_tempo_se_arrumar,
        "definir_despertador": exec_definir_despertador,
        "ajustar_antecedencia_voo": exec_ajustar_antecedencia_voo,
        "ajustar_renda": exec_ajustar_renda,
        "apagar_tarefa": exec_apagar_tarefa,
        "registrar_acordei": exec_registrar_acordei,
        "consultar_diario": exec_consultar_diario,
        "buscar_na_memoria": exec_buscar_na_memoria,
        "anotar_no_diario": exec_anotar_no_diario,
        "consultar_feriados": exec_consultar_feriados,
        "atualizar_perfil": exec_atualizar_perfil,
        "salvar_lugar_apelido": exec_salvar_lugar_apelido,
        "planejar_dia": exec_planejar_dia,
        "planejar_compras_viagem": exec_planejar_compras_viagem,
        "consultar_clima": exec_consultar_clima,
        "estimar_trajeto": exec_estimar_trajeto,
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
        "comecar_treino": exec_comecar_treino,
        "atualizar_carga_treino": exec_atualizar_carga_treino,
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
        "consultar_tarefas": exec_consultar_tarefas,
        "consultar_gastos": exec_consultar_gastos,
        "consultar_agenda": exec_consultar_agenda,
        "consultar_voos": exec_consultar_voos,
        "briefing_meteo_voo": exec_briefing_meteo_voo,
        "fazer_pergunta_aviacao": exec_fazer_pergunta_aviacao,
        "revisar_pergunta_aviacao": exec_revisar_pergunta_aviacao,
        "responder_pergunta_aviacao": exec_responder_pergunta_aviacao,
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
            resposta = _desescapar_unicode(resposta)
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


_RE_ESCAPE_UNICODE = re.compile(r"\\u([0-9a-fA-F]{4})")


def _desescapar_unicode(texto):
    """A IA as vezes devolve "\\u00e1" literal no texto (visto no chat em 10/2026: "j\\u00e1") -
    vira o caractere de verdade. So o padrao \\uXXXX; o resto do texto fica como veio."""
    if not isinstance(texto, str) or "\\u" not in texto:
        return texto
    return _RE_ESCAPE_UNICODE.sub(lambda m: chr(int(m.group(1), 16)), texto)


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
        meta = ctx.get("meta") or [{} for _ in ctx["mensagens"]]
        itens = [{**m, "criado_em": mm.get("criado_em")} for m, mm in zip(ctx["mensagens"], meta)]
        mensagens = _historico_com_datas(conn, itens) + [{"role": "user", "content": texto}]
        return mensagens, ctx["contexto_fixo"] or ""
    except Exception:  # noqa: BLE001
        app.logger.exception("chat: montar_contexto (A5) falhou - usando historico antigo")
        return mensagens_antigas, ""


# Mensagem de um dia que ja passou e ainda e recente (virou a meia-noite conversando) vai na integra.
_HISTORICO_HORAS_CONTINUIDADE = 4


def _historico_com_datas(conn, itens: list[dict], agora: datetime | None = None) -> list[dict]:
    """2026-10-12 (o "date de sabado" que a IA achou que era hoje): `itens` = [{role, content,
    criado_em(UTC)}] em ordem. Mensagem de HOJE vai igual. Mensagem de dia que ja passou:
    - se o dia ja tem diario (diario_dias com resumo) e ja faz mais de algumas horas, sai - o
      "Diario dos ultimos dias" do contexto conta aquele dia, com o nome certo;
    - senao vai marcada "[ontem (domingo 11/10), 21:54 - dia que ja passou]".
    Nunca comeca por 'assistant' (a API exige 'user' primeiro)."""
    agora = agora or _agora_brasilia().replace(tzinfo=None)
    hoje = agora.date()
    datas = [diario.utc_para_local(it.get("criado_em")) for it in itens]
    passados = sorted({d.date() for d in datas if d and d.date() < hoje})
    com_diario = diario.dias_com_resumo(conn, passados) if passados else set()
    saida = []
    for it, dt in zip(itens, datas):
        if dt is None or dt.date() >= hoje:
            saida.append({"role": it["role"], "content": it["content"]})
            continue
        recente = agora - dt < timedelta(hours=_HISTORICO_HORAS_CONTINUIDADE)
        if not recente and dt.date().isoformat() in com_diario:
            continue
        marca = f"[{diario.rotulo_dia(dt.date(), hoje)}, {dt:%H:%M} - dia que já passou] "
        saida.append({"role": it["role"], "content": marca + (it["content"] or "")})
    while saida and saida[0]["role"] != "user":
        saida.pop(0)
    return saida


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
                    "data": ef.get("data"), "feito": ef.get("feito"),
                    "tabela": ef.get("tabela"), "antes": ef.get("antes"), "linha": ef.get("linha"),
                    "subtarefas": ef.get("subtarefas"), "pulo": ef.get("pulo"),
                    "historico_ids": ef.get("historico_ids")}
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
        raise _DesfazerRecusado("esse evento não foi criado pelo painel - não da pra desfazer por aqui", 403)
    if not caldav_client.configurado():
        raise _DesfazerRecusado("agenda do iCloud não configurada - não da pra desfazer o evento agora", 503)


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
                raise _DesfazerRecusado("não consegui apagar o evento no iCloud agora - tenta de novo", 502) from e
            conn.execute("DELETE FROM eventos_criados WHERE uid = ?", (item["uid"],))
            desfeitos += 1
            continue
        if not isinstance(id_, int):
            continue
        if entidade == "edicao":
            colunas = db.EDICAO_COLUNAS.get(item.get("tabela"))
            antes = {c: v for c, v in (item.get("antes") or {}).items() if colunas and c in colunas}
            if not antes:
                continue
            sets = ", ".join(f"{c} = ?" for c in antes)  # nomes vindos da lista fechada acima
            cur = conn.execute(f"UPDATE {item['tabela']} SET {sets} WHERE id = ?", [*antes.values(), id_])
        elif entidade == "tarefa_apagada":
            # volta a tarefa que a IA apagou, com o mesmo id (colunas da lista fechada)
            linha = {c: v for c, v in (item.get("linha") or {}).items() if c in db.TAREFA_RESTAURAVEL}
            if linha.get("id") != id_ or not linha.get("title"):
                continue
            cur = conn.execute(
                f"INSERT OR IGNORE INTO tasks ({', '.join(linha)}) VALUES ({', '.join('?' for _ in linha)})",
                list(linha.values()),
            )
            if cur.rowcount:
                for s in item.get("subtarefas") or []:
                    if isinstance(s, dict) and isinstance(s.get("title"), str):
                        conn.execute(
                            "INSERT INTO subtasks (task_id, title, completed_at, position) VALUES (?, ?, ?, ?)",
                            (id_, s["title"], s.get("completed_at"), s.get("position") or 0),
                        )
                pulo = item.get("pulo")
                if isinstance(pulo, dict):
                    conn.execute("DELETE FROM tarefas_puladas WHERE origem_id = ? AND data = ?",
                                 (pulo.get("origem_id"), pulo.get("data")))
        elif entidade == "tarefa":
            # card de compromisso (2026-10-14): o lembrete de comprar o presente e a tarefa de
            # chamar o Uber nasceram dele - vao junto
            extras = db.extras_tarefa(conn, id_)
            if isinstance(extras.get("lembrete_id"), int):
                conn.execute("DELETE FROM lembretes WHERE id = ?", (extras["lembrete_id"],))
            if isinstance(extras.get("uber_tarefa_id"), int):
                conn.execute("DELETE FROM tasks WHERE id = ? AND completed_at IS NULL", (extras["uber_tarefa_id"],))
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
        elif entidade == "voo_agendado":
            # so o agendamento: se ja virou voo contado (com horas), nao apaga o diario
            cur = conn.execute("DELETE FROM voos WHERE id = ? AND horas IS NULL", (id_,))
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
        elif entidade == "treino_carga" and isinstance(item.get("antes"), str):
            for h in item.get("historico_ids") or []:
                conn.execute("DELETE FROM treino_cargas WHERE id = ? AND ficha_id = ?", (h, id_))
            cur = conn.execute("UPDATE treino_fichas SET exercicios = ? WHERE id = ?", (item["antes"], id_))
        elif entidade == "refeicao":
            refeicoes.criar_tabela(conn)
            cur = conn.execute("DELETE FROM refeicoes WHERE id = ?", (id_,))
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
            return jsonify({"error": "nada pra desfazer com esse código"}), 404
        if acao["desfeito_em"]:
            return jsonify({"error": "isso já foi desfeito"}), 409
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
            return jsonify({"error": "isso já foi desfeito"}), 409
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
        return "Não reconheci essa ação."
    try:
        task_id = int(dados.split(":", 1)[1])
    except ValueError:
        return "Não reconheci essa ação."
    conn = get_db()
    try:
        row = conn.execute("SELECT title, completed_at FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return "Essa tarefa não existe mais."
        if row["completed_at"]:
            return "Já estava marcada como feita."
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


def _aviso_voo_sair(voo: dict, janela_minutos: int = 25, conn=None) -> str | None:
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
    # 2026-10-11: o Alex tem que estar no aeroclube X min ANTES (briefing, padrao 30) - e o
    # lugar e de onde o voo SAI (origem, ex: SSBL), nao o destino da navegacao.
    briefing = vida_assistente.voo_briefing_min(conn) if conn is not None else 30
    lugar = voo.get("origem") or voo["destino"]
    if conn is not None:
        lugar = vida_assistente.resolver_lugar(conn, lugar)
    try:
        hora_voo = datetime.fromisoformat(f"{voo['data']}T{voo['hora']}")
        chegar_ate = hora_voo - timedelta(minutes=briefing)
        # 2026-10-15: 1 consulta por HORA por voo (antes: a cada tick de 5 min ate avisar)
        agora = datetime.now()
        chave = ("voo", agora.date().isoformat(), agora.hour, voo.get("id"), voo["hora"], lugar)
        if chave not in _CACHE_TRAJETO_AVISO:
            _CACHE_TRAJETO_AVISO[chave] = maps_client.horario_de_saida(
                origem, lugar, chegar_ate, margem_minutos=10, lentidao=True)
        resultado = _CACHE_TRAJETO_AVISO[chave]
    except (ValueError, requests.RequestException):
        return None

    sair_ate = datetime.fromisoformat(resultado["sair_ate"])
    minutos_pra_sair = (sair_ate - datetime.now()).total_seconds() / 60
    if not (0 <= minutos_pra_sair <= janela_minutos):
        return None

    resumo = maps_client.resumo_transito(resultado)
    return (
        f"Saia até as {sair_ate:%H:%M} pra chegar no briefing das {chegar_ate:%H:%M} "
        f"(voo das {voo['hora']} pra {voo['destino']}, {resultado['duracao_minutos']} min de trajeto)."
        + (f" {resumo}." if resumo else "")
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
        atualizar_uber_pedido(conn, pedido["id"], status="erro", erro="sem endereço de origem")
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
        atualizar_uber_pedido(conn, pedido["id"], status="erro", erro="não consegui obter o preço")
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
    "adiado_hiperfoco", "tarefa_preparo", "se_arrumar", "hora_de_sair",
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
                 f"Seu bloco de foco{duracao} acabou. Levanta, bebe água, e ve se continua ou para.")
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
            f"Faz {dias} dias que você não fala com {pessoa['nome']}."
            if pessoa["ultimo_contato"]
            else f"Ainda não tem conversa registrada com {pessoa['nome']}."
        )
        avisos.append(("pessoa_sem_contato", ref, "Faz tempo", texto))

    if agora.hour >= 10:
        ref = vida.id_estavel("assinaturas", hoje.strftime("%Y-%m"))
        if not ja_notificado_alguma_vez(conn, "revisao_assinaturas", ref):
            pendentes = _assinaturas_pendentes_revisao(conn, hoje)
            if pendentes:
                avisos.append(
                    ("revisao_assinaturas", ref, "Revisao do mês",
                     f"{len(pendentes)} assinatura(s) pra confirmar se você ainda usa - 1 toque cada no painel.")
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
                ("agua_pausa", slot, "Pausa rápida",
                 f"Bebe um copo de água e levanta 2 minutos ({copos} copo(s) hoje).")
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
                ("clima_compromisso", 0, "Chuva no seu horário",
                 f"{resumo['texto']} Pega {nomes} - sai mais cedo ou leva guarda-chuva.")
            )

    checklist_voo = ", ".join(vida.CHECKLIST_PRE_VOO).lower()
    for voo in list_voos(conn):
        try:
            data_voo = date.fromisoformat(voo["data"])
        except (TypeError, ValueError):
            continue
        destino = voo.get("destino") or "o voo"
        if voo.get("hora") and voo.get("horas") is None:
            continue  # 4a leva: voo com hora tem vespera/manha no chat (conversa_proativa)
        if data_voo == hoje + timedelta(days=1) and agora.hour >= 19:
            ref = vida.id_estavel("pre_voo", voo["id"], "vespera")
            if not ja_notificado_alguma_vez(conn, "pre_voo", ref):
                avisos.append(("pre_voo", ref, "Voo amanhã", f"Voo amanhã pra {destino}. Separa hoje: {checklist_voo}."))
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
        quando = "já passou do prazo" if m["dias_ate"] < 0 else "vence hoje" if m["dias_ate"] == 0 else f"vence em {m['dias_ate']} dia(s)"
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
            avisos.append(("revisao_mensal", ref, "Como foi o mês", _revisao_do_mes(conn, primeiro, ultimo)["texto"]))

    # documento vencendo (burocracia): 4a leva - marcos 60/30/7 no chat + push
    # (conversa_proativa.documentos_vencendo), no lugar do aviso unico de 8-30 dias

    if agora.weekday() == 6 and agora.hour >= 10:
        semana = hoje.isocalendar()
        ref = vida.id_estavel("aprender", semana[0], semana[1])
        if not ja_notificado_alguma_vez(conn, "aprender", ref):
            for a in list_aprender(conn):
                parado = (hoje - date.fromisoformat(a["ultima_vez"] or a["criado_em"][:10])).days
                if parado >= 7:
                    avisos.append(
                        ("aprender", ref, "Quer retomar?",
                         f"Faz {parado} dias que você não mexe em \"{a['tema']}\". 20 minutos hoje?")
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
                        f"custos fixos já comprometem {pct}%.",
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


# Onde o toque na notificacao abre (?aba= -> init.js/service worker abrem a aba certa).
_ABA_DO_AVISO = {
    "tarefa": "tarefas", "se_arrumar": "tarefas", "hora_de_sair": "tarefas", "compromisso": "tarefas",
    "lembrete": "tarefas", "espera": "tarefas", "conta_a_vencer": "construtora", "orcamento": "gastos",
    "gasto": "gastos", "cobranca": "gastos", "assinatura": "gastos", "cartao": "gastos", "renda": "gastos",
    "voo": "aviacao", "pre_voo": "aviacao", "currency": "aviacao", "meta": "painel", "habito": "vida",
}


def _repetir_avisos_insistentes(conn, subs, silencioso: bool, em_hiperfoco: bool) -> int:
    """Repeticoes de notificacoes.INSISTENCIA: mesma tag (substitui a anterior e toca de novo),
    so se o aviso ainda vale. Silencio e hiperfoco valem igual ao 1o envio."""
    agora = datetime.now()
    repetir, encerrar = notificacoes.repeticoes_devidas(db.avisos_insistentes_pendentes(conn), agora)
    for a in encerrar:
        db.encerrar_aviso_insistente(conn, a["id"], agora)
    enviados = 0
    for a in repetir:
        tipo = a["tipo"]
        if tipo in notificacoes.INSISTENCIA_DE_TAREFA:
            row = conn.execute("SELECT completed_at FROM tasks WHERE id = ?", (a["referencia_id"],)).fetchone()
            if not row or row["completed_at"]:
                db.encerrar_aviso_insistente(conn, a["id"], agora)
                continue
        if not avisos_assistente.esta_ligado(tipo, conn=conn):
            continue
        if silencioso and tipo not in NOTIFICACOES_URGENTES:
            continue
        if em_hiperfoco and tipo not in vida.CRITICOS_HIPERFOCO:
            continue
        titulo, corpo = notificacoes.texto_repeticao(tipo, a["titulo"], a["corpo"], int(a["tentativas"]))
        for s in subs:
            if not push_client.enviar(json.loads(s["subscription_json"]), titulo, corpo,
                                      url=_url_do_aviso(tipo, a["tag"]), tag=a["tag"]):
                delete_push_subscription(conn, s["endpoint"])
        db.registrar_repeticao_aviso(conn, a["id"])
        enviados += 1
    return enviados


# aviso de UMA tarefa: o toque abre a propria tarefa (rola ate ela e abre concluir / pra amanha)
_AVISOS_DE_UMA_TAREFA = {"tarefa_horario", "tarefa_preparo", "tarefa_horario_passou", "tarefa_parada", "se_arrumar", "hora_de_sair"}


def _url_do_aviso(tipo: str, tag: str = "") -> str:
    ref = tag.rsplit("-", 1)[-1] if tag else ""
    if tipo in _AVISOS_DE_UMA_TAREFA and ref.isdigit() and int(ref) > 0:
        return f"/?aba=tarefas&tarefa={ref}"
    for prefixo, aba in _ABA_DO_AVISO.items():
        if tipo.startswith(prefixo):
            return f"/?aba={aba}"
    return "/"


# Heartbeat do agendador - a tela de Notificacoes mostra se ele esta rodando de verdade.
# Bug real (2026-10-11): o painel subia com `waitress app:app`, que nunca chama
# iniciar_scheduler() - nenhum aviso automatico saiu, nunca, e nada na tela mostrava isso.
_AGENDADOR = {"iniciado": False, "ultimo_tick": None}


def estado_agendador() -> dict:
    ultimo = _AGENDADOR["ultimo_tick"]
    vivo = _AGENDADOR["iniciado"] and (ultimo is None or datetime.now() - ultimo < timedelta(minutes=12))
    return {"ligado": bool(vivo), "ultimo_tick": ultimo.isoformat(timespec="minutes") if ultimo else None}


_CACHE_TRAJETO_AVISO: dict = {}


def _info_trajeto_aviso(local: str) -> dict:
    """{"min", "resumo"} de casa ate o local com o transito de AGORA e os trechos parados.
    Recalcula no maximo 1x por HORA por local (2026-10-15, pedido do Alex: "a cada hora"; antes
    era 1x por dia) - o tick roda a cada 5 min, sem cache seriam ~50 chamadas por compromisso.
    So entra aqui nas 4 h antes do evento (notificacoes.plano_se_arrumar). Falha = min None."""
    agora = datetime.now()
    chave = (agora.date().isoformat(), agora.hour, local.strip().lower())
    if chave not in _CACHE_TRAJETO_AVISO:
        casa = os.environ.get("ENDERECO_CASA", "").strip()
        info = {"min": None, "resumo": ""}
        if casa and maps_client.configurado():
            try:
                viagem = maps_client.tempo_de_viagem(casa, local, lentidao=True)
                info = {"min": int(viagem["duracao_minutos"]), "resumo": maps_client.resumo_transito(viagem)}
            except Exception as e:  # rede/Google fora/cota: aviso sai com a folga padrao
                app.logger.warning("trajeto pro aviso de sair: %s", e)
        _CACHE_TRAJETO_AVISO[chave] = info
    return _CACHE_TRAJETO_AVISO[chave]


def _trajeto_min_aviso(local: str):
    return _info_trajeto_aviso(local)["min"]


def _minutos_se_arrumar(conn) -> int:
    return vida_assistente.se_arrumar_min(conn)


def verificar_e_notificar():
    """Roda as verificacoes proativas e manda pra quem tiver canal configurado
    (push web e/ou Telegram) - cada tipo de aviso so dispara uma vez por dia
    (dedup em notificacoes_enviadas). Chamado pelo scheduler (ver
    iniciar_scheduler) e pelo endpoint manual."""
    _AGENDADOR["ultimo_tick"] = datetime.now()
    # Materializa ANTES de qualquer early-return de canal - rotina recorrente
    # (remedio, academia) tem que aparecer mesmo se push/Telegram nao
    # estiverem configurados ainda, nao pode ficar refem de notificacao.
    conn_materializar = get_db()
    materializar_tarefas_recorrentes(conn_materializar)
    # diario: fecha os dias que passaram (1 chamada de IA por tick no maximo, so quando falta)
    diario.garantir_dias_fechados(conn_materializar)
    # painel puxando assunto: fechar o dia (21h) e padroes da semana (domingo) entram no
    # chat mesmo sem push configurado - o push so avisa (la embaixo, junto dos outros)
    avisos_conversa = conversa_proativa.verificar(conn_materializar, datetime.now())
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
                avisos.append(("tarefa_parada", tarefa_id, "Isso ainda tá pendente?", msg))

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
            titulo = "Orçamento estourado" if nivel == "estourado" else "Orçamento quase no limite"
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
            avisos.append(("cobranca_generica", ref_id, "Cobrança sem identificar", msg))

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

    # Compromisso de sair (date, festa...): "hora de se arrumar" (tempo dele: 40 min padrao,
    # muda pelo chat) e "hora de sair" no lugar do "daqui a pouco" de 10 min, que pra esses
    # chegaria tarde demais (ele ja devia estar saindo).
    planos_sair = notificacoes.plano_se_arrumar(
        conn, datetime.now(), _minutos_se_arrumar(conn),
        trajeto_min=lambda local: _trajeto_min_aviso(vida_assistente.resolver_lugar(conn, local)),
    )
    ids_sair = {p["id"] for p in planos_sair}
    local_do_plano = {p["id"]: p["local"] for p in planos_sair}
    for tipo_sair, ref_sair, titulo_sair, corpo_sair in notificacoes.avisos_se_arrumar(planos_sair):
        if not ja_notificou_hoje(conn, tipo_sair, ref_sair):
            # "hora de sair" leva o transito da ultima hora: "+12 min de transito. Parado na ..."
            if tipo_sair == "hora_de_sair" and local_do_plano.get(ref_sair):
                resumo = _info_trajeto_aviso(vida_assistente.resolver_lugar(conn, local_do_plano[ref_sair]))["resumo"]
                if resumo:
                    corpo_sair = f"{corpo_sair} {resumo}."
            avisos.append((tipo_sair, ref_sair, titulo_sair, corpo_sair))

    for tarefa_id, msg in notificacoes.tarefas_preparo(conn, ignorar=ids_sair):
        if not ja_notificou_hoje(conn, "tarefa_preparo", tarefa_id):
            avisos.append(("tarefa_preparo", tarefa_id, "Daqui a pouco", msg))

    refeicoes_hoje = {
        r["id"]: r["title"] for r in conn.execute(
            "SELECT id, title FROM tasks WHERE due_date = ? AND hora IS NOT NULL AND completed_at IS NULL",
            (date.today().isoformat(),),
        ).fetchall() if notificacoes.e_refeicao(r["title"])
    }
    for tarefa_id, msg in notificacoes.tarefas_com_horario_chegando(conn):
        if tarefa_id in ids_sair:
            continue
        if not ja_notificou_hoje(conn, "tarefa_horario", tarefa_id):
            if tarefa_id in refeicoes_hoje:
                # "Comer: almoco - arroz, feijao, frango" -> "Hora de comer" / "Almoco - arroz..."
                corpo = re.sub(r"^\s*comer\s*:?\s*", "", refeicoes_hoje[tarefa_id], flags=re.I) or msg
                avisos.append(("tarefa_horario", tarefa_id, "Hora de comer", corpo[:1].upper() + corpo[1:]))
            else:
                avisos.append(("tarefa_horario", tarefa_id, "Tá na hora", msg))

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
                "Compromisso chegando",
                f"{evento['titulo']} às {hora_txt} - em menos de 10 min. Já vai se preparando.",
            )
        )

    for voo in notificacoes.voos_de_hoje_com_horario(conn):
        if ja_notificou_hoje(conn, "voo_sair", voo["id"]):
            continue
        msg = _aviso_voo_sair(voo, conn=conn)
        if msg:
            avisos.append(("voo_sair", voo["id"], "Hora de ir pro voo", msg))

    if notificacoes.planejamento_semanal_devido() and not ja_notificou_hoje(conn, "planejamento_semanal"):
        avisos.append(
            (
                "planejamento_semanal",
                0,
                "Como fica sua semana?",
                "Já sabe sua agenda dessa semana? Manda pra mim que eu registro tudo.",
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
    # 2026-10-13: o fechamento agora e uma conversa no chat (conversa_proativa) - quando
    # ela saiu, o push leva o resumo dela no lugar do texto antigo.
    for tipo_conv, titulo_conv, corpo_conv in avisos_conversa:
        if not ja_notificou_hoje(conn, tipo_conv):
            avisos.append((tipo_conv, 0, titulo_conv, corpo_conv))
    if (
        notificacoes.fechamento_noturno_devido()
        and not _briefing_noite_p3_substitui_fechamento(conn)
        and not ja_notificou_hoje(conn, "fechamento_noturno")
        and not ja_notificou_hoje(conn, "fechar_dia_chat")
    ):
        avisos.append(
            ("fechamento_noturno", 0, "Fechando o dia", notificacoes.mensagem_fechamento_noturno(conn))
        )

    msg = notificacoes.currency_voo_baixa(conn, limiar_dias=21)
    if msg and not ja_notificou_hoje(conn, "currency_voo"):
        avisos.append(("currency_voo", 0, "Faz tempo que você não voa", msg))

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
            quem = conta.get("fornecedor") or conta.get("descricao") or "fornecedor não informado"
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

    def _despachar(titulo: str, corpo: str, botoes=None, tipo: str = "", ref_id=0):
        for s in subs:
            sub_dict = json.loads(s["subscription_json"])
            if tipo:
                ok = push_client.enviar(sub_dict, titulo, corpo, url=_url_do_aviso(tipo, f"{tipo}-{ref_id}"), tag=f"{tipo}-{ref_id}")
            else:
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
        _despachar(titulo, corpo, botoes, tipo=tipo, ref_id=ref_id)
        marcar_notificado(conn, tipo, ref_id)
        if subs and tipo in notificacoes.INSISTENCIA:
            db.registrar_aviso_insistente(conn, tipo, ref_id, titulo, corpo, f"{tipo}-{ref_id}", datetime.now())
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

    # Aviso importante que ninguem tocou: repete (so push, o Telegram fica com o 1o envio).
    if subs:
        enviados += _repetir_avisos_insistentes(conn, subs, silencioso, em_hiperfoco)

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


# ---- Diario de decisao (Fase 5, US-C2) - NAO confundir com a tabela
# `decisoes` (Fase 1, "vale a pena?" com pros/contras da IA, efemera) - esta
# aqui e um diario persistente (decisao + contexto + resultado revisado
# depois), dai o nome diferente (diario_decisoes) em db.py e as rotas
# proprias abaixo.


def _criar_medicamento(conn, nome: str, dosagem: str | None, horario: str, recorrencia: str, texto: str | None):
    """Orquestra as duas insercoes (a tarefa recorrente que de verdade
    aparece na agenda/dispara aviso, e o metadado estruturado em
    medicamentos) - compartilhado entre a rota HTTP do form e o executor do
    chat tool, pra nunca divergir. Devolve {"erro": ...} se horario/
    recorrencia vierem invalidos, nunca deixa criar um medicamento quebrado."""
    hora_normalizada = _normalizar_hora(horario)
    if not hora_normalizada:
        return {"erro": "horário inválido - use HH:MM"}
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


# ---- Brain dump (Fase 5, US-C6) - despejo rapido de pensamento solto, sem
# classificar em tarefa/nota/gasto na hora; classifica depois com calma.


def _voo_com_clima(voo: dict) -> dict:
    """Anexa previsao do tempo (se der) pro destino/data do voo - nunca
    quebra se a cidade nao for encontrada ou a data estiver fora da janela
    de previsao, so nao inclui o campo 'clima'."""
    previsao = clima.previsao_para_cidade_e_data(voo["destino"], voo["data"])
    return {**voo, "clima": previsao}


# ---- Assistente de vida (BRIEFING.md, Fase 1) ----

def _checkin_com_rotulos(checkin: dict | None) -> dict | None:
    if not checkin:
        return None
    return {c: vida.ROTULO_CHECKIN.get(checkin.get(c)) for c in vida.CAMPOS_CHECKIN}


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


def _criar_habito(conn, nome, meta, frequencia_tipo, dias_semana, vezes_por_semana, horario) -> dict:
    nome = _texto_curto(nome, 80)
    if not nome:
        return {"erro": "informe o nome do hábito"}
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


def _criar_viagem(conn, destino, data_ida, data_volta, motivo, internacional=False) -> dict:
    destino = _texto_curto(destino, 80)
    ida = _data_iso_valida(data_ida)
    volta = _data_iso_valida(data_volta) if data_volta not in (None, "") else None
    if not destino or not ida:
        return {"erro": "informe o destino e a data de ida (AAAA-MM-DD)"}
    if data_volta not in (None, "") and (not volta or volta < ida):
        return {"erro": "data de volta inválida (tem que ser depois da ida)"}
    viagem_id = create_viagem(conn, destino, ida, volta, _texto_curto(motivo, 80), bool(internacional))
    return {"ok": True, "viagem_id": viagem_id}


# ---- Fase 6 (US-E13): modulo Projetos generico -----------------------------
# Viagens NAO migram pra ca (decisao do Alex) - ver
# /api/viagens/<id>/como-projeto abaixo, que so EMPRESTA o formato via
# vida.converter_viagem_para_projeto pro card reaproveitar o visual, sem
# duplicar dado (le direto de viagens/viagem_itens toda vez).

def _projeto_detalhado(conn, projeto: dict, hoje: date) -> dict:
    return vida.projeto_detalhado(projeto, list_etapas_projeto(conn, projeto["id"]), hoje)


def _criar_projeto(conn, nome, prazo_final) -> dict:
    nome = _texto_curto(nome, 120)
    if not nome:
        return {"erro": "informe o nome do projeto"}
    prazo = None
    if prazo_final not in (None, ""):
        prazo = _data_iso_valida(prazo_final)
        if not prazo:
            return {"erro": "prazo inválido (AAAA-MM-DD)"}
    projeto_id = create_projeto(conn, nome, prazo)
    return {"ok": True, "projeto_id": projeto_id}


def _adicionar_etapa(conn, projeto_id, texto, data_prevista) -> dict:
    texto = _texto_curto(texto, 200)
    if not texto:
        return {"erro": "informe o texto da etapa"}
    data_p = None
    if data_prevista not in (None, ""):
        data_p = _data_iso_valida(data_prevista)
        if not data_p:
            return {"erro": "data da etapa inválida (AAAA-MM-DD)"}
    etapa_id = adicionar_etapa_projeto(conn, projeto_id, texto, data_p)
    if etapa_id is None:
        return {"erro": "projeto não encontrado"}
    return {"ok": True, "etapa_id": etapa_id}


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
        return {"erro": "tipo inválido (use casa, carro, equipamento ou outro)"}
    item = _texto_curto(body.get("item"), 80)
    if not item:
        return {"erro": "informe o item"}

    if tipo == "carro":
        data = _data_iso_valida(body.get("data") or body.get("ultima_vez"))
        if not data:
            return {"erro": "informe a data (AAAA-MM-DD)"}
        km = _numero_positivo_opcional(body.get("km"))
        if km == "invalido":
            return {"erro": "km inválido (número maior ou igual a zero)"}
        proxima_em_km = _numero_positivo_opcional(body.get("proxima_em_km"))
        if proxima_em_km == "invalido":
            return {"erro": "proxima_em_km inválido (número maior ou igual a zero)"}
        proxima_em_data = None
        if body.get("proxima_em_data") not in (None, ""):
            proxima_em_data = _data_iso_valida(body.get("proxima_em_data"))
            if not proxima_em_data:
                return {"erro": "proxima_em_data inválida (AAAA-MM-DD)"}
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
        return {"erro": "data da última vez inválida"}
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


def _criar_ideia_presente(conn, pessoa, ideia, ocasiao) -> dict:
    pessoa = _texto_curto(pessoa, 80)
    ideia_txt = _texto_curto(ideia, 200)
    if not pessoa or not ideia_txt:
        return {"erro": "informe a pessoa e a ideia de presente"}
    ideia_id = create_ideia_presente(conn, pessoa, ideia_txt, _texto_curto(ocasiao, 60))
    return {"ok": True, "ideia_id": ideia_id}


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
        return {"erro": "data de compra inválida (não pode ser no futuro)"}
    garantia_id = create_garantia(conn, produto, compra, prazo, nota_fiscal_anexo)
    return {"ok": True, "garantia_id": garantia_id}


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
                    "já passou do prazo" if dias_ate < 0
                    else "vence hoje" if dias_ate == 0
                    else f"vence em {dias_ate} dia(s)"
                )
        if not motivo and m["proxima_em_km"] is not None and km_atual is not None:
            km_faltando = m["proxima_em_km"] - km_atual
            if km_faltando <= km_aviso:
                motivo = (
                    f"já passou {abs(km_faltando):.0f}km do previsto" if km_faltando < 0
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
    if lugar in LUGARES_AEROCLUBE:
        return _mensagem_aeroclube(conn, evento, agora)
    return None


LUGARES_AEROCLUBE = ("aeroclube", "ssbl", "aeroclube de blumenau")


def _mensagem_aeroclube(conn, evento: str, agora: datetime) -> str | None:
    """4a leva: automacao de localizacao do Atalhos no aeroclube. Chegou com voo hoje ->
    checklist no chat; saiu depois de decolar -> "quanto deu?" na hora (o tick nao repete)."""
    voos = conn.execute(
        "SELECT id, hora FROM voos WHERE data = ? AND horas IS NULL AND COALESCE(tipo, '') != 'simulador' "
        "ORDER BY hora",
        (agora.date().isoformat(),),
    ).fetchall()
    if not voos:
        return None
    if evento == "chegou":
        v = next((v for v in voos if not v["hora"] or v["hora"] >= agora.strftime("%H:%M")), voos[0])
        chave = f"aeroclube_chegou_{v['id']}"
        if obter_configuracao(conn, chave):
            return None
        definir_configuracao(conn, chave, agora.isoformat(timespec="minutes"))
        # "Fone (headset)" -> "fone (headset)", mas sigla fica ("CIV e CMA")
        itens = ", ".join(t if t[:2].isupper() else t[:1].lower() + t[1:] for t in cards.MOCHILA_VOO)
        decola = f" Decola {v['hora']}." if v["hora"] else ""
        texto = f"Chegou no aeroclube.{decola} Confere: {itens}. Bom voo!"
        conversa_proativa.publicar(conn, "aeroclube_chegou", texto, [])
        return texto
    agora_hhmm = agora.strftime("%H:%M")
    voados = [v for v in voos if (v["hora"] and v["hora"] <= agora_hhmm)
              or (not v["hora"] and obter_configuracao(conn, f"aeroclube_chegou_{v['id']}"))]
    if voados and conversa_proativa.perguntar_horas_agora(conn, voados[-1]["id"], agora):
        return "Quanto deu o voo? Um toque no chat e eu somo nas tuas horas."
    return None


# ---- Assistente de vida (BRIEFING.md, Fase 3) ----


def _criar_aprender(conn, tema, nota) -> dict:
    if isinstance(tema, str) and len(tema.strip()) > 80:
        return {"erro": "tema muito longo (até 80 caracteres)"}
    tema = _texto_curto(tema, 80)
    if not tema:
        return {"erro": "informe o tema"}
    nota = nota.strip()[:300] or None if isinstance(nota, str) else None
    return {"ok": True, "id": create_aprender(conn, tema, nota)}


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
        aviso = "Não consegui ler a página agora - o link ficou salvo."
    if resumo is None and aviso is None:
        aviso = "Salvei o link, mas não deu pra resumir."
    salvo_id = create_salvo(conn, url, titulo, resumo)
    return {"ok": True, "id": salvo_id, "titulo": titulo, "resumo": resumo, "aviso": aviso}


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


def _uso_apps(conn, dias: int) -> dict:
    desde = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")
    minutos = vida.uso_de_apps(list_eventos_app(conn, desde))
    return {
        "dias": dias,
        "apps": [{"app": a, "minutos": m, "texto": vida.formatar_minutos(m)} for a, m in minutos.items()],
        "total_minutos": sum(minutos.values()),
    }


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


def _definir_limite_cartao(conn, bank_account_id: int, limite) -> dict:
    if limite in (None, ""):
        ok = definir_limite_conta(conn, bank_account_id, None)
        return {"ok": True} if ok else {"erro": "conta não encontrada"}
    valida = isinstance(limite, (int, float)) and not isinstance(limite, bool) and math.isfinite(limite) and limite > 0
    if not valida:
        return {"erro": "limite precisa ser um número maior que zero (ou vazio pra apagar)"}
    ok = definir_limite_conta(conn, bank_account_id, float(limite))
    return {"ok": True} if ok else {"erro": "conta não encontrada"}


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


TAMANHO_MAX_PDF_BYTES = 15 * 1024 * 1024  # 15MB - cabe folgado num orcamento escaneado


TAMANHO_MAX_IMAGEM_BYTES = 10 * 1024 * 1024  # 10MB - foto de celular cabe folgado


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
    "corrigir_ultimo": "uma correcao do último item",
    "desconhecido": None,
}


def _texto_falado_intent(resultado: dict) -> str:
    """Frase curta pronta pro Atalho falar de volta (acao "Falar Texto"/
    "Mostrar Resultado" do app Atalhos) - nunca executa a acao aqui (fora do
    escopo da US-B4, ver docs/INTENT.md), so descreve o que foi entendido."""
    if resultado.get("teto_ia_estourado"):
        return "O limite mensal de IA já estourou, não consegui entender esse comando agora."

    acao = resultado.get("acao")
    rotulo = _ROTULO_ACAO_INTENT.get(acao)
    if not rotulo:
        return "Não entendi esse comando. Tenta de novo com mais detalhe."

    parametros = resultado.get("parametros") or {}
    detalhe = ""
    if acao == "navegar_tela" and parametros.get("tela"):
        detalhe = f' ({parametros["tela"]})'
    elif acao in ("registrar_tarefa", "registrar_gasto") and parametros.get("titulo"):
        detalhe = f': {parametros["titulo"]}'
    elif acao == "consultar" and parametros.get("pergunta"):
        detalhe = f': {parametros["pergunta"]}'

    if resultado.get("precisa_confirmacao"):
        return f"Acho que entendi {rotulo}{detalhe}, mas não tenho certeza. Confirma no painel antes de executar."
    return f"Entendi {rotulo}{detalhe}. Confirma no painel pra executar."


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
        # frequente, o dedup em notificacoes_enviadas ja evita reenvio. Primeira
        # checagem logo ao subir (sem esperar 5 min) - painel reiniciado perto de um
        # horario nao perde o aviso.
        scheduler.add_job(
            verificar_e_notificar, "interval", minutes=5, next_run_time=datetime.now() + timedelta(seconds=30)
        )
        # backup semanal (domingo 3h da manha - baixo uso), ver
        # rodar_backup_automatico_semanal pro que ele faz
        scheduler.add_job(rodar_backup_automatico_semanal, "cron", day_of_week="sun", hour=3, minute=0)
        # backup DIARIO (3h30, mantem 14) + um disparo imediato ao subir o
        # app: se o ultimo backup tiver mais de 24 h (PC desligado de
        # madrugada) ele recupera na hora - ver backup_diario.py
        scheduler.add_job(backup_diario.rodar_backup_diario, "cron", hour=3, minute=30)
        scheduler.add_job(backup_diario.backup_se_atrasado, "date")
        # sync automatico do Nubank as 4h de Brasilia (uso/m2-sync). O
        # BackgroundScheduler usa o fuso local do processo, e nao existe TZ
        # configurado nem no .env nem no render.yaml - o Render (producao de
        # teste, ver render.yaml) sobe o container em UTC, e sem TZ setado
        # localmente o Python tambem cai em UTC. 4h em Brasilia (America/
        # Sao_Paulo, fixo em UTC-3 desde que o Brasil aboliu o horario de
        # verao em 2019, sem trocas de horario pra acompanhar) = 7h UTC.
        scheduler.add_job(rodar_sincronizacao_nubank_automatica, "cron", hour=7, minute=0)
        scheduler.start()
        _AGENDADOR["iniciado"] = True


# Fase 7: rotas por Blueprint (rotas/*.py, carga automatica) - SEMPRE no fim,
# depois de todo helper que os blueprints usam via rotas._base.app_modulo().
rotas.registrar_todas(app)


if __name__ == "__main__":
    iniciar_scheduler()
    iniciar_telegram()
    app.run(debug=True, port=5001)
