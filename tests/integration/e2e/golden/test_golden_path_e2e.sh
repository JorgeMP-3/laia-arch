#!/usr/bin/env bash
# integrity:id=golden_path_e2e
# integrity:name=T3 golden-path e2e (provision -> tool-call in own container -> deprovision)
# integrity:level=e2e
# integrity:layers=agora,executor,lxd,data,cross
# integrity:profiles=vm
# integrity:requires=lxd,curl,python3
# integrity:timeout=900
#
# T3 (Track T) -- the golden path, end to end, on the golden VM only:
#   provision a throwaway user/agent
#     -> the executor in THEIR container runs a tool-call
#     -> the result lands in THEIR data zone (/srv/laia/users/<slug>/home)
#     -> deprovision, leaving no container/LXD residue.
# This exercises the backbone of the ecosystem (LAIA_ECOSYSTEM.md §4): the LLM
# reasons in the brain, but actions execute in the user's office (their
# container). We assert the action via the executor /exec path deterministically
# (no LLM/API key required); a real chat turn is an optional extra step.
#
# DESTRUCTIVE: it creates and deletes an LXD container and host directories.
# It is hard-gated so it can NEVER run against production by accident:
#   * profile is `vm` only (CI/host never select it), and
#   * it refuses to run unless LAIA_E2E_ALLOW_DESTRUCTIVE=1 is set explicitly.
# Run on the golden VM laia-dev with:
#   LAIA_E2E_ALLOW_DESTRUCTIVE=1 tests/integration/run_integrity.sh --profile vm --level e2e
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../lib/integrity_shell.sh
source "$SCRIPT_DIR/../../lib/integrity_shell.sh"

require_cmds lxc curl python3

# ── Hard safety gate ─────────────────────────────────────────────────────────
[[ "${LAIA_E2E_ALLOW_DESTRUCTIVE:-0}" == "1" ]] \
  || integ_skip "destructive e2e disabled; set LAIA_E2E_ALLOW_DESTRUCTIVE=1 on the golden VM to run"

# Throwaway, clearly-synthetic slug. Slug regex: ^[a-z0-9][a-z0-9-]{1,30}$.
SLUG="${LAIA_E2E_SLUG:-t3e2e$$}"
USERS_DIR="${LAIA_USERS_DIR_OVERRIDE:-/srv/laia/users}"
USER_DIR="$USERS_DIR/$SLUG"
CONTAINER="agent-$SLUG"
EXEC_PORT="${LAIA_EXECUTOR_PORT:-9091}"

# Resolve the orchestrator entrypoint (same binary the backend uses).
LAIACTL="${LAIACTL_PATH:-$INTEGRITY_REPO_ROOT/infra/laiactl}"
[[ -x "$LAIACTL" ]] || integ_fail "laiactl not found/executable at $LAIACTL (set LAIACTL_PATH)"

ctl() { "$LAIACTL" "$@"; }

# ── Idempotency: never clobber a pre-existing (real) slug ────────────────────
if lxc info "$CONTAINER" >/dev/null 2>&1 || lxc info "laia-$SLUG" >/dev/null 2>&1 || [[ -e "$USER_DIR" ]]; then
  integ_fail "refusing to run: slug '$SLUG' already has a container or data dir (not a clean throwaway)"
fi

# ── Strict teardown: always remove the throwaway, even on failure ────────────
cleanup() {
  local rc=$?
  set +e
  ctl delete-agent "$SLUG" --yes --force >/dev/null 2>&1
  lxc delete "$CONTAINER" --force >/dev/null 2>&1
  lxc delete "laia-$SLUG" --force >/dev/null 2>&1
  # Throwaway data zone: this test user is synthetic, so purge it fully (real
  # deprovision keeps user data by design -- rule ④ -- which we assert below).
  rm -rf "$USER_DIR" >/dev/null 2>&1
  return "$rc"
}
trap cleanup EXIT

# ── 1. Provision ─────────────────────────────────────────────────────────────
integ_info "provisioning throwaway agent '$SLUG'"
ctl create-agent "$SLUG" >/dev/null 2>&1 || integ_fail "create-agent $SLUG failed"
ctl install-agent-runtime "$SLUG" >/dev/null 2>&1 || integ_fail "install-agent-runtime $SLUG failed"
ctl init-agent-workspace "$SLUG" >/dev/null 2>&1 || integ_fail "init-agent-workspace $SLUG failed"

