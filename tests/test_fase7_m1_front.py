"""Fase 7, faixa M1 (m1-front): guardas das regras globais do style.css.

- O :focus-visible global usa o token --anel-foco (o anel antigo de --accent-2 quase
  sumia no preto) e mantem um outline transparente pro modo de alto contraste.
- Rede de seguranca `[hidden] { display: none !important; }`: sem ela, qualquer
  `display: flex` de classe ou id vencia o atributo hidden.
"""

import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
STYLE = (RAIZ / "static" / "css" / "style.css").read_text(encoding="utf-8")
TOKENS = (RAIZ / "static" / "css" / "ui" / "tokens.css").read_text(encoding="utf-8")


def _sem_comentarios(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _blocos(css, seletor):
    """Corpos das regras cujo seletor e exatamente `seletor` (fora de @media)."""
    padrao = re.compile(r"(?:^|})\s*" + re.escape(seletor) + r"\s*\{([^}]*)\}", re.M)
    return padrao.findall(_sem_comentarios(css))


class TestFocoGlobal(unittest.TestCase):
    def test_token_existe(self):
        self.assertRegex(TOKENS, r"--anel-foco\s*:")

    def test_focus_visible_global_usa_anel_foco(self):
        blocos = _blocos(STYLE, ":focus-visible")
        self.assertEqual(len(blocos), 1, "um unico :focus-visible global no style.css")
        corpo = blocos[0]
        self.assertRegex(corpo, r"box-shadow\s*:\s*var\(--anel-foco\)")
        self.assertNotIn("--accent-2", corpo)

    def test_focus_visible_mantem_outline_para_alto_contraste(self):
        corpo = _blocos(STYLE, ":focus-visible")[0]
        self.assertNotRegex(corpo, r"outline\s*:\s*(none|0)\b")
        self.assertRegex(corpo, r"outline\s*:\s*\d+px\s+solid\s+transparent")


class TestRedeHidden(unittest.TestCase):
    def test_hidden_global_com_important(self):
        blocos = _blocos(STYLE, "[hidden]")
        self.assertEqual(len(blocos), 1)
        self.assertRegex(blocos[0], r"display\s*:\s*none\s*!important")

    def test_hidden_fica_perto_do_topo(self):
        limpo = _sem_comentarios(STYLE)
        pos_hidden = limpo.find("[hidden] {")
        pos_root_fim = limpo.find("}", limpo.find(":root"))
        self.assertGreater(pos_hidden, pos_root_fim)
        # antes de qualquer componente: logo depois do :root e do reset `*`
        self.assertLess(limpo.count("{", 0, pos_hidden), 5)


if __name__ == "__main__":
    unittest.main()
