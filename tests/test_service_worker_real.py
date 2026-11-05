# tests/test_service_worker_real.py - O service worker de verdade instala no Chromium.
# Todo outro teste de navegador roda sem ele (ver `_contexto_sem_sw` em tests/playwright_helper.py):
# este e o que confere que a instalacao funciona. Arquivo faltando em ASSETS derruba o `addAll`
# inteiro e o app perde o modo offline sem nenhum erro na tela.
import json
import os
import re
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app as app_module  # noqa: E402

PIN = "123456"
PORTA = int(os.environ.get("PORTA_TESTE_SW", "8990"))
BASE_URL = f"http://127.0.0.1:{PORTA}"

db.init_db()
_conn = db.get_db()
auth.definir_pin(_conn, PIN, PIN)
_conn.commit()
_conn.close()

from tests.playwright_helper import get_chrome_path, subir_servidor  # noqa: E402

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

_CHROME = get_chrome_path()
_SW = (Path(__file__).resolve().parent.parent / "static" / "service-worker.js").read_text(encoding="utf-8")
_ASSETS = set(re.findall(r'"(/[^"]*)"', re.search(r"ASSETS\s*=\s*\[(.*?)\]", _SW, re.S).group(1)))


@unittest.skipUnless(_PLAYWRIGHT_OK, "playwright nao instalado")
@unittest.skipUnless(_pronto, "servidor de teste nao respondeu")
class ServiceWorkerRealTestCase(unittest.TestCase):
    def test_instala_assume_a_pagina_e_guarda_todos_os_arquivos(self):
        kwargs = {"headless": True}
        if _CHROME is not None and Path(_CHROME).exists():
            kwargs["executable_path"] = _CHROME
        with sync_playwright() as p:
            browser = p.chromium.launch(**kwargs)
            try:
                ctx = browser.new_context(service_workers="allow")
                r = ctx.request.post(BASE_URL + "/login", data=json.dumps({"pin": PIN}), headers={"Content-Type": "application/json"})
                self.assertEqual(r.status, 200, r.text())
                page = ctx.new_page()
                page.goto(BASE_URL + "/")
                page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=30000)
                guardados = page.evaluate(
                    "async () => (await (await caches.open((await caches.keys())[0])).keys()).map((r) => new URL(r.url).pathname)"
                )
                self.assertEqual(sorted(_ASSETS - set(guardados)), [])
                # com ele no comando todo /static/ passa pelo fetch dele: um erro ali e app que nao abre.
                # So o que e do painel: a rede dos testes e fechada e a fonte do Google falha sempre.
                falhas = []
                # ERR_ABORTED = pedido da pagina anterior cortado pelo reload, nao falha do SW (que seria ERR_FAILED)
                page.on(
                    "requestfailed",
                    lambda pedido: falhas.append(f"{pedido.url} {pedido.failure}")
                    if pedido.url.startswith(BASE_URL) and pedido.failure != "net::ERR_ABORTED"
                    else None,
                )
                # v102 (estaticos.py): CSS/JS com ?v=<impressao> saem da copia guardada, sem ir a rede
                versionados = []
                page.on(
                    "response",
                    lambda r: versionados.append(r) if r.url.startswith(BASE_URL + "/static/") and "?v=" in r.url else None,
                )
                page.reload()
                page.wait_for_function("typeof showTab === 'function'")
                self.assertEqual(falhas, [])
                self.assertGreater(len(versionados), 150)
                da_rede = [r.url for r in versionados if not r.from_service_worker]
                self.assertEqual(da_rede, [], "arquivo versionado foi a rede com a copia certa guardada")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
