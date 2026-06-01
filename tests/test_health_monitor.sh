#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# tests/test_health_monitor.sh
#
# Test del monitor de salud (Track B · B2). Host-free y determinista: NO toca el
# ecosistema real. Cubre el criterio de aceptación del PRD:
#   "un fallo simulado deja el estado en 'rojo' con la causa; al recuperarse,
#    vuelve a 'verde'. Sin ruido (sobrescribe estado, no acumula)."
#
# Dos niveles:
#   1) helper python `laia_health_state.py` con reportes T1 sintéticos
#      (verde / rojo / error / recuperación) → asserts sobre latest.json/.txt/history.
#   2) entrypoint `laia-health-monitor` con un LAIA_ROOT falso que monta el runner
#      T1 real + un test sintético controlable por env → green→red→green E2E,
#      sin contactar prod.
#
# Run:  bash tests/test_health_monitor.sh
# ─────────────────────────────────────────────────────────────────────────────
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT_REPO="$(cd "$TEST_DIR/.." && pwd)"
HELPER="$LAIA_ROOT_REPO/infra/bin/laia_health_state.py"
MONITOR="$LAIA_ROOT_REPO/infra/bin/laia-health-monitor"
PY="${LAIA_PYTHON:-python3}"

PASS=0
FAIL=0
FAILURES=()

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    PASS=$((PASS + 1)); printf '  ✓ %s\n' "$desc"
  else
    FAIL=$((FAIL + 1)); FAILURES+=("$desc — expected '$expected', got '$actual'")
    printf '  ✗ %s (expected %s, got %s)\n' "$desc" "$expected" "$actual"
  fi
}
assert_true() {
  local desc="$1"; shift
  if "$@"; then PASS=$((PASS + 1)); printf '  ✓ %s\n' "$desc"
  else FAIL=$((FAIL + 1)); FAILURES+=("$desc"); printf '  ✗ %s\n' "$desc"; fi
}
assert_contains() {
  local desc="$1" hay="$2" needle="$3"
  if [[ "$hay" == *"$needle"* ]]; then PASS=$((PASS + 1)); printf '  ✓ %s\n' "$desc"
  else FAIL=$((FAIL + 1)); FAILURES+=("$desc — '$needle' no está en la salida"); printf '  ✗ %s\n' "$desc"; fi
}

