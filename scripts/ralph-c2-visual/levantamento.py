"""Levantamento visual da C2 (Playwright headless 390x844, app em banco de teste).

Uso: PORTA=5120 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-c2-visual/levantamento.py [--fotos]

Passa por Hoje, Painel, Tarefas, Vida (so Habitos/Projetos/Agenda, que sao da C2) e Assistente e
lista: erros de console/pageerror, alvos de toque < 44px, contraste de texto < 4.5:1 (WCAG, cores
computadas, fundo efetivo = pilha de background-color ate o <body>), botoes de "adicionar" fora
do .btn-adicionar, emoji em elemento de interface, secoes longas fora de .secao-recolhivel e
foco sem anel visivel. Resultado em levantamento-resultado.json (fora do commit).
Com --fotos, salva no maximo 2 PNG por aba nesta pasta (fora do commit).
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:" + os.environ.get("PORTA", "5120")
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
FOTOS = "--fotos" in sys.argv or "--fotos-cheias" in sys.argv
FOTOS_CHEIAS = "--fotos-cheias" in sys.argv  # so pra revisao local, nunca vai pro git
# Falhas de ambiente ja conhecidas das faixas V0a-P1b (sandbox sem CA do proxy no Chromium e IA duble).
AMBIENTE = ("fonts.googleapis.com", "fonts.gstatic.com", "/api/summary/today")

AUDITORIA_JS = r"""
(escopo) => {
  const raiz = document.querySelector(escopo.raiz);
  if (!raiz) return {erro: 'sem raiz ' + escopo.raiz};
  // Vida: so os blocos entre o h2 "Habitos" e o h2 da proxima secao que nao e da C2.
  let dentro = () => true;
  if (escopo.vida) {
    const meus = new Set();
    let ligado = false;
    for (const filho of raiz.children) {
      if (filho.tagName === 'H2') {
        const t = filho.textContent.trim();
        ligado = /^(Habitos|Projetos|Agenda)/.test(t);
      }
      if (ligado) meus.add(filho);
    }
    dentro = (el) => { for (const m of meus) if (m.contains(el)) return true; return false; };
  }
  const visivel = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return false;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) === 0) return false;
    return !el.closest('[hidden]');
  };
  const nome = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    else if (el.classList.length) s += '.' + [...el.classList].slice(0, 2).join('.');
    const t = (el.getAttribute('aria-label') || el.textContent || el.value || '').trim().replace(/\s+/g, ' ');
    return s + (t ? ' "' + t.slice(0, 28) + '"' : '');
  };
  const parse = (c) => {
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (!m) return [0, 0, 0, 0];
    const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  };
  const mistura = (topo, base) => {
    const a = topo[3];
    return [topo[0] * a + base[0] * (1 - a), topo[1] * a + base[1] * (1 - a), topo[2] * a + base[2] * (1 - a), 1];
  };
  const fundo = (el) => {
    const pilha = [];
    for (let e = el; e; e = e.parentElement) {
      const c = parse(getComputedStyle(e).backgroundColor);
      if (c[3] > 0) pilha.push(c);
      if (c[3] >= 1) break;
    }
    let cor = [0, 0, 0, 1];  // --bg #000
    for (let i = pilha.length - 1; i >= 0; i--) cor = mistura(pilha[i], cor);
    return cor;
  };
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  };
  const razao = (a, b) => { const la = lum(a), lb = lum(b); return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05); };
  const opacidade = (el) => { let o = 1; for (let e = el; e; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity); return o; };

  const saida = {toque: [], contraste: [], adicionar: [], emoji: [], longas: [], foco: []};
  const interativos = raiz.querySelectorAll('button, a[href], input:not([type=hidden]), select, textarea, summary, [role=button], label.chip, [tabindex="0"]');
  const vistos = new Set();
  for (const el of interativos) {
    if (!dentro(el) || !visivel(el)) continue;
    const r = el.getBoundingClientRect();
    // input checkbox/radio dentro de label: vale a area do label
    let alvo = r;
    if ((el.type === 'checkbox' || el.type === 'radio') && el.closest('label')) alvo = el.closest('label').getBoundingClientRect();
    if (Math.round(alvo.height) < 44 || Math.round(alvo.width) < 44) {
      const k = nome(el);
      if (!vistos.has(k)) { vistos.add(k); saida.toque.push(k + ' ' + Math.round(alvo.width) + 'x' + Math.round(alvo.height)); }
    }
    const txt = (el.textContent || '').trim();
    if (el.tagName === 'BUTTON' && /^(\+|adicionar|criar|nov[oa]\b)/i.test(txt) && !el.classList.contains('btn-adicionar'))
      saida.adicionar.push(nome(el));
    if (/\p{Extended_Pictographic}/u.test(txt) && !el.closest('.card-resultado, .chat-msg, .lista-item-corpo'))
      saida.emoji.push(nome(el));
  }
  // emoji em titulos/rotulos de interface
  for (const el of raiz.querySelectorAll('h2, h3, h4, label, .card-titulo, .secao-cabecalho, .chip, legend, th')) {
    if (!dentro(el) || !visivel(el)) continue;
    const proprio = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('');
    if (/\p{Extended_Pictographic}/u.test(proprio)) saida.emoji.push(nome(el));
  }
  // contraste: elementos com texto proprio
  const vistosC = new Set();
  const walker = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (!n.textContent.trim()) continue;
    const el = n.parentElement;
    if (!el || !dentro(el) || !visivel(el) || vistosC.has(el)) continue;
    if (el.closest('svg, script, style, option')) continue;
    vistosC.add(el);
    const cs = getComputedStyle(el);
    const cor = parse(cs.color);
    const o = opacidade(el);
    const fundoCor = fundo(el);
    const efetiva = mistura([cor[0], cor[1], cor[2], cor[3] * o], fundoCor);
    const rz = razao(efetiva, fundoCor);
    const grande = parseFloat(cs.fontSize) >= 24 || (parseFloat(cs.fontSize) >= 18.66 && parseInt(cs.fontWeight) >= 700);
    const minimo = grande ? 3 : 4.5;
    if (rz < minimo && !el.disabled && !el.closest('[disabled]')) {
      saida.contraste.push(nome(el) + ' ' + rz.toFixed(2) + ':1 cor=' + cs.color + ' op=' + o.toFixed(2) + ' fonte=' + cs.fontSize);
    }
  }
  // secoes longas (> 700px) fora de recolhivel
  for (const el of raiz.querySelectorAll('ul, ol, .card, form, section, .card-vida')) {
    if (!dentro(el) || !visivel(el)) continue;
    const h = el.getBoundingClientRect().height;
    if (h > 700 && !el.closest('.secao-recolhivel') && !el.querySelector('.secao-recolhivel'))
      saida.longas.push(nome(el) + ' ' + Math.round(h) + 'px');
  }
  saida.longas = saida.longas.slice(0, 8);
  return saida;
}
"""

ABAS = [
    ("hoje", {"raiz": "#tab-hoje"}),
    ("painel", {"raiz": "#tab-painel"}),
    ("tarefas", {"raiz": "#tab-tarefas"}),
    ("vida", {"raiz": "#tab-vida", "vida": True}),
    ("assistente", {"raiz": "#tab-assistente"}),
]


def semear(req):
    h = {"Content-Type": "application/json"}
    for t in ("Pagar boleto do condominio", "Ligar pro mecanico sobre a revisao", "Separar documentos do IR"):
        req.post(BASE + "/api/tasks", data=json.dumps({"titulo": t}), headers=h)
    req.post(BASE + "/api/tasks", data=json.dumps({"titulo": "Renovar CNH", "due_date": "2026-09-20"}), headers=h)
    for nome, meta in (("Beber agua", "8 copos"), ("Ler 10 paginas", ""), ("Caminhar", "30 min")):
        req.post(BASE + "/api/habitos", data=json.dumps({"nome": nome, "meta": meta, "frequencia_tipo": "diario"}), headers=h)
    for nome in ("Reforma da varanda", "Curso de ingles"):
        req.post(BASE + "/api/projetos", data=json.dumps({"nome": nome, "prazo_final": "2026-12-15"}), headers=h)
    req.post(BASE + "/api/lembretes", data=json.dumps({"titulo": "Aniversario da Ana", "data": "2026-10-02"}), headers=h)


def main():
    erros, rede = [], []
    resultado = {}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True)
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        h = {"Content-Type": "application/json"}
        r = ctx.request.post(BASE + "/configurar-pin", data=json.dumps({"pin": "135790", "confirmacao": "135790"}), headers=h)
        if r.status != 200:
            r = ctx.request.post(BASE + "/login", data=json.dumps({"pin": "135790"}), headers=h)
        assert r.status == 200, r.text()
        if not os.environ.get("SEM_SEMENTE"):
            semear(ctx.request)
        page = ctx.new_page()
        page.on("console", lambda m: erros.append(("console." + m.type, m.text)) if m.type == "error" else None)
        page.on("pageerror", lambda e: erros.append(("pageerror", str(e))))
        page.on("response", lambda resp: rede.append((resp.status, resp.url)) if resp.status >= 400 else None)
        page.on("requestfailed", lambda req: rede.append(("falhou", req.url)))
        page.goto(BASE + "/")
        page.wait_for_load_state("networkidle")
        time.sleep(1.5)
        for aba, escopo in ABAS:
            if aba != "hoje":
                page.click(f"button.tab-btn[data-tab='{aba}']")
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                time.sleep(1.2)
            resultado[aba] = page.evaluate(AUDITORIA_JS, escopo)
            # foco: Tab pelos primeiros elementos da aba e mede se algo muda no elemento focado
            sem_anel = []
            ids = page.evaluate("""(r) => [...document.querySelector(r).querySelectorAll('button, input:not([type=hidden]), select, textarea')]
                .filter(e => { const b = e.getBoundingClientRect(); return b.width && b.height && !e.closest('[hidden]') && !e.disabled; })
                .slice(0, 25).map((e, i) => { e.dataset.c2foco = r + String(i); return r + String(i); })""", escopo["raiz"])
            for i in ids:
                info = page.evaluate("""(i) => {
                    const e = document.querySelector('[data-c2foco="' + CSS.escape(i) + '"]');
                    const a = getComputedStyle(e); const antes = a.boxShadow + '|' + a.outlineStyle + a.outlineWidth + a.outlineColor + '|' + a.borderColor;
                    return {antes, nome: (e.id ? '#' + e.id : e.tagName.toLowerCase() + '.' + [...e.classList].slice(0,2).join('.')) + ' ' + (e.textContent||e.placeholder||'').trim().slice(0,20)};
                }""", i)
                page.keyboard.press("Shift")  # heuristica do :focus-visible: ultima interacao foi teclado
                page.evaluate("(i) => document.querySelector('[data-c2foco=\"' + CSS.escape(i) + '\"]').focus()", i)
                depois = page.evaluate("""(i) => {
                    const e = document.querySelector('[data-c2foco="' + CSS.escape(i) + '"]');
                    if (!e.matches(':focus-visible')) return 'sem-fv';
                    const a = getComputedStyle(e); return a.boxShadow + '|' + a.outlineStyle + a.outlineWidth + a.outlineColor + '|' + a.borderColor;
                }""", i)
                if depois != "sem-fv":
                    # anel "quase invisivel" do style.css: outline com --accent-2 (#08080a)
                    fraco = ("rgba(8, 8, 10" in depois and "box-shadow" not in depois and depois.split("|")[0] == info["antes"].split("|")[0])
                    if depois == info["antes"] or fraco:
                        sem_anel.append(info["nome"])
            resultado[aba]["foco"] = sem_anel
            page.keyboard.press("Escape")
            if FOTOS:
                page.evaluate("() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0); }")
                page.screenshot(path=os.path.join(AQUI, f"c2-{aba}.png"), animations="disabled", full_page=FOTOS_CHEIAS)
        b.close()
    erros_reais = [e for e in erros if not ("Failed to load resource" in e[1])]
    rede_reais = [x for x in rede if not any(a in x[1] for a in AMBIENTE)]
    resultado["_erros_console"] = erros_reais
    resultado["_rede"] = rede_reais
    with open(os.path.join(AQUI, "levantamento-resultado.json"), "w") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=1)
    for aba, _ in ABAS:
        r = resultado[aba]
        print(f"== {aba}: toque={len(r['toque'])} contraste={len(r['contraste'])} adicionar={len(r['adicionar'])} "
              f"emoji={len(r['emoji'])} longas={len(r['longas'])} foco_fraco={len(r['foco'])}")
    print("console:", erros_reais)
    print("rede:", rede_reais)


if __name__ == "__main__":
    main()
