"""Leva 08/11, C7: chave da API recusada (401). O nucleo (ia.core) nao repete nem cai no fallback do mesmo
provedor, pausa as chamadas seguintes, o chat responde uma mensagem clara e sai UM aviso por dia (fora do
silencio). Tudo dublado: nenhuma API real, nenhuma chave lida."""
import json
import os
import sys
import tempfile
import types
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import anthropic  # noqa: E402
import httpx  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
from ia import core  # noqa: E402
from ia.contrato import Adapter, Resposta  # noqa: E402

_tmp = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402

PIN = "135790"
ERRO_401 = ("Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', "
            "'message': 'invalid x-api-key'}}")


class _Duble(Adapter):
    def __init__(self, roteiros=None):
        self.roteiros = list(roteiros or [])
        self.chamadas = 0

    def chamar(self, **kwargs):
        self.chamadas += 1
        return self.roteiros.pop(0) if self.roteiros else Resposta(ok=True, texto="ok")


def _erro_autenticacao():
    resp = httpx.Response(401, request=httpx.Request("POST", "http://ia-morta.invalid/v1/messages"))
    return anthropic.AuthenticationError("invalid x-api-key", response=resp, body=None)


class NucleoTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for alvo, valor in (("DIR_CONFIG", Path(self.tmp.name)), ("ESPERA_RETRY_S", 0)):
            p = patch.object(core, alvo, valor)
            p.start()
            self.addCleanup(p.stop)
        core.limpar_cache()
        self.addCleanup(core.limpar_cache)
        self.anthropic = _Duble([Resposta(ok=False, erro=ERRO_401)])
        self.openai = _Duble()
        core.registrar_adapter("anthropic", lambda: self.anthropic)
        core.registrar_adapter("openai", lambda: self.openai)
        self.addCleanup(core.registrar_adapter, "anthropic", None)
        self.addCleanup(core.registrar_adapter, "openai", None)
        medicao = types.ModuleType("ia.medicao")
        medicao.registrar_uso = lambda *a, **k: None
        teto = types.ModuleType("ia.teto")
        teto.teto_permite = lambda funcao: True
        p = patch.dict(sys.modules, {"ia.medicao": medicao, "ia.teto": teto})
        p.start()
        self.addCleanup(p.stop)

    def config(self, fallback):
        dados = {
            "funcao": "diario_teste", "ativo": False,
            "modelo_atual": {"provedor": "anthropic", "modelo": "claude-haiku-teste"},
            "fallback": fallback, "max_tokens_saida": 100, "cache": {"ativo": False}, "modo": "padrao",
        }
        (Path(self.tmp.name) / "diario_teste.json").write_text(json.dumps(dados), encoding="utf-8")

    def test_401_nao_tenta_o_fallback_do_mesmo_provedor_nem_de_novo(self):
        self.config([{"provedor": "anthropic", "modelo": "claude-sonnet-teste"}])
        resp = core.chamar_ia("diario_teste", [{"role": "user", "content": "oi"}])
        self.assertFalse(resp.ok)
        self.assertEqual(self.anthropic.chamadas, 1)  # nem o Sonnet do fallback (mesma chave)
        self.assertEqual(core.classificar_falha(resp.erro), "chave")
        self.assertIsInstance(core.excecao_de_resposta("diario_teste", resp), core.ChaveRecusada)
        self.assertIsInstance(core.excecao_de_resposta("diario_teste", resp), core.ErroProvedor)
        self.assertTrue(core.chave_recusada("anthropic"))
        # proximo tick (diario/cartoes da manha): nem chama a API
        resp2 = core.chamar_ia("diario_teste", [{"role": "user", "content": "oi"}])
        self.assertFalse(resp2.ok)
        self.assertEqual(self.anthropic.chamadas, 1)
        self.assertEqual(core.classificar_falha(resp2.erro), "chave")

    def test_fallback_de_outro_provedor_ainda_vale(self):
        self.config([{"provedor": "openai", "modelo": "gpt-teste"}])
        resp = core.chamar_ia("diario_teste", [{"role": "user", "content": "oi"}])
        self.assertTrue(resp.ok)
        self.assertEqual((self.anthropic.chamadas, self.openai.chamadas), (1, 1))

    def test_pausa_acaba_e_sucesso_limpa(self):
        self.config([])
        core.chamar_ia("diario_teste", [{"role": "user", "content": "oi"}])
        self.assertIsNotNone(core.ultima_recusa())
        with patch.object(core, "PAUSA_CHAVE_RECUSADA_S", 0):
            self.assertFalse(core.chave_recusada("anthropic"))
            resp = core.chamar_ia("diario_teste", [{"role": "user", "content": "oi"}])
        self.assertTrue(resp.ok)
        self.assertEqual(self.anthropic.chamadas, 2)
        self.assertIsNone(core.ultima_recusa())

    def test_erro_de_autenticacao(self):
        self.assertTrue(core.erro_de_autenticacao(ERRO_401))
        self.assertTrue(core.erro_de_autenticacao(exc=_erro_autenticacao()))
        self.assertFalse(core.erro_de_autenticacao("Error code: 529 - overloaded"))
        self.assertFalse(core.erro_de_autenticacao("JSON invalido na resposta (JSONDecodeError: x)"))
        self.assertEqual(core.classificar_falha("anthropic/x: Error code: 500 | anthropic/y: " + ERRO_401), "provedor")


