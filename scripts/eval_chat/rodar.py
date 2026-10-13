#!/usr/bin/env python3
"""Prova de qualidade do chat (eval): roda mensagens realistas do Alex pelo pipeline REAL
(`app._processar_mensagem_chat`) e confere, de forma deterministica, se o chat chamou as
ferramentas certas, respondeu com o tamanho certo e sem cara de robo.

SEGURANCA (o que este script garante):
- o banco real NUNCA e escrito: ele e lido uma vez (`sqlite3.backup()` a partir de uma conexao
  somente-leitura) para um arquivo temporario, e o pipeline roda contra uma COPIA desse snapshot
  (restaurada do zero antes de cada caso, entao um caso nao contamina o outro);
- efeitos externos desligados por patch: agenda iCloud/CalDAV, Uber, push, Telegram e qualquer
  requisicao HTTP que escreva (POST/PUT/PATCH/DELETE) que nao seja da API da Anthropic. O que
  seria enviado fica registrado em `bloqueios` no JSON de resultados;
- sem a flag `--rodar` NADA chama a IA e NADA abre o banco: so valida o `casos.json` e imprime a
  estimativa de custo. Com `--rodar` as chamadas sao REAIS (centavos de dolar, ver a estimativa).

Uso (da raiz do repositorio):
    python scripts/eval_chat/rodar.py                      # valida casos.json + estimativa de custo
    python scripts/eval_chat/rodar.py --rodar              # roda tudo (gasta API de verdade)
    python scripts/eval_chat/rodar.py --rodar --juiz       # + nota 1-5 de um juiz Haiku por caso
    python scripts/eval_chat/rodar.py --rodar --ids gasto-simples,desabafo-cansaco

Resultados: tabela no terminal + scripts/eval_chat/resultados/AAAA-MM-DD-HHMM.json (gitignored)."""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

CASOS_PADRAO = Path(__file__).with_name("casos.json")
PASTA_RESULTADOS = Path(__file__).with_name("resultados")
CONFIG_CHAT = RAIZ / "ia" / "config.d" / "chat.json"
JUIZ_MODELO = "claude-haiku-5-5"
MODELOS_ESPERADOS = {"haiku", "sonnet", "local", "qualquer"}
TETO_PADRAO_USD = 1.0  # trava de seguranca da rodada: para de chamar a IA se passar disso
_RE_TABELA = re.compile(r"^[a-z_][a-z0-9_]*$")
# emoji de verdade (figuras, simbolos, dingbats), sem contar o check mark de formatacao
_RE_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-⛿✀-✒✕-➿⭐⬆]")

# premissas da estimativa de custo (so uma ordem de grandeza - o custo real vem da rodada)
EST_TOKENS_VARIAVEIS_IN = 4000  # "Contexto de agora" + memorias + mensagem, por rodada
EST_SAIDA_REGISTRO = 100
EST_SAIDA_DUMP = 220
EST_SAIDA_CONVERSA = 650
EST_SAIDA_POR_FERRAMENTA = 90  # JSON do tool_use
EST_CHARS_POR_TOKEN = 3.2


# --------------------------------------------------------------------------- utilidades
def _norm(texto) -> str:
    """Minusculo, sem acento, espacos colapsados - as frases proibidas e os regex de `contem`
    sao comparados contra isto (entao 'Ótima pergunta' pega 'otima pergunta' tambem)."""
    if not isinstance(texto, str):
        return ""
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sem_acento).strip()


def contar_emojis(texto: str) -> int:
    return len(_RE_EMOJI.findall(texto or ""))


def carregar_casos(caminho: Path | str = CASOS_PADRAO) -> dict:
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def nomes_das_ferramentas() -> set[str]:
    """Nomes reais das tools do chat (ia/funcoes/chat.py::CHAT_TOOLS). Importar o modulo nao toca
    banco nem rede; a chave de API so e exigida na importacao do cliente, entao no modo de
    validacao (sem chamada) um valor de enchimento basta."""
    os.environ.setdefault("ANTHROPIC_API_KEY", "validacao-sem-chamada")
    from ia.funcoes import chat as chat_mod

    return {t["name"] for t in chat_mod.CHAT_TOOLS}


