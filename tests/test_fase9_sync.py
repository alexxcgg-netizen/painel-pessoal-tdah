"""Fase 9, Faixa F9-sync: idempotencia de verdade na sincronizacao Pluggy
(Nubank) - upsert por external_id (novas/atualizadas/sem_mudanca) + colunas
ricas da transacao + reconciliacao (remocao) das transacoes que sumiram
quando o item Pluggy e reconectado e reimporta o historico com um novo
conjunto de ids (ver CHANGELOG 2026-09-25). Nunca chama Pluggy de verdade
(tudo mockado) nem le o .env real - mesmo padrao de
tests/test_fase8_f1_banco.py."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

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


def _tx(tx_id: str, dia: int, valor: float = -10.0, descricao: str = "COMPRA") -> dict:
    return {
        "id": tx_id,
        "date": f"2026-09-{dia:02d}T00:00:00Z",
        "amount": valor,
        "description": descricao,
    }


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

    def _total_linhas(self, bank_account_id=None):
        conn = db.get_db()
        if bank_account_id is None:
            total = conn.execute("SELECT COUNT(*) c FROM bank_transactions").fetchone()["c"]
        else:
            total = conn.execute(
                "SELECT COUNT(*) c FROM bank_transactions WHERE bank_account_id = ?",
                (bank_account_id,),
            ).fetchone()["c"]
        conn.close()
        return total

    def _ids_existentes(self, bank_account_id=None):
        conn = db.get_db()
        if bank_account_id is None:
            rows = conn.execute("SELECT external_id FROM bank_transactions").fetchall()
        else:
            rows = conn.execute(
                "SELECT external_id FROM bank_transactions WHERE bank_account_id = ?",
                (bank_account_id,),
            ).fetchall()
        conn.close()
        return {r["external_id"] for r in rows}


class IdempotenciaTestCase(_BaseTestCase):
    @patch("pluggy_client.get_transactions", return_value=(TRANSACOES_V1, False))
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
                self.assertEqual(corpo["removidas"], 0)

        self.assertEqual(self._total_linhas(), 1)

    @patch("pluggy_client.get_accounts", return_value=CONTAS_OK)
    @patch("pluggy_client.get_item", return_value=ITEM_OK)
    def test_transacao_que_mudou_atualiza_sem_criar_linha_nova(self, mock_item, mock_accounts):
        with patch("pluggy_client.get_transactions", return_value=(TRANSACOES_V1, False)):
            resp1 = self.client.post("/api/bancos/sincronizar-nubank")
        self.assertEqual(resp1.get_json()["novas"], 1)

        with patch("pluggy_client.get_transactions", return_value=(TRANSACOES_V2_MUDOU, False)):
            resp2 = self.client.post("/api/bancos/sincronizar-nubank")
        corpo2 = resp2.get_json()
        self.assertEqual(corpo2["novas"], 0)
        self.assertEqual(corpo2["atualizadas"], 1)
        self.assertEqual(corpo2["removidas"], 0)

        conn = db.get_db()
        linhas = conn.execute("SELECT * FROM bank_transactions").fetchall()
        conn.close()
        self.assertEqual(len(linhas), 1)
        self.assertEqual(db.criptografia.descriptografar(linhas[0]["descricao"]), "IFOOD *RESTAURANTE XPTO")
        self.assertEqual(db._dnum(linhas[0]["valor"], float), -55.0)

    @patch("pluggy_client.get_transactions", return_value=(TRANSACOES_V1, False))
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
        with patch(
            "pluggy_client.get_transactions",
            side_effect=lambda conta_id: (transacoes_por_conta[conta_id], False),
        ):
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


class ReconciliacaoTestCase(_BaseTestCase):
    """Faixa F9-sync: depois do upsert, o que a Pluggy devolveu na leva
    atual e a fonte da verdade pro intervalo de datas dessa leva - apaga o
    que sumiu (mesma conta, mesmo intervalo, external_id que nao veio mais)
    e nunca apaga o que esta fora do intervalo ou quando a busca nao pode
    ser confiada (truncada/vazia)."""

    @patch("pluggy_client.get_accounts", return_value=CONTAS_OK)
    @patch("pluggy_client.get_item", return_value=ITEM_OK)
    def test_reconexao_com_ids_novos_remove_as_antigas(self, mock_item, mock_accounts):
        lote_a = [_tx(f"A{i}", 18 + i) for i in range(5)]
        lote_b = [_tx(f"B{i}", 18 + i) for i in range(5)]  # mesmas datas, ids novos

        with patch("pluggy_client.get_transactions", return_value=(lote_a, False)):
            resp1 = self.client.post("/api/bancos/sincronizar-nubank")
        self.assertEqual(resp1.get_json()["novas"], 5)

        with patch("pluggy_client.get_transactions", return_value=(lote_b, False)):
            resp2 = self.client.post("/api/bancos/sincronizar-nubank")
        corpo2 = resp2.get_json()
        self.assertEqual(corpo2["novas"], 5)
        self.assertEqual(corpo2["removidas"], 5)

        self.assertEqual(self._total_linhas(), 5)
        self.assertEqual(self._ids_existentes(), {f"B{i}" for i in range(5)})

    @patch("pluggy_client.get_accounts", return_value=CONTAS_OK)
    @patch("pluggy_client.get_item", return_value=ITEM_OK)
    def test_duas_compras_iguais_no_mesmo_dia_nao_se_apagam(self, mock_item, mock_accounts):
        lote = [
            _tx("cafe-1", 20, valor=-8.0, descricao="CAFE"),
            _tx("cafe-2", 20, valor=-8.0, descricao="CAFE"),
        ]
        with patch("pluggy_client.get_transactions", return_value=(lote, False)):
            resp = self.client.post("/api/bancos/sincronizar-nubank")
        self.assertEqual(resp.get_json()["removidas"], 0)
        self.assertEqual(self._total_linhas(), 2)

    @patch("pluggy_client.get_accounts", return_value=CONTAS_OK)
    @patch("pluggy_client.get_item", return_value=ITEM_OK)
    def test_transacao_antiga_fora_do_intervalo_devolvido_fica(self, mock_item, mock_accounts):
        antiga = _tx("old-1", 1, valor=-99.0, descricao="ALUGUEL")  # fora da janela recente
        recentes = [_tx(f"R{i}", 18 + i) for i in range(3)]
        with patch("pluggy_client.get_transactions", return_value=([antiga] + recentes, False)):
            resp1 = self.client.post("/api/bancos/sincronizar-nubank")
        self.assertEqual(resp1.get_json()["novas"], 4)

        # 2a sync so devolve a janela recente com ids novos - "old-1" esta
        # fora do intervalo [dmin, dmax] dessa leva e nunca e considerado.
        recentes_novos = [_tx(f"N{i}", 18 + i) for i in range(3)]
        with patch("pluggy_client.get_transactions", return_value=(recentes_novos, False)):
            resp2 = self.client.post("/api/bancos/sincronizar-nubank")
        corpo2 = resp2.get_json()
        self.assertEqual(corpo2["removidas"], 3)

        ids = self._ids_existentes()
        self.assertIn("old-1", ids)
        self.assertEqual(ids, {"old-1", "N0", "N1", "N2"})

    @patch("pluggy_client.get_accounts", return_value=CONTAS_OK)
    @patch("pluggy_client.get_item", return_value=ITEM_OK)
    def test_busca_truncada_nao_apaga_nada(self, mock_item, mock_accounts):
        lote_a = [_tx(f"A{i}", 18 + i) for i in range(3)]
        with patch("pluggy_client.get_transactions", return_value=(lote_a, False)):
            self.client.post("/api/bancos/sincronizar-nubank")

        # 2a sync veio truncada (bateu no teto de paginas): mesmo sem
        # devolver os ids A, nao pode ser tratada como fonte da verdade.
        lote_b_parcial = [_tx("B0", 18)]
        with patch("pluggy_client.get_transactions", return_value=(lote_b_parcial, True)):
            resp = self.client.post("/api/bancos/sincronizar-nubank")
        self.assertEqual(resp.get_json()["removidas"], 0)

        # upsert roda normalmente (B0 entra); so a reconciliacao (remocao) e que nao roda.
        self.assertEqual(self._total_linhas(), 4)
        self.assertIn("A0", self._ids_existentes())

    @patch("pluggy_client.get_accounts", return_value=CONTAS_OK)
    @patch("pluggy_client.get_item", return_value=ITEM_OK)
    def test_lista_vazia_nao_apaga_nada(self, mock_item, mock_accounts):
        lote_a = [_tx(f"A{i}", 18 + i) for i in range(3)]
        with patch("pluggy_client.get_transactions", return_value=(lote_a, False)):
            self.client.post("/api/bancos/sincronizar-nubank")

        with patch("pluggy_client.get_transactions", return_value=([], False)):
            resp = self.client.post("/api/bancos/sincronizar-nubank")
        self.assertEqual(resp.get_json()["removidas"], 0)
        self.assertEqual(self._total_linhas(), 3)

    @patch("pluggy_client.get_accounts", return_value=[
        {"id": "conta-1", "type": "BANK", "balance": 1000.0},
        {"id": "cartao-1", "type": "CREDIT", "balance": 200.0},
    ])
    @patch("pluggy_client.get_item", return_value=ITEM_OK)
    def test_reconciliacao_de_uma_conta_nao_afeta_a_outra(self, mock_item, mock_accounts):
        lote_conta_a = [_tx(f"CA{i}", 18 + i) for i in range(3)]
        lote_cartao = [_tx(f"CC{i}", 18 + i) for i in range(3)]
        primeira_leva = {"conta-1": lote_conta_a, "cartao-1": lote_cartao}
        with patch(
            "pluggy_client.get_transactions",
            side_effect=lambda cid: (primeira_leva[cid], False),
        ):
            self.client.post("/api/bancos/sincronizar-nubank")

        # 2a sync: so a conta (BANK) reconecta com ids novos; o cartao
        # devolve exatamente o mesmo de sempre.
        lote_conta_b = [_tx(f"CB{i}", 18 + i) for i in range(3)]
        segunda_leva = {"conta-1": lote_conta_b, "cartao-1": lote_cartao}
        with patch(
            "pluggy_client.get_transactions",
            side_effect=lambda cid: (segunda_leva[cid], False),
        ):
            resp = self.client.post("/api/bancos/sincronizar-nubank")
        self.assertEqual(resp.get_json()["removidas"], 3)

        conn = db.get_db()
        contas = {c["tipo"]: c["id"] for c in db.list_bank_accounts(conn)}
        conn.close()
        ids_cartao = self._ids_existentes(contas["cartao"])
        self.assertEqual(ids_cartao, {f"CC{i}" for i in range(3)})

    @patch("pluggy_client.get_accounts", return_value=CONTAS_OK)
    @patch("pluggy_client.get_item", return_value=ITEM_OK)
    def test_reconciliacao_funciona_com_encryption_key(self, mock_item, mock_accounts):
        chave = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"ENCRYPTION_KEY": chave}):
            lote_a = [_tx(f"A{i}", 18 + i) for i in range(3)]
            with patch("pluggy_client.get_transactions", return_value=(lote_a, False)):
                self.client.post("/api/bancos/sincronizar-nubank")

            lote_b = [_tx(f"B{i}", 18 + i) for i in range(3)]
            with patch("pluggy_client.get_transactions", return_value=(lote_b, False)):
                resp = self.client.post("/api/bancos/sincronizar-nubank")
            self.assertEqual(resp.get_json()["removidas"], 3)
            self.assertEqual(self._ids_existentes(), {f"B{i}" for i in range(3)})


if __name__ == "__main__":
    unittest.main()
