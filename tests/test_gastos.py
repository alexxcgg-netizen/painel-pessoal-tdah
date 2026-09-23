import unittest
from datetime import date

from gastos import (
    aplicar_apelidos,
    detectar_aumento_assinatura,
    detectar_gastos_recorrentes,
    e_cobranca_generica,
    historico_diario,
    resumo_semanal,
    sobra_do_mes,
    sugerir_categoria,
    total_gasto_fixo_mensal,
)


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


class ResumoSemanalTestCase(unittest.TestCase):
    """hoje = 2026-09-18 (sexta). Semana atual: 12 a 18/09. Semana
    anterior: 05 a 11/09."""

    def test_sem_gastos_retorna_zeros(self):
        r = resumo_semanal([], date(2026, 9, 18))
        self.assertEqual(r["total_semana"], 0)
        self.assertEqual(r["total_semana_anterior"], 0)
        self.assertIsNone(r["variacao_pct"])
        self.assertIsNone(r["categoria_top"])
        self.assertIsNone(r["categoria_top_valor"])

    def test_soma_gastos_da_semana_atual(self):
        expenses = [
            {"amount": 50.0, "category": "mercado", "created_at": "2026-09-14 10:00:00"},
            {"amount": 30.0, "category": "transporte", "created_at": "2026-09-18 08:00:00"},
        ]
        r = resumo_semanal(expenses, date(2026, 9, 18))
        self.assertEqual(r["total_semana"], 80.0)

    def test_soma_gastos_da_semana_anterior_separado(self):
        expenses = [
            {"amount": 100.0, "category": "mercado", "created_at": "2026-09-08 10:00:00"},
            {"amount": 20.0, "category": "lazer", "created_at": "2026-09-16 10:00:00"},
        ]
        r = resumo_semanal(expenses, date(2026, 9, 18))
        self.assertEqual(r["total_semana"], 20.0)
        self.assertEqual(r["total_semana_anterior"], 100.0)

    def test_ignora_gasto_de_tres_semanas_atras(self):
        expenses = [{"amount": 999.0, "category": "mercado", "created_at": "2026-08-20 10:00:00"}]
        r = resumo_semanal(expenses, date(2026, 9, 18))
        self.assertEqual(r["total_semana"], 0)
        self.assertEqual(r["total_semana_anterior"], 0)

    def test_variacao_percentual_positiva(self):
        expenses = [
            {"amount": 100.0, "category": "mercado", "created_at": "2026-09-08 10:00:00"},
            {"amount": 150.0, "category": "mercado", "created_at": "2026-09-14 10:00:00"},
        ]
        r = resumo_semanal(expenses, date(2026, 9, 18))
        self.assertEqual(r["variacao_pct"], 50)

    def test_variacao_percentual_negativa(self):
        expenses = [
            {"amount": 200.0, "category": "mercado", "created_at": "2026-09-08 10:00:00"},
            {"amount": 100.0, "category": "mercado", "created_at": "2026-09-14 10:00:00"},
        ]
        r = resumo_semanal(expenses, date(2026, 9, 18))
        self.assertEqual(r["variacao_pct"], -50)

    def test_sem_semana_anterior_variacao_fica_none(self):
        expenses = [{"amount": 50.0, "category": "mercado", "created_at": "2026-09-14 10:00:00"}]
        r = resumo_semanal(expenses, date(2026, 9, 18))
        self.assertIsNone(r["variacao_pct"])

    def test_categoria_top_identificada(self):
        expenses = [
            {"amount": 30.0, "category": "mercado", "created_at": "2026-09-14 10:00:00"},
            {"amount": 80.0, "category": "contas", "created_at": "2026-09-15 10:00:00"},
            {"amount": 20.0, "category": "lazer", "created_at": "2026-09-16 10:00:00"},
        ]
        r = resumo_semanal(expenses, date(2026, 9, 18))
        self.assertEqual(r["categoria_top"], "contas")
        self.assertEqual(r["categoria_top_valor"], 80.0)

    def test_categoria_ausente_vira_outros(self):
        expenses = [{"amount": 40.0, "category": None, "created_at": "2026-09-14 10:00:00"}]
        r = resumo_semanal(expenses, date(2026, 9, 18))
        self.assertEqual(r["categoria_top"], "outros")

    def test_borda_exata_dos_7_dias(self):
        expenses = [
            {"amount": 10.0, "category": "mercado", "created_at": "2026-09-12 00:00:01"},
            {"amount": 20.0, "category": "mercado", "created_at": "2026-09-11 23:59:59"},
        ]
        r = resumo_semanal(expenses, date(2026, 9, 18))
        self.assertEqual(r["total_semana"], 10.0)
        self.assertEqual(r["total_semana_anterior"], 20.0)


