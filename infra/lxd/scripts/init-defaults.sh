#!/usr/bin/env bash
set -euo pipefail

POOL_NAME="${POOL_NAME:-default}"
NETWORK_NAME="${NETWORK_NAME:-lxdbr0}"
NETWORK_IPV4="${NETWORK_IPV4:-10.99.0.1/24}"

if ! command -v lxc >/dev/null 2>&1; then
  echo "lxc command not found" >&2
  exit 1
fi

if ! lxc version >/dev/null 2>&1; then
  echo "LXD is not responding" >&2
  exit 1
fi

if lxc storage list --format csv | cut -d, -f1 | grep -qx "$POOL_NAME"; then
  echo "Storage pool already exists: $POOL_NAME"
else
  lxc storage create "$POOL_NAME" dir
  echo "Created storage pool: $POOL_NAME (driver=dir)"
fi

if lxc network list --format csv | cut -d, -f1 | grep -qx "$NETWORK_NAME"; then
  echo "Network already exists: $NETWORK_NAME"
else
  lxc network create "$NETWORK_NAME" \
    ipv4.address="$NETWORK_IPV4" \
    ipv4.nat=true \
    ipv6.address=none
  echo "Created network: $NETWORK_NAME ($NETWORK_IPV4)"
fi

echo "LXD defaults ready."

