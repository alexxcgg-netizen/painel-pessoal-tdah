# tests/test_r2_inicio_ia.py - Reformulacao R2 (etapa 2): Inicio (hero, "Agora", 3 numeros,
# "Acesso rapido"), estado vazio da IA com 6 sugestoes, subtitulos do Mais com dado real,
# #erro-banner virou toast fixo (nao empurra layout), nada coberto pela barra, reduced-motion
# e zero pageerror. Rota nova: GET /api/inicio (rotas/inicio.py - sem IA, sem rede).
# Mesmo padrao de tests/test_r1_esqueleto.py: servidor real no mesmo processo + Playwright,
# banco temporario; IA nunca e chamada de verdade (summarize_day e chat trocados por fakes).
import json
import os
import tempfile
import time
import unittest
import urllib.request
from contextlib import nullcontext
from datetime import date, datetime, timedelta
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
from rotas import inicio as rota_inicio  # noqa: E402

PIN = "123456"
PORTA = int(os.environ.get("PORTA_TESTE_R2", "8872"))
BASE_URL = f"http://127.0.0.1:{PORTA}"

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

from tests.playwright_helper import CONTAR_FETCH, esperar_assentar, esperar_carga, get_chrome_path  # noqa: E402

_CHROME = get_chrome_path()

# Conta os setTimeout(…, 900) do app (a correcao de rolagem de abrirPeloMais): armado = quantos, feito = quantos ja rodaram.
CONTAR_CORRECAO_900 = """
(() => {
  const t = window.__t900 = { armado: 0, feito: 0, visto: 0 };
  const real = window.setTimeout;
  window.setTimeout = function (fn, ms, ...args) {
    if (ms !== 900 || typeof fn !== 'function') return real.call(this, fn, ms, ...args);
    t.armado++;
    return real.call(this, function () { try { return fn.apply(this, arguments); } finally { t.feito++; } }, ms, ...args);
  };
})();
"""


