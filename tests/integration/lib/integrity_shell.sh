#!/usr/bin/env bash
# Shared shell helpers for LAIA integrity modules. Tests source this file and
# then exit 0/pass, 1/fail, or 77/explicit skip for the Python runner.

INTEGRITY_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INTEGRITY_REPO_ROOT="$(cd "$INTEGRITY_LIB_DIR/../../.." && pwd)"

integ_info() {
  printf 'INFO: %s\n' "$*"
}

integ_fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

integ_skip() {
  printf 'SKIP: %s\n' "$*"
  exit 77
}

require_cmds() {
  local cmd
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || integ_skip "missing command: $cmd"
  done
}

mode_of() {
  stat -c '%a' "$1" 2>/dev/null
}

assert_dir() {
  [[ -d "$1" ]] || integ_fail "missing directory: $1"
}

assert_file() {
  [[ -f "$1" ]] || integ_fail "missing file: $1"
}

assert_mode() {
  local path="$1" expected="$2" actual
  actual="$(mode_of "$path")"
  [[ "$actual" == "$expected" ]] || integ_fail "$path mode=$actual, expected $expected"
}

lxc_container_state() {
  local container="$1"
  lxc list "$container" -c s --format csv 2>/dev/null | head -1
}

assert_lxc_running() {
  local container="$1" state
  state="$(lxc_container_state "$container")"
  [[ "$state" == "RUNNING" ]] || integ_fail "container $container state=${state:-absent}, expected RUNNING"
}

container_ipv4() {
  local container="$1"
  lxc list "$container" --format json 2>/dev/null | python3 -c '
import json
import sys

container = sys.argv[1]
try:
    doc = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(1)

for item in doc:
    if item.get("name") != container:
        continue
    network = item.get("state", {}).get("network", {})
    for iface in network.values():
        for addr in iface.get("addresses", []):
            if addr.get("family") == "inet" and addr.get("address"):
                print(addr["address"])
                sys.exit(0)
sys.exit(1)
' "$container"
}

agent_container_count() {
  command -v lxc >/dev/null 2>&1 || {
    printf '0\n'
    return 0
  }
  lxc list -c n --format csv 2>/dev/null | awk '$1 ~ /^agent-/ {n++} END {print n + 0}'
}

agora_health_json() {
  local container="${1:-${CONTAINER:-laia-agora}}"
  local port="${2:-${AGORA_HEALTH_PORT:-8000}}"
  local ip
  ip="$(container_ipv4 "$container")" || return 1
  [[ -n "$ip" ]] || return 1
  curl -fsS -m 5 "http://${ip}:${port}/api/health"
}

assert_health_ok() {
  local health="$1"
  python3 - "$health" <<'PY' || integ_fail "/api/health does not report ok:true and auth_json_ready:true"
import json
import sys

doc = json.loads(sys.argv[1])
assert doc.get("ok") is True, doc
assert doc.get("auth_json_ready") is True, doc
PY
}
