"""Verificacao V0a no Playwright headless 390x844.
Uso: PORTA=5170 python verificar.py <prefixo>   (prefixo: 'referencia' ou 'depois')
Salva <prefixo>-hoje.png e <prefixo>-vida.png nesta pasta, confere erro de console/pageerror,
recurso com falha de rede (fora as falhas de ambiente listadas em AMBIENTE),
e (com prefixo 'depois') se os tokens da V0a resolvem no :root.
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

AQUI = os.path.dirname(os.path.abspath(__file__))
prefixo = sys.argv[1] if len(sys.argv) > 1 else "depois"
BASE = "http://127.0.0.1:" + os.environ.get("PORTA", "5170")
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
TOKENS = [
    "--raio", "--raio-sm", "--raio-lg", "--raio-pilula",
    "--espaco-1", "--espaco-2", "--espaco-3", "--espaco-4", "--espaco-5", "--espaco-6",
    "--elevacao-1", "--elevacao-2", "--elevacao-3", "--borda-sutil", "--borda-forte",
    "--superficie-1", "--superficie-2", "--superficie-3", "--realce-superficie",
    "--fonte-mono", "--transicao-rapida", "--transicao-media", "--toque-min", "--anel-foco",
]
erros, falhas_rede = [], []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, headless=True)
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    r = ctx.request.post(BASE + "/configurar-pin", data=json.dumps({"pin": "135790", "confirmacao": "135790"}),
                         headers={"Content-Type": "application/json"})
    if r.status != 200:
        r = ctx.request.post(BASE + "/login", data=json.dumps({"pin": "135790"}),
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
    time.sleep(1.5)
    page.screenshot(path=os.path.join(AQUI, f"{prefixo}-hoje.png"), animations="disabled")
    tokens = page.evaluate(
        "(ns) => { const cs = getComputedStyle(document.documentElement);"
        " return Object.fromEntries(ns.map(n => [n, cs.getPropertyValue(n).trim()])); }", TOKENS)
    page.click("button.tab-btn[data-tab='vida']")
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    time.sleep(1.2)
    page.screenshot(path=os.path.join(AQUI, f"{prefixo}-vida.png"), animations="disabled")
    b.close()

# Falhas de ambiente conhecidas (sandbox sem internet confiavel e IA com chave falsa):
# - Google Fonts: o Chromium do sandbox nao confia no CA do proxy (ERR_CERT_AUTHORITY_INVALID);
# - /api/summary/today: chama a IA, que aqui e dublê com chave falsa -> 502 esperado.
# O console so diz "Failed to load resource" sem URL, entao esses erros sao conferidos pela rede.
AMBIENTE = ("fonts.googleapis.com", "fonts.gstatic.com", "/api/summary/today")
falhas_ambiente = [f for f in falhas_rede if any(a in f[1] for a in AMBIENTE)]
falhas_rede = [f for f in falhas_rede if f not in falhas_ambiente]
erros = [e for e in erros if not e[1].startswith("Failed to load resource")] if not falhas_rede else erros
faltando = [n for n, v in tokens.items() if not v]
res = {"erros_console": erros, "falhas_rede": falhas_rede, "falhas_ambiente_ignoradas": falhas_ambiente, "tokens": tokens, "tokens_faltando": faltando}
json.dump(res, open(os.path.join(AQUI, f"{prefixo}-resultado.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps({"erros_console": erros, "falhas_rede": falhas_rede,
                  "falhas_ambiente_ignoradas": falhas_ambiente, "tokens_faltando": faltando},
                 ensure_ascii=False, indent=1))
ok = not erros and not falhas_rede and (prefixo == "referencia" or not faltando)
print("OK" if ok else "FALHOU")
sys.exit(0 if ok else 1)
