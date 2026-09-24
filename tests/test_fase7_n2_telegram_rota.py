"""Fase 7, faixa N2 (captura por Telegram) - rotas/n2_telegram.py (webhook).

A infra de Blueprint com carga automatica (rotas/__init__.py, rotas/_base.py
- Etapa 0/X1) ainda nao chegou em fase7/integracao quando esta faixa foi
escrita (ver scripts/ralph-n2-telegram/progress.txt) - N2 estava listada em
STATUS.md como dependente dela. Pra nao bloquear a faixa inteira nisso, este
teste registra um `rotas._base` MINIMO em sys.modules (sem escrever nenhum
arquivo em disco) so o suficiente pra `rotas.n2_telegram` importar - se a
infra real ja tiver chegado (rotas/_base.py de verdade no disco), o import
normal dela e' usado sem alteracao nenhuma (ver _preparar_rotas_n2_telegram).

Nenhuma chamada real ao Telegram ou a IA - claude_client.extrair_nota_fiscal_foto,
app._executar_captura, app._salvar_link e' tudo dublê (FakeApp abaixo)."""

import hmac
import os
import sys
import types
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import pytest

import db

_RAIZ = Path(__file__).resolve().parent.parent


def _preparar_rotas_n2_telegram():
    """Garante que `import rotas.n2_telegram` funcione neste ambiente de
    teste. Devolve o modulo `rotas.n2_telegram` e uma referencia mutavel
    (`_app_atual`, lista de 1 elemento) que os testes usam pra trocar o
    FakeApp que `app_modulo()` devolve, request a request."""
    _app_atual = [None]

    if "rotas" not in sys.modules:
        pacote = types.ModuleType("rotas")
        pacote.__path__ = [str(_RAIZ / "rotas")]
        sys.modules["rotas"] = pacote

    try:
        import rotas._base as base_real  # noqa: F401  - Etapa 0 ja chegou? usa a de verdade

        # Infra real: precisamos ainda conseguir trocar o app devolvido por
        # app_modulo() por teste - envolve com um indirect simples.
        def app_modulo():
            return _app_atual[0]

        sys.modules["rotas._base"].app_modulo = app_modulo
    except ModuleNotFoundError:
        base_falso = types.ModuleType("rotas._base")

        def app_modulo():
            return _app_atual[0]

        base_falso.app_modulo = app_modulo
        sys.modules["rotas._base"] = base_falso

    sys.modules.pop("rotas.n2_telegram", None)
    import rotas.n2_telegram as n2_telegram

    return n2_telegram, _app_atual


n2_telegram, _app_atual = _preparar_rotas_n2_telegram()


class FakeApp:
    """Dublê de app.py - so o que rotas/n2_telegram.py usa via app_modulo()."""

    def __init__(self, corpo_captura=None, status_captura=201, resultado_salvar=None):
        import threading

        self._TETO_IA_LOCK = threading.Lock()
        self.TETO_IA_MSG = "teto mensal de gasto com IA estourado"
        self.chamadas_executar_captura = []
        self.chamadas_salvar_link = []
        self._corpo_captura = corpo_captura or {"resumo_texto": "Tarefa criada.", "titulo": "algo"}
        self._status_captura = status_captura
        self._resultado_salvar = resultado_salvar or {"ok": True}

    def _executar_captura(self, texto, clarificacao):
        self.chamadas_executar_captura.append((texto, clarificacao))

        class _RespostaFalsa:
            def __init__(self, corpo):
                self._corpo = corpo

            def get_json(self):
                return self._corpo

        return _RespostaFalsa(self._corpo_captura), self._status_captura

    def _salvar_link(self, conn, url):
        self.chamadas_salvar_link.append((conn, url))
        return self._resultado_salvar

    def _call_claude(self, fn, *args):
        return fn(*args), None

    def _log_usage(self, conn, usage, feature="outro"):
        pass


SEGREDO = "segredo-do-webhook-teste"
CHAT_PERMITIDO = "998877"


@pytest.fixture
def app_flask(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-fake")
    monkeypatch.setenv("TELEGRAM_CHAT_ID_PERMITIDO", CHAT_PERMITIDO)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SEGREDO)
    monkeypatch.delenv("APP_URL_PUBLICA", raising=False)

    caminho_original = db.DB_PATH
    db.DB_PATH = tmp_path / "painel.db"
    db.garantir_banco_nao_producao()
    db.init_db()

    _app_atual[0] = FakeApp()

    from flask import Flask

    flask_app = Flask(__name__)
    flask_app.register_blueprint(n2_telegram.bp)
    flask_app.testing = True

    yield flask_app

    db.DB_PATH = caminho_original
    _app_atual[0] = None


def _post(cliente, corpo, secret=SEGREDO, com_secret=True):
    headers = {n2_telegram.CABECALHO_SECRETO: secret} if com_secret else {}
    return cliente.post("/api/telegram/webhook", json=corpo, headers=headers)


def _update_texto(update_id=1, chat_id=CHAT_PERMITIDO, texto="lembra de pagar a agua"):
    return {"update_id": update_id, "message": {"chat": {"id": int(chat_id) if chat_id.lstrip("-").isdigit() else chat_id}, "text": texto}}


# ---- ROTAS_COM_TOKEN --------------------------------------------------


def test_declara_a_rota_como_maquina_a_maquina():
    assert n2_telegram.ROTAS_COM_TOKEN == {"/api/telegram/webhook"}


# ---- secret ---------------------------------------------------------------


def test_secret_ausente_e_401(app_flask):
    cliente = app_flask.test_client()
    resposta = _post(cliente, _update_texto(), com_secret=False)
    assert resposta.status_code == 401
    assert _app_atual[0].chamadas_executar_captura == []


