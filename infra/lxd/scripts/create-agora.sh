#!/usr/bin/env bash
# create-agora.sh — provision the `laia-agora` orchestrator container.
#
# Steps:
#   1. Create /srv/laia/agora/ on the host (bind-mount source).
#   2. Launch `laia-agora` container from the `laia-agora` image.
#   3. Attach a disk device that bind-mounts /srv/laia/agora/ → /opt/agora/data/.
#   4. Add a proxy device that exposes container :8000 on host :HOST_PORT.
#   5. Start the agora-backend service.
#   6. Verify /health responds.
#
# Idempotent: refuses to clobber an existing container; use lxc delete first.
#
# Usage:
#   sudo bash create-agora.sh
#   HOST_PORT=8088 bash create-agora.sh

set -euo pipefail

IMAGE="${IMAGE:-laia-agora}"
CONTAINER="${CONTAINER:-laia-agora}"
PROFILE="${PROFILE:-laia-agora}"
HOST_PORT="${HOST_PORT:-8088}"
CONTAINER_PORT="${CONTAINER_PORT:-8000}"
HOST_DATA_DIR="${HOST_DATA_DIR:-/srv/laia/agora}"

command -v lxc >/dev/null 2>&1 || { echo "lxc not found" >&2; exit 1; }

if lxc info "$CONTAINER" >/dev/null 2>&1; then
  echo "Container already exists: $CONTAINER" >&2
  echo "Remove first with: lxc delete --force $CONTAINER" >&2
  exit 1
fi

lxc profile show "$PROFILE" >/dev/null 2>&1 \
  || { echo "Missing LXD profile: $PROFILE" >&2; exit 1; }

lxc image info "$IMAGE" >/dev/null 2>&1 \
  || { echo "Missing LXD image: $IMAGE (build with build-agora-image.sh)" >&2; exit 1; }

# ── host data dir ───────────────────────────────────────────────────────────

if [[ ! -d "$HOST_DATA_DIR" ]]; then
  echo "Creating host data dir: $HOST_DATA_DIR"
  if [[ "$EUID" -ne 0 ]]; then
    echo "Need root to create $HOST_DATA_DIR — rerun with sudo or create it manually." >&2
    exit 2
  fi
  mkdir -p "$HOST_DATA_DIR"
  # uid 100000 = LXD unprivileged container root. The post-mount chown
  # below tightens it to the `agora` service account once the container
  # is running and we can resolve the per-container uid mapping.
  chown -R 100000:100000 "$HOST_DATA_DIR"
fi

# ── launch ──────────────────────────────────────────────────────────────────

echo "Launching $CONTAINER from image $IMAGE..."
lxc launch "$IMAGE" "$CONTAINER" -p default -p "$PROFILE"

# Attach the data bind-mount (must be done before the service starts hitting it).
echo "Attaching bind mount: $HOST_DATA_DIR → /opt/agora/data"
lxc config device add "$CONTAINER" agora-data disk \
    source="$HOST_DATA_DIR" \
    path=/opt/agora/data

# Ensure /opt/agora/data is writable by the hardened agora service user
# inside the container. The unit runs as User=agora (A3 hardening), not
# root, so the bind-mounted dir needs the right ownership.
echo "Fixing ownership of /opt/agora/data inside container ..."
lxc exec "$CONTAINER" -- chown -R agora:agora /opt/agora/data 2>&1 || \
  echo "  (warn) chown failed — bind mount may need manual ownership fix" >&2

# Proxy device: host:HOST_PORT → container:CONTAINER_PORT
echo "Adding proxy device: host :$HOST_PORT → container :$CONTAINER_PORT"
lxc config device add "$CONTAINER" agora-api proxy \
    listen="tcp:0.0.0.0:${HOST_PORT}" \
    connect="tcp:127.0.0.1:${CONTAINER_PORT}"

# ── network + service ───────────────────────────────────────────────────────

echo "Waiting for network..."
for i in {1..30}; do
  IPV4=$(lxc list "$CONTAINER" --format=csv -c4 2>/dev/null | awk '{print $1}')
  [[ -n "$IPV4" ]] && break
  sleep 1
done
[[ -n "$IPV4" ]] || { echo "Timed out waiting for IPv4" >&2; exit 1; }
echo "Container IP: $IPV4"

echo "Starting agora-backend.service..."
lxc exec "$CONTAINER" -- systemctl start agora-backend.service

# ── verify ──────────────────────────────────────────────────────────────────

echo "Waiting for /health to respond on host port $HOST_PORT..."
for i in {1..30}; do
  if curl -fsS "http://127.0.0.1:${HOST_PORT}/health" >/dev/null 2>&1; then
    echo "  → /health OK"
    break
  fi
  sleep 1
done

if ! curl -fsS "http://127.0.0.1:${HOST_PORT}/health" >/dev/null 2>&1; then
  echo "WARNING: /health did not respond — inspect logs:" >&2
  echo "  lxc exec $CONTAINER -- journalctl -u agora-backend.service -n 50" >&2
fi

cat <<EOF

Provisioned $CONTAINER successfully.

  Container IP: $IPV4
  Host bind:    $HOST_DATA_DIR
  AGORA URL:    http://127.0.0.1:${HOST_PORT}

Quick check:
  curl http://127.0.0.1:${HOST_PORT}/health
  lxc exec $CONTAINER -- systemctl status agora-backend.service
EOF
