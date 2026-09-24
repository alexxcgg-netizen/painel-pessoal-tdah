"""Fuzz leve de UI da C2 (Playwright headless 390x844, app em banco de teste, nunca o real).

Uso: PORTA=5120 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-c2-visual/fuzz.py

Cenarios (cada um conta 1): abrir/fechar bottom-sheet rapido (clique duplo, ESC, fundo,
reabrir durante a animacao), recolher/abrir secao em rajada, troca de aba em rajada, Caixa
do assistente com a API devolvendo 500 / JSON malformado / formato inesperado (page.route),
Regras/Avisos idem, strings gigantes, unicode e HTML nos campos (captura, chat, sheets).
Depois de cada cenario confere invariantes (sheet fechado = escondido e de volta no lugar,
body sem trava de scroll, aria-expanded == data-aberto). Resultado: 0 erro de console e 0
excecao, fora "Failed to load resource" (o proprio navegador loga todo 4xx/5xx que o cenario
provoca de proposito) e as falhas de ambiente ja conhecidas (fontes/IA duble).
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:" + os.environ.get("PORTA", "5120")
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
SHEETS = [  # (aba, botao que abre, id do sheet)
    ("vida", "#habito-abrir-btn", "habito-sheet"),
    ("vida", "#projeto-abrir-btn", "projeto-sheet"),
    ("vida", "#evento-abrir-btn", "evento-sheet"),
    ("tarefas", "#tarefa-abrir-btn", "tarefa-sheet"),
    ("painel", "#lembrete-abrir-btn", "lembrete-sheet"),
    ("painel", "#medicamento-abrir-btn", "medicamento-sheet"),
    ("painel", "#espera-abrir-btn", "espera-sheet"),
    ("painel", "#diario-decisao-abrir-btn", "diario-decisao-sheet"),
]
GIGANTE = "Á🙂<b>x</b>&\"'" * 6000  # ~66 mil caracteres com unicode, emoji e HTML
ESTRANHOS = ["", " ", "​", "<script>alert(1)</script>", "'; DROP TABLE tasks;--", "🙂" * 500,
             "a\nb\tc", "%s%n{}[]", "0" * 5000]

erros = []
atual = {"nome": ""}
resultados = []


def ok_console(m):
    if m.type != "error":
        return
    if "Failed to load resource" in m.text:
        return
    erros.append((atual["nome"], "console", m.text[:300]))


def invariantes(page):
    return page.evaluate("""() => {
      const r = [];
      const abertos = [...document.querySelectorAll('.bottom-sheet.bottom-sheet--aberto')];
      for (const s of document.querySelectorAll('.bottom-sheet')) {
        const aberto = s.classList.contains('bottom-sheet--aberto');
        if (!aberto && !s.hidden && !s.classList.contains('bottom-sheet--fechando')) r.push('sheet visivel sem estar aberto: ' + s.id);
        if (aberto && s.hidden) r.push('sheet aberto mas hidden: ' + s.id);
        if (!aberto && !s.classList.contains('bottom-sheet--fechando') && s.parentElement === document.body) r.push('sheet fechado ficou no body: ' + s.id);
      }
      if (!abertos.length && document.body.classList.contains('bottom-sheet-bloqueado')) r.push('body travado sem sheet aberto');
      for (const sec of document.querySelectorAll('.secao-recolhivel')) {
        const cab = sec.querySelector(':scope > .secao-cabecalho');
        if (cab && cab.getAttribute('aria-expanded') !== String(sec.dataset.aberto === 'true')) r.push('aria-expanded != data-aberto: ' + (sec.dataset.secaoId || '?'));
      }
      for (const t of document.querySelectorAll('.tab-content[hidden]')) {
        if (getComputedStyle(t).display !== 'none') r.push('aba escondida visivel: ' + t.id);
      }
      return r;
    }""")


def cenario(page, nome, fn):
    atual["nome"] = nome
    antes = len(erros)
    try:
        fn(page)
        # deixa a animacao de fechar (240ms) e os fetch terminarem. No Chromium headless (sem
        # GPU) o blur da barra de abas deixa quadro longo e o setTimeout de 240ms pode atrasar
        # bem - entao espera o estado assentar (ate 3s) antes de acusar invariante quebrada.
        inv = []
        for _ in range(12):
            page.wait_for_timeout(250)
            inv = invariantes(page)
            if not inv:
                break
        for x in inv:
            erros.append((nome, "invariante", x))
    except Exception as e:  # noqa: BLE001 - qualquer falha do cenario conta como erro
        erros.append((nome, "script", repr(e)[:300]))
    resultados.append((nome, len(erros) == antes))


def ir(page, aba):
    page.evaluate("() => { document.querySelectorAll('.bottom-sheet--aberto').forEach(s => window.fecharBottomSheet(s)); }")
    page.wait_for_timeout(300)
    page.click(f"button.tab-btn[data-tab='{aba}']")
    page.wait_for_timeout(500)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True)
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        h = {"Content-Type": "application/json"}
        r = ctx.request.post(BASE + "/login", data=json.dumps({"pin": "135790"}), headers=h)
        if r.status != 200:
            ctx.request.post(BASE + "/configurar-pin", data=json.dumps({"pin": "135790", "confirmacao": "135790"}), headers=h)
        page = ctx.new_page()
        page.on("console", ok_console)
        page.on("pageerror", lambda e: erros.append((atual["nome"], "pageerror", str(e)[:300])))
        page.goto(BASE + "/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)

        # ---- 1) bottom-sheets: 6 padroes x 8 sheets = 48 cenarios ----
        for aba, botao, sid in SHEETS:
            ir(page, aba)

            def abre_esc(pg, botao=botao):
                pg.click(botao)
                pg.keyboard.press("Escape")

            def duplo(pg, botao=botao, sid=sid):
                pg.click(botao)
                pg.evaluate("(id) => window.abrirBottomSheet(id)", sid)
                pg.keyboard.press("Escape")

            def fundo(pg, botao=botao):
                pg.click(botao)
                pg.wait_for_timeout(350)
                pg.mouse.click(195, 40)  # fundo escurecido, fora do painel

            def reabre_na_animacao(pg, sid=sid):
                pg.evaluate("""(id) => { window.abrirBottomSheet(id); window.fecharBottomSheet(id);
                               window.abrirBottomSheet(id); }""", sid)
                pg.wait_for_timeout(400)
                aberto = pg.evaluate("(id) => { const s = document.getElementById(id); return !s.hidden && s.classList.contains('bottom-sheet--aberto'); }", sid)
                if not aberto:
                    raise AssertionError("reabriu durante a animacao e ficou fechado")
                pg.keyboard.press("Escape")

            def rajada(pg, sid=sid):
                pg.evaluate("""(id) => { for (let i = 0; i < 25; i++) { window.abrirBottomSheet(id);
                               if (i % 2) window.fecharBottomSheet(id); } window.fecharBottomSheet(id); }""", sid)

            def gigante_cancela(pg, botao=botao, sid=sid):
                pg.click(botao)
                pg.wait_for_timeout(300)
                pg.evaluate("""([id, txt]) => { const s = document.getElementById(id);
                    s.querySelectorAll('input[type=text], textarea').forEach(i => { i.value = txt; i.dispatchEvent(new Event('input', {bubbles: true})); }); }""", [sid, GIGANTE])
                cancelar = page.locator(f"#{sid} .btn-secundario").first
                cancelar.click()

            for nome, fn in (("abre+ESC", abre_esc), ("abre 2x+ESC", duplo), ("toque no fundo", fundo),
                             ("reabre na animacao", reabre_na_animacao), ("rajada 25x", rajada),
                             ("texto gigante+cancelar", gigante_cancela)):
                cenario(page, f"sheet {sid}: {nome}", fn)

        # ---- 2) salvar com strings estranhas (servidor valida; UI nao pode quebrar) ----
        ir(page, "tarefas")
        for i, txt in enumerate(ESTRANHOS):
            def salvar_tarefa(pg, txt=txt):
                pg.click("#tarefa-abrir-btn")
                pg.wait_for_timeout(300)
                pg.fill("#nova-tarefa-titulo", txt)
                pg.evaluate("() => document.getElementById('nova-tarefa-form').requestSubmit()")
                pg.wait_for_timeout(700)
                pg.keyboard.press("Escape")
            cenario(page, f"tarefa com texto estranho #{i}", salvar_tarefa)

        ir(page, "painel")

        def espera_gigante(pg):
            pg.click("#espera-abrir-btn")
            pg.wait_for_timeout(300)
            pg.evaluate("(t) => { document.getElementById('espera-quem').value = t; document.getElementById('espera-sobre').value = t; document.getElementById('espera-form').requestSubmit(); }", GIGANTE)
            pg.wait_for_timeout(900)
            pg.keyboard.press("Escape")
        cenario(page, "espera com texto gigante (servidor)", espera_gigante)

        # ---- 3) secoes recolhiveis em rajada ----
        for sid in ("painel-memoria-rotina-planos", "painel-memoria-fora-do-painel"):
            def rajada_secao(pg, sid=sid, n=11):
                cab = pg.locator(f"[data-secao-id='{sid}'] > .secao-cabecalho")
                for _ in range(n):
                    cab.click(delay=0)
            cenario(page, f"secao {sid}: 11 cliques rapidos", rajada_secao)
            cenario(page, f"secao {sid}: teclado Enter/Espaco", lambda pg, sid=sid: (
                pg.focus(f"[data-secao-id='{sid}'] > .secao-cabecalho"),
                pg.keyboard.press("Enter"), pg.keyboard.press(" "), pg.keyboard.press("Enter")))

        ir(page, "assistente")
        for sid in ("assistente-avisos-tipos", "caixa-historico"):
            def rajada_secao2(pg, sid=sid):
                cab = pg.locator(f"[data-secao-id='{sid}'] > .secao-cabecalho")
                for _ in range(9):
                    cab.click(delay=0)
            cenario(page, f"secao {sid}: 9 cliques rapidos", rajada_secao2)

        # ---- 4) troca de aba em rajada ----
        def abas_rajada(pg):
            for aba in ["hoje", "painel", "vida", "tarefas", "assistente", "painel", "hoje", "assistente", "vida", "hoje"]:
                pg.click(f"button.tab-btn[data-tab='{aba}']", delay=0)
        cenario(page, "troca de aba em rajada (10)", abas_rajada)

        # ---- 5) Caixa/Regras/Avisos com API quebrada (page.route) ----
        respostas = [
            ("500", {"status": 500, "content_type": "application/json", "body": json.dumps({"error": "falha simulada"})}),
            ("JSON malformado", {"status": 200, "content_type": "application/json", "body": "{itens: [1, 2,"}),
            ("HTML no lugar de JSON", {"status": 200, "content_type": "text/html", "body": "<html>erro</html>"}),
            ("formato inesperado (lista)", {"status": 200, "content_type": "application/json", "body": "[1, null, \"x\"]"}),
            ("itens com campos lixo", {"status": 200, "content_type": "application/json",
                                       "body": json.dumps({"itens": [{"id": None, "tipo": {}, "titulo": 5, "opcoes": "x"},
                                                                     {"id": 9, "tipo": "pergunta", "titulo": GIGANTE[:3000], "opcoes": [None, {}, 3]}],
                                                           "pendentes": "muitos", "tipos": [None, {"tipo": 1}], "regras": [{}]})}),
            ("vazio 204", {"status": 204, "body": ""}),
        ]
        for rotulo, resp in respostas:
            def api_quebrada(pg, resp=resp):
                handler = lambda route: route.fulfill(**resp)  # noqa: E731
                pg.route("**/api/assistente/**", handler)
                try:
                    # recarrega a faixa da Hoje e a aba Assistente inteira com a API quebrada
                    pg.click("button.tab-btn[data-tab='hoje']")
                    pg.wait_for_timeout(300)
                    pg.click("button.tab-btn[data-tab='assistente']")
                    pg.wait_for_timeout(700)
                    for sel in ("#tab-assistente .caixa-item-opcao", "#tab-assistente .regra-pausar",
                                "#tab-assistente .aviso-ligado", "#caixa-compacta-lista .caixa-item-opcao"):
                        loc = pg.locator(sel).first
                        if loc.count() and loc.is_visible():
                            loc.click()
                            pg.wait_for_timeout(300)
                    if pg.locator("#avisos-silencio-form .btn").is_visible():
                        pg.click("#avisos-silencio-form .btn")
                        pg.wait_for_timeout(300)
                finally:
                    pg.unroute("**/api/assistente/**", handler)
            cenario(page, f"Assistente com API {rotulo}", api_quebrada)

        # responder na Caixa com o POST devolvendo 500 depois de a lista ter carregado certo
        def responder_500(pg):
            pg.click("button.tab-btn[data-tab='hoje']")
            pg.wait_for_timeout(600)
            handler = lambda route: route.fulfill(status=500, content_type="application/json", body="{}")  # noqa: E731
            pg.route("**/api/assistente/caixa/*/responder", handler)
            try:
                loc = pg.locator("#caixa-compacta-lista .caixa-item-opcao").first
                if loc.count():
                    loc.click()
                    loc.click(force=True) if loc.count() and loc.is_visible() else None
                pg.wait_for_timeout(500)
            finally:
                pg.unroute("**/api/assistente/caixa/*/responder", handler)
        cenario(page, "Caixa: responder com POST 500", responder_500)

        # ---- 6) campos de texto fora dos sheets com texto gigante ----
        for sel in ("#captura-input", "#chat-input"):
            def campo_gigante(pg, sel=sel):
                pg.click("button.tab-btn[data-tab='hoje']")
                pg.wait_for_timeout(300)
                pg.evaluate("([s, t]) => { const i = document.querySelector(s); i.value = t; i.dispatchEvent(new Event('input', {bubbles: true})); }", [sel, GIGANTE])
                pg.evaluate("(s) => { document.querySelector(s).value = ''; }", sel)
            cenario(page, f"{sel} com texto gigante", campo_gigante)

        b.close()

    total = len(resultados)
    falhos = [n for n, okk in resultados if not okk]
    print(f"cenarios: {total}  ok: {total - len(falhos)}  com erro: {len(falhos)}")
    for e in erros[:40]:
        print("  ERRO", e)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fuzz-resultado.json"), "w") as f:
        json.dump({"cenarios": total, "falhos": falhos, "erros": erros}, f, ensure_ascii=False, indent=1)
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
