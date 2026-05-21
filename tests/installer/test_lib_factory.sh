#!/usr/bin/env bash
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
LIB="$LAIA_ROOT/infra/installer/lib"
PASS=0; FAIL=0; FAILURES=()
assert() { local d="$1" s="$2"; if [[ "$s" == 0 ]]; then PASS=$((PASS+1)); printf '  ✓ %s\n' "$d"; else FAIL=$((FAIL+1)); FAILURES+=("$d"); printf '  ✗ %s\n' "$d"; fi; }

TMPDIR_TEST="$(mktemp -d "${HOME}/laia-factory.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT
export NO_COLOR=1
export LAIA_LOG_FILE="$TMPDIR_TEST/log"
export LAIA_HOME_OVERRIDE="$TMPDIR_TEST/LAIA-ARCH"
export LAIA_AGORA_ENV_FILE_OVERRIDE="$TMPDIR_TEST/agora/.env"
OPT_AUTH_FILE=""
OPT_ADMIN_USER=""
OPT_ADMIN_PASS=""
OPT_YES=true
export LAIA_NONINTERACTIVE=true

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
source "$LIB/factory.sh"
DATA_DIR="$LAIA_HOME_OVERRIDE"

mkdir -p "$DATA_DIR"
fact_seed_cli_config >/dev/null
assert "cli-config.yaml seeded" "$([[ -f "$DATA_DIR/cli-config.yaml" ]] && echo 0 || echo 1)"
assert ".env seeded" "$([[ -f "$DATA_DIR/.env" ]] && echo 0 || echo 1)"

fact_seed_authjson >/dev/null
assert "auth.json placeholder seeded" "$(grep -q '"provider":"unset"' "$DATA_DIR/auth.json" && echo 0 || echo 1)"
assert "auth.json mode 600" "$([[ "$(stat -c %a "$DATA_DIR/auth.json")" == 600 ]] && echo 0 || echo 1)"

printf '{"provider":"test"}\n' >"$TMPDIR_TEST/custom-auth.json"
rm -f "$DATA_DIR/auth.json"
OPT_AUTH_FILE="$TMPDIR_TEST/custom-auth.json"
fact_seed_authjson >/dev/null
assert "auth.json copied from --auth-file" "$(grep -q '"provider":"test"' "$DATA_DIR/auth.json" && echo 0 || echo 1)"

OPT_ADMIN_USER="rootadmin"
OPT_ADMIN_PASS="secretpass"
fact_seed_admin_user >/dev/null
assert "admin credentials file written" "$([[ -f "$DATA_DIR/.admin-credentials" ]] && echo 0 || echo 1)"
assert "admin username persisted" "$(grep -q '^username=rootadmin$' "$DATA_DIR/.admin-credentials" && echo 0 || echo 1)"
assert "admin password persisted" "$(grep -q '^password=secretpass$' "$DATA_DIR/.admin-credentials" && echo 0 || echo 1)"
assert "admin credentials mode 600" "$([[ "$(stat -c %a "$DATA_DIR/.admin-credentials")" == 600 ]] && echo 0 || echo 1)"

before="$(cat "$DATA_DIR/.admin-credentials")"
OPT_ADMIN_PASS="changed"
fact_seed_admin_user >/dev/null
after="$(cat "$DATA_DIR/.admin-credentials")"
assert "admin credentials not overwritten" "$([[ "$before" == "$after" ]] && echo 0 || echo 1)"

AGORA_TELEGRAM_TOKEN="tok-test"
fact_persist_env_to_container >/dev/null
assert "AGORA env token persisted" "$(grep -q '^AGORA_TELEGRAM_TOKEN=tok-test$' "$LAIA_AGORA_ENV_FILE_OVERRIDE" && echo 0 || echo 1)"

printf '\nPASS: %d FAIL: %d\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then printf '%s\n' "${FAILURES[@]}"; exit 1; fi
