"""Fase 7, faixa N2 (captura por Telegram) - fluxo NOVO, baseado em WEBHOOK.

Convive com `telegram_bot.py` (Fase 3, canal de CONVERSA - /api/chat por
long polling): os dois sao independentes aqui no codigo, mas usam o MESMO
`TELEGRAM_BOT_TOKEN` por instrucao da tarefa, e a API do Telegram nao deixa
um bot ter webhook E long polling ligados ao mesmo tempo (`getUpdates` passa
a devolver 409 assim que um `setWebhook` for registrado pro mesmo token).
Ver docs/telegram-captura.md ("Convivencia com o bot antigo") pra decisao
de qual dos dois fica ligado - o integrador escolhe.

Este modulo e' de CAPTURA (texto vira tarefa/gasto/meta, audio e' transcrito
e cai no mesmo fluxo, foto de nota fiscal vira gasto, link cai em "Salvos
pra ver depois"), nunca de conversa - isso continua em telegram_bot.py.

Desenho: nenhuma funcao daqui importa `app` (direto ou via `rotas._base`) -
evita risco de import circular (mesmo motivo documentado em
`rotas/_base.py`) e deixa tudo testavel com dubles, sem Flask nem rede
real. Quem monta as pecas de verdade (banco,
`app._executar_captura`, `app._salvar_link`, extracao de nota fiscal) e'
`rotas/n2_telegram.py`, na hora da requisicao.
"""

from __future__ import annotations

import difflib
import re

import mimetypes
import os
import time

import requests

import leitura

TIMEOUT_TELEGRAM = 15  # segundos - sendMessage/getFile
TIMEOUT_DOWNLOAD = 30  # segundos - baixar o arquivo em si (pode ser maior)
LIMITE_TEXTO_TELEGRAM = 4096  # limite de caracteres por mensagem da API do Telegram
TAMANHO_MAX_ARQUIVO = 20 * 1024 * 1024  # 20MB - mesmo teto que a Bot API do Telegram usa pra getFile

# Nome usado em ia.teto.teto_permite(...)/ia.medicao.registrar_uso(...) pra
# transcricao de audio - ver transcrever() abaixo e docs/telegram-captura.md.
FUNCAO_TRANSCRICAO = "transcricao"
PROVEDOR_TRANSCRICAO = "groq"
# 2026-10-10: large-v3 (cheio) no lugar do turbo - mais preciso em portugues e o unico dos
# dois que devolve no_speech_prob util por trecho (o turbo "ouvia" um "E ai" em audio so de
# silencio com no_speech_prob 0). Groq: US$0,111/hora de audio (antes 0,04 do turbo).
MODELO_TRANSCRICAO = "whisper-large-v3"
PRECO_TRANSCRICAO_USD_POR_SEGUNDO = 0.111 / 3600
# Vocabulario do Alex pro Whisper acertar nome proprio (prompt curto: prompt longo vaza pro
# texto quando o audio e quase silencio).
PROMPT_TRANSCRICAO = (
    "Alex falando com o assistente do painel pessoal. Brusque, Blumenau, aeroclube, CIV, ANAC, "
    "SSBL, PR-LOM, PT-XXW, Fiorino, contabilidade, notas fiscais, Roberta."
)
# trecho com no_speech_prob acima disso e descartado (o Whisper inventa frase em silencio:
# "Legenda Adriana Zanotto", "E ai", "Idiota." no fim da fala...)
LIMITE_SEM_FALA = 0.6
MARGEM_FALA_S = 0.6

# 2026-10-11 (print do Alex): o Whisper as vezes REPETE o prompt de vocabulario no fim da fala
# ("... em Brusque mesmo. Bursque, Bblumenau, aeroclube, CIV, ANAC, SSBL, PR-LOM...") - eco do
# prompt, alucinacao conhecida quando o audio termina em silencio. Corta a enumeracao final
# quando ela e, na maior parte, a propria lista (com erro de grafia: comparacao aproximada).
_VOCAB_PROMPT = [
    v.strip().lower() for v in PROMPT_TRANSCRICAO.split(". ", 1)[1].rstrip(".").split(",") if v.strip()
]
_FRASE_PROMPT = PROMPT_TRANSCRICAO.split(". ", 1)[0].lower()


