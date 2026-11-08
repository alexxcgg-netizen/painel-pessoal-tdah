"""Leva 08/11, 3a rodada (frente B, item 1): tarefa com hora e periodo do dia nao fica sem data.

"remedio de manha as 7": o modelo manda quando="de manha" + hora="07:00". Na 2a rodada o "quando" com texto
contava como dia dito, resolver_data_relativa devolvia None e a tarefa ficava sem data (nunca avisava).
Agora periodo do dia ("de manha", "a noite", "mais tarde", "daqui a pouco") e hora sem dia: hoje, ou amanha
se a hora ja passou. Prazo vago de verdade ("essa semana", "quando der") continua sem data.
"""
import os
import unittest
from datetime import date, datetime

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

from ia.funcoes import chat as chat_mod  # noqa: E402
from ia.funcoes.chat import resolver_quando_data  # noqa: E402

DIA = date(2026, 11, 3)
HOJE = "2026-11-03"
AMANHA = "2026-11-04"


def _as(h, m=0):
    return datetime(2026, 11, 3, h, m)


class PeriodoDoDiaTestCase(unittest.TestCase):
    def test_de_manha_as_7_dito_de_noite_vai_pra_amanha(self):
        for quando in ("de manhã", "de manha", "cedo", "logo cedo"):
            with self.subTest(quando=quando):
                entrada = {"titulo": "Tomar o remedio", "quando": quando, "hora": "07:00"}
                self.assertEqual(resolver_quando_data(entrada, DIA, _as(22)), AMANHA)

    def test_periodo_com_hora_que_ainda_vem_fica_hoje(self):
        for quando, hora in (("à noite", "23:00"), ("mais tarde", "22:40"), ("daqui a pouco", "22:15"),
                             ("depois do almoço", "23:30"), ("à tarde", "22:20")):
            with self.subTest(quando=quando):
                entrada = {"titulo": "x", "quando": quando, "hora": hora}
                self.assertEqual(resolver_quando_data(entrada, DIA, _as(22)), HOJE)

    def test_periodo_com_hora_passada_vai_pra_amanha(self):
        for quando, hora in (("à noite", "20:00"), ("mais tarde", "21:00"), ("de tarde", "15:00")):
            with self.subTest(quando=quando):
                entrada = {"titulo": "x", "quando": quando, "hora": hora}
                self.assertEqual(resolver_quando_data(entrada, DIA, _as(22)), AMANHA)

    def test_margem_vale_com_periodo_tambem(self):
        entrada = {"titulo": "x", "quando": "agorinha", "hora": "21:45"}
        self.assertEqual(resolver_quando_data(entrada, DIA, _as(22)), HOJE)

    def test_periodo_com_quando_data_de_hoje_do_modelo(self):
        entrada = {"titulo": "x", "quando": "de manhã", "quando_data": HOJE, "hora": "07:00"}
        self.assertEqual(resolver_quando_data(entrada, DIA, _as(22)), AMANHA)
        entrada = {"titulo": "x", "quando": "de manhã", "quando_data": "2026-11-06", "hora": "07:00"}
        self.assertEqual(resolver_quando_data(entrada, DIA, _as(22)), "2026-11-06")

    def test_periodo_sem_hora_continua_sem_data(self):
        self.assertIsNone(resolver_quando_data({"titulo": "x", "quando": "mais tarde"}, DIA, _as(22)))


class PrazoVagoEDiaDitoTestCase(unittest.TestCase):
    def test_prazo_vago_continua_sem_data(self):
        for quando in ("essa semana", "quando der", "algum dia", "fim de semana", "semana que vem", "esse mês",
                       "sem pressa"):
            with self.subTest(quando=quando):
                self.assertIsNone(resolver_quando_data({"titulo": "x", "quando": quando, "hora": "07:00"}, DIA,
                                                       _as(22)))

    def test_prazo_vago_com_data_do_modelo_usa_a_data(self):
        entrada = {"titulo": "x", "quando": "essa semana", "quando_data": "2026-11-05", "hora": "07:00"}
        self.assertEqual(resolver_quando_data(entrada, DIA, _as(22)), "2026-11-05")

    def test_dia_dito_e_hoje_dito_nao_mudam(self):
        casos = (({"quando": "hoje", "hora": "07:00"}, HOJE), ({"quando": "hoje de manhã", "hora": "07:00"}, HOJE),
                 ({"quando": "hoje à noite", "hora": "21:00"}, HOJE), ({"quando": "amanhã", "hora": "07:00"}, AMANHA),
                 ({"quando": "sexta", "hora": "07:00"}, "2026-11-06"))
        for entrada, esperado in casos:
            with self.subTest(entrada=entrada):
                self.assertEqual(resolver_quando_data({"titulo": "x", **entrada}, DIA, _as(22)), esperado)


class DescricaoTestCase(unittest.TestCase):
    def test_hora_explica_periodo_do_dia(self):
        tool = next(t for t in chat_mod.CHAT_TOOLS if t["name"] == "registrar_tarefa")
        desc = tool["input_schema"]["properties"]["hora"]["description"]
        self.assertIn("Periodo do dia", desc)
        self.assertIn("nao e dia", desc)


if __name__ == "__main__":
    unittest.main()
