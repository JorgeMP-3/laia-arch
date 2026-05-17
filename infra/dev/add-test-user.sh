#!/usr/bin/env bash
# add-test-user.sh — crea un user adicional en AGORA y abre chat con él,
# reutilizando el container LXD del último deploy-redesign.sh.
#
# Útil para probar multi-tenancy: cada user tiene su propio session_id en
# el AgentPool, su propio AIAgent cacheado, sus propias tools forwardeadas
# (en este modo, al mismo container — los archivos se mezclan en
# /srv/laia/users/redesign-test/home/; para containers separados ver
# `deploy-redesign.sh --slug NOMBRE` + `chat-with-agent.sh`).
#
# Uso:
#   bash infra/dev/add-test-user.sh maria
#   bash infra/dev/add-test-user.sh maria "Crea /home/user/maria.txt"  # single-shot
#   AGORA_PORT=18860 bash infra/dev/add-test-user.sh maria             # puerto custom
#   TEST_USER=mi_user bash infra/dev/add-test-user.sh -                # nombre explícito

set -uo pipefail

USERNAME="${1:-}"
SHOT_MESSAGE="${2:-}"
[[ -z "$USERNAME" ]] && { echo "Uso: $0 <username> [single_shot_message]" >&2; exit 2; }

STATE_FILE="${STATE_FILE:-/tmp/laia-redesign-state.json}"
[[ -f "$STATE_FILE" ]] || { echo "Falta $STATE_FILE — corre primero deploy-redesign.sh" >&2; exit 1; }

command -v jq >/dev/null || { echo "jq no instalado (apt install jq)" >&2; exit 1; }

# Sanitiza el username al regex que el backend acepta (^[a-z0-9_]+$).
_safe_username() {
  local raw="${1,,}"
  raw="$(echo "$raw" | sed -E 's/[^a-z0-9_]+/_/g; s/_+/_/g; s/^_+|_+$//g')"
  echo "$raw"
}
TEST_USER="${TEST_USER:-$(_safe_username "$USERNAME")}"
TEST_PASS="${TEST_PASS:-chattest}"

SLUG=$(jq -r .slug "$STATE_FILE")
CONTAINER_IP=$(jq -r .container_ip "$STATE_FILE")
API_TOKEN=$(jq -r .api_token "$STATE_FILE")

# Localiza un agora-backend ya arriba — específicamente uno corriendo
# `uvicorn app.main:app` (no cualquier uvicorn). Si pasas AGORA_PORT lo
# respetamos sin auto-detectar.
_find_agora_port() {
  # Para cada PID de "uvicorn app.main:app", saca su puerto vía ss.
  while read -r pid; do
    [[ -z "$pid" ]] && continue
    ss -tlnp 2>/dev/null | grep "pid=$pid" | head -1 \
      | sed -nE 's/.*:([0-9]+).*pid='"$pid"'.*/\1/p'
  done < <(pgrep -fa "uvicorn app.main:app" | awk '{print $1}') | head -1
}

AGORA_PORT="${AGORA_PORT:-$(_find_agora_port)}"
[[ -z "$AGORA_PORT" ]] && {
  echo "No encuentro un agora-backend corriendo (busqué procesos 'uvicorn app.main:app')." >&2
  echo "Lánzalo primero con: bash infra/dev/chat-with-agent.sh" >&2
  exit 1
}
URL="http://127.0.0.1:$AGORA_PORT"

if ! curl -fsS "$URL/api/health" >/dev/null 2>&1; then
  echo "agora-backend detectado en :$AGORA_PORT pero /api/health no responde" >&2
  exit 1
fi

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; BLD='\033[1m'; DIM='\033[2m'; RST='\033[0m'
else GRN=''; YEL=''; RED=''; CYN=''; BLD=''; DIM=''; RST=''; fi
log()  { printf "${CYN}▸${RST} %s\n" "$*"; }
ok()   { printf "  ${GRN}✓${RST} %s\n" "$*"; }
warn() { printf "  ${YEL}⚠${RST} %s\n" "$*"; }
die()  { printf "  ${RED}✗${RST} %s\n" "$*" >&2; exit 1; }

