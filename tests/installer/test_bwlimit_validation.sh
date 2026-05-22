#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# tests/installer/test_bwlimit_validation.sh
#
# Verifies that bin/laia-clone strictly validates --bwlimit and --source
# against shell-metacharacter injection. Also exercises --bwlimit-file.
#
# Run via tests/installer/run_all.sh.
# Exit code: 0 if all assertions pass, 1 otherwise.
# ─────────────────────────────────────────────────────────────────────────────
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
BIN="$LAIA_ROOT/bin/laia-clone"

PASS=0; FAIL=0; FAILURES=()
expect_rc() {
  local desc="$1" want="$2"; shift 2
  "$@" >/dev/null 2>&1
  local got=$?
  if [[ "$got" == "$want" ]]; then
    PASS=$((PASS+1)); printf '  ✓ %s (rc=%d)\n' "$desc" "$got"
  else
    FAIL=$((FAIL+1))
    FAILURES+=("$desc (want=$want got=$got)")
    printf '  ✗ %s (want=%d got=%d)\n' "$desc" "$want" "$got"
  fi
}

echo "→ Valid --bwlimit values are accepted (--dry-run, rc=0)"
for v in "50M" "1G" "512K" "10" "999G"; do
  expect_rc "--bwlimit=$v ok" 0 "$BIN" --source 'user@host' --dry-run --bwlimit "$v" --yes
done

echo
echo "→ Invalid --bwlimit values rejected with exit 2"
for v in "abc" "50MB" "50M;" "\$(rm)" "50M; rm /tmp/x" "" "-5M"; do
  expect_rc "--bwlimit='$v' rejected" 2 "$BIN" --source 'user@host' --dry-run --bwlimit "$v" --yes
done

echo
echo "→ Valid --source values are accepted"
for v in "user@host" "laia@10.0.0.5" "laia-hermes@old.example.com" "x@[::1]"; do
  expect_rc "--source='$v' ok" 0 "$BIN" --source "$v" --dry-run --yes
done

echo
echo "→ Invalid --source values rejected with exit 2"
for v in 'user@host; rm /tmp/x' 'user@host$(rm)' 'user@host|cmd' 'user@host '\''X'\''' 'user@'; do
  expect_rc "--source='$v' rejected" 2 "$BIN" --source "$v" --dry-run --yes
done

echo
echo "→ Invalid --only-agent slug rejected"
expect_rc "--only-agent with space rejected" 2 \
  "$BIN" --source user@host --dry-run --only-agent "foo bar" --yes
expect_rc "--only-agent with semicolon rejected" 2 \
  "$BIN" --source user@host --dry-run --only-agent "foo;bar" --yes
expect_rc "--only-agent valid slug ok" 0 \
  "$BIN" --source user@host --dry-run --only-agent "agent-jorge" --yes

echo
echo "→ --bwlimit-file loads from file and unlinks"
TMP=$(mktemp); echo -n '25M' > "$TMP"
expect_rc "--bwlimit-file with valid content ok" 0 \
  "$BIN" --source user@host --dry-run --bwlimit-file "$TMP" --yes
if [[ ! -f "$TMP" ]]; then
  PASS=$((PASS+1)); printf '  ✓ bwlimit-file unlinked after read\n'
else
  FAIL=$((FAIL+1)); FAILURES+=("bwlimit-file not unlinked")
  printf '  ✗ bwlimit-file not unlinked\n'
  rm -f "$TMP"
fi

echo
echo "→ --bwlimit-file with injection content rejected"
TMP=$(mktemp); echo -n '50M; rm /tmp/x' > "$TMP"
expect_rc "--bwlimit-file with bad content → exit 2" 2 \
  "$BIN" --source user@host --dry-run --bwlimit-file "$TMP" --yes
rm -f "$TMP" 2>/dev/null

echo
echo "→ --bwlimit + --bwlimit-file conflict → exit 2"
TMP=$(mktemp); echo -n '10M' > "$TMP"
expect_rc "--bwlimit + --bwlimit-file → exit 2" 2 \
  "$BIN" --source user@host --dry-run --bwlimit 25M --bwlimit-file "$TMP" --yes
rm -f "$TMP" 2>/dev/null

echo
echo "═══════════════════════════════════════════════════"
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
if [[ $FAIL -gt 0 ]]; then
  echo "Failures:"
  for f in "${FAILURES[@]}"; do printf "  - %s\n" "$f"; done
  exit 1
fi
exit 0
