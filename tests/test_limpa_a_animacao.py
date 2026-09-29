# tests/test_limpa_a_animacao.py - Faixa limpa/A-anim (skill
# animacoes-interface): confere os 2 detalhes que ficaram faltando nas
# animacoes de uso diario.
#
#   1) Concluir tarefa: 600ms depois do toque, o item some do DOM de
#      verdade E o proximo item da lista sobe (y menor que antes) - a
#      lista fecha o espaco, nao "pula" com um buraco.
#   2) Secao recolhivel (static/js/ui/secao-recolhivel.js, tecnica grid
#      0fr->1fr): abre/fecha de verdade, com e sem "reduzir movimento"
#      (reduced_motion="reduce" so troca a transicao por corte seco, o
#      resultado final - conteudo visivel/escondido - e o mesmo).
#
# Mesmo padrao de banco temporario + servidor HTTP real (numa thread) de
# tests/test_vel_a2b_otimista.py (db.DB_PATH reapontado ANTES de importar
# app, porque outros modulos de teste tambem trocam db.DB_PATH na propria
# importacao e todos rodam no mesmo processo quando a suite roda junta).
# Porta propria (8861) pra nao colidir com os outros testes com servidor.
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
_DB_PROPRIO = Path(_tmp_dir.name) / "painel.db"
db.DB_PATH = _DB_PROPRIO
db.garantir_banco_nao_producao()

import app as app_module  # noqa: E402

PIN = "123456"
PORTA = int(os.environ.get("PORTA_TESTE_LIMPA_A", "8861"))
BASE_URL = f"http://127.0.0.1:{PORTA}"

db.init_db()
_conn = db.get_db()
auth.definir_pin(_conn, PIN, PIN)
_conn.commit()
_conn.close()

_thread = threading.Thread(
    target=lambda: app_module.app.run(host="127.0.0.1", port=PORTA, use_reloader=False, threaded=True),
    daemon=True,
)
_thread.start()
_pronto = False
for _ in range(50):
    try:
        urllib.request.urlopen(BASE_URL + "/", timeout=1)
        _pronto = True
        break
    except Exception:
        time.sleep(0.2)

try:
    from playwright.sync_api import sync_playwright

    _PLAYWRIGHT_OK = True
except Exception:
    _PLAYWRIGHT_OK = False

from tests.playwright_helper import get_chrome_path; _CHROME = get_chrome_path()