WORK="$(mktemp -d "${TMPDIR:-/tmp}/laia-health-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# jq-free JSON field reader.
json_get() { "$PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); k=sys.argv[2].split("."); v=d
for p in k: v=v[p] if isinstance(v,dict) else v
print(v if v is not None else "")' "$1" "$2" 2>/dev/null; }

# ── Reportes T1 sintéticos ──────────────────────────────────────────────────
cat >"$WORK/green.json" <<'EOF'
{"schema_version":1,"profile":"host","environment":{"lxd_available":true},
 "summary":{"total":2,"selected":2,"passed":2,"failed":0,"skipped":0,"duration_ms":120},
 "tests":[{"id":"a","name":"A","status":"pass"},{"id":"b","name":"B","status":"pass"}]}
EOF
cat >"$WORK/red.json" <<'EOF'
{"schema_version":1,"profile":"host","environment":{"lxd_available":true},
 "summary":{"total":2,"selected":2,"passed":1,"failed":1,"skipped":0,"duration_ms":300},
 "tests":[{"id":"a","name":"A","status":"pass"},
  {"id":"agora_health","name":"AGORA health contract","status":"fail","exit_code":1,
   "layers":["agora"],"stderr":"curl: (7) Failed to connect to localhost:8088\nFAIL /api/health"}]}
EOF

ST="$WORK/state"

echo "→ Helper: fallo simulado → rojo con causa"
"$PY" "$HELPER" --report "$WORK/red.json" --runner-exit 1 --state-dir "$ST" \
  --host testhost --now-epoch 1000 >/dev/null
assert_eq "status rojo" "red" "$(json_get "$ST/latest.json" status)"
assert_contains "causa nombra el check fallido" "$(json_get "$ST/latest.json" cause)" "agora_health"
assert_true "latest.json es JSON válido" "$PY" -c "import json;json.load(open('$ST/latest.json'))"
assert_contains "latest.txt muestra RED" "$(cat "$ST/latest.txt")" "LAIA health — RED"
assert_contains "latest.txt incluye stderr-tail de la causa" "$(cat "$ST/latest.txt")" "8088"

echo
echo "→ Helper: recuperación → verde sin causa"
"$PY" "$HELPER" --report "$WORK/green.json" --runner-exit 0 --state-dir "$ST" \
  --host testhost --now-epoch 2000 >/dev/null
assert_eq "status verde" "green" "$(json_get "$ST/latest.json" status)"
assert_eq "verde sin causa" "" "$(json_get "$ST/latest.json" cause)"
assert_contains "latest.txt muestra GREEN" "$(cat "$ST/latest.txt")" "LAIA health — GREEN"

echo
echo "→ Helper: runner exit 2 → error (no verde falso)"
"$PY" "$HELPER" --report "$WORK/green.json" --runner-exit 2 --state-dir "$ST" \
  --host testhost --now-epoch 3000 >/dev/null
assert_eq "status error pese a reporte con passed" "error" "$(json_get "$ST/latest.json" status)"

echo
echo "→ Helper: reporte vacío/ilegible → error"
printf '' | "$PY" "$HELPER" --report - --runner-exit 2 --state-dir "$ST" --host testhost --now-epoch 4000 >/dev/null
assert_eq "status error con reporte vacío" "error" "$(json_get "$ST/latest.json" status)"

echo
echo "→ Sobrescribe, no acumula ruido: history capado a --history-max"
ST2="$WORK/state2"
for i in $(seq 1 7); do
  "$PY" "$HELPER" --report "$WORK/green.json" --runner-exit 0 --state-dir "$ST2" \
    --host testhost --now-epoch "$((5000 + i))" --history-max 3 >/dev/null
done
hist_lines=$(grep -c . "$ST2/history.jsonl")
assert_eq "history capado a 3 líneas tras 7 runs" "3" "$hist_lines"
assert_true "sólo hay UN latest.json (no acumulación)" test -f "$ST2/latest.json"

echo
echo "→ E2E monitor con runner real + test sintético (sin tocar prod)"
FAKE="$WORK/fakeroot"
mkdir -p "$FAKE/tests/integration/lib"
cp "$LAIA_ROOT_REPO/tests/integration/run_integrity.sh" "$FAKE/tests/integration/"
cp "$LAIA_ROOT_REPO/tests/integration/lib/integrity_runner.py" "$FAKE/tests/integration/lib/"
cat >"$FAKE/tests/integration/test_synthetic.sh" <<'EOF'
#!/usr/bin/env bash
# integrity:id=synthetic_probe
# integrity:name=Synthetic probe
# integrity:level=integration
# integrity:layers=agora
# integrity:profiles=ci,host,vm
[[ "${SYNTH_FAIL:-0}" == "1" ]] && { echo "boom simulado" >&2; exit 1; }
echo ok; exit 0
EOF
chmod +x "$FAKE/tests/integration/test_synthetic.sh"
EST="$WORK/estate"

LAIA_ROOT="$FAKE" LAIA_HEALTH_STATE_DIR="$EST" LAIA_HEALTH_PROFILE=host "$MONITOR" run >/dev/null 2>&1
mrc=$?
assert_eq "monitor sale 0 (estado publicado)" "0" "$mrc"
assert_eq "E2E sano → verde" "green" "$(json_get "$EST/latest.json" status)"

SYNTH_FAIL=1 LAIA_ROOT="$FAKE" LAIA_HEALTH_STATE_DIR="$EST" "$MONITOR" run >/dev/null 2>&1
assert_eq "E2E fallo simulado → rojo" "red" "$(json_get "$EST/latest.json" status)"
assert_contains "E2E rojo nombra la causa" "$(json_get "$EST/latest.json" cause)" "synthetic_probe"

LAIA_ROOT="$FAKE" LAIA_HEALTH_STATE_DIR="$EST" "$MONITOR" run >/dev/null 2>&1
assert_eq "E2E recuperación → verde" "green" "$(json_get "$EST/latest.json" status)"

echo
echo "→ Subcomando show / path"
show_out="$(LAIA_ROOT="$FAKE" LAIA_HEALTH_STATE_DIR="$EST" "$MONITOR" show)"
assert_contains "show imprime el estado" "$show_out" "LAIA health"
path_out="$(LAIA_ROOT="$FAKE" LAIA_HEALTH_STATE_DIR="$EST" "$MONITOR" path)"
assert_eq "path imprime el dir de salud" "$EST" "$path_out"

echo
echo "→ Runner ausente → error (no rompe)"
EST3="$WORK/estate3"
LAIA_ROOT="$WORK/nonexistent-root" LAIA_HEALTH_STATE_DIR="$EST3" "$MONITOR" run >/dev/null 2>&1
mrc3=$?
assert_eq "monitor sale 0 aun sin runner" "0" "$mrc3"
assert_eq "estado error si falta el runner" "error" "$(json_get "$EST3/latest.json" status)"

echo
echo "═══════════════════════════════════════════════════"
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
if [[ $FAIL -gt 0 ]]; then
  echo; echo "Failures:"
  for f in "${FAILURES[@]}"; do printf "  - %s\n" "$f"; done
  exit 1
fi
exit 0
