"""08/11/2026: a regra local "baguncou meu dia" devolvia {} cru e o despachante do classificador local
descartava como formato invalido - a regra nunca disparava pelo chat (so pelo gatilho das 14h)."""
import os
import unittest

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import classificador_local  # noqa: E402


class DespachoReplanejarTestCase(unittest.TestCase):
    def test_frase_de_replanejar_chega_na_regra(self):
        for frase in ("baguncou meu dia", "recomeca meu dia", "meu dia virou bagunca"):
            with self.subTest(frase=frase):
                r = classificador_local.casar(frase)
                self.assertIsNotNone(r, frase)
                self.assertEqual(r["regra"], "p5_replanejar")
                self.assertEqual(r["parametros"], {})

    def test_frase_comum_nao_vira_replanejar(self):
        r = classificador_local.casar("comprar pao amanha")
        self.assertTrue(r is None or r["regra"] != "p5_replanejar")


if __name__ == "__main__":
    unittest.main()
