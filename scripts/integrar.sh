#!/usr/bin/env bash
# M1 da Fase 7: integra faixas prontas na fase7/integracao, sem IA.
# Uso: scripts/integrar.sh <faixa> [<faixa> ...]   (ex: a5-historico n3e-widgetkit)
# Pra cada faixa: fetch, checa donos (so avisa), merge --no-ff, roda os testes
# que a faixa criou/alterou, e desfaz o merge se algum teste falhar.
set -u
cd "$(git rev-parse --show-toplevel)" || exit 2
PY="${PAINEL_PY:-/home/user/painel-pessoal-tdah/.venv/bin/python}"
[ "$(git branch --show-current)" = "fase7/integracao" ] || { echo "rode na fase7/integracao"; exit 2; }
git fetch -q origin
falhas=0
for faixa in "$@"; do
  ramo="origin/fase7/$faixa"
  git rev-parse -q --verify "$ramo" >/dev/null || { echo "[$faixa] branch nao encontrada"; falhas=1; continue; }
  if git merge-base --is-ancestor "$ramo" HEAD; then echo "[$faixa] ja integrada"; continue; fi
  base=$(git merge-base HEAD "$ramo")
  fora=$(git -c core.quotepath=off diff --name-only "$base" "$ramo" | while read -r f; do
    "$PY" -c "import sys,fnmatch,json;d=json.load(open('donos.json'))['faixas'];p=d.get('$faixa',[])+['scripts/ralph-$faixa/*','changelog.d/$faixa.md'];sys.exit(0 if any(fnmatch.fnmatch('$f',x) for x in p) else 1)" || echo "$f"; done)
  [ -n "$fora" ] && echo "[$faixa] AVISO fora da lista de donos:" && echo "$fora" | sed 's/^/    /'
  testes=$(git diff --name-only "$base" "$ramo" -- 'tests/test_*.py' | tr '\n' ' ')
  jstestes=$(git diff --name-only "$base" "$ramo" -- 'tests/js/*.test.js' | tr '\n' ' ')
  if ! git merge --no-ff -q "$ramo" -m "Merge faixa $faixa na integracao

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01VJzoYB1yYVL6gVFtBEB1Q7"; then
    conflitos=$(git diff --name-only --diff-filter=U)
    so_compartilhados=1
    for c in $conflitos; do case "$c" in AGENTS.md|CHANGELOG.md|TODO.md|STATUS.md) ;; *) so_compartilhados=0;; esac; done
    if [ -n "$conflitos" ] && [ $so_compartilhados -eq 1 ]; then
      # Faixas nao editam esses arquivos: o conflito vem so da resolucao de merge delas. Fica a versao da integracao.
      git checkout --ours -- $conflitos && git add -- $conflitos && git commit -q --no-edit
      echo "[$faixa] conflito so em compartilhados ($conflitos): mantida a versao da integracao"
    else
      echo "[$faixa] CONFLITO - merge abortado: $conflitos"; git merge --abort; falhas=1; continue
    fi
  fi
  ok=0
  [ -n "$testes" ] && { scripts/testes.sh $testes || ok=1; }
  [ -n "$jstestes" ] && { scripts/testes.sh --js $jstestes || ok=1; }
  if [ $ok -ne 0 ]; then echo "[$faixa] TESTES FALHARAM - merge desfeito"; git reset -q --hard HEAD~1; falhas=1; continue; fi
  echo "[$faixa] integrada ($(git rev-parse --short HEAD)) testes: ${testes:-nenhum} ${jstestes}"
done
git push -q origin fase7/integracao 2>&1 | grep -v "^remote:" | tail -1
exit $falhas
