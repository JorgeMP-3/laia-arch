#!/usr/bin/env bash
set -euo pipefail

LAIA_ROOT="${LAIA_ROOT:-/home/laia-hermes/LAIA}"

"$LAIA_ROOT/infra/lxd/scripts/check-host.sh"

echo
echo "Profile laia-employee:"
lxc profile show laia-employee

echo
echo "Images matching laia-agent:"
if ! lxc image list --format csv 2>/dev/null | grep -E 'laia-agent' || true; then
  true
fi

echo
echo "Existing LAIA agent containers:"
if ! lxc list --format csv 2>/dev/null | grep -E '^laia-' || true; then
  true
fi

echo "LXD setup verification complete."
