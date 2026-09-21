"""Bot do Telegram - canal de conversa principal do painel, alem do chat web.
O Alex manda mensagem pro bot como manda pra qualquer contato humano; o bot
roda o mesmo pipeline de /api/chat (app._processar_mensagem_chat, passado
aqui como `chat_fn`) e responde no proprio Telegram. As notificacoes
proativas (verificar_e_notificar, em app.py) tambem chegam por aqui quando
configurado, alem do push web - e o canal que faz o painel parecer alguem
te mandando mensagem, nao um app que voce precisa abrir.

So fica ativo quando TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID existem no .env:
1. Fala com o @BotFather no Telegram, manda /newbot, pega o token
2. Manda qualquer mensagem pro bot novo, depois abre no navegador
   https://api.telegram.org/bot<TOKEN>/getUpdates - o "chat":{"id": ...}
   da resposta e o seu TELEGRAM_CHAT_ID
3. Cola os dois no .env e reinicia o python app.py

E um bot de UM USUARIO SO: qualquer mensagem vinda de um chat_id diferente
do TELEGRAM_CHAT_ID configurado e ignorada (nunca processada, nunca
respondida) - garante que so o Alex consegue conversar com o painel dele
por ali, mesmo que o token do bot vaze/seja descoberto por alguem.

Usa long polling (getUpdates), nao webhook - funciona rodando de casa, sem
precisar de URL publica/HTTPS exposta, o mesmo motivo que o app inteiro
roda assim hoje."""

import os
import threading
import time

import requests

POLLING_TIMEOUT = 25  # segundos - long polling do getUpdates
LIMITE_TEXTO_TELEGRAM = 4096  # limite de caracteres por mensagem imposto pela API


def configurado() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN")) and bool(os.environ.get("TELEGRAM_CHAT_ID"))


def _url(metodo: str) -> str:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    return f"https://api.telegram.org/bot{token}/{metodo}"


def enviar_mensagem(texto: str, botoes: list[tuple[str, str]] | None = None) -> bool:
    """Manda uma mensagem pro chat configurado (TELEGRAM_CHAT_ID) - usado
    tanto pra responder uma conversa quanto pros avisos proativos do
    scheduler. Corta com seguranca no limite de caracteres do Telegram em
    vez de deixar a chamada falhar.

    'botoes' (opcional) e uma lista de (texto_do_botao, callback_data) - vira
    um botao inline embaixo da mensagem que, ao ser tocado, manda um
    callback_query de volta pro bot (ver processar_callback) em vez de abrir
    o app - a acao acontece com um toque, sem precisar digitar nada."""
    if not configurado():
        return False
    payload = {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": texto[:LIMITE_TEXTO_TELEGRAM]}
    if botoes:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": label, "callback_data": dados} for label, dados in botoes]]
        }
    try:
        resposta = requests.post(_url("sendMessage"), json=payload, timeout=10)
        return resposta.status_code == 200
    except requests.RequestException:
        return False


def responder_callback(callback_query_id: str, texto: str | None = None) -> bool:
    """Fecha o "carregando" que o Telegram mostra no botao logo apos o
    toque - a API exige essa chamada sempre, mesmo sem nada pra mostrar
    (senao o botao fica girando ate dar timeout do lado do usuario)."""
    if not configurado():
        return False
    payload = {"callback_query_id": callback_query_id}
    if texto:
        payload["text"] = texto
    try:
        resposta = requests.post(_url("answerCallbackQuery"), json=payload, timeout=10)
        return resposta.status_code == 200
    except requests.RequestException:
        return False


def remover_botoes(chat_id: str, message_id: int) -> bool:
    """Tira o teclado inline da mensagem depois do toque - evita um segundo
    toque acidental disparar a mesma acao de novo."""
    if not configurado():
        return False
    try:
        resposta = requests.post(
            _url("editMessageReplyMarkup"),
            json={"chat_id": chat_id, "message_id": message_id, "reply_markup": {"inline_keyboard": []}},
            timeout=10,
        )
        return resposta.status_code == 200
    except requests.RequestException:
        return False


