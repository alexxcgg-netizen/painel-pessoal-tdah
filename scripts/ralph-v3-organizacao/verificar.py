"""Verificacao V3-organizacao (vida/habitos, vida/projetos, vida/agenda-painel,
tarefas/tarefas) no Playwright headless 390x844. Mesmo padrao da V0b
(scripts/ralph-v0b-botoes/verificar.py): sobe o app num banco de teste temporario
(servidor.py, dublê do iCloud), loga, abre cada formulario pelo novo `.btn-adicionar`
(bottom-sheet), cria 1 item de teste em cada secao, confere que aparece na lista e
que nao ha erro de console. 2 screenshots no final.

Uso: PORTA=5150 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-v3-organizacao/verificar.py
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
PORTA = os.environ.get("PORTA", "5150")
BASE = "http://127.0.0.1:" + PORTA
CHROME = "/opt/pw-browsers/chromium"
PIN = "135790"

# ---- sobe o servidor num banco de teste (subprocesso, mesmo padrao da V0b) ----
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

        # ---- Vida > Habitos / Projetos / Agenda ----
        page.click('.tab-btn[data-tab="vida"]')
        time.sleep(0.4)

        # Habitos
        page.click("#habito-abrir-btn")
        sheet_visivel = page.is_visible("#habito-sheet")
        page.fill("#habito-nome", "Meditar (teste playwright)")
        page.click("#habito-form button[type=submit]")
        page.wait_for_selector("#lista-habitos li:has-text('Meditar (teste playwright)')", timeout=5000)
        habito_fechou = not page.is_visible("#habito-sheet") or page.get_attribute("#habito-sheet", "hidden") is not None
        resultados["habitos"] = {
            "abriu_sheet": sheet_visivel,
            "fechou_apos_salvar": habito_fechou,
            "apareceu_na_lista": True,
        }

        # Projetos
        page.click("#projeto-abrir-btn")
        sheet_visivel = page.is_visible("#projeto-sheet")
        page.fill("#projeto-nome", "Reforma teste (playwright)")
        page.click("#projeto-form button[type=submit]")
        page.wait_for_selector("#lista-projetos li:has-text('Reforma teste (playwright)')", timeout=5000)
        resultados["projetos"] = {"abriu_sheet": sheet_visivel, "apareceu_na_lista": True}

        # Agenda (iCloud dublê no servidor.py - nunca chama rede real)
        page.click("#evento-abrir-btn")
        sheet_visivel = page.is_visible("#evento-sheet")
        page.fill("#evento-titulo", "Evento teste (playwright)")
        amanha = time.strftime("%Y-%m-%d", time.localtime(time.time() + 86400))
        page.fill("#evento-data", amanha)
        page.fill("#evento-hora-inicio", "10:00")
        page.fill("#evento-hora-fim", "11:00")
        page.click("#evento-form button[type=submit]")
        page.wait_for_selector("#lista-eventos-criados li:has-text('Evento teste (playwright)')", timeout=5000)
        resultados["agenda"] = {"abriu_sheet": sheet_visivel, "apareceu_na_lista": True}

        time.sleep(0.3)
        page.screenshot(path=os.path.join(AQUI, "v3-vida.png"), animations="disabled")

        # ---- Tarefas ----
        page.click('.tab-btn[data-tab="tarefas"]')
        time.sleep(0.4)
        page.click("#tarefa-abrir-btn")
        sheet_visivel = page.is_visible("#tarefa-sheet")
        page.fill("#nova-tarefa-titulo", "Tarefa teste (playwright)")
        page.click("#nova-tarefa-form button[type=submit]")
        page.wait_for_selector("#lista-tarefas li:has-text('Tarefa teste (playwright)')", timeout=5000)
        resultados["tarefas"] = {"abriu_sheet": sheet_visivel, "apareceu_na_lista": True}

        time.sleep(0.3)
        page.screenshot(path=os.path.join(AQUI, "v3-tarefas.png"), animations="disabled")

        b.close()
finally:
    servidor.terminate()
    try:
        servidor.wait(timeout=5)
    except Exception:
        servidor.kill()

# Falhas de ambiente conhecidas (sandbox sem internet confiavel e IA com chave falsa) - mesmo
# raciocinio de scripts/ralph-v0a-tokens/verificar.py e scripts/ralph-v0b-botoes/verificar.py:
# fonte externa (Google Fonts) e /api/summary/today (clima/IA reais, fora do escopo desta faixa).
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
json.dump(res, open(os.path.join(AQUI, "v3-resultado.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps(res, ensure_ascii=False, indent=1))

todas_abriram = all(v.get("abriu_sheet") for v in resultados.values())
todas_apareceram = all(v.get("apareceu_na_lista") for v in resultados.values())
ok = not erros and not falhas_rede and todas_abriram and todas_apareceram and len(resultados) == 4
print("OK" if ok else "FALHOU")
sys.exit(0 if ok else 1)
