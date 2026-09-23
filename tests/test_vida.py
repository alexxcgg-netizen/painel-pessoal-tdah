import unittest
from datetime import date, datetime, timedelta

import vida


class ValorCheckinTestCase(unittest.TestCase):
    def test_aceita_rotulos_e_numeros(self):
        self.assertEqual(vida.valor_checkin("ruim"), 1)
        self.assertEqual(vida.valor_checkin(" OK "), 2)
        self.assertEqual(vida.valor_checkin("Bom"), 3)
        self.assertEqual(vida.valor_checkin(3), 3)

    def test_rejeita_lixo(self):
        for ruim in [None, "", "otimo", 0, 4, -1, True, False, 2.5, [], {}]:
            self.assertIsNone(vida.valor_checkin(ruim), msg=repr(ruim))


class HiperfocoTestCase(unittest.TestCase):
    def test_ativo_ate_o_horario(self):
        agora = datetime(2026, 9, 23, 10, 0)
        self.assertTrue(vida.hiperfoco_ativo("2026-09-23T10:25:00", agora))
        self.assertFalse(vida.hiperfoco_ativo("2026-09-23T10:00:00", agora))
        self.assertFalse(vida.hiperfoco_ativo("2026-09-23T09:00:00", agora))

    def test_vazio_ou_invalido_nunca_ativo(self):
        agora = datetime(2026, 9, 23, 10, 0)
        for valor in [None, "", "amanha", "25/09/2026"]:
            self.assertFalse(vida.hiperfoco_ativo(valor, agora))
            self.assertEqual(vida.minutos_restantes_hiperfoco(valor, agora), 0)

    def test_minutos_restantes_arredonda_pra_cima(self):
        agora = datetime(2026, 9, 23, 10, 0, 0)
        self.assertEqual(vida.minutos_restantes_hiperfoco("2026-09-23T10:25:00", agora), 25)
        self.assertEqual(vida.minutos_restantes_hiperfoco("2026-09-23T10:00:30", agora), 1)


class EssencialHeuristicaTestCase(unittest.TestCase):
    HOJE = date(2026, 9, 23)

    def test_atrasada_e_com_hora_hoje_vem_primeiro(self):
        tarefas = [
            {"id": 1, "title": "sem prazo", "due_date": None, "hora": None},
            {"id": 2, "title": "atrasada", "due_date": "2026-09-18", "hora": None},
            {"id": 3, "title": "hoje com hora", "due_date": "2026-09-23", "hora": "15:00"},
            {"id": 4, "title": "futura", "due_date": "2026-10-10", "hora": None},
        ]
        self.assertEqual(vida.escolher_essencial_heuristica(tarefas, self.HOJE), [3, 2, 1])

    def test_rotina_perde_pra_tarefa_normal(self):
        tarefas = [
            {"id": 1, "title": "remedio", "due_date": "2026-09-23", "hora": None, "recorrente_origem_id": 9},
            {"id": 2, "title": "ligar banco", "due_date": "2026-09-23", "hora": None},
        ]
        self.assertEqual(vida.escolher_essencial_heuristica(tarefas, self.HOJE, n=1), [2])

    def test_lista_vazia_e_data_invalida(self):
        self.assertEqual(vida.escolher_essencial_heuristica([], self.HOJE), [])
        tarefas = [{"id": 7, "title": "x", "due_date": "lixo", "hora": None}]
        self.assertEqual(vida.escolher_essencial_heuristica(tarefas, self.HOJE), [7])


