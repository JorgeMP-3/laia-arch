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

# B1 finding: UFW with a default-drop FORWARD/INPUT policy silently blocks every
# LXD bridge — the bridge's own nftables accept rules lose to UFW's terminal
# drop, so the container gets no DHCP/DNS/egress. A bridge needs an explicit
# `ufw allow in on <br>` (host-bound traffic: DHCP/DNS) AND `ufw route allow in
# on <br>` (forwarded egress). Idempotent; only when ufw is installed + active.
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -qi '^Status: active'; then
  if ufw allow in on "$NETWORK_NAME" >/dev/null 2>&1 \
     && ufw route allow in on "$NETWORK_NAME" >/dev/null 2>&1; then
    echo "UFW: allowed in/route-in on $NETWORK_NAME (bridge DHCP/DNS/egress)"
  else
    echo "WARN: could not apply UFW rules for $NETWORK_NAME — if containers have no" >&2
    echo "      network, run: sudo ufw allow in on $NETWORK_NAME && sudo ufw route allow in on $NETWORK_NAME" >&2
  fi
fi

echo "LXD defaults ready."

