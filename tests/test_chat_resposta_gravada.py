# tests/test_chat_resposta_gravada.py - bug do iPhone (2026-11-05): mandar uma mensagem no chat e sair
# do app antes da resposta. O iOS congela/derruba a conexao; o servidor termina e GRAVA a resposta, mas
# ao voltar o app ficava nos pontinhos (ou em "a conexao caiu") e a resposta so aparecia depois de
# reabrir. static/js/secoes/hoje/chat.js agora busca em /api/chat/historico o que ficou gravado.
#
# Aqui o stream e historico sao simulados com page.route (a IA de verdade nao roda nos testes); o
# que se confere e o comportamento do app: mostra a resposta gravada, nao reenvia a mensagem
# (reenviar duplicaria) e, se nada foi gravado, avisa em vez de ficar parado. Porta propria (8883).
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
PORTA = int(os.environ.get("PORTA_TESTE_RESPOSTA_GRAVADA", "8883"))
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

TEXTO = "O date é no sábado, quero saber a que horas chego em casa"
RESPOSTA = "Chegas em casa por volta das 20h38."

# troca document.hidden/visibilityState e dispara o evento, como o iOS faz ao sair/voltar
_SEGUNDO_PLANO = """(escondido) => {
  Object.defineProperty(document, "hidden", { configurable: true, get: () => escondido });
  Object.defineProperty(document, "visibilityState", { configurable: true, get: () => (escondido ? "hidden" : "visible") });
  document.dispatchEvent(new Event("visibilitychange"));
}"""


def _historico(com_resposta):
    itens = [{"papel": "user", "texto": TEXTO, "cards": []}]
    if com_resposta:
        itens.append({"papel": "assistant", "texto": RESPOSTA, "cards": []})
    return json.dumps(itens)


@unittest.skipUnless(_PLAYWRIGHT_OK, "playwright nao instalado")
@unittest.skipUnless(_pronto, "servidor de teste nao respondeu")
class ChatRespostaGravadaTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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

    def _abrir_chat(self, stream, historico_com_resposta, pedidos):
        ctx = self._browser.new_context(viewport={"width": 390, "height": 844})
        ctx.add_init_script(CONTAR_FETCH)
        self.addCleanup(ctx.close)
        r = ctx.request.post(BASE_URL + "/login", data=json.dumps({"pin": PIN}), headers={"Content-Type": "application/json"})
        self.assertEqual(r.status, 200, r.text())
        page = ctx.new_page()
        self.erros = []
        page.on("pageerror", lambda exc: self.erros.append(str(exc)))
        page.on("request", lambda req: pedidos.append(f"{req.method} {req.url}"))
        page.goto(BASE_URL + "/")
        esperar_carga(page)
        # so depois de carregar: o historico "de antes" (vazio) precisa passar sem ser trocado
        page.route("**/api/chat/stream", stream)
        page.route(
            "**/api/chat/historico",
            lambda route: route.fulfill(status=200, content_type="application/json", body=_historico(historico_com_resposta())),
        )
        abrir_tela(page, "assistente")
        page.wait_for_selector("#chat-input", state="visible")
        return page

    def _mandar(self, page):
        page.fill("#chat-input", TEXTO)
        page.click("#chat-send")

    def test_stream_que_acaba_sem_fim_mostra_a_resposta_gravada_sem_reenviar(self):
        pedidos = []
        gravada = {"v": False}

        def stream(route):
            # o servidor recebeu, comecou a pensar e a conexao foi embora antes do evento "fim"
            gravada["v"] = True
            route.fulfill(status=200, content_type="text/event-stream", body='event: passo\ndata: {"texto":"Calculando o trajeto"}\n\n')

        page = self._abrir_chat(stream, lambda: gravada["v"], pedidos)
        self._mandar(page)
        page.wait_for_function(
            "(t) => [...document.querySelectorAll('#chat-mensagens .chat-bolha')].some((b) => b.textContent.includes(t))",
            arg=RESPOSTA,
            timeout=15000,
        )
        texto_tela = page.inner_text("#chat-mensagens")
        self.assertNotIn("A conexão caiu", texto_tela)
        self.assertNotIn("incompleta", texto_tela)
        self.assertEqual([p for p in pedidos if p.startswith("POST") and p.endswith("/api/chat")], [], "reenviou a mensagem")
        self.assertEqual(page.locator("#chat-mensagens .chat-digitando").count(), 0, "pontinhos ficaram na tela")
        self.assertEqual(self.erros, [], f"pageerror: {self.erros}")

    def test_stream_congelado_ao_sair_do_app_busca_o_gravado_na_volta(self):
        pedidos = []
        gravada = {"v": False}

        def stream(route):
            gravada["v"] = True  # chegou no servidor; a conexao congelou (nunca responde)

        page = self._abrir_chat(stream, lambda: gravada["v"], pedidos)
        self._mandar(page)
        # espera o pedido do stream sair (depois do GPS) e so entao "sai do app"
        for _ in range(100):
            if gravada["v"]:
                break
            page.wait_for_timeout(100)
        self.assertTrue(gravada["v"], "o stream nem foi pedido")
        page.evaluate(_SEGUNDO_PLANO, True)
        page.wait_for_timeout(300)
        page.evaluate(_SEGUNDO_PLANO, False)
        # a volta espera ~2,5 s sem dado novo, aborta e busca o gravado
        page.wait_for_function(
            "(t) => [...document.querySelectorAll('#chat-mensagens .chat-bolha')].some((b) => b.textContent.includes(t))",
            arg=RESPOSTA,
            timeout=20000,
        )
        self.assertEqual([p for p in pedidos if p.startswith("POST") and p.endswith("/api/chat")], [], "reenviou a mensagem")
        self.assertEqual(self.erros, [], f"pageerror: {self.erros}")

    def test_nada_gravado_avisa_em_vez_de_ficar_parado(self):
        pedidos = []
        page = self._abrir_chat(
            lambda route: route.fulfill(status=200, content_type="text/event-stream", body='event: passo\ndata: {"texto":"x"}\n\n'),
            lambda: False,
            pedidos,
        )
        achou = page.evaluate("() => recuperarRespostaGravada(%s, 2500)" % json.dumps(TEXTO))
        self.assertFalse(achou)
        self.assertEqual(self.erros, [], f"pageerror: {self.erros}")

    def test_resposta_gravada_so_conta_depois_da_mensagem_certa(self):
        """Resposta de OUTRA pergunta (mais antiga) no historico nao pode ser tomada pela de agora."""
        pedidos = []
        page = self._abrir_chat(
            lambda route: route.fulfill(status=200, content_type="text/event-stream", body=""),
            lambda: False,
            pedidos,
        )
        page.unroute("**/api/chat/historico")
        antigo = json.dumps([
            {"papel": "user", "texto": "outra pergunta de antes", "cards": []},
            {"papel": "assistant", "texto": "resposta antiga", "cards": []},
            {"papel": "user", "texto": TEXTO, "cards": []},
        ])
        page.route("**/api/chat/historico", lambda route: route.fulfill(status=200, content_type="application/json", body=antigo))
        achou = page.evaluate("() => recuperarRespostaGravada(%s, 2200)" % json.dumps(TEXTO))
        self.assertFalse(achou, "tomou a resposta da pergunta antiga")


if __name__ == "__main__":
    unittest.main()
