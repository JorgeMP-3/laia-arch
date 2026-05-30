#!/usr/bin/env bash
# integrity:id=host_layout_contract
# integrity:name=Host layout contract
# integrity:level=integration
# integrity:layers=host,data
# integrity:profiles=vm
# integrity:timeout=30
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../lib/integrity_shell.sh
source "$SCRIPT_DIR/../../lib/integrity_shell.sh"

SRV_ROOT="${LAIA_SRV_DIR_OVERRIDE:-/srv/laia}"
AGORA_DATA_DIR="${LAIA_AGORA_DIR_OVERRIDE:-$SRV_ROOT/agora}"
USERS_DIR="${LAIA_USERS_DIR_OVERRIDE:-$SRV_ROOT/users}"
STATE_DIR="${LAIA_STATE_ROOT:-$SRV_ROOT/state}"
ARCH_DIR="${LAIA_ARCH_DIR_OVERRIDE:-$SRV_ROOT/arch}"

assert_dir "$SRV_ROOT"
assert_dir "$AGORA_DATA_DIR"
assert_dir "$STATE_DIR"
assert_dir "$ARCH_DIR"
assert_file "${AGORA_DB:-$AGORA_DATA_DIR/agora.db}"

if [[ -d "$USERS_DIR" ]]; then
  integ_info "users zone present at $USERS_DIR"
elif [[ "$(agent_container_count)" -gt 0 ]]; then
  integ_fail "missing $USERS_DIR while agent-* containers are provisioned"
else
  integ_info "users zone absent and no agent-* containers are provisioned"
fi

integ_info "host layout OK under $SRV_ROOT"