class SugerirCategoriaTestCase(unittest.TestCase):
    def test_sem_historico_nao_decide(self):
        self.assertIsNone(sugerir_categoria("SUPERMERCADO BOM PRECO", []))

    def test_descricao_vazia_nao_decide(self):
        historico = [{"category": "mercado", "description": "mercado bom preco"}]
        self.assertIsNone(sugerir_categoria("", historico))
        self.assertIsNone(sugerir_categoria(None, historico))

    def test_padrao_claro_decide_categoria(self):
        historico = [
            {"category": "mercado", "description": "compra supermercado bompreco"},
            {"category": "mercado", "description": "supermercado bompreco semana"},
            {"category": "mercado", "description": "supermercado bompreco mensal"},
        ]
        self.assertEqual(sugerir_categoria("PGTO SUPERMERCADO BOMPRECO LTDA", historico), "mercado")

    def test_padrao_ambiguo_nao_decide(self):
        """A mesma palavra aparecendo em categorias diferentes, sem uma clara
        dominante, deve ficar sem categoria em vez de arriscar um palpite."""
        historico = [
            {"category": "mercado", "description": "compra posto ipiranga conveniencia"},
            {"category": "transporte", "description": "combustivel posto ipiranga"},
        ]
        self.assertIsNone(sugerir_categoria("POSTO IPIRANGA", historico))

    def test_uma_unica_coincidencia_nao_decide(self):
        """Uma unica batida no historico e pouco pra confiar - precisa de
        pelo menos 2 gastos passados apontando pra mesma categoria."""
        historico = [{"category": "lazer", "description": "cinema shopping"}]
        self.assertIsNone(sugerir_categoria("CINEMA SHOPPING CENTER", historico))

    def test_usa_source_text_quando_sem_description(self):
        historico = [
            {"category": "contas", "source_text": "paguei a conta de luz da casa"},
            {"category": "contas", "source_text": "conta de luz atrasada"},
        ]
        self.assertEqual(sugerir_categoria("CIA ELETRICA - CONTA DE LUZ", historico), "contas")

    def test_gasto_sem_categoria_no_historico_e_ignorado(self):
        historico = [
            {"category": None, "description": "mercado bompreco"},
            {"category": None, "description": "mercado bompreco"},
        ]
        self.assertIsNone(sugerir_categoria("SUPERMERCADO BOMPRECO", historico))


def _gasto(descricao, valor, ano_mes_dia, categoria="contas"):
    return {
        "amount": valor,
        "category": categoria,
        "description": descricao,
        "created_at": f"{ano_mes_dia} 10:00:00",
    }


