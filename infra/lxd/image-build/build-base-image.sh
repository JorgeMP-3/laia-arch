#!/usr/bin/env bash
set -euo pipefail

BASE_IMAGE="${BASE_IMAGE:-ubuntu:22.04}"
BASE_CONTAINER="${BASE_CONTAINER:-laia-agent-base}"
ALIAS="${ALIAS:-laia-agent}"
PROFILE="${PROFILE:-laia-employee}"

if ! command -v lxc >/dev/null 2>&1; then
  echo "lxc command not found" >&2
  exit 1
fi

if ! lxc profile show "$PROFILE" >/dev/null 2>&1; then
  echo "Missing LXD profile: $PROFILE" >&2
  exit 1
fi

if lxc info "$BASE_CONTAINER" >/dev/null 2>&1; then
  echo "Base container already exists: $BASE_CONTAINER" >&2
  echo "Delete it manually or set BASE_CONTAINER to another name." >&2
  exit 1
fi

if lxc image info "$ALIAS" >/dev/null 2>&1; then
  echo "Image alias already exists: $ALIAS" >&2
  echo "Delete it manually before rebuilding, or set ALIAS to a new value." >&2
  exit 1
fi

lxc launch "$BASE_IMAGE" "$BASE_CONTAINER" -p default -p "$PROFILE"

echo "Waiting for network..."
sleep 8

lxc exec "$BASE_CONTAINER" -- bash -lc '
  set -euo pipefail
  export DEBIAN_FRONTEND=noninteractive
  if apt-get update && apt-get install -y python3 python3-venv python3-pip git curl ca-certificates jq; then
    echo "Package installation complete."
  else
    echo "WARNING: apt install failed. Continuing only if base image already has required tools." >&2
  fi
  command -v python3 >/dev/null
  command -v git >/dev/null
  command -v curl >/dev/null
  mkdir -p /opt/laia/workspaces/personal /opt/laia/data /opt/laia/runtime /opt/laia/logs
  python3 -m venv /opt/laia/runtime/venv || python3 -m venv --without-pip /opt/laia/runtime/venv
  cat > /opt/laia/agent.json <<JSON
{
  "image": "laia-agent",
  "workspace": "/opt/laia/workspaces/personal/workspace.db",
  "status": "base-image"
}
JSON
  cat > /opt/laia/healthcheck.sh <<SH
#!/usr/bin/env bash
set -euo pipefail
test -d /opt/laia/workspaces/personal
test -d /opt/laia/data
test -d /opt/laia/runtime
test -x /usr/bin/python3
test -x /usr/bin/git
test -x /usr/bin/curl
test -x /opt/laia/runtime/venv/bin/python
echo "laia-agent-ok"
SH
  chmod +x /opt/laia/healthcheck.sh
'

lxc exec "$BASE_CONTAINER" -- /opt/laia/healthcheck.sh
lxc stop "$BASE_CONTAINER"
lxc publish "$BASE_CONTAINER" --alias "$ALIAS"
lxc delete "$BASE_CONTAINER"

echo "Published image: $ALIAS"
