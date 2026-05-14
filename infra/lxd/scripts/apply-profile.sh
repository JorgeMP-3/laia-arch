#!/usr/bin/env bash
set -euo pipefail

LAIA_ROOT="${LAIA_ROOT:-/home/laia-hermes/LAIA}"
PROFILE_NAME="${PROFILE_NAME:-laia-employee}"
PROFILE_FILE="${PROFILE_FILE:-$LAIA_ROOT/infra/lxd/profiles/laia-employee.yaml}"

if ! command -v lxc >/dev/null 2>&1; then
  echo "lxc command not found" >&2
  exit 1
fi

if [[ ! -f "$PROFILE_FILE" ]]; then
  echo "Profile file not found: $PROFILE_FILE" >&2
  exit 1
fi

if ! lxc version >/dev/null 2>&1; then
  echo "LXD is not responding. Run infra/lxd/scripts/check-host.sh first." >&2
  exit 1
fi

if ! lxc profile show "$PROFILE_NAME" >/dev/null 2>&1; then
  lxc profile create "$PROFILE_NAME"
fi

lxc profile edit "$PROFILE_NAME" < "$PROFILE_FILE"
lxc profile show "$PROFILE_NAME" >/dev/null

echo "Applied LXD profile: $PROFILE_NAME"

