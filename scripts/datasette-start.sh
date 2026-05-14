#!/bin/bash
# Lanza Datasette con todos los workspaces de Hermes en http://localhost:8076

PORT=8076
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
DBS_DIR="$HERMES_HOME/cache/datasette-dbs"

# Sincronizar symlinks con los workspaces actuales
mkdir -p "$DBS_DIR"
for db in "$HERMES_HOME/workspaces"/*/workspace.db; do
  ws=$(basename "$(dirname "$db")")
  ln -sf "$db" "$DBS_DIR/${ws}.db"
done

# Matar instancia previa si existe
pkill -f "datasette.*8076" 2>/dev/null
sleep 0.5

echo "Iniciando Datasette en http://localhost:$PORT"
datasette "$DBS_DIR"/*.db --port "$PORT" --host 0.0.0.0
