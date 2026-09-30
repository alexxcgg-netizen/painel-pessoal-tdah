"""Vel (vel4): robustez das abas Vida/Painel - troca rapida, cache curto de
carga (static/js/nucleo/navegacao.js) e regras de desempenho.

Reaproveita a infra de shim/seed/gunicorn de scripts/medir_velocidade.py
(banco temporario, nunca o real; sem IA/Pluggy).
"""
import importlib.util
import random
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _ler(rel):
    return (REPO / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------- estaticos
def test_vida_secoes_abaixo_da_dobra_usam_content_visibility_auto():
    css = _ler("static/css/ui/desempenho.css")
    assert ".vida-secoes > .secao-recolhivel:nth-child(n + 4)" in css
    bloco = css.split(".vida-secoes > .secao-recolhivel:nth-child(n + 4)", 1)[1].split("}", 1)[0]
    assert "content-visibility: auto" in bloco
    assert "contain-intrinsic-size: auto" in bloco  # altura reservada: sem pulo de scroll


def test_fila_offline_invalida_cache_das_abas_ao_sincronizar():
    js = _ler("static/js/fila-offline.js")
    assert 'typeof invalidarDadosAbas === "function"' in js
    # a invalidacao vem depois do fetch direto e antes de ler o corpo
    i_fetch = js.index("res = await fetch(item.url")
    i_inv = js.index('typeof invalidarDadosAbas === "function"')
    assert i_fetch < i_inv < js.index("corpo = await res.json()")


def test_relogio_de_contagem_nao_roda_com_app_em_segundo_plano():
    js = _ler("static/js/cards.js")
    trecho = js.split("function iniciarRelogio()", 1)[1].split("function destacarItem", 1)[0]
    assert "document.hidden" in trecho


# ------------------------------------------------------------------ browser
pytest.importorskip("playwright")
_spec = importlib.util.spec_from_file_location("medir_velocidade", REPO / "scripts" / "medir_velocidade.py")
mv = importlib.util.module_from_spec(_spec)
sys.path.insert(0, str(REPO / "scripts"))
_spec.loader.exec_module(mv)
CHROME_OK = mv.CHROME is not None and Path(mv.CHROME).exists()


ABAS = mv.ABAS


@pytest.fixture(scope="module")
def app_no_ar():
    tempdir = Path(tempfile.mkdtemp(prefix="test_vel4_"))
    shim = mv.escrever_shim(tempdir, tempdir / "teste.db", tempdir / "tempos.json")
    mv.semear_banco(tempdir / "teste.db")
    proc = mv.subir_gunicorn(shim, tempdir)
    try:
        yield mv.BASE_URL, mv.PIN
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        shutil.rmtree(tempdir, ignore_errors=True)


@pytest.fixture()
def pagina(app_no_ar):
    from playwright.sync_api import sync_playwright

    base_url, pin = app_no_ar
    erros, gets = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=mv.CHROME)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        ctx.route("**/*", lambda r: r.continue_() if "127.0.0.1" in r.request.url else r.abort())
        ctx.request.post(base_url + "/login", data={"pin": pin})
        page = ctx.new_page()
        page.on("pageerror", lambda exc: erros.append(str(exc)))
        page.on("request", lambda r: gets.append(r.url) if r.method == "GET" and "/api/" in r.url else None)
        page.goto(base_url + "/", wait_until="load")
        page.wait_for_timeout(800)
        yield page, erros, gets
        browser.close()


ESTADO_JS = """() => ({
  vis: [...document.querySelectorAll('.tab-content')].filter(e => !e.hidden).map(e => e.id),
  ativo: [...document.querySelectorAll('.tab-btn.active')].map(b => b.dataset.tab),
  entraEscondida: [...document.querySelectorAll('.tab-content')].filter(e => e.hidden && /entra-/.test(e.className)).length,
  attrDivergente: [...document.querySelectorAll('.secao-recolhivel')].filter(s => {
    const a = s.dataset.aberto === 'true';
    const b = s.querySelector(':scope > .secao-cabecalho')?.getAttribute('aria-expanded') === 'true';
    return a !== b;
  }).length,
  ocultoMasAberto: document.querySelectorAll('.secao-recolhivel[data-aberto="true"] .c2-cv-oculto').length,
})"""


