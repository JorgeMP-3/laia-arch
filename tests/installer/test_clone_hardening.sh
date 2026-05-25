#!/usr/bin/env bash
# Hardening tests for the cloner — covers the new behaviors landed in
# the pre-Fase-5 audit fixes:
#   * Phase markers (clone_phase_mark_start / clone_phase_mark_done /
#     clone_phase_should_skip).
#   * SSH connect timeout honors LAIA_SSH_TIMEOUT.
#   * fact_reset_imported_admin_password schema validation dies cleanly
#     on incompatible DBs.
#   * SSHPASS handled via -f file, never via env (regression guard for
#     the security fix).
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
PASS=0; FAIL=0; FAILURES=()
assert() {
  local desc="$1" rc="$2"
  if [[ "$rc" == 0 ]]; then PASS=$((PASS+1)); printf '  ✓ %s\n' "$desc"
  else FAIL=$((FAIL+1)); FAILURES+=("$desc"); printf '  ✗ %s\n' "$desc"; fi
}

# ---------------------------------------------------------------------------
# Phase markers
# ---------------------------------------------------------------------------

echo "→ Phase marker primitives (mark_start / mark_done / should_skip)"
TMPDIR_TEST="$(mktemp -d "${TMPDIR:-/tmp}/laia-marker-test.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

# Source common.sh + clone.sh in a subshell so we can call the helpers.
# We stub clone_dest_laia_home to point at our tmp dir.
out=$(
  bash -c '
    set -e
    export LAIA_ROOT="'"$LAIA_ROOT"'"
    source "'"$LAIA_ROOT"'/infra/installer/lib/common.sh"
    # Minimal stubs the clone.sh source order expects:
    inst_is_override_mode() { return 0; }
    clone_dest_laia_home() { printf "%s\n" "'"$TMPDIR_TEST"'"; }
    source "'"$LAIA_ROOT"'/infra/installer/lib/clone.sh"

    # Initial state: no marker.
    OPT_RESUME=true
    clone_phase_should_skip "phase-x" && echo "BUG: should_skip true with no marker"

    # Mark done → should_skip returns true.
    clone_phase_mark_done "phase-x"
    clone_phase_should_skip "phase-x" || echo "BUG: should_skip false after mark_done"

    # mark_start clears the marker (preparing for fresh run).
    clone_phase_mark_start "phase-x"
    clone_phase_should_skip "phase-x" && echo "BUG: should_skip true after mark_start"

    # OPT_RESUME=false → should_skip always returns false even if marker exists.
    clone_phase_mark_done "phase-x"
    OPT_RESUME=false
    clone_phase_should_skip "phase-x" && echo "BUG: should_skip true with OPT_RESUME=false"

    # mark_done writes an EMPTY file (content-stable across runs).
    OPT_RESUME=true
    clone_phase_mark_done "phase-y"
    if [[ -s "'"$TMPDIR_TEST"'/.clone-state/phase-y.done" ]]; then
      echo "BUG: mark_done wrote non-empty content (breaks idempotency md5)"
    fi
    echo "ok"
  ' 2>&1
)
if grep -q "BUG:" <<<"$out"; then
  printf '%s\n' "$out" | grep "BUG:" >&2
  assert "phase markers behave correctly" 1
else
  assert "phase markers behave correctly" 0
fi

# ---------------------------------------------------------------------------
# SSH timeout configurable via LAIA_SSH_TIMEOUT
# ---------------------------------------------------------------------------

echo
echo "→ SSH connect timeout reads LAIA_SSH_TIMEOUT (default 15s)"
if grep -q 'ConnectTimeout=$_ssh_timeout' "$LAIA_ROOT/infra/installer/lib/clone.sh"; then
  assert "SSH preflight uses LAIA_SSH_TIMEOUT variable" 0
else
  assert "SSH preflight uses LAIA_SSH_TIMEOUT variable" 1
fi
if grep -q 'LAIA_SSH_TIMEOUT:-15' "$LAIA_ROOT/infra/installer/lib/clone.sh"; then
  assert "SSH preflight default is 15s (was 5s)" 0
