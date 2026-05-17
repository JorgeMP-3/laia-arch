#!/usr/bin/env bash
# rebuild-4-first-user.sh — fase 4: provisionar el primer usuario completo.
#
# Hace 3 cosas:
#   1. Crea el container laia-<slug> con bind mounts (vía create-agent.sh).
#   2. Crea el user en agora.db (via API del backend que ya está en
#      laia-agora) — hereda los defaults openai-codex / gpt-5.5.
#   3. Registra el agente con su (container_ip, api_token) — vincula
#      el user en AGORA con su container LXD.
#
# Salida: imprime el comando para empezar a chatear con
# chat-with-deployed.sh.
#
# Uso:
#   sudo bash rebuild-4-first-user.sh --slug jorge_dev
#   sudo bash rebuild-4-first-user.sh --slug alice --display "Alice Tester"

set -uo pipefail

SLUG=""
DISPLAY_NAME=""
PASSWORD="${PASSWORD:-chattest}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --slug) SLUG="$2"; shift 2;;
    --display) DISPLAY_NAME="$2"; shift 2;;
    --password) PASSWORD="$2"; shift 2;;
    -h|--help) sed -n '1,15p' "$0"; exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done
[[ -z "$SLUG" ]] && { echo "Uso: $0 --slug <name>" >&2; exit 2; }
[[ -z "$DISPLAY_NAME" ]] && DISPLAY_NAME="$SLUG"

if [[ $EUID -ne 0 ]]; then
  echo "Necesito sudo (lxc launch + chown /srv/laia/users)." >&2
  exec sudo -E bash "$0" --slug "$SLUG" --display "$DISPLAY_NAME" --password "$PASSWORD"
fi

ORIG_USER="${SUDO_USER:-laia-hermes}"
ORIG_HOME=$(getent passwd "$ORIG_USER" | cut -d: -f6)
REPO="${LAIA_ROOT:-$ORIG_HOME/LAIA}"
SCRIPTS_DIR="$REPO/infra/lxd/scripts"
AGORA_STATE="/tmp/laia-agora-state.json"

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; BLD='\033[1m'; RST='\033[0m'
else GRN=''; YEL=''; RED=''; CYN=''; BLD=''; RST=''; fi
log()  { printf "${CYN}▸${RST} %s\n" "$*"; }
ok()   { printf "  ${GRN}✓${RST} %s\n" "$*"; }
warn() { printf "  ${YEL}⚠${RST} %s\n" "$*"; }
die()  { printf "  ${RED}✗${RST} %s\n" "$*" >&2; exit 1; }
section() { printf "\n${BLD}== %s ==${RST}\n" "$*"; }

command -v jq >/dev/null || die "jq no encontrado"
[[ -f "$AGORA_STATE" ]] || die "$AGORA_STATE no existe — corre rebuild-3-provision-agora.sh primero"

API_URL=$(jq -r .api_url "$AGORA_STATE")

# Validación del slug (regex permitido por POST /api/users tras C4):
#   ^[a-z0-9_][a-z0-9_-]*[a-z0-9_]$|^[a-z0-9_]$
if [[ ! "$SLUG" =~ ^[a-z0-9_]([a-z0-9_-]*[a-z0-9_])?$ ]]; then
  die "slug '$SLUG' inválido — solo a-z, 0-9, _ y - (sin empezar/terminar en -)"
fi

# ────────────────────────────────────────────────────────────────────────────
section "1/4 Provisionar container laia-${SLUG}"
# ────────────────────────────────────────────────────────────────────────────
if lxc info "laia-${SLUG}" >/dev/null 2>&1; then
  warn "container laia-${SLUG} ya existe — borrándolo para recrear limpio"
  lxc delete --force "laia-${SLUG}"
fi
mkdir -p "/srv/laia/users/${SLUG}/home" "/srv/laia/users/${SLUG}/workspace" "/srv/laia/users/${SLUG}/plugins"
chown -R 1000000:1000000 "/srv/laia/users/${SLUG}" 2>/dev/null || true

log "create-agent.sh ${SLUG}"
PROVISION_JSON=$(bash "$SCRIPTS_DIR/create-agent.sh" "$SLUG" laia-agent 2>&1 | tail -1)
echo "$PROVISION_JSON" | jq . >/dev/null || die "create-agent.sh no devolvió JSON: $PROVISION_JSON"

