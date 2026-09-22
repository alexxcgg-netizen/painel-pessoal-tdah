import unittest
from datetime import date

from agenda import (
    HORARIOS_SUGERIDOS_DIA,
    dias_ate_o_fim_da_semana,
    distribuir_tarefas_na_semana,
    maior_janela_livre,
    proximos_n_dias,
    sugerir_dia_menos_corrido,
)


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

    def test_sem_produtividade_informada_comportamento_nao_muda(self):
        dias = [date(2026, 9, 21), date(2026, 9, 22), date(2026, 9, 23)]
        carga = {"2026-09-21": 3, "2026-09-22": 0, "2026-09-23": 2}
        r = sugerir_dia_menos_corrido(carga, dias, produtividade_por_dia_semana=None)
        self.assertEqual(r["data"], "2026-09-22")

    def test_produtividade_desempata_carga_igual(self):
        # segunda (21) e terca (22) empatam em carga; terca (weekday=1) tem
        # produtividade historica bem maior - deve vencer o empate.
        dias = [date(2026, 9, 21), date(2026, 9, 22)]
        carga = {"2026-09-21": 1, "2026-09-22": 1}
        r = sugerir_dia_menos_corrido(carga, dias, produtividade_por_dia_semana={0: 0.1, 1: 0.9})
        self.assertEqual(r["data"], "2026-09-22")

    def test_produtividade_nao_ganha_de_carga_bem_menor(self):
        # terca tem carga bem maior mesmo com produtividade alta - o bonus e
        # so um desempate fraco (peso 0.5), nunca deveria virar uma carga de
        # verdade bem mais leve.
        dias = [date(2026, 9, 21), date(2026, 9, 22)]
        carga = {"2026-09-21": 0, "2026-09-22": 5}
        r = sugerir_dia_menos_corrido(carga, dias, produtividade_por_dia_semana={0: 0.0, 1: 1.0})
        self.assertEqual(r["data"], "2026-09-21")

    def test_dia_sem_entrada_na_produtividade_nao_ganha_nem_perde_bonus(self):
        dias = [date(2026, 9, 21), date(2026, 9, 22)]
        carga = {"2026-09-21": 1, "2026-09-22": 1}
        r = sugerir_dia_menos_corrido(carga, dias, produtividade_por_dia_semana={1: 0.9})
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


class ProximosNDiasTestCase(unittest.TestCase):
    def test_gera_n_dias_a_partir_do_dado(self):
        inicio = date(2026, 9, 21)
        dias = proximos_n_dias(inicio, 5)
        self.assertEqual(dias, [date(2026, 9, 21 + i) for i in range(5)])

    def test_zero_dias_devolve_lista_vazia(self):
        self.assertEqual(proximos_n_dias(date(2026, 9, 21), 0), [])

    def test_atravessa_troca_de_mes(self):
        dias = proximos_n_dias(date(2026, 9, 29), 3)
        self.assertEqual(dias, [date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1)])


class DistribuirTarefasNaSemanaTestCase(unittest.TestCase):
    def test_espalha_pelos_dias_menos_carregados(self):
        dias = [date(2026, 9, 21), date(2026, 9, 22), date(2026, 9, 23)]
        # 21 ja tem 2 marcados, 22 e 23 estao livres - as duas tarefas novas
        # devem ir pros dias vazios, nao empilhar em cima do 21.
        carga = {"2026-09-21": 2}
        propostas = distribuir_tarefas_na_semana(carga, dias, ["lavar o carro", "estudar meteorologia"])
        self.assertEqual(len(propostas), 2)
        dias_escolhidos = {p["dia"] for p in propostas}
        self.assertNotIn("2026-09-21", dias_escolhidos)
        self.assertEqual(dias_escolhidos, {"2026-09-22", "2026-09-23"})

    def test_titulo_preservado_na_proposta(self):
        dias = [date(2026, 9, 21)]
        propostas = distribuir_tarefas_na_semana({}, dias, ["cotar portas"])
        self.assertEqual(propostas[0]["titulo"], "cotar portas")
        self.assertIn(propostas[0]["hora"], HORARIOS_SUGERIDOS_DIA)

    def test_mais_tarefas_que_horarios_do_dia_nao_repete_horario_no_mesmo_dia(self):
        # so 1 dia candidato - todas as tarefas caem nele, mas cada uma pega
        # um horario diferente de HORARIOS_SUGERIDOS_DIA, em ordem.
        dias = [date(2026, 9, 21)]
        titulos = [f"tarefa {i}" for i in range(len(HORARIOS_SUGERIDOS_DIA))]
        propostas = distribuir_tarefas_na_semana({}, dias, titulos)
        horarios_usados = [p["hora"] for p in propostas]
        self.assertEqual(horarios_usados, HORARIOS_SUGERIDOS_DIA)

    def test_horario_nunca_cai_em_almoco_ou_janta(self):
        for h in HORARIOS_SUGERIDOS_DIA:
            hora, minuto = h.split(":")
            minutos_do_dia = int(hora) * 60 + int(minuto)
            self.assertFalse(12 * 60 <= minutos_do_dia < 14 * 60, f"{h} cai no almoco")
            self.assertFalse(18 * 60 <= minutos_do_dia < 20 * 60, f"{h} cai na janta")

    def test_lista_vazia_devolve_lista_vazia(self):
        self.assertEqual(distribuir_tarefas_na_semana({}, [date(2026, 9, 21)], []), [])

    def test_carga_simulada_nao_afeta_carga_por_dia_original(self):
        carga_original = {"2026-09-21": 0}
        dias = [date(2026, 9, 21), date(2026, 9, 22)]
        distribuir_tarefas_na_semana(carga_original, dias, ["a", "b", "c"])
        self.assertEqual(carga_original, {"2026-09-21": 0})


if __name__ == "__main__":
    unittest.main()
