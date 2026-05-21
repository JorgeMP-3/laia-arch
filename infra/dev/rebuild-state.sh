#!/usr/bin/env bash
# rebuild-state.sh — regenerate persistent AGORA rebuild state from live LXD + DB.

set -uo pipefail

SLUG_FILTER=""
INCLUDE_STOPPED=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --slug) SLUG_FILTER="$2"; shift 2;;
    --include-stopped) INCLUDE_STOPPED=1; shift;;
    -h|--help)
      sed -n '1,32p' "$0"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

ORIG_USER="${SUDO_USER:-${USER:-laia-hermes}}"
ORIG_HOME="${HOME:-$(getent passwd "$ORIG_USER" 2>/dev/null | cut -d: -f6)}"
[[ -z "$ORIG_HOME" ]] && ORIG_HOME="/home/$ORIG_USER"
REPO="${LAIA_ROOT:-$ORIG_HOME/LAIA}"
STATE_DIR="${LAIA_STATE_DIR:-$ORIG_HOME/.laia/state}"
DEFAULT_PASSWORD="${LAIA_DEFAULT_USER_PASSWORD:-chattest}"

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; BLD='\033[1m'; RST='\033[0m'
else GRN=''; YEL=''; RED=''; CYN=''; BLD=''; RST=''; fi

log() { printf "${CYN}▸${RST} %s\n" "$*"; }
ok() { printf "  ${GRN}✓${RST} %s\n" "$*"; }
warn() { printf "  ${YEL}⚠${RST} %s\n" "$*"; }
die() { printf "  ${RED}✗${RST} %s\n" "$*" >&2; exit 1; }
section() { printf "\n${BLD}== %s ==${RST}\n" "$*"; }

command -v lxc >/dev/null 2>&1 || die "lxc no encontrado"
command -v jq >/dev/null 2>&1 || die "jq no encontrado"

mkdir -p "$STATE_DIR" || die "no pude crear $STATE_DIR"
chmod 700 "$STATE_DIR" 2>/dev/null || true

container_state() {
  lxc list "$1" -c s --format csv 2>/dev/null | head -1
}

container_ip() {
  lxc list "$1" --format json 2>/dev/null \
    | jq -r '.[0].state.network.eth0.addresses[]? | select(.family=="inet") | .address' \
    | head -1
}

config_value() {
  local container="$1" device="$2" key="$3"
  lxc config show "$container" --expanded 2>/dev/null \
    | awk -v d="$device" -v k="$key" '
      $0 ~ "^  " d ":" { in_dev=1; next }
      in_dev && $0 ~ /^  [^ ]/ { in_dev=0 }
      in_dev && $1 == k ":" { sub(/^[^:]+:[[:space:]]*/, ""); print; exit }
    '
}

json_write() {
  local file="$1"
  shift
  jq -n "$@" > "$file" || die "no pude escribir JSON $file"
  chmod 0644 "$file" 2>/dev/null || true
  if command -v chown >/dev/null 2>&1; then
    chown "$ORIG_USER:$(id -gn "$ORIG_USER" 2>/dev/null || echo "$ORIG_USER")" "$file" 2>/dev/null || true
  fi
}

section "State de laia-agora"
if lxc info laia-agora >/dev/null 2>&1; then
  AGORA_IP="$(container_ip laia-agora)"
  [[ -n "$AGORA_IP" ]] || warn "laia-agora sin IPv4; state tendrá container_ip vacío"
  listen="$(config_value laia-agora agora-api listen)"
  connect="$(config_value laia-agora agora-api connect)"
  host_port="${listen##*:}"
  container_port="${connect##*:}"
  [[ "$host_port" =~ ^[0-9]+$ ]] || host_port=8088
  [[ "$container_port" =~ ^[0-9]+$ ]] || container_port=8000
  data_dir="$(config_value laia-agora agora-data source)"
  auth_json="$(config_value laia-agora agora-auth source)"
  [[ -n "$data_dir" ]] || data_dir="/srv/laia/agora"
  [[ -n "$auth_json" ]] || auth_json="$ORIG_HOME/.laia/auth.json"
  json_write "$STATE_DIR/laia-agora-state.json" \
    --arg c "laia-agora" \
    --arg ip "$AGORA_IP" \
    --arg data "$data_dir" \
    --arg auth "$auth_json" \
    --arg root "$REPO" \
    --arg api "http://${AGORA_IP}:${container_port}" \
    --argjson hp "$host_port" \
    --argjson cp "$container_port" \
    '{container:$c,container_ip:$ip,host_port:$hp,container_port:$cp,data_dir:$data,auth_json_host:$auth,laia_root:$root,api_url:$api}'
  ok "state guardado en $STATE_DIR/laia-agora-state.json"
