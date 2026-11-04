# tests/test_testes_script.py - scripts/testes.py: fila do navegador em paralelo, um pytest por
# arquivo, e o "refazer sozinho" do que falhou. Nenhum pytest de verdade roda aqui: `_rodar` e duble.
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import testes  # noqa: E402


class TextoDoPytestTestCase(unittest.TestCase):
    def test_falhas_pega_so_o_resumo_final(self):
        saida = "tests/a.py F\nFAILED tests/a.py::C::t - AssertionError: x\nERROR tests/b.py\n1 failed in 1s"
        self.assertEqual(testes._falhas(saida), ["FAILED tests/a.py::C::t - AssertionError: x", "ERROR tests/b.py"])

    def test_falhas_enxerga_subteste(self):
        linha = "SUBFAILED(tela='hoje', largura=390) tests/r3.py::C::t - AssertionError: x"
        self.assertEqual(testes._falhas(f"{linha}\n1 failed in 1s"), [linha])

    def test_alvo_vira_o_id_que_o_pytest_aceita(self):
        self.assertEqual(testes._alvo("FAILED tests/a.py::C::t - AssertionError: a b c"), "tests/a.py::C::t")
        self.assertEqual(testes._alvo("ERROR tests/b.py"), "tests/b.py")
        self.assertEqual(testes._alvo("SUBFAILED(tela='a b', largura=390) tests/r3.py::C::t - x: y.py"), "tests/r3.py::C::t")

    def test_contagem_soma_todos_os_arquivos(self):
        saida = ("===== a.py (1 s)\n..\n3 passed, 1 skipped, 2 subtests passed in 2.10s\n"
                 "===== b.py (2 s)\n..\n2 passed, 1 failed in 1.00s\n")
        self.assertEqual(testes._contagem(saida), "5 passed, 1 skipped, 1 failed")

    def test_contagem_sem_nada_nao_quebra(self):
        self.assertEqual(testes._contagem(""), "(sem saida)")

    def test_resumo_le_o_final_do_node(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "js.txt"
            arquivo.write_text("ℹ tests 490\nℹ pass 489\nℹ fail 1\nℹ duration_ms 12\n", encoding="utf-8")
            self.assertEqual(testes._resumo(arquivo), "489 pass, 1 fail")

    def test_resumo_do_pytest_mostra_falhas_e_a_ultima_linha(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "rapida.txt"
            arquivo.write_text("FAILED tests/a.py::t - x\n1 failed, 2 passed in 1s\n", encoding="utf-8")
            self.assertEqual(testes._resumo(arquivo), "FAILED tests/a.py::t - x\n1 failed, 2 passed in 1s")


class RefazerSozinhoTestCase(unittest.TestCase):
    def test_sem_falha_nao_roda_nada(self):
        with patch.object(testes, "_rodar") as rodar:
            self.assertEqual(testes.refazer_sozinho("3 passed in 1s", []), (0, "", []))
        rodar.assert_not_called()

    def test_quem_passou_sozinho_aparece_e_o_codigo_fica_zero(self):
        saida = "FAILED tests/a.py::t1 - x\nFAILED tests/a.py::t2 - y\n"
        with patch.object(testes, "_rodar", return_value=(0, "2 passed in 1s")) as rodar:
            codigo, _, sozinho = testes.refazer_sozinho(saida, [])
        self.assertEqual((codigo, sozinho), (0, ["tests/a.py::t1", "tests/a.py::t2"]))
        self.assertEqual(rodar.call_args.args[0][-2:], ["tests/a.py::t1", "tests/a.py::t2"])

    def test_quem_falhou_de_novo_mantem_o_erro(self):
        saida = "FAILED tests/a.py::t1 - x\nFAILED tests/a.py::t2 - y\n"
        with patch.object(testes, "_rodar", return_value=(1, "FAILED tests/a.py::t2 - y\n1 failed, 1 passed in 1s")):
            codigo, _, sozinho = testes.refazer_sozinho(saida, [])
        self.assertEqual((codigo, sozinho), (1, ["tests/a.py::t1"]))

    def test_cada_arquivo_e_refeito_no_proprio_processo(self):
        saida = "FAILED tests/a.py::t1 - x\nFAILED tests/b.py::t2 - y\n"
        with patch.object(testes, "_rodar", return_value=(0, "1 passed in 1s")) as rodar:
            testes.refazer_sozinho(saida, [])
        self.assertEqual([c.args[0][-1] for c in rodar.call_args_list], ["tests/a.py::t1", "tests/b.py::t2"])

    def test_refazer_que_morreu_nao_vira_passou_sozinho(self):
        with patch.object(testes, "_rodar", return_value=(3, "INTERNALERROR> boom")):
            codigo, _, sozinho = testes.refazer_sozinho("FAILED tests/a.py::t - x\n", [])
        self.assertEqual((codigo, sozinho), (3, []))

    def test_pular_ao_refazer_nao_e_passar(self):
        with patch.object(testes, "_rodar", return_value=(0, "1 skipped in 1s")):
            codigo, _, sozinho = testes.refazer_sozinho("FAILED tests/a.py::t - x\n", [])
        self.assertEqual((codigo, sozinho), (1, []))


class FecharNavegadorTestCase(unittest.TestCase):
    INSTAVEL = ("a.py", 1, "FAILED tests/a.py::t - x\n1 failed, 2 passed in 1s", 1)
    OK = ("b.py", 0, "3 passed in 1s", 1)

    def _fechar(self, resultados, refeito=(0, "1 passed in 1s"), extras=()):
        with patch.object(testes, "_rodar", return_value=refeito) as self.rodar:
            codigo, _, linhas = testes.fechar_navegador(resultados, list(extras))
        return codigo, linhas

    def test_instavel_que_passa_sozinho_fica_verde_e_aparece(self):
        codigo, linhas = self._fechar([self.INSTAVEL, self.OK])
        self.assertEqual(codigo, 0)
        self.assertEqual(linhas, ["so passou sozinho: tests/a.py::t", "5 passed, 1 so sozinho"])

    def test_tudo_certo_nao_refaz_nada(self):
        codigo, linhas = self._fechar([self.OK])
        self.assertEqual((codigo, linhas), (0, ["3 passed"]))
        self.rodar.assert_not_called()

    def test_arquivo_que_morreu_nao_some_com_o_refazer_de_outro(self):
        for codigo_morto in (3, 3221225477, testes.ESTOUROU):
            codigo, linhas = self._fechar([self.INSTAVEL, ("c.py", codigo_morto, "INTERNALERROR> boom", 1)])
            self.assertEqual(codigo, 1)
            self.assertIn(f"FALHOU: c.py: saiu com codigo {codigo_morto}", linhas)

    def test_falha_de_subteste_e_refeita_e_nao_e_perdoada_a_toa(self):
        arquivo = ("r3.py", 1, "SUBFAILED(tela='a b', largura=390) tests/r3.py::C::t - x\n1 failed in 1s", 1)
        codigo, _ = self._fechar([arquivo, self.INSTAVEL], refeito=(1, "FAILED tests/x.py::t - y\n1 failed in 1s"))
        self.assertEqual(codigo, 1)
        self.assertEqual(self.rodar.call_args_list[0].args[0][-1], "tests/r3.py::C::t")

    def test_servidor_que_nao_subiu_e_falha_mesmo_saindo_zero(self):
        pulou = ("r1.py", 0, "SKIPPED [7] tests/r1.py:98: servidor de teste nao respondeu\n7 skipped in 11s", 11)
        codigo, linhas = self._fechar([pulou, self.OK])
        self.assertEqual(codigo, 1)
        self.assertIn("FALHOU: r1.py: servidor de teste nao respondeu", linhas)

    def test_skip_comum_nao_e_falha(self):
        pulou = ("r1.py", 0, "SKIPPED [1] tests/r1.py:98: so no Linux\n1 passed, 1 skipped in 1s", 1)
        self.assertEqual(self._fechar([pulou])[0], 0)

    def test_arquivo_sem_nenhum_teste_e_falha_sem_filtro(self):
        vazio = ("c.py", 5, "no tests ran in 0.1s", 0)
        self.assertEqual(self._fechar([vazio])[0], 1)
        self.assertEqual(self._fechar([vazio], extras=["-k", "nada"])[0], 0)

    def test_com_x_nao_refaz_porque_o_resto_do_arquivo_nem_rodou(self):
        codigo, linhas = self._fechar([self.INSTAVEL], extras=["-x"])
        self.assertEqual(codigo, 1)
        self.assertIn("FAILED tests/a.py::t - x", linhas)
        self.rodar.assert_not_called()


class FilaDoNavegadorTestCase(unittest.TestCase):
    def setUp(self):
        self._pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self._pasta.cleanup)
        self.base = Path(self._pasta.name)
        (self.base / "tests").mkdir()
        self.arquivos = []
        for nome in ("test_a.py", "test_b.py", "test_c.py"):
            caminho = self.base / "tests" / nome
            caminho.write_text("x", encoding="utf-8")
            self.arquivos.append(caminho)

    def test_cada_arquivo_ganha_um_pytest_e_o_mais_demorado_vem_primeiro(self):
        ordem = []

        def rodar(comando, base, ambiente=None):
            ordem.append(Path(comando[-1]).name)
            return 0, "1 passed in 0.1s"

        with patch.object(testes, "PROCESSOS_NAVEGADOR", 1), patch.object(testes, "_rodar", rodar), \
                patch.object(testes, "_ler_tempos", return_value={"test_b.py": 50, "test_c.py": 9}):
            resultados = testes.rodar_navegador(self.arquivos, [], self.base)
        self.assertEqual(ordem, ["test_b.py", "test_c.py", "test_a.py"])
        self.assertEqual([r[0] for r in resultados], ["test_b.py", "test_c.py", "test_a.py"])
        self.assertEqual(testes._contagem(testes._juntar(resultados)), "3 passed")

    def test_cada_arquivo_roda_na_propria_porta_livre(self):
        self.arquivos[0].write_text('os.environ.get("PORTA_TESTE_A", "8842")', encoding="utf-8")
        self.arquivos[1].write_text('os.environ.get("PORTA_TESTE_B", "8843")', encoding="utf-8")
        with patch.object(testes, "AMBIENTE", {}):  # a propria suite pode ter posto estas no ambiente
            a = testes._portas_livres(self.arquivos[0])
            b = testes._portas_livres(self.arquivos[1])
        self.assertNotIn("PORTA_TESTE_B", a)
        self.assertNotEqual(int(a["PORTA_TESTE_A"]), 8842)
        self.assertNotEqual(a["PORTA_TESTE_A"], b["PORTA_TESTE_B"])

    def test_fila_presa_morre_no_limite_e_vira_estouro(self):
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.addCleanup(proc.kill)
        self.assertEqual(testes._esperar_fila(proc, time.monotonic() + 0.2), testes.ESTOUROU)
        self.assertIsNotNone(proc.poll())

    def test_fila_que_terminou_devolve_o_codigo_dela(self):
        proc = subprocess.Popen([sys.executable, "-c", "raise SystemExit(3)"])
        self.assertEqual(testes._esperar_fila(proc, time.monotonic() + 30), 3)

    def test_porta_fica_fora_da_faixa_das_conexoes_de_saida(self):
        self.arquivos[0].write_text('os.environ.get("PORTA_TESTE_A", "8842")', encoding="utf-8")
        with patch.object(testes, "AMBIENTE", {}):
            porta = int(testes._portas_livres(self.arquivos[0])["PORTA_TESTE_A"])
        self.assertLess(porta, 49152)

    def test_porta_ocupada_fica_de_fora(self):
        with socket.socket() as ocupada:
            ocupada.bind(("127.0.0.1", 0))
            ocupada.listen()
            numero = ocupada.getsockname()[1]
            with patch.object(testes, "_PROXIMA_PORTA", iter([numero, 28999])):
                self.assertEqual(testes._porta_livre(), 28999)

    def test_arquivo_que_nao_existe_nao_trava_a_porta(self):
        self.assertEqual(testes._portas_livres(self.base / "nao-existe.py"), testes.AMBIENTE)

    def test_tempos_quebrados_ou_ausentes_nao_travam(self):
        with patch.object(testes, "TEMPOS_NAVEGADOR", self.base / "nao-existe.json"):
            self.assertEqual(testes._ler_tempos(), {})
        quebrado = self.base / "quebrado.json"
        quebrado.write_text("{ nao e json", encoding="utf-8")
        with patch.object(testes, "TEMPOS_NAVEGADOR", quebrado):
            self.assertEqual(testes._ler_tempos(), {})


class CopiaDoCodigoTestCase(unittest.TestCase):
    def test_copia_que_falha_nao_deixa_pasta_pra_tras(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = Path(pasta)
            (base / "a.txt").write_text("x", encoding="utf-8")
            (base / "copia").mkdir()
            lista = SimpleNamespace(stdout=b"a.txt\0")
            with patch.object(testes, "RAIZ", base), patch.object(testes.subprocess, "run", return_value=lista), \
                    patch.object(testes.tempfile, "mkdtemp", return_value=str(base / "copia")), \
                    patch.object(testes.shutil, "copyfile", side_effect=PermissionError):
                with self.assertRaises(PermissionError):
                    testes.copiar_codigo()
            self.assertFalse((base / "copia").exists())


class SeparacaoDasFilasTestCase(unittest.TestCase):
    def test_cada_tipo_de_arquivo_vai_pra_fila_certa(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = Path(pasta)
            (base / "tests").mkdir()
            (base / "tests" / "test_comum.py").write_text("def test_x(): pass", encoding="utf-8")
            (base / "tests" / "test_app.py").write_text("def test_x(): pass", encoding="utf-8")
            (base / "tests" / "test_tela.py").write_text("from playwright.sync_api import sync_playwright", encoding="utf-8")
            filas = testes._filas(base)
        self.assertEqual([a.name for a in filas["rapida"][0]], ["test_comum.py"])
        self.assertEqual([a.name for a in filas["grandes"][0]], ["test_app.py"])
        self.assertEqual([a.name for a in filas["navegador"][0]], ["test_tela.py"])


if __name__ == "__main__":
    unittest.main()
