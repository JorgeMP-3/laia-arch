#!/usr/bin/env bash
# integrity:id=load_smoke
# integrity:name=T6 load smoke (N concurrent agents, no RAM/disk exhaustion)
# integrity:level=e2e
# integrity:layers=lxd,executor,host,data
# integrity:profiles=vm
# integrity:requires=lxd,curl,python3
# integrity:timeout=1800
#
# T6 (Track T, absorbs C5). Provision N throwaway agents, assert every executor
# answers, and check the host kept enough RAM/disk headroom (a user must not be
# able to exhaust the box). Then deprovision all and assert no LXD residue.
# This is a smoke, not a benchmark: it proves the box survives N concurrent
# per-user containers, and is where idle-eviction (Track C) will later be
# verified.
#
# DESTRUCTIVE and VM-only, hard-gated like the golden-path e2e:
#   * profile vm only, and
#   * requires LAIA_E2E_ALLOW_DESTRUCTIVE=1.
# Run on the golden VM:
#   LAIA_E2E_ALLOW_DESTRUCTIVE=1 LAIA_LOAD_N=5 \
#     tests/integration/run_integrity.sh --profile vm --level e2e --layer lxd
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../lib/integrity_shell.sh
source "$SCRIPT_DIR/../../lib/integrity_shell.sh"

require_cmds lxc curl python3

[[ "${LAIA_E2E_ALLOW_DESTRUCTIVE:-0}" == "1" ]] \
  || integ_skip "destructive load smoke disabled; set LAIA_E2E_ALLOW_DESTRUCTIVE=1 on the golden VM"

# Tunables. Defaults are modest so the smoke is quick and safe on a dev VM.
N="${LAIA_LOAD_N:-5}"
MIN_FREE_MB="${LAIA_LOAD_MIN_FREE_MB:-512}"     # host MemAvailable floor after provisioning
MIN_DISK_MB="${LAIA_LOAD_MIN_DISK_MB:-1024}"    # free disk floor on the user zone
USERS_DIR="${LAIA_USERS_DIR_OVERRIDE:-/srv/laia/users}"
EXEC_PORT="${LAIA_EXECUTOR_PORT:-9091}"
LAIACTL="${LAIACTL_PATH:-$INTEGRITY_REPO_ROOT/infra/laiactl}"
[[ -x "$LAIACTL" ]] || integ_fail "laiactl not found/executable at $LAIACTL (set LAIACTL_PATH)"

PREFIX="t6load$$"
SLUGS=()
for i in $(seq 1 "$N"); do
  SLUGS+=("${PREFIX}x${i}")
done

# Idempotency: none of the throwaway slugs may pre-exist.
for slug in "${SLUGS[@]}"; do
  if lxc info "agent-$slug" >/dev/null 2>&1 || [[ -e "$USERS_DIR/$slug" ]]; then
    integ_fail "refusing to run: throwaway slug '$slug' already exists"
  fi
done

cleanup() {
  local rc=$?
  set +e
  for slug in "${SLUGS[@]}"; do
    "$LAIACTL" delete-agent "$slug" --yes --force >/dev/null 2>&1
    lxc delete "agent-$slug" --force >/dev/null 2>&1
    rm -rf "${USERS_DIR:?}/$slug" >/dev/null 2>&1
  done
  return "$rc"
}
trap cleanup EXIT

free_mb() {
  # MemAvailable is the kernel's best estimate of allocatable memory.
  awk '/^MemAvailable:/ {print int($2/1024)}' /proc/meminfo
}
disk_free_mb() {
  df -Pm "$USERS_DIR" 2>/dev/null | awk 'NR==2 {print $4}'
}

start_free="$(free_mb)"
start_disk="$(disk_free_mb)"
integ_info "baseline: MemAvailable=${start_free}MB, disk free on $USERS_DIR=${start_disk}MB; provisioning N=$N"

# ── Provision N agents (sequential create; runtime install kicks them live) ──
for slug in "${SLUGS[@]}"; do
  "$LAIACTL" create-agent "$slug" >/dev/null 2>&1 || integ_fail "create-agent $slug failed"
  "$LAIACTL" install-agent-runtime "$slug" >/dev/null 2>&1 || integ_fail "install-agent-runtime $slug failed"
done

# ── Assert every agent is up and its executor answers ────────────────────────
live=0
for slug in "${SLUGS[@]}"; do
  container="agent-$slug"
  assert_lxc_running "$container"
  ip=""
  for _ in $(seq 1 30); do
    ip="$(container_ipv4 "$container")" && [[ -n "$ip" ]] && break
    sleep 2
  done
  [[ -n "$ip" ]] || integ_fail "$container never got an IPv4"
  token="$(lxc exec "$container" -- cat /etc/laia/executor-token 2>/dev/null)"
  [[ -n "$token" ]] || integ_fail "executor token missing in $container"
  ok=""
  for _ in $(seq 1 30); do
    if curl -fsS -m 5 -H "Authorization: Bearer $token" "http://$ip:$EXEC_PORT/health" >/dev/null 2>&1; then
      ok=1
      break
    fi
    sleep 2
  done
  [[ -n "$ok" ]] || integ_fail "executor on $container ($ip:$EXEC_PORT) did not answer /health"
  live=$((live + 1))
done
integ_info "all $live/$N agents RUNNING with a responsive executor"

# ── Resource headroom: a fleet of N must not exhaust the host ────────────────
end_free="$(free_mb)"
end_disk="$(disk_free_mb)"
integ_info "after N=$N: MemAvailable=${end_free}MB (floor ${MIN_FREE_MB}MB), disk free=${end_disk}MB (floor ${MIN_DISK_MB}MB)"
[[ "$end_free" -ge "$MIN_FREE_MB" ]] \
  || integ_fail "RAM headroom exhausted: MemAvailable ${end_free}MB < floor ${MIN_FREE_MB}MB at N=$N"
[[ "$end_disk" -ge "$MIN_DISK_MB" ]] \
  || integ_fail "disk headroom exhausted: ${end_disk}MB free < floor ${MIN_DISK_MB}MB at N=$N"

# ── Deprovision all and assert no LXD residue ────────────────────────────────
for slug in "${SLUGS[@]}"; do
  "$LAIACTL" delete-agent "$slug" --yes --force >/dev/null 2>&1 || integ_fail "delete-agent $slug failed"
done
sleep 1
leftover=0
for slug in "${SLUGS[@]}"; do
  lxc info "agent-$slug" >/dev/null 2>&1 && leftover=$((leftover + 1))
done
[[ "$leftover" -eq 0 ]] || integ_fail "$leftover throwaway container(s) survived deprovision"

integ_info "T6 load smoke OK: N=$N agents provisioned, served, and torn down cleanly"
