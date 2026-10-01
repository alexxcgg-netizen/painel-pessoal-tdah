# tests/test_anim2_animacoes.py - Faixa anim2 (Onda 1 de animacao): lista sem reanimar,
# saida que fecha o espaco, contagem que termina no valor certo, barra por transform,
# copo d'agua sem disabled, fundo estatico, reduced-motion e um fuzz leve.
# Mesmo padrao de servidor real + banco temporario de tests/test_limpa_a_animacao.py
# (porta propria 8899).
import json
import os
import random
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "teste-fake")

import auth  # noqa: E402
import db  # noqa: E402

_tmp_dir = tempfile.TemporaryDirectory()
_DB_PROPRIO = Path(_tmp_dir.name) / "painel.db"
db.DB_PATH = _DB_PROPRIO
db.garantir_banco_nao_producao()

import app as app_module  # noqa: E402

PIN = "123456"
PORTA = int(os.environ.get("PORTA_TESTE_ANIM2", "8899"))
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

from tests.playwright_helper import get_chrome_path, abrir_tela  # noqa: E402

_CHROME = get_chrome_path()


def _nota(titulo):
    conn = db.get_db()
    cur = conn.execute("INSERT INTO notas (titulo, corpo) VALUES (?, ?)", (titulo, "corpo"))
    conn.commit()
    conn.close()
    return cur.lastrowid


def _limpar_notas():
    conn = db.get_db()
    conn.execute("DELETE FROM notas")
    conn.commit()
    conn.close()


def _contar_notas():
    conn = db.get_db()
    n = conn.execute("SELECT COUNT(*) FROM notas").fetchone()[0]
    conn.close()
    return n


