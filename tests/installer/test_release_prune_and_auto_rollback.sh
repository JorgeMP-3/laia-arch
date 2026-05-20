#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# tests/installer/test_release_prune_and_auto_rollback.sh
#
# Covers two release-only behaviours:
#
# (A) --prune --keep N:
#     Install v1, release v2, v3, v4, v5, then release v6 with --prune --keep 2.
#     Expected: v6 (current) + the 2 newest others (v5, v4) are kept; v1, v2, v3
#     are deleted.
#
# (B) Auto-rollback on healthcheck failure:
#     With v1 active, run laia-release v2 plus LAIA_FORCE_HEALTHCHECK_FAIL=1.
#     Expected: v2 dir gets built, symlink briefly switches to v2, healthcheck
#     fails, symlink is rolled back to v1, the release script exits non-zero,
#     and v2 directory remains on disk for inspection.
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

run_silent() {
  local label="$1"; shift
  local log="$TMPDIR_TEST/${label}.log"
  if ! "$@" >"$log" 2>&1; then
    echo "✗ $label failed — log:"
    cat "$log"
    exit 1
  fi
}

# ── Tmpdir + overrides ─────────────────────────────────────────────────────
TMPDIR_TEST="$(mktemp -d "${HOME}/laia-release-extra.XXXXXX")"
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
ROOT="$TMPDIR_TEST/opt"

# ──────────────────────────────────────────────────────────────────────────
# (A) --prune --keep N
# ──────────────────────────────────────────────────────────────────────────
echo "=== (A) --prune --keep 2 ============================================"

# Initial install v0.1.0
run_silent install_v1 "$BIN/laia-install" \
  --from-local "$LAIA_ROOT" --version v0.1.0 \
  --skip-pip --skip-frontend --yes

# A few releases without --prune
for v in v0.2.0 v0.3.0 v0.4.0 v0.5.0; do
  run_silent "release_$v" "$BIN/laia-release" \
    --version "$v" --allow-dirty --force \
    --skip-tests --skip-pip --skip-frontend --yes \
    "$LAIA_ROOT"
done

assert "before prune: all 5 versions exist" \
  "$([[ -d $ROOT/laia-v0.1.0 && -d $ROOT/laia-v0.2.0 && -d $ROOT/laia-v0.3.0 \
       && -d $ROOT/laia-v0.4.0 && -d $ROOT/laia-v0.5.0 ]] && echo 0 || echo 1)"

# Release v0.6.0 with --prune --keep 2.
# Expected keep set: v0.6.0 (current) + the 2 newest others among
# {v0.1.0..v0.5.0} which are v0.5.0 and v0.4.0. So v0.1.0, v0.2.0, v0.3.0
# should be removed.
run_silent release_prune "$BIN/laia-release" \
  --version v0.6.0 --allow-dirty --force \
  --skip-tests --skip-pip --skip-frontend --yes \
  --prune --keep 2 \
  "$LAIA_ROOT"

assert "after prune: v0.6.0 (current) kept" \
  "$([[ -d "$ROOT/laia-v0.6.0" ]] && echo 0 || echo 1)"
assert "after prune: v0.5.0 kept" \
  "$([[ -d "$ROOT/laia-v0.5.0" ]] && echo 0 || echo 1)"
assert "after prune: v0.4.0 kept" \
  "$([[ -d "$ROOT/laia-v0.4.0" ]] && echo 0 || echo 1)"
assert "after prune: v0.3.0 REMOVED" \
  "$([[ ! -d "$ROOT/laia-v0.3.0" ]] && echo 0 || echo 1)"
assert "after prune: v0.2.0 REMOVED" \
  "$([[ ! -d "$ROOT/laia-v0.2.0" ]] && echo 0 || echo 1)"
assert "after prune: v0.1.0 REMOVED" \
  "$([[ ! -d "$ROOT/laia-v0.1.0" ]] && echo 0 || echo 1)"
assert "symlink still resolves to v0.6.0" \
  "$([[ "$(readlink "$SYMLINK")" == "laia-v0.6.0" ]] && echo 0 || echo 1)"

# Idempotency: re-running prune when nothing exceeds the keep budget should be a no-op.
run_silent release_prune_noop "$BIN/laia-release" \
  --version v0.6.0 --allow-dirty --force \
  --skip-tests --skip-pip --skip-frontend --yes \
  --prune --keep 5 \
  "$LAIA_ROOT"
assert "re-prune with larger --keep budget: nothing else removed" \
  "$([[ -d "$ROOT/laia-v0.5.0" && -d "$ROOT/laia-v0.4.0" && -d "$ROOT/laia-v0.6.0" ]] && echo 0 || echo 1)"

# ──────────────────────────────────────────────────────────────────────────
# (B) Auto-rollback on healthcheck failure
# ──────────────────────────────────────────────────────────────────────────
echo
echo "=== (B) Auto-rollback on healthcheck failure ========================="

# Fresh tmpdir for clarity: continue in the same one, but record current state.
# We'll do: clean up everything except v0.6.0 first, then release v0.7.0 with
# LAIA_FORCE_HEALTHCHECK_FAIL=1 and assert symlink rolled back to v0.6.0.
rm -rf "$ROOT"/laia-v0.4.0 "$ROOT"/laia-v0.5.0   # narrow the test surface

PREV_BEFORE="$(readlink "$SYMLINK")"
[[ "$PREV_BEFORE" == "laia-v0.6.0" ]] || {
  echo "✗ pre-(B) state wrong: symlink is $PREV_BEFORE, expected laia-v0.6.0"
  exit 1
}

# Run the failing release and capture exit code.
set +e
LAIA_FORCE_HEALTHCHECK_FAIL=1 "$BIN/laia-release" \
  --version v0.7.0 --allow-dirty --force \
  --skip-tests --skip-pip --skip-frontend --yes \
  "$LAIA_ROOT" >"$TMPDIR_TEST/release_fail.log" 2>&1
rc=$?
set -e

assert "failing release exits non-zero (got $rc)" \
  "$([[ "$rc" -ne 0 ]] && echo 0 || echo 1)"
assert "symlink rolled back to v0.6.0" \
  "$([[ "$(readlink "$SYMLINK")" == "laia-v0.6.0" ]] && echo 0 || echo 1)"
assert "v0.7.0 directory still on disk (kept for forensic inspection)" \
  "$([[ -d "$ROOT/laia-v0.7.0" ]] && echo 0 || echo 1)"
assert "release log mentions 'rolling back'" \
  "$(grep -qi 'rolling back' "$TMPDIR_TEST/release_fail.log" && echo 0 || echo 1)"
assert "release log mentions auto-rollback target" \
  "$(grep -qF 'v0.6.0' "$TMPDIR_TEST/release_fail.log" && echo 0 || echo 1)"

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
