"""Infra de testes da Fase 7, faixa A12 (infra de testes).

So fixtures OPT-IN aqui - nada autouse que mude comportamento pra suite
inteira (regra explicita de docs/agentes/fase7-regras-faixa.md, porque este
arquivo nao existia antes e passa a afetar TODOS os ~1800 testes so por
existir). Sem pedir um fixture daqui explicitamente, nenhum teste muda de
comportamento.

Hoje a suite ja isola `db.DB_PATH` sozinha (cada arquivo de teste cria seu
proprio `tempfile.TemporaryDirectory()` na importacao, ou cada `setUp`
troca `db.DB_PATH` antes de usar - ver `docs/testes.md#isolamento-de-banco`
pro levantamento completo) - os fixtures abaixo sao so pra quem for
escrever um teste `pytest` "puro" (funcao solta, sem `unittest.TestCase`)
no futuro e quiser a mesma garantia sem repetir o boilerplate.
"""

import importlib
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# Fase 7 / C1 (aviso URGENTE do integrador): nenhum teste pode chegar na API
# real de IA. Carregado antes de qualquer arquivo de teste, entao os clientes
# criados na importacao (ia.legado.client, adapters) ja nascem apontando pra
# uma porta local fechada - uma chamada que escape de um duble falha na hora,
# sem sair da maquina. Chave da Anthropic sempre falsa (as outras ficam como
# estao: ha testes que conferem o comportamento SEM chave).
os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:9"
os.environ["OPENAI_BASE_URL"] = "http://127.0.0.1:9"
os.environ["GOOGLE_GEMINI_BASE_URL"] = "http://127.0.0.1:9"
os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")


@pytest.fixture
def db_temporario():
    """OPT-IN: isola `db.DB_PATH` num SQLite temporario proprio deste
    teste, chama `db.garantir_banco_nao_producao()` (guarda contra tocar o
    banco real) e `db.init_db()`. Restaura `db.DB_PATH` no final. Uso:

        def test_algo(db_temporario):
            conn = db_temporario.get_db()
            ...

    So ativa pra quem pedir `db_temporario` na assinatura do teste - o
    `import db` fica de fora do escopo do modulo de proposito, pra este
    conftest nunca mudar o estado de um teste que nao pediu o fixture."""
    db = importlib.import_module("db")
    original = db.DB_PATH
    with tempfile.TemporaryDirectory() as tmp:
        db.DB_PATH = Path(tmp) / "painel_teste.db"
        if hasattr(db, "garantir_banco_nao_producao"):
            db.garantir_banco_nao_producao()
        db.init_db()
        try:
            yield db
        finally:
            db.DB_PATH = original


@pytest.fixture
def relogio_congelado():
    """OPT-IN: devolve uma funcao pra congelar `datetime.now()` num modulo
    (por padrao `app`) durante o teste, no padrao ja usado no resto da
    suite (`patch("app.datetime")` com `fromisoformat`/`combine` reais - ver
    `tests/test_app.py::NotificacaoAgrupadaTestCase`). Cada chamada devolve
    o `mock` do `datetime` pro teste ajustar mais (ex: `.utcnow`) se
    precisar. Desfaz tudo sozinho no fim do teste. Uso:

        def test_algo(relogio_congelado):
            relogio_congelado(datetime(2026, 9, 24, 14, 0))
            ...  # codigo que chama app.datetime.now() ve esse instante

    So ativa pra quem pedir `relogio_congelado` na assinatura - nenhum
    outro teste tem `app.datetime`/`vida.datetime` mexido por causa deste
    fixture."""
    ativos = []

    def _congelar(agora: datetime, modulo: str = "app"):
        alvo = importlib.import_module(modulo)
        p = patch.object(alvo, "datetime")
        mock_dt = p.start()
        mock_dt.now.return_value = agora
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_dt.combine = datetime.combine
        ativos.append(p)
        return mock_dt

    try:
        yield _congelar
    finally:
        for p in reversed(ativos):
            p.stop()


@pytest.fixture(autouse=True)
def _nunca_o_banco_do_checkout(tmp_path):
    """Rede de seguranca (integrador, Fase 7): so age quando `db.DB_PATH`
    ainda aponta pro banco padrao do checkout (`data/painel.db`). Quem ja
    isola o proprio banco (quase toda a suite) nao muda nada. O caso que
    pega: teste com conexao em memoria cujo codigo abre `db.get_db()` por
    dentro (ex.: assistente.caixa.enfileirar, ia.core.chamar_ia -> teto e
    uso_ia), que antes gravava no `data/painel.db` de quem rodasse."""
    db = importlib.import_module("db")
    if Path(db.DB_PATH).resolve() != db.DB_PATH_PRODUCAO:
        yield
        return
    original = db.DB_PATH
    db.DB_PATH = tmp_path / "painel_teste.db"
    db.init_db()
    try:
        yield
    finally:
        db.DB_PATH = original
