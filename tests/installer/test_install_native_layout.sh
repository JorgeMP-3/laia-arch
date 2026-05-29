#!/usr/bin/env bash
# C4 install-native executable spec — the installer gate for the locked v2
# ARCH layout contract:
#   - ARCH runtime dir /srv/laia/arch (0750), override-backed here
#   - ARCH secrets in /srv/laia/arch/secrets (0700), files 0600
#   - no ~/.laia in the admin HOME
#   - laia auth writes to the secrets dir, not HOME
#
# Implemented in C4 (2026-05-29) — the LAIA_C4_READY skip guard was removed once
# the installer + `laia auth` dispatch landed and this went green.
#
# NOTE(C2): raw.idmap + container read access is validated in the LXD/mount
# slice, not here. This test only specifies host-side install/auth artifacts.
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

mode_of() {
  stat -c '%a' "$1" 2>/dev/null || printf 'missing'
}

owner_of() {
  stat -c '%U' "$1" 2>/dev/null || printf 'missing'
}

TMPDIR_TEST="$(mktemp -d "${TMPDIR:-/tmp}/laia-install-native-layout.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

export HOME="$TMPDIR_TEST/home"
mkdir -p "$HOME"

export NO_COLOR=1
export LAIA_INSTALL_ROOT_OVERRIDE="$TMPDIR_TEST/opt"
export LAIA_BIN_DIR_OVERRIDE="$TMPDIR_TEST/bin"
export LAIA_HOME_OVERRIDE="$TMPDIR_TEST/LAIA-ARCH"
export LAIA_ARCH_DIR_OVERRIDE="$TMPDIR_TEST/srv/laia/arch"
export LAIA_ARCH_CREDS_DIR_OVERRIDE="$TMPDIR_TEST/srv/laia/arch/secrets"
export LAIA_SYSTEMD_DIR_OVERRIDE="$TMPDIR_TEST/systemd"
export LAIA_SHELL_RC_OVERRIDE="$TMPDIR_TEST/rc"
export LAIA_LOG_FILE="$TMPDIR_TEST/install.log"
export LAIA_HOST_ARCH_OVERRIDE=amd64
mkdir -p "$LAIA_INSTALL_ROOT_OVERRIDE"

echo "→ C4 install-native layout"
if "$BIN/laia-install" \
    --from-local "$LAIA_ROOT" \
    --version v0.0.0-c4-native-layout \
    --skip-pip \
    --skip-frontend \
    --admin-user admin \
    --admin-pass pass123 \
    --yes \
    >"$TMPDIR_TEST/install.out" 2>&1; then
  assert "factory/headless install exits 0" 0
else
  assert "factory/headless install exits 0" 1
fi

assert "/srv/laia/arch override exists" \
  "$([[ -d "$LAIA_ARCH_DIR_OVERRIDE" ]] && echo 0 || echo 1)"
assert "/srv/laia/arch override owner is admin user" \
  "$([[ "$(owner_of "$LAIA_ARCH_DIR_OVERRIDE")" == "$(id -un)" ]] && echo 0 || echo 1)"
assert "/srv/laia/arch override mode is 0750" \
  "$([[ "$(mode_of "$LAIA_ARCH_DIR_OVERRIDE")" == "750" ]] && echo 0 || echo 1)"

assert "/srv/laia/arch/secrets override exists" \
  "$([[ -d "$LAIA_ARCH_CREDS_DIR_OVERRIDE" ]] && echo 0 || echo 1)"
assert "/srv/laia/arch/secrets override owner is admin user" \
  "$([[ "$(owner_of "$LAIA_ARCH_CREDS_DIR_OVERRIDE")" == "$(id -un)" ]] && echo 0 || echo 1)"
assert "/srv/laia/arch/secrets override mode is 0700" \
  "$([[ "$(mode_of "$LAIA_ARCH_CREDS_DIR_OVERRIDE")" == "700" ]] && echo 0 || echo 1)"

for secret in auth.json .env; do
  assert "$secret seeded in /srv/laia/arch/secrets" \
    "$([[ -f "$LAIA_ARCH_CREDS_DIR_OVERRIDE/$secret" ]] && echo 0 || echo 1)"
  assert "$secret mode is 0600" \
    "$([[ "$(mode_of "$LAIA_ARCH_CREDS_DIR_OVERRIDE/$secret")" == "600" ]] && echo 0 || echo 1)"
done

assert "factory install does not create ~/.laia" \
  "$([[ ! -e "$HOME/.laia" ]] && echo 0 || echo 1)"
assert "factory install does not leave auth.json in LAIA_HOME" \
  "$([[ ! -e "$LAIA_HOME_OVERRIDE/auth.json" ]] && echo 0 || echo 1)"
assert "factory install does not leave .env in LAIA_HOME" \
  "$([[ ! -e "$LAIA_HOME_OVERRIDE/.env" ]] && echo 0 || echo 1)"

echo
echo "→ C4 laia auth writes to ARCH secrets"
if "$LAIA_BIN_DIR_OVERRIDE/laia" auth add openrouter \
    --type api-key \
    --api-key c4-test-key \
    --label c4-test \
    >"$TMPDIR_TEST/auth.out" 2>&1; then
  assert "laia auth add exits 0" 0
else
  assert "laia auth add exits 0" 1
fi

assert "laia auth keeps auth store in /srv/laia/arch/secrets" \
  "$([[ -f "$LAIA_ARCH_CREDS_DIR_OVERRIDE/auth.json" ]] && grep -q 'c4-test' "$LAIA_ARCH_CREDS_DIR_OVERRIDE/auth.json" && echo 0 || echo 1)"
assert "laia auth keeps auth.json mode 0600" \
  "$([[ "$(mode_of "$LAIA_ARCH_CREDS_DIR_OVERRIDE/auth.json")" == "600" ]] && echo 0 || echo 1)"
assert "laia auth still does not create ~/.laia" \
  "$([[ ! -e "$HOME/.laia" ]] && echo 0 || echo 1)"
assert "laia auth does not create legacy LAIA_HOME auth.json" \
  "$([[ ! -e "$LAIA_HOME_OVERRIDE/auth.json" ]] && echo 0 || echo 1)"

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
  echo "Install output:"
  cat "$TMPDIR_TEST/install.out" 2>/dev/null || true
  echo
  echo "Auth output:"
  cat "$TMPDIR_TEST/auth.out" 2>/dev/null || true
  exit 1
fi
exit 0
