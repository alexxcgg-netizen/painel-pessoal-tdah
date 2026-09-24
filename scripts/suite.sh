#!/usr/bin/env bash
# Fase 7, faixa A12 (infra de testes). Roda a suite COMPLETA (Python +
# JS) em paralelo, com timeout, e imprime so FAIL/ERROR e o resumo (no
# maximo ~40 linhas). Sai != 0 se houver falha ou timeout. Ver
# docs/testes.md pra tempo antes/depois e como interpretar a saida.
#
# Uso:
#   scripts/suite.sh                 # tudo (Python + JS), paralelo
#   TESTES_JOBS=2 scripts/suite.sh   # menos processos (maquina fraca)
#   TESTES_TIMEOUT=300 scripts/suite.sh
#
# Como paraleliza (sem pytest-xdist - nao esta instalado no .venv
# compartilhado e a faixa foi instruida a nao instalar la, ver
# scripts/ralph-a12-testes/progress.txt): coleta todos os node ids de
# teste Python (`pytest --collect-only -q`) e distribui em round-robin
# por N processos `pytest` SEPARADOS (um por grupo). Isolamento por
# processo e seguro aqui porque cada arquivo de teste ja cria o proprio
# `db.DB_PATH` isolado (tempfile.TemporaryDirectory(), por arquivo ou por
# setUp - nenhum teste usa mais o caminho fixo de producao) - dois
# processos nunca disputam o mesmo arquivo de banco. Ver
# docs/testes.md#isolamento-de-banco pra detalhe.
set -uo pipefail
set +m 2>/dev/null || true  # sem controle de job -> sem "Killed" poluindo stderr no timeout

PY="${PAINEL_PY:-/home/user/painel-pessoal-tdah/.venv/bin/python}"
JOBS="${TESTES_JOBS:-$(nproc 2>/dev/null || echo 4)}"
TIMEOUT="${TESTES_TIMEOUT:-600}"

cd "$(git rev-parse --show-toplevel)" || { echo "ERROR: nao encontrei a raiz do repo git" >&2; exit 2; }

if [ ! -x "$PY" ]; then
  echo "ERROR: python nao encontrado em $PY (defina PAINEL_PY=...)" >&2
  exit 2
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

# ---- 1. coleta os node ids de teste Python e distribui em N grupos
#         (round-robin simples - os testes desta suite sao unitarios e de
#         custo parecido entre si, entao count-por-grupo ja balanceia bem;
#         ver docs/testes.md pro numero real medido) ----
"$PY" -m pytest --collect-only -q tests/ 2>"$WORKDIR/collect.err" \
  | grep '::' > "$WORKDIR/nodeids.txt"
if [ ! -s "$WORKDIR/nodeids.txt" ]; then
  echo "ERROR: falha ao coletar os testes Python (veja $WORKDIR/collect.err antes do trap limpar, rode sem paralelismo pra depurar)" >&2
  cat "$WORKDIR/collect.err" >&2
  exit 2
fi

awk -v n="$JOBS" -v dir="$WORKDIR" '{
  grupo = (NR - 1) % n
  print $0 > (dir "/py_" grupo ".ids")
}' "$WORKDIR/nodeids.txt"

# ---- 2. dispara cada grupo Python num processo pytest isolado ----
PIDS=()
LOGS=()
for ((i = 0; i < JOBS; i++)); do
  ids_file="$WORKDIR/py_$i.ids"
  [ -s "$ids_file" ] || continue
  log="$WORKDIR/py_$i.log"
  LOGS+=("$log")
  (
    mapfile -t ids <"$ids_file"
    nice -n 10 "$PY" -m pytest -q -p no:cacheprovider "${ids[@]}" >"$log" 2>&1
  ) &
  PIDS+=("$!")
done

# ---- 3. JS em paralelo tambem (tests/js/*.test.js, roda em segundos) ----
js_log="$WORKDIR/js.log"
if compgen -G "tests/js/*.test.js" >/dev/null; then
  ( nice -n 10 node --test tests/js/*.test.js >"$js_log" 2>&1 ) &
  PIDS+=("$!")
  LOGS+=("$js_log")
fi

# ---- 4. watchdog do timeout geral (mata tudo se passar do limite) ----
(
  sleep "$TIMEOUT"
  echo "TIMEOUT: a suite nao terminou em ${TIMEOUT}s - matando os grupos ainda rodando" >>"$WORKDIR/timeout.flag"
  kill -9 "${PIDS[@]}" 2>/dev/null
) &
WATCHDOG=$!

FALHOU=0
for pid in "${PIDS[@]}"; do
  wait "$pid" 2>/dev/null || FALHOU=1
done
kill "$WATCHDOG" 2>/dev/null
wait "$WATCHDOG" 2>/dev/null

# ---- 5. agrega: so FAIL/ERROR + um resumo, no maximo ~40 linhas ----
{
  if [ -f "$WORKDIR/timeout.flag" ]; then
    cat "$WORKDIR/timeout.flag"
  fi
  for log in "${LOGS[@]}"; do
    grep -E "^(FAILED|ERROR)|not ok" "$log"
  done
} | sort -u

echo "----"
"$PY" - "${LOGS[@]}" <<'PYEOF'
import re
import sys

total_py_passed = total_py_failed = total_py_error = total_py_sub = 0
js_pass = js_fail = None
for caminho in sys.argv[1:]:
    try:
        texto = open(caminho, encoding="utf-8", errors="replace").read()
    except OSError:
        continue
    if caminho.endswith("js.log"):
        m_pass = re.search(r"^# pass (\d+)", texto, re.M)
        m_fail = re.search(r"^# fail (\d+)", texto, re.M)
        js_pass = int(m_pass.group(1)) if m_pass else js_pass
        js_fail = int(m_fail.group(1)) if m_fail else js_fail
        continue
    m = re.search(
        r"(?:(\d+) passed)?(?:, )?(?:(\d+) failed)?(?:, )?(?:(\d+) error\w*)?"
        r"(?:, )?(?:(\d+) subtests passed)? in [\d.]+s",
        texto,
    )
    if not m:
        continue
    total_py_passed += int(m.group(1) or 0)
    total_py_failed += int(m.group(2) or 0)
    total_py_error += int(m.group(3) or 0)
    total_py_sub += int(m.group(4) or 0)

partes = [f"Python: {total_py_passed} passed"]
if total_py_sub:
    partes.append(f"{total_py_sub} subtests passed")
if total_py_failed:
    partes.append(f"{total_py_failed} failed")
if total_py_error:
    partes.append(f"{total_py_error} error(s)")
resumo = ", ".join(partes)
if js_pass is not None or js_fail is not None:
    resumo += f" | JS: {js_pass or 0} pass, {js_fail or 0} fail"
print(resumo)
PYEOF

exit "$FALHOU"
