#!/usr/bin/env bash
# Smoke tests for infra/dev/setup-ctl-venv.sh:
#  - exits 2 with bad args
#  - --help prints usage
#  - rejects missing requirements file
#  - rejects missing python3
# We DO NOT actually create the venv here (that requires network +
# python3-venv); a separate manual smoke step covers that case.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

SCRIPT="$ROOT/infra/dev/setup-ctl-venv.sh"
[[ -x "$SCRIPT" ]] || { echo "FAIL: $SCRIPT no es ejecutable"; exit 1; }

# Case 1: --help → exit 0, prints usage.
out=$("$SCRIPT" --help 2>&1)
echo "$out" | grep -q "setup-ctl-venv.sh" || { echo "FAIL: --help no menciona el script"; echo "$out"; exit 1; }

# Case 2: arg desconocido → exit 2.
set +e
"$SCRIPT" --garbage >/dev/null 2>&1
rc=$?
set -e
[[ $rc -eq 2 ]] || { echo "FAIL: bad arg returned $rc, expected 2"; exit 1; }

# Case 3: requirements file missing → exit 1 + mensaje claro.
mkdir -p "$TMP/devdir"
cp "$SCRIPT" "$TMP/devdir/setup-ctl-venv.sh"
chmod +x "$TMP/devdir/setup-ctl-venv.sh"
set +e
out=$("$TMP/devdir/setup-ctl-venv.sh" 2>&1)
rc=$?
set -e
[[ $rc -eq 1 ]] || { echo "FAIL: missing req exit $rc, expected 1"; echo "$out"; exit 1; }
echo "$out" | grep -q "requirements-ctl.txt no existe" \
  || { echo "FAIL: error message wrong"; echo "$out"; exit 1; }

# Case 4: con python3 ausente del PATH → exit 1 con mensaje. PATH debe
# llevar bash (el shebang lo necesita) pero NO python3.
MINI_PATH="$TMP/minipath"
mkdir -p "$MINI_PATH"
ln -s "$(command -v bash)" "$MINI_PATH/bash"
ln -s "$(command -v sed)"  "$MINI_PATH/sed"
ln -s "$(command -v rm)"   "$MINI_PATH/rm"
ln -s "$(command -v cat)"  "$MINI_PATH/cat"
ln -s "$(command -v sha256sum)" "$MINI_PATH/sha256sum"
ln -s "$(command -v awk)"  "$MINI_PATH/awk"
ln -s "$(command -v dirname)" "$MINI_PATH/dirname"
ln -s "$(command -v command)" "$MINI_PATH/command" 2>/dev/null || true
set +e
out=$(PATH="$MINI_PATH" "$SCRIPT" 2>&1)
rc=$?
set -e
[[ $rc -eq 1 ]] || { echo "FAIL: missing python3 returned $rc, expected 1"; echo "$out"; exit 1; }
echo "$out" | grep -q "python3 no instalado" \
  || { echo "FAIL: missing-python3 message wrong"; echo "$out"; exit 1; }

echo "test_ctl_setup.sh: ok"
