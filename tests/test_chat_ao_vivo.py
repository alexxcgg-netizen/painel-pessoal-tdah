"""Resposta do chat AO VIVO (2026-10-13): /api/chat/stream (text/event-stream) e o modo
stream do loop de tool-use (ia/funcoes/chat.py, ao_texto). Cliente Anthropic sempre
mockado e banco temporario (nunca o data/painel.db)."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import claude_client  # noqa: E402
from ia.funcoes import chat as chat_mod  # noqa: E402

PIN_TESTE = "123456"


def _resp(content, stop_reason="end_turn"):
    return SimpleNamespace(
        content=content, stop_reason=stop_reason, model="claude-haiku-5-5",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5,
                              cache_read_input_tokens=0, cache_creation_input_tokens=0),
    )


def _texto(t):
    return SimpleNamespace(type="text", text=t)


def _tool(nome, entrada, id_="t1"):
    return SimpleNamespace(type="tool_use", name=nome, input=entrada, id=id_)


class _FluxoFalso:
    """Duble de client.messages.stream(...): context manager com text_stream e
    get_final_message, como o SDK."""

    def __init__(self, resposta):
        self.resposta = resposta

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def text_stream(self):
        for b in self.resposta.content:
            if b.type == "text":
                for palavra in b.text.split(" "):
                    yield palavra + " "

    def get_final_message(self):
        return self.resposta


def _eventos_sse(corpo: str):
    eventos = []
    for bloco in corpo.split("\n\n"):
        evento, dado = None, None
        for linha in bloco.split("\n"):
            if linha.startswith("event: "):
                evento = linha[7:]
            elif linha.startswith("data: "):
                dado = json.loads(linha[6:])
        if evento:
            eventos.append((evento, dado))
    return eventos


class LoopEmModoStreamTestCase(unittest.TestCase):
    def setUp(self):
        p = patch.object(chat_mod, "_decidir_rota", return_value="padrao")
        p.start()
        self.addCleanup(p.stop)

    def _rodar(self, respostas, executores=None):
        fila = list(respostas)
        avisos = []
        with patch.object(claude_client.client.messages, "stream",
                          side_effect=lambda **kw: _FluxoFalso(fila.pop(0))) as stream, \
                patch.object(claude_client.client.messages, "create") as create, \
                claude_client.ao_texto(lambda ev, dado: avisos.append((ev, dado))):
            saida = claude_client.chat([{"role": "user", "content": "oi"}], "ctx", [], executores or {})
        return saida, avisos, stream, create

    def test_texto_chega_aos_pedacos_e_nao_usa_create(self):
        (texto, _, _), avisos, stream, create = self._rodar([_resp([_texto("Oi, tudo certo por aqui.")])])
        self.assertEqual(texto, "Oi, tudo certo por aqui.")
        pedacos = [d for ev, d in avisos if ev == "texto"]
        self.assertGreater(len(pedacos), 1)
        self.assertEqual("".join(pedacos).strip(), "Oi, tudo certo por aqui.")
        create.assert_not_called()
        self.assertEqual(stream.call_count, 1)

    def test_texto_antes_de_ferramenta_manda_recomeca(self):
        respostas = [
            _resp([_texto("Deixa eu ver"), _tool("consultar_clima", {})], stop_reason="tool_use"),
            _resp([_texto("Vai chover a tarde.")]),
        ]
        (texto, acoes, _), avisos, _s, _c = self._rodar(
            respostas, {"consultar_clima": lambda e: {"ok": True}})
        self.assertEqual(texto, "Vai chover a tarde.")
        self.assertEqual(acoes, ["consultar_clima"])
        eventos = [ev for ev, _ in avisos]
        self.assertIn("recomeca", eventos)
        # o recomeca vem DEPOIS do "deixa eu ver" e ANTES da resposta final
        i = eventos.index("recomeca")
        self.assertIn("Deixa", "".join(d for ev, d in avisos[:i] if ev == "texto"))
        self.assertIn("chover", "".join(d for ev, d in avisos[i:] if ev == "texto"))

    def test_sem_aviso_ligado_continua_no_create(self):
        with patch.object(claude_client.client.messages, "create",
                          return_value=_resp([_texto("ok")])) as create, \
                patch.object(claude_client.client.messages, "stream") as stream:
            claude_client.chat([{"role": "user", "content": "oi"}], "ctx", [], {})
        create.assert_called_once()
        stream.assert_not_called()

    def test_aviso_que_quebra_nao_derruba_a_resposta(self):
        def quebra(ev, dado):
            raise RuntimeError("tela fechou")

        with patch.object(claude_client.client.messages, "stream",
                          side_effect=lambda **kw: _FluxoFalso(_resp([_texto("Beleza, anotei.")]))), \
                claude_client.ao_texto(quebra):
            texto, _, _ = claude_client.chat([{"role": "user", "content": "oi"}], "ctx", [], {})
        self.assertEqual(texto, "Beleza, anotei.")


class RotaStreamTestCase(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()
        p = patch.object(chat_mod, "_decidir_rota", return_value="padrao")
        p.start()
        self.addCleanup(p.stop)

    def _post(self, corpo):
        res = self.client.post("/api/chat/stream", json=corpo)
        return res, res.get_data(as_text=True)

    def test_eventos_de_texto_e_fim_com_o_mesmo_corpo_do_chat(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            chat_mod._avisar("texto", "Bora, ")
            chat_mod._avisar("texto", "anotei.")
            return "Bora, anotei.", [], {"model": "x", "input_tokens": 1, "output_tokens": 1,
                                         "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
                                         "cost_usd": 0.0}

        with patch("claude_client.chat", side_effect=fake_chat):
            res, corpo = self._post({"mensagem": "o que voce acha da minha semana ate agora?"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/event-stream", res.headers["Content-Type"])
        eventos = _eventos_sse(corpo)
        self.assertEqual([d for ev, d in eventos if ev == "texto"], ["Bora, ", "anotei."])
        self.assertEqual(eventos[-1][0], "fim")
        fim = eventos[-1][1]
        self.assertEqual(fim["resumo_texto"], "Bora, anotei.")
        self.assertIn("cards", fim)
        # salvou no historico igual o /api/chat
        conn = db.get_db()
        try:
            n = conn.execute("SELECT COUNT(*) n FROM chat_mensagens").fetchone()["n"]
        finally:
            conn.close()
        self.assertEqual(n, 2)

    def test_erro_do_pipeline_vira_evento_de_erro(self):
        with patch("claude_client.chat", side_effect=RuntimeError("bug")):
            res, corpo = self._post({"mensagem": "oi tudo bem"})
        self.assertEqual(res.status_code, 200)
        eventos = _eventos_sse(corpo)
        self.assertEqual(eventos[-1][0], "erro")
        self.assertIn("error", eventos[-1][1])

    def test_validacao_igual_ao_chat(self):
        for corpo in ({"mensagem": ""}, {"mensagem": None}, {}, {"mensagem": "x" * 100000}):
            with self.subTest(corpo=str(corpo)[:30]):
                res = self.client.post("/api/chat/stream", json=corpo)
                self.assertEqual(res.status_code, 400)

    def test_exige_login(self):
        anonimo = app.app.test_client()
        res = anonimo.post("/api/chat/stream", json={"mensagem": "oi"})
        self.assertIn(res.status_code, (302, 401))


if __name__ == "__main__":
    unittest.main()
