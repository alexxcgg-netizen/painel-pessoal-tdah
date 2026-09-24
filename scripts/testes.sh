#!/usr/bin/env bash
# Roda so os testes pedidos e imprime apenas FAIL/ERROR e o resumo (max 40 linhas).
# Uso: scripts/testes.sh tests/test_x.py [tests/test_y.py ...]
#      scripts/testes.sh --js tests/js/x.test.js
PY="${PAINEL_PY:-/home/user/painel-pessoal-tdah/.venv/bin/python}"
cd "$(git rev-parse --show-toplevel)" || exit 2
if [ "$1" = "--js" ]; then
  shift
  nice -n 10 timeout "${TESTES_TIMEOUT:-300}" node --test "$@" 2>&1 | grep -E "not ok|# (pass|fail|tests)" | tail -40
  exit "${PIPESTATUS[0]}"
fi
nice -n 10 timeout "${TESTES_TIMEOUT:-600}" "$PY" -m pytest -q -p no:cacheprovider "$@" 2>&1 \
  | grep -E "^(FAILED|ERROR)|[0-9]+ (passed|failed|error)" | tail -40
exit "${PIPESTATUS[0]}"
