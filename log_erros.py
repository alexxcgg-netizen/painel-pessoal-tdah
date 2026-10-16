"""Grava os erros do servidor em arquivo (2026-10-16).

Antes, WARNING/ERROR/traceback so apareciam na janela do console do Waitress e sumiam quando ela
fechava ou reiniciava - o relatorio do painel (`scripts/relatorio_painel.py`) nao tinha o que ler.
Agora vao tambem pra `data/erros_servidor.log` (rotativo, 3 x 500 KB; `data/` e gitignored).
So WARNING pra cima: nada de conteudo de pedido, so o que a propria aplicacao decidiu logar.
Sob teste nao liga (o banco aponta pra pasta temporaria e nao se grava lixo no disco do Alex).
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

NOME = "erros_servidor.log"
_MARCA = "_painel_log_erros"


def configurar(pasta: Path, forcar: bool = False) -> Path | None:
    """Liga o arquivo de erros (uma vez so). Devolve o caminho, ou None se nao ligou."""
    if not forcar and {"pytest", "unittest"} & set(sys.modules):
        return None
    raiz = logging.getLogger()
    if any(getattr(h, _MARCA, False) for h in raiz.handlers):
        return pasta / NOME
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        h = RotatingFileHandler(pasta / NOME, maxBytes=500_000, backupCount=2, encoding="utf-8")
    except OSError:  # disco cheio/sem permissao: o servidor sobe do mesmo jeito
        return None
    h.setLevel(logging.WARNING)
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    setattr(h, _MARCA, True)
    raiz.addHandler(h)
    if raiz.level in (logging.NOTSET, logging.WARNING) or raiz.level > logging.WARNING:
        raiz.setLevel(logging.WARNING)
    return pasta / NOME
