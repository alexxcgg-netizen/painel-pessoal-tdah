"""Verificacao v6-financas no Playwright headless 390x844 (abas Gastos,
Bancos, Construtora - historia final da faixa, docs/agentes/fase7-regras-faixa.md).
Uso: PORTA=5194 python verificar.py
Salva gastos.png e construtora.png nesta pasta (2 screenshots no total, pedido
do prompt da faixa), confere erro de console/pageerror e falha de rede (fora
as falhas de ambiente conhecidas) nas 3 abas.
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:" + os.environ.get("PORTA", "5194")
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

erros, falhas_rede = [], []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, headless=True)
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    r = ctx.request.post(
        BASE + "/configurar-pin",
        data=json.dumps({"pin": "135790", "confirmacao": "135790"}),
        headers={"Content-Type": "application/json"},
    )
    if r.status != 200:
        r = ctx.request.post(
            BASE + "/login", data=json.dumps({"pin": "135790"}), headers={"Content-Type": "application/json"}
        )
    assert r.status == 200, r.text()
    page = ctx.new_page()
    page.on("console", lambda m: erros.append(("console." + m.type, m.text)) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(("pageerror", str(e))))
    page.on("response", lambda resp: falhas_rede.append((resp.status, resp.url)) if resp.status >= 400 else None)
    page.on("requestfailed", lambda req: falhas_rede.append(("falhou", req.url)))
    page.goto(BASE + "/")
    page.wait_for_load_state("networkidle")
    time.sleep(1.0)

    # ---- Gastos (gastos/gastos, gastos/assinaturas, gastos/metas) ----
    page.click("button.tab-btn[data-tab='gastos']")
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    time.sleep(1.0)
    # Confere que a secao nova esta la e que os 2 botoes de adicionar abrem o
    # bottom sheet (fallback local, ja que static/js/ui/bottom-sheet.js segue
    # vazio nesta integracao - ver APRENDIZADOS.md #3/#4), com ESC fechando.
    assert page.locator("#assinaturas-financas-box").count() == 1, "secao assinaturas nao renderizou"
    page.click("#btn-nova-assinatura")
    time.sleep(0.3)
    sheet_aberto = page.evaluate("document.getElementById('sheet-nova-assinatura').hidden === false")
    assert sheet_aberto, "bottom sheet de nova assinatura nao abriu"
    page.keyboard.press("Escape")
    time.sleep(0.3)
    sheet_fechado = page.evaluate("document.getElementById('sheet-nova-assinatura').hidden === true")
    assert sheet_fechado, "ESC nao fechou o bottom sheet"

    # Fluxo completo de verdade (formulario -> POST -> lista atualizada), pra
    # nao so ver telas vazias no screenshot: 1 assinatura + 1 parcela.
    page.click("#btn-nova-assinatura")
    page.fill("#assinatura-nome", "Netflix")
    page.fill("#assinatura-valor", "39.90")
    page.fill("#assinatura-dia", "28")  # dia futuro no mes (hoje e 24) - conta no total deste mes
    page.fill("#assinatura-cartao", "nubank")
    page.click("#assinatura-salvar-btn")
    page.wait_for_selector("#lista-assinaturas-ativas .lista-item", timeout=5000)

    page.click("#btn-nova-parcela")
    page.fill("#parcela-descricao", "Geladeira")
    page.fill("#parcela-n", "10")
    page.fill("#parcela-valor-total", "3200")
    page.fill("#parcela-cartao", "nubank")
    page.click("#parcela-salvar-btn")
    page.wait_for_selector("#lista-parcelas .lista-item", timeout=5000)
    time.sleep(0.5)

    assert page.locator("#comprometido-box").is_visible(), "card de comprometido nao apareceu com dado real"
    page.screenshot(path=os.path.join(AQUI, "gastos.png"), animations="disabled")

    # ---- Bancos (bancos/bancos, bancos/ofx) - sem screenshot (limite de 2),
    # so confere console/rede limpos. ----
    page.click("button.tab-btn[data-tab='bancos']")
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    time.sleep(1.0)
    assert page.locator("#lista-bancos").count() == 1, "lista de bancos nao renderizou"

    # ---- Construtora (construtora/construtora, construtora/contas-a-pagar) ----
    page.click("button.tab-btn[data-tab='construtora']")
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    time.sleep(1.0)
    assert page.locator("#construtora-card, #construtora-info").count() >= 1, "card/info da construtora nao renderizou"
    page.screenshot(path=os.path.join(AQUI, "construtora.png"), animations="disabled")

    b.close()

# Falhas de ambiente conhecidas (sandbox sem internet confiavel e IA com chave
# falsa) - mesma lista de scripts/ralph-v0a-tokens/verificar.py:
AMBIENTE = ("fonts.googleapis.com", "fonts.gstatic.com", "/api/summary/today")
falhas_ambiente = [f for f in falhas_rede if any(a in f[1] for a in AMBIENTE)]
falhas_rede = [f for f in falhas_rede if f not in falhas_ambiente]
erros = [e for e in erros if not e[1].startswith("Failed to load resource")] if not falhas_rede else erros

res = {"erros_console": erros, "falhas_rede": falhas_rede, "falhas_ambiente_ignoradas": falhas_ambiente}
json.dump(res, open(os.path.join(AQUI, "resultado.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps(res, ensure_ascii=False, indent=1))
ok = not erros and not falhas_rede
print("OK" if ok else "FALHOU")
sys.exit(0 if ok else 1)
