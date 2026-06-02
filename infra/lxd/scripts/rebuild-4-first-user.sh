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
KEEP_LEGACY="${KEEP_LEGACY:-0}"
INSTALL_BASE_SKILLS="${INSTALL_BASE_SKILLS:-1}"
EXISTING_USER_ONLY="${EXISTING_USER_ONLY:-0}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --slug) SLUG="$2"; shift 2;;
    --display) DISPLAY_NAME="$2"; shift 2;;
    --password) PASSWORD="$2"; shift 2;;
    --keep-legacy) KEEP_LEGACY=1; shift;;
    --no-base-skills) INSTALL_BASE_SKILLS=0; shift;;
    --existing-user-only) EXISTING_USER_ONLY=1; shift;;
    -h|--help) sed -n '1,16p' "$0"; exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done
[[ -z "$SLUG" ]] && { echo "Uso: $0 --slug <name>" >&2; exit 2; }
[[ -z "$DISPLAY_NAME" ]] && DISPLAY_NAME="$SLUG"

if [[ $EUID -ne 0 ]]; then
  echo "Necesito sudo (lxc launch + chown /srv/laia/users)." >&2
  args=(--slug "$SLUG" --display "$DISPLAY_NAME" --password "$PASSWORD")
  [[ "$KEEP_LEGACY" == "1" ]] && args+=(--keep-legacy)
  [[ "$INSTALL_BASE_SKILLS" == "0" ]] && args+=(--no-base-skills)
  [[ "$EXISTING_USER_ONLY" == "1" ]] && args+=(--existing-user-only)
  exec sudo -E bash "$0" "${args[@]}"
fi

ORIG_USER="${SUDO_USER:-${LAIA_ADMIN_USER:-}}"
if [[ -z "$ORIG_USER" || "$ORIG_USER" == "root" ]]; then
  ORIG_USER=$(getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 {print $1; exit}')
fi
[[ -n "$ORIG_USER" ]] || { echo "Cannot determine ORIG_USER (set SUDO_USER or LAIA_ADMIN_USER)" >&2; exit 1; }
ORIG_HOME=$(getent passwd "$ORIG_USER" | cut -d: -f6)
[[ -n "$ORIG_HOME" ]] || { echo "Cannot resolve home for user '$ORIG_USER'" >&2; exit 1; }
REPO="${LAIA_ROOT:-$ORIG_HOME/LAIA}"
SCRIPTS_DIR="$REPO/infra/lxd/scripts"
PREFLIGHT="$REPO/infra/dev/preflight.sh"
STATE_DIR="${LAIA_STATE_DIR:-$ORIG_HOME/.laia/state}"
AGORA_STATE="$STATE_DIR/laia-agora-state.json"
LEGACY_AGORA_STATE="/tmp/laia-agora-state.json"
RUN_SMOKE="${RUN_SMOKE:-1}"

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; BLD='\033[1m'; RST='\033[0m'
else GRN=''; YEL=''; RED=''; CYN=''; BLD=''; RST=''; fi
log()  { printf "${CYN}▸${RST} %s\n" "$*"; }
ok()   { printf "  ${GRN}✓${RST} %s\n" "$*"; }
warn() { printf "  ${YEL}⚠${RST} %s\n" "$*"; }
die()  { printf "  ${RED}✗${RST} %s\n" "$*" >&2; exit 1; }
section() { printf "\n${BLD}== %s ==${RST}\n" "$*"; }

command -v jq >/dev/null || die "jq no encontrado"
if [[ -x "$PREFLIGHT" ]]; then
  section "0/4 Preflight operativo"
  bash "$PREFLIGHT"
  rc=$?
  [[ "$rc" -eq 2 ]] && die "preflight encontró blockers; corrige antes de provisionar user"
else
  warn "preflight no encontrado en $PREFLIGHT"
fi

mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR" 2>/dev/null || true
if [[ -f "$LEGACY_AGORA_STATE" && ! -f "$AGORA_STATE" ]]; then
  mv "$LEGACY_AGORA_STATE" "$AGORA_STATE" 2>/dev/null && \
    warn "migrado state legacy $LEGACY_AGORA_STATE → $AGORA_STATE"
fi
[[ -f "$AGORA_STATE" ]] || die "$AGORA_STATE no existe — corre rebuild-3-provision-agora.sh primero"

API_URL=$(jq -r .api_url "$AGORA_STATE")

# Validación del slug (regex permitido por POST /api/users tras C4):
#   ^[a-z0-9_][a-z0-9_-]*[a-z0-9_]$|^[a-z0-9_]$
if [[ ! "$SLUG" =~ ^[a-z0-9_]([a-z0-9_-]*[a-z0-9_])?$ ]]; then
  die "slug '$SLUG' inválido — solo a-z, 0-9, _ y - (sin empezar/terminar en -)"
fi
CONTAINER="agent-${SLUG}"
LEGACY_CONTAINER="laia-${SLUG}"

# ────────────────────────────────────────────────────────────────────────────
section "1/4 Provisionar container ${CONTAINER}"
# ────────────────────────────────────────────────────────────────────────────
if lxc info "$CONTAINER" >/dev/null 2>&1; then
  warn "container $CONTAINER ya existe — borrándolo para recrear limpio"
  lxc delete --force "$CONTAINER"
fi
# Limpieza del legacy ``laia-<slug>`` si quedó vivo de instalaciones anteriores
# y NO es uno de los containers protegidos (laia-jorge sprint-2 snapshot,
# laia-agora cerebro). Sin esto, agent-<slug> y laia-<slug> coexisten tras
# rebuild-4, lo que confunde al smoke y al forwarder. Si quieres preservarlo,
# pasa ``--keep-legacy``.
if [[ "$KEEP_LEGACY" != "1" ]] && lxc info "$LEGACY_CONTAINER" >/dev/null 2>&1; then
  case "$LEGACY_CONTAINER" in
    laia-agora|laia-jorge)
      warn "$LEGACY_CONTAINER es protegido — no lo toco"
      ;;
    *)
      warn "container legacy $LEGACY_CONTAINER detectado — borrándolo (usa --keep-legacy para preservarlo)"
      lxc delete --force "$LEGACY_CONTAINER" || warn "fallo al borrar $LEGACY_CONTAINER, sigo"
      ;;
  esac
