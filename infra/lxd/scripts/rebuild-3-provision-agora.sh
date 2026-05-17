#!/usr/bin/env bash
# rebuild-3-provision-agora.sh — fase 3: provisionar el container laia-agora.
#
# Lanza el container con la imagen laia-agora, monta /srv/laia/agora →
# /opt/agora/data, hace bind-mount FILE del auth.json del host al
# container para que el AIAgent del backend pueda autenticarse contra
# ChatGPT Teams sin que el operador tenga que duplicar tokens, y abre
# un proxy device host:8000 → container:8000 para que chat-with-deployed.sh
# pueda hablar contra el backend.
#
# Bind mount del auth.json: ARCH refresca tokens en el host, AGORA los
# lee (read-only). El container ve EXACTAMENTE el mismo archivo, sin
# divergencias.
#
# Permisos: ~/.laia/auth.json es 0600 por default (solo lectura para el
# dueño). El uid del host (laia-hermes) mapea a un uid alto en el
# container (LXD unprivileged), donde el `agora` user es uid bajo —
# tendrá que ver el archivo como "other". Por eso hacemos chmod 644.
#
# Si esto te incomoda, una alternativa es montar el dir entero con shift
# (raw.idmap) — más invasivo pero el file queda 0600. Lo dejo como TODO.

set -uo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Necesito sudo (lxc launch + mount + chmod)." >&2
  exec sudo -E bash "$0" "$@"
fi

ORIG_USER="${SUDO_USER:-laia-hermes}"
ORIG_HOME=$(getent passwd "$ORIG_USER" | cut -d: -f6)
REPO="${LAIA_ROOT:-$ORIG_HOME/LAIA}"

CONTAINER="${CONTAINER:-laia-agora}"
IMAGE="${IMAGE:-laia-agora}"
PROFILE="${PROFILE:-laia-agora}"
HOST_PORT="${HOST_PORT:-8088}"           # cambiado a 8088 para no chocar con FastAPI default
CONTAINER_PORT="${CONTAINER_PORT:-8000}"
HOST_DATA_DIR="${HOST_DATA_DIR:-/srv/laia/agora}"
AUTH_JSON_HOST="${AUTH_JSON_HOST:-$ORIG_HOME/.laia/auth.json}"
AUTH_JSON_CONTAINER="${AUTH_JSON_CONTAINER:-/opt/agora/data/auth.json}"

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; BLD='\033[1m'; RST='\033[0m'
else GRN=''; YEL=''; RED=''; CYN=''; BLD=''; RST=''; fi
log()  { printf "${CYN}▸${RST} %s\n" "$*"; }
ok()   { printf "  ${GRN}✓${RST} %s\n" "$*"; }
warn() { printf "  ${YEL}⚠${RST} %s\n" "$*"; }
die()  { printf "  ${RED}✗${RST} %s\n" "$*" >&2; exit 1; }
section() { printf "\n${BLD}== %s ==${RST}\n" "$*"; }

command -v lxc >/dev/null || die "lxc no encontrado"
command -v jq  >/dev/null || die "jq no encontrado"

# ────────────────────────────────────────────────────────────────────────────
section "1/7 Pre-flight"
# ────────────────────────────────────────────────────────────────────────────
lxc image info "$IMAGE" >/dev/null 2>&1 || die "imagen '$IMAGE' no existe — corre rebuild-2-images.sh primero"
lxc profile show "$PROFILE" >/dev/null 2>&1 || die "profile '$PROFILE' no existe — corre rebuild-2-images.sh"
[[ -f "$AUTH_JSON_HOST" ]] || die "no encuentro $AUTH_JSON_HOST (corre 'laia auth' como $ORIG_USER en host primero)"
ok "imagen, profile, auth.json en host: OK"

# ────────────────────────────────────────────────────────────────────────────
section "2/7 Limpiar instancia previa de laia-agora si existe"
# ────────────────────────────────────────────────────────────────────────────
if lxc info "$CONTAINER" >/dev/null 2>&1; then
  log "borrando $CONTAINER previo"
  lxc delete --force "$CONTAINER"
  ok "$CONTAINER eliminado"
else
  ok "no había instancia previa"
fi

# ────────────────────────────────────────────────────────────────────────────
section "3/7 Preparar /srv/laia/agora en host"
# ────────────────────────────────────────────────────────────────────────────
if [[ ! -d "$HOST_DATA_DIR" ]]; then
  log "mkdir $HOST_DATA_DIR"
  mkdir -p "$HOST_DATA_DIR"
fi
# Default uid mapping para LXD unprivileged: container uid 0 → host uid 1000000.
# Después chowneamos al uid del agora user dentro del container (post-mount).
chown -R 1000000:1000000 "$HOST_DATA_DIR" 2>/dev/null || true
ok "$HOST_DATA_DIR listo"

# ────────────────────────────────────────────────────────────────────────────
section "4/7 chmod 644 $AUTH_JSON_HOST (para que el container pueda leerlo)"
# ────────────────────────────────────────────────────────────────────────────
CURRENT_MODE=$(stat -c %a "$AUTH_JSON_HOST")
if [[ "$CURRENT_MODE" != "644" ]]; then
  warn "TRADE-OFF: este chmod hace el auth.json legible por TODOS los users del host."
  warn "  Si compartes el host con otros humanos, considera usar un setup con raw.idmap."
  warn "  Si tu host es single-user (laia-hermes), es aceptable."
  log "chmod 644 $AUTH_JSON_HOST (era $CURRENT_MODE)"
  chmod 644 "$AUTH_JSON_HOST"
  ok "auth.json ahora 644"
