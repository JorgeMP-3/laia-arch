#!/usr/bin/env bash
# Sube todos los proyectos git de workspaces de LAIA a sus propias repos de GitHub.
# Crea la repo si no existe (privada por defecto).
#
# Uso: sync-workspaces-github.sh [--dry-run] [workspace-name]
#   --dry-run   Muestra lo que haría sin hacer cambios
#   workspace   Limita la sincronización a un workspace concreto

set -euo pipefail

LAIA_HOME="${HERMES_HOME:-$HOME/LAIA}"
WORKSPACES_DIR="$LAIA_HOME/workspaces"
DRY_RUN=false
TARGET_WS=""

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        *) TARGET_WS="$arg" ;;
    esac
done

# --- Dependencias ---
if ! command -v gh &>/dev/null; then
    echo "ERROR: gh CLI no instalado."
    echo "  Linux:  sudo apt install gh  /  snap install gh"
    echo "  macOS:  brew install gh"
    exit 1
fi

if ! gh auth status &>/dev/null 2>&1; then
    echo "ERROR: no autenticado en GitHub."
    echo "  Ejecuta: gh auth login"
    exit 1
fi

GH_USER=$(gh api user --jq .login 2>/dev/null)
echo "GitHub: $GH_USER  |  dry-run: $DRY_RUN"
echo "Workspaces: $WORKSPACES_DIR"
echo ""

# --- Función principal de sync ---
sync_repo() {
    local repo_path="$1"
    local repo_name="$2"

    (
        cd "$repo_path"

        # Commit cambios pendientes
        git add -A
        if ! git diff --cached --quiet 2>/dev/null; then
            git commit -q -m "sync: $(date '+%Y-%m-%d %H:%M')" 2>/dev/null || true
        fi

        # Normalizar nombre de rama a main
        local branch
        branch=$(git branch --show-current 2>/dev/null || echo "")
        if [ -z "$branch" ]; then
            git checkout -q -b main 2>/dev/null || true
            branch="main"
        elif [ "$branch" = "master" ]; then
            git branch -m master main 2>/dev/null || true
            branch="main"
        fi

        if [ "$DRY_RUN" = "true" ]; then
            echo "  [DRY] sync $repo_name → github.com/$GH_USER/$repo_name ($branch)"
            return
        fi

        # Crear/conectar remote
        if ! git remote get-url origin &>/dev/null; then
            if gh repo view "$GH_USER/$repo_name" &>/dev/null 2>&1; then
                git remote add origin "https://github.com/$GH_USER/$repo_name.git"
                echo "  → remote conectado: $GH_USER/$repo_name"
            else
                gh repo create "$repo_name" \
                    --private \
                    --description "LAIA workspace: $repo_name" \
                    --source=. \
                    --remote=origin \
                    --push \
                    2>&1 | grep -v "^$" || true
                echo "  ✓ repo creado: github.com/$GH_USER/$repo_name"
                return
            fi
        fi

        git push -u origin "$branch" -q 2>&1 | grep -v "^$" || echo "  AVISO: push fallido en $repo_name"
        echo "  ✓ $repo_name → github.com/$GH_USER/$repo_name ($branch)"
    )
}

process_workspace() {
    local ws_dir="$1"
    local ws_name
    ws_name=$(basename "$ws_dir")
    local ws_code="$ws_dir/code"

    [ -d "$ws_code" ] || return

    echo "=== $ws_name ==="
    local found=false

    # Subproyectos con git propio
    for subdir in "$ws_code"/*/; do
        [ -d "$subdir/.git" ] || continue
        local proj_name
        proj_name=$(basename "$subdir")
        sync_repo "$subdir" "$proj_name"
        found=true
    done

    # La carpeta code/ con git propio
    if [ -d "$ws_code/.git" ]; then
        sync_repo "$ws_code" "${ws_name}-code"
        found=true
    fi

    [ "$found" = false ] && echo "  Sin repos git. Ejecuta primero: init-workspace-git.sh $ws_name"
    echo ""
}

# --- Bucle principal ---
if [ -n "$TARGET_WS" ]; then
    ws_dir="$WORKSPACES_DIR/$TARGET_WS"
    [ -d "$ws_dir" ] || { echo "ERROR: workspace '$TARGET_WS' no encontrado"; exit 1; }
    process_workspace "$ws_dir"
else
    for ws_dir in "$WORKSPACES_DIR"/*/; do
        process_workspace "$ws_dir"
    done
fi

echo "Sincronización completada."