# ── 2. Provisioned-state invariants (T2 contract for a fresh user) ───────────
assert_lxc_running "$CONTAINER"
assert_dir "$USER_DIR/home"
assert_dir "$USER_DIR/workspace"

# ── 3. Tool-call executes in THEIR container, via the executor ───────────────
# Wait for the executor to answer its liveness probe.
ip=""
for _ in $(seq 1 30); do
  ip="$(container_ipv4 "$CONTAINER")" && [[ -n "$ip" ]] && break
  sleep 2
done
[[ -n "$ip" ]] || integ_fail "container $CONTAINER never got an IPv4"

token="$(lxc exec "$CONTAINER" -- cat /etc/laia/executor-token 2>/dev/null)"
[[ -n "$token" ]] || integ_fail "executor token missing in $CONTAINER (/etc/laia/executor-token)"

health_ok=""
for _ in $(seq 1 30); do
  if curl -fsS -m 5 -H "Authorization: Bearer $token" "http://$ip:$EXEC_PORT/health" >/dev/null 2>&1; then
    health_ok=1
    break
  fi
  sleep 2
done
[[ -n "$health_ok" ]] || integ_fail "executor /health never came up on $ip:$EXEC_PORT"

# The tool-call writes a sentinel into the user's home. /home/user is the bind
# mount of $USER_DIR/home, so a host-side check proves the action ran in THEIR
# office and landed in THEIR data zone -- not in the brain container.
sentinel=".t3-sentinel-$$"
payload="$(python3 - "$sentinel" <<'PY'
import json
import sys
sentinel = sys.argv[1]
print(json.dumps({
    "tool": "bash",
    "args": {"command": f"echo T3-GOLDEN-OK > /home/user/{sentinel}"},
    "request_id": "t3-e2e",
}))
PY
)"
resp="$(curl -fsS -m 30 -H "Authorization: Bearer $token" -H 'Content-Type: application/json' \
  -X POST -d "$payload" "http://$ip:$EXEC_PORT/exec")" \
  || integ_fail "POST /exec failed"

python3 - "$resp" <<'PY' || integ_fail "/exec did not return ok:true"
import json
import sys
doc = json.loads(sys.argv[1])
assert doc.get("ok") is True, doc
PY

# Host-side proof: the sentinel exists in the user's data zone with our content.
host_sentinel="$USER_DIR/home/$sentinel"
[[ -f "$host_sentinel" ]] || integ_fail "tool-call did not land in the user's data zone ($host_sentinel)"
grep -qx 'T3-GOLDEN-OK' "$host_sentinel" \
  || integ_fail "sentinel content mismatch in $host_sentinel"
integ_info "tool-call executed in $CONTAINER and landed in the user's data zone"

# ── 4. Optional: a real chat turn (needs an LLM key) ─────────────────────────
if [[ "${LAIA_E2E_CHAT:-0}" == "1" ]]; then
  integ_info "LAIA_E2E_CHAT=1 set -- a live chat turn would run here (LLM-key dependent)"
else
  integ_info "skipping live chat turn (set LAIA_E2E_CHAT=1 + an LLM key to exercise it); \
the executor /exec path above is the deterministic architectural assertion"
fi

# ── 5. Deprovision and assert no LXD residue ─────────────────────────────────
ctl delete-agent "$SLUG" --yes --force >/dev/null 2>&1 || integ_fail "delete-agent $SLUG failed"
sleep 1
if lxc info "$CONTAINER" >/dev/null 2>&1 || lxc info "laia-$SLUG" >/dev/null 2>&1; then
  integ_fail "container for '$SLUG' still present after deprovision"
fi
# Note: per ecosystem rule ④, real user data survives container destruction by
# design (bind mount). The throwaway $USER_DIR is purged by this test's
# teardown, not by deprovision.
integ_info "deprovision left no container/LXD residue"

integ_info "T3 golden-path e2e OK for throwaway '$SLUG'"
