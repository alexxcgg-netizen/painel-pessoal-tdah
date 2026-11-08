"""Leva 08/11, 2a rodada (frente B, item 1): hora sem dia que ja passou vai pra amanha.

Caso do cacador: as 22h ele diz "remedio as 7" -> a tarefa ia pra hoje 07:00, saia na hora um push
de atraso e amanha as 7h nada. Agora: hora ja passada (mais de 30 min) sem dia dito = amanha;
passou so uns minutos ("as 14h" dito as 14:05) = agora, fica hoje; disse "hoje" = hoje.
"""
import os
import unittest
from datetime import date, datetime
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

from ia.funcoes import chat as chat_mod  # noqa: E402
from ia.funcoes.chat import resolver_quando_data  # noqa: E402

DIA = date(2026, 11, 3)
AMANHA = "2026-11-04"
HOJE = "2026-11-03"


def _as(h, m=0):
    return datetime(2026, 11, 3, h, m)


class HoraPassadaViraAmanhaTestCase(unittest.TestCase):
    def test_remedio_as_7_dito_de_noite_vai_pra_amanha(self):
        self.assertEqual(resolver_quando_data({"titulo": "Tomar o remedio", "hora": "07:00"}, DIA, _as(22)), AMANHA)

    def test_quando_data_de_hoje_mandado_pelo_modelo_tambem_vira_amanha(self):
        # o modelo antigo preenchia quando_data=hoje quando so tinha hora: sem "quando" = ele nao disse o dia
        entrada = {"titulo": "Tomar o remedio", "quando_data": HOJE, "hora": "07:00"}
        self.assertEqual(resolver_quando_data(entrada, DIA, _as(22)), AMANHA)

    def test_poucos_minutos_depois_e_agora_fica_hoje(self):
        for agora in (_as(14, 5), _as(14, 29), _as(14, 30)):
            with self.subTest(agora=agora):
                self.assertEqual(resolver_quando_data({"titulo": "x", "hora": "14:00"}, DIA, agora), HOJE)
        self.assertEqual(resolver_quando_data({"titulo": "x", "hora": "14:00"}, DIA, _as(14, 31)), AMANHA)

    def test_hora_que_ainda_vem_fica_hoje(self):
        self.assertEqual(resolver_quando_data({"titulo": "x", "hora": "23:00"}, DIA, _as(22)), HOJE)
        self.assertEqual(resolver_quando_data({"titulo": "x", "hora": "09:00"}, DIA, _as(6, 40)), HOJE)

    def test_disse_hoje_fica_hoje_mesmo_com_a_hora_passada(self):
        entrada = {"titulo": "x", "quando": "hoje", "quando_data": HOJE, "hora": "07:00"}
        self.assertEqual(resolver_quando_data(entrada, DIA, _as(22)), HOJE)
        self.assertEqual(resolver_quando_data({"titulo": "x", "quando": "hoje", "hora": "07:00"}, DIA, _as(22)), HOJE)

    def test_dia_dito_nao_muda(self):
        # "tarefa com dia ganha hora": o dia vem do "quando" e a hora escolhida nao mexe nele
        self.assertEqual(resolver_quando_data({"titulo": "x", "quando": "amanha", "hora": "07:00"}, DIA, _as(22)),
                         AMANHA)
        self.assertEqual(resolver_quando_data({"titulo": "x", "quando": "sexta", "hora": "08:30"}, DIA, _as(22)),
                         "2026-11-06")
        entrada = {"titulo": "x", "quando_data": "2026-11-10", "hora": "07:00"}
        self.assertEqual(resolver_quando_data(entrada, DIA, _as(22)), "2026-11-10")

    def test_quando_vago_continua_sem_dia(self):
        self.assertIsNone(resolver_quando_data({"quando": "quando der", "hora": "07:00"}, DIA, _as(22)))

    def test_madrugada_de_hoje_que_ja_passou(self):
        # 23h50 "me lembra 0h30" -> 0h30 de hoje ja passou ha 23h: e a 0h30 de amanha
        self.assertEqual(resolver_quando_data({"titulo": "x", "hora": "00:30"}, DIA, _as(23, 50)), AMANHA)

    def test_formatos_de_hora(self):
        for hora in ("7", "7h", "07h00", "7:00", " 07:00 "):
            with self.subTest(hora=hora):
                self.assertEqual(resolver_quando_data({"titulo": "x", "hora": hora}, DIA, _as(22)), AMANHA)
        for hora in ("de manha", "25:00", "07:75"):
            with self.subTest(hora=hora):
                self.assertEqual(resolver_quando_data({"titulo": "x", "hora": hora}, DIA, _as(22)), HOJE)

    def test_relogio_de_outro_dia_nao_decide(self):
        # teste com "hoje" fixo e maquina em outro dia: nada de empurrar pra amanha
        self.assertEqual(resolver_quando_data({"titulo": "x", "hora": "07:00"}, DIA, datetime(2026, 11, 5, 22)),
                         HOJE)

    def test_sem_agora_usa_o_relogio_de_brasilia(self):
        visto = {}

        class _Relogio(datetime):
            @classmethod
            def now(cls, tz=None):
                visto["tz"] = tz
                return datetime(2026, 11, 3, 22, 0, tzinfo=tz)

        with patch.object(chat_mod, "datetime", _Relogio):
            self.assertEqual(resolver_quando_data({"titulo": "x", "hora": "07:00"}, DIA), AMANHA)
        self.assertEqual(str(visto["tz"]), "America/Sao_Paulo")

    def test_regras_antigas_seguem(self):
        self.assertEqual(resolver_quando_data({"titulo": "x", "quando": "amanha"}, DIA), AMANHA)
        self.assertIsNone(resolver_quando_data({"titulo": "x"}, DIA, _as(22)))
        self.assertIsNone(resolver_quando_data("lixo", DIA))


class DescricaoDaFerramentaTestCase(unittest.TestCase):
    def _hora(self):
        tool = next(t for t in chat_mod.CHAT_TOOLS if t["name"] == "registrar_tarefa")
        return tool["input_schema"]["properties"]["hora"]["description"]

    def test_nao_manda_mais_preencher_a_data_de_hoje(self):
        desc = self._hora()
        self.assertNotIn("com a data de hoje", desc)
        self.assertIn("AMANHA", desc)
        self.assertIn("quando='hoje'", desc)


if __name__ == "__main__":
    unittest.main()
