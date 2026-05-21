#!/usr/bin/env bash
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
BIN="$LAIA_ROOT/bin"
PASS=0; FAIL=0; FAILURES=()
assert() { local d="$1" s="$2"; if [[ "$s" == 0 ]]; then PASS=$((PASS+1)); printf '  ✓ %s\n' "$d"; else FAIL=$((FAIL+1)); FAILURES+=("$d"); printf '  ✗ %s\n' "$d"; fi; }

TMPDIR_TEST="$(mktemp -d "${HOME}/laia-minimal.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT
export NO_COLOR=1
export LAIA_INSTALL_ROOT_OVERRIDE="$TMPDIR_TEST/opt"
export LAIA_BIN_DIR_OVERRIDE="$TMPDIR_TEST/bin"
export LAIA_HOME_OVERRIDE="$TMPDIR_TEST/LAIA-ARCH"
export LAIA_SYSTEMD_DIR_OVERRIDE="$TMPDIR_TEST/systemd"
export LAIA_SHELL_RC_OVERRIDE="$TMPDIR_TEST/rc"
export LAIA_LOG_FILE="$TMPDIR_TEST/log"
mkdir -p "$LAIA_INSTALL_ROOT_OVERRIDE"

"$BIN/laia-install" --from-local "$LAIA_ROOT" --version v0.0.0-minimal --skip-pip --skip-frontend --minimal --yes >"$TMPDIR_TEST/run.log" 2>&1
assert "minimal install exits 0" "$?"
assert "auth.json not created in --minimal" "$([[ ! -f "$LAIA_HOME_OVERRIDE/auth.json" ]] && echo 0 || echo 1)"
assert ".admin-credentials not created in --minimal" "$([[ ! -f "$LAIA_HOME_OVERRIDE/.admin-credentials" ]] && echo 0 || echo 1)"
assert "minimal log says factory skipped" "$(grep -q 'Factory bootstrap (SKIPPED' "$TMPDIR_TEST/run.log" && echo 0 || echo 1)"

printf '\nPASS: %d FAIL: %d\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then cat "$TMPDIR_TEST/run.log"; printf '%s\n' "${FAILURES[@]}"; exit 1; fi
