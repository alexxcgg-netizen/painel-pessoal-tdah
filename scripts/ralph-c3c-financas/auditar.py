"""Auditoria visual da faixa c3c-financas (Playwright headless 390x844).

Percorre Gastos (inclui Assinaturas e parcelas), Bancos, Construtora e Contas
pessoais (aba Vida) e lista: erro de console, alvo de toque < 44px, contraste
< 4.5:1, valor em R$ estourando a coluna, botao "adicionar" fora do padrao,
emoji usado como icone e inconsistencia com docs/MASTER.md.

Uso: PORTA=5133 python auditar.py [--json saida.json] [--screenshots]
Nao grava nada no banco real: o servidor (servidor.py) sobe num banco temporario.
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:" + os.environ.get("PORTA", "5133")
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
AMBIENTE = ("fonts.googleapis.com", "fonts.gstatic.com", "/api/summary/today", "cdn.pluggy.ai")

# Raizes auditadas por tela. Contas pessoais mora dentro da aba Vida: audita
# so os elementos da secao (irmaos entre o h2 e a lista) + o sheet dela.
TELAS = {
    "gastos": ["#tab-gastos", "#sheet-nova-assinatura", "#sheet-nova-parcela"],
    "bancos": ["#tab-bancos"],
    "construtora": ["#tab-construtora"],
    "contas-pessoais": ["@contas-pessoais", "#sheet-nova-conta-pessoal"],
}

JS_AUDITAR = r"""
(raizes) => {
  const achados = [];
  const uniq = new Set();
  function add(tipo, el, detalhe) {
    const id = el.id ? '#' + el.id : '';
    const cls = (el.className && typeof el.className === 'string') ? '.' + el.className.trim().split(/\s+/).slice(0,3).join('.') : '';
    const txt = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().replace(/\s+/g,' ').slice(0,40);
    const chave = tipo + '|' + el.tagName + id + cls + '|' + detalhe;
    if (uniq.has(chave)) return;
    uniq.add(chave);
    achados.push({tipo, el: el.tagName.toLowerCase() + id + cls, texto: txt, detalhe});
  }
  function visivel(el) {
    if (!el.isConnected) return false;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return false;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) === 0) return false;
    let p = el;
    while (p) { if (p.hidden) return false; p = p.parentElement; }
    return true;
  }
  function parseCor(s) {
    const m = s.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number);
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  }
  function lum(c) {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  }
  function fundoEfetivo(el) {
    const camadas = [];
    let p = el;
    while (p) {
      const c = parseCor(getComputedStyle(p).backgroundColor);
      if (c && c.a > 0) { camadas.push(c); if (c.a >= 1) break; }
      p = p.parentElement;
    }
    let base = {r: 0, g: 0, b: 0};
    for (let i = camadas.length - 1; i >= 0; i--) {
      const c = camadas[i];
      base = {r: c.r * c.a + base.r * (1 - c.a), g: c.g * c.a + base.g * (1 - c.a), b: c.b * c.a + base.b * (1 - c.a)};
    }
    return base;
  }
  function contraste(el) {
    const cs = getComputedStyle(el);
    const fg = parseCor(cs.color); if (!fg) return 21;
    const bg = fundoEfetivo(el);
    const fgm = {r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a)};
    const l1 = lum(fgm), l2 = lum(bg);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  }
  function elementosDaRaiz(sel) {
    if (sel === '@contas-pessoais') {
      const lista = document.getElementById('lista-contas-pessoais');
      if (!lista) return [];
      const out = [];
      let p = lista;
      // sobe irmaos ate o h2 "Contas pessoais"
      while (p) { out.push(p); if (p.tagName === 'H2') break; p = p.previousElementSibling; }
      return out;
    }
    const r = document.querySelector(sel);
    return r ? [r] : [];
  }
  const emojiRe = /\p{Extended_Pictographic}/u;
  let nDestaque = 0;
  for (const sel of raizes) {
    for (const raiz of elementosDaRaiz(sel)) {
      const todos = [raiz, ...raiz.querySelectorAll('*')];
      for (const el of todos) {
        if (!visivel(el)) continue;
        const tag = el.tagName;
        const cs = getComputedStyle(el);
        // --- toque
        const clicavel = tag === 'BUTTON' || (tag === 'A' && el.href) || tag === 'SELECT' ||
          (tag === 'INPUT' && el.type !== 'hidden' && el.type !== 'file') || (tag === 'LABEL' && el.htmlFor) ||
          el.getAttribute('role') === 'button' || tag === 'TEXTAREA' || (el.onclick != null) ||
          (el.classList.contains('chip') && cs.cursor === 'pointer');
        if (clicavel) {
          const r = el.getBoundingClientRect();
          // area estendida por ::after invisivel nao e medivel aqui: so reporta
          if (r.height < 44 || r.width < 44) add('toque<44', el, Math.round(r.width) + 'x' + Math.round(r.height));
          // botao nativo sem estilo (cinza/azul padrao do navegador)
          if (tag === 'BUTTON') {
            const bg = cs.backgroundColor;
            if (bg === 'rgb(239, 239, 239)' || bg === 'rgb(240, 240, 240)' || bg === 'buttonface' || bg === 'rgb(0, 0, 255)')
              add('master:botao-nativo', el, bg);
          }
        }
        // --- botao adicionar fora do padrao
        if (tag === 'BUTTON' || tag === 'A') {
          const t = (el.innerText || '').trim().toLowerCase();
          if (/^(\+|adicionar|nova |novo |criar|\+ )/.test(t) && !el.classList.contains('btn-adicionar'))
            add('adicionar-fora-do-padrao', el, t.slice(0, 30));
          if (el.classList.contains('btn-adicionar') && !el.classList.contains('btn'))
            add('adicionar-sem-classe-base', el, '');
        }
        // --- texto direto (nos de texto proprios)
        const textoProprio = Array.from(el.childNodes).filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').trim();
        if (textoProprio) {
          if (emojiRe.test(textoProprio)) add('emoji', el, textoProprio.slice(0, 30));
          const c = contraste(el);
          const grande = parseFloat(cs.fontSize) >= 24 || (parseFloat(cs.fontSize) >= 18.66 && Number(cs.fontWeight) >= 700);
          if (c < (grande ? 3 : 4.5)) add('contraste', el, c.toFixed(2) + ':1 ' + cs.color);
          // --- R$ estourando
          if (/R\$\s?-?[\d.]/.test(textoProprio)) {
            const r = el.getBoundingClientRect();
            if (r.right > window.innerWidth + 0.5 || el.scrollWidth > el.clientWidth + 1 && cs.overflow !== 'visible')
              add('R$-estoura', el, 'right=' + Math.round(r.right) + ' sw=' + el.scrollWidth + ' cw=' + el.clientWidth);
            let p = el.parentElement;
            while (p && p !== document.body) {
              const pr = p.getBoundingClientRect();
              const pcs = getComputedStyle(p);
              if (pr.width > 0 && (pcs.overflow !== 'visible' || pcs.borderTopWidth !== '0px' || p.classList.contains('card'))) {
                if (r.right > pr.right + 0.5 || r.left < pr.left - 0.5) add('R$-estoura', el, 'sai do pai ' + p.tagName.toLowerCase() + (p.id ? '#' + p.id : '') + ' (' + Math.round(r.right) + '>' + Math.round(pr.right) + ')');
                break;
              }
              p = p.parentElement;
            }
            if (!/Plex|mono/i.test(cs.fontFamily) && !/Sora/.test(cs.fontFamily.split(',')[0]) )
              add('master:numero-sem-mono', el, cs.fontFamily.split(',')[0]);
            else if (!/Plex|mono/i.test(cs.fontFamily)) add('master:numero-sem-mono', el, cs.fontFamily.split(',')[0]);
          }
          if (/\bNaN\b|\bundefined\b|\bnull\b/.test(textoProprio)) add('NaN/undefined', el, textoProprio.slice(0, 40));
        }
        // --- MASTER: li.item + .lista-item no mesmo elemento; card dentro de card dentro de card
        if (el.classList.contains('item') && el.classList.contains('lista-item')) add('master:item+lista-item', el, '');
        if (el.classList.contains('card') && el.parentElement && el.parentElement.closest('.card') && el.parentElement.closest('.card').parentElement.closest('.card'))
          add('master:card>card>card', el, '');
        if (el.classList.contains('card--destaque') || el.classList.contains('card-destaque')) nDestaque++;
        if (el.classList.contains('card-destaque')) add('master:classe-errada', el, '.card-destaque (use .card--destaque)');
        // emoji tambem via pseudo-elemento
        for (const ps of ['::before', '::after']) {
          const c = getComputedStyle(el, ps).content;
          if (c && c !== 'none' && c !== 'normal' && emojiRe.test(c)) add('emoji', el, ps + ' ' + c);
        }
      }
    }
  }
  if (nDestaque > 1) achados.push({tipo: 'master:>1-destaque', el: '-', texto: '', detalhe: String(nDestaque)});
  return achados;
}
"""


def logar(ctx):
    r = ctx.request.post(BASE + "/configurar-pin", data=json.dumps({"pin": "135790", "confirmacao": "135790"}),
                         headers={"Content-Type": "application/json"})
    if r.status != 200:
        r = ctx.request.post(BASE + "/login", data=json.dumps({"pin": "135790"}),
                             headers={"Content-Type": "application/json"})
    assert r.status == 200, r.text()


def semear(ctx):
    """Dado sintetico via API (assinatura/parcela/conta pessoal) - idempotente o bastante pra rodar de novo."""
    j = {"Content-Type": "application/json"}
    ja = ctx.request.get(BASE + "/api/financas/assinaturas").json().get("assinaturas", [])
    if not ja:
        ctx.request.post(BASE + "/api/financas/assinaturas", headers=j, data=json.dumps(
            {"nome": "Streaming de filmes", "valor": 39.9, "dia_cobranca": 28, "cartao_ou_forma": "nubank"}))
        ctx.request.post(BASE + "/api/financas/assinaturas", headers=j, data=json.dumps(
            {"nome": "Academia do bairro com nome bem comprido pra testar quebra", "valor": 129999.99,
             "dia_cobranca": 31, "cartao_ou_forma": "debito automatico"}))
        ctx.request.post(BASE + "/api/financas/parcelas", headers=j, data=json.dumps(
            {"descricao": "Geladeira", "n_parcelas": 10, "valor_total": 3200, "cartao": "nubank"}))
        ctx.request.post(BASE + "/api/contas-pessoais", headers=j, data=json.dumps(
            {"nome": "Internet", "dia_vencimento": 26, "valor": 119.9}))
        ctx.request.post(BASE + "/api/contas-pessoais", headers=j, data=json.dumps(
            {"nome": "Condominio", "dia_vencimento": 5, "valor": 987654.32}))


def abrir_aba(page, aba):
    page.click(f"button.tab-btn[data-tab='{aba}']")
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    time.sleep(1.0)


def main():
    saida_json = None
    if "--json" in sys.argv:
        saida_json = sys.argv[sys.argv.index("--json") + 1]
    screenshots = "--screenshots" in sys.argv
    erros, falhas_rede, achados = [], [], {}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True)
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        logar(ctx)
        semear(ctx)
        page = ctx.new_page()
        page.on("console", lambda m: erros.append(("console." + m.type, m.text)) if m.type == "error" else None)
        page.on("pageerror", lambda e: erros.append(("pageerror", str(e))))
        page.on("response", lambda resp: falhas_rede.append((resp.status, resp.url)) if resp.status >= 400 else None)
        page.on("requestfailed", lambda req: falhas_rede.append(("falhou", req.url)))
        page.goto(BASE + "/")
        page.wait_for_load_state("networkidle")
        time.sleep(1.0)
        for tela, raizes in TELAS.items():
            aba = "vida" if tela == "contas-pessoais" else tela
            abrir_aba(page, aba)
            achados[tela] = page.evaluate(JS_AUDITAR, raizes)
            # sheets: abre, audita, fecha
            sheets = [r for r in raizes if r.startswith("#sheet")]
            for s in sheets:
                btn = {"#sheet-nova-assinatura": "#btn-nova-assinatura", "#sheet-nova-parcela": "#btn-nova-parcela",
                       "#sheet-nova-conta-pessoal": "#btn-nova-conta-pessoal"}[s]
                page.locator(btn).scroll_into_view_if_needed()
                page.click(btn)
                time.sleep(0.5)
                achados[tela + s.replace("#", ":")] = page.evaluate(JS_AUDITAR, [s])
                geo = page.evaluate("""(s) => { const el = document.querySelector(s);
                    const p = el.querySelector('.bottom-sheet-painel') || el; const r = p.getBoundingClientRect();
                    return {top: r.top, bottom: r.bottom, h: r.height, vh: innerHeight}; }""", s)
                if geo["bottom"] > geo["vh"] + 1 or geo["top"] < 0:
                    achados[tela + s.replace("#", ":")].append({"tipo": "sheet-fora-da-tela", "el": s, "texto": "", "detalhe": json.dumps(geo)})
                if screenshots and s == "#sheet-nova-assinatura":
                    page.screenshot(path=os.path.join(AQUI, "sheet-assinatura.png"), animations="disabled")
                page.keyboard.press("Escape")
                time.sleep(0.4)
            if screenshots and tela == "gastos":
                page.evaluate("document.getElementById('assinaturas-financas-box').scrollIntoView()")
                time.sleep(0.3)
                page.screenshot(path=os.path.join(AQUI, "gastos-assinaturas.png"), animations="disabled")
            if screenshots and tela == "construtora":
                page.evaluate("window.scrollTo(0,0)")
                page.screenshot(path=os.path.join(AQUI, "construtora.png"), animations="disabled")
        # Construtora: lucro/margem/VGV nunca podem aparecer
        abrir_aba(page, "construtora")
        texto_constr = page.inner_text("#tab-construtora").lower()
        proibidos = [w for w in ("lucro", "margem", "vgv", "52.500", "28,4") if w in texto_constr]
        b.close()

    falhas_amb = [f for f in falhas_rede if any(a in str(f[1]) for a in AMBIENTE)]
    falhas_rede = [f for f in falhas_rede if f not in falhas_amb]
    if not falhas_rede:
        erros = [e for e in erros if not e[1].startswith("Failed to load resource")]
    res = {"erros_console": erros, "falhas_rede": falhas_rede, "construtora_proibidos_visiveis": proibidos,
           "achados": achados}
    if saida_json:
        json.dump(res, open(saida_json, "w"), indent=1, ensure_ascii=False)
    for tela, lst in achados.items():
        print(f"== {tela}: {len(lst)}")
        for a in lst:
            print(f"  {a['tipo']:<26} {a['el'][:60]:<60} {a['texto'][:28]!r:<30} {a['detalhe']}")
    print("console:", erros)
    print("rede:", falhas_rede)
    print("construtora proibidos:", proibidos)


if __name__ == "__main__":
    main()