def _parece_vocab(item: str) -> bool:
    item = re.sub(r"[^\w\- ]", "", item.lower()).strip()
    if not item:
        return False
    return any(difflib.SequenceMatcher(None, item, v).ratio() >= 0.75 for v in _VOCAB_PROMPT)


def tirar_eco_do_prompt(texto: str) -> str:
    """Tira do FIM do texto a lista de vocabulario repetida pelo Whisper (e a frase de abertura
    do prompt, se vier). So corta enumeracao de 4+ itens curtos em que 60%+ batem com a lista -
    "fui pra Brusque e Blumenau" (fala normal) nunca e cortado."""
    texto = (texto or "").strip()
    if _FRASE_PROMPT[:30] in texto.lower():
        texto = texto[: texto.lower().index(_FRASE_PROMPT[:30])].strip()
    m = re.search(r"((?:[\w\-]+(?: [\w\-]+)?\s*,\s*){3,}[\w\-]+(?: [\w\-]+)?\s*[.!]?)\s*$", texto)
    if m:
        itens = [i for i in re.split(r"\s*,\s*", m.group(1).rstrip(".! ")) if i]
        if len(itens) >= 4 and sum(_parece_vocab(i) for i in itens) >= 0.6 * len(itens):
            texto = texto[: m.start()].rstrip(" ,")
    return texto


# trecho do Whisper que encosta menos que isso (fracao da duracao dele) nos trechos de voz DELE
# medidos no celular = conversa do fundo, sai
TRECHO_VOZ_MIN_SOBREPOSICAO = 0.2
TRECHO_VOZ_MARGEM_S = 0.35


def _sobreposicao(ini: float, fim: float, trechos_voz) -> float:
    total = 0.0
    for a, b in trechos_voz:
        total += max(0.0, min(fim, b + TRECHO_VOZ_MARGEM_S) - max(ini, a - TRECHO_VOZ_MARGEM_S))
    return total


def texto_dos_trechos(resposta: dict, fala_desde: float | None = None, fala_ate: float | None = None,
                      trechos_voz: list | None = None) -> str:
    """Monta o texto so com os trechos que sao fala de verdade: descarta trecho que o
    Whisper marcou como provavel silencio e, quando o app mediu onde a voz comecou/terminou
    (fala_desde/fala_ate, em segundos desde o inicio da gravacao), trecho que cai inteiro
    fora disso - e ai que nasce a palavra inventada do fim. Sem `segments` (resposta
    simples), usa `text` como veio."""
    trechos = resposta.get("segments")
    if not isinstance(trechos, list):
        return tirar_eco_do_prompt(resposta.get("text") or "")
    bons = []
    for t in trechos:
        if not isinstance(t, dict):
            continue
        if float(t.get("no_speech_prob") or 0) >= LIMITE_SEM_FALA:
            continue
        ini, fim = float(t.get("start") or 0), float(t.get("end") or 0)
        if fala_ate is not None and ini > fala_ate + MARGEM_FALA_S:
            continue
        if fala_desde is not None and fim < fala_desde - MARGEM_FALA_S:
            continue
        # 2026-10-13: voz de fundo - trecho que quase nao encosta em nenhum momento em que ELE falava
        if trechos_voz and fim - ini > 0.3 and _sobreposicao(ini, fim, trechos_voz) < TRECHO_VOZ_MIN_SOBREPOSICAO * (fim - ini):
            continue
        bons.append((t.get("text") or "").strip())
    return tirar_eco_do_prompt(" ".join(b for b in bons if b))


class ErroCaptura(Exception):
    """Erro conhecido/tratado no processamento de um update (download
    falhou, teto de IA estourado, IA fora do ar, audio vazio...) - sempre
    vira uma mensagem curta pro Alex no Telegram, nunca uma excecao crua
    subindo ate o Flask (que responderia 500 e o Telegram reenviaria)."""