class DetectarGastosRecorrentesTestCase(unittest.TestCase):
    def test_sem_gastos_retorna_vazio(self):
        self.assertEqual(detectar_gastos_recorrentes([], date(2026, 9, 21)), [])

    def test_repete_em_2_meses_com_valor_igual_e_recorrente(self):
        gastos = [
            _gasto("Netflix", 39.90, "2026-07-15"),
            _gasto("Netflix", 39.90, "2026-08-15"),
        ]
        resultado = detectar_gastos_recorrentes(gastos, date(2026, 9, 21), minimo_meses=2)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["descricao"], "Netflix")
        self.assertEqual(resultado[0]["valor_medio"], 39.90)
        self.assertEqual(resultado[0]["meses_confirmados"], 2)

    def test_aparece_em_so_1_mes_nao_e_recorrente(self):
        gastos = [_gasto("Netflix", 39.90, "2026-09-15")]
        resultado = detectar_gastos_recorrentes(gastos, date(2026, 9, 21), minimo_meses=2)
        self.assertEqual(resultado, [])

    def test_mesma_descricao_duas_vezes_no_mesmo_mes_nao_conta_como_2_meses(self):
        gastos = [
            _gasto("Netflix", 39.90, "2026-09-01"),
            _gasto("Netflix", 39.90, "2026-09-15"),
        ]
        resultado = detectar_gastos_recorrentes(gastos, date(2026, 9, 21), minimo_meses=2)
        self.assertEqual(resultado, [])

    def test_valor_variando_muito_nao_e_recorrente(self):
        # mercado repete todo mes mas o valor varia muito - nao e "fixo"
        gastos = [
            _gasto("Mercado Central", 200.0, "2026-07-15", categoria="mercado"),
            _gasto("Mercado Central", 600.0, "2026-08-15", categoria="mercado"),
        ]
        resultado = detectar_gastos_recorrentes(gastos, date(2026, 9, 21))
        self.assertEqual(resultado, [])

    def test_valor_dentro_da_tolerancia_ainda_conta(self):
        gastos = [
            _gasto("Academia", 100.0, "2026-07-15"),
            _gasto("Academia", 105.0, "2026-08-15"),  # 5% de diferenca, tolerancia padrao e 15%
        ]
        resultado = detectar_gastos_recorrentes(gastos, date(2026, 9, 21), minimo_meses=2)
        self.assertEqual(len(resultado), 1)

    def test_descricoes_diferentes_nao_agrupam(self):
        gastos = [
            _gasto("Netflix", 39.90, "2026-07-15"),
            _gasto("Spotify", 39.90, "2026-08-15"),
        ]
        resultado = detectar_gastos_recorrentes(gastos, date(2026, 9, 21), minimo_meses=2)
        self.assertEqual(resultado, [])

    def test_gasto_fora_da_janela_de_meses_e_ignorado(self):
        gastos = [
            _gasto("Netflix", 39.90, "2026-01-15"),  # fora da janela de 3 meses
            _gasto("Netflix", 39.90, "2026-08-15"),
        ]
        resultado = detectar_gastos_recorrentes(gastos, date(2026, 9, 21), meses_analise=3, minimo_meses=2)
        self.assertEqual(resultado, [])

    def test_descricao_vazia_e_ignorada(self):
        gastos = [
            {"amount": 100, "category": "outros", "description": None, "created_at": "2026-07-15 10:00:00"},
            {"amount": 100, "category": "outros", "description": "", "created_at": "2026-08-15 10:00:00"},
        ]
        resultado = detectar_gastos_recorrentes(gastos, date(2026, 9, 21), minimo_meses=2)
        self.assertEqual(resultado, [])

    def test_usa_source_text_quando_nao_ha_description(self):
        gastos = [
            {"amount": 39.90, "category": "contas", "source_text": "netflix mensal", "created_at": "2026-07-15 10:00:00"},
            {"amount": 39.90, "category": "contas", "source_text": "netflix mensal", "created_at": "2026-08-15 10:00:00"},
        ]
        resultado = detectar_gastos_recorrentes(gastos, date(2026, 9, 21), minimo_meses=2)
        self.assertEqual(len(resultado), 1)

    def test_ordenado_do_maior_pro_menor_valor_medio(self):
        gastos = [
            _gasto("Netflix", 39.90, "2026-07-15"),
            _gasto("Netflix", 39.90, "2026-08-15"),
            _gasto("Aluguel", 1500.0, "2026-07-05"),
            _gasto("Aluguel", 1500.0, "2026-08-05"),
        ]
        resultado = detectar_gastos_recorrentes(gastos, date(2026, 9, 21), minimo_meses=2)
        self.assertEqual([r["descricao"] for r in resultado], ["Aluguel", "Netflix"])

    def test_3_meses_confirmados(self):
        gastos = [
            _gasto("Netflix", 39.90, "2026-06-15"),
            _gasto("Netflix", 39.90, "2026-07-15"),
            _gasto("Netflix", 39.90, "2026-08-15"),
        ]
        resultado = detectar_gastos_recorrentes(gastos, date(2026, 9, 21), meses_analise=4, minimo_meses=2)
        self.assertEqual(resultado[0]["meses_confirmados"], 3)


