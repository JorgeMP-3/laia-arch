#!/usr/bin/env bash
# Idempotent: create and permission the production state/data directories.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

LAIA_USER="${LAIA_USER:-${SUDO_USER:-${LAIA_ADMIN_USER:-}}}"
if [[ -z "$LAIA_USER" || "$LAIA_USER" == "root" ]]; then
  LAIA_USER=$(getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 {print $1; exit}')
fi
[[ -n "$LAIA_USER" ]] || { echo "Cannot determine LAIA_USER (set LAIA_USER or SUDO_USER)" >&2; exit 1; }

dirs=(
  /srv/laia
  /srv/laia/state
  /srv/laia/agora
  /srv/laia/agora/frontend
  /srv/laia/agents
  /srv/laia/backups
  /srv/laia/backups/state
  /srv/laia/backups/workspace
  /srv/laia/backups/snapshots
)

for d in "${dirs[@]}"; do
  install -d -m 0750 -o "$LAIA_USER" -g "$LAIA_USER" "$d"
  echo "  ok  $d"
done

# Copy existing dev state if present and prod state is empty
DEV_STATE="/home/${LAIA_USER}/LAIA/.laia/state/agents.json"
PROD_STATE="/srv/laia/state/agents.json"
if [[ -f "$DEV_STATE" && ! -f "$PROD_STATE" ]]; then
  install -m 0640 -o "$LAIA_USER" -g "$LAIA_USER" "$DEV_STATE" "$PROD_STATE"
  echo "  copied dev state → $PROD_STATE"
fi

echo
echo "Production directories ready."
echo "Next: sudo bash infra/scripts/install-agora-backend-service.sh"
