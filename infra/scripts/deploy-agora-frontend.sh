#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${LAIA_ROOT:-}" ]]; then
  _script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  LAIA_ROOT="$(git -C "$_script_dir" rev-parse --show-toplevel 2>/dev/null || cd "$_script_dir/../.." && pwd)"
  unset _script_dir
fi
DIST_SRC="$LAIA_ROOT/laia-ui/packages/agora-app/dist"
DIST_DST="${AGORA_FRONTEND_DIST:-/srv/laia/agora/frontend/dist}"

cd "$LAIA_ROOT/laia-ui"
pnpm build:agora

rm -rf "$DIST_DST"
mkdir -p "$(dirname "$DIST_DST")"
cp -r "$DIST_SRC" "$DIST_DST"

echo "AGORA frontend deployed to $DIST_DST"

