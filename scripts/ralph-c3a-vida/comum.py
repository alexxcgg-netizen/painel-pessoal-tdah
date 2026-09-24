"""Base compartilhada dos scripts da faixa C3a (auditar.py, fuzz.py, capturar.py).

Sobe o app da worktree num banco TEMPORARIO (servidor.py, nunca o real), loga por PIN e
semeia dados SINTETICOS pt-BR em cada secao da aba Vida que e desta faixa. Secoes que
dependem de dado dificil de semear (assinaturas recorrentes, uso do celular, salvos que
chamariam IA pra resumir) sao preenchidas por `page.route` (dublê) - nenhuma chamada real
de API sai do ambiente.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import date, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
PORTA = os.environ.get("PORTA", "5131")
BASE = "http://127.0.0.1:" + PORTA
CHROME = "/opt/pw-browsers/chromium"
PY = "/home/user/painel-pessoal-tdah/.venv/bin/python"
PIN = "135790"

# Hosts externos que nao existem no sandbox (sem internet) - mesma excecao que a V3/V4
# ja documentaram. Falha de rede desses nao conta como erro da aba.
HOSTS_IGNORADOS = ("fonts.googleapis.com", "fonts.gstatic.com", "cdn.jsdelivr.net", "/api/summary/today")


def subir_servidor():
    env = dict(os.environ)
    env["PORTA"] = PORTA
    srv = subprocess.Popen([PY, os.path.join(AQUI, "servidor.py"), REPO], env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for _ in range(80):
        try:
            urllib.request.urlopen(BASE + "/", timeout=1)
            return srv
        except Exception:
            if srv.poll() is not None:
                break
            time.sleep(0.5)
    srv.terminate()
    print("servidor nao respondeu", (srv.stdout.read() if srv.stdout else "")[-3000:])
    sys.exit(2)


def logar(ctx):
    cab = {"Content-Type": "application/json"}
    r = ctx.request.post(BASE + "/configurar-pin", data=json.dumps({"pin": PIN, "confirmacao": PIN}), headers=cab)
    if r.status != 200:
        r = ctx.request.post(BASE + "/login", data=json.dumps({"pin": PIN}), headers=cab)
    assert r.status == 200, r.text()


def _post(ctx, url, corpo):
    r = ctx.request.post(BASE + url, data=json.dumps(corpo), headers={"Content-Type": "application/json"})
    return r.status


def semear(ctx):
    """Dados sinteticos, pt-BR. Devolve {url: status} pra conferencia."""
    hoje = date.today()
    st = {}
    st["garantia"] = ctx.request.post(BASE + "/api/garantias", multipart={
        "produto": "Geladeira Frost Free", "data_compra": (hoje - timedelta(days=700)).isoformat(),
        "prazo_garantia_meses": "24"}).status
    ctx.request.post(BASE + "/api/garantias", multipart={
        "produto": "Notebook de trabalho", "data_compra": (hoje - timedelta(days=60)).isoformat(),
        "prazo_garantia_meses": "12"})
    st["ideia"] = _post(ctx, "/api/ideias-presente", {"pessoa": "Mae", "ideia": "Livro de receitas", "ocasiao": "Aniversario"})
    st["pessoa"] = _post(ctx, "/api/pessoas", {"nome": "Joao", "frequencia_dias": 14})
    _post(ctx, "/api/pessoas", {"nome": "Tia Marta", "frequencia_dias": 30})
    st["ficha"] = _post(ctx, "/api/treino/fichas", {"grupo": "Peito", "exercicios": "Supino reto|4|10|40kg\nCrucifixo|3|12|"})
    st["manutencao"] = _post(ctx, "/api/manutencoes", {"tipo": "casa", "item": "Filtro de agua", "intervalo_meses": 6,
                                                      "ultima_vez": (hoje - timedelta(days=170)).isoformat()})
    _post(ctx, "/api/manutencoes", {"tipo": "carro", "item": "Troca de oleo", "data": (hoje - timedelta(days=90)).isoformat(),
                                    "km": 42000, "proxima_em_km": 52000, "proxima_em_data": None})
    st["aprender"] = _post(ctx, "/api/aprender", {"tema": "Investimento em FII"})
    st["compras"] = _post(ctx, "/api/compras", {"itens": ["Cafe", "Leite", "Pao de forma"]})
    st["responder"] = _post(ctx, "/api/responder", {"quem": "Carlos", "sobre": "orcamento da reforma"})
    st["medida"] = _post(ctx, "/api/medidas", {"tipo": "peso", "valor": 82.4, "unidade": "kg"})
    _post(ctx, "/api/medidas", {"tipo": "cintura", "valor": 91, "unidade": "cm"})
    return st


def _json(route, dados, status=200):
    route.fulfill(status=status, content_type="application/json", body=json.dumps(dados))


def dubles_leitura(page):
    """GETs que dependem de dado dificil de semear - respondidos com dublê sintetico."""
    page.route("**/api/assinaturas/revisao", lambda r: _json(r, [
        {"descricao": "Streaming de video", "valor": 39.9, "categoria": "Lazer"},
        {"descricao": "Armazenamento na nuvem", "valor": 9.9, "categoria": "Servicos"}])
        if r.request.method == "GET" else r.continue_())
    page.route("**/api/uso-apps?dias=7", lambda r: _json(r, {"apps": [
        {"app": "Instagram", "texto": "1h40 por dia"}, {"app": "YouTube", "texto": "55 min por dia"}]}))
    page.route("**/api/salvos", lambda r: _json(r, [
        {"id": 1, "url": "https://exemplo.com.br/artigo-sono", "titulo": "Como dormir melhor", "lido_em": None,
         "resumo": "Rotina fixa, luz baixa a noite e cafe so ate 14h."},
        {"id": 2, "url": "https://exemplo.com.br/video", "titulo": None, "lido_em": "2026-09-01", "resumo": None}])
        if r.request.method == "GET" else r.continue_())


def abrir_vida(page):
    page.goto(BASE + "/")
    page.wait_for_load_state("networkidle")
    time.sleep(0.6)
    page.click('.tab-btn[data-tab="vida"]')
    page.wait_for_load_state("networkidle")
    time.sleep(0.8)


def ligar_coleta(page, erros, rede):
    page.on("console", lambda m: erros.append(("console." + m.type, m.text)) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(("pageerror", str(e))))
    page.on("response", lambda resp: rede.append((resp.status, resp.url)) if resp.status >= 400 else None)
    page.on("requestfailed", lambda req: rede.append(("falhou", req.url)))


def filtrar_erros(erros):
    """Tira ruido de rede externa (sem internet no sandbox)."""
    return [e for e in erros if not any(h in e[1] for h in HOSTS_IGNORADOS)
            and "Failed to load resource" not in e[1]]
