# ia/core.py — nucleo do sistema de IA hibrido (faixa A1).
#
# Ponto unico de entrada: chamar_ia(funcao, mensagens, ...). Cada "funcao" de IA do
# app (classify_capture, chat, extrair_nota_fiscal...) tem um arquivo de config em
# ia/config.d/<funcao>.json que diz qual provedor/modelo usar, qual o alvo da
# migracao, e a lista de fallback. Trocar de modelo = editar o JSON (o cache
# confere o mtime do arquivo, entao nao precisa reiniciar o app).
#
# Fluxo de chamar_ia:
#   1. le a config (_carregar_config, com cache)
#   2. consulta o teto mensal (ia.teto.teto_permite, se o modulo ja existir)
#   3. monta a lista de tentativas: [alvo se ativo, senao modelo_atual] + fallback
#      (entradas repetidas - mesmo provedor/modelo/esforco - sao puladas pra nao
#      pagar duas vezes pela mesma falha)
#   4. pra cada tentativa: chama o Adapter do provedor; excecao de rede/timeout
#      ganha 1 retry no mesmo modelo; se houver schema, o JSON da resposta e
#      validado; qualquer falha passa pra proxima tentativa
#   5. toda tentativa (inclusive retry e falha) e registrada via
#      ia.medicao.registrar_uso (se o modulo ja existir) - nunca com conteudo
#
# Os modulos ia.adapters.anthropic, ia.adapters.openai, ia.medicao e ia.teto sao
# de outras faixas (A2, A3, A4) e sao importados de forma tardia e tolerante: se
# ainda nao existirem, o nucleo continua funcionando (sem medicao/teto, e o
# provedor sem adapter vira uma tentativa que falha com erro claro).

import importlib
import json
import logging
import re
import socket
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from ia.contrato import Adapter, Resposta

log = logging.getLogger(__name__)

DIR_CONFIG = Path(__file__).resolve().parent / "config.d"

# Espera antes do retry de rede (segundos). Os testes zeram isto.
ESPERA_RETRY_S = 0.5

# provedor -> modulo do adapter (import tardio)
MODULOS_ADAPTER = {
    "anthropic": "ia.adapters.anthropic",
    "openai": "ia.adapters.openai",
    "gemini": "ia.adapters.gemini",
}

# Nomes de classe procurados no modulo do adapter, em ordem, se o modulo nao
# expuser uma funcao criar_adapter().
_NOMES_CLASSE_ADAPTER = {
    "anthropic": ("AdapterAnthropic", "AnthropicAdapter"),
    "openai": ("AdapterOpenAI", "AdapterOpenAi", "OpenAIAdapter"),
    "gemini": ("AdapterGemini",),
}

_NOME_FUNCAO_OK = re.compile(r"^[a-z0-9][a-z0-9_]*$")

_CACHE_CONFIG: dict = {}          # funcao -> (mtime_ns, config)
_CACHE_ADAPTERS: dict = {}        # provedor -> instancia de Adapter
_FABRICAS_REGISTRADAS: dict = {}  # provedor -> callable que devolve um Adapter
_TRAVA = threading.Lock()


class ConfigIAErro(ValueError):
    """Config de funcao de IA ausente ou mal formada (erro de programacao, nao
    de rede - por isso sobe como excecao em vez de virar Resposta(ok=False))."""


# --------------------------------------------------------------------------
# Excecoes de falha de chamada (Fase 7, faixa C1)
# --------------------------------------------------------------------------
# chamar_ia nunca levanta: devolve Resposta(ok=False, erro=...). As funcoes de
# ia/funcoes/* que precisam levantar usam excecao_de_resposta() pra escolher a
# excecao certa, e app._call_claude traduz cada uma na mensagem certa:
#   TetoEstourado    -> app.TETO_IA_MSG (402)
#   ErroProvedor     -> app.CLAUDE_ERROR_MSG (502) - rede, timeout, 5xx, adapter
#   RespostaInvalida -> app.CLAUDE_FORMAT_ERROR_MSG (502) - JSON/schema
# Todas herdam de ValueError de proposito: quem ja capturava ValueError
# (codigo e testes antigos das faixas A7/A8/A9) continua funcionando.

ERRO_TETO = "teto_ia_estourado"

