#!/usr/bin/env bash
# integrity:id=migrate_v1_to_v2_prod_outage_regression
# integrity:name=Regression: v1-to-v2 outage auth/data mount
# integrity:level=integration
# integrity:layers=agora,data,lxd
# integrity:profiles=host,vm
# integrity:requires=lxd,curl,python3
# integrity:timeout=60
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../lib/integrity_shell.sh
source "$SCRIPT_DIR/../../lib/integrity_shell.sh"

CONTAINER="${CONTAINER:-laia-agora}"

require_cmds lxc curl python3
assert_lxc_running "$CONTAINER"

# Regression for migrate-v1-to-v2-prod-outage:
# - the auth.json mountpoint must still exist under the AGORA data mount;
# - the AGORA service user must be able to traverse/read /opt/agora/data.
lxc exec "$CONTAINER" -- sh -lc '
  id agora >/dev/null 2>&1
  if command -v runuser >/dev/null 2>&1; then
    runuser -u agora -- sh -lc "cd /opt/agora/data && test -r auth.json && test -r agora.db && test -x ."
  else
    su -s /bin/sh agora -c "cd /opt/agora/data && test -r auth.json && test -r agora.db && test -x ."
  fi
' || integ_fail "agora user cannot access /opt/agora/data/auth.json and agora.db"

health="$(agora_health_json "$CONTAINER")" \
  || integ_fail "/api/health unavailable after auth/data mount check"
assert_health_ok "$health"

integ_info "outage regression OK: auth mountpoint and AGORA data access are intact"
