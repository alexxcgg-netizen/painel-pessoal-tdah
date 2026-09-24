#!/usr/bin/env python3
"""Garante que nenhum arquivo pertence a duas faixas da Fase 7.

Uso:
  scripts/checar_donos.py                 # prova que as listas nao se sobrepoem
  scripts/checar_donos.py --faixa n1-assinaturas [--base origin/fase7/integracao]
                                          # falha se o diff da faixa tocar fora da lista dela

Padroes em donos.json usam fnmatch (o * atravessa "/"). Toda faixa tambem pode
mexer em scripts/ralph-<faixa>/** e changelog.d/<faixa>.md.
"""
import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def carregar_donos(caminho: Path = RAIZ / "donos.json") -> dict[str, list[str]]:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return {faixa: padroes for faixa, padroes in dados["faixas"].items()}


def padroes_da_faixa(donos: dict, faixa: str) -> list[str]:
    return donos.get(faixa, []) + [f"scripts/ralph-{faixa}/*", f"changelog.d/{faixa}.md"]


def donos_do_arquivo(donos: dict, caminho: str) -> list[str]:
    return [f for f in donos if any(fnmatch.fnmatch(caminho, p) for p in padroes_da_faixa(donos, f))]


def _git(*args: str) -> list[str]:
    saida = subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout
    return [linha for linha in saida.splitlines() if linha]


def checar_sobreposicao(donos: dict) -> list[str]:
    # Arquivos reais + os proprios padroes tratados como caminho (pega sobreposicao de arquivo que ainda nao existe).
    candidatos = set(_git("ls-files"))
    for faixa, padroes in donos.items():
        candidatos.update(p.replace("*", "x") for p in padroes)
    erros = []
    for caminho in sorted(candidatos):
        faixas = donos_do_arquivo(donos, caminho)
        if len(faixas) > 1:
            erros.append(f"{caminho}: {', '.join(faixas)}")
    return erros


def checar_faixa(donos: dict, faixa: str, base: str) -> list[str]:
    if faixa not in donos:
        return [f"faixa desconhecida: {faixa}"]
    alterados = _git("diff", "--name-only", f"{base}...HEAD")
    permitidos = padroes_da_faixa(donos, faixa)
    return [c for c in alterados if not any(fnmatch.fnmatch(c, p) for p in permitidos)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--faixa")
    ap.add_argument("--base", default="origin/fase7/integracao")
    args = ap.parse_args()
    donos = carregar_donos()
    if args.faixa:
        fora = checar_faixa(donos, args.faixa, args.base)
        for c in fora:
            print(f"FORA DA FAIXA {args.faixa}: {c}")
        return 1 if fora else 0
    erros = checar_sobreposicao(donos)
    for e in erros:
        print(f"SOBREPOSICAO: {e}")
    print(f"{len(donos)} faixas, {len(erros)} sobreposicoes")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
