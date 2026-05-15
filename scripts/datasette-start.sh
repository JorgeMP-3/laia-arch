#!/bin/bash
# Lanza Datasette con todos los workspaces de Hermes en http://localhost:8076

PORT=8076
LAIA_HOME="${LAIA_HOME:-$HOME/.laia}"
if [ -f "$LAIA_HOME/.env.paths" ]; then
  # shellcheck disable=SC1091
  . "$LAIA_HOME/.env.paths"
fi
WORKSPACES_DIR="${LAIA_WORKSPACES:-$LAIA_HOME/workspaces}"
DBS_DIR="$LAIA_HOME/cache/datasette-dbs"

# Sincronizar symlinks con los workspaces actuales
mkdir -p "$DBS_DIR"
for db in "$WORKSPACES_DIR"/*/workspace.db; do
  ws=$(basename "$(dirname "$db")")
  ln -sf "$db" "$DBS_DIR/${ws}.db"
done

# Matar instancia previa si existe
pkill -f "datasette.*8076" 2>/dev/null
sleep 0.5

echo "Iniciando Datasette en http://localhost:$PORT"
datasette "$DBS_DIR"/*.db --port "$PORT" --host 0.0.0.0