# ---- Webhook (N2) x polling antigo (telegram_bot.py) - Fase 7, faixa C1 ----
# A API do Telegram nao deixa getUpdates (polling) e webhook no MESMO bot (409).
# modo_telegram() decide quem roda; app.iniciar_telegram so sobe o polling e
# rotas/n2_telegram.py so processa o webhook quando o modo deixa. Ver
# docs/telegram-captura.md, secao 7.
MODOS_TELEGRAM = ("auto", "polling", "webhook", "ambos", "desligado")


def token_captura() -> str:
    """Token do bot de captura (webhook): TELEGRAM_BOT_TOKEN_CAPTURA se
    existir (bot separado, recomendado), senao o mesmo TELEGRAM_BOT_TOKEN do
    bot antigo."""
    return os.environ.get("TELEGRAM_BOT_TOKEN_CAPTURA") or os.environ.get("TELEGRAM_BOT_TOKEN", "")


def modo_telegram(env=None) -> dict:
    """{"polling": bool, "webhook": bool, "bots_separados": bool, "modo": str,
    "motivo": str}. Flag TELEGRAM_MODO (auto|polling|webhook|ambos|desligado,
    padrao auto). Com bots separados (TELEGRAM_BOT_TOKEN_CAPTURA diferente de
    TELEGRAM_BOT_TOKEN) os dois podem rodar juntos. Com um bot so, NUNCA os
    dois: `auto` escolhe webhook se TELEGRAM_WEBHOOK_SECRET estiver
    configurado (o Alex ja fez o setWebhook - polling daria 409), senao
    polling; `ambos` com um bot so vira webhook (e avisa no motivo)."""
    env = os.environ if env is None else env
    modo = (env.get("TELEGRAM_MODO") or "auto").strip().lower()
    if modo not in MODOS_TELEGRAM:
        modo = "auto"
    token_antigo = env.get("TELEGRAM_BOT_TOKEN") or ""
    token_cap = env.get("TELEGRAM_BOT_TOKEN_CAPTURA") or ""
    separados = bool(token_cap) and token_cap != token_antigo

    if modo == "desligado":
        polling = webhook = False
        motivo = "TELEGRAM_MODO=desligado"
    elif separados:
        polling = modo in ("auto", "polling", "ambos")
        webhook = modo in ("auto", "webhook", "ambos")
        motivo = "bots separados: cada um no seu modo"
    elif modo == "auto":
        webhook = bool(env.get("TELEGRAM_WEBHOOK_SECRET"))
        polling = not webhook
        motivo = "auto: webhook configurado" if webhook else "auto: sem webhook, polling antigo"
    elif modo == "ambos":
        polling, webhook = False, True
        motivo = "ambos com um bot so da 409 no Telegram - ficou so o webhook"
    else:
        polling, webhook = modo == "polling", modo == "webhook"
        motivo = f"TELEGRAM_MODO={modo}"
    return {"polling": polling, "webhook": webhook, "bots_separados": separados, "modo": modo, "motivo": motivo}


def configurado() -> bool:
    return bool(token_captura()) and bool(os.environ.get("TELEGRAM_CHAT_ID_PERMITIDO"))


def _url_bot(metodo: str) -> str:
    return f"https://api.telegram.org/bot{token_captura()}/{metodo}"


def _url_arquivo(file_path: str) -> str:
    return f"https://api.telegram.org/file/bot{token_captura()}/{file_path}"


def extrair_chat_id(update: dict) -> str | None:
    """chat_id de um update com 'message' (texto, foto, voz, documento...) -
    None se o update nao tiver mensagem (callback_query, membro entrando no
    grupo etc - fora do escopo desta faixa, ignorado por quem chama)."""
    mensagem = update.get("message")
    if not isinstance(mensagem, dict):
        return None
    chat = mensagem.get("chat")
    if not isinstance(chat, dict) or chat.get("id") is None:
        return None
    return str(chat["id"])


