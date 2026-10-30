"""Checagem barata do app iOS ANTES de gastar um build de Mac no GitHub Actions (2026-10-30).

Nao compila nada (nao tem Mac aqui): so confere coisas estruturais que ja quebraram ou quebrariam
o build de primeira - SWIFT_VERSION aceito pelo Xcode, um `@main` por alvo, App Group e chaves do
UserDefaults iguais nos arquivos, bundle id da extensao, API do iOS 18 protegida, workflow sem segredo.

Uso: .venv/Scripts/python.exe native/ios/checar_projeto.py   (sai com 1 se achar problema)
"""
import pathlib
import re
import sys

import yaml

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
problemas = []


def erro(msg):
    problemas.append(msg)


proj = yaml.safe_load((AQUI / "project.yml").read_text(encoding="utf-8"))
base = proj.get("settings", {}).get("base", {})

# 1. Valores oficiais do Xcode (5.9 tambem compilou no build de 23/10; a lista e so pra nao inventar versao)
if str(base.get("SWIFT_VERSION")) not in {"4.0", "4.2", "5.0", "6.0"}:
    erro(f"SWIFT_VERSION {base.get('SWIFT_VERSION')!r} fora dos valores oficiais (use 5.0 ou 6.0)")


def arquivos_do_alvo(alvo):
    swift = []
    for fonte in alvo.get("sources", []):
        fonte = fonte if isinstance(fonte, dict) else {"path": fonte}
        p = (AQUI / fonte["path"]).resolve()
        excl = set(fonte.get("excludes", []))
        if p.is_dir():
            swift += [f for f in p.rglob("*.swift") if f.name not in excl]
        elif p.suffix == ".swift":
            swift.append(p)
        if not p.exists():
            erro(f"fonte nao existe: {fonte['path']}")
    return swift


alvos = proj["targets"]
for nome, alvo in alvos.items():
    arquivos = arquivos_do_alvo(alvo)
    mains = [f.name for f in arquivos if re.search(r"^\s*@main\b", f.read_text(encoding="utf-8"), re.M)]
    if len(mains) != 1:
        erro(f"alvo {nome}: precisa de exatamente 1 @main, achei {mains}")
    # 2. API do iOS 18 (Central de Controle) so dentro de #if compiler(>=6.0) + @available(iOS 18)
    for f in arquivos:
        txt = f.read_text(encoding="utf-8")
        if re.search(r":\s*ControlWidget\b", txt):
            if "#if compiler(>=6.0)" not in txt or "@available(iOS 18" not in txt:
                erro(f"{f.name}: ControlWidget sem #if compiler(>=6.0)/@available(iOS 18.0, *)")
        if "containerBackground(" in txt and "17.0" not in txt:
            erro(f"{f.name}: containerBackground (iOS 17) sem #available")

# 3. App Group igual em todo lugar
grupos = set()
for alvo in alvos.values():
    grupos.update(alvo.get("entitlements", {}).get("properties", {}).get("com.apple.security.application-groups", []))
swift_todos = list((AQUI / "App").rglob("*.swift")) + list((AQUI.parent / "widgetkit").rglob("*.swift"))
for f in swift_todos:
    grupos.update(re.findall(r'"(group\.[\w.]+)"', f.read_text(encoding="utf-8")))
if len(grupos) != 1:
    erro(f"App Group diferente entre arquivos: {sorted(grupos)}")

# 4. Chaves do UserDefaults que o app grava e o widget le
app_txt = (AQUI / "App" / "PainelApp.swift").read_text(encoding="utf-8")
cfg_txt = (AQUI.parent / "widgetkit" / "Config.swift").read_text(encoding="utf-8")
for chave in ("painel_widget_url_base", "painel_widget_token"):
    if chave not in app_txt or chave not in cfg_txt:
        erro(f"chave {chave} nao bate entre PainelApp.swift e Config.swift")
intent_txt = (AQUI.parent / "widgetkit" / "PainelControleIntent.swift").read_text(encoding="utf-8")
if "painel_capturar_pedido" not in app_txt or "painel_capturar_pedido" not in intent_txt:
    erro("chave painel_capturar_pedido nao bate entre PainelApp.swift e PainelControleIntent.swift")

# 5. Bundle id da extensao comeca com o do app; o app embute a extensao
app_id = alvos["Painel"]["settings"]["base"]["PRODUCT_BUNDLE_IDENTIFIER"]
ext_id = alvos["PainelWidgetExtension"]["settings"]["base"]["PRODUCT_BUNDLE_IDENTIFIER"]
if not ext_id.startswith(app_id + "."):
    erro(f"bundle id da extensao ({ext_id}) precisa comecar com {app_id}.")
if not any(d.get("target") == "PainelWidgetExtension" and d.get("embed") for d in alvos["Painel"].get("dependencies", [])):
    erro("app nao embute PainelWidgetExtension")

# 6. Workflow: sem segredo, scheme e nomes de produto certos
wf = (RAIZ / ".github" / "workflows" / "build-ios.yml").read_text(encoding="utf-8")
if "secrets." in wf:
    erro("workflow usa secrets.* (devia ser sem segredo)")
for trecho in ("-scheme Painel", "Release-iphoneos/Painel.app", "PlugIns/PainelWidgetExtension.appex"):
    if trecho not in wf:
        erro(f"workflow nao tem {trecho!r} (nome de alvo/scheme mudou?)")

if problemas:
    print("PROBLEMAS:")
    for p in problemas:
        print(" -", p)
    sys.exit(1)
print("ok: nada estrutural errado (isso nao substitui o build de verdade)")