@unittest.skipUnless(_PLAYWRIGHT_OK, "playwright nao instalado")
@unittest.skipUnless(_pronto, "servidor de teste nao respondeu")
class Anim2TestCase(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = _DB_PROPRIO
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()
        _limpar_notas()

    def _pagina(self, p, reduzido=False):
        kwargs = {"headless": True}
        if _CHROME is not None and Path(_CHROME).exists():
            kwargs["executable_path"] = _CHROME
        browser = p.chromium.launch(**kwargs)
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844}, reduced_motion="reduce" if reduzido else "no-preference"
        )
        r = ctx.request.post(BASE_URL + "/login", data=json.dumps({"pin": PIN}), headers={"Content-Type": "application/json"})
        self.assertEqual(r.status, 200, r.text())
        page = ctx.new_page()
        erros = []
        page.on("pageerror", lambda exc: erros.append(str(exc)))
        page.goto(BASE_URL + "/")
        page.wait_for_load_state("networkidle")
        abrir_tela(page, "painel")  # R1: Painel abre pelo Mais (saiu da barra)
        page.wait_for_selector("#lista-notas", state="attached")
        page.evaluate("loadNotas()")  # espera a carga inicial terminar (evita corrida com o teste)
        page.wait_for_timeout(300)
        return browser, page, erros

    def _recarregar_notas(self, page):
        page.evaluate("loadNotas()")
        page.wait_for_timeout(60)

    def _entrando(self, page):
        return page.evaluate("document.querySelectorAll('#lista-notas > li.c2-entra').length")

    def test_lista_nao_reanima_so_o_item_novo_entra(self):
        with sync_playwright() as p:
            browser, page, erros = self._pagina(p)
            try:
                for i in range(4):
                    _nota(f"anim2 nota {i}")
                self._recarregar_notas(page)
                self.assertEqual(self._entrando(page), 4, "itens novos entram (escalonados)")
                page.wait_for_timeout(1000)
                self.assertEqual(self._entrando(page), 0, "classe removida no fim (sem transform residual)")
                self._recarregar_notas(page)  # mesmos dados: nada anima
                self.assertEqual(self._entrando(page), 0)
                self.assertEqual(page.evaluate("document.querySelectorAll('#lista-notas > li').length"), 4)
                _nota("anim2 nota NOVA")
                self._recarregar_notas(page)
                self.assertEqual(self._entrando(page), 1, "so o item novo entra")
                self.assertIn("NOVA", page.evaluate("document.querySelector('#lista-notas > li.c2-entra').textContent"))
                self.assertEqual(erros, [])
            finally:
                browser.close()

    def test_apagar_fecha_espaco_e_remove_so_no_fim(self):
        for i in range(3):
            _nota(f"anim2 apagar {i}")
        with sync_playwright() as p:
            browser, page, erros = self._pagina(p)
            try:
                self._recarregar_notas(page)
                page.wait_for_timeout(900)
                y2_antes = page.locator("#lista-notas > li").nth(1).bounding_box()["y"]
                total = page.locator("#lista-notas > li").count()
                page.locator("#lista-notas > li").first.locator("button").evaluate("b => b.click()")
                page.wait_for_timeout(60)
                # ainda no DOM, ja marcado saindo
                self.assertEqual(page.locator("#lista-notas > li").count(), total)
                self.assertEqual(page.locator("#lista-notas > li.saindo").count(), 1)
                page.wait_for_timeout(800)
                self.assertEqual(page.locator("#lista-notas > li").count(), total - 1)
                y_depois = page.locator("#lista-notas > li").first.bounding_box()["y"]
                self.assertLess(y_depois, y2_antes, "o de baixo subiu (espaco fechou)")
                self.assertEqual(erros, [])
            finally:
                browser.close()

    def test_saida_tem_timeout_de_seguranca_sem_raf(self):
        _nota("anim2 sem raf a")
        _nota("anim2 sem raf b")
        with sync_playwright() as p:
            browser, page, erros = self._pagina(p)
            try:
                self._recarregar_notas(page)
                page.evaluate("window.requestAnimationFrame = () => 0")  # rAF pausado (2o plano no iOS)
                page.locator("#lista-notas > li").first.locator("button").evaluate("b => b.click()")
                page.wait_for_timeout(900)
                self.assertEqual(page.locator("#lista-notas > li").count(), 1)
                self.assertEqual(erros, [])
            finally:
                browser.close()

    def test_reduced_motion_sem_animacao_e_estado_final_certo(self):
        for i in range(3):
            _nota(f"anim2 reduzido {i}")
        with sync_playwright() as p:
            browser, page, erros = self._pagina(p, reduzido=True)
            try:
                self._recarregar_notas(page)
                self.assertEqual(self._entrando(page), 0)
                page.locator("#lista-notas > li").first.locator("button").evaluate("b => b.click()")
                page.wait_for_timeout(250)
                self.assertEqual(page.locator("#lista-notas > li").count(), 2)
                # contagem: valor final direto
                page.evaluate("window.__el = document.createElement('span'); document.body.appendChild(window.__el); animarNumero(window.__el, 42)")
                self.assertEqual(page.evaluate("window.__el.textContent"), "42")
                infinitas = page.evaluate(
                    "document.getAnimations().filter(a => a.effect && a.effect.getComputedTiming().iterations === Infinity && a.playState === 'running'"
                    " && !/carregando|shimmer|girar|spin/.test(String((a.effect.target && a.effect.target.className) || '') + (a.animationName || ''))).map(a => a.animationName)"
                )
                self.assertEqual(infinitas, [])
                self.assertEqual(erros, [])
            finally:
                browser.close()

    def test_contagem_termina_no_valor_final_mesmo_sem_raf(self):
        with sync_playwright() as p:
            browser, page, erros = self._pagina(p)
            try:
                page.evaluate(
                    "window.requestAnimationFrame = () => 0; window.__el = document.createElement('span');"
                    "document.body.appendChild(window.__el); animarNumero(window.__el, 137)"
                )
                page.wait_for_timeout(1100)
                self.assertEqual(page.evaluate("window.__el.textContent"), "137")
                # 2a contagem sobre a mesma: vence a ultima
                page.evaluate("animarNumero(window.__el, 5); animarNumero(window.__el, 9)")
                page.wait_for_timeout(1100)
                self.assertEqual(page.evaluate("window.__el.textContent"), "9")
                self.assertEqual(erros, [])
            finally:
                browser.close()

    def test_barra_por_transform_e_check_desenha(self):
        with sync_playwright() as p:
            browser, page, erros = self._pagina(p)
            try:
                r = page.evaluate(
                    """() => {
                      const trilho = document.createElement('div'); trilho.className = 'garantia-barra-trilho';
                      trilho.style.width = '200px';
                      const b = document.createElement('div'); b.className = 'garantia-barra-preenchido';
                      trilho.appendChild(b); document.querySelector('#tab-painel').appendChild(trilho);
                      definirProgressoBarra(b, 40);
                      return new Promise(res => setTimeout(() => res({
                        widthInline: b.style.width, p: b.style.getPropertyValue('--p'),
                        transform: getComputedStyle(b).transform, cls: b.className }), 700));
                    }"""
                )
                self.assertEqual(r["widthInline"], "")
                self.assertEqual(r["p"], "0.4")
                self.assertTrue(r["transform"].startswith("matrix(0.4"), r["transform"])
                self.assertNotIn("c2-barra-p", r["cls"])
                c = page.evaluate(
                    """() => {
                      const s = document.createElementNS('http://www.w3.org/2000/svg','svg');
                      s.setAttribute('viewBox','0 0 24 24'); s.setAttribute('width','24');
                      const path = document.createElementNS('http://www.w3.org/2000/svg','path');
                      path.setAttribute('d','M4 12l5 5L20 6'); s.appendChild(path);
                      const alvo = document.createElement('span'); alvo.appendChild(s);
                      document.querySelector('#tab-painel').appendChild(alvo);
                      animarCheck(alvo);
                      const desenha = path.classList.contains('c2-check-desenha');
                      const pulso = alvo.classList.contains('c2-pulso');
                      return new Promise(res => setTimeout(() => res({desenha, pulso, restou: alvo.classList.contains('c2-pulso')}), 900));
                    }"""
                )
                self.assertTrue(c["desenha"])
                self.assertTrue(c["pulso"])
                self.assertFalse(c["restou"])
                self.assertEqual(erros, [])
            finally:
                browser.close()

    def test_copo_dois_toques_rapidos_botao_nunca_disabled(self):
        with sync_playwright() as p:
            browser, page, erros = self._pagina(p)
            try:
                page.route("**/api/hidratacao", lambda route: (time.sleep(0.25), route.continue_())[1] if route.request.method == "POST" else route.continue_())
                page.evaluate("document.getElementById('hidratacao-total').textContent = '0'")
                antes = page.evaluate("fetch('/api/saude/hoje').then(r => r.json()).then(d => d.hidratacao_hoje)")
                btn = page.locator("#hidratacao-btn")
                btn.click(force=True)
                btn.click(force=True)
                self.assertFalse(btn.is_disabled())
                self.assertEqual(page.evaluate("document.getElementById('hidratacao-total').textContent"), "2")
                self.assertEqual(page.evaluate("document.querySelector('.hidratacao-flutuante')"), None)
                page.wait_for_timeout(1500)
                self.assertFalse(btn.is_disabled())
                depois = page.evaluate("fetch('/api/saude/hoje').then(r => r.json()).then(d => d.hidratacao_hoje)")
                self.assertEqual(depois - antes, 2)
                self.assertEqual(page.evaluate("document.getElementById('hidratacao-total').textContent"), str(depois))
                nivel = float(page.evaluate("document.getElementById('hidratacao-nivel').style.getPropertyValue('--nivel')"))
                self.assertAlmostEqual(nivel, min(1, depois / 8), places=3)
                self.assertEqual(erros, [])
            finally:
                browser.close()

    def test_fundo_estatico_sem_animacao(self):
        with sync_playwright() as p:
            browser, page, erros = self._pagina(p)
            try:
                page.wait_for_timeout(500)
                r = page.evaluate(
                    """() => {
                      const a = document.querySelector('.aurora');
                      const cs = getComputedStyle(a);
                      const infinitas = document.getAnimations().filter(x => x.effect && x.effect.getComputedTiming().iterations === Infinity && x.playState === 'running')
                        .map(x => (x.effect.target && (x.effect.target.className || x.effect.target.tagName)) || '?')
                        .filter(c => !/carregando|shimmer/.test(String(c)));
                      return {anim: cs.animationName, filter: cs.filter,
                        auroraAnims: a.getAnimations({subtree: true}).length,
                        bodyAnims: document.body.getAnimations().length, infinitas};
                    }"""
                )
                self.assertEqual(r["anim"], "none")
                self.assertEqual(r["filter"], "none")
                self.assertEqual(r["auroraAnims"], 0)
                self.assertEqual(r["infinitas"], [], r["infinitas"])
                self.assertEqual(erros, [])
            finally:
                browser.close()

    def test_fuzz_leve_lista_consistente_com_os_dados(self):
        rnd = random.Random(20260930)
        with sync_playwright() as p:
            browser, page, erros = self._pagina(p)
            try:
                for i in range(3):
                    _nota(f"fuzz base {i}")
                self._recarregar_notas(page)
                cenarios = 0
                for passo in range(36):
                    op = rnd.choice(["add", "add", "apagar", "aba", "reduzido", "normal", "recarregar", "raf"])
                    if op == "add":
                        _nota(f"fuzz {passo} " + "x" * rnd.choice([1, 20, 400]))
                        self._recarregar_notas(page)
                    elif op == "apagar":
                        loc = page.locator("#lista-notas > li:not(.saindo)")
                        if loc.count():
                            loc.nth(rnd.randrange(loc.count())).locator("button").evaluate("b => b.click()")
                            page.wait_for_timeout(rnd.choice([0, 30, 120, 300]))
                    elif op == "aba":
                        abrir_tela(page, rnd.choice(["hoje", "tarefas", "painel"]))  # R1: via Mais se fora da barra
                        abrir_tela(page, "painel")
                    elif op == "reduzido":
                        page.emulate_media(reduced_motion="reduce")
                    elif op == "normal":
                        page.emulate_media(reduced_motion="no-preference")
                    elif op == "recarregar":
                        self._recarregar_notas(page)
                    elif op == "raf":
                        page.evaluate("window.requestAnimationFrame = () => 0")
                    cenarios += 1
                page.wait_for_timeout(1200)
                self._recarregar_notas(page)
                page.wait_for_timeout(1000)
                self.assertGreaterEqual(cenarios, 30)
                dom_ids = page.evaluate("Array.from(document.querySelectorAll('#lista-notas > li')).map(li => li.textContent)")
                self.assertEqual(len(dom_ids), _contar_notas(), "DOM final = dados")
                self.assertEqual(len(dom_ids), len(set(dom_ids)), "sem item duplicado")
                self.assertEqual(page.locator("#lista-notas > li.saindo").count(), 0, "sem fantasma")
                self.assertEqual(page.locator("#lista-notas > li.c2-entra").count(), 0)
                self.assertEqual(erros, [])
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
