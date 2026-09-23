import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
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


class SaldoContaTestCase(_BancoIsoladoTestCase):
    def test_conta_nova_nao_tem_saldo(self):
        conta_id = db.get_or_create_bank_account(self.conn, "nubank", "conta")
        row = self.conn.execute("SELECT saldo FROM bank_accounts WHERE id = ?", (conta_id,)).fetchone()
        self.assertIsNone(row["saldo"])

    def test_atualizar_saldo_conta_grava_valor_absoluto(self):
        conta_id = db.get_or_create_bank_account(self.conn, "nubank", "conta")
        db.atualizar_saldo_conta(self.conn, conta_id, 16344.40)
        row = self.conn.execute("SELECT saldo FROM bank_accounts WHERE id = ?", (conta_id,)).fetchone()
        self.assertEqual(row["saldo"], 16344.40)

        db.atualizar_saldo_conta(self.conn, conta_id, 20000.0)
        row = self.conn.execute("SELECT saldo FROM bank_accounts WHERE id = ?", (conta_id,)).fetchone()
        self.assertEqual(row["saldo"], 20000.0)

    def test_buscar_conta_por_nome_parcial_e_sem_diferenciar_maiusculas(self):
        db.get_or_create_bank_account(self.conn, "nubank", "conta")
        achada = db.buscar_conta_por_nome(self.conn, "NUBANK")
        self.assertIsNotNone(achada)
        self.assertEqual(achada["banco"], "nubank")

        achada2 = db.buscar_conta_por_nome(self.conn, "nu")
        self.assertIsNotNone(achada2)

    def test_buscar_conta_por_nome_sem_match_devolve_none(self):
        db.get_or_create_bank_account(self.conn, "nubank", "conta")
        self.assertIsNone(db.buscar_conta_por_nome(self.conn, "itau"))

    def test_buscar_conta_por_nome_prefere_conta_sobre_cartao(self):
        db.get_or_create_bank_account(self.conn, "nubank", "cartao")
        db.get_or_create_bank_account(self.conn, "nubank", "conta")
        achada = db.buscar_conta_por_nome(self.conn, "nubank")
        self.assertEqual(achada["tipo"], "conta")

    def test_buscar_conta_por_nome_vazio_devolve_none(self):
        self.assertIsNone(db.buscar_conta_por_nome(self.conn, ""))
        self.assertIsNone(db.buscar_conta_por_nome(self.conn, None))

    def test_ajustar_saldo_conta_sem_saldo_conhecido_devolve_none(self):
        conta_id = db.get_or_create_bank_account(self.conn, "nubank", "conta")
        self.assertIsNone(db.ajustar_saldo_conta(self.conn, conta_id, -50.0))

    def test_ajustar_saldo_conta_com_saldo_conhecido(self):
        conta_id = db.get_or_create_bank_account(self.conn, "nubank", "conta")
        db.atualizar_saldo_conta(self.conn, conta_id, 1000.0)
        resultado = db.ajustar_saldo_conta(self.conn, conta_id, -150.0)
        self.assertEqual(resultado, (1000.0, 850.0))
        row = self.conn.execute("SELECT saldo FROM bank_accounts WHERE id = ?", (conta_id,)).fetchone()
        self.assertEqual(row["saldo"], 850.0)

    def test_ajustar_saldo_conta_positivo_pra_renda(self):
        conta_id = db.get_or_create_bank_account(self.conn, "nubank", "conta")
        db.atualizar_saldo_conta(self.conn, conta_id, 1000.0)
        resultado = db.ajustar_saldo_conta(self.conn, conta_id, 2500.0)
        self.assertEqual(resultado, (1000.0, 3500.0))


