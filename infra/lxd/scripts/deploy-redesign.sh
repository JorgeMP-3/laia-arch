#!/usr/bin/env bash
# deploy-redesign.sh — prepara un container LXD ejecutor para probar el rediseño.
#
# Diseño:
#   - El agora-backend corre en el HOST (su venv ya tiene .laia-core instalado).
#   - Un container LXD nuevo (slug por defecto `redesign-test`) corre laia-executor.
#   - NO toca laia-jorge ni ningún container existente — solo hace snapshot
#     defensivo y crea uno nuevo.
#
# Flujo:
#   1. Snapshot defensivo de todos los containers laia-* existentes.
#   2. Aplica el profile laia-employee si falta.
#   3. Construye la imagen base con executor si no existe (puede tardar).
#   4. Lanza el container y verifica que el executor responde.
#   5. Imprime los curl listos para arrancar el backend, configurar LLM key,
#      registrar el agente y chatear.
#
# Uso:
#   sudo bash deploy-redesign.sh [--slug NOMBRE] [--rebuild-image]
#   sudo bash deploy-redesign.sh --slug demo
#
# Tras este script, el resto se hace desde tu shell (sin sudo):
#   bash infra/dev/chat-with-agent.sh    # script complementario, ver más abajo

set -euo pipefail

SLUG="redesign-test"
REBUILD_IMAGE=0
IMAGE_ALIAS="laia-agent"
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$SCRIPTS_DIR/../../.." && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --slug)         SLUG="$2"; shift 2;;
    --rebuild-image)REBUILD_IMAGE=1; shift;;
    -h|--help)
      sed -n '1,30p' "$0"; exit 0;;
    *)
      echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "Necesito sudo (LXD + bind mounts en /srv/laia)." >&2
  exec sudo -E bash "$0" --slug "$SLUG" $([[ $REBUILD_IMAGE -eq 1 ]] && echo --rebuild-image)
fi

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; BLD='\033[1m'; RST='\033[0m'
else
  GRN=''; YEL=''; RED=''; CYN=''; BLD=''; RST=''
fi
log()  { printf "${CYN}▸${RST} %s\n" "$*"; }
ok()   { printf "  ${GRN}✓${RST} %s\n" "$*"; }
warn() { printf "  ${YEL}⚠${RST} %s\n" "$*"; }
die()  { printf "  ${RED}✗${RST} %s\n" "$*" >&2; exit 1; }
section() { printf "\n${BLD}== %s ==${RST}\n" "$*"; }

command -v lxc >/dev/null  || die "lxc no encontrado en PATH"
command -v jq  >/dev/null  || die "jq no encontrado (apt install jq)"

