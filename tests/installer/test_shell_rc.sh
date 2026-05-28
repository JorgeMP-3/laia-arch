#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# tests/installer/test_shell_rc.sh
#
# Verifies the idempotent block management in shell_rc.sh:
#   - Apply on a fresh rc file → adds one block, preserves prior content.
#   - Apply twice → still exactly one block (no duplicates).
#   - Apply with a different LAIA_HOME → replaces the value, still one block.
#   - Remove → strips the block without touching surrounding lines.
#
# Uses LAIA_SHELL_RC_OVERRIDE to redirect writes to a tmpfile. No sudo.
# ─────────────────────────────────────────────────────────────────────────────
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
LIB="$LAIA_ROOT/infra/installer/lib"

# Suppress install log noise from log_info etc.
export LAIA_LOG_FILE="$(mktemp)"

# Quiet color codes so grep assertions are simpler.
export NO_COLOR=1

# shellcheck source=../../infra/installer/lib/common.sh
source "$LIB/common.sh"
# shellcheck source=../../infra/installer/lib/sudo.sh
source "$LIB/sudo.sh"

RC_FILE="$(mktemp)"
export LAIA_SHELL_RC_OVERRIDE="$RC_FILE"
trap 'rm -f "$RC_FILE" "$LAIA_LOG_FILE"' EXIT

# shellcheck source=../../infra/installer/lib/shell_rc.sh
source "$LIB/shell_rc.sh"

PASS=0
FAIL=0
FAILURES=()

assert() {
  local desc="$1" cond_status="$2"
  if [[ "$cond_status" == "0" ]]; then
    PASS=$((PASS + 1))
    printf '  ✓ %s\n' "$desc"
  else
    FAIL=$((FAIL + 1))
    FAILURES+=("$desc")
    printf '  ✗ %s\n' "$desc"
  fi
}

count_marker() {
  # grep -c prints "0" and exits 1 when no matches; mask the exit and let the
  # printed count flow through unchanged.
  local n
  n="$(grep -c '^# >>> laia >>>$' "$RC_FILE" 2>/dev/null)" || true
  printf '%s\n' "${n:-0}"
}

# ── Test 1: fresh file with prior content ──────────────────────────────────
echo "→ Test 1: apply on a fresh file"

cat >"$RC_FILE" <<'EOF'
# user's existing shell rc
export PATH="$HOME/bin:$PATH"
alias ll='ls -la'
EOF

shell_rc_apply "/home/test-user/LAIA-ARCH" >/dev/null 2>&1
status=$?
assert "apply succeeds" "$status"
assert "exactly one LAIA block present" "$([[ "$(count_marker)" == "1" ]] && echo 0 || echo 1)"
assert "LAIA_HOME has the expected value" \
  "$(grep -q 'export LAIA_HOME="/home/test-user/LAIA-ARCH"' "$RC_FILE" && echo 0 || echo 1)"
assert "pre-existing PATH line preserved" \
  "$(grep -q 'export PATH="\$HOME/bin:\$PATH"' "$RC_FILE" && echo 0 || echo 1)"
assert "pre-existing alias preserved" \
  "$(grep -q "alias ll='ls -la'" "$RC_FILE" && echo 0 || echo 1)"
assert "end marker present" \
  "$(grep -q '^# <<< laia <<<$' "$RC_FILE" && echo 0 || echo 1)"

# ── Test 2: re-apply with same value → still one block ─────────────────────
echo
echo "→ Test 2: apply twice with same value (idempotency)"

shell_rc_apply "/home/test-user/LAIA-ARCH" >/dev/null 2>&1
assert "exactly one LAIA block after second apply" \
  "$([[ "$(count_marker)" == "1" ]] && echo 0 || echo 1)"

# ── Test 3: re-apply with different value → block updated, not duplicated ──
echo
echo "→ Test 3: apply with a different LAIA_HOME"

shell_rc_apply "/srv/laia-different" >/dev/null 2>&1
assert "still exactly one LAIA block" \
  "$([[ "$(count_marker)" == "1" ]] && echo 0 || echo 1)"
assert "new LAIA_HOME present" \
  "$(grep -q 'export LAIA_HOME="/srv/laia-different"' "$RC_FILE" && echo 0 || echo 1)"
assert "old LAIA_HOME removed" \
  "$(! grep -q '/home/test-user/LAIA-ARCH' "$RC_FILE" && echo 0 || echo 1)"
assert "user content still preserved" \
  "$(grep -q "alias ll='ls -la'" "$RC_FILE" && echo 0 || echo 1)"

# ── Test 4: remove block ───────────────────────────────────────────────────
echo
echo "→ Test 4: remove the LAIA block"

shell_rc_remove >/dev/null 2>&1
assert "no LAIA begin marker after remove" \
  "$([[ "$(count_marker)" == "0" ]] && echo 0 || echo 1)"
assert "no LAIA end marker after remove" \
  "$(! grep -q '^# <<< laia <<<$' "$RC_FILE" && echo 0 || echo 1)"
assert "user PATH still preserved after remove" \
  "$(grep -q 'export PATH="\$HOME/bin:\$PATH"' "$RC_FILE" && echo 0 || echo 1)"
assert "no LAIA_HOME left over" \
  "$(! grep -q 'LAIA_HOME' "$RC_FILE" && echo 0 || echo 1)"

# ── Test 5: remove on a file without the block is a no-op ──────────────────
echo
echo "→ Test 5: remove on file without block is a no-op"

cat >"$RC_FILE" <<'EOF'
export PATH="$HOME/bin:$PATH"
EOF
original_md5="$(md5sum "$RC_FILE" | awk '{print $1}')"
shell_rc_remove >/dev/null 2>&1
new_md5="$(md5sum "$RC_FILE" | awk '{print $1}')"
assert "file unchanged when no block present" \
  "$([[ "$original_md5" == "$new_md5" ]] && echo 0 || echo 1)"

# ── Test 6: apply on an empty file ─────────────────────────────────────────
echo
echo "→ Test 6: apply on an empty file"

: >"$RC_FILE"
shell_rc_apply "/srv/empty-test" >/dev/null 2>&1
assert "exactly one block on previously empty file" \
  "$([[ "$(count_marker)" == "1" ]] && echo 0 || echo 1)"
assert "LAIA_HOME present" \
  "$(grep -q 'LAIA_HOME="/srv/empty-test"' "$RC_FILE" && echo 0 || echo 1)"

# ── Test 7: apply preserves the rc file mode (not clobbered by mktemp 0600) ──
echo
echo "→ Test 7: apply preserves rc mode"

cat >"$RC_FILE" <<'EOF'
export PATH="$HOME/bin:$PATH"
EOF
chmod 644 "$RC_FILE"
shell_rc_apply "/srv/mode-test" >/dev/null 2>&1
mode_after="$(stat -c '%a' "$RC_FILE" 2>/dev/null)"
assert "mode stays 644 after apply (mv would leave 600)" \
  "$([[ "$mode_after" == "644" ]] && echo 0 || echo 1)"

# ── Summary ────────────────────────────────────────────────────────────────
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
