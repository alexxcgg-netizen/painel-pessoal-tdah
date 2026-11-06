# tests/test_tarefas_aba_nova.py - aba Tarefas nova (leva 06/11, frente 6): grupos estilo Ajustes, regua
# do dia, folha de acoes (dia/hora/nome/Feito/Apagar) com Desfazer, em 390 px. Servidor HTTP real numa
# thread (Playwright precisa de rede de verdade pra page.route), banco temporario. Sem espera fixa:
# tudo espera a condicao (docs/testes.md, "No Windows").
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
PORTA = int(os.environ.get("PORTA_TESTE_TAREFAS_NOVA", "8917"))
BASE_URL = f"http://127.0.0.1:{PORTA}"

db.init_db()
_conn = db.get_db()
auth.definir_pin(_conn, PIN, PIN)
_conn.commit()
_conn.close()

from tests.playwright_helper import esperar_assentar, get_chrome_path, subir_servidor  # noqa: E402

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

_CHROME = get_chrome_path()

# previsao fake: chuva das 17h as 21h (a de verdade depende de cidade configurada e de rede)
_CLIMA = {"configurado": True, "alerta": True, "chovendo_agora": False, "hora_inicio": 17, "hora_fim": 21,
          "chuva_pct_max": 80, "cidade": "Cidade Teste", "texto": "Risco de chuva entre 17h e 21h."}

# nada encavalado: caixinha, titulo e hora de cada linha nao se cruzam e cabem na linha
_SOBREPOSTOS = """() => {
  const ruins = [];
  document.querySelectorAll('#lista-tarefas li.tt-item').forEach((li) => {
    const r = li.getBoundingClientRect();
    const partes = ['.tt-caixa', '.tt-titulo', '.tt-hora'].map((s) => li.querySelector(s))
      .filter((el) => el && !el.hidden && el.getBoundingClientRect().width > 0)
      .map((el) => el.getBoundingClientRect());
    partes.forEach((a, i) => {
      if (a.left < r.left - 1 || a.right > r.right + 1) ruins.push('fora da linha: ' + li.textContent);
      partes.slice(i + 1).forEach((b) => {
        if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1)
          ruins.push('encavalado: ' + li.textContent);
      });
    });
  });
  return ruins;
}"""


