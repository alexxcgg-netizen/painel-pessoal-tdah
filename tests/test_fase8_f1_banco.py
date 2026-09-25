"""Fase 8, faixa F1: sincronizacao Nubank (item ja autorizado via
PLUGGY_ITEM_ID_NUBANK) + lista unificada de gastos com selo de origem.

Nunca chama a Pluggy real - tests/conftest.py ja trava rede pra toda a
suite, e aqui tambem sempre usamos patch em pluggy_client.* por seguranca
dupla. Sobe o app.py inteiro (como tests/test_app.py) porque a rota usa
`app_modulo()` (rotas/_base.py) pra reaproveitar `_recusar_no_modo_visitante`
e `_categorizar_transacoes_importadas` de app.py."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402

PIN_TESTE = "123456"

ITEM_OK = {"status": "UPDATED", "connector": {"name": "Nubank"}}
CONTAS_OK = [{"id": "conta-1", "type": "BANK", "balance": 1000.0}]
TRANSACOES_OK = [
    {"id": "tx-1", "date": "2026-09-20T00:00:00Z", "amount": -50.0, "description": "IFOOD"},
]


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()
        conn = db.get_db()
        conn.execute("DELETE FROM memorias")
        auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
        conn.commit()
        conn.close()
        self.client = app.app.test_client()
        res = self.client.post("/login", json={"pin": PIN_TESTE})
        assert res.status_code == 200, res.get_json()
        self._env_original = dict(os.environ)
        os.environ["PLUGGY_CLIENT_ID"] = "id-fake"
        os.environ["PLUGGY_CLIENT_SECRET"] = "secret-fake"
        os.environ["PLUGGY_ITEM_ID_NUBANK"] = "item-fake"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env_original)


class SincronizarNubankTestCase(_BaseTestCase):
    @patch("pluggy_client.get_transactions", return_value=(TRANSACOES_OK, False))
    @patch("pluggy_client.get_accounts", return_value=CONTAS_OK)
    @patch("pluggy_client.get_item", return_value=ITEM_OK)
    def test_sincronizar_grava_transacoes_com_origem_nubank(self, *_mocks):
        resp = self.client.post("/api/bancos/sincronizar-nubank")
        self.assertEqual(resp.status_code, 200)
        corpo = resp.get_json()
        self.assertEqual(corpo["banco"], "nubank")
        self.assertEqual(corpo["contas"][0]["novas"], 1)

        conn = db.get_db()
        contas = db.list_bank_accounts(conn)
        self.assertEqual(len(contas), 1)
        self.assertEqual(contas[0]["banco"], "nubank")
        transacoes = db.list_all_bank_transactions(conn)
        self.assertEqual(len(transacoes), 1)
        self.assertEqual(transacoes[0]["descricao"], "IFOOD")
        conn.close()

    @patch("pluggy_client.get_transactions", return_value=(TRANSACOES_OK, False))
    @patch("pluggy_client.get_accounts", return_value=CONTAS_OK)
    @patch("pluggy_client.get_item", return_value=ITEM_OK)
    def test_sincronizar_nao_apaga_lancamento_manual(self, *_mocks):
        conn = db.get_db()
        conn.execute(
            "INSERT INTO expenses (amount, category, description, source_text, tipo) "
            "VALUES (?, ?, ?, ?, 'real')",
            (30.0, "mercado", "compra manual", "digitado no chat"),
        )
        conn.commit()
        conn.close()

        resp = self.client.post("/api/bancos/sincronizar-nubank")
        self.assertEqual(resp.status_code, 200)

        conn = db.get_db()
        manuais = conn.execute("SELECT * FROM expenses WHERE tipo = 'real'").fetchall()
        conn.close()
        self.assertEqual(len(manuais), 1)
        self.assertEqual(manuais[0]["description"], "compra manual")

    def test_sem_item_id_configurado_devolve_erro_sem_chamar_pluggy(self):
        del os.environ["PLUGGY_ITEM_ID_NUBANK"]
        with patch("pluggy_client.get_item") as mock_get_item:
            resp = self.client.post("/api/bancos/sincronizar-nubank")
            mock_get_item.assert_not_called()
        self.assertEqual(resp.status_code, 400)

    def test_erro_404_da_pluggy_vira_mensagem_amigavel_sem_vazar_segredo(self):
        resposta_falsa = requests.Response()
        resposta_falsa.status_code = 404
        resposta_falsa._content = b'{"code":"ITEM_NOT_FOUND","message":"corpo cru da pluggy"}'
        erro = requests.HTTPError(response=resposta_falsa)
        with patch("pluggy_client.get_item", side_effect=erro):
            resp = self.client.post("/api/bancos/sincronizar-nubank")
        self.assertEqual(resp.status_code, 404)
        corpo = resp.get_json()
        self.assertIn("reconectar", corpo["error"])
        texto = resp.get_data(as_text=True)
        self.assertNotIn("secret-fake", texto)
        self.assertNotIn("ITEM_NOT_FOUND", texto)
        self.assertNotIn("corpo cru da pluggy", texto)


class GastosUnificadosTestCase(_BaseTestCase):
    def test_lista_unificada_traz_manual_e_banco_com_origem_certa(self):
        conn = db.get_db()
        conn.execute(
            "INSERT INTO expenses (amount, category, description, source_text, tipo) "
            "VALUES (?, ?, ?, ?, 'real')",
            (20.0, "mercado", "padaria", "digitado no chat"),
        )
        conta_id = db.get_or_create_bank_account(conn, "nubank", "conta")
        db.insert_bank_transactions(
            conn,
            conta_id,
            [{"external_id": "tx-9", "data": "2026-09-21", "valor": -75.0, "descricao": "UBER", "categoria": "transporte"}],
        )
        conn.commit()
        conn.close()

        resp = self.client.get("/api/gastos/unificados")
        self.assertEqual(resp.status_code, 200)
        itens = resp.get_json()
        origens = {i["description"]: i["origem"] for i in itens}
        self.assertEqual(origens["padaria"], "manual")
        self.assertEqual(origens["UBER"], "Nubank")

    def test_lista_unificada_vazia_sem_lancamentos(self):
        resp = self.client.get("/api/gastos/unificados")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), [])


if __name__ == "__main__":
    unittest.main()