# ────────────────────────────────────────────────────────────────────────────
section "1/5 Snapshot defensivo de containers existentes"
# ────────────────────────────────────────────────────────────────────────────
SNAP_LABEL="pre-redesign-$(date +%Y%m%d-%H%M%S)"
mapfile -t EXISTING < <(lxc list -c n --format csv | grep '^laia-' || true)
if [[ ${#EXISTING[@]} -eq 0 ]]; then
  ok "no hay containers laia-* — nada que snapshotear"
else
  for c in "${EXISTING[@]}"; do
    log "snapshot ${c} → ${SNAP_LABEL}"
    if lxc snapshot "$c" "$SNAP_LABEL" 2>/dev/null; then
      ok "snapshot creado para $c"
    else
      warn "snapshot de $c falló (posiblemente ya existe el label) — continúo"
    fi
  done
fi

# ────────────────────────────────────────────────────────────────────────────
section "2/5 Profile laia-employee"
# ────────────────────────────────────────────────────────────────────────────
if ! lxc profile show laia-employee >/dev/null 2>&1; then
  log "aplicando profile desde infra/lxd/profiles/laia-employee.yaml"
  lxc profile create laia-employee 2>/dev/null || true
  lxc profile edit laia-employee < "$REPO/infra/lxd/profiles/laia-employee.yaml"
  ok "profile laia-employee aplicado"
else
  ok "profile laia-employee ya existe"
fi

# ────────────────────────────────────────────────────────────────────────────
section "3/5 Imagen base con laia-executor"
# ────────────────────────────────────────────────────────────────────────────
if lxc image info "$IMAGE_ALIAS" >/dev/null 2>&1 && [[ $REBUILD_IMAGE -eq 0 ]]; then
  ok "imagen '$IMAGE_ALIAS' ya existe (pasa --rebuild-image para recrearla)"
else
  if [[ $REBUILD_IMAGE -eq 1 ]] && lxc image info "$IMAGE_ALIAS" >/dev/null 2>&1; then
    warn "borrando imagen previa $IMAGE_ALIAS (--rebuild-image)"
    lxc image delete "$IMAGE_ALIAS"
  fi
  log "construyendo imagen base (puede tardar 3-8 min) — log en /tmp/build-base.log"
  # Pasamos LAIA_ROOT explícito porque sudo strippea $HOME → /root, y el
  # build script lo usa como default para localizar el repo.
  if ! LAIA_ROOT="$REPO" bash "$REPO/infra/lxd/image-build/build-base-image.sh" >/tmp/build-base.log 2>&1; then
    tail -30 /tmp/build-base.log
    die "build-base-image.sh falló — ver /tmp/build-base.log"
  fi
  ok "imagen '$IMAGE_ALIAS' construida"
fi

# ────────────────────────────────────────────────────────────────────────────
section "4/5 Lanzar container agent-${SLUG}"
# ────────────────────────────────────────────────────────────────────────────
CONTAINER="agent-${SLUG}"
if lxc info "$CONTAINER" >/dev/null 2>&1; then
  warn "container $CONTAINER ya existe — borrándolo para recrear limpio"
  lxc delete --force "$CONTAINER"
fi

# /srv/laia/users/{slug}/ bind mount tree.
mkdir -p "/srv/laia/users/${SLUG}/home" "/srv/laia/users/${SLUG}/workspace" "/srv/laia/users/${SLUG}/plugins"
chown -R 1000000:1000000 "/srv/laia/users/${SLUG}" 2>/dev/null || true  # unprivileged LXD uid map

log "ejecutando create-agent.sh ${SLUG} ${IMAGE_ALIAS}"
PROVISION_JSON=$(bash "$SCRIPTS_DIR/create-agent.sh" "$SLUG" "$IMAGE_ALIAS" 2>&1 | tail -1)
echo "$PROVISION_JSON" | jq . >/dev/null || die "create-agent.sh no devolvió JSON: $PROVISION_JSON"

CONTAINER_IP=$(echo "$PROVISION_JSON" | jq -r .ipv4)
API_TOKEN=$(echo "$PROVISION_JSON" | jq -r .api_token)
API_PORT=$(echo "$PROVISION_JSON" | jq -r .api_port)
CONTAINER=$(echo "$PROVISION_JSON" | jq -r '.container // empty')
[[ -n "$CONTAINER" && "$CONTAINER" != "null" ]] || CONTAINER="agent-${SLUG}"
ok "container provisionado: ip=$CONTAINER_IP, port=$API_PORT"

# Espera al executor (hasta 30s).
log "esperando a que /health del executor responda…"
for i in {1..60}; do
  if curl -fsS "http://$CONTAINER_IP:$API_PORT/health" >/dev/null 2>&1; then
    ok "executor responde en http://$CONTAINER_IP:$API_PORT/health"
    break
  fi
  sleep 0.5
  if [[ $i -eq 60 ]]; then
    die "executor no respondió en 30s — revisa: lxc exec $CONTAINER -- journalctl -u laia-executor.service --no-pager | tail -40"
  fi
done

# ────────────────────────────────────────────────────────────────────────────
section "5/5 Persistir info para el siguiente paso (chat)"
# ────────────────────────────────────────────────────────────────────────────
STATE_FILE="/tmp/laia-redesign-state.json"
# Algunos entornos (apparmor con perfil estricto en /usr/bin/bash) bloquean
# la redirección directa de bash a /tmp aunque seas root. Borramos el archivo
# previo y escribimos vía tee (/usr/bin/tee suele tener menos restricciones),
# así el flujo es robusto en cualquier host.
rm -f "$STATE_FILE"
cat <<EOF | tee "$STATE_FILE" >/dev/null
{
  "slug": "$SLUG",
  "container": "$CONTAINER",
  "container_ip": "$CONTAINER_IP",
  "api_token": "$API_TOKEN",
  "api_port": $API_PORT,
  "snapshot_label": "$SNAP_LABEL",
  "agora_data_dir": "/srv/laia/agora",
  "laia_root": "$REPO"
}
EOF
# 0600: el state lleva api_token y está en /tmp (world-traversable).
chmod 0600 "$STATE_FILE"
# El owner del repo debe poder leer + sobreescribir desde scripts SIN sudo
# en el siguiente paso — con 0600 sigue pudiendo: es el owner del archivo.
chown "$(stat -c %U "$REPO"):$(stat -c %G "$REPO")" "$STATE_FILE" 2>/dev/null || true
ok "estado guardado en $STATE_FILE"

printf "\n${BLD}=== Deploy listo ===${RST}\n"
echo "Container: $CONTAINER ($CONTAINER_IP:$API_PORT)"
echo "Estado para el siguiente paso: $STATE_FILE"
echo
echo "Próximo paso (SIN sudo):"
echo "  bash $REPO/infra/dev/chat-with-agent.sh"
echo
echo "Para deshacer:"
echo "  sudo lxc delete --force $CONTAINER"
echo "  sudo rm -rf /srv/laia/users/${SLUG}"
echo "Tus containers existentes tienen snapshot ${SNAP_LABEL} si necesitas volver."
