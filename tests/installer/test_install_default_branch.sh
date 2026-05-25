#!/usr/bin/env bash
# Regression coverage for the curl|bash installer branch contract.
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
BOOT="$LAIA_ROOT/install.sh"

PASS=0
FAIL=0
FAILURES=()

ok() {
  PASS=$((PASS + 1))
  printf '  ok: %s\n' "$1"
}

fail() {
  FAIL=$((FAIL + 1))
  FAILURES+=("$1")
  printf '  fail: %s\n' "$1"
}

assert_contains() {
  local desc="$1" needle="$2" haystack="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    ok "$desc"
  else
    fail "$desc"
  fi
}

assert_not_contains() {
  local desc="$1" needle="$2" haystack="$3"
  if [[ "$haystack" != *"$needle"* ]]; then
    ok "$desc"
  else
    fail "$desc"
  fi
}

bootstrap_lib="$(mktemp)"
trap 'rm -f "$bootstrap_lib"' EXIT
sed '/^main "\$@"/,$d' "$BOOT" >"$bootstrap_lib"

echo "-> installer default branch contract"

source_text="$(cat "$BOOT")"
assert_contains "DEFAULT_BRANCH points at stable" 'DEFAULT_BRANCH="stable"' "$source_text"
assert_contains "help documents branch override" "--branch BRANCH" "$source_text"
assert_contains "LAIA_BRANCH defaults from DEFAULT_BRANCH" \
  'LAIA_BRANCH="${LAIA_BRANCH:-$DEFAULT_BRANCH}"' "$source_text"
assert_not_contains "bootstrap comments no longer advertise feat/installer-wizard" \
  "raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-wizard/install.sh" \
  "$source_text"

echo
echo "-> --branch still overrides default"

override_output="$(
  bash -c "
    source '$bootstrap_lib'
    parse_args --branch main --mode install --yes
    printf 'BRANCH:%s\n' \"\$LAIA_BRANCH\"
    printf 'PRESERVE:%s\n' \"\$OPT_PRESERVE_BRANCH\"
  "
)"

assert_contains "--branch sets LAIA_BRANCH" "BRANCH:main" "$override_output"
assert_contains "--branch marks branch as explicit" "PRESERVE:true" "$override_output"

echo
printf 'PASS: %d FAIL: %d\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  printf 'Failures:\n'
  for failure in "${FAILURES[@]}"; do
    printf '  - %s\n' "$failure"
  done
  exit 1
fi
exit 0
