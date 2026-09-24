"""Faixa A7 (Migracao 1) - ia/funcoes/captura.py:resolver_data.

Pura interpretacao de calendario (sem IA, sem banco, sem rede): converte a
pista textual em pt-BR que o modelo devolve ("amanha", "sexta que vem", "dia
15", "em 6 meses", "ate dezembro"...) numa data absoluta AAAA-MM-DD, ancorada
num `hoje` fixo passado pelo teste (nunca date.today() implicito, senao o
teste quebraria dependendo do dia em que rodar).
"""
import unittest
from datetime import date

from ia.funcoes.captura import resolver_data

# Quinta-feira, de proposito (deixa "hoje"/"amanha"/"sexta que vem" -
# inclusive o caso "hoje ja e o dia da semana pedido" - todos exercitados
# por datas diferentes ao longo dos testes).
HOJE = date(2026, 9, 24)


class CasosBasicosTestCase(unittest.TestCase):
    def test_amanha(self):
        self.assertEqual(resolver_data("amanha", HOJE), "2026-09-25")

    def test_amanha_acentuado_e_dentro_de_frase(self):
        self.assertEqual(resolver_data("Marca pra amanhã de manha", HOJE), "2026-09-25")

    def test_depois_de_amanha(self):
        self.assertEqual(resolver_data("depois de amanha", HOJE), "2026-09-26")

    def test_depois_de_amanha_acentuado(self):
        self.assertEqual(resolver_data("depois de amanhã", HOJE), "2026-09-26")

    def test_hoje(self):
        self.assertEqual(resolver_data("hoje", HOJE), "2026-09-24")

    def test_hoje_as_14h(self):
        self.assertEqual(resolver_data("hoje as 14h", HOJE), "2026-09-24")

    def test_hoje_acentuado_com_hora(self):
        self.assertEqual(resolver_data("hoje às 14h", HOJE), "2026-09-24")


class DiaDoMesTestCase(unittest.TestCase):
    def test_dia_15_ainda_nao_chegou_no_mes_atual(self):
        # HOJE = 24/09 -> dia 15 desse mes ja passou, deve ir pro mes seguinte.
        self.assertEqual(resolver_data("dia 15", HOJE), "2026-10-15")

    def test_dia_ainda_nao_chegou_fica_no_mes_atual(self):
        self.assertEqual(resolver_data("dia 30", HOJE), "2026-09-30")

    def test_dia_igual_a_hoje_fica_no_mes_atual(self):
        self.assertEqual(resolver_data("dia 24", HOJE), "2026-09-24")

    def test_dia_31_pula_mes_sem_dia_31(self):
        # Setembro nao tem dia 31 -> teria que ir pra outubro, que tem.
        self.assertEqual(resolver_data("dia 31", HOJE), "2026-10-31")

    def test_dia_31_pulando_fevereiro(self):
        hoje = date(2026, 12, 20)
        # Dezembro/26 (dia 31 ja passou -> pula), janeiro/27 tem 31, mas
        # dezembro ainda nao passou do dia 31... ajuste: dez tem 31 dias e
        # ainda nao chegou -> cai em 31/12/2026.
        self.assertEqual(resolver_data("dia 31", hoje), "2026-12-31")

    def test_dia_invalido_maior_que_31(self):
        self.assertIsNone(resolver_data("dia 45", HOJE))


class SemanaTestCase(unittest.TestCase):
    def test_sexta_que_vem_a_partir_de_quinta(self):
        # HOJE e quinta (weekday=3); sexta (weekday=4) e amanha mesmo.
        self.assertEqual(resolver_data("sexta que vem", HOJE), "2026-09-25")

    def test_sexta_que_vem_quando_hoje_ja_e_sexta_pula_semana(self):
        sexta = date(2026, 9, 25)
        self.assertEqual(resolver_data("sexta que vem", sexta), "2026-10-02")

    def test_sexta_sem_que_vem_quando_hoje_ja_e_sexta_e_hoje(self):
        sexta = date(2026, 9, 25)
        self.assertEqual(resolver_data("sexta-feira", sexta), "2026-09-25")

    def test_proxima_segunda(self):
        self.assertEqual(resolver_data("proxima segunda", HOJE), "2026-09-28")

    def test_domingo_que_vem(self):
        self.assertEqual(resolver_data("domingo que vem", HOJE), "2026-09-27")

    def test_semana_que_vem(self):
        self.assertEqual(resolver_data("semana que vem", HOJE), "2026-10-01")

    def test_proxima_semana(self):
        self.assertEqual(resolver_data("na proxima semana", HOJE), "2026-10-01")


