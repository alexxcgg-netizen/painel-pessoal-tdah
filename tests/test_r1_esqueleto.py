# tests/test_r1_esqueleto.py - Reformulacao R1 (esqueleto): barra de 5 itens,
# tela Mais (cada linha abre a tela certa + "‹" volta), botao "+" (FAB) com a
# folha de captura, chat na tela IA com campo fixo, nada fixo cobrindo o fim
# do conteudo, reduced-motion e zero pageerror.
# Mesmo padrao de servidor real + Playwright de tests/test_limpa_d_financas.py
# (banco temporario, db.DB_PATH reapontado antes de cada teste). IA nunca e
# chamada de verdade: classify_capture e chat sao trocados por fakes (o
# servidor roda no mesmo processo, entao o patch vale pra ele).
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
_DB_PROPRIO = Path(_tmp_dir.name) / "painel.db"
db.DB_PATH = _DB_PROPRIO
db.garantir_banco_nao_producao()

import app as app_module  # noqa: E402

PIN = "123456"
PORTA = int(os.environ.get("PORTA_TESTE_R1", "8871"))
BASE_URL = f"http://127.0.0.1:{PORTA}"

db.init_db()
_conn = db.get_db()
auth.definir_pin(_conn, PIN, PIN)
_conn.commit()
_conn.close()

_thread = threading.Thread(
    target=lambda: app_module.app.run(host="127.0.0.1", port=PORTA, use_reloader=False, threaded=True),
    daemon=True,
)
_thread.start()
_pronto = False
for _ in range(50):
    try:
        urllib.request.urlopen(BASE_URL + "/", timeout=1)
        _pronto = True
        break
    except Exception:
        time.sleep(0.2)

try:
    from playwright.sync_api import sync_playwright

    _PLAYWRIGHT_OK = True
except Exception:
    _PLAYWRIGHT_OK = False

from tests.playwright_helper import get_chrome_path  # noqa: E402

_CHROME = get_chrome_path()

BARRA = ["hoje", "tarefas", "assistente", "gastos", "mais"]
ROTULOS = ["Início", "Tarefas", "IA", "Finanças", "Mais"]
TELAS_DO_MAIS = ["painel", "vida", "aviacao", "construtora", "ajustes-ia", "config"]
TELAS_COM_FAB = ["hoje", "tarefas", "gastos"]


