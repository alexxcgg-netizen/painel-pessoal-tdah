"""Fase 7 / C1 - historia 1: chat com o historico da A5 e medicao nova.

- fonte unica do gasto do mes (ia.medicao.gasto_mes_atual): cada chamada
  conta uma vez, mesmo gravada em uso_ia (nova) e api_usage (antiga);
- teto unico (ia.teto, sem teto por padrao) vale pro chat, intent e nota fiscal;
- historico: resumo da A5 no contexto_fixo e so o que nao foi resumido na
  integra (nunca os dois).

Tudo com duble: o cliente Anthropic e mockado (nenhuma chamada real) e o
banco e temporario (nunca o data/painel.db)."""
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
from ia import historico, medicao, teto  # noqa: E402
from ia.funcoes import chat as chat_mod  # noqa: E402

PIN_TESTE = "123456"


def _resp_texto(texto, in_tok=1000, out_tok=100):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=texto)],
        stop_reason="end_turn",
        model="claude-sonnet-5",
        usage=SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok,
                              cache_read_input_tokens=0, cache_creation_input_tokens=0),
    )


class _Base(unittest.TestCase):
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
        # roteador A14 fora do caminho: sempre o chat padrao com tools
        p = patch.object(chat_mod, "_decidir_rota", return_value="padrao")
        p.start()
        self.addCleanup(p.stop)

    def _contar(self, tabela):
        conn = db.get_db()
        try:
            return conn.execute(f"SELECT COUNT(*) AS n FROM {tabela}").fetchone()["n"]
        finally:
            conn.close()

    def _gravar_uso_ia(self, custo_usd):
        medicao.registrar_uso("chat", "anthropic", "claude-sonnet-5", custo_usd=custo_usd)


class FonteUnicaDoGastoTestCase(_Base):
    def test_chat_de_verdade_conta_uma_vez_so_no_gasto_do_mes(self):
        with patch.object(claude_client.client.messages, "create",
                          return_value=_resp_texto("Oi!", in_tok=1000, out_tok=100)) as create:
            res = self.client.post("/api/chat", json={"mensagem": "me conta uma piada"})
        self.assertEqual(res.status_code, 200, res.get_json())
        create.assert_called_once()
        # a mesma chamada foi pras duas tabelas...
        self.assertEqual(self._contar("uso_ia"), 1)
        self.assertEqual(self._contar("api_usage"), 1)
        conn = db.get_db()
        custo_novo = conn.execute("SELECT custo_usd FROM uso_ia").fetchone()["custo_usd"]
        custo_antigo = conn.execute("SELECT cost_usd FROM api_usage").fetchone()["cost_usd"]
        conn.close()
        self.assertGreater(custo_novo, 0)
        self.assertAlmostEqual(custo_novo, custo_antigo, places=9)
        # ...mas o gasto do mes conta uma vez so
        self.assertAlmostEqual(medicao.gasto_mes_atual(), custo_novo, places=9)

    def test_duas_mensagens_somam_duas_chamadas_nao_quatro(self):
        with patch.object(claude_client.client.messages, "create",
                          return_value=_resp_texto("ok", in_tok=500, out_tok=50)):
            self.client.post("/api/chat", json={"mensagem": "primeira"})
            self.client.post("/api/chat", json={"mensagem": "segunda"})
        conn = db.get_db()
        soma_nova = conn.execute("SELECT SUM(custo_usd) AS s FROM uso_ia").fetchone()["s"]
        conn.close()
        self.assertEqual(self._contar("uso_ia"), 2)
        self.assertAlmostEqual(medicao.gasto_mes_atual(), soma_nova, places=9)

    def test_legado_antes_da_medicao_nova_entra_no_gasto(self):
        # mes da virada: gasto antigo (so api_usage) antes da 1a linha de uso_ia
        conn = db.get_db()
        conn.execute("INSERT INTO api_usage (model, input_tokens, output_tokens, cost_usd, feature, created_at) "
                     "VALUES ('x', 1, 1, 2.0, 'chat', datetime('now', '-1 minute'))")
        conn.commit()
        conn.close()
        self._gravar_uso_ia(0.5)
        self.assertAlmostEqual(medicao.gasto_mes_atual(), 2.5, places=9)

    def test_legado_depois_da_medicao_nova_nao_duplica(self):
        self._gravar_uso_ia(0.5)
        conn = db.get_db()
        conn.execute("INSERT INTO api_usage (model, input_tokens, output_tokens, cost_usd, feature, created_at) "
                     "VALUES ('x', 1, 1, 0.5, 'chat', datetime('now', '+1 minute'))")
        conn.commit()
        conn.close()
        self.assertAlmostEqual(medicao.gasto_mes_atual(), 0.5, places=9)

    def test_so_legado_conta_tudo(self):
        conn = db.get_db()
        db.record_usage(conn, "x", 1, 1, 3.0, "chat")
        conn.close()
        self.assertAlmostEqual(medicao.gasto_mes_atual(), 3.0, places=9)

    def test_banco_sem_tabela_antiga_nao_quebra(self):
        conn = db.get_db()
        conn.execute("DROP TABLE api_usage")
        conn.commit()
        conn.close()
        self._gravar_uso_ia(0.25)
        self.assertAlmostEqual(medicao.gasto_mes_atual(), 0.25, places=9)


