#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <employee-slug> <snapshot-name>" >&2
  echo "Example: $0 jorge pre-update" >&2
}

if [[ $# -ne 2 ]]; then
  usage
  exit 1
fi

EMPLOYEE="$1"
SNAPSHOT="$2"
CONTAINER="${AGENT_CONTAINER_PREFIX:-agent-}${EMPLOYEE}"
LEGACY_CONTAINER="laia-${EMPLOYEE}"

if ! command -v lxc >/dev/null 2>&1; then
  echo "lxc command not found" >&2
  exit 1
fi

if ! lxc info "$CONTAINER" >/dev/null 2>&1; then
  if lxc info "$LEGACY_CONTAINER" >/dev/null 2>&1; then
    CONTAINER="$LEGACY_CONTAINER"
  else
    echo "Container not found: $CONTAINER (or legacy $LEGACY_CONTAINER)" >&2
    exit 1
  fi
fi

if ! lxc info "$CONTAINER" --all-projects | grep -q "$SNAPSHOT"; then
  echo "Snapshot not confirmed in lxc info output: $SNAPSHOT" >&2
  echo "Continuing may fail if the snapshot does not exist." >&2
fi

echo "About to restore $CONTAINER to snapshot $SNAPSHOT"
echo "This discards changes after the snapshot."
read -r -p "Type RESTORE to continue: " CONFIRM

if [[ "$CONFIRM" != "RESTORE" ]]; then
  echo "Cancelled"
  exit 1
fi

lxc restore "$CONTAINER" "$SNAPSHOT"
echo "Restored: $CONTAINER/$SNAPSHOT"
