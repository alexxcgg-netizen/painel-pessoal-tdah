# Faixa P4 (Fase 7): parser local (sem IA) + validacao/normalizacao +
# recusa de regra sobre vida amorosa/relacionamento. Nenhum destes testes
# toca banco nem rede - so o motor puro (assistente/regras.py).
import unittest

from assistente import regras as motor


class TestParserDiario(unittest.TestCase):
    def test_hora_com_h(self):
        bruto = motor.interpretar_regra_local("todo dia às 18h me lembra de tomar o remédio")
        self.assertEqual(bruto["gatilho"], "horario")
        self.assertEqual(bruto["condicao"], {"tipo": "diario", "hora": "18:00"})
        self.assertEqual(bruto["acao"], {"mensagem": "tomar o remédio"})

    def test_hora_com_dois_pontos(self):
        bruto = motor.interpretar_regra_local("todo dia as 07:30 me lembra de tomar agua")
        self.assertEqual(bruto["condicao"]["hora"], "07:30")

    def test_hora_com_h_e_minuto(self):
        bruto = motor.interpretar_regra_local("todo dia às 6h15 me lembra de acordar")
        self.assertEqual(bruto["condicao"]["hora"], "06:15")

    def test_variante_todos_os_dias(self):
        bruto = motor.interpretar_regra_local("todos os dias às 9h me lembra de alongar")
        self.assertIsNotNone(bruto)
        self.assertEqual(bruto["condicao"]["tipo"], "diario")

    def test_maiusculas(self):
        bruto = motor.interpretar_regra_local("TODO DIA ÀS 6H ME LEMBRA DE TOMAR REMEDIO")
        self.assertEqual(bruto["condicao"]["hora"], "06:00")
        self.assertEqual(bruto["acao"]["mensagem"], "TOMAR REMEDIO")

    def test_mensagem_preserva_conteudo_original(self):
        bruto = motor.interpretar_regra_local("todo dia às 18h me lembra de ligar pro contador")
        self.assertEqual(bruto["acao"]["mensagem"], "ligar pro contador")

    def test_sem_hora_nao_bate(self):
        self.assertIsNone(motor.interpretar_regra_local("todo dia me lembra de beber agua"))

    def test_frase_qualquer_nao_bate(self):
        self.assertIsNone(motor.interpretar_regra_local("oi tudo bem?"))

    def test_texto_vazio(self):
        self.assertIsNone(motor.interpretar_regra_local(""))
        self.assertIsNone(motor.interpretar_regra_local("   "))
        self.assertIsNone(motor.interpretar_regra_local(None))


class TestParserSemanal(unittest.TestCase):
    def test_segunda(self):
        bruto = motor.interpretar_regra_local("toda segunda às 9h me lembra de pagar o boleto")
        self.assertEqual(bruto["condicao"], {"tipo": "semanal", "dia_semana": 0, "hora": "09:00"})

    def test_sexta_feira_com_minuto(self):
        bruto = motor.interpretar_regra_local("toda sexta-feira as 20h30 me lembra de ligar pra minha mae")
        self.assertEqual(bruto["condicao"]["dia_semana"], 4)
        self.assertEqual(bruto["condicao"]["hora"], "20:30")

    def test_sabado_com_acento_e_concordancia_masculina(self):
        # "todo sábado" (concordancia masculina correta) tambem precisa bater,
        # nao so "toda segunda" etc (feminino).
        bruto = motor.interpretar_regra_local("todo sábado às 10h me lembra de lavar o carro")
        self.assertIsNotNone(bruto)
        self.assertEqual(bruto["condicao"]["dia_semana"], 5)

    def test_todos_os_dias_da_semana(self):
        casos = [
            ("toda terça às 8h me lembra de regar", 1),
            ("toda quarta às 8h me lembra de regar", 2),
            ("toda quinta às 8h me lembra de regar", 3),
            ("toda domingo às 8h me lembra de descansar", 6),
        ]
        for texto, esperado in casos:
            with self.subTest(texto=texto):
                bruto = motor.interpretar_regra_local(texto)
                self.assertEqual(bruto["condicao"]["dia_semana"], esperado)

    def test_sem_hora_no_padrao_semanal_nao_bate_como_semanal(self):
        # Sem "às HH" explicito, nao ha como extrair horario - cai pra IA.
        self.assertIsNone(motor.interpretar_regra_local("toda segunda me lembra de pagar o boleto"))