def fake_usage():
    return {"model": "claude-sonnet-4-5", "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.0001}


@unittest.skipUnless(_PLAYWRIGHT_OK, "playwright nao instalado")
@unittest.skipUnless(_pronto, "servidor de teste nao respondeu")
class R1EsqueletoTestCase(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = _DB_PROPRIO
        db.init_db()
        conn = db.get_db()
        conn.execute("DELETE FROM expenses")
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()
        # resumo do dia (aba Painel/Inicio) e IA: fake, nunca rede (sem isso o 502 do resumo
        # mostra o #erro-banner no topo e a pagina "pula" no meio das medidas).
        resumo = patch("claude_client.summarize_day", return_value=("Resumo de teste.", fake_usage()))
        resumo.start()
        self.addCleanup(resumo.stop)

    # ---- infraestrutura ----
    def _abrir(self, p, largura=390, reduzir=False):
        kwargs = {"headless": True}
        if _CHROME is not None and Path(_CHROME).exists():
            kwargs["executable_path"] = _CHROME
        browser = p.chromium.launch(**kwargs)
        ctx = browser.new_context(
            viewport={"width": largura, "height": 844},
            reduced_motion="reduce" if reduzir else "no-preference",
        )
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(BASE_URL) else r.abort())
        r = ctx.request.post(
            BASE_URL + "/login", data=json.dumps({"pin": PIN}), headers={"Content-Type": "application/json"}
        )
        self.assertEqual(r.status, 200, r.text())
        page = ctx.new_page()
        erros = []
        page.on("pageerror", lambda exc: erros.append(str(exc)))
        page.goto(BASE_URL + "/")
        page.wait_for_load_state("networkidle")
        return browser, page, erros

    def _visivel(self, page, aba):
        return page.evaluate(f"(() => {{ const el = document.getElementById('tab-{aba}'); return !!el && !el.hidden; }})()")

    def _ativo(self, page):
        return page.evaluate("[...document.querySelectorAll('.tab-btn.active')].map(b => b.dataset.tab)")

    # ---- 1. barra ----
    def test_barra_tem_5_itens_com_labels_inteiros(self):
        with sync_playwright() as p:
            for largura in (390, 320):
                browser, page, erros = self._abrir(p, largura=largura)
                try:
                    abas = page.evaluate("[...document.querySelectorAll('#tabbar .tab-btn')].map(b => b.dataset.tab)")
                    self.assertEqual(abas, BARRA)
                    rotulos = page.evaluate(
                        "[...document.querySelectorAll('#tabbar .tab-btn-rotulo')].map(s => s.textContent.trim())"
                    )
                    self.assertEqual(rotulos, ROTULOS)
                    cortados = page.evaluate(
                        """[...document.querySelectorAll('#tabbar .tab-btn')].filter(b => {
                            const s = b.querySelector('.tab-btn-rotulo');
                            const rs = s.getBoundingClientRect(), rb = b.getBoundingClientRect();
                            return s.scrollWidth > s.clientWidth + 0.5 || b.scrollWidth > b.clientWidth + 0.5
                                || rs.left < rb.left - 0.5 || rs.right > rb.right + 0.5;
                        }).map(b => b.dataset.tab)"""
                    )
                    self.assertEqual(cortados, [], f"rotulo cortado em {largura}px")
                    alturas = page.evaluate("[...document.querySelectorAll('#tabbar .tab-btn')].map(b => b.getBoundingClientRect().height)")
                    self.assertTrue(all(h >= 44 for h in alturas), alturas)
                    sem_scroll = page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
                    self.assertTrue(sem_scroll, f"scroll horizontal em {largura}px")
                    # cada item da barra abre a propria tela e fica ativo
                    for aba in BARRA:
                        page.click(f'.tab-btn[data-tab="{aba}"]')
                        self.assertTrue(self._visivel(page, aba), aba)
                        self.assertEqual(self._ativo(page), [aba])
                    self.assertEqual(erros, [])
                finally:
                    browser.close()

    # ---- 2. Mais ----
    def test_cada_linha_do_mais_abre_a_tela_certa_e_voltar_funciona(self):
        with sync_playwright() as p:
            browser, page, erros = self._abrir(p)
            try:
                page.click('.tab-btn[data-tab="mais"]')
                page.wait_for_timeout(700)  # fim da animacao de entrada (mede layout assentado)
                linhas = page.evaluate(
                    "[...document.querySelectorAll('#tab-mais [data-abre-tela]')].map(b => [b.dataset.abreTela, b.dataset.alvo || null, b.querySelector('.mais-titulo').textContent.trim()])"
                )
                destinos = {d for d, _a, _t in linhas}
                self.assertTrue(set(TELAS_DO_MAIS) <= destinos, destinos)
                titulos = [t for _d, _a, t in linhas]
                for esperado in ["Saúde", "Hábitos e metas", "Pessoas", "Viagens e lugares", "Notas e ideias",
                                 "Meu dia", "Vida completa", "Aviação", "Construtora", "Avisos e regras", "Configurações"]:
                    self.assertIn(esperado, titulos)
                altura_min = page.evaluate("Math.min(...[...document.querySelectorAll('#tab-mais .mais-linha')].map(l => l.getBoundingClientRect().height))")
                self.assertGreaterEqual(altura_min, 63.5)
                for i, (destino, alvo, titulo) in enumerate(linhas):
                    page.click('.tab-btn[data-tab="mais"]')
                    page.evaluate("window.scrollTo(0, 0)")
                    page.locator("#tab-mais [data-abre-tela]").nth(i).click()
                    page.wait_for_timeout(900)  # rolagem suave ate o alvo + animacao de entrada
                    self.assertTrue(self._visivel(page, destino), f"{titulo} nao abriu #tab-{destino}")
                    self.assertFalse(self._visivel(page, "mais"))
                    self.assertEqual(self._ativo(page), ["mais"], f"{titulo}: item Mais deveria ficar ativo")
                    if alvo:
                        topo = page.evaluate(
                            f"""(() => {{ const el = document.querySelector('#tab-{destino}').querySelector({json.dumps(alvo)});
                                const b = (el.closest('.card, .secao-recolhivel') || el).getBoundingClientRect();
                                return [b.top, b.bottom]; }})()"""
                        )
                        self.assertLess(topo[0], 844, f"{titulo}: alvo {alvo} nao ficou na tela ({topo})")
                        self.assertGreater(topo[1], 0, f"{titulo}: alvo {alvo} nao ficou na tela ({topo})")
                        aberto = page.evaluate(
                            f"""(() => {{ const el = document.querySelector('#tab-{destino}').querySelector({json.dumps(alvo)});
                                const s = el.closest('.secao-recolhivel'); return s ? s.dataset.aberto : 'sem-secao'; }})()"""
                        )
                        self.assertIn(aberto, ("true", "sem-secao"), f"{titulo}: secao nao abriu")
                    if destino in TELAS_DO_MAIS:
                        page.click(f"#tab-{destino} .cab-tela-voltar")
                        self.assertTrue(self._visivel(page, "mais"), f"voltar de {destino} nao voltou pro Mais")
                        self.assertEqual(self._ativo(page), ["mais"])
                self.assertEqual(erros, [])
            finally:
                browser.close()

    def test_direcao_da_troca_e_cache_de_30s_continuam(self):
        with sync_playwright() as p:
            browser, page, erros = self._abrir(p)
            try:
                pedidos = []
                page.on("request", lambda r: pedidos.append(r.url) if "/api/habitos" in r.url else None)
                page.click('.tab-btn[data-tab="mais"]')
                page.click('#tab-mais [data-abre-tela="vida"]:not([data-alvo])')
                self.assertTrue(page.evaluate("document.getElementById('tab-vida').classList.contains('entra-direita')"))
                page.wait_for_timeout(600)
                primeira = len(pedidos)
                self.assertGreaterEqual(primeira, 1, "Vida deveria carregar ao abrir pelo Mais")
                page.click("#tab-vida .cab-tela-voltar")
                self.assertTrue(page.evaluate("document.getElementById('tab-mais').classList.contains('entra-esquerda')"))
                page.click('#tab-mais [data-abre-tela="vida"]:not([data-alvo])')
                page.wait_for_timeout(600)
                self.assertEqual(len(pedidos), primeira, "segunda abertura em < 30 s nao devia recarregar")
                # Avisos e regras carrega a caixa ao abrir (evento aba:aberta)
                caixa = []
                page.on("request", lambda r: caixa.append(r.url) if "/api/p4_caixa" in r.url or "caixa" in r.url else None)
                page.evaluate("showTab('ajustes-ia')")
                page.wait_for_timeout(500)
                self.assertTrue(self._visivel(page, "ajustes-ia"))
                self.assertGreaterEqual(len(caixa), 1, "Avisos e regras deveria carregar a caixa ao abrir")
                self.assertEqual(erros, [])
            finally:
                browser.close()

    # ---- 3. FAB + folha ----
    def test_fab_abre_e_fecha_a_folha_e_a_captura_envia(self):
        parsed = {"tipo": "gasto", "titulo": "mercado r1", "valor": 42.0, "categoria": "mercado", "quando": None, "duvida": None}
        with sync_playwright() as p:
            browser, page, erros = self._abrir(p)
            try:
                for aba in BARRA:
                    page.click(f'.tab-btn[data-tab="{aba}"]')
                    visivel = page.locator("#fab-captura").is_visible()
                    self.assertEqual(visivel, aba in TELAS_COM_FAB, f"FAB em {aba}")
                page.evaluate("showTab('vida')")
                self.assertFalse(page.locator("#fab-captura").is_visible())
                page.click('.tab-btn[data-tab="hoje"]')
                caixa = page.locator("#fab-captura").bounding_box()
                self.assertGreaterEqual(caixa["width"], 59.5)
                self.assertGreaterEqual(caixa["height"], 59.5)

                # abre / ESC fecha
                page.click("#fab-captura")
                page.wait_for_selector("#folha-captura.bottom-sheet--aberto")
                page.wait_for_timeout(350)
                self.assertTrue(page.evaluate("document.getElementById('folha-captura').contains(document.activeElement)"),
                                "foco deveria ficar dentro da folha")
                self.assertTrue(page.locator("#captura-input").is_visible())
                self.assertEqual(page.locator(".folha-atalho").count(), 4)
                self.assertTrue(page.locator("#comando-voz-btn").is_visible())
                # foco preso: Tab varias vezes nao sai da folha
                for _ in range(12):
                    page.keyboard.press("Tab")
                self.assertTrue(page.evaluate("document.getElementById('folha-captura').contains(document.activeElement)"))
                page.keyboard.press("Escape")
                page.wait_for_function("document.getElementById('folha-captura').hidden")

                # abre / toque no veu fecha
                page.click("#fab-captura")
                page.wait_for_selector("#folha-captura.bottom-sheet--aberto")
                page.wait_for_timeout(350)
                page.mouse.click(195, 40)
                page.wait_for_function("document.getElementById('folha-captura').hidden")

                # atalho poe prefixo no mesmo campo; captura envia
                page.click("#fab-captura")
                page.wait_for_selector("#folha-captura.bottom-sheet--aberto")
                page.wait_for_timeout(350)
                page.click('.folha-atalho[data-prefixo="gastei "]')
                self.assertEqual(page.input_value("#captura-input"), "gastei ")
                page.click('.folha-atalho[data-prefixo="tarefa: "]')
                self.assertEqual(page.input_value("#captura-input"), "tarefa: ", "trocar de atalho troca o prefixo")
                page.fill("#captura-input", "gastei 42 no mercado r1")
                with patch("claude_client.classify_capture", return_value=(parsed, fake_usage())):
                    page.click("#captura-btn")
                    page.wait_for_selector("#captura-retorno:not([hidden])", timeout=10000)
                self.assertIn("Salvo", page.inner_text("#captura-retorno"))
                gastos = page.evaluate("fetch('/api/expenses').then(r => r.json())")
                self.assertTrue(any(abs(g["amount"] - 42.0) < 0.001 for g in gastos), gastos)
                # o resultado tambem fica no historico da conversa (tela IA)
                self.assertGreaterEqual(page.locator("#chat-mensagens > *").count(), 1)
                page.keyboard.press("Escape")
                page.wait_for_function("document.getElementById('folha-captura').hidden")
                self.assertEqual(erros, [])
            finally:
                browser.close()

    # ---- 4. chat na tela IA ----
    def test_chat_mora_na_tela_ia_com_campo_fixo_e_envia(self):
        def fake_chat(mensagens, contexto, memorias, executores):
            return "Resposta de teste do R1.", [], fake_usage()

        with sync_playwright() as p:
            browser, page, erros = self._abrir(p)
            try:
                self.assertEqual(page.locator("#tab-hoje #chat-form").count(), 0, "chat saiu do Inicio")
                self.assertEqual(page.locator("#tab-assistente #chat-form").count(), 1)
                self.assertEqual(page.locator("#tab-ajustes-ia #secao-caixa-assistente").count(), 1)
                page.click('.tab-btn[data-tab="assistente"]')
                page.wait_for_timeout(800)  # fim da animacao de entrada (mede layout assentado)
                form = page.locator("#chat-form").bounding_box()
                barra = page.locator("#tabbar").bounding_box()
                self.assertGreaterEqual(form["height"], 55.5)
                self.assertLessEqual(form["y"] + form["height"], barra["y"] + 0.5, "campo deveria ficar acima da barra")
                page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                page.wait_for_timeout(200)
                lista = page.locator("#chat-mensagens").bounding_box()
                self.assertLessEqual(lista["y"] + lista["height"], form["y"] + 0.5, "lista nao pode ficar atras do campo")
                self.assertEqual(page.evaluate("getComputedStyle(document.getElementById('chat-form')).position"), "fixed")
                page.fill("#chat-input", "oi, teste do r1")
                with patch("claude_client.chat", side_effect=fake_chat):
                    page.click("#chat-send")
                    page.wait_for_function(
                        "document.getElementById('chat-mensagens').textContent.includes('Resposta de teste do R1')",
                        timeout=10000,
                    )
                page.wait_for_timeout(300)
                # a ultima mensagem fica visivel logo acima do campo fixo (pagina rola pro fim)
                ultima = page.evaluate("(() => { const r = document.getElementById('chat-mensagens').lastElementChild.getBoundingClientRect(); return [r.top, r.bottom]; })()")
                topo_form = page.evaluate("document.getElementById('chat-form').getBoundingClientRect().top")
                self.assertGreaterEqual(ultima[0], 0, "ultima mensagem deveria estar na tela")
                self.assertLessEqual(ultima[1], topo_form + 0.5, "ultima mensagem nao pode ficar atras do campo")
                self.assertEqual(erros, [])
            finally:
                browser.close()

    # ---- 5. nada fixo cobre o fim do conteudo ----
    def test_nenhum_elemento_fixo_cobre_o_ultimo_conteudo(self):
        with sync_playwright() as p:
            browser, page, erros = self._abrir(p)
            try:
                for aba in BARRA + TELAS_DO_MAIS:
                    page.evaluate(f"showTab('{aba}')")
                    page.wait_for_timeout(500)
                    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                    page.wait_for_timeout(250)
                    medida = page.evaluate(
                        f"""(() => {{
                            const tela = document.getElementById('tab-{aba}');
                            const filhos = [...tela.children].filter(el => {{
                                if (el.id === 'chat-form') return false;
                                const r = el.getBoundingClientRect();
                                return r.height > 0 && getComputedStyle(el).position !== 'fixed';
                            }});
                            const ultimo = filhos[filhos.length - 1];
                            const fundo = ultimo.getBoundingClientRect().bottom;
                            const tetos = [document.getElementById('tabbar').getBoundingClientRect().top];
                            const fab = document.getElementById('fab-captura');
                            if (fab && !fab.hidden) tetos.push(fab.getBoundingClientRect().top);
                            const form = document.getElementById('chat-form');
                            if (tela.contains(form)) tetos.push(form.getBoundingClientRect().top);
                            return {{ fundo, teto: Math.min(...tetos), quem: ultimo.id || ultimo.className }};
                        }})()"""
                    )
                    self.assertLessEqual(
                        medida["fundo"], medida["teto"] + 0.5,
                        f"{aba}: ultimo conteudo ({medida['quem']}) termina em {medida['fundo']}, chrome fixo comeca em {medida['teto']}",
                    )
                self.assertEqual(erros, [])
            finally:
                browser.close()

    # ---- 6. reduced-motion ----
    def test_reduced_motion_troca_e_folha_sem_animacao_e_sem_erro(self):
        with sync_playwright() as p:
            browser, page, erros = self._abrir(p, reduzir=True)
            try:
                for aba in BARRA + TELAS_DO_MAIS:
                    page.evaluate(f"showTab('{aba}')")
                    self.assertTrue(self._visivel(page, aba))
                page.click('.tab-btn[data-tab="hoje"]')
                page.click("#fab-captura")
                page.wait_for_selector("#folha-captura.bottom-sheet--aberto")
                dur = page.evaluate(
                    "parseFloat(getComputedStyle(document.querySelector('#folha-captura .bottom-sheet-painel')).transitionDuration)"
                )
                self.assertLess(dur, 0.02, "folha deveria abrir sem transicao com reduced-motion")
                page.keyboard.press("Escape")
                page.wait_for_function("document.getElementById('folha-captura').hidden")
                self.assertEqual(erros, [])
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
