"""Fuzz de UI da aba Vida (faixa C3a) - Playwright headless 390x844, banco de teste.

Cenarios (>= 40): abrir/fechar bottom-sheet rapido, ESC (com e sem sheet aberto), toque no
fundo, recolher/abrir secao em rajada, dica "!" em rajada, salvar com a API devolvendo 500,
JSON invalido e formato errado (page.route), GET de lista com 500/JSON invalido/formato
errado no carregamento, strings gigantes, duplo clique no salvar. Meta: 0 erro de console do
app e 0 excecao (pageerror). "Failed to load resource" (log do proprio navegador pra resposta
4xx/5xx que o cenario provocou de proposito, e fontes externas sem internet no sandbox) e
contado a parte.

Uso: PORTA=5131 /home/user/painel-pessoal-tdah/.venv/bin/python scripts/ralph-c3a-vida/fuzz.py
"""
import json
import sys
import time
import traceback

from playwright.sync_api import sync_playwright

import comum

GIGANTE = "Ação ç ñ 😀 <b>x</b> ' \" \\ " * 400  # ~10k chars, unicode, HTML e aspas

# sheet -> (botao que abre, id do form, id do submit, campos {seletor: valor}, rota do POST)
SHEETS = {
    "garantia": ("#garantia-abrir-btn", "#garantia-form", "#garantia-btn",
                 {"#garantia-produto": "Micro-ondas", "#garantia-data-compra": "2026-01-10",
                  "#garantia-prazo": "12"}, "/api/garantias"),
    "ideia-presente": ("#ideia-presente-abrir-btn", "#ideia-presente-form", "#ideia-presente-btn",
                       {"#ideia-presente-pessoa": "Pai", "#ideia-presente-ideia": "Relogio"},
                       "/api/ideias-presente"),
    "pessoa": ("#pessoa-abrir-btn", "#pessoa-form", "#pessoa-btn", {"#pessoa-nome": "Ana"}, "/api/pessoas"),
    "manutencao": ("#manutencao-abrir-btn", "#manutencao-form", "#manutencao-btn",
                   {"#manutencao-item": "Ar-condicionado", "#manutencao-meses": "6"}, "/api/manutencoes"),
    "aprender": ("#aprender-abrir-btn", "#aprender-form", "#aprender-btn", {"#aprender-tema": "Excel"},
                 "/api/aprender"),
    "salvo": ("#salvo-abrir-btn", "#salvo-form", "#salvo-btn", {"#salvo-url": "https://exemplo.com.br/a"},
              "/api/salvos"),
    "compra": ("#compra-abrir-btn", "#compra-form", "#compra-btn", {"#compra-item": "Arroz"}, "/api/compras"),
    "responder": ("#responder-abrir-btn", "#responder-form", "#responder-btn", {"#responder-quem": "Bia"},
                  "/api/responder"),
    "ficha": ("#ficha-abrir-btn", "#ficha-form", "#ficha-btn", {"#ficha-grupo": "Costas"}, "/api/treino/fichas"),
}

GETS_LISTA = ["/api/garantias", "/api/ideias-presente", "/api/pessoas", "/api/treino/fichas", "/api/manutencoes",
              "/api/aprender", "/api/salvos", "/api/compras", "/api/responder", "/api/assinaturas/revisao",
              "/api/progresso?dias=30", "/api/uso-apps?dias=7", "/api/revisao-mensal", "/api/treino"]

resultados = []  # (nome, ok, detalhe)
erros_app = []   # (cenario, tipo, texto)
ruido_rede = [0]
cenario_atual = [""]


def coletar(page):
    def no_console(m):
        if m.type != "error":
            return
        if "Failed to load resource" in m.text:
            ruido_rede[0] += 1
            return
        erros_app.append((cenario_atual[0], "console.error", m.text))
    page.on("console", no_console)
    page.on("pageerror", lambda e: erros_app.append((cenario_atual[0], "pageerror", str(e))))


def cenario(nome):
    def deco(fn):
        fn.nome = nome
        return fn
    return deco


