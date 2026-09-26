"""Fase 7, faixa N2 (captura por Telegram) - telegram_captura.transcrever().

`requests.post` e' sempre mockado aqui (nenhuma chamada real a Groq/qualquer
provedor de IA) - so `ia.teto`/`ia.medicao` rodam de verdade, contra um
banco temporario (mesmo padrao de tests/test_ia_teto.py), pra garantir que o
teto de IA e' respeitado E que o uso e' registrado com o custo certo."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")
os.environ.setdefault("GROQ_API_KEY", "teste-fake-groq")

import pytest
import requests as requests_mod

import db
import ia.medicao as medicao
import ia.teto as teto
import telegram_captura as tc


class _Resposta:
    def __init__(self, status_code=200, corpo=None, levanta=None):
        self.status_code = status_code
        self._corpo = corpo or {}
        self._levanta = levanta

    def raise_for_status(self):
        if self._levanta:
            raise self._levanta

    def json(self):
        return self._corpo


@pytest.fixture
def banco_temporario():
    tmp = tempfile.TemporaryDirectory()
    caminho_original = db.DB_PATH
    db.DB_PATH = Path(tmp.name) / "painel.db"
    db.garantir_banco_nao_producao()
    db.init_db()
    try:
        yield
    finally:
        db.DB_PATH = caminho_original
        tmp.cleanup()


def test_transcrever_com_sucesso_registra_uso_e_devolve_texto(banco_temporario):
    with patch("telegram_captura.requests.post", return_value=_Resposta(200, {"text": "compra 40 reais"})):
        texto = tc.transcrever(b"audio-fake", "audio/ogg", duracao_segundos=36)
    assert texto == "compra 40 reais"
    esperado_usd = 36 * tc.PRECO_TRANSCRICAO_USD_POR_SEGUNDO
    assert medicao.gasto_mes_atual() == pytest.approx(esperado_usd)


def test_transcrever_teto_estourado_levanta_erro_sem_chamar_rede(banco_temporario):
    # Estoura o teto padrao (R$40) de proposito.
    medicao.registrar_uso("chat", "anthropic", "claude-sonnet-5", custo_usd=1000.0)
    assert teto.nivel_alerta() == "estourado_100"

    with patch("telegram_captura.requests.post") as post_mock:
        with pytest.raises(tc.ErroCaptura):
            tc.transcrever(b"audio", "audio/ogg", duracao_segundos=10)
    post_mock.assert_not_called()


def test_transcrever_sem_api_key_levanta_erro(banco_temporario, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(tc.ErroCaptura, match="GROQ_API_KEY"):
        tc.transcrever(b"audio", "audio/ogg", duracao_segundos=5)


def test_transcrever_falha_de_rede_registra_uso_ok_false_e_levanta_erro(banco_temporario):
    with patch("telegram_captura.requests.post", side_effect=requests_mod.exceptions.ConnectionError("fora do ar")):
        with pytest.raises(tc.ErroCaptura):
            tc.transcrever(b"audio", "audio/ogg", duracao_segundos=8)
    conn = db.get_db()
    try:
        linha = conn.execute(
            "SELECT ok FROM uso_ia WHERE funcao = ? ORDER BY id DESC LIMIT 1", (tc.FUNCAO_TRANSCRICAO,)
        ).fetchone()
    finally:
        conn.close()
    assert linha is not None
    assert linha["ok"] == 0


def test_transcrever_resposta_http_erro_levanta_erro_capturado(banco_temporario):
    erro_http = requests_mod.exceptions.HTTPError("500")
    with patch("telegram_captura.requests.post", return_value=_Resposta(500, {}, levanta=erro_http)):
        with pytest.raises(tc.ErroCaptura):
            tc.transcrever(b"audio", "audio/ogg", duracao_segundos=8)


def test_transcrever_texto_vazio_levanta_erro(banco_temporario):
    with patch("telegram_captura.requests.post", return_value=_Resposta(200, {"text": "   "})):
        with pytest.raises(tc.ErroCaptura, match="não entendi nada"):
            tc.transcrever(b"audio", "audio/ogg", duracao_segundos=3)


def test_transcrever_json_malformado_levanta_erro(banco_temporario):
    class _RespostaJsonQuebrado(_Resposta):
        def json(self):
            raise ValueError("corpo nao e' JSON")

    with patch("telegram_captura.requests.post", return_value=_RespostaJsonQuebrado(200, {})):
        with pytest.raises(tc.ErroCaptura):
            tc.transcrever(b"audio", "audio/ogg", duracao_segundos=3)


@pytest.mark.parametrize("duracao", [0, -5, None])
def test_transcrever_duracao_invalida_nao_gera_custo_negativo(banco_temporario, duracao):
    with patch("telegram_captura.requests.post", return_value=_Resposta(200, {"text": "ok"})):
        tc.transcrever(b"audio", "audio/ogg", duracao_segundos=duracao)
    assert medicao.gasto_mes_atual() >= 0
