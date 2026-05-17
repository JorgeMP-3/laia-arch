#!/usr/bin/env bash
# chat-with-agent.sh — arranca el agora-backend en el host y abre un chat
# interactivo con el agente del container provisionado por deploy-redesign.sh.
#
# Precondición: haber corrido `sudo bash infra/lxd/scripts/deploy-redesign.sh`
# antes; ese script deja un /tmp/laia-redesign-state.json con la info
# (ip, token, slug) del container del executor.
#
# Lo que hace:
#   1. Lee el estado del deploy + tu API key LLM (env DEEPSEEK_API_KEY o flag).
#   2. Arranca el agora-backend en localhost:8088 con .laia-core en PYTHONPATH
#      y AGORA_DATA_DIR=/srv/laia/agora (mismo path que la imagen).
#   3. Logea como admin (jorge / dev-admin).
#   4. Configura LLM key del user jorge.
#   5. Registra el agente apuntando al container_ip + api_token.
#   6. Abre un REPL: cada línea que escribas se manda al chat endpoint,
#      la respuesta SSE se imprime token a token.
#
# Uso:
#   bash chat-with-agent.sh                       # interactivo
#   bash chat-with-agent.sh "¿qué hora es?"       # un único turno

set -euo pipefail

# ────────────────────────────────────────────────────────────────────────────
# Sanity check: PM2 sometimes respawns a stale agora-backend from a previous
# sprint. Symptom: this script "works" but the user sees responses from the
# old code path. We pick a random port further down so we don't conflict, but
# the shared SQLite DB at /srv/laia/agora/agora.db means a zombie backend
# can still interfere with state. If we detect a uvicorn parented to PM2,
# warn the operator before we touch anything.
# ────────────────────────────────────────────────────────────────────────────
if command -v pm2 >/dev/null 2>&1; then
  if pm2 jlist 2>/dev/null | grep -q '"name":"agora-backend"' && \
     pm2 jlist 2>/dev/null | grep -E '"status":"(online|launching)"' >/dev/null; then
    cat >&2 <<'PM2_WARN'
⚠  Detected an active PM2-managed agora-backend.
   The PM2 daemon will keep respawning the OLD code path even if this script
   starts a fresh backend on a different port. Stop the PM2 service first:

     pm2 stop agora-backend      # transient
     pm2 delete agora-backend    # permanent (then `pm2 save`)

PM2_WARN
  fi
fi


STATE_FILE="${STATE_FILE:-/tmp/laia-redesign-state.json}"
# Default: openai-codex via ChatGPT Teams OAuth — el admin ya tiene los
# tokens en ~/.laia/auth.json (compartidos con ARCH) y el backend hace
# symlink al levantar. No requiere API key del usuario. Para forzar otro
# provider, fija LLM_PROVIDER + (LLM_API_KEY o DEEPSEEK_API_KEY/etc.).
PROVIDER="${LLM_PROVIDER:-openai-codex}"
# gpt-5.5 está disponible vía OAuth de ChatGPT (Codex API-only models como
# gpt-5-codex fallan con HTTP 400 en este flujo).
MODEL="${LLM_MODEL:-gpt-5.5}"
LLM_API_KEY="${LLM_API_KEY:-${DEEPSEEK_API_KEY:-${ANTHROPIC_API_KEY:-${OPENAI_API_KEY:-}}}}"

# Providers que autentican via auth.json (no requieren key per-user). Debe
# coincidir con chat_engine.OAUTH_PROVIDERS del backend.
_is_oauth_provider() {
  case "$1" in
    openai-codex|qwen-oauth|google-gemini-cli|copilot-acp|minimax-oauth) return 0;;
    *) return 1;;
  esac
}

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; BLD='\033[1m'; DIM='\033[2m'; RST='\033[0m'
else
  GRN=''; YEL=''; RED=''; CYN=''; BLD=''; DIM=''; RST=''
fi
log()  { printf "${CYN}▸${RST} %s\n" "$*"; }
ok()   { printf "  ${GRN}✓${RST} %s\n" "$*"; }
warn() { printf "  ${YEL}⚠${RST} %s\n" "$*"; }
die()  { printf "  ${RED}✗${RST} %s\n" "$*" >&2; exit 1; }