def responde(status, corpo, so_post=False):
    """Handler de page.route que devolve status/corpo fixos (fabrica, pra nao cair na
    armadilha do lambda com parametro padrao: o Playwright chama handler(route, request))."""
    def handler(route, _request=None):
        if so_post and route.request.method != "POST":
            return route.continue_()
        return route.fulfill(status=status, content_type="application/json", body=corpo)
    return handler


def esperar_fechado(page, sid, ms=1500):
    page.wait_for_function(f"document.getElementById('sheet-{sid}').hidden === true", timeout=ms)


def esperar_aberto(page, sid, ms=1500):
    page.wait_for_function(
        f"(() => {{ const s = document.getElementById('sheet-{sid}'); return !s.hidden && s.classList.contains('bottom-sheet--aberto'); }})()",
        timeout=ms)


def abrir_sheet(page, sid):
    btn = SHEETS[sid][0]
    page.locator(btn).scroll_into_view_if_needed()
    page.click(btn)
    esperar_aberto(page, sid)


def preencher(page, sid):
    for sel, val in SHEETS[sid][3].items():
        page.fill(sel, val)
    if sid == "ficha":
        page.fill("#ficha-ex-nome", "Remada curvada")
        page.fill("#ficha-ex-series", "3")
        page.fill("#ficha-ex-reps", "10")
        page.click("#ficha-ex-add-btn")


def fechar_tudo(page):
    for _ in range(3):
        if not page.evaluate("!!document.querySelector('.bottom-sheet--aberto')"):
            break
        page.keyboard.press("Escape")
        time.sleep(0.3)
    page.evaluate("limparErro && limparErro()")


def botao_restaurado(page, sid):
    return page.evaluate(f"(() => {{ const b = document.querySelector('{SHEETS[sid][2]}'); return !b.disabled && !b.querySelector('.spinner'); }})()")


