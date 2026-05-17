#!/usr/bin/env bash
# rebuild-3b-fix-authjson.sh — fix posterior al provision de laia-agora.
#
# Problema: el bind mount FILE (~/.laia/auth.json → /opt/agora/data/auth.json)
# falló porque /opt/agora/data ya está bind-mounted desde /srv/laia/agora —
# anidar mounts file-on-file sobre otro bind mount no funciona fiable en
# LXD/kernel ARM.
#
# Solución: montar el DIR entero ~/.laia → /var/lib/laia-host (fuera del
# otro mount) y setear AGORA_ARCH_AUTH_JSON=/var/lib/laia-host/auth.json
# vía drop-in del systemd unit. El agent_pool ya respeta esa env var
# (la añadí en su día para este caso exacto).
#
# Es idempotente: si ya está montado lo deja como está. Si la imagen tenía
# un agora-auth roto, lo borra.

set -uo pipefail

if [[ $EUID -ne 0 ]]; then
  exec sudo -E bash "$0" "$@"
fi

ORIG_USER="${SUDO_USER:-laia-hermes}"
ORIG_HOME=$(getent passwd "$ORIG_USER" | cut -d: -f6)
CONTAINER="${CONTAINER:-laia-agora}"
HOST_LAIA_DIR="${HOST_LAIA_DIR:-$ORIG_HOME/.laia}"
CONTAINER_LAIA_PATH="${CONTAINER_LAIA_PATH:-/var/lib/laia-host}"
ENV_AUTH_PATH="${CONTAINER_LAIA_PATH}/auth.json"

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; BLD='\033[1m'; RST='\033[0m'
else GRN=''; YEL=''; RED=''; CYN=''; BLD=''; RST=''; fi
log()  { printf "${CYN}▸${RST} %s\n" "$*"; }
ok()   { printf "  ${GRN}✓${RST} %s\n" "$*"; }
warn() { printf "  ${YEL}⚠${RST} %s\n" "$*"; }
die()  { printf "  ${RED}✗${RST} %s\n" "$*" >&2; exit 1; }
section() { printf "\n${BLD}== %s ==${RST}\n" "$*"; }

lxc info "$CONTAINER" >/dev/null 2>&1 || die "container $CONTAINER no existe"
[[ -d "$HOST_LAIA_DIR" ]] || die "$HOST_LAIA_DIR no existe"
[[ -f "$HOST_LAIA_DIR/auth.json" ]] || die "$HOST_LAIA_DIR/auth.json no existe — corre 'laia auth' primero"

# ────────────────────────────────────────────────────────────────────────────
section "1/4 Limpiar device roto (agora-auth) si quedó en config"
# ────────────────────────────────────────────────────────────────────────────
if lxc config device list "$CONTAINER" 2>/dev/null | grep -q '^agora-auth$'; then
  log "borrando device agora-auth (mount file roto)"
  lxc config device remove "$CONTAINER" agora-auth >/dev/null 2>&1 || true
  ok "device agora-auth removido"
else
  ok "no había device agora-auth pendiente"
fi

# ────────────────────────────────────────────────────────────────────────────
section "2/4 Bind mount $HOST_LAIA_DIR → $CONTAINER_LAIA_PATH"
# ────────────────────────────────────────────────────────────────────────────
if lxc config device list "$CONTAINER" 2>/dev/null | grep -q '^arch-laia$'; then
  warn "device arch-laia ya existe — recreando"
  lxc config device remove "$CONTAINER" arch-laia >/dev/null
fi

# Permisos: el dir ~/.laia/ debe ser TRAVERSABLE por cualquier uid del
# container (LXD unprivileged mapea root del container a uid 100000 host,
# que no es el dueño del dir). Sin chmod 755, ls dentro del container da
# Permission denied. El auth.json individual sigue siendo 644 (legible
# pero no editable por otros); el resto de archivos mantienen sus
# permisos.
DIR_MODE=$(stat -c %a "$HOST_LAIA_DIR")
if [[ "$DIR_MODE" != "755" ]]; then
  warn "TRADE-OFF: chmod 755 $HOST_LAIA_DIR (era $DIR_MODE)"
  warn "  Cualquier user del host podrá LISTAR el contenido de ~/.laia/."
  warn "  Archivos individuales conservan sus permisos (auth.json 644, etc.)"
  warn "  Si compartes el host con otros humanos, considera raw.idmap."
  chmod 755 "$HOST_LAIA_DIR"
  ok "$HOST_LAIA_DIR ahora 755 (traversable)"
