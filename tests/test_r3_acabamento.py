# tests/test_r3_acabamento.py - Reformulacao R3 (etapa 3, acabamento): todas as telas internas
# (Tarefas, Financas, Meu dia, Vida, Aviacao, Construtora, Configuracoes, Avisos e regras e a
# folha do +) na mesma escala de Inicio/IA/Mais. Em 390 e 320px, com todas as secoes
# recolhiveis abertas: nenhum alvo de toque visivel < 44px de altura, nenhum texto < 12px,
# nada vazando na horizontal, titulos de secao com o MESMO estilo computado e zero pageerror.
# Mais: o Inicio nao mostra a faixa do assistente sem pendencia real, placeholder novo da IA e o
# "ouvir" das bolhas com area de toque >= 44px.
# Mesmo padrao de tests/test_r2_inicio_ia.py: servidor real no mesmo processo + Playwright,
# banco temporario, rede externa bloqueada no navegador; IA nunca e chamada de verdade.
import os
import tempfile
import time
import unittest
import urllib.request
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

PIN = "123456"
PORTA = int(os.environ.get("PORTA_TESTE_R3", "8873"))
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

# Telas desta onda (data-tab) + a parte de baixo do Inicio (essencial, visao do dia) + a folha
# do "+" (aberta a partir do Inicio).
TELAS = ["tarefas", "gastos", "painel", "vida", "aviacao", "construtora", "config", "ajustes-ia", "hoje"]

# Auditoria rodada DENTRO da pagina. `sel` = raiz auditada (#tab-X ou #folha-captura).
# Devolve listas de violacoes (vazias = ok) e os estilos distintos dos titulos de secao.
# Titulo de secao = .rotulo-tela e qualquer <h2> visivel da tela (o h1 e o do cabecalho;
# titulo de card e h3; a saudacao do Inicio e o hero, nao titulo de secao). Alvo de toque = botao, link, campo, select, summary, [role=button]
# e o <label> de checkbox/radio/arquivo (o input em si costuma ser escondido/miudo).
AUDIT_JS = r"""
(sel) => {
  const raiz = document.querySelector(sel);
  if (!raiz) return {erro: 'sem raiz ' + sel};
  const W = document.documentElement.clientWidth;
  const visivel = (el) => {
    if (!el || el.closest('[hidden]')) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    for (let a = el; a && a !== document.documentElement; a = a.parentElement) {
      const cs = getComputedStyle(a);
      if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.02) return false;
      if (cs.clipPath && cs.clipPath.startsWith('inset(50%')) return false;
      if (cs.clip && cs.clip.startsWith('rect(0')) return false;
    }
    return true;
  };
  const nome = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    if (el.classList.length) s += '.' + [...el.classList].slice(0, 2).join('.');
    const t = (el.textContent || el.getAttribute('aria-label') || el.placeholder || '').trim().replace(/\s+/g, ' ').slice(0, 28);
    return s + (t ? ' "' + t + '"' : '');
  };
  const pequenos = [];
  const vistos = new Set();
  raiz.querySelectorAll('button, a[href], input, select, textarea, summary, [role=button], label[for]').forEach((el) => {
    let alvo = el;
    if (el.matches('input[type=hidden]')) return;
    if (el.matches('label[for]')) {
      const c = document.getElementById(el.getAttribute('for'));
      if (!c || !c.matches('input[type=checkbox], input[type=radio], input[type=file]')) return;
    }
    if (el.matches('input[type=checkbox], input[type=radio], input[type=file]')) {
      alvo = el.closest('label') || (el.id && document.querySelector('label[for="' + el.id + '"]')) || el;
    }
    if (vistos.has(alvo)) return;
    vistos.add(alvo);
    if (!visivel(alvo)) return;
    const h = alvo.getBoundingClientRect().height;
    if (h < 43.5) pequenos.push(nome(alvo) + ' h=' + h.toFixed(1));
  });
  const miudos = [];
  const largos = [];
  raiz.querySelectorAll('*').forEach((el) => {
    if (el.namespaceURI === 'http://www.w3.org/2000/svg' && el.tagName.toLowerCase() !== 'text') return;
    const temTexto = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!temTexto && !el.matches('input, textarea, select')) return;
    if (!visivel(el)) return;
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs < 11.95) miudos.push(nome(el) + ' fs=' + fs);
    const r = el.getBoundingClientRect();
    if (r.right > W + 1 || r.left < -1) {
      let rolavel = false;
      for (let a = el.parentElement; a && a !== raiz.parentElement; a = a.parentElement) {
        const ox = getComputedStyle(a).overflowX;
        if (ox === 'auto' || ox === 'scroll') { rolavel = true; break; }
      }
      if (!rolavel) largos.push(nome(el) + ' [' + r.left.toFixed(0) + ',' + r.right.toFixed(0) + ']');
    }
  });
  const estilos = {};
  raiz.querySelectorAll('.rotulo-tela, h2:not(.inicio-saudacao)').forEach((el) => {
    if (!visivel(el)) return;
    const cs = getComputedStyle(el);
    const k = [cs.fontSize, cs.fontWeight, cs.letterSpacing, cs.textTransform, cs.color].join(' | ');
    (estilos[k] = estilos[k] || []).push(nome(el));
  });
  return {
    pequenos, miudos, largos, titulos: estilos,
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  };
}
"""

