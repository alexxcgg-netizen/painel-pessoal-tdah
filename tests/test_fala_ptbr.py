"""fala_ptbr: texto escrito -> fala pt-BR antes do TTS (horario, dinheiro,
unidade, data, sigla, numero com genero). Sem rede, sem banco."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fala_ptbr  # noqa: E402
from fala_ptbr import normalizar, por_extenso  # noqa: E402


class TestPorExtenso(unittest.TestCase):
    def test_basicos(self):
        casos = {
            0: "zero", 1: "um", 15: "quinze", 21: "vinte e um", 100: "cem", 101: "cento e um",
            200: "duzentos", 999: "novecentos e noventa e nove", 1000: "mil", 1001: "mil e um",
            1100: "mil e cem", 1250: "mil duzentos e cinquenta", 2026: "dois mil e vinte e seis",
            21000: "vinte e um mil", 1_000_000: "um milhão",
            1_200_000: "um milhão e duzentos mil", 3_000_000: "três milhões",
        }
        for n, esperado in casos.items():
            with self.subTest(n=n):
                self.assertEqual(por_extenso(n), esperado)

    def test_feminino(self):
        self.assertEqual(por_extenso(2, True), "duas")
        self.assertEqual(por_extenso(21, True), "vinte e uma")
        self.assertEqual(por_extenso(1850, True), "mil oitocentas e cinquenta")
        self.assertEqual(por_extenso(-3), "menos três")


class TestNormalizar(unittest.TestCase):
    def _tem(self, entrada, *trechos):
        saida = normalizar(entrada)
        for t in trechos:
            self.assertIn(t, saida, f"{entrada!r} -> {saida!r}")
        return saida

    def test_horarios(self):
        self._tem("Dentista às 14:30", "às catorze e trinta")
        self._tem("academia às 9h", "às nove horas")
        self._tem("das 8h às 18h", "das oito horas às dezoito horas")
        self._tem("às 21:00", "vinte e uma horas")
        self._tem("às 13:05", "treze e cinco")
        self._tem("às 14h30", "catorze e trinta")
        self._tem("12:00 almoço", "meio-dia")
        self._tem("0h30", "meia-noite e trinta")
        self._tem("1h", "uma hora")
        self._tem("estudo de 1h30min", "uma hora e trinta minutos")

    def test_dinheiro(self):
        self._tem("R$ 1.250,90", "mil duzentos e cinquenta reais e noventa centavos")
        self._tem("R$ 0,50", "cinquenta centavos")
        self._tem("R$ 1,00", "um real")
        self._tem("R$ 2 mil", "dois mil reais")
        self._tem("R$ 3.000.000,00", "três milhões de reais")
        self.assertNotIn("R$", normalizar("conta de R$ 89,9"))

    def test_unidades_e_genero(self):
        self._tem("1.850 kcal", "mil oitocentas e cinquenta calorias")
        self._tem("120g de proteína", "cento e vinte gramas")
        self._tem("2 refeições, 3 tarefas, 2 dias", "duas refeições", "três tarefas", "dois dias")
        self._tem("2 mil calorias", "duas mil calorias")
        self._tem("15 kt", "quinze nós")
        self._tem("270°", "duzentos e setenta graus")
        self._tem("75,5%", "setenta e cinco vírgula cinco por cento")
        self._tem("3x por semana", "três vezes por semana")
        self._tem("~30 min", "cerca de trinta minutos")
        self._tem("10-12 repetições", "dez a doze")

    def test_datas_e_ordinais(self):
        self._tem("vence 13/10", "treze de outubro")
        self._tem("13/10/2026", "treze de outubro de dois mil e vinte e seis")
        self._tem("2026-10-13", "treze de outubro")
        self._tem("1 de outubro", "primeiro de outubro")
        self._tem("2º lugar, 1ª vez", "segundo lugar", "primeira vez")

    def test_aviacao_e_siglas(self):
        self._tem("FL350", "nível três cinco zero")
        self._tem("pista 09L", "pista zero nove esquerda")
        self._tem("QNH 1013", "um zero um três")
        self._tem("em SBSP", "ésse bê ésse pê")
        self._tem("METAR e TAF", "métar", "táfi")
        self._tem("Seu TDAH", "tê dê á agá")
        self._tem("tá ok.", "ó quêi.")

    def test_limpeza(self):
        saida = normalizar("**Resumo:** foca 😄 -> agora https://x.com/a")
        for proibido in ("*", "😄", "->", "http"):
            self.assertNotIn(proibido, saida)

    def test_digitos_soltos(self):
        self._tem("Ligue 0800", "zero oito zero zero")
        self._tem("código 47999998888", "quatro sete nove")

    def test_texto_sem_numero_nao_muda(self):
        for t in ("Bom dia, Alex.", "oi", "abcde", "x" * 300):
            self.assertEqual(normalizar(t), t)

    def test_entrada_estranha_nao_quebra(self):
        for t in ("", "   ", None, 5, "😀" * 50, "R$", "99:99", "1/99", "a" * 5000, "\x00 12 \x00"):
            normalizar(t)

    def test_erro_interno_devolve_texto_original(self):
        original = fala_ptbr._normalizar
        fala_ptbr._normalizar = lambda t: 1 / 0
        try:
            self.assertEqual(normalizar("às 14:30"), "às 14:30")
        finally:
            fala_ptbr._normalizar = original


if __name__ == "__main__":
    unittest.main()
