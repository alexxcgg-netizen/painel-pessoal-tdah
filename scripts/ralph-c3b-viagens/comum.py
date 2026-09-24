"""Pecas compartilhadas pelos scripts Playwright da faixa C3b (auditar.py, fuzz.py, verificar.py).
Banco sempre sintetico (servidor.py). Leaflet servido de copia local conferida pelo SRI
(vendor/, baixada com curl - o Chromium do sandbox nao passa pelo proxy); tiles do OSM viram
um PNG transparente de 1x1 (duble, sem rede)."""
import base64
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:" + os.environ.get("PORTA", "5132")
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
PIN = "135790"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
# Falhas de ambiente conhecidas (fonte do Google sem rede e resumo de IA com chave falsa) -
# mesma lista de scripts/ralph-v0c-secoes/verificar.py.
AMBIENTE = ("fonts.googleapis.com", "fonts.gstatic.com", "/api/summary/today")


def logar(ctx):
    r = ctx.request.post(BASE + "/configurar-pin", data=json.dumps({"pin": PIN, "confirmacao": PIN}),
                         headers={"Content-Type": "application/json"})
    if r.status != 200:
        r = ctx.request.post(BASE + "/login", data=json.dumps({"pin": PIN}),
                             headers={"Content-Type": "application/json"})
    assert r.status == 200, r.text()


VENDOR = ("leaflet.js", "leaflet.css", "images/marker-icon.png", "images/marker-icon-2x.png",
          "images/marker-shadow.png")


def garantir_vendor():
    """Baixa (curl, fora do navegador) a copia local do Leaflet 1.9.4 se ainda nao existir.
    Nao versionada - o SRI em static/js/secoes/vida/lugares.js confere o conteudo."""
    import subprocess

    for rel in VENDOR:
        destino = os.path.join(AQUI, "vendor", *rel.split("/"))
        if not os.path.exists(destino):
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            subprocess.run(["curl", "-sS", "-o", destino,
                            "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/" + rel], check=True)


def rotas_de_rede(ctx):
    garantir_vendor()

    def leaflet(route):
        rel = route.request.url.split("/dist/", 1)[-1].split("?", 1)[0]
        caminho = os.path.join(AQUI, "vendor", *rel.split("/"))
        tipo = ("text/css" if rel.endswith(".css") else "image/png" if rel.endswith(".png")
                else "application/javascript")
        with open(caminho, "rb") as f:
            route.fulfill(status=200, body=f.read(), content_type=tipo,
                          headers={"Access-Control-Allow-Origin": "*"})

    ctx.route("https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/**", leaflet)
    ctx.route("https://*.tile.openstreetmap.org/**",
              lambda route: route.fulfill(status=200, body=PNG_1X1, content_type="image/png"))
    ctx.route("https://fonts.googleapis.com/**", lambda route: route.fulfill(status=200, body="", content_type="text/css"))
    ctx.route("https://fonts.gstatic.com/**", lambda route: route.abort())


def semear(ctx):
    """Dados sinteticos em pt-BR (nenhum dado real do Alex)."""
    def post(url, corpo):
        r = ctx.request.post(BASE + url, data=json.dumps(corpo), headers={"Content-Type": "application/json"})
        return r.json() if r.ok else None

    post("/api/viagens", {"destino": "Gramado", "data_ida": "2026-11-12", "data_volta": "2026-11-16",
                          "internacional": False})
    post("/api/viagens", {"destino": "Lisboa", "data_ida": "2027-02-03", "internacional": True})
    post("/api/lugares", {"nome": "Cafe da Praca", "cidade": "Blumenau"})
    post("/api/lugares", {"nome": "Lugar naoexiste", "cidade": "Cidade X"})
    c = post("/api/cotacoes", {"titulo": "Portas de madeira"})
    if c:
        cid = c.get("id") or c.get("cotacao_id")
        for forn, valor in (("Madeireira Alfa", 4200.5), ("Serraria Beta", 3890.0), ("Loja Gama", 5100)):
            post(f"/api/cotacoes/{cid}/itens", {"fornecedor": forn, "valor": valor})
    post("/api/voos", {"data": "2026-10-02", "hora": "09:30", "origem": "SSBL", "destino": "Florianopolis"})
    post("/api/voos", {"data": "2026-09-20", "destino": "Curitiba", "horas": 1.5,
                       "observacao": "Treino de pouso, vento cruzado moderado."})


def ligar_coletores(page, erros, falhas_rede):
    page.on("console", lambda m: erros.append(("console." + m.type, m.text)) if m.type == "error" else None)
    page.on("pageerror", lambda e: erros.append(("pageerror", str(e))))
    page.on("response", lambda resp: falhas_rede.append((resp.status, resp.url)) if resp.status >= 400 else None)
    page.on("requestfailed", lambda req: falhas_rede.append(("falhou", req.url)))


def abrir_aba(page, aba):
    page.click(f'.tab-btn[data-tab="{aba}"]')
    page.wait_for_selector(f"#tab-{aba}:not([hidden])")
    page.wait_for_timeout(500)
