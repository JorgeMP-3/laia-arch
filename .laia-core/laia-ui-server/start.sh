#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="${LAIA_VENV:-$HOME/LAIA/.laia-arch/venv}"

# Build frontend if it exists
if [ -d "$SCRIPT_DIR/frontend" ]; then
  echo "Building frontend..."
  cd "$SCRIPT_DIR/frontend" && npm run build
  cd "$SCRIPT_DIR"
fi

echo ""
echo "Starting Workspace UI at http://localhost:8077"
echo "Swagger docs:          http://localhost:8077/docs"
echo ""

cd "$SCRIPT_DIR/backend"
"$VENV/bin/uvicorn" main:app --host 0.0.0.0 --port 8077 --reload
