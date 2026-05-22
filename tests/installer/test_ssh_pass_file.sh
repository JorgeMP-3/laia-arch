#!/usr/bin/env bash
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
BIN="$LAIA_ROOT/bin/laia-clone"

PASS=0; FAIL=0; FAILURES=()
assert() {
  local desc="$1" rc="$2"
  if [[ "$rc" == 0 ]]; then PASS=$((PASS+1)); printf '  ✓ %s\n' "$desc"
  else FAIL=$((FAIL+1)); FAILURES+=("$desc"); printf '  ✗ %s\n' "$desc"; fi
}

STUB_DIR="$(mktemp -d)"
trap 'rm -rf "$STUB_DIR"' EXIT
cat >"$STUB_DIR/sshpass" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$STUB_DIR/sshpass"
export PATH="$STUB_DIR:$PATH"

echo "→ Valid --ssh-pass-file: password loaded, file unlinked, not echoed"
TMP=$(mktemp); chmod 0600 "$TMP"; echo -n 'SshSecret123!' > "$TMP"
out=$("$BIN" --dry-run --source user@host --ssh-pass-file "$TMP" --yes 2>&1)
rc=$?
[[ $rc == 0 ]] && r1=0 || r1=1
assert "exit 0 on dry-run with valid ssh-pass-file" $r1
[[ ! -f "$TMP" ]] && r2=0 || r2=1
assert "ssh-pass-file unlinked after read" $r2
if grep -q 'SshSecret123!' <<<"$out"; then r3=1; else r3=0; fi
assert "SSH password not echoed in dry-run output" $r3

echo
echo "→ Missing --ssh-pass-file → exit 2"
"$BIN" --dry-run --source user@host --ssh-pass-file /tmp/no-such-laia-ssh-pass --yes >/dev/null 2>&1
rc=$?
[[ $rc == 2 ]] && r=0 || r=1
assert "missing --ssh-pass-file → exit 2 (got $rc)" $r

echo
echo "→ Empty --ssh-pass-file → exit 2 and unlinks"
TMP=$(mktemp); chmod 0600 "$TMP"; : > "$TMP"
"$BIN" --dry-run --source user@host --ssh-pass-file "$TMP" --yes >/dev/null 2>&1
rc=$?
[[ $rc == 2 ]] && r=0 || r=1
assert "empty --ssh-pass-file → exit 2 (got $rc)" $r
[[ ! -f "$TMP" ]] && r=0 || r=1
assert "empty ssh-pass-file unlinked" $r

echo
echo "→ Password variable is not embedded in argv construction"
if grep -q -- '--ssh-pass-file.*\$SSHPASS' "$BIN"; then
  r=1
else
  r=0
fi
assert "no SSHPASS value passed via argv" $r

echo
echo "═══════════════════════════════════════════════════"
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
if [[ $FAIL -gt 0 ]]; then
  echo "Failures:"
  for f in "${FAILURES[@]}"; do printf "  - %s\n" "$f"; done
  exit 1
fi
exit 0