class TetoUnicoTestCase(_Base):
    def _estourar_teto(self):
        conn = db.get_db()
        db.definir_teto_mensal_ia(conn, 1.0)  # USD
        conn.commit()
        conn.close()
        self._gravar_uso_ia(1.01)

    def test_sem_teto_configurado_gasto_alto_nao_bloqueia_nada(self):
        self._gravar_uso_ia(10000.0)
        self.assertFalse(app._teto_ia_estourado("chat"))
        self.assertFalse(app._teto_ia_estourado("intent"))
        self.assertFalse(app._teto_ia_estourado("nota_fiscal"))

    def test_teto_configurado_bloqueia_o_chat(self):
        self._estourar_teto()
        with patch.object(claude_client.client.messages, "create") as create:
            res = self.client.post("/api/chat", json={"mensagem": "me conta uma piada"})
        self.assertEqual(res.status_code, 402)
        self.assertEqual(res.get_json()["error"], app.TETO_IA_MSG)
        create.assert_not_called()

    def test_teto_configurado_bloqueia_intent(self):
        self._estourar_teto()
        with patch("claude_client.classify_intent") as mock_classify:
            res = self.client.post("/api/intent/classificar", json={"texto": "texto nunca visto antes"})
        mock_classify.assert_not_called()
        self.assertTrue(res.get_json()["teto_ia_estourado"])

    def test_teto_configurado_em_usd_vale_convertido(self):
        conn = db.get_db()
        db.definir_teto_mensal_ia(conn, 1.0)  # USD -> R$5,50
        conn.commit()
        conn.close()
        self._gravar_uso_ia(1.01)
        self.assertTrue(app._teto_ia_estourado("chat"))

    def test_abaixo_do_teto_libera(self):
        self._gravar_uso_ia(0.01)
        self.assertFalse(app._teto_ia_estourado("chat"))

    def test_erro_no_calculo_do_teto_bloqueia(self):
        with patch("ia.teto.teto_permite", side_effect=RuntimeError("banco travado")):
            self.assertTrue(app._teto_ia_estourado("chat"))

    def test_nota_fiscal_respeita_o_teto_unico(self):
        self._estourar_teto()
        import base64
        with patch("claude_client.extrair_nota_fiscal_foto") as extrair:
            res = self.client.post("/api/notas-fiscais/extrair", json={
                "imagem_base64": base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 50).decode(),
                "media_type": "image/png",
            })
        extrair.assert_not_called()
        self.assertEqual(res.status_code, 402)


