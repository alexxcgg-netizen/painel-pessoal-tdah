import json, re, pathlib, sys
base = pathlib.Path(__file__).parent
dados = json.loads((base.parent / "dados_lab.json").read_text())
casca = (base / "casca.html").read_text()
scripts, fontes = [], []
nums = [int(a) for a in sys.argv[1:]] or list(range(1, 7))
for n in nums:
    p = base / f"v{n:02d}.js"
    if not p.exists():
        print("faltando", p.name); continue
    js = p.read_text()
    m = re.search(r"fontes\s*:\s*\[(.*?)\]", js, re.S)
    if m:
        fontes += re.findall(r"[\"']([^\"']+)[\"']", m.group(1))
    scripts.append(f"<script>\n{js}\n</script>")
fam = "&".join("family=" + f for f in dict.fromkeys(fontes))
out = (casca.replace("__FONTES__&", (fam + "&") if fam else "")
            .replace("__DADOS__", json.dumps(dados, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__DIRECOES__", "\n".join(scripts)))
nome = "conversa-vida.html" if not sys.argv[1:] else "previa-" + "-".join(sys.argv[1:]) + ".html"
(base / nome).write_text(out)
print("ok", len(out), "bytes,", len(scripts), "direcoes")
