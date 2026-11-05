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
import time
import unittest
import urllib.request
from contextlib import nullcontext
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

from tests.playwright_helper import CONTAR_FETCH, abrir_tela, esperar_carga, get_chrome_path  # noqa: E402

_CHROME = get_chrome_path()


class _Contextos:
    """Cada teste usa o Chromium da classe: new_context ja traz o contador de fetch (esperar_carga)
    e close() fecha so os contextos do teste, nunca o navegador compartilhado."""

    def __init__(self, browser):
        self._browser = browser
        self._contextos = []

    def new_context(self, **kwargs):
        ctx = self._browser.new_context(**kwargs)
        ctx.add_init_script(CONTAR_FETCH)
        self._contextos.append(ctx)
        return ctx

    def close(self):
        for ctx in self._contextos:
            ctx.close()

# troca document.hidden/visibilityState e dispara o evento, como o iOS faz ao sair/voltar
_SEGUNDO_PLANO = """(escondido) => {
  Object.defineProperty(document, "hidden", { configurable: true, get: () => escondido });
  Object.defineProperty(document, "visibilityState", { configurable: true, get: () => (escondido ? "hidden" : "visible") });
  document.dispatchEvent(new Event("visibilitychange"));
}"""

# volta contando as medidas que a volta agenda (init.js: 0, 350 e 900 ms). A troca dura so o evento:
# quem agenda pega o contador, a remedida automatica da 6a camada continua fora da conta
_VOLTAR_CONTANDO_MEDIDAS = """() => {
  const medir = window._medirDesvioTela;
  window.__medidasDaVolta = 0;
  window._medirDesvioTela = () => { medir(); window.__medidasDaVolta++; };
  (""" + _SEGUNDO_PLANO + """)(false);
  window._medirDesvioTela = medir;
}"""


def _voltar_e_esperar_as_medidas(page):
    # "0px" ja e o valor de antes da volta: esperar o valor nao provaria nada, tem que esperar a medida
    page.evaluate(_VOLTAR_CONTANDO_MEDIDAS)
    page.wait_for_function("window.__medidasDaVolta >= 3")


def _eh_visto(request):
    return request.url.endswith("/api/push/visto") and request.method == "POST"