EXEC_IP=$(echo "$PROVISION_JSON" | jq -r .ipv4)
API_TOKEN=$(echo "$PROVISION_JSON" | jq -r .api_token)
API_PORT=$(echo "$PROVISION_JSON" | jq -r .api_port)
ok "container laia-${SLUG} provisionado (ip=$EXEC_IP, port=$API_PORT)"

# Esperar al /health del executor (hasta 30s).
log "esperando executor /health"
for i in {1..60}; do
  if curl -fsS "http://${EXEC_IP}:${API_PORT}/health" >/dev/null 2>&1; then
    ok "executor responde"
    break
  fi
  sleep 0.5
done
curl -fsS "http://${EXEC_IP}:${API_PORT}/health" >/dev/null 2>&1 \
  || die "executor no respondió en 30s"

# ────────────────────────────────────────────────────────────────────────────
section "2/4 Crear/reactivar user en agora.db"
# ────────────────────────────────────────────────────────────────────────────
log "login admin (jorge / dev-admin) contra $API_URL"
ADMIN_TOKEN=$(curl -fsS -X POST "$API_URL/api/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"jorge","password":"dev-admin"}' | jq -r .access_token)
[[ -n "$ADMIN_TOKEN" && "$ADMIN_TOKEN" != "null" ]] || die "admin login falló"
ok "admin token obtenido"

log "POST /api/users con username=$SLUG"
CREATE_RESP=$(curl -sS -X POST "$API_URL/api/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$SLUG\",\"display_name\":\"$DISPLAY_NAME\",\"role\":\"employee\",\"password\":\"$PASSWORD\"}")
USER_ID=$(echo "$CREATE_RESP" | jq -r .user.id 2>/dev/null)
if [[ -z "$USER_ID" || "$USER_ID" == "null" ]]; then
  echo "$CREATE_RESP" | jq . 2>/dev/null || echo "$CREATE_RESP"
  die "no se pudo crear user '$SLUG'"
fi
ok "user creado (id=$USER_ID, defaults openai-codex / gpt-5.5)"

# ────────────────────────────────────────────────────────────────────────────
section "3/4 Registrar agente en AGORA → laia-${SLUG}"
# ────────────────────────────────────────────────────────────────────────────
REG=$(curl -sS -X POST "$API_URL/api/agents/register" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"slug\":\"$SLUG\",\"user_id\":\"$USER_ID\",\"container_ip\":\"$EXEC_IP\",\"api_token\":\"$API_TOKEN\"}")
AGENT_ID=$(echo "$REG" | jq -r '.agent.id // .id // empty')
if [[ -z "$AGENT_ID" ]]; then
  echo "$REG" | jq . 2>/dev/null || echo "$REG"
  die "registro de agente falló"
fi
ok "agente registrado (id=$AGENT_ID)"

# ────────────────────────────────────────────────────────────────────────────
section "4/4 Guardar state file"
# ────────────────────────────────────────────────────────────────────────────
USER_STATE="/tmp/laia-state-${SLUG}.json"
cat > "$USER_STATE" <<EOF
{
  "slug": "$SLUG",
  "username": "$SLUG",
  "user_id": "$USER_ID",
  "agent_id": "$AGENT_ID",
  "password": "$PASSWORD",
  "container": "laia-${SLUG}",
  "container_ip": "$EXEC_IP",
  "api_token": "$API_TOKEN",
  "api_port": $API_PORT,
  "agora_api_url": "$API_URL",
  "laia_root": "$REPO"
}
EOF
chmod 0644 "$USER_STATE"
chown "$ORIG_USER:$(id -gn "$ORIG_USER")" "$USER_STATE" 2>/dev/null || true
ok "state guardado en $USER_STATE"

# ────────────────────────────────────────────────────────────────────────────
printf "\n${BLD}=== Primer usuario listo ===${RST}\n"
echo "Slug:         $SLUG"
echo "Container:    laia-$SLUG ($EXEC_IP:$API_PORT)"
echo "User ID:      $USER_ID"
echo "Agent ID:     $AGENT_ID"
echo "Password:     $PASSWORD"
echo "AGORA API:    $API_URL"
echo ""
echo "Próximo paso (SIN sudo):"
echo "  bash $REPO/infra/dev/chat-with-deployed.sh --slug $SLUG"
echo ""
echo "Para crear más usuarios después:"
echo "  sudo bash $REPO/infra/lxd/scripts/rebuild-4-first-user.sh --slug otro_nombre"
