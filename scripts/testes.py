"""Suite de testes inteira, rapida (2026-10-13): `.venv/Scripts/python.exe scripts/testes.py`.

Em serie levava ~28 min. Aqui roda em TRES filas ao mesmo tempo (pytest-xdist):

  - RAPIDA: todo arquivo que nao sobe servidor, em paralelo com `--dist loadfile` (cada
    arquivo inteiro num processo so - os arquivos isolam o banco na importacao e alguns
    dependem da ordem dos proprios testes);
  - GRANDES: arquivos enormes que recriam o banco a cada teste (hoje so test_app.py, ~530
    testes, sozinho segurava a fila rapida inteira) - aqui os testes dele sao espalhados um
    a um (`--dist load`) entre alguns processos;
  - NAVEGADOR: os arquivos que sobem servidor Flask numa thread (quase todos com Playwright),
    num processo so.

Por que o navegador fica separado: o servidor de um arquivo continua vivo depois que ele
termina e usa o `db.DB_PATH` global da hora - se o mesmo processo seguisse pra um arquivo
comum, o servidor velho segurava o banco novo (WinError 32); e os testes de tempo ("some em
X ms") davam falha falsa com varios navegadores disputando CPU. Misturado era ~50 falhas falsas.

Argumentos extras vao pros tres pytest (ex.: `-x`, `-k chat`). Sai com codigo != 0 se
qualquer fila falhar. As saidas completas ficam em data/testes/ (fora do git).
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "data" / "testes"
# so roda no Linux (gunicorn) - no Windows erra na coleta
SO_LINUX = {"test_vel_a2c_abas.py"}
# setUp apaga e recria o banco em todo teste -> da pra espalhar teste a teste
GRANDES = {"test_app.py"}
PROCESSOS_NAVEGADOR = 1  # testes de tempo ("some em X ms"): com 3 juntos davam falha falsa
PROCESSOS_GRANDES = 4
# cada processo carrega os modulos de teste (~300 MB): com 18 deu MemoryError na coleta com
# outro programa pesado aberto, e 14 ou 18 davam o mesmo tempo
PROCESSOS_RAPIDA_MAX = 10
_SOBE_SERVIDOR = re.compile(r"sync_playwright|\.run\(host=|make_server|serve_forever")


def _filas():
    todos = sorted((RAIZ / "tests").glob("test_*.py"))
    if sys.platform == "win32":
        todos = [t for t in todos if t.name not in SO_LINUX]
    navegador, grandes, rapida = [], [], []
    for t in todos:
        if _SOBE_SERVIDOR.search(t.read_text(encoding="utf-8")):
            navegador.append(t)
        elif t.name in GRANDES:
            grandes.append(t)
        else:
            rapida.append(t)
    nucleos = os.cpu_count() or 4
    livres = nucleos - PROCESSOS_NAVEGADOR * 2 - PROCESSOS_GRANDES  # navegador come ~2 nucleos
    return {
        "rapida": (rapida, max(2, min(PROCESSOS_RAPIDA_MAX, livres)), "loadfile"),
        "grandes": (grandes, PROCESSOS_GRANDES, "load"),
        "navegador": (navegador, PROCESSOS_NAVEGADOR, "loadfile"),
    }


def _comando(arquivos, processos, dist, extras):
    return [
        sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "no:logging",
        "-W", "ignore::DeprecationWarning", "--tb=short",
        "-n", str(processos), "--dist", dist,
        *extras, *[str(a.relative_to(RAIZ)) for a in arquivos],
    ]


def _resumo(caminho: Path) -> str:
    linhas = caminho.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    falhas = [l for l in linhas if l.startswith(("FAILED ", "ERROR "))]
    final = linhas[-1] if linhas else "(sem saida)"
    return "\n".join([*falhas, final])


def main() -> int:
    extras = sys.argv[1:]
    SAIDA.mkdir(parents=True, exist_ok=True)
    inicio = time.monotonic()
    rodando = {}
    for nome, (arquivos, processos, dist) in _filas().items():
        if not arquivos:
            continue
        arq_saida = SAIDA / f"{nome}.txt"
        print(f"[{nome}] {len(arquivos)} arquivos em {processos} processos -> {arq_saida.relative_to(RAIZ)}")
        rodando[nome] = (
            subprocess.Popen(_comando(arquivos, processos, dist, extras), cwd=RAIZ,
                             stdout=arq_saida.open("w", encoding="utf-8"), stderr=subprocess.STDOUT),
            arq_saida,
        )
    codigo = 0
    for nome, (proc, arq_saida) in rodando.items():
        proc.wait()
        print(f"\n[{nome}] {_resumo(arq_saida)}")
        codigo = codigo or proc.returncode
    print(f"\nTotal: {time.monotonic() - inicio:.0f} s")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