class TestParserGastoCategoria(unittest.TestCase):
    def test_exemplo_do_briefing(self):
        bruto = motor.interpretar_regra_local("me avisa se gastar mais de 300 com mercado na semana")
        self.assertEqual(bruto, {
            "gatilho": "gasto_categoria",
            "condicao": {"categoria": "mercado", "periodo": "semana", "valor_limite": 300.0},
            "acao": {},
            "texto": "me avisa se gastar mais de 300 com mercado na semana",
        })

    def test_com_virgula_decimal(self):
        bruto = motor.interpretar_regra_local("me avisa se eu gastar mais de 45,90 com uber no mes")
        self.assertEqual(bruto["condicao"]["valor_limite"], 45.9)
        self.assertEqual(bruto["condicao"]["periodo"], "mes")

    def test_hoje(self):
        bruto = motor.interpretar_regra_local("me avisa se gastar mais de 50 com uber hoje")
        self.assertEqual(bruto["condicao"]["periodo"], "dia")

    def test_sem_periodo_cai_no_padrao_mes(self):
        bruto = motor.interpretar_regra_local("me avisa se gastar mais de 100 com lazer")
        self.assertEqual(bruto["condicao"]["periodo"], "mes")

    def test_categoria_com_duas_palavras(self):
        bruto = motor.interpretar_regra_local("me avisa se gastar mais de 200 com cartao de credito na semana")
        self.assertEqual(bruto["condicao"]["categoria"], "cartao de credito")

    def test_periodo_antes_da_categoria_nao_bate_local(self):
        # Ordem incomum ("no mes com X") - fora do formato simples, cai pra IA.
        self.assertIsNone(motor.interpretar_regra_local("me avisa se eu gastar mais de 150,50 no mes com farmacia"))

    def test_valor_com_separador_de_milhar_nao_bate_local(self):
        self.assertIsNone(
            motor.interpretar_regra_local("me avisa se gastar mais de 1.500 com reforma na semana")
        )

    def test_verbo_no_passado(self):
        bruto = motor.interpretar_regra_local("me avisa se eu gastei mais de 80 com farmacia")
        self.assertIsNotNone(bruto)
        self.assertEqual(bruto["condicao"]["categoria"], "farmacia")


