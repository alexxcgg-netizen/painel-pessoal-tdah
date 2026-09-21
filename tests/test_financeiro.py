import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import db


class _BancoIsoladoTestCase(unittest.TestCase):
    """Base com banco temporario isolado - mesmo padrao usado em
    test_aprendizado.py e test_notificacoes.py."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._caminho_original = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "painel.db"
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()
        db.DB_PATH = self._caminho_original
        self._tmp.cleanup()


class IncomesTestCase(_BancoIsoladoTestCase):
    def test_create_income_e_list_incomes(self):
        db.create_income(self.conn, 3000.0, "outros", None, "entrou 3000 na conta")
        incomes = db.list_incomes(self.conn)
        self.assertEqual(len(incomes), 1)
        self.assertEqual(incomes[0]["amount"], 3000.0)
        self.assertEqual(incomes[0]["category"], "outros")
        self.assertEqual(incomes[0]["source_text"], "entrou 3000 na conta")

    def test_list_incomes_respeita_limit(self):
        for i in range(5):
            db.create_income(self.conn, float(i), "outros")
        self.assertEqual(len(db.list_incomes(self.conn, limit=3)), 3)

    def test_total_incomes_mes_soma_so_do_mes_pedido(self):
        self.conn.execute(
            "INSERT INTO incomes (amount, category, created_at) VALUES (100, 'outros', '2026-01-15 10:00:00')"
        )
        self.conn.execute(
            "INSERT INTO incomes (amount, category, created_at) VALUES (200, 'outros', '2026-01-20 10:00:00')"
        )
        self.conn.execute(
            "INSERT INTO incomes (amount, category, created_at) VALUES (50, 'outros', '2026-02-01 10:00:00')"
        )
        self.conn.commit()
        self.assertEqual(db.total_incomes_mes(self.conn, "2026-01"), 300.0)
        self.assertEqual(db.total_incomes_mes(self.conn, "2026-02"), 50.0)
        self.assertEqual(db.total_incomes_mes(self.conn, "2026-03"), 0.0)


class OrcamentosTestCase(_BancoIsoladoTestCase):
    def test_definir_e_obter_orcamento(self):
        db.definir_orcamento(self.conn, "mercado", 800.0)
        self.assertEqual(db.obter_orcamento(self.conn, "mercado"), 800.0)

    def test_obter_orcamento_inexistente_retorna_none(self):
        self.assertIsNone(db.obter_orcamento(self.conn, "lazer"))

    def test_definir_orcamento_atualiza_valor_existente(self):
        db.definir_orcamento(self.conn, "mercado", 800.0)
        db.definir_orcamento(self.conn, "mercado", 1000.0)
        self.assertEqual(db.obter_orcamento(self.conn, "mercado"), 1000.0)
        self.assertEqual(len(db.list_orcamentos(self.conn)), 1)

    def test_list_orcamentos_ordenado_por_categoria(self):
        db.definir_orcamento(self.conn, "transporte", 300.0)
        db.definir_orcamento(self.conn, "mercado", 800.0)
        categorias = [o["categoria"] for o in db.list_orcamentos(self.conn)]
        self.assertEqual(categorias, ["mercado", "transporte"])

    def test_apagar_orcamento(self):
        db.definir_orcamento(self.conn, "mercado", 800.0)
        db.apagar_orcamento(self.conn, "mercado")
        self.assertIsNone(db.obter_orcamento(self.conn, "mercado"))

    def test_apagar_orcamento_inexistente_nao_quebra(self):
        db.apagar_orcamento(self.conn, "nao existe")  # nao deve levantar excecao

    def test_gasto_mes_por_categoria_so_conta_real_da_categoria_e_mes(self):
        self.conn.execute(
            "INSERT INTO expenses (amount, category, tipo, created_at) "
            "VALUES (300, 'mercado', 'real', '2026-01-10 10:00:00')"
        )
        self.conn.execute(
            "INSERT INTO expenses (amount, category, tipo, created_at) "
            "VALUES (500, 'mercado', 'planejado', '2026-01-11 10:00:00')"  # planejado nao conta
        )
        self.conn.execute(
            "INSERT INTO expenses (amount, category, tipo, created_at) "
            "VALUES (100, 'transporte', 'real', '2026-01-12 10:00:00')"  # categoria diferente
        )
        self.conn.execute(
            "INSERT INTO expenses (amount, category, tipo, created_at) "
            "VALUES (200, 'mercado', 'real', '2026-02-01 10:00:00')"  # mes diferente
        )
        self.conn.commit()
        self.assertEqual(db.gasto_mes_por_categoria(self.conn, "mercado", "2026-01"), 300.0)

    def test_gasto_mes_por_categoria_sem_gasto_retorna_zero(self):
        self.assertEqual(db.gasto_mes_por_categoria(self.conn, "lazer", "2026-01"), 0.0)


class TotalGastosBancariosMesTestCase(_BancoIsoladoTestCase):
    def _transacao(self, valor, data, external_id):
        conta_id = db.get_or_create_bank_account(self.conn, "Nubank")
        self.conn.execute(
            "INSERT INTO bank_transactions (bank_account_id, data, descricao, valor, external_id) "
            "VALUES (?, ?, 'compra', ?, ?)",
            (conta_id, data, valor, external_id),
        )
        self.conn.commit()

    def test_sem_transacoes_retorna_zero(self):
        self.assertEqual(db.total_gastos_bancarios_mes(self.conn, "2026-01"), 0.0)

    def test_soma_so_saidas_do_mes_pedido(self):
        self._transacao(-100.0, "2026-01-10", "ext1")  # saida
        self._transacao(-50.0, "2026-01-15", "ext2")  # saida
        self._transacao(1000.0, "2026-01-20", "ext3")  # entrada, nao conta
        self._transacao(-30.0, "2026-02-01", "ext4")  # mes diferente
        self.assertEqual(db.total_gastos_bancarios_mes(self.conn, "2026-01"), 150.0)


class ApelidosGastoTestCase(_BancoIsoladoTestCase):
    def test_definir_e_listar_apelido(self):
        db.definir_apelido_gasto(self.conn, "apple.com/bill", 14.90, "iCloud 200GB")
        apelidos = db.list_apelidos_gasto(self.conn)
        self.assertEqual(len(apelidos), 1)
        self.assertEqual(apelidos[0]["descricao_normalizada"], "apple.com/bill")
        self.assertEqual(apelidos[0]["valor"], 14.90)
        self.assertEqual(apelidos[0]["apelido"], "iCloud 200GB")

    def test_mesma_descricao_e_valor_atualiza_o_apelido(self):
        db.definir_apelido_gasto(self.conn, "apple.com/bill", 14.90, "iCloud")
        db.definir_apelido_gasto(self.conn, "apple.com/bill", 14.90, "iCloud 200GB")
        apelidos = db.list_apelidos_gasto(self.conn)
        self.assertEqual(len(apelidos), 1)
        self.assertEqual(apelidos[0]["apelido"], "iCloud 200GB")

    def test_mesma_descricao_valor_diferente_e_outro_apelido(self):
        db.definir_apelido_gasto(self.conn, "apple.com/bill", 14.90, "iCloud 200GB")
        db.definir_apelido_gasto(self.conn, "apple.com/bill", 21.90, "Apple Music")
        apelidos = db.list_apelidos_gasto(self.conn)
        self.assertEqual(len(apelidos), 2)


if __name__ == "__main__":
    unittest.main()
