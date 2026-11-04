# tests/test_rede_fechada.py - bloqueio do tests/conftest.py: teste nenhum sai da maquina. Nome de
# fora falha na hora, endereco numerico resolve (as defesas de SSRF dependem disso) e localhost segue
# livre. O Chromium e outro processo: quem fecha ele e o tests/playwright_helper.py.
import errno
import socket
import threading
import time
import unittest

import requests

import leitura
from tests import playwright_helper  # noqa: F401 - e ele que fecha o Chromium

try:
    from playwright.sync_api import Error as ErroPlaywright
    from playwright.sync_api import sync_playwright

    _PLAYWRIGHT_OK = True
except ImportError:
    _PLAYWRIGHT_OK = False

# o bloqueio mora no conftest, que `python -m unittest` nao carrega: la esses testes iriam pra rede
_FECHADA = socket.socket.connect.__name__ == "_connect_so_local"


@unittest.skipUnless(_FECHADA, "precisa do conftest: rodar com pytest")
class RedeFechadaTestCase(unittest.TestCase):
    def test_nome_de_fora_nao_resolve(self):
        with self.assertRaises(socket.gaierror):
            socket.getaddrinfo("api.telegram.org", 443)
        with self.assertRaises(socket.gaierror):
            socket.gethostbyname("api.telegram.org")

    def test_nome_que_parece_loopback_nao_engana(self):
        with self.assertRaises(socket.gaierror):
            socket.getaddrinfo("127.exemplo.com", 443)

    def test_endereco_numerico_resolve_sem_rede(self):
        self.assertEqual(socket.getaddrinfo("169.254.169.254", 80)[0][4][0], "169.254.169.254")

    def test_conexao_pra_fora_e_recusada(self):
        with socket.socket() as s, self.assertRaises(ConnectionRefusedError):
            s.connect(("93.184.216.34", 80))
        with socket.socket() as s:
            self.assertEqual(s.connect_ex(("93.184.216.34", 80)), errno.ECONNREFUSED)

    def test_requests_falha_na_hora_com_o_erro_de_sem_internet(self):
        inicio = time.monotonic()
        with self.assertRaises(requests.ConnectionError):
            requests.get("https://api.telegram.org/bot/getMe", timeout=30)
        self.assertLess(time.monotonic() - inicio, 2)

    def test_localhost_continua_livre(self):
        with socket.socket() as servidor:
            servidor.bind(("127.0.0.1", 0))
            servidor.listen(1)
            aceita = threading.Thread(target=lambda: servidor.accept()[0].close(), daemon=True)
            aceita.start()
            with socket.create_connection(servidor.getsockname(), timeout=5):
                pass
            aceita.join(5)

    def test_defesa_de_ssrf_barra_pelo_endereco_e_nao_por_erro_de_nome(self):
        with self.assertRaises(leitura.LinkInvalido) as erro:
            leitura.validar_url("http://169.254.169.254/latest/meta-data")
        self.assertIn("público", str(erro.exception))


@unittest.skipUnless(_PLAYWRIGHT_OK, "playwright nao instalado")
class ChromiumFechadoTestCase(unittest.TestCase):
    def test_navegador_nao_alcanca_nome_de_fora(self):
        with sync_playwright() as p:
            navegador = p.chromium.launch()
            try:
                pagina = navegador.new_page()
                with self.assertRaises(ErroPlaywright) as erro:
                    pagina.goto("https://fonts.googleapis.com/css2?family=Inter")
                self.assertIn("ERR_NAME_NOT_RESOLVED", str(erro.exception))
            finally:
                navegador.close()


if __name__ == "__main__":
    unittest.main()
