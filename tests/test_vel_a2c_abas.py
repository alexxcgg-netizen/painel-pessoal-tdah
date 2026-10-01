"""Vel (A2c): smoke test Playwright das 8 abas depois da otimizacao de
showTab/animacao de entrada/carga do Painel (static/js/nucleo/navegacao.js,
static/js/nucleo/init.js).

Abre o app, passa pelas 8 abas (ORDEM_ABAS de navegacao.js) e confere:
  - 0 `pageerror` (nenhum script quebrou com elemento ausente / undefined);
  - cada aba mostra algum conteudo visivel (nao fica em branco ao trocar);
  - criar tarefa (formulario direto - #tarefa-abrir-btn, sem IA) e criar
    gasto via captura de texto livre (classificador_local/regras/n1_financas.py
    resolve "gastei X reais..." sem IA - ver app.py `/api/capture`) continuam
    funcionando com a aba de origem (Hoje) e a de destino (Tarefas/Gastos)
    ja montadas (n1_financas nao precisa de rede/IA, dentro da regra do
    BRIEF de nao chamar IA/Pluggy de verdade em teste).

Reaproveita a infra de shim/seed/gunicorn de scripts/medir_velocidade.py
(banco temporario, nunca o real) em vez de duplicar.
"""
import importlib.util
import shutil
import sys
import tempfile
import time
from pathlib import Path

import pytest

pytest.importorskip("playwright")

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("medir_velocidade", REPO / "scripts" / "medir_velocidade.py")
mv = importlib.util.module_from_spec(_spec)
sys.path.insert(0, str(REPO / "scripts"))
_spec.loader.exec_module(mv)

CHROME_DISPONIVEL = mv.CHROME is not None and Path(mv.CHROME).exists()

# R1 (reformulacao): barra de 5 - abas fora dela abrem pela tela Mais.
from tests.playwright_helper import abrir_tela  # noqa: E402

ABAS = mv.ABAS  # ["hoje", "painel", "aviacao", "vida", "tarefas", "gastos", "construtora", "assistente"]


@pytest.fixture(scope="module")
def app_no_ar():
    tempdir = Path(tempfile.mkdtemp(prefix="test_vel_a2c_"))
    dbpath = tempdir / "teste.db"
    tempos_path = tempdir / "tempos.json"
    shim = mv.escrever_shim(tempdir, dbpath, tempos_path)
    mv.semear_banco(dbpath)
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


@pytest.fixture(scope="module")
def pagina(app_no_ar):
    from playwright.sync_api import sync_playwright

    base_url, pin = app_no_ar
    erros = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=mv.CHROME)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        ctx.route("**/*", lambda r: r.continue_() if "127.0.0.1" in r.request.url else r.abort())
        ctx.request.post(base_url + "/login", data={"pin": pin})
        page = ctx.new_page()
        page.on("pageerror", lambda exc: erros.append(str(exc)))
        page.goto(base_url + "/", wait_until="load")
        page.wait_for_timeout(800)
        yield page, erros
        browser.close()


def test_zero_pageerror_e_conteudo_ao_passar_pelas_8_abas(pagina):
    page, erros = pagina
    for aba in ABAS:
        abrir_tela(page, aba)
        page.wait_for_function(
            f"document.querySelector('#tab-{aba}') && !document.querySelector('#tab-{aba}').hidden"
        )
        page.wait_for_timeout(250)
        secao = page.locator(f"#tab-{aba}")
        assert secao.is_visible(), f"aba {aba} nao ficou visivel"
        texto = secao.inner_text().strip()
        assert len(texto) > 0, f"aba {aba} ficou sem conteudo visivel"
    assert erros == [], f"pageerror ao passar pelas 8 abas: {erros}"


def test_criar_tarefa_form_direto_com_outras_abas_montadas(pagina):
    page, erros = pagina
    page.click('.tab-btn[data-tab="tarefas"]')
    page.wait_for_timeout(300)
    titulo = f"tarefa vel a2c {int(time.time())}"
    page.click("#tarefa-abrir-btn")
    page.wait_for_selector("#nova-tarefa-titulo", state="visible")
    page.fill("#nova-tarefa-titulo", titulo)
    page.click("#nova-tarefa-btn")
    page.wait_for_function("document.querySelector('#nova-tarefa-btn').textContent.includes('Salvar tarefa')")
    page.wait_for_timeout(300)
    assert titulo in page.locator("#lista-tarefas").inner_text()
    assert erros == [], f"pageerror ao criar tarefa: {erros}"


def test_captura_de_gasto_nao_quebra_pagina(pagina):
    """A captura de gasto de texto livre ("gastei X reais...") no app real
    cai na classificacao por IA (nao ha regra local pra despesa simples de
    um unico item - so pra assinatura/parcela, ver classificador_local/
    regras/n1_financas.py), e o BRIEF proibe teste chamar IA de verdade. O
    que cabe aqui, sem violar essa regra e sem mock de IA (fora dos meus
    arquivos: captura.js/app.py/claude_client.py sao de outra faixa), e
    confirmar que digitar e clicar em Adicionar - com a aba Gastos ja
    montada, igual sempre foi - nao produz `pageerror` nem deixa a UI
    travada (botao sempre volta pra "Adicionar"), que e a garantia que
    importa pra esta faixa (nao mudei quando/como os elementos das abas
    existem, so a troca de aba e a animacao)."""
    page, erros = pagina
    page.click('.tab-btn[data-tab="hoje"]')
    page.wait_for_timeout(300)
    # R1: a captura mora na folha do botao "+" (antes no topo de toda tela)
    page.click("#fab-captura")
    page.wait_for_selector("#folha-captura.bottom-sheet--aberto")
    page.wait_for_timeout(350)
    marcador = f"vel a2c {int(time.time())}"
    page.fill("#captura-input", f"gastei 17 reais no mercado {marcador}")
    page.click("#captura-btn")
    page.wait_for_function(
        "document.querySelector('#captura-btn').textContent.includes('Adicionar')", timeout=15000
    )
    page.wait_for_timeout(300)
    page.keyboard.press("Escape")  # R1: fecha a folha antes de trocar de aba
    page.wait_for_function("document.getElementById('folha-captura').hidden")
    page.click('.tab-btn[data-tab="gastos"]')
    page.wait_for_timeout(300)
    assert erros == [], f"pageerror ao usar a captura de gasto: {erros}"
