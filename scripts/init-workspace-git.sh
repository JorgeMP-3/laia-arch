#!/usr/bin/env bash
# Inicializa repos git en las carpetas code/ de todos los workspaces de LAIA.
# Se puede llamar manualmente o integrarse en create-workspace.py.

set -euo pipefail

LAIA_HOME="${HERMES_HOME:-$HOME/LAIA}"
WORKSPACES_DIR="$LAIA_HOME/workspaces"

# Workspace específico (opcional): init-workspace-git.sh [nombre]
TARGET_WS="${1:-}"

echo "LAIA workspaces: $WORKSPACES_DIR"
echo ""

_gitignore() {
    cat << 'EOF'
# macOS
.DS_Store
# Node.js
node_modules/
npm-debug.log*
# Python
__pycache__/
*.pyc
.venv/
# Xcode / iOS
DerivedData/
*.xcworkspace/xcuserdata/
*.xcuserstate
.build/
Pods/
# Environment
.env
*.env.local
# Logs
*.log
EOF
}

init_git() {
    local dir="$1"
    local label="$2"

    (
        cd "$dir"
        git init -q
        _gitignore > .gitignore
        git add -A
        git commit -q -m "chore: init workspace — $label" 2>/dev/null || true
    )
    echo "  ✓ git init — $label"
}

process_workspace() {
    local ws_dir="$1"
    local ws_name
    ws_name=$(basename "$ws_dir")
    local ws_code="$ws_dir/code"

    [ -d "$ws_code" ] || return

    echo "=== $ws_name ==="

    local found_subgit=false

    for subdir in "$ws_code"/*/; do
        [ -d "$subdir" ] || continue
        if [ -d "$subdir/.git" ]; then
            echo "  ✓ ya existe — $ws_name/code/$(basename "$subdir")"
            found_subgit=true
        fi
    done

    if [ -d "$ws_code/.git" ]; then
        echo "  ✓ ya existe — $ws_name/code"
    elif [ "$found_subgit" = false ]; then
        init_git "$ws_code" "$ws_name/code"
    fi
    echo ""
}

if [ -n "$TARGET_WS" ]; then
    ws_dir="$WORKSPACES_DIR/$TARGET_WS"
    if [ ! -d "$ws_dir" ]; then
        echo "ERROR: workspace '$TARGET_WS' no encontrado en $WORKSPACES_DIR"
        exit 1
    fi
    process_workspace "$ws_dir"
else
    for ws_dir in "$WORKSPACES_DIR"/*/; do
        process_workspace "$ws_dir"
    done
fi

echo "Listo. Usa sync-workspaces-github.sh para subir a GitHub."
