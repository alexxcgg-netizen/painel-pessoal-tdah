"""Blueprint atalho - gerado/movido de app.py (faixa R1, sem mudanca de comportamento)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from rotas._base import app_modulo
from datetime import timedelta
from db import criar_item_cotacao, definir_configuracao, get_db, obter_configuracao, registrar_evento_app
import json
import vida

bp = Blueprint("atalho", __name__)

@bp.route("/api/atalho/local", methods=["POST"])
def atalho_local():
    """Automacao de localizacao do Atalhos (chegou/saiu de um lugar). Devolve
    a mensagem pro proprio Atalho mostrar - vazia quando nao ha nada a dizer
    (o Atalho so mostra notificacao se o texto nao estiver vazio). A mesma
    mensagem nao se repete em menos de 2h (geofence costuma disparar mais de
    uma vez quando o sinal oscila na porta de casa)."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    _inteiro_no_intervalo = app._inteiro_no_intervalo
    _mensagem_local = app._mensagem_local
    _token_atalho_valido = app._token_atalho_valido
    datetime = app.datetime
    if not _token_atalho_valido(obrigatorio=True):
        return jsonify({"error": "token inválido"}), 401
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

@bp.route("/api/atalho/despertador", methods=["GET"])
def atalho_despertador():
    """4a leva: a automacao "todo dia 22h" do Atalhos pergunta a hora de acordar amanha
    (primeiro compromisso com hora - voo ou tarefa - menos trajeto e tempo de se arrumar).
    `?ate=HH:MM` = o horario normal dele: se nao precisar acordar antes disso, tem=false e o
    Atalho nao mexe no alarme. Depois da meia-noite (antes das 4h) olha o proprio dia."""
    app = app_modulo()
    if not app._token_atalho_valido(obrigatorio=True):
        return jsonify({"error": "token inválido"}), 401
    agora = app._agora_brasilia().replace(tzinfo=None)
    dia = agora.date() if agora.hour < 4 else agora.date() + timedelta(days=1)
    ate = app._normalizar_hora(request.args.get("ate")) if request.args.get("ate") else None
    import despertador

    conn = get_db()
    try:
        p = app._primeiro_compromisso_do_dia(conn, dia.isoformat())
        pedida = despertador.pedido(conn, dia.isoformat())
    finally:
        conn.close()
    base = {"tem": False, "data": dia.isoformat(), "mensagem": ""}
    if pedida:
        # pedido explicito do Alex no chat ("amanha quero acordar as 7"): ignora o `ate`, mas se um
        # compromisso exigir acordar ANTES, o mais cedo ganha (acordar atrasado perde o voo)
        hora = despertador.mais_cedo(pedida, p["acordar"] if p else None)
        motivo = "você pediu" if hora == pedida else f"{p['titulo']} às {p['hora']} pede antes das {pedida}"
        return jsonify({
            "tem": True,
            "data": dia.isoformat(),
            "acordar": hora,
            "acordar_iso": f"{dia.isoformat()}T{hora}:00",
            "titulo": "pedido" if hora == pedida else p["titulo"],
            "hora": hora if hora == pedida else p["hora"],
            "sair": p["sair"] if p and hora != pedida else None,
            "mensagem": f"Despertador às {hora}: {motivo}.",
        })
    if not p:
        return jsonify(base)
    if ate and p["acordar"] >= ate:
        return jsonify(base | {"acordar": p["acordar"], "titulo": p["titulo"], "hora": p["hora"]})
    titulo = "o voo" if p["titulo"] == "voo" else f"\"{p['titulo']}\""
    return jsonify({
        "tem": True,
        "data": dia.isoformat(),
        "acordar": p["acordar"],
        "acordar_iso": f"{dia.isoformat()}T{p['acordar']}:00",
        "titulo": p["titulo"],
        "hora": p["hora"],
        "sair": p["sair"],
        "mensagem": f"Despertador às {p['acordar']}: {titulo} às {p['hora']}, sai {p['sair']}.",
    })


