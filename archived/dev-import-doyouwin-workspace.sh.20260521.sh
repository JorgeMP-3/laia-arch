#!/usr/bin/env bash
# import-doyouwin-workspace.sh — copy /home/laia-hermes/.laia/workspaces/doyouwin
# into the AGORA data dir as a read-only secondary workspace.
#
# Run on the host (needs sudo: we write under /srv/laia and chown to the
# unprivileged agora uid). Idempotent: re-running overwrites the previous
# copy with the latest snapshot from ARCH.
#
# Usage:
#   sudo bash infra/dev/import-doyouwin-workspace.sh
#   sudo bash infra/dev/import-doyouwin-workspace.sh --refresh   # alias

set -euo pipefail

SRC="${SRC:-/home/laia-hermes/.laia/workspaces/doyouwin}"
DST_PARENT="${DST_PARENT:-/srv/laia/agora/workspaces}"
DST="$DST_PARENT/doyouwin"

if [[ ! -d "$SRC" ]]; then
  echo "error: source workspace $SRC missing" >&2
  exit 1
fi

if [[ $EUID -ne 0 ]]; then
  echo "Necesito sudo (escribo en /srv/laia y hago chown unpriv-id)." >&2
  exec sudo -E bash "$0" "$@"
fi

mkdir -p "$DST_PARENT"
# Wipe previous copy so removed files in ARCH don't linger.
rm -rf "$DST"
cp -r "$SRC" "$DST"

# Restore write bit on the .db so we can still ensure-schema if needed in
# the future, but the WorkspaceStore opens it via ``mode=ro`` URI +
# ``PRAGMA query_only=1``, which is the actual safety boundary.
chmod -R u+rw,go+r "$DST"
# Same idmap as the rest of /srv/laia/agora (unprivileged 100000:100000).
# This matches the bind-mount inside laia-agora where agora:agora sees it.
chown -R 100000:100000 "$DST" 2>/dev/null || true

echo "imported $SRC → $DST"
echo "$(du -sh "$DST" | cut -f1)"
echo
echo "Próximo paso (sin sudo):"
echo "  Reinicia el backend para que cargue el secondary workspace:"
echo "  lxc exec laia-agora -- systemctl restart agora-backend"
