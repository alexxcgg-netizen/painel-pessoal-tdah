import unittest
from datetime import date

from voos import (
    dias_desde_ultimo_voo,
    historico_horas_acumuladas,
    inicio_da_semana,
    proximos_voos,
    resumo_horas,
)


class VoosTestCase(unittest.TestCase):
    def test_inicio_da_semana_e_segunda(self):
        # 18/09/2026 e uma sexta-feira
        self.assertEqual(inicio_da_semana(date(2026, 9, 18)), date(2026, 9, 14))

    def test_inicio_da_semana_numa_segunda_e_ela_mesma(self):
        self.assertEqual(inicio_da_semana(date(2026, 9, 14)), date(2026, 9, 14))

    def test_resumo_sem_voos_e_tudo_zero(self):
        self.assertEqual(
            resumo_horas([], date(2026, 9, 18)),
            {"horas_semana": 0, "horas_mes": 0, "horas_total": 0},
        )

    def test_resumo_ignora_voos_agendados_sem_horas(self):
        voos = [{"data": "2026-09-17", "horas": None}]
        r = resumo_horas(voos, date(2026, 9, 18))
        self.assertEqual(r["horas_semana"], 0)

    def test_resumo_ignora_voos_futuros_mesmo_com_horas(self):
        voos = [{"data": "2026-09-25", "horas": 2.0}]
        r = resumo_horas(voos, date(2026, 9, 18))
        self.assertEqual(r["horas_total"], 0)

    def test_resumo_soma_voos_da_semana_e_do_mes(self):
        voos = [
            {"data": "2026-09-14", "horas": 1.5},  # segunda desta semana
            {"data": "2026-09-10", "horas": 2.0},  # mes atual, semana passada
            {"data": "2026-08-30", "horas": 3.0},  # mes passado
        ]
        r = resumo_horas(voos, date(2026, 9, 18))
        self.assertEqual(r["horas_semana"], 1.5)
        self.assertEqual(r["horas_mes"], 3.5)
        self.assertEqual(r["horas_total"], 6.5)

    def test_resumo_arredonda_pra_duas_casas(self):
        voos = [{"data": "2026-09-18", "horas": 1.111}, {"data": "2026-09-18", "horas": 1.111}]
        r = resumo_horas(voos, date(2026, 9, 18))
        self.assertEqual(r["horas_semana"], 2.22)

    def test_proximos_voos_inclui_hoje_e_futuro_ordenado(self):
        voos = [
            {"data": "2026-09-20", "horas": None, "destino": "B"},
            {"data": "2026-09-18", "horas": 1.0, "destino": "A"},
            {"data": "2026-09-10", "horas": 1.0, "destino": "passado"},
        ]
        r = proximos_voos(voos, date(2026, 9, 18))
        self.assertEqual([v["destino"] for v in r], ["A", "B"])

    def test_proximos_voos_vazio_quando_nao_ha_futuro(self):
        voos = [{"data": "2026-09-01", "horas": 1.0, "destino": "X"}]
        self.assertEqual(proximos_voos(voos, date(2026, 9, 18)), [])

    def test_historico_acumula_em_ordem_cronologica(self):
        voos = [
            {"data": "2026-09-10", "horas": 1.5},
            {"data": "2026-09-01", "horas": 2.0},
            {"data": "2026-09-15", "horas": 1.0},
        ]
        r = historico_horas_acumuladas(voos, date(2026, 9, 18))
        self.assertEqual(
            r,
            [
                {"data": "2026-09-01", "acumulado": 2.0},
                {"data": "2026-09-10", "acumulado": 3.5},
                {"data": "2026-09-15", "acumulado": 4.5},
            ],
        )

    def test_historico_ignora_voos_futuros_e_sem_horas(self):
        voos = [
            {"data": "2026-09-01", "horas": 2.0},
            {"data": "2026-09-25", "horas": 5.0},
            {"data": "2026-09-05", "horas": None},
        ]
        r = historico_horas_acumuladas(voos, date(2026, 9, 18))
        self.assertEqual(r, [{"data": "2026-09-01", "acumulado": 2.0}])

    def test_historico_vazio_sem_voos(self):
        self.assertEqual(historico_horas_acumuladas([], date(2026, 9, 18)), [])

    def test_dias_desde_ultimo_voo_sem_nenhum_voo_e_none(self):
        self.assertIsNone(dias_desde_ultimo_voo([], date(2026, 9, 18)))

    def test_dias_desde_ultimo_voo_ignora_agendado_sem_horas(self):
        voos = [{"data": "2026-09-18", "horas": None}]
        self.assertIsNone(dias_desde_ultimo_voo(voos, date(2026, 9, 18)))

    def test_dias_desde_ultimo_voo_conta_a_partir_do_mais_recente(self):
        voos = [
            {"data": "2026-09-01", "horas": 1.0},
            {"data": "2026-09-10", "horas": 1.5},
        ]
        self.assertEqual(dias_desde_ultimo_voo(voos, date(2026, 9, 18)), 8)

    def test_dias_desde_ultimo_voo_hoje_e_zero(self):
        voos = [{"data": "2026-09-18", "horas": 1.0}]
        self.assertEqual(dias_desde_ultimo_voo(voos, date(2026, 9, 18)), 0)

    def test_dias_desde_ultimo_voo_ignora_voo_agendado_no_futuro(self):
        voos = [
            {"data": "2026-09-10", "horas": 1.0},
            {"data": "2026-09-25", "horas": None},
        ]
        self.assertEqual(dias_desde_ultimo_voo(voos, date(2026, 9, 18)), 8)


if __name__ == "__main__":
    unittest.main()
