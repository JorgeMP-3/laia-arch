#!/usr/bin/env bash
# Test: clone_install_first_if_needed detects a partial /opt/laia install
# and cleans it up before re-running laia-install. Without this, a previous
# failed install left `laia-vX.Y.Z/` around and the next attempt aborted
# with "Version already installed".
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
BIN="$LAIA_ROOT/bin"
PASS=0; FAIL=0; FAILURES=()
assert() { local d="$1" s="$2"; if [[ "$s" == 0 ]]; then PASS=$((PASS+1)); printf '  ✓ %s\n' "$d"; else FAIL=$((FAIL+1)); FAILURES+=("$d"); printf '  ✗ %s\n' "$d"; fi; }

TMPDIR_TEST="$(mktemp -d "${HOME}/laia-partial-install.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

INSTALL_ROOT="$TMPDIR_TEST/opt"
mkdir -p "$INSTALL_ROOT"
# Simulate a partial install: a versioned dir exists but no symlink and
# no .laia-core inside (interrupted halfway).
mkdir -p "$INSTALL_ROOT/laia-v0.0.0-test/services"
echo "v0.0.0-test" >"$INSTALL_ROOT/laia-v0.0.0-test/VERSION"

# Build a minimal source dir for laia-clone --source-dir
SRC="$TMPDIR_TEST/source"
mkdir -p "$SRC/agora" "$SRC/users" "$SRC/home/.laia"
printf 'db\n' >"$SRC/agora/agora.db"

export NO_COLOR=1
export LAIA_INSTALL_ROOT_OVERRIDE="$INSTALL_ROOT"
export LAIA_BIN_DIR_OVERRIDE="$TMPDIR_TEST/usr_local_bin"
export LAIA_HOME_OVERRIDE="$TMPDIR_TEST/LAIA-ARCH"
export LAIA_USERS_DIR_OVERRIDE="$TMPDIR_TEST/srv/users"
export LAIA_AGORA_DIR_OVERRIDE="$TMPDIR_TEST/srv/agora"
export LAIA_ARCH_DIR_OVERRIDE="$TMPDIR_TEST/srv/arch"
export LAIA_ARCH_CREDS_DIR_OVERRIDE="$TMPDIR_TEST/home/.laia"
export LAIA_SYSTEMD_DIR_OVERRIDE="$TMPDIR_TEST/etc_systemd"
export LAIA_LOG_FILE="$TMPDIR_TEST/log"
export LAIA_TEST_STUB_LOG="$TMPDIR_TEST/stub.log"

"$BIN/laia-clone" --source-dir "$SRC" --yes >"$TMPDIR_TEST/run.log" 2>&1
rc=$?
assert "clone exits 0 even with partial install present" "$rc"
assert "partial laia-v0.0.0-test removed and rebuilt" \
  "$([[ -d "$INSTALL_ROOT/laia-v0.0.0-test/.laia-core" || -L "$INSTALL_ROOT/laia" ]] && echo 0 || echo 1)"
assert "run log mentions partial cleanup" \
  "$(grep -q 'Partial /opt/laia install detected' "$TMPDIR_TEST/run.log" && echo 0 || echo 1)"
assert "install-first ran after cleanup" \
  "$(grep -q 'Install-first' "$TMPDIR_TEST/run.log" && echo 0 || echo 1)"

printf '\nPASS: %d FAIL: %d\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then printf '%s\n' "${FAILURES[@]}"; cat "$TMPDIR_TEST/run.log"; exit 1; fi