@unittest.skipUnless(_PLAYWRIGHT_OK, "playwright nao instalado")
@unittest.skipUnless(_pronto, "servidor de teste nao respondeu")
class TarefasAbaNovaTestCase(unittest.TestCase):
    def setUp(self):
        db.DB_PATH = _DB_PROPRIO
        if _DB_PROPRIO.exists():
            conn = db.get_db()
            conn.execute("DELETE FROM subtasks")
            conn.execute("DELETE FROM tasks")
            conn.commit()
            conn.close()
        db.init_db()
        conn = db.get_db()
        auth.definir_pin(conn, PIN, PIN)
        conn.commit()
        conn.close()

    def _linha(self, task_id):
        conn = db.get_db()
        try:
            return dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())
        finally:
            conn.close()

    def _abrir(self, p):
        kwargs = {"headless": True}
        if _CHROME is not None and Path(_CHROME).exists():
            kwargs["executable_path"] = _CHROME
        browser = p.chromium.launch(**kwargs)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        r = ctx.request.post(BASE_URL + "/login", data=json.dumps({"pin": PIN}),
                             headers={"Content-Type": "application/json"})
        self.assertEqual(r.status, 200, r.text())
        page = ctx.new_page()
        erros = []
        page.on("pageerror", lambda exc: erros.append(str(exc)))
        page.route("**/api/clima/hoje", lambda route: route.fulfill(status=200, content_type="application/json",
                                                                    body=json.dumps(_CLIMA)))
        page.goto(BASE_URL + "/")
        page.wait_for_load_state("networkidle")
        hoje = page.evaluate("tlIsoDe(new Date())")
        amanha = page.evaluate("tlIsoDe(new Date(Date.now() + 86400000))")
        return browser, ctx, page, erros, hoje, amanha

    def _criar(self, ctx, titulo, data=None, hora=None):
        r = ctx.request.post(BASE_URL + "/api/tasks", data=json.dumps({"titulo": titulo, "due_date": data}),
                             headers={"Content-Type": "application/json"})
        self.assertEqual(r.status, 201, r.text())
        tid = r.json()["id"]
        if hora:
            r = ctx.request.post(BASE_URL + f"/api/tasks/{tid}/mover", data=json.dumps({"hora": hora}),
                                 headers={"Content-Type": "application/json"})
            self.assertEqual(r.status, 200, r.text())
        return tid

    def _ir_pra_aba(self, page):
        page.click('.tab-btn[data-tab="tarefas"]')
        page.wait_for_selector("#lista-tarefas li.tt-item")
        esperar_assentar(page, "#tab-tarefas")

    def _grupo_da(self, page, tid):
        return page.evaluate(
            "(id) => { const li = document.querySelector(`#lista-tarefas li.tt-item[data-id='${id}']`);"
            " return li ? li.closest('.tt-grupo').dataset.ttChave : null; }", tid)

    def test_visual_390_regua_e_grupos(self):
        with sync_playwright() as p:
            browser, ctx, page, erros, hoje, amanha = self._abrir(p)
            try:
                self._criar(ctx, "Separar os papéis da empresa com um nome bem comprido pra cortar", hoje, "10:00")
                self._criar(ctx, "Ligar pro contador", hoje, "16:30")
                self._criar(ctx, "Comprar ração", hoje)
                self._criar(ctx, "Revisar a carta VFR", amanha, "09:00")
                self._criar(ctx, "Lavar o carro")
                self._ir_pra_aba(page)

                grupos = page.eval_on_selector_all("#lista-tarefas .tt-grupo:not([hidden]) > h3 .tt-grupo-nome",
                                                   "els => els.map(e => e.textContent)")
                self.assertEqual(grupos, ["Manhã", "Tarde", "Sem hora", "Amanhã", "Sem data"])
                # regua: uma bolinha por tarefa de hoje com hora, chuva da previsao
                page.wait_for_selector("#tt-regua-chuva:not([hidden])")
                self.assertEqual(page.locator("#tt-regua .tt-marco").count(), 2)
                self.assertIn("chuva 80%", page.inner_text("#tt-regua-chuva"))
                self.assertEqual(page.get_attribute("#tt-regua .tt-marco >> nth=0", "role"), "slider")
                # hora em mono a direita, coral nas de hoje
                self.assertEqual(page.inner_text("#lista-tarefas li.tt-item >> nth=0 >> .tt-hora"), "10:00")
                # sem rolagem lateral e nada encavalado
                larg = page.evaluate("[document.scrollingElement.scrollWidth, window.innerWidth]")
                self.assertLessEqual(larg[0], larg[1], f"rolagem lateral: {larg}")
                self.assertEqual(page.evaluate(_SOBREPOSTOS), [])
                # toque >= 44 px na caixinha (area do ::after) e na linha
                alt = page.evaluate("document.querySelector('#lista-tarefas .tt-abrir').getBoundingClientRect().height")
                self.assertGreaterEqual(alt, 44)
                self.assertEqual(erros, [], f"pageerror: {erros}")
            finally:
                browser.close()

    def test_folha_muda_dia_com_desfazer(self):
        with sync_playwright() as p:
            browser, ctx, page, erros, hoje, amanha = self._abrir(p)
            try:
                tid = self._criar(ctx, "Ligar pro contador", hoje, "16:30")
                self._criar(ctx, "Outra de hoje", hoje)
                self._ir_pra_aba(page)
                page.click(f"#lista-tarefas li.tt-item[data-id='{tid}'] .tt-abrir")
                page.wait_for_selector("#tarefa-folha.bottom-sheet--aberto")
                self.assertEqual(page.inner_text("#tt-folha-titulo"), "Ligar pro contador")
                # sem rolagem lateral com a folha aberta
                larg = page.evaluate("[document.scrollingElement.scrollWidth, window.innerWidth]")
                self.assertLessEqual(larg[0], larg[1])
                page.click("#tt-folha-dias button:has-text('Amanhã')")
                # otimista: ja esta no grupo Amanha antes da resposta confirmar
                page.wait_for_function(
                    "(id) => document.querySelector(`#lista-tarefas li.tt-item[data-id='${id}']`)"
                    "?.closest('.tt-grupo').dataset.ttChave === 'g:amanha'", arg=tid)
                page.wait_for_selector("#desfazer-toast.visivel .desfazer-btn:not([hidden])")
                self.assertIn("pra amanhã", page.inner_text("#desfazer-toast .desfazer-texto"))
                self._esperar_servidor(lambda: self._linha(tid)["due_date"] == amanha)
                self.assertEqual(self._linha(tid)["hora"], "16:30")
                page.click("#desfazer-toast .desfazer-btn")
                page.wait_for_function(
                    "(id) => document.querySelector(`#lista-tarefas li.tt-item[data-id='${id}']`)"
                    "?.closest('.tt-grupo').dataset.ttChave === 'g:tarde'", arg=tid)
                self._esperar_servidor(lambda: self._linha(tid)["due_date"] == hoje)
                self.assertEqual(erros, [], f"pageerror: {erros}")
            finally:
                browser.close()

    def test_folha_hora_nome_e_erro_volta(self):
        with sync_playwright() as p:
            browser, ctx, page, erros, hoje, amanha = self._abrir(p)
            try:
                tid = self._criar(ctx, "Pagar o IPVA", hoje, "10:00")
                self._ir_pra_aba(page)
                # +1 h
                page.click(f"#lista-tarefas li.tt-item[data-id='{tid}'] .tt-abrir")
                page.wait_for_selector("#tarefa-folha.bottom-sheet--aberto")
                page.click("#tt-folha-horas button:has-text('+1 h')")
                page.wait_for_function(
                    "(id) => document.querySelector(`#lista-tarefas li.tt-item[data-id='${id}'] .tt-hora`)?.textContent === '11:00'",
                    arg=tid)
                self._esperar_servidor(lambda: self._linha(tid)["hora"] == "11:00")
                page.wait_for_selector("#tarefa-folha", state="hidden")
                # nome: edita e fecha com Enter -> grava
                page.click(f"#lista-tarefas li.tt-item[data-id='{tid}'] .tt-abrir")
                page.wait_for_selector("#tarefa-folha.bottom-sheet--aberto")
                page.fill("#tt-folha-nome", "Pagar o IPVA do carro")
                page.press("#tt-folha-nome", "Enter")
                page.wait_for_function(
                    "(id) => document.querySelector(`#lista-tarefas li.tt-item[data-id='${id}'] .tt-titulo`)?.textContent === 'Pagar o IPVA do carro'",
                    arg=tid)
                self._esperar_servidor(lambda: self._linha(tid)["title"] == "Pagar o IPVA do carro")
                page.wait_for_selector("#tarefa-folha", state="hidden")
                # "Escolher": o relogio nativo grava ao confirmar (Enter/fechar), nao a cada giro
                page.click(f"#lista-tarefas li.tt-item[data-id='{tid}'] .tt-abrir")
                page.wait_for_selector("#tarefa-folha.bottom-sheet--aberto")
                page.fill("#tt-folha-horas input[type=time]", "18:45")
                self.assertEqual(self._linha(tid)["hora"], "11:00", "gravou antes de confirmar")
                page.press("#tt-folha-horas input[type=time]", "Enter")
                self._esperar_servidor(lambda: self._linha(tid)["hora"] == "18:45")
                page.wait_for_selector("#tarefa-folha", state="hidden")
                page.click("#desfazer-toast .desfazer-btn")
                self._esperar_servidor(lambda: self._linha(tid)["hora"] == "11:00")
                page.wait_for_function(
                    "(id) => document.querySelector(`#lista-tarefas li.tt-item[data-id='${id}'] .tt-hora`)?.textContent === '11:00'",
                    arg=tid)
                # Sem hora com a rota falhando: volta pro que era
                page.route("**/api/tasks/*/mover", lambda route: route.fulfill(
                    status=500, content_type="application/json", body='{"error": "falha simulada"}'))
                page.click(f"#lista-tarefas li.tt-item[data-id='{tid}'] .tt-abrir")
                page.wait_for_selector("#tarefa-folha.bottom-sheet--aberto")
                page.click("#tt-folha-horas button:has-text('Sem hora')")
                page.wait_for_function("document.getElementById('erro-banner').textContent.includes('falha simulada')")
                page.wait_for_function(
                    "(id) => document.querySelector(`#lista-tarefas li.tt-item[data-id='${id}'] .tt-hora`)?.textContent === '11:00'",
                    arg=tid)
                self.assertEqual(self._linha(tid)["hora"], "11:00")
                self.assertEqual(erros, [], f"pageerror: {erros}")
            finally:
                browser.close()

    def test_regua_teclado_e_arrastar(self):
        with sync_playwright() as p:
            browser, ctx, page, erros, hoje, amanha = self._abrir(p)
            try:
                tid = self._criar(ctx, "Separar os papéis", hoje, "15:00")
                self._ir_pra_aba(page)
                marco = page.locator(f"#tt-regua .tt-marco[data-id='{tid}']")
                marco.focus()
                page.keyboard.press("ArrowRight")
                self._esperar_servidor(lambda: self._linha(tid)["hora"] == "15:15")
                page.wait_for_selector("#desfazer-toast.visivel")
                self.assertIn("15:00 → 15:15", page.inner_text("#desfazer-toast .desfazer-texto"))
                esperar_assentar(page, "#tt-regua")
                # arrastar com o ponteiro ~1/16 da regua pra direita (7h-23h = 16 h -> ~1 h)
                caixa = marco.bounding_box()
                trilho = page.locator("#tt-regua-trilho").bounding_box()
                x0, y0 = caixa["x"] + caixa["width"] / 2, caixa["y"] + caixa["height"] / 2
                page.mouse.move(x0, y0)
                page.mouse.down()
                page.mouse.move(x0 + trilho["width"] / 32, y0, steps=4)
                page.mouse.move(x0 + trilho["width"] / 16, y0, steps=4)
                page.mouse.up()
                self._esperar_servidor(lambda: self._linha(tid)["hora"] not in ("15:00", "15:15"))
                hora = self._linha(tid)["hora"]
                minutos = int(hora[:2]) * 60 + int(hora[3:])
                self.assertEqual(minutos % 15, 0, hora)
                self.assertGreater(minutos, 15 * 60 + 15)
                self.assertEqual(erros, [], f"pageerror: {erros}")
            finally:
                browser.close()

    def test_caixinha_marca_feito_e_desfazer_reabre(self):
        with sync_playwright() as p:
            browser, ctx, page, erros, hoje, amanha = self._abrir(p)
            try:
                tid = self._criar(ctx, "Comprar ração", hoje)
                self._criar(ctx, "Outra", hoje)
                self._ir_pra_aba(page)
                page.click(f"#lista-tarefas li.tt-item[data-id='{tid}'] .tt-caixa")
                page.wait_for_selector(f"#lista-tarefas li.tt-item.feito[data-id='{tid}']")
                page.wait_for_selector(f"#lista-tarefas li.tt-item[data-id='{tid}']", state="detached")
                self._esperar_servidor(lambda: self._linha(tid)["completed_at"] is not None)
                self.assertFalse(page.locator("#tarefa-folha.bottom-sheet--aberto").count(), "a caixinha nao abre a folha")
                page.click("#desfazer-toast .desfazer-btn")
                self._esperar_servidor(lambda: self._linha(tid)["completed_at"] is None)
                page.wait_for_selector(f"#lista-tarefas li.tt-item[data-id='{tid}']")
                self.assertEqual(erros, [], f"pageerror: {erros}")
            finally:
                browser.close()

    def test_apagar_pela_folha_e_desfazer(self):
        with sync_playwright() as p:
            browser, ctx, page, erros, hoje, amanha = self._abrir(p)
            try:
                tid = self._criar(ctx, "Lavar o carro", hoje, "18:00")
                self._ir_pra_aba(page)
                self.assertEqual(page.locator(f"#tt-regua .tt-marco[data-id='{tid}']").count(), 1)
                page.click(f"#lista-tarefas li.tt-item[data-id='{tid}'] .tt-abrir")
                page.wait_for_selector("#tarefa-folha.bottom-sheet--aberto")
                page.click("#tt-folha-apagar")
                # a bolinha sai da regua na hora; a linha sai do DOM depois da animacao
                page.wait_for_selector(f"#tt-regua .tt-marco[data-id='{tid}']", state="detached")
                page.wait_for_selector(f"#lista-tarefas li.tt-item[data-id='{tid}']", state="detached")
                self._esperar_servidor(lambda: not self._existe(tid))
                page.wait_for_selector("#desfazer-toast.visivel .desfazer-btn:not([hidden])")
                self.assertIn("apagada", page.inner_text("#desfazer-toast .desfazer-texto"))
                page.click("#desfazer-toast .desfazer-btn")
                self._esperar_servidor(lambda: self._existe(tid))
                page.wait_for_selector(f"#lista-tarefas li.tt-item[data-id='{tid}']")
                page.wait_for_selector(f"#tt-regua .tt-marco[data-id='{tid}']")
                self.assertEqual(erros, [], f"pageerror: {erros}")
            finally:
                browser.close()

    def _existe(self, task_id):
        conn = db.get_db()
        try:
            return conn.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone() is not None
        finally:
            conn.close()

    def _esperar_servidor(self, condicao, limite=10.0):
        fim = time.monotonic() + limite
        while time.monotonic() < fim:
            if condicao():
                return
            time.sleep(0.05)
        self.fail("o servidor nao chegou no estado esperado")


if __name__ == "__main__":
    unittest.main()
