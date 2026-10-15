"""Tarefas: lista monta 10 por vez com botao 'Ver mais'."""
import pathlib
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent


class TarefasVerMaisTestCase(unittest.TestCase):
    def test_template_tem_botao_ver_mais_escondido(self):
        html = (RAIZ / "templates/secoes/tarefas/tarefas.html").read_text(encoding="utf-8")
        self.assertIn('id="tarefas-ver-mais"', html)
        self.assertIn("hidden>Ver mais", html)

    def test_js_monta_10_por_vez(self):
        js = (RAIZ / "static/js/secoes/tarefas/tarefas.js").read_text(encoding="utf-8")
        self.assertIn("LOTE_INICIAL_TAREFAS = 10", js)
        self.assertIn("proximoLoteTarefas", js)

    def test_service_worker_versao_nova(self):
        sw = (RAIZ / "static/service-worker.js").read_text(encoding="utf-8")
        self.assertIn("painel-pessoal-v80", sw)


if __name__ == "__main__":
    unittest.main()