def fake_usage():
    return {"model": "claude-sonnet-4-5", "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.0001}


def _hoje():
    return date.today().isoformat()


def _limpar_e_semear(tarefas=(), atrasadas=0, feitas=0, copos=0, gasto=None, notas=0, voo=None):
    """Banco do teste no estado pedido. tarefas = [(titulo, hora|None)] pendentes de hoje."""
    db.DB_PATH = _DB_PROPRIO
    db.init_db()
    conn = db.get_db()
    for tabela in ("subtasks", "tasks", "expenses", "notas", "hidratacao_registros", "voos", "habitos", "chat_mensagens"):
        try:
            conn.execute(f"DELETE FROM {tabela}")
        except Exception:
            pass
    auth.definir_pin(conn, PIN, PIN)
    h = _hoje()
    for titulo, hora in tarefas:
        conn.execute("INSERT INTO tasks(title, due_date, hora) VALUES (?, ?, ?)", (titulo, h, hora))
    for i in range(feitas):
        conn.execute(
            "INSERT INTO tasks(title, due_date, completed_at) VALUES (?, ?, datetime('now'))", (f"Feita {i}", h)
        )
    for i in range(atrasadas):
        dia = (date.today() - timedelta(days=2 + i)).isoformat()
        conn.execute("INSERT INTO tasks(title, due_date) VALUES (?, ?)", (f"Atrasada {i}", dia))
    for _ in range(copos):
        db.registrar_hidratacao(conn, h)
    if gasto is not None:
        conn.execute(
            "INSERT INTO expenses(amount, category, description, tipo, created_at) "
            "VALUES (?, 'mercado', 'teste', 'real', ?)",
            (gasto, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
    for i in range(notas):
        conn.execute("INSERT INTO notas(titulo, corpo) VALUES (?, 'x')", (f"Nota {i}",))
    if voo:
        conn.execute("INSERT INTO voos(data, origem, destino) VALUES (?, 'SBMT', ?)", voo)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# 1) Rota agregadora (sem navegador)
# ---------------------------------------------------------------------------
class R2RotaInicioTestCase(unittest.TestCase):
    def setUp(self):
        _limpar_e_semear()
        self.client = app_module.app.test_client()
        r = self.client.post("/login", json={"pin": PIN})
        self.assertEqual(r.status_code, 200)

    def test_montar_resumo_frases(self):
        m = rota_inicio.montar_resumo
        self.assertEqual(m(0, 0, None, False), "Nada marcado pra hoje.")
        self.assertEqual(m(0, 3, None, False), "Tudo feito hoje: 3 de 3.")
        self.assertEqual(m(1, 0, None, False), "1 tarefa hoje.")
        self.assertEqual(m(6, 0, "09:00", False), "6 tarefas hoje. A primeira é às 9h.")
        self.assertEqual(m(6, 2, "14:30", False), "6 tarefas hoje. A próxima é às 14h30.")
        self.assertEqual(m(2, 0, "16:00", True), "2 tarefas hoje. A próxima é às 16h.")
        self.assertEqual(m(2, 0, "lixo", False), "2 tarefas hoje.")

    def test_sem_tarefas(self):
        d = self.client.get("/api/inicio").get_json()
        self.assertEqual(d["resumo"], "Nada marcado pra hoje.")
        self.assertEqual(d["atrasadas"], 0)
        self.assertIsNone(d["agora"])
        self.assertEqual(d["tarefas_hoje"], {"feitas": 0, "total": 0})
        self.assertEqual(d["agua"], {"copos": 0, "meta": 8})

    def test_varias_tarefas_atrasadas_e_numeros(self):
        _limpar_e_semear(
            tarefas=[("Ligar pro fornecedor", "00:00"), ("Pagar boleto", None), ("Academia", None)],
            atrasadas=2, feitas=1, copos=3, gasto=42.5, notas=12,
            voo=((date.today() + timedelta(days=2)).isoformat(), "SBJD"),
        )
        d = self.client.get("/api/inicio").get_json()
        self.assertTrue(d["resumo"].startswith("3 tarefas hoje."), d["resumo"])
        self.assertEqual(d["atrasadas"], 2)
        self.assertEqual(d["tarefas_hoje"], {"feitas": 1, "total": 4})
        self.assertEqual(d["tarefas_pendentes"], 5)
        self.assertEqual(d["agua"], {"copos": 3, "meta": 8})
        self.assertAlmostEqual(d["gasto_hoje"], 42.5)
        self.assertEqual(d["notas"], 12)
        self.assertEqual(d["proximo_voo"]["destino"], "SBJD")
        # "Agora": a tarefa com horário (00:00 já passou -> a mais recente que passou)
        self.assertEqual(d["agora"]["titulo"], "Ligar pro fornecedor")
        self.assertEqual(d["agora"]["hora"], "00:00")
        self.assertEqual(d["agora"]["origem"], "tarefa")

    def test_agora_sem_horario_cai_na_primeira_de_hoje(self):
        _limpar_e_semear(tarefas=[("Sem hora A", None), ("Sem hora B", None)])
        d = self.client.get("/api/inicio").get_json()
        self.assertEqual(d["agora"]["titulo"], "Sem hora A")
        self.assertIsNone(d["agora"]["hora"])

    def test_modo_visitante_esconde_gasto_agua_e_remedio(self):
        _limpar_e_semear(copos=2, gasto=10)
        with patch.object(app_module, "_modo_visitante_ativo", return_value=True):
            d = self.client.get("/api/inicio").get_json()
        self.assertIsNone(d["gasto_hoje"])
        self.assertIsNone(d["gasto_mes"])
        self.assertIsNone(d["agua"])
        self.assertIsNone(d["proximo_remedio"])
        self.assertTrue(d["visitante"])

    def test_nao_chama_ia(self):
        with patch("claude_client.chat", side_effect=AssertionError("IA chamada")), patch(
            "claude_client.summarize_day", side_effect=AssertionError("IA chamada")
        ):
            r = self.client.get("/api/inicio")
        self.assertEqual(r.status_code, 200)

    def test_exige_login(self):
        anon = app_module.app.test_client()
        r = anon.get("/api/inicio")
        self.assertIn(r.status_code, (302, 401))


# ---------------------------------------------------------------------------
# 2) Tela (Playwright)
# ---------------------------------------------------------------------------
@unittest.skipUnless(_PLAYWRIGHT_OK, "playwright nao instalado")
@unittest.skipUnless(_pronto, "servidor de teste nao respondeu")
class R2InicioIATestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Um Playwright e um Chromium pra classe toda; cada teste ganha contexto novo (isolado).
        cls._pw_cm = sync_playwright()
        cls._pw = cls._pw_cm.__enter__()
        kwargs = {"headless": True}
        if _CHROME is not None and Path(_CHROME).exists():
            kwargs["executable_path"] = _CHROME
        cls._browser = cls._pw.chromium.launch(**kwargs)

    @classmethod
    def tearDownClass(cls):
        try:
            cls._browser.close()
        finally:
            cls._pw_cm.__exit__(None, None, None)

    def setUp(self):
        _limpar_e_semear()
        resumo = patch("claude_client.summarize_day", return_value=("Resumo de teste.", fake_usage()))
        resumo.start()
        self.addCleanup(resumo.stop)

    def _abrir(self, p, reduzir=False, largura=390):
        # devolve o contexto no lugar do "browser": os testes chamam .close() nele no finally
        browser = self._browser.new_context(
            viewport={"width": largura, "height": 844},
            reduced_motion="reduce" if reduzir else "no-preference",
        )
        ctx = browser
        ctx.add_init_script(CONTAR_FETCH)
        ctx.add_init_script(CONTAR_CORRECAO_900)
        r = ctx.request.post(
            BASE_URL + "/login", data=json.dumps({"pin": PIN}), headers={"Content-Type": "application/json"}
        )
        self.assertEqual(r.status, 200, r.text())
        page = ctx.new_page()
        erros = []
        page.on("pageerror", lambda exc: erros.append(str(exc)))
        page.goto(BASE_URL + "/")
        esperar_carga(page)
        page.wait_for_function("document.getElementById('inicio-chip') && !document.getElementById('inicio-chip').hidden")
        self._esperar_contagem(page)
        esperar_assentar(page)
        return browser, page, erros

    def _texto(self, page, seletor):
        return page.locator(seletor).first.text_content().strip()

    def _visivel(self, page, aba):
        return page.evaluate(f"!document.getElementById('tab-{aba}').hidden")

    def _ativo(self, page):
        return page.evaluate("[...document.querySelectorAll('.tab-btn.active')].map(b => b.dataset.tab)")

    def _esperar_aba(self, page, aba):
        # showTab tira o hidden dentro do clique; o que pode quebrar vem depois, ao desenhar a carga
        page.wait_for_function(f"!document.getElementById('tab-{aba}').hidden")
        esperar_carga(page)

    def _esperar_contagem(self, page):
        # animarNumero (nucleo/ui.js) guarda el._c2Contagem enquanto conta e limpa ao escrever o valor final
        page.wait_for_function(
            "['tarefas', 'gasto', 'agua'].every(n => !document.getElementById('inicio-num-' + n)._c2Contagem)",
            timeout=10000,
        )

    def _esperar_rolagem_ate_alvo(self, page, aba):
        # abrirPeloMais (nucleo/navegacao.js) corrige a rolagem num setTimeout(900) armado dentro de um
        # rAF e nao marca nada na tela: CONTAR_CORRECAO_900 conta os timers de 900 ms armados e os que
        # ja rodaram. Espera o timer novo (armado depois da ultima espera) rodar, sem prazo fixo.
        page.wait_for_function("window.__t900.armado > window.__t900.visto && window.__t900.feito === window.__t900.armado")
        page.evaluate("window.__t900.visto = window.__t900.armado")
        esperar_assentar(page, f"#tab-{aba}")

    # ---- hero ----
    def test_hero_sem_tarefas_tudo_em_dia(self):
        with nullcontext(self._pw) as p:
            browser, page, erros = self._abrir(p)
            try:
                saud = self._texto(page, "#inicio-saudacao")
                self.assertRegex(saud, r"^(Bom dia|Boa tarde|Boa noite), Alex!$")
                self.assertEqual(self._texto(page, "#inicio-resumo"), "Nada marcado pra hoje.")
                self.assertEqual(self._texto(page, "#inicio-chip-texto"), "Tudo em dia")
                self.assertIn("ok", page.get_attribute("#inicio-chip", "class"))
                # sem nada marcado: estado vazio do "Agora" com "Planejar o dia"
                self.assertFalse(page.locator("#inicio-agora-vazio").is_hidden())
                self.assertTrue(page.locator("#inicio-agora").is_hidden())
                # hero na escala da prévia: 28/800, card 22px
                estilo = page.evaluate(
                    "(() => { const h = getComputedStyle(document.getElementById('inicio-saudacao'));"
                    " const c = getComputedStyle(document.getElementById('inicio-hero'));"
                    " return [h.fontSize, h.fontWeight, h.textTransform, c.borderTopLeftRadius]; })()"
                )
                self.assertEqual(estilo, ["28px", "800", "none", "22px"])
                self.assertEqual(erros, [])
            finally:
                browser.close()

    def test_hero_varias_tarefas_e_atrasadas(self):
        _limpar_e_semear(tarefas=[("A", None), ("B", None), ("C", None)], atrasadas=2)
        with nullcontext(self._pw) as p:
            browser, page, erros = self._abrir(p)
            try:
                self.assertEqual(self._texto(page, "#inicio-resumo"), "3 tarefas hoje.")
                self.assertEqual(self._texto(page, "#inicio-chip-texto"), "2 atrasadas")
                self.assertIn("alerta", page.get_attribute("#inicio-chip", "class"))
                self.assertEqual(self._texto(page, "#inicio-sub-tarefas"), "3 pra hoje")
                self.assertEqual(erros, [])
            finally:
                browser.close()

    def test_pendencias_do_assistente_viram_aviso_de_1_linha(self):
        with nullcontext(self._pw) as p:
            browser, page, erros = self._abrir(p)
            try:
                # o card grande saiu do topo do Início
                self.assertEqual(page.locator("#tab-hoje .caixa-compacta").count(), 0)
                linha = page.locator("#caixa-compacta-linha")
                self.assertTrue(linha.is_hidden(), "sem pendência, sem aviso")
                page.evaluate(
                    "(() => { const l = document.getElementById('caixa-compacta-linha');"
                    " document.getElementById('caixa-compacta-titulo').textContent = 'Pendências do assistente (2)';"
                    " l.hidden = false; })()"
                )
                altura = linha.bounding_box()["height"]
                self.assertLess(altura, 70, "aviso de 1 linha")
                linha.click()
                self._esperar_aba(page, "ajustes-ia")
                self.assertTrue(self._visivel(page, "ajustes-ia"))
                self.assertEqual(erros, [])
            finally:
                browser.close()

    # ---- "Agora" ----
    def test_agora_concluir_otimista_some_e_atualiza(self):
        _limpar_e_semear(tarefas=[("Ligar pro fornecedor", "00:00"), ("Pagar boleto", None)])
        with nullcontext(self._pw) as p:
            browser, page, erros = self._abrir(p)
            try:
                self.assertEqual(self._texto(page, "#inicio-agora-titulo"), "Ligar pro fornecedor")
                self.assertEqual(self._texto(page, "#inicio-agora-hora"), "0:00")
                ok = page.locator("#inicio-agora-ok").bounding_box()
                self.assertGreaterEqual(ok["width"], 51.5)
                self.assertGreaterEqual(ok["height"], 51.5)
                page.click("#inicio-agora-ok")
                # otimista: marca "saindo" no mesmo toque
                self.assertIn("saindo", page.get_attribute("#inicio-agora", "class") or "")
                page.wait_for_function(
                    "document.getElementById('inicio-agora-titulo').textContent === 'Pagar boleto'", timeout=5000
                )
                conn = db.get_db()
                feita = conn.execute(
                    "SELECT completed_at FROM tasks WHERE title = 'Ligar pro fornecedor'"
                ).fetchone()["completed_at"]
                conn.close()
                self.assertIsNotNone(feita)
                self._esperar_contagem(page)
                self.assertEqual(self._texto(page, "#inicio-num-tarefas"), "1/2")
                # conclui a última -> estado vazio
                page.click("#inicio-agora-ok")
                page.wait_for_function("!document.getElementById('inicio-agora-vazio').hidden", timeout=5000)
                self.assertEqual(self._texto(page, "#inicio-resumo"), "Tudo feito hoje: 2 de 2.")
                self.assertEqual(erros, [])
            finally:
                browser.close()

    def test_agora_falha_na_rede_devolve_o_card(self):
        _limpar_e_semear(tarefas=[("Ligar pro fornecedor", "00:00")])
        with nullcontext(self._pw) as p:
            browser, page, erros = self._abrir(p)
            try:
                page.route("**/api/tasks/*/complete", lambda r: r.fulfill(status=500, body="{}"))
                page.click("#inicio-agora-ok")
                page.wait_for_function(
                    "!document.getElementById('inicio-agora').classList.contains('saindo')", timeout=5000
                )
                self.assertFalse(page.locator("#inicio-agora").is_hidden())
                self.assertFalse(page.locator("#inicio-agora-ok").is_disabled())
                self.assertEqual(erros, [])
            finally:
                browser.close()

    def test_planejar_o_dia_abre_a_ia_com_a_sugestao(self):
        with nullcontext(self._pw) as p:
            browser, page, erros = self._abrir(p)
            try:
                with patch("claude_client.chat", side_effect=AssertionError("não pode enviar sozinho")):
                    page.click("#inicio-planejar")
                    page.wait_for_timeout(300)
                self.assertTrue(self._visivel(page, "assistente"))
                self.assertEqual(page.input_value("#chat-input"), "Me ajuda a planejar o dia")
                self.assertEqual(erros, [])
            finally:
                browser.close()

    # ---- 3 números ----
    def test_numeros_batem_com_os_dados_e_abrem_a_tela_certa(self):
        _limpar_e_semear(tarefas=[("A", None), ("B", None)], feitas=1, copos=3, gasto=42)
        with nullcontext(self._pw) as p:
            browser, page, erros = self._abrir(p)
            try:
                self.assertEqual(self._texto(page, "#inicio-num-tarefas"), "1/3")
                self.assertEqual(self._texto(page, "#inicio-num-gasto"), "R$ 42")
                self.assertEqual(self._texto(page, "#inicio-num-agua"), "3/8")
                for num, aba in (("tarefas", "tarefas"), ("gasto", "gastos"), ("agua", "painel")):
                    page.evaluate("showTab('hoje')")
                    esperar_assentar(page, "#tab-hoje")
                    page.click(f"#inicio-num-{num}")
                    self._esperar_aba(page, aba)
                    self.assertTrue(self._visivel(page, aba), f"{num} deveria abrir {aba}")
                self.assertEqual(erros, [])
            finally:
                browser.close()

    # ---- Acesso rápido ----
    def test_cada_atalho_abre_o_destino(self):
        destinos = {
            "tarefas": ("tarefas", None),
            "agenda": ("painel", "#agenda-vazio"),
            "financas": ("gastos", None),
            "habitos": ("vida", "#vida-habitos"),
            "saude": ("painel", "#saude-grid"),
            "aviacao": ("aviacao", None),
            "notas": ("painel", "#lista-notas"),
            "construtora": ("construtora", None),
        }
        with nullcontext(self._pw) as p:
            browser, page, erros = self._abrir(p)
            try:
                atalhos = page.evaluate("[...document.querySelectorAll('.inicio-atalho')].map(a => a.dataset.atalho)")
                self.assertEqual(atalhos, list(destinos), "8 cards, em ordem, número par")
                for atalho, (aba, alvo) in destinos.items():
                    page.evaluate("showTab('hoje'); window.scrollTo(0, 0)")
                    esperar_assentar(page, "#tab-hoje")
                    card = page.locator(f'.inicio-atalho[data-atalho="{atalho}"]')
                    card.scroll_into_view_if_needed()
                    caixa = card.bounding_box()
                    self.assertGreaterEqual(caixa["height"], 127.5)
                    card.click()
                    self._esperar_aba(page, aba)
                    if alvo:
                        self._esperar_rolagem_ate_alvo(page, aba)
                    self.assertTrue(self._visivel(page, aba), f"{atalho} deveria abrir {aba}")
                    item = aba if aba in ("hoje", "tarefas", "assistente", "gastos") else "mais"
                    self.assertEqual(self._ativo(page), [item])
                    if alvo:
                        # rolou até a seção (o bloco do alvo ficou na tela)
                        topo = page.evaluate(
                            f"(() => {{ const el = document.querySelector('#tab-{aba} {alvo}');"
                            " const b = el.closest('.card, .secao-recolhivel') || el;"
                            " return b.getBoundingClientRect().top; })()"
                        )
                        self.assertLess(topo, 844, f"{atalho}: alvo fora da tela")
                        self.assertGreaterEqual(topo, -1, f"{atalho}: alvo acima da tela")
                self.assertEqual(erros, [])
            finally:
                browser.close()

    def test_subtitulos_com_dado_real_no_inicio_e_no_mais(self):
        _limpar_e_semear(notas=12, voo=((date.today() + timedelta(days=1)).isoformat(), "SBJD"))
        with nullcontext(self._pw) as p:
            browser, page, erros = self._abrir(p)
            try:
                self.assertEqual(self._texto(page, "#inicio-sub-notas"), "12 notas")
                self.assertEqual(self._texto(page, "#inicio-sub-aviacao"), "Voo amanhã · SBJD")
                self.assertEqual(self._texto(page, "#mais-sub-notas"), "12 notas")
                self.assertEqual(self._texto(page, "#mais-sub-aviacao"), "Próximo voo: amanhã · SBJD")
                # sem hábitos: o Mais mantém a descrição fixa
                self.assertEqual(self._texto(page, "#mais-sub-habitos"), "Hábitos do dia e projetos")
                self.assertEqual(erros, [])
            finally:
                browser.close()

    # ---- IA ----
    def test_ia_vazia_com_6_sugestoes_e_sugestao_envia_pelo_chat(self):
        recebidas = []

        def fake_chat(mensagens, contexto, memorias, executores):
            recebidas.append(mensagens[-1]["content"] if mensagens else None)
            return "Hoje você tem 2 tarefas.", [], fake_usage()

        with nullcontext(self._pw) as p:
            browser, page, erros = self._abrir(p)
            try:
                page.click('.tab-btn[data-tab="assistente"]')
                page.wait_for_selector(".chat-sugestao", state="visible")
                esperar_assentar(page, "#tab-assistente")
                self.assertEqual(self._texto(page, ".chat-ola-titulo"), "Oi, Alex")
                sugestoes = page.evaluate("[...document.querySelectorAll('.chat-sugestao')].map(b => b.textContent.trim())")
                self.assertEqual(
                    sugestoes,
                    [
                        "O que tenho hoje?",
                        "Quanto gastei este mês?",
                        "O que está atrasado?",
                        "O que vence essa semana?",
                        "Me ajuda a planejar o dia",
                        "Quando é meu próximo voo?",
                    ],
                )
                colunas = page.evaluate(
                    "getComputedStyle(document.querySelector('.chat-sugestoes')).gridTemplateColumns.split(' ').length"
                )
                self.assertEqual(colunas, 2)
                self.assertEqual(self._texto(page, "#chat-nota"), "Responde com o que está no seu painel.")
                with patch("claude_client.chat", side_effect=fake_chat):
                    page.click('.chat-sugestao[data-pergunta="O que tenho hoje?"]')
                    page.wait_for_function(
                        "document.getElementById('chat-mensagens').textContent.includes('Hoje você tem 2 tarefas')",
                        timeout=10000,
                    )
                self.assertEqual(page.locator(".chat-vazio").count(), 0, "estado vazio some com mensagens")
                self.assertEqual(self._texto(page, ".chat-bolha.user"), "O que tenho hoje?")
                self.assertTrue(recebidas and "O que tenho hoje?" in str(recebidas[-1]))
                # bolhas na escala nova + botão ouvir continua na resposta
                bolha = page.evaluate(
                    "(() => { const s = getComputedStyle(document.querySelector('.chat-bolha.user'));"
                    " return [s.fontSize, s.paddingTop, s.borderTopLeftRadius, s.maxWidth]; })()"
                )
                self.assertEqual(bolha, ["16px", "14px", "18px", "85%"])
                self.assertEqual(page.locator(".chat-linha.assistant .btn-ouvir-chat").count(), 1)
                # a última mensagem fica acima do rodapé e do campo
                # (a lista rola em scroll-behavior: smooth: quem mostra que parou e a propria ultima linha)
                esperar_assentar(page, "#chat-mensagens > :last-child")
                ultima = page.evaluate("document.getElementById('chat-mensagens').lastElementChild.getBoundingClientRect().bottom")
                nota = page.evaluate("document.getElementById('chat-nota').getBoundingClientRect()")
                form = page.evaluate("document.getElementById('chat-form').getBoundingClientRect().top")
                self.assertLessEqual(ultima, nota["top"] + 0.5)
                self.assertLessEqual(nota["bottom"], form + 0.5, "rodapé fica acima do campo")
                self.assertEqual(erros, [])
            finally:
                browser.close()

    # ---- toast de erro ----
    def test_erro_vira_toast_fixo_que_nao_empurra_layout(self):
        with nullcontext(self._pw) as p:
            browser, page, erros = self._abrir(p)
            try:
                antes = page.evaluate("document.getElementById('inicio-hero').getBoundingClientRect().top")
                page.evaluate("mostrarErro('Falhou de teste')")
                esperar_assentar(page, "#erro-banner")
                esperar_assentar(page, "#inicio-hero")
                depois = page.evaluate("document.getElementById('inicio-hero').getBoundingClientRect().top")
                self.assertAlmostEqual(antes, depois, delta=0.5)
                self.assertEqual(page.evaluate("getComputedStyle(document.getElementById('erro-banner')).position"), "fixed")
                self.assertTrue(page.locator("#erro-banner").is_visible())
                page.click("#erro-banner")
                page.wait_for_selector("#erro-banner", state="hidden")
                self.assertTrue(page.locator("#erro-banner").is_hidden(), "tocar fecha o toast")
                # rolar até um alvo do Mais com o toast aberto continua certo. A carga do Painel empurra
                # o alvo e a correcao de 900 ms roda uma vez so: carregado antes (cache de 30 s), nada
                # cresce depois do toque e a medida nao corre contra a rede.
                page.evaluate("showTab('painel')")
                self._esperar_aba(page, "painel")
                page.evaluate("mostrarErro('Falhou de novo')")
                page.click('.tab-btn[data-tab="mais"]')
                self._esperar_aba(page, "mais")
                esperar_assentar(page, "#tab-mais")
                page.evaluate("document.querySelector('#tab-mais [data-alvo=\"#lista-notas\"]').click()")
                self._esperar_aba(page, "painel")
                self._esperar_rolagem_ate_alvo(page, "painel")
                topo = page.evaluate(
                    "document.querySelector('#tab-painel #lista-notas').closest('.card').getBoundingClientRect().top"
                )
                self.assertAlmostEqual(topo, 12, delta=2)
                self.assertEqual(erros, [])
            finally:
                browser.close()

    # ---- nada coberto ----
    def test_nada_do_inicio_fica_coberto_pela_barra_ou_fab(self):
        _limpar_e_semear(tarefas=[("A", "00:00"), ("B", None)], atrasadas=1)
        with nullcontext(self._pw) as p:
            for largura in (390, 320):
                browser, page, erros = self._abrir(p, largura=largura)
                try:
                    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                    esperar_assentar(page)
                    medida = page.evaluate(
                        """(() => {
                            const tela = document.getElementById('tab-hoje');
                            const filhos = [...tela.children].filter(el => el.getBoundingClientRect().height > 0);
                            const fundo = filhos[filhos.length - 1].getBoundingClientRect().bottom;
                            const fab = document.getElementById('fab-captura').getBoundingClientRect().top;
                            const barra = document.getElementById('tabbar').getBoundingClientRect().top;
                            const larg = document.documentElement.scrollWidth;
                            return {fundo, teto: Math.min(fab, barra), larg};
                        })()"""
                    )
                    self.assertLessEqual(medida["fundo"], medida["teto"] + 0.5)
                    self.assertLessEqual(medida["larg"], largura, "sem rolagem lateral")
                    self.assertEqual(erros, [])
                finally:
                    browser.close()

    # ---- reduced-motion ----
    def test_reduced_motion_numeros_finais_na_hora_e_sem_erro(self):
        _limpar_e_semear(tarefas=[("A", None)], copos=2)
        with nullcontext(self._pw) as p:
            browser, page, erros = self._abrir(p, reduzir=True)
            try:
                self.assertEqual(self._texto(page, "#inicio-num-tarefas"), "0/1")
                self.assertEqual(self._texto(page, "#inicio-num-agua"), "2/8")
                trans = page.evaluate("getComputedStyle(document.querySelector('.inicio-atalho')).transitionDuration")
                self.assertTrue(all(float(t.rstrip("s")) <= 0.001 for t in trans.split(",")), trans)
                page.click('.tab-btn[data-tab="assistente"]')
                page.wait_for_selector(".chat-sugestao", state="visible")
                esperar_carga(page)
                self.assertEqual(page.locator(".chat-sugestao").count(), 6)
                self.assertEqual(erros, [])
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
