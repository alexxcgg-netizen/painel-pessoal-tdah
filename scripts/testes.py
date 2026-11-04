"""Suite de testes inteira, rapida: `.venv/Scripts/python.exe scripts/testes.py`.

Em serie levava ~28 min. Aqui roda em QUATRO filas ao mesmo tempo:

  - RAPIDA: todo arquivo que nao sobe servidor, em paralelo com `--dist loadfile` (cada
    arquivo inteiro num processo so - os arquivos isolam o banco na importacao e alguns
    dependem da ordem dos proprios testes);
  - GRANDES: arquivos enormes que recriam o banco a cada teste (hoje so test_app.py, ~530
    testes, sozinho segurava a fila rapida inteira) - aqui os testes dele sao espalhados um
    a um (`--dist load`) entre alguns processos;
  - NAVEGADOR: os arquivos que sobem servidor Flask numa thread (quase todos com Playwright),
    um pytest proprio por arquivo, varios ao mesmo tempo;
  - JS: `node --test tests/js`.

Por que o navegador nao usa xdist: cada processo do xdist importa TODOS os arquivos, e cada
arquivo sobe o proprio servidor na importacao, numa porta fixa. O primeiro processo ficava com
todas as portas e os testes dos outros falavam com o servidor dele (outro banco, sem os patches).
Com um pytest por arquivo cada servidor so tem o seu teste, e o servidor que sobra quando um
arquivo termina morre junto com o processo.

Teste do navegador que falha roda de novo sozinho no fim, um arquivo por vez e com as outras
filas ja paradas: os testes de tempo ("some em X ms") podem dar falha falsa com o PC cheio. Quem
so passou sozinho aparece no relatorio. O refazer nao perdoa o que ele nao alcanca: arquivo que
morreu, estourou o limite ou pulou porque o servidor nao subiu continua sendo falha.

Cada arquivo do navegador recebe porta propria (`PORTA_TESTE_*`). Duas suites ao mesmo tempo nao:
os relatorios de data/testes/ tem nome fixo e uma atropela a outra (o codigo de saida segue certo).

Roda numa COPIA do codigo em pasta temporaria (2026-10-30): da pra seguir mexendo no projeto
com a suite andando, e ela confere exatamente o que estava salvo na hora que comecou. `--aqui`
roda na pasta do projeto, como antes.

Argumentos extras vao pros pytest (ex.: `-x`, `-k chat`) e deixam o JS de fora. Sai com codigo
!= 0 se qualquer fila falhar. As saidas completas ficam em data/testes/ (fora do git).
"""

import itertools
import json
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "data" / "testes"
TEMPOS_NAVEGADOR = SAIDA / "tempos_navegador.json"
FORA_DA_COPIA = ("amostras_voz/",)
# so roda no Linux (gunicorn) - no Windows erra na coleta
SO_LINUX = {"test_vel_a2c_abas.py"}
# setUp apaga e recria o banco em todo teste -> da pra espalhar teste a teste
GRANDES = {"test_app.py"}
PROCESSOS_NAVEGADOR = 5  # o maior arquivo leva ~40 s: com mais de 5 juntos o tempo nao cai
LIMITE_ARQUIVO_S = 300  # arquivo do navegador preso nao pode segurar a fila pra sempre
LIMITE_FILA_S = 600  # idem pras outras filas, contado do inicio da suite: elas levam ~1 min
ESTOUROU = 124
PROCESSOS_GRANDES = 4
# cada processo carrega os modulos de teste (~300 MB): com 18 deu MemoryError na coleta com
# outro programa pesado aberto, e 14 ou 18 davam o mesmo tempo
PROCESSOS_RAPIDA_MAX = 10
_SOBE_SERVIDOR = re.compile(r"sync_playwright|subir_servidor|\.run\(host=|make_server|serve_forever")
_CONTAGEM = re.compile(r"(\d+) (passed|failed|skipped|errors?)")
# 'SUBFAILED(tela=1, largura=390) tests/x.py::C::t - motivo': o rotulo do subteste pode ter espaco
_FALHA = re.compile(r"^(?:FAILED|ERROR|SUBFAILED)\b.*?(\S+\.py(?:::\S+)?)")
_PORTA = re.compile(r"PORTA_TESTE_\w+")
# fora da faixa dinamica do sistema (49152+ no Windows): porta de bind(0) sai de la, e no tempo entre
# fechar e o servidor subir uma conexao de saida pode pegar o numero. Base sorteada: `testes_afetados` ao mesmo
# tempo que a suite dificilmente cai nos mesmos numeros
_PROXIMA_PORTA = itertools.count(random.randrange(20000, 29000))
# skip destes motivos nao e "nao se aplica aqui": o arquivo inteiro deixou de conferir
_SKIP_E_FALHA = ("servidor de teste nao respondeu", "playwright nao instalado")
# o filho escreve em cp1252 se a saida nao for um console, e acento vira lixo na leitura
AMBIENTE = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def copiar_codigo() -> Path:
    """Tudo que o git enxerga (versionado + novo nao ignorado): sem .env, sem data/, sem .venv."""
    destino = Path(tempfile.mkdtemp(prefix="painel_testes_"))
    try:
        lista = subprocess.run(["git", "ls-files", "-z", "-co", "--exclude-standard"], cwd=RAIZ,
                               capture_output=True, check=True).stdout.decode("utf-8").split("\0")
        for nome in lista:
            origem = RAIZ / nome
            if nome and not nome.startswith(FORA_DA_COPIA) and origem.is_file():
                alvo = destino / nome
                alvo.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(origem, alvo)
    except BaseException:
        shutil.rmtree(destino, ignore_errors=True)
        raise
    return destino


