"""2026-10-16: erros do servidor vao pra arquivo (log_erros.py) e erro de JS do aparelho vira
diagnostico `erro_js`. Nada de tocar o disco real: pasta temporaria, handler removido no fim."""
import logging
import tempfile
import unittest
from pathlib import Path

import log_erros


class LogErrosTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name)
        self.raiz = logging.getLogger()
        self.antes = list(self.raiz.handlers)
        self.nivel = self.raiz.level
        self.addCleanup(self._limpar)

    def _limpar(self):
        for h in list(self.raiz.handlers):
            if h not in self.antes:
                self.raiz.removeHandler(h)
                h.close()
        self.raiz.setLevel(self.nivel)
        self._tmp.cleanup()

    def test_sob_teste_nao_liga_sozinho(self):
        self.assertIsNone(log_erros.configurar(self.pasta))
        self.assertFalse((self.pasta / log_erros.NOME).exists())

    def test_grava_warning_e_traceback_mas_nao_info_e_liga_uma_vez_so(self):
        caminho = log_erros.configurar(self.pasta, forcar=True)
        self.assertEqual(caminho, self.pasta / log_erros.NOME)
        log_erros.configurar(self.pasta, forcar=True)
        self.assertEqual(sum(getattr(h, log_erros._MARCA, False) for h in self.raiz.handlers), 1)
        log = logging.getLogger("teste.log_erros")
        log.info("isto nao entra")
        log.warning("aviso que entra")
        try:
            1 / 0
        except ZeroDivisionError:
            log.exception("quebrou no meio")
        for h in self.raiz.handlers:
            h.flush()
        texto = caminho.read_text(encoding="utf-8")
        self.assertNotIn("isto nao entra", texto)
        self.assertIn("WARNING teste.log_erros: aviso que entra", texto)
        self.assertIn("ZeroDivisionError", texto)

    def test_pasta_impossivel_nao_derruba_o_servidor(self):
        arquivo = self.pasta / "arquivo"
        arquivo.write_text("x")
        self.assertIsNone(log_erros.configurar(arquivo / "dentro", forcar=True))  # pasta dentro de arquivo


if __name__ == "__main__":
    unittest.main()
