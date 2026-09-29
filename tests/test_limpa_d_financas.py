# tests/test_limpa_d_financas.py - Faixa limpa/d-financas: a aba Financas
# tinha duas listas quase iguais (o extrato novo "Ultimos dias" no topo
# estilo Conversa e a lista antiga #lista-gastos mais abaixo, paginada via
# /api/gastos/unificados) - este teste confere que sobrou UMA lista so (o
# extrato) e que as acoes que so a lista antiga tinha (corrigir categoria,
# "e tarefa") migraram pros itens manuais dessa lista unica e continuam
# funcionando de ponta a ponta. Mesmo padrao de servidor real + Playwright
# de tests/test_vel_a2b_otimista.py (banco temporario, db.DB_PATH
# reapontado antes de cada teste).
import json
import os
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
PORTA = int(os.environ.get("PORTA_TESTE_LIMPA_D", "8853"))
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

from tests.playwright_helper import get_chrome_path; _CHROME = get_chrome_path()


def _lancar_browser(p):
    kwargs = {"headless": True}
    if _CHROME is not None and Path(_CHROME).exists():
        kwargs["executable_path"] = _CHROME
    return p.chromium.launch(**kwargs)


@unittest.skipUnless(_PLAYWRIGHT_OK, "playwright nao instalado")
@unittest.skipUnless(_pronto, "servidor de teste nao respondeu")
class LimpaDFinancasTestCase(unittest.TestCase):
    def setUp(self):
        # Outros modulos de teste tambem trocam db.DB_PATH na importacao; o
        # servidor deste modulo roda no mesmo processo, entao reaponta pro
        # banco proprio antes de cada teste (senao: "no such table" quando a
        # suite roda junta).
        db.DB_PATH = _DB_PROPRIO
        db.init_db()
        conn = db.get_db()
        conn.execute("DELETE FROM expenses")
        conn.execute("DELETE FROM tasks")
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()

    def _login_e_abrir_financas(self, ctx):
        r = ctx.request.post(
            BASE_URL + "/login",
            data=json.dumps({"pin": PIN}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(r.status, 200, r.text())
        page = ctx.new_page()
        erros = []
        page.on("pageerror", lambda exc: erros.append(str(exc)))
        page.goto(BASE_URL + "/")
        page.wait_for_load_state("networkidle")
        page.click('.tab-btn[data-tab="gastos"]')
        # O cartao "Ultimos dias" comeca recolhido (pedido do dono, movimento.js
        # ligarDetalheAnimado) - o <ul> existe no DOM mas com altura 0 até abrir
        # o <summary>; e mesmo aberto, uma lista vazia tem altura 0 (sem
        # "visible" pro Playwright) - por isso espera o aria-expanded do
        # summary virar "true" em vez de esperar o <ul> ficar visivel.
        page.wait_for_selector("#lista-extrato-financas", state="attached")
        page.click("#fc-card-ultimos-dias summary")
        page.wait_for_selector('#fc-card-ultimos-dias summary[aria-expanded="true"]')
        return page, erros

    def test_uma_lista_so_na_aba_financas(self):
        conn = db.get_db()
        db.criar_gasto_de_brain_dump(conn, 9.9, "outros", "so pra lista nao ficar vazia")
        conn.close()

        with sync_playwright() as p:
            browser = _lancar_browser(p)
            try:
                ctx = browser.new_context(viewport={"width": 390, "height": 844})
                page, erros = self._login_e_abrir_financas(ctx)
                page.wait_for_selector("#lista-extrato-financas li")

                # #lista-gastos (lista antiga) nao existe mais no DOM - nao e
                # so "escondida", a secao "Extrato completo" saiu de vez.
                self.assertEqual(page.locator("#lista-gastos").count(), 0)
                self.assertEqual(page.locator('[data-secao-id="gastos-extrato-completo"]').count(), 0)

                # A unica lista de gastos da aba e o extrato novo.
                self.assertEqual(page.locator("#lista-extrato-financas").count(), 1)
                self.assertTrue(page.locator("#lista-extrato-financas").is_visible())

                self.assertEqual(erros, [], f"pageerror inesperado: {erros}")
            finally:
                browser.close()

    def test_item_manual_mostra_e_usa_a_acao_de_corrigir_categoria(self):
        conn = db.get_db()
        gasto_id = db.criar_gasto_de_brain_dump(conn, 42.5, "mercado", "Compras da semana - teste limpa D")
        conn.close()

        with sync_playwright() as p:
            browser = _lancar_browser(p)
            try:
                ctx = browser.new_context(viewport={"width": 390, "height": 844})
                page, erros = self._login_e_abrir_financas(ctx)

                item = page.locator("#lista-extrato-financas li.fc-extrato-editavel", has_text="Compras da semana")
                page.wait_for_selector("#lista-extrato-financas li.fc-extrato-editavel")
                self.assertGreaterEqual(item.count(), 1)

                linha = item.first.locator(".item-linha")
                self.assertEqual(linha.get_attribute("aria-expanded"), "false")
                linha.click()
                self.assertEqual(linha.get_attribute("aria-expanded"), "true")

                acoes = item.first.locator(".fc-extrato-acoes")
                acoes.wait_for(state="visible")
                self.assertTrue(acoes.locator("button.gasto-categoria").count() >= 1)
                self.assertTrue(acoes.locator("button.btn-corrigir-gasto").count() >= 1)

                acoes.locator("button.gasto-categoria").first.click()
                select = item.first.locator("select.correcao-select-categoria")
                select.wait_for(state="visible")
                select.select_option("lazer")
                page.wait_for_timeout(500)

                r = ctx.request.get(BASE_URL + "/api/financas/extrato?dias=15")
                dados = r.json()
                achou = [i for i in dados["itens"] if i["id"] == f"exp-{gasto_id}"]
                self.assertEqual(len(achou), 1)
                self.assertEqual(achou[0]["categoria"], "Lazer")

                self.assertEqual(erros, [], f"pageerror inesperado: {erros}")
            finally:
                browser.close()

    def test_item_manual_vira_tarefa_pela_mesma_acao_da_lista_antiga(self):
        conn = db.get_db()
        db.criar_gasto_de_brain_dump(conn, 15.0, "outros", "Nao era gasto de verdade - teste limpa D")
        conn.close()

        with sync_playwright() as p:
            browser = _lancar_browser(p)
            try:
                ctx = browser.new_context(viewport={"width": 390, "height": 844})
                page, erros = self._login_e_abrir_financas(ctx)

                item = page.locator("#lista-extrato-financas li.fc-extrato-editavel", has_text="Nao era gasto de verdade")
                page.wait_for_selector("#lista-extrato-financas li.fc-extrato-editavel")
                item.first.locator(".item-linha").click()
                acoes = item.first.locator(".fc-extrato-acoes")
                acoes.wait_for(state="visible")
                acoes.locator("button.btn-corrigir-gasto").click()
                page.wait_for_timeout(600)

                r_extrato = ctx.request.get(BASE_URL + "/api/financas/extrato?dias=15")
                self.assertNotIn(
                    "Nao era gasto de verdade",
                    json.dumps(r_extrato.json()),
                    "o lancamento deveria ter saido do extrato depois de virar tarefa",
                )

                r_tasks = ctx.request.get(BASE_URL + "/api/tasks")
                self.assertIn("Nao era gasto de verdade", json.dumps(r_tasks.json()))

                self.assertEqual(erros, [], f"pageerror inesperado: {erros}")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
