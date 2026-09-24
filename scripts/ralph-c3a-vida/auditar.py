"""Auditoria da aba Vida (faixa C3a) no Playwright headless 390x844, banco de teste.

Percorre #tab-vida inteira (+ a secao painel/peso-e-medidas, que e desta faixa mas mora na
aba Painel) e cada bottom-sheet da faixa aberto, e lista:
  erros de console | alvo de toque < 44px | contraste < 4.5:1 (cores computadas, fundo
  composto subindo a arvore ate o --bg preto) | botao "adicionar" fora de .btn.btn-adicionar |
  emoji como icone | filho de .vida-secoes sem .secao-recolhivel | elemento com [hidden]
  que continua visivel | botao nativo sem estilo (fundo azul/cinza do navegador).

Uso: PORTA=5131 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-c3a-vida/auditar.py [--json]
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

import comum

# Donos por data-secao-id (donos.json) - pra saber o que e desta faixa.
OUTRAS = {"vida-habitos": "c2-visual", "vida-projetos": "c2-visual", "vida-agenda": "c2-visual",
          "vida-viagens": "c3b-viagens", "vida-lugares": "c3b-viagens", "vida-contas-pessoais": "c3c-financas"}

SHEETS = ["garantia", "ideia-presente", "pessoa", "ficha", "manutencao", "aprender", "salvo", "compra",
          "responder"]

JS_AUDITAR = r"""
(raizSel) => {
  const raizes = [...document.querySelectorAll(raizSel)];
  const achados = [];
  const parse = (s) => {
    const cs = s.match(/color\(srgb ([^)]+)\)/);
    if (cs) {
      const p = cs[1].split(/[ \/]+/).filter(Boolean).map(Number);
      return { r: p[0] * 255, g: p[1] * 255, b: p[2] * 255, a: p.length > 3 ? p[3] : 1 };
    }
    const m = s.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number);
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const misturar = (topo, base, a) => ({ r: topo.r * a + base.r * (1 - a), g: topo.g * a + base.g * (1 - a), b: topo.b * a + base.b * (1 - a) });
  const fundoDe = (el) => {
    const cadeia = [];
    let opac = 1;
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const cs = getComputedStyle(n);
      opac *= Number(cs.opacity);
      const c = parse(cs.backgroundColor);
      if (c && c.a > 0) cadeia.push(c);
    }
    let base = { r: 0, g: 0, b: 0 };
    for (let i = cadeia.length - 1; i >= 0; i--) base = misturar(cadeia[i], base, cadeia[i].a);
    return { base, opac };
  };
  const nome = (el) => {
    const id = el.id ? "#" + el.id : "";
    const cls = el.className && typeof el.className === "string" ? "." + el.className.trim().split(/\s+/).slice(0, 3).join(".") : "";
    const txt = (el.textContent || el.getAttribute("aria-label") || el.placeholder || "").trim().replace(/\s+/g, " ").slice(0, 30);
    return `${el.tagName.toLowerCase()}${id}${cls} "${txt}"`;
  };
  const secaoDe = (el) => {
    const s = el.closest("[data-secao-id]");
    if (s) return s.dataset.secaoId;
    const sh = el.closest(".bottom-sheet");
    return sh ? sh.id : "?";
  };
  const visivel = (el) => {
    if (!el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    // dentro de .secao-conteudo recolhida (max-height 0) nao e visivel de fato
    const cont = el.closest(".secao-conteudo");
    if (cont && cont.getBoundingClientRect().height < 1) return false;
    return true;
  };
  const emojiRe = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B50}\u{2B06}\u{2194}-\u{21FF}\u{2705}\u{274C}]/u;
  for (const raiz of raizes) {
    // alvo de toque
    raiz.querySelectorAll("button, a[href], input:not([type=hidden]), select, textarea, [role=button], summary").forEach((el) => {
      if (!visivel(el)) return;
      let alvo = el;
      if ((el.type === "checkbox" || el.type === "radio") && el.closest("label")) alvo = el.closest("label");
      let r = alvo.getBoundingClientRect();
      // area de toque real: se o retangulo e menor que 44, testa o hit-test a 21px do centro
      // (cobre ::after invisivel que amplia a area, como o MASTER permite)
      let ok = r.height >= 44 && r.width >= 44;
      if (!ok) {
        alvo.scrollIntoView({ block: "center" });
        r = alvo.getBoundingClientRect();
        const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        const bate = (x, y) => { const h = document.elementFromPoint(x, y); return h && (h === alvo || alvo.contains(h)); };
        ok = (r.width >= 44 || (bate(cx - 21, cy) && bate(cx + 21, cy))) && (r.height >= 44 || (bate(cx, cy - 21) && bate(cx, cy + 21)));
      }
      if (!ok)
        achados.push({ tipo: "toque", secao: secaoDe(el), el: nome(el), medida: `${Math.round(r.width)}x${Math.round(r.height)}` });
      const cs = getComputedStyle(el);
      if (el.tagName === "BUTTON" && (cs.appearance === "auto" || cs.appearance === "button") && cs.borderStyle === "outset")
        achados.push({ tipo: "botao-nativo", secao: secaoDe(el), el: nome(el) });
    });
    // contraste: todo elemento com texto proprio (no de texto direto)
    raiz.querySelectorAll("*").forEach((el) => {
      if (!visivel(el)) return;
      const temTexto = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 0);
      const ehCampo = el.matches("input:not([type=checkbox]):not([type=radio]):not([type=file]), select, textarea");
      if (!temTexto && !ehCampo) return;
      const cs = getComputedStyle(el);
      const cor = parse(cs.color);
      if (!cor) return;
      const { base, opac } = fundoDe(el);
      const final = misturar(cor, base, cor.a * opac);
      const l1 = lum(final), l2 = lum(base);
      const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
      const px = parseFloat(cs.fontSize), peso = Number(cs.fontWeight);
      const grande = px >= 24 || (px >= 18.66 && peso >= 700);
      if (ratio < (window.__LIMIAR || 4.5))
        achados.push({ tipo: "contraste", secao: secaoDe(el), el: nome(el), ratio: Math.round(ratio * 100) / 100,
          fonte: `${px}px/${peso}`, grande, cor: cs.color, opac: Math.round(opac * 100) / 100 });
      // placeholder
      if (ehCampo && el.placeholder && !el.value) {
        const ph = parse(getComputedStyle(el, "::placeholder").color);
        if (ph) {
          const f2 = misturar(ph, base, ph.a * opac);
          const rr = (Math.max(lum(f2), l2) + 0.05) / (Math.min(lum(f2), l2) + 0.05);
          if (rr < 4.5) achados.push({ tipo: "contraste-placeholder", secao: secaoDe(el), el: nome(el), ratio: Math.round(rr * 100) / 100 });
        }
      }
      if (temTexto && emojiRe.test(el.textContent) && (el.closest("button") || el.matches(".chip, .item-titulo, h2, h3, .secao-cabecalho")))
        achados.push({ tipo: "emoji", secao: secaoDe(el), el: nome(el) });
    });
    // botao adicionar fora do padrao (fora de sheet)
    raiz.querySelectorAll("button").forEach((b) => {
      if (!visivel(b) || b.closest(".bottom-sheet")) return;
      const t = (b.textContent || "").trim().toLowerCase();
      if (/^(\+\s*)?(adicionar|nova|novo|criar|salvar link|\+)/.test(t) && !(b.classList.contains("btn") && b.classList.contains("btn-adicionar")))
        achados.push({ tipo: "adicionar-fora-padrao", secao: secaoDe(b), el: nome(b) });
      if (b.classList.contains("btn-adicionar") && !b.getAttribute("aria-controls") && !b.dataset.abreSheet && !/abrir-btn$/.test(b.id))
        achados.push({ tipo: "adicionar-sem-sheet", secao: secaoDe(b), el: nome(b) });
    });
    // [hidden] que continua visivel
    raiz.querySelectorAll("[hidden]").forEach((el) => {
      const cs = getComputedStyle(el);
      if (cs.display !== "none") achados.push({ tipo: "hidden-visivel", secao: secaoDe(el), el: nome(el), display: cs.display });
    });
    // filhos de .vida-secoes sem .secao-recolhivel
    raiz.querySelectorAll(".vida-secoes > *").forEach((el) => {
      if (el.matches(".secao-recolhivel, .bottom-sheet")) return;
      achados.push({ tipo: "sem-recolhivel", secao: secaoDe(el), el: nome(el), altura: Math.round(el.getBoundingClientRect().height) });
    });
  }
  return achados;
}
"""


def main():
    srv = comum.subir_servidor()
    erros, rede, achados = [], [], []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=comum.CHROME, headless=True)
            ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
            comum.logar(ctx)
            print("seed", comum.semear(ctx), file=sys.stderr)
            page = ctx.new_page()
            comum.ligar_coleta(page, erros, rede)
            comum.dubles_leitura(page)
            comum.abrir_vida(page)
            if os.environ.get("LIMIAR"):
                page.evaluate(f"window.__LIMIAR = {os.environ['LIMIAR']}")
            # abre as secoes recolhidas pra auditar tudo, e as dicas colapsaveis
            page.evaluate("""() => document.querySelectorAll('#tab-vida .secao-recolhivel[data-aberto="false"] > .secao-cabecalho').forEach(b => b.click())""")
            time.sleep(0.5)
            # rola a aba inteira (lazy/observers)
            altura = page.evaluate("document.documentElement.scrollHeight")
            for y in range(0, altura, 600):
                page.evaluate(f"window.scrollTo(0,{y})")
                time.sleep(0.05)
            achados += page.evaluate(JS_AUDITAR, "#tab-vida")
            # sheets da faixa
            for s in SHEETS:
                page.evaluate(f"window.abrirBottomSheet('sheet-{s}')")
                time.sleep(0.35)
                achados += page.evaluate(JS_AUDITAR, f"#sheet-{s}")
                page.keyboard.press("Escape")
                time.sleep(0.3)
            # peso-e-medidas (aba Painel)
            page.click('.tab-btn[data-tab="painel"]')
            time.sleep(2.0)  # espera a animacao de entrada dos li.item (opacity) terminar
            achados += page.evaluate(JS_AUDITAR, '[data-secao-id="painel-peso-e-medidas"]')
            page.evaluate("window.abrirBottomSheet('sheet-medida')")
            time.sleep(0.35)
            achados += page.evaluate(JS_AUDITAR, "#sheet-medida")
            page.keyboard.press("Escape")
            time.sleep(0.3)
            b.close()
    finally:
        srv.terminate()
    for a in achados:
        a["dono"] = OUTRAS.get(a.get("secao"), "c3a")
    res = {"erros_console": erros, "rede_4xx5xx": [r for r in rede if not any(h in str(r[1]) for h in comum.HOSTS_IGNORADOS)],
           "achados": achados}
    if "--json" in sys.argv:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print("erros console:", len(erros))
        for e in erros:
            print("  ", e)
        print("rede:", res["rede_4xx5xx"])
        print("rede (bruta, inclui hosts ignorados):", sorted(set(map(str, rede)))[:10])
        vistos = set()
        for a in sorted(achados, key=lambda x: (x["dono"], x["tipo"], x.get("secao", ""))):
            chave = (a["dono"], a["tipo"], a.get("secao"), a["el"][:50])
            if chave in vistos:
                continue
            vistos.add(chave)
            extra = {k: v for k, v in a.items() if k not in ("dono", "tipo", "secao", "el")}
            print(f"[{a['dono']}] {a['tipo']:<22} {a.get('secao', ''):<28} {a['el'][:70]} {extra}")


if __name__ == "__main__":
    main()