@bp.route("/api/atalho/app", methods=["POST"])
def atalho_app():
    """Automacao 'App abriu/fechou' do Atalhos (uma por app) - o Screen Time
    nao e legivel pelo Atalhos, entao o tempo de uso e aproximado por aqui."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    _texto_curto = app._texto_curto
    _token_atalho_valido = app._token_atalho_valido
    datetime = app.datetime
    if not _token_atalho_valido(obrigatorio=True):
        return jsonify({"error": "token inválido"}), 401
    body = _corpo_json()
    nome = _texto_curto(body.get("app"), 40)
    evento = body.get("evento")
    if not nome or evento not in ("abriu", "fechou"):
        return jsonify({"error": "mande app e evento ('abriu' ou 'fechou')"}), 400
    conn = get_db()
    registrar_evento_app(conn, nome, evento, datetime.now().isoformat(timespec="seconds"))
    conn.close()
    return jsonify({"ok": True})

@bp.route("/api/atalho/capturar", methods=["POST"])
def atalho_capturar():
    """Pro Atalho "Ei Siri, anota" do iPhone - mesma logica de /api/capture,
    so que autenticado por token em vez de sessao de login (o app Atalhos
    nao guarda cookie entre execucoes)."""
    app = app_modulo()
    _corpo_json = app._corpo_json
    _executar_captura = app._executar_captura
    _token_atalho_valido = app._token_atalho_valido
    if not _token_atalho_valido():
        return jsonify({"error": "token inválido"}), 401

    body = _corpo_json()
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "texto vazio"}), 400
    return _executar_captura(text, "")

@bp.route("/api/atalho/comando-voz", methods=["POST"])
def atalho_comando_voz():
    """US-B4: pro Atalho "Ei Siri, [comando]" do iPhone - mesmo padrao de
    autenticacao por token dos outros /api/atalho/*. Recebe o texto que o
    Siri ja transcreveu (acao "Ditar Texto" do app Atalhos) e reusa a MESMA
    logica de classificacao de /api/intent/classificar (_classificar_intent,
    fonte unica - nunca duplicada aqui). Devolve so uma frase curta ("fala")
    pronta pro Atalho falar de volta - NAO executa a acao classificada
    sozinho (fora do escopo desta historia; a execucao de verdade acontece
    no painel, US-B1/US-B2, com a confirmacao explicita do Alex)."""
    app = app_modulo()
    _classificar_intent = app._classificar_intent
    _corpo_json = app._corpo_json
    _texto_falado_intent = app._texto_falado_intent
    _token_atalho_valido = app._token_atalho_valido
    if not _token_atalho_valido():
        return jsonify({"error": "token inválido"}), 401

    body = _corpo_json()
    texto = (body.get("texto") or body.get("text") or "").strip()
    if not texto:
        return jsonify({"error": "texto vazio", "fala": "Não entendi, pode repetir?"}), 400

    conn = get_db()
    resultado, error = _classificar_intent(conn, texto)
    if error:
        conn.close()
        status = error[1] if isinstance(error, tuple) else 502
        return jsonify({"error": "erro ao classificar", "fala": "Deu um erro ao tentar entender o comando."}), status
    conn.commit()
    conn.close()

    return jsonify({**resultado, "fala": _texto_falado_intent(resultado)})

@bp.route("/api/atalho/perguntar", methods=["POST"])
def atalho_perguntar():
    """"Ei Siri, pergunta pro painel" (2026-10-13): o texto ditado vai pro MESMO chat da tela
    principal (_processar_mensagem_chat - memorias, tarefas, ferramentas; a conversa aparece
    no app depois) em modo voz, e volta so a frase pronta pro Atalho falar ("fala"), sem
    markdown nem card. Diferente do comando-voz (que so classifica): aqui a IA faz de verdade
    o que faria no chat. Autenticado pelo mesmo token dos outros /api/atalho/*."""
    import re

    app = app_modulo()
    if not app._token_atalho_valido(obrigatorio=True):
        return jsonify({"error": "token inválido"}), 401
    body = app._corpo_json()
    texto = app._texto_seguro(body.get("texto") or body.get("text"))
    if not texto:
        return jsonify({"error": "texto vazio", "fala": "Não entendi, pode repetir?"}), 400
    if len(texto) > app.TAMANHO_MAX_TEXTO_CHAT:
        return jsonify({"error": app.MSG_TEXTO_LONGO, "fala": "Ficou longo demais, fala mais curto."}), 400

    conn = get_db()
    try:
        resposta, _acoes, erro = app._processar_mensagem_chat(conn, texto, {}, modo_voz=True)
    finally:
        conn.close()
    if erro:
        status = 402 if erro == app.TETO_IA_MSG else 502
        return jsonify({"error": erro, "fala": "Não consegui responder agora. Tenta pelo app."}), status
    # lista do chat vira frase: "hoje:\n- academia\n- ligar" -> "hoje: academia. Ligar."
    limpo = re.sub(r"[*_#`>|]+", "", resposta or "")
    partes = [re.sub(r"^[-•\d.)\s]+", "", linha).strip() for linha in limpo.splitlines()]
    fala = ""
    for parte in filter(None, partes):
        if fala:
            if fala.endswith(":"):
                fala += " "
            else:
                fala += " " if fala.endswith((",", ".", "!", "?")) else ". "
                parte = parte[:1].upper() + parte[1:]
        fala += parte
    if fala and fala[-1] not in ".!?":
        fala += "."
    return jsonify({"fala": fala or "Pronto.", "resposta": resposta})

@bp.route("/api/atalho/cotacao-pdf", methods=["POST"])
def atalho_cotacao_pdf():
    """Pro Atalho "Compartilhar PDF" do iPhone - aparece no menu de
    Compartilhar do iOS quando o Alex ta vendo o PDF de um orcamento
    (ex: recebido no WhatsApp). Recebe o PDF + o titulo da cotacao (o Alex
    fala/digita, ex: "portas") e acha ou cria a cotacao sozinho - assim nao
    precisa saber o ID numerico dela."""
    app = app_modulo()
    TAMANHO_MAX_PDF_BYTES = app.TAMANHO_MAX_PDF_BYTES
    _call_claude = app._call_claude
    _log_usage = app._log_usage
    _resolver_cotacao_por_titulo = app._resolver_cotacao_por_titulo
    _token_atalho_valido = app._token_atalho_valido
    claude_client = app.claude_client
    if not _token_atalho_valido():
        return jsonify({"error": "token inválido"}), 401

    titulo_cotacao = (request.form.get("titulo_cotacao") or "").strip()
    if not titulo_cotacao:
        return jsonify({"error": "informe o titulo da cotação (ex: portas)"}), 400

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

@bp.route("/api/atalho/resumo", methods=["GET"])
def atalho_resumo():
    """Resumo compacto pra widget externo (ex: Scriptable no iPhone) -
    autenticado por token, sem sessao, e sem chamar a IA (so leitura direta
    do banco) pra ficar rapido o bastante pra um widget de tela inicial."""
    app = app_modulo()
    _eventos_de_hoje_com_seguranca = app._eventos_de_hoje_com_seguranca
    _token_atalho_valido = app._token_atalho_valido
    date = app.date
    datetime = app.datetime
    if not _token_atalho_valido():
        return jsonify({"error": "token inválido"}), 401

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