fi
mkdir -p "/srv/laia/users/${SLUG}/home" "/srv/laia/users/${SLUG}/workspace" "/srv/laia/users/${SLUG}/plugins"
chown -R 1000000:1000000 "/srv/laia/users/${SLUG}" 2>/dev/null || true

log "create-agent.sh ${SLUG}"
PROVISION_JSON=$(bash "$SCRIPTS_DIR/create-agent.sh" "$SLUG" laia-agent 2>&1 | tail -1)
echo "$PROVISION_JSON" | jq . >/dev/null || die "create-agent.sh no devolvió JSON: $PROVISION_JSON"

EXEC_IP=$(echo "$PROVISION_JSON" | jq -r .ipv4)
API_TOKEN=$(echo "$PROVISION_JSON" | jq -r .api_token)
API_PORT=$(echo "$PROVISION_JSON" | jq -r .api_port)
CONTAINER=$(echo "$PROVISION_JSON" | jq -r '.container // empty')
[[ -n "$CONTAINER" && "$CONTAINER" != "null" ]] || CONTAINER="agent-${SLUG}"
ok "container ${CONTAINER} provisionado (ip=$EXEC_IP, port=$API_PORT)"

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
ADMIN_USERNAME="${AGORA_ADMIN_USERNAME:-jorge}"
ADMIN_PASSWORD="${AGORA_ADMIN_PASSWORD:-dev-admin}"
log "login admin ($ADMIN_USERNAME) contra $API_URL"
ADMIN_TOKEN=$(curl -fsS -X POST "$API_URL/api/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$ADMIN_USERNAME\",\"password\":\"$ADMIN_PASSWORD\"}" | jq -r .access_token 2>/dev/null || true)
if [[ -z "$ADMIN_TOKEN" || "$ADMIN_TOKEN" == "null" ]]; then
  ADMIN_TOKEN="${AGORA_TOKEN:-}"