def test_secret_errado_e_401(app_flask):
    cliente = app_flask.test_client()
    resposta = _post(cliente, _update_texto(), secret="outro-segredo-qualquer")
    assert resposta.status_code == 401
    assert _app_atual[0].chamadas_executar_captura == []


def test_secret_correto_mas_timing_safe(app_flask, monkeypatch):
    """`_secret_valido` usa hmac.compare_digest - garante que nao caiu pra
    uma comparacao ingenua (`==`) que um refactor futuro poderia introduzir
    sem querer."""
    chamadas = []
    original = hmac.compare_digest

    def espiao(a, b):
        chamadas.append((a, b))
        return original(a, b)

    monkeypatch.setattr(n2_telegram.hmac, "compare_digest", espiao)
    cliente = app_flask.test_client()
    _post(cliente, _update_texto())
    assert len(chamadas) == 1


# ---- allowlist de chat -----------------------------------------------


def test_chat_nao_permitido_e_200_silencioso(app_flask):
    cliente = app_flask.test_client()
    update = _update_texto(chat_id="111111")
    resposta = _post(cliente, update)
    assert resposta.status_code == 200
    assert _app_atual[0].chamadas_executar_captura == []


def test_sem_chat_permitido_configurado_nunca_processa(app_flask, monkeypatch):
    monkeypatch.delenv("TELEGRAM_CHAT_ID_PERMITIDO", raising=False)
    cliente = app_flask.test_client()
    resposta = _post(cliente, _update_texto())
    assert resposta.status_code == 200
    assert _app_atual[0].chamadas_executar_captura == []


# ---- corpo malformado -------------------------------------------------


def test_corpo_nao_json_e_400(app_flask):
    cliente = app_flask.test_client()
    resposta = cliente.post(
        "/api/telegram/webhook",
        data="isso nao e json",
        headers={n2_telegram.CABECALHO_SECRETO: SEGREDO, "Content-Type": "text/plain"},
    )
    assert resposta.status_code == 400


def test_update_id_ausente_e_400(app_flask):
    cliente = app_flask.test_client()
    resposta = cliente.post(
        "/api/telegram/webhook",
        json={"message": {"chat": {"id": int(CHAT_PERMITIDO)}, "text": "oi"}},
        headers={n2_telegram.CABECALHO_SECRETO: SEGREDO},
    )
    assert resposta.status_code == 400


# ---- idempotencia -------------------------------------------------------


def test_update_processado_uma_vez_so(app_flask):
    cliente = app_flask.test_client()
    update = _update_texto(update_id=42, texto="compra 20 reais no mercado")

    r1 = _post(cliente, update)
    assert r1.status_code == 200
    assert r1.get_json().get("duplicado") is not True

    r2 = _post(cliente, update)
    assert r2.status_code == 200
    assert r2.get_json().get("duplicado") is True

    assert len(_app_atual[0].chamadas_executar_captura) == 1


def test_updates_diferentes_processam_normalmente(app_flask):
    cliente = app_flask.test_client()
    _post(cliente, _update_texto(update_id=1, texto="tarefa um"))
    _post(cliente, _update_texto(update_id=2, texto="tarefa dois"))
    assert len(_app_atual[0].chamadas_executar_captura) == 2


# ---- fluxo completo: texto ----------------------------------------------


def test_texto_valido_chama_executar_captura_e_responde_ok(app_flask):
    cliente = app_flask.test_client()
    resposta = _post(cliente, _update_texto(texto="lembra de pagar a agua"))
    assert resposta.status_code == 200
    assert resposta.get_json() == {"ok": True}
    assert _app_atual[0].chamadas_executar_captura == [("lembra de pagar a agua", "")]


def test_link_valido_chama_salvar_link(app_flask, monkeypatch):
    monkeypatch.setattr(n2_telegram.telegram_captura.leitura, "validar_url", lambda url: url.strip())
    cliente = app_flask.test_client()
    update = _update_texto(texto="https://exemplo.com/pagina")
    resposta = _post(cliente, update)
    assert resposta.status_code == 200
    assert _app_atual[0].chamadas_salvar_link
    assert _app_atual[0].chamadas_executar_captura == []


# ---- _extrair_nota_fiscal (adapter) --------------------------------------


def test_extrair_nota_fiscal_recusa_com_teto_estourado(app_flask, monkeypatch):
    monkeypatch.setattr(db, "resumo_custo_api", lambda conn: {"teto_estourado": True})
    dados, erro = n2_telegram._extrair_nota_fiscal(b"jpeg", "image/jpeg")
    assert dados is None
    assert erro == _app_atual[0].TETO_IA_MSG


def test_extrair_nota_fiscal_devolve_dados_no_sucesso(app_flask, monkeypatch):
    monkeypatch.setattr(db, "resumo_custo_api", lambda conn: {"teto_estourado": False})
    monkeypatch.setattr(
        n2_telegram.claude_client,
        "extrair_nota_fiscal_foto",
        lambda image_bytes, media_type: ({"valor": 12.5, "estabelecimento": "Loja X"}, {"model": "m", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0}),
    )
    dados, erro = n2_telegram._extrair_nota_fiscal(b"jpeg", "image/jpeg")
    assert erro is None
    assert dados == {"valor": 12.5, "estabelecimento": "Loja X"}


def test_extrair_nota_fiscal_erro_na_chamada_vira_mensagem_curta(app_flask, monkeypatch):
    monkeypatch.setattr(db, "resumo_custo_api", lambda conn: {"teto_estourado": False})

    def _app_call_claude_com_erro(fn, *args):
        return None, ("erro-flask-fake", 502)

    _app_atual[0]._call_claude = _app_call_claude_com_erro
    dados, erro = n2_telegram._extrair_nota_fiscal(b"jpeg", "image/jpeg")
    assert dados is None
    assert erro