def montar_cenarios():
    cen = []
    for sid in SHEETS:
        @cenario(f"{sid}: abrir/fechar rapido 8x (botao + Cancelar, inclusive durante o fechamento)")
        def c1(page, sid=sid):
            page.locator(SHEETS[sid][0]).scroll_into_view_if_needed()
            for _ in range(8):
                # clique "cru" (sem esperar o botao ficar estavel/livre) = dedo apressado
                page.evaluate(f"document.querySelector('{SHEETS[sid][0]}').click()")
                time.sleep(0.03)
                page.evaluate(f"document.querySelector('#sheet-{sid} [id$=cancelar-btn]').click()")
                time.sleep(0.03)
            esperar_fechado(page, sid, 2500)
            time.sleep(0.3)
            # nao pode ter ficado preso: abre e fecha de novo pelo caminho normal
            abrir_sheet(page, sid)
            page.click(f"#sheet-{sid} [id$=cancelar-btn]")
            esperar_fechado(page, sid)
            time.sleep(0.3)
            assert not page.evaluate("document.body.classList.contains('bottom-sheet-bloqueado')"), "scroll do body ficou travado"
        cen.append(c1)

        @cenario(f"{sid}: ESC fecha e devolve o foco ao botao")
        def c2(page, sid=sid):
            abrir_sheet(page, sid)
            page.keyboard.press("Escape")
            esperar_fechado(page, sid)
            foco = page.evaluate("document.activeElement && document.activeElement.id")
            assert foco == SHEETS[sid][0][1:], f"foco foi pra {foco}"
        cen.append(c2)

        @cenario(f"{sid}: salvar com API 500 mantem o sheet e restaura o botao")
        def c3(page, sid=sid):
            rota = SHEETS[sid][4]
            page.route(f"**{rota}", lambda r: r.fulfill(status=500, content_type="application/json",
                                                        body=json.dumps({"error": "falha simulada"}))
                       if r.request.method == "POST" else r.continue_())
            try:
                abrir_sheet(page, sid)
                preencher(page, sid)
                page.click(SHEETS[sid][2])
                page.wait_for_function("!document.getElementById('erro-banner').hidden", timeout=3000)
                time.sleep(0.2)
                assert not page.evaluate(f"document.getElementById('sheet-{sid}').hidden"), "sheet fechou com erro"
                assert botao_restaurado(page, sid), "botao ficou travado"
            finally:
                page.unroute(f"**{rota}")
                fechar_tudo(page)
        cen.append(c3)

        @cenario(f"{sid}: salvar com JSON invalido nao lanca excecao")
        def c4(page, sid=sid):
            rota = SHEETS[sid][4]
            page.route(f"**{rota}", lambda r: r.fulfill(status=200, content_type="application/json", body="{oops: [")
                       if r.request.method == "POST" else r.continue_())
            try:
                abrir_sheet(page, sid)
                preencher(page, sid)
                page.click(SHEETS[sid][2])
                page.wait_for_function(f"(() => {{ const b = document.querySelector('{SHEETS[sid][2]}'); return !b.disabled && !b.querySelector('.spinner'); }})()", timeout=4000)
            finally:
                page.unroute(f"**{rota}")
                fechar_tudo(page)
        cen.append(c4)

    for sid in ["garantia", "ideia-presente", "pessoa", "aprender", "compra", "responder", "manutencao"]:
        @cenario(f"{sid}: string gigante (~10k chars, unicode/HTML) respeita maxlength e salva")
        def c5(page, sid=sid):
            abrir_sheet(page, sid)
            preencher(page, sid)
            primeiro = list(SHEETS[sid][3])[0]
            page.fill(primeiro, GIGANTE)
            n = page.evaluate(f"document.querySelector('{primeiro}').value.length")
            mx = page.evaluate(f"document.querySelector('{primeiro}').maxLength")
            assert mx < 0 or n <= mx, f"passou do maxlength: {n} > {mx}"
            page.click(SHEETS[sid][2])
            esperar_fechado(page, sid, 4000)
            fechar_tudo(page)
        cen.append(c5)

    @cenario("duplo clique no salvar (compra) nao trava o sheet")
    def c6(page):
        abrir_sheet(page, "compra")
        preencher(page, "compra")
        page.dblclick("#compra-btn")
        esperar_fechado(page, "compra", 4000)
        assert botao_restaurado(page, "compra")
    cen.append(c6)

    @cenario("toque no fundo escurecido fecha o sheet")
    def c7(page):
        abrir_sheet(page, "pessoa")
        page.mouse.click(195, 40)
        esperar_fechado(page, "pessoa")
    cen.append(c7)

    @cenario("ESC sem nenhum sheet aberto nao faz nada")
    def c8(page):
        for _ in range(5):
            page.keyboard.press("Escape")
        assert page.evaluate("!document.querySelector('.bottom-sheet--aberto')")
    cen.append(c8)

    @cenario("sheet ocupa a tela (nao preso na aba) e o veu cobre o viewport")
    def c9(page):
        abrir_sheet(page, "garantia")
        r = page.evaluate("(() => { const s = document.getElementById('sheet-garantia').getBoundingClientRect(); return [s.top, s.height]; })()")
        assert abs(r[0]) < 2 and abs(r[1] - 844) < 2, f"moldura do sheet = {r}"
        fechar_tudo(page)
    cen.append(c9)

    @cenario("todas as secoes da faixa: recolher/abrir em rajada (7 cliques) fica consistente")
    def c10(page):
        ids = page.evaluate("[...document.querySelectorAll('#tab-vida .secao-recolhivel[data-secao-id^=vida-]')].map(s => s.dataset.secaoId)")
        assert len(ids) >= 14, ids
        for sid in ids:
            cab = page.locator(f'[data-secao-id="{sid}"] > .secao-cabecalho')
            if not cab.is_visible():
                continue  # ainda-usa pode estar hidden (sem assinatura)
            cab.scroll_into_view_if_needed()
            for _ in range(7):
                cab.click()
            time.sleep(0.45)
            st = page.evaluate(f"(() => {{ const s = document.querySelector('[data-secao-id=\"{sid}\"]'); return [s.dataset.aberto, s.querySelector('.secao-cabecalho').getAttribute('aria-expanded')]; }})()")
            assert st[0] == st[1], f"{sid}: data-aberto={st[0]} aria-expanded={st[1]}"
            if st[0] == "false":
                cab.click()
                time.sleep(0.35)
    cen.append(c10)

    @cenario("dica '!' em rajada (9 cliques) termina aberta e com aria-expanded certo")
    def c11(page):
        t = page.locator('[data-secao-id="vida-garantia"] .dica-toggle')
        t.scroll_into_view_if_needed()
        for _ in range(9):
            t.click()
        st = page.evaluate("(() => { const t = document.querySelector('[data-secao-id=vida-garantia] .dica-toggle'); return [t.getAttribute('aria-expanded'), t.closest('.dica-colapsavel').querySelector('.dica-texto').hidden]; })()")
        assert st == ["true", False], st
        t.click()
    cen.append(c11)

    for modo in ("500", "json-invalido", "formato-errado"):
        @cenario(f"carregar a aba com todos os GETs de lista em {modo}")
        def c12(page, modo=modo):
            def responder(r):
                if r.request.method != "GET":
                    return r.continue_()
                if modo == "500":
                    return r.fulfill(status=500, content_type="application/json", body='{"error":"x"}')
                if modo == "json-invalido":
                    return r.fulfill(status=200, content_type="application/json", body="<html>nao e json")
                return r.fulfill(status=200, content_type="application/json", body='{"inesperado": true}')
            for g in GETS_LISTA:
                page.route(f"**{g}", responder)
            try:
                comum.abrir_vida(page)
                time.sleep(0.8)
            finally:
                for g in GETS_LISTA:
                    page.unroute(f"**{g}")
                comum.dubles_leitura(page)
                comum.abrir_vida(page)
        cen.append(c12)

    @cenario("Mensagem dificil: 500, JSON invalido e texto gigante")
    def c13(page):
        page.locator("#mensagem-situacao").scroll_into_view_if_needed()
        for corpo, status in (('{"error":"falhou"}', 500), ("nao-json", 200)):
            page.route("**/api/mensagem-dificil", responde(status, corpo))
            page.fill("#mensagem-situacao", GIGANTE)
            page.click("#mensagem-btn")
            page.wait_for_function("!document.getElementById('mensagem-btn').disabled", timeout=4000)
            page.unroute("**/api/mensagem-dificil")
        fechar_tudo(page)
    cen.append(c13)

    @cenario("Vale a pena?: 500, JSON invalido e texto gigante")
    def c14(page):
        page.locator("#decisao-pergunta").scroll_into_view_if_needed()
        for corpo, status in (('{"error":"falhou"}', 500), ("nao-json", 200)):
            page.route("**/api/decisao", responde(status, corpo))
            page.fill("#decisao-pergunta", GIGANTE)
            page.click("#decisao-btn")
            page.wait_for_function("!document.getElementById('decisao-btn').disabled", timeout=4000)
            page.unroute("**/api/decisao")
        fechar_tudo(page)
    cen.append(c14)

    @cenario("Revisao trimestral: ano absurdo e API 500")
    def c15(page):
        sec = page.locator('[data-secao-id="vida-revisao-trimestral"]')
        if sec.get_attribute("data-aberto") == "false":
            sec.locator("> .secao-cabecalho").click()
            time.sleep(0.4)
        page.route("**/api/revisao-periodo**", lambda r: r.fulfill(status=500, content_type="application/json", body='{"error":"x"}'))
        for ano in ("99999999", "-5", "abc", ""):
            page.evaluate(f"document.getElementById('revisao-periodo-ano').value = {json.dumps(ano)}")
            page.click("#revisao-periodo-btn")
            time.sleep(0.2)
        page.unroute("**/api/revisao-periodo**")
        fechar_tudo(page)
    cen.append(c15)

    @cenario("Peso e medidas (aba Painel): abrir/fechar rapido, ESC, 500 e JSON invalido")
    def c16(page):
        page.click('.tab-btn[data-tab="painel"]')
        time.sleep(0.8)
        page.locator("#medida-abrir-btn").scroll_into_view_if_needed()
        for _ in range(6):
            page.evaluate("document.getElementById('medida-abrir-btn').click()")
            time.sleep(0.03)
            page.evaluate("document.getElementById('medida-cancelar-btn').click()")
            time.sleep(0.03)
        esperar_fechado(page, "medida", 2500)
        time.sleep(0.3)
        for corpo, status in (('{"error":"falha"}', 500), ("{oops", 200)):
            page.route("**/api/medidas", responde(status, corpo, so_post=True))
            page.click("#medida-abrir-btn")
            esperar_aberto(page, "medida")
            page.fill("#medida-valor", "81.3")
            page.click("#medida-btn")
            time.sleep(0.5)
            page.unroute("**/api/medidas")
            assert not page.evaluate("document.getElementById('medida-btn').disabled")
            page.keyboard.press("Escape")
            esperar_fechado(page, "medida")
        page.evaluate("document.getElementById('medida-tipo-select').value='outro'; document.getElementById('medida-tipo-select').dispatchEvent(new Event('change'))")
        page.click('.tab-btn[data-tab="vida"]')
        time.sleep(0.6)
        fechar_tudo(page)
    cen.append(c16)
    return cen


