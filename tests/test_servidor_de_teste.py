"""Servidor dos testes de navegador: conexao reaproveitada, nao uma nova por pedido.

Com uma conexao por pedido a fila esgotava as portas de saida do Windows e script deixava de
carregar ao acaso. Ver `subir_servidor` em tests/playwright_helper.py.
"""
import http.client
import re
import socket
import sys
import time
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from tests.playwright_helper import subir_servidor  # noqa: E402

_SERVIDOR_DO_FLASK = re.compile(r"\.run\(\s*host=|app\.run\(")


def _app(environ, start_response):
    start_response("200 OK", [("Content-Type", "text/plain"), ("Content-Length", "2")])
    return [b"ok"]


class ServidorDeTesteTestCase(unittest.TestCase):
    def _esperar_subir(self, porta):
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", porta), timeout=1).close()
                return
            except OSError:
                time.sleep(0.1)
        self.fail("servidor nao subiu")

    def test_dois_pedidos_usam_a_mesma_conexao(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            porta = s.getsockname()[1]
        subir_servidor(_app, porta)
        self._esperar_subir(porta)
        conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=5)
        self.addCleanup(conexao.close)
        conexao.request("GET", "/")
        primeira = conexao.getresponse()
        primeira.read()
        self.assertFalse(primeira.will_close, "servidor fechou a conexao depois do pedido")
        tomada = conexao.sock
        conexao.request("GET", "/")
        conexao.getresponse().read()
        self.assertIs(conexao.sock, tomada)

    def test_teste_nenhum_volta_pro_servidor_do_flask(self):
        voltaram = [
            t.name for t in (RAIZ / "tests").glob("test_*.py")
            if t.name != Path(__file__).name and _SERVIDOR_DO_FLASK.search(t.read_text(encoding="utf-8"))
        ]
        self.assertEqual(voltaram, [])


if __name__ == "__main__":
    unittest.main()
