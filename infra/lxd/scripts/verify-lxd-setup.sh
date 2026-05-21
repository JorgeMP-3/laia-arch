#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${LAIA_ROOT:-}" ]]; then
  _script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  LAIA_ROOT="$(git -C "$_script_dir" rev-parse --show-toplevel 2>/dev/null || cd "$_script_dir/../../.." && pwd)"
  unset _script_dir
fi
[[ -d "$LAIA_ROOT/infra/lxd/scripts" ]] || { echo "Cannot resolve LAIA_ROOT (pass it explicitly)" >&2; exit 1; }

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
