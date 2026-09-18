import unittest
from datetime import date

from voos import inicio_da_semana, proximos_voos, resumo_horas


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


if __name__ == "__main__":
    unittest.main()