fi
[[ -n "$ADMIN_TOKEN" && "$ADMIN_TOKEN" != "null" ]] || die "admin login falló"
ok "admin token obtenido"

if [[ "$EXISTING_USER_ONLY" == "1" ]]; then
  log "--existing-user-only: saltando POST /api/users"
  USER_ID=$(curl -fsS "$API_URL/api/users" -H "Authorization: Bearer $ADMIN_TOKEN" \
    | jq -r ".users[] | select(.username==\"$SLUG\") | .id" 2>/dev/null || true)
  if [[ -z "$USER_ID" || "$USER_ID" == "null" ]]; then
    DB_PATH="${AGORA_DB_PATH:-/srv/laia/agora/agora.db}"
    if command -v sqlite3 >/dev/null 2>&1 && [[ -f "$DB_PATH" ]]; then
      USER_ID=$(sqlite3 "$DB_PATH" "select id from users where username='$SLUG' limit 1;" 2>/dev/null || true)
    fi
  fi
  [[ -n "$USER_ID" && "$USER_ID" != "null" ]] || die "user '$SLUG' no existe en agora.db importada"
  ok "user existente encontrado (id=$USER_ID)"
else
  log "POST /api/users con username=$SLUG"
  CREATE_RESP=$(curl -sS -X POST "$API_URL/api/users" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"$SLUG\",\"display_name\":\"$DISPLAY_NAME\",\"role\":\"employee\",\"password\":\"$PASSWORD\"}")
  USER_ID=$(echo "$CREATE_RESP" | jq -r .user.id 2>/dev/null)
  if [[ -z "$USER_ID" || "$USER_ID" == "null" ]]; then
    CREATE_DETAIL=$(echo "$CREATE_RESP" | jq -r .detail 2>/dev/null)
    if [[ "$CREATE_DETAIL" == "username already exists" ]]; then
      warn "user '$SLUG' ya existe — recuperándolo y reactivándolo"
      USER_ID=$(curl -fsS "$API_URL/api/users" -H "Authorization: Bearer $ADMIN_TOKEN" \
        | jq -r ".users[] | select(.username==\"$SLUG\") | .id")
      [[ -n "$USER_ID" && "$USER_ID" != "null" ]] \
        || { echo "$CREATE_RESP"; die "no encuentro user '$SLUG' tras conflict"; }
      curl -fsS -X PATCH "$API_URL/api/users/$USER_ID" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -H 'Content-Type: application/json' \
        -d "{\"display_name\":\"$DISPLAY_NAME\"}" >/dev/null \
        || warn "PATCH user falló (no crítico, sigo)"
      curl -fsS -X POST "$API_URL/api/users/$USER_ID/reset-password" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -H 'Content-Type: application/json' \
        -d "{\"new_password\":\"$PASSWORD\"}" >/dev/null \
        || warn "reset-password falló (no crítico, sigo)"
      ok "user reactivado (id=$USER_ID)"
    else
      echo "$CREATE_RESP" | jq . 2>/dev/null || echo "$CREATE_RESP"
      die "no se pudo crear user '$SLUG'"
    fi
  else
    ok "user creado (id=$USER_ID, defaults openai-codex / gpt-5.5)"
  fi
fi

# ────────────────────────────────────────────────────────────────────────────
section "3/4 Registrar agente en AGORA → ${CONTAINER}"
# ────────────────────────────────────────────────────────────────────────────
register_agent() {
  curl -sS -X POST "$API_URL/api/agents/register" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H 'Content-Type: application/json' \
    -d "{\"slug\":\"$SLUG\",\"user_id\":\"$USER_ID\",\"container_ip\":\"$EXEC_IP\",\"api_token\":\"$API_TOKEN\"}"
}

REG=$(register_agent)
AGENT_ID=$(echo "$REG" | jq -r '.agent.id // .id // empty')
if [[ -z "$AGENT_ID" ]] && echo "$REG" | grep -q "already has agent"; then
  echo "$REG" | jq . 2>/dev/null || echo "$REG"
  die "backend no incluye registro idempotente; corre rebuild-2 + rebuild-3 antes de repetir rebuild-4"
