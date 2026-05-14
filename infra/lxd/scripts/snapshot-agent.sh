#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <employee-slug> [snapshot-name]" >&2
  echo "Example: $0 jorge pre-update" >&2
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage
  exit 1
fi

EMPLOYEE="$1"
SNAPSHOT="${2:-manual-$(date -u +%Y%m%dT%H%M%SZ)}"
CONTAINER="laia-${EMPLOYEE}"

if ! command -v lxc >/dev/null 2>&1; then
  echo "lxc command not found" >&2
  exit 1
fi

if ! lxc info "$CONTAINER" >/dev/null 2>&1; then
  echo "Container not found: $CONTAINER" >&2
  exit 1
fi

lxc snapshot "$CONTAINER" "$SNAPSHOT"
echo "Snapshot created: $CONTAINER/$SNAPSHOT"

