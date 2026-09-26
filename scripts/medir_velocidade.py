#!/usr/bin/env python3
"""scripts/medir_velocidade.py — mede a velocidade real do painel como no
iPhone: gunicorn (--workers 1 --threads 8, igual ao render.yaml), banco
temporario com volume realista, IA simulada lenta (3s, chave dummy) e
Playwright em 390x844 com CPU 4x mais lenta (CDP Emulation.setCPUThrottlingRate).

So MEDE. Nao corrige nada do app. Reexecutavel a qualquer momento (antes ou
depois de correcoes) — grava JSON + tabela markdown em --out-dir.

Uso:
    .venv/bin/python scripts/medir_velocidade.py [--out-dir DIR] [--repeticoes 10] [--sleep-render]

--sleep-render roda uma rodada extra atrasando TODAS as respostas do
servidor em 5s (simulacao do Render free acordando) e tira um print.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import subprocess
import sys
import tempfile
import textwrap
import time
from datetime import date, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PORT = 8799
BASE_URL = f"http://127.0.0.1:{PORT}"
PIN = "123456"
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

METAS = {
    "toque_botao": 100,
    "trocar_aba": 200,
    "concluir_tarefa": 100,
    "salvar_tarefa": 300,
    "salvar_lembrete": 300,
    "salvar_gasto": 300,
    "chat_recebi": 200,
    "abertura_com_cache": 1500,
}

ABAS = ["hoje", "painel", "aviacao", "vida", "tarefas", "gastos", "construtora", "assistente"]


# --------------------------------------------------------------------------
# 1) app "shim": importa o app.py real deste worktree, troca o DB por um
#    temporario com volume grande e faz a IA responder lento (3s), como
#    audit_app.py/audit.py da auditoria original. Gerado num arquivo próprio
#    pra poder subir sob gunicorn (--workers 1 --threads 8, igual ao Render).
# --------------------------------------------------------------------------
SHIM_TEMPLATE = '''
import os, sys, time
from pathlib import Path
os.environ["ANTHROPIC_API_KEY"] = "dummy"
os.environ["OPENAI_API_KEY"] = "dummy"
REPO = Path({repo!r})
sys.path.insert(0, str(REPO))
os.chdir(REPO)
import db
db.DB_PATH = Path({dbpath!r})
import auth, claude_client
_orig = {{n: getattr(claude_client, n) for n in ("summarize_day", "escolher_essencial", "chat")
         if hasattr(claude_client, n)}}
def _lenta(n):
    def f(*a, **k):
        time.sleep(3)
        return _orig[n](*a, **k)
    return f
import app as _m
for n in _orig:
    setattr(claude_client, n, _lenta(n))
    setattr(_m.claude_client, n, getattr(claude_client, n))
app = _m.app

from flask import request, g

ATRASO_GLOBAL = float(os.environ.get("MEDIR_ATRASO_GLOBAL", "0"))
if ATRASO_GLOBAL:
    @app.before_request
    def _atraso_global():
        if request.path.startswith("/api/") or request.path == "/":
            time.sleep(ATRASO_GLOBAL)

# p50/p95 por rota, medido no servidor (before/after_request), como no audit.py
import json as _json
TEMPOS_PATH = Path({tempos_path!r})
_tempos = {{}}
@app.before_request
def _t0():
    g._t0 = time.perf_counter()
@app.after_request
def _t1(resp):
    if request.path.startswith("/api/") or request.path == "/":
        chave = request.method + " " + request.path
        _tempos.setdefault(chave, []).append((time.perf_counter() - g._t0) * 1000)
        TEMPOS_PATH.write_text(_json.dumps(_tempos))
    return resp
'''


def escrever_shim(tempdir: Path, dbpath: Path, tempos_path: Path) -> Path:
    shim = tempdir / "medir_app.py"
    shim.write_text(
        SHIM_TEMPLATE.format(repo=str(REPO), dbpath=str(dbpath), tempos_path=str(tempos_path))
    )
    return shim


# --------------------------------------------------------------------------
# 2) seed do banco - mesmo volume do audit.py da auditoria (3000 transacoes,
#    1500 gastos, 400 tarefas com 100 pendentes, habitos, assinaturas, parcelas)
# --------------------------------------------------------------------------
SEED_SCRIPT = '''
import sys, random
from pathlib import Path
from datetime import date, timedelta, datetime
sys.path.insert(0, {repo!r})
import os
os.chdir({repo!r})
import db
db.DB_PATH = Path({dbpath!r})
db.init_db()
import auth
conn = db.get_db()
auth.definir_pin(conn, {pin!r}, {pin!r})
random.seed(7)
HOJE = date.today()
conta = db.get_or_create_bank_account(conn, "Nubank", "conta")
cartao = db.get_or_create_bank_account(conn, "Nubank", "cartao")
db.atualizar_saldo_conta(conn, conta, 1520.40)
db.atualizar_saldo_conta(conn, cartao, 2377.35)
cats = ["Groceries", "Restaurants", "Pharmacy", "Transport", "Shopping", "Services", "Entertainment"]
for i in range(3000):
    d = (HOJE - timedelta(days=random.randint(0, 540))).isoformat()
    conn.execute(
        "INSERT INTO bank_transactions (bank_account_id,data,descricao,valor,external_id,categoria,"
        "categoria_pluggy,descricao_original,tipo_operacao) VALUES (?,?,?,?,?,?,?,?,?)",
        (cartao if i % 3 else conta, d, db.criptografia.criptografar(f"LOJA {{i%90}} LTDA"),
         db._cnum(round(random.uniform(5, 400), 2)), f"x{{i}}", None, random.choice(cats),
         f"LOJA {{i%90}} LTDA", "CREDIT" if i % 17 == 0 else "DEBIT"),
    )
for i in range(1500):
    dt = datetime.now() - timedelta(days=random.randint(0, 365), minutes=random.randint(0, 900))
    conn.execute(
        "INSERT INTO expenses (amount,category,description,source_text,tipo,created_at) VALUES (?,?,?,?,?,?)",
        (round(random.uniform(3, 300), 2), random.choice(["mercado", "transporte", "lazer", "outros"]),
         f"gasto {{i}}", "", "real", dt.strftime("%Y-%m-%d %H:%M:%S")),
    )
# 400 tarefas, 100 pendentes (300 ja concluidas - bate com o brief)
for i in range(400):
    pendente = i < 100
    due = (HOJE + timedelta(days=random.randint(-20, 30))).isoformat() if i % 4 == 0 else None
    comp = None if pendente else (datetime.now() - timedelta(days=random.randint(0, 90))).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO tasks (title,due_date,completed_at) VALUES (?,?,?)", (f"Tarefa {{i}}", due, comp))
for i in range(8):
    conn.execute("INSERT INTO assinatura (nome,valor,dia_cobranca,inicio) VALUES (?,?,?,?)",
                 (f"Assin {{i}}", 19.9 + i, (HOJE.day + i) % 28 + 1, "2025-01-01"))
cols = [r[1] for r in conn.execute("PRAGMA table_info(compra_parcelada)")]
try:
    base = {{"descricao": "Geladeira", "valor_parcela": 250.0, "valor_total": 2500.0, "n_parcelas": 10,
            "primeira_parcela": (HOJE.replace(day=1) - timedelta(days=60)).isoformat(), "parcela_atual": 3}}
    for k in range(4):
        linha = {{c: v for c, v in base.items() if c in cols}}
        linha["descricao"] = f"Compra parcelada {{k}}"
        conn.execute(f"INSERT INTO compra_parcelada ({{','.join(linha)}}) VALUES ({{','.join('?'*len(linha))}})",
                     tuple(linha.values()))
except Exception as e:
    print("parcelas nao inseridas:", e, cols)
try:
    for nome, freq in [("Beber agua", "diaria"), ("Alongar", "diaria"), ("Ler", "semanal")]:
        db.create_habito(conn, nome, None, freq, None, None if freq == "diaria" else 3, None)
except Exception as e:
    print("habitos nao inseridos:", e)
conn.commit()
conn.close()
print("seed ok")
'''


def semear_banco(dbpath: Path):
    codigo = SEED_SCRIPT.format(repo=str(REPO), dbpath=str(dbpath), pin=PIN)
    subprocess.run([sys.executable, "-c", codigo], check=True, cwd=REPO)


# --------------------------------------------------------------------------
# 3) subir gunicorn (--workers 1 --threads 8 --timeout 120, igual render.yaml)
# --------------------------------------------------------------------------
def subir_gunicorn(shim: Path, tempdir: Path, atraso_global: float = 0) -> subprocess.Popen:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(tempdir) + os.pathsep + str(REPO)
    env["MEDIR_ATRASO_GLOBAL"] = str(atraso_global)
    proc = subprocess.Popen(
        [sys.executable, "-m", "gunicorn", "medir_app:app", "--workers", "1", "--threads", "8",
         "--timeout", "120", "--bind", f"127.0.0.1:{PORT}"],
        cwd=tempdir, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        time.sleep(0.5)
        try:
            import urllib.request
            urllib.request.urlopen(BASE_URL + "/login", timeout=1)
            break
        except Exception:
            continue
    return proc


# --------------------------------------------------------------------------
# 4) medicoes no navegador (Playwright + CDP)
# --------------------------------------------------------------------------
JS_OBSERVER_SETUP = """
window.__eventos = [];
window.__longtasks = [];
try {
  new PerformanceObserver((list) => {
    for (const e of list.getEntries()) {
      window.__eventos.push({name: e.name, start: e.startTime, dur: e.duration, procEnd: e.processingEnd});
    }
  }).observe({type: 'event', buffered: true, durationThreshold: 0});
} catch (e) { window.__obs_event_erro = String(e); }
try {
  new PerformanceObserver((list) => {
    for (const e of list.getEntries()) window.__longtasks.push({start: e.startTime, dur: e.duration});
  }).observe({type: 'longtask', buffered: true});
} catch (e) { window.__obs_longtask_erro = String(e); }
"""


def medir_toque_e_frame(page, seletor, acao=None):
    """Tempo entre pointerdown no seletor e o proximo frame com mudanca de
    estilo observavel (classe/atributo) OU o proximo evento 'click' processado
    (Event Timing API), o que vier primeiro medido."""
    page.evaluate("window.__marcador = null; window.__t_pointerdown = null;")
    el = page.locator(seletor).first
    box = el.bounding_box()
    t0 = time.perf_counter()
    el.dispatch_event("pointerdown")
    if acao:
        acao()
    else:
        el.click()
    # espera 1 frame + mede via rAF quando o snapshot de estilo (classList) muda
    dt_ms = page.evaluate(
        """() => new Promise((resolve) => {
            const t0 = performance.now();
            requestAnimationFrame(() => requestAnimationFrame(() => resolve(performance.now() - t0)));
        })"""
    )
    total_ms = (time.perf_counter() - t0) * 1000
    return round(total_ms, 1)


def coletar_longtasks(page):
    try:
        return page.evaluate("window.__longtasks || []")
    except Exception:
        return []


def rodar_medicoes(page, ctx, n_rep: int):
    resultados = {}
    longtasks_por_acao = {}

    def registrar(nome, valores, lt):
        resultados[nome] = valores
        longtasks_por_acao[nome] = lt

    # ---- 1) toque em botao qualquer (chip de energia em Tarefas: muda .active
    #         de classe de forma sincrona, sem esperar rede) ------------------
    page.click('.tab-btn[data-tab="tarefas"]')
    page.wait_for_timeout(600)
    vals, lts = [], []
    for i in range(n_rep):
        page.evaluate("window.__longtasks = []")
        t0 = time.perf_counter()
        page.click("#energia-botoes button:nth-child(1)")
        page.evaluate(
            "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )
        vals.append((time.perf_counter() - t0) * 1000)
        lts.append(coletar_longtasks(page))
        page.wait_for_timeout(150)
    registrar("toque_botao", vals, lts)

    # ---- 2) trocar de aba (cada uma das 8) ---------------------------------
    for aba in ABAS:
        vals, lts = [], []
        outra = "hoje" if aba != "hoje" else "painel"
        for i in range(n_rep):
            page.click(f'.tab-btn[data-tab="{outra}"]')
            page.wait_for_timeout(120)
            page.evaluate("window.__longtasks = []")
            t0 = time.perf_counter()
            page.click(f'.tab-btn[data-tab="{aba}"]')
            page.wait_for_function(f"document.querySelector('#tab-{aba}') && !document.querySelector('#tab-{aba}').hidden")
            # fim das tarefas longas pendentes: espera 1 frame livre (heuristica: 80ms sem novo longtask)
            page.wait_for_timeout(80)
            vals.append((time.perf_counter() - t0) * 1000)
            lts.append(coletar_longtasks(page))
        registrar(f"trocar_aba_{aba}", vals, lts)

    # ---- 3) concluir tarefa (precisa de tarefas pendentes: 100 semeadas) ---
    page.click('.tab-btn[data-tab="tarefas"]')
    page.wait_for_timeout(500)
    vals, lts = [], []
    for i in range(n_rep):
        page.evaluate("window.__longtasks = []")
        btns = page.locator("#lista-tarefas button:has-text('concluir')")
        if btns.count() == 0:
            break
        t0 = time.perf_counter()
        btns.first.click()
        try:
            page.wait_for_selector("#lista-tarefas li.saindo", timeout=3000)
        except Exception:
            pass
        vals.append((time.perf_counter() - t0) * 1000)
        lts.append(coletar_longtasks(page))
        page.wait_for_timeout(400)
    registrar("concluir_tarefa", vals, lts)

    # ---- 4a) salvar tarefa (formulario direto, sem IA) ---------------------
    vals, lts = [], []
    for i in range(n_rep):
        page.click("#tarefa-abrir-btn")
        page.wait_for_selector("#nova-tarefa-titulo", state="visible")
        page.fill("#nova-tarefa-titulo", f"medir {i}")
        page.evaluate("window.__longtasks = []")
        t0 = time.perf_counter()
        page.click("#nova-tarefa-btn")
        page.wait_for_function("document.querySelector('#nova-tarefa-btn').textContent.includes('Salvar tarefa')")
        vals.append((time.perf_counter() - t0) * 1000)
        lts.append(coletar_longtasks(page))
        page.wait_for_timeout(200)
    registrar("salvar_tarefa", vals, lts)

    # ---- 4b) salvar lembrete (aba Painel, formulario direto) ---------------
    page.click('.tab-btn[data-tab="painel"]')
    page.wait_for_timeout(800)
    vals, lts = [], []
    for i in range(n_rep):
        page.click("#lembrete-abrir-btn")
        page.wait_for_selector("#lembrete-titulo", state="visible")
        page.fill("#lembrete-titulo", f"lembrete {i}")
        page.fill("#lembrete-data", "2026-12-01")
        page.evaluate("window.__longtasks = []")
        t0 = time.perf_counter()
        page.click("#lembrete-btn")
        page.wait_for_function("document.querySelector('#lembrete-btn').textContent.includes('Salvar data')")
        vals.append((time.perf_counter() - t0) * 1000)
        lts.append(coletar_longtasks(page))
        page.wait_for_timeout(200)
    registrar("salvar_lembrete", vals, lts)

    # ---- 4c) salvar gasto (captura de texto livre - passa pela IA simulada) -
    page.click('.tab-btn[data-tab="hoje"]')
    page.wait_for_timeout(300)
    vals, lts = [], []
    for i in range(min(n_rep, 5)):  # 3s de IA cada -> 5 bastam pra mediana/pior
        page.fill("#captura-input", f"gastei 20 reais no mercado {i}")
        page.evaluate("window.__longtasks = []")
        t0 = time.perf_counter()
        page.click("#captura-btn")
        page.wait_for_function("document.querySelector('#captura-btn').textContent.includes('Adicionar')")
        vals.append((time.perf_counter() - t0) * 1000)
        lts.append(coletar_longtasks(page))
        page.wait_for_timeout(200)
    registrar("salvar_gasto", vals, lts)

    # ---- 5) chat/voz: primeiro sinal de "recebi" ---------------------------
    vals, lts = [], []
    for i in range(n_rep):
        page.fill("#chat-input", f"oi {i}")
        page.evaluate("window.__longtasks = []")
        t0 = time.perf_counter()
        page.click("#chat-send")
        page.wait_for_function(
            "document.querySelectorAll('#chat-mensagens .chat-bolha, #chat-mensagens [class*=bolha]').length > 0"
            " || document.querySelector('#chat-mensagens')?.textContent.length > 0"
        )
        vals.append((time.perf_counter() - t0) * 1000)
        lts.append(coletar_longtasks(page))
        page.wait_for_timeout(3200)  # espera a IA simulada (3s) terminar antes do proximo envio
    registrar("chat_recebi", vals, lts)

    return resultados, longtasks_por_acao


def medir_abertura(ctx, com_cache: bool):
    page = ctx.new_page()
    page.add_init_script(JS_OBSERVER_SETUP)
    t0 = time.perf_counter()
    page.goto(BASE_URL + "/", wait_until="load")
    load_ms = (time.perf_counter() - t0) * 1000
    # "Hoje utilizavel": chat aceita digitar + lista de foco/tarefas visivel
    try:
        page.wait_for_selector("#chat-input:not([disabled])", timeout=5000)
        page.wait_for_function("document.querySelector('#lista-tarefas') || document.querySelector('#tab-hoje')", timeout=5000)
        util_ms = (time.perf_counter() - t0) * 1000
    except Exception:
        util_ms = None
    dom_n = page.evaluate("document.getElementsByTagName('*').length")
    metrics = {}
    try:
        cdp = ctx.new_cdp_session(page)
        cdp.send("Performance.enable")
        for m in cdp.send("Performance.getMetrics")["metrics"]:
            if m["name"] in ("ScriptDuration", "LayoutDuration", "RecalcStyleDuration", "TaskDuration"):
                metrics[m["name"]] = m["value"]
    except Exception:
        pass
    bytes_js, bytes_css, n_arquivos = 0, 0, 0
    for r in page.evaluate("performance.getEntriesByType('resource').map(r => ({name:r.name, size:r.transferSize, type:r.initiatorType}))"):
        n_arquivos += 1
        if r["name"].endswith(".js"):
            bytes_js += r["size"] or 0
        elif r["name"].endswith(".css"):
            bytes_css += r["size"] or 0
    page.close()
    return {
        "load_ms": round(load_ms, 1),
        "utilizavel_ms": round(util_ms, 1) if util_ms else None,
        "dom_elementos": dom_n,
        "bytes_js": bytes_js,
        "bytes_css": bytes_css,
        "n_arquivos": n_arquivos,
        "cdp_metrics_ms": {k: round(v * 1000, 1) if k != "TaskDuration" else round(v * 1000, 1) for k, v in metrics.items()},
    }


# --------------------------------------------------------------------------
def resumir(vals):
    if not vals:
        return {"mediana": None, "pior": None, "n": 0}
    vals = sorted(vals)
    return {"mediana": round(statistics.median(vals), 1), "pior": round(vals[-1], 1), "n": len(vals)}


def p50_p95(lista_ms):
    if not lista_ms:
        return None, None
    s = sorted(lista_ms)
    p50 = s[len(s) // 2]
    p95 = s[min(len(s) - 1, int(len(s) * 0.95))]
    return round(p50, 1), round(p95, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(REPO / "scratchpad_velocidade"))
    ap.add_argument("--repeticoes", type=int, default=10)
    ap.add_argument("--sleep-render", action="store_true")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    tempdir = Path(tempfile.mkdtemp(prefix="medir_"))
    dbpath = tempdir / "medir.db"
    tempos_path = tempdir / "tempos.json"
    shim = escrever_shim(tempdir, dbpath, tempos_path)

    print("semeando banco...", file=sys.stderr)
    semear_banco(dbpath)

    print("subindo gunicorn (--workers 1 --threads 8, igual render.yaml)...", file=sys.stderr)
    proc = subir_gunicorn(shim, tempdir)

    from playwright.sync_api import sync_playwright

    relatorio = {"gerado_em": datetime.now().isoformat(), "metas": METAS, "acoes": {}, "rotas_servidor": {},
                 "abertura": {}, "longtasks": {}, "avisos": []}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROME)
            ctx = browser.new_context(viewport={"width": 390, "height": 844})
            ctx.route("**/*", lambda r: r.continue_() if "127.0.0.1" in r.request.url else r.abort())
            ctx.request.post(BASE_URL + "/login", data={"pin": PIN})

            page = ctx.new_page()
            page.add_init_script(JS_OBSERVER_SETUP)
            cdp = ctx.new_cdp_session(page)
            cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})

            page.goto(BASE_URL + "/", wait_until="load")
            page.wait_for_timeout(1000)

            resultados, longtasks = rodar_medicoes(page, ctx, args.repeticoes)
            for nome, vals in resultados.items():
                relatorio["acoes"][nome] = resumir(vals)
                lt = longtasks.get(nome, [])
                total_lt = sum(len(x) for x in lt)
                maior_lt = max((e["dur"] for x in lt for e in x), default=0)
                relatorio["longtasks"][nome] = {"contagem": total_lt, "maior_ms": round(maior_lt, 1)}
            page.close()

            # abertura fria (novo contexto sem cache) + abertura com cache (2a carga)
            ctx2 = browser.new_context(viewport={"width": 390, "height": 844})
            ctx2.route("**/*", lambda r: r.continue_() if "127.0.0.1" in r.request.url else r.abort())
            ctx2.request.post(BASE_URL + "/login", data={"pin": PIN})
            relatorio["abertura"]["fria"] = medir_abertura(ctx2, com_cache=False)
            relatorio["abertura"]["com_cache_2a_carga"] = medir_abertura(ctx2, com_cache=True)
            ctx2.close()

            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    if tempos_path.exists():
        tempos = json.loads(tempos_path.read_text())
        for rota, vals in tempos.items():
            p50, p95 = p50_p95(vals)
            relatorio["rotas_servidor"][rota] = {"p50_ms": p50, "p95_ms": p95, "n": len(vals)}

    # ---- simulacao Render acordando (atraso global de 5s numa rodada extra) --
    if args.sleep_render:
        print("simulando Render acordando (atraso de 5s em tudo)...", file=sys.stderr)
        tempdir2 = Path(tempfile.mkdtemp(prefix="medir_sleep_"))
        db2 = tempdir2 / "medir.db"
        tempos2 = tempdir2 / "tempos.json"
        shim2 = escrever_shim(tempdir2, db2, tempos2)
        semear_banco(db2)
        proc2 = subir_gunicorn(shim2, tempdir2, atraso_global=5.0)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=CHROME)
                ctx = browser.new_context(viewport={"width": 390, "height": 844})
                ctx.route("**/*", lambda r: r.continue_() if "127.0.0.1" in r.request.url else r.abort())
                ctx.request.post(BASE_URL + "/login", data={"pin": PIN})
                page = ctx.new_page()
                t0 = time.perf_counter()
                page.goto(BASE_URL + "/", wait_until="commit")
                page.wait_for_timeout(1500)  # tela como o usuario veria nos primeiros ~1.5s de espera
                page.screenshot(path=str(out / "render_acordando.png"))
                page.wait_for_timeout(6000)
                relatorio["render_acordando"] = {
                    "descricao": "1a requisicao apos dormir (Render free) - nao medivel localmente em duracao real; "
                                  "aqui simulado atrasando TODAS as respostas em 5s. Print em render_acordando.png "
                                  "mostra a tela ~1.5s apos o toque.",
                    "tem_indicador_carregando_visivel": page.evaluate(
                        "!!document.querySelector('.carregando, .loading, [class*=spinner], [class*=skeleton]')"
                    ),
                }
                browser.close()
        finally:
            proc2.terminate()
            try:
                proc2.wait(timeout=10)
            except Exception:
                proc2.kill()

    # ---- grava JSON ----------------------------------------------------------
    (out / "antes.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=1, default=str))

    # ---- tabela markdown ------------------------------------------------------
    linhas_tabela = []
    mapa_meta = {
        "toque_botao": ("Toque em botão (chip energia)", METAS["toque_botao"]),
        "concluir_tarefa": ("Concluir tarefa", METAS["concluir_tarefa"]),
        "salvar_tarefa": ("Salvar tarefa (form direto)", METAS["salvar_tarefa"]),
        "salvar_lembrete": ("Salvar lembrete (form direto)", METAS["salvar_lembrete"]),
        "salvar_gasto": ("Salvar gasto (captura texto/IA)", METAS["salvar_gasto"]),
        "chat_recebi": ("Chat: 1º sinal de recebi", METAS["chat_recebi"]),
    }
    for chave, (rotulo, meta) in mapa_meta.items():
        r = relatorio["acoes"].get(chave, {})
        linhas_tabela.append((rotulo, r.get("mediana"), r.get("pior"), meta))
    for aba in ABAS:
        r = relatorio["acoes"].get(f"trocar_aba_{aba}", {})
        linhas_tabela.append((f"Trocar de aba: {aba}", r.get("mediana"), r.get("pior"), METAS["trocar_aba"]))
    ab = relatorio["abertura"].get("com_cache_2a_carga", {})
    linhas_tabela.append(("Abrir com cache (2ª carga)", ab.get("utilizavel_ms") or ab.get("load_ms"), None, METAS["abertura_com_cache"]))

    md = ["# Medição de velocidade — antes\n", f"Gerado em {relatorio['gerado_em']}\n",
          "| ação | mediana (ms) | pior de 10 (ms) | meta (ms) | dentro da meta? | causa provável |",
          "|---|---|---|---|---|---|"]
    for rotulo, mediana, pior, meta in linhas_tabela:
        ok = "-" if mediana is None else ("SIM" if mediana <= meta else "NAO")
        md.append(f"| {rotulo} | {mediana} | {pior} | {meta} | {ok} | (ver relatório/achados) |")
    md.append("\n## p50/p95 por rota /api (servidor)\n")
    md.append("| rota | p50 (ms) | p95 (ms) | meta p95 | n |")
    md.append("|---|---|---|---|---|")
    for rota, r in sorted(relatorio["rotas_servidor"].items(), key=lambda kv: -(kv[1]["p95_ms"] or 0)):
        ok = "" if r["p95_ms"] is None else ("" if r["p95_ms"] < 500 else " (ACIMA)")
        md.append(f"| {rota} | {r['p50_ms']} | {r['p95_ms']}{ok} | 500 | {r['n']} |")
    md.append("\n## Abertura\n")
    md.append("```")
    md.append(json.dumps(relatorio["abertura"], ensure_ascii=False, indent=1))
    md.append("```")
    md.append("\n## Tarefas longas (>50ms) por ação\n")
    md.append("| ação | contagem | maior (ms) |")
    md.append("|---|---|---|")
    for nome, lt in relatorio["longtasks"].items():
        md.append(f"| {nome} | {lt['contagem']} | {lt['maior_ms']} |")
    if "render_acordando" in relatorio:
        md.append("\n## Render free acordando (simulado)\n")
        md.append(json.dumps(relatorio["render_acordando"], ensure_ascii=False, indent=1))

    (out / "antes.md").write_text("\n".join(md) + "\n")
    print(f"OK - relatorio em {out}/antes.json e {out}/antes.md", file=sys.stderr)


if __name__ == "__main__":
    main()
