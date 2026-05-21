#!/usr/bin/env bash
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
BIN="$LAIA_ROOT/bin"
PASS=0; FAIL=0; FAILURES=()
assert() { local d="$1" s="$2"; if [[ "$s" == 0 ]]; then PASS=$((PASS+1)); printf '  ✓ %s\n' "$d"; else FAIL=$((FAIL+1)); FAILURES+=("$d"); printf '  ✗ %s\n' "$d"; fi; }

TMPDIR_TEST="$(mktemp -d "${HOME}/laia-clone-install.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT
SRC="$TMPDIR_TEST/source"
mkdir -p "$SRC/agora" "$SRC/users/jorge/home" "$SRC/home/.laia"
printf '{}\n' >"$SRC/home/.laia/auth.json"

export NO_COLOR=1
export LAIA_INSTALL_ROOT_OVERRIDE="$TMPDIR_TEST/opt"
export LAIA_BIN_DIR_OVERRIDE="$TMPDIR_TEST/bin"
export LAIA_HOME_OVERRIDE="$TMPDIR_TEST/LAIA-ARCH"
export LAIA_SYSTEMD_DIR_OVERRIDE="$TMPDIR_TEST/systemd"
export LAIA_SHELL_RC_OVERRIDE="$TMPDIR_TEST/rc"
export LAIA_USERS_DIR_OVERRIDE="$TMPDIR_TEST/srv/users"
export LAIA_AGORA_DIR_OVERRIDE="$TMPDIR_TEST/srv/agora"
export LAIA_ARCH_DIR_OVERRIDE="$TMPDIR_TEST/srv/arch"
export LAIA_ARCH_CREDS_DIR_OVERRIDE="$TMPDIR_TEST/home/.laia"
export LAIA_LOG_FILE="$TMPDIR_TEST/log"
export LAIA_HOST_ARCH_OVERRIDE=amd64
mkdir -p "$LAIA_INSTALL_ROOT_OVERRIDE"

"$BIN/laia-clone" --source-dir "$SRC" --yes >"$TMPDIR_TEST/run.log" 2>&1
assert "clone exits 0" "$?"
assert "install-first created /opt/laia symlink override" "$([[ -L "$LAIA_INSTALL_ROOT_OVERRIDE/laia" ]] && echo 0 || echo 1)"
assert "install-first used --minimal" "$(grep -q 'Factory bootstrap (SKIPPED' "$TMPDIR_TEST/run.log" && echo 0 || echo 1)"
assert "users data copied" "$([[ -d "$LAIA_USERS_DIR_OVERRIDE/jorge/home" ]] && echo 0 || echo 1)"

printf '\nPASS: %d FAIL: %d\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then cat "$TMPDIR_TEST/run.log"; printf '%s\n' "${FAILURES[@]}"; exit 1; fi
