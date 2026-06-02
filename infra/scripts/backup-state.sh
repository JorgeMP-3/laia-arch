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

# Sin esto, el primer cp/tar falla contra un destino inexistente
# (/srv/laia/backups no se crea en ningún otro sitio).
mkdir -p "${BACKUP_ROOT}/state" "${BACKUP_ROOT}/workspace"

# ── 1. State JSON ─────────────────────────────────────────────────────────────
STATE_DST="${BACKUP_ROOT}/state/${TS}-agents.json"
if [[ -f "${STATE_SRC}/agents.json" ]]; then
  cp "${STATE_SRC}/agents.json" "$STATE_DST"
  echo "  state   → $STATE_DST"
fi

# ── 2. AGORA data (users, tasks, events) ─────────────────────────────────────
# Sin `|| true` ni `2>/dev/null`: si un paso falla, el script ABORTA (set -e)
# con el error visible. Un backup que falla en silencio y reporta verde es
# exactamente el patrón del outage del cutover 2026-05-30.
if [[ -d "$AGORA_DATA" ]]; then
  AGORA_DB="${AGORA_DATA}/agora.db"
  if [[ -f "$AGORA_DB" ]]; then
    command -v sqlite3 >/dev/null 2>&1 \
      || { echo "ERROR: sqlite3 no instalado — copiar una SQLite EN USO sin .backup produce un artefacto corrupto." >&2; exit 1; }
    DB_DST="${BACKUP_ROOT}/state/${TS}-agora.db"
    # `.backup` = snapshot consistente de la DB en uso (incluye el -wal);
    # un tar/cp del archivo vivo puede capturar media transacción.
    sqlite3 -readonly "$AGORA_DB" ".timeout 5000" ".backup '$DB_DST'"
    echo "  agoradb → $DB_DST"
  fi
  AGORA_DST="${BACKUP_ROOT}/state/${TS}-agora-data.tar.gz"
  # El resto del dir, sin la DB viva ni sus journals (van aparte, arriba).
  tar -czf "$AGORA_DST" -C "$(dirname "$AGORA_DATA")" \
    --exclude="$(basename "$AGORA_DATA")/agora.db" \
    --exclude="$(basename "$AGORA_DATA")/agora.db-wal" \
    --exclude="$(basename "$AGORA_DATA")/agora.db-shm" \
    "$(basename "$AGORA_DATA")"
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
