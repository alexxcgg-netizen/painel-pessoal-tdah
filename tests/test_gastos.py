import unittest
from datetime import date

from gastos import historico_diario, resumo_semanal


class GastosTestCase(unittest.TestCase):
    def test_zero_preenchido_sem_nenhum_gasto(self):
        r = historico_diario([], 3, date(2026, 9, 18))
        self.assertEqual(
            r,
            [
                {"data": "2026-09-16", "total": 0},
                {"data": "2026-09-17", "total": 0},
                {"data": "2026-09-18", "total": 0},
            ],
        )

    def test_soma_gastos_do_mesmo_dia(self):
        expenses = [
            {"amount": 50.0, "created_at": "2026-09-18 10:00:00"},
            {"amount": 25.5, "created_at": "2026-09-18 15:30:00"},
        ]
        r = historico_diario(expenses, 3, date(2026, 9, 18))
        self.assertEqual(r[-1], {"data": "2026-09-18", "total": 75.5})

    def test_ignora_gasto_fora_da_janela(self):
        expenses = [{"amount": 100.0, "created_at": "2026-09-01 10:00:00"}]
        r = historico_diario(expenses, 3, date(2026, 9, 18))
        self.assertEqual(sum(d["total"] for d in r), 0)

    def test_dias_ficam_em_ordem_cronologica(self):
        r = historico_diario([], 5, date(2026, 9, 18))
        self.assertEqual(
            [d["data"] for d in r],
            ["2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18"],
        )

    def test_arredonda_pra_duas_casas(self):
        expenses = [
            {"amount": 10.111, "created_at": "2026-09-18 10:00:00"},
            {"amount": 10.111, "created_at": "2026-09-18 11:00:00"},
        ]
        r = historico_diario(expenses, 1, date(2026, 9, 18))
        self.assertEqual(r[0]["total"], 20.22)

    def test_atravessa_virada_de_mes(self):
        expenses = [{"amount": 30.0, "created_at": "2026-08-31 10:00:00"}]
        r = historico_diario(expenses, 3, date(2026, 9, 1))
        self.assertEqual(
            [d["data"] for d in r], ["2026-08-30", "2026-08-31", "2026-09-01"]
        )
        self.assertEqual(r[1]["total"], 30.0)


class ResumoSemanalTestCase(unittest.TestCase):
    """hoje = 2026-09-18 (sexta). Semana atual: 12 a 18/09. Semana
    anterior: 05 a 11/09."""

    def test_sem_gastos_retorna_zeros(self):
        r = resumo_semanal([], date(2026, 9, 18))
        self.assertEqual(r["total_semana"], 0)
        self.assertEqual(r["total_semana_anterior"], 0)
        self.assertIsNone(r["variacao_pct"])
        self.assertIsNone(r["categoria_top"])
        self.assertIsNone(r["categoria_top_valor"])

    def test_soma_gastos_da_semana_atual(self):
        expenses = [
            {"amount": 50.0, "category": "mercado", "created_at": "2026-09-14 10:00:00"},
            {"amount": 30.0, "category": "transporte", "created_at": "2026-09-18 08:00:00"},
        ]
        r = resumo_semanal(expenses, date(2026, 9, 18))
        self.assertEqual(r["total_semana"], 80.0)

    def test_soma_gastos_da_semana_anterior_separado(self):
        expenses = [
            {"amount": 100.0, "category": "mercado", "created_at": "2026-09-08 10:00:00"},
            {"amount": 20.0, "category": "lazer", "created_at": "2026-09-16 10:00:00"},
        ]
        r = resumo_semanal(expenses, date(2026, 9, 18))
        self.assertEqual(r["total_semana"], 20.0)
        self.assertEqual(r["total_semana_anterior"], 100.0)

    def test_ignora_gasto_de_tres_semanas_atras(self):
        expenses = [{"amount": 999.0, "category": "mercado", "created_at": "2026-08-20 10:00:00"}]
        r = resumo_semanal(expenses, date(2026, 9, 18))
        self.assertEqual(r["total_semana"], 0)
        self.assertEqual(r["total_semana_anterior"], 0)

    def test_variacao_percentual_positiva(self):
        expenses = [
            {"amount": 100.0, "category": "mercado", "created_at": "2026-09-08 10:00:00"},
            {"amount": 150.0, "category": "mercado", "created_at": "2026-09-14 10:00:00"},
        ]
        r = resumo_semanal(expenses, date(2026, 9, 18))
        self.assertEqual(r["variacao_pct"], 50)

    def test_variacao_percentual_negativa(self):
        expenses = [
            {"amount": 200.0, "category": "mercado", "created_at": "2026-09-08 10:00:00"},
            {"amount": 100.0, "category": "mercado", "created_at": "2026-09-14 10:00:00"},
        ]
        r = resumo_semanal(expenses, date(2026, 9, 18))
        self.assertEqual(r["variacao_pct"], -50)

    def test_sem_semana_anterior_variacao_fica_none(self):
        expenses = [{"amount": 50.0, "category": "mercado", "created_at": "2026-09-14 10:00:00"}]
        r = resumo_semanal(expenses, date(2026, 9, 18))
        self.assertIsNone(r["variacao_pct"])

    def test_categoria_top_identificada(self):
        expenses = [
            {"amount": 30.0, "category": "mercado", "created_at": "2026-09-14 10:00:00"},
            {"amount": 80.0, "category": "contas", "created_at": "2026-09-15 10:00:00"},
            {"amount": 20.0, "category": "lazer", "created_at": "2026-09-16 10:00:00"},
        ]
        r = resumo_semanal(expenses, date(2026, 9, 18))
        self.assertEqual(r["categoria_top"], "contas")
        self.assertEqual(r["categoria_top_valor"], 80.0)

    def test_categoria_ausente_vira_outros(self):
        expenses = [{"amount": 40.0, "category": None, "created_at": "2026-09-14 10:00:00"}]
        r = resumo_semanal(expenses, date(2026, 9, 18))
        self.assertEqual(r["categoria_top"], "outros")

    def test_borda_exata_dos_7_dias(self):
        expenses = [
            {"amount": 10.0, "category": "mercado", "created_at": "2026-09-12 00:00:01"},
            {"amount": 20.0, "category": "mercado", "created_at": "2026-09-11 23:59:59"},
        ]
        r = resumo_semanal(expenses, date(2026, 9, 18))
        self.assertEqual(r["total_semana"], 10.0)
        self.assertEqual(r["total_semana_anterior"], 20.0)


if __name__ == "__main__":
    unittest.main()
