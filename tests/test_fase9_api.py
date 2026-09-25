"""Fase 9, Faixa F9-api: testes de GET /api/financas/extrato, GET
/api/financas/resumo e a correcao de /api/patrimonio (fatura de cartao
entra como divida, nunca como saldo positivo) - ver AGENTS.md da faixa.
Nunca chama Pluggy de verdade nem le o .env real - mesmo padrao de
tests/test_fase9_sync.py: banco temporario, transacoes inseridas direto
(mesmo formato que rotas/f8_banco.py grava, incluindo criptografia de
`valor`/`descricao` quando ENCRYPTION_KEY esta configurada)."""

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from cryptography.fernet import Fernet

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth
import db

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402

PIN_TESTE = "123456"
HOJE = date.today()


def _iso(dias_atras: int) -> str:
    return (HOJE - timedelta(days=dias_atras)).isoformat()


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

    def _conta(self, banco="Nubank", tipo="conta"):
        conn = db.get_db()
        conta_id = db.get_or_create_bank_account(conn, banco, tipo)
        conn.commit()
        conn.close()
        return conta_id

    def _tx(
        self,
        bank_account_id,
        external_id,
        data,
        valor,
        tipo_operacao,
        descricao="Compra Teste",
        categoria_pluggy=None,
        descricao_original=None,
        estorno_de_external_id=None,
        categoria=None,
    ):
        conn = db.get_db()
        conn.execute(
            """INSERT INTO bank_transactions
               (bank_account_id, data, descricao, valor, external_id, categoria,
                estabelecimento, categoria_pluggy, descricao_original, tipo_operacao,
                estorno_de_external_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                bank_account_id,
                data,
                db.criptografia.criptografar(descricao),
                db._cnum(valor),
                external_id,
                categoria,
                None,
                categoria_pluggy,
                descricao_original if descricao_original is not None else descricao,
                tipo_operacao,
                estorno_de_external_id,
            ),
        )
        conn.commit()
        conn.close()


class ExtratoSinalTestCase(_BaseTestCase):
    def test_compra_cartao_amount_positivo_debit_vira_saida_negativa(self):
        cartao_id = self._conta("Nubank", "cartao")
        self._tx(cartao_id, "c1", _iso(1), 55.90, "DEBIT", descricao="IFOOD")

        res = self.client.get("/api/financas/extrato")
        corpo = res.get_json()
        item = next(i for i in corpo["itens"] if i["id"] == "bt-1")
        self.assertEqual(item["valor"], -55.90)
        self.assertEqual(item["tipo_conta"], "cartao")

    def test_entrada_credit_na_conta_aparece_positiva(self):
        conta_id = self._conta("Nubank", "conta")
        self._tx(conta_id, "e1", _iso(1), 200.0, "CREDIT", descricao="Salario")

        res = self.client.get("/api/financas/extrato")
        corpo = res.get_json()
        item = next(i for i in corpo["itens"] if i["id"] == "bt-1")
        self.assertEqual(item["valor"], 200.0)

    def test_sem_tipo_operacao_usa_sinal_do_valor_como_esta(self):
        conta_id = self._conta("Nubank", "conta")
        self._tx(conta_id, "s1", _iso(1), -30.0, None, descricao="Antiga")

        res = self.client.get("/api/financas/extrato")
        corpo = res.get_json()
        item = next(i for i in corpo["itens"] if i["id"] == "bt-1")
        self.assertEqual(item["valor"], -30.0)


class ExtratoParcelaFuturaTestCase(_BaseTestCase):
    def test_parcela_futura_nao_aparece_nem_soma(self):
        cartao_id = self._conta("Nubank", "cartao")
        data_futura = (HOJE + timedelta(days=200)).isoformat()
        self._tx(cartao_id, "fut1", data_futura, 100.0, "DEBIT", descricao="Parcela 2/12")
        self._tx(cartao_id, "hoje1", _iso(0), 10.0, "DEBIT", descricao="Compra hoje")

        res = self.client.get("/api/financas/extrato?dias=90")
        corpo = res.get_json()
        ids = [i["id"] for i in corpo["itens"]]
        self.assertNotIn("bt-1", ids)
        self.assertIn("bt-2", ids)


class ExtratoPaginacaoTestCase(_BaseTestCase):
    def test_tres_janelas_cobrem_sem_sobreposicao_nem_buraco(self):
        conta_id = self._conta("Nubank", "conta")
        for i in range(40):
            self._tx(conta_id, f"p{i}", _iso(i), 10.0, "DEBIT", descricao=f"Gasto {i}")

        vistos = []
        antes = None
        for _ in range(3):
            params = {"dias": "15"}
            if antes:
                params["antes"] = antes
            res = self.client.get("/api/financas/extrato", query_string=params)
            corpo = res.get_json()
            datas = [i["data"] for i in corpo["itens"]]
            vistos.extend(datas)
            antes = corpo["proximo_antes"]
            if antes is None:
                break

        self.assertEqual(len(vistos), len(set(vistos)) and len(vistos))
        self.assertEqual(len(vistos), len(set(vistos)))
        self.assertIsNone(antes)
        self.assertEqual(sorted(vistos), sorted(_iso(i) for i in range(40)))


class ResumoTestCase(_BaseTestCase):
    def test_pagamento_de_fatura_nao_entra_em_gasto_mes(self):
        conta_id = self._conta("Nubank", "conta")
        self._tx(
            conta_id,
            "pgto1",
            _iso(0),
            500.0,
            "DEBIT",
            descricao="Pagamento de fatura",
            categoria_pluggy="Credit card payment",
        )
        self._tx(conta_id, "g1", _iso(0), 20.0, "DEBIT", descricao="Padaria")

        res = self.client.get("/api/financas/resumo")
        corpo = res.get_json()
        self.assertEqual(corpo["gasto_mes"], 20.0)

    def test_transferencia_entre_contas_proprias_nao_entra_em_gasto_mes(self):
        conta_id = self._conta("Nubank", "conta")
        self._tx(
            conta_id,
            "t1",
            _iso(0),
            300.0,
            "DEBIT",
            descricao="Transferencia enviada",
            categoria_pluggy="Transfers",
        )

        res = self.client.get("/api/financas/resumo")
        corpo = res.get_json()
        self.assertEqual(corpo["gasto_mes"], 0)

    def test_fatura_atual_e_saldo_conta_vem_de_bank_accounts(self):
        conta_id = self._conta("Nubank", "conta")
        cartao_id = self._conta("Nubank", "cartao")
        conn = db.get_db()
        db.atualizar_saldo_conta(conn, conta_id, 1000.0)
        db.atualizar_saldo_conta(conn, cartao_id, 250.0)
        conn.commit()
        conn.close()

        res = self.client.get("/api/financas/resumo")
        corpo = res.get_json()
        self.assertEqual(corpo["saldo_conta"], 1000.0)
        self.assertEqual(corpo["fatura_atual"], 250.0)


class EstornoTestCase(_BaseTestCase):
    def test_estorno_aparece_com_estorno_de(self):
        cartao_id = self._conta("Nubank", "cartao")
        self._tx(cartao_id, "orig1", _iso(3), 40.0, "DEBIT", descricao="LOJA XPTO")
        self._tx(
            cartao_id,
            "est1",
            _iso(1),
            40.0,
            "CREDIT",
            descricao="Estorno LOJA XPTO",
            estorno_de_external_id="orig1",
        )

        res = self.client.get("/api/financas/extrato")
        corpo = res.get_json()
        item = next(i for i in corpo["itens"] if i["id"] == "bt-2")
        self.assertIsNotNone(item["estorno_de"])


class ValidacaoParametrosTestCase(_BaseTestCase):
    def test_dias_invalido_cai_no_padrao_15(self):
        res = self.client.get("/api/financas/extrato?dias=abc")
        self.assertEqual(res.status_code, 200)
        corpo = res.get_json()
        self.assertEqual(corpo["de"], (HOJE - timedelta(days=14)).isoformat())

    def test_dias_fora_do_limite_cai_no_padrao_15(self):
        res = self.client.get("/api/financas/extrato?dias=999")
        self.assertEqual(res.status_code, 200)
        corpo = res.get_json()
        self.assertEqual(corpo["de"], (HOJE - timedelta(days=14)).isoformat())

    def test_antes_invalido_e_400(self):
        res = self.client.get("/api/financas/extrato?antes=31-13-2026")
        self.assertEqual(res.status_code, 400)
        corpo = res.get_json()
        self.assertIn("error", corpo)


class CriptografiaTestCase(_BaseTestCase):
    def test_valores_cifrados_funcionam(self):
        chave = Fernet.generate_key().decode()
        os.environ["ENCRYPTION_KEY"] = chave
        try:
            conta_id = self._conta("Nubank", "conta")
            self._tx(conta_id, "cif1", _iso(0), 77.0, "DEBIT", descricao="Compra Cifrada")

            res = self.client.get("/api/financas/extrato")
            corpo = res.get_json()
            item = next(i for i in corpo["itens"] if i["id"] == "bt-1")
            self.assertEqual(item["valor"], -77.0)
            self.assertIn("Compra Cifrada".split()[0].lower(), item["descricao"].lower())
        finally:
            os.environ.pop("ENCRYPTION_KEY", None)


class PatrimonioTestCase(_BaseTestCase):
    def test_patrimonio_cartao_entra_como_divida(self):
        conta_id = self._conta("Nubank", "conta")
        cartao_id = self._conta("Nubank", "cartao")
        goal_id = None
        conn = db.get_db()
        db.atualizar_saldo_conta(conn, conta_id, 100.0)
        db.atualizar_saldo_conta(conn, cartao_id, 2377.35)
        goal_id = db.create_goal(conn, "Meta Teste", 1000.0, None)
        db.add_to_goal(conn, goal_id, 50.0)
        conn.commit()
        conn.close()

        res = self.client.get("/api/patrimonio")
        corpo = res.get_json()
        self.assertEqual(corpo["saldo_bancario"], 100.0)
        self.assertEqual(corpo["fatura_aberta"], 2377.35)
        self.assertEqual(corpo["valor_guardado_metas"], 50.0)
        self.assertEqual(corpo["patrimonio_total"], -2227.35)


if __name__ == "__main__":
    unittest.main()
