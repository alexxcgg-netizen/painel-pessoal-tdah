"""So os testes ligados ao que mudou (2026-10-30): `.venv/Scripts/python.exe scripts/testes_afetados.py`.

Olha o que mudou desde o ultimo commit e escolhe os testes pelo texto deles, sem dependencia nova:

  - teste alterado: ele mesmo;
  - modulo Python comum: os testes que citam o modulo, e os que citam quem importa ele; em rotas/,
    tambem os que citam as URLs dele;
  - modulo central (citado por mais de 1/4 dos testes, como app.py e db.py): citar o modulo nao
    separa nada, entao vale o que mudou la dentro - nome da funcao e rota dela;
  - migracao SQL: os testes que citam as tabelas do arquivo;
  - JS, CSS, HTML e o resto: os testes que citam o arquivo; JS roda tambem `node --test tests/js`;
  - conftest ou infra de teste: suite inteira.

E um filtro por texto, pra resposta em segundos enquanto se trabalha: pode deixar passar uma quebra
indireta. Antes de commit quem manda continua sendo `scripts/testes.py`.

`--ver` so lista o que rodaria. Argumentos extras vao pro pytest.
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
import testes  # noqa: E402

PROCESSOS = 6
_SO_DOCUMENTO = (".md", ".txt", ".log", ".bat")
_INFRA = {"scripts/testes.py", "requirements.txt"}
_TABELA = re.compile(r"\b(?:CREATE TABLE(?: IF NOT EXISTS)?|ALTER TABLE|INSERT INTO|UPDATE)\s+[\"']?(\w+)", re.I)
_ROTA = re.compile(r"[\"'](/[\w/<>:.-]*)[\"']")


def arquivos_mudados() -> list[str]:
    saida = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=RAIZ, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", check=True).stdout
    return [linha[3:].split(" -> ")[-1].strip().strip('"') for linha in saida.splitlines()]


def linhas_mudadas(arquivo: str) -> set[int] | None:
    """Linhas novas/alteradas do arquivo; None se ele nem existe no ultimo commit."""
    r = subprocess.run(["git", "diff", "-U0", "HEAD", "--", arquivo], cwd=RAIZ, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if not r.stdout:
        return None
    linhas = set()
    for inicio, qtd in re.findall(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", r.stdout, re.M):
        qtd = int(qtd) if qtd else 1
        linhas.update(range(int(inicio), int(inicio) + max(qtd, 1)))
    return linhas


def simbolos_mudados(fonte: str, linhas: set[int]) -> set[str]:
    """Nome das funcoes/classes/constantes tocadas e as rotas citadas dentro delas."""
    achados = set()

    def visitar(no):
        if linhas.isdisjoint(range(no.lineno, (no.end_lineno or no.lineno) + 1)):
            return
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            inicio = min([d.lineno for d in no.decorator_list] + [no.lineno])
            achados.add(no.name)
            achados.update(r for r in _ROTA.findall("\n".join(fonte.splitlines()[inicio - 1:no.end_lineno])) if len(r) > 1)
            if isinstance(no, ast.ClassDef):
                for filho in no.body:
                    if hasattr(filho, "lineno"):
                        visitar(filho)
        elif isinstance(no, (ast.Assign, ast.AnnAssign)):
            alvos = no.targets if isinstance(no, ast.Assign) else [no.target]
            achados.update(a.id for a in alvos if isinstance(a, ast.Name))

    for no in ast.parse(fonte).body:
        if hasattr(no, "lineno"):
            visitar(no)
    return achados


def eh_infra(arquivo: str) -> bool:
    """Lista fixa + todo .py de tests/ que nao e teste (conftest, ajudantes)."""
    caminho = Path(arquivo)
    return arquivo in _INFRA or (arquivo.startswith("tests/") and caminho.suffix == ".py" and not caminho.name.startswith("test_"))


def cita(texto: str, palavra: str) -> bool:
    return re.search(rf"(?<![\w/]){re.escape(palavra)}(?![\w])", texto) is not None


def escolher(mudados, textos, modulos, ler=None, linhas=linhas_mudadas):
    """-> (testes escolhidos, roda_js, suite_inteira). `textos`: {teste: conteudo}; `modulos`: {nome: conteudo}."""
    ler = ler or (lambda a: (RAIZ / a).read_text(encoding="utf-8", errors="replace"))
    escolhidos, js, inteira = set(), False, False
    limite_central = len(textos) / 4
    citantes = lambda palavra: {t for t, texto in textos.items() if cita(texto, palavra)}  # noqa: E731

    for arquivo in mudados:
        caminho = Path(arquivo)
        if eh_infra(arquivo):
            inteira = True
        elif arquivo.startswith("tests/js/"):
            js = True
        elif caminho.name.startswith("test_") and caminho.suffix == ".py":
            if (RAIZ / arquivo).exists():
                escolhidos.add(arquivo)
        elif arquivo.startswith(("tests/", "docs/", "native/")) or caminho.suffix in _SO_DOCUMENTO:
            if arquivo == "CHANGELOG.md":
                escolhidos.update(citantes("CHANGELOG.md"))
        elif caminho.suffix == ".py":
            if not (RAIZ / arquivo).exists():
                inteira = True
                continue
            nome = caminho.stem
            diretos = citantes(nome)
            if len(diretos) > limite_central:
                fonte = ler(arquivo)
                toque = linhas(arquivo)
                nomes = simbolos_mudados(fonte, toque) if toque else {nome}
                if not nomes:  # import ou `if` de topo num modulo central: nao da pra saber quem pega
                    inteira = True
                for simbolo in nomes:
                    escolhidos.update(citantes(simbolo))
            else:
                escolhidos.update(diretos)
                if arquivo.startswith("rotas/"):  # teste de rota cita a URL, nao o nome do arquivo
                    for rota in _ROTA.findall(ler(arquivo)):
                        prefixo = rota.split("<")[0].rstrip("/")
                        if len(prefixo) > 1:
                            escolhidos.update(citantes(prefixo))
                for outro, texto in modulos.items():
                    if outro != nome and cita(texto, nome) and len(citantes(outro)) <= limite_central:
                        escolhidos.update(citantes(outro))
        elif caminho.suffix == ".sql":
            for tabela in set(_TABELA.findall(ler(arquivo))) if (RAIZ / arquivo).exists() else ():
                escolhidos.update(citantes(tabela))
        else:  # o resto vale pelo nome do arquivo, inclusive citado com a pasta (`templates/index.html`)
            js = js or caminho.suffix == ".js"
            escolhidos.update(t for t, texto in textos.items() if caminho.name in texto)
    return escolhidos, js, inteira


def main() -> int:
    extras = [a for a in sys.argv[1:] if a != "--ver"]
    so_ver = "--ver" in sys.argv
    mudados = arquivos_mudados()
    textos = {f"tests/{t.name}": t.read_text(encoding="utf-8", errors="replace") for t in (RAIZ / "tests").glob("test_*.py")}
    modulos = {p.stem: p.read_text(encoding="utf-8", errors="replace")
               for pasta in (RAIZ, RAIZ / "rotas", RAIZ / "assistente", RAIZ / "ia") for p in pasta.glob("*.py")}
    escolhidos, js, inteira = escolher(mudados, textos, modulos)
    if inteira:
        print("mudou a infra de teste, o topo de um modulo central ou apagou um modulo: use a suite inteira (scripts/testes.py)")
        return 2
    filas = testes._filas()
    navegador = {f"tests/{a.name}" for a in filas["navegador"][0]}
    grandes = {f"tests/{a.name}" for a in filas["grandes"][0]}
    if sys.platform == "win32":
        escolhidos -= {f"tests/{nome}" for nome in testes.SO_LINUX}
    comuns = sorted(escolhidos - navegador)
    no_navegador = sorted(escolhidos & navegador)
    print(f"{len(mudados)} arquivos mudados -> {len(comuns)} arquivos de teste + {len(no_navegador)} de navegador"
          + (" + testes JS" if js else ""))
    for t in comuns + no_navegador:
        print(f"  {t}")
    if not (comuns or no_navegador or js):
        print("nada ligado ao que mudou: isso nao quer dizer que esta certo. Antes de commit, scripts/testes.py")
    if so_ver or not (comuns or no_navegador or js):
        return 0
    codigo = 0
    base = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "no:logging",
            "-W", "ignore::DeprecationWarning", "--tb=short", *extras]
    simples = [t for t in comuns if t not in grandes]
    if simples:
        codigo |= subprocess.run([*base, "-n", str(min(PROCESSOS, len(simples))), "--dist", "loadfile", *simples], cwd=RAIZ).returncode
    if set(comuns) & grandes:
        codigo |= subprocess.run([*base, "-n", "4", "--dist", "load", *sorted(set(comuns) & grandes)], cwd=RAIZ).returncode
    if no_navegador:
        cod_nav, _, linhas = testes.fechar_navegador(testes.rodar_navegador([RAIZ / t for t in no_navegador], extras), extras)
        print("\n".join(f"navegador: {l}" for l in linhas))
        codigo |= cod_nav
    if js:
        codigo |= subprocess.run(testes.comando_js(), cwd=RAIZ).returncode
    return codigo


if __name__ == "__main__":
    sys.exit(main())