def enviar_mensagem(texto: str) -> bool:
    """Manda uma mensagem pro chat permitido (TELEGRAM_CHAT_ID_PERMITIDO) -
    mesmo padrao de telegram_bot.enviar_mensagem (nunca levanta excecao,
    corta com seguranca no limite de caracteres, devolve False em qualquer
    falha de rede/config)."""
    if not configurado():
        return False
    payload = {"chat_id": os.environ["TELEGRAM_CHAT_ID_PERMITIDO"], "text": texto[:LIMITE_TEXTO_TELEGRAM]}
    try:
        resposta = requests.post(_url_bot("sendMessage"), json=payload, timeout=TIMEOUT_TELEGRAM)
        return resposta.status_code == 200
    except requests.RequestException:
        return False


def baixar_arquivo(file_id: str) -> tuple[bytes, str] | None:
    """getFile + download (2 chamadas HTTP, exigidas pela Bot API do
    Telegram: getFile devolve o `file_path`, o download em si e' noutro
    dominio/URL). Devolve (bytes, mime) ou None se qualquer passo falhar
    (file_id invalido, arquivo grande demais, Telegram fora do ar) - quem
    chama decide a mensagem de erro pro Alex."""
    try:
        resposta = requests.get(_url_bot("getFile"), params={"file_id": file_id}, timeout=TIMEOUT_TELEGRAM)
        resposta.raise_for_status()
        corpo = resposta.json()
        if not corpo.get("ok"):
            return None
        info = corpo.get("result") or {}
        file_path = info.get("file_path")
        tamanho = info.get("file_size") or 0
        if not file_path or tamanho > TAMANHO_MAX_ARQUIVO:
            return None
        download = requests.get(_url_arquivo(file_path), timeout=TIMEOUT_DOWNLOAD)
        download.raise_for_status()
        if not download.content:
            return None
        mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        return download.content, mime
    except (requests.RequestException, ValueError, KeyError):
        return None


def transcrever(audio_bytes: bytes, mime: str, *, duracao_segundos: int = 0,
                fala_desde: float | None = None, fala_ate: float | None = None,
                trechos_voz: list | None = None) -> str:
    """Transcreve audio pt-BR via Groq (whisper-large-v3-turbo - escolha
    documentada em docs/telegram-captura.md). Levanta ErroCaptura em
    qualquer situacao que impeca a transcricao (teto de IA estourado,
    GROQ_API_KEY ausente, chamada falhou, resultado vazio) - quem chama
    (processar_atualizacao) traduz isso numa mensagem curta pro Telegram.

    So esta funcao (o valor PADRAO injetado em processar_atualizacao) faz
    chamada de rede de verdade - os testes sempre passam um dublê no lugar
    dela (ver tests/test_fase7_n2_captura.py)."""
    import ia.medicao
    import ia.teto

    if not ia.teto.teto_permite(FUNCAO_TRANSCRICAO):
        raise ErroCaptura(ia.teto.TETO_IA_MSG)
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ErroCaptura("transcrição de áudio não configurada (falta GROQ_API_KEY no .env)")

    inicio = time.perf_counter()
    extensao = mimetypes.guess_extension(mime) or ".ogg"
    try:
        resposta = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (f"audio{extensao}", audio_bytes, mime)},
            data={"model": MODELO_TRANSCRICAO, "language": "pt", "response_format": "verbose_json",
                  "temperature": "0", "prompt": PROMPT_TRANSCRICAO},
            timeout=TIMEOUT_TELEGRAM * 4,
        )
        resposta.raise_for_status()
        corpo = resposta.json()
        texto = texto_dos_trechos(corpo if isinstance(corpo, dict) else {}, fala_desde, fala_ate, trechos_voz)
    except (requests.RequestException, ValueError) as exc:
        ia.medicao.registrar_uso(FUNCAO_TRANSCRICAO, PROVEDOR_TRANSCRICAO, MODELO_TRANSCRICAO, ok=False)
        raise ErroCaptura("não consegui transcrever o áudio agora - tenta de novo ou manda por texto") from exc

    latencia_ms = int(round((time.perf_counter() - inicio) * 1000))
    custo_usd = max(0, int(duracao_segundos or 0)) * PRECO_TRANSCRICAO_USD_POR_SEGUNDO
    ia.medicao.registrar_uso(
        FUNCAO_TRANSCRICAO,
        PROVEDOR_TRANSCRICAO,
        MODELO_TRANSCRICAO,
        custo_usd=custo_usd,
        latencia_ms=latencia_ms,
        ok=True,
    )
    if not texto:
        raise ErroCaptura("não entendi nada no áudio - tenta falar de novo ou manda por texto")
    return texto


