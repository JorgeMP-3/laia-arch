#!/usr/bin/env bash
set -euo pipefail

LAIA_ROOT="${LAIA_ROOT:-/home/laia-hermes/LAIA}"
DIST_SRC="$LAIA_ROOT/laia-ui/packages/agora-app/dist"
DIST_DST="${AGORA_FRONTEND_DIST:-/srv/laia/agora/frontend/dist}"

cd "$LAIA_ROOT/laia-ui"
pnpm build:agora

rm -rf "$DIST_DST"
mkdir -p "$(dirname "$DIST_DST")"
cp -r "$DIST_SRC" "$DIST_DST"

echo "AGORA frontend deployed to $DIST_DST"

