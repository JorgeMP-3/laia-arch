#!/usr/bin/env bash
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
BIN="$LAIA_ROOT/bin"
PASS=0; FAIL=0; FAILURES=()
assert() { local d="$1" s="$2"; if [[ "$s" == 0 ]]; then PASS=$((PASS+1)); printf '  ✓ %s\n' "$d"; else FAIL=$((FAIL+1)); FAILURES+=("$d"); printf '  ✗ %s\n' "$d"; fi; }

TMPDIR_TEST="$(mktemp -d "${HOME}/laia-factory-install.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT
export NO_COLOR=1
export LAIA_INSTALL_ROOT_OVERRIDE="$TMPDIR_TEST/opt"
export LAIA_BIN_DIR_OVERRIDE="$TMPDIR_TEST/bin"
export LAIA_HOME_OVERRIDE="$TMPDIR_TEST/LAIA-ARCH"
export LAIA_ARCH_DIR_OVERRIDE="$TMPDIR_TEST/srv/laia/arch"
export LAIA_ARCH_CREDS_DIR_OVERRIDE="$TMPDIR_TEST/srv/laia/arch/secrets"
export LAIA_SYSTEMD_DIR_OVERRIDE="$TMPDIR_TEST/systemd"
export LAIA_SHELL_RC_OVERRIDE="$TMPDIR_TEST/rc"
export LAIA_LOG_FILE="$TMPDIR_TEST/log"
export LAIA_HOST_ARCH_OVERRIDE=amd64
mkdir -p "$LAIA_INSTALL_ROOT_OVERRIDE"

"$BIN/laia-install" --from-local "$LAIA_ROOT" --version v0.0.0-factory --skip-pip --skip-frontend --admin-user admin --admin-pass pass123 --yes >"$TMPDIR_TEST/run.log" 2>&1
assert "factory install exits 0" "$?"
# C4 native layout (v2): secrets in the ARCH secrets dir, NOT LAIA_HOME.
assert "auth.json created in ARCH secrets" "$([[ -f "$LAIA_ARCH_CREDS_DIR_OVERRIDE/auth.json" ]] && echo 0 || echo 1)"
assert ".env created in ARCH secrets" "$([[ -f "$LAIA_ARCH_CREDS_DIR_OVERRIDE/.env" ]] && echo 0 || echo 1)"
assert "auth.json NOT in LAIA_HOME" "$([[ ! -e "$LAIA_HOME_OVERRIDE/auth.json" ]] && echo 0 || echo 1)"
assert "cli-config.yaml created in LAIA_HOME" "$([[ -f "$LAIA_HOME_OVERRIDE/cli-config.yaml" ]] && echo 0 || echo 1)"
assert "admin credentials created" "$([[ -f "$LAIA_HOME_OVERRIDE/.admin-credentials" ]] && echo 0 || echo 1)"
assert "admin credentials contain user" "$(grep -q '^username=admin$' "$LAIA_HOME_OVERRIDE/.admin-credentials" && echo 0 || echo 1)"
assert "bootstrap functions stubbed by override" "$(grep -q '\[stub\] skipping boot_build_images' "$TMPDIR_TEST/run.log" && echo 0 || echo 1)"

printf '\nPASS: %d FAIL: %d\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then cat "$TMPDIR_TEST/run.log"; printf '%s\n' "${FAILURES[@]}"; exit 1; fi