log "Conectando al agora-backend en :$AGORA_PORT (container: $SLUG @ $CONTAINER_IP)"

ADMIN_TOKEN=$(curl -fsS -X POST "$URL/api/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"jorge","password":"dev-admin"}' | jq -r .access_token)
[[ -n "$ADMIN_TOKEN" && "$ADMIN_TOKEN" != "null" ]] || die "login admin falló"
ok "admin token obtenido"

# Crear o reactivar el user.
log "Creando user '$TEST_USER'"
CREATE_RESP=$(curl -sS -X POST "$URL/api/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$TEST_USER\",\"display_name\":\"$USERNAME\",\"role\":\"employee\",\"password\":\"$TEST_PASS\"}")
TEST_USER_ID=$(echo "$CREATE_RESP" | jq -r .user.id 2>/dev/null)
if [[ -z "$TEST_USER_ID" || "$TEST_USER_ID" == "null" ]]; then
  # 409 active conflict — reusar el user existente.
  TEST_USER_ID=$(curl -fsS "$URL/api/users" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    | jq -r ".users[]? | select(.username == \"$TEST_USER\") | .id")
  [[ -n "$TEST_USER_ID" && "$TEST_USER_ID" != "null" ]] \
    || { echo "$CREATE_RESP"; die "no se pudo crear ni encontrar user '$TEST_USER'"; }
  warn "user $TEST_USER ya existía — reusando id=$TEST_USER_ID"
else
  ok "user $TEST_USER creado/reactivado (id=$TEST_USER_ID)"
fi

USER_TOKEN=$(curl -fsS -X POST "$URL/api/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$TEST_USER\",\"password\":\"$TEST_PASS\"}" | jq -r .access_token)
[[ -n "$USER_TOKEN" && "$USER_TOKEN" != "null" ]] || die "login del user falló"
ok "user token obtenido"

# Bind del user al agente del container actual (si aún no lo tiene).
# Reusamos el mismo container LXD entre users.
log "Vinculando user → agente del container existente"
EXISTING_AGENT=$(curl -fsS "$URL/api/agents" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | jq -r '.agents[]? | select(.slug == "'$SLUG'") | .container' \
  | head -1)

# Más fiable: leer del store via /api/users/{id} si está expuesto, o
# directamente registrar uno (no es problema tener varios agentes apuntando
# al mismo container — solo cuentan los api_token + container_ip).
REG=$(curl -sS -X POST "$URL/api/agents/register" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"slug\":\"$SLUG-${TEST_USER}\",\"user_id\":\"$TEST_USER_ID\",\"container_ip\":\"$CONTAINER_IP\",\"api_token\":\"$API_TOKEN\"}")
AGENT_ID=$(echo "$REG" | jq -r '.agent.id // .id // empty')
if [[ -z "$AGENT_ID" ]]; then
  if echo "$REG" | grep -q "already has an agent"; then
    ok "user $TEST_USER ya tiene agente vinculado"
  else
    echo "$REG"; die "no se pudo registrar agente"
  fi
else
  ok "agente registrado (id=$AGENT_ID, mismo container que $SLUG)"
fi

# ---------------------------------------------------------------------------
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

if [[ -n "$SHOT_MESSAGE" && "$SHOT_MESSAGE" != "-" ]]; then
  chat_turn "$SHOT_MESSAGE"
  exit 0
fi

printf "\n${BLD}=== Chat interactivo como user '%s' ===${RST}\n" "$TEST_USER"
echo "Container compartido: $SLUG @ $CONTAINER_IP"
echo "Session id: chat-cli-$TEST_USER (aislada del resto de users)"
echo "Ctrl+C para salir."
echo
while IFS= read -r -p "> " msg; do
  [[ -z "$msg" ]] && continue
  chat_turn "$msg"
done