@unittest.skipUnless(_PLAYWRIGHT_OK, "playwright nao instalado")
@unittest.skipUnless(_pronto, "servidor de teste nao respondeu")
class VoltaDoSegundoPlanoTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Um Playwright e um Chromium pra classe toda; cada teste ganha contexto novo (isolado).
        cls._pw_cm = sync_playwright()
        cls._pw = cls._pw_cm.__enter__()
        kwargs = {"headless": True}
        if _CHROME is not None and Path(_CHROME).exists():
            kwargs["executable_path"] = _CHROME
        cls._browser = cls._pw.chromium.launch(**kwargs)

    @classmethod
    def tearDownClass(cls):
        try:
            cls._browser.close()
        finally:
            cls._pw_cm.__exit__(None, None, None)

    def setUp(self):
        db.DB_PATH = _DB_PROPRIO

    def test_sair_fecha_o_teclado_e_voltar_remede_sem_pular(self):
        with nullcontext(self._pw) as p:
            browser = _Contextos(self._browser)
            try:
                ctx = browser.new_context(viewport={"width": 390, "height": 844})
                r = ctx.request.post(BASE_URL + "/login", data=json.dumps({"pin": PIN}),
                                     headers={"Content-Type": "application/json"})
                self.assertEqual(r.status, 200, r.text())
                page = ctx.new_page()
                erros = []
                page.on("pageerror", lambda exc: erros.append(str(exc)))
                page.goto(BASE_URL + "/")
                esperar_carga(page)
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
                page.wait_for_function("window.__medidas >= 4")  # rAF + o segundo passe de 350 ms
                self.assertGreaterEqual(page.evaluate("window.__medidas"), 4, "a volta tem que re-medir a tela (2 passes)")
                self.assertEqual(page.evaluate("window.scrollY"), y_antes, "re-medir nao pode mexer na rolagem")

                # pageshow (voltar do cache do navegador) tambem re-mede
                page.evaluate("window.__medidas = 0; window.dispatchEvent(new Event('pageshow'))")
                page.wait_for_function("window.__medidas >= 4")
                self.assertGreaterEqual(page.evaluate("window.__medidas"), 4)
                self.assertEqual(erros, [], f"pageerror: {erros}")
            finally:
                browser.close()

    def test_fundo_visivel_abaixo_do_layout_desce_as_pecas_fixas(self):
        """2a camada (2026-10-14): o iOS deixou o fundo visivel 300px abaixo do fundo do layout
        (campo e barra no meio da tela, print do Alex) -> --vv-desvio = 300px e as pecas fixas
        descem esse tanto; com o campo em foco (teclado aberto de verdade) ou tudo certo, 0."""
        with nullcontext(self._pw) as p:
            browser = _Contextos(self._browser)
            try:
                ctx = browser.new_context(viewport={"width": 390, "height": 844})
                ctx.request.post(BASE_URL + "/login", data=json.dumps({"pin": PIN}),
                                 headers={"Content-Type": "application/json"})
                page = ctx.new_page()
                erros = []
                page.on("pageerror", lambda exc: erros.append(str(exc)))
                page.goto(BASE_URL + "/")
                esperar_carga(page)
                abrir_tela(page, "assistente")
                desvio = "() => getComputedStyle(document.documentElement).getPropertyValue('--vv-desvio').trim()"
                self.assertEqual(page.evaluate(desvio), "0px")
                page.evaluate("""() => {
                  const vv = window.visualViewport;
                  Object.defineProperty(vv, "offsetTop", { configurable: true, get: () => 300 });
                }""")
                _voltar_e_esperar_as_medidas(page)
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

    def test_folga_fixa_do_app_na_tela_de_inicio_nao_desce_a_barra(self):
        """3a camada (2026-10-14, print do Alex: barra cortada pela metade). No app da tela de
        inicio o fundo visivel fica sempre ~34px abaixo do layout - e o normal, entao 0px; so o
        que passar disso (o bug de verdade, +300) desce as pecas."""
        with nullcontext(self._pw) as p:
            browser = _Contextos(self._browser)
            try:
                ctx = browser.new_context(viewport={"width": 390, "height": 844})
                ctx.add_init_script("""
                  if (window.visualViewport) {
                    Object.defineProperty(window.visualViewport, "height", {
                      configurable: true, get: () => document.documentElement.clientHeight + 34 });
                  }""")
                ctx.request.post(BASE_URL + "/login", data=json.dumps({"pin": PIN}),
                                 headers={"Content-Type": "application/json"})
                page = ctx.new_page()
                erros = []
                page.on("pageerror", lambda exc: erros.append(str(exc)))
                page.goto(BASE_URL + "/")
                esperar_carga(page)
                desvio = "() => getComputedStyle(document.documentElement).getPropertyValue('--vv-desvio').trim()"
                _voltar_e_esperar_as_medidas(page)
                self.assertEqual(page.evaluate(desvio), "0px")
                page.evaluate("""() => Object.defineProperty(window.visualViewport, "offsetTop",
                                   { configurable: true, get: () => 300 })""")
                _voltar_e_esperar_as_medidas(page)
                # 5a camada: a sonda mede o fundo visivel contra onde o fixed se prende de verdade -
                # os 34 de folga fingidos + 300 do teclado preso = 334, tudo de verdade fora da tela
                self.assertEqual(page.evaluate(desvio), "334px")
                self.assertEqual(erros, [], f"pageerror: {erros}")
            finally:
                browser.close()

    def test_primeira_medida_zero_e_depois_a_folga_normal_nao_desce_a_barra(self):
        """4a camada (2026-10-15, "ainda aparece pela metade"): a 1a medida saia 0 (iOS se
        arrumando ao abrir) e depois vinham os 34px normais - a regra do MENOR desvio descia a
        barra 34px. Folga pequena nunca mexe; o teclado preso (+300) continua corrigido."""
        with nullcontext(self._pw) as p:
            browser = _Contextos(self._browser)
            try:
                ctx = browser.new_context(viewport={"width": 390, "height": 844})
                ctx.request.post(BASE_URL + "/login", data=json.dumps({"pin": PIN}),
                                 headers={"Content-Type": "application/json"})
                page = ctx.new_page()
                erros = []
                page.on("pageerror", lambda exc: erros.append(str(exc)))
                page.goto(BASE_URL + "/")
                esperar_carga(page)
                desvio = "() => getComputedStyle(document.documentElement).getPropertyValue('--vv-desvio').trim()"
                self.assertEqual(page.evaluate(desvio), "0px")  # 1a medida: 0
                page.evaluate("""() => Object.defineProperty(window.visualViewport, "height",
                                   { configurable: true, get: () => document.documentElement.clientHeight + 34 })""")
                _voltar_e_esperar_as_medidas(page)
                self.assertEqual(page.evaluate(desvio), "0px", "folga de 34px nao pode descer a barra")
                self.assertEqual(page.evaluate("getComputedStyle(document.querySelector('#tabbar')).translate"), "0px")
                page.evaluate("""() => Object.defineProperty(window.visualViewport, "offsetTop",
                                   { configurable: true, get: () => 300 })""")
                _voltar_e_esperar_as_medidas(page)
                self.assertEqual(page.evaluate(desvio), "334px")  # 34 fingidos + 300
                self.assertEqual(erros, [], f"pageerror: {erros}")
            finally:
                browser.close()

    def test_medida_real_do_iphone_documento_menor_que_a_tela_nao_desce_a_barra(self):
        """5a camada (2026-10-15, /api/diagnostico do iPhone dele, iOS 18.7 no app da tela de
        inicio): clientHeight 62px menor que a tela (faixa do relogio) e o fundo visivel = fundo da
        tela. A conta antiga (fundo visivel - clientHeight) descia a barra 62px pra fora da tela;
        o ancoradouro do position:fixed nao mudou, entao 0. O teclado preso (+300) segue corrigido."""
        with nullcontext(self._pw) as p:
            browser = _Contextos(self._browser)
            try:
                ctx = browser.new_context(viewport={"width": 440, "height": 956})
                ctx.add_init_script("""
                  Object.defineProperty(HTMLHtmlElement.prototype, "clientHeight", {
                    configurable: true, get: () => window.innerHeight - 62 });""")
                ctx.request.post(BASE_URL + "/login", data=json.dumps({"pin": PIN}),
                                 headers={"Content-Type": "application/json"})
                page = ctx.new_page()
                erros = []
                page.on("pageerror", lambda exc: erros.append(str(exc)))
                page.goto(BASE_URL + "/")
                esperar_carga(page)
                desvio = "() => getComputedStyle(document.documentElement).getPropertyValue('--vv-desvio').trim()"
                _voltar_e_esperar_as_medidas(page)
                self.assertEqual(page.evaluate(desvio), "0px", "62px da faixa do relogio nao e bug")
                fundo = page.evaluate("document.querySelector('#tabbar').getBoundingClientRect().bottom")
                self.assertLessEqual(fundo, 956, "a barra tem que caber inteira na tela")
                page.evaluate("""() => Object.defineProperty(window.visualViewport, "offsetTop",
                                   { configurable: true, get: () => 300 })""")
                _voltar_e_esperar_as_medidas(page)
                self.assertEqual(page.evaluate(desvio), "300px")
                self.assertEqual(erros, [], f"pageerror: {erros}")
            finally:
                browser.close()

    def test_medida_impossivel_no_meio_da_transicao_nao_some_com_a_barra(self):
        """6a camada (2026-10-16, diagnostico do iPhone dele na tela IA): o iOS devolveu
        vvTopo = 956 (a tela inteira) no meio de uma transicao e a barra desceu 1912px, sumida.
        Medida impossivel e descartada (0px, barra no lugar) e remedida; quando a tela assenta
        no teclado preso de verdade (+300), a correcao volta."""
        with nullcontext(self._pw) as p:
            browser = _Contextos(self._browser)
            try:
                ctx = browser.new_context(viewport={"width": 440, "height": 956})
                ctx.request.post(BASE_URL + "/login", data=json.dumps({"pin": PIN}),
                                 headers={"Content-Type": "application/json"})
                page = ctx.new_page()
                erros = []
                page.on("pageerror", lambda exc: erros.append(str(exc)))
                page.goto(BASE_URL + "/")
                esperar_carga(page)
                abrir_tela(page, "assistente")
                desvio = "() => getComputedStyle(document.documentElement).getPropertyValue('--vv-desvio').trim()"
                page.evaluate("""() => Object.defineProperty(window.visualViewport, "offsetTop",
                                   { configurable: true, get: () => window.innerHeight })""")
                _voltar_e_esperar_as_medidas(page)
                self.assertEqual(page.evaluate(desvio), "0px", "vvTopo = tela inteira e medida impossivel")
                fundo = page.evaluate("document.querySelector('#tabbar').getBoundingClientRect().bottom")
                self.assertLessEqual(fundo, 956, "a barra tem que continuar na tela")
                # a tela assenta (teclado preso de verdade): a remedida automatica corrige
                page.evaluate("""() => Object.defineProperty(window.visualViewport, "offsetTop",
                                   { configurable: true, get: () => 300 })""")
                page.wait_for_function(f"({desvio})() === '300px'")
                self.assertEqual(page.evaluate(desvio), "300px")
                self.assertEqual(erros, [], f"pageerror: {erros}")
            finally:
                browser.close()

    def test_app_aberto_avisa_que_viu_os_avisos_insistentes(self):
        """2026-10-16: so o toque na notificacao parava a insistencia. Agora abrir o app (e voltar pra
        tela) manda POST /api/push/visto; em segundo plano nao manda."""
        with nullcontext(self._pw) as p:
            browser = _Contextos(self._browser)
            try:
                ctx = browser.new_context(viewport={"width": 390, "height": 844})
                ctx.request.post(BASE_URL + "/login", data=json.dumps({"pin": PIN}),
                                 headers={"Content-Type": "application/json"})
                page = ctx.new_page()
                visto = []
                page.on("request", lambda r: visto.append(r.url) if _eh_visto(r) else None)
                erros = []
                page.on("pageerror", lambda exc: erros.append(str(exc)))
                page.goto(BASE_URL + "/")
                esperar_carga(page)
                # ao abrir saem 2 avisos (pageshow e o forcado de 1200 ms); com os 2 fora, `antes` nao muda sozinho
                while len(visto) < 2:
                    page.wait_for_event("request", _eh_visto, timeout=10000)
                self.assertGreaterEqual(len(visto), 1, "ao abrir o app")
                antes = len(visto)
                page.evaluate(_SEGUNDO_PLANO, True)  # vai pra segundo plano
                page.evaluate("_avisarQueViu(true)")  # forcado fura a pausa de 20 s: so o escondido segura
                page.wait_for_timeout(300)
                self.assertEqual(len(visto), antes, "escondido nao avisa")
                page.evaluate(_SEGUNDO_PLANO, False)  # de volta na tela: agora so a pausa segura
                page.evaluate("() => { window.dispatchEvent(new Event('focus')); }")
                page.wait_for_timeout(300)
                self.assertEqual(len(visto), antes, "20 s de pausa entre avisos (sem martelar o servidor)")
                self.assertEqual(erros, [], f"pageerror: {erros}")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
