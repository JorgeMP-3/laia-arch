#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# tests/installer/test_lib_common.sh
#
# Unit tests for infra/installer/lib/*.sh — verifies helper behavior
# without needing a real system (no /opt writes, no sudo).
#
# Run:
#   bash tests/installer/test_lib_common.sh
# ─────────────────────────────────────────────────────────────────────────────
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
LIB="$LAIA_ROOT/infra/installer/lib"

PASS=0
FAIL=0
FAILURES=()

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    PASS=$((PASS + 1))
    printf '  ✓ %s\n' "$desc"
  else
    FAIL=$((FAIL + 1))
    FAILURES+=("$desc — expected '$expected', got '$actual'")
    printf '  ✗ %s\n' "$desc"
  fi
}

assert_true() {
  local desc="$1"; shift
  if "$@"; then
    PASS=$((PASS + 1))
    printf '  ✓ %s\n' "$desc"
  else
    FAIL=$((FAIL + 1))
    FAILURES+=("$desc — returned $?")
    printf '  ✗ %s\n' "$desc"
  fi
}

# ── common.sh ───────────────────────────────────────────────────────────────
echo "→ common.sh"
# shellcheck source=../../infra/installer/lib/common.sh
source "$LIB/common.sh"

assert_eq "LAIA_LIB_COMMON_LOADED is set" "1" "$LAIA_LIB_COMMON_LOADED"

# Re-source must be idempotent (the guard short-circuits before redefining
# read-only constants, which would otherwise error).
assert_true "common.sh is idempotent on re-source" \
  bash -c "source '$LIB/common.sh'; source '$LIB/common.sh'"

# log_* functions must exist
for fn in log_info log_success log_warn log_error log_step die require_cmd; do
  assert_true "function $fn defined" declare -F "$fn" >/dev/null
done

# ── version.sh ──────────────────────────────────────────────────────────────
echo
echo "→ version.sh"
# shellcheck source=../../infra/installer/lib/version.sh
source "$LIB/version.sh"

assert_eq "LAIA_INSTALL_ROOT=/opt"       "/opt"       "$LAIA_INSTALL_ROOT"
assert_eq "LAIA_INSTALL_PREFIX=/opt/laia" "/opt/laia" "$LAIA_INSTALL_PREFIX"
assert_eq "LAIA_USR_LOCAL_BIN=/usr/local/bin" "/usr/local/bin" "$LAIA_USR_LOCAL_BIN"

# install_path_for_version
assert_eq "install_path_for_version v0.1.0" "/opt/laia-v0.1.0" \
  "$(install_path_for_version v0.1.0)"
assert_eq "install_path_for_version 0.1.0 (no v)" "/opt/laia-v0.1.0" \
  "$(install_path_for_version 0.1.0)"
assert_eq "install_path_for_version v2.7.99" "/opt/laia-v2.7.99" \
  "$(install_path_for_version v2.7.99)"

# detect_version with explicit
assert_eq "detect_version explicit v0.5.0" "v0.5.0" \
  "$(detect_version /tmp v0.5.0)"
assert_eq "detect_version normalizes 0.5.0 → v0.5.0" "v0.5.0" \
  "$(detect_version /tmp 0.5.0)"

# detect_version reads VERSION file
TMP_VER_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_VER_DIR"' EXIT
echo "0.9.1" >"$TMP_VER_DIR/VERSION"
assert_eq "detect_version reads VERSION file" "v0.9.1" \
  "$(detect_version "$TMP_VER_DIR")"

# detect_version with no info returns failure
EMPTY_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_VER_DIR" "$EMPTY_DIR"' EXIT
if detect_version "$EMPTY_DIR" 2>/dev/null; then
  FAIL=$((FAIL + 1))
  FAILURES+=("detect_version on empty dir should fail")
  echo "  ✗ detect_version on empty dir fails"
else
  PASS=$((PASS + 1))
  echo "  ✓ detect_version on empty dir fails"
fi

# ── system.sh ───────────────────────────────────────────────────────────────
echo
echo "→ system.sh"
# shellcheck source=../../infra/installer/lib/system.sh
source "$LIB/system.sh"

detect_os
assert_true "detect_os sets LAIA_OS" test -n "$LAIA_OS"

# missing_cmds with a cmd that should exist and one that shouldn't
result="$(missing_cmds bash totally-not-a-real-command-xyzzy)"
assert_eq "missing_cmds reports only the missing one" \
  "totally-not-a-real-command-xyzzy" "$result"

# ── sudo.sh ─────────────────────────────────────────────────────────────────
echo
echo "→ sudo.sh"
# shellcheck source=../../infra/installer/lib/sudo.sh
source "$LIB/sudo.sh"

assert_true "LAIA_USER is set" test -n "$LAIA_USER"
assert_true "LAIA_USER_HOME is set" test -n "$LAIA_USER_HOME"
assert_true "LAIA_USER_HOME is a directory" test -d "$LAIA_USER_HOME"
assert_true "is_root function exists" declare -F is_root >/dev/null

# We're (most likely) not root in test, so is_root must return 1
if is_root; then
  echo "  ⚠ running as root — skipping is_root nonzero check"
else
  assert_true "is_root returns nonzero for non-root" bash -c '! ( source '"$LIB"'/sudo.sh && is_root )'
fi

# ── Summary ─────────────────────────────────────────────────────────────────
echo
echo "═══════════════════════════════════════════════════"
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
if [[ $FAIL -gt 0 ]]; then
  echo
  echo "Failures:"
  for f in "${FAILURES[@]}"; do
    printf "  - %s\n" "$f"
  done
  exit 1
fi
exit 0