# Abre toda secao recolhivel/details da raiz pra auditar o conteudo de dentro tambem.
ABRIR_TUDO_JS = r"""
(sel) => {
  const raiz = document.querySelector(sel);
  raiz.querySelectorAll('.secao-recolhivel').forEach((s) => {
    if (s.dataset.aberto === 'false') { const c = s.querySelector('.secao-cabecalho'); if (c) c.click(); }
  });
  raiz.querySelectorAll('details:not([open])').forEach((d) => { d.open = true; });
}
"""


def semear(conn):
    """Estado com dado de verdade em cada tela (chips de tarefa, extrato, voo, habito...)."""
    h = date.today().isoformat()
    for tabela in ("subtasks", "tasks", "expenses", "notas", "voos", "habitos"):
        try:
            conn.execute(f"DELETE FROM {tabela}")
        except Exception:
            pass
    antigo = (datetime.now() - timedelta(days=9)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO tasks(title, due_date, created_at) VALUES (?, ?, ?)",
        ("Tarefa atrasada e travada com um título bem comprido pra quebrar linha", (date.today() - timedelta(days=3)).isoformat(), antigo),
    )
    for i in range(4):
        conn.execute("INSERT INTO tasks(title, due_date) VALUES (?, ?)", (f"Tarefa {i}", h if i % 2 else None))
    conn.execute("INSERT INTO tasks(title, due_date, completed_at) VALUES ('Feita', ?, datetime('now'))", (h,))
    agora = datetime.now()
    for i in range(6):
        dt = (agora - timedelta(days=i)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO expenses(amount, category, description, tipo, created_at) VALUES (?, ?, ?, 'real', ?)",
            (12.5 + 10 * i, ["mercado", "transporte", "lazer"][i % 3], f"gasto {i}", dt),
        )
    conn.execute("INSERT INTO notas(titulo, corpo) VALUES ('Ideia', 'texto da nota')")
    conn.execute("INSERT INTO voos(data, origem, destino) VALUES (?, 'SBMT', 'SBJD')", ((date.today() + timedelta(days=2)).isoformat(),))
    try:
        conn.execute("INSERT INTO habitos(nome) VALUES ('Beber água')")
    except Exception:
        pass


