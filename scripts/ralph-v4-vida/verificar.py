"""Verificacao V4 (vida: garantia, ideias-de-presente, pessoas, treino, manutencao,
quero-aprender, salvos, lista-de-compras, pra-responder, ainda-usa, mensagem-dificil,
vale-a-pena, seu-progresso, revisao-trimestral, e painel/peso-e-medidas) no Playwright
headless 390x844. Mesmo padrao de scripts/ralph-v3-organizacao/verificar.py: sobe o app
num banco de teste temporario (servidor.py), loga, rola a aba Vida inteira, abre o
formulario de Garantia pelo novo `.btn-adicionar` (bottom-sheet), cria 1 item de teste,
confere que aparece na lista e que fecha o sheet, confere zero erro de console. 2
screenshots no final.

Uso: PORTA=5160 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-v4-vida/verificar.py
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
PORTA = os.environ.get("PORTA", "5160")
BASE = "http://127.0.0.1:" + PORTA
CHROME = "/opt/pw-browsers/chromium"
PIN = "135790"

# ---- sobe o servidor num banco de teste (subprocesso, mesmo padrao da V3/V0d) ----
env = dict(os.environ)
env["PORTA"] = PORTA
servidor = subprocess.Popen(
    ["/home/user/painel-pessoal-tdah/.venv/bin/python", os.path.join(AQUI, "servidor.py"), REPO],
    env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)

pronto = False
for _ in range(60):
    try:
        urllib.request.urlopen(BASE + "/", timeout=1)
        pronto = True
        break
    except Exception:
        if servidor.poll() is not None:
            break
        time.sleep(0.5)

if not pronto:
    servidor.terminate()
    saida = servidor.stdout.read() if servidor.stdout else ""
    print("servidor nao respondeu em /", saida[-3000:])
    sys.exit(2)

erros, falhas_rede = [], []
resultados = {}

try:
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
        time.sleep(0.8)

        # ---- aba Vida: rolagem inteira ----
        page.click('.tab-btn[data-tab="vida"]')
        time.sleep(0.6)

        secoes_esperadas = [
            "vida-garantia", "vida-ideias-presente", "vida-pessoas", "vida-treino",
            "vida-manutencao", "vida-quero-aprender", "vida-salvos", "vida-lista-de-compras",
            "vida-pra-responder", "vida-mensagem-dificil", "vida-vale-a-pena",
            "vida-seu-progresso", "vida-revisao-trimestral",
        ]
        secoes_presentes = {
            sid: page.locator(f'.secao-recolhivel[data-secao-id="{sid}"]').count() > 0
            for sid in secoes_esperadas
        }
        resultados["secoes_presentes"] = secoes_presentes

        # Rolagem inteira da aba: o scroll e do documento (nao de #tab-vida, que e
        # display:block normal, nao um container com overflow proprio). BUG
        # PRE-EXISTENTE fora dos meus arquivos: static/css/secoes/painel.css tem
        # `#tab-painel { display: flex }` (ID) SEM o guard `:not([hidden])`, que ganha
        # de `.tab-content:not([hidden])` (style.css) por especificidade - o Painel
        # fica sempre no fluxo do documento (mesmo com o atributo `hidden`), empurrando
        # a Vida pra baixo dele mesmo com a aba Vida ativa. Nao e meu arquivo (dono:
        # faixa do Painel) - anotado em progress.txt, nao mexi. Rolo o documento
        # inteiro mesmo assim (pra pegar erro de layout/console de ponta a ponta), mas
        # o screenshot final usa `locator("#tab-vida").screenshot()` (recorte do
        # elemento, nao da viewport) pra mostrar so a aba Vida de fato, sem o
        # vazamento do Painel por cima.
        altura_total = page.evaluate("document.documentElement.scrollHeight")
        passo = 700
        y = 0
        while y < altura_total:
            page.evaluate(f"window.scrollTo(0, {y})")
            time.sleep(0.1)
            y += passo
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.3)

        page.locator("#tab-vida").screenshot(path=os.path.join(AQUI, "v4-vida-rolagem.png"), animations="disabled")

        # ---- Garantia: abre o form pelo .btn-adicionar novo, cria 1 item de teste ----
        page.click("#garantia-abrir-btn")
        sheet_visivel = page.is_visible("#sheet-garantia")
        page.fill("#garantia-produto", "Geladeira teste (playwright)")
        page.fill("#garantia-data-compra", "2026-01-10")
        page.fill("#garantia-prazo", "12")
        page.screenshot(path=os.path.join(AQUI, "v4-garantia-sheet-aberto.png"), animations="disabled")
        page.click("#garantia-form button[type=submit]")
        page.wait_for_selector("#lista-garantias li:has-text('Geladeira teste (playwright)')", timeout=5000)
        # bottom-sheet.js (V0d) anima o fechamento (~240ms) antes de aplicar `hidden` -
        # espera a transicao terminar (state="attached", nao "visible": o proprio ponto
        # do atributo hidden e o elemento NAO ficar visivel).
        try:
            page.wait_for_selector("#sheet-garantia[hidden]", state="attached", timeout=2000)
            garantia_fechou = True
        except Exception:
            garantia_fechou = False
        resultados["garantia"] = {
            "abriu_sheet": sheet_visivel,
            "apareceu_na_lista": True,
            "fechou_apos_salvar": garantia_fechou,
        }

        b.close()
finally:
    servidor.terminate()
    try:
        servidor.wait(timeout=5)
    except Exception:
        servidor.kill()

# Falhas de ambiente conhecidas (sandbox sem internet confiavel) - mesmo raciocinio de
# scripts/ralph-v3-organizacao/verificar.py.
AMBIENTE = ("fonts.googleapis.com", "fonts.gstatic.com", "/api/summary/today")
falhas_ambiente = [f for f in falhas_rede if any(a in f[1] for a in AMBIENTE)]
falhas_rede = [f for f in falhas_rede if f not in falhas_ambiente]
erros = [e for e in erros if not (e[1].startswith("Failed to load resource") and not falhas_rede)]

res = {
    "resultados": resultados,
    "erros_console": erros,
    "falhas_rede": falhas_rede,
    "falhas_ambiente_ignoradas": falhas_ambiente,
}
json.dump(res, open(os.path.join(AQUI, "v4-resultado.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps(res, ensure_ascii=False, indent=1))

todas_secoes = all(resultados.get("secoes_presentes", {}).values())
garantia_ok = (
    resultados.get("garantia", {}).get("abriu_sheet")
    and resultados["garantia"].get("apareceu_na_lista")
    and resultados["garantia"].get("fechou_apos_salvar")
)
ok = not erros and not falhas_rede and todas_secoes and garantia_ok
print("OK" if ok else "FALHOU")
sys.exit(0 if ok else 1)
