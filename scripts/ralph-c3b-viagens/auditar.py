"""Historia 1 da faixa C3b: auditoria visual/acessibilidade de Viagens, Lugares, Cotacoes e
aba Aviacao em Playwright headless 390x844 (banco sintetico - servidor.py na porta 5132).

Uso: PORTA=5132 python scripts/ralph-c3b-viagens/auditar.py [--screenshots]
Grava auditoria-resultado.json nesta pasta.
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comum import AMBIENTE, AQUI, BASE, CHROME, abrir_aba, ligar_coletores, logar, rotas_de_rede, semear  # noqa: E402

# JS que coleta os problemas de UMA secao: comeca no <h2> com o titulo dado e vai ate o
# proximo <h2> (ou o fim da aba). Mede so o que esta visivel.
COLETOR = r"""
([raizSel, titulo]) => {
  const raiz = document.querySelector(raizSel);
  let elems = [];
  if (titulo) {
    const h2s = [...raiz.querySelectorAll(':scope > h2, :scope > * > h2, h2')];
    const h = h2s.find(x => x.textContent.trim() === titulo);
    if (!h) return {erro: 'titulo nao achado ' + titulo};
    elems.push(h);
    let n = h.nextElementSibling;
    while (n && n.tagName !== 'H2' && !n.querySelector('h2, .secao-cabecalho') && !n.matches('.secao-recolhivel')) { elems.push(n); n = n.nextElementSibling; }
  } else {
    elems = [raiz];
  }
  const todos = [];
  elems.forEach(e => { todos.push(e); e.querySelectorAll('*').forEach(x => todos.push(x)); });
  const visivel = el => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none' && !el.closest('[hidden]');
  };
  const nome = el => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    if (el.classList.length) s += '.' + [...el.classList].slice(0, 3).join('.');
    const t = (el.getAttribute('aria-label') || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 30);
    return t ? s + ' "' + t + '"' : s;
  };
  // --- toque < 44px
  const tocaveis = todos.filter(el => el.matches('button, a[href], input:not([type=hidden]), select, textarea, [role=button], label.cotacao-upload-label, summary'));
  const toque = [];
  tocaveis.forEach(el => {
    if (!visivel(el)) return;
    if (el.closest('.leaflet-container') && !el.closest('.leaflet-control')) return;
    let alvo = el;
    // checkbox dentro de label: a area de toque e a label inteira
    if (el.matches('input[type=checkbox], input[type=radio]') && el.closest('label')) alvo = el.closest('label');
    if (el.matches('input[type=file]') && el.closest('label')) return;
    const r = alvo.getBoundingClientRect();
    if (r.height < 43.5 || r.width < 43.5) toque.push({el: nome(el), w: Math.round(r.width), h: Math.round(r.height)});
  });
  // --- contraste
  const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const lum = ([r, g, b]) => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const misturar = (top, base) => { const a = top[3]; return [top[0]*a + base[0]*(1-a), top[1]*a + base[1]*(1-a), top[2]*a + base[2]*(1-a), 1]; };
  const fundoDe = el => {
    const pilha = [];
    let n = el;
    while (n && n.nodeType === 1) { const bg = parse(getComputedStyle(n).backgroundColor); if (bg && bg[3] > 0) pilha.push(bg); n = n.parentElement; }
    let cor = [0, 0, 0, 1];
    for (let i = pilha.length - 1; i >= 0; i--) cor = misturar(pilha[i], cor);
    return cor;
  };
  const contraste = [];
  const vistos = new Set();
  todos.forEach(el => {
    if (!visivel(el)) return;
    if (el.closest('.leaflet-container') || el.closest('svg')) return;
    const temTexto = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!temTexto) return;
    const cs = getComputedStyle(el);
    let fg = parse(cs.color); if (!fg) return;
    const bg = fundoDe(el);
    fg = misturar([fg[0], fg[1], fg[2], fg[3] * parseFloat(cs.opacity || 1)], bg);
    const L1 = lum(fg), L2 = lum(bg);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const tam = parseFloat(cs.fontSize), peso = parseInt(cs.fontWeight);
    const grande = tam >= 24 || (tam >= 18.66 && peso >= 700);
    const minimo = grande ? 3 : 4.5;
    if (ratio < minimo) {
      const k = nome(el);
      if (!vistos.has(k)) { vistos.add(k); contraste.push({el: k, ratio: +ratio.toFixed(2), cor: cs.color, px: tam, peso}); }
    }
  });
  // --- emoji como icone (texto de interface, fora de conteudo do usuario)
  const reEmoji = /\p{Extended_Pictographic}/u;
  const emoji = [];
  todos.forEach(el => {
    if (!visivel(el)) return;
    [...el.childNodes].forEach(n => { if (n.nodeType === 3 && reEmoji.test(n.textContent)) emoji.push({el: nome(el), texto: n.textContent.trim().slice(0, 40)}); });
    const antes = getComputedStyle(el, '::before').content;
    if (antes && antes !== 'none' && reEmoji.test(antes)) emoji.push({el: nome(el) + '::before', texto: antes});
  });
  // --- hidden que nao some
  const hiddenVisivel = [];
  todos.forEach(el => { if (el.hasAttribute('hidden') && getComputedStyle(el).display !== 'none') hiddenVisivel.push(nome(el) + ' display=' + getComputedStyle(el).display); });
  // --- botao adicionar fora do padrao: botao com texto de adicionar sem .btn.btn-adicionar/.btn-primario/.btn-secundario
  const addFora = [];
  tocaveis.forEach(el => {
    if (!el.matches('button, a')) return;
    const t = el.textContent.trim().toLowerCase();
    if (/^(\+|nova|novo|adicionar|\+ adicionar|criar)/.test(t) && !(el.classList.contains('btn'))) addFora.push(nome(el));
  });
  // --- botoes crus (sem .btn nem estilo de componente) - aparencia antiga
  const crus = [];
  tocaveis.forEach(el => {
    if (el.tagName !== 'BUTTON' || !visivel(el)) return;
    if (el.classList.contains('btn') || el.classList.contains('dica-toggle') || el.classList.contains('btn-ouvir') || el.closest('.leaflet-container')) return;
    crus.push(nome(el) + ' bg=' + getComputedStyle(el).backgroundColor + ' h=' + Math.round(el.getBoundingClientRect().height));
  });
  const recolhivel = elems.some(e => e.matches('.secao-recolhivel') || e.querySelector('.secao-recolhivel'));
  const altura = elems.reduce((s, e) => s + (visivel(e) ? e.getBoundingClientRect().height : 0), 0);
  return {toque, contraste, emoji, hiddenVisivel, addFora, crus, recolhivel, altura: Math.round(altura)};
}
"""


def main():
    shots = "--screenshots" in sys.argv
    erros, falhas_rede = [], []
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True)
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        logar(ctx)
        rotas_de_rede(ctx)
        if not ctx.request.get(BASE + "/api/viagens").json():
            semear(ctx)
        page = ctx.new_page()
        ligar_coletores(page, erros, falhas_rede)
        page.goto(BASE + "/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)

        # Vida > Viagens/Lugares
        abrir_aba(page, "vida")
        page.wait_for_selector("#lista-viagens li", timeout=8000)
        page.wait_for_selector("#lista-lugares li", timeout=8000)
        # abre os 2 mapas (1 com coordenada, 1 "nao encontrado")
        for btn in page.query_selector_all("#lista-lugares .lugar-mapa-box > button"):
            btn.click()
        page.wait_for_selector("#lista-lugares .leaflet-container", timeout=8000)
        page.wait_for_timeout(600)
        res["viagens"] = page.evaluate(COLETOR, ["#tab-vida", "Viagens"])
        res["lugares"] = page.evaluate(COLETOR, ["#tab-vida", "Lugares que gostei"])
        page.click("#viagem-abrir-btn")
        page.wait_for_timeout(500)
        res["viagem_sheet"] = page.evaluate(COLETOR, ["#viagem-sheet", None])
        res["viagem_sheet_geo"] = page.evaluate("""() => { const s = document.querySelector('#viagem-sheet');
            const cs = getComputedStyle(s); const p = s.querySelector('.bottom-sheet-painel');
            return {bg: cs.backgroundColor, padding: cs.padding, border: cs.borderTopWidth,
                    fundo: !!s.querySelector('.bottom-sheet-fundo'), alca: !!s.querySelector('.bottom-sheet-alca'),
                    painelTop: Math.round(p.getBoundingClientRect().top), painelH: Math.round(p.getBoundingClientRect().height)}; }""")
        if shots:
            page.screenshot(path=os.path.join(AQUI, "c3b-viagem-sheet.png"))
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

        # Construtora > Cotacoes
        abrir_aba(page, "construtora")
        page.wait_for_selector("#lista-cotacoes li", timeout=8000)
        page.click("#lista-cotacoes .cotacao-cabecalho")
        page.wait_for_selector("#lista-cotacoes .cotacao-grafico", timeout=8000)
        res["cotacoes"] = page.evaluate(COLETOR, ["#tab-construtora", "Cotacoes"])

        # Aviacao
        abrir_aba(page, "aviacao")
        page.wait_for_selector("#lista-voos li", timeout=15000)
        page.fill("#metar-icao", "SBBI")
        page.click("#metar-btn")
        page.wait_for_selector("#metar-resultado:not([hidden])", timeout=8000)
        page.wait_for_timeout(500)
        res["aviacao"] = page.evaluate(COLETOR, ["#tab-aviacao", None])
        if shots:
            page.screenshot(path=os.path.join(AQUI, "c3b-aviacao.png"), full_page=False)
        b.close()

    falhas_amb = [f for f in falhas_rede if any(a in str(f[1]) for a in AMBIENTE)]
    falhas_rede = [f for f in falhas_rede if f not in falhas_amb]
    if not falhas_rede:
        erros = [e for e in erros if not e[1].startswith("Failed to load resource")]
    saida = {"erros_console": erros, "falhas_rede": falhas_rede, "falhas_ambiente": falhas_amb, "secoes": res}
    with open(os.path.join(AQUI, "auditoria-resultado.json"), "w") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)
    print(json.dumps(saida, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
