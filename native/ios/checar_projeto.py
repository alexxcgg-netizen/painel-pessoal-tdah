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

# 2b. Atividade ao vivo (04/11): os atributos (ActivityAttributes) que o app liga tem que estar nos DOIS alvos,
#     e intervalo de timer a partir de "agora" nao pode ser cru (alvo ja passado = fim antes do comeco, derruba):
#     usar ContentState.intervalo(de:ate:)
arquivos_app = {f.name for f in arquivos_do_alvo(alvos["Painel"])}
arquivos_widget = {f.name for f in arquivos_do_alvo(alvos["PainelWidgetExtension"])}
for f in (AQUI.parent / "widgetkit").glob("*.swift"):
    txt = f.read_text(encoding="utf-8")
    if re.search(r":\s*ActivityAttributes\b", txt) and not (f.name in arquivos_app and f.name in arquivos_widget):
        erro(f"{f.name}: ActivityAttributes precisa entrar nos dois alvos (sources do Painel no project.yml)")
for f in list((AQUI / "App").rglob("*.swift")) + list((AQUI.parent / "widgetkit").rglob("*.swift")):
    txt = f.read_text(encoding="utf-8")
    for m in re.finditer(r"timerInterval:\s*([^,)]*)", txt):
        trecho = m.group(1)
        if "..." in trecho and re.search(r"Date\(\)|\bagora\b|\.now\b", trecho):
            erro(f"{f.name}: timerInterval com intervalo cru ({trecho.strip()!r}); use ContentState.intervalo(de:ate:)")

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

# 5b. Avisos no app (06/11): tarefa de segundo plano registrada no codigo tem que estar liberada no Info.plist
#     (senao o BGTaskScheduler.register derruba o app no launch), e o GPS em segundo plano precisa do modo
#     "location" (senao allowsBackgroundLocationUpdates = true derruba o app)
plist_app = alvos["Painel"].get("info", {}).get("properties", {})
modos = set(plist_app.get("UIBackgroundModes", []))
permitidas = set(plist_app.get("BGTaskSchedulerPermittedIdentifiers", []))
for f in (AQUI / "App").rglob("*.swift"):
    txt = f.read_text(encoding="utf-8")
    if "BGTaskScheduler.shared.register" in txt:
        for ident in re.findall(r'static let tarefaFundo = "([^"]+)"', txt):
            if ident not in permitidas:
                erro(f"{f.name}: tarefa de fundo {ident!r} fora do BGTaskSchedulerPermittedIdentifiers")
        if "fetch" not in modos:
            erro(f"{f.name}: BGAppRefreshTask sem 'fetch' no UIBackgroundModes")
    if "allowsBackgroundLocationUpdates = true" in txt and "location" not in modos:
        erro(f"{f.name}: GPS em segundo plano sem 'location' no UIBackgroundModes")

# 5c. Ao vivo de tarefa (06/11): o LiveActivityIntent roda no processo do app, entao o arquivo do intent entra
#     nos dois alvos; arquivo compartilhado que usa `#if PAINEL_APP` precisa da flag no alvo do app (senao o app
#     compila o ramo do widget e quebra em PainelDados, que nao existe la)
app_swift = {f.name for f in arquivos_do_alvo(alvos["Painel"])}
ext_swift = {f.name for f in arquivos_do_alvo(alvos["PainelWidgetExtension"])}
for f in (AQUI.parent / "widgetkit").glob("*.swift"):
    txt = f.read_text(encoding="utf-8")
    if "LiveActivityIntent" in txt and not ({f.name} <= app_swift and {f.name} <= ext_swift):
        erro(f"{f.name}: LiveActivityIntent precisa estar nos dois alvos (app e widget)")
    if "#if PAINEL_APP" in txt and f.name in app_swift:
        flag = str(alvos["Painel"].get("settings", {}).get("base", {}).get("SWIFT_ACTIVE_COMPILATION_CONDITIONS", ""))
        if "PAINEL_APP" not in flag.split() or "$(inherited)" not in flag:
            erro(f"{f.name} usa #if PAINEL_APP: falta SWIFT_ACTIVE_COMPILATION_CONDITIONS \"$(inherited) PAINEL_APP\" no app")
    if "#if PAINEL_APP" in txt and "PAINEL_APP" in str(alvos["PainelWidgetExtension"].get("settings", {})):
        erro(f"{f.name}: a extensao do widget nao pode ter PAINEL_APP")

