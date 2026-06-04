#!/usr/bin/env bash
# add-test-user.sh — registrar un nuevo usuario AGORA con SU PROPIO container LXD.
#
# Por defecto (arquitectura producción):
#   1. Provisiona laia-<slug> via deploy-redesign.sh (container propio,
#      bind mounts a /srv/laia/users/<slug>/)
#   2. Crea el usuario en AGORA (POST /api/users) — hereda los defaults
#      OAuth (openai-codex / gpt-5.5)
#   3. Registra el agente en AGORA apuntando a SU container
#   4. Guarda el state en /tmp/laia-state-<slug>.json para chats futuros
#   5. Abre el REPL (o ejecuta un mensaje single-shot)
#
# Modo --shared (solo para iterar rápido en la lógica del cerebro):
#   No provisiona container — reusa el del último deploy-redesign.sh
#   (state en /tmp/laia-redesign-state.json). Útil cuando solo te
#   importa probar multi-tenancy en AGORA y no te importa el aislamiento
#   filesystem entre users.
#
# Uso:
#   bash infra/dev/add-test-user.sh maria                    # container propio (recomendado)
#   bash infra/dev/add-test-user.sh maria "hola"             # single-shot
#   bash infra/dev/add-test-user.sh maria --shared           # reusa container existente
#   AGORA_PORT=18860 bash infra/dev/add-test-user.sh carlos  # port custom
#
# Tras provisionar, para volver a chatear como ese user sin reprovisionar:
#   STATE_FILE=/tmp/laia-state-maria.json bash infra/dev/chat-with-agent.sh

set -uo pipefail

USERNAME=""
SHOT_MESSAGE=""
SHARED_MODE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --shared) SHARED_MODE=1; shift;;
    -h|--help) sed -n '1,29p' "$0"; exit 0;;
    -*) echo "Unknown flag: $1" >&2; exit 2;;
    *)
      if [[ -z "$USERNAME" ]]; then USERNAME="$1"
      elif [[ -z "$SHOT_MESSAGE" ]]; then SHOT_MESSAGE="$1"
      else echo "Demasiados argumentos: $1" >&2; exit 2
      fi
      shift;;
  esac
done
[[ -z "$USERNAME" ]] && { echo "Uso: $0 <username> [single_shot_message] [--shared]" >&2; exit 2; }

command -v jq >/dev/null || { echo "jq no instalado (apt install jq)" >&2; exit 1; }

# Sanitiza al regex que acepta el backend (POST /api/users):
#   ^[a-z0-9_][a-z0-9_-]*[a-z0-9_]$|^[a-z0-9_]$
# Convierte espacios/símbolos a `_`, colapsa repeticiones.
_safe_username() {
  local raw="${1,,}"
  raw="$(echo "$raw" | sed -E 's/[^a-z0-9_-]+/_/g; s/[_-]+/_/g; s/^_+|_+$//g')"
  echo "$raw"
}
TEST_USER="${TEST_USER:-$(_safe_username "$USERNAME")}"
TEST_PASS="${TEST_PASS:-chattest}"
SLUG="$TEST_USER"  # 1 user = 1 slug = 1 container

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; BLD='\033[1m'; DIM='\033[2m'; RST='\033[0m'
else GRN=''; YEL=''; RED=''; CYN=''; BLD=''; DIM=''; RST=''; fi
log()  { printf "${CYN}▸${RST} %s\n" "$*"; }
ok()   { printf "  ${GRN}✓${RST} %s\n" "$*"; }
warn() { printf "  ${YEL}⚠${RST} %s\n" "$*"; }
die()  { printf "  ${RED}✗${RST} %s\n" "$*" >&2; exit 1; }
section() { printf "\n${BLD}== %s ==${RST}\n" "$*"; }

REPO="$(cd "$(dirname "$0")/../.." && pwd)"

# ────────────────────────────────────────────────────────────────────────────
# Paso 1 — provisionar container LXD propio (o reusar en --shared)
# ────────────────────────────────────────────────────────────────────────────
SHARED_STATE_FILE="${STATE_FILE:-/tmp/laia-redesign-state.json}"
PER_USER_STATE_FILE="/tmp/laia-state-${SLUG}.json"

if [[ "$SHARED_MODE" == "1" ]]; then
  section "Paso 1/4 — Modo --shared: reusando container existente"
  [[ -f "$SHARED_STATE_FILE" ]] || die "Falta $SHARED_STATE_FILE — corre primero 'sudo bash infra/lxd/scripts/deploy-redesign.sh'"
  STATE_FILE_TO_USE="$SHARED_STATE_FILE"
  warn "Atajo de testing: $TEST_USER comparte filesystem con $(jq -r .slug "$SHARED_STATE_FILE")"
  warn "Para aislamiento real, lanza sin --shared (provisiona container propio)"
