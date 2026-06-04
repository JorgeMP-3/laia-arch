#!/usr/bin/env bash
set -euo pipefail

BRIDGE="${BRIDGE:-lxdbr0}"
SUBNET="${SUBNET:-10.99.0.0/24}"
OUT_IF="${OUT_IF:-}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "This script must run as root. Use: sudo $0" >&2
  exit 1
fi

if [[ -z "$OUT_IF" ]]; then
  OUT_IF="$(ip route show default | awk 'NR == 1 {print $5}')"
fi

if [[ -z "$OUT_IF" ]]; then
  echo "Could not detect default outbound interface. Set OUT_IF=enp0s1." >&2
  exit 1
fi

echo "Using bridge=$BRIDGE subnet=$SUBNET out_if=$OUT_IF"

sysctl -w net.ipv4.ip_forward=1 >/dev/null
printf '%s\n' 'net.ipv4.ip_forward=1' >/etc/sysctl.d/99-laia-lxd-forward.conf

iptables -t nat -C POSTROUTING -s "$SUBNET" -o "$OUT_IF" -j MASQUERADE 2>/dev/null \
  || iptables -t nat -A POSTROUTING -s "$SUBNET" -o "$OUT_IF" -j MASQUERADE

iptables -C FORWARD -i "$BRIDGE" -o "$OUT_IF" -j ACCEPT 2>/dev/null \
  || iptables -I FORWARD 1 -i "$BRIDGE" -o "$OUT_IF" -j ACCEPT

iptables -C FORWARD -i "$OUT_IF" -o "$BRIDGE" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null \
  || iptables -I FORWARD 1 -i "$OUT_IF" -o "$BRIDGE" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT

echo "LAIA LXD egress rules applied."

if command -v lxc >/dev/null 2>&1 && lxc info agent-jorge-dev >/dev/null 2>&1; then
  echo "Testing agent-jorge-dev egress..."
  lxc exec agent-jorge-dev -- ping -c 1 -W 3 1.1.1.1
  lxc exec agent-jorge-dev -- curl -4 -I --max-time 8 http://ports.ubuntu.com/ubuntu-ports/dists/jammy/InRelease
fi
