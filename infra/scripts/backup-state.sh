#!/usr/bin/env bash
# Backup: LXD state JSON + workspace DBs.
# Run as laia-hermes or root (LXD snapshots need root).
set -euo pipefail

if [[ -z "${LAIA_ROOT:-}" ]]; then
  _script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  LAIA_ROOT="$(git -C "$_script_dir" rev-parse --show-toplevel 2>/dev/null || cd "$_script_dir/../.." && pwd)"
  unset _script_dir
fi
BACKUP_ROOT="${BACKUP_ROOT:-/srv/laia/backups}"
TS=$(date +%Y%m%d-%H%M%S)
STATE_SRC="${LAIA_STATE_ROOT:-${LAIA_ROOT}/.laia/state}"
AGORA_DATA="${AGORA_DATA_DIR:-/srv/laia/agora}"

# ── 1. State JSON ─────────────────────────────────────────────────────────────
STATE_DST="${BACKUP_ROOT}/state/${TS}-agents.json"
if [[ -f "${STATE_SRC}/agents.json" ]]; then
  cp "${STATE_SRC}/agents.json" "$STATE_DST"
  echo "  state   → $STATE_DST"
fi

# ── 2. AGORA data (users, tasks, events) ─────────────────────────────────────
if [[ -d "$AGORA_DATA" ]]; then
  AGORA_DST="${BACKUP_ROOT}/state/${TS}-agora-data.tar.gz"
  tar -czf "$AGORA_DST" -C "$(dirname "$AGORA_DATA")" "$(basename "$AGORA_DATA")" 2>/dev/null || true
  echo "  agora   → $AGORA_DST"
fi

# ── 3. Personal workspace DBs from containers ─────────────────────────────────
CONTAINERS=$(lxc list --format csv 2>/dev/null | awk -F',' '/^laia-/ {print $1}' || true)
for container in $CONTAINERS; do
  slug="${container#laia-}"
  WS_DST="${BACKUP_ROOT}/workspace/${TS}-${slug}-workspace.db"
  if lxc exec "$container" -- test -s /opt/laia/workspaces/personal/workspace.db 2>/dev/null; then
    lxc file pull "${container}/opt/laia/workspaces/personal/workspace.db" "$WS_DST" 2>/dev/null && \
      echo "  ws      → $WS_DST" || true
  fi
done

# ── 4. LXD snapshots (optional, slow) ────────────────────────────────────────
if [[ "${SNAPSHOT:-0}" == "1" ]]; then
  for container in $CONTAINERS; do
    snap_name="backup-${TS}"
    lxc snapshot "$container" "$snap_name" && \
      echo "  snapshot $container/$snap_name" || true
  done
fi

echo
echo "Backup complete: ${BACKUP_ROOT}"
