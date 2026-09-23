"""Fase 6 F3: US-F14 (Cotacoes - grafico + fechamento do modo visitante).

Gap real encontrado na faixa: /api/cotacoes (lista e detalhe) nunca tinha
ganhado a checagem de modo visitante que todo outro endpoint financeiro
(expenses/incomes/orcamentos...) ja tem - ver AGENTS.md/progress-f3.txt.
Segue o padrao de tests/test_modo_visitante_telas.py: confere o corpo
BRUTO da resposta, nao so campos estruturados, pra pegar qualquer
vazamento de valor."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402

PIN_TESTE = "123456"


class CotacoesModoVisitanteTestCase(unittest.TestCase):
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

    def _criar_cotacao_com_item(self, titulo="portas", fornecedor="Fornecedor Segredo", valor=54321.99):
        cotacao_id = self.client.post("/api/cotacoes", json={"titulo": titulo}).get_json()["id"]
        self.client.post(f"/api/cotacoes/{cotacao_id}/itens", json={"fornecedor": fornecedor, "valor": valor})
        return cotacao_id

    def test_lista_de_cotacoes_some_com_modo_visitante(self):
        self._criar_cotacao_com_item()
        antes = self.client.get("/api/cotacoes")
        self.assertIn(b"portas", antes.data)

        self._ativar_modo_visitante()
        res = self.client.get("/api/cotacoes")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), [])
        self.assertNotIn(b"portas", res.data)

    def test_detalhe_de_cotacao_bloqueado_com_modo_visitante(self):
        cotacao_id = self._criar_cotacao_com_item()
        self._ativar_modo_visitante()
        res = self.client.get(f"/api/cotacoes/{cotacao_id}")
        self.assertEqual(res.status_code, 403)
        self.assertNotIn(b"Fornecedor Segredo", res.data)
        self.assertNotIn(b"54321.99", res.data)

    def test_criar_cotacao_bloqueada_com_modo_visitante(self):
        self._ativar_modo_visitante()
        res = self.client.post("/api/cotacoes", json={"titulo": "nunca deveria existir"})
        self.assertEqual(res.status_code, 403)
        self.assertEqual(db.list_cotacoes(self.conn), [])

    def test_adicionar_item_bloqueado_com_modo_visitante(self):
        self.client.post("/api/modo-visitante", json={"ativar": False})  # garante desligado
        cotacao_id = self.client.post("/api/cotacoes", json={"titulo": "ferro"}).get_json()["id"]
        self._ativar_modo_visitante()
        res = self.client.post(f"/api/cotacoes/{cotacao_id}/itens", json={"fornecedor": "X", "valor": 100})
        self.assertEqual(res.status_code, 403)
        self.assertEqual(db.list_itens_cotacao(self.conn, cotacao_id), [])

    def test_dados_voltam_apos_desativar_modo_visitante(self):
        self._criar_cotacao_com_item()
        self._ativar_modo_visitante()
        self.assertEqual(self.client.get("/api/cotacoes").get_json(), [])

        res = self.client.post("/api/modo-visitante", json={"ativar": False, "pin": PIN_TESTE})
        self.assertEqual(res.status_code, 200)
        depois = self.client.get("/api/cotacoes")
        self.assertIn(b"portas", depois.data)


if __name__ == "__main__":
    unittest.main()
