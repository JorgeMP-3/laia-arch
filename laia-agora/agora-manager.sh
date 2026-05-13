#!/bin/bash
# agora-manager.sh — Gestión de contenedores LAIA-AGORA
#
# Uso:
#   ./agora-manager.sh add <nombre>     — Crear y arrancar agente para un usuario
#   ./agora-manager.sh remove <nombre>  — Parar y eliminar contenedor (datos conservados)
#   ./agora-manager.sh list             — Estado de todos los contenedores agora
#   ./agora-manager.sh status           — Docker stats en tiempo real
#   ./agora-manager.sh logs <nombre>    — Logs del contenedor
#
# Puertos asignados: 9200–9209 (máximo 10 usuarios por ahora)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.agora.yml"
DATA_BASE="/opt/agora"
PORT_BASE=9200
IMAGE="laia-agora:latest"

# ── helpers ──────────────────────────────────────────────────────────────────

usage() {
    echo "Uso: $0 [add|remove|list|status|logs] [nombre]"
    exit 1
}

require_name() {
    [[ -z "${NAME:-}" ]] && { echo "Error: falta el nombre de usuario."; usage; }
}

next_free_port() {
    for port in $(seq $PORT_BASE $((PORT_BASE + 9))); do
        if ! ss -tlnp | grep -q ":$port "; then
            echo "$port"
            return
        fi
    done
    echo "Error: no hay puertos libres en el rango $PORT_BASE-$((PORT_BASE+9))" >&2
    exit 1
}

# ── comandos ─────────────────────────────────────────────────────────────────

cmd_add() {
    require_name

    local data_dir="$DATA_BASE/$NAME"
    local port
    port=$(next_free_port)

    echo "→ Creando agora para '$NAME' en puerto $port"

    # Directorio de datos del usuario
    if [[ ! -d "$data_dir" ]]; then
        sudo mkdir -p "$data_dir"
        sudo chown 10001:10001 "$data_dir"
        echo "  ✓ Directorio de datos: $data_dir"
    else
        echo "  · Directorio de datos ya existe: $data_dir"
    fi

    # Arrancar contenedor con docker run (sin modificar el compose)
    docker run -d \
        --name "agora-$NAME" \
        --restart unless-stopped \
        --network bridge \
        -p "127.0.0.1:${port}:9000" \
        -v "${data_dir}:/opt/data" \
        -v "${SCRIPT_DIR}/config/agora.yaml:/opt/hermes/cli-config.yaml.example:ro" \
        -e "AGORA_USER=$NAME" \
        -e "HERMES_TOOLSET=agora" \
        -e "HERMES_USER_MODE=restricted" \
        -e "HERMES_UID=10001" \
        -e "HERMES_GID=10001" \
        --security-opt no-new-privileges:true \
        --cap-drop ALL \
        --cap-add CHOWN \
        --cap-add SETUID \
        --cap-add SETGID \
        --memory 2g \
        --cpus 1.5 \
        "$IMAGE" gateway run

    echo "  ✓ Contenedor agora-$NAME arrancado en 127.0.0.1:$port"
    echo ""
    echo "  Añade a nginx:"
    echo "    location /agora/$NAME/ {"
    echo "        proxy_pass http://127.0.0.1:$port/;"
    echo "    }"
}

cmd_remove() {
    require_name

    echo "→ Eliminando agora-$NAME (datos en $DATA_BASE/$NAME conservados)"
    docker stop "agora-$NAME" 2>/dev/null || true
    docker rm   "agora-$NAME" 2>/dev/null || true
    echo "  ✓ Contenedor eliminado"
}

cmd_list() {
    echo "LAIA-AGORA — Contenedores activos:"
    echo ""
    docker ps -a \
        --filter "name=agora-" \
        --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" \
        | column -t
}

cmd_status() {
    docker stats $(docker ps --filter "name=agora-" --format "{{.Names}}" | tr '\n' ' ') \
        --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
}

cmd_logs() {
    require_name
    docker logs -f --tail 50 "agora-$NAME"
}

# ── main ─────────────────────────────────────────────────────────────────────

CMD="${1:-}"
NAME="${2:-}"

case "$CMD" in
    add)    cmd_add    ;;
    remove) cmd_remove ;;
    list)   cmd_list   ;;
    status) cmd_status ;;
    logs)   cmd_logs   ;;
    *)      usage      ;;
esac
