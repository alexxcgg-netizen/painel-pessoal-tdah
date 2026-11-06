# tests/test_vis_c2_animacao.py - Vis (C2b, skill animacoes-interface):
# confere que o sistema de movimento novo (static/css/ui/movimento.css,
# static/js/nucleo/movimento.js + ganchos pequenos em navegacao.js/gastos.js/
# api.js/captura.js) nao quebra nenhuma das 8 abas e que "reduzir movimento"
# e respeitado de verdade (nao so no papel): concluir tarefa e trocar de aba
# continuam funcionando, nada fica "preso" com opacidade menor que 1 depois
# de um tempo razoavel, e numero que normalmente conta aparece direto no
# valor final.
#
# Mesmo padrao de banco temporario + servidor HTTP real (numa thread) de
# tests/test_vel_a2b_otimista.py (db.DB_PATH reapontado ANTES de importar
# app, porque outros modulos de teste tambem trocam db.DB_PATH na propria
# importacao e todos rodam no mesmo processo quando a suite roda junta).
import json
import os
import tempfile
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
PORTA = int(os.environ.get("PORTA_TESTE_VIS_C2", "8846"))
BASE_URL = f"http://127.0.0.1:{PORTA}"

# Mesma ordem de static/js/nucleo/navegacao.js (ORDEM_ABAS) - as 8 abas do app.
ABAS = ["hoje", "painel", "aviacao", "vida", "tarefas", "gastos", "construtora", "assistente"]

db.init_db()
_conn = db.get_db()
auth.definir_pin(_conn, PIN, PIN)
_conn.commit()
_conn.close()

from tests.playwright_helper import subir_servidor  # noqa: E402

subir_servidor(app_module.app, PORTA)
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

from tests.playwright_helper import CONTAR_FETCH, abrir_tela, esperar_assentar, esperar_carga, get_chrome_path; _CHROME = get_chrome_path()


