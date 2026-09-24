"""Historia 3 da faixa C3b: fuzz de UI (Playwright headless 390x844, banco sintetico).

Uso: PORTA=5132 python scripts/ralph-c3b-viagens/fuzz.py
Grava fuzz-resultado.json nesta pasta. Meta: 0 erro de console, 0 excecao (pageerror) e
todas as checagens de estado ok.

As respostas 500 / JSON invalido sao INJETADAS com page.route (nada muda no servidor). O
"Failed to load resource" que o proprio navegador loga pra essas URLs injetadas e esperado e
fica fora da contagem - qualquer outro erro de console conta.
"""
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comum import AMBIENTE, AQUI, BASE, CHROME, abrir_aba, logar, rotas_de_rede, semear  # noqa: E402

SHEETS = {
    "viagem": ("vida", "#viagem-abrir-btn", "#viagem-sheet", "#viagem-cancelar-btn"),
    "lugar": ("vida", "#lugar-abrir-btn", "#lugar-sheet", "#lugar-cancelar-btn"),
    "cotacao": ("construtora", "#cotacao-abrir-btn", "#cotacao-sheet", "#cotacao-cancelar-btn"),
    "voo": ("aviacao", "#voo-abrir-btn", "#voo-sheet", "#voo-cancelar-btn"),
}
GIGANTE = ("Ç~<b>x</b>&amp;'\"😀" * 900)[:12000]


class Fuzz:
    def __init__(self, page):
        self.page = page
        self.erros = []
        self.injetadas = set()
        self.rotas = []
        self.posts = []
        page.on("console", self._console)
        page.on("pageerror", lambda e: self.erros.append(("pageerror", str(e)[:300])))
        page.on("request", lambda r: self.posts.append(r.url) if r.method in ("POST", "DELETE") else None)

    def _console(self, m):
        if m.type != "error":
            return
        url = (m.location or {}).get("url", "")
        if m.text.startswith("Failed to load resource") and (
            url in self.injetadas or any(a in url for a in AMBIENTE)
        ):
            return
        self.erros.append(("console.error", m.text[:300]))

    # ---- injecao de falha ----
    def falhar(self, padrao, metodo, modo, atraso=0):
        rx = re.compile(padrao)

        def handler(route):
            req = route.request
            if metodo and req.method != metodo:
                return route.fallback()
            self.injetadas.add(req.url)
            if atraso:
                time.sleep(atraso)
            if modo == "500":
                return route.fulfill(status=500, content_type="application/json", body='{"error": "falha injetada"}')
            if modo == "json":
                return route.fulfill(status=200, content_type="application/json", body='{"quebrado": [1, 2')
            if modo == "objeto":
                return route.fulfill(status=200, content_type="application/json", body='{"inesperado": true}')
            if modo == "abort":
                return route.abort()
            return route.fallback()

        self.page.route(rx, handler)
        self.rotas.append((rx, handler))

    def limpar(self):
        for rx, h in self.rotas:
            self.page.unroute(rx, h)
        self.rotas = []
        # fecha qualquer sheet aberto e o banner de erro
        for _ in range(3):
            if self.page.evaluate("document.querySelectorAll('.bottom-sheet--aberto').length") == 0:
                break
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(300)
        self.page.evaluate("() => { const b = document.querySelector('#erro-banner'); if (b) b.hidden = true; }")

    # ---- utilidades ----
    def aba(self, nome):
        if self.page.evaluate(f"document.querySelector('#tab-{nome}').hidden"):
            abrir_aba(self.page, nome)

    def abrir(self, chave):
        aba, btn, sheet, _ = SHEETS[chave]
        self.aba(aba)
        self.page.click(btn)
        self.page.wait_for_selector(f"{sheet}.bottom-sheet--aberto", timeout=3000)
        self.page.wait_for_timeout(320)

    def aberto(self, sheet):
        return self.page.evaluate(f"!document.querySelector('{sheet}').hidden")

    def banner(self):
        return self.page.evaluate("!document.querySelector('#erro-banner').hidden")

    def scroll_livre(self):
        return self.page.evaluate("!document.body.classList.contains('bottom-sheet-bloqueado')")

    def preencher(self, chave, gigante=False):
        p = self.page
        s = GIGANTE if gigante else None
        # rascunho de um cenario anterior (ESC fecha sem limpar, de proposito) nao vaza
        p.evaluate(f"document.querySelector('{SHEETS[chave][2]} form').reset()")
        if chave == "viagem":
            p.fill("#viagem-nova-destino", s or "Fuzz Destino")
            p.fill("#viagem-nova-ida", "2027-03-10")
            p.fill("#viagem-nova-volta", "2027-03-15")
        elif chave == "lugar":
            p.fill("#lugar-nome", s or "Fuzz Lugar")
            p.fill("#lugar-cidade", s or "Fuzz Cidade")
        elif chave == "cotacao":
            p.fill("#cotacao-titulo", s or "Fuzz Cotacao")
        elif chave == "voo":
            p.fill("#voo-data", "15/10/2026")
            p.fill("#voo-destino", s or "Fuzz Aerodromo")
            p.fill("#voo-origem", s or "SSBL")
            p.fill("#voo-obs", s or "")

    def salvar(self, chave):
        btn = {"viagem": "#viagem-nova-btn", "lugar": "#lugar-btn", "cotacao": "#cotacao-btn", "voo": "#voo-btn"}[chave]
        self.page.click(btn)