else
  section "Paso 1/4 — Provisionar laia-${SLUG} (container LXD propio)"
  if lxc info "laia-${SLUG}" >/dev/null 2>&1 && lxc list "laia-${SLUG}" -c s --format csv | grep -q "RUNNING"; then
    ok "container laia-${SLUG} ya está corriendo — reusándolo"
    # Reconstruir state desde el container existente.
    ip=$(lxc list "laia-${SLUG}" --format json | jq -r '.[0].state.network.eth0.addresses[]? | select(.family=="inet") | .address' | head -1)
    token=$(lxc exec "laia-${SLUG}" -- cat /etc/laia/executor-token 2>/dev/null | tr -d '\n')
    [[ -n "$ip" && -n "$token" ]] || die "No pude recuperar ip/token de laia-${SLUG}"
    # Algunos entornos con apparmor bloquean redirecciones bash a /tmp.
    # Borramos primero y escribimos con tee para evitar el problema.
    rm -f "$PER_USER_STATE_FILE"
    cat <<EOF | tee "$PER_USER_STATE_FILE" >/dev/null
{"slug":"${SLUG}","container":"laia-${SLUG}","container_ip":"${ip}","api_token":"${token}","api_port":9091,"agora_data_dir":"/srv/laia/agora","laia_root":"${REPO}"}
EOF
  else
    log "Lanzando deploy-redesign.sh --slug ${SLUG} (requiere sudo)"
    sudo bash "$REPO/infra/lxd/scripts/deploy-redesign.sh" --slug "$SLUG" || die "deploy-redesign.sh falló"
    # deploy-redesign.sh sobreescribe /tmp/laia-redesign-state.json — lo copiamos
    # a su nombre per-user para no perderlo cuando el siguiente deploy corra.
    sudo cp /tmp/laia-redesign-state.json "$PER_USER_STATE_FILE"
    # 600: el state lleva api_token; el chown de abajo nos hace owner.
    sudo chmod 600 "$PER_USER_STATE_FILE"
    sudo chown "$(id -u):$(id -g)" "$PER_USER_STATE_FILE" 2>/dev/null || true
  fi
  STATE_FILE_TO_USE="$PER_USER_STATE_FILE"
fi

CONTAINER_IP=$(jq -r .container_ip "$STATE_FILE_TO_USE")
API_TOKEN=$(jq -r .api_token "$STATE_FILE_TO_USE")
CONTAINER_SLUG=$(jq -r .slug "$STATE_FILE_TO_USE")
ok "Container: laia-${CONTAINER_SLUG} @ ${CONTAINER_IP}:9091 (state: ${STATE_FILE_TO_USE})"

# ────────────────────────────────────────────────────────────────────────────
# Paso 2 — localizar agora-backend
# ────────────────────────────────────────────────────────────────────────────
section "Paso 2/4 — Localizar agora-backend"

_find_agora_port() {
  while read -r pid; do
    [[ -z "$pid" ]] && continue
    ss -tlnp 2>/dev/null | grep "pid=$pid" | head -1 \
      | sed -nE 's/.*:([0-9]+).*pid='"$pid"'.*/\1/p'
  done < <(pgrep -fa "uvicorn app.main:app" | awk '{print $1}') | head -1
}

AGORA_PORT="${AGORA_PORT:-$(_find_agora_port)}"
[[ -z "$AGORA_PORT" ]] && die "No encuentro un agora-backend corriendo. Lánzalo primero con: bash infra/dev/chat-with-agent.sh"
URL="http://127.0.0.1:$AGORA_PORT"
curl -fsS "$URL/api/health" >/dev/null 2>&1 || die "agora-backend en :$AGORA_PORT no responde"
ok "agora-backend en :$AGORA_PORT"

# ────────────────────────────────────────────────────────────────────────────
# Paso 3 — crear/reactivar user + registrar su agente
# ────────────────────────────────────────────────────────────────────────────
section "Paso 3/4 — Crear user '$TEST_USER' + registrar agente"

