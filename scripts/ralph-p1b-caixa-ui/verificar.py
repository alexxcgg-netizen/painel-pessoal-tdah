"""Verificacao P1b-caixa-ui (faixa compacta em Hoje, selo de pendencias, tela
Assistente com Caixa/Regras/Avisos) no Playwright headless 390x844. Mesmo
padrao da V3 (scripts/ralph-v3-organizacao/verificar.py): sobe o app num
banco de teste temporario (servidor.py, com itens sinteticos ja inseridos em
`assistente_itens`/`p4_regras`), loga, confere a faixa compacta + selo na
aba Hoje, depois a tela Assistente (3 secoes) e responde 1 item pra provar
que ele some da lista. 2 screenshots no final.

Uso: PORTA=5142 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-p1b-caixa-ui/verificar.py
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
PORTA = os.environ.get("PORTA", "5142")
BASE = "http://127.0.0.1:" + PORTA
CHROME = "/opt/pw-browsers/chromium"
PIN = "135790"

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

        # ---- faixa compacta + selo na aba Hoje ----
        page.wait_for_selector("#caixa-assistente .secao-recolhivel", timeout=5000)
        titulo_compacto = page.text_content("#caixa-compacta-titulo")
        itens_compactos = page.locator("#caixa-compacta-lista .caixa-item").count()
        selo_hoje = page.locator('.tab-btn[data-tab="hoje"] .nav-selo').text_content()
        selo_hoje_visivel = page.locator('.tab-btn[data-tab="hoje"] .nav-selo').is_visible()
        resultados["faixa_compacta"] = {
            "titulo": titulo_compacto,
            "quantidade_itens_mostrados": itens_compactos,
            "selo_hoje": selo_hoje,
            "selo_hoje_visivel": selo_hoje_visivel,
        }

        # recolher/expandir (V0c: max-height anima, aria-expanded muda)
        cabecalho = page.locator("#caixa-assistente .secao-cabecalho")
        cabecalho.click()
        time.sleep(0.45)
        aberto_depois_clique = page.get_attribute("#caixa-assistente .secao-recolhivel", "data-aberto")
        cabecalho.click()
        time.sleep(0.45)
        resultados["recolhivel"] = {"fechou_no_1o_clique": aberto_depois_clique == "false"}

        time.sleep(0.3)
        page.screenshot(path=os.path.join(AQUI, "p1b-hoje.png"), animations="disabled")

        # ---- responder 1 item (some com animacao) ----
        # A faixa compacta ja mostra so as 3 mais urgentes (de 4 pendentes) -
        # responder uma NAO muda a CONTAGEM da lista (continuam cabendo 3),
        # entao a prova certa e o item respondido (id 1, "Pagou o cartao de
        # credito?") sumir da lista, nao o total encolher.
        item_id_respondido = page.get_attribute("#caixa-compacta-lista .caixa-item", "data-item-id")
        page.locator("#caixa-compacta-lista .caixa-item-opcao").first.click()
        page.wait_for_selector(f'#caixa-compacta-lista .caixa-item[data-item-id="{item_id_respondido}"]', state="detached", timeout=5000)
        selo_depois = page.locator('.tab-btn[data-tab="hoje"] .nav-selo').text_content()
        resultados["responder"] = {"item_sumiu": True, "selo_depois": selo_depois}

        # ---- Ver tudo -> aba Assistente ----
        page.click("#caixa-compacta-vertudo")
        time.sleep(0.5)
        assistente_visivel = page.is_visible("#tab-assistente")
        resultados["ver_tudo_abre_assistente"] = assistente_visivel

        # ---- secao Caixa (aba Assistente): todos os itens + historico ----
        page.wait_for_selector("#caixa-lista-pendentes .caixa-item", timeout=5000)
        pendentes_secao = page.locator("#caixa-lista-pendentes .caixa-item").count()
        page.click('#secao-caixa-assistente .secao-recolhivel[data-secao-id="caixa-historico"] .secao-cabecalho')
        time.sleep(0.4)
        historico_itens = page.locator("#caixa-lista-historico .caixa-item-historico").count()
        resultados["secao_caixa"] = {"pendentes": pendentes_secao, "historico": historico_itens}

        # ---- secao Regras ----
        page.wait_for_selector("#regras-lista .regra-item", timeout=5000)
        regras_antes = page.locator("#regras-lista .regra-item").count()
        page.click("#regras-lista .regra-pausar")
        page.wait_for_selector("#regras-lista .regra-retomar", timeout=5000)
        status_pausada = page.text_content("#regras-lista .regra-status")
        resultados["secao_regras"] = {"quantidade": regras_antes, "pausou": "Pausada" in (status_pausada or "")}

        # ---- secao Avisos ----
        page.wait_for_selector("#avisos-lista .aviso-item", timeout=5000)
        avisos_qtd = page.locator("#avisos-lista .aviso-item").count()
        tem_form_silencio = page.is_visible("#avisos-silencio-form")
        resultados["secao_avisos"] = {"quantidade_tipos": avisos_qtd, "form_silencio_visivel": tem_form_silencio}

        time.sleep(0.3)
        page.screenshot(path=os.path.join(AQUI, "p1b-assistente.png"), animations="disabled")

        b.close()
finally:
    servidor.terminate()
    try:
        servidor.wait(timeout=5)
    except Exception:
        servidor.kill()

# Falhas de ambiente conhecidas (mesmo raciocinio das outras faixas: fonte externa e
# rotas que dependem de IA/clima reais, fora do escopo desta faixa).
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
json.dump(res, open(os.path.join(AQUI, "p1b-resultado.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps(res, ensure_ascii=False, indent=1))

ok = (
    not erros
    and not falhas_rede
    and resultados.get("faixa_compacta", {}).get("quantidade_itens_mostrados") == 3
    and resultados.get("faixa_compacta", {}).get("selo_hoje_visivel")
    and resultados.get("faixa_compacta", {}).get("selo_hoje") == "4"
    and resultados.get("recolhivel", {}).get("fechou_no_1o_clique")
    and resultados.get("responder", {}).get("item_sumiu")
    and resultados.get("responder", {}).get("selo_depois") == "3"
    and resultados.get("ver_tudo_abre_assistente")
    and resultados.get("secao_caixa", {}).get("pendentes") == 3
    # 2 no historico: o item ja resolvido no seed (servidor.py) + o item
    # respondido no proprio teste, logo acima (ambos entram em "resolvido").
    and resultados.get("secao_caixa", {}).get("historico") == 2
    and resultados.get("secao_regras", {}).get("quantidade") == 1
    and resultados.get("secao_regras", {}).get("pausou")
    and resultados.get("secao_avisos", {}).get("quantidade_tipos", 0) > 0
    and resultados.get("secao_avisos", {}).get("form_silencio_visivel")
)
print("OK" if ok else "FALHOU")
sys.exit(0 if ok else 1)
