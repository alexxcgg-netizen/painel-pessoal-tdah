"""scripts/testes_afetados.py: escolha dos testes pelo que mudou."""

import importlib.util
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
_spec = importlib.util.spec_from_file_location("testes_afetados", RAIZ / "scripts" / "testes_afetados.py")
af = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(af)

FONTE = '''
LIMITE = 3

@bp.route("/api/gastos/resumo")
def resumo():
    return LIMITE

def outro():
    return 2

class Coisa:
    def metodo(self):
        return 1
'''


class SimbolosTestCase(unittest.TestCase):
    def test_funcao_tocada_traz_nome_e_rota(self):
        self.assertEqual(af.simbolos_mudados(FONTE, {6}), {"resumo", "/api/gastos/resumo"})

    def test_mudar_o_decorador_conta_como_mudar_a_funcao(self):
        self.assertIn("resumo", af.simbolos_mudados(FONTE, {4, 5}))

    def test_constante_e_metodo(self):
        self.assertEqual(af.simbolos_mudados(FONTE, {2}), {"LIMITE"})
        self.assertEqual(af.simbolos_mudados(FONTE, {13}), {"Coisa", "metodo"})

    def test_linha_em_branco_nao_traz_nada(self):
        self.assertEqual(af.simbolos_mudados(FONTE, {1}), set())


class EscolherTestCase(unittest.TestCase):
    def setUp(self):
        self.textos = {f"tests/test_{i}.py": "import app\nimport db\n" for i in range(8)}
        self.textos["tests/test_agenda.py"] = "import caldav_client\n"
        self.textos["tests/test_rota.py"] = 'client.get("/api/gastos/resumo")\n'
        self.textos["tests/test_home.py"] = 'x = "visao-dia.js"\n'
        self.textos["tests/test_notas.py"] = "SELECT * FROM notas\n"
        self.modulos = {"app": "import caldav_client\n", "caldav_client": "import os\n"}

    def _escolher(self, mudados, fonte="", linhas=()):
        return af.escolher(mudados, self.textos, self.modulos, ler=lambda _a: fonte, linhas=lambda _a: set(linhas))

    def test_modulo_comum_pega_quem_cita_e_nao_explode_pelo_central(self):
        escolhidos, _, inteira = self._escolher(["caldav_client.py"])
        self.assertEqual(escolhidos, {"tests/test_agenda.py"})
        self.assertFalse(inteira)

    def test_modulo_central_vai_pela_funcao_e_pela_rota(self):
        escolhidos, _, _ = self._escolher(["app.py"], fonte=FONTE, linhas={6})
        self.assertEqual(escolhidos, {"tests/test_rota.py"})

    def test_css_cita_o_arquivo_e_js_liga_os_testes_de_js(self):
        escolhidos, js, _ = self._escolher(["static/js/visao-dia.js"])
        self.assertEqual(escolhidos, {"tests/test_home.py"})
        self.assertTrue(js)
        self.assertFalse(self._escolher(["static/css/x.css"])[1])

    def test_rota_pega_o_teste_que_so_cita_a_url(self):
        fonte = '@bp.route("/api/gastos/<int:i>")\ndef ver(i):\n    return i\n'
        self.assertEqual(self._escolher(["rotas/garantias.py"], fonte=fonte)[0], {"tests/test_rota.py"})

    def test_arquivo_citado_com_a_pasta_conta(self):
        self.textos["tests/test_tela.py"] = 'abrir("templates/index.html")\n'
        self.textos["tests/test_manifesto.py"] = 'ler("static/manifest.json")\n'
        self.assertEqual(self._escolher(["templates/index.html"])[0], {"tests/test_tela.py"})
        self.assertEqual(self._escolher(["static/manifest.json"])[0], {"tests/test_manifesto.py"})

    def test_documento_nao_roda_nada(self):
        self.assertEqual(self._escolher(["docs/a.md", "README.md", "native/ios/App/a.swift"]), (set(), False, False))

    def test_infra_de_teste_pede_a_suite_inteira(self):
        for arquivo in ("tests/conftest.py", "tests/playwright_helper.py", "tests/banco_modelo.py", "scripts/testes.py"):
            self.assertTrue(self._escolher([arquivo])[2], arquivo)

    def test_topo_de_modulo_central_pede_a_suite_inteira(self):
        self.assertTrue(self._escolher(["app.py"], fonte="import os\n", linhas={1})[2])

    def test_citar_precisa_ser_a_palavra_inteira(self):
        self.assertTrue(af.cita("import db\n", "db"))
        self.assertFalse(af.cita("import dbx\n", "db"))
        self.assertFalse(af.cita("visao-dia.jsx", "visao-dia.js"))


if __name__ == "__main__":
    unittest.main()
