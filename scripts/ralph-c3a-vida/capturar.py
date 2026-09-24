"""Verificacao final da C3a no Playwright headless 390x844 (banco de teste, rede travada):
confere 0 erro de console do app e 0 saida de rede, e tira as 2 capturas finais (nao versionadas,
ver .gitignore desta pasta):
  c3a-vida-secoes.png  - viewport na aba Vida (Garantia + Manutencao com itens)
  c3a-vida-sheet.png   - sheet "Adicionar produto" aberto

Uso: PORTA=5131 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-c3a-vida/capturar.py
"""
import sys
import time

from playwright.sync_api import sync_playwright

import comum


def main():
    srv = comum.subir_servidor()
    erros, rede = [], []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=comum.CHROME, headless=True)
            ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                service_workers="block")
            comum.logar(ctx)
            comum.semear(ctx)
            page = ctx.new_page()
            comum.proteger_rede(page)
            comum.ligar_coleta(page, erros, rede)
            comum.dubles_leitura(page)
            comum.abrir_vida(page)
            time.sleep(1.2)
            page.evaluate("""() => { const el = document.querySelector('[data-secao-id="vida-garantia"]');
                window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 12); }""")
            time.sleep(0.6)
            page.screenshot(path=f"{comum.AQUI}/c3a-vida-secoes.png")
            page.click("#garantia-abrir-btn")
            page.wait_for_selector("#sheet-garantia.bottom-sheet--aberto", state="attached")
            time.sleep(0.5)
            page.fill("#garantia-produto", "Maquina de lavar")
            page.screenshot(path=f"{comum.AQUI}/c3a-vida-sheet.png")
            page.keyboard.press("Escape")
            time.sleep(0.4)
            b.close()
    finally:
        srv.terminate()
    app = comum.filtrar_erros(erros)
    saidas = comum.saidas_bloqueadas()
    print("erros de console do app:", len(app), app[:5])
    print("tentativas de saida de rede do servidor:", len(saidas))
    sys.exit(1 if app or saidas else 0)


if __name__ == "__main__":
    main()
