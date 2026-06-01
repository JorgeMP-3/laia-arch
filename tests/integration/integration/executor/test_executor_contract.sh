#!/usr/bin/env bash
# integrity:id=executor_contract
# integrity:name=Per-user executor contract
# integrity:level=integration
# integrity:layers=executor,data
# integrity:profiles=host,vm
# integrity:requires=lxd
# integrity:timeout=60
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../lib/integrity_shell.sh
source "$SCRIPT_DIR/../../lib/integrity_shell.sh"

USERS_DIR="${LAIA_USERS_DIR_OVERRIDE:-/srv/laia/users}"

require_cmds lxc

mapfile -t agents < <(lxc list -c ns --format csv 2>/dev/null | awk -F, '$1 ~ /^agent-/ {print}')
if [[ "${#agents[@]}" -eq 0 ]]; then
  integ_skip "0 agent-* containers provisioned"
fi

for row in "${agents[@]}"; do
  name="${row%%,*}"
  state="${row##*,}"
  slug="${name#agent-}"
  [[ "$state" == "RUNNING" ]] || integ_fail "executor $name state=$state, expected RUNNING"
  assert_dir "$USERS_DIR/$slug"
  assert_dir "$USERS_DIR/$slug/home"
  assert_dir "$USERS_DIR/$slug/workspace"
done

integ_info "executor contract OK for ${#agents[@]} agent container(s)"
