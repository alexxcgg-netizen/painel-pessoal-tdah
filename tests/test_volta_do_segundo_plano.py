# tests/test_volta_do_segundo_plano.py - bug do iPhone (2026-10-13): sair do app com o teclado
# aberto no chat e voltar deixava o campo, a nota e a barra de abas (position: fixed no fundo)
# pendurados no meio da tela ate a proxima rolagem. static/js/nucleo/init.js agora fecha o
# teclado ao sair e, na volta, forca o navegador a medir a tela de novo (vai-e-volta de 1px).
#
# O teclado do iOS nao existe no Chromium headless - aqui confere o que da pra conferir: o campo
# perde o foco ao ir pro segundo plano, a volta re-mede (scrollTo chamado) sem mudar a rolagem
# e sem erro de pagina. Mesmo padrao de servidor real numa thread de test_limpa_a_animacao.py;
# porta propria (8881).
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
PORTA = int(os.environ.get("PORTA_TESTE_VOLTA", "8881"))
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

from tests.playwright_helper import abrir_tela, get_chrome_path  # noqa: E402

_CHROME = get_chrome_path()

# troca document.hidden/visibilityState e dispara o evento, como o iOS faz ao sair/voltar
_SEGUNDO_PLANO = """(escondido) => {
  Object.defineProperty(document, "hidden", { configurable: true, get: () => escondido });
  Object.defineProperty(document, "visibilityState", { configurable: true, get: () => (escondido ? "hidden" : "visible") });
  document.dispatchEvent(new Event("visibilitychange"));
}"""


@unittest.skipUnless(_PLAYWRIGHT_OK, "playwright nao instalado")
@unittest.skipUnless(_pronto, "servidor de teste nao respondeu")
class VoltaDoSegundoPlanoTestCase(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = _DB_PROPRIO

    def test_sair_fecha_o_teclado_e_voltar_remede_sem_pular(self):
        with sync_playwright() as p:
            kwargs = {"headless": True}
            if _CHROME is not None and Path(_CHROME).exists():
                kwargs["executable_path"] = _CHROME
            browser = p.chromium.launch(**kwargs)
            try:
                ctx = browser.new_context(viewport={"width": 390, "height": 844})
                r = ctx.request.post(BASE_URL + "/login", data=json.dumps({"pin": PIN}),
                                     headers={"Content-Type": "application/json"})
                self.assertEqual(r.status, 200, r.text())
                page = ctx.new_page()
                erros = []
                page.on("pageerror", lambda exc: erros.append(str(exc)))
                page.goto(BASE_URL + "/")
                page.wait_for_load_state("networkidle")
                abrir_tela(page, "assistente")
                page.wait_for_selector("#chat-input", state="visible")

                page.focus("#chat-input")
                self.assertEqual(page.evaluate("document.activeElement.id"), "chat-input")
                page.evaluate(_SEGUNDO_PLANO, True)
                self.assertNotEqual(page.evaluate("document.activeElement.id"), "chat-input",
                                    "o teclado (foco no campo) tem que fechar ao sair do app")

                y_antes = page.evaluate("window.scrollY")
                page.evaluate("""() => {
                  window.__medidas = 0;
                  const original = window.scrollTo.bind(window);
                  window.scrollTo = (...a) => { window.__medidas++; return original(...a); };
                }""")
                page.evaluate(_SEGUNDO_PLANO, False)
                page.wait_for_timeout(500)  # rAF + o segundo passe de 350 ms
                self.assertGreaterEqual(page.evaluate("window.__medidas"), 4, "a volta tem que re-medir a tela (2 passes)")
                self.assertEqual(page.evaluate("window.scrollY"), y_antes, "re-medir nao pode mexer na rolagem")

                # pageshow (voltar do cache do navegador) tambem re-mede
                page.evaluate("window.__medidas = 0; window.dispatchEvent(new Event('pageshow'))")
                page.wait_for_timeout(500)
                self.assertGreaterEqual(page.evaluate("window.__medidas"), 4)
                self.assertEqual(erros, [], f"pageerror: {erros}")
            finally:
                browser.close()

    def test_fundo_visivel_abaixo_do_layout_desce_as_pecas_fixas(self):
        """2a camada (2026-10-14): o iOS deixou o fundo visivel 300px abaixo do fundo do layout
        (campo e barra no meio da tela, print do Alex) -> --vv-desvio = 300px e as pecas fixas
        descem esse tanto; com o campo em foco (teclado aberto de verdade) ou tudo certo, 0."""
        with sync_playwright() as p:
            kwargs = {"headless": True}
            if _CHROME is not None and Path(_CHROME).exists():
                kwargs["executable_path"] = _CHROME
            browser = p.chromium.launch(**kwargs)
            try:
                ctx = browser.new_context(viewport={"width": 390, "height": 844})
                ctx.request.post(BASE_URL + "/login", data=json.dumps({"pin": PIN}),
                                 headers={"Content-Type": "application/json"})
                page = ctx.new_page()
                erros = []
                page.on("pageerror", lambda exc: erros.append(str(exc)))
                page.goto(BASE_URL + "/")
                page.wait_for_load_state("networkidle")
                abrir_tela(page, "assistente")
                desvio = "() => getComputedStyle(document.documentElement).getPropertyValue('--vv-desvio').trim()"
                self.assertEqual(page.evaluate(desvio), "0px")
                page.evaluate("""() => {
                  const vv = window.visualViewport;
                  Object.defineProperty(vv, "offsetTop", { configurable: true, get: () => 300 });
                }""")
                page.evaluate(_SEGUNDO_PLANO, False)
                page.wait_for_timeout(1100)  # mede em 0, 350 e 900 ms
                self.assertEqual(page.evaluate(desvio), "300px")
                for sel in ("#tabbar", "#chat-form"):
                    self.assertEqual(page.evaluate(f"getComputedStyle(document.querySelector('{sel}')).translate"), "0px 300px", sel)
                # digitando: o deslocamento e do teclado de verdade - nao mexe
                page.focus("#chat-input")
                page.evaluate("window.visualViewport.dispatchEvent(new Event('resize'))")
                self.assertEqual(page.evaluate(desvio), "0px")
                self.assertEqual(erros, [], f"pageerror: {erros}")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
