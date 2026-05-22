#!/usr/bin/env bash
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"

PASS=0; FAIL=0; FAILURES=()
ok()   { PASS=$((PASS+1)); printf '  ✓ %s\n' "$1"; }
nope() { FAIL=$((FAIL+1)); FAILURES+=("$1"); printf '  ✗ %s\n' "$1"; }

echo "→ HeadlessUI submits optional fields as empty defaults"
if PYTHONPATH="$LAIA_ROOT/.laia-core" python3 - <<'PY'
import sys
from laia_cli.install_wizard._headless_ui import HeadlessUI
from laia_cli.install_wizard.flows.install import _ADMIN_SCREEN

ui = HeadlessUI({})
values = ui.render(_ADMIN_SCREEN)
if values.get("admin_user") != "admin":
    print(f"admin_user default missing: {values!r}", file=sys.stderr)
    sys.exit(1)
if values.get("admin_pass") != "":
    print(f"admin_pass should be empty optional value: {values!r}", file=sys.stderr)
    sys.exit(1)
if values.get("_action") != "next":
    print(f"expected next action: {values!r}", file=sys.stderr)
    sys.exit(1)
PY
then
  ok "install --yes can reach password autogeneration path"
else
  nope "HeadlessUI still blocks optional admin_pass"
fi

echo
echo "═══════════════════════════════════════════════════"
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
if [[ $FAIL -gt 0 ]]; then
  echo "Failures:"
  for f in "${FAILURES[@]}"; do printf "  - %s\n" "$f"; done
  exit 1
fi
exit 0