class TestNormalizarRegraHorario(unittest.TestCase):
    def test_diario_ok(self):
        regra = motor.normalizar_regra({
            "gatilho": "horario", "condicao": {"tipo": "diario", "hora": "18:00"},
            "acao": {"mensagem": "tomar remedio"}, "texto": "todo dia as 18h tomar remedio",
        })
        self.assertEqual(regra["condicao"]["hora"], "18:00")

    def test_hora_invalida_fora_do_intervalo(self):
        with self.assertRaises(ValueError):
            motor.normalizar_regra({
                "gatilho": "horario", "condicao": {"tipo": "diario", "hora": "25:00"},
                "acao": {}, "texto": "x",
            })

    def test_hora_formato_invalido(self):
        for hora in ("18", "18:60", "abc", "", None, "6:00 AM"):
            with self.subTest(hora=hora):
                with self.assertRaises(ValueError):
                    motor.normalizar_regra({
                        "gatilho": "horario", "condicao": {"tipo": "diario", "hora": hora},
                        "acao": {}, "texto": "x",
                    })

    def test_hora_aceita_so_hora_sem_minuto(self):
        regra = motor.normalizar_regra({
            "gatilho": "horario", "condicao": {"tipo": "diario", "hora": "7h"},
            "acao": {}, "texto": "lembrete as 7h",
        })
        self.assertEqual(regra["condicao"]["hora"], "07:00")

    def test_semanal_sem_dia_semana(self):
        with self.assertRaises(ValueError):
            motor.normalizar_regra({
                "gatilho": "horario", "condicao": {"tipo": "semanal", "hora": "09:00"},
                "acao": {}, "texto": "x",
            })

    def test_semanal_dia_fora_do_intervalo(self):
        with self.assertRaises(ValueError):
            motor.normalizar_regra({
                "gatilho": "horario",
                "condicao": {"tipo": "semanal", "hora": "09:00", "dia_semana": 7},
                "acao": {}, "texto": "x",
            })

    def test_tipo_data_valida(self):
        regra = motor.normalizar_regra({
            "gatilho": "horario",
            "condicao": {"tipo": "data", "hora": "10:00", "data": "2026-12-25"},
            "acao": {"mensagem": "abrir os presentes"}, "texto": "x",
        })
        self.assertEqual(regra["condicao"]["data"], "2026-12-25")

    def test_tipo_data_invalida(self):
        with self.assertRaises(ValueError):
            motor.normalizar_regra({
                "gatilho": "horario",
                "condicao": {"tipo": "data", "hora": "10:00", "data": "25/12/2026"},
                "acao": {}, "texto": "x",
            })

    def test_tipo_desconhecido(self):
        with self.assertRaises(ValueError):
            motor.normalizar_regra({
                "gatilho": "horario", "condicao": {"tipo": "mensal", "hora": "10:00"},
                "acao": {}, "texto": "x",
            })

    def test_mensagem_vazia_usa_o_texto_original(self):
        regra = motor.normalizar_regra({
            "gatilho": "horario", "condicao": {"tipo": "diario", "hora": "08:00"},
            "acao": {}, "texto": "me lembra de acordar",
        })
        self.assertEqual(regra["acao"]["mensagem"], "me lembra de acordar")


class TestNormalizarRegraGastoCategoria(unittest.TestCase):
    def test_ok(self):
        regra = motor.normalizar_regra({
            "gatilho": "gasto_categoria",
            "condicao": {"categoria": "Mercado", "periodo": "semana", "valor_limite": "300"},
            "acao": {}, "texto": "x",
        })
        self.assertEqual(regra["condicao"], {"categoria": "mercado", "periodo": "semana", "valor_limite": 300.0})

    def test_categoria_vazia(self):
        with self.assertRaises(ValueError):
            motor.normalizar_regra({
                "gatilho": "gasto_categoria",
                "condicao": {"categoria": "  ", "periodo": "mes", "valor_limite": 10},
                "acao": {}, "texto": "x",
            })

    def test_periodo_invalido(self):
        with self.assertRaises(ValueError):
            motor.normalizar_regra({
                "gatilho": "gasto_categoria",
                "condicao": {"categoria": "mercado", "periodo": "ano", "valor_limite": 10},
                "acao": {}, "texto": "x",
            })

    def test_valor_limite_zero_ou_negativo(self):
        for valor in (0, -10, "abc", None):
            with self.subTest(valor=valor):
                with self.assertRaises(ValueError):
                    motor.normalizar_regra({
                        "gatilho": "gasto_categoria",
                        "condicao": {"categoria": "mercado", "periodo": "mes", "valor_limite": valor},
                        "acao": {}, "texto": "x",
                    })

    def test_periodo_padrao_e_mes(self):
        regra = motor.normalizar_regra({
            "gatilho": "gasto_categoria",
            "condicao": {"categoria": "mercado", "valor_limite": 10},
            "acao": {}, "texto": "x",
        })
        self.assertEqual(regra["condicao"]["periodo"], "mes")


