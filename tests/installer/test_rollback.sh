#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# tests/installer/test_rollback.sh
#
# Verifies laia-rollback:
#   - Install v_a, release v_b, rollback (no args) → back to v_a via .previous.
#   - After rollback, .previous now points to v_b.
#   - Subsequent rollback (no args) bounces back to v_b.
#   - Explicit `rollback v_a` works.
#   - --list shows the current version marked + previous hint.
#   - Asking to roll back to the currently-active version aborts cleanly.
#   - Asking to roll back to a non-installed version aborts cleanly.
# ─────────────────────────────────────────────────────────────────────────────
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
BIN="$LAIA_ROOT/bin"

PASS=0
FAIL=0
FAILURES=()

assert() {
  local desc="$1" status="$2"
  if [[ "$status" == "0" ]]; then
    PASS=$((PASS + 1))
    printf '  ✓ %s\n' "$desc"
  else
    FAIL=$((FAIL + 1))
    FAILURES+=("$desc")
    printf '  ✗ %s\n' "$desc"
  fi
}

# ── Tmpdir + overrides ─────────────────────────────────────────────────────
TMPDIR_TEST="$(mktemp -d "${HOME}/laia-rollback.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

export LAIA_INSTALL_ROOT_OVERRIDE="$TMPDIR_TEST/opt"
export LAIA_BIN_DIR_OVERRIDE="$TMPDIR_TEST/usr-local-bin"
export LAIA_HOME_OVERRIDE="$TMPDIR_TEST/LAIA-ARCH"
export LAIA_SYSTEMD_DIR_OVERRIDE="$TMPDIR_TEST/systemd"
export LAIA_SHELL_RC_OVERRIDE="$TMPDIR_TEST/bashrc-test"
export LAIA_LOG_FILE="$TMPDIR_TEST/run.log"
export NO_COLOR=1

mkdir -p "$LAIA_INSTALL_ROOT_OVERRIDE"
: >"$LAIA_SHELL_RC_OVERRIDE"

SYMLINK="$TMPDIR_TEST/opt/laia"
PREV_FILE="$SYMLINK.previous"

VER_A="v0.0.0-a"
VER_B="v0.0.0-b"

run_silent() {
  local label="$1"; shift
  local log="$TMPDIR_TEST/${label}.log"
  if ! "$@" >"$log" 2>&1; then
    echo "✗ $label failed — log:"
    cat "$log"
    exit 1
  fi
}

# ── Setup: install v_a + release v_b ───────────────────────────────────────
echo "→ Setup: install $VER_A, then release $VER_B"
run_silent install_a "$BIN/laia-install" \
  --from-local "$LAIA_ROOT" --version "$VER_A" \
  --skip-pip --skip-frontend --yes

run_silent release_b "$BIN/laia-release" \
  --version "$VER_B" --allow-dirty \
  --skip-tests --skip-pip --skip-frontend --yes \
  "$LAIA_ROOT"

assert "after setup: symlink → v_b" \
  "$([[ "$(readlink "$SYMLINK")" == "laia-$VER_B" ]] && echo 0 || echo 1)"
assert "after setup: .previous == v_a" \
  "$([[ "$(cat "$PREV_FILE" 2>/dev/null)" == "$VER_A" ]] && echo 0 || echo 1)"

# ── Test 1: rollback (no args) uses .previous ──────────────────────────────
echo
echo "→ Test 1: laia-rollback (no args) → resolves to v_a via .previous"
run_silent rollback1 "$BIN/laia-rollback" --yes

assert "symlink moved to v_a" \
  "$([[ "$(readlink "$SYMLINK")" == "laia-$VER_A" ]] && echo 0 || echo 1)"
assert ".previous now contains v_b (the version we rolled FROM)" \
  "$([[ "$(cat "$PREV_FILE" 2>/dev/null)" == "$VER_B" ]] && echo 0 || echo 1)"

# ── Test 2: rollback again bounces forward to v_b ──────────────────────────
echo
echo "→ Test 2: another rollback bounces back to v_b"
run_silent rollback2 "$BIN/laia-rollback" --yes

assert "symlink moved back to v_b" \
  "$([[ "$(readlink "$SYMLINK")" == "laia-$VER_B" ]] && echo 0 || echo 1)"
assert ".previous now contains v_a again" \
  "$([[ "$(cat "$PREV_FILE" 2>/dev/null)" == "$VER_A" ]] && echo 0 || echo 1)"

# ── Test 3: explicit target ────────────────────────────────────────────────
echo
echo "→ Test 3: explicit rollback target"
run_silent rollback3 "$BIN/laia-rollback" --yes "$VER_A"

assert "explicit rollback v_a → symlink at v_a" \
  "$([[ "$(readlink "$SYMLINK")" == "laia-$VER_A" ]] && echo 0 || echo 1)"

# ── Test 4: --list shows both with current marker ──────────────────────────
echo
echo "→ Test 4: --list output"
list_out="$("$BIN/laia-rollback" --list 2>&1)"
assert "--list mentions v_a" \
  "$(grep -qF "$VER_A" <<<"$list_out" && echo 0 || echo 1)"
assert "--list mentions v_b" \
  "$(grep -qF "$VER_B" <<<"$list_out" && echo 0 || echo 1)"
assert "--list marks current with (current)" \
  "$(grep -q '(current)' <<<"$list_out" && echo 0 || echo 1)"
assert "--list shows previous hint" \
  "$(grep -q 'Previous' <<<"$list_out" && echo 0 || echo 1)"

# ── Test 5: rollback to current → must abort ───────────────────────────────
echo
echo "→ Test 5: rollback to currently-active version aborts"
if "$BIN/laia-rollback" --yes "$VER_A" >/dev/null 2>&1; then
  assert "rollback to current refuses (got 0, expected nonzero)" "1"
else
  assert "rollback to current refuses with nonzero exit" "0"
fi

# ── Test 6: rollback to nonexistent version → must abort ───────────────────
echo
echo "→ Test 6: rollback to nonexistent version aborts"
if "$BIN/laia-rollback" --yes "v9.9.9-missing" >/dev/null 2>&1; then
  assert "rollback to missing version refuses (got 0, expected nonzero)" "1"
else
  assert "rollback to missing version refuses with nonzero exit" "0"
fi

# ── Test 7: dry-run does NOT mutate ────────────────────────────────────────
echo
echo "→ Test 7: dry-run is non-mutating"
pre_target="$(readlink "$SYMLINK")"
pre_prev="$(cat "$PREV_FILE" 2>/dev/null || true)"
"$BIN/laia-rollback" --dry-run --yes >/dev/null 2>&1
assert "dry-run did not change symlink" \
  "$([[ "$(readlink "$SYMLINK")" == "$pre_target" ]] && echo 0 || echo 1)"
assert "dry-run did not change .previous" \
  "$([[ "$(cat "$PREV_FILE" 2>/dev/null || true)" == "$pre_prev" ]] && echo 0 || echo 1)"

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
  echo
  echo "Logs in: $TMPDIR_TEST"
  exit 1
fi
exit 0