class NotasTestCase(_BancoIsoladoTestCase):
    def test_create_nota_e_list_notas(self):
        nota_id = db.create_nota(self.conn, "Viagem Portugal", "Comprar passagens\nHotel em Lisboa", ["portugal", "viagem"])
        notas = db.list_notas(self.conn)
        self.assertEqual(len(notas), 1)
        self.assertEqual(notas[0]["id"], nota_id)
        self.assertEqual(notas[0]["titulo"], "Viagem Portugal")
        self.assertEqual(notas[0]["tags"], "portugal,viagem")

    def test_create_nota_sem_tags(self):
        db.create_nota(self.conn, "Rascunho", "so um texto solto")
        notas = db.list_notas(self.conn)
        self.assertIsNone(notas[0]["tags"])

    def test_buscar_notas_por_titulo(self):
        db.create_nota(self.conn, "Viagem Portugal", "roteiro de dezembro", ["portugal"])
        db.create_nota(self.conn, "Lista de compras", "arroz, feijao", ["mercado"])
        achadas = db.buscar_notas(self.conn, "Portugal")
        self.assertEqual(len(achadas), 1)
        self.assertEqual(achadas[0]["titulo"], "Viagem Portugal")

    def test_buscar_notas_por_tag(self):
        db.create_nota(self.conn, "Viagem Portugal", "roteiro de dezembro", ["portugal", "viagem"])
        achadas = db.buscar_notas(self.conn, "viagem")
        self.assertEqual(len(achadas), 1)

    def test_buscar_notas_por_corpo(self):
        db.create_nota(self.conn, "Anotacao qualquer", "lembrar de levar o passaporte")
        achadas = db.buscar_notas(self.conn, "passaporte")
        self.assertEqual(len(achadas), 1)

    def test_buscar_notas_sem_match(self):
        db.create_nota(self.conn, "Viagem Portugal", "roteiro de dezembro", ["portugal"])
        self.assertEqual(db.buscar_notas(self.conn, "nada a ver"), [])

    def test_buscar_notas_termo_vazio_devolve_vazio(self):
        db.create_nota(self.conn, "Viagem Portugal", "roteiro de dezembro", ["portugal"])
        self.assertEqual(db.buscar_notas(self.conn, ""), [])

    def test_apagar_nota(self):
        nota_id = db.create_nota(self.conn, "Descartavel", "sem importancia")
        db.apagar_nota(self.conn, nota_id)
        self.assertEqual(db.list_notas(self.conn), [])


class ResumoCustoApiTestCase(_BancoIsoladoTestCase):
    """US-A5 (Fase 5): gasto com a API da Anthropic (mes atual + ultimos 30
    dias), agrupado por feature - card financeiro."""

    def _inserir_uso(self, dias_atras: float, custo: float, feature: str = "chat"):
        criado_em = (
            datetime.now(timezone.utc) - timedelta(days=dias_atras)
        ).replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")
        self.conn.execute(
            "INSERT INTO api_usage (model, input_tokens, output_tokens, cost_usd, feature, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("claude-haiku-4-5-20251001", 100, 20, custo, feature, criado_em),
        )
        self.conn.commit()

    def test_record_usage_grava_feature(self):
        db.record_usage(self.conn, "claude-sonnet-5", 100, 20, 0.01, feature="intent")
        row = self.conn.execute("SELECT feature FROM api_usage").fetchone()
        self.assertEqual(row["feature"], "intent")

    def test_record_usage_sem_feature_usa_outro(self):
        db.record_usage(self.conn, "claude-sonnet-5", 100, 20, 0.01)
        row = self.conn.execute("SELECT feature FROM api_usage").fetchone()
        self.assertEqual(row["feature"], "outro")

    def test_sem_dados_tudo_zero(self):
        resumo = db.resumo_custo_api(self.conn)
        self.assertEqual(resumo["mes_atual_usd"], 0)
        self.assertEqual(resumo["ultimos_30_dias_usd"], 0)
        self.assertEqual(resumo["ultimos_30_dias_por_feature"], [])
        self.assertEqual(resumo["moeda"], "USD")

    def test_soma_apenas_ultimos_30_dias(self):
        self._inserir_uso(dias_atras=5, custo=1.0)
        self._inserir_uso(dias_atras=29, custo=2.0)
        self._inserir_uso(dias_atras=40, custo=100.0)  # fora da janela
        resumo = db.resumo_custo_api(self.conn)
        self.assertEqual(resumo["ultimos_30_dias_usd"], 3.0)

    def test_agrupa_por_feature_nos_ultimos_30_dias(self):
        self._inserir_uso(dias_atras=1, custo=1.5, feature="chat")
        self._inserir_uso(dias_atras=2, custo=0.5, feature="chat")
        self._inserir_uso(dias_atras=1, custo=2.0, feature="intent")
        resumo = db.resumo_custo_api(self.conn)
        por_feature = {p["feature"]: p["custo_usd"] for p in resumo["ultimos_30_dias_por_feature"]}
        self.assertEqual(por_feature["chat"], 2.0)
        self.assertEqual(por_feature["intent"], 2.0)

    def test_mes_atual_exclui_uso_do_mes_passado(self):
        # linha de "ha muito tempo" (fora do mes calendario atual, mas ainda
        # pode estar ou nao dentro dos ultimos 30 dias dependendo do dia -
        # entao usamos uma bem antiga pra garantir que caia fora dos dois)
        self._inserir_uso(dias_atras=90, custo=50.0)
        self._inserir_uso(dias_atras=0, custo=3.0)
        resumo = db.resumo_custo_api(self.conn)
        self.assertEqual(resumo["mes_atual_usd"], 3.0)

    def test_arredonda_pra_4_casas(self):
        self._inserir_uso(dias_atras=0, custo=0.000123456)
        resumo = db.resumo_custo_api(self.conn)
        self.assertEqual(resumo["ultimos_30_dias_usd"], round(0.000123456, 4))


if __name__ == "__main__":
    unittest.main()
