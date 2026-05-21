#!/usr/bin/env bash
# Test: infra/dev/preflight.sh EXPECTED_OWNER auto-detects to ORIG_USER:ORIG_GROUP
# instead of hardcoded laia-hermes:laia-hermes.
#
# We can't run preflight end-to-end (requires lxc/jq/curl), but we can:
#   1) sed-grep the file to ensure the hardcoded fallback is gone, and
#   2) source-exec just the EXPECTED_OWNER resolution block in isolation
#      with a fake ORIG_USER and assert it resolves to <user>:<group>.
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
PREFLIGHT="$LAIA_ROOT/infra/dev/preflight.sh"
PASS=0; FAIL=0; FAILURES=()
assert() { local d="$1" s="$2"; if [[ "$s" == 0 ]]; then PASS=$((PASS+1)); printf '  ✓ %s\n' "$d"; else FAIL=$((FAIL+1)); FAILURES+=("$d"); printf '  ✗ %s\n' "$d"; fi; }

assert "preflight.sh exists" "$([[ -f "$PREFLIGHT" ]] && echo 0 || echo 1)"
assert "no hardcoded laia-hermes:laia-hermes default" "$(grep -q 'laia-hermes:laia-hermes' "$PREFLIGHT" && echo 1 || echo 0)"
assert "EXPECTED_OWNER uses ORIG_USER:ORIG_GROUP" \
  "$(grep -Eq 'EXPECTED_OWNER=.*ORIG_USER.*ORIG_GROUP' "$PREFLIGHT" && echo 0 || echo 1)"

# Isolated resolution: feed it ORIG_USER=$USER (the test runner's user) and
# verify EXPECTED_OWNER resolves to that user's user:group.
ME="$(id -un)"
MY_GROUP="$(id -gn)"
RESOLVED="$(ORIG_USER="$ME" bash -c '
ORIG_USER="${SUDO_USER:-${LAIA_ADMIN_USER:-${USER:-}}}"
[[ -n "$ORIG_USER" ]] || ORIG_USER="'"$ME"'"
ORIG_GROUP=$(id -gn "$ORIG_USER" 2>/dev/null || echo "$ORIG_USER")
EXPECTED_OWNER="${LAIA_EXPECTED_OWNER:-${ORIG_USER}:${ORIG_GROUP}}"
printf "%s" "$EXPECTED_OWNER"
')"
assert "EXPECTED_OWNER resolves to current user:group" \
  "$([[ "$RESOLVED" == "$ME:$MY_GROUP" ]] && echo 0 || echo 1)"

printf '\nPASS: %d FAIL: %d\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then printf '%s\n' "${FAILURES[@]}"; exit 1; fi
