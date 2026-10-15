# tests/test_microfone_falhas.py - "clico pra falar e as vezes nao sai, ou nao escuta nada"
# (Alex, 2026-10-15). Navegador de verdade (Chromium com microfone falso), servidor numa thread,
# transcricao interceptada - nada de rede nem IA. Porta propria (8895).
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
PORTA = int(os.environ.get("PORTA_TESTE_MIC", "8895"))
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


@unittest.skipUnless(_PLAYWRIGHT_OK, "playwright nao instalado")
@unittest.skipUnless(_pronto, "servidor de teste nao respondeu")
class MicrofoneFalhasTestCase(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = _DB_PROPRIO

    def _abrir(self, p, script=None):
        kwargs = {"headless": True, "args": ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"]}
        if _CHROME is not None and Path(_CHROME).exists():
            kwargs["executable_path"] = _CHROME
        browser = p.chromium.launch(**kwargs)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        ctx.grant_permissions(["microphone"], origin=BASE_URL)
        if script:
            ctx.add_init_script(script)
        ctx.request.post(BASE_URL + "/login", data=json.dumps({"pin": PIN}), headers={"Content-Type": "application/json"})
        page = ctx.new_page()
        self.erros = []
        page.on("pageerror", lambda exc: self.erros.append(str(exc)))
        self.transcricoes = []

        def _transcrever(route):
            self.transcricoes.append(route.request.post_data_buffer or b"")
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"texto": "teste do microfone"}))

        page.route("**/api/voz/transcrever", _transcrever)
        page.route("**/api/chat**", lambda route: route.fulfill(status=503, body="{}", content_type="application/json"))
        page.goto(BASE_URL + "/")
        page.wait_for_load_state("networkidle")
        abrir_tela(page, "assistente")
        page.wait_for_selector("#chat-mic", state="visible")
        return browser, page

    def test_microfone_que_nao_responde_avisa_e_libera(self):
        """getUserMedia que nunca responde deixava a barra em 0:00 pra sempre."""
        with sync_playwright() as p:
            browser, page = self._abrir(p, "navigator.mediaDevices.getUserMedia = () => new Promise(() => {});")
            try:
                page.click("#chat-mic")
                self.assertIn("gravando", page.get_attribute("#chat-form", "class") or "")
                page.wait_for_timeout(5600)
                self.assertNotIn("gravando", page.get_attribute("#chat-form", "class") or "")
                self.assertIn("não respondeu", page.inner_text("#erro-banner"))
                self.assertEqual(self.erros, [])
            finally:
                browser.close()

    def test_detector_surdo_nao_joga_o_audio_fora(self):
        """AudioContext parado (iPhone na volta do fundo) = detector so le zeros. Antes virava
        'Nao ouvi nada' e o audio ia pro lixo; agora vai pra transcricao, sem cortar por trecho."""
        surdo = "AnalyserNode.prototype.getFloatTimeDomainData = function (a) { a.fill(0); };"
        with sync_playwright() as p:
            browser, page = self._abrir(p, surdo)
            try:
                page.click("#chat-mic")
                page.wait_for_timeout(1500)
                page.click("#chat-send")
                page.wait_for_timeout(1200)
                self.assertEqual(len(self.transcricoes), 1, "o audio tem que ir pra transcricao")
                corpo = self.transcricoes[0]
                self.assertIn(b'name="audio"', corpo)
                self.assertNotIn(b'name="fala_ate"', corpo)
                self.assertNotIn(b'name="trechos_voz"', corpo)
                self.assertNotIn("Não ouvi nada", page.get_attribute("#chat-input", "placeholder") or "")
                self.assertEqual(self.erros, [])
            finally:
                browser.close()

    def test_mandar_antes_do_microfone_abrir_avisa(self):
        """Tocar de novo antes de o microfone abrir sumia calado - agora avisa."""
        lento = """
          const _orig = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
          navigator.mediaDevices.getUserMedia = (c) => new Promise((r) => setTimeout(() => r(_orig(c)), 800));
        """
        with sync_playwright() as p:
            browser, page = self._abrir(p, lento)
            try:
                page.click("#chat-mic")
                page.wait_for_timeout(150)
                page.click("#chat-send")  # gravando, o enviar manda
                page.wait_for_timeout(300)
                self.assertIn("Gravou muito pouco", page.get_attribute("#chat-input", "placeholder") or "")
                page.wait_for_timeout(900)  # o microfone que abriu atrasado e solto, sem gravar
                self.assertNotIn("gravando", page.get_attribute("#chat-form", "class") or "")
                self.assertEqual(self.transcricoes, [])
                self.assertEqual(self.erros, [])
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
