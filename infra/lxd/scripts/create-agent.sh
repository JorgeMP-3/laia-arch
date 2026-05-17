#!/usr/bin/env bash
# create-agent.sh — provision a new per-user LXD container running laia-executor.
#
# Architecture (post-redesign):
#   - The container holds NO LLM brain. It runs `laia-executor` (FastAPI :9091)
#     which AGORA forwards filesystem/bash tool calls to over the LXD bridge.
#   - The user is root inside the container. No sandbox, no command blacklist.
#   - Persistent data lives on the host under /srv/laia/users/<slug>/ and is
#     bind-mounted into the container so files survive container recreation.
#
# Bind mounts (host → container):
#   /srv/laia/users/<slug>/home       →  /home/user
#   /srv/laia/users/<slug>/plugins    →  /opt/laia/plugins
#   /srv/laia/users/<slug>/workspace  →  /var/lib/laia/workspace
#
# Usage:
#   sudo bash create-agent.sh <slug> [image-alias]
#   sudo bash create-agent.sh jorge
#
# Output (last line, JSON): {"slug","container","ipv4","api_token","api_port"}

set -euo pipefail

usage() {
  echo "Usage: $0 <slug> [image-alias]" >&2
  echo "Example: $0 jorge laia-agent" >&2
  echo "Run with sudo so the host /srv/laia/users/<slug>/ dirs can be created." >&2
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage
  exit 1
fi

SLUG="$1"
IMAGE="${2:-laia-agent}"
CONTAINER="laia-${SLUG}"
PROFILE="${PROFILE:-laia-employee}"
API_PORT="${API_PORT:-9091}"
HOST_USER_ROOT="${HOST_USER_ROOT:-/srv/laia/users}"
LXD_UID_OFFSET="${LXD_UID_OFFSET:-100000}"

if ! [[ "$SLUG" =~ ^[a-z0-9][a-z0-9_-]{1,30}$ ]]; then
  echo "Invalid slug: $SLUG (must match ^[a-z0-9][a-z0-9_-]{1,30}$ — letters, digits, '_' or '-')" >&2
  exit 1
fi

command -v lxc >/dev/null 2>&1 || { echo "lxc not found" >&2; exit 1; }

if lxc info "$CONTAINER" >/dev/null 2>&1; then
  echo "Container already exists: $CONTAINER" >&2
  echo "Remove first with: lxc delete --force $CONTAINER" >&2
  exit 1
fi

lxc profile show "$PROFILE" >/dev/null 2>&1 || {
  echo "Missing LXD profile: $PROFILE" >&2
  echo "Apply it with: lxc profile create $PROFILE && lxc profile edit $PROFILE < infra/lxd/profiles/laia-employee.yaml" >&2
  exit 1
}

lxc image info "$IMAGE" >/dev/null 2>&1 || {
  echo "Missing LXD image: $IMAGE" >&2
  echo "Build it first: bash infra/lxd/image-build/build-base-image.sh" >&2
  exit 1
}

# ── host data dirs ──────────────────────────────────────────────────────────

USER_DIR="${HOST_USER_ROOT}/${SLUG}"
if [[ ! -d "$USER_DIR" ]]; then
  if [[ "$EUID" -ne 0 ]]; then
    echo "Need root to create $USER_DIR — rerun with sudo." >&2
    exit 2
  fi
  echo "Creating host data dirs under $USER_DIR ..."
  mkdir -p "$USER_DIR/home" "$USER_DIR/plugins" "$USER_DIR/workspace"
  # LXD unprivileged root inside container maps to uid LXD_UID_OFFSET on the host
  # (default 100000). Owning the bind sources with that uid lets the in-container
  # user write freely.
  chown -R "${LXD_UID_OFFSET}:${LXD_UID_OFFSET}" "$USER_DIR"
  chmod -R 0755 "$USER_DIR"
fi

# ── generate per-agent token ─────────────────────────────────────────────────

API_TOKEN=$(head -c 32 /dev/urandom | base64 | tr -d '+/=\n' | head -c 40)
[[ ${#API_TOKEN} -ge 32 ]] || { echo "Failed to generate api_token" >&2; exit 1; }

# ── create container (do not start yet — we attach devices first) ───────────

echo "Initializing $CONTAINER from image $IMAGE..."
lxc init "$IMAGE" "$CONTAINER" -p default -p "$PROFILE"

# Attach bind-mount devices BEFORE first boot so the executor service sees them.
echo "Attaching bind mounts ..."
lxc config device add "$CONTAINER" home disk \
    source="${USER_DIR}/home" \
    path=/home/user
lxc config device add "$CONTAINER" plugins disk \
    source="${USER_DIR}/plugins" \
    path=/opt/laia/plugins
lxc config device add "$CONTAINER" workspace disk \
    source="${USER_DIR}/workspace" \
    path=/var/lib/laia/workspace

echo "Starting $CONTAINER ..."
lxc start "$CONTAINER"

echo "Waiting for network..."
IPV4=""
for _ in {1..30}; do
  IPV4=$(lxc list "$CONTAINER" --format=csv -c4 2>/dev/null | awk '{print $1}')
  [[ -n "$IPV4" ]] && break
  sleep 1
done
[[ -n "$IPV4" ]] || { echo "Timed out waiting for IPv4" >&2; exit 1; }
echo "Container IP: $IPV4"

# ── write executor token + minimal agent.json ───────────────────────────────

echo "Installing executor token and config ..."
lxc exec "$CONTAINER" -- mkdir -p /etc/laia
# Token file: read by laia-executor at startup (LAIA_EXECUTOR_TOKEN_FILE).
echo "$API_TOKEN" | lxc exec "$CONTAINER" -- tee /etc/laia/executor-token >/dev/null
lxc exec "$CONTAINER" -- chmod 0600 /etc/laia/executor-token

# Minimal agent.json — only what the executor needs to identify itself.
cat <<EOF | lxc exec "$CONTAINER" -- tee /etc/laia/agent.json >/dev/null
{
  "slug": "$SLUG",
  "container": "$CONTAINER",
  "api_port": $API_PORT,
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
lxc exec "$CONTAINER" -- chmod 0644 /etc/laia/agent.json

# ── start the executor service ──────────────────────────────────────────────

echo "Enabling and starting laia-executor.service ..."
lxc exec "$CONTAINER" -- systemctl enable --now laia-executor.service || {
  echo "WARN: laia-executor.service did not start cleanly — check the image build." >&2
  echo "  lxc exec $CONTAINER -- journalctl -u laia-executor.service -n 50" >&2
}

# ── verify /health ──────────────────────────────────────────────────────────

echo "Waiting for /health on $IPV4:$API_PORT ..."
HEALTHY=0
for _ in {1..30}; do
  if curl -fsS "http://$IPV4:$API_PORT/health" >/dev/null 2>&1; then
    HEALTHY=1
    break
  fi
  sleep 1
done
if [[ "$HEALTHY" -eq 1 ]]; then
  echo "  → /health OK"
else
  echo "  → /health did not respond — inspect logs:" >&2
  echo "    lxc exec $CONTAINER -- journalctl -u laia-executor.service -n 50" >&2
fi

# ── summary ─────────────────────────────────────────────────────────────────

cat <<EOF

Provisioned $CONTAINER successfully.

Register this agent in AGORA with:
  slug:         $SLUG
  container:    $CONTAINER
  container_ip: $IPV4
  api_token:    $API_TOKEN
  api_port:     $API_PORT

Host data lives at:
  $USER_DIR/home       → /home/user        (user files)
  $USER_DIR/plugins    → /opt/laia/plugins (user plugins)
  $USER_DIR/workspace  → /var/lib/laia/workspace (private workspace.db)

Last line is JSON for scripts:
EOF
printf '{"slug":"%s","container":"%s","ipv4":"%s","api_token":"%s","api_port":%s}\n' \
  "$SLUG" "$CONTAINER" "$IPV4" "$API_TOKEN" "$API_PORT"
