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
# Permisos (C2 · T1): auth.json se queda 0600 (owned por el admin laia-arch).
# Para que el container unprivileged lo lea SIN chmod world-readable, mapeamos
# con raw.idmap el uid/gid del admin del host ↔ el uid/gid del user `agora` del
# container. Consecuencia: como ese mapeo carva el uid de `agora` del rango base,
# /srv/laia/agora (data) debe quedar host-owned por el MISMO uid del admin para
# que el container lo siga viendo como `agora`. Ambos mounts (data + secretos)
# los consume el mismo uid del container, así que comparten dueño host-side.

set -uo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Necesito sudo (lxc launch + mount + chmod)." >&2
  exec sudo -E bash "$0" "$@"
fi

ORIG_USER="${SUDO_USER:-${LAIA_ADMIN_USER:-}}"
if [[ -z "$ORIG_USER" || "$ORIG_USER" == "root" ]]; then
  ORIG_USER=$(getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 {print $1; exit}')
fi
[[ -n "$ORIG_USER" ]] || { echo "Cannot determine ORIG_USER (set SUDO_USER or LAIA_ADMIN_USER)" >&2; exit 1; }
ORIG_HOME=$(getent passwd "$ORIG_USER" | cut -d: -f6)
[[ -n "$ORIG_HOME" ]] || { echo "Cannot resolve home for user '$ORIG_USER'" >&2; exit 1; }
REPO="${LAIA_ROOT:-$ORIG_HOME/LAIA}"
PREFLIGHT="$REPO/infra/dev/preflight.sh"
STATE_DIR="${LAIA_STATE_DIR:-$ORIG_HOME/.laia/state}"
STATE_FILE="$STATE_DIR/laia-agora-state.json"
LEGACY_STATE_FILE="/tmp/laia-agora-state.json"

CONTAINER="${CONTAINER:-laia-agora}"
IMAGE="${IMAGE:-laia-agora}"
PROFILE="${PROFILE:-laia-agora}"
HOST_PORT="${HOST_PORT:-8088}"           # cambiado a 8088 para no chocar con FastAPI default
CONTAINER_PORT="${CONTAINER_PORT:-8000}"
HOST_DATA_DIR="${HOST_DATA_DIR:-/srv/laia/agora}"
# v2 layout (C2): los secretos viven en /srv/laia/arch/secrets (0700, files 0600),
# owned por el admin (laia-arch). En un host v1 aún sin migrar, override:
#   LAIA_ARCH_CREDS_DIR_OVERRIDE=$ORIG_HOME/.laia
SECRETS_DIR="${LAIA_ARCH_CREDS_DIR_OVERRIDE:-/srv/laia/arch/secrets}"
AUTH_JSON_HOST="${AUTH_JSON_HOST:-$SECRETS_DIR/auth.json}"
AUTH_JSON_CONTAINER="${AUTH_JSON_CONTAINER:-/opt/agora/data/auth.json}"

# raw.idmap (C2 · T1): mapeamos el uid/gid del admin del host (dueño de los
# secretos) al uid/gid del user `agora` DENTRO del container, para que el bind
# del auth.json 0600 sea legible SIN chmod world-readable. Los uids del host se
# calculan; los del container vienen de la imagen (override si cambia).
ARCH_UID="$(id -u "$ORIG_USER")"
ARCH_GID="$(id -g "$ORIG_USER")"
AGORA_UID="${AGORA_UID:-999}"     # user `agora` en la imagen orchestrator
AGORA_GID="${AGORA_GID:-988}"

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

if [[ -x "$PREFLIGHT" ]]; then
  section "0/7 Preflight operativo"
  bash "$PREFLIGHT"
  rc=$?
  [[ "$rc" -eq 2 ]] && die "preflight encontró blockers; corrige antes de provisionar"
else
  warn "preflight no encontrado en $PREFLIGHT"
fi

mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR" 2>/dev/null || true
if [[ -f "$LEGACY_STATE_FILE" && ! -f "$STATE_FILE" ]]; then
  mv "$LEGACY_STATE_FILE" "$STATE_FILE" 2>/dev/null && \
    warn "migrado state legacy $LEGACY_STATE_FILE → $STATE_FILE"
fi

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
# Con el raw.idmap de C2 (host admin ↔ container `agora`), /srv/laia/agora debe
# quedar host-owned por el admin para que el container lo siga viendo como
# `agora` (antes era 1000000 = container root vía rango base).
chown -R "$ARCH_UID:$ARCH_GID" "$HOST_DATA_DIR" 2>/dev/null || true
ok "$HOST_DATA_DIR listo (owned $ARCH_UID:$ARCH_GID para el shift de idmap)"

# ────────────────────────────────────────────────────────────────────────────
section "4/7 Endurecer secretos (0700 dir / 0600 file) — sin world-read"
# ────────────────────────────────────────────────────────────────────────────
# C2: NO chmod 644. El auth.json se queda 0600; el raw.idmap (sección 5) hace
# que el container `agora` lo lea. Aseguramos dir 0700, file 0600, dueño = admin.
install -d -m 0700 -o "$ARCH_UID" -g "$ARCH_GID" "$SECRETS_DIR"
chown "$ARCH_UID:$ARCH_GID" "$AUTH_JSON_HOST"
chmod 0600 "$AUTH_JSON_HOST"
ok "secretos: $SECRETS_DIR 0700, auth.json 0600 (owned $ORIG_USER) — sin world-read"

# ────────────────────────────────────────────────────────────────────────────
section "5/7 Crear container laia-agora con raw.idmap + montar"
# ────────────────────────────────────────────────────────────────────────────
log "lxc init $IMAGE $CONTAINER -p default -p $PROFILE"
lxc init "$IMAGE" "$CONTAINER" -p default -p "$PROFILE" >/dev/null
ok "$CONTAINER creado (stopped)"

# raw.idmap debe fijarse ANTES del primer arranque para que el shift aplique
# limpio (sin reinicio). Mapea host admin (uid/gid) ↔ container agora (uid/gid).
log "raw.idmap: host $ARCH_UID/$ARCH_GID ↔ container agora $AGORA_UID/$AGORA_GID"
lxc config set "$CONTAINER" raw.idmap "uid $ARCH_UID $AGORA_UID
gid $ARCH_GID $AGORA_GID"
ok "raw.idmap fijado"

log "bind mount: $HOST_DATA_DIR → /opt/agora/data"
lxc config device add "$CONTAINER" agora-data disk \
    source="$HOST_DATA_DIR" path=/opt/agora/data >/dev/null
ok "bind data añadido"

log "bind mount FILE: $AUTH_JSON_HOST → $AUTH_JSON_CONTAINER (read-only, 0600)"
lxc config device add "$CONTAINER" agora-auth disk \
    source="$AUTH_JSON_HOST" path="$AUTH_JSON_CONTAINER" \
    readonly=true >/dev/null
ok "bind auth.json añadido (read-only; queda 0600, legible vía idmap)"

log "proxy device: host :$HOST_PORT → container :$CONTAINER_PORT"
lxc config device add "$CONTAINER" agora-api proxy \
    listen="tcp:0.0.0.0:${HOST_PORT}" \
    connect="tcp:127.0.0.1:${CONTAINER_PORT}" >/dev/null
ok "proxy añadido"

log "lxc start $CONTAINER (idmap aplicado al arrancar)"
lxc start "$CONTAINER" >/dev/null
sleep 3
ok "$CONTAINER arrancado"

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
# Refresh agora_api_url in every existing per-user state file. rebuild-3
# almost always gives laia-agora a new container IP, which silently
# invalidates ``laia-state-<slug>.json`` files written by rebuild-4 for
# previous incarnations. Without this, ``chat-with-deployed.sh`` and
# anything else that reads those files keeps hitting a stale IP and
# fails with "container no responde".
NEW_AGORA_URL="http://${CONTAINER_IP}:${CONTAINER_PORT}"
shopt -s nullglob
USER_STATE_FILES=( "$STATE_DIR"/laia-state-*.json )
shopt -u nullglob
if (( ${#USER_STATE_FILES[@]} > 0 )); then
  log "actualizando agora_api_url en ${#USER_STATE_FILES[@]} state file(s) de usuarios"
  for f in "${USER_STATE_FILES[@]}"; do
    [[ -f "$f" ]] || continue
    tmp="$f.tmp.$$"
    if jq --arg url "$NEW_AGORA_URL" '.agora_api_url = $url' "$f" > "$tmp" 2>/dev/null; then
      mv "$tmp" "$f"
      chown "$ORIG_USER:$(id -gn "$ORIG_USER")" "$f" 2>/dev/null || true
      ok "$(basename "$f") → $NEW_AGORA_URL"
    else
      rm -f "$tmp"
      warn "$(basename "$f"): jq falló, dejando intacto"
    fi
  done
fi

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