class DiasEmpacadaTestCase(unittest.TestCase):
    HOJE = date(2026, 9, 23)

    def test_com_prazo_trava_a_partir_de_3_dias(self):
        self.assertIsNone(vida.dias_empacada({"due_date": "2026-09-21"}, [], self.HOJE))
        self.assertEqual(vida.dias_empacada({"due_date": "2026-09-20"}, [], self.HOJE), 3)

    def test_sem_prazo_trava_depois_de_7_dias_sem_progresso(self):
        tarefa = {"due_date": None, "created_at": "2026-09-10 08:00:00"}
        self.assertEqual(vida.dias_empacada(tarefa, [], self.HOJE), 13)
        recente = {"due_date": None, "created_at": "2026-09-20 08:00:00"}
        self.assertIsNone(vida.dias_empacada(recente, [], self.HOJE))

    def test_passo_feito_na_ultima_semana_destrava(self):
        tarefa = {"due_date": None, "created_at": "2026-09-01 08:00:00"}
        subtasks = [{"completed_at": "2026-09-20 10:00:00"}]
        self.assertIsNone(vida.dias_empacada(tarefa, subtasks, self.HOJE))
        antigo = [{"completed_at": "2026-09-02 10:00:00"}]
        self.assertEqual(vida.dias_empacada(tarefa, antigo, self.HOJE), 22)

    def test_concluida_ou_rotina_nunca_trava(self):
        self.assertIsNone(vida.dias_empacada({"due_date": "2026-01-01", "completed_at": "x"}, [], self.HOJE))
        self.assertIsNone(vida.dias_empacada({"due_date": "2026-01-01", "recorrente_origem_id": 3}, [], self.HOJE))

    def test_dados_ruins_nao_quebram(self):
        self.assertIsNone(vida.dias_empacada({"due_date": "lixo"}, [], self.HOJE))
        self.assertIsNone(vida.dias_empacada({"due_date": None, "created_at": None}, [], self.HOJE))
        self.assertIsNone(vida.dias_empacada({"due_date": None, "created_at": "ontem"}, [], self.HOJE))


class ProximoVencimentoTestCase(unittest.TestCase):
    def test_ainda_nao_venceu_neste_mes(self):
        self.assertEqual(vida.proximo_vencimento(25, date(2026, 9, 23)), date(2026, 9, 25))
        self.assertEqual(vida.proximo_vencimento(23, date(2026, 9, 23)), date(2026, 9, 23))

    def test_ja_venceu_vai_pro_mes_seguinte(self):
        self.assertEqual(vida.proximo_vencimento(5, date(2026, 9, 23)), date(2026, 10, 5))

    def test_virada_de_ano(self):
        self.assertEqual(vida.proximo_vencimento(10, date(2026, 12, 20)), date(2027, 1, 10))

    def test_dia_31_em_mes_curto_vira_ultimo_dia(self):
        self.assertEqual(vida.proximo_vencimento(31, date(2026, 9, 10)), date(2026, 9, 30))
        self.assertEqual(vida.proximo_vencimento(31, date(2027, 2, 1)), date(2027, 2, 28))
        self.assertEqual(vida.proximo_vencimento(30, date(2028, 2, 1)), date(2028, 2, 29))


class PessoasTestCase(unittest.TestCase):
    HOJE = date(2026, 9, 23)

    def test_pessoas_sem_contato(self):
        pessoas = [
            {"id": 1, "nome": "Mae", "frequencia_dias": 7, "ultimo_contato": "2026-09-10", "criado_em": "2026-01-01 00:00:00"},
            {"id": 2, "nome": "Joao", "frequencia_dias": 30, "ultimo_contato": "2026-09-10", "criado_em": "2026-01-01 00:00:00"},
            {"id": 3, "nome": "Novo", "frequencia_dias": 7, "ultimo_contato": None, "criado_em": "2026-09-22 00:00:00"},
            {"id": 4, "nome": "Antigo", "frequencia_dias": 7, "ultimo_contato": None, "criado_em": "2026-09-01 00:00:00"},
        ]
        resultado = [(p["nome"], dias) for p, dias in vida.pessoas_sem_contato(pessoas, self.HOJE)]
        self.assertEqual(resultado, [("Antigo", 22), ("Mae", 13)])

    def test_achar_pessoa(self):
        pessoas = [{"id": 1, "nome": "Mãe"}, {"id": 2, "nome": "João Pedro"}, {"id": 3, "nome": "Vo Maria"}]
        self.assertEqual(vida.achar_pessoa(pessoas, "mae")["id"], 1)
        self.assertEqual(vida.achar_pessoa(pessoas, "joao")["id"], 2)
        self.assertEqual(vida.achar_pessoa(pessoas, "JOÃO PEDRO")["id"], 2)
        self.assertEqual(vida.achar_pessoa(pessoas, "maria")["id"], 3)
        self.assertIsNone(vida.achar_pessoa(pessoas, "carlos"))
        self.assertIsNone(vida.achar_pessoa(pessoas, ""))
        self.assertIsNone(vida.achar_pessoa([], "mae"))