ADMIN_TOKEN=$(curl -fsS -X POST "$URL/api/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"jorge","password":"dev-admin"}' | jq -r .access_token)
[[ -n "$ADMIN_TOKEN" && "$ADMIN_TOKEN" != "null" ]] || die "login admin falló"

CREATE_RESP=$(curl -sS -X POST "$URL/api/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$TEST_USER\",\"display_name\":\"$USERNAME\",\"role\":\"employee\",\"password\":\"$TEST_PASS\"}")
TEST_USER_ID=$(echo "$CREATE_RESP" | jq -r .user.id 2>/dev/null)
if [[ -z "$TEST_USER_ID" || "$TEST_USER_ID" == "null" ]]; then
  # 409 active conflict — el user existe activo, reusarlo.
  TEST_USER_ID=$(curl -fsS "$URL/api/users" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    | jq -r ".users[]? | select(.username == \"$TEST_USER\") | .id")
  [[ -n "$TEST_USER_ID" && "$TEST_USER_ID" != "null" ]] \
    || { echo "$CREATE_RESP" | jq . 2>/dev/null || echo "$CREATE_RESP"; die "no se pudo crear ni encontrar user '$TEST_USER'"; }
  warn "user '$TEST_USER' ya existía activo — reusando id=$TEST_USER_ID"

  # Si el user existente tiene un agent_id apuntando a OTRO container, lo
  # desligamos. La nueva arquitectura es 1 user = 1 container con el mismo slug.
  EXISTING_AGENT_ID=$(curl -fsS "$URL/api/users/$TEST_USER_ID" \
    -H "Authorization: Bearer $ADMIN_TOKEN" | jq -r '.user.agent_id // empty')
  if [[ -n "$EXISTING_AGENT_ID" ]]; then
    EXISTING_CONTAINER=$(curl -fsS "$URL/api/users/$TEST_USER_ID" \
      -H "Authorization: Bearer $ADMIN_TOKEN" \
      | jq -r '.agents[]? | select(.id == "'"$EXISTING_AGENT_ID"'") | .container_name')
    if [[ -n "$EXISTING_CONTAINER" && "$EXISTING_CONTAINER" != "laia-${SLUG}" ]]; then
      warn "user tenía agent_id=$EXISTING_AGENT_ID apuntando a $EXISTING_CONTAINER (wrong) — re-bindeando"
      # Soft-delete del user + recrear lo dispara la reactivación que limpia agent_id.
      curl -fsS -X DELETE "$URL/api/users/$TEST_USER_ID" \
        -H "Authorization: Bearer $ADMIN_TOKEN" >/dev/null
      RECREATE=$(curl -sS -X POST "$URL/api/users" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -H 'Content-Type: application/json' \
        -d "{\"username\":\"$TEST_USER\",\"display_name\":\"$USERNAME\",\"role\":\"employee\",\"password\":\"$TEST_PASS\"}")
      TEST_USER_ID=$(echo "$RECREATE" | jq -r .user.id 2>/dev/null)
      ok "user reactivado limpio (id=$TEST_USER_ID)"
    fi
  fi
else
  ok "user $TEST_USER creado (id=$TEST_USER_ID)"
fi

USER_TOKEN=$(curl -fsS -X POST "$URL/api/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$TEST_USER\",\"password\":\"$TEST_PASS\"}" | jq -r .access_token)
[[ -n "$USER_TOKEN" && "$USER_TOKEN" != "null" ]] || die "login del user falló"
ok "user token obtenido"

REG=$(curl -sS -X POST "$URL/api/agents/register" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"slug\":\"$CONTAINER_SLUG\",\"user_id\":\"$TEST_USER_ID\",\"container_ip\":\"$CONTAINER_IP\",\"api_token\":\"$API_TOKEN\"}")
AGENT_ID=$(echo "$REG" | jq -r '.agent.id // .id // empty')
if [[ -z "$AGENT_ID" ]]; then
  if echo "$REG" | grep -q "already has an agent"; then
    ok "user $TEST_USER ya tenía agente vinculado (continuando)"
  else
    echo "$REG" | jq . 2>/dev/null || echo "$REG"; die "registro de agente falló"
  fi
else
  ok "agente registrado (id=$AGENT_ID → laia-$CONTAINER_SLUG)"
fi

# ────────────────────────────────────────────────────────────────────────────
# Paso 4 — REPL (o single-shot)
# ────────────────────────────────────────────────────────────────────────────
section "Paso 4/4 — Chat"

chat_turn() {
  local msg="$1"
  printf "\n${DIM}-> %s${RST}\n" "$msg"
  curl -sN -X POST "$URL/api/agents/me/chat" \
    -H "Authorization: Bearer $USER_TOKEN" \
    -H 'Content-Type: application/json' \
    -d "$(jq -nc --arg m "$msg" --arg s "chat-cli-$TEST_USER" '{message: $m, session_id: $s}')" \
    | while IFS= read -r line; do
        if [[ "$line" == data:* ]]; then
          json="${line#data: }"
          type=$(echo "$json" | jq -r .type 2>/dev/null)
          case "$type" in
            token)  printf "%s" "$(echo "$json" | jq -r .value)";;
            tool)   printf "\n${YEL}[tool %s %s]${RST}" "$(echo "$json" | jq -r .name)" "$(echo "$json" | jq -r .status)";;
            done)   printf "\n${GRN}[done]${RST} %s\n" "$(echo "$json" | jq -r '.response // ""')";;
            error)  printf "\n${RED}[error]${RST} %s\n" "$(echo "$json" | jq -r .message)";;
          esac
        fi
      done
}

if [[ -n "$SHOT_MESSAGE" ]]; then
  chat_turn "$SHOT_MESSAGE"
  exit 0
fi

printf "\n${BLD}=== Chat interactivo como user '%s' ===${RST}\n" "$TEST_USER"
echo "Container: laia-$CONTAINER_SLUG @ $CONTAINER_IP (filesystem en /srv/laia/users/$CONTAINER_SLUG/)"
echo "Session id: chat-cli-$TEST_USER"
echo "Ctrl+C para salir."
echo
echo "Para volver a chatear como $TEST_USER en otra sesión, sin reprovisionar:"
echo "  STATE_FILE=$PER_USER_STATE_FILE bash infra/dev/chat-with-agent.sh"
echo
while IFS= read -r -p "> " msg; do
  [[ -z "$msg" ]] && continue
  chat_turn "$msg"
done
