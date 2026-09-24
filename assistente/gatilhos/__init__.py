"""Gatilhos do assistente proativo (Fase 7, Etapa 0).

Cada faixa que quer o assistente puxando assunto sozinho ("conta vencendo
amanha", "3 dias sem treinar", "voo em 2h") cria o PROPRIO arquivo
`assistente/gatilhos/<nome>.py` com:

    def executar(conn, agora):
        '''agora: datetime (hora local). Olha o banco e, se for o caso,
        enfileira na Caixa via assistente.contrato.enfileirar(..., chave_unica=...)
        - chave_unica evita repetir o mesmo aviso a cada tick. Nao faz commit
        (quem chama commita). Pode devolver qualquer coisa (vai pro relatorio).'''

`executar_todos(conn, agora)` carrega todo modulo desta pasta (ordem
alfabetica, modulo sem `executar` e ignorado) e chama cada um, isolando
excecao POR MODULO: um gatilho quebrado loga o erro, desfaz o que ele mesmo
escreveu (rollback) e os outros continuam. Quem chama e o `/api/tick` (faixa
P1a) - este pacote nao cria endpoint nem agenda nada.
"""

import importlib
import logging
import pkgutil

log = logging.getLogger(__name__)


def nomes_gatilhos() -> list[str]:
    """Nome de todo modulo desta pasta (ordem alfabetica). Usa `__path__`,
    entao teste pode acrescentar uma pasta temporaria."""
    return sorted({m.name for m in pkgutil.iter_modules(__path__) if not m.ispkg})


def executar_todos(conn, agora) -> dict:
    """Roda `executar(conn, agora)` de cada gatilho. Devolve
    `{nome: {"ok": True, "resultado": ...} | {"ok": False, "erro": "..."}}`
    (so os modulos que tem `executar`). Cada gatilho que deu certo e
    commitado na hora, entao a falha de um gatilho posterior (rollback) nunca
    desfaz o que um anterior ja gravou."""
    relatorio = {}
    for nome in nomes_gatilhos():
        try:
            fn = getattr(importlib.import_module(f"{__name__}.{nome}"), "executar", None)
            if not callable(fn):
                continue
            resultado = fn(conn, agora)
            conn.commit()
            relatorio[nome] = {"ok": True, "resultado": resultado}
        except Exception as e:
            log.exception("gatilho %s falhou", nome)
            try:
                conn.rollback()
            except Exception:
                log.exception("gatilho %s: rollback falhou", nome)
            relatorio[nome] = {"ok": False, "erro": f"{type(e).__name__}: {e}"}
    return relatorio
