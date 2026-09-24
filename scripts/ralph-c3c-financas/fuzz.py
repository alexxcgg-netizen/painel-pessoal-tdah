"""Fuzz de UI da faixa c3c-financas (Playwright headless 390x844).

Cenarios: formulario de assinatura/parcela/conta pessoal com valor 0, negativo,
gigante, texto no lugar de numero, data invalida, dia 31 em mes curto; API
devolvendo 500, JSON invalido ou formato estranho (page.route) nas 4 telas;
abrir/fechar sheet rapido e clique duplo no salvar.

Meta: 0 erro de console (fora o "Failed to load resource" das respostas 500 que
o proprio cenario forca), 0 excecao de pagina e nenhum NaN/undefined/null/
Infinity visivel.

Uso: PORTA=5133 python fuzz.py   (servidor.py rodando num banco temporario)
"""
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:" + os.environ.get("PORTA", "5133")
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
AMBIENTE = ("fonts.googleapis.com", "fonts.gstatic.com", "/api/summary/today", "cdn.pluggy.ai")
RUIM = re.compile(r"\bNaN\b|\bundefined\b|\bnull\b|\bInfinity\b|\[object Object\]")
RAIZES = ["#tab-gastos", "#tab-bancos", "#tab-construtora", "#lista-contas-pessoais",
          "#sheet-nova-assinatura", "#sheet-nova-parcela", "#sheet-nova-conta-pessoal", "#erro-banner"]

resultados = []
erros_pagina = []
respostas_forcadas = []


def json_resp(route, corpo, status=200):
    respostas_forcadas.append(route.request.url)
    route.fulfill(status=status, content_type="application/json",
                  body=corpo if isinstance(corpo, str) else json.dumps(corpo))


def texto_ruim(page):
    return page.evaluate("""([raizes, re]) => {
      const rx = new RegExp(re);
      const achados = [];
      for (const s of raizes) {
        const el = document.querySelector(s);
        if (!el || el.hidden) continue;
        const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
        let n;
        while ((n = walker.nextNode())) {
          const p = n.parentElement;
          if (!p || p.closest('[hidden]') || !p.getClientRects().length) continue;
          if (rx.test(n.textContent)) achados.push(s + ': ' + n.textContent.trim().slice(0, 60));
        }
        for (const inp of el.querySelectorAll('input')) if (rx.test(inp.value)) achados.push(s + ' input: ' + inp.value);
      }
      return achados;
    }""", [RAIZES, RUIM.pattern])


def cenario(page, nome, fn):
    antes = len(erros_pagina)
    detalhe = ""
    ok = True
    try:
        r = fn()
        if r is False:
            ok, detalhe = False, "assercao do cenario falhou"
        elif isinstance(r, str):
            ok, detalhe = False, r
    except Exception as e:  # noqa: BLE001
        ok, detalhe = False, f"excecao no roteiro: {e!r}"[:300]
    time.sleep(0.15)
    novos = erros_pagina[antes:]
    if novos:
        ok = False
        detalhe += f" erros={novos[:3]}"
    ruins = texto_ruim(page)
    if ruins:
        ok = False
        detalhe += f" texto_ruim={ruins[:3]}"
    resultados.append((nome, ok, detalhe.strip()))


def abrir_aba(page, aba):
    page.click(f"button.tab-btn[data-tab='{aba}']")
    time.sleep(0.9)


def recarregar(page, aba):
    page.goto(BASE + "/")
    page.wait_for_load_state("networkidle")
    abrir_aba(page, aba)


def sheet_aberto(page, sid):
    return page.evaluate(f"!document.getElementById('{sid}').hidden")


def fechar_sheets(page):
    for _ in range(3):
        aberto = page.evaluate("[...document.querySelectorAll('.bottom-sheet')].some(s => !s.hidden)")
        if not aberto:
            return
        page.keyboard.press("Escape")
        time.sleep(0.35)