else
  warn "laia-agora no existe; no genero state de agora"
fi

section "States de usuarios"
QUERY="select u.username,u.id,a.id,a.container_name,a.container_ip,a.api_token from users u join agents a on a.user_id=u.id where u.active=1 order by u.username;"
ROWS="$(lxc exec laia-agora -- sqlite3 -separator $'\t' /opt/agora/data/agora.db "$QUERY" 2>/dev/null || true)"
if [[ -z "$ROWS" ]]; then
  warn "no pude leer users/agents desde agora.db"
else
  while IFS=$'\t' read -r slug user_id agent_id container db_ip api_token; do
    [[ -n "$slug" ]] || continue
    [[ -n "$SLUG_FILTER" && "$slug" != "$SLUG_FILTER" ]] && continue
    [[ "$container" == "laia-jorge" && "$INCLUDE_STOPPED" -eq 0 ]] && { warn "skip laia-jorge (container sprint2 intocable)"; continue; }
    state="$(container_state "$container")"
    if [[ "$INCLUDE_STOPPED" -eq 0 && "$state" != "RUNNING" ]]; then
      warn "skip $container (state=$state; usa --include-stopped si lo necesitas)"
      continue
    fi
    live_ip="$(container_ip "$container")"
    exec_ip="${live_ip:-$db_ip}"
    api_port="$(lxc exec "$container" -- sh -c "jq -r '.api_port // 9091' /etc/laia/agent.json 2>/dev/null" 2>/dev/null || true)"
    [[ "$api_port" =~ ^[0-9]+$ ]] || api_port=9091
    [[ -n "$api_token" ]] || api_token="$(lxc exec "$container" -- sh -c 'cat /etc/laia/executor-token 2>/dev/null' 2>/dev/null || true)"
    old_state="$STATE_DIR/laia-state-${slug}.json"
    [[ -f "$old_state" ]] || old_state="/tmp/laia-state-${slug}.json"
    password="$(jq -r '.password // empty' "$old_state" 2>/dev/null || true)"
    if [[ -z "$password" ]]; then
      password="$DEFAULT_PASSWORD"
      warn "password de $slug no recuperable; uso LAIA_DEFAULT_USER_PASSWORD/chattest"
    fi
    agora_api="$(jq -r '.api_url // empty' "$STATE_DIR/laia-agora-state.json" 2>/dev/null || true)"
    [[ -n "$agora_api" ]] || agora_api="http://127.0.0.1:8088"
    json_write "$STATE_DIR/laia-state-${slug}.json" \
      --arg slug "$slug" \
      --arg uid "$user_id" \
      --arg aid "$agent_id" \
      --arg pw "$password" \
      --arg container "$container" \
      --arg ip "$exec_ip" \
      --arg token "$api_token" \
      --arg agora "$agora_api" \
      --arg root "$REPO" \
      --argjson port "$api_port" \
      '{slug:$slug,username:$slug,user_id:$uid,agent_id:$aid,password:$pw,container:$container,container_ip:$ip,api_token:$token,api_port:$port,agora_api_url:$agora,laia_root:$root}'
    ok "state guardado en $STATE_DIR/laia-state-${slug}.json"
  done <<< "$ROWS"
fi

printf "\n${GRN}✓ rebuild-state completado.${RST}\n"
