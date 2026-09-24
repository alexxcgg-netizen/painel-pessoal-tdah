"""Verificacao V0d (bottom sheet + barra de navegacao) no Playwright headless 390x844.
Uso: PORTA=5104 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-v0d-sheet-nav/verificar.py

Nao ha nenhum `.bottom-sheet` real no HTML ainda (nenhuma secao usa a API - isso e
trabalho de faixas futuras, ex. P1b), entao este script INJETA um sheet de teste via
page.evaluate (como o progress.txt/prompt pede) pra exercitar abrirBottomSheet/
fecharBottomSheet de verdade no navegador: abre, confere aria-modal/role/foco preso
no primeiro campo, fecha com ESC, confere que o foco voltou pro botao que abriu e que
o evento bottomsheet:fechado disparou. Salva no maximo 2 screenshots (barra visivel e
sheet aberto) e falha se houver qualquer erro de console/pageerror.
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:" + os.environ.get("PORTA", "5104")
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

erros, falhas_rede = [], []
checagens = {}

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
            BASE + "/login",
            data=json.dumps({"pin": "135790"}),
            headers={"Content-Type": "application/json"},
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

    # 1a screenshot: barra de navegacao inferior no acabamento novo (nada aberto ainda).
    page.screenshot(path=os.path.join(AQUI, "01-barra.png"), animations="disabled")

    checagens["abrirBottomSheet_existe"] = page.evaluate("typeof window.abrirBottomSheet === 'function'")
    checagens["fecharBottomSheet_existe"] = page.evaluate("typeof window.fecharBottomSheet === 'function'")

    # Injeta um sheet de teste (contrato de autoria: so o <div class="bottom-sheet" hidden>,
    # o resto - fundo, painel, alca - o componente monta sozinho na 1a abertura) e um botao
    # gatilho fora dele, como uma secao real teria.
    page.evaluate(
        """() => {
      const gatilho = document.createElement('button');
      gatilho.id = 'v0d-gatilho-teste';
      gatilho.textContent = 'Abrir teste';
      gatilho.style.cssText = 'position:fixed;top:8px;left:8px;z-index:99';
      document.body.appendChild(gatilho);

      const sheet = document.createElement('div');
      sheet.className = 'bottom-sheet';
      sheet.id = 'v0d-sheet-teste';
      sheet.hidden = true;
      sheet.innerHTML = `
        <h2>Sheet de verificacao (V0d)</h2>
        <form data-fecha-ao-enviar>
          <label>Campo de teste <input type="text" id="v0d-campo-1"></label>
          <button type="button" id="v0d-botao-2">Segundo foco</button>
        </form>`;
      document.body.appendChild(sheet);
      gatilho.addEventListener('click', () => window.abrirBottomSheet('v0d-sheet-teste'));
      window.__v0dFechou = false;
      sheet.addEventListener('bottomsheet:fechado', () => { window.__v0dFechou = true; });
    }"""
    )

    page.click("#v0d-gatilho-teste")
    page.wait_for_selector("#v0d-sheet-teste.bottom-sheet--aberto")
    time.sleep(0.4)  # deixa a transicao de slide terminar antes do screenshot

    checagens["aria_modal"] = page.eval_on_selector("#v0d-sheet-teste", "el => el.getAttribute('aria-modal')")
    checagens["role"] = page.eval_on_selector("#v0d-sheet-teste", "el => el.getAttribute('role')")
    checagens["hidden_false"] = page.eval_on_selector("#v0d-sheet-teste", "el => el.hidden")
    checagens["estrutura_montada"] = page.eval_on_selector(
        "#v0d-sheet-teste", "el => !!el.querySelector('.bottom-sheet-painel') && !!el.querySelector('.bottom-sheet-fundo')"
    )
    checagens["foco_no_primeiro_campo"] = page.evaluate("document.activeElement && document.activeElement.id")
    checagens["scroll_bloqueado"] = page.eval_on_selector(
        "body", "el => el.classList.contains('bottom-sheet-bloqueado')"
    )

    # 2a screenshot: sheet aberto, fundo escurecido, painel elevado - com a barra por baixo.
    page.screenshot(path=os.path.join(AQUI, "02-sheet-aberto.png"), animations="disabled")

    # Tab a partir do ultimo campo deve voltar pro primeiro (foco preso).
    page.focus("#v0d-botao-2")
    page.keyboard.press("Tab")
    checagens["foco_preso_voltou_ao_primeiro"] = page.evaluate("document.activeElement && document.activeElement.id")

    # ESC fecha e devolve o foco pro gatilho.
    page.keyboard.press("Escape")
    page.wait_for_selector("#v0d-sheet-teste[hidden]", state="attached")
    checagens["fechou_com_esc"] = page.eval_on_selector("#v0d-sheet-teste", "el => el.hidden")
    checagens["evento_fechado_disparou"] = page.evaluate("window.__v0dFechou === true")
    checagens["foco_devolvido_ao_gatilho"] = page.evaluate("document.activeElement && document.activeElement.id")
    checagens["scroll_liberado"] = page.eval_on_selector(
        "body", "el => !el.classList.contains('bottom-sheet-bloqueado')"
    )

    # Barra de navegacao: toque minimo 44px e o selo (estilo pronto, mesmo sem HTML da P1b ainda).
    checagens["tab_btn_min_44px"] = page.eval_on_selector(
        "#tabbar .tab-btn", "el => getComputedStyle(el).minHeight"
    )

    b.close()

# Falhas de ambiente conhecidas (mesmas do resto da Fase 7 - sandbox sem CA valido pro
# proxy de fontes, e IA com chave falsa -> 502 esperado em /api/summary/today). O console
# so imprime "Failed to load resource" sem URL pra essas, entao a checagem real e pela rede;
# se so sobrarem esses dois casos, os console.error correspondentes tambem saem da lista.
AMBIENTE = ("fonts.googleapis.com", "fonts.gstatic.com", "/api/summary/today")
falhas_ambiente = [f for f in falhas_rede if any(a in f[1] for a in AMBIENTE)]
falhas_rede = [f for f in falhas_rede if f not in falhas_ambiente]
if not falhas_rede:
    erros = [e for e in erros if not e[1].startswith("Failed to load resource")]

esperado = {
    "abrirBottomSheet_existe": True,
    "fecharBottomSheet_existe": True,
    "aria_modal": "true",
    "role": "dialog",
    "hidden_false": False,
    "estrutura_montada": True,
    "foco_no_primeiro_campo": "v0d-campo-1",
    "scroll_bloqueado": True,
    "foco_preso_voltou_ao_primeiro": "v0d-campo-1",
    "fechou_com_esc": True,
    "evento_fechado_disparou": True,
    "foco_devolvido_ao_gatilho": "v0d-gatilho-teste",
    "scroll_liberado": True,
}
divergencias = {k: {"esperado": v, "obtido": checagens.get(k)} for k, v in esperado.items() if checagens.get(k) != v}
if checagens.get("tab_btn_min_44px") and not checagens["tab_btn_min_44px"].endswith("px"):
    divergencias["tab_btn_min_44px"] = checagens["tab_btn_min_44px"]
elif checagens.get("tab_btn_min_44px"):
    valor_px = float(checagens["tab_btn_min_44px"].replace("px", ""))
    if valor_px < 44:
        divergencias["tab_btn_min_44px"] = checagens["tab_btn_min_44px"]

resultado = {
    "checagens": checagens,
    "divergencias": divergencias,
    "erros_console": erros,
    "falhas_rede": falhas_rede,
    "falhas_ambiente_ignoradas": falhas_ambiente,
}
with open(os.path.join(AQUI, "resultado.json"), "w") as f:
    json.dump(resultado, f, indent=1, ensure_ascii=False)
print(json.dumps(resultado, ensure_ascii=False, indent=1))

ok = not erros and not falhas_rede and not divergencias
print("OK" if ok else "FALHOU")
sys.exit(0 if ok else 1)
