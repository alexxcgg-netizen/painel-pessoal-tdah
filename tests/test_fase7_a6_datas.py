"""Fase 7 / A6: data relativa do tool `registrar_tarefa` resolvida em codigo
(docs/calculos.md 1.2/1.3). Sem IA, sem banco."""
import os
import random
import string
import unittest
from datetime import date, datetime, timedelta

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

from ia.funcoes.chat import resolver_data_relativa, resolver_quando_data

HOJE = date(2026, 9, 24)  # quinta-feira


class ResolverDataRelativaTestCase(unittest.TestCase):
    CASOS = [
        # palavras
        ("hoje", date(2026, 9, 24)),
        ("Hoje às 14h", date(2026, 9, 24)),
        ("hj a noite", date(2026, 9, 24)),
        ("amanhã", date(2026, 9, 25)),
        ("AMANHA de manha", date(2026, 9, 25)),
        ("depois de amanhã", date(2026, 9, 26)),
        # dia da semana: proxima ocorrencia DEPOIS de hoje
        ("sexta", date(2026, 9, 25)),
        ("sexta-feira", date(2026, 9, 25)),
        ("quinta", date(2026, 10, 1)),
        ("próxima segunda", date(2026, 9, 28)),
        ("segunda-feira que vem", date(2026, 9, 28)),
        ("no sábado", date(2026, 9, 26)),
        ("domingo", date(2026, 9, 27)),
        ("terça da semana que vem", date(2026, 9, 29)),
        ("sexta da próxima semana", date(2026, 10, 2)),
        # quantidades
        ("daqui a 3 dias", date(2026, 9, 27)),
        ("em 2 semanas", date(2026, 10, 8)),
        ("daqui 6 meses", date(2027, 3, 24)),
        ("daqui a um mês", date(2026, 10, 24)),
        ("em um ano", date(2027, 9, 24)),
        ("dentro de dez dias", date(2026, 10, 4)),
        ("em duas semanas", date(2026, 10, 8)),
        ("em 1 dia", date(2026, 9, 25)),
        # datas ditas
        ("15/10", date(2026, 10, 15)),
        ("01/09", date(2027, 9, 1)),
        ("15/10/2027", date(2027, 10, 15)),
        ("15/10/27", date(2027, 10, 15)),
        ("2026-12-25", date(2026, 12, 25)),
        ("25 de dezembro", date(2026, 12, 25)),
        ("dia 5 de março", date(2027, 3, 5)),
        ("5 de marco de 2028", date(2028, 3, 5)),
        ("dia 30", date(2026, 9, 30)),
        ("dia 24", date(2026, 9, 24)),
        ("dia 10", date(2026, 10, 10)),
        ("dia 31", date(2026, 10, 31)),
        ("fim do mês", date(2026, 9, 30)),
        ("final do ano", date(2026, 12, 31)),
        # vago / impossivel / lixo -> None
        ("essa semana", None),
        ("semana que vem", None),
        ("mês que vem", None),
        ("quando der", None),
        ("algum dia", None),
        ("fim de semana", None),
        ("31/02", None),
        ("2026-13-01", None),
        ("dia 45", None),
        ("em 99999 dias", None),
        ("daqui a 500 anos", None),
        ("", None),
        ("   ", None),
        ("x" * 1000, None),
        ("ontem", None),
    ]

    def test_casos(self):
        for texto, esperado in self.CASOS:
            with self.subTest(texto=texto):
                self.assertEqual(resolver_data_relativa(texto, HOJE), esperado)

    def test_soma_de_mes_respeita_fim_do_mes(self):
        self.assertEqual(resolver_data_relativa("daqui 1 mes", date(2026, 1, 31)), date(2026, 2, 28))
        self.assertEqual(resolver_data_relativa("daqui 1 mes", date(2028, 1, 31)), date(2028, 2, 29))
        self.assertEqual(resolver_data_relativa("em 1 ano", date(2028, 2, 29)), date(2029, 2, 28))

    def test_virada_de_ano(self):
        self.assertEqual(resolver_data_relativa("amanha", date(2026, 12, 31)), date(2027, 1, 1))
        self.assertEqual(resolver_data_relativa("dia 5", date(2026, 12, 20)), date(2027, 1, 5))
        self.assertEqual(resolver_data_relativa("segunda", date(2026, 12, 31)), date(2027, 1, 4))

    def test_hoje_em_varios_formatos(self):
        self.assertEqual(resolver_data_relativa("amanha", "2026-09-24"), date(2026, 9, 25))
        self.assertEqual(resolver_data_relativa("amanha", datetime(2026, 9, 24, 23, 59)), date(2026, 9, 25))
        for invalido in (None, 20260924, "24/09/2026", "lixo"):
            with self.subTest(hoje=invalido), self.assertRaises(ValueError):
                resolver_data_relativa("amanha", invalido)

    def test_texto_que_nao_e_string(self):
        for valor in (None, 3, 2.5, ["amanha"], {"q": "amanha"}, b"amanha"):
            with self.subTest(valor=valor):
                self.assertIsNone(resolver_data_relativa(valor, HOJE))

    def test_fuzz_nunca_levanta_e_fica_numa_janela_sensata(self):
        rnd = random.Random(7)
        pedacos = ["amanha", "hoje", "sexta", "dia", "de", "em", "daqui a", "semanas", "meses", "31", "/", "-",
                   "2026", "99", "que vem", "proxima", "janeiro", "fim do", "mes", "0", "00/00", "💥", "\n"]
        for i in range(300):
            if i % 2:
                texto = " ".join(rnd.choice(pedacos) for _ in range(rnd.randint(1, 6)))
            else:
                texto = "".join(rnd.choice(string.printable) for _ in range(rnd.randint(0, 40)))
            with self.subTest(texto=texto):
                r = resolver_data_relativa(texto, HOJE)
                if r is not None:
                    self.assertIsInstance(r, date)
                    self.assertGreaterEqual(r, date(2000, 1, 1))
                    self.assertLessEqual(r, HOJE + timedelta(days=3660 * 3))


