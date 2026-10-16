#!/usr/bin/env python3
"""scripts/indice_changelog.py - indice no topo do CHANGELOG.md (uma linha por entrada) e
arquivo dos dias antigos em docs/historico/CHANGELOG-AAAA-MM.md.

Por que (2026-10-16, pedido do Alex: "cada vez gastar menos, acertar mais"): o CHANGELOG passou
de 3.600 linhas e toda sessao nova que precisava lembrar de algo vasculhava tudo. Agora a sessao
le so o indice; achou o assunto, abre a entrada (aqui ou no historico) e le so ela.

Uso:
  .venv/Scripts/python.exe scripts/indice_changelog.py                   # refaz o indice
  .venv/Scripts/python.exe scripts/indice_changelog.py --arquivar-antes 2026-10-01
  .venv/Scripts/python.exe scripts/indice_changelog.py --checar          # 1 se o indice esta velho
"""

import argparse
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CHANGELOG = RAIZ / "CHANGELOG.md"
HISTORICO = RAIZ / "docs" / "historico"
INICIO = "<!-- indice:inicio (gerado por scripts/indice_changelog.py - nao editar a mao) -->"
FIM = "<!-- indice:fim -->"
_TITULO = re.compile(r"^## (\d{4}-\d{2}-\d{2})")
_LIMITE_TITULO = 110


def separar(texto: str) -> tuple[str, list[str]]:
    """(cabeca antes da 1a entrada, [entradas "## ..." inteiras, na ordem do arquivo])."""
    linhas = texto.splitlines(keepends=True)
    inicios = [i for i, l in enumerate(linhas) if _TITULO.match(l)]
    if not inicios:
        return texto, []
    cabeca = "".join(linhas[: inicios[0]])
    entradas = ["".join(linhas[a:b]) for a, b in zip(inicios, inicios[1:] + [len(linhas)])]
    return cabeca, entradas


def _sem_indice(cabeca: str) -> str:
    if INICIO in cabeca and FIM in cabeca:
        antes, resto = cabeca.split(INICIO, 1)
        cabeca = antes.rstrip("\n") + "\n\n" + resto.split(FIM, 1)[1].lstrip("\n")
    return cabeca.rstrip("\n") + "\n\n"


def _linha(entrada: str) -> str:
    titulo = entrada.splitlines()[0][3:].strip()
    if len(titulo) > _LIMITE_TITULO:
        titulo = titulo[: _LIMITE_TITULO - 1].rstrip() + "…"
    return f"- {titulo}\n"


def montar_indice(entradas: list[str], arquivos: list[tuple[str, list[str]]]) -> str:
    partes = [
        INICIO + "\n",
        "## Índice (ler isto primeiro)\n\n",
        "Uma linha por entrada, mais nova em cima. Achou o assunto: busque o título (aqui embaixo ou no\n",
        "arquivo do histórico indicado) e leia só aquela entrada.\n\n",
        *map(_linha, entradas),
    ]
    for nome, antigas in arquivos:
        partes += [f"\n**Arquivadas em `{nome}`:**\n\n", *map(_linha, antigas)]
    partes.append(FIM + "\n\n")
    return "".join(partes)


def _arquivos_historico(pasta: Path) -> list[tuple[Path, list[str]]]:
    if not pasta.is_dir():
        return []
    return [(p, separar(p.read_text(encoding="utf-8"))[1])
            for p in sorted(pasta.glob("CHANGELOG-*.md"), reverse=True)]


def arquivar(changelog: Path, pasta: Path, antes: str) -> int:
    """Move as entradas com data < `antes` pro CHANGELOG-AAAA-MM.md do mes delas (mais nova em
    cima, como no principal). Devolve quantas moveu."""
    cabeca, entradas = separar(changelog.read_text(encoding="utf-8"))
    ficam = [e for e in entradas if _TITULO.match(e).group(1) >= antes]
    saem = [e for e in entradas if _TITULO.match(e).group(1) < antes]
    por_mes: dict[str, list[str]] = {}
    for e in saem:
        por_mes.setdefault(_TITULO.match(e).group(1)[:7], []).append(e)
    pasta.mkdir(parents=True, exist_ok=True)
    for mes, novas in por_mes.items():
        destino = pasta / f"CHANGELOG-{mes}.md"
        if destino.exists():
            cab, velhas = separar(destino.read_text(encoding="utf-8"))
        else:
            cab = (f"# CHANGELOG arquivado - {mes}\n\nEntradas antigas tiradas do `CHANGELOG.md` "
                   "(o índice no topo de lá lista todas). Mais nova em cima.\n\n")
            velhas = []
        todas = sorted(novas + velhas, key=lambda e: _TITULO.match(e).group(1), reverse=True)
        destino.write_text(cab + "".join(_fechar(e) for e in todas), encoding="utf-8", newline="\n")
    changelog.write_text(cabeca + "".join(_fechar(e) for e in ficam), encoding="utf-8", newline="\n")
    return len(saem)


def _fechar(entrada: str) -> str:
    return entrada.rstrip("\n") + "\n\n"


def texto_com_indice(changelog: Path, pasta: Path) -> str:
    cabeca, entradas = separar(changelog.read_text(encoding="utf-8"))
    arquivos = [(p.relative_to(changelog.parent).as_posix(), e) for p, e in _arquivos_historico(pasta)]
    corpo = "".join(_fechar(e) for e in entradas).rstrip("\n") + "\n"
    return _sem_indice(cabeca) + montar_indice(entradas, arquivos) + corpo


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--arquivar-antes", metavar="AAAA-MM-DD")
    p.add_argument("--checar", action="store_true")
    p.add_argument("--changelog", type=Path, default=CHANGELOG)
    p.add_argument("--historico", type=Path, default=HISTORICO)
    args = p.parse_args(argv)

    if args.checar:
        atual = args.changelog.read_text(encoding="utf-8")
        if atual != texto_com_indice(args.changelog, args.historico):
            print("indice do CHANGELOG desatualizado: rode scripts/indice_changelog.py", file=sys.stderr)
            return 1
        return 0
    if args.arquivar_antes:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.arquivar_antes):
            print("--arquivar-antes precisa ser AAAA-MM-DD", file=sys.stderr)
            return 2
        print(f"{arquivar(args.changelog, args.historico, args.arquivar_antes)} entradas arquivadas")
    args.changelog.write_text(texto_com_indice(args.changelog, args.historico), encoding="utf-8", newline="\n")
    print(f"indice atualizado em {args.changelog}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