class DetectarAumentoAssinaturaTestCase(unittest.TestCase):
    def test_sem_gastos_retorna_vazio(self):
        self.assertEqual(detectar_aumento_assinatura([], date(2026, 9, 21)), [])

    def test_aumento_acima_do_limiar_e_detectado(self):
        gastos = [
            _gasto("Netflix", 39.90, "2026-07-15"),
            _gasto("Netflix", 39.90, "2026-08-15"),
            _gasto("Netflix", 44.90, "2026-09-15"),  # ~12.5% de aumento
        ]
        resultado = detectar_aumento_assinatura(gastos, date(2026, 9, 21), minimo_meses=2)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["descricao"], "Netflix")
        self.assertEqual(resultado[0]["valor_anterior_medio"], 39.90)
        self.assertEqual(resultado[0]["valor_novo"], 44.90)
        self.assertAlmostEqual(resultado[0]["aumento_pct"], 12.5, delta=0.1)

    def test_aumento_pequeno_dentro_do_limiar_nao_dispara(self):
        gastos = [
            _gasto("Academia", 100.0, "2026-07-15"),
            _gasto("Academia", 100.0, "2026-08-15"),
            _gasto("Academia", 102.0, "2026-09-15"),  # 2%, abaixo do limiar padrao de 5%
        ]
        resultado = detectar_aumento_assinatura(gastos, date(2026, 9, 21), minimo_meses=2)
        self.assertEqual(resultado, [])

    def test_preco_estavel_nao_dispara(self):
        gastos = [
            _gasto("Spotify", 21.90, "2026-07-15"),
            _gasto("Spotify", 21.90, "2026-08-15"),
            _gasto("Spotify", 21.90, "2026-09-15"),
        ]
        resultado = detectar_aumento_assinatura(gastos, date(2026, 9, 21), minimo_meses=2)
        self.assertEqual(resultado, [])

    def test_gasto_que_diminuiu_nao_dispara(self):
        gastos = [
            _gasto("Streaming X", 50.0, "2026-07-15"),
            _gasto("Streaming X", 50.0, "2026-08-15"),
            _gasto("Streaming X", 30.0, "2026-09-15"),
        ]
        resultado = detectar_aumento_assinatura(gastos, date(2026, 9, 21), minimo_meses=2)
        self.assertEqual(resultado, [])

    def test_ainda_nao_e_assinatura_estabelecida_nao_dispara(self):
        # so 1 ocorrencia anterior - nao chega no minimo_meses pra virar
        # "assinatura conhecida" antes de comparar com a nova
        gastos = [
            _gasto("Servico Novo", 20.0, "2026-08-15"),
            _gasto("Servico Novo", 40.0, "2026-09-15"),
        ]
        resultado = detectar_aumento_assinatura(gastos, date(2026, 9, 21), minimo_meses=2)
        self.assertEqual(resultado, [])

    def test_historico_instavel_nao_e_assinatura_e_nao_dispara(self):
        # as ANTERIORES ja variam muito entre si - nunca foi um valor
        # "fixo", entao nao da pra dizer que "subiu de preco"
        gastos = [
            _gasto("Mercado Central", 100.0, "2026-06-15", categoria="mercado"),
            _gasto("Mercado Central", 400.0, "2026-07-15", categoria="mercado"),
            _gasto("Mercado Central", 100.0, "2026-08-15", categoria="mercado"),
            _gasto("Mercado Central", 900.0, "2026-09-15", categoria="mercado"),
        ]
        resultado = detectar_aumento_assinatura(gastos, date(2026, 9, 21), meses_analise=4, minimo_meses=2)
        self.assertEqual(resultado, [])

    def test_segunda_cobranca_do_mesmo_mes_nao_conta_como_novo_aumento(self):
        gastos = [
            _gasto("Netflix", 39.90, "2026-07-15"),
            _gasto("Netflix", 39.90, "2026-08-15"),
            _gasto("Netflix", 39.90, "2026-09-01"),
            _gasto("Netflix", 60.0, "2026-09-20"),  # mesmo mes da 3a ocorrencia
        ]
        resultado = detectar_aumento_assinatura(gastos, date(2026, 9, 21), minimo_meses=2)
        self.assertEqual(resultado, [])

    def test_ordenado_do_maior_aumento_pro_menor(self):
        gastos = [
            _gasto("Netflix", 40.0, "2026-07-15"),
            _gasto("Netflix", 40.0, "2026-08-15"),
            _gasto("Netflix", 44.0, "2026-09-15"),  # 10%
            _gasto("Aluguel", 1000.0, "2026-07-05"),
            _gasto("Aluguel", 1000.0, "2026-08-05"),
            _gasto("Aluguel", 1300.0, "2026-09-05"),  # 30%
        ]
        resultado = detectar_aumento_assinatura(gastos, date(2026, 9, 21), minimo_meses=2)
        self.assertEqual([r["descricao"] for r in resultado], ["Aluguel", "Netflix"])

    def test_descricoes_diferentes_nao_se_confundem(self):
        gastos = [
            _gasto("Netflix", 40.0, "2026-07-15"),
            _gasto("Netflix", 40.0, "2026-08-15"),
            _gasto("Spotify", 44.0, "2026-09-15"),
        ]
        resultado = detectar_aumento_assinatura(gastos, date(2026, 9, 21), minimo_meses=2)
        self.assertEqual(resultado, [])


