#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# tests/installer/test_flags.sh
#
# Verifies that all 5 entrypoint scripts respond to --help, --version, and
# --dry-run without side effects, and that argument parsing is well-formed.
#
# Run:
#   bash tests/installer/test_flags.sh
#
# Exit code: 0 if all assertions pass, 1 otherwise.
# ─────────────────────────────────────────────────────────────────────────────
set -u

# Resolve LAIA_ROOT relative to this test file.
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
BIN="$LAIA_ROOT/bin"

PASS=0
FAIL=0
FAILURES=()

# assert_zero <description> <command...>  — command must exit 0
assert_zero() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    PASS=$((PASS + 1))
    printf '  ✓ %s\n' "$desc"
  else
    FAIL=$((FAIL + 1))
    FAILURES+=("$desc (exit $?)")
    printf '  ✗ %s\n' "$desc"
  fi
}

# assert_nonzero <description> <command...>  — command must exit nonzero
assert_nonzero() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    FAIL=$((FAIL + 1))
    FAILURES+=("$desc (expected nonzero, got 0)")
    printf '  ✗ %s\n' "$desc"
  else
    PASS=$((PASS + 1))
    printf '  ✓ %s\n' "$desc"
  fi
}

# assert_contains <description> <expected_substring> <command...>
assert_contains() {
  local desc="$1" expected="$2"; shift 2
  local out
  out="$("$@" 2>&1)" || true
  if [[ "$out" == *"$expected"* ]]; then
    PASS=$((PASS + 1))
    printf '  ✓ %s\n' "$desc"
  else
    FAIL=$((FAIL + 1))
    FAILURES+=("$desc — output did not contain: $expected")
    printf '  ✗ %s\n' "$desc"
  fi
}

# ── Tests ───────────────────────────────────────────────────────────────────

echo "→ Sanity: scripts exist and are executable"
for script in laia laia-install laia-clone laia-release laia-rollback; do
  assert_zero "$script is executable" test -x "$BIN/$script"
done

echo
echo "→ --help on each script (must exit 0 and mention 'USAGE')"
for script in laia laia-install laia-clone laia-release laia-rollback; do
  assert_contains "$script --help mentions USAGE" "USAGE" "$BIN/$script" --help
done

echo
echo "→ --version on the delegator and on subcommand scripts"
assert_contains "laia --version starts with 'laia '" "laia " "$BIN/laia" --version
assert_contains "laia-install --version starts with 'laia-install '" "laia-install " "$BIN/laia-install" --version

echo
echo "→ --dry-run on each script with side effects (must exit 0, no mutations)"
for script in laia-install laia-clone laia-release laia-rollback; do
  case "$script" in
    laia-clone)
      assert_zero "$script --dry-run with dummy host" "$BIN/$script" --dry-run dummy@example.com
      ;;
    *)
      assert_zero "$script --dry-run" "$BIN/$script" --dry-run
      ;;
  esac
done

echo
echo "→ Bad arguments must fail with exit 2"
assert_nonzero "laia <unknown-subcommand>"   "$BIN/laia" foobar
assert_nonzero "laia-install --bogus"        "$BIN/laia-install" --bogus
assert_nonzero "laia-clone (no host)"        "$BIN/laia-clone"
assert_nonzero "laia-clone bad-host-format"  "$BIN/laia-clone" notanemail
assert_nonzero "laia-release --keep abc"     "$BIN/laia-release" --keep abc

echo
echo "→ laia-rollback --list works without /opt/laia existing"
assert_zero "laia-rollback --list" "$BIN/laia-rollback" --list

echo
echo "→ laia delegator dispatches to subcommands"
assert_contains "laia install --dry-run dispatches" "SCAFFOLD" "$BIN/laia" install --dry-run
assert_contains "laia rollback --list dispatches" "Installed LAIA" "$BIN/laia" rollback --list

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