def _filas(base=RAIZ):
    todos = sorted((base / "tests").glob("test_*.py"))
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
    livres = nucleos - PROCESSOS_NAVEGADOR - PROCESSOS_GRANDES
    return {
        "rapida": (rapida, max(2, min(PROCESSOS_RAPIDA_MAX, livres)), "loadfile"),
        "grandes": (grandes, PROCESSOS_GRANDES, "load"),
        "navegador": (navegador, PROCESSOS_NAVEGADOR, None),
    }


def _pytest(extras, *alvos):
    return [
        sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "no:logging",
        "-W", "ignore::DeprecationWarning", "--tb=short", *extras, *alvos,
    ]


def _comando(arquivos, processos, dist, extras, base=RAIZ):
    return _pytest(["-n", str(processos), "--dist", dist, *extras], *[str(a.relative_to(base)) for a in arquivos])


def comando_js(base=RAIZ):
    return ["node", "--test", *sorted(str(p.relative_to(base)) for p in (base / "tests" / "js").glob("*.test.js"))]


def _matar(processo):
    if sys.platform == "win32":  # o python da venv e um lancador: o pytest de verdade e filho dele
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(processo.pid)], capture_output=True)
    else:
        processo.kill()


def _rodar(comando, base, ambiente=AMBIENTE):
    processo = subprocess.Popen(comando, cwd=base, env=ambiente, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                encoding="utf-8", errors="replace")
    try:
        saida, _ = processo.communicate(timeout=LIMITE_ARQUIVO_S)
    except subprocess.TimeoutExpired:
        _matar(processo)
        saida, _ = processo.communicate()
        return ESTOUROU, f"{saida}\nestourou o limite de {LIMITE_ARQUIVO_S} s"
    return processo.returncode, saida


def _porta_livre() -> int:
    while True:
        porta = next(_PROXIMA_PORTA)
        with socket.socket() as s:
            exclusivo = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
            if exclusivo is not None:
                s.setsockopt(socket.SOL_SOCKET, exclusivo, 1)
            try:
                s.bind(("127.0.0.1", porta))
            except OSError:  # em uso ou reservada pelo Windows
                continue
        return porta


def _portas_livres(arquivo: Path) -> dict:
    """Ambiente do arquivo com as `PORTA_TESTE_*` dele em portas livres, uma pra cada."""
    ambiente = dict(AMBIENTE)
    for nome in set(_PORTA.findall(arquivo.read_text(encoding="utf-8"))) if arquivo.exists() else ():
        ambiente[nome] = str(_porta_livre())
    return ambiente


def _falhas(saida: str) -> list[str]:
    return [l for l in saida.splitlines() if _FALHA.match(l)]


def _alvo(falha: str) -> str:
    """'FAILED tests/x.py::C::t - motivo' -> 'tests/x.py::C::t'."""
    return _FALHA.match(falha).group(1)


def _aceito(codigo, extras) -> bool:
    return codigo == 0 or (codigo == 5 and bool(extras))  # 5: o filtro nao achou teste aqui