class TotalGastoFixoMensalTestCase(unittest.TestCase):
    def test_soma_vazia_e_zero(self):
        self.assertEqual(total_gasto_fixo_mensal([]), 0)

    def test_soma_varios_recorrentes(self):
        recorrentes = [{"valor_medio": 39.90}, {"valor_medio": 100.0}, {"valor_medio": 1500.0}]
        self.assertEqual(total_gasto_fixo_mensal(recorrentes), 1639.90)


class SobraDoMesTestCase(unittest.TestCase):
    def test_sobra_positiva(self):
        r = sobra_do_mes(renda_mes=3000.0, gasto_real_mes=2000.0, gasto_planejado_mes=0.0)
        self.assertEqual(r["renda_mes"], 3000.0)
        self.assertEqual(r["gasto_mes"], 2000.0)
        self.assertEqual(r["sobra"], 1000.0)

    def test_sobra_negativa_quando_gasta_mais_que_recebe(self):
        r = sobra_do_mes(renda_mes=1000.0, gasto_real_mes=1500.0, gasto_planejado_mes=0.0)
        self.assertEqual(r["sobra"], -500.0)

    def test_sem_nenhuma_renda_nem_gasto(self):
        r = sobra_do_mes(renda_mes=0.0, gasto_real_mes=0.0, gasto_planejado_mes=0.0)
        self.assertEqual(r["sobra"], 0.0)

    def test_sobra_considerando_planejado_desconta_o_planejado_da_sobra(self):
        r = sobra_do_mes(renda_mes=3000.0, gasto_real_mes=2000.0, gasto_planejado_mes=500.0)
        self.assertEqual(r["sobra"], 1000.0)
        self.assertEqual(r["gasto_planejado_mes"], 500.0)
        self.assertEqual(r["sobra_considerando_planejado"], 500.0)

    def test_planejado_pode_deixar_sobra_considerando_planejado_negativa(self):
        r = sobra_do_mes(renda_mes=1000.0, gasto_real_mes=800.0, gasto_planejado_mes=500.0)
        self.assertEqual(r["sobra"], 200.0)
        self.assertEqual(r["sobra_considerando_planejado"], -300.0)

    def test_arredonda_pra_duas_casas(self):
        r = sobra_do_mes(renda_mes=1000.333, gasto_real_mes=500.111, gasto_planejado_mes=0.0)
        self.assertEqual(r["renda_mes"], 1000.33)
        self.assertEqual(r["gasto_mes"], 500.11)