@unittest.skipUnless(_PLAYWRIGHT_OK, "playwright nao instalado")
@unittest.skipUnless(_pronto, "servidor de teste nao respondeu")
class LimpaAAnimacaoTestCase(unittest.TestCase):
    def setUp(self):
        # Outros modulos de teste tambem trocam db.DB_PATH na importacao; o
        # servidor deste modulo roda no mesmo processo, entao reaponta pro
        # banco proprio antes de cada teste (senao: "no such table" quando a
        # suite roda junta).
        db.DB_PATH = _DB_PROPRIO
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()

    def _navegador(self, p, **context_kwargs):
        kwargs = {"headless": True}
        if _CHROME is not None and Path(_CHROME).exists():
            kwargs["executable_path"] = _CHROME
        browser = p.chromium.launch(**kwargs)
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, **context_kwargs)
        r = ctx.request.post(
            BASE_URL + "/login",
            data=json.dumps({"pin": PIN}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(r.status, 200, r.text())
        return browser, ctx

    def test_concluir_tarefa_fecha_o_espaco_sem_pular(self):
        with sync_playwright() as p:
            browser, ctx = self._navegador(p)
            try:
                for titulo in ["limpa-a tarefa 1", "limpa-a tarefa 2"]:
                    rt = ctx.request.post(
                        BASE_URL + "/api/tasks",
                        data=json.dumps({"titulo": titulo}),
                        headers={"Content-Type": "application/json"},
                    )
                    self.assertEqual(rt.status, 201, rt.text())

                erros = []
                page = ctx.new_page()
                page.on("pageerror", lambda exc: erros.append(str(exc)))
                page.goto(BASE_URL + "/")
                page.wait_for_load_state("networkidle")
                page.click('.tab-btn[data-tab="tarefas"]')
                page.wait_for_selector("#lista-tarefas li")

                itens = page.locator("#lista-tarefas li")
                self.assertGreaterEqual(itens.count(), 2, "precisa de pelo menos 2 tarefas pendentes pro teste")
                titulo_2o = itens.nth(1).inner_text()
                y_antes = itens.nth(1).bounding_box()["y"]

                itens.first.locator("button:has-text('concluir')").click(force=True)

                # 600ms depois: o item saiu do DOM de verdade (nao so visualmente) ...
                page.wait_for_timeout(600)
                textos_depois = page.locator("#lista-tarefas li").all_inner_texts()
                self.assertTrue(
                    all(titulo_2o.split("\n")[0] in t or t != "" for t in textos_depois),
                )
                # a 1a tarefa concluida nao aparece mais na lista principal
                self.assertNotIn("limpa-a tarefa 1", "\n".join(textos_depois))

                # ... e o item que era o 2o (agora o 1o) subiu: y menor que antes,
                # a lista fechou o espaco em vez de deixar um buraco.
                novo_primeiro = page.locator("#lista-tarefas li").first
                self.assertIn("limpa-a tarefa 2", novo_primeiro.inner_text())
                y_depois = novo_primeiro.bounding_box()["y"]
                self.assertLess(y_depois, y_antes, f"item nao subiu: antes y={y_antes}, depois y={y_depois}")

                self.assertEqual(erros, [], f"pageerror ao concluir tarefa: {erros}")
            finally:
                browser.close()

    def _abre_e_fecha_secao_vida(self, reduced_motion=None):
        with sync_playwright() as p:
            kwargs = {}
            if reduced_motion:
                kwargs["reduced_motion"] = reduced_motion
            browser, ctx = self._navegador(p, **kwargs)
            try:
                erros = []
                page = ctx.new_page()
                page.on("pageerror", lambda exc: erros.append(str(exc)))
                if reduced_motion:
                    page.emulate_media(reduced_motion=reduced_motion)
                page.goto(BASE_URL + "/")
                page.wait_for_load_state("networkidle")
                page.click('.tab-btn[data-tab="vida"]')
                page.wait_for_selector('.secao-recolhivel[data-secao-id="vida-revisao-trimestral"]')

                # is_visible() do Playwright nao considera overflow:hidden de um
                # ancestral (so visibility/display/opacity do proprio elemento) -
                # com a tecnica de grid, o botao de dentro tem largura/altura
                # mesmo fechado (o grid so encolhe o CONTAINER pra 0px, o
                # overflow:hidden e quem some com o conteudo visualmente). Por
                # isso a altura real do .secao-conteudo (o container que o grid
                # controla) e a medida certa aqui, no lugar de is_visible() no
                # botao de dentro.
                def altura_conteudo():
                    return page.eval_on_selector(
                        "#conteudo-vida-revisao-trimestral", "el => el.getBoundingClientRect().height"
                    )

                secao = page.locator('.secao-recolhivel[data-secao-id="vida-revisao-trimestral"]')
                self.assertEqual(secao.get_attribute("data-aberto"), "false", "secao deveria comecar fechada")
                self.assertLess(altura_conteudo(), 1, "conteudo fechado deveria ter altura ~0")

                secao.locator(".secao-cabecalho").click()
                page.wait_for_timeout(500)
                self.assertEqual(secao.get_attribute("data-aberto"), "true")
                self.assertGreater(altura_conteudo(), 40, "conteudo deveria ganhar altura depois de abrir")

                secao.locator(".secao-cabecalho").click()
                page.wait_for_timeout(500)
                self.assertEqual(secao.get_attribute("data-aberto"), "false")
                self.assertLess(altura_conteudo(), 1, "conteudo deveria voltar a altura ~0 depois de fechar de novo")

                self.assertEqual(erros, [], f"pageerror abrindo/fechando secao (reduced_motion={reduced_motion}): {erros}")
            finally:
                browser.close()

    def test_secao_recolhivel_da_vida_abre_e_fecha(self):
        self._abre_e_fecha_secao_vida(reduced_motion=None)

    def test_secao_recolhivel_da_vida_abre_e_fecha_com_reduced_motion(self):
        self._abre_e_fecha_secao_vida(reduced_motion="reduce")


if __name__ == "__main__":
    unittest.main()
