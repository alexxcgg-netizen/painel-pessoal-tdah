"""Verificacao V2 (aba Painel) no Playwright headless 390x844.
Uso: PORTA=5140 python verificar.py

Loga, vai pra aba Painel, confere que as secoes recolhiveis (memoria) comecam FECHADAS
por padrao, abre e fecha uma pelo cabecalho, confere o card "Custo de IA", 0 erro de
console/rede (fora falhas de ambiente conhecidas), e tira 2 screenshots.
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:" + os.environ.get("PORTA", "5140")
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
    page.on(
        "response", lambda resp: falhas_rede.append((resp.status, resp.url)) if resp.status >= 400 else None
    )
    page.on("requestfailed", lambda req: falhas_rede.append(("falhou", req.url)))
    page.goto(BASE + "/")
    page.wait_for_load_state("networkidle")
    time.sleep(1.0)

    # vai pra aba Painel
    page.click(".tab-btn[data-tab='painel']")
    page.wait_for_timeout(600)

    memoria_aberto_inicial = page.eval_on_selector(
        "[data-secao-id='painel-memoria-rotina-planos']", "el => el.dataset.aberto"
    )
    fora_aberto_inicial = page.eval_on_selector(
        "[data-secao-id='painel-memoria-fora-do-painel']", "el => el.dataset.aberto"
    )
    aria_inicial = page.eval_on_selector(
        "[data-secao-id='painel-memoria-rotina-planos'] .secao-cabecalho", "el => el.getAttribute('aria-expanded')"
    )

    time.sleep(0.3)
    page.screenshot(path=os.path.join(AQUI, "v2-painel-fechado.png"), animations="disabled")

    # abre a secao "O que eu lembro sobre voce" pelo cabecalho (clique real)
    page.click("[data-secao-id='painel-memoria-rotina-planos'] .secao-cabecalho")
    page.wait_for_timeout(500)
    aberto_depois = page.eval_on_selector(
        "[data-secao-id='painel-memoria-rotina-planos']", "el => el.dataset.aberto"
    )
    aria_depois = page.eval_on_selector(
        "[data-secao-id='painel-memoria-rotina-planos'] .secao-cabecalho", "el => el.getAttribute('aria-expanded')"
    )

    # fecha de novo (abre e fecha, pedido do prompt)
    page.click("[data-secao-id='painel-memoria-rotina-planos'] .secao-cabecalho")
    page.wait_for_timeout(500)
    fechado_de_novo = page.eval_on_selector(
        "[data-secao-id='painel-memoria-rotina-planos']", "el => el.dataset.aberto"
    )

    # card de custo de IA
    custo_ia_visivel = page.eval_on_selector(
        "#custo-ia-v2-box", "el => !!el && getComputedStyle(el).display !== 'none'"
    )
    custo_ia_gasto = page.eval_on_selector("#custo-ia-v2-gasto", "el => el && el.textContent")
    custo_ia_tabela_linhas = page.eval_on_selector_all("#custo-ia-v2-tabela-corpo tr", "els => els.length")
    custo_ia_grafico_svg = page.eval_on_selector("#custo-ia-v2-grafico svg", "el => !!el")

    page.wait_for_timeout(300)
    page.screenshot(path=os.path.join(AQUI, "v2-painel-custo-ia.png"), animations="disabled")

    # exporta CSV: confere que o link aponta pro endpoint certo e responde 200
    href_exportar = page.eval_on_selector("#custo-ia-v2-exportar", "el => el.getAttribute('href')")
    resp_csv = ctx.request.get(BASE + href_exportar)
    csv_ok = resp_csv.status == 200 and "text/csv" in (resp_csv.headers.get("content-type") or "")

    b.close()

AMBIENTE = ("fonts.googleapis.com", "fonts.gstatic.com", "/api/summary/today")
falhas_ambiente = [f for f in falhas_rede if any(a in f[1] for a in AMBIENTE)]
falhas_rede = [f for f in falhas_rede if f not in falhas_ambiente]
erros_ambiente = ("ERR_CERT_AUTHORITY_INVALID", "502 (BAD GATEWAY)")
erros = [e for e in erros if not any(a in e[1] for a in erros_ambiente)]

memoria_fechada_por_padrao = memoria_aberto_inicial == "false" and fora_aberto_inicial == "false"
abre_fecha_ok = (
    aria_inicial == "false" and aberto_depois == "true" and aria_depois == "true" and fechado_de_novo == "false"
)
custo_ia_ok = bool(custo_ia_visivel) and custo_ia_gasto and "R$" in custo_ia_gasto and custo_ia_tabela_linhas >= 1

res = {
    "erros_console": erros,
    "falhas_rede": falhas_rede,
    "falhas_ambiente_ignoradas": falhas_ambiente,
    "memoria_aberto_inicial": memoria_aberto_inicial,
    "fora_aberto_inicial": fora_aberto_inicial,
    "memoria_fechada_por_padrao": memoria_fechada_por_padrao,
    "aria_inicial": aria_inicial,
    "aberto_depois": aberto_depois,
    "aria_depois": aria_depois,
    "fechado_de_novo": fechado_de_novo,
    "abre_fecha_ok": abre_fecha_ok,
    "custo_ia_visivel": custo_ia_visivel,
    "custo_ia_gasto": custo_ia_gasto,
    "custo_ia_tabela_linhas": custo_ia_tabela_linhas,
    "custo_ia_grafico_svg": custo_ia_grafico_svg,
    "custo_ia_ok": custo_ia_ok,
    "href_exportar": href_exportar,
    "csv_ok": csv_ok,
}
json.dump(res, open(os.path.join(AQUI, "v2-painel-resultado.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps(res, ensure_ascii=False, indent=1))

ok = not erros and not falhas_rede and memoria_fechada_por_padrao and abre_fecha_ok and custo_ia_ok and csv_ok
print("OK" if ok else "FALHOU")
sys.exit(0 if ok else 1)