else
  ok "auth.json ya está en 644"
fi

# ────────────────────────────────────────────────────────────────────────────
section "5/7 Lanzar container laia-agora"
# ────────────────────────────────────────────────────────────────────────────
log "lxc launch $IMAGE $CONTAINER -p default -p $PROFILE"
lxc launch "$IMAGE" "$CONTAINER" -p default -p "$PROFILE" >/dev/null
sleep 3
ok "$CONTAINER lanzado"

log "bind mount: $HOST_DATA_DIR → /opt/agora/data"
lxc config device add "$CONTAINER" agora-data disk \
    source="$HOST_DATA_DIR" path=/opt/agora/data >/dev/null
ok "bind data añadido"

log "bind mount FILE: $AUTH_JSON_HOST → $AUTH_JSON_CONTAINER (read-only)"
lxc config device add "$CONTAINER" agora-auth disk \
    source="$AUTH_JSON_HOST" path="$AUTH_JSON_CONTAINER" \
    readonly=true >/dev/null
ok "bind auth.json añadido (read-only)"

log "proxy device: host :$HOST_PORT → container :$CONTAINER_PORT"
lxc config device add "$CONTAINER" agora-api proxy \
    listen="tcp:0.0.0.0:${HOST_PORT}" \
    connect="tcp:127.0.0.1:${CONTAINER_PORT}" >/dev/null
ok "proxy añadido"

# ────────────────────────────────────────────────────────────────────────────
section "6/7 Fix ownership + arrancar systemd unit"
# ────────────────────────────────────────────────────────────────────────────
log "chown agora:agora /opt/agora/data (dentro del container)"
lxc exec "$CONTAINER" -- chown -R agora:agora /opt/agora/data 2>&1 \
  || warn "chown falló (puede ser permission-denied por raw.idmap; continúo)"

log "systemctl daemon-reload + start agora-backend.service"
lxc exec "$CONTAINER" -- systemctl daemon-reload
lxc exec "$CONTAINER" -- systemctl enable --now agora-backend.service \
  || warn "enable --now falló — revisa journalctl dentro del container"

# ────────────────────────────────────────────────────────────────────────────
section "7/7 Esperar /api/health"
# ────────────────────────────────────────────────────────────────────────────
CONTAINER_IP=$(lxc list "$CONTAINER" --format json | jq -r '.[0].state.network.eth0.addresses[]? | select(.family=="inet") | .address' | head -1)
[[ -z "$CONTAINER_IP" ]] && die "no pude obtener IP del container"

# Probamos contra la IP del bridge LXD (más fiable que via proxy host:8088).
HEALTH_URL="http://${CONTAINER_IP}:${CONTAINER_PORT}/api/health"
log "esperando $HEALTH_URL ..."
SUCCESS=0
for i in {1..60}; do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    SUCCESS=1
    break
  fi
  sleep 1
done
if [[ "$SUCCESS" -ne 1 ]]; then
  echo ""
  echo "--- journalctl agora-backend (últimas 40 líneas) ---"
  lxc exec "$CONTAINER" -- journalctl -u agora-backend.service --no-pager -n 40 || true
  die "/api/health no respondió en 60s. Revisa el log."
fi
ok "/api/health responde en $HEALTH_URL"

# También probamos el proxy host:8088
if curl -fsS "http://127.0.0.1:${HOST_PORT}/api/health" >/dev/null 2>&1; then
  ok "proxy host:$HOST_PORT también responde"
else
  warn "proxy host:$HOST_PORT no responde (el container sí). Revisa lxc network."
fi

# Guarda el state para el script siguiente.
STATE_FILE="/tmp/laia-agora-state.json"
cat > "$STATE_FILE" <<EOF
{
  "container": "$CONTAINER",
  "container_ip": "$CONTAINER_IP",
  "host_port": $HOST_PORT,
  "container_port": $CONTAINER_PORT,
  "data_dir": "$HOST_DATA_DIR",
  "auth_json_host": "$AUTH_JSON_HOST",
  "laia_root": "$REPO",
  "api_url": "http://${CONTAINER_IP}:${CONTAINER_PORT}"
}
EOF
chmod 0644 "$STATE_FILE"
chown "$ORIG_USER:$(id -gn "$ORIG_USER")" "$STATE_FILE" 2>/dev/null || true

# ────────────────────────────────────────────────────────────────────────────
printf "\n${BLD}=== AGORA Arquitectura provisionada ===${RST}\n"
echo "Container:    $CONTAINER ($CONTAINER_IP)"
echo "API URL:      http://${CONTAINER_IP}:${CONTAINER_PORT}"
echo "Proxy host:   http://127.0.0.1:${HOST_PORT}"
echo "State file:   $STATE_FILE"
echo ""
echo "Verificar hardening systemd (A3):"
echo "  lxc exec $CONTAINER -- systemctl show agora-backend.service \\"
echo "      | grep -E 'User=|ProtectSystem|NoNewPrivileges|PrivateTmp|CapabilityBoundingSet'"
echo ""
echo "Siguiente paso (provisionar el primer usuario):"
echo "  sudo bash $REPO/infra/lxd/scripts/rebuild-4-first-user.sh --slug jorge_dev"