command -v jq >/dev/null || die "jq no instalado (apt install jq)"

# Si el state.json no existe pero el container del executor SÍ está
# corriendo (típico tras un reboot que limpia /tmp), reconstruirlo desde
# `lxc info` y `lxc exec ... cat /etc/laia/executor-token`.
recover_state() {
  local container="${1:-laia-redesign-test}"
  command -v lxc >/dev/null || return 1
  local info
  info=$(lxc list "$container" --format json 2>/dev/null) || return 1
  [[ "$info" == "[]" || -z "$info" ]] && return 1
  local status ip token slug
  status=$(echo "$info" | jq -r '.[0].status // empty')
  [[ "$status" == "Running" ]] || return 1
  ip=$(echo "$info" | jq -r '.[0].state.network.eth0.addresses[]? | select(.family == "inet") | .address' | head -1)
  [[ -n "$ip" ]] || return 1
  token=$(lxc exec "$container" -- cat /etc/laia/executor-token 2>/dev/null | tr -d '\n')
  [[ -n "$token" ]] || return 1
  slug=$(echo "$container" | sed 's/^laia-//')
  cat > "$STATE_FILE" <<EOF
{
  "slug": "$slug",
  "container": "$container",
  "container_ip": "$ip",
  "api_token": "$token",
  "api_port": 9091,
  "agora_data_dir": "/srv/laia/agora",
  "laia_root": "$(cd "$(dirname "$0")/../.." && pwd)"
}
EOF
  return 0
}

if [[ ! -f "$STATE_FILE" ]]; then
  warn "$STATE_FILE no existe — intentando recuperar desde el container LXD"
  if recover_state; then
    ok "estado reconstruido en $STATE_FILE"
  else
    die "No pude recuperar el estado. Lanza primero: sudo bash infra/lxd/scripts/deploy-redesign.sh"
  fi
fi

SLUG=$(jq -r .slug "$STATE_FILE")
CONTAINER_IP=$(jq -r .container_ip "$STATE_FILE")
API_TOKEN=$(jq -r .api_token "$STATE_FILE")
API_PORT=$(jq -r .api_port "$STATE_FILE")
REPO=$(jq -r .laia_root "$STATE_FILE")

if _is_oauth_provider "$PROVIDER"; then
  AUTH_JSON="${AGORA_ARCH_AUTH_JSON:-$HOME/.laia/auth.json}"
  if [[ ! -f "$AUTH_JSON" ]]; then
    die "Provider OAuth '$PROVIDER' pero no encuentro $AUTH_JSON. Corre 'laia auth' en ARCH primero, o exporta AGORA_ARCH_AUTH_JSON."
  fi
  ok "Provider OAuth '$PROVIDER' — usaré tokens de $AUTH_JSON (no requiere API key per-user)"
  LLM_API_KEY=""  # explícitamente vacío; el AIAgent lee tokens del store
elif [[ -z "$LLM_API_KEY" ]]; then
  read -r -p "Pega tu API key de ${PROVIDER}: " LLM_API_KEY
  [[ -n "$LLM_API_KEY" ]] || die "necesito una API key real"
fi

# Puerto random para no chocar con un agora-backend viejo en :8088 que
# pueda haber quedado huérfano de una sesión anterior. Forzable con
# AGORA_PORT=N si necesitas curl externo apuntando a un puerto fijo.
AGORA_PORT="${AGORA_PORT:-$(shuf -i 18000-18999 -n 1)}"
AGORA_DATA_DIR="${AGORA_DATA_DIR:-/srv/laia/agora}"

# ────────────────────────────────────────────────────────────────────────────
log "Arrancando agora-backend en localhost:${AGORA_PORT}"
# ────────────────────────────────────────────────────────────────────────────
BACKEND_LOG=/tmp/agora-backend-chat.log
: > "$BACKEND_LOG"

BACKEND_PID=""
# Detectar backend ya escuchando este puerto (de un run interrumpido). El
# patrón coincide con --port 8088 o --port=8088 (no usa ':' antes del num,
# que era el bug anterior).
if pgrep -f "uvicorn app.main:app.*port[ =]$AGORA_PORT( |$)" >/dev/null; then
  warn "ya hay un backend en :$AGORA_PORT — reutilizando"