# Prefixos que _chamar_uma_vez usa pra erro de FORMATO (a IA respondeu, mas
# fora do JSON/schema). Qualquer outro erro de tentativa e do provedor.
PREFIXOS_ERRO_FORMATO = (
    "resposta sem JSON",
    "JSON invalido na resposta",
    "JSON fora do schema",
    "JSON precisa ser objeto",
)


class FalhaChamadaIA(ValueError):
    """Base das falhas de chamada de IA (ver quadro acima). `erro` guarda o
    texto de Resposta.erro (nunca conteudo de prompt)."""

    def __init__(self, mensagem: str = "", erro: str = ""):
        super().__init__(mensagem or erro or "falha ao chamar IA")
        self.erro = erro or mensagem


class TetoEstourado(FalhaChamadaIA):
    """O teto mensal de IA (ia/teto.py) bloqueou a chamada."""


class ErroProvedor(FalhaChamadaIA):
    """Rede, timeout, erro do provedor ou do adapter em todas as tentativas."""


class RespostaInvalida(FalhaChamadaIA):
    """A IA respondeu, mas fora do formato pedido (JSON/schema) em todas as
    tentativas."""


def classificar_falha(erro: Optional[str]) -> str:
    """"teto" | "formato" | "provedor" a partir de Resposta.erro de
    chamar_ia. O erro agregado tem o formato "prov/modelo: erro | ..."; e
    "formato" so quando TODAS as tentativas falharam por formato."""
    texto = (erro or "").strip()
    if not texto:
        return "provedor"
    if texto == ERRO_TETO or texto.endswith(": " + ERRO_TETO):
        return "teto"
    partes = [p.strip() for p in texto.split(" | ") if p.strip()]

    def _e_formato(parte: str) -> bool:
        detalhe = parte.split(": ", 1)[1] if ": " in parte else parte
        return detalhe.startswith(PREFIXOS_ERRO_FORMATO) or parte.startswith(PREFIXOS_ERRO_FORMATO)

    if partes and all(_e_formato(p) for p in partes):
        return "formato"
    return "provedor"


def excecao_de_resposta(funcao: str, resp: Optional[Resposta]) -> FalhaChamadaIA:
    """Excecao certa pra uma Resposta(ok=False) de chamar_ia. A mensagem
    carrega "<funcao>: <erro>" (os testes antigos procuram o erro no str)."""
    erro = (resp.erro if resp is not None else None) or "falha na chamada de IA"
    tipo = classificar_falha(erro)
    classe = {"teto": TetoEstourado, "formato": RespostaInvalida}.get(tipo, ErroProvedor)
    return classe(f"{funcao}: {erro}", erro=erro)


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

def _validar_entrada_modelo(entrada, onde: str, arquivo: Path) -> dict:
    if not isinstance(entrada, dict):
        raise ConfigIAErro(f"{arquivo.name}: '{onde}' precisa ser um objeto "
                           f"{{\"provedor\": ..., \"modelo\": ...}}")
    for chave in ("provedor", "modelo"):
        valor = entrada.get(chave)
        if not isinstance(valor, str) or not valor.strip():
            raise ConfigIAErro(f"{arquivo.name}: '{onde}.{chave}' ausente ou vazio")
    esforco = entrada.get("esforco", "")
    if not isinstance(esforco, str):
        raise ConfigIAErro(f"{arquivo.name}: '{onde}.esforco' precisa ser texto")
    return {"provedor": entrada["provedor"].strip().lower(),
            "modelo": entrada["modelo"].strip(),
            "esforco": esforco.strip()}


