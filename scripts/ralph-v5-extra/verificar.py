"""Verificacao final da faixa V5-extra (viagens, lugares, cotacoes, aviacao) no Playwright
headless 390x844.
Uso: PORTA=5199 python verificar.py

Cobre as 3 areas pedidas no prompt da faixa:
  - Vida > Viagens/Lugares: abre o bottom-sheet real (.btn-adicionar), cria uma viagem e um
    lugar de verdade (POST real no banco de teste), confere que a lista atualiza e o sheet
    fecha sozinho.
  - Aviacao: as 4 secoes (horas-voadas, registrar-voo, proximos-voos, metar) presentes e sem
    erro; registra um voo de verdade.
  - Construtora > Cotacoes: abre o bottom-sheet, cria uma cotacao, adiciona 2 fornecedores
    (dispara o grafico de comparacao) - conferido por asserção, sem screenshot dedicado (o
    prompt da faixa pede 2 screenshots no total, nao por tela).
Zero erro de console/pageerror (fora as falhas de ambiente conhecidas, mesma lista de
scripts/ralph-v0c-secoes/verificar.py). 2 screenshots em scripts/ralph-v5-extra/.
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:" + os.environ.get("PORTA", "5199")
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
PIN = "135790"


def log(*a):
    print(*a, flush=True)


erros, falhas_rede = [], []
checagens = {}

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, headless=True)
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    r = ctx.request.post(BASE + "/configurar-pin", data=json.dumps({"pin": PIN, "confirmacao": PIN}),
                          headers={"Content-Type": "application/json"})
    if r.status != 200:
        r = ctx.request.post(BASE + "/login", data=json.dumps({"pin": PIN}),
                              headers={"Content-Type": "application/json"})
    assert r.status == 200, r.text()

    page = ctx.new_page()
    page.on("console", lambda m: erros.append(("console." + m.type, m.text)) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(("pageerror", str(e))))
    page.on("response", lambda resp: falhas_rede.append((resp.status, resp.url))
            if resp.status >= 400 else None)
    page.on("requestfailed", lambda req: falhas_rede.append(("falhou", req.url)))
    page.goto(BASE + "/")
    page.wait_for_load_state("networkidle")
    time.sleep(1.0)

    # ---------------- Vida > Viagens/Lugares ----------------
    page.click('.tab-btn[data-tab="vida"]')
    page.wait_for_selector("#tab-vida:not([hidden])")
    time.sleep(0.6)

    page.click("#viagem-abrir-btn")
    time.sleep(0.4)
    checagens["viagem_sheet_visivel_apos_abrir"] = page.eval_on_selector(
        "#viagem-sheet", "el => !el.hidden"
    )
    page.fill("#viagem-nova-destino", "Florianopolis")
    page.fill("#viagem-nova-ida", "2026-12-20")
    page.click("#viagem-nova-btn")
    page.wait_for_function("document.querySelector('#viagem-sheet').hidden === true", timeout=5000)
    try:
        page.wait_for_selector("#lista-viagens >> text=Florianopolis", timeout=8000)
        checagens["viagem_criada_na_lista"] = True
    except Exception:
        checagens["viagem_criada_na_lista"] = False

    page.click("#lugar-abrir-btn")
    time.sleep(0.4)
    checagens["lugar_sheet_visivel_apos_abrir"] = page.eval_on_selector(
        "#lugar-sheet", "el => !el.hidden"
    )
    page.fill("#lugar-nome", "Cafe Ambrosia")
    page.fill("#lugar-cidade", "Blumenau")
    page.click("#lugar-btn")
    page.wait_for_function("document.querySelector('#lugar-sheet').hidden === true", timeout=5000)
    try:
        page.wait_for_selector("#lista-lugares >> text=Cafe Ambrosia", timeout=8000)
        checagens["lugar_criado_na_lista"] = True
    except Exception:
        checagens["lugar_criado_na_lista"] = False

    # rola ate a secao Viagens (a lista da aba Vida e longa - sem isso o
    # screenshot pega o fim da pagina, nao Viagens/Lugares).
    page.eval_on_selector("#viagem-abrir-btn", "el => el.scrollIntoView({block: 'start'})")
    time.sleep(0.4)
    page.screenshot(path=os.path.join(AQUI, "v5-extra-vida-viagens-lugares.png"), animations="disabled")

    # ---------------- Aviacao ----------------
    page.click('.tab-btn[data-tab="aviacao"]')
    page.wait_for_selector("#tab-aviacao:not([hidden])")
    time.sleep(0.6)

    for sel in ("#voo-form", "#lista-voos", "#metar-form", "#voos-stats-grid"):
        checagens[f"aviacao_presente_{sel}"] = page.eval_on_selector(sel, "el => !!el") if page.query_selector(sel) else False

    page.fill("#voo-data", "20/12/2026")
    page.fill("#voo-destino", "SBBI")
    with page.expect_response(lambda r2: r2.url.endswith("/api/voos") and r2.request.method == "POST"):
        page.click("#voo-btn")
    # apos o POST, loadVoosResumo() recarrega a lista E busca previsao do
    # tempo pro voo (clima.previsao_para_cidade_e_data, timeout de 8s por
    # chamada HTTP no servidor) - no sandbox sem internet confiavel essa
    # chamada pode esgotar o timeout antes de desistir, entao o texto so
    # aparece bem depois do clique; timeout generoso de proposito.
    try:
        page.wait_for_selector("#lista-voos >> text=SBBI", timeout=25000)
        checagens["voo_registrado_na_lista"] = True
    except Exception:
        checagens["voo_registrado_na_lista"] = False

    time.sleep(0.3)
    page.screenshot(path=os.path.join(AQUI, "v5-extra-aviacao.png"), animations="disabled")

    # ---------------- Construtora > Cotacoes (so asserção, sem screenshot) ----------------
    page.click('.tab-btn[data-tab="construtora"]')
    page.wait_for_selector("#tab-construtora:not([hidden])")
    time.sleep(0.6)

    page.click("#cotacao-abrir-btn")
    time.sleep(0.4)
    checagens["cotacao_sheet_visivel_apos_abrir"] = page.eval_on_selector(
        "#cotacao-sheet", "el => !el.hidden"
    )
    page.fill("#cotacao-titulo", "Portas")
    page.click("#cotacao-btn")
    page.wait_for_function("document.querySelector('#cotacao-sheet').hidden === true", timeout=5000)
    try:
        page.wait_for_selector("#lista-cotacoes >> text=Portas", timeout=8000)
        checagens["cotacao_criada_na_lista"] = True
    except Exception:
        checagens["cotacao_criada_na_lista"] = False

    # Comportamento ja existente de criarItemCotacao/loadCotacoes (nao mexido
    # nesta faixa): ao adicionar um fornecedor, loadCotacoes() reconstroi a
    # <li> inteira (fecha o detalhe de novo, carregado=false) - por isso
    # reabre o cabecalho a cada fornecedor, nao so na primeira vez.
    def abrir_detalhe_cotacao():
        page.click("#lista-cotacoes .cotacao-cabecalho")
        page.wait_for_selector(".cotacao-add-form input[placeholder='Fornecedor']", timeout=10000)

    abrir_detalhe_cotacao()
    page.fill(".cotacao-add-form input[placeholder='Fornecedor']", "Fornecedor A")
    page.fill(".cotacao-add-form input[placeholder='Valor R$']", "5000")
    with page.expect_response(lambda r2: r2.url.endswith("/itens") and r2.request.method == "POST"):
        page.click(".cotacao-add-form button[type='submit']")
    time.sleep(0.8)

    abrir_detalhe_cotacao()
    page.fill(".cotacao-add-form input[placeholder='Fornecedor']", "Fornecedor B")
    page.fill(".cotacao-add-form input[placeholder='Valor R$']", "4200")
    with page.expect_response(lambda r2: r2.url.endswith("/itens") and r2.request.method == "POST"):
        page.click(".cotacao-add-form button[type='submit']")
    time.sleep(0.8)

    abrir_detalhe_cotacao()
    page.wait_for_selector(".cotacao-grafico", timeout=10000)
    checagens["grafico_comparacao_renderizado"] = bool(page.query_selector(".cotacao-grafico"))

    b.close()

# Falhas de ambiente conhecidas (sandbox sem internet confiavel) - mesma lista de
# scripts/ralph-v0c-secoes/verificar.py.
AMBIENTE = ("fonts.googleapis.com", "fonts.gstatic.com", "/api/summary/today",
            "aviationweather.gov", "windy.com", "leaflet", "openstreetmap")
falhas_ambiente = [f for f in falhas_rede if any(a in f[1] for a in AMBIENTE)]
falhas_rede = [f for f in falhas_rede if f not in falhas_ambiente]
erros = [e for e in erros if not e[1].startswith("Failed to load resource")] if not falhas_rede else erros

res = {
    "erros_console": erros,
    "falhas_rede": falhas_rede,
    "falhas_ambiente_ignoradas": falhas_ambiente,
    "checagens": checagens,
}
json.dump(res, open(os.path.join(AQUI, "v5-extra-resultado.json"), "w"), indent=1, ensure_ascii=False)
log(json.dumps(res, ensure_ascii=False, indent=1))

ok = not erros and not falhas_rede and all(checagens.values())
log("OK" if ok else "FALHOU")
sys.exit(0 if ok else 1)
