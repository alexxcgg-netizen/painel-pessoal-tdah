"""M1 rodada 2: verificacao no Playwright headless (390x844), porta 5141, banco temporario.

Reaproveita a trava de rede da C3a (scripts/ralph-c3a-vida/servidor.py + comum.proteger_rede):
servidor com ANTHROPIC/OPENAI_BASE_URL em 127.0.0.1:9 e chaves "teste-fake", /api/summary/today
dublado e toda requisicao do navegador pra fora do app abortada. Nenhuma chamada real.

Uso: PORTA=5141 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-m1-front/verificar_r2.py
     (sobe o servidor sozinho se a porta estiver livre)
"""
import os
import sys
import urllib.request

os.environ.setdefault("PORTA", "5141")
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), "ralph-c3a-vida"))
import comum  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

# Cor efetiva atras de um elemento: compoe os background-color (rgba / color(srgb ...)) do
# elemento ate a raiz. `razaoPiorCaso` soma, em cada camada com gradiente (--realce-superficie),
# o pico dele (3,5% de --text), que so clareia o fundo.
JS_CONTRASTE = r"""
(el) => {
  const parse = (s) => {
    let m = s.match(/rgba?\(([^)]+)\)/);
    if (m) { const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return [p[0]/255, p[1]/255, p[2]/255, p.length > 3 ? p[3] : 1]; }
    m = s.match(/color\(srgb ([^)]+)\)/);
    if (m) { const p = m[1].split(/[ \/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; }
    return [0, 0, 0, 0];
  };
  const camadas = [];
  for (let n = el; n && n.nodeType === 1; n = n.parentElement) { const cs = getComputedStyle(n); camadas.push([parse(cs.backgroundColor), cs.backgroundImage.includes('gradient')]); }
  const txt = parse(getComputedStyle(document.body).color);
  let cor = [0, 0, 0], comRealce = [0, 0, 0];
  for (const [c, grad] of camadas.reverse()) {
    cor = [0, 1, 2].map((i) => c[i] * c[3] + cor[i] * (1 - c[3]));
    comRealce = [0, 1, 2].map((i) => c[i] * c[3] + comRealce[i] * (1 - c[3]));
    if (grad) comRealce = [0, 1, 2].map((i) => txt[i] * 0.035 + comRealce[i] * 0.965);
  }
  const lum = (c) => { const l = c.map((v) => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4); return 0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2]; };
  const ph = parse(getComputedStyle(el, "::placeholder").color);
  const razao = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const hex = (c) => "#" + c.slice(0, 3).map((v) => Math.round(v * 255).toString(16).padStart(2, "0")).join("");
  return { fundo: hex(cor), placeholder: hex(ph), razao: +razao(ph, cor).toFixed(2), razaoPiorCaso: +razao(ph, comRealce).toFixed(2) };
}
"""


def main():
    srv = None
    try:
        urllib.request.urlopen(comum.BASE + "/", timeout=1)
    except Exception:
        srv = comum.subir_servidor()
    falhas = []
    erros_console = []
    try:
        with sync_playwright() as p:
            nav = p.chromium.launch(executable_path=comum.CHROME)
            ctx = nav.new_context(viewport={"width": 390, "height": 844})
            comum.logar(ctx)
            comum.semear(ctx)
            page = ctx.new_page()
            comum.proteger_rede(page)
            page.on("console", lambda m: m.type == "error" and erros_console.append(m.text))
            page.on("pageerror", lambda e: erros_console.append(str(e)))
            page.goto(comum.BASE + "/")
            page.wait_for_load_state("networkidle")
            for passo in PASSOS:
                falhas += passo(page) or []
            nav.close()
    finally:
        if srv:
            srv.terminate()
    ruido = [e for e in erros_console if not any(h in e for h in comum.HOSTS_IGNORADOS) and "net::ERR_FAILED" not in e]
    if ruido:
        falhas.append(f"{len(ruido)} erro(s) de console: {ruido[:5]}")
    bloqueadas = comum.saidas_bloqueadas()
    print("saidas bloqueadas no servidor:", len(bloqueadas))
    print("erros de console:", len(ruido))
    print("FALHAS:" if falhas else "OK: 0 falhas", *falhas, sep="\n  ")
    return 1 if falhas else 0


def ir_para_aba(page, aba):
    page.click(f'#tabbar [data-tab="{aba}"], [data-tab="{aba}"]')
    page.wait_for_selector(f"#tab-{aba}:not([hidden])")
    page.wait_for_timeout(300)


