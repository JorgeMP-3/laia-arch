#!/usr/bin/env bash
# Verifies setup-prod-dirs follows the v2 canonical /srv/laia layout without
# touching the real /srv/laia on developer hosts.
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
SCRIPT="$LAIA_ROOT/infra/scripts/setup-prod-dirs.sh"

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

mode_of() {
  stat -c '%a' "$1" 2>/dev/null || printf 'missing'
}

TMPDIR_TEST="$(mktemp -d "${TMPDIR:-/tmp}/laia-setup-prod-dirs.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

SRV_ROOT="$TMPDIR_TEST/srv/laia"
export LAIA_SRV_DIR_OVERRIDE="$SRV_ROOT"
export LAIA_USER="$(id -un)"
export NO_COLOR=1

echo "→ setup-prod-dirs canonical v2 layout"
if bash "$SCRIPT" >"$TMPDIR_TEST/run1.out" 2>&1; then
  assert "setup-prod-dirs exits 0 with override" 0
else
  assert "setup-prod-dirs exits 0 with override" 1
fi

for d in state arch agora agora/frontend users backups backups/state backups/workspace backups/snapshots; do
  assert "$SRV_ROOT/$d exists" "$([[ -d "$SRV_ROOT/$d" ]] && echo 0 || echo 1)"
done

assert "canonical users dir mode is 0750" \
  "$([[ "$(mode_of "$SRV_ROOT/users")" == "750" ]] && echo 0 || echo 1)"
assert "ARCH secrets dir mode is 0700" \
  "$([[ "$(mode_of "$SRV_ROOT/arch/secrets")" == "700" ]] && echo 0 || echo 1)"
assert "legacy agents dir is not created" \
  "$([[ ! -e "$SRV_ROOT/agents" ]] && echo 0 || echo 1)"
assert "script output mentions /users" \
  "$(grep -qF "$SRV_ROOT/users" "$TMPDIR_TEST/run1.out" && echo 0 || echo 1)"
assert "script output does not mention /agents" \
  "$(! grep -qF "$SRV_ROOT/agents" "$TMPDIR_TEST/run1.out" && echo 0 || echo 1)"

echo
echo "→ setup-prod-dirs is idempotent"
if bash "$SCRIPT" >"$TMPDIR_TEST/run2.out" 2>&1; then
  assert "second setup-prod-dirs run exits 0" 0
else
  assert "second setup-prod-dirs run exits 0" 1
fi
assert "legacy agents dir still absent after second run" \
  "$([[ ! -e "$SRV_ROOT/agents" ]] && echo 0 || echo 1)"

echo
echo "═══════════════════════════════════════════════════"
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  echo
  echo "Failures:"
  for f in "${FAILURES[@]}"; do
    printf "  - %s\n" "$f"
  done
  echo
  echo "First run output:"
  cat "$TMPDIR_TEST/run1.out" 2>/dev/null || true
  exit 1
fi
exit 0
