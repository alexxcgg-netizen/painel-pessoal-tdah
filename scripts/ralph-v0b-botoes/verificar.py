"""Verificacao V0b (botoes) no Playwright headless 390x844.
Uso: PORTA=5183 python verificar.py
Loga, injeta via page.evaluate um botao de cada tipo (.btn-primario, .btn-secundario,
.btn-perigo, .btn-fab, .btn-adicionar + variante pilula + disabled + is-carregando) dentro
de um container que ja existe no app (#tab-hoje, sem pagina de demonstracao a parte), tira
1 screenshot e confere zero erro de console/pageerror (fora falhas de ambiente conhecidas).
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:" + os.environ.get("PORTA", "5183")
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

INJETAR_BOTOES = """() => {
  const alvo = document.querySelector('#tab-hoje');
  if (!alvo) return {ok: false, motivo: 'container #tab-hoje nao encontrado'};
  const caixa = document.createElement('div');
  caixa.id = 'v0b-verificacao';
  caixa.style.cssText = 'display:flex;flex-direction:column;gap:16px;padding:16px;';
  caixa.innerHTML = `
    <button type="button" class="btn btn-primario">Salvar</button>
    <button type="button" class="btn btn-secundario">Cancelar</button>
    <button type="button" class="btn btn-perigo">Excluir</button>
    <button type="button" class="btn btn-fab btn-fab--mais" aria-label="Adicionar rapido"></button>
    <button type="button" class="btn btn-adicionar"><span>Adicionar hábito</span></button>
    <button type="button" class="btn btn-adicionar btn-adicionar--pilula"><span>Novo item</span></button>
    <button type="button" class="btn btn-adicionar" disabled><span>Adicionar (desabilitado)</span></button>
    <button type="button" class="btn btn-primario is-carregando" disabled aria-busy="true"><span>Salvando…</span></button>
  `;
  alvo.insertBefore(caixa, alvo.firstChild);
  return {ok: true};
}"""

MEDIR_BOTOES = """() => {
  const sel = ['.btn-primario', '.btn-secundario', '.btn-perigo', '.btn-fab', '.btn-adicionar'];
  return sel.map(s => {
    const el = document.querySelector('#v0b-verificacao ' + s);
    if (!el) return {seletor: s, achou: false};
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      seletor: s, achou: true,
      altura: Math.round(r.height), largura: Math.round(r.width),
      outlineNoFoco: cs.outlineStyle,
      cursor: cs.cursor,
    };
  });
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

    injecao = page.evaluate(INJETAR_BOTOES)
    assert injecao.get("ok"), injecao

    # foco visivel: confere que o :focus-visible troca o outline padrao (nunca o azul do
    # navegador) por um box-shadow proprio, e que ELE DE FATO substitui o box-shadow "de
    # repouso" da variante (nao so empata na cascata e fica escondido atras dele)
    sem_foco = page.evaluate(
        "() => getComputedStyle(document.querySelector('#v0b-verificacao .btn-secundario')).boxShadow"
    )
    page.click("#v0b-verificacao .btn-primario")
    page.keyboard.press("Tab")
    foco = page.evaluate(
        "() => { const el = document.activeElement; const cs = getComputedStyle(el);"
        " return {tag: el.tagName, classe: el.className, outline: cs.outlineStyle,"
        " boxShadow: cs.boxShadow}; }"
    )

    medidas = page.evaluate(MEDIR_BOTOES)
    time.sleep(0.4)
    page.screenshot(path=os.path.join(AQUI, "v0b-botoes.png"), animations="disabled")
    b.close()

# Falhas de ambiente conhecidas (sandbox sem internet confiavel e IA com chave falsa) - ver
# scripts/ralph-v0a-tokens/verificar.py, mesmo raciocinio.
AMBIENTE = ("fonts.googleapis.com", "fonts.gstatic.com", "/api/summary/today")
falhas_ambiente = [f for f in falhas_rede if any(a in f[1] for a in AMBIENTE)]
falhas_rede = [f for f in falhas_rede if f not in falhas_ambiente]
erros = [e for e in erros if not e[1].startswith("Failed to load resource")] if not falhas_rede else erros

nao_encontrados = [m["seletor"] for m in medidas if not m.get("achou")]
baixos = [m for m in medidas if m.get("achou") and m["altura"] < 44]
# o anel de foco tem que (1) nao ser o outline azul padrao do navegador e (2) realmente
# aparecer - ou seja, o botao focado nao pode ficar so com o box-shadow "de repouso" de
# quando esta sem foco (senao a regra de foco perdeu o empate de especificidade na cascata)
foco_ok = (
    foco.get("outline") == "none"
    and "rgb" in (foco.get("boxShadow") or "")
    and foco.get("boxShadow") != sem_foco
)

res = {
    "erros_console": erros,
    "falhas_rede": falhas_rede,
    "falhas_ambiente_ignoradas": falhas_ambiente,
    "medidas": medidas,
    "nao_encontrados": nao_encontrados,
    "abaixo_de_44px": baixos,
    "foco_visivel": foco,
    "foco_ok": foco_ok,
}
json.dump(res, open(os.path.join(AQUI, "v0b-resultado.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps(res, ensure_ascii=False, indent=1))

ok = not erros and not falhas_rede and not nao_encontrados and not baixos and foco_ok
print("OK" if ok else "FALHOU")
sys.exit(0 if ok else 1)