fi

if [[ "$(stat -c %a "$HOST_LAIA_DIR/auth.json")" != "644" ]]; then
  log "chmod 644 $HOST_LAIA_DIR/auth.json"
  chmod 644 "$HOST_LAIA_DIR/auth.json"
fi

log "lxc config device add $CONTAINER arch-laia disk source=$HOST_LAIA_DIR path=$CONTAINER_LAIA_PATH"
if ! lxc config device add "$CONTAINER" arch-laia disk \
       source="$HOST_LAIA_DIR" path="$CONTAINER_LAIA_PATH" \
       readonly=true >/tmp/lxc-device-add.log 2>&1; then
  cat /tmp/lxc-device-add.log
  die "lxc config device add falló — ver /tmp/lxc-device-add.log"
fi
ok "device arch-laia añadido (read-only)"

# Verificar que el mount ahora SÍ funciona.
log "verificando que el container ve $ENV_AUTH_PATH"
for i in {1..15}; do
  if lxc exec "$CONTAINER" -- test -r "$ENV_AUTH_PATH" 2>/dev/null; then
    ok "$ENV_AUTH_PATH legible dentro del container"
    break
  fi
  sleep 0.5
  [[ $i -eq 15 ]] && die "$ENV_AUTH_PATH no aparece dentro del container — abort"
done

# ────────────────────────────────────────────────────────────────────────────
section "3/4 Systemd drop-in con AGORA_ARCH_AUTH_JSON"
# ────────────────────────────────────────────────────────────────────────────
log "creando /etc/systemd/system/agora-backend.service.d/auth-bind.conf en el container"
lxc exec "$CONTAINER" -- bash -lc "
  set -euo pipefail
  mkdir -p /etc/systemd/system/agora-backend.service.d
  cat > /etc/systemd/system/agora-backend.service.d/auth-bind.conf <<'DROPIN'
[Service]
# Where to read OAuth tokens from. Bind-mounted read-only from the host's
# ~/.laia/ — ARCH is the canonical writer, AGORA only reads.
Environment=AGORA_ARCH_AUTH_JSON=$ENV_AUTH_PATH
# Allow the agora user to read $CONTAINER_LAIA_PATH (it's RO mounted so
# the read works; we just need ReadWritePaths to NOT block reads).
ReadOnlyPaths=$CONTAINER_LAIA_PATH
DROPIN
  systemctl daemon-reload
"
ok "drop-in escrito + daemon-reload"

# ────────────────────────────────────────────────────────────────────────────
section "4/4 Restart backend + verificar auth_json_ready"
# ────────────────────────────────────────────────────────────────────────────
lxc exec "$CONTAINER" -- systemctl restart agora-backend.service
log "esperando a que el backend vuelva a responder"
CONTAINER_IP=$(lxc list "$CONTAINER" --format json | jq -r '.[0].state.network.eth0.addresses[]? | select(.family=="inet") | .address' | head -1)
HEALTH_URL="http://${CONTAINER_IP}:8000/api/health"
for i in {1..40}; do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then break; fi
  sleep 0.5
done
curl -fsS "$HEALTH_URL" >/dev/null 2>&1 || die "/api/health no responde tras el restart"

HEALTH_JSON=$(curl -fsS "$HEALTH_URL")
AUTH_READY=$(echo "$HEALTH_JSON" | jq -r .auth_json_ready)
AUTH_STATUS=$(echo "$HEALTH_JSON" | jq -r .auth_json_status)
AUTH_PATH=$(echo "$HEALTH_JSON" | jq -r .auth_json_path)

echo ""
echo "/api/health says:"
echo "  auth_json_ready : $AUTH_READY"
echo "  auth_json_status: $AUTH_STATUS"
echo "  auth_json_path  : $AUTH_PATH"
echo ""

if [[ "$AUTH_READY" == "true" ]]; then
  ok "OAuth credentials reachable — provider openai-codex usable ✓"
else
  warn "auth_json_ready=false aún. Revisa journalctl:"
  warn "  lxc exec $CONTAINER -- journalctl -u agora-backend -n 30 --no-pager"
fi

printf "\n${BLD}=== Auth.json fix terminado ===${RST}\n"
echo "Siguiente paso:"
echo "  sudo bash $ORIG_HOME/LAIA/infra/lxd/scripts/rebuild-4-first-user.sh --slug jorge-dev"
echo "  (usa GUION '-' en el slug, no '_'  — restricción de create-agent.sh)"