def extrair_texto_e_chat_id(update: dict) -> tuple[str, str] | None:
    """Pura: separa (texto, chat_id) de um update do Telegram, ou None se o
    update nao tiver mensagem de texto (foto, sticker, membro entrando no
    grupo etc) - so identifica o que tem, nao decide quem tem permissao
    (isso fica em processar_update, que compara com TELEGRAM_CHAT_ID)."""
    mensagem = update.get("message")
    if not isinstance(mensagem, dict):
        return None
    texto = mensagem.get("text")
    chat = mensagem.get("chat")
    if not texto or not isinstance(chat, dict) or chat.get("id") is None:
        return None
    return texto, str(chat["id"])


def processar_update(update: dict, chat_fn) -> str | None:
    """Processa um update: se tiver texto E vier do chat_id autorizado,
    chama chat_fn(texto) (o pipeline de conversa de verdade, ver
    app._processar_mensagem_chat) e devolve a resposta pra mandar de volta.
    None quando o update deve ser ignorado sem resposta nenhuma - update sem
    texto, ou de um chat_id nao autorizado (nunca revela que o bot existe
    pra quem nao e o Alex, so fica em silencio)."""
    extraido = extrair_texto_e_chat_id(update)
    if not extraido:
        return None
    texto, chat_id = extraido
    if chat_id != os.environ.get("TELEGRAM_CHAT_ID", ""):
        return None
    return chat_fn(texto)


def processar_callback(update: dict, callback_fn) -> dict | None:
    """Se o update for um clique num botao inline (callback_query) vindo do
    chat autorizado, chama callback_fn(dados) - onde 'dados' e o
    callback_data que o botao carregava, ex: "completar_tarefa:123" - e
    devolve o que precisa pra fechar o loop (responder_callback +
    remover_botoes). None quando nao e callback, ou vem de outro chat
    (mesma regra de silencio de processar_update - nunca revela que o bot
    existe pra quem nao e o Alex)."""
    callback = update.get("callback_query")
    if not isinstance(callback, dict):
        return None
    dados = callback.get("data")
    mensagem = callback.get("message")
    callback_query_id = callback.get("id")
    if not dados or not callback_query_id or not isinstance(mensagem, dict):
        return None
    chat = mensagem.get("chat")
    message_id = mensagem.get("message_id")
    if not isinstance(chat, dict) or chat.get("id") is None or message_id is None:
        return None
    if str(chat["id"]) != os.environ.get("TELEGRAM_CHAT_ID", ""):
        return None
    texto_resposta = callback_fn(dados)
    return {
        "callback_query_id": callback_query_id,
        "chat_id": str(chat["id"]),
        "message_id": message_id,
        "texto_resposta": texto_resposta,
    }


def _buscar_updates(offset: int | None) -> list[dict]:
    params = {"timeout": POLLING_TIMEOUT}
    if offset is not None:
        params["offset"] = offset
    resposta = requests.get(_url("getUpdates"), params=params, timeout=POLLING_TIMEOUT + 10)
    resposta.raise_for_status()
    return resposta.json().get("result", [])


def iniciar_polling(chat_fn, parar_evento: threading.Event | None = None, callback_fn=None):
    """Loop de long polling - roda pra sempre (chamado numa thread separada,
    ver iniciar_thread) ou ate parar_evento ser setado (usado so em teste,
    pra nao deixar uma thread de teste rodando pra sempre). Erro de rede so
    espera um pouco e tenta de novo, nunca derruba a thread.

    'callback_fn' (opcional) trata toques em botao inline (ver
    processar_callback) - sem ele, um callback_query so e ignorado (nenhum
    botao foi mandado, entao nenhum devia chegar)."""
    parar_evento = parar_evento or threading.Event()
    offset = None
    while not parar_evento.is_set():
        try:
            updates = _buscar_updates(offset)
        except requests.RequestException:
            time.sleep(5)
            continue
        for update in updates:
            offset = update["update_id"] + 1
            if callback_fn is not None:
                resultado = processar_callback(update, callback_fn)
                if resultado:
                    responder_callback(resultado["callback_query_id"], resultado["texto_resposta"])
                    remover_botoes(resultado["chat_id"], resultado["message_id"])
                    continue
            resposta = processar_update(update, chat_fn)
            if resposta:
                enviar_mensagem(resposta)


def iniciar_thread(chat_fn, callback_fn=None) -> threading.Thread:
    """Sobe o polling numa thread daemon (nao impede o processo de terminar) -
    chamado uma vez, na subida do app (ver app.iniciar_telegram)."""
    thread = threading.Thread(
        target=iniciar_polling, args=(chat_fn,), kwargs={"callback_fn": callback_fn}, daemon=True
    )
    thread.start()
    return thread
