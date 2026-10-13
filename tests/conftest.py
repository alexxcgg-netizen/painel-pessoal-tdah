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

import gc
import importlib
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# Fase 7 / C1 (aviso URGENTE do integrador): nenhum teste pode chegar na API
# real de IA. Carregado antes de qualquer arquivo de teste, entao os clientes
# criados na importacao (ia.legado.client, adapters) ja nascem apontando pra
# um endereco local morto - uma chamada que escape de um duble falha, sem sair
# da maquina. Chave da Anthropic sempre falsa (as outras ficam como estao: ha
# testes que conferem o comportamento SEM chave).
#
# 2026-10-13: era a porta 9 fechada, mas no Windows conexao RECUSADA demora ~2 s
# (o SO tenta o SYN de novo) e o SDK tenta 3x: 7,5 s por chamada, ~15 s por
# pagina nos testes de navegador (o resumo do dia chama a IA ao abrir). Agora e
# um socket local que aceita e derruba na hora (RST): mesmo erro pro app
# (APIConnectionError), em ~1 s.
import socket as _socket  # noqa: E402
import struct as _struct  # noqa: E402
import threading as _threading  # noqa: E402

_ia_morta = _socket.socket()
_ia_morta.bind(("127.0.0.1", 0))
_ia_morta.listen(128)


def _derrubar_conexoes():
    while True:
        try:
            con, _ = _ia_morta.accept()
            con.setsockopt(_socket.SOL_SOCKET, _socket.SO_LINGER, _struct.pack("ii", 1, 0))
            con.close()
        except OSError:
            return


_threading.Thread(target=_derrubar_conexoes, name="ia-morta", daemon=True).start()
_URL_IA_MORTA = f"http://127.0.0.1:{_ia_morta.getsockname()[1]}"
os.environ["ANTHROPIC_BASE_URL"] = _URL_IA_MORTA
os.environ["OPENAI_BASE_URL"] = _URL_IA_MORTA
os.environ["GOOGLE_GEMINI_BASE_URL"] = _URL_IA_MORTA
os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

# Velocidade (2026-10-13): o hash do PIN em producao e scrypt, lento DE PROPOSITO
# (~80 ms pra gerar + ~75 ms pra conferir) contra forca bruta. Na suite isso se
# paga em todo setUp que define PIN e faz login - milhares de vezes. Aqui troca
# so o GERAR por pbkdf2 com 1 iteracao (o conferir le o metodo do proprio hash,
# entao fica rapido sozinho). Tem que vir antes de qualquer `import auth`, que
# faz `from werkzeug.security import generate_password_hash`. Producao intocada.
import werkzeug.security as _ws  # noqa: E402

_gerar_hash_original = _ws.generate_password_hash


def _gerar_hash_rapido(senha, method="pbkdf2:sha256:1", salt_length=16):
    return _gerar_hash_original(senha, method=method, salt_length=salt_length)


_ws.generate_password_hash = _gerar_hash_rapido


# Windows: apagar um arquivo que outro handle ainda mantem aberto da
# `PermissionError [WinError 32]` (no Linux/macOS o unlink simplesmente
# funciona). Na suite isso acontecia com o `painel.db`: varios modulos de teste
# sobem um servidor Flask numa thread daemon (ex.: tests/test_anim2_animacoes.py)
# e o `db.DB_PATH` e um global compartilhado - quando o teste do navegador
# termina, a requisicao que ainda estava no ar (ex.: /api/summary/today
# esperando a IA falhar e tentar de novo) segura a conexao por alguns segundos,
# bem na hora em que o `setUp` do teste seguinte faz `db.DB_PATH.unlink()` ou o
# `TemporaryDirectory` limpa a pasta. A janela e curta e a conexao se fecha
# sozinha quando o handler termina, entao em vez de mexer em ~30 arquivos de
# teste (e sem mudar o app) o `os.unlink`/`os.remove` tenta de novo por ate
# 30 s SO nesse erro especifico (winerror 32), coletando o lixo entre as
# tentativas (fecha conexao sqlite sem referencia). Qualquer outro erro, ou o
# mesmo erro depois do prazo, sobe como antes - nada de assercao mascarada.
if os.name == "nt":
    _unlink_original = os.unlink

    def _unlink_com_retentativa(path, *args, **kwargs):
        limite = time.monotonic() + 30
        while True:
            try:
                return _unlink_original(path, *args, **kwargs)
            except PermissionError as erro:
                if getattr(erro, "winerror", None) != 32 or time.monotonic() >= limite:
                    raise
                gc.collect()
                time.sleep(0.05)

    os.unlink = _unlink_com_retentativa
    os.remove = _unlink_com_retentativa


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
