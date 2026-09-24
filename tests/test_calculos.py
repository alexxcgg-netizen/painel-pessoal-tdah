import unittest
from datetime import date, datetime
from decimal import Decimal

import calculos


D = Decimal


class DecTestCase(unittest.TestCase):
    """Helper interno _dec, testado indiretamente por todas as funcoes
    publicas, mas com alguns casos diretos pra deixar claro o contrato."""

    def test_aceita_int_float_str_decimal(self):
        self.assertEqual(calculos._dec(10), D("10"))
        self.assertEqual(calculos._dec(10.5), D("10.5"))
        self.assertEqual(calculos._dec("10.5"), D("10.5"))
        self.assertEqual(calculos._dec(D("10.5")), D("10.5"))
        self.assertEqual(calculos._dec("10,5"), D("10.5"))

    def test_float_nao_herda_imprecisao_binaria(self):
        # Decimal(0.1) != Decimal("0.1") - _dec tem que passar por str().
        self.assertEqual(calculos._dec(0.1), D("0.1"))

    def test_rejeita_lixo(self):
        for ruim in [None, "", "abc", [], {}, object(), True, False]:
            with self.assertRaises(ValueError, msg=repr(ruim)):
                calculos._dec(ruim)

    def test_rejeita_infinito_e_nan(self):
        for ruim in [float("inf"), float("-inf"), float("nan")]:
            with self.assertRaises(ValueError):
                calculos._dec(ruim)


class ParaDataTestCase(unittest.TestCase):
    def test_aceita_date_datetime_string(self):
        self.assertEqual(calculos._para_data(date(2026, 3, 1)), date(2026, 3, 1))
        self.assertEqual(calculos._para_data(datetime(2026, 3, 1, 10, 30)), date(2026, 3, 1))
        self.assertEqual(calculos._para_data("2026-03-01"), date(2026, 3, 1))
        self.assertEqual(calculos._para_data("2026-03-01T10:30:00"), date(2026, 3, 1))

    def test_rejeita_invalida(self):
        for ruim in [None, "", "31/03/2026", "2026-13-40", "amanha", 123, []]:
            with self.assertRaises(ValueError, msg=repr(ruim)):
                calculos._para_data(ruim)


