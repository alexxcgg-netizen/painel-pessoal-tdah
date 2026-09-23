import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import claude_client
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"

import app  # noqa: E402

PIN_TESTE = "123456"


class ModoVisitanteTelasTestCase(unittest.TestCase):
    """US-C20: garante que o dado sensivel nao aparece no corpo da RESPOSTA
    (nao so escondido via CSS) quando o modo visitante esta ativo - testa o
    texto bruto de cada resposta, nao so campos estruturados especificos,
    pra pegar qualquer vazamento (ex: valor aparecendo dentro de um texto
    livre gerado por IA)."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        self.conn = conn
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()

    def tearDown(self):
        self.conn.close()

    def _ativar_modo_visitante(self):
        res = self.client.post("/api/modo-visitante", json={"ativar": True})
        assert res.status_code == 200

    # ---- financeiro ----

    def test_expenses_some_com_modo_visitante(self):
        self.conn.execute(
            "INSERT INTO expenses (amount, category, description, tipo) VALUES (7777.77, 'segredo-financeiro', 'x', 'real')"
        )
        self.conn.commit()
        antes = self.client.get("/api/expenses")
        self.assertIn(b"segredo-financeiro", antes.data)

        self._ativar_modo_visitante()
        res = self.client.get("/api/expenses")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), [])
        self.assertNotIn(b"segredo-financeiro", res.data)
        self.assertNotIn(b"7777.77", res.data)

    def test_summary_today_oculta_gasto_e_nao_chama_ia(self):
        self.conn.execute(
            "INSERT INTO expenses (amount, category, description, tipo) VALUES (9999.99, 'valor-secreto', 'x', 'real')"
        )
        self.conn.commit()
        self._ativar_modo_visitante()
        with patch.object(claude_client.client.messages, "create") as mock_create:
            res = self.client.get("/api/summary/today")
        self.assertEqual(res.status_code, 200)
        mock_create.assert_not_called()
        dados = res.get_json()
        self.assertIsNone(dados["gasto_hoje"])
        self.assertIsNone(dados["gasto_planejado"])
        self.assertNotIn(b"9999.99", res.data)
        self.assertNotIn(b"valor-secreto", res.data)

    def test_summary_today_normal_sem_modo_visitante(self):
        conteudo = [SimpleNamespace(type="text", text="Resumo normal do dia.")]
        resp = SimpleNamespace(
            content=conteudo,
            stop_reason="end_turn",
            model=claude_client.SONNET,
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        with patch.object(claude_client.client.messages, "create", return_value=resp):
            res = self.client.get("/api/summary/today")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["gasto_hoje"], 0)

    def test_outros_endpoints_financeiros_somem_com_modo_visitante(self):
        self.conn.execute(
            "INSERT INTO expenses (amount, category, description, tipo) VALUES (321.0, 'categoria-secreta', 'x', 'real')"
        )
        self.conn.execute(
            "INSERT INTO incomes (amount, category, description) VALUES (5000.0, 'salario-secreto', 'x')"
        )
        self.conn.commit()
        db.definir_orcamento(self.conn, "categoria-secreta", 100.0)

        self._ativar_modo_visitante()
        for url in (
            "/api/incomes",
            "/api/orcamentos",
            "/api/gastos-fixos",
            "/api/expenses/historico",
        ):
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, url)
            self.assertEqual(res.get_json(), [], url)
            self.assertNotIn(b"secreto", res.data, url)

        res_semanal = self.client.get("/api/gastos/resumo-semanal")
        self.assertEqual(res_semanal.get_json()["total_semana"], 0)

        res_sobra = self.client.get("/api/sobra-do-mes")
        dados_sobra = res_sobra.get_json()
        self.assertEqual(dados_sobra["renda_mes"], 0)
        self.assertEqual(dados_sobra["gasto_mes"], 0)
        self.assertNotIn(b"321.0", res_sobra.data)
        self.assertNotIn(b"5000.0", res_sobra.data)

    # ---- saude ----

    def test_saude_hoje_oculta_com_modo_visitante(self):
        hoje = date.today().isoformat()
        db.upsert_saude_dia(self.conn, hoje, {"passos": 12345, "sono_horas": 6.5})
        antes = self.client.get("/api/saude/hoje")
        self.assertIn(b"passos", antes.data)

        self._ativar_modo_visitante()
        res = self.client.get("/api/saude/hoje")
        self.assertEqual(res.status_code, 200)
        dados = res.get_json()
        self.assertIsNone(dados["dados"])
        self.assertTrue(dados.get("oculto"))
        self.assertNotIn(b"12345", res.data)

    def test_medidas_somem_com_modo_visitante(self):
        db.create_medida_corporal(self.conn, "peso", 88.8, "kg", "2026-06-01")
        antes = self.client.get("/api/medidas")
        self.assertIn(b"88.8", antes.data)

        self._ativar_modo_visitante()
        res = self.client.get("/api/medidas")
        self.assertEqual(res.get_json(), [])
        self.assertNotIn(b"88.8", res.data)

    # ---- diario de decisao ----

    def test_decisoes_somem_com_modo_visitante(self):
        db.create_decisao(self.conn, "devo pedir demissao segredo-x", json.dumps({"resumo": "sim"}))
        antes = self.client.get("/api/decisoes")
        self.assertIn(b"segredo-x", antes.data)

        self._ativar_modo_visitante()
        res = self.client.get("/api/decisoes")
        self.assertEqual(res.get_json(), [])
        self.assertNotIn(b"segredo-x", res.data)

    def test_criar_decisao_bloqueada_com_modo_visitante(self):
        self._ativar_modo_visitante()
        with patch.object(claude_client.client.messages, "create") as mock_create:
            res = self.client.post("/api/decisao", json={"pergunta": "vale a pena trocar de emprego"})
        self.assertEqual(res.status_code, 403)
        mock_create.assert_not_called()
        self.assertEqual(db.list_decisoes(self.conn), [])

    # ---- desativando volta tudo ao normal ----

    def test_dados_voltam_apos_desativar_com_pin(self):
        self.conn.execute(
            "INSERT INTO expenses (amount, category, description, tipo) VALUES (50.0, 'mercado', 'x', 'real')"
        )
        self.conn.commit()
        self._ativar_modo_visitante()
        self.assertEqual(self.client.get("/api/expenses").get_json(), [])

        res = self.client.post("/api/modo-visitante", json={"ativar": False, "pin": PIN_TESTE})
        self.assertEqual(res.status_code, 200)
        depois = self.client.get("/api/expenses").get_json()
        self.assertEqual(len(depois), 1)
        self.assertEqual(depois[0]["category"], "mercado")


if __name__ == "__main__":
    unittest.main()