class DiversosTestCase(unittest.TestCase):
    def test_sugestao_acao_data(self):
        self.assertIsNotNone(vida.sugestao_acao_data("Aniversário da Mãe"))
        self.assertIsNotNone(vida.sugestao_acao_data("niver do Joao"))
        self.assertIsNone(vida.sugestao_acao_data("Vencimento do seguro"))
        self.assertIsNone(vida.sugestao_acao_data(None))

    def test_momento_rotina(self):
        self.assertEqual(vida.momento_rotina(datetime(2026, 9, 23, 7, 0)), "manha")
        self.assertEqual(vida.momento_rotina(datetime(2026, 9, 23, 14, 59)), "manha")
        self.assertEqual(vida.momento_rotina(datetime(2026, 9, 23, 22, 0)), "noite")
        self.assertEqual(vida.momento_rotina(datetime(2026, 9, 23, 1, 0)), "noite")

    def test_rotina_manha_devida_janela_de_5_min(self):
        self.assertTrue(vida.rotina_manha_devida(datetime(2026, 9, 23, 7, 0), "07:00"))
        self.assertTrue(vida.rotina_manha_devida(datetime(2026, 9, 23, 7, 4, 59), "07:00"))
        self.assertFalse(vida.rotina_manha_devida(datetime(2026, 9, 23, 7, 5), "07:00"))
        self.assertFalse(vida.rotina_manha_devida(datetime(2026, 9, 23, 6, 59), "07:00"))
        self.assertTrue(vida.rotina_manha_devida(datetime(2026, 9, 23, 7, 2), "lixo"))

    def test_id_estavel_e_normalizar(self):
        self.assertEqual(vida.id_estavel("a", 1), vida.id_estavel("a", 1))
        self.assertNotEqual(vida.id_estavel("a", 1), vida.id_estavel("a", 2))
        self.assertLess(vida.id_estavel("x"), 2**62)
        self.assertEqual(vida.normalizar_nome("  Ãção   Téste "), "acao teste")
        self.assertEqual(vida.normalizar_nome(None), "")


class ResumoCurtoLockscreenTestCase(unittest.TestCase):
    def test_singular_sem_gasto(self):
        self.assertEqual(vida.resumo_curto_lockscreen(1, 0.0), "1 tarefa")

    def test_plural_com_gasto(self):
        self.assertEqual(vida.resumo_curto_lockscreen(3, 45.5), "3 tarefas · R$ 45.50 hoje")

    def test_zero_tarefas(self):
        self.assertEqual(vida.resumo_curto_lockscreen(0, 0.0), "0 tarefas")


