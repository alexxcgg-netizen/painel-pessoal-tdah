import unittest

from estudo import TEMAS, proximo_tema


class ProximoTemaTestCase(unittest.TestCase):
    def test_indice_zero_devolve_primeiro_tema(self):
        tema, proximo = proximo_tema(0)
        self.assertEqual(tema, TEMAS[0])
        self.assertEqual(proximo, 1)

    def test_avanca_um_por_chamada(self):
        _, i1 = proximo_tema(0)
        tema2, i2 = proximo_tema(i1)
        self.assertEqual(tema2, TEMAS[1])
        self.assertEqual(i2, 2)

    def test_volta_pro_inicio_depois_do_ultimo(self):
        ultimo_indice = len(TEMAS) - 1
        tema, proximo = proximo_tema(ultimo_indice)
        self.assertEqual(tema, TEMAS[-1])
        self.assertEqual(proximo, 0)

    def test_indice_fora_do_intervalo_nao_quebra(self):
        tema, proximo = proximo_tema(len(TEMAS) * 3 + 1)
        self.assertEqual(tema, TEMAS[1])
        self.assertEqual(proximo, 2)

    def test_uma_volta_completa_passa_por_todos_os_temas_uma_vez(self):
        indice = 0
        vistos = []
        for _ in range(len(TEMAS)):
            tema, indice = proximo_tema(indice)
            vistos.append(tema)
        self.assertEqual(vistos, TEMAS)


if __name__ == "__main__":
    unittest.main()