else
  pushd "$REPO/services/agora-backend" >/dev/null
  AGORA_DATA_DIR="$AGORA_DATA_DIR" \
  LAIA_ROOT="$REPO" \
  LAIA_HOME="$AGORA_DATA_DIR" \
  PYTHONPATH="$REPO/services/agora-backend:$REPO/.laia-core" \
  nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$AGORA_PORT" \
      >"$BACKEND_LOG" 2>&1 &
  BACKEND_PID=$!
  popd >/dev/null

  for i in {1..60}; do
    if curl -fsS "http://127.0.0.1:$AGORA_PORT/api/health" >/dev/null 2>&1; then
      ok "backend up (pid=$BACKEND_PID), log: $BACKEND_LOG"
      break
    fi
    sleep 0.5
    if [[ $i -eq 60 ]]; then
      echo "--- últimos 30 logs ---"
      tail -30 "$BACKEND_LOG"
      die "backend no arrancó en 30s"
    fi
  done
fi

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    warn "Parando backend (pid=$BACKEND_PID)"
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# ────────────────────────────────────────────────────────────────────────────
log "Login como admin (jorge / dev-admin)"
# ────────────────────────────────────────────────────────────────────────────
ADMIN_TOKEN=$(curl -fsS -X POST "http://127.0.0.1:$AGORA_PORT/api/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"jorge","password":"dev-admin"}' | jq -r .access_token)
[[ -n "$ADMIN_TOKEN" && "$ADMIN_TOKEN" != "null" ]] || die "login falló — revisa $BACKEND_LOG"
ok "admin token obtenido"

# ────────────────────────────────────────────────────────────────────────────
# Crear (o reciclar) un usuario de test propio, así no pisamos al seed
# `jorge` que ya tiene un agent_jorge bind del sprint 2.
# ────────────────────────────────────────────────────────────────────────────
# El backend valida username con regex `^[a-z0-9_]+$` — solo minúsculas,
# dígitos y guiones-bajos. Cualquier carácter fuera de ese set lo
# convertimos a `_`, y luego colapsamos múltiples `_` para que el nombre
# no quede feo.
_safe_username() {
  local raw="$1"
  raw="${raw,,}"                              # lower
  raw="$(echo "$raw" | sed -E 's/[^a-z0-9_]+/_/g; s/_+/_/g; s/^_+|_+$//g')"
  echo "$raw"
}
TEST_USER="${TEST_USER:-$(_safe_username "chat_${SLUG}")}"
log "Preparando usuario de test '$TEST_USER'"

# Si existe, lo borramos para empezar limpio (drop user + su agent_id binding).
EXISTING_USER=$(curl -fsS "http://127.0.0.1:$AGORA_PORT/api/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | jq -r ".users[]? | select(.username == \"$TEST_USER\") | .id")
if [[ -n "$EXISTING_USER" && "$EXISTING_USER" != "null" ]]; then
  curl -fsS -X DELETE "http://127.0.0.1:$AGORA_PORT/api/users/$EXISTING_USER" \
    -H "Authorization: Bearer $ADMIN_TOKEN" >/dev/null 2>&1 || true
fi

CREATE_RESP=$(curl -sS -X POST "http://127.0.0.1:$AGORA_PORT/api/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$TEST_USER\",\"display_name\":\"Chat Test\",\"role\":\"employee\",\"password\":\"chattest\"}")
TEST_USER_ID=$(echo "$CREATE_RESP" | jq -r .user.id 2>/dev/null)
if [[ -z "$TEST_USER_ID" || "$TEST_USER_ID" == "null" ]]; then
  echo "Respuesta del backend:"; echo "$CREATE_RESP" | jq . 2>/dev/null || echo "$CREATE_RESP"
  die "no se pudo crear test user '$TEST_USER'"
fi
ok "user $TEST_USER creado (id=$TEST_USER_ID)"

USER_TOKEN=$(curl -fsS -X POST "http://127.0.0.1:$AGORA_PORT/api/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$TEST_USER\",\"password\":\"chattest\"}" | jq -r .access_token)
[[ -n "$USER_TOKEN" && "$USER_TOKEN" != "null" ]] || die "login test user falló"
ok "token de test user obtenido"

# ────────────────────────────────────────────────────────────────────────────
# El backend ya defaultea cada user nuevo a (openai-codex / gpt-5-codex /
# codex_responses). Si el operador pidió OTRO provider via LLM_PROVIDER,
# sobrescribimos aquí; si pidió OAuth, no hacemos PATCH (el default basta).
# ────────────────────────────────────────────────────────────────────────────
if _is_oauth_provider "$PROVIDER" && [[ "$PROVIDER" == "openai-codex" ]]; then
  ok "Provider openai-codex es el default del backend — sin PATCH"
elif _is_oauth_provider "$PROVIDER"; then
  log "Forzando provider OAuth distinto ($PROVIDER, model=$MODEL)"
  curl -fsS -X PATCH "http://127.0.0.1:$AGORA_PORT/api/user/llm-config" \
    -H "Authorization: Bearer $USER_TOKEN" \
    -H 'Content-Type: application/json' \
    -d "{\"provider\":\"$PROVIDER\",\"model\":\"$MODEL\"}" >/dev/null
  ok "LLM provider actualizado"
else
  log "Configurando LLM key del user $TEST_USER (provider=$PROVIDER, model=$MODEL)"
  curl -fsS -X PATCH "http://127.0.0.1:$AGORA_PORT/api/user/llm-config" \
    -H "Authorization: Bearer $USER_TOKEN" \
    -H 'Content-Type: application/json' \
    -d "{\"provider\":\"$PROVIDER\",\"model\":\"$MODEL\",\"api_key\":\"$LLM_API_KEY\"}" \
    >/dev/null
  ok "LLM config aplicada"
fi

# ────────────────────────────────────────────────────────────────────────────
log "Registrando agente apuntando al container del executor"
# ────────────────────────────────────────────────────────────────────────────
REG=$(curl -fsS -X POST "http://127.0.0.1:$AGORA_PORT/api/agents/register" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"slug\":\"$SLUG\",\"user_id\":\"$TEST_USER_ID\",\"container_ip\":\"$CONTAINER_IP\",\"api_token\":\"$API_TOKEN\"}")
AGENT_ID=$(echo "$REG" | jq -r '.agent.id // .id // empty' 2>/dev/null)
[[ -n "$AGENT_ID" ]] || { echo "$REG"; die "registro falló"; }
ok "agente registrado (id=$AGENT_ID)"

# ────────────────────────────────────────────────────────────────────────────
log "Verificando conectividad al executor desde el host"
# ────────────────────────────────────────────────────────────────────────────
if curl -fsS "http://$CONTAINER_IP:$API_PORT/health" >/dev/null; then
  ok "executor accesible"
else
  warn "executor /health no responde — el chat fallará al primer tool call"
fi

# ────────────────────────────────────────────────────────────────────────────
chat_turn() {
  local msg="$1"
  printf "\n${DIM}-> %s${RST}\n" "$msg"
  curl -sN -X POST "http://127.0.0.1:$AGORA_PORT/api/agents/me/chat" \
    -H "Authorization: Bearer $USER_TOKEN" \
    -H 'Content-Type: application/json' \
    -d "$(jq -nc --arg m "$msg" '{message: $m, session_id: "chat-cli"}')" \
    | while IFS= read -r line; do
        if [[ "$line" == data:* ]]; then
          json="${line#data: }"
          type=$(echo "$json" | jq -r .type 2>/dev/null)
          case "$type" in
            token)  printf "%s" "$(echo "$json" | jq -r .value)";;
            tool)   printf "\n${YEL}[tool %s %s]${RST}" "$(echo "$json" | jq -r .name)" "$(echo "$json" | jq -r .status)";;
            done)   printf "\n${GRN}[done]${RST} %s\n" "$(echo "$json" | jq -r '.response // ""')";;
            error)  printf "\n${RED}[error]${RST} %s\n" "$(echo "$json" | jq -r .message);";;
          esac
        fi
      done
}

if [[ $# -ge 1 ]]; then
  chat_turn "$*"
  exit 0
fi

printf "\n${BLD}=== Chat interactivo con %s ===${RST}\n" "$SLUG"
echo "Escribe tu mensaje y Enter. Ctrl+C para salir."
echo
while IFS= read -r -p "> " msg; do
  [[ -z "$msg" ]] && continue
  chat_turn "$msg"
done