fi
if [[ -z "$AGENT_ID" ]]; then
  echo "$REG" | jq . 2>/dev/null || echo "$REG"
  die "registro de agente falló"
fi
ok "agente registrado (id=$AGENT_ID)"

# ────────────────────────────────────────────────────────────────────────────
section "4/4 Guardar state file"
# ────────────────────────────────────────────────────────────────────────────
USER_STATE="$STATE_DIR/laia-state-${SLUG}.json"
LEGACY_USER_STATE="/tmp/laia-state-${SLUG}.json"
if [[ -f "$LEGACY_USER_STATE" && ! -f "$USER_STATE" ]]; then
  mv "$LEGACY_USER_STATE" "$USER_STATE" 2>/dev/null && \
    warn "migrado state legacy $LEGACY_USER_STATE → $USER_STATE"
fi
cat > "$USER_STATE" <<EOF
{
  "slug": "$SLUG",
  "username": "$SLUG",
  "user_id": "$USER_ID",
  "agent_id": "$AGENT_ID",
  "password": "$PASSWORD",
  "container": "$CONTAINER",
  "container_ip": "$EXEC_IP",
  "api_token": "$API_TOKEN",
  "api_port": $API_PORT,
  "agora_api_url": "$API_URL",
  "laia_root": "$REPO"
}
EOF
# 0600: el state lleva password y api_token del usuario.
chmod 0600 "$USER_STATE"
chown "$ORIG_USER:$(id -gn "$ORIG_USER")" "$USER_STATE" 2>/dev/null || true
ok "state guardado en $USER_STATE"

# ────────────────────────────────────────────────────────────────────────────
# 4.5/4 Auto-install base skills (curated catalog).
# ────────────────────────────────────────────────────────────────────────────
if [[ "$INSTALL_BASE_SKILLS" == "1" ]]; then
  section "4.5/4 Auto-install base skills"
  USER_TOKEN=$(curl -fsS -X POST "$API_URL/api/login" \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"$SLUG\",\"password\":\"$PASSWORD\"}" \
    | jq -r .access_token 2>/dev/null || true)
  if [[ -z "$USER_TOKEN" || "$USER_TOKEN" == "null" ]]; then
    warn "user login para auto-install falló — saltando base skills"
  else
    BASE_SKILLS=(google-workspace notion linear airtable nano-pdf
                  ocr-and-documents arxiv github-issues workspace-read maps
                  agent-self-edit agent-learning agent-scheduler
                  agent-delegation doyouwin-reference)
    installed=0
    skipped=0
    for slug in "${BASE_SKILLS[@]}"; do
      resp=$(curl -sS -X POST "$API_URL/api/me/skills/install" \
        -H "Authorization: Bearer $USER_TOKEN" \
        -H 'Content-Type: application/json' \
        -d "{\"slug\":\"$slug\"}" 2>&1)
      if echo "$resp" | jq -e .ok >/dev/null 2>&1; then
        installed=$((installed+1))
      else
        # Probable: the catalog doesn't have this slug yet — run
        # ``infra/dev/seed-base-skills.sh`` to populate it. We don't abort
        # because the agent is otherwise functional without skills.
        skipped=$((skipped+1))
      fi
    done
    ok "auto-install: $installed instaladas, $skipped saltadas (corre seed-base-skills.sh si faltan en el catálogo)"
  fi
fi

# ────────────────────────────────────────────────────────────────────────────
printf "\n${BLD}=== Primer usuario listo ===${RST}\n"
echo "Slug:         $SLUG"
echo "Container:    $CONTAINER ($EXEC_IP:$API_PORT)"
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

if [[ "$RUN_SMOKE" == "1" && -x "$REPO/infra/dev/smoke-test.sh" ]]; then
  echo ""
  log "ejecutando smoke test end-to-end"
  sudo -u "$ORIG_USER" LAIA_STATE_DIR="$STATE_DIR" bash "$REPO/infra/dev/smoke-test.sh" --slug "$SLUG" \
    || die "smoke test falló"
fi
