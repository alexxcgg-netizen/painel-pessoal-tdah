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

from tests.playwright_helper import subir_servidor  # noqa: E402

subir_servidor(app_module.app, PORTA)
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

# Marco dos cenarios de erro: mostrarErro roda no fim do apiFetch e o que desfaz o toque vem
# logo depois, no mesmo passo. Nao espera a contagem da lista pra nao esvaziar o assert dela.
ERRO_APARECEU = "document.getElementById('erro-banner').textContent.includes('falha simulada')"

# Cronometro DENTRO da pagina, do toque (pointerdown) ate o quadro que mostra a mudanca: a mesma regua
# de scripts/medir_velocidade.py. O relogio do Python inclui a viagem do Playwright ate o navegador e
# estoura os 150 ms com a CPU cheia. Marcar o toque so no click, ou parar na mudanca do DOM, deixa de
# fora uma trava de 1 s no pointerdown ou no quadro seguinte, com a tela parada.
_CRONOMETRAR = """([seletor, texto]) => {
  const pronto = () => [...document.querySelectorAll(seletor)].some((el) => el.textContent.includes(texto));
  window.__toqueEm = null;
  window.__quadroEm = null;
  window.addEventListener('pointerdown', () => { window.__toqueEm = performance.now(); }, {capture: true, once: true});
  const olhar = new MutationObserver(() => {
    if (!pronto()) return;
    olhar.disconnect();
    requestAnimationFrame(() => { window.__quadroEm = performance.now(); });
  });
  olhar.observe(document.getElementById('lista-tarefas'),
    {subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class']});
}"""


def _tempo_ate_o_quadro(page):
    page.wait_for_function("window.__quadroEm !== null")
    return page.evaluate("window.__quadroEm - window.__toqueEm")


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

    def _conferir_linha_inteira(self, page):
        self.assertEqual(page.locator("#lista-tarefas li.saindo").count(), 0, "item voltou pela metade")
        self.assertEqual(page.locator("#lista-tarefas li.tl-feita").count(), 0, "item voltou riscado")
        self.assertEqual(page.locator("#lista-tarefas .tl-ponto[disabled]").count(), 0, "item voltou sem poder tocar")

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
                # sem isso o Playwright segurava o clique sem ser culpa do app.
                page.evaluate(_CRONOMETRAR, ["#lista-tarefas li.saindo", ""])
                page.locator("#lista-tarefas .tl-ponto").first.click(force=True)
                dt_ms = _tempo_ate_o_quadro(page)
                self.assertLess(dt_ms, 150, f"item demorou {dt_ms:.0f}ms pra sumir (deveria ser otimista)")
                self.assertEqual(len(rotas_paradas), 1, "o POST deveria estar pendente nesse ponto")

                # so agora libera a rede de verdade (a chamada real termina por tras) -
                # continue_ primeiro, unroute depois (unroute já resolve rotas pendentes).
                pendentes = page.evaluate("_tarefasPendentes.length")
                rotas_paradas[0].continue_()
                page.unroute("**/api/tasks/*/complete")
                # a lista recarrega quando o POST volta e a linha ja saiu; tocar na proxima
                # antes disso deixa o re-render passar por cima da linha que esta saindo
                page.wait_for_function("(n) => _tarefasPendentes.length < n", arg=pendentes, timeout=10000)
                # linha do tempo: a linha concluida so sai depois do check (~500 ms do toque) -
                # contar antes disso pegava ela ainda na tela
                page.wait_for_selector("#lista-tarefas li.saindo", state="detached")

                # ---- cenario 2: servidor devolve 500 -> item volta ----
                page.wait_for_selector("#lista-tarefas li")
                n_antes = page.locator("#lista-tarefas li").count()

                def erro_500(route):
                    route.fulfill(status=500, content_type="application/json", body='{"error": "falha simulada"}')

                page.route("**/api/tasks/*/complete", erro_500)
                page.locator("#lista-tarefas .tl-ponto").first.click()
                page.wait_for_function(ERRO_APARECEU)
                # prova negativa: a linha sairia do DOM 500 ms depois do toque (removerTimeout em
                # tarefas.js) e o erro e quem cancela isso. Contar antes desse prazo passa com o
                # rollback quebrado; este timer, armado depois do dele, so dispara depois.
                page.evaluate("new Promise((pronto) => setTimeout(pronto, 500))")
                n_depois = page.locator("#lista-tarefas li").count()
                self.assertEqual(n_depois, n_antes, "item deveria voltar pra lista depois do erro 500")
                self._conferir_linha_inteira(page)

                # ---- cenario 3: o erro chega com a linha ja fora do DOM -> ela e recolocada no
                # lugar. O erro instantaneo acima nunca passa por esse caminho.
                page.unroute("**/api/tasks/*/complete")
                rotas_paradas.clear()
                page.route("**/api/tasks/*/complete", lambda route: rotas_paradas.append(route))
                page.locator("#lista-tarefas .tl-ponto").first.click()
                page.wait_for_function("(n) => document.querySelectorAll('#lista-tarefas li').length < n", arg=n_antes)
                erro_500(rotas_paradas[0])
                page.wait_for_function("(n) => document.querySelectorAll('#lista-tarefas li').length === n", arg=n_antes)
                self._conferir_linha_inteira(page)
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

                page.evaluate(_CRONOMETRAR, ["#lista-tarefas", titulo])
                page.click("#nova-tarefa-btn", force=True)
                dt_ms = _tempo_ate_o_quadro(page)
                self.assertLess(dt_ms, 150, f"tarefa demorou {dt_ms:.0f}ms pra aparecer (deveria ser otimista)")
                self.assertEqual(len(rotas_paradas), 1, "o POST deveria estar pendente nesse ponto")
                self.assertTrue(
                    page.locator("#lista-tarefas li.item-otimista").count() >= 1,
                    "o item otimista deveria ter a marca visual .item-otimista",
                )

                rotas_paradas[0].continue_()
                page.unroute("**/api/tasks")
                # o item otimista sai quando o POST volta; o real entra no recarregar da lista
                page.wait_for_function(
                    """(titulo) => {
                        const lista = document.querySelector('#lista-tarefas');
                        return !lista.querySelector('li.item-otimista') && lista.textContent.includes(titulo);
                    }""",
                    arg=titulo,
                    timeout=10000,
                )
                # o sheet fecha em 240 ms: reabrir antes disso cancela o fechamento
                page.wait_for_selector("#tarefa-sheet", state="hidden")
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
                # o app tira o item e devolve o texto logo depois de mostrar o erro
                page.wait_for_function(ERRO_APARECEU)
                n_depois = page.locator("#lista-tarefas li").count()
                self.assertEqual(n_depois, n_antes, "a lista nao deveria ganhar item permanente depois do erro 500")
                self.assertNotIn(titulo2, page.locator("#lista-tarefas").inner_text())
                self.assertEqual(page.locator("#nova-tarefa-titulo").input_value(), titulo2, "o texto deveria voltar pro campo em erro")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
