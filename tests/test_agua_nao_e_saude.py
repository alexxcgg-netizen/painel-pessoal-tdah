"""A palavra "agua" so abre o card de saude quando e a agua que ele BEBE (07/11/2026).

Bug real: "e se eu so jogar uma agua no carro?" (duvida sobre lavar o carro) caia no atalho local do chat e
respondia "Sua saude hoje." duas vezes, sem responder nada. Sem rede, sem banco."""
import os
import unittest

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import aprendizado  # noqa: E402


class AguaDeBeberVsAguaNoCarro(unittest.TestCase):
    def test_duvida_do_carro_vai_pra_ia(self):
        for frase in (
            "E se eu só jogar uma água nele? É pior do que só jogar uma água nele?",
            "Se eu só jogar uma água no carro ajuda? Ou é melhor não?",
            "vale lavar o carro com 80% de chuva?",
            "posso molhar a moto agora?",
        ):
            with self.subTest(frase=frase):
                self.assertTrue(aprendizado.exige_ia(frase), "tem que ir pra IA")
                self.assertIsNone(aprendizado.consulta_conhecida(frase), "nao pode virar consulta local")

    def test_agua_de_beber_continua_no_atalho(self):
        for frase in ("quanta água eu bebi hoje?", "mostra meus copos de água", "como tá minha saúde hoje?"):
            with self.subTest(frase=frase):
                plano = aprendizado.consulta_conhecida(frase)
                self.assertIsNotNone(plano)
                self.assertEqual(plano["parametros"]["fontes"][0]["fonte"], "saude_dia")

    def test_registrar_copo_continua(self):
        plano = aprendizado.consulta_conhecida("tomei um copo de água")
        self.assertEqual(plano["parametros"], {"campo": "hidratacao"})


if __name__ == "__main__":
    unittest.main()