class _BaseApp(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = Path(_tmp.name) / "painel.db"
        db.garantir_banco_nao_producao()
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        self.assertEqual(self.client.post("/login", json={"pin": PIN}).status_code, 200)
        core.limpar_chave_recusada()
        self.addCleanup(core.limpar_chave_recusada)


class ChatComChaveRecusadaTestCase(_BaseApp):
    def test_chat_responde_claro_e_nao_bate_de_novo(self):
        with patch("claude_client.chat", side_effect=_erro_autenticacao()) as chat:
            r1 = self.client.post("/api/chat", json={"mensagem": "monta meu dia"})
            r2 = self.client.post("/api/chat", json={"mensagem": "e agora?"})
        self.assertEqual(r1.status_code, 502)
        self.assertEqual(r1.get_json()["error"], app.IA_CHAVE_RECUSADA_MSG)
        self.assertIn("chave da API foi recusada", r1.get_json()["error"])
        self.assertEqual(r2.get_json()["error"], app.IA_CHAVE_RECUSADA_MSG)
        self.assertEqual(chat.call_count, 1)  # a 2a nem chamou
        conn = db.get_db()
        try:  # ele ja viu no chat: conta como o aviso do dia (sem push repetindo)
            self.assertTrue(db.ja_notificou_hoje(conn, app.TIPO_AVISO_CHAVE_RECUSADA))
        finally:
            conn.close()

    def test_outro_erro_continua_generico(self):
        with patch("claude_client.chat", side_effect=core.ErroProvedor("chat: Error code: 529")):
            r = self.client.post("/api/chat", json={"mensagem": "oi"})
        self.assertEqual(r.get_json()["error"], app.CLAUDE_ERROR_MSG)


class AvisoDoDiaTestCase(_BaseApp):
    def setUp(self):
        super().setUp()
        self.push = patch("assistente.caixa.enviar_push", return_value=True)
        self.enviar = self.push.start()
        self.addCleanup(self.push.stop)
        for alvo in ("app._pra_fila_do_app",):
            p = patch(alvo, return_value=False)
            p.start()
            self.addCleanup(p.stop)
        p = patch("telegram_bot.configurado", return_value=False)
        p.start()
        self.addCleanup(p.stop)

    def test_um_aviso_por_dia(self):
        conn = db.get_db()
        try:
            meio_dia = datetime.combine(date.today(), datetime.min.time()).replace(hour=12)
            self.assertTrue(app._avisar_chave_recusada(conn, agora=meio_dia))
            self.assertFalse(app._avisar_chave_recusada(conn, agora=meio_dia))
        finally:
            conn.close()
        self.assertEqual(self.enviar.call_count, 1)
        titulo, corpo = self.enviar.call_args[0][1:3]
        self.assertIn("chave recusada", titulo)

    def test_de_madrugada_espera_o_silencio_acabar(self):
        conn = db.get_db()
        try:
            madrugada = datetime.combine(date.today(), datetime.min.time()).replace(hour=0, minute=4)
            self.assertFalse(app._avisar_chave_recusada(conn, agora=madrugada))
            self.assertFalse(db.ja_notificou_hoje(conn, app.TIPO_AVISO_CHAVE_RECUSADA))
            manha = madrugada.replace(hour=10)
            self.assertTrue(app._avisar_chave_recusada(conn, agora=manha))
        finally:
            conn.close()
        self.assertEqual(self.enviar.call_count, 1)


if __name__ == "__main__":
    unittest.main()
