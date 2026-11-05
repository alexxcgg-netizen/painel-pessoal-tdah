"""Gera o icone "Mostrador do dia" (escolhido pelo Alex em 05/11/2026) em SVG e PNG.

Um relogio com os tres passos do compromisso na borda (se arrumar, sair, chegar) e o ponteiro no agora.
Saidas: AppIcon do app iOS (claro, escuro e tingido do iOS 18+) e os icones do PWA (static/icons).
Uso: .venv/Scripts/python.exe scripts/icone_mostrador.py  (precisa do Playwright, ja usado nos testes)
"""
import math, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

RAIZ = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent

def raios(cor, op):
    s = []
    for i in range(12):
        a = math.radians(i * 30)
        x1, y1 = 50 + 34.5 * math.sin(a), 50 - 34.5 * math.cos(a)
        x2, y2 = 50 + 31.2 * math.sin(a), 50 - 31.2 * math.cos(a)
        s.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{cor}" stroke-opacity="{op}" stroke-width="1.7" stroke-linecap="round"/>')
    return "".join(s)

def svg(fundo, face1, face2, tinta, arcos, centro, borda):
    a1, a2, a3 = arcos
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
<defs><radialGradient id="f" cx=".42" cy=".36" r=".75"><stop offset="0" stop-color="{face1}"/><stop offset="1" stop-color="{face2}"/></radialGradient></defs>
<rect width="100" height="100" fill="{fundo}"/>
<circle cx="50" cy="50" r="38" fill="url(#f)"/>
<circle cx="50" cy="50" r="37.75" fill="none" stroke="{borda}" stroke-width=".5"/>
{raios(tinta, .34)}
<g fill="none" stroke-width="4.2" stroke-linecap="round" transform="rotate(-90 50 50)">
<circle cx="50" cy="50" r="25" stroke="{a1}" pathLength="360" stroke-dasharray="40 320" stroke-dashoffset="-2"/>
<circle cx="50" cy="50" r="25" stroke="{a2}" pathLength="360" stroke-dasharray="36 324" stroke-dashoffset="-52"/>
<circle cx="50" cy="50" r="25" stroke="{a3}" pathLength="360" stroke-dasharray="26 334" stroke-dashoffset="-98"/>
</g>
<line x1="50" y1="50" x2="64.3" y2="36.3" stroke="{tinta}" stroke-width="3.6" stroke-linecap="round"/>
<line x1="50" y1="50" x2="45" y2="54.8" stroke="{tinta}" stroke-width="3.6" stroke-linecap="round"/>
<circle cx="50" cy="50" r="4.3" fill="{centro}"/><circle cx="50" cy="50" r="1.6" fill="{face2}"/>
</svg>'''

VARIANTES = {
    "escuro": svg("#000000", "#26262a", "#161618", "#ffffff", ("#ff9f0a", "#ff375f", "#30d158"), "#ff9f0a", "#ffffff22"),
    "claro": svg("#f2f2f7", "#ffffff", "#f4f4f7", "#1c1c1e", ("#ff9500", "#ff2d55", "#34c759"), "#ff9500", "#00000014"),
    "tingido": svg("#000000", "#2c2c2c", "#1e1e1e", "#ffffff", ("#ffffff", "#b8b8b8", "#7a7a7a"), "#ffffff", "#ffffff1a"),
}

def render(pg, codigo, tam, saida):
    pg.set_viewport_size({"width": tam, "height": tam})
    pg.set_content(f'<html><body style="margin:0;background:#000">{codigo.replace("<svg ", f"<svg width=\"{tam}\" height=\"{tam}\" ", 1)}</body></html>')
    pg.locator("svg").screenshot(path=str(saida))

ios = RAIZ / "native/ios/App/Assets.xcassets/AppIcon.appiconset"
web = RAIZ / "static/icons"
(web / "icon.svg").write_text(VARIANTES["escuro"], encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(device_scale_factor=1)
    render(pg, VARIANTES["claro"], 1024, ios / "icon-1024.png")
    render(pg, VARIANTES["escuro"], 1024, ios / "icon-1024-escuro.png")
    render(pg, VARIANTES["tingido"], 1024, ios / "icon-1024-tingido.png")
    for t in (180, 192, 512):
        render(pg, VARIANTES["escuro"], t, web / f"icon-{t}.png")
    b.close()
print("ok")
