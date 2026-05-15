#!/usr/bin/env bash
# create-agent.sh — provision a new child agent container from the laia-agent image.
#
# Generates a per-container api_token, writes agent.json, captures the bridge IP,
# starts the runtime + API services, and prints the connection info that AGORA
# needs to register the agent in its DB.
#
# Usage:
#   bash create-agent.sh <employee-slug> [image-alias]
#   bash create-agent.sh nombrix
#
# Output (last line, JSON): {"slug","container","ipv4","api_token","api_port"}

set -euo pipefail

usage() {
  echo "Usage: $0 <employee-slug> [image-alias]" >&2
  echo "Example: $0 nombrix laia-agent" >&2
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage
  exit 1
fi

EMPLOYEE="$1"
IMAGE="${2:-laia-agent}"
CONTAINER="laia-${EMPLOYEE}"
PROFILE="${PROFILE:-laia-employee}"
API_PORT="${API_PORT:-9090}"

if ! [[ "$EMPLOYEE" =~ ^[a-z0-9][a-z0-9-]{1,30}$ ]]; then
  echo "Invalid employee slug: $EMPLOYEE" >&2
  exit 1
fi

command -v lxc >/dev/null 2>&1 || { echo "lxc not found" >&2; exit 1; }

if lxc info "$CONTAINER" >/dev/null 2>&1; then
  echo "Container already exists: $CONTAINER" >&2
  exit 1
fi

lxc profile show "$PROFILE" >/dev/null 2>&1 || {
  echo "Missing LXD profile: $PROFILE" >&2
  echo "Create it first: bash infra/lxd/scripts/apply-profile.sh" >&2
  exit 1
}

lxc image info "$IMAGE" >/dev/null 2>&1 || {
  echo "Missing LXD image: $IMAGE" >&2
  echo "Build it first: bash infra/lxd/image-build/build-base-image.sh" >&2
  exit 1
}

# ── generate per-agent token ─────────────────────────────────────────────────

API_TOKEN=$(head -c 32 /dev/urandom | base64 | tr -d '+/=\n' | head -c 40)
[[ ${#API_TOKEN} -ge 32 ]] || { echo "Failed to generate api_token" >&2; exit 1; }

# ── launch container ────────────────────────────────────────────────────────

echo "Launching $CONTAINER from image $IMAGE..."
lxc launch "$IMAGE" "$CONTAINER" -p default -p "$PROFILE"

echo "Waiting for network..."
# Wait until container reports an IPv4
for i in {1..30}; do
  IPV4=$(lxc list "$CONTAINER" --format=csv -c4 2>/dev/null | awk '{print $1}')
  [[ -n "$IPV4" ]] && break
  sleep 1
done
[[ -n "$IPV4" ]] || { echo "Timed out waiting for IPv4" >&2; exit 1; }
echo "Container IP: $IPV4"

# ── write agent.json ────────────────────────────────────────────────────────

# Resolve AGORA backend URL: the host reachable from inside the container.
# Default: LXD bridge gateway (10.0.0.1). Override with AGORA_BACKEND_URL env.
AGORA_URL="${AGORA_BACKEND_URL:-http://10.0.0.1:8088}"

cat <<EOF | lxc exec "$CONTAINER" -- tee /opt/laia/agent.json >/dev/null
{
  "employee": "$EMPLOYEE",
  "container": "$CONTAINER",
  "workspace": "/opt/laia/workspaces/personal/workspace.db",
  "status": "created",
  "api_token": "$API_TOKEN",
  "bootstrap_token": "$API_TOKEN",
  "api_port": $API_PORT,
  "heartbeat_interval": 5,
  "agora_backend_url": "$AGORA_URL",
  "profile": "agora-agent"
}
EOF
# Also write AGORA_BACKEND_URL to the systemd environment so the agent
# wrapper can discover it without re-reading agent.json.
lxc exec "$CONTAINER" -- mkdir -p /etc/systemd/system/laia-agent-api.service.d
cat <<EOF | lxc exec "$CONTAINER" -- tee /etc/systemd/system/laia-agent-api.service.d/agora.conf >/dev/null
[Service]
Environment=AGORA_BACKEND_URL=$AGORA_URL
Environment=LAIA_PROFILE=agora-agent
EOF
lxc exec "$CONTAINER" -- systemctl daemon-reload
lxc exec "$CONTAINER" -- chown laia-agent:laia-agent /opt/laia/agent.json
lxc exec "$CONTAINER" -- chmod 0640 /opt/laia/agent.json

# ── start services ──────────────────────────────────────────────────────────

echo "Starting laia-agent.service and laia-agent-api.service..."
lxc exec "$CONTAINER" -- systemctl start laia-agent.service laia-agent-api.service

# ── verify API responds ─────────────────────────────────────────────────────

echo "Waiting for /health to respond..."
for i in {1..15}; do
  if curl -fsS "http://$IPV4:$API_PORT/health" >/dev/null 2>&1; then
    echo "  → /health OK"
    break
  fi
  sleep 1
done

# ── machine-readable summary ────────────────────────────────────────────────

echo ""
echo "Provisioned $CONTAINER successfully."
echo ""
echo "Register this agent in AGORA with the following values:"
echo "  slug:         $EMPLOYEE"
echo "  container:    $CONTAINER"
echo "  container_ip: $IPV4"
echo "  api_token:    $API_TOKEN"
echo "  api_port:     $API_PORT"
echo ""
echo "Last line is JSON for scripts:"
printf '{"slug":"%s","container":"%s","ipv4":"%s","api_token":"%s","api_port":%s}\n' \
  "$EMPLOYEE" "$CONTAINER" "$IPV4" "$API_TOKEN" "$API_PORT"
