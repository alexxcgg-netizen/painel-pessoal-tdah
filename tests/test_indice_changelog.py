"""scripts/indice_changelog.py: indice no topo do CHANGELOG e arquivo dos dias antigos
(2026-10-16 - cada sessao nova le so o indice em vez das 3.600 linhas)."""

import tempfile
import unittest
from pathlib import Path

from scripts import indice_changelog as ic

CABECA = "# Changelog\n\nTexto de cima.\n\n"
ENTRADAS = (
    "## 2026-10-02 - Coisa nova (SW v9)\n- detalhe a\n\n"
    "## 2026-10-01 - Outra coisa\n- detalhe b\n\n"
    "## 2026-09-30 - Coisa velha\n- detalhe c\n\n"
    "## 2026-09-21 (2) - Mais velha ainda\n- detalhe d\n"
)


class IndiceChangelogTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        self.log = self.raiz / "CHANGELOG.md"
        self.hist = self.raiz / "docs" / "historico"
        self.log.write_text(CABECA + ENTRADAS, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def rodar(self, *args):
        return ic.main([*args, "--changelog", str(self.log), "--historico", str(self.hist)])

    def test_indice_lista_tudo_e_e_idempotente(self):
        self.assertEqual(self.rodar("--checar"), 1)
        self.assertEqual(self.rodar(), 0)
        texto = self.log.read_text(encoding="utf-8")
        self.assertTrue(texto.startswith(CABECA.rstrip("\n")))
        indice = texto.split(ic.INICIO)[1].split(ic.FIM)[0]
        for titulo in ("2026-10-02 - Coisa nova (SW v9)", "2026-09-21 (2) - Mais velha ainda"):
            self.assertIn(f"- {titulo}\n", indice)
        self.assertEqual(self.rodar("--checar"), 0)
        self.rodar()
        self.assertEqual(self.log.read_text(encoding="utf-8"), texto, "rodar de novo nao muda nada")
        self.assertEqual(texto.count(ic.INICIO), 1)

    def test_arquivar_move_os_dias_antigos_sem_perder_nada(self):
        self.assertEqual(self.rodar("--arquivar-antes", "2026-10-01"), 0)
        texto = self.log.read_text(encoding="utf-8")
        corpo = texto.split(ic.FIM)[1]
        self.assertIn("- detalhe a", corpo)
        self.assertIn("- detalhe b", corpo)
        self.assertNotIn("detalhe c", corpo)
        arquivo = (self.hist / "CHANGELOG-2026-09.md").read_text(encoding="utf-8")
        self.assertLess(arquivo.index("detalhe c"), arquivo.index("detalhe d"), "mais nova em cima")
        self.assertIn("Arquivadas em `docs/historico/CHANGELOG-2026-09.md`", texto)
        self.assertIn("- 2026-09-30 - Coisa velha\n", texto.split(ic.FIM)[0])
        self.assertEqual(self.rodar("--checar"), 0)
        # arquivar de novo depois (outro mes ja existente) junta sem duplicar
        self.rodar("--arquivar-antes", "2026-10-02")
        self.assertEqual(self.log.read_text(encoding="utf-8").split(ic.FIM)[1].count("## 2026"), 1)
        self.assertIn("detalhe b", (self.hist / "CHANGELOG-2026-10.md").read_text(encoding="utf-8"))
        self.assertEqual((self.hist / "CHANGELOG-2026-09.md").read_text(encoding="utf-8").count("## 2026"), 2)

    def test_changelog_do_repo_esta_com_o_indice_em_dia(self):
        # entrada nova no CHANGELOG sem rodar o script = indice velho; este teste avisa
        self.assertEqual(ic.main(["--checar"]), 0,
                         "rode .venv/Scripts/python.exe scripts/indice_changelog.py")


if __name__ == "__main__":
    unittest.main()
