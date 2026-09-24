"""Fase 7 / C1 - historia 10: regressao dos 500 que o fuzz
(scripts/ralph-c1-backend/fuzz.py) achou. Todos devem virar 4xx controlado."""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
from assistente import caixa  # noqa: E402

PIN_TESTE = "123456"
REGRA = {"gatilho": "horario", "condicao": {"tipo": "diario", "hora": "18:00"},
         "acao": {"mensagem": "lembrete sintetico"}, "texto": "todo dia 18h"}


class RobustezTestCase(unittest.TestCase):
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
        assert self.client.post("/login", json={"pin": PIN_TESTE}).status_code == 200

    def test_assinatura_com_valor_estranho_e_400_e_listagem_segue_ok(self):
        for valor in ("NaN", "Infinity", 1e308, True, "muito", [], {"x": 1}):
            with self.subTest(valor=valor):
                res = self.client.post("/api/financas/assinaturas",
                                       json={"nome": "Sintetica", "valor": valor, "dia_cobranca": 5})
                self.assertEqual(res.status_code, 400, res.get_json())
        res = self.client.post("/api/financas/assinaturas",
                               json={"nome": "Sintetica", "valor": 10, "dia_cobranca": True})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.client.get("/api/financas/assinaturas").status_code, 200)

    def test_data_invalida_nao_e_gravada(self):
        res = self.client.post("/api/financas/assinaturas",
                               json={"nome": "X", "valor": 10, "dia_cobranca": 5, "inicio": "2026-02-30"})
        self.assertEqual(res.status_code, 400)
        res = self.client.post("/api/financas/parcelas", json={
            "descricao": "Y", "valor_total": 100, "n_parcelas": 2, "primeira_parcela": "2026-99-01"})
        self.assertEqual(res.status_code, 400)
        for rota in ("/api/financas/assinaturas", "/api/financas/parcelas", "/api/financas/comprometido"):
            self.assertEqual(self.client.get(rota).status_code, 200, rota)

    def test_parcelas_demais_e_400(self):
        res = self.client.post("/api/financas/parcelas",
                               json={"descricao": "Z", "valor_parcela": 1, "n_parcelas": 100000})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.client.get("/api/financas/parcelas").status_code, 200)

    def test_patch_assinatura_com_valor_texto_e_400(self):
        self.client.post("/api/financas/assinaturas", json={"nome": "A", "valor": 10, "dia_cobranca": 5})
        res = self.client.patch("/api/financas/assinaturas/1", json={"valor": "muito"})
        self.assertEqual(res.status_code, 400)

    def test_p4_confirmar_e_pausar_com_corpo_lixo(self):
        for corpo in ([1, 2], "texto", {"texto_original": 123, "json": REGRA}):
            with self.subTest(corpo=corpo):
                res = self.client.post("/api/p4_regras/confirmar", json=corpo)
                self.assertEqual(res.status_code, 400)
        self.client.post("/api/p4_regras/confirmar", json={"texto_original": "t", "json": REGRA})
        self.assertLess(self.client.post("/api/p4_regras/1/pausar", json=[1]).status_code, 500)

    def test_caixa_responder_com_corpo_lixo(self):
        item_id = caixa.enfileirar("pergunta", "Pagou a conta sintetica?")
        for corpo in ({"resposta": 5}, "x", [1], {"resposta": "sim", "texto": 7}):
            with self.subTest(corpo=corpo):
                res = self.client.post(f"/api/assistente/caixa/{item_id}/responder", json=corpo)
                self.assertLess(res.status_code, 500)


if __name__ == "__main__":
    unittest.main()
