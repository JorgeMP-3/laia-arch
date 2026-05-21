#!/usr/bin/env bash
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
LIB="$LAIA_ROOT/infra/installer/lib"
PASS=0; FAIL=0; FAILURES=()

assert() { local d="$1" s="$2"; if [[ "$s" == 0 ]]; then PASS=$((PASS+1)); printf '  ✓ %s\n' "$d"; else FAIL=$((FAIL+1)); FAILURES+=("$d"); printf '  ✗ %s\n' "$d"; fi; }

TMPDIR_TEST="$(mktemp -d "${HOME}/laia-bootstrap.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

export NO_COLOR=1
export LAIA_LOG_FILE="$TMPDIR_TEST/log"
export LAIA_HOME_OVERRIDE="$TMPDIR_TEST/home"
export LAIA_HOST_ARCH_OVERRIDE=amd64

# shellcheck source=/dev/null
source "$LIB/common.sh"
# shellcheck source=/dev/null
source "$LIB/sudo.sh"
# shellcheck source=/dev/null
source "$LIB/system.sh"
# shellcheck source=/dev/null
source "$LIB/version.sh"
# shellcheck source=/dev/null
source "$LIB/install.sh"
# shellcheck source=/dev/null
source "$LIB/bootstrap.sh"

boot_detect_arch >/dev/null
assert "boot_detect_arch exports amd64" "$([[ "${LAIA_HOST_ARCH:-}" == amd64 ]] && echo 0 || echo 1)"

boot_check_lxd_installed >/dev/null
assert "boot_check_lxd_installed override exits 0" "$?"
boot_init_defaults >/dev/null
assert "boot_init_defaults override exits 0" "$?"
boot_build_images >/dev/null
assert "boot_build_images override exits 0" "$?"
boot_provision_agora >/dev/null
assert "boot_provision_agora override exits 0" "$?"
boot_wait_for_agora_health >/dev/null
assert "boot_wait_for_agora_health override exits 0" "$?"

export LAIA_HOST_ARCH_OVERRIDE=riscv64
if ( boot_detect_arch >/dev/null 2>&1 ); then
  assert "unsupported arch is rejected" 1
else
  assert "unsupported arch is rejected" 0
fi

printf '\nPASS: %d FAIL: %d\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then printf '%s\n' "${FAILURES[@]}"; exit 1; fi