class TestNormalizarRegraOutrosGatilhos(unittest.TestCase):
    def test_habito_nao_feito_ate_com_nome(self):
        regra = motor.normalizar_regra({
            "gatilho": "habito_nao_feito_ate",
            "condicao": {"habito_nome": "Meditar", "hora": "20h"},
            "acao": {}, "texto": "x",
        })
        self.assertEqual(regra["condicao"], {"habito_nome": "Meditar", "hora": "20:00"})

    def test_habito_nao_feito_ate_sem_nome(self):
        with self.assertRaises(ValueError):
            motor.normalizar_regra({
                "gatilho": "habito_nao_feito_ate", "condicao": {}, "acao": {}, "texto": "x",
            })

    def test_habito_id_invalido(self):
        with self.assertRaises(ValueError):
            motor.normalizar_regra({
                "gatilho": "habito_nao_feito_ate",
                "condicao": {"habito_nome": "Meditar", "habito_id": "abc"},
                "acao": {}, "texto": "x",
            })

    def test_tarefa_vencida_condicao_vazia(self):
        regra = motor.normalizar_regra({
            "gatilho": "tarefa_vencida", "condicao": {}, "acao": {}, "texto": "x",
        })
        self.assertEqual(regra["condicao"], {})

    def test_sinal_iphone_tipo_valido(self):
        regra = motor.normalizar_regra({
            "gatilho": "sinal_iphone",
            "condicao": {"tipo": "cheguei", "lugar": "trabalho"},
            "acao": {"mensagem": "chegou!"}, "texto": "x",
        })
        self.assertEqual(regra["condicao"], {"tipo": "cheguei", "lugar": "trabalho"})
        self.assertEqual(regra["acao"], {"mensagem": "chegou!"})

    def test_sinal_iphone_tipo_invalido(self):
        with self.assertRaises(ValueError):
            motor.normalizar_regra({
                "gatilho": "sinal_iphone", "condicao": {"tipo": "explodiu"}, "acao": {}, "texto": "x",
            })

    def test_sinal_iphone_sem_lugar(self):
        regra = motor.normalizar_regra({
            "gatilho": "sinal_iphone", "condicao": {"tipo": "acordei"}, "acao": {}, "texto": "x",
        })
        self.assertNotIn("lugar", regra["condicao"])


class TestNormalizarRegraFormatoGeral(unittest.TestCase):
    def test_nao_e_dict(self):
        for bruto in (None, "texto", 42, [1, 2], True):
            with self.subTest(bruto=bruto):
                with self.assertRaises(ValueError):
                    motor.normalizar_regra(bruto)

    def test_gatilho_invalido(self):
        with self.assertRaises(ValueError):
            motor.normalizar_regra({"gatilho": "chute", "condicao": {}, "acao": {}, "texto": "x"})

    def test_condicao_nao_e_dict(self):
        with self.assertRaises(ValueError):
            motor.normalizar_regra({"gatilho": "tarefa_vencida", "condicao": "nada", "acao": {}, "texto": "x"})

    def test_texto_vazio(self):
        with self.assertRaises(ValueError):
            motor.normalizar_regra({"gatilho": "tarefa_vencida", "condicao": {}, "acao": {}, "texto": "   "})

    def test_texto_muito_longo_e_cortado(self):
        regra = motor.normalizar_regra({
            "gatilho": "tarefa_vencida", "condicao": {}, "acao": {}, "texto": "x" * 1000,
        })
        self.assertEqual(len(regra["texto"]), 400)

    def test_acao_none_vira_dict_vazio(self):
        regra = motor.normalizar_regra({
            "gatilho": "tarefa_vencida", "condicao": {}, "acao": None, "texto": "x",
        })
        self.assertEqual(regra["acao"], {})


