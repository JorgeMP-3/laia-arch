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
# Sudo clone must not leave root-owned HOME control artifacts
# ---------------------------------------------------------------------------

echo
echo "→ sudo clone leaves resume markers user-owned and staging clean"
if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
  SUDO_CLONE_DIR="$TMPDIR_TEST/sudo-clone"
  SUDO_SRC="$SUDO_CLONE_DIR/source"
  SUDO_DEST="$SUDO_CLONE_DIR/dest"
  mkdir -p "$SUDO_SRC/LAIA-ARCH" \
           "$SUDO_SRC/users/jorge/home" \
           "$SUDO_SRC/agora" \
           "$SUDO_SRC/home/.laia" \
           "$SUDO_DEST"
  printf 'SOUL\n' >"$SUDO_SRC/LAIA-ARCH/SOUL.md"
  printf 'file\n' >"$SUDO_SRC/users/jorge/home/file.txt"
  printf 'auth\n' >"$SUDO_SRC/home/.laia/auth.json"

  out=$(
    sudo -n env \
      LAIA_HOME_OVERRIDE="$SUDO_DEST/LAIA-ARCH" \
      LAIA_USERS_DIR_OVERRIDE="$SUDO_DEST/srv-users" \
      LAIA_AGORA_DIR_OVERRIDE="$SUDO_DEST/agora" \
      LAIA_ARCH_DIR_OVERRIDE="$SUDO_DEST/arch" \
      LAIA_ARCH_CREDS_DIR_OVERRIDE="$SUDO_DEST/creds" \
      LAIA_TOOLS_HOME_OVERRIDE="$SUDO_DEST/tools-home" \
      LAIA_INSTALL_ROOT_OVERRIDE="$SUDO_DEST/opt" \
      LAIA_LOG_FILE="$SUDO_CLONE_DIR/run.log" \
      NO_COLOR=1 \
      "$LAIA_ROOT/bin/laia-clone" --source-dir "$SUDO_SRC" --yes --no-lxd \
      2>&1
  )
  rc=$?
  if [[ $rc -ne 0 ]]; then
    printf '%s\n' "$out" >&2
    assert "sudo laia-clone fixture exits 0" 1
  else
    assert "sudo laia-clone fixture exits 0" 0

    owner_bad=0
    while IFS= read -r marker; do
      [[ -z "$marker" ]] && continue
      [[ "$(stat -c '%U' "$marker")" == "$(id -un)" ]] || owner_bad=1
    done < <(find "$SUDO_DEST/LAIA-ARCH/.clone-state" -type f -name '*.done' 2>/dev/null | sort)
    assert "sudo clone .clone-state markers are owned by invoking user" "$owner_bad"

    if [[ -e "$HOME/.laia-clone-stage" ]]; then
      assert "sudo clone leaves no staging dir in HOME on success" 1
    else
      assert "sudo clone leaves no staging dir in HOME on success" 0
    fi
  fi
else
  echo "  (sudo -n unavailable — skipping sudo clone ownership block)"
fi

echo
echo "→ staging helper cleans transient stage and preserves user ownership on failure"
stage_out=$(
  bash -c '
    set -e
    export LAIA_ROOT="'"$LAIA_ROOT"'"
    export LAIA_USER="$(id -un)"
    export LAIA_USER_HOME="'"$TMPDIR_TEST"'/stage-home"
    source "'"$LAIA_ROOT"'/infra/installer/lib/common.sh"
    inst_is_override_mode() { return 0; }
    source "'"$LAIA_ROOT"'/infra/installer/lib/clone.sh"
    stage="$LAIA_USER_HOME/.laia-clone-stage/users"
    clone_stage_prepare "$stage"
    [[ -d "$stage" ]] || echo "BUG: stage not created"
    clone_home_artifact_restore_owner "$stage"
    [[ "$(stat -c "%U" "$stage")" == "$LAIA_USER" ]] || echo "BUG: stage not user-owned"
    clone_stage_cleanup "$stage"
    [[ ! -e "$LAIA_USER_HOME/.laia-clone-stage" ]] || echo "BUG: stage root not removed"
    echo "ok"
  ' 2>&1
)
if grep -q "BUG:" <<<"$stage_out"; then
  printf '%s\n' "$stage_out" | grep "BUG:" >&2
  assert "stage helper ownership/cleanup behavior" 1
else
  assert "stage helper ownership/cleanup behavior" 0
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
