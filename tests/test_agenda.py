import unittest
from datetime import date

from agenda import dias_ate_o_fim_da_semana, maior_janela_livre, sugerir_dia_menos_corrido


class DiasAteOFimDaSemanaTestCase(unittest.TestCase):
    def test_de_segunda_ate_domingo(self):
        segunda = date(2026, 9, 21)  # segunda-feira
        dias = dias_ate_o_fim_da_semana(segunda)
        self.assertEqual(len(dias), 7)
        self.assertEqual(dias[0], segunda)
        self.assertEqual(dias[-1], date(2026, 9, 27))  # domingo

    def test_no_domingo_so_sobra_o_proprio_dia(self):
        domingo = date(2026, 9, 27)
        dias = dias_ate_o_fim_da_semana(domingo)
        self.assertEqual(dias, [domingo])

    def test_na_sexta_sobram_tres_dias(self):
        sexta = date(2026, 9, 25)
        dias = dias_ate_o_fim_da_semana(sexta)
        self.assertEqual(dias, [date(2026, 9, 25), date(2026, 9, 26), date(2026, 9, 27)])


class SugerirDiaMenosCorridoTestCase(unittest.TestCase):
    def test_escolhe_o_dia_com_menos_carga(self):
        dias = [date(2026, 9, 21), date(2026, 9, 22), date(2026, 9, 23)]
        carga = {"2026-09-21": 3, "2026-09-22": 0, "2026-09-23": 2}
        r = sugerir_dia_menos_corrido(carga, dias)
        self.assertEqual(r["data"], "2026-09-22")
        self.assertEqual(r["carga"], 0)
        self.assertEqual(r["dia_semana"], "terca")

    def test_empate_escolhe_o_dia_mais_proximo(self):
        dias = [date(2026, 9, 21), date(2026, 9, 22), date(2026, 9, 23)]
        r = sugerir_dia_menos_corrido({}, dias)
        self.assertEqual(r["data"], "2026-09-21")

    def test_dia_sem_entrada_no_dict_vale_zero(self):
        dias = [date(2026, 9, 21), date(2026, 9, 22)]
        carga = {"2026-09-21": 5}
        r = sugerir_dia_menos_corrido(carga, dias)
        self.assertEqual(r["data"], "2026-09-22")


class MaiorJanelaLivreTestCase(unittest.TestCase):
    def test_dia_totalmente_livre(self):
        r = maior_janela_livre([], "06:00", "22:00", 60)
        self.assertEqual(r, {"inicio": "06:00", "fim": "22:00", "minutos": 960})

    def test_acha_a_maior_folga_entre_compromissos(self):
        compromissos = [("08:00", "09:00"), ("12:00", "12:30"), ("18:00", "19:00")]
        r = maior_janela_livre(compromissos, "06:00", "22:00", 30)
        # a maior folga e das 12h30 as 18h (5h30 = 330min)
        self.assertEqual(r, {"inicio": "12:30", "fim": "18:00", "minutos": 330})

    def test_none_quando_nenhuma_folga_cabe_a_duracao(self):
        compromissos = [("06:00", "21:50")]
        r = maior_janela_livre(compromissos, "06:00", "22:00", 60)
        self.assertIsNone(r)

    def test_dia_totalmente_ocupado_retorna_none(self):
        compromissos = [("06:00", "22:00")]
        r = maior_janela_livre(compromissos, "06:00", "22:00", 15)
        self.assertIsNone(r)

    def test_compromisso_fora_da_janela_e_ignorado(self):
        compromissos = [("23:00", "23:30")]
        r = maior_janela_livre(compromissos, "06:00", "22:00", 60)
        self.assertEqual(r, {"inicio": "06:00", "fim": "22:00", "minutos": 960})

    def test_compromisso_cruzando_a_borda_e_cortado(self):
        compromissos = [("05:00", "07:00"), ("21:00", "23:00")]
        r = maior_janela_livre(compromissos, "06:00", "22:00", 60)
        self.assertEqual(r, {"inicio": "07:00", "fim": "21:00", "minutos": 840})

    def test_compromissos_desordenados_sao_ordenados_antes(self):
        compromissos = [("18:00", "19:00"), ("08:00", "09:00")]
        r = maior_janela_livre(compromissos, "06:00", "22:00", 30)
        self.assertEqual(r["inicio"], "09:00")
        self.assertEqual(r["fim"], "18:00")


if __name__ == "__main__":
    unittest.main()