@pytest.mark.skipif(not CHROME_OK, reason="Chromium do Playwright nao encontrado")
@pytest.mark.parametrize("semente", [1, 2, 3])
def test_trocar_de_aba_30x_rapido_nao_quebra_a_tela(pagina, semente):
    page, erros, _ = pagina
    rnd = random.Random(semente)
    seq = [rnd.choice(ABAS) for _ in range(30)]
    seq[-1] = ["vida", "painel", "tarefas"][semente - 1]
    for aba in seq:
        page.evaluate(f"document.querySelector('.tab-btn[data-tab=\"{aba}\"]').click()")
        page.wait_for_timeout(rnd.choice([0, 5, 20, 60]))
    page.wait_for_timeout(1500)
    st = page.evaluate(ESTADO_JS)
    assert st["vis"] == [f"tab-{seq[-1]}"], st
    assert st["ativo"] == [seq[-1]], st
    assert st["entraEscondida"] == 0, st
    assert st["attrDivergente"] == 0 and st["ocultoMasAberto"] == 0, st
    assert erros == [], erros


@pytest.mark.skipif(not CHROME_OK, reason="Chromium do Playwright nao encontrado")
def test_abrir_e_fechar_secao_da_vida_rapido_termina_consistente(pagina):
    page, erros, _ = pagina
    page.click('.tab-btn[data-tab="vida"]')
    page.wait_for_timeout(600)
    cab = page.locator("#tab-vida .secao-cabecalho").nth(2)
    for _ in range(7):
        cab.click()
        page.wait_for_timeout(25)
    page.wait_for_timeout(700)
    st = page.evaluate(ESTADO_JS)
    assert st["attrDivergente"] == 0 and st["ocultoMasAberto"] == 0, st
    assert erros == [], erros


@pytest.mark.skipif(not CHROME_OK, reason="Chromium do Playwright nao encontrado")
def test_cache_de_30s_pula_recarga_sem_escrita_e_recarrega_depois_de_escrita(pagina):
    page, erros, gets = pagina
    contar = lambda sufixo: sum(1 for u in gets if u.split("?")[0].endswith(sufixo))  # noqa: E731

    def ir(aba):
        page.click(f'.tab-btn[data-tab="{aba}"]')
        page.wait_for_timeout(700)

    ir("painel")
    page.wait_for_timeout(3500)  # deixa terminar o resumo (falha lenta no teste) e os loads em rAF
    # a carga inicial da pagina (foco/visibilidade/erros de startup) pode ter
    # invalidado o cache uma vez: uma volta completa assenta o estado
    ir("hoje")
    ir("painel")
    page.wait_for_timeout(1500)
    base = contar("/api/saude/hoje")
    assert base >= 1
    # sem escrita: voltar dentro dos 30s NAO refaz o GET
    ir("hoje")
    ir("painel")
    assert contar("/api/saude/hoje") == base
    # escrita (+1 copo) invalida: proxima visita refaz o GET e mostra o total novo
    page.wait_for_function("/^[0-9]+$/.test(document.querySelector('#hidratacao-total').textContent.trim())")
    antes = int(page.text_content("#hidratacao-total"))
    page.click("#hidratacao-btn")
    page.wait_for_function(f"Number(document.querySelector('#hidratacao-total').textContent) === {antes + 1}")
    ir("hoje")
    n = contar("/api/saude/hoje")
    ir("painel")
    assert contar("/api/saude/hoje") > n
    page.wait_for_function(f"Number(document.querySelector('#hidratacao-total').textContent) === {antes + 1}")
    assert erros == [], erros


@pytest.mark.skipif(not CHROME_OK, reason="Chromium do Playwright nao encontrado")
def test_voltar_do_segundo_plano_recarrega_a_aba(pagina):
    page, erros, gets = pagina
    page.click('.tab-btn[data-tab="vida"]')
    page.wait_for_timeout(900)
    page.click('.tab-btn[data-tab="hoje"]')
    page.wait_for_timeout(300)
    base = sum(1 for u in gets if u.split("?")[0].endswith("/api/habitos"))
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")  # visibilityState = visible no headless
    page.click('.tab-btn[data-tab="vida"]')
    page.wait_for_timeout(900)
    assert sum(1 for u in gets if u.split("?")[0].endswith("/api/habitos")) > base
    assert erros == [], erros


def test_erro_do_resumo_de_ia_nao_invalida_o_cache_das_abas():
    js = _ler("static/js/nucleo/api.js")
    assert '"/api/summary/today"' in js
    trecho = js.split("if (!res.ok) {", 1)[1].split("return null;", 1)[0]
    assert "ehUrlOpcionalSemInvalidar(url)" in trecho and "invalidarDadosAbas" in trecho