def preencher(page, campos):
    for sel, val in campos.items():
        # evaluate em vez de fill: permite "valor impossivel" em input number/date
        page.evaluate("([s, v]) => { const el = document.querySelector(s); el.value = v; "
                      "el.dispatchEvent(new Event('input', {bubbles: true})); }", [sel, val])


def erro_visivel(page, id_erro):
    return page.evaluate(f"(() => {{ const e = document.getElementById('{id_erro}'); "
                         "return e && !e.hidden ? e.textContent.trim() : ''; })()")


def contar(page, url, chave):
    r = page.request.get(BASE + url).json()
    return len(r[chave]) if isinstance(r, dict) else len(r)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, headless=True)
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        r = ctx.request.post(BASE + "/login", data=json.dumps({"pin": "135790"}),
                             headers={"Content-Type": "application/json"})
        if r.status != 200:
            r = ctx.request.post(BASE + "/configurar-pin", data=json.dumps({"pin": "135790", "confirmacao": "135790"}),
                                 headers={"Content-Type": "application/json"})
        assert r.status == 200, r.text()
        page = ctx.new_page()

        def on_console(m):
            if m.type != "error":
                return
            if m.text.startswith("Failed to load resource"):
                return  # conferido pela rede abaixo (500 forcado ou falha de ambiente)
            erros_pagina.append(("console", m.text[:200]))

        page.on("console", on_console)
        page.on("pageerror", lambda e: erros_pagina.append(("pageerror", str(e)[:200])))

        def on_resp(resp):
            if resp.status >= 400 and not any(a in resp.url for a in AMBIENTE) and resp.url not in respostas_forcadas:
                # 400 de validacao do back nao deve acontecer: a UI barra antes
                erros_pagina.append(("rede", f"{resp.status} {resp.url}"))

        page.on("response", on_resp)
        recarregar(page, "gastos")

        # ---------- A. Formulario de assinatura ----------
        def tenta_assinatura(nome, valor, dia, espera_erro=True):
            def roteiro():
                fechar_sheets(page)
                n0 = contar(page, "/api/financas/assinaturas", "assinaturas")
                page.click("#btn-nova-assinatura")
                time.sleep(0.35)
                preencher(page, {"#assinatura-nome": nome, "#assinatura-valor": valor, "#assinatura-dia": dia})
                page.click("#assinatura-salvar-btn")
                time.sleep(0.6)
                n1 = contar(page, "/api/financas/assinaturas", "assinaturas")
                msg = erro_visivel(page, "assinatura-erro")
                if espera_erro:
                    if n1 != n0:
                        return f"criou com valor invalido ({valor!r}/{dia!r})"
                    if not msg:
                        return "sem mensagem de erro no sheet"
                    if not sheet_aberto(page, "sheet-nova-assinatura"):
                        return "sheet fechou com erro"
                else:
                    if n1 != n0 + 1:
                        return f"nao criou ({msg})"
                    if sheet_aberto(page, "sheet-nova-assinatura"):
                        return "sheet nao fechou apos salvar"
                fechar_sheets(page)
                return True
            return roteiro

        casos_invalidos = [
            ("valor 0", "Teste", "0", "10"), ("valor 0,00", "Teste", "0,00", "10"),
            ("valor negativo", "Teste", "-5", "10"), ("valor negativo com virgula", "Teste", "-21,90", "10"),
            ("valor gigante", "Teste", "999999999999", "10"), ("valor 1e400", "Teste", "1e400", "10"),
            ("valor texto", "Teste", "abc", "10"), ("valor NaN", "Teste", "NaN", "10"),
            ("valor Infinity", "Teste", "Infinity", "10"), ("valor vazio", "Teste", "", "10"),
            ("valor so espacos", "Teste", "   ", "10"), ("valor com duas virgulas", "Teste", "1,2,3", "10"),
            ("valor script", "Teste", "<script>alert(1)</script>", "10"),
            ("valor string gigante", "Teste", "9" * 5000, "10"),
            ("dia 0", "Teste", "10", "0"), ("dia 32", "Teste", "10", "32"), ("dia negativo", "Teste", "10", "-1"),
            ("dia texto", "Teste", "10", "abc"), ("dia decimal", "Teste", "10", "1.5"), ("dia vazio", "Teste", "10", ""),
            ("nome vazio", "", "10", "10"), ("nome so espacos", "    ", "10", "10"),
        ]
        for nome_c, nome, valor, dia in casos_invalidos:
            cenario(page, f"assinatura: {nome_c}", tenta_assinatura(nome, valor, dia))
        cenario(page, "assinatura: valida com virgula (21,90)", tenta_assinatura("Musica", "21,90", "5", espera_erro=False))
        cenario(page, "assinatura: valida milhar (1.234,56)", tenta_assinatura("Seguro", "1.234,56", "12", espera_erro=False))
        cenario(page, "assinatura: nome gigante (10k chars) vira 80", tenta_assinatura("N" * 10000, "10", "3", espera_erro=False))
        cenario(page, "assinatura: nome com emoji e acento", tenta_assinatura("Clube do livro \U0001F4DA ç", "15", "7", espera_erro=False))

        def dia31_mes_curto():
            fechar_sheets(page)
            page.click("#btn-nova-assinatura")
            time.sleep(0.3)
            preencher(page, {"#assinatura-nome": "Dia31Teste", "#assinatura-valor": "9,90", "#assinatura-dia": "31"})
            page.click("#assinatura-salvar-btn")
            time.sleep(0.8)
            lst = page.request.get(BASE + "/api/financas/assinaturas").json()["assinaturas"]
            a = [x for x in lst if x["nome"] == "Dia31Teste"]
            if not a:
                return "nao criou dia 31"
            prox = a[0]["proxima_cobranca"]
            ano, mes, dia = map(int, prox.split("-"))
            import calendar
            if dia != min(31, calendar.monthrange(ano, mes)[1]):
                return f"proxima cobranca {prox} nao crava no ultimo dia"
            txt = page.inner_text("#lista-assinaturas-ativas")
            if "Dia31Teste" not in txt or "dia 31" not in txt:
                return "linha de dia 31 nao apareceu"
            return True
        cenario(page, "assinatura: dia 31 em mes curto crava no ultimo dia", dia31_mes_curto)

        def duplo_clique_salvar():
            fechar_sheets(page)
            n0 = contar(page, "/api/financas/assinaturas", "assinaturas")
            page.click("#btn-nova-assinatura")
            time.sleep(0.3)
            preencher(page, {"#assinatura-nome": "Duplo", "#assinatura-valor": "5", "#assinatura-dia": "2"})
            page.evaluate("(() => { const f = document.getElementById('form-nova-assinatura'); "
                          "f.requestSubmit(); f.requestSubmit(); f.requestSubmit(); })()")
            time.sleep(1.0)
            n1 = contar(page, "/api/financas/assinaturas", "assinaturas")
            fechar_sheets(page)
            return True if n1 == n0 + 1 else f"criou {n1 - n0} vezes"
        cenario(page, "assinatura: submit triplo cria so 1", duplo_clique_salvar)

        # ---------- B. Formulario de parcela ----------
        def tenta_parcela(campos, espera_erro=True):
            def roteiro():
                fechar_sheets(page)
                n0 = contar(page, "/api/financas/parcelas", "parcelas")
                page.click("#btn-nova-parcela")
                time.sleep(0.35)
                base = {"#parcela-descricao": "Compra teste", "#parcela-n": "10", "#parcela-valor-total": "",
                        "#parcela-valor-parcela": "", "#parcela-primeira": ""}
                base.update(campos)
                preencher(page, base)
                page.click("#parcela-salvar-btn")
                time.sleep(0.6)
                n1 = contar(page, "/api/financas/parcelas", "parcelas")
                msg = erro_visivel(page, "parcela-erro")
                if espera_erro:
                    if n1 != n0:
                        return f"criou com dado invalido {campos}"
                    if not msg:
                        return "sem mensagem de erro no sheet"
                elif n1 != n0 + 1:
                    return f"nao criou ({msg})"
                fechar_sheets(page)
                return True
            return roteiro

        casos_parcela = [
            ("valor total 0", {"#parcela-valor-total": "0"}),
            ("valor total negativo", {"#parcela-valor-total": "-300"}),
            ("valor total gigante", {"#parcela-valor-total": "1000000000000"}),
            ("valor total texto", {"#parcela-valor-total": "tres mil"}),
            ("valor parcela negativo", {"#parcela-valor-parcela": "-1"}),
            ("valor parcela texto", {"#parcela-valor-parcela": "abc"}),
            ("sem valor nenhum", {}),
            ("n parcelas 0", {"#parcela-n": "0", "#parcela-valor-total": "100"}),
            ("n parcelas negativo", {"#parcela-n": "-3", "#parcela-valor-total": "100"}),
            ("n parcelas 601", {"#parcela-n": "601", "#parcela-valor-total": "100"}),
            ("n parcelas texto", {"#parcela-n": "doze", "#parcela-valor-total": "100"}),
            ("n parcelas gigante", {"#parcela-n": "99999999999999999999", "#parcela-valor-total": "100"}),
            ("data ano 9999", {"#parcela-valor-total": "100", "#parcela-primeira": "9999-12-31"}),
            ("data ano 1900", {"#parcela-valor-total": "100", "#parcela-primeira": "1900-01-01"}),
            ("descricao vazia", {"#parcela-descricao": "", "#parcela-valor-total": "100"}),
        ]
        for nome_c, campos in casos_parcela:
            cenario(page, f"parcela: {nome_c}", tenta_parcela(campos))
        # data impossivel: o input date sanitiza pra "" -> vira "hoje" (padrao documentado) ou erro de badInput
        cenario(page, "parcela: data 2026-02-31 (impossivel) nao quebra",
                tenta_parcela({"#parcela-valor-total": "100", "#parcela-primeira": "2026-02-31"}, espera_erro=False))
        cenario(page, "parcela: valida 12x de 250,00 com data",
                tenta_parcela({"#parcela-n": "12", "#parcela-valor-parcela": "250,00", "#parcela-primeira": "2026-01-31"},
                              espera_erro=False))
        cenario(page, "parcela: 1x (a vista)", tenta_parcela({"#parcela-n": "1", "#parcela-valor-total": "99,90"}, espera_erro=False))

        # ---------- C. Conta pessoal (aba Vida) ----------
        abrir_aba(page, "vida")

        def tenta_conta(nome, dia, valor, espera_erro=True):
            def roteiro():
                fechar_sheets(page)
                n0 = len(page.request.get(BASE + "/api/contas-pessoais").json())
                page.locator("#btn-nova-conta-pessoal").scroll_into_view_if_needed()
                page.click("#btn-nova-conta-pessoal")
                time.sleep(0.35)
                preencher(page, {"#conta-pessoal-nome": nome, "#conta-pessoal-dia": dia, "#conta-pessoal-valor": valor})
                page.click("#conta-pessoal-btn")
                time.sleep(0.6)
                n1 = len(page.request.get(BASE + "/api/contas-pessoais").json())
                msg = erro_visivel(page, "conta-pessoal-erro")
                if espera_erro and (n1 != n0 or not msg):
                    return f"esperava erro (n0={n0} n1={n1} msg={msg!r})"
                if not espera_erro and n1 != n0 + 1:
                    return f"nao criou ({msg})"
                fechar_sheets(page)
                return True
            return roteiro

        for nome_c, args in [("valor negativo", ("Luz", "10", "-10")), ("valor texto", ("Luz", "10", "dez")),
                             ("valor gigante", ("Luz", "10", "1" * 20)), ("dia 32", ("Luz", "32", "10")),
                             ("dia 0", ("Luz", "0", "10")), ("nome vazio", ("", "10", "10"))]:
            cenario(page, f"conta pessoal: {nome_c}", tenta_conta(*args))
        cenario(page, "conta pessoal: sem valor (opcional)", tenta_conta("Agua", "31", "", espera_erro=False))
        cenario(page, "conta pessoal: valor com virgula", tenta_conta("Gas", "15", "89,90", espera_erro=False))

        # ---------- D. Sheet: abrir/fechar rapido ----------
        abrir_aba(page, "gastos")

        def abre_fecha_rapido(btn, sid, vezes=15):
            def roteiro():
                fechar_sheets(page)
                for _ in range(vezes):
                    page.click(btn)
                    page.keyboard.press("Escape")
                time.sleep(0.6)
                page.click(btn)
                time.sleep(0.5)
                if not sheet_aberto(page, sid):
                    return "nao reabriu depois da rajada"
                foco = page.evaluate("document.activeElement && document.activeElement.id")
                page.keyboard.press("Escape")
                time.sleep(0.5)
                if sheet_aberto(page, sid):
                    return "ESC nao fechou"
                if not foco or not foco.startswith(("assinatura-", "parcela-", "conta-pessoal-")):
                    return f"foco nao foi pro 1o campo ({foco})"
                return True
            return roteiro

        cenario(page, "sheet assinatura: 15x abre+ESC", abre_fecha_rapido("#btn-nova-assinatura", "sheet-nova-assinatura"))
        cenario(page, "sheet parcela: 15x abre+ESC", abre_fecha_rapido("#btn-nova-parcela", "sheet-nova-parcela"))

        def abre_fecha_x():
            fechar_sheets(page)
            for _ in range(8):
                page.click("#btn-nova-parcela")
                time.sleep(0.05)
                page.click("#sheet-nova-parcela .bottom-sheet-fechar")
            time.sleep(0.6)
            return True if not sheet_aberto(page, "sheet-nova-parcela") else "ficou aberto"
        cenario(page, "sheet parcela: 8x abre + X", abre_fecha_x)

        def abre_fecha_fundo():
            fechar_sheets(page)
            page.click("#btn-nova-assinatura")
            time.sleep(0.4)
            page.mouse.click(195, 20)  # toque no fundo escurecido
            time.sleep(0.5)
            return True if not sheet_aberto(page, "sheet-nova-assinatura") else "toque fora nao fechou"
        cenario(page, "sheet assinatura: toque fora fecha", abre_fecha_fundo)

        def dois_sheets():
            fechar_sheets(page)
            page.evaluate("document.getElementById('btn-nova-assinatura').click(); document.getElementById('btn-nova-parcela').click();")
            time.sleep(0.5)
            fechar_sheets(page)
            aberto = page.evaluate("[...document.querySelectorAll('.bottom-sheet')].some(s => !s.hidden)")
            return True if not aberto else "sheet preso aberto"
        cenario(page, "sheets: abre os 2 no mesmo tick e fecha", dois_sheets)

        def erro_some_ao_reabrir():
            fechar_sheets(page)
            page.click("#btn-nova-assinatura")
            time.sleep(0.3)
            preencher(page, {"#assinatura-nome": "", "#assinatura-valor": "", "#assinatura-dia": ""})
            page.click("#assinatura-salvar-btn")
            time.sleep(0.2)
            fechar_sheets(page)
            page.click("#btn-nova-assinatura")
            time.sleep(0.3)
            msg = erro_visivel(page, "assinatura-erro")
            fechar_sheets(page)
            return True if not msg else "erro velho continua no sheet"
        cenario(page, "sheet: erro antigo some ao reabrir", erro_some_ao_reabrir)

        # ---------- E. API com defeito (page.route) ----------
        def com_rota(padrao, corpo, status, aba, checar=None):
            def roteiro():
                page.route(padrao, lambda route: json_resp(route, corpo, status))
                try:
                    recarregar(page, aba)
                    time.sleep(0.6)
                    if checar:
                        return checar()
                    return True
                finally:
                    page.unroute(padrao)
            return roteiro

        rotas_gastos = [
            ("**/api/financas/comprometido", "500", '{"error": "boom"}', 500),
            ("**/api/financas/comprometido", "JSON invalido", "{{nao e json", 200),
            ("**/api/financas/comprometido", "campos estranhos",
             {"total_mensal": {"total": "abc", "detalhe_assinaturas": "x"}, "proximas_cobrancas": [None, {"tipo": "assinatura"}, 5],
              "impacto_limite_cartao": [{"cartao": None, "limite": "x", "meses": [{"mes": "2026-10", "total": None, "fracao": "y"}]}]}, 200),
            ("**/api/financas/comprometido", "total gigante",
             {"total_mensal": {"total": 1e15, "assinaturas_total": 1e15, "parcelas_total": 0, "detalhe_assinaturas": [{}],
                               "detalhe_parcelas": []}, "proximas_cobrancas": [], "impacto_limite_cartao": []}, 200),
            ("**/api/financas/comprometido", "lista em vez de objeto", [1, 2, 3], 200),
            ("**/api/financas/assinaturas?ativas=1", "500", "{}", 500),
            ("**/api/financas/assinaturas?ativas=1", "JSON invalido", "<html>", 200),
            ("**/api/financas/assinaturas?ativas=1", "itens sem campo", {"assinaturas": [{}, None, {"nome": 5, "valor": "x", "proxima_cobranca": 7}]}, 200),
            ("**/api/financas/assinaturas?ativas=1", "assinaturas nao e lista", {"assinaturas": "x"}, 200),
            ("**/api/financas/parcelas?em_andamento=1", "500", "{}", 500),
            ("**/api/financas/parcelas?em_andamento=1", "JSON invalido", "[", 200),
            ("**/api/financas/parcelas?em_andamento=1", "itens sem campo",
             {"parcelas": [{}, {"descricao": None, "n_parcelas": 0, "parcelas_pagas": 5, "valor_parcela": None}]}, 200),
            ("**/api/expenses", "gastos objeto em vez de lista", {"x": 1}, 200),
            ("**/api/expenses", "gastos 500", "{}", 500),
            ("**/api/expenses/historico?dias=14", "historico com total texto", [{"data": "2026-09-01", "total": "abc"}, {"data": None}], 200),
            ("**/api/metas", "metas com alvo 0", [{"id": 99, "titulo": "Zero", "valor_alvo": 0, "valor_guardado": 5}], 200),
            ("**/api/gastos/resumo-semanal", "resumo semanal sem campos", {"total_semana": 10, "variacao_pct": None}, 200),
            ("**/api/ia/custo", "custo IA vazio", {}, 200),
        ]
        # meta falsa (id 99) nao existe no banco: o historico dela tambem e forcado
        page.route("**/api/metas/99/historico", lambda route: json_resp(route, {"pontos": None, "valor_alvo": 0}))
        for padrao, nome_c, corpo, st in rotas_gastos:
            cenario(page, f"API gastos {padrao.split('/api/')[1]}: {nome_c}", com_rota(padrao, corpo, st, "gastos"))
        page.unroute("**/api/metas/99/historico")

        def checa_construtora(proibidos=("lucro", "margem", "vgv")):
            def f():
                txt = page.inner_text("#tab-construtora").lower()
                if "carregando..." in txt:
                    return "ficou em 'Carregando...'"
                achou = [w for w in proibidos if w in txt]
                return True if not achou else f"mostrou {achou}"
            return f

        rotas_constr = [
            ("500", "{}", 500), ("502 com erro", {"configurado": True, "erro": "Nao consegui falar"}, 502),
            ("JSON invalido", "nao-json", 200), ("nao configurado", {"configurado": False}, 200),
            ("dados texto", {"configurado": True, "dados": {"tot_entradas": "x", "tot_saidas": None},
                             "contas": [{"dias_ate_vencer": None, "valor": "y", "fornecedor": None, "descricao": None}]}, 200),
            ("com lucro/margem/VGV no JSON", {"configurado": True, "dados": {"tot_entradas": 1000, "tot_saidas": 500,
                                                                              "lucro_liquido": 500, "margem": 50, "vgv": 999},
                                              "contas": []}, 200),
            ("contas nao e lista", {"configurado": True, "dados": {"tot_entradas": 1, "tot_saidas": 2}, "contas": "x"}, 200),
            ("valores gigantes", {"configurado": True, "dados": {"tot_entradas": 123456789012.34, "tot_saidas": 98765432109.87},
                                  "contas": [{"dias_ate_vencer": -9999, "valor": 1e12, "fornecedor": "F" * 300}]}, 200),
        ]
        for nome_c, corpo, st in rotas_constr:
            cenario(page, f"API construtora: {nome_c}", com_rota("**/api/construtora/resumo", corpo, st, "construtora", checa_construtora()))

        def sem_estouro_construtora():
            r = page.evaluate("""() => { const c = document.getElementById('construtora-card').getBoundingClientRect();
              return [...document.querySelectorAll('#tab-construtora .construtora-stat-valor, #lista-contas-a-vencer .lista-item-valor')]
                .some(e => e.getBoundingClientRect().right > Math.min(c.right, innerWidth) + 1); }""")
            return "valor estourou a coluna" if r else True
        cenario(page, "API construtora: gigante nao estoura 390px",
                com_rota("**/api/construtora/resumo", rotas_constr[-1][1], 200, "construtora", sem_estouro_construtora))

        rotas_bancos = [
            ("**/api/bancos", "500", "{}", 500), ("**/api/bancos", "JSON invalido", "{", 200),
            ("**/api/bancos", "conta estranha", [{"id": 1, "banco": None, "tipo": "cartao", "saldo": "abc",
                                                   "limite_info": {"fracao": "x"}, "ultima_transacao": "2026-09-01",
                                                   "total_transacoes": None, "total_gasto": None}], 200),
            ("**/api/patrimonio", "patrimonio vazio", {}, 200),
            ("**/api/bancos/sync-status", "status vazio", {}, 200),
        ]
        for padrao, nome_c, corpo, st in rotas_bancos:
            cenario(page, f"API bancos {padrao.split('/api/')[1]}: {nome_c}", com_rota(padrao, corpo, st, "bancos"))

        rotas_contas = [
            ("500", "{}", 500), ("JSON invalido", "}", 200), ("objeto em vez de lista", {"a": 1}, 200),
            ("itens sem campo", [{}, None, {"id": 7, "nome": None, "valor": "x", "proximo_vencimento": None, "dias_ate_vencer": "y"}], 200),
        ]
        for nome_c, corpo, st in rotas_contas:
            cenario(page, f"API contas pessoais: {nome_c}", com_rota("**/api/contas-pessoais", corpo, st, "vida"))

        def post_500():
            page.route("**/api/financas/assinaturas", lambda route: json_resp(route, '{"error":"falhou"}', 500)
                       if route.request.method == "POST" else route.continue_())
            try:
                recarregar(page, "gastos")
                page.click("#btn-nova-assinatura")
                time.sleep(0.3)
                preencher(page, {"#assinatura-nome": "X", "#assinatura-valor": "10", "#assinatura-dia": "3"})
                page.click("#assinatura-salvar-btn")
                time.sleep(0.6)
                msg = erro_visivel(page, "assinatura-erro")
                aberto = sheet_aberto(page, "sheet-nova-assinatura")
                btn_ok = page.evaluate("!document.getElementById('assinatura-salvar-btn').disabled")
                fechar_sheets(page)
                return True if (msg and aberto and btn_ok) else f"msg={msg!r} aberto={aberto} btn_ok={btn_ok}"
            finally:
                page.unroute("**/api/financas/assinaturas")
        cenario(page, "API POST assinatura 500: erro no sheet, botao volta", post_500)

        b.close()

    falhas = [r for r in resultados if not r[1]]
    for nome, ok, det in resultados:
        print(("OK   " if ok else "FALHA"), nome, ("- " + det if det else ""))
    print(f"\n{len(resultados)} cenarios, {len(falhas)} falha(s)")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
