# tests/test_vel_a2b_otimista.py - Vel A2b (uso diario, atualizacao
# otimista): concluir tarefa tem que sumir da lista quase na hora do toque
# (< 150ms), mesmo com o servidor atrasado, e devolver o item se a rede
# falhar. Mesmo padrao de banco temporario dos testes de UI existentes
# (tests/test_fase9_ui.py: db.DB_PATH temporario + auth.definir_pin), mas
# com um servidor HTTP real (numa thread) porque o Playwright precisa de
# rede de verdade pra interceptar a rota com `page.route`.
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
PORTA = int(os.environ.get("PORTA_TESTE_A2B", "8842"))
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
class VelA2bOtimistaTestCase(unittest.TestCase):
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

    def test_concluir_tarefa_otimista_some_rapido_e_volta_em_erro(self):
        with sync_playwright() as p:
            kwargs = {"headless": True}
            if _CHROME is not None and Path(_CHROME).exists():
                kwargs["executable_path"] = _CHROME
            browser = p.chromium.launch(**kwargs)
            try:
                ctx = browser.new_context(viewport={"width": 390, "height": 844})
                r = ctx.request.post(
                    BASE_URL + "/login",
                    data=json.dumps({"pin": PIN}),
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(r.status, 200, r.text())

                for titulo in ["a2b tarefa 1", "a2b tarefa 2"]:
                    rt = ctx.request.post(
                        BASE_URL + "/api/tasks",
                        data=json.dumps({"titulo": titulo}),
                        headers={"Content-Type": "application/json"},
                    )
                    self.assertEqual(rt.status, 201, rt.text())

                page = ctx.new_page()
                page.goto(BASE_URL + "/")
                page.wait_for_load_state("networkidle")
                page.click('.tab-btn[data-tab="tarefas"]')
                page.wait_for_selector("#lista-tarefas li")

                # ---- cenario 1: servidor "atrasado" (POST fica parado de
                # proposito, sem dar continue/fulfill ainda) -> mesmo assim o
                # item tem que sumir da tela quase na hora do toque, SEM
                # esperar a rede. Mais deterministico que medir ms contra um
                # delay: aqui a rede fica provadamente pendente enquanto
                # conferimos o DOM.
                rotas_paradas = []
                page.route("**/api/tasks/*/complete", lambda route: rotas_paradas.append(route))

                # force=True: pula a espera de "estabilidade" do Playwright
                # antes do clique (o app anima a entrada dos itens da lista) -
                # sem isso o cronometro capturava a espera do PROPRIO
                # Playwright, nao o tempo da nossa atualizacao otimista.
                t0 = time.time()
                page.locator("#lista-tarefas button:has-text('concluir')").first.click(force=True)
                page.wait_for_selector("#lista-tarefas li.saindo", timeout=150)
                dt_ms = (time.time() - t0) * 1000
                self.assertLess(dt_ms, 150, f"item demorou {dt_ms:.0f}ms pra sumir (deveria ser otimista)")
                self.assertEqual(len(rotas_paradas), 1, "o POST deveria estar pendente nesse ponto")

                # so agora libera a rede de verdade (a chamada real termina por tras) -
                # continue_ primeiro, unroute depois (unroute já resolve rotas pendentes).
                rotas_paradas[0].continue_()
                page.unroute("**/api/tasks/*/complete")
                page.wait_for_timeout(400)

                # ---- cenario 2: servidor devolve 500 -> item volta ----
                page.wait_for_selector("#lista-tarefas li")
                n_antes = page.locator("#lista-tarefas li").count()

                def erro_500(route):
                    route.fulfill(status=500, content_type="application/json", body='{"error": "falha simulada"}')

                page.route("**/api/tasks/*/complete", erro_500)
                page.locator("#lista-tarefas button:has-text('concluir')").first.click()
                page.wait_for_timeout(600)
                n_depois = page.locator("#lista-tarefas li").count()
                self.assertEqual(n_depois, n_antes, "item deveria voltar pra lista depois do erro 500")
            finally:
                browser.close()

    def test_nova_tarefa_otimista_aparece_antes_da_resposta_e_some_em_erro(self):
        # Vel (A2d): mesmo padrao do teste acima (concluir tarefa otimista),
        # agora pro formulario direto de "nova tarefa" (#nova-tarefa-btn).
        with sync_playwright() as p:
            kwargs = {"headless": True}
            if _CHROME is not None and Path(_CHROME).exists():
                kwargs["executable_path"] = _CHROME
            browser = p.chromium.launch(**kwargs)
            try:
                ctx = browser.new_context(viewport={"width": 390, "height": 844})
                r = ctx.request.post(
                    BASE_URL + "/login",
                    data=json.dumps({"pin": PIN}),
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(r.status, 200, r.text())

                page = ctx.new_page()
                page.goto(BASE_URL + "/")
                page.wait_for_load_state("networkidle")
                page.click('.tab-btn[data-tab="tarefas"]')
                page.wait_for_selector("#lista-tarefas li")

                # ---- cenario 1: servidor "atrasado" -> a tarefa aparece na
                # lista (estado "salvando") quase na hora do toque, SEM
                # esperar a rede.
                rotas_paradas = []
                page.route("**/api/tasks", lambda route: rotas_paradas.append(route) if route.request.method == "POST" else route.continue_())

                titulo = f"a2d nova tarefa otimista {int(time.time())}"
                page.click("#tarefa-abrir-btn")
                page.wait_for_selector("#nova-tarefa-titulo", state="visible")
                page.fill("#nova-tarefa-titulo", titulo)

                # Vel (limpa/v-abas): media com o relogio do Python (time.time()
                # em volta de page.click()+wait_for_function) inclui a viagem
                # IPC do Playwright ate o browser - fica instavel sob carga
                # (CPU concorrente), estourando os 150ms mesmo quando a
                # atualizacao otimista em si e instantanea. Mede-se agora
                # DENTRO da pagina (performance.now no pointerdown ate o
                # frame em que o item otimista aparece), a mesma regua de
                # scripts/medir_velocidade.py (JS_LER_EVENTO/clicar_e_medir).
                page.evaluate(
                    """(titulo) => {
                        window.__t0_a2d = null;
                        window.__t_visivel_a2d = null;
                        document.addEventListener('pointerdown', () => {
                            if (window.__t0_a2d === null) window.__t0_a2d = performance.now();
                        }, {capture: true, once: true});
                    }""",
                    titulo,
                )
                page.click("#nova-tarefa-btn", force=True)
                dt_ms = page.evaluate(
                    """(titulo) => new Promise((resolve) => {
                        const t0 = window.__t0_a2d ?? performance.now();
                        const limite = performance.now() + 150;
                        (function tick() {
                            const achou = document.querySelector('#lista-tarefas')?.textContent.includes(titulo);
                            if (achou) { resolve(performance.now() - t0); return; }
                            if (performance.now() > limite) { resolve(null); return; }
                            requestAnimationFrame(tick);
                        })();
                    })""",
                    titulo,
                )
                self.assertIsNotNone(dt_ms, "tarefa nao apareceu em 150ms (deveria ser otimista)")
                self.assertLess(dt_ms, 150, f"tarefa demorou {dt_ms:.0f}ms pra aparecer (deveria ser otimista)")
                self.assertEqual(len(rotas_paradas), 1, "o POST deveria estar pendente nesse ponto")
                self.assertTrue(
                    page.locator("#lista-tarefas li.item-otimista").count() >= 1,
                    "o item otimista deveria ter a marca visual .item-otimista",
                )

                rotas_paradas[0].continue_()
                page.unroute("**/api/tasks")
                page.wait_for_timeout(400)
                self.assertIn(titulo, page.locator("#lista-tarefas").inner_text())
                self.assertEqual(
                    page.locator("#lista-tarefas li.item-otimista").count(),
                    0,
                    "o item otimista deveria ter sido substituido pelo real",
                )

                # ---- cenario 2: servidor devolve 500 -> item some e o texto
                # volta pro campo ----
                n_antes = page.locator("#lista-tarefas li").count()
                titulo2 = f"a2d nova tarefa erro {int(time.time())}"

                def erro_500(route):
                    if route.request.method == "POST":
                        route.fulfill(status=500, content_type="application/json", body='{"error": "falha simulada"}')
                    else:
                        route.continue_()

                page.route("**/api/tasks", erro_500)
                page.click("#tarefa-abrir-btn")
                page.wait_for_selector("#nova-tarefa-titulo", state="visible")
                page.fill("#nova-tarefa-titulo", titulo2)
                page.click("#nova-tarefa-btn")
                page.wait_for_timeout(600)
                n_depois = page.locator("#lista-tarefas li").count()
                self.assertEqual(n_depois, n_antes, "a lista nao deveria ganhar item permanente depois do erro 500")
                self.assertNotIn(titulo2, page.locator("#lista-tarefas").inner_text())
                self.assertEqual(page.locator("#nova-tarefa-titulo").input_value(), titulo2, "o texto deveria voltar pro campo em erro")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
