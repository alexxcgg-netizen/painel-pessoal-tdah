"""Fase 9, Faixa F9-sync: idempotencia de verdade na sincronizacao Pluggy
(Nubank) - upsert por external_id (novas/atualizadas/sem_mudanca), colunas
ricas da transacao e a migracao que limpa as duplicatas do incidente de
reconexao do item Pluggy (ver CHANGELOG 2026-09-25). Nunca chama Pluggy de
verdade (tudo mockado) nem le o .env real - mesmo padrao de
tests/test_fase8_f1_banco.py."""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402
import pluggy_client  # noqa: E402

PIN_TESTE = "123456"

ITEM_OK = {"status": "UPDATED", "connector": {"name": "Nubank"}}
CONTAS_OK = [{"id": "conta-1", "type": "BANK", "balance": 1000.0}]
TRANSACOES_V1 = [
    {
        "id": "tx-1",
        "date": "2026-09-20T00:00:00Z",
        "amount": -50.0,
        "description": "IFOOD *RESTAURANTE",
        "category": "Alimentacao",
        "type": "DEBIT",
        "merchant": {"name": "iFood", "businessName": "IFOOD.COM"},
    },
]
TRANSACOES_V2_MUDOU = [
    {
        "id": "tx-1",
        "date": "2026-09-20T00:00:00Z",
        "amount": -55.0,  # valor corrigido pela Pluggy
        "description": "IFOOD *RESTAURANTE XPTO",
        "category": "Alimentacao",
        "type": "DEBIT",
        "merchant": {"name": "iFood", "businessName": "IFOOD.COM"},
    },
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


class IdempotenciaTestCase(_BaseTestCase):
    @patch("pluggy_client.get_transactions", return_value=TRANSACOES_V1)
    @patch("pluggy_client.get_accounts", return_value=CONTAS_OK)
    @patch("pluggy_client.get_item", return_value=ITEM_OK)
    def test_dez_sincronizacoes_iguais_nao_duplicam(self, *_mocks):
        for i in range(10):
            resp = self.client.post("/api/bancos/sincronizar-nubank")
            self.assertEqual(resp.status_code, 200)
            corpo = resp.get_json()
            self.assertTrue(corpo["ok"])
            if i == 0:
                self.assertEqual(corpo["novas"], 1)
                self.assertEqual(corpo["atualizadas"], 0)
            else:
                self.assertEqual(corpo["novas"], 0)
                self.assertEqual(corpo["atualizadas"], 0)
                self.assertEqual(corpo["sem_mudanca"], 1)

        conn = db.get_db()
        total = conn.execute("SELECT COUNT(*) c FROM bank_transactions").fetchone()["c"]
        conn.close()
        self.assertEqual(total, 1)

    @patch("pluggy_client.get_accounts", return_value=CONTAS_OK)
    @patch("pluggy_client.get_item", return_value=ITEM_OK)
    def test_transacao_que_mudou_atualiza_sem_criar_linha_nova(self, mock_item, mock_accounts):
        with patch("pluggy_client.get_transactions", return_value=TRANSACOES_V1):
            resp1 = self.client.post("/api/bancos/sincronizar-nubank")
        self.assertEqual(resp1.get_json()["novas"], 1)

        with patch("pluggy_client.get_transactions", return_value=TRANSACOES_V2_MUDOU):
            resp2 = self.client.post("/api/bancos/sincronizar-nubank")
        corpo2 = resp2.get_json()
        self.assertEqual(corpo2["novas"], 0)
        self.assertEqual(corpo2["atualizadas"], 1)

        conn = db.get_db()
        linhas = conn.execute("SELECT * FROM bank_transactions").fetchall()
        conn.close()
        self.assertEqual(len(linhas), 1)
        self.assertEqual(db.criptografia.descriptografar(linhas[0]["descricao"]), "IFOOD *RESTAURANTE XPTO")
        self.assertEqual(db._dnum(linhas[0]["valor"], float), -55.0)

    @patch("pluggy_client.get_transactions", return_value=TRANSACOES_V1)
    @patch("pluggy_client.get_accounts", return_value=CONTAS_OK)
    @patch("pluggy_client.get_item", return_value=ITEM_OK)
    def test_grava_colunas_ricas_do_pluggy(self, *_mocks):
        self.client.post("/api/bancos/sincronizar-nubank")
        conn = db.get_db()
        linha = conn.execute("SELECT * FROM bank_transactions").fetchone()
        conn.close()
        self.assertEqual(linha["estabelecimento"], "IFOOD.COM")
        self.assertEqual(linha["categoria_pluggy"], "Alimentacao")
        self.assertEqual(linha["descricao_original"], "IFOOD *RESTAURANTE")
        self.assertEqual(linha["tipo_operacao"], "DEBIT")
        self.assertIsNone(linha["estorno_de_external_id"])


class CartaoContaTestCase(_BaseTestCase):
    @patch("pluggy_client.get_accounts", return_value=[
        {"id": "conta-1", "type": "BANK", "balance": 1000.0},
        {"id": "cartao-1", "type": "CREDIT", "balance": 320.5},
    ])
    @patch("pluggy_client.get_item", return_value=ITEM_OK)
    def test_conta_e_cartao_viram_linhas_separadas_com_saldo_proprio(self, mock_item, mock_accounts):
        transacoes_por_conta = {
            "conta-1": [{"id": "tx-conta", "date": "2026-09-20", "amount": -10.0, "description": "PIX"}],
            "cartao-1": [{"id": "tx-cartao", "date": "2026-09-20", "amount": -200.0, "description": "COMPRA CARTAO"}],
        }
        with patch("pluggy_client.get_transactions", side_effect=lambda conta_id: transacoes_por_conta[conta_id]):
            resp = self.client.post("/api/bancos/sincronizar-nubank")
        self.assertEqual(resp.status_code, 200)

        conn = db.get_db()
        contas = {c["tipo"]: c for c in db.list_bank_accounts(conn)}
        conn.close()
        self.assertEqual(set(contas), {"conta", "cartao"})
        self.assertEqual(contas["conta"]["saldo"], 1000.0)
        self.assertEqual(contas["cartao"]["saldo"], 320.5)


class NormalizarTransacoesTestCase(unittest.TestCase):
    def test_campos_ricos_extraidos_da_resposta_pluggy(self):
        normalizadas = pluggy_client.normalizar_transacoes(TRANSACOES_V1)
        self.assertEqual(len(normalizadas), 1)
        t = normalizadas[0]
        self.assertEqual(t["external_id"], "tx-1")
        self.assertEqual(t["estabelecimento"], "IFOOD.COM")
        self.assertEqual(t["categoria_pluggy"], "Alimentacao")
        self.assertEqual(t["tipo_operacao"], "DEBIT")
        self.assertIsNone(t["estorno_de_external_id"])


class MigracaoLimpaDuplicataTestCase(unittest.TestCase):
    """Testa o DELETE da migracao 202609251300_f9_sync.sql isolado (roda o
    SQL direto num banco de teste), sem depender do runner de migracoes (que
    so aplica um arquivo uma vez por banco)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.caminho = Path(self._tmp.name) / "dedup.db"

    def _bank_transactions_com(self, linhas):
        conn = sqlite3.connect(self.caminho)
        conn.execute(
            """CREATE TABLE bank_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank_account_id INTEGER NOT NULL,
                data TEXT NOT NULL,
                descricao TEXT,
                valor REAL NOT NULL,
                external_id TEXT NOT NULL,
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            )"""
        )
        for l in linhas:
            conn.execute(
                "INSERT INTO bank_transactions (bank_account_id, data, descricao, valor, external_id) "
                "VALUES (?, ?, ?, ?, ?)",
                l,
            )
        conn.commit()
        return conn

    def _sql_dedup(self):
        texto = (Path(__file__).parent.parent / "migracoes" / "202609251300_f9_sync.sql").read_text()
        # so o bloco do DELETE (as colunas novas ja nao existem nesta tabela de teste minima)
        inicio = texto.index("DELETE FROM bank_transactions")
        return texto[inicio:]

    def test_remove_duplicata_reimportada_mantendo_a_mais_antiga(self):
        conn = self._bank_transactions_com([
            (1, "2026-09-01", "UBER", -20.0, "old-1"),
            (1, "2026-09-01", "UBER", -20.0, "new-1-apos-reconexao"),
        ])
        conn.executescript(self._sql_dedup())
        conn.commit()
        linhas = conn.execute("SELECT external_id FROM bank_transactions").fetchall()
        self.assertEqual([r[0] for r in linhas], ["old-1"])
        conn.close()

    def test_nao_remove_transacao_unica(self):
        conn = self._bank_transactions_com([
            (1, "2026-09-01", "MERCADO", -30.0, "unica-1"),
            (1, "2026-09-02", "MERCADO", -30.0, "unica-2"),  # data diferente, nao e duplicata
        ])
        conn.executescript(self._sql_dedup())
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM bank_transactions").fetchone()[0]
        self.assertEqual(total, 2)
        conn.close()


if __name__ == "__main__":
    unittest.main()
