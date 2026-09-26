"""Auditoria 2026-09-26: gasto manual/chat (categoria interna minuscula,
ex. "mercado") e gasto do Nubank ("Groceries" -> "Mercado") tem que somar na
MESMA categoria em /api/financas/resumo - antes viravam duas barras
("Mercado" e "mercado"). Banco temporario, sem Pluggy/IA real."""
import unittest
from datetime import date

import db
from tests.test_fase9_api import _BaseTestCase, _iso

import financas_descricao


class RotuloCategoriaManualTestCase(unittest.TestCase):
    def test_categorias_internas_viram_rotulo_igual_ao_do_banco(self):
        esperado = {"mercado": "Mercado", "transporte": "Transporte", "lazer": "Lazer",
                    "contas": "Contas", "saude": "Saúde", "outros": "Outros"}
        for interna, rotulo in esperado.items():
            self.assertEqual(financas_descricao.rotulo_categoria_manual(interna), rotulo)

    def test_vazio_ou_estranho_nao_quebra(self):
        self.assertEqual(financas_descricao.rotulo_categoria_manual(None), "Outros")
        self.assertEqual(financas_descricao.rotulo_categoria_manual(""), "Outros")
        self.assertEqual(financas_descricao.rotulo_categoria_manual("  MERCADO "), "Mercado")
        self.assertEqual(financas_descricao.rotulo_categoria_manual("pet shop"), "Pet shop")


class ResumoJuntaCategoriasTestCase(_BaseTestCase):
    def test_manual_e_banco_somam_na_mesma_barra(self):
        cartao = self._conta("Nubank", "cartao")
        self._tx(cartao, "g1", _iso(0), 100.0, "DEBIT", descricao="ZAFFARI", categoria_pluggy="Groceries")
        conn = db.get_db()
        conn.execute("INSERT INTO expenses (amount, category, description, source_text, tipo) VALUES (40, 'mercado', 'feira', '', 'real')")
        conn.commit(); conn.close()
        cats = {c["categoria"]: c["valor"] for c in self.client.get("/api/financas/resumo").get_json()["por_categoria"]}
        self.assertEqual(cats, {"Mercado": 140.0})

    def test_extrato_mostra_rotulo_bonito_no_manual(self):
        conn = db.get_db()
        conn.execute("INSERT INTO expenses (amount, category, description, source_text, tipo) VALUES (12, 'saude', 'remedio', '', 'real')")
        conn.commit(); conn.close()
        itens = self.client.get("/api/financas/extrato").get_json()["itens"]
        self.assertEqual(itens[0]["categoria"], "Saúde")


if __name__ == "__main__":
    unittest.main()