@unittest.skipUnless(_PLAYWRIGHT_OK, "playwright nao instalado")
@unittest.skipUnless(_pronto, "servidor de teste nao respondeu")
class VisC2AnimacaoTestCase(unittest.TestCase):
    def setUp(self):
        # Outros modulos de teste tambem trocam db.DB_PATH na importacao; o
        # servidor deste modulo roda no mesmo processo, entao reaponta pro
        # banco proprio antes de cada teste (senao: "no such table" quando a
        # suite roda junta).
        db.DB_PATH = _DB_PROPRIO
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()

    def _novo_browser(self, p, **context_kwargs):
        kwargs = {"headless": True}
        if _CHROME is not None and Path(_CHROME).exists():
            kwargs["executable_path"] = _CHROME
        browser = p.chromium.launch(**kwargs)
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, **context_kwargs)
        r = ctx.request.post(
            BASE_URL + "/login",
            data=json.dumps({"pin": PIN}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(r.status, 200, r.text())
        return browser, ctx

    # ---- (a) sem "reduzir movimento": passa pelas 8 abas, 0 pageerror ----

    def test_8_abas_sem_reduzir_movimento_zero_pageerror(self):
        with sync_playwright() as p:
            browser, ctx = self._novo_browser(p)
            try:
                erros = []
                page = ctx.new_page()
                page.on("pageerror", lambda exc: erros.append(str(exc)))
                page.add_init_script(CONTAR_FETCH)
                page.goto(BASE_URL + "/")
                page.wait_for_load_state("networkidle")
                esperar_assentar(page, "#tab-hoje")

                for aba in ABAS:
                    abrir_tela(page, aba)  # R1: barra de 5 - fora dela, abre pelo Mais
                    page.wait_for_function(
                        f"document.querySelector('#tab-{aba}') && !document.querySelector('#tab-{aba}').hidden"
                    )
                    esperar_carga(page)  # um erro ao desenhar a resposta so vira pageerror depois que ela volta
                    secao = page.locator(f"#tab-{aba}")
                    self.assertTrue(secao.is_visible(), f"aba {aba} nao ficou visivel")

                # o desenho da ultima resposta vem depois do fetch resolver
                esperar_assentar(page, "#tab-assistente")
                self.assertEqual(erros, [], f"pageerror ao passar pelas 8 abas: {erros}")
            finally:
                browser.close()

    # ---- (b) com "reduzir movimento" ----

    def test_reduzir_movimento_concluir_e_trocar_de_aba_funcionam_sem_animar(self):
        with sync_playwright() as p:
            browser, ctx = self._novo_browser(p, reduced_motion="reduce")
            try:
                rt = ctx.request.post(
                    BASE_URL + "/api/tasks",
                    data=json.dumps({"titulo": "vis c2 tarefa reduzir movimento"}),
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(rt.status, 201, rt.text())

                erros = []
                page = ctx.new_page()
                page.on("pageerror", lambda exc: erros.append(str(exc)))
                page.emulate_media(reduced_motion="reduce")
                page.goto(BASE_URL + "/")
                page.wait_for_load_state("networkidle")
                esperar_assentar(page, "#tab-hoje")

                # ---- concluir tarefa continua funcionando ----
                page.click('.tab-btn[data-tab="tarefas"]')
                page.wait_for_selector("#lista-tarefas li")
                n_antes = page.locator("#lista-tarefas li").count()
                page.locator("#lista-tarefas .tt-caixa").first.click(force=True)
                page.wait_for_function(
                    "(n) => document.querySelectorAll('#lista-tarefas li').length < n",
                    arg=n_antes,
                    timeout=2000,
                )

                # ---- trocar de aba continua funcionando ----
                page.click('.tab-btn[data-tab="gastos"]')
                page.wait_for_function(
                    "document.querySelector('#tab-gastos') && !document.querySelector('#tab-gastos').hidden"
                )
                page.wait_for_selector("#fc-frase-resumo")
                page.wait_for_function(
                    "document.querySelector('#fc-frase-resumo').textContent.includes('Você gastou')"
                )

                # ---- "gasto do mes" mostra o valor final direto, sem contar:
                # com reduzir movimento, animarNumero (nucleo/ui.js) escreve o
                # valor formatado final de uma vez (sem loop de requestAnimationFrame)
                # - confere lendo o texto 2x, e batendo igual (se
                # estivesse contando de verdade, o valor mudaria entre as leituras). ----
                frase_texto_1 = page.eval_on_selector("#fc-frase-resumo", "el => el.textContent")
                self.assertIn("Você gastou", frase_texto_1)
                frase_texto_2 = page.eval_on_selector("#fc-frase-resumo", "el => el.textContent")
                self.assertEqual(
                    frase_texto_1, frase_texto_2, "frase-resumo mudou de valor - parece estar contando mesmo com reduzir movimento"
                )

                # ---- 300ms depois, nada visivel com opacity < 1 nos
                # elementos que o sistema de movimento anima (cards
                # escalonados, toasts, tab entrando) ----
                page.wait_for_timeout(300)
                problemas = page.evaluate(
                    """
                    () => {
                      const seletores = [
                        '.c2-entra', '.c2-titulo-riscando', '.c2-check-desenha',
                        '.entra-direita', '.entra-esquerda', '.c2-toast-entra',
                        '#tab-gastos', '#lista-tarefas li'
                      ];
                      const problemas = [];
                      seletores.forEach((sel) => {
                        document.querySelectorAll(sel).forEach((el) => {
                          const r = el.getBoundingClientRect();
                          const visivel = r.width > 0 && r.height > 0 && !el.hidden;
                          if (!visivel) return;
                          const op = parseFloat(getComputedStyle(el).opacity);
                          if (op < 1) problemas.push(sel + ' -> ' + (el.id || el.className));
                        });
                      });
                      return problemas;
                    }
                    """
                )
                self.assertEqual(problemas, [], f"elementos ainda com opacity < 1 depois de 300ms: {problemas}")
                self.assertEqual(erros, [], f"pageerror com reduzir movimento: {erros}")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