def _normalizar_config(bruto, funcao: str, arquivo: Path) -> dict:
    if not isinstance(bruto, dict):
        raise ConfigIAErro(f"{arquivo.name}: o arquivo precisa ser um objeto JSON")
    nome = bruto.get("funcao", funcao)
    if nome != funcao:
        raise ConfigIAErro(f"{arquivo.name}: campo 'funcao' ({nome!r}) diferente do "
                           f"nome do arquivo ({funcao!r})")
    ativo = bruto.get("ativo", False)
    if not isinstance(ativo, bool):
        raise ConfigIAErro(f"{arquivo.name}: 'ativo' precisa ser true/false")

    modelo_atual = _validar_entrada_modelo(bruto.get("modelo_atual"), "modelo_atual", arquivo)
    alvo = None
    if bruto.get("alvo") is not None:
        alvo = _validar_entrada_modelo(bruto["alvo"], "alvo", arquivo)
    if ativo and alvo is None:
        raise ConfigIAErro(f"{arquivo.name}: 'ativo' e true mas nao ha 'alvo'")

    fallback_bruto = bruto.get("fallback", [])
    if not isinstance(fallback_bruto, list):
        raise ConfigIAErro(f"{arquivo.name}: 'fallback' precisa ser uma lista")
    fallback = [_validar_entrada_modelo(f, f"fallback[{i}]", arquivo)
                for i, f in enumerate(fallback_bruto)]

    max_tokens = bruto.get("max_tokens_saida", 1024)
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0:
        raise ConfigIAErro(f"{arquivo.name}: 'max_tokens_saida' precisa ser inteiro > 0")

    cache = bruto.get("cache", {"ativo": False})
    if not isinstance(cache, dict):
        raise ConfigIAErro(f"{arquivo.name}: 'cache' precisa ser um objeto")
    cache = {"ativo": bool(cache.get("ativo", False)), "ttl": cache.get("ttl", "5m"), **{
        k: v for k, v in cache.items() if k not in ("ativo", "ttl")}}

    modo = bruto.get("modo", "padrao")
    if not isinstance(modo, str) or not modo:
        raise ConfigIAErro(f"{arquivo.name}: 'modo' precisa ser texto")

    # opcional (so o chat usa): modelo pra conversa de verdade (pergunta,
    # conselho, estudo) com limite de saida proprio
    conversa = None
    if bruto.get("conversa") is not None:
        conversa = _validar_entrada_modelo(bruto["conversa"], "conversa", arquivo)
        limite = bruto["conversa"].get("max_tokens_saida", max_tokens)
        if isinstance(limite, bool) or not isinstance(limite, int) or limite <= 0:
            raise ConfigIAErro(f"{arquivo.name}: 'conversa.max_tokens_saida' precisa ser inteiro > 0")
        conversa["max_tokens_saida"] = limite

    return {
        "funcao": funcao,
        "ativo": ativo,
        "modelo_atual": modelo_atual,
        "alvo": alvo,
        "fallback": fallback,
        "max_tokens_saida": max_tokens,
        "cache": cache,
        "modo": modo,
        "conversa": conversa,
    }


