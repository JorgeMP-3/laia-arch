#!/usr/bin/env bash
# integrity:id=cross_consistency_live
# integrity:name=T4 cross-consistency (live DB/FS/containers)
# integrity:level=integration
# integrity:layers=cross,data,lxd,executor
# integrity:profiles=host,vm
# integrity:requires=lxd,python3,sqlite3
# integrity:timeout=60
#
# T4 integration test. Reconciles the live agora.db against the on-disk user
# zone and the LXD container inventory, in both directions (no orphans either
# way). Read-only. Where agora.db is idmap-shifted and unreadable host-side
# (production), the test skips cleanly (exit 77) rather than false-failing —
# the same constraint D2 documents. It runs green on the VM laia-dev.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../lib/integrity_shell.sh
source "$SCRIPT_DIR/../../lib/integrity_shell.sh"

require_cmds lxc python3 sqlite3

AGORA_DATA_DIR="${LAIA_AGORA_DIR_OVERRIDE:-/srv/laia/agora}"
AGORA_DB="${AGORA_DB:-$AGORA_DATA_DIR/agora.db}"
USERS_DIR="${LAIA_USERS_DIR_OVERRIDE:-/srv/laia/users}"
RECONCILE="$INTEGRITY_REPO_ROOT/tests/integration/lib/reconcile.py"

assert_file "$RECONCILE"

[[ -f "$AGORA_DB" ]] || integ_skip "agora.db not present at $AGORA_DB"
[[ -r "$AGORA_DB" ]] || integ_skip "agora.db not readable host-side (idmap-shifted; run on the VM)"
# Confirm we can actually open it read-only before trusting the reconcile.
sqlite3 "file:$AGORA_DB?mode=ro" 'SELECT 1;' >/dev/null 2>&1 \
  || integ_skip "agora.db not openable read-only host-side (idmap); run on the VM"

if [[ ! -d "$USERS_DIR" ]]; then
  # No user zone yet: only valid if no agent-* containers are provisioned.
  if [[ "$(agent_container_count)" -gt 0 ]]; then
    integ_fail "user zone $USERS_DIR missing while agent-* containers exist"
  fi
  integ_skip "no user zone and no agent containers — nothing to reconcile"
fi

python3 "$RECONCILE" --db "$AGORA_DB" --users-dir "$USERS_DIR" \
  || integ_fail "live cross-consistency check found orphans (see above)"

integ_info "live DB/FS/containers reconciliation OK"
