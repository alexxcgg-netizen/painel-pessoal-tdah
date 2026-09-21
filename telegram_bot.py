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


def enviar_mensagem(texto: str) -> bool:
    """Manda uma mensagem pro chat configurado (TELEGRAM_CHAT_ID) - usado
    tanto pra responder uma conversa quanto pros avisos proativos do
    scheduler. Corta com seguranca no limite de caracteres do Telegram em
    vez de deixar a chamada falhar."""
    if not configurado():
        return False
    try:
        resposta = requests.post(
            _url("sendMessage"),
            json={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": texto[:LIMITE_TEXTO_TELEGRAM]},
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


def _buscar_updates(offset: int | None) -> list[dict]:
    params = {"timeout": POLLING_TIMEOUT}
    if offset is not None:
        params["offset"] = offset
    resposta = requests.get(_url("getUpdates"), params=params, timeout=POLLING_TIMEOUT + 10)
    resposta.raise_for_status()
    return resposta.json().get("result", [])


def iniciar_polling(chat_fn, parar_evento: threading.Event | None = None):
    """Loop de long polling - roda pra sempre (chamado numa thread separada,
    ver iniciar_thread) ou ate parar_evento ser setado (usado so em teste,
    pra nao deixar uma thread de teste rodando pra sempre). Erro de rede so
    espera um pouco e tenta de novo, nunca derruba a thread."""
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
            resposta = processar_update(update, chat_fn)
            if resposta:
                enviar_mensagem(resposta)


def iniciar_thread(chat_fn) -> threading.Thread:
    """Sobe o polling numa thread daemon (nao impede o processo de terminar) -
    chamado uma vez, na subida do app (ver app.iniciar_telegram)."""
    thread = threading.Thread(target=iniciar_polling, args=(chat_fn,), daemon=True)
    thread.start()
    return thread
