# tests/_c4_screenshot.py - script pontual (nao faz parte da suite pytest) so
# pra tirar os prints antes/depois da faixa C4. Sobe o app num banco
# temporario, loga com o PIN de teste e usa o Chromium do venv (nunca
# `playwright install`) pra fotografar a aba Vida em 390x844.
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "dummy")
os.environ.setdefault("OPENAI_API_KEY", "dummy")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_tmp_dir.name) / "painel.db"
db.garantir_banco_nao_producao()

import app  # noqa: E402

PIN_TESTE = "123456"
PORT = 8971
OUT_DIR = Path(
    "/tmp/claude-0/-home-user-financeiro-construtora/"
    "17e4bd9b-4591-5043-a1c2-e3ff8a458d65/scratchpad/c4"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)


def preparar_banco():
    if db.DB_PATH.exists():
        db.DB_PATH.unlink()
    db.init_db()
    conn = db.get_db()
    auth.definir_pin(conn, PIN_TESTE, PIN_TESTE)
    conn.commit()
    conn.close()


def subir_servidor():
    app.app.run(port=PORT, use_reloader=False, threaded=True)


def main():
    preparar_banco()
    t = threading.Thread(target=subir_servidor, daemon=True)
    t.start()
    time.sleep(1.5)

    from playwright.sync_api import sync_playwright

    erros_pagina = []
    erros_console = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        page.on("pageerror", lambda exc: erros_pagina.append(str(exc)))
        page.on("console", lambda msg: erros_console.append(msg.text) if msg.type == "error" else None)

        base = f"http://127.0.0.1:{PORT}"
        r = context.request.post(f"{base}/login", data={"pin": PIN_TESTE})
        assert r.ok, r.text()

        page.goto(base)
        page.wait_for_timeout(600)

        # "Depois": aba Vida - grupos (estado inicial, so os cartoes)
        page.evaluate("window.showTab('vida')")
        page.wait_for_timeout(700)
        page.screenshot(path=str(OUT_DIR / "depois-01-grupos.png"))

        # Abre um grupo (Rotina) - lista de secoes aparece
        page.click('.vg-cartao[data-grupo="rotina"]')
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT_DIR / "depois-02-grupo-aberto.png"))

        # Abre uma secao dentro do grupo - so ela aparece, com "Voltar aos grupos"
        page.click('.vg-linha[data-id="vida-habitos"]')
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT_DIR / "depois-03-secao-aberta.png"))

        # Deep link: window.VidaGrupos.abrirSecao("secao-aviacao")
        page.evaluate("window.VidaGrupos.abrirSecao('secao-aviacao')")
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT_DIR / "depois-04-deeplink-aviacao.png"))

        browser.close()

    (OUT_DIR / "pageerrors.txt").write_text("\n".join(erros_pagina) or "(nenhum)", encoding="utf-8")
    print("pageerror (excecao JS nao tratada):", len(erros_pagina))
    for e in erros_pagina:
        print(" -", e)
    print("console.error (rede/fontes externas bloqueadas no sandbox - informativo, nao e pageerror):", len(erros_console))
    for e in erros_console:
        print(" -", e)


if __name__ == "__main__":
    main()