class HistoricoA5NoChatTestCase(_Base):
    def _inserir_mensagens(self, n):
        conn = db.get_db()
        ids = []
        for i in range(n):
            papel = "user" if i % 2 == 0 else "assistant"
            cur = conn.execute("INSERT INTO chat_mensagens (papel, texto) VALUES (?, ?)",
                               (papel, f"mensagem-{i:02d}"))
            ids.append(cur.lastrowid)
        conn.commit()
        conn.close()
        return ids

    def _textos_enviados(self, kwargs):
        textos = []
        for m in kwargs["messages"]:
            for b in m["content"]:
                if isinstance(b, dict) and b.get("type") == "text":
                    textos.append(b["text"])
        return "\n".join(textos)

    def test_resumo_vai_no_contexto_fixo_e_resumidas_nao_repetem(self):
        ids = self._inserir_mensagens(30)
        conn = db.get_db()
        historico._salvar_estado(conn, "RESUMO-SINTETICO do comeco", ids[9], "2099-01-01")
        conn.close()
        with patch.object(historico, "precisa_reconstruir", return_value=False), \
                patch.object(claude_client.client.messages, "create",
                             return_value=_resp_texto("ok")) as create:
            res = self.client.post("/api/chat", json={"mensagem": "e agora?"})
        self.assertEqual(res.status_code, 200, res.get_json())
        enviado = self._textos_enviados(create.call_args.kwargs)
        self.assertIn("RESUMO-SINTETICO do comeco", enviado)
        for i in range(10):  # ids[0..9] estao no resumo: nunca na integra
            self.assertNotIn(f"mensagem-{i:02d}", enviado)
        for i in range(10, 30):  # o resto (20) vai literal, sem buraco
            self.assertIn(f"mensagem-{i:02d}", enviado)
        self.assertIn("e agora?", enviado)

    def test_sem_resumo_manda_no_maximo_o_teto_literal(self):
        self._inserir_mensagens(40)
        with patch.object(historico, "precisa_reconstruir", return_value=False), \
                patch.object(claude_client.client.messages, "create",
                             return_value=_resp_texto("ok")) as create:
            self.client.post("/api/chat", json={"mensagem": "oi"})
        enviado = self._textos_enviados(create.call_args.kwargs)
        presentes = [i for i in range(40) if f"mensagem-{i:02d}" in enviado]
        self.assertEqual(len(presentes), historico.MENSAGENS_LITERAIS_MAX)
        self.assertEqual(presentes[-1], 39)

    def test_falha_na_a5_cai_no_historico_antigo(self):
        self._inserir_mensagens(4)
        with patch.object(historico, "montar_contexto", side_effect=RuntimeError("tabela sumiu")), \
                patch.object(claude_client.client.messages, "create",
                             return_value=_resp_texto("ok")) as create:
            res = self.client.post("/api/chat", json={"mensagem": "oi de novo"})
        self.assertEqual(res.status_code, 200)
        enviado = self._textos_enviados(create.call_args.kwargs)
        self.assertIn("mensagem-00", enviado)
        self.assertIn("oi de novo", enviado)

    def test_app_liga_medir_uso_e_conn_no_chat(self):
        vistos = {}

        def fake_chat(mensagens, contexto, memorias, executores):
            opcoes = chat_mod._OPCOES_CHAT.get()
            vistos.update(opcoes)
            vistos["ultima"] = mensagens[-1]
            return "ok", [], {"model": "m", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0}

        with patch.object(historico, "montar_contexto",
                          return_value={"contexto_fixo": "RESUMO", "mensagens": []}), \
                patch("claude_client.chat", side_effect=fake_chat):
            self.client.post("/api/chat", json={"mensagem": "tudo certo?"})
        self.assertTrue(vistos["medir_uso"])
        self.assertIsNotNone(vistos["conn"])
        self.assertEqual(vistos["contexto_fixo"], "RESUMO")
        self.assertEqual(vistos["ultima"], {"role": "user", "content": "tudo certo?"})
        # fora do `with`, as opcoes somem (nao vazam pra outra chamada)
        self.assertIsNone(chat_mod._OPCOES_CHAT.get())

    def test_kwarg_explicito_ganha_da_opcao_do_contexto(self):
        with chat_mod.opcoes_chat(contexto_fixo="DO CONTEXTO", medir_uso=True), \
                patch("ia.teto.teto_permite", return_value=True), \
                patch("ia.medicao.registrar_uso") as reg, \
                patch.object(claude_client.client.messages, "create",
                             return_value=_resp_texto("ok")) as create:
            claude_client.chat([{"role": "user", "content": "oi"}], "ctx", [], {},
                               contexto_fixo="EXPLICITO", medir_uso=False)
        enviado = self._textos_enviados(create.call_args.kwargs)
        self.assertIn("EXPLICITO", enviado)
        self.assertNotIn("DO CONTEXTO", enviado)
        reg.assert_not_called()


if __name__ == "__main__":
    unittest.main()
