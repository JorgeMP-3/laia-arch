#!/usr/bin/env bash
# integrity:id=agora_contract
# integrity:name=AGORA service contract
# integrity:level=integration
# integrity:layers=agora,data
# integrity:profiles=host,vm
# integrity:requires=lxd,curl,python3
# integrity:timeout=60
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../lib/integrity_shell.sh
source "$SCRIPT_DIR/../../lib/integrity_shell.sh"

CONTAINER="${CONTAINER:-laia-agora}"
AGORA_DATA_DIR="${LAIA_AGORA_DIR_OVERRIDE:-/srv/laia/agora}"
AGORA_DB="${AGORA_DB:-$AGORA_DATA_DIR/agora.db}"

require_cmds lxc curl python3
assert_lxc_running "$CONTAINER"

health="$(agora_health_json "$CONTAINER")" \
  || integ_fail "/api/health unavailable for $CONTAINER"
assert_health_ok "$health"

if [[ -r "$AGORA_DB" ]] && command -v sqlite3 >/dev/null 2>&1; then
  res="$(sqlite3 "file:$AGORA_DB?mode=ro" 'PRAGMA integrity_check;' 2>/dev/null | head -1)"
  [[ "$res" == "ok" ]] || integ_fail "host-side agora.db integrity_check=${res:-<error>}"
else
  lxc exec "$CONTAINER" -- sh -lc 'command -v sqlite3 >/dev/null 2>&1 && sqlite3 "file:/opt/agora/data/agora.db?mode=ro" "PRAGMA integrity_check;"' \
    | head -1 | grep -qx 'ok' \
    || integ_fail "in-container agora.db integrity_check failed"
fi

integ_info "AGORA contract OK"