def _ler_tempos() -> dict:
    try:
        return json.loads(TEMPOS_NAVEGADOR.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def rodar_navegador(arquivos, extras, base=RAIZ):
    """Um pytest por arquivo, o mais demorado primeiro. -> [(nome, codigo, saida, segundos)]."""
    tempos = _ler_tempos()
    fila = sorted(arquivos, key=lambda a: (-tempos.get(a.name, 0), -a.stat().st_size))

    def um(arquivo):
        inicio = time.monotonic()
        # -r troca o padrao (fE) em vez de somar: sem fE somem as linhas FAILED que o refazer le
        comando = _pytest(["-rfEs", *extras], str(arquivo.relative_to(base)))
        codigo, saida = _rodar(comando, base, _portas_livres(arquivo))
        return arquivo.name, codigo, saida, time.monotonic() - inicio

    with ThreadPoolExecutor(PROCESSOS_NAVEGADOR) as pool:
        return list(pool.map(um, fila))


def _juntar(resultados) -> str:
    return "\n".join(f"===== {nome} ({seg:.0f} s)\n{texto}" for nome, _, texto, seg in resultados)


def _perdidos(resultados, extras) -> list[str]:
    """O que o refazer nao alcanca: arquivo que nao terminou direito ou nem chegou a conferir."""
    perdidos = []
    for nome, codigo, texto, _ in resultados:
        motivo = next((m for m in _SKIP_E_FALHA if m in texto), None)
        if motivo:
            perdidos.append(f"{nome}: {motivo}")
        elif not _aceito(codigo, extras) and not (codigo == 1 and _falhas(texto)):
            perdidos.append(f"{nome}: saiu com codigo {codigo}" + (" sem nenhum teste" if codigo == 5 else ""))
    return perdidos


def refazer_sozinho(saida: str, extras, base=RAIZ):
    """Roda de novo o que falhou, um arquivo por vez. -> (codigo, saida, quem so passou sozinho)."""
    por_arquivo: dict[str, list[str]] = {}
    for falha in _falhas(saida):
        alvo = _alvo(falha)
        alvos = por_arquivo.setdefault(alvo.split("::")[0], [])
        if alvo not in alvos:
            alvos.append(alvo)
    codigo_final, textos, sozinho = 0, [], []
    for arquivo, alvos in por_arquivo.items():
        codigo, texto = _rodar(_pytest(extras, *alvos), base, _portas_livres(base / arquivo))
        textos.append(texto)
        ultima = texto.strip().splitlines()[-1] if texto.strip() else ""
        pulou = "skipped" in ultima  # pular nao e passar
        if codigo in (0, 1) and not pulou:
            ainda = {_alvo(f) for f in _falhas(texto)}
            sozinho += [a for a in alvos if a not in ainda]
        codigo_final = codigo_final or codigo or int(pulou)
    return codigo_final, "\n".join(textos), sozinho


def fechar_navegador(resultados, extras, base=RAIZ):
    """Refaz o que falhou e fecha a conta. -> (codigo, saida completa, linhas do relatorio)."""
    saida = _juntar(resultados)
    perdidos = _perdidos(resultados, extras)
    if any(e in ("-x", "--exitfirst") or e.startswith("--maxfail") for e in extras):
        # o que vinha depois da falha nao rodou: passar ao refazer nao diria nada
        restantes, sozinho, refeito = _falhas(saida), [], ""
        cod_refeito = 1 if restantes else 0
    else:
        cod_refeito, refeito, sozinho = refazer_sozinho(saida, extras, base)
        restantes = _falhas(refeito)
    linhas = [f"so passou sozinho: {alvo}" for alvo in sozinho]
    linhas += restantes + [f"FALHOU: {p}" for p in perdidos]
    if cod_refeito not in (0, 1):
        linhas.append(f"FALHOU: o refazer saiu com codigo {cod_refeito}")
    linhas.append(_contagem(saida, 0 if cod_refeito else len(sozinho)))
    return cod_refeito or (1 if perdidos else 0), f"{saida}\n===== refeitos sozinhos\n{refeito}", linhas


def _contagem(saida: str, refeitos: int = 0) -> str:
    """Soma as linhas finais dos pytest ('3 passed, 1 skipped in 2.1s'). `refeitos`: a fila ficou
    verde refazendo esses, entao os erros da primeira passada nao contam."""
    somas: dict[str, int] = {}
    for bloco in saida.split("===== ")[1:]:
        for qtd, tipo in _CONTAGEM.findall(bloco.strip().splitlines()[-1]):
            somas[tipo] = somas.get(tipo, 0) + int(qtd)
    if refeitos:
        somas = {tipo: qtd for tipo, qtd in somas.items() if tipo in ("passed", "skipped")}
        somas["so sozinho"] = refeitos
    return ", ".join(f"{qtd} {tipo}" for tipo, qtd in somas.items()) or "(sem saida)"


def _resumo(caminho: Path) -> str:
    texto = caminho.read_text(encoding="utf-8", errors="replace").strip()
    contagem = re.findall(r"^\S+ (pass|fail) (\d+)$", texto, re.M)  # final do node --test
    if contagem:
        return ", ".join(f"{qtd} {tipo}" for tipo, qtd in contagem)
    linhas = texto.splitlines()
    return "\n".join([*_falhas(texto), linhas[-1] if linhas else "(sem saida)"])


def _disparar(nome, comando, base):
    arq_saida = SAIDA / f"{nome}.txt"
    processo = subprocess.Popen(comando, cwd=base, env=AMBIENTE, stdout=arq_saida.open("w", encoding="utf-8"),
                                stderr=subprocess.STDOUT)
    return processo, arq_saida


def _esperar_fila(proc, ate: float) -> int:
    """Codigo da fila. Teste preso nao trava a suite: passou de `ate`, mata e devolve ESTOUROU."""
    try:
        return proc.wait(timeout=max(0, ate - time.monotonic()))
    except subprocess.TimeoutExpired:
        _matar(proc)
        proc.wait()
        return ESTOUROU


def main() -> int:
    sys.stdout.reconfigure(errors="replace")  # acento de teste que falhou nao derruba o relatorio
    extras = [a for a in sys.argv[1:] if a != "--aqui"]
    SAIDA.mkdir(parents=True, exist_ok=True)
    inicio = time.monotonic()
    base = RAIZ if "--aqui" in sys.argv else copiar_codigo()
    rodando = {}
    codigo = 0
    try:
        filas = _filas(base)
        for nome in ("rapida", "grandes"):
            arquivos, processos, dist = filas[nome]
            if arquivos:
                print(f"[{nome}] {len(arquivos)} arquivos em {processos} processos")
                rodando[nome] = _disparar(nome, _comando(arquivos, processos, dist, extras, base), base)
        if not extras:
            if shutil.which("node"):
                rodando["js"] = _disparar("js", comando_js(base), base)
            else:
                print("[js] NAO RODOU: node nao esta no PATH")
                codigo = 1
        arquivos, processos, _ = filas["navegador"]
        print(f"[navegador] {len(arquivos)} arquivos, {processos} de cada vez")
        resultados = rodar_navegador(arquivos, extras, base)
        fim_nav = time.monotonic() - inicio

        for nome, (proc, caminho) in rodando.items():
            cod_fila = _esperar_fila(proc, inicio + LIMITE_FILA_S)
            print(f"\n[{nome}] {_resumo(caminho)}")
            if cod_fila == ESTOUROU:
                print(f"[{nome}] ESTOUROU {LIMITE_FILA_S} s: teste preso, ver data/testes/{nome}.txt")
            if not _aceito(cod_fila, extras):
                codigo = codigo or cod_fila

        cod_nav, saida_nav, linhas = fechar_navegador(resultados, extras, base)
        (SAIDA / "navegador.txt").write_text(saida_nav, encoding="utf-8")
        if not extras:  # `-k` e cia. distorcem o tempo do arquivo
            tempos = {nome: round(seg, 1) for nome, _, _, seg in resultados}
            TEMPOS_NAVEGADOR.write_text(json.dumps(tempos, indent=1, sort_keys=True), encoding="utf-8")
        print("\n" + "\n".join(f"[navegador] {l}" for l in linhas[:-1]))
        print(f"[navegador] {linhas[-1]} em {fim_nav:.0f} s")
        codigo = codigo or cod_nav
    finally:
        for proc, _ in rodando.values():
            if proc.poll() is None:
                _matar(proc)
        if base != RAIZ:
            shutil.rmtree(base, ignore_errors=True)
    print(f"\nTotal: {time.monotonic() - inicio:.0f} s")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