class ECobrancaGenericaTestCase(unittest.TestCase):
    def test_reconhece_apple_com(self):
        self.assertTrue(e_cobranca_generica("APPLE.COM/BILL"))
        self.assertTrue(e_cobranca_generica("apple.com/bill"))
        self.assertTrue(e_cobranca_generica("Compra Apple.Com"))

    def test_nao_reconhece_outras_descricoes(self):
        self.assertFalse(e_cobranca_generica("Netflix"))
        self.assertFalse(e_cobranca_generica("Mercado Central"))

    def test_none_ou_vazio_nao_e_generica(self):
        self.assertFalse(e_cobranca_generica(None))
        self.assertFalse(e_cobranca_generica(""))


class AplicarApelidosTestCase(unittest.TestCase):
    def test_sem_apelido_conhecido_passa_direto(self):
        gastos_reais = [{"amount": 14.90, "description": "APPLE.COM/BILL", "created_at": "2026-09-05"}]
        resultado = aplicar_apelidos(gastos_reais, {})
        self.assertEqual(resultado[0]["description"], "APPLE.COM/BILL")

    def test_com_apelido_troca_a_descricao(self):
        gastos_reais = [{"amount": 14.90, "description": "APPLE.COM/BILL", "created_at": "2026-09-05"}]
        apelidos = {("apple.com/bill", 14.90): "iCloud 200GB"}
        resultado = aplicar_apelidos(gastos_reais, apelidos)
        self.assertEqual(resultado[0]["description"], "iCloud 200GB")

    def test_valores_diferentes_nao_se_confundem(self):
        gastos_reais = [
            {"amount": 14.90, "description": "APPLE.COM/BILL", "created_at": "2026-09-05"},
            {"amount": 21.90, "description": "APPLE.COM/BILL", "created_at": "2026-09-06"},
        ]
        apelidos = {("apple.com/bill", 14.90): "iCloud 200GB", ("apple.com/bill", 21.90): "Apple Music"}
        resultado = aplicar_apelidos(gastos_reais, apelidos)
        self.assertEqual(resultado[0]["description"], "iCloud 200GB")
        self.assertEqual(resultado[1]["description"], "Apple Music")

    def test_nao_altera_a_lista_original(self):
        gastos_reais = [{"amount": 14.90, "description": "APPLE.COM/BILL", "created_at": "2026-09-05"}]
        aplicar_apelidos(gastos_reais, {("apple.com/bill", 14.90): "iCloud 200GB"})
        self.assertEqual(gastos_reais[0]["description"], "APPLE.COM/BILL")

    def test_usa_source_text_quando_sem_description(self):
        gastos_reais = [{"amount": 14.90, "description": None, "source_text": "apple.com/bill", "created_at": "2026-09-05"}]
        apelidos = {("apple.com/bill", 14.90): "iCloud 200GB"}
        resultado = aplicar_apelidos(gastos_reais, apelidos)
        self.assertEqual(resultado[0]["description"], "iCloud 200GB")

    def test_dois_apelidos_diferentes_agrupam_como_recorrentes_separados(self):
        gastos_reais = [
            {"amount": 14.90, "description": "APPLE.COM/BILL", "created_at": "2026-07-05"},
            {"amount": 14.90, "description": "APPLE.COM/BILL", "created_at": "2026-08-05"},
            {"amount": 21.90, "description": "APPLE.COM/BILL", "created_at": "2026-07-06"},
            {"amount": 21.90, "description": "APPLE.COM/BILL", "created_at": "2026-08-06"},
        ]
        apelidos = {("apple.com/bill", 14.90): "iCloud 200GB", ("apple.com/bill", 21.90): "Apple Music"}
        rotulados = aplicar_apelidos(gastos_reais, apelidos)
        recorrentes = detectar_gastos_recorrentes(rotulados, date(2026, 9, 21), minimo_meses=2)
        descricoes = {r["descricao"] for r in recorrentes}
        self.assertEqual(descricoes, {"iCloud 200GB", "Apple Music"})


if __name__ == "__main__":
    unittest.main()
