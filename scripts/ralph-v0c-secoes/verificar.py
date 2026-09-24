"""Verificacao V0c (secao recolhivel, card, chip, campo, lista-item) no Playwright headless
390x844.
Uso: PORTA=5185 python verificar.py
Loga, injeta via page.evaluate uma secao recolhivel + card + chips + campo + lista dentro de
um container que ja existe no app (#tab-hoje, sem pagina de demonstracao a parte), clica no
cabecalho da secao pra abrir (confere aria-expanded + localStorage), tira 2 screenshots
(fechada e aberta) e confere zero erro de console/pageerror (fora falhas de ambiente
conhecidas, mesma lista que V0a/V0b).
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:" + os.environ.get("PORTA", "5185")
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

INJETAR = """() => {
  const alvo = document.querySelector('#tab-hoje');
  if (!alvo) return {ok: false, motivo: 'container #tab-hoje nao encontrado'};
  const caixa = document.createElement('div');
  caixa.id = 'v0c-verificacao';
  caixa.style.cssText = 'display:flex;flex-direction:column;gap:16px;padding:16px;';
  caixa.innerHTML = `
    <section class="secao-recolhivel" data-aberto="false" data-secao-id="v0c-verificacao-teste">
      <button type="button" class="secao-cabecalho" aria-expanded="false">Sua rotina <span class="chevron"></span></button>
      <div class="secao-conteudo"><p>Conteudo de teste da secao recolhivel (V0c).</p></div>
    </section>
    <div class="card card--destaque">
      <div class="card-cabecalho">
        <h3 class="card-titulo">Resumo do mes</h3>
        <div class="card-acao"><button type="button" class="chip">Ver tudo</button></div>
      </div>
      <div class="card-numero">R$ 1.234,56</div>
      <div class="card-legenda">3 lancamentos pendentes</div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      <button type="button" class="chip">Todos</button>
      <button type="button" class="chip chip--ativo">Ativos</button>
      <button type="button" class="chip">Concluidos</button>
    </div>
    <div>
      <label class="campo-rotulo" for="v0c-campo-teste">Nome</label>
      <input class="campo" id="v0c-campo-teste" type="text" placeholder="Digite algo">
    </div>
    <ul class="lista">
      <li class="lista-item">
        <div class="lista-item-corpo">
          <span class="lista-item-titulo">Item 1</span>
          <span class="lista-item-meta">Hoje</span>
        </div>
        <div class="lista-item-acoes"><button type="button" class="chip chip--compacto">Editar</button></div>
      </li>
      <li class="lista-item">
        <div class="lista-item-corpo">
          <span class="lista-item-titulo">Item 2</span>
          <span class="lista-item-meta">Ontem</span>
        </div>
        <div class="lista-item-acoes"><button type="button" class="chip chip--compacto">Editar</button></div>
      </li>
    </ul>
  `;
  alvo.insertBefore(caixa, alvo.firstChild);
  if (typeof window.ligarSecoesRecolhiveis === 'function') window.ligarSecoesRecolhiveis(caixa);
  return {ok: true};
}"""

MEDIR = """() => {
  const raiz = '#v0c-verificacao ';
  const medir = (sel) => {
    const el = document.querySelector(raiz + sel);
    if (!el) return {seletor: sel, achou: false};
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {seletor: sel, achou: true, altura: Math.round(r.height), largura: Math.round(r.width),
      raio: cs.borderRadius, sombra: cs.boxShadow, borda: cs.borderTopWidth + ' ' + cs.borderTopColor};
  };
  return [
    medir('.secao-cabecalho'),
    medir('.chip'),
    medir('.campo'),
    medir('.lista-item'),
    medir('.card'),
  ];
}"""

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
    time.sleep(1.0)

    injecao = page.evaluate(INJETAR)
    assert injecao.get("ok"), injecao

    aria_antes = page.eval_on_selector("#v0c-verificacao .secao-cabecalho", "el => el.getAttribute('aria-expanded')")
    time.sleep(0.4)
    page.screenshot(path=os.path.join(AQUI, "v0c-secoes-fechada.png"), animations="disabled")

    # abre a secao pelo cabecalho (clique real, nao via JS) - confere aria-expanded + estado
    page.click("#v0c-verificacao .secao-cabecalho")
    time.sleep(0.5)  # transicao de max-height (0.3s) + folga
    aria_depois = page.eval_on_selector("#v0c-verificacao .secao-cabecalho", "el => el.getAttribute('aria-expanded')")
    dados_aberto = page.eval_on_selector("#v0c-verificacao .secao-recolhivel", "el => el.dataset.aberto")
    salvo_ls = page.evaluate("() => localStorage.getItem('secaoRecolhivel:v0c-verificacao-teste')")

    # foco visivel no campo: nao pode ser o azul padrao do navegador
    page.click("#v0c-campo-teste")
    foco = page.evaluate(
        "() => { const el = document.activeElement; const cs = getComputedStyle(el);"
        " return {tag: el.tagName, outline: cs.outlineStyle, boxShadow: cs.boxShadow}; }"
    )

    medidas = page.evaluate(MEDIR)
    time.sleep(0.3)
    page.screenshot(path=os.path.join(AQUI, "v0c-secoes-aberta.png"), animations="disabled")
    b.close()

# Falhas de ambiente conhecidas (sandbox sem internet confiavel e IA com chave falsa) - ver
# scripts/ralph-v0a-tokens/verificar.py, mesmo raciocinio.
AMBIENTE = ("fonts.googleapis.com", "fonts.gstatic.com", "/api/summary/today")
falhas_ambiente = [f for f in falhas_rede if any(a in f[1] for a in AMBIENTE)]
falhas_rede = [f for f in falhas_rede if f not in falhas_ambiente]
erros = [e for e in erros if not e[1].startswith("Failed to load resource")] if not falhas_rede else erros

nao_encontrados = [m["seletor"] for m in medidas if not m.get("achou")]
baixos = [m for m in medidas if m.get("achou") and m["altura"] < 44 and m["seletor"] != ".card"]
foco_ok = (foco.get("boxShadow") or "none") != "none" or (foco.get("outline") or "none") != "none"
aria_ok = aria_antes == "false" and aria_depois == "true" and dados_aberto == "true"
storage_ok = salvo_ls == "1"

res = {
    "erros_console": erros,
    "falhas_rede": falhas_rede,
    "falhas_ambiente_ignoradas": falhas_ambiente,
    "medidas": medidas,
    "nao_encontrados": nao_encontrados,
    "abaixo_de_44px": baixos,
    "aria_expanded_antes": aria_antes,
    "aria_expanded_depois": aria_depois,
    "data_aberto_depois": dados_aberto,
    "aria_ok": aria_ok,
    "localstorage_salvo": salvo_ls,
    "storage_ok": storage_ok,
    "foco_campo": foco,
    "foco_ok": foco_ok,
}
json.dump(res, open(os.path.join(AQUI, "v0c-resultado.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps(res, ensure_ascii=False, indent=1))

ok = (not erros and not falhas_rede and not nao_encontrados and not baixos
      and foco_ok and aria_ok and storage_ok)
print("OK" if ok else "FALHOU")
sys.exit(0 if ok else 1)
