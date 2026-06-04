#!/usr/bin/env bash
# ARCH console unit spec (ARCH-usable S5, 2026-06-04). Guards for
# problems.md::ui-prod-layer-rota-v0.11.0-necesita-remake-v0.2.0:
#   - the console binds LOOPBACK ONLY (users must never reach ARCH; the old
#     unit bound 0.0.0.0 exposing unauthenticated PTY terminals to the LAN)
#   - it runs as ${LAIA_USER}, never root
#   - no `export`-style lines (systemd does not parse them — the malformed
#     EnvironmentFile is exactly what broke the v0.11 unit)
#   - no dependency on the retired laia-gateway unit
#   - the backend code default is also loopback (belt AND suspenders)
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
TMPL="$LAIA_ROOT/infra/installer/systemd/laia-ui-server.service.tmpl"
BACKEND="$LAIA_ROOT/.laia-core/laia-ui-server/backend/main.py"

PASS=0
FAIL=0
FAILURES=()

assert() {
  local desc="$1" status="$2"
  if [[ "$status" == "0" ]]; then
    PASS=$((PASS + 1)); printf '  PASS %s\n' "$desc"
  else
    FAIL=$((FAIL + 1)); FAILURES+=("$desc"); printf '  FAIL %s\n' "$desc"
  fi
}

echo "-> unit del operador (loopback, no-root, sin export)"
assert "template existe" "$([[ -f "$TMPL" ]] && echo 0 || echo 1)"
assert "ExecStart bindea 127.0.0.1" \
  "$(grep -E '^ExecStart=' "$TMPL" | grep -q -- '--host 127.0.0.1' && echo 0 || echo 1)"
# Directives only — comments may mention the old values they replaced.
assert "nada de 0.0.0.0 en DIRECTIVAS del template" \
  "$(! grep -v '^\s*#' "$TMPL" | grep -q '0\.0\.0\.0' && echo 0 || echo 1)"
assert "User= es \${LAIA_USER} (no root)" \
  "$(grep -q '^User=\${LAIA_USER}$' "$TMPL" && echo 0 || echo 1)"
assert "sin lineas 'export ' (systemd no las parsea)" \
  "$(! grep -q '^export ' "$TMPL" && echo 0 || echo 1)"
assert "sin dependencia del gateway retirado en DIRECTIVAS" \
  "$(! grep -v '^\s*#' "$TMPL" | grep -q 'laia-gateway' && echo 0 || echo 1)"

echo
echo "-> el codigo tambien default a loopback (belt and suspenders)"
assert "main.py: default LAIA_UI_HOST=127.0.0.1" \
  "$(grep -q 'LAIA_UI_HOST.*127\.0\.0\.1' "$BACKEND" && echo 0 || echo 1)"
assert "main.py: sin 0.0.0.0 hardcodeado en uvicorn.run" \
  "$(! grep -q 'host="0\.0\.0\.0"' "$BACKEND" && echo 0 || echo 1)"

echo
echo "=================================================="
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  echo; echo "Failures:"; printf '  - %s\n' "${FAILURES[@]}"
  exit 1
fi
exit 0