def _fake_usage():
    return {"model": "claude-sonnet-4-5", "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0}


@unittest.skipUnless(_PLAYWRIGHT_OK, "playwright nao instalado")
@unittest.skipUnless(_pronto, "servidor de teste nao respondeu")
class R3AcabamentoTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.DB_PATH = _DB_PROPRIO
        conn = db.get_db()
        semear(conn)
        conn.commit()
        conn.close()
        cls._patches = [
            patch("claude_client.summarize_day", return_value=("Resumo de teste.", _fake_usage())),
            patch("claude_client.chat", side_effect=lambda *a, **k: ("Resposta de teste.", [], _fake_usage())),
        ]
        for p in cls._patches:
            p.start()
        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(executable_path=_CHROME) if _CHROME else cls._pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls._browser.close()
        cls._pw.stop()
        for p in cls._patches:
            p.stop()

    def _pagina(self, largura):
        ctx = self._browser.new_context(viewport={"width": largura, "height": 844}, has_touch=True)
        self.addCleanup(ctx.close)
        ctx.add_init_script(CONTAR_FETCH)
        r = ctx.request.post(BASE_URL + "/login", data={"pin": PIN})
        self.assertEqual(r.status, 200)
        page = ctx.new_page()
        erros = []
        page.on("pageerror", lambda e: erros.append(str(e)))
        page.goto(BASE_URL + "/")
        esperar_carga(page)
        return page, erros

    def _esperar_rede(self, page):
        esperar_carga(page)

    def _auditar(self, page, sel):
        page.evaluate(ABRIR_TUDO_JS, sel)
        self._esperar_rede(page)
        esperar_assentar(page, sel)
        return page.evaluate(AUDIT_JS, sel)

    def _checar(self, res, onde):
        self.assertNotIn("erro", res, onde)
        self.assertEqual(res["pequenos"], [], f"{onde}: alvos de toque < 44px")
        self.assertEqual(res["miudos"], [], f"{onde}: textos < 12px")
        self.assertEqual(res["largos"], [], f"{onde}: elementos vazando na horizontal")
        self.assertFalse(res["overflow"], f"{onde}: rolagem horizontal na pagina")
        self.assertLessEqual(len(res["titulos"]), 1, f"{onde}: titulos de secao com estilos diferentes: {res['titulos']}")

    def _rodar_telas(self, largura):
        page, erros = self._pagina(largura)
        for aba in TELAS:
            page.evaluate("(a) => showTab(a)", aba)
            self._esperar_rede(page)
            with self.subTest(tela=aba, largura=largura):
                self._checar(self._auditar(page, f"#tab-{aba}"), f"{aba}@{largura}")
        page.evaluate("() => showTab('hoje')")
        self._esperar_rede(page)
        page.click("#fab-captura")
        page.wait_for_selector("#folha-captura:not([hidden])")
        with self.subTest(tela="folha+", largura=largura):
            self._checar(self._auditar(page, "#folha-captura"), f"folha+@{largura}")
        self.assertEqual(erros, [], f"pageerror @{largura}")

    def test_telas_390(self):
        self._rodar_telas(390)

    def test_telas_320(self):
        self._rodar_telas(320)

    def test_titulos_de_secao_iguais_aos_do_inicio(self):
        """O rotulo de secao das telas desta onda e o mesmo do Inicio ("AGORA")."""
        page, erros = self._pagina(390)
        ref = page.evaluate(
            "() => { const cs = getComputedStyle(document.querySelector('#tab-hoje .rotulo-tela'));"
            " return [cs.fontSize, cs.fontWeight, cs.letterSpacing, cs.textTransform, cs.color].join(' | '); }"
        )
        self.assertIn("13px", ref)
        self.assertIn("uppercase", ref)
        for aba in TELAS:
            page.evaluate("(a) => showTab(a)", aba)
            self._esperar_rede(page)
            res = self._auditar(page, f"#tab-{aba}")
            for estilo in res["titulos"]:
                self.assertEqual(estilo, ref, f"{aba}: {res['titulos'][estilo]}")
        self.assertEqual(erros, [])

    def test_inicio_sem_pendencia_nao_mostra_faixa_do_assistente(self):
        page, erros = self._pagina(390)
        # A faixa so nasce da resposta da caixa: lida ela, ja apareceu ou nao aparece mais
        page.wait_for_function(
            "() => window.__jsonLidos.some((url) => url.includes('/api/assistente/caixa'))", timeout=10000
        )
        faixas = page.evaluate(
            "() => [...document.querySelectorAll('#caixa-assistente .caixa-aviso-linha')]"
            ".filter((el) => !el.hidden && el.getBoundingClientRect().height > 0).map((el) => el.textContent.trim())"
        )
        self.assertEqual(faixas, [])
        self.assertEqual(erros, [])

    def test_inicio_com_pendencia_mostra_a_faixa(self):
        page, erros = self._pagina(390)
        page.route(
            "**/api/assistente/caixa",
            lambda r: r.fulfill(
                status=200,
                content_type="application/json",
                body='{"pendentes": 2, "itens": [{"id": 1, "tipo": "pergunta", "titulo": "Pergunta X"}]}',
            ),
        )
        page.reload()
        esperar_carga(page)
        page.wait_for_selector("#caixa-compacta-linha:not([hidden])", timeout=5000)
        self.assertIn("(2)", page.text_content("#caixa-compacta-linha"))
        self.assertEqual(erros, [])

    def test_placeholder_da_ia_e_ouvir_das_bolhas(self):
        page, erros = self._pagina(390)
        self.assertEqual(page.get_attribute("#chat-input", "placeholder"), "Pergunta ou fala algo…")
        page.click('.tab-btn[data-tab="assistente"]')
        page.fill("#chat-input", "oi")
        page.click("#chat-send")
        page.wait_for_function("document.getElementById('chat-mensagens').textContent.includes('Resposta de teste')", timeout=10000)
        # No caminho ao vivo o botao ouvir so entra depois da ultima palavra pingar
        page.wait_for_selector("#chat-mensagens .btn-ouvir-chat", state="attached", timeout=10000)
        esperar_assentar(page, "#chat-mensagens")
        alturas = page.evaluate(
            "() => [...document.querySelectorAll('#chat-mensagens button')]"
            ".filter((b) => b.getBoundingClientRect().height > 0).map((b) => b.getBoundingClientRect().height)"
        )
        self.assertTrue(alturas, "bolha da IA sem botao ouvir")
        self.assertTrue(all(h >= 43.5 for h in alturas), alturas)
        self.assertEqual(erros, [])


if __name__ == "__main__":
    unittest.main()