def _carregar_config(funcao: str) -> dict:
    """Le ia/config.d/<funcao>.json, valida e guarda em cache. O cache e
    invalidado quando o mtime do arquivo muda (trocar o modelo = editar o JSON,
    sem reiniciar). Levanta ConfigIAErro com mensagem clara se o arquivo nao
    existir ou estiver mal formado."""
    if not isinstance(funcao, str) or not _NOME_FUNCAO_OK.match(funcao):
        raise ConfigIAErro(f"nome de funcao de IA invalido: {funcao!r} "
                           f"(use so minusculas, numeros e _)")
    arquivo = Path(DIR_CONFIG) / f"{funcao}.json"
    try:
        mtime = arquivo.stat().st_mtime_ns
    except FileNotFoundError:
        raise ConfigIAErro(
            f"funcao de IA {funcao!r} sem config: crie {arquivo} "
            f"(formato em ia/config.d/README.md)") from None

    with _TRAVA:
        em_cache = _CACHE_CONFIG.get(funcao)
        if em_cache and em_cache[0] == mtime:
            return em_cache[1]

    try:
        bruto = json.loads(arquivo.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigIAErro(f"{arquivo.name}: JSON invalido ({e})") from None
    config = _normalizar_config(bruto, funcao, arquivo)

    with _TRAVA:
        _CACHE_CONFIG[funcao] = (mtime, config)
    return config


def carregar_todas_configs() -> dict:
    """Junta todas as configs de ia/config.d/*.json em {funcao: config}. Util
    pro roteador/painel de custo listar o que existe. Arquivo invalido levanta
    ConfigIAErro (melhor quebrar no teste do que em producao)."""
    return {arq.stem: _carregar_config(arq.stem)
            for arq in sorted(Path(DIR_CONFIG).glob("*.json"))}


def limpar_cache() -> None:
    """Esquece configs e adapters em cache (usado pelos testes)."""
    with _TRAVA:
        _CACHE_CONFIG.clear()
        _CACHE_ADAPTERS.clear()


# --------------------------------------------------------------------------
# Adapters
# --------------------------------------------------------------------------

def registrar_adapter(provedor: str, fabrica: Optional[Callable[[], Adapter]]) -> None:
    """Registra (ou remove, com fabrica=None) uma fabrica de Adapter pra um
    provedor, com prioridade sobre o import de ia.adapters.<provedor>. Serve
    pros testes (dubles) e pra provedores novos sem mexer neste arquivo."""
    provedor = provedor.strip().lower()
    with _TRAVA:
        _CACHE_ADAPTERS.pop(provedor, None)
        if fabrica is None:
            _FABRICAS_REGISTRADAS.pop(provedor, None)
        else:
            _FABRICAS_REGISTRADAS[provedor] = fabrica


def _instanciar_do_modulo(provedor: str) -> Adapter:
    nome_modulo = MODULOS_ADAPTER.get(provedor)
    if not nome_modulo:
        raise LookupError(f"provedor de IA desconhecido: {provedor!r}")
    try:
        modulo = importlib.import_module(nome_modulo)
    except ImportError as e:
        raise LookupError(f"adapter do provedor {provedor!r} indisponivel "
                          f"({nome_modulo}: {e})") from None

    fabrica = getattr(modulo, "criar_adapter", None)
    if callable(fabrica):
        return fabrica()
    for nome in _NOMES_CLASSE_ADAPTER.get(provedor, ()):
        classe = getattr(modulo, nome, None)
        if isinstance(classe, type):
            return classe()
    # Ultimo recurso: a unica subclasse de Adapter definida no proprio modulo.
    candidatas = [obj for obj in vars(modulo).values()
                  if isinstance(obj, type) and issubclass(obj, Adapter)
                  and obj is not Adapter and obj.__module__ == modulo.__name__]
    if len(candidatas) == 1:
        return candidatas[0]()
    raise LookupError(f"{nome_modulo} nao expoe criar_adapter() nem uma classe "
                      f"Adapter reconhecivel")


def _obter_adapter(provedor: str) -> Adapter:
    with _TRAVA:
        if provedor in _CACHE_ADAPTERS:
            return _CACHE_ADAPTERS[provedor]
        fabrica = _FABRICAS_REGISTRADAS.get(provedor)
    adapter = fabrica() if fabrica else _instanciar_do_modulo(provedor)
    with _TRAVA:
        _CACHE_ADAPTERS.setdefault(provedor, adapter)
        return _CACHE_ADAPTERS[provedor]


# --------------------------------------------------------------------------
# Medicao e teto (modulos da faixa A4, import tardio)
# --------------------------------------------------------------------------

def _registrar_uso(funcao: str, resp: Resposta, provedor: str, modelo: str,
                   latencia_ms: int, ok: bool) -> None:
    try:
        from ia.medicao import registrar_uso
    except ImportError:
        return
    try:
        registrar_uso(
            funcao, provedor, modelo,
            tokens_in=resp.tokens_in if resp else 0,
            tokens_out=resp.tokens_out if resp else 0,
            tokens_cache_lido=resp.tokens_cache_lido if resp else 0,
            tokens_cache_escrito=resp.tokens_cache_escrito if resp else 0,
            custo_usd=resp.custo_usd if resp else 0.0,
            latencia_ms=latencia_ms,
            ok=ok,
        )
    except Exception:  # medicao nunca derruba a chamada
        log.exception("ia.core: falha ao registrar uso de %s", funcao)


def _teto_permite(funcao: str) -> bool:
    try:
        from ia.teto import teto_permite
    except ImportError:
        return True
    try:
        return bool(teto_permite(funcao))
    except Exception:
        # Erro no calculo do teto: na duvida, bloqueia (custo e o motivo de existir).
        log.exception("ia.core: falha ao consultar teto de %s", funcao)
        return False


# --------------------------------------------------------------------------
# Retry de rede
# --------------------------------------------------------------------------

_NOMES_ERRO_REDE = (
    "APIConnectionError", "APITimeoutError", "TimeoutException", "NetworkError",
    "ConnectError", "ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout",
    "RemoteProtocolError", "ReadError",
)


def _erro_de_rede(exc: BaseException) -> bool:
    """True pra excecao de rede/timeout (vale 1 retry). Um adapter pode forcar
    a decisao definindo exc.retentavel = True/False."""
    marcado = getattr(exc, "retentavel", None)
    if isinstance(marcado, bool):
        return marcado
    if isinstance(exc, (TimeoutError, ConnectionError, socket.timeout)):
        return True
    return any(c.__name__ in _NOMES_ERRO_REDE for c in type(exc).__mro__)


# --------------------------------------------------------------------------
# Validacao de JSON contra schema (subconjunto de JSON Schema, sem dependencia)
# --------------------------------------------------------------------------

_TIPOS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def validar_schema(valor, schema: dict, caminho: str = "$") -> Optional[str]:
    """Valida valor contra um subconjunto de JSON Schema: type (texto ou
    lista), properties, required, additionalProperties (bool), items, enum,
    const, minimum/maximum, minLength/maxLength, minItems/maxItems.
    Palavras-chave desconhecidas sao ignoradas. Devolve None se valido, senao
    a descricao do primeiro problema."""
    if not isinstance(schema, dict):
        return None
    tipo = schema.get("type")
    if tipo is not None:
        tipos = tipo if isinstance(tipo, list) else [tipo]
        if not any(_TIPOS.get(t, lambda v: True)(valor) for t in tipos):
            return f"{caminho}: esperado {'/'.join(map(str, tipos))}, veio {type(valor).__name__}"
    if "const" in schema and valor != schema["const"]:
        return f"{caminho}: esperado {schema['const']!r}"
    if "enum" in schema and valor not in schema["enum"]:
        return f"{caminho}: {valor!r} fora de {schema['enum']!r}"

    if _TIPOS["number"](valor):
        if "minimum" in schema and valor < schema["minimum"]:
            return f"{caminho}: {valor} < minimo {schema['minimum']}"
        if "maximum" in schema and valor > schema["maximum"]:
            return f"{caminho}: {valor} > maximo {schema['maximum']}"
    if isinstance(valor, str):
        if "minLength" in schema and len(valor) < schema["minLength"]:
            return f"{caminho}: texto menor que {schema['minLength']}"
        if "maxLength" in schema and len(valor) > schema["maxLength"]:
            return f"{caminho}: texto maior que {schema['maxLength']}"

    if isinstance(valor, dict):
        props = schema.get("properties") or {}
        for chave in schema.get("required") or []:
            if chave not in valor:
                return f"{caminho}: campo obrigatorio ausente {chave!r}"
        if schema.get("additionalProperties") is False:
            extras = [k for k in valor if k not in props]
            if extras:
                return f"{caminho}: campo nao permitido {extras[0]!r}"
        for chave, sub in props.items():
            if chave in valor:
                erro = validar_schema(valor[chave], sub, f"{caminho}.{chave}")
                if erro:
                    return erro

    if isinstance(valor, list):
        if "minItems" in schema and len(valor) < schema["minItems"]:
            return f"{caminho}: menos de {schema['minItems']} itens"
        if "maxItems" in schema and len(valor) > schema["maxItems"]:
            return f"{caminho}: mais de {schema['maxItems']} itens"
        itens = schema.get("items")
        if isinstance(itens, dict):
            for i, item in enumerate(valor):
                erro = validar_schema(item, itens, f"{caminho}[{i}]")
                if erro:
                    return erro
    return None


_CERCA_MARKDOWN = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


def _extrair_json(resp: Resposta):
    """Devolve (dados, erro). Usa resp.dados se o adapter ja parseou; senao
    json.loads do texto (tolerando cerca ```json ... ```)."""
    if resp.dados is not None:
        return resp.dados, None
    texto = resp.texto
    if not isinstance(texto, str) or not texto.strip():
        return None, "resposta sem JSON (texto vazio)"
    cerca = _CERCA_MARKDOWN.match(texto)
    if cerca:
        texto = cerca.group(1)
    try:
        return json.loads(texto), None
    except (json.JSONDecodeError, ValueError) as e:
        return None, f"JSON invalido na resposta ({e.__class__.__name__}: {e})"


# --------------------------------------------------------------------------
# Ponto unico de entrada
# --------------------------------------------------------------------------

def _montar_tentativas(config: dict) -> list:
    principal = config["alvo"] if config["ativo"] else config["modelo_atual"]
    tentativas, vistas = [], set()
    for entrada in [principal, *config["fallback"]]:
        chave = (entrada["provedor"], entrada["modelo"], entrada["esforco"])
        if chave in vistas:
            continue
        vistas.add(chave)
        tentativas.append(entrada)
    return tentativas


def _chamar_uma_vez(funcao, entrada, adapter, kwargs, schema):
    """Uma chamada ao adapter. Devolve (resp_ou_None, erro_ou_None,
    excecao_ou_None). Registra o uso."""
    inicio = time.monotonic()
    try:
        resp = adapter.chamar(modelo=entrada["modelo"], esforco=entrada["esforco"], **kwargs)
    except Exception as exc:  # noqa: BLE001 - qualquer falha do adapter vira tentativa falha
        latencia = int((time.monotonic() - inicio) * 1000)
        _registrar_uso(funcao, None, entrada["provedor"], entrada["modelo"], latencia, ok=False)
        return None, f"{exc.__class__.__name__}: {exc}", exc
    latencia = int((time.monotonic() - inicio) * 1000)

    if not isinstance(resp, Resposta):
        _registrar_uso(funcao, None, entrada["provedor"], entrada["modelo"], latencia, ok=False)
        return None, f"adapter devolveu {type(resp).__name__} em vez de Resposta", None

    if not resp.latencia_ms:
        resp.latencia_ms = latencia
    resp.provedor = resp.provedor or entrada["provedor"]
    resp.modelo = resp.modelo or entrada["modelo"]
    resp.esforco = resp.esforco or entrada["esforco"]

    erro = None if resp.ok else (resp.erro or "adapter devolveu ok=False sem erro")
    if erro is None and schema is not None:
        dados, erro = _extrair_json(resp)
        if erro is None:
            problema = validar_schema(dados, schema)
            if problema:
                erro = f"JSON fora do schema ({problema})"
            elif not isinstance(dados, dict):
                erro = f"JSON precisa ser objeto, veio {type(dados).__name__}"
            else:
                resp.dados = dados

    _registrar_uso(funcao, resp, resp.provedor, resp.modelo, resp.latencia_ms, ok=erro is None)
    return resp, erro, None


def chamar_ia(funcao: str, mensagens: list, *, sistema: str = "",
              contexto_fixo: str = "", schema: Optional[dict] = None,
              opcoes: Optional[dict] = None) -> Resposta:
    """Ponto unico de entrada da IA (ver contrato em ia/contrato.py).

    opcoes (todas opcionais) sobrescrevem a config so nesta chamada:
      max_tokens_saida (int), modo (str), cache (dict), ignorar_teto (bool -
      so pra chamadas que ja checaram o teto por conta propria).

    Config ausente/invalida levanta ConfigIAErro (erro de programacao). Falha
    de IA (rede, provedor, JSON invalido, teto) nunca levanta: volta
    Resposta(ok=False, erro=...)."""
    config = _carregar_config(funcao)
    opcoes = opcoes or {}

    if not opcoes.get("ignorar_teto") and not _teto_permite(funcao):
        principal = config["alvo"] if config["ativo"] else config["modelo_atual"]
        return Resposta(ok=False, provedor=principal["provedor"], modelo=principal["modelo"],
                        esforco=principal["esforco"], erro=ERRO_TETO)

    kwargs = {
        "sistema": sistema,
        "contexto_fixo": contexto_fixo,
        "mensagens": mensagens,
        "schema": schema,
        "max_tokens_saida": int(opcoes.get("max_tokens_saida", config["max_tokens_saida"])),
        "cache": dict(opcoes.get("cache", config["cache"])),
        "modo": opcoes.get("modo", config["modo"]),
    }

    erros = []
    ultima = None
    for indice, entrada in enumerate(_montar_tentativas(config)):
        rotulo = f"{entrada['provedor']}/{entrada['modelo']}"
        ultima = entrada
        try:
            adapter = _obter_adapter(entrada["provedor"])
        except Exception as exc:  # noqa: BLE001
            erros.append(f"{rotulo}: {exc}")
            continue

        resp, erro, exc = _chamar_uma_vez(funcao, entrada, adapter, kwargs, schema)
        if exc is not None and _erro_de_rede(exc):
            log.warning("ia.core: %s em %s, tentando de novo: %s", funcao, rotulo, erro)
            if ESPERA_RETRY_S:
                time.sleep(ESPERA_RETRY_S)
            resp, erro, exc = _chamar_uma_vez(funcao, entrada, adapter, kwargs, schema)

        if erro is None:
            resp.fallback_usado = indice > 0
            resp.erro = None
            return resp
        erros.append(f"{rotulo}: {erro}")
        log.warning("ia.core: %s falhou em %s: %s", funcao, rotulo, erro)

    return Resposta(
        ok=False,
        provedor=ultima["provedor"] if ultima else "",
        modelo=ultima["modelo"] if ultima else "",
        esforco=ultima["esforco"] if ultima else "",
        fallback_usado=len(erros) > 1,
        erro=" | ".join(erros) or "nenhuma tentativa configurada",
    )
