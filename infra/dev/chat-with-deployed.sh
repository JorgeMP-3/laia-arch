#!/usr/bin/env bash
# chat-with-deployed.sh — chat contra la arquitectura DESPLEGADA.
#
# A diferencia de chat-with-agent.sh (que arranca un uvicorn en host),
# este script asume que el backend YA está corriendo dentro del container
# `laia-agora`. Solo se ocupa de:
#   1. Leer /tmp/laia-state-<slug>.json (creado por rebuild-4-first-user.sh)
#   2. Login como el user del state
#   3. Abrir un REPL streaming sobre /api/agents/me/chat
#
# El backend en laia-agora corre como user `agora` (no root), con
# ProtectSystem=strict, NoNewPrivileges, etc. (Bloque A3). Las tools del
# LLM se forwardean automáticamente al executor del usuario; las
# AGORA_LOCAL_DENY se bloquean en el cerebro (Bloque A2).
#
# Uso:
#   bash chat-with-deployed.sh --slug jorge_dev
#   bash chat-with-deployed.sh --slug alice "Crea /home/user/hola.txt y léelo"  # single-shot

set -uo pipefail

SLUG=""
SHOT_MESSAGE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --slug) SLUG="$2"; shift 2;;
    -h|--help) sed -n '1,15p' "$0"; exit 0;;
    *)
      if [[ -z "$SHOT_MESSAGE" ]]; then SHOT_MESSAGE="$1"
      else echo "Demasiados args: $1" >&2; exit 2
      fi
      shift;;
  esac
done
[[ -z "$SLUG" ]] && { echo "Uso: $0 --slug <name> [single_shot_msg]" >&2; exit 2; }

STATE_FILE="/tmp/laia-state-${SLUG}.json"
[[ -f "$STATE_FILE" ]] || { echo "No encuentro $STATE_FILE. Provisiona el user primero:" >&2;
                            echo "  sudo bash infra/lxd/scripts/rebuild-4-first-user.sh --slug $SLUG" >&2;
                            exit 1; }

command -v jq >/dev/null || { echo "jq no instalado (apt install jq)" >&2; exit 1; }

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; BLD='\033[1m'; DIM='\033[2m'; RST='\033[0m'
else GRN=''; YEL=''; RED=''; CYN=''; BLD=''; DIM=''; RST=''; fi
log()  { printf "${CYN}▸${RST} %s\n" "$*"; }
ok()   { printf "  ${GRN}✓${RST} %s\n" "$*"; }
warn() { printf "  ${YEL}⚠${RST} %s\n" "$*"; }
die()  { printf "  ${RED}✗${RST} %s\n" "$*" >&2; exit 1; }

USERNAME=$(jq -r .username "$STATE_FILE")
PASSWORD=$(jq -r .password "$STATE_FILE")
API_URL=$(jq -r .agora_api_url "$STATE_FILE")
EXEC_IP=$(jq -r .container_ip "$STATE_FILE")
EXEC_PORT=$(jq -r .api_port "$STATE_FILE")

log "AGORA API: $API_URL"
log "User:      $USERNAME"
log "Executor:  laia-${SLUG} @ ${EXEC_IP}:${EXEC_PORT}"

# Verificar que el backend responde.
if ! curl -fsS "$API_URL/api/health" >/dev/null 2>&1; then
  die "$API_URL/api/health no responde. ¿Está vivo el container laia-agora?
       lxc info laia-agora
       lxc exec laia-agora -- journalctl -u agora-backend --no-pager -n 20"
fi
ok "AGORA backend responde"

USER_TOKEN=$(curl -fsS -X POST "$API_URL/api/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}" | jq -r .access_token)
[[ -n "$USER_TOKEN" && "$USER_TOKEN" != "null" ]] || die "login falló"
ok "user token obtenido"

# Verificar que el executor del user responde (network reachability).
if ! curl -fsS "http://${EXEC_IP}:${EXEC_PORT}/health" >/dev/null 2>&1; then
  warn "executor en ${EXEC_IP}:${EXEC_PORT} no responde — los tool calls forwardeados fallarán"
else
  ok "executor del user accesible"
fi

# ───────────────────────────────────────────────────────────────────────────
chat_turn() {
  local msg="$1"
  printf "\n${DIM}-> %s${RST}\n" "$msg"
  curl -sN -X POST "$API_URL/api/agents/me/chat" \
    -H "Authorization: Bearer $USER_TOKEN" \
    -H 'Content-Type: application/json' \
    -d "$(jq -nc --arg m "$msg" --arg s "deployed-cli-$SLUG" '{message: $m, session_id: $s}')" \
    | while IFS= read -r line; do
        if [[ "$line" == data:* ]]; then
          json="${line#data: }"
          type=$(echo "$json" | jq -r .type 2>/dev/null)
          case "$type" in
            token)  printf "%s" "$(echo "$json" | jq -r .value)";;
            tool)   printf "\n${YEL}[tool %s %s]${RST}" \
                      "$(echo "$json" | jq -r .name)" \
                      "$(echo "$json" | jq -r .status)";;
            done)   printf "\n${GRN}[done]${RST} %s\n" \
                      "$(echo "$json" | jq -r '.response // ""')";;
            error)  printf "\n${RED}[error]${RST} %s\n" \
                      "$(echo "$json" | jq -r .message)";;
          esac
        fi
      done
}

if [[ -n "$SHOT_MESSAGE" ]]; then
  chat_turn "$SHOT_MESSAGE"
  exit 0
fi

printf "\n${BLD}=== Chat deployed (slug=%s contra laia-agora) ===${RST}\n" "$SLUG"
echo "Session id: deployed-cli-$SLUG"
echo "Ctrl+C para salir."
echo
while IFS= read -r -p "> " msg; do
  [[ -z "$msg" ]] && continue
  chat_turn "$msg"
done