else
  assert "SSH preflight default is 15s (was 5s)" 1
fi

# ---------------------------------------------------------------------------
# Admin reset schema validation
# ---------------------------------------------------------------------------

echo
echo "→ fact_reset_imported_admin_password schema validation"
if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "  (sqlite3 missing — skipping schema-validation block)"
else
  BAD_DB_DIR="$TMPDIR_TEST/bad"
  mkdir -p "$BAD_DB_DIR"
  # 1. DB without 'users' table at all.
  sqlite3 "$BAD_DB_DIR/agora.db" "CREATE TABLE other_table (id INTEGER);" 2>/dev/null
  out=$(
    AGORA_DB_PATH="$BAD_DB_DIR/agora.db" \
    LAIA_HOME_OVERRIDE="$BAD_DB_DIR" \
    LAIA_INSTALL_ROOT_OVERRIDE="$BAD_DB_DIR/opt" \
    LAIA_ROOT="$LAIA_ROOT" \
    bash -c '
      source "'"$LAIA_ROOT"'/infra/installer/lib/common.sh"
      source "'"$LAIA_ROOT"'/infra/installer/lib/sudo.sh"
      source "'"$LAIA_ROOT"'/infra/installer/lib/install.sh"
      source "'"$LAIA_ROOT"'/infra/installer/lib/factory.sh"
      fact_reset_imported_admin_password
    ' 2>&1
  )
  rc=$?
  if [[ $rc -eq 6 ]] && grep -q "no 'users' table\|missing required column" <<<"$out"; then
    assert "missing users table dies with exit 6 + clear message" 0
  else
    assert "missing users table dies with exit 6 + clear message (got rc=$rc)" 1
  fi

  # 2. DB with users table but missing 'password' column.
  WORSE_DB_DIR="$TMPDIR_TEST/worse"
  mkdir -p "$WORSE_DB_DIR"
  sqlite3 "$WORSE_DB_DIR/agora.db" \
    "CREATE TABLE users (id TEXT, username TEXT, active INTEGER);" 2>/dev/null
  out=$(
    AGORA_DB_PATH="$WORSE_DB_DIR/agora.db" \
    LAIA_HOME_OVERRIDE="$WORSE_DB_DIR" \
    LAIA_INSTALL_ROOT_OVERRIDE="$WORSE_DB_DIR/opt" \
    LAIA_ROOT="$LAIA_ROOT" \
    bash -c '
      source "'"$LAIA_ROOT"'/infra/installer/lib/common.sh"
      source "'"$LAIA_ROOT"'/infra/installer/lib/sudo.sh"
      source "'"$LAIA_ROOT"'/infra/installer/lib/install.sh"
      source "'"$LAIA_ROOT"'/infra/installer/lib/factory.sh"
      fact_reset_imported_admin_password
    ' 2>&1
  )
  rc=$?
  if [[ $rc -eq 6 ]] && grep -q "missing required column 'password'" <<<"$out"; then
    assert "users without password column dies with exit 6" 0
  else
    assert "users without password column dies with exit 6 (got rc=$rc)" 1
  fi
fi

# ---------------------------------------------------------------------------
# SSHPASS never exported to env (regression guard for security fix)
# ---------------------------------------------------------------------------

echo
echo "→ SSHPASS never exported to environment (security regression guard)"
if grep -E "^[[:space:]]*export[[:space:]]+SSHPASS[[:space:]]*$" "$LAIA_ROOT/bin/laia-clone" >/dev/null 2>&1; then
  assert "bin/laia-clone does NOT export SSHPASS" 1
else
  assert "bin/laia-clone does NOT export SSHPASS" 0
fi
if grep -q "sshpass -e ssh" "$LAIA_ROOT/infra/installer/lib/clone.sh"; then
  assert "clone.sh does NOT use sshpass -e" 1
else
  assert "clone.sh does NOT use sshpass -e" 0
fi
if grep -q 'sshpass -f' "$LAIA_ROOT/infra/installer/lib/clone.sh"; then
  assert "clone.sh uses sshpass -f <file>" 0
else
  assert "clone.sh uses sshpass -f <file>" 1
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