class ResolverQuandoDataTestCase(unittest.TestCase):
    def test_codigo_resolve_a_pista_e_vence_o_modelo(self):
        self.assertEqual(resolver_quando_data({"titulo": "x", "quando": "amanha"}, HOJE), "2026-09-25")
        self.assertEqual(
            resolver_quando_data({"quando": "amanha", "quando_data": "2030-01-01"}, HOJE), "2026-09-25"
        )

    def test_transicao_usa_data_do_modelo_quando_a_pista_e_vaga(self):
        self.assertEqual(
            resolver_quando_data({"quando": "essa semana", "quando_data": "2026-09-26"}, HOJE), "2026-09-26"
        )
        self.assertIsNone(resolver_quando_data({"quando": "essa semana", "quando_data": "lixo"}, HOJE))
        self.assertIsNone(resolver_quando_data({"quando_data": 20260926}, HOJE))

    def test_hora_sem_dia_e_hoje(self):
        self.assertEqual(resolver_quando_data({"titulo": "x", "hora": "14:00"}, HOJE), "2026-09-24")
        self.assertIsNone(resolver_quando_data({"quando": "quando der", "hora": "14:00"}, HOJE))

    def test_sem_nada_e_entrada_invalida(self):
        self.assertIsNone(resolver_quando_data({"titulo": "x"}, HOJE))
        for entrada in (None, "amanha", [], 3):
            with self.subTest(entrada=entrada):
                self.assertIsNone(resolver_quando_data(entrada, HOJE))

    def test_hoje_padrao_e_o_dia_de_hoje(self):
        self.assertEqual(resolver_quando_data({"quando": "hoje"}), date.today().isoformat())


if __name__ == "__main__":
    unittest.main()
