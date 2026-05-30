#!/usr/bin/env bash
# Idempotent: create and permission the production state/data directories.
set -euo pipefail

SRV_ROOT="${LAIA_SRV_DIR_OVERRIDE:-/srv/laia}"
OVERRIDE_MODE=false
if [[ -n "${LAIA_SRV_DIR_OVERRIDE:-}" ]]; then
  OVERRIDE_MODE=true
fi

if [[ "$OVERRIDE_MODE" != true && $EUID -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

LAIA_USER="${LAIA_USER:-${SUDO_USER:-${LAIA_ADMIN_USER:-}}}"
if [[ -z "$LAIA_USER" || "$LAIA_USER" == "root" ]]; then
  LAIA_USER=$(getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 {print $1; exit}')
fi
[[ -n "$LAIA_USER" ]] || { echo "Cannot determine LAIA_USER (set LAIA_USER or SUDO_USER)" >&2; exit 1; }

dirs=(
  "$SRV_ROOT"
  "$SRV_ROOT/state"
  "$SRV_ROOT/arch"
  "$SRV_ROOT/agora"
  "$SRV_ROOT/agora/frontend"
  "$SRV_ROOT/users"
  "$SRV_ROOT/backups"
  "$SRV_ROOT/backups/state"
  "$SRV_ROOT/backups/workspace"
  "$SRV_ROOT/backups/snapshots"
)

for d in "${dirs[@]}"; do
  if [[ "$OVERRIDE_MODE" == true ]]; then
    install -d -m 0750 "$d"
  else
    install -d -m 0750 -o "$LAIA_USER" -g "$LAIA_USER" "$d"
  fi
  echo "  ok  $d"
done

# C4 native layout (v2): ARCH secrets dir is stricter (0700) — secrets inside
# are 0600 and read by laia-agora via the C2 raw.idmap mount, never world-read.
if [[ "$OVERRIDE_MODE" == true ]]; then
  install -d -m 0700 "$SRV_ROOT/arch/secrets"
else
  install -d -m 0700 -o "$LAIA_USER" -g "$LAIA_USER" "$SRV_ROOT/arch/secrets"
fi
echo "  ok  $SRV_ROOT/arch/secrets (0700)"

# Copy existing dev state if present and prod state is empty
DEV_STATE="/home/${LAIA_USER}/LAIA/.laia/state/agents.json"
PROD_STATE="$SRV_ROOT/state/agents.json"
if [[ -f "$DEV_STATE" && ! -f "$PROD_STATE" ]]; then
  if [[ "$OVERRIDE_MODE" == true ]]; then
    install -m 0640 "$DEV_STATE" "$PROD_STATE"
  else
    install -m 0640 -o "$LAIA_USER" -g "$LAIA_USER" "$DEV_STATE" "$PROD_STATE"
  fi
  echo "  copied dev state → $PROD_STATE"
fi

echo
echo "Production directories ready."
echo "Next: sudo bash infra/scripts/install-agora-backend-service.sh"