def main():
    resultados = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME, headless=True)
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        logar(ctx)
        rotas_de_rede(ctx)
        if not ctx.request.get(BASE + "/api/viagens").json():
            semear(ctx)
        page = ctx.new_page()
        f = Fuzz(page)
        page.goto(BASE + "/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)

        def cenario(nome, func):
            antes = len(f.erros)
            try:
                ok = func()
                ok = True if ok is None else ok
                detalhe = "" if ok is True else str(ok)
                ok = ok is True
            except Exception as e:  # noqa: BLE001 - falha do cenario, registrada
                ok, detalhe = False, f"{type(e).__name__}: {str(e)[:200]}"
            page.wait_for_timeout(250)
            novos = f.erros[antes:]
            f.limpar()
            resultados.append({"cenario": nome, "ok": ok and not novos, "detalhe": detalhe, "erros": novos})
            print(("OK  " if ok and not novos else "FAIL") + " " + nome + (f" | {detalhe}" if detalhe else "")
                  + (f" | {novos}" if novos else ""), flush=True)

        # ---------- mapa com CDN do Leaflet fora do ar (precisa vir ANTES de carregar o Leaflet) ----------
        def mapa_sem_cdn():
            f.aba("vida")
            page.wait_for_selector("#lista-lugares .lugar-mapa-btn")
            f.falhar(r"cdn\.jsdelivr\.net/npm/leaflet", None, "abort")
            page.click("#lista-lugares li:first-child .lugar-mapa-btn")
            page.wait_for_timeout(1200)
            txt = page.inner_text("#lista-lugares li:first-child .lugar-mapa")
            page.click("#lista-lugares li:first-child .lugar-mapa-btn")  # fecha
            return "Não consegui carregar o mapa" in txt or f"texto: {txt[:80]}"
        cenario("mapa: CDN do Leaflet fora -> aviso, sem excecao", mapa_sem_cdn)

        def mapa_rapido():
            f.aba("vida")
            btn = "#lista-lugares li:first-child .lugar-mapa-btn"
            for _ in range(11):
                page.click(btn)
            page.wait_for_timeout(1500)
            vis = page.evaluate("!document.querySelector('#lista-lugares li:first-child .lugar-mapa').hidden")
            h = page.evaluate("document.querySelector('#lista-lugares li:first-child .lugar-mapa').getBoundingClientRect().height")
            return (vis and h >= 170) or f"visivel={vis} altura={h}"
        cenario("mapa: abrir/fechar 11x rapido termina aberto com 180px", mapa_rapido)

        # ---------- sheets: abrir/fechar ----------
        for chave, (aba, btn, sheet, cancelar) in SHEETS.items():
            def rapido(chave=chave, btn=btn, sheet=sheet):
                f.aba(SHEETS[chave][0])
                for _ in range(8):
                    page.click(btn)
                    page.keyboard.press("Escape")
                page.wait_for_timeout(500)
                return (not f.aberto(sheet) and f.scroll_livre()) or "sheet ficou aberto ou scroll travado"
            cenario(f"{chave}: abrir+ESC 8x rapido", rapido)

            def fora(chave=chave, sheet=sheet):
                f.abrir(chave)
                page.mouse.click(195, 40)  # fundo escurecido, acima do painel
                page.wait_for_timeout(450)
                return not f.aberto(sheet) or "toque fora nao fechou"
            cenario(f"{chave}: toque fora fecha", fora)

            def cancelar_limpa(chave=chave, sheet=sheet, cancelar=cancelar, btn=btn):
                f.abrir(chave)
                f.preencher(chave)
                page.click(cancelar)
                page.wait_for_timeout(450)
                vazio = page.evaluate(f"[...document.querySelectorAll('{sheet} input[type=text], {sheet} textarea')].every(i => !i.value)")
                foco = page.evaluate("document.activeElement && ('#' + document.activeElement.id)")
                return (not f.aberto(sheet) and vazio and foco == btn) or f"aberto={f.aberto(sheet)} vazio={vazio} foco={foco}"
            cenario(f"{chave}: Cancelar fecha, limpa e devolve o foco", cancelar_limpa)

            def duplo(chave=chave, btn=btn, sheet=sheet):
                f.aba(SHEETS[chave][0])
                page.click(btn)
                page.evaluate(f"document.querySelector('{btn}').click()")
                page.wait_for_timeout(350)
                n = page.evaluate("document.querySelectorAll('.bottom-sheet--aberto').length")
                page.keyboard.press("Escape")
                page.wait_for_timeout(450)
                return (n == 1 and not f.aberto(sheet) and f.scroll_livre()) or f"abertos={n}"
            cenario(f"{chave}: clique duplo no botao abre 1 sheet so", duplo)

            def api500(chave=chave, sheet=sheet):
                url = {"viagem": r"/api/viagens$", "lugar": r"/api/lugares$", "cotacao": r"/api/cotacoes$", "voo": r"/api/voos$"}[chave]
                f.abrir(chave)
                f.preencher(chave)
                f.falhar(url, "POST", "500")
                f.salvar(chave)
                page.wait_for_timeout(700)
                return (f.aberto(sheet) and f.banner()) or f"aberto={f.aberto(sheet)} banner={f.banner()}"
            cenario(f"{chave}: salvar com API 500 mantem sheet e mostra erro", api500)

            def json_ruim(chave=chave, sheet=sheet):
                url = {"viagem": r"/api/viagens$", "lugar": r"/api/lugares$", "cotacao": r"/api/cotacoes$", "voo": r"/api/voos$"}[chave]
                f.abrir(chave)
                f.preencher(chave)
                f.falhar(url, "POST", "json")
                f.salvar(chave)
                page.wait_for_timeout(700)
                habilitado = page.evaluate(f"!document.querySelector('{sheet} [type=submit]').disabled")
                return habilitado or "botao ficou travado em 'salvando'"
            cenario(f"{chave}: salvar com JSON invalido nao quebra", json_ruim)

            def gigante(chave=chave, sheet=sheet):
                f.abrir(chave)
                f.preencher(chave, gigante=True)
                f.salvar(chave)
                page.wait_for_function(f"document.querySelector('{sheet}').hidden", timeout=15000)
                return True
            cenario(f"{chave}: strings gigantes (12k, emoji, HTML) salvam e fecham", gigante)

        # ---------- validacoes de data/valor ----------
        def viagem_volta_antes():
            f.abrir("viagem")
            n0 = len(f.posts)
            page.fill("#viagem-nova-destino", "Volta antes")
            page.fill("#viagem-nova-ida", "2027-05-10")
            page.fill("#viagem-nova-volta", "2027-05-01")
            f.salvar("viagem")
            page.wait_for_timeout(400)
            return (len(f.posts) == n0 and f.banner() and f.aberto("#viagem-sheet")) or "enviou ou nao avisou"
        cenario("viagem: volta antes da ida bloqueia", viagem_volta_antes)

        def viagem_data_invalida():
            f.abrir("viagem")
            n0 = len(f.posts)
            page.fill("#viagem-nova-destino", "Data ruim")
            page.evaluate("document.querySelector('#viagem-nova-ida').value = '2026-13-45'")
            f.salvar("viagem")
            page.wait_for_timeout(400)
            return len(f.posts) == n0 or "enviou data invalida"
        cenario("viagem: data de ida invalida nao envia", viagem_data_invalida)

        for rotulo, campo, valor in (
            ("data 31/02", "#voo-data", "31/02/2026"),
            ("data texto", "#voo-data", "ontem"),
            ("horas negativas", "#voo-horas", "-3"),
            ("horas texto", "#voo-horas", "abc"),
            ("hora 25:99", "#voo-hora", "25:99"),
        ):
            def voo_invalido(campo=campo, valor=valor):
                f.abrir("voo")
                n0 = len(f.posts)
                f.preencher("voo")
                page.fill(campo, valor)
                f.salvar("voo")
                page.wait_for_timeout(400)
                return (len(f.posts) == n0 and f.aberto("#voo-sheet")) or "enviou voo invalido"
            cenario(f"voo: {rotulo} nao envia", voo_invalido)

        def voo_duplo():
            f.abrir("voo")
            f.preencher("voo")
            page.fill("#voo-destino", "Duplo toque")
            f.falhar(r"/api/voos$", "POST", "lento", atraso=0)
            n0 = sum(1 for u in f.posts if u.endswith("/api/voos"))
            page.evaluate("() => { const b = document.querySelector('#voo-btn'); b.click(); b.click(); b.click(); }")
            page.wait_for_function("document.querySelector('#voo-sheet').hidden", timeout=15000)
            n = sum(1 for u in f.posts if u.endswith("/api/voos")) - n0
            return n == 1 or f"{n} POSTs"
        cenario("voo: toque triplo em Salvar gera 1 voo so", voo_duplo)

        # ---------- cotacao: fornecedor ----------
        # alvo fixo: a cotacao semeada com fornecedores (as criadas pelo fuzz entram no topo)
        ALVO = "#lista-cotacoes li[data-fuzz=alvo]"

        def abrir_detalhe():
            f.aba("construtora")
            page.wait_for_selector("#lista-cotacoes li")
            page.evaluate("""() => { const li = [...document.querySelectorAll('#lista-cotacoes > li')]
                .find(l => l.querySelector('.item-titulo').textContent === 'Portas de madeira');
                if (li) li.dataset.fuzz = 'alvo'; }""")
            cab = ALVO + " .cotacao-cabecalho"
            if page.get_attribute(cab, "aria-expanded") != "true":
                page.click(cab)
            page.wait_for_selector(ALVO + " .cotacao-add-form", timeout=5000)

        for rotulo, valor in (("negativo", "-50"), ("infinito", "1e999"), ("texto", "abc"), ("vazio", "")):
            def forn_invalido(valor=valor):
                abrir_detalhe()
                n0 = len(f.posts)
                page.fill(ALVO + " .cotacao-add-form input:nth-child(1)", "Fornecedor fuzz")
                page.fill(ALVO + " .cotacao-add-form input:nth-child(2)", valor)
                page.click(ALVO + " .cotacao-add-form button")
                page.wait_for_timeout(400)
                return len(f.posts) == n0 or "enviou valor invalido"
            cenario(f"cotacao: fornecedor com valor {rotulo} nao envia", forn_invalido)

        for modo in ("500", "json"):
            def forn_api(modo=modo):
                abrir_detalhe()
                f.falhar(r"/api/cotacoes/\d+/itens$", "POST", modo)
                page.fill(ALVO + " .cotacao-add-form input:nth-child(1)", "Fornecedor fuzz")
                page.fill(ALVO + " .cotacao-add-form input:nth-child(2)", "123,45")
                page.click(ALVO + " .cotacao-add-form button")
                page.wait_for_timeout(700)
                hab = page.evaluate("!document.querySelector('" + ALVO + " .cotacao-add-form button').disabled")
                return hab or "botao travado"
            cenario(f"cotacao: adicionar fornecedor com API {modo}", forn_api)

        def forn_apagar_500():
            abrir_detalhe()
            f.falhar(r"/api/cotacoes/\d+/itens/\d+$", "DELETE", "500")
            page.click(ALVO + " .cotacao-item-apagar")
            page.wait_for_timeout(700)
            n = page.evaluate("document.querySelectorAll('" + ALVO + " .cotacao-item').length")
            hab = page.evaluate("!document.querySelector('" + ALVO + " .cotacao-item-apagar').disabled")
            return (n >= 1 and hab and f.banner()) or f"itens={n} habilitado={hab}"
        cenario("cotacao: apagar fornecedor com API 500 mantem o item", forn_apagar_500)

        def detalhe_json_ruim():
            f.aba("construtora")
            page.evaluate("() => { loadCotacoes(); }")
            page.wait_for_timeout(600)
            f.falhar(r"/api/cotacoes/\d+$", "GET", "json")
            page.click("#lista-cotacoes li:first-child .cotacao-cabecalho")
            page.wait_for_timeout(700)
            return True
        cenario("cotacao: detalhe com JSON invalido", detalhe_json_ruim)

        # ---------- listas com GET quebrado ----------
        for alvo, rx, chamada, aba in (
            ("viagens", r"/api/viagens$", "loadViagens()", "vida"),
            ("lugares", r"/api/lugares$", "loadLugares()", "vida"),
            ("cotacoes", r"/api/cotacoes$", "loadCotacoes()", "construtora"),
            ("voos/resumo", r"/api/voos/resumo$", "loadVoosResumo()", "aviacao"),
        ):
            for modo in ("500", "json", "objeto"):
                def lista(rx=rx, chamada=chamada, aba=aba, modo=modo):
                    f.aba(aba)
                    f.falhar(rx, "GET", modo)
                    page.evaluate(f"() => {{ {chamada}; }}")
                    page.wait_for_timeout(700)
                    return True
                cenario(f"lista {alvo}: GET {modo}", lista)

        # ---------- METAR ----------
        for rotulo, icao, modo in (("API 500", "SBBI", "500"), ("JSON invalido", "SBBI", "json"),
                                   ("sem dado (ZZZZ)", "ZZZZ", None), ("HTML no campo", "<img", None)):
            def metar(icao=icao, modo=modo):
                f.aba("aviacao")
                if modo:
                    f.falhar(r"/api/clima/metar", "GET", modo)
                page.fill("#metar-icao", icao)
                page.click("#metar-btn")
                page.wait_for_timeout(800)
                hab = page.evaluate("!document.querySelector('#metar-btn').disabled")
                return hab or "botao Consultar travado"
            cenario(f"metar: {rotulo}", metar)

        # ---------- secoes recolhiveis ----------
        for sid, aba in (("vida-viagens", "vida"), ("vida-lugares", "vida"), ("construtora-cotacoes", "construtora"),
                         ("aviacao-proximos-voos", "aviacao"), ("aviacao-metar", "aviacao")):
            def recolher(sid=sid, aba=aba):
                f.aba(aba)
                cab = f'[data-secao-id="{sid}"] > .secao-cabecalho'
                for _ in range(9):
                    page.click(cab)
                page.wait_for_timeout(600)
                estado = page.evaluate(f"""() => {{ const s = document.querySelector('[data-secao-id="{sid}"]');
                    return [s.dataset.aberto, s.querySelector('.secao-cabecalho').getAttribute('aria-expanded'),
                            localStorage.getItem('secao-recolhivel:{sid}') || Object.keys(localStorage).filter(k => k.includes('{sid}')).map(k => localStorage.getItem(k))[0]]; }}""")
                page.click(cab)  # volta pro aberto
                page.wait_for_timeout(400)
                return (estado[0] == "false" and estado[1] == "false") or f"estado={estado}"
            cenario(f"secao {sid}: 9 toques rapidos terminam fechada e salva", recolher)

        # ---------- acoes das listas com API falhando ----------
        def mala_500():
            f.aba("vida")
            f.falhar(r"/api/viagens/\d+/mala$", "POST", "500")
            page.click("#lista-viagens li:first-child .item-acoes button:first-child")
            page.wait_for_timeout(700)
            return page.evaluate("!document.querySelector('#lista-viagens li:first-child .item-acoes button').disabled") or "travado"
        cenario("viagem: montar mala com API 500", mala_500)

        def numero_voo_500():
            f.aba("vida")
            f.falhar(r"/api/viagens/\d+/numero-voo$", "POST", "500")
            page.fill("#lista-viagens li:first-child .viagem-voo-form .campo", "LA3251")
            page.click("#lista-viagens li:first-child .viagem-voo-form .btn")
            page.wait_for_timeout(700)
            return page.evaluate("!document.querySelector('#lista-viagens li:first-child .viagem-voo-form .btn').disabled") or "travado"
        cenario("viagem: numero do voo com API 500", numero_voo_500)

        def apagar_voo_500():
            f.aba("aviacao")
            page.wait_for_selector("#lista-voos li")
            f.falhar(r"/api/voos/\d+$", "DELETE", "500")
            n0 = page.evaluate("document.querySelectorAll('#lista-voos li').length")
            page.click("#lista-voos li:first-child .item-acoes button:last-child")
            page.wait_for_timeout(700)
            n = page.evaluate("document.querySelectorAll('#lista-voos li').length")
            return n == n0 or f"sumiu item: {n0}->{n}"
        cenario("voo: apagar com API 500 mantem o voo", apagar_voo_500)

        def esc_durante_save():
            f.abrir("lugar")
            f.preencher("lugar")
            f.falhar(r"/api/lugares$", "POST", "lento", atraso=1.2)
            f.salvar("lugar")
            page.keyboard.press("Escape")
            page.wait_for_timeout(1800)
            return not f.aberto("#lugar-sheet") or "sheet reabriu/ficou"
        cenario("lugar: ESC com salvamento lento em andamento", esc_durante_save)

        b.close()

    falhas = [r for r in resultados if not r["ok"]]
    saida = {"total": len(resultados), "ok": len(resultados) - len(falhas), "falhas": falhas, "cenarios": resultados}
    with open(os.path.join(AQUI, "fuzz-resultado.json"), "w") as fh:
        json.dump(saida, fh, ensure_ascii=False, indent=1)
    print(f"\n{saida['ok']}/{saida['total']} cenarios ok, {len(falhas)} falha(s)")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