def _eh_link(texto: str) -> str | None:
    """URL valida se `texto` (ja sem espaco nas pontas) for SO um link
    http(s), sem mais nada - None caso contrario (mensagem normal de
    captura, mesmo que cite uma URL no meio da frase). Reusa a MESMA
    validacao de SSRF do fluxo /api/salvos que ja existe (leitura.py) -
    nao duplica a checagem de host publico/redirecionamento aqui."""
    if not texto or " " in texto or "\n" in texto or "\t" in texto:
        return None
    try:
        return leitura.validar_url(texto)
    except leitura.LinkInvalido:
        return None


def _resumo_captura(corpo: dict, url_app: str) -> str:
    """Traduz o corpo devolvido por `executar_captura` (mesmo contrato de
    `app._executar_captura`/docs/CARDS.md: `resumo_texto` sempre presente,
    `duvida` quando a IA precisa de esclarecimento, `titulo` no sucesso) num
    texto curto pro Telegram - que nao renderiza cards."""
    rodape = f"\n{url_app}" if url_app else ""
    if corpo.get("duvida"):
        return f"❓ {corpo['duvida']}{rodape}"
    resumo = corpo.get("resumo_texto") or "Capturado."
    titulo = corpo.get("titulo")
    linha_titulo = f'\n"{titulo}"' if titulo else ""
    return f"✅ {resumo}{linha_titulo}{rodape}"


def _processar_texto(texto, *, conn, executar_captura, salvar_link, enviar_mensagem, url_app):
    url = _eh_link(texto)
    if url:
        resultado = salvar_link(conn, url)
        if "erro" in resultado:
            enviar_mensagem(f"Não consegui salvar o link: {resultado['erro']}")
            return
        resumo = resultado.get("resumo") or resultado.get("aviso") or "Link salvo."
        titulo = resultado.get("titulo") or url
        rodape = f"\n{url_app}" if url_app else ""
        enviar_mensagem(f'🔖 Salvo pra ver depois: "{titulo}"\n{resumo}{rodape}')
        return
    corpo, _status = executar_captura(texto, "")
    enviar_mensagem(_resumo_captura(corpo, url_app))


def _processar_audio(voice, *, executar_captura, enviar_mensagem, baixar_arquivo, transcrever, url_app):
    file_id = voice.get("file_id") if isinstance(voice, dict) else None
    if not file_id:
        enviar_mensagem("Não recebi o áudio direito - tenta de novo.")
        return
    baixado = baixar_arquivo(file_id)
    if not baixado:
        enviar_mensagem("Não consegui baixar o áudio - tenta de novo.")
        return
    audio_bytes, mime_download = baixado
    mime = voice.get("mime_type") or mime_download
    duracao = voice.get("duration") or 0
    try:
        texto = transcrever(audio_bytes, mime, duracao_segundos=duracao)
    except ErroCaptura as exc:
        enviar_mensagem(f"Não consegui processar o áudio: {exc}")
        return
    corpo, _status = executar_captura(texto, "")
    enviar_mensagem(f'🎙️ Entendi: "{texto}"\n\n' + _resumo_captura(corpo, url_app))


