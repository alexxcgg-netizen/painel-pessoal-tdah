import random
import unittest
from datetime import date, timedelta

from streak import calcular_streak


class StreakTestCase(unittest.TestCase):
    def test_sem_atividade_nenhuma_e_zero(self):
        self.assertEqual(calcular_streak(set(), date(2026, 9, 18)), 0)

    def test_atividade_so_hoje_e_um(self):
        hoje = date(2026, 9, 18)
        self.assertEqual(calcular_streak({hoje.isoformat()}, hoje), 1)

    def test_atividade_so_ontem_ainda_conta_um(self):
        hoje = date(2026, 9, 18)
        ontem = hoje - timedelta(days=1)
        self.assertEqual(calcular_streak({ontem.isoformat()}, hoje), 1)

    def test_sequencia_de_varios_dias_terminando_hoje(self):
        hoje = date(2026, 9, 18)
        dias = {(hoje - timedelta(days=i)).isoformat() for i in range(5)}
        self.assertEqual(calcular_streak(dias, hoje), 5)

    def test_sequencia_terminando_ontem_ainda_valida(self):
        hoje = date(2026, 9, 18)
        dias = {(hoje - timedelta(days=i)).isoformat() for i in range(1, 6)}
        self.assertEqual(calcular_streak(dias, hoje), 5)

    def test_buraco_de_dois_dias_quebra_a_sequencia(self):
        hoje = date(2026, 9, 18)
        anteontem = hoje - timedelta(days=2)
        self.assertEqual(calcular_streak({anteontem.isoformat()}, hoje), 0)

    def test_dias_fora_de_ordem_no_set_nao_afetam_resultado(self):
        hoje = date(2026, 9, 18)
        dias = {(hoje - timedelta(days=i)).isoformat() for i in (3, 0, 2, 1)}
        self.assertEqual(calcular_streak(dias, hoje), 4)

    def test_dias_distantes_no_futuro_e_passado_sao_ignorados(self):
        hoje = date(2026, 9, 18)
        dias = {hoje.isoformat(), (hoje + timedelta(days=30)).isoformat(), "2020-01-01"}
        self.assertEqual(calcular_streak(dias, hoje), 1)

    def test_atravessa_virada_de_ano(self):
        hoje = date(2027, 1, 2)
        dias = {(hoje - timedelta(days=i)).isoformat() for i in range(4)}
        self.assertEqual(calcular_streak(dias, hoje), 4)

    def test_atravessa_ano_bissexto(self):
        hoje = date(2028, 3, 1)
        dias = {(hoje - timedelta(days=i)).isoformat() for i in range(3)}
        self.assertEqual(calcular_streak(dias, hoje), 3)

    def test_streak_nao_quebra_com_strings_malformadas_no_set(self):
        hoje = date(2026, 9, 18)
        dias = {hoje.isoformat(), "", "nao-e-data", "2026-13-40"}
        self.assertEqual(calcular_streak(dias, hoje), 1)

    def test_fuzz_streak_contra_implementacao_de_referencia(self):
        """Stress test: gera cenarios aleatorios de dias ativos/inativos e
        confere contra uma contagem de referencia feita por forca bruta."""
        random.seed(42)
        for _ in range(200):
            hoje = date(2020, 1, 1) + timedelta(days=random.randint(0, 4000))
            janela = random.randint(0, 60)
            dias_ativos = {
                (hoje - timedelta(days=i)).isoformat()
                for i in range(janela)
                if random.random() < 0.7
            }

            esperado = 0
            cursor = hoje
            if cursor.isoformat() not in dias_ativos:
                cursor -= timedelta(days=1)
            if cursor.isoformat() in dias_ativos:
                while cursor.isoformat() in dias_ativos:
                    esperado += 1
                    cursor -= timedelta(days=1)

            self.assertEqual(calcular_streak(dias_ativos, hoje), esperado)


if __name__ == "__main__":
    unittest.main()