def main():
    srv = comum.subir_servidor()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=comum.CHROME, headless=True)
            # service worker bloqueado: pedido feito pelo SW nao passa pelo page.route (o dublê
            # do cenario nao pegaria) e o precache disputa a rede com o cenario.
            ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1,
                                service_workers="block")
            comum.logar(ctx)
            comum.semear(ctx)
            page = ctx.new_page()
            comum.proteger_rede(page)
            page.set_default_timeout(5000)
            page.set_default_navigation_timeout(30000)
            coletar(page)
            comum.dubles_leitura(page)
            comum.abrir_vida(page)
            for fn in montar_cenarios():
                cenario_atual[0] = fn.nome
                antes = len(erros_app)
                t0 = time.time()
                try:
                    fn(page)
                    ok = len(erros_app) == antes
                    resultados.append((fn.nome, ok, "" if ok else erros_app[antes:]))
                    if "-v" in sys.argv:
                        print(f"{'ok ' if ok else 'FALHA'} {time.time() - t0:5.1f}s {fn.nome}", flush=True)
                except Exception as e:  # noqa: BLE001 - fuzz: qualquer falha vira resultado
                    resultados.append((fn.nome, False, f"{type(e).__name__}: {str(e)[:200]}"))
                    if "-v" in sys.argv:
                        print(f"FALHA {time.time() - t0:5.1f}s {fn.nome}: {str(e)[:160]}", flush=True)
                    if "--tb" in sys.argv:
                        traceback.print_exc()
                    try:
                        fechar_tudo(page)
                    except Exception:  # noqa: BLE001
                        try:
                            comum.abrir_vida(page)
                        except Exception:  # noqa: BLE001
                            pass
            b.close()
    finally:
        srv.terminate()
    saidas = comum.saidas_bloqueadas()
    for l in saidas:
        print("SAIDA DE REDE TENTADA (bloqueada):", l)
    falhas = [r for r in resultados if not r[1]]
    for nome, ok, det in resultados:
        if not ok:
            print("FALHA", nome, "->", det)
    print(f"cenarios: {len(resultados)} | ok: {len(resultados) - len(falhas)} | falhas: {len(falhas)} | "
          f"erros de console do app: {sum(1 for e in erros_app if e[1] == 'console.error')} | "
          f"excecoes: {sum(1 for e in erros_app if e[1] == 'pageerror')} | "
          f"logs 'Failed to load resource' (500 provocado/rede externa abortada): {ruido_rede[0]} | "
          f"tentativas de saida do servidor pra fora do loopback: {len(saidas)}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
