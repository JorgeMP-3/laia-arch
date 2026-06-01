#!/usr/bin/env bash
# integrity:id=lxd_contract
# integrity:name=LXD container contract
# integrity:level=integration
# integrity:layers=lxd
# integrity:profiles=host,vm
# integrity:requires=lxd
# integrity:timeout=45
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../lib/integrity_shell.sh
source "$SCRIPT_DIR/../../lib/integrity_shell.sh"

CONTAINER="${CONTAINER:-laia-agora}"

require_cmds lxc
assert_lxc_running "$CONTAINER"
lxc exec "$CONTAINER" -- test -d /opt/agora/data \
  || integ_fail "$CONTAINER lacks /opt/agora/data bind mount"

integ_info "LXD contract OK for $CONTAINER"
