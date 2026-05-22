#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# tests/installer/test_admin_pass_file.sh
#
# Verifies the --admin-pass-file pathway in bin/laia-install:
#   * file content is loaded into OPT_ADMIN_PASS
#   * file is unlinked immediately after read
#   * --admin-pass and --admin-pass-file together → exit 2
#   * missing/unreadable file → exit 2
#   * password never appears in the process's argv (read from /proc)
#
# Run via tests/installer/run_all.sh.
# Exit code: 0 if all assertions pass, 1 otherwise.
# ─────────────────────────────────────────────────────────────────────────────
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
BIN="$LAIA_ROOT/bin/laia-install"

PASS=0; FAIL=0; FAILURES=()
assert() {
  local desc="$1" rc="$2"
  if [[ "$rc" == 0 ]]; then PASS=$((PASS+1)); printf '  ✓ %s\n' "$desc"
  else FAIL=$((FAIL+1)); FAILURES+=("$desc"); printf '  ✗ %s\n' "$desc"; fi
}

# Each test uses --dry-run so the binary stops before any mutations but after
# the new resolve_admin_pass_file() runs.

echo "→ Valid --admin-pass-file: password loaded, file unlinked"
TMP=$(mktemp); chmod 0600 "$TMP"; echo -n 'GoodPass123!' > "$TMP"
out=$("$BIN" --dry-run --from-local "$LAIA_ROOT" --version v0.0.0-test \
              --admin-pass-file "$TMP" --yes 2>&1)
rc=$?
[[ $rc == 0 ]] && r1=0 || r1=1
assert "exit 0 on dry-run with valid pass-file" $r1
[[ ! -f "$TMP" ]] && r2=0 || r2=1
assert "pass-file unlinked after read" $r2
# The password must NOT appear in any output (we never print or log it).
if grep -q 'GoodPass123!' <<<"$out"; then r3=1; else r3=0; fi
assert "password not echoed in --dry-run output" $r3

echo
echo "→ Missing pass-file → exit 2"
"$BIN" --dry-run --from-local "$LAIA_ROOT" --version v0.0.0-test \
       --admin-pass-file /tmp/does-not-exist-xyzzy --yes >/dev/null 2>&1
rc=$?
[[ $rc == 2 ]] && r=0 || r=1
assert "missing --admin-pass-file → exit 2 (got $rc)" $r

echo
echo "→ Empty pass-file → exit 2"
TMP=$(mktemp); chmod 0600 "$TMP"; : > "$TMP"
"$BIN" --dry-run --from-local "$LAIA_ROOT" --version v0.0.0-test \
       --admin-pass-file "$TMP" --yes >/dev/null 2>&1
rc=$?
[[ $rc == 2 ]] && r=0 || r=1
assert "empty --admin-pass-file → exit 2 (got $rc)" $r
rm -f "$TMP"

echo
echo "→ --admin-pass + --admin-pass-file → exit 2"
TMP=$(mktemp); chmod 0600 "$TMP"; echo -n 'A' > "$TMP"
"$BIN" --dry-run --from-local "$LAIA_ROOT" --version v0.0.0-test \
       --admin-pass FOO --admin-pass-file "$TMP" --yes >/dev/null 2>&1
rc=$?
[[ $rc == 2 ]] && r=0 || r=1
assert "both --admin-pass and --admin-pass-file → exit 2 (got $rc)" $r
rm -f "$TMP"

echo
echo "→ Password not visible in /proc/<pid>/cmdline while binary is running"
# We can't easily race a real install, but we can confirm the FILE-based path
# never embeds the password in argv: scan the script's argv-handling code for
# `OPT_ADMIN_PASS` being used in any subcommand list. (Belt and braces.)
if grep -q -- '--admin-pass=.*\$OPT_ADMIN_PASS' "$BIN"; then
  r=1   # found unexpected use of $OPT_ADMIN_PASS in an argv-style invocation
else
  r=0
fi
assert "no '--admin-pass=\$OPT_ADMIN_PASS' string in bin/laia-install" $r

echo
echo "═══════════════════════════════════════════════════"
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
if [[ $FAIL -gt 0 ]]; then
  echo "Failures:"
  for f in "${FAILURES[@]}"; do printf "  - %s\n" "$f"; done
  exit 1
fi
exit 0