class PriorizarEsperasTestCase(unittest.TestCase):
    def test_ordena_por_tempo_parado(self):
        hoje = date(2026, 9, 23)
        esperas = [
            {"id": 1, "quem": "A", "criado_em": "2026-09-20T10:00:00"},
            {"id": 2, "quem": "B", "criado_em": "2026-09-10T10:00:00"},
        ]
        resultado = vida.priorizar_esperas(esperas, hoje)
        self.assertEqual([r["id"] for r in resultado], [2, 1])
        self.assertEqual(resultado[0]["dias_parado"], 13)

    def test_importante_pula_a_frente_de_espera_mais_recente(self):
        hoje = date(2026, 9, 23)
        esperas = [
            {"id": 1, "quem": "recente-importante", "criado_em": "2026-09-21T10:00:00", "importante": 1},
            {"id": 2, "quem": "antiga-comum", "criado_em": "2026-09-18T10:00:00", "importante": 0},
        ]
        resultado = vida.priorizar_esperas(esperas, hoje)
        self.assertEqual(resultado[0]["id"], 1)

    def test_importante_nao_supera_espera_muito_mais_antiga(self):
        hoje = date(2026, 9, 23)
        esperas = [
            {"id": 1, "quem": "recente-importante", "criado_em": "2026-09-22T10:00:00", "importante": 1},
            {"id": 2, "quem": "muito-antiga", "criado_em": "2026-08-01T10:00:00", "importante": 0},
        ]
        resultado = vida.priorizar_esperas(esperas, hoje)
        self.assertEqual(resultado[0]["id"], 2)

    def test_lista_vazia(self):
        self.assertEqual(vida.priorizar_esperas([], date(2026, 9, 23)), [])


class TarefasCompativeisComEnergiaTestCase(unittest.TestCase):
    def _tarefas(self):
        return [
            {"id": 1, "title": "leve", "esforco": "baixa"},
            {"id": 2, "title": "media", "esforco": "media"},
            {"id": 3, "title": "pesada", "esforco": "alta"},
            {"id": 4, "title": "sem-classificacao", "esforco": None},
        ]

    def test_energia_baixa_so_pega_leves(self):
        resultado = vida.tarefas_compativeis_com_energia(self._tarefas(), "baixa")
        self.assertEqual([t["id"] for t in resultado], [1])

    def test_energia_media_pega_leve_e_media_e_sem_classificacao(self):
        resultado = vida.tarefas_compativeis_com_energia(self._tarefas(), "media")
        self.assertEqual([t["id"] for t in resultado], [1, 2, 4])

    def test_energia_alta_pega_todas(self):
        resultado = vida.tarefas_compativeis_com_energia(self._tarefas(), "alta")
        self.assertEqual([t["id"] for t in resultado], [1, 2, 3, 4])

    def test_nivel_invalido_devolve_vazio(self):
        self.assertEqual(vida.tarefas_compativeis_com_energia(self._tarefas(), "lixo"), [])


class IntervalosDePeriodoTestCase(unittest.TestCase):
    def test_intervalo_trimestre(self):
        self.assertEqual(vida.intervalo_trimestre(2026, 1), (date(2026, 1, 1), date(2026, 3, 31)))
        self.assertEqual(vida.intervalo_trimestre(2026, 3), (date(2026, 7, 1), date(2026, 9, 30)))
        self.assertEqual(vida.intervalo_trimestre(2026, 4), (date(2026, 10, 1), date(2026, 12, 31)))

    def test_intervalo_trimestre_invalido_levanta(self):
        with self.assertRaises(ValueError):
            vida.intervalo_trimestre(2026, 5)
        with self.assertRaises(ValueError):
            vida.intervalo_trimestre(2026, 0)

    def test_intervalo_ano(self):
        self.assertEqual(vida.intervalo_ano(2026), (date(2026, 1, 1), date(2026, 12, 31)))

    def test_trimestre_de(self):
        self.assertEqual(vida.trimestre_de(date(2026, 1, 15)), 1)
        self.assertEqual(vida.trimestre_de(date(2026, 4, 1)), 2)
        self.assertEqual(vida.trimestre_de(date(2026, 9, 23)), 3)
        self.assertEqual(vida.trimestre_de(date(2026, 12, 31)), 4)


if __name__ == "__main__":
    unittest.main()
