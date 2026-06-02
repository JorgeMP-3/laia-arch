#!/usr/bin/env bash
# Verifies that when SSH key auth fails and no --ssh-pass-file was supplied,
# laia-clone dies with a clear message and exit 3 — it MUST NOT fall back to
# reading from /dev/tty (the old behavior crashed VMs running curl|sudo bash
# with "/dev/tty: No such device or address"; see ~/laia-developers/workflow-main/problems.md::
# wizard-clone-tty).
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

# Build a stub PATH that makes `ssh` always fail (simulating a host where
# the user's SSH key isn't authorized at $OPT_SOURCE). sshpass is included
# only so the script doesn't bail at the "sshpass not installed" check —
# we want to reach the preflight test, not block on a dep.
STUB_DIR="$(mktemp -d)"
trap 'rm -rf "$STUB_DIR" "$TMPDIR_TEST"' EXIT

cat >"$STUB_DIR/ssh" <<'EOF'
#!/usr/bin/env bash
# Stub: always fail, mimicking refused key auth.
exit 255
EOF
cat >"$STUB_DIR/sshpass" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$STUB_DIR/ssh" "$STUB_DIR/sshpass"
export PATH="$STUB_DIR:$PATH"

# Fake an already-completed install so clone_install_first_if_needed
# short-circuits and we land straight in clone_preflight.
TMPDIR_TEST="$(mktemp -d "${TMPDIR:-/tmp}/laia-clone-no-pass.XXXXXX")"
export LAIA_INSTALL_ROOT_OVERRIDE="$TMPDIR_TEST/opt"
export LAIA_BIN_DIR_OVERRIDE="$TMPDIR_TEST/bin"
export LAIA_HOME_OVERRIDE="$TMPDIR_TEST/LAIA-ARCH"
export LAIA_USERS_DIR_OVERRIDE="$TMPDIR_TEST/srv/users"
export LAIA_AGORA_DIR_OVERRIDE="$TMPDIR_TEST/srv/agora"
export LAIA_ARCH_DIR_OVERRIDE="$TMPDIR_TEST/srv/arch"
export LAIA_ARCH_CREDS_DIR_OVERRIDE="$TMPDIR_TEST/home/.laia"
export LAIA_SYSTEMD_DIR_OVERRIDE="$TMPDIR_TEST/systemd"
export LAIA_SHELL_RC_OVERRIDE="$TMPDIR_TEST/rc"
export LAIA_LOG_FILE="$TMPDIR_TEST/log"
export LAIA_HOST_ARCH_OVERRIDE=amd64
mkdir -p "$LAIA_INSTALL_ROOT_OVERRIDE" "$TMPDIR_TEST/installed/.laia-core"
ln -s "$TMPDIR_TEST/installed" "$LAIA_INSTALL_ROOT_OVERRIDE/laia"

echo "→ SSH key auth fails AND no --ssh-pass-file → exit 3 with clear message"
set +e
out=$("$BIN" --source user@unreachable.invalid --yes 2>&1)
rc=$?
set -e

[[ $rc == 3 ]] && r=0 || r=1
assert "exit code 3 on SSH key auth failure (got $rc)" $r

if grep -q 'SSH key auth to user@unreachable.invalid failed' <<<"$out"; then r=0; else r=1; fi
assert "stderr names the failed source clearly" $r

if grep -q "wizard.*Password SSH" <<<"$out"; then r=0; else r=1; fi
assert "stderr points the user to the wizard's password mode" $r

# The bug we're closing: /dev/tty error must NOT appear.
if grep -qi 'dev/tty' <<<"$out"; then r=1; else r=0; fi
assert "no /dev/tty errors in output (wizard-clone-tty regression guard)" $r

echo
echo "═══════════════════════════════════════════════════"
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
if [[ $FAIL -gt 0 ]]; then
  echo "Failures:"
  for f in "${FAILURES[@]}"; do printf "  - %s\n" "$f"; done
  echo "--- captured output ---"
  printf '%s\n' "$out"
  exit 1
fi
exit 0