# 5d. Recado da pagina (06/11: Feito/Desfazer dentro do app e a ilha nao saia): o nome do canal tem que ser o
#     mesmo nos dois lados (PainelApp.swift registra, static/js/nucleo/api.js manda)
painel_app = (AQUI / "App" / "PainelApp.swift").read_text(encoding="utf-8")
api_js = (RAIZ / "static" / "js" / "nucleo" / "api.js").read_text(encoding="utf-8")
if 'add(AvisoDaPagina(), name: "painel")' not in painel_app:
    erro("PainelApp.swift: canal 'painel' da pagina nao registrado (AvisoDaPagina)")
if "messageHandlers.painel" not in api_js:
    erro("static/js/nucleo/api.js nao avisa o app (messageHandlers.painel)")

# 5e. GPS mais esperto (06/11, painel esperto frente 3): sensor de movimento sem NSMotionUsageDescription derruba o
#     app na primeira leitura; cerca/visita pedem o texto do "Sempre"; o desenho da viagem tem que estar no widget e
#     ligado no AtividadeCompromisso; caminhos e chaves do JSON iguais dos dois lados (app x painel)
app_txt_todo = "\n".join(f.read_text(encoding="utf-8") for f in (AQUI / "App").rglob("*.swift"))
if "CMMotionActivityManager" in app_txt_todo and not str(plist_app.get("NSMotionUsageDescription") or "").strip():
    erro("app usa CMMotionActivityManager sem NSMotionUsageDescription no Info.plist (project.yml)")
if ("CLCircularRegion" in app_txt_todo or "startMonitoringVisits" in app_txt_todo) \
        and not str(plist_app.get("NSLocationAlwaysAndWhenInUseUsageDescription") or "").strip():
    erro("cerca/visita sem NSLocationAlwaysAndWhenInUseUsageDescription no Info.plist")
if "AtividadeViagem.swift" not in ext_swift:
    erro("AtividadeViagem.swift fora do alvo do widget")
ativ_txt = (AQUI.parent / "widgetkit" / "AtividadeCompromisso.swift").read_text(encoding="utf-8")
for trecho in ("e.ehViagem", "TelaViagem(", "AnelViagem("):
    if trecho not in ativ_txt:
        erro(f"AtividadeCompromisso.swift nao liga a viagem ({trecho!r})")
attr_txt = (AQUI.parent / "widgetkit" / "CompromissoAtributos.swift").read_text(encoding="utf-8")
if "struct Viagem" not in attr_txt:
    erro("CompromissoAtributos.swift sem a struct Viagem (ContentState.viagem tem que estar nos dois alvos)")
rota_gps = RAIZ / "rotas" / "localizacao_viagem.py"
loc_txt = (AQUI / "App" / "Localizacao.swift").read_text(encoding="utf-8")
if rota_gps.exists():
    rota_txt = rota_gps.read_text(encoding="utf-8")
    for caminho in ("api/localizacao/cercas", "api/localizacao/posicao"):
        if f'"{caminho}"' not in loc_txt or f"/{caminho}" not in rota_txt:
            erro(f"caminho {caminho} nao bate entre Localizacao.swift e rotas/localizacao_viagem.py")
    viagem_py = (RAIZ / "viagem_acompanhada.py").read_text(encoding="utf-8")
    bloco = re.search(r"struct Viagem: Codable.*?enum CodingKeys.*?\n\s*\}", attr_txt, re.S)
    for chave in re.findall(r'= "(\w+)"', bloco.group(0) if bloco else ""):
        if f'"{chave}"' not in viagem_py:
            erro(f"chave {chave!r} da Viagem (CompromissoAtributos.swift) nao sai de viagem_acompanhada.py")
else:
    erro("rotas/localizacao_viagem.py nao existe (cercas/posicao)")

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
