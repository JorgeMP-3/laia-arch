#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="${LAIA_VENV:-$HOME/LAIA/.laia-core/venv}"

# Build frontend if it exists (pnpm is the LAIA convention)
if [ -d "$SCRIPT_DIR/frontend" ]; then
  echo "Building frontend..."
  cd "$SCRIPT_DIR/frontend" && pnpm run build
  cd "$SCRIPT_DIR"
fi

echo ""
echo "Starting Workspace UI at http://localhost:8077"
echo "Swagger docs:          http://localhost:8077/docs"
echo ""

cd "$SCRIPT_DIR/backend"
# Loopback only — operator console, never exposed (see backend/main.py).
"$VENV/bin/uvicorn" main:app --host "${LAIA_UI_HOST:-127.0.0.1}" --port 8077 --reload
