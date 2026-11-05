"""Mede quanto tempo o app leva pra abrir com latência de celular (2026-11-05, leva "perfeição").

Não é teste da suíte (o nome não começa com test_): roda só quando chamado de propósito:

    .venv/Scripts/python.exe -m pytest tests/medir_abertura.py -q -s

Banco temporário vazio com PIN; Chromium sem service worker (igual ao WKWebView do app nativo, onde ele não roda)
e com a rede atrasada pelo DevTools (ida e volta de LATENCIA_MS, banda de 4G). Abre a página duas vezes - a
primeira (sem nada guardado) e a segunda (o que acontece todo dia) - com e sem `estaticos.py`, e imprime o tempo
até o app ficar pronto (`showTab` existe) e quantos pedidos foram à rede.
"""
import json
import os
import tempfile
import time
from pathlib import Path

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

LATENCIA_MS = 80
PORTA = int(os.environ.get("PORTA_MEDIR_ABERTURA", "8994"))
BASE = f"http://127.0.0.1:{PORTA}"
PIN = "246810"


def _rodada(navegador, nome):
    ctx = navegador.new_context(service_workers="block")
    try:
        r = ctx.request.post(BASE + "/login", data=json.dumps({"pin": PIN}), headers={"Content-Type": "application/json"})
        assert r.status == 200, r.text()
        page = ctx.new_page()
        cdp = ctx.new_cdp_session(page)
        cdp.send("Network.enable")
        cdp.send(
            "Network.emulateNetworkConditions",
            {"offline": False, "latency": LATENCIA_MS, "downloadThroughput": 2_500_000, "uploadThroughput": 750_000},
        )
        linhas = []
        for vez in ("1a abertura", "2a abertura"):
            pedidos = []
            ouvinte = lambda resp: pedidos.append(resp) if resp.url.startswith(BASE) else None  # noqa: E731
            page.on("response", ouvinte)
            t0 = time.perf_counter()
            page.goto(BASE + "/", wait_until="commit")
            page.wait_for_function("typeof showTab === 'function'", timeout=120000)
            pronto = time.perf_counter() - t0
            page.wait_for_load_state("load")
            page.remove_listener("response", ouvinte)
            rede = [p for p in pedidos if not p.from_service_worker and p.status != 0]
            do_cache = page.evaluate(
                "performance.getEntriesByType('resource').filter(e => e.name.includes('/static/') && e.transferSize === 0).length"
            )
            linhas.append(f"{nome:14} {vez}: pronto em {pronto * 1000:6.0f} ms; {len(rede):3d} respostas; {do_cache:3d} do cache local")
        return linhas
    finally:
        ctx.close()


def test_medir_abertura():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright não instalado")

    with tempfile.TemporaryDirectory() as pasta:
        db.DB_PATH = Path(pasta) / "painel.db"
        db.garantir_banco_nao_producao()
        import app as app_mod
        import estaticos
        from tests.playwright_helper import subir_servidor

        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()

        app = app_mod.app
        versionado = app.view_functions["static"]
        subir_servidor(app, PORTA)
        time.sleep(1.5)

        linhas = []
        with sync_playwright() as p:
            navegador = p.chromium.launch(headless=True)
            try:
                # sem estaticos.py: como era até a v101
                app.view_functions["static"] = app.send_static_file
                app.after_request_funcs[None].remove(estaticos._depois)
                linhas += _rodada(navegador, "antes")
                # com estaticos.py
                app.view_functions["static"] = versionado
                app.after_request_funcs[None].append(estaticos._depois)
                estaticos.limpar()
                linhas += _rodada(navegador, "depois")
            finally:
                navegador.close()
        print(f"\nlatência {LATENCIA_MS} ms por ida e volta, sem service worker (como o app nativo):")
        print("\n".join(linhas))
