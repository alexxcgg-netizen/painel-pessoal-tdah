import unittest
from datetime import date

from gastos import historico_diario


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


if __name__ == "__main__":
    unittest.main()