def passo_contraste(page):
    """H2: placeholder do .campo >= 4.5:1 no sheet (fundo sem e com foco) e num campo inline."""
    falhas = []
    ir_para_aba(page, "vida")
    page.click("#compra-abrir-btn")
    page.wait_for_selector("#sheet-compra.bottom-sheet--aberto")
    page.wait_for_timeout(400)
    campo = page.locator("#compra-item")
    for estado in ("focado", "sem foco"):
        if estado == "sem foco":
            page.evaluate("document.activeElement && document.activeElement.blur()")
        else:
            campo.focus()
        page.wait_for_timeout(250)  # transicao de fundo do .campo
        r = campo.evaluate(JS_CONTRASTE)
        print(f"contraste placeholder sheet ({estado}):", r)
        if r["razaoPiorCaso"] < 4.5:
            falhas.append(f"placeholder no sheet ({estado}) {r}")
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    return falhas


def passo_contraste_varredura(page):
    """H2: todo .campo com placeholder visivel, em cada aba, >= 4.5:1."""
    falhas, medidos = [], 0
    abas = page.eval_on_selector_all("#tabbar [data-tab], nav [data-tab]", "els => [...new Set(els.map(e => e.dataset.tab))]")
    for aba in abas:
        try:
            ir_para_aba(page, aba)
        except Exception:
            continue
        for campo in page.locator(f"#tab-{aba} .campo[placeholder]:visible").all():
            r = campo.evaluate(JS_CONTRASTE)
            medidos += 1
            if r["razao"] < 4.5:
                falhas.append(f"aba {aba}: {campo.evaluate('e => e.id || e.name || e.placeholder')} {r}")
    print(f"varredura de placeholder: {medidos} campos em {len(abas)} abas, {len(falhas)} abaixo de 4.5")
    return falhas


def passo_garantia_chip(page):
    """H3: a regra `.garantia-chip` do style.css existe no CSSOM (comentario nao engole mais) e o
    chip continua sem caixa-alta."""
    falhas = []
    tem = page.evaluate("""() => [...document.styleSheets].filter(s => (s.href || '').includes('/style.css'))
        .some(s => [...s.cssRules].some(r => r.selectorText === '.garantia-chip'))""")
    print("regra .garantia-chip no CSSOM do style.css:", tem)
    if not tem:
        falhas.append(".garantia-chip continua fora do CSSOM do style.css")
    ir_para_aba(page, "vida")
    chip = page.locator("#lista-garantias .garantia-chip").first
    chip.wait_for(state="attached", timeout=5000)
    tt = chip.evaluate("e => getComputedStyle(e).textTransform")
    print("text-transform do chip de garantia:", tt)
    if tt != "none":
        falhas.append(f"chip de garantia em caixa-alta ({tt})")
    return falhas


JS_TOQUE = r"""
(el) => {
  el.scrollIntoView({ block: "center" });
  const r = el.getBoundingClientRect();
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  const depois = getComputedStyle(el, "::after");
  const pontos = [[0, 0], [-20, 0], [20, 0], [0, -20], [0, 20], [-20, -20], [20, 20]];
  // Ponto "morto" = dentro dos 44px da dica mas o toque cai em algo que nao e controle. Cair
  // num controle vizinho (ex.: o cabecalho da secao logo acima, que corta o ::after pela borda
  // de cima do conteudo) e sobreposicao legitima, nao area perdida.
  const erros = pontos.filter(([dx, dy]) => {
    const alvo = document.elementFromPoint(cx + dx, cy + dy);
    if (alvo === el || el.contains(alvo)) return false;
    return !(alvo && alvo.closest("button, a[href], input, select, textarea, summary"));
  });
  const quem = erros.map(([dx, dy]) => {
    const a = document.elementFromPoint(cx + dx, cy + dy);
    return a ? a.tagName.toLowerCase() + (a.id ? "#" + a.id : "") + (a.className && a.className.baseVal === undefined ? "." + String(a.className).trim().split(/\s+/).join(".") : "") : "nada";
  });
  return { largura: depois.width, altura: depois.height, inset: depois.inset, falhos: erros.map(String), quem };
}
"""


def passo_toque_dica(page):
    """H4: a dica "!" de Viagens e Lugares tem 44px de toque CENTRADOS no botao (hit-test em
    +-20px do centro)."""
    falhas = []
    ir_para_aba(page, "vida")
    for secao in ("vida-viagens", "vida-lugares"):
        sec = page.locator(f'[data-secao-id="{secao}"]')
        if sec.get_attribute("data-aberto") != "true":
            sec.locator(".secao-cabecalho").first.click()
            page.wait_for_timeout(400)
        r = sec.locator(".dica-toggle").first.evaluate(JS_TOQUE)
        print(f"toque da dica em {secao}:", r)
        if r["falhos"]:
            falhas.append(f"{secao}: pontos fora da area de toque {r['falhos']}")
    return falhas


PASSOS = [passo_contraste, passo_contraste_varredura, passo_garantia_chip, passo_toque_dica]

if __name__ == "__main__":
    sys.exit(main())