class SomarMesesTestCase(unittest.TestCase):
    def test_soma_simples(self):
        self.assertEqual(calculos._somar_meses(date(2026, 1, 15), 1), date(2026, 2, 15))
        self.assertEqual(calculos._somar_meses(date(2026, 1, 15), 12), date(2027, 1, 15))

    def test_comprime_fim_de_mes(self):
        self.assertEqual(calculos._somar_meses(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(calculos._somar_meses(date(2024, 1, 31), 1), date(2024, 2, 29))  # bissexto

    def test_zero_meses_e_a_propria_data(self):
        self.assertEqual(calculos._somar_meses(date(2026, 5, 20), 0), date(2026, 5, 20))

    def test_vira_o_ano(self):
        self.assertEqual(calculos._somar_meses(date(2026, 11, 30), 3), date(2027, 2, 28))


class PercentualMetaTestCase(unittest.TestCase):
    def test_casos_basicos(self):
        self.assertEqual(calculos.percentual_meta(50, 100), D("50.00"))
        self.assertEqual(calculos.percentual_meta(0, 100), D("0.00"))
        self.assertEqual(calculos.percentual_meta(100, 100), D("100.00"))
        self.assertEqual(calculos.percentual_meta(33, 100), D("33.00"))

    def test_trava_em_100_quando_passa_do_alvo(self):
        self.assertEqual(calculos.percentual_meta(150, 100), D("100.00"))
        self.assertEqual(calculos.percentual_meta(10_000_000, 1), D("100.00"))

    def test_atual_negativo_vira_zero(self):
        self.assertEqual(calculos.percentual_meta(-50, 100), D("0.00"))

    def test_alvo_zero_ou_negativo_nao_quebra(self):
        self.assertEqual(calculos.percentual_meta(50, 0), D("0.00"))
        self.assertEqual(calculos.percentual_meta(50, -100), D("0.00"))

    def test_arredondamento_bancario(self):
        # 1/3 * 100 = 33.333...  -> 33.33
        self.assertEqual(calculos.percentual_meta(1, 3), D("33.33"))

    def test_fuzz_nunca_sai_do_intervalo_0_100(self):
        casos = [
            (0, 1), (1, 1), (2, 1), (-1, 1), (-999999, 1),
            (999999999999, 1), (0.01, 0.01), (0.0001, 100),
            (100, 100), (99.99, 100), (100.01, 100),
        ]
        for atual, alvo in casos:
            pct = calculos.percentual_meta(atual, alvo)
            self.assertGreaterEqual(pct, D("0.00"), msg=(atual, alvo))
            self.assertLessEqual(pct, D("100.00"), msg=(atual, alvo))


class ProjecaoMetaTestCase(unittest.TestCase):
    HOJE = date(2026, 9, 24)

    def test_meta_ja_batida(self):
        r = calculos.projecao_meta(100, 100, 50, self.HOJE)
        self.assertTrue(r["atingivel"])
        self.assertEqual(r["meses_necessarios"], 0)
        self.assertEqual(r["falta"], D("0.00"))
        self.assertEqual(r["data_prevista"], self.HOJE)

    def test_meta_passada_do_alvo(self):
        r = calculos.projecao_meta(150, 100, 50, self.HOJE)
        self.assertTrue(r["atingivel"])
        self.assertEqual(r["meses_necessarios"], 0)

    def test_projecao_exata(self):
        # falta 500, aporta 100/mes -> 5 meses
        r = calculos.projecao_meta(0, 500, 100, self.HOJE)
        self.assertTrue(r["atingivel"])
        self.assertEqual(r["meses_necessarios"], 5)
        self.assertEqual(r["data_prevista"], date(2027, 2, 24))

    def test_projecao_arredonda_pra_cima(self):
        # falta 501, aporta 100/mes -> 5 nao basta, precisa de 6
        r = calculos.projecao_meta(0, 501, 100, self.HOJE)
        self.assertEqual(r["meses_necessarios"], 6)

    def test_aporte_zero_ou_negativo_nunca_atinge(self):
        for aporte in [0, -10, -0.01]:
            r = calculos.projecao_meta(0, 100, aporte, self.HOJE)
            self.assertFalse(r["atingivel"], msg=aporte)
            self.assertIsNone(r["meses_necessarios"])
            self.assertIsNone(r["data_prevista"])

    def test_alvo_invalido_conta_como_atingida(self):
        r = calculos.projecao_meta(10, 0, 50, self.HOJE)
        self.assertTrue(r["atingivel"])
        self.assertEqual(r["falta"], D("0.00"))

    def test_aceita_hoje_como_string(self):
        r = calculos.projecao_meta(0, 200, 100, "2026-09-24")
        self.assertEqual(r["data_prevista"], date(2026, 11, 24))

    def test_hoje_invalido_levanta(self):
        with self.assertRaises(ValueError):
            calculos.projecao_meta(0, 100, 10, "nao e data")


class ParcelaPriceTestCase(unittest.TestCase):
    def test_sem_juros_e_divisao_simples(self):
        self.assertEqual(calculos.parcela_price(1200, 0, 12), D("100.00"))

    def test_com_juros_conhecido(self):
        # 1000 emprestado, 2% a.m., 12x -> parcela ~94.56 (valor de referencia
        # da formula Price padrao)
        p = calculos.parcela_price(1000, "0.02", 12)
        self.assertEqual(p, D("94.56"))

    def test_valor_zero(self):
        self.assertEqual(calculos.parcela_price(0, 0.02, 12), D("0.00"))

    def test_n_invalido_levanta(self):
        for n in [0, -1, -12, 1.5, "abc", None]:
            with self.assertRaises(ValueError, msg=n):
                calculos.parcela_price(1000, 0.02, n)

    def test_taxa_menos_100_por_cento_levanta(self):
        with self.assertRaises(ValueError):
            calculos.parcela_price(1000, -1, 12)
        with self.assertRaises(ValueError):
            calculos.parcela_price(1000, -1.5, 12)

    def test_n_igual_1(self):
        # 1 parcela = o proprio valor + 1 periodo de juros
        p = calculos.parcela_price(1000, 0.02, 1)
        self.assertEqual(p, D("1020.00"))

    def test_fuzz_valores_grandes_e_pequenos(self):
        casos = [
            (0.01, 0.0, 1), (999999999.99, 0.05, 360), (1, 0.001, 240),
            (50000, 0.015, 60), (10, 0, 3), (1000000, 0.1, 2),
        ]
        for valor, taxa, n in casos:
            p = calculos.parcela_price(valor, taxa, n)
            self.assertIsInstance(p, Decimal, msg=(valor, taxa, n))
            self.assertGreaterEqual(p, D("0.00"), msg=(valor, taxa, n))


class TabelaAmortizacaoTestCase(unittest.TestCase):
    def test_price_saldo_final_zero_e_soma_bate(self):
        tabela = calculos.tabela_amortizacao(1000, 0.02, 12, "price")
        self.assertEqual(len(tabela), 12)
        self.assertEqual(tabela[-1]["saldo_devedor"], D("0.00"))
        soma_amortizacao = sum((l["amortizacao"] for l in tabela), D("0"))
        self.assertEqual(soma_amortizacao, D("1000.00"))
        for linha in tabela:
            self.assertEqual(linha["valor_parcela"], linha["juros"] + linha["amortizacao"])

    def test_sac_amortizacao_fixa_parcela_decrescente(self):
        tabela = calculos.tabela_amortizacao(1200, 0.02, 12, "sac")
        self.assertEqual(len(tabela), 12)
        self.assertEqual(tabela[-1]["saldo_devedor"], D("0.00"))
        amortizacoes = [l["amortizacao"] for l in tabela[:-1]]
        self.assertTrue(all(a == amortizacoes[0] for a in amortizacoes))
        parcelas = [l["valor_parcela"] for l in tabela]
        self.assertEqual(parcelas, sorted(parcelas, reverse=True))
        soma_amortizacao = sum((l["amortizacao"] for l in tabela), D("0"))
        self.assertEqual(soma_amortizacao, D("1200.00"))

    def test_uma_parcela_so(self):
        tabela = calculos.tabela_amortizacao(500, 0.03, 1, "price")
        self.assertEqual(len(tabela), 1)
        self.assertEqual(tabela[0]["saldo_devedor"], D("0.00"))
        self.assertEqual(tabela[0]["amortizacao"], D("500.00"))

    def test_sistema_invalido_levanta(self):
        for sistema in ["PRICE_ERRADO", "", None, "sac2", 123]:
            with self.assertRaises(ValueError, msg=sistema):
                calculos.tabela_amortizacao(1000, 0.02, 12, sistema)

    def test_sistema_case_insensitive(self):
        a = calculos.tabela_amortizacao(1000, 0.02, 6, "PRICE")
        b = calculos.tabela_amortizacao(1000, 0.02, 6, "price")
        self.assertEqual(a, b)

    def test_n_invalido_levanta(self):
        for n in [0, -5, 2.5]:
            with self.assertRaises(ValueError, msg=n):
                calculos.tabela_amortizacao(1000, 0.02, n)

    def test_fuzz_varias_combinacoes_fecham_saldo_zero(self):
        casos = [
            (100, 0.0, 3), (1_000_000, 0.089, 24), (0.5, 0.02, 5),
            (999999.99, 0.01, 120), (10, 0.5, 4),
        ]
        for valor, taxa, n in casos:
            for sistema in ("price", "sac"):
                tabela = calculos.tabela_amortizacao(valor, taxa, n, sistema)
                self.assertEqual(tabela[-1]["saldo_devedor"], D("0.00"), msg=(valor, taxa, n, sistema))


class JurosCompostosTestCase(unittest.TestCase):
    def test_sem_aporte(self):
        r = calculos.juros_compostos(1000, 0.10, 2)
        self.assertEqual(r["saldo_final"], D("1210.00"))
        self.assertEqual(r["total_aportado"], D("1000.00"))
        self.assertEqual(r["total_juros"], D("210.00"))

    def test_com_aporte_mensal(self):
        r = calculos.juros_compostos(0, 0.01, 3, 100)
        # mes1: 0*1.01+100=100 ; mes2: 100*1.01+100=201 ; mes3: 201*1.01+100=303.01
        self.assertEqual(r["saldo_final"], D("303.01"))
        self.assertEqual(r["total_aportado"], D("300.00"))

    def test_zero_periodos_nao_muda_nada(self):
        r = calculos.juros_compostos(500, 0.05, 0, 50)
        self.assertEqual(r["saldo_final"], D("500.00"))
        self.assertEqual(r["total_aportado"], D("500.00"))
        self.assertEqual(r["total_juros"], D("0.00"))

    def test_taxa_zero_so_soma_aportes(self):
        r = calculos.juros_compostos(100, 0, 5, 20)
        self.assertEqual(r["saldo_final"], D("200.00"))
        self.assertEqual(r["total_juros"], D("0.00"))

    def test_taxa_negativa_saldo_encolhe(self):
        r = calculos.juros_compostos(1000, -0.1, 1)
        self.assertEqual(r["saldo_final"], D("900.00"))

    def test_n_periodos_negativo_levanta(self):
        with self.assertRaises(ValueError):
            calculos.juros_compostos(1000, 0.1, -1)

    def test_n_periodos_fracionario_levanta(self):
        with self.assertRaises(ValueError):
            calculos.juros_compostos(1000, 0.1, 2.5)

    def test_fuzz_grandes_e_pequenos(self):
        casos = [
            (0, 0, 0), (1, 1, 12), (999999999, 0.2, 60),
            (0.01, 0.001, 360), (-500, 0.05, 12),  # saldo inicial negativo (divida)
        ]
        for principal, taxa, n in casos:
            r = calculos.juros_compostos(principal, taxa, n)
            self.assertIsInstance(r["saldo_final"], Decimal, msg=(principal, taxa, n))


class TotalPorCategoriaTestCase(unittest.TestCase):
    def test_soma_basica(self):
        itens = [
            {"categoria": "mercado", "valor": 50},
            {"categoria": "mercado", "valor": 30.5},
            {"categoria": "lazer", "valor": 20},
        ]
        self.assertEqual(
            calculos.total_por_categoria(itens),
            {"mercado": D("80.50"), "lazer": D("20.00")},
        )

    def test_sem_categoria_vira_outros(self):
        itens = [{"valor": 10}, {"categoria": "", "valor": 5}, {"categoria": None, "valor": 1}]
        self.assertEqual(calculos.total_por_categoria(itens), {"outros": D("16.00")})

    def test_lista_vazia(self):
        self.assertEqual(calculos.total_por_categoria([]), {})

    def test_valor_faltando_levanta(self):
        with self.assertRaises(ValueError):
            calculos.total_por_categoria([{"categoria": "x"}])

    def test_item_nao_dict_levanta(self):
        with self.assertRaises(ValueError):
            calculos.total_por_categoria(["nao e dict"])

    def test_categoria_nao_string_levanta(self):
        with self.assertRaises(ValueError):
            calculos.total_por_categoria([{"categoria": 123, "valor": 10}])

    def test_valor_negativo_soma_normal(self):
        itens = [{"categoria": "a", "valor": 100}, {"categoria": "a", "valor": -30}]
        self.assertEqual(calculos.total_por_categoria(itens), {"a": D("70.00")})

    def test_fuzz_muitos_itens(self):
        itens = [{"categoria": f"cat{i % 5}", "valor": i} for i in range(200)]
        totais = calculos.total_por_categoria(itens)
        self.assertEqual(len(totais), 5)
        self.assertEqual(sum(totais.values(), D("0")), D(str(sum(range(200)))) + D("0.00"))


class SaldoAposTestCase(unittest.TestCase):
    def test_sem_tipo_usa_sinal(self):
        r = calculos.saldo_apos(1000, [{"valor": 100}, {"valor": -50}])
        self.assertEqual(r, D("1050.00"))

    def test_com_tipo_ignora_sinal_da_entrada(self):
        r = calculos.saldo_apos(1000, [{"valor": -100, "tipo": "entrada"}])
        self.assertEqual(r, D("1100.00"))
        r2 = calculos.saldo_apos(1000, [{"valor": 100, "tipo": "saida"}])
        self.assertEqual(r2, D("900.00"))

    def test_lista_vazia_devolve_saldo(self):
        self.assertEqual(calculos.saldo_apos(500.5, []), D("500.50"))

    def test_saldo_pode_ficar_negativo(self):
        r = calculos.saldo_apos(100, [{"valor": 500, "tipo": "saida"}])
        self.assertEqual(r, D("-400.00"))

    def test_tipo_invalido_levanta(self):
        with self.assertRaises(ValueError):
            calculos.saldo_apos(100, [{"valor": 10, "tipo": "transferencia"}])

    def test_lancamento_sem_valor_levanta(self):
        with self.assertRaises(ValueError):
            calculos.saldo_apos(100, [{"tipo": "entrada"}])

    def test_fuzz_muitos_lancamentos(self):
        lancs = [{"valor": 1, "tipo": "entrada"} for _ in range(1000)]
        self.assertEqual(calculos.saldo_apos(0, lancs), D("1000.00"))


class ParcelasRestantesTestCase(unittest.TestCase):
    def test_casos_basicos(self):
        self.assertEqual(calculos.parcelas_restantes(12, 0), 12)
        self.assertEqual(calculos.parcelas_restantes(12, 5), 7)
        self.assertEqual(calculos.parcelas_restantes(12, 12), 0)

    def test_ja_quitado_nunca_negativo(self):
        self.assertEqual(calculos.parcelas_restantes(12, 20), 0)
        self.assertEqual(calculos.parcelas_restantes(1, 999999), 0)

    def test_n_total_invalido_levanta(self):
        for n in [0, -1, 1.5]:
            with self.assertRaises(ValueError, msg=n):
                calculos.parcelas_restantes(n, 0)

    def test_parcela_atual_invalida_levanta(self):
        for p in [-1, 1.5, "abc"]:
            with self.assertRaises(ValueError, msg=p):
                calculos.parcelas_restantes(12, p)


class DataUltimaParcelaTestCase(unittest.TestCase):
    def test_n_1_e_a_propria_primeira(self):
        self.assertEqual(calculos.data_ultima_parcela("2026-01-15", 1), date(2026, 1, 15))

    def test_varias_parcelas(self):
        self.assertEqual(calculos.data_ultima_parcela("2026-01-15", 12), date(2026, 12, 15))

    def test_fim_de_mes_bissexto(self):
        self.assertEqual(calculos.data_ultima_parcela("2024-01-31", 2), date(2024, 2, 29))
        self.assertEqual(calculos.data_ultima_parcela("2023-01-31", 2), date(2023, 2, 28))

    def test_n_invalido_levanta(self):
        for n in [0, -1, 1.5]:
            with self.assertRaises(ValueError, msg=n):
                calculos.data_ultima_parcela("2026-01-01", n)

    def test_primeira_invalida_levanta(self):
        with self.assertRaises(ValueError):
            calculos.data_ultima_parcela("nao e data", 12)


class DiasAteTestCase(unittest.TestCase):
    def test_futuro_positivo(self):
        self.assertEqual(calculos.dias_ate("2026-10-01", "2026-09-24"), 7)

    def test_passado_negativo(self):
        self.assertEqual(calculos.dias_ate("2026-09-01", "2026-09-24"), -23)

    def test_hoje_e_zero(self):
        self.assertEqual(calculos.dias_ate("2026-09-24", "2026-09-24"), 0)

    def test_aceita_date_e_datetime(self):
        self.assertEqual(
            calculos.dias_ate(date(2026, 10, 1), datetime(2026, 9, 24, 8, 0)), 7
        )

    def test_vira_o_ano(self):
        self.assertEqual(calculos.dias_ate("2027-01-01", "2026-12-31"), 1)

    def test_data_invalida_levanta(self):
        with self.assertRaises(ValueError):
            calculos.dias_ate("31/12/2026", "2026-09-24")

    def test_hoje_invalido_levanta(self):
        with self.assertRaises(ValueError):
            calculos.dias_ate("2026-09-24", None)

    def test_fuzz_bissextos_e_limites(self):
        casos = [
            ("2024-02-29", "2023-02-28", 366),
            ("2000-03-01", "2000-02-28", 2),  # ano 2000 e bissexto (regra dos 400)
            ("1900-03-01", "1900-02-28", 1),  # 1900 NAO e bissexto (regra dos 100)
            ("2026-01-01", "2026-01-01", 0),
        ]
        for data, hoje, esperado in casos:
            self.assertEqual(calculos.dias_ate(data, hoje), esperado, msg=(data, hoje))


class ComprometidoMensalTestCase(unittest.TestCase):
    def test_so_assinaturas(self):
        self.assertEqual(calculos.comprometido_mensal([10, 20.5, "5"], []), D("35.50"))

    def test_assinaturas_como_dict(self):
        self.assertEqual(
            calculos.comprometido_mensal([{"valor": 10}, {"valor": 20}], []), D("30.00")
        )

    def test_parcelas_ativas_entram(self):
        parcelas = [{"valor_parcela": 100, "parcelas_restantes": 3}]
        self.assertEqual(calculos.comprometido_mensal([], parcelas), D("100.00"))

    def test_parcelas_quitadas_nao_entram(self):
        parcelas = [{"valor_parcela": 100, "parcelas_restantes": 0}, {"valor_parcela": 50, "parcelas_restantes": -1}]
        self.assertEqual(calculos.comprometido_mensal([], parcelas), D("0.00"))

    def test_parcela_sem_campo_restantes_conta_como_ativa(self):
        parcelas = [{"valor_parcela": 75}]
        self.assertEqual(calculos.comprometido_mensal([], parcelas), D("75.00"))

    def test_combina_assinaturas_e_parcelas(self):
        r = calculos.comprometido_mensal(
            [50, {"valor": 30}],
            [{"valor_parcela": 100, "parcelas_restantes": 2}, {"valor_parcela": 40, "parcelas_restantes": 0}],
        )
        self.assertEqual(r, D("180.00"))

    def test_listas_vazias(self):
        self.assertEqual(calculos.comprometido_mensal([], []), D("0.00"))

    def test_parcela_sem_valor_levanta(self):
        with self.assertRaises(ValueError):
            calculos.comprometido_mensal([], [{"parcelas_restantes": 2}])

    def test_assinatura_dict_sem_valor_levanta(self):
        with self.assertRaises(ValueError):
            calculos.comprometido_mensal([{"nome": "netflix"}], [])


if __name__ == "__main__":
    unittest.main()