class MesEAnoTestCase(unittest.TestCase):
    def test_ate_dezembro_ultimo_dia(self):
        self.assertEqual(resolver_data("ate dezembro", HOJE), "2026-12-31")

    def test_ate_dezembro_acentuado(self):
        self.assertEqual(resolver_data("até dezembro", HOJE), "2026-12-31")

    def test_ate_mes_ja_passado_vira_ano_que_vem(self):
        # HOJE e setembro/2026 -> "ate marco" (mes 3, ja passou) vai pra 2027.
        self.assertEqual(resolver_data("ate marco", HOJE), "2027-03-31")

    def test_ate_mes_com_ano_explicito(self):
        self.assertEqual(resolver_data("ate junho de 2028", HOJE), "2028-06-30")

    def test_mes_que_vem(self):
        self.assertEqual(resolver_data("mes que vem", HOJE), "2026-10-24")

    def test_mes_que_vem_comprime_dia_curto(self):
        hoje = date(2026, 1, 31)
        self.assertEqual(resolver_data("mes que vem", hoje), "2026-02-28")

    def test_em_6_meses(self):
        self.assertEqual(resolver_data("em 6 meses", HOJE), "2027-03-24")

    def test_em_1_ano(self):
        self.assertEqual(resolver_data("em 1 ano", HOJE), "2027-09-24")

    def test_em_1_ano_29_fevereiro_comprime(self):
        hoje = date(2028, 2, 29)  # 2028 e bissexto
        self.assertEqual(resolver_data("em 1 ano", hoje), "2029-02-28")

    def test_daqui_a_2_semanas(self):
        self.assertEqual(resolver_data("daqui a 2 semanas", HOJE), "2026-10-08")

    def test_daqui_3_dias_sem_a(self):
        self.assertEqual(resolver_data("daqui 3 dias", HOJE), "2026-09-27")


class InvalidoTestCase(unittest.TestCase):
    def test_texto_vazio(self):
        self.assertIsNone(resolver_data("", HOJE))

    def test_none(self):
        self.assertIsNone(resolver_data(None, HOJE))

    def test_texto_sem_pista_de_data(self):
        self.assertIsNone(resolver_data("comprar leite", HOJE))

    def test_algum_dia_e_vago_demais(self):
        self.assertIsNone(resolver_data("algum dia", HOJE))

    def test_quando_der_e_vago_demais(self):
        self.assertIsNone(resolver_data("quando der", HOJE))

    def test_tipo_errado_lista(self):
        self.assertIsNone(resolver_data(["amanha"], HOJE))  # type: ignore[arg-type]

    def test_tipo_errado_numero(self):
        self.assertIsNone(resolver_data(42, HOJE))  # type: ignore[arg-type]

    def test_mes_inexistente(self):
        self.assertIsNone(resolver_data("ate blergsteiro", HOJE))

    def test_em_zero_dias_e_invalido(self):
        self.assertIsNone(resolver_data("em 0 dias", HOJE))

    def test_em_unidade_desconhecida_nao_bate_regex(self):
        self.assertIsNone(resolver_data("em 5 luas", HOJE))

    def test_string_so_espaco(self):
        self.assertIsNone(resolver_data("   ", HOJE))

    def test_dia_zero_invalido(self):
        self.assertIsNone(resolver_data("dia 0", HOJE))


class RobustezFuzzTestCase(unittest.TestCase):
    """Nunca deve levantar excecao nem travar, pra nenhuma entrada -
    devolve None ou uma string AAAA-MM-DD valida, sempre."""

    ENTRADAS = [
        "amanha", "AMANHÃ", "  amanhã  ", "depois de amanha às 9h",
        "sexta que vem às 18h", "dia 1", "dia 29 de fevereiro (nao existe)",
        "em 999 meses", "em -3 dias", "em 3.5 dias", "ate dezembro de 1999",
        "ate dezembro de 9999", "🎉 amanha 🎉", "a" * 5000, "日本語のテキスト",
        "sexta-feira que vem, as 20h, sem falta", "proximo domingo",
        "semana que vem, ou talvez nao", "'; DROP TABLE tasks; --",
        "<script>alert(1)</script> amanha", "\n\tamanha\n\t", None, "", 123,
        3.14, [], {}, True, False,
    ]

    def test_nunca_levanta_excecao_e_sempre_devolve_none_ou_data_valida(self):
        for entrada in self.ENTRADAS:
            with self.subTest(entrada=repr(entrada)[:60]):
                try:
                    resultado = resolver_data(entrada, HOJE)  # type: ignore[arg-type]
                except Exception as exc:  # noqa: BLE001
                    self.fail(f"resolver_data levantou {exc!r} pra entrada {entrada!r}")
                if resultado is not None:
                    self.assertIsInstance(resultado, str)
                    date.fromisoformat(resultado)  # levanta se nao for AAAA-MM-DD valida

    def test_nunca_devolve_data_no_passado(self):
        """Toda data relativa resolvida (nao "hoje") deve ser hoje ou futuro -
        nenhuma pista de "quando" deveria mandar pro passado."""
        pistas_futuras = [
            "amanha", "depois de amanha", "sexta que vem", "dia 15",
            "em 6 meses", "ate dezembro", "semana que vem", "mes que vem",
            "em 1 ano", "proximo domingo",
        ]
        for pista in pistas_futuras:
            with self.subTest(pista=pista):
                resultado = resolver_data(pista, HOJE)
                self.assertIsNotNone(resultado)
                self.assertGreaterEqual(date.fromisoformat(resultado), HOJE)


if __name__ == "__main__":
    unittest.main()