def _processar_foto(fotos, *, executar_captura, enviar_mensagem, baixar_arquivo, extrair_nota_fiscal, url_app):
    if not fotos:
        enviar_mensagem("Não recebi a foto direito - tenta de novo.")
        return
    # Telegram manda varias resolucoes da mesma foto em 'photo' (PhotoSize) -
    # a maior tem mais detalhe pra ler o valor/estabelecimento.
    maior = max(fotos, key=lambda f: f.get("file_size") or 0)
    file_id = maior.get("file_id")
    if not file_id:
        enviar_mensagem("Não recebi a foto direito - tenta de novo.")
        return
    baixado = baixar_arquivo(file_id)
    if not baixado:
        enviar_mensagem("Não consegui baixar a foto - tenta de novo.")
        return
    imagem_bytes, _mime = baixado
    # O array 'photo' do Telegram e' sempre JPEG (o proprio Telegram
    # reprocessa a foto original nesse formato) - diferente de 'document',
    # fora do escopo desta faixa.
    dados, erro = extrair_nota_fiscal(imagem_bytes, "image/jpeg")
    if erro:
        enviar_mensagem(f"Não consegui ler a nota fiscal: {erro}")
        return
    valor = dados.get("valor") if dados else None
    if not isinstance(valor, (int, float)) or isinstance(valor, bool) or valor <= 0:
        enviar_mensagem("Não consegui ler um valor claro na foto - manda o gasto por texto mesmo.")
        return
    estabelecimento = dados.get("estabelecimento")
    texto = f"Gastei R$ {valor} em {estabelecimento}" if estabelecimento else f"Gastei R$ {valor}"
    corpo, _status = executar_captura(texto, "")
    rodape_desfazer = f"\n(pra desfazer, abre o app: {url_app})" if url_app else "\n(pra desfazer, abre o app)"
    enviar_mensagem(_resumo_captura(corpo, url_app) + rodape_desfazer)


def processar_atualizacao(
    update: dict,
    *,
    conn,
    executar_captura,
    salvar_link,
    extrair_nota_fiscal,
    enviar_mensagem=enviar_mensagem,
    baixar_arquivo=baixar_arquivo,
    transcrever=transcrever,
    url_app: str = "",
) -> None:
    """Processa UM update ja validado por quem chama (secret do webhook,
    chat_id permitido, update_id novo - tudo isso e' responsabilidade de
    `rotas/n2_telegram.py`, que so chama esta funcao quando o update e' pra
    processar de verdade). Sempre manda uma resposta pro Telegram, mesmo em
    erro - nunca deixa o Alex sem retorno depois de mandar algo.

    Parametros injetados (dublês nos testes, pecas de verdade na rota):
    - `conn`: conexao de banco (pra `salvar_link`, que precisa gravar).
    - `executar_captura(texto, clarificacao) -> (corpo: dict, status: int)`:
      mesmo contrato de `app._executar_captura`, so devolvendo o corpo ja
      decodificado (nao um Response do Flask) - fonte unica da classificacao
      de captura, nunca reimplementada aqui.
    - `salvar_link(conn, url) -> dict`: mesmo contrato de `app._salvar_link`.
    - `extrair_nota_fiscal(image_bytes, media_type) -> (dados: dict | None, erro: str | None)`:
      envolve `claude_client.extrair_nota_fiscal_foto` com o MESMO controle
      de teto/`_call_claude`/log de uso que a rota /api/extrair-nota-fiscal
      ja usa (ver rotas/n2_telegram.py) - nao duplica esse controle aqui.
    - `enviar_mensagem`/`baixar_arquivo`/`transcrever`: clientes de rede,
      com um padrao real como default (nunca chamado nos testes, que sempre
      passam um dublê)."""
    mensagem = update.get("message")
    if not isinstance(mensagem, dict):
        return

    texto = mensagem.get("text")
    voice = mensagem.get("voice")
    fotos = mensagem.get("photo")

    if isinstance(texto, str) and texto.strip():
        _processar_texto(
            texto.strip(),
            conn=conn,
            executar_captura=executar_captura,
            salvar_link=salvar_link,
            enviar_mensagem=enviar_mensagem,
            url_app=url_app,
        )
    elif isinstance(voice, dict):
        _processar_audio(
            voice,
            executar_captura=executar_captura,
            enviar_mensagem=enviar_mensagem,
            baixar_arquivo=baixar_arquivo,
            transcrever=transcrever,
            url_app=url_app,
        )
    elif isinstance(fotos, list) and fotos:
        _processar_foto(
            fotos,
            executar_captura=executar_captura,
            enviar_mensagem=enviar_mensagem,
            baixar_arquivo=baixar_arquivo,
            extrair_nota_fiscal=extrair_nota_fiscal,
            url_app=url_app,
        )
    else:
        enviar_mensagem("So entendo texto, áudio (mensagem de voz) ou foto de nota fiscal por aqui, por enquanto.")