# --------------------------------------------------------------------------- validacao
def validar_casos(dados: dict, nomes_tools: set[str] | None = None, checar_roteador: bool = True) -> tuple[list[str], list[str]]:
    """(erros, avisos). Erro = o arquivo esta quebrado (formato, tool que nao existe, regex
    invalido). Aviso = o caso e valido, mas o roteador do chat discorda do `modelo_esperado`."""
    erros: list[str] = []
    avisos: list[str] = []
    if not isinstance(dados, dict):
        return ["raiz do casos.json precisa ser um objeto"], avisos
    glob = dados.get("global")
    if not isinstance(glob, dict):
        erros.append("falta o bloco 'global'")
        glob = {}
    frases = glob.get("frases_proibidas")
    if not (isinstance(frases, list) and frases and all(isinstance(f, str) and f.strip() for f in frases)):
        erros.append("global.frases_proibidas precisa ser uma lista nao vazia de textos")
    if not (isinstance(glob.get("max_emojis"), int) and glob["max_emojis"] >= 0):
        erros.append("global.max_emojis precisa ser um inteiro >= 0")

    casos = dados.get("casos")
    if not (isinstance(casos, list) and casos):
        return erros + ["'casos' precisa ser uma lista nao vazia"], avisos

    ids_vistos: set[str] = set()
    for i, caso in enumerate(casos, 1):
        if not isinstance(caso, dict):
            erros.append(f"caso #{i}: precisa ser um objeto")
            continue
        cid = caso.get("id")
        rotulo = f"caso '{cid}'" if isinstance(cid, str) and cid else f"caso #{i}"
        if not (isinstance(cid, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", cid)):
            erros.append(f"{rotulo}: 'id' precisa ser minusculo-com-hifens")
        elif cid in ids_vistos:
            erros.append(f"{rotulo}: id repetido")
        else:
            ids_vistos.add(cid)
        if not (isinstance(caso.get("mensagem"), str) and caso["mensagem"].strip()):
            erros.append(f"{rotulo}: 'mensagem' vazia")

        listas = {
            "ferramentas_obrigatorias": caso.get("ferramentas_obrigatorias", []),
            "ferramentas_proibidas": caso.get("ferramentas_proibidas", []),
        }
        grupos = caso.get("ferramentas_alguma_de", [])
        for nome_campo, lista in listas.items():
            if not (isinstance(lista, list) and all(isinstance(t, str) for t in lista)):
                erros.append(f"{rotulo}: '{nome_campo}' precisa ser lista de textos")
                continue
            if nomes_tools is not None:
                for t in lista:
                    if t not in nomes_tools:
                        erros.append(f"{rotulo}: ferramenta '{t}' em {nome_campo} nao existe no chat")
        if not (isinstance(grupos, list) and all(isinstance(g, list) and g and all(isinstance(t, str) for t in g) for g in grupos)):
            erros.append(f"{rotulo}: 'ferramentas_alguma_de' precisa ser lista de listas (nao vazias) de textos")
        elif nomes_tools is not None:
            for g in grupos:
                for t in g:
                    if t not in nomes_tools:
                        erros.append(f"{rotulo}: ferramenta '{t}' em ferramentas_alguma_de nao existe no chat")
        if isinstance(listas["ferramentas_obrigatorias"], list) and isinstance(listas["ferramentas_proibidas"], list):
            conflito = set(listas["ferramentas_obrigatorias"]) & set(listas["ferramentas_proibidas"])
            if conflito:
                erros.append(f"{rotulo}: ferramenta ao mesmo tempo obrigatoria e proibida: {sorted(conflito)}")

        tam = caso.get("resposta")
        if not (isinstance(tam, dict) and isinstance(tam.get("min_chars"), int) and isinstance(tam.get("max_chars"), int)
                and 0 <= tam["min_chars"] <= tam["max_chars"]):
            erros.append(f"{rotulo}: 'resposta' precisa de min_chars <= max_chars (inteiros)")

        for campo in ("contem", "nao_contem"):
            padroes = caso.get(campo, [])
            if not (isinstance(padroes, list) and all(isinstance(p, str) for p in padroes)):
                erros.append(f"{rotulo}: '{campo}' precisa ser lista de regex")
                continue
            for p in padroes:
                try:
                    re.compile(p)
                except re.error as exc:
                    erros.append(f"{rotulo}: regex invalido em {campo} ({p!r}): {exc}")

        cria = caso.get("cria", {})
        if not (isinstance(cria, dict) and all(isinstance(t, str) and _RE_TABELA.match(t) and isinstance(n, int) and n >= 1
                                                for t, n in cria.items())):
            erros.append(f"{rotulo}: 'cria' precisa ser {{tabela: n >= 1}} com nomes de tabela simples")

        esperado = caso.get("modelo_esperado", "qualquer")
        if esperado not in MODELOS_ESPERADOS:
            erros.append(f"{rotulo}: modelo_esperado precisa ser um de {sorted(MODELOS_ESPERADOS)}")
        elif checar_roteador and isinstance(caso.get("mensagem"), str):
            aviso = _checar_roteador(rotulo, caso["mensagem"], esperado)
            if aviso:
                avisos.append(aviso)
    return erros, avisos


def _checar_roteador(rotulo: str, mensagem: str, esperado: str) -> str | None:
    """Confere de graca (sem IA) se o roteador do chat manda a mensagem pro modelo que o caso
    espera. Nunca levanta excecao: sem o modulo, simplesmente nao avisa."""
    try:
        from ia import roteador_chat

        conversa = roteador_chat.e_conversa(mensagem)
    except Exception:  # noqa: BLE001
        return None
    if esperado == "sonnet" and not conversa:
        return f"{rotulo}: esperava Sonnet, mas ia.roteador_chat.e_conversa diz que NAO e conversa (vai pro Haiku)"
    if esperado == "haiku" and conversa:
        return f"{rotulo}: esperava Haiku, mas ia.roteador_chat.e_conversa diz que e conversa (vai pro Sonnet)"
    return None


# --------------------------------------------------------------------------- checagens
def avaliar_resposta(caso: dict, glob: dict, resposta: str | None, acoes: list[str], erro: str | None,
                     deltas: dict[str, int] | None = None, modelos_usados: list[str] | None = None) -> list[str]:
    """Aplica as checagens deterministicas de um caso. Devolve a lista de falhas (vazia = passou)."""
    if erro:
        return [f"o pipeline devolveu erro: {erro}"]
    falhas: list[str] = []
    texto = (resposta or "").strip()
    chamadas = set(acoes or [])

    for t in caso.get("ferramentas_obrigatorias", []):
        if t not in chamadas:
            falhas.append(f"nao chamou a ferramenta obrigatoria '{t}'")
    for grupo in caso.get("ferramentas_alguma_de", []):
        if not (set(grupo) & chamadas):
            falhas.append(f"nao chamou nenhuma de {grupo}")
    for t in caso.get("ferramentas_proibidas", []):
        if t in chamadas:
            falhas.append(f"chamou a ferramenta proibida '{t}'")

    faixa = caso["resposta"]
    if len(texto) < faixa["min_chars"]:
        falhas.append(f"resposta curta demais ({len(texto)} < {faixa['min_chars']} caracteres)")
    if len(texto) > faixa["max_chars"]:
        falhas.append(f"resposta longa demais ({len(texto)} > {faixa['max_chars']} caracteres)")

    norm = _norm(texto)
    for frase in list(glob.get("frases_proibidas", [])) + list(caso.get("frases_proibidas_extra", [])):
        if _norm(frase) and _norm(frase) in norm:
            falhas.append(f"frase com cara de robo: {frase!r}")
    emojis = contar_emojis(texto)
    if emojis > glob.get("max_emojis", 1):
        falhas.append(f"emoji demais ({emojis} > {glob.get('max_emojis', 1)})")

    for padrao in caso.get("contem", []):
        if not re.search(padrao, norm):
            falhas.append(f"faltou na resposta: /{padrao}/")
    for padrao in caso.get("nao_contem", []):
        if re.search(padrao, norm):
            falhas.append(f"nao devia aparecer na resposta: /{padrao}/")

    for tabela, minimo in (caso.get("cria") or {}).items():
        if (deltas or {}).get(tabela, 0) < minimo:
            falhas.append(f"esperava >= {minimo} linha(s) nova(s) em '{tabela}' (veio {(deltas or {}).get(tabela, 0)})")

    esperado = caso.get("modelo_esperado", "qualquer")
    if esperado != "qualquer" and modelos_usados is not None:
        if esperado == "local":
            if modelos_usados:
                falhas.append(f"devia resolver local (sem IA), mas chamou {sorted(set(modelos_usados))}")
        elif not modelos_usados:
            falhas.append(f"esperava o modelo {esperado}, mas resolveu local (sem chamar IA)")
        elif not all(esperado in m.lower() for m in modelos_usados):
            falhas.append(f"esperava o modelo {esperado}, usou {sorted(set(modelos_usados))}")
    return falhas


# --------------------------------------------------------------------------- estimativa de custo
def _modelos_do_chat() -> tuple[str, str]:
    """(modelo de registro, modelo de conversa) lidos de ia/config.d/chat.json."""
    try:
        cfg = json.loads(CONFIG_CHAT.read_text(encoding="utf-8"))
        registro = cfg["modelo_atual"]["modelo"]
        conversa = (cfg.get("conversa") or {}).get("modelo") or registro
        return registro, conversa
    except Exception:  # noqa: BLE001
        return "claude-haiku-5-5", "claude-sonnet-5"


def tokens_fixos_do_chat() -> int:
    """Tokens (aprox.) do prefixo fixo cacheado: system prompt + definicao das tools."""
    os.environ.setdefault("ANTHROPIC_API_KEY", "validacao-sem-chamada")
    from ia.funcoes import chat as chat_mod

    chars = len(chat_mod.montar_sistema_chat([])) + len(json.dumps(chat_mod.CHAT_TOOLS, ensure_ascii=False))
    return int(chars / EST_CHARS_POR_TOKEN)


def estimar_custo(dados: dict, tokens_fixos: int, juiz: bool = False, precos: dict | None = None) -> dict:
    """Estimativa grosseira (ordem de grandeza, +/- 50%) de uma rodada completa em USD."""
    from ia import precos as precos_mod

    tabela = precos if precos is not None else precos_mod.carregar_precos()
    modelo_registro, modelo_conversa = _modelos_do_chat()
    cambio = tabela.get("cambio_usd_brl", 5.5)
    escreveu_cache: set[str] = set()
    por_caso = []
    total = 0.0
    for caso in dados["casos"]:
        esperado = caso.get("modelo_esperado", "qualquer")
        custo = 0.0
        modelo = None
        if esperado != "local":
            modelo = modelo_conversa if esperado == "sonnet" else modelo_registro
            n_ferr = len(caso.get("ferramentas_obrigatorias", [])) + len(caso.get("ferramentas_alguma_de", []))
            rodadas = 1 + (1 if n_ferr else 0)
            if esperado == "sonnet":
                saida_final = EST_SAIDA_CONVERSA
            elif caso.get("grupo") == "dump de audio":
                saida_final = EST_SAIDA_DUMP
            else:
                saida_final = EST_SAIDA_REGISTRO
            for r in range(rodadas):
                primeira_do_modelo = modelo not in escreveu_cache
                escreveu_cache.add(modelo)
                saida = (saida_final if r == rodadas - 1 else EST_SAIDA_POR_FERRAMENTA * max(n_ferr, 1))
                custo += precos_mod.custo_usd(
                    modelo,
                    tokens_in=EST_TOKENS_VARIAVEIS_IN + (500 * r),
                    tokens_out=saida,
                    tokens_cache_lido=0 if primeira_do_modelo else tokens_fixos,
                    tokens_cache_escrito=tokens_fixos if primeira_do_modelo else 0,
                    precos=tabela,
                )
        if juiz:
            custo += precos_mod.custo_usd(JUIZ_MODELO, tokens_in=900 + len(caso["mensagem"]) // 3, tokens_out=90, precos=tabela)
        por_caso.append({"id": caso["id"], "modelo": modelo or "local", "usd": round(custo, 5)})
        total += custo
    return {
        "total_usd": round(total, 4),
        "total_brl": round(total * cambio, 2),
        "faixa_usd": [round(total * 0.6, 4), round(total * 1.8, 4)],
        "casos": len(dados["casos"]),
        "juiz": juiz,
        "tokens_fixos": tokens_fixos,
        "por_caso": por_caso,
    }


# --------------------------------------------------------------------------- copia do banco
def preparar_copia(origem: Path, destino: Path) -> None:
    """Snapshot consistente do banco `origem` em `destino` via sqlite3.backup(), a partir de uma
    conexao SOMENTE-LEITURA (o banco de origem nunca e escrito, nem por engano)."""
    origem, destino = Path(origem), Path(destino)
    if not origem.is_file():
        raise FileNotFoundError(f"banco de origem nao encontrado: {origem}")
    if origem.resolve() == destino.resolve():
        raise ValueError("a copia nao pode ter o mesmo caminho do banco de origem")
    destino.parent.mkdir(parents=True, exist_ok=True)
    ro = sqlite3.connect(f"{origem.resolve().as_uri()}?mode=ro", uri=True)
    dest = sqlite3.connect(destino)
    try:
        ro.backup(dest)
    finally:
        dest.close()
        ro.close()


def restaurar_copia(pristino: Path, trabalho: Path) -> None:
    """Volta o banco de trabalho ao snapshot (chamado antes de cada caso)."""
    for sufixo in ("-wal", "-shm", "-journal"):
        Path(str(trabalho) + sufixo).unlink(missing_ok=True)
    shutil.copyfile(pristino, trabalho)


# --------------------------------------------------------------------------- efeitos externos
def _host_da_anthropic(url: str) -> bool:
    host = (urlparse(str(url)).hostname or "").lower()
    base = (urlparse(os.environ.get("ANTHROPIC_BASE_URL", "")).hostname or "").lower()
    return host.endswith("anthropic.com") or (bool(base) and host == base)


@contextlib.contextmanager
def efeitos_externos_desligados(bloqueios: list[dict]):
    """Desliga tudo que sairia do computador: CalDAV (iCloud), Uber, push, Telegram e qualquer
    requisicao HTTP que escreva (POST/PUT/PATCH/DELETE) fora da API da Anthropic. O que seria
    feito vai para `bloqueios` (alvo + resumo dos argumentos). Credenciais dessas integracoes e
    da construtora/Pluggy somem do ambiente enquanto durar o bloco."""
    from unittest import mock

    import caldav_client
    import push_client
    import requests
    import telegram_bot
    import uber_client

    def gravar(alvo: str, retorno):
        def falso(*args, **kwargs):
            bloqueios.append({"alvo": alvo, "args": repr(args)[:160]})
            return retorno(*args, **kwargs) if callable(retorno) else retorno
        return falso

    def evento_falso(titulo, inicio, fim, lembrar_min_antes=None):
        return {"uid": "eval-chat-fake", "titulo": titulo, "inicio": inicio.isoformat(), "fim": fim.isoformat()}

    original_request = requests.sessions.Session.request

    def request_seguro(self, method, url, *args, **kwargs):
        if str(method).upper() in ("GET", "HEAD", "OPTIONS") or _host_da_anthropic(url):
            return original_request(self, method, url, *args, **kwargs)
        bloqueios.append({"alvo": f"http {str(method).upper()}", "args": str(url)[:160]})
        resposta = requests.Response()
        resposta.status_code = 200
        resposta._content = b"{}"
        resposta.url = str(url)
        return resposta

    alvos = [
        (caldav_client, "configurado", lambda: True),  # liga pra a tool agendar_evento exercitar o caminho
        (caldav_client, "criar_evento", gravar("caldav.criar_evento", evento_falso)),
        (caldav_client, "apagar_evento", gravar("caldav.apagar_evento", True)),
        (caldav_client, "eventos_do_dia", lambda dia: []),
        (caldav_client, "horario_ocupado", lambda inicio, fim: False),
        (uber_client, "configurado", lambda: True),  # so grava um pedido agendado no banco da copia
        (uber_client, "pedir_corrida", gravar("uber.pedir_corrida", {})),
        (uber_client, "estimar_corrida", gravar("uber.estimar_corrida", {})),
        (uber_client, "renovar_token", gravar("uber.renovar_token", {})),
        (uber_client, "trocar_codigo_por_token", gravar("uber.trocar_codigo_por_token", {})),
        (push_client, "configurado", lambda: False),
        (push_client, "enviar", gravar("push.enviar", True)),
        (telegram_bot, "configurado", lambda: False),
        (telegram_bot, "enviar_mensagem", gravar("telegram.enviar_mensagem", True)),
        (telegram_bot, "enviar_documento", gravar("telegram.enviar_documento", True)),
        (telegram_bot, "responder_callback", gravar("telegram.responder_callback", True)),
        (telegram_bot, "remover_botoes", gravar("telegram.remover_botoes", True)),
        (requests.sessions.Session, "request", request_seguro),
    ]
    sem_credencial = ["ICLOUD_USERNAME", "ICLOUD_APP_PASSWORD", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                      "CONSTRUTORA_API_URL", "CONSTRUTORA_API_KEY", "PLUGGY_CLIENT_ID", "PLUGGY_CLIENT_SECRET",
                      "PLUGGY_ITEM_ID_NUBANK"]
    with contextlib.ExitStack() as pilha:
        pilha.enter_context(mock.patch.dict(os.environ, {}))  # restaura o ambiente inteiro ao sair
        for chave in sem_credencial:
            os.environ.pop(chave, None)
        for modulo, nome, novo in alvos:
            pilha.enter_context(mock.patch.object(modulo, nome, novo))
        yield


# --------------------------------------------------------------------------- juiz (opcional)
_PROMPT_JUIZ = (
    "Voce avalia respostas de um assistente pessoal brasileiro (chat de um app) ao usuario Alex. "
    "Responda SOMENTE um JSON: {\"humano\": 1-5, \"resolveu\": 1-5, \"motivo\": \"ate 15 palavras\"}. "
    "humano: 5 = parece uma pessoa de verdade falando (natural, direto, sem formula de atendente), "
    "1 = parece IA/robo (frases de efeito, introducao generica, tom de call center). "
    "resolveu: 5 = fez exatamente o que foi pedido, 1 = ignorou ou errou o pedido."
)


def julgar(client, mensagem: str, resposta: str, acoes: list[str]) -> dict | None:
    """Uma chamada ao Haiku pontuando a resposta. Devolve {humano, resolveu, motivo, custo_usd} ou None."""
    from ia import precos as precos_mod

    try:
        r = client.messages.create(
            model=JUIZ_MODELO,
            max_tokens=200,
            system=_PROMPT_JUIZ,
            messages=[{"role": "user", "content": (
                f"Mensagem do Alex: {mensagem}\n\nFerramentas que o assistente usou: {', '.join(acoes) or 'nenhuma'}\n\n"
                f"Resposta do assistente: {resposta}")}],
        )
        texto = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        achado = re.search(r"\{.*\}", texto, re.S)
        nota = json.loads(achado.group(0)) if achado else {}
        custo = precos_mod.custo_usd(JUIZ_MODELO, tokens_in=r.usage.input_tokens, tokens_out=r.usage.output_tokens)
        return {
            "humano": int(nota["humano"]), "resolveu": int(nota["resolveu"]),
            "motivo": str(nota.get("motivo", ""))[:200], "custo_usd": custo,
        }
    except Exception as exc:  # noqa: BLE001 - o juiz e opcional, nunca derruba a rodada
        print(f"  (juiz falhou: {type(exc).__name__}: {exc})", file=sys.stderr)
        return None


# --------------------------------------------------------------------------- execucao
def _contar(conn, tabelas) -> dict[str, int]:
    saida = {}
    for t in tabelas:
        if not _RE_TABELA.match(t):
            raise ValueError(f"nome de tabela invalido: {t!r}")
        try:
            saida[t] = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except sqlite3.OperationalError:
            saida[t] = 0  # tabela inexistente nesse banco: conta 0 (o 'cria' vai falhar com clareza)
    return saida


def _rodar_um_caso(app, db, caso: dict, glob: dict, trabalho: Path, pristino: Path, juiz_client, bloqueios: list[dict]) -> dict:
    restaurar_copia(pristino, trabalho)
    conn = db.get_db()
    inicio_bloqueios = len(bloqueios)
    try:
        conn.execute("DELETE FROM chat_mensagens")
        conn.execute("DELETE FROM chat_resumo_historico")
        conn.commit()
        tabelas = sorted(set(caso.get("cria", {}).keys()))
        antes = _contar(conn, tabelas)
        ultimo_uso = conn.execute("SELECT COALESCE(MAX(id), 0) FROM api_usage").fetchone()[0]
        detalhes: dict = {}
        t0 = time.monotonic()
        erro = None
        try:
            resposta, acoes, erro = app._processar_mensagem_chat(
                conn, caso["mensagem"], detalhes, origem_audio=bool(caso.get("origem_audio", False)))
        except Exception as exc:  # noqa: BLE001 - um caso quebrado nao para a rodada
            resposta, acoes, erro = None, [], f"excecao {type(exc).__name__}: {exc}"
        ms = int((time.monotonic() - t0) * 1000)
        depois = _contar(conn, tabelas)
        deltas = {t: depois[t] - antes[t] for t in tabelas}
        usos = conn.execute(
            "SELECT model, input_tokens, output_tokens, cost_usd FROM api_usage WHERE id > ? ORDER BY id", (ultimo_uso,)
        ).fetchall()
    finally:
        conn.close()

    modelos = [u["model"] for u in usos]
    custo = sum(u["cost_usd"] or 0.0 for u in usos)
    falhas = avaliar_resposta(caso, glob, resposta, acoes, erro, deltas, modelos)
    nota = julgar(juiz_client, caso["mensagem"], resposta, acoes) if (juiz_client and resposta and not erro) else None
    via = "local" if not modelos else ("sonnet" if any("sonnet" in m for m in modelos) else "haiku" if any("haiku" in m for m in modelos) else modelos[0])
    return {
        "id": caso["id"], "grupo": caso.get("grupo"), "mensagem": caso["mensagem"], "ok": not falhas, "falhas": falhas,
        "resposta": resposta, "erro": erro, "acoes": acoes, "via": via, "modelos": modelos,
        "tokens_in": sum(u["input_tokens"] or 0 for u in usos), "tokens_out": sum(u["output_tokens"] or 0 for u in usos),
        "custo_usd": round(custo, 6), "ms": ms, "deltas": deltas,
        "cards": [c.get("type") for c in (detalhes.get("cards") or []) if isinstance(c, dict)],
        "bloqueios": bloqueios[inicio_bloqueios:], "juiz": nota,
    }


def executar(dados: dict, banco_origem: Path | str, *, juiz: bool = False, ids: list[str] | None = None,
             teto_usd: float = TETO_PADRAO_USD, pasta_resultados: Path | None = PASTA_RESULTADOS,
             imprimir=print) -> dict:
    """Roda os casos pelo pipeline real contra uma copia temporaria de `banco_origem`.
    Devolve o dicionario de resultados (e grava o JSON em `pasta_resultados`, se dada)."""
    import db

    glob = dados["global"]
    casos = [c for c in dados["casos"] if not ids or c["id"] in ids]
    if not casos:
        raise ValueError("nenhum caso selecionado (confira --ids)")

    bloqueios: list[dict] = []
    resultados: list[dict] = []
    db_path_antes = db.DB_PATH
    inicio = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="eval_chat_") as tmp:
        pristino, trabalho = Path(tmp) / "pristino.db", Path(tmp) / "painel.db"
        preparar_copia(Path(banco_origem), pristino)
        try:
            # DB_PATH aponta para a copia ANTES de importar o app (o import pode inicializar o banco)
            db.DB_PATH = pristino
            db.garantir_banco_nao_producao()
            db.init_db()  # migra o snapshot pro schema atual (so a copia)
            db.DB_PATH = trabalho
            db.garantir_banco_nao_producao()

            import app

            juiz_client = None
            if juiz:
                from ia.funcoes import chat as chat_mod

                juiz_client = chat_mod.client
            gasto = 0.0
            with efeitos_externos_desligados(bloqueios):
                for i, caso in enumerate(casos, 1):
                    if gasto >= teto_usd:
                        resultados.append({"id": caso["id"], "ok": False, "falhas": [f"nao rodou: teto da rodada (US$ {teto_usd:.2f}) atingido"],
                                           "via": "-", "acoes": [], "custo_usd": 0.0, "resposta": None, "juiz": None, "bloqueios": []})
                        continue
                    r = _rodar_um_caso(app, db, caso, glob, trabalho, pristino, juiz_client, bloqueios)
                    gasto += r["custo_usd"] + ((r["juiz"] or {}).get("custo_usd", 0.0))
                    resultados.append(r)
                    imprimir(f"[{i}/{len(casos)}] {'OK  ' if r['ok'] else 'FALHA'} {r['id']} ({r['via']}, US$ {r['custo_usd']:.4f})")
        finally:
            db.DB_PATH = db_path_antes

    custo_chat = sum(r["custo_usd"] for r in resultados)
    custo_juiz = sum((r.get("juiz") or {}).get("custo_usd", 0.0) for r in resultados)
    from ia import precos as precos_mod

    cambio = precos_mod.carregar_precos().get("cambio_usd_brl", 5.5)
    relatorio = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "banco_origem": str(banco_origem),
        "juiz": juiz,
        "totais": {
            "casos": len(resultados), "passaram": sum(1 for r in resultados if r["ok"]),
            "custo_chat_usd": round(custo_chat, 5), "custo_juiz_usd": round(custo_juiz, 5),
            "custo_total_usd": round(custo_chat + custo_juiz, 5), "custo_total_brl": round((custo_chat + custo_juiz) * cambio, 3),
            "segundos": round(time.monotonic() - inicio, 1),
            "bloqueios_externos": len(bloqueios),
        },
        "casos": resultados,
    }
    if pasta_resultados:
        pasta_resultados = Path(pasta_resultados)
        pasta_resultados.mkdir(parents=True, exist_ok=True)
        caminho = pasta_resultados / f"{datetime.now():%Y-%m-%d-%H%M}.json"
        caminho.write_text(json.dumps(relatorio, ensure_ascii=False, indent=1), encoding="utf-8")
        relatorio["arquivo"] = str(caminho)
    return relatorio


# --------------------------------------------------------------------------- saida
def imprimir_tabela(relatorio: dict, imprimir=print) -> None:
    com_juiz = relatorio.get("juiz")
    cab = f"{'caso':<32} {'via':<7} {'ok':<5} {'chars':>5} {'US$':>8}  ferramentas"
    if com_juiz:
        cab += "  [humano/resolveu]"
    imprimir("\n" + cab)
    imprimir("-" * len(cab))
    for r in relatorio["casos"]:
        chars = len((r.get("resposta") or "").strip())
        linha = f"{r['id'][:32]:<32} {r.get('via', '-'):<7} {'ok' if r['ok'] else 'FALHA':<5} {chars:>5} {r.get('custo_usd', 0.0):>8.4f}  {','.join(r.get('acoes') or []) or '-'}"
        if com_juiz and r.get("juiz"):
            linha += f"  [{r['juiz']['humano']}/{r['juiz']['resolveu']}]"
        imprimir(linha)
    falhos = [r for r in relatorio["casos"] if not r["ok"]]
    if falhos:
        imprimir("\nFalhas:")
        for r in falhos:
            for f in r["falhas"]:
                imprimir(f"  - {r['id']}: {f}")
    t = relatorio["totais"]
    imprimir(f"\nPassaram {t['passaram']}/{t['casos']}  |  custo total US$ {t['custo_total_usd']:.4f} (~R$ {t['custo_total_brl']:.2f})"
             f"  [chat {t['custo_chat_usd']:.4f} + juiz {t['custo_juiz_usd']:.4f}]  |  {t['segundos']}s"
             f"  |  efeitos externos bloqueados: {t['bloqueios_externos']}")
    if com_juiz:
        notas = [r["juiz"] for r in relatorio["casos"] if r.get("juiz")]
        if notas:
            imprimir(f"Juiz: parece gente {sum(n['humano'] for n in notas) / len(notas):.1f}/5  |  resolveu {sum(n['resolveu'] for n in notas) / len(notas):.1f}/5  ({len(notas)} notas)")
    if relatorio.get("arquivo"):
        imprimir(f"Resultados: {relatorio['arquivo']}")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Prova de qualidade do chat (so chama a IA com --rodar).")
    ap.add_argument("--rodar", action="store_true", help="roda de verdade (chamadas REAIS a API, custa dinheiro)")
    ap.add_argument("--juiz", action="store_true", help="com --rodar: um Haiku da nota 1-5 (parece gente / resolveu)")
    ap.add_argument("--casos", default=str(CASOS_PADRAO), help="caminho do casos.json")
    ap.add_argument("--banco", default=None, help="banco de origem do snapshot (padrao: o banco do painel)")
    ap.add_argument("--ids", default=None, help="ids separados por virgula (so esses casos)")
    ap.add_argument("--teto-usd", type=float, default=TETO_PADRAO_USD, help="para a rodada se o gasto passar disso")
    args = ap.parse_args(argv)

    if args.rodar:
        # ANTES de qualquer import do chat (ia.legado cria o cliente da Anthropic na importacao):
        # o app so le o .env fora de teste e a chave de enchimento da validacao nao pode virar a do cliente
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv())
        os.environ.setdefault("FLASK_SKIP_DOTENV", "1")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ERRO  falta ANTHROPIC_API_KEY (no .env ou no ambiente).")
            return 1

    dados = carregar_casos(args.casos)
    erros, avisos = validar_casos(dados, nomes_das_ferramentas())
    for a in avisos:
        print(f"AVISO {a}")
    if erros:
        for e in erros:
            print(f"ERRO  {e}")
        print(f"\ncasos.json invalido ({len(erros)} erro(s)).")
        return 1
    ids = [i.strip() for i in args.ids.split(",") if i.strip()] if args.ids else None
    if ids:
        desconhecidos = set(ids) - {c["id"] for c in dados["casos"]}
        if desconhecidos:
            print(f"ERRO  ids inexistentes: {sorted(desconhecidos)}")
            return 1
        dados = {**dados, "casos": [c for c in dados["casos"] if c["id"] in ids]}

    est = estimar_custo(dados, tokens_fixos_do_chat(), juiz=args.juiz)
    print(f"casos.json valido: {est['casos']} caso(s), {len(avisos)} aviso(s) do roteador.")
    print(f"Estimativa de UMA rodada{' com juiz' if args.juiz else ''}: ~US$ {est['total_usd']:.3f} (~R$ {est['total_brl']:.2f}), "
          f"provavel entre US$ {est['faixa_usd'][0]:.3f} e {est['faixa_usd'][1]:.3f}.")
    if not args.rodar:
        print("Modo validacao: nada foi chamado nem aberto. Use --rodar pra rodar de verdade.")
        return 0

    import db

    origem = Path(args.banco) if args.banco else db.DB_PATH
    print(f"\nSnapshot de {origem} -> copia temporaria (o banco real nao e escrito).")
    try:
        relatorio = executar(dados, origem, juiz=args.juiz, ids=ids, teto_usd=args.teto_usd)
    except FileNotFoundError as exc:
        print(f"ERRO  {exc}")
        return 1
    imprimir_tabela(relatorio)
    return 0 if relatorio["totais"]["passaram"] == relatorio["totais"]["casos"] else 2


if __name__ == "__main__":
    sys.exit(main())
