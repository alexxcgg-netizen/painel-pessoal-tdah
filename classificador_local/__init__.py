"""Regras locais do classificador (Fase 7, Etapa 0): frases que resolvem SEM IA.

Cada faixa que quer uma frase resolvida localmente ("assinei Netflix 55 por
mes", "tomei um copo de agua", "replaneja meu dia", "me avisa se...") cria o
PROPRIO arquivo em `classificador_local/regras/<nome>.py` - ninguem edita
app.py nem o arquivo de outra faixa. Ver classificador_local/README.md.

Contrato de um modulo de regra:
- `casar(texto: str) -> dict | None`: None = nao e comigo. Senao um dict com
  pelo menos "acao" (str); "confianca" (0..1, padrao 1.0), "parametros"
  (dict, padrao {}) e "precisa_confirmacao" (bool, padrao False) sao
  opcionais. Tem que ser RAPIDO e sem efeito colateral (roda em toda mensagem
  de chat/captura/intent) - so regex/texto, nunca banco nem rede.
- `executar(conn, parametros: dict) -> dict | None`: faz a acao e devolve
  `{"efeitos": [...], "resumo_texto": "..."}` (efeitos no formato `_efeito`
  de docs/CARDS.md - viram os MESMOS cards do chat, com Desfazer) ou um
  envelope pronto `{"cards": [...], "resumo_texto": "...", "passos": [...]}`.
  "passos" e opcional nos dois formatos. None = desisti, segue o fluxo normal
  (IA). NAO faz commit - quem chama commita tudo junto.

Onde isso e consultado (app.py), sempre ANTES de qualquer IA:
- `_classificar_intent` (primeira camada, so classifica - campo aditivo
  "regra_local" no resultado);
- `_executar_captura` (/api/capture e /api/atalho/capturar) e
  `_processar_mensagem_chat` (/api/chat e Telegram): casou e `executar`
  devolveu algo -> resposta so com os cards da regra, sem chamar a IA.

Com `regras/` vazio, nada disso muda comportamento nenhum.
"""

import importlib
import logging
import pkgutil
import time

import cards
from classificador_local import regras as _pacote_regras

log = logging.getLogger(__name__)


def nomes_regras() -> list[str]:
    """Nome de todo modulo em `regras/` (ordem alfabetica). Usa `__path__` do
    pacote, entao teste pode acrescentar uma pasta temporaria."""
    return sorted({m.name for m in pkgutil.iter_modules(_pacote_regras.__path__) if not m.ispkg})


def _modulo_regra(nome: str):
    return importlib.import_module(f"{_pacote_regras.__name__}.{nome}")


def _normalizar(bruto, nome: str) -> dict | None:
    if not isinstance(bruto, dict):
        return None
    acao = bruto.get("acao")
    if not isinstance(acao, str) or not acao.strip():
        return None
    confianca = bruto.get("confianca", 1.0)
    if not isinstance(confianca, (int, float)) or isinstance(confianca, bool):
        confianca = 1.0
    confianca = max(0.0, min(1.0, float(confianca)))
    parametros = bruto.get("parametros")
    return {
        "acao": acao.strip(),
        "confianca": confianca,
        "parametros": parametros if isinstance(parametros, dict) else {},
        "precisa_confirmacao": bool(bruto.get("precisa_confirmacao", False)),
        "regra": nome,
    }


def casar(texto) -> dict | None:
    """Primeira regra (ordem alfabetica do arquivo) que casa com o texto, ou
    None. Regra que levanta excecao ou devolve formato invalido e pulada
    (loga) - uma regra quebrada nunca derruba chat/captura."""
    if not isinstance(texto, str) or not texto.strip():
        return None
    for nome in nomes_regras():
        try:
            modulo = _modulo_regra(nome)
            fn = getattr(modulo, "casar", None)
            if not callable(fn):
                continue
            bruto = fn(texto)
        except Exception:
            log.exception("classificador_local: regra %s falhou no casar()", nome)
            continue
        if bruto is None:
            continue
        resultado = _normalizar(bruto, nome)
        if resultado:
            return resultado
        log.warning("classificador_local: regra %s devolveu formato invalido: %r", nome, bruto)
    return None


def executar(conn, resultado, criar_token=None) -> dict | None:
    """Roda `executar(conn, parametros)` da regra que casou e devolve o
    envelope do contrato de cards (`{cards, resumo_texto, passos}`), ou None
    se a regra nao tem executor, desistiu (None) ou falhou (excecao: loga e
    faz rollback do que a regra tiver escrito - quem chama segue o fluxo
    normal). `criar_token` e o mesmo de cards.montar_resposta (Desfazer)."""
    if not isinstance(resultado, dict) or not isinstance(resultado.get("regra"), str):
        return None
    nome = resultado["regra"]
    parametros = resultado.get("parametros") if isinstance(resultado.get("parametros"), dict) else {}
    inicio = time.perf_counter()
    try:
        fn = getattr(_modulo_regra(nome), "executar", None)
        if not callable(fn):
            return None
        saida = fn(conn, parametros)
    except Exception:
        log.exception("classificador_local: regra %s falhou no executar()", nome)
        conn.rollback()
        return None
    if not isinstance(saida, dict):
        return None
    passos = saida.get("passos")
    if not isinstance(passos, list) or not passos:
        passos = [{
            "modulo": "Classificador local",
            "descricao": f"Resolveu sem IA ({nome})",
            "ms": int(round((time.perf_counter() - inicio) * 1000)),
        }]
    resumo = saida.get("resumo_texto") if isinstance(saida.get("resumo_texto"), str) else ""
    if isinstance(saida.get("cards"), list):
        return cards.envelope(saida["cards"], resumo, passos)
    efeitos = saida.get("efeitos") if isinstance(saida.get("efeitos"), list) else []
    return cards.montar_resposta(conn, efeitos, resumo, passos, criar_token)
