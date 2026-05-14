#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <employee-slug> [image-alias]" >&2
  echo "Example: $0 jorge laia-agent" >&2
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage
  exit 1
fi

EMPLOYEE="$1"
IMAGE="${2:-laia-agent}"
CONTAINER="laia-${EMPLOYEE}"

if ! [[ "$EMPLOYEE" =~ ^[a-z0-9][a-z0-9-]{1,30}$ ]]; then
  echo "Invalid employee slug: $EMPLOYEE" >&2
  exit 1
fi

if ! command -v lxc >/dev/null 2>&1; then
  echo "lxc command not found" >&2
  exit 1
fi

if lxc info "$CONTAINER" >/dev/null 2>&1; then
  echo "Container already exists: $CONTAINER" >&2
  exit 1
fi

if ! lxc profile show laia-employee >/dev/null 2>&1; then
  echo "Missing LXD profile: laia-employee" >&2
  echo "Create it first with:" >&2
  echo "  infra/lxd/scripts/apply-profile.sh" >&2
  exit 1
fi

if ! lxc image info "$IMAGE" >/dev/null 2>&1; then
  echo "Missing LXD image: $IMAGE" >&2
  echo "Build/publish it first. See infra/lxd/image-build/README.md" >&2
  exit 1
fi

lxc launch "$IMAGE" "$CONTAINER" -p default -p laia-employee

echo "Waiting for container to boot..."
sleep 3

lxc exec "$CONTAINER" -- mkdir -p \
  /opt/laia/workspaces/personal \
  /opt/laia/data \
  /opt/laia/runtime \
  /opt/laia/logs

cat <<EOF | lxc exec "$CONTAINER" -- tee /opt/laia/agent.json >/dev/null
{
  "employee": "$EMPLOYEE",
  "container": "$CONTAINER",
  "workspace": "/opt/laia/workspaces/personal/workspace.db",
  "status": "created"
}
EOF

echo "Created $CONTAINER"
echo "Next: initialize WorkspaceStore inside /opt/laia/workspaces/personal"