class TestForaDeEscopo(unittest.TestCase):
    """Fora do escopo (docs/agentes/fase7-assistente.md): vida amorosa e
    relacionamento nunca viram regra - nem local, nem via normalizar_regra
    (defesa em profundidade pra regra digitada direto via rotas/p4_regras.py)."""

    FRASES_FORA_DE_ESCOPO = (
        "me avisa se minha namorada me mandar mensagem",
        "todo dia às 20h me lembra de ligar pro meu namorado",
        "me lembra de falar sobre casamento com minha esposa",
        "toda sexta às 19h me lembra de sair com meu marido",
        "me avisa se eu ficar com ciume de novo",
        "me lembra de conversar sobre o relacionamento",
        "ME AVISA SE MINHA NAMORADA LIGAR",
    )

    def test_fora_de_escopo_detecta(self):
        for frase in self.FRASES_FORA_DE_ESCOPO:
            with self.subTest(frase=frase):
                self.assertTrue(motor.fora_de_escopo(frase))

    def test_frase_normal_nao_e_fora_de_escopo(self):
        self.assertFalse(motor.fora_de_escopo("todo dia às 18h me lembra de tomar o remédio"))
        self.assertFalse(motor.fora_de_escopo("me avisa se gastar mais de 300 com mercado na semana"))

    def test_parser_local_nunca_devolve_regra_de_relacionamento(self):
        self.assertIsNone(
            motor.interpretar_regra_local("todo dia às 18h me lembra da minha namorada")
        )

    def test_normalizar_regra_recusa_mesmo_com_gatilho_valido(self):
        # Mesmo que o gatilho/condicao estejam bem formados, o TEXTO fala de
        # relacionamento -> recusado (cobre o caminho "confirmar" direto,
        # sem passar pelo parser/IA).
        with self.assertRaises(ValueError):
            motor.normalizar_regra({
                "gatilho": "horario",
                "condicao": {"tipo": "diario", "hora": "20:00"},
                "acao": {"mensagem": "x"},
                "texto": "todo dia às 20h me lembra de ligar pro meu namorado",
            })

    def test_interpretar_regra_recusa_sem_chamar_ia(self):
        from unittest.mock import patch

        from ia import core
        with patch.object(core, "chamar_ia") as mock_chamar:
            resultado = motor.interpretar_regra("me avisa se minha namorada me mandar mensagem")
        mock_chamar.assert_not_called()
        self.assertFalse(resultado["ok"])
        self.assertIn("vida amorosa", resultado["erro"].lower())


class TestMontarResumoRegra(unittest.TestCase):
    def test_horario_diario(self):
        resumo = motor.montar_resumo_regra({
            "gatilho": "horario", "condicao": {"tipo": "diario", "hora": "18:00"},
            "acao": {"mensagem": "tomar remedio"}, "texto": "x",
        })
        self.assertIn("todo dia", resumo)
        self.assertIn("18:00", resumo)
        self.assertIn("tomar remedio", resumo)

    def test_horario_semanal(self):
        resumo = motor.montar_resumo_regra({
            "gatilho": "horario",
            "condicao": {"tipo": "semanal", "dia_semana": 0, "hora": "09:00"},
            "acao": {"mensagem": "pagar boleto"}, "texto": "x",
        })
        self.assertIn("segunda", resumo)

    def test_gasto_categoria(self):
        resumo = motor.montar_resumo_regra({
            "gatilho": "gasto_categoria",
            "condicao": {"categoria": "mercado", "periodo": "semana", "valor_limite": 300.0},
            "acao": {}, "texto": "x",
        })
        self.assertIn("mercado", resumo)
        self.assertIn("300", resumo)
        self.assertIn("semana", resumo)

    def test_todos_os_gatilhos_produzem_resumo_nao_vazio(self):
        casos = [
            {"gatilho": "horario", "condicao": {"tipo": "diario", "hora": "08:00"}, "acao": {"mensagem": "x"}},
            {"gatilho": "gasto_categoria", "condicao": {"categoria": "y", "periodo": "mes", "valor_limite": 1}, "acao": {}},
            {"gatilho": "habito_nao_feito_ate", "condicao": {"habito_nome": "Meditar"}, "acao": {}},
            {"gatilho": "tarefa_vencida", "condicao": {}, "acao": {}},
            {"gatilho": "sinal_iphone", "condicao": {"tipo": "cheguei", "lugar": "casa"}, "acao": {}},
            {"gatilho": "sinal_iphone", "condicao": {"tipo": "dormir"}, "acao": {}},
        ]
        for regra in casos:
            regra["texto"] = "x"
            with self.subTest(gatilho=regra["gatilho"], condicao=regra["condicao"]):
                resumo = motor.montar_resumo_regra(regra)
                self.assertTrue(resumo)
                self.assertIsInstance(resumo, str)


if __name__ == "__main__":
    unittest.main()
