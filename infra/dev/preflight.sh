#!/usr/bin/env bash
# preflight.sh — detect recurrent AGORA rebuild/ops footguns.
#
# Default mode is read-only: report warnings/blockers and exit 0 unless a
# blocker prevents the rebuild from being meaningful. Use --fix to apply the
# small safe fixes this script knows about.

set -uo pipefail

FIX=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --fix) FIX=1; shift;;
    -h|--help)
      sed -n '1,28p' "$0"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

ORIG_USER="${SUDO_USER:-${USER:-laia-hermes}}"
if [[ -n "${SUDO_USER:-}" ]]; then
  ORIG_HOME="$(getent passwd "$ORIG_USER" 2>/dev/null | cut -d: -f6)"
else
  ORIG_HOME="${HOME:-$(getent passwd "$ORIG_USER" 2>/dev/null | cut -d: -f6)}"
fi
[[ -z "$ORIG_HOME" ]] && ORIG_HOME="/home/$ORIG_USER"

REPO="${LAIA_ROOT:-$ORIG_HOME/LAIA}"
STATE_DIR="${LAIA_STATE_DIR:-$ORIG_HOME/.laia/state}"
HOST_DATA_DIR="${HOST_DATA_DIR:-/srv/laia/agora}"
AUTH_JSON_HOST="${AUTH_JSON_HOST:-$ORIG_HOME/.laia/auth.json}"
EXPECTED_OWNER="${LAIA_EXPECTED_OWNER:-laia-hermes:laia-hermes}"
IMAGE_ALIAS="${LAIA_AGORA_IMAGE_ALIAS:-laia-agora}"
DRIFT_THRESHOLD="${LAIA_IMAGE_DRIFT_THRESHOLD_SECONDS:-0}"

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; BLD='\033[1m'; RST='\033[0m'
else
  GRN=''; YEL=''; RED=''; CYN=''; BLD=''; RST=''
fi

WARNINGS=0
BLOCKERS=0

log() { printf "${CYN}▸${RST} %s\n" "$*"; }
ok() { printf "  ${GRN}✓${RST} %s\n" "$*"; }
warn() { WARNINGS=$((WARNINGS + 1)); printf "  ${YEL}⚠${RST} %s\n" "$*"; }
block() { BLOCKERS=$((BLOCKERS + 1)); printf "  ${RED}✗${RST} %s\n" "$*" >&2; }
section() { printf "\n${BLD}== %s ==${RST}\n" "$*"; }

have() { command -v "$1" >/dev/null 2>&1; }

run_as_owner() {
  if [[ "$(id -un 2>/dev/null || true)" == "$ORIG_USER" ]]; then
    "$@"
  elif have sudo; then
    sudo -u "$ORIG_USER" "$@"
  else
    "$@"
  fi
}

iso_to_epoch() {
  local raw="$1"
  raw="${raw#Created: }"
  raw="${raw#Uploaded: }"
  raw="${raw// UTC/}"
  date -u -d "$raw" +%s 2>/dev/null || return 1
}

port_line_is_lxd_proxy() {
  local line="$1"
  [[ "$line" == *"lxd"* || "$line" == *"forkproxy"* ]]
}

port_has_lxd_proxy_config() {
  local port="$1"
  have lxc || return 1
  lxc config show laia-agora --expanded 2>/dev/null \
    | grep -qE "listen: tcp:.*:${port}$"
}

section "Prerequisitos"
for cmd in lxc git jq curl; do
  if have "$cmd"; then ok "$cmd disponible"; else block "$cmd no encontrado en PATH"; fi
done

section "Procesos fantasma y puertos"
PM2_AVAILABLE=0
if have pm2 || run_as_owner bash -lc 'command -v pm2 >/dev/null 2>&1'; then
  PM2_AVAILABLE=1
fi
if [[ "$PM2_AVAILABLE" -eq 1 ]]; then
  PM2_JSON="$(run_as_owner bash -lc 'pm2 jlist' 2>/dev/null || true)"
  if [[ -n "$PM2_JSON" ]]; then
    while IFS=$'\t' read -r name status restarts; do
      [[ -n "$name" ]] || continue
      if [[ "$name" == *agora* ]]; then
        if [[ "$status" == "stopped" ]]; then
          ok "pm2 '$name' está stopped"
        elif [[ "${restarts:-0}" =~ ^[0-9]+$ && "$restarts" -gt 50 ]]; then
          warn "pm2 '$name' tiene $restarts restarts (>50); posible respawner viejo"
          if [[ "$FIX" -eq 1 ]]; then
            run_as_owner pm2 stop "$name" >/dev/null 2>&1 && ok "pm2 stop $name aplicado" || warn "pm2 stop $name falló"
          fi
        else
          warn "pm2 contiene '$name'; verifica que no sea agora-backend legado"
        fi
      fi
    done < <(python3 - <<'PY' "$PM2_JSON" 2>/dev/null || true
import json, sys
try:
    data = json.loads(sys.argv[1])
except Exception:
    data = []
for item in data:
    name = str(item.get("name", ""))
    env = item.get("pm2_env", {})
    restarts = env.get("restart_time", 0)
    status = env.get("status", "")
    print(f"{name}\t{status}\t{restarts}")
PY
)
  else
    ok "pm2 sin procesos visibles"
  fi
else
  ok "pm2 no instalado (skip)"
fi

if have systemctl; then
  SYS_STATE="$(systemctl is-active agora-backend.service 2>/dev/null || true)"
  case "$SYS_STATE" in
    active|activating|failed) warn "agora-backend.service en host está '$SYS_STATE' (esperado: inactive)";;
    inactive|unknown|"") ok "agora-backend.service host inactive/ausente";;
    *) ok "agora-backend.service host: $SYS_STATE";;
  esac
else
  ok "systemctl no disponible (skip)"
fi

mapfile -t UVICORN_PIDS < <(pgrep -f "uvicorn app.main:app" 2>/dev/null || true)
if [[ ${#UVICORN_PIDS[@]} -eq 0 ]]; then
  ok "no hay uvicorn app.main:app manual en host"
else
  for pid in "${UVICORN_PIDS[@]}"; do
    cwd="$(readlink "/proc/$pid/cwd" 2>/dev/null || true)"
    args="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    if [[ "$cwd" == "$REPO/services/agora-backend"* || "$args" == *"$REPO/services/agora-backend"* ]]; then
      warn "uvicorn manual del repo en host: pid=$pid cwd=${cwd:-?}"
    fi
  done
fi

if have ss; then
  for port in 8088 8089 9090 9091; do
    mapfile -t LISTENERS < <(ss -ltnp "sport = :$port" 2>/dev/null | tail -n +2 || true)
    if [[ ${#LISTENERS[@]} -eq 0 ]]; then
      ok "host:$port libre"
    else
      for line in "${LISTENERS[@]}"; do
        if port_line_is_lxd_proxy "$line" || port_has_lxd_proxy_config "$port"; then
          ok "host:$port ocupado por proxy LXD esperado"
        else
          warn "host:$port ocupado por proceso no-LXD: $line"
        fi
      done
    fi
  done
else
  warn "ss no disponible; no puedo inspeccionar listeners"
fi

section "Imagen vs repo"
if have lxc && have git && [[ -d "$REPO/.git" ]]; then
  IMAGE_INFO="$(lxc image info "$IMAGE_ALIAS" 2>/dev/null || true)"
  if [[ -z "$IMAGE_INFO" ]]; then
    warn "imagen '$IMAGE_ALIAS' no existe; corre rebuild-2-images.sh"
  else
    raw_uploaded="$(printf '%s\n' "$IMAGE_INFO" | awk -F': ' '/^[[:space:]]*Uploaded:/ {print $2; exit}')"
    raw_created="$(printf '%s\n' "$IMAGE_INFO" | awk -F': ' '/^[[:space:]]*Created:/ {print $2; exit}')"
    built_epoch="$(iso_to_epoch "${raw_uploaded:-$raw_created}" || true)"
    commit_epoch="$(git -C "$REPO" log -1 --format=%ct -- services/agora-backend .laia-core 2>/dev/null || true)"
    if [[ "$built_epoch" =~ ^[0-9]+$ && "$commit_epoch" =~ ^[0-9]+$ ]]; then
      drift=$((commit_epoch - built_epoch))
      if [[ "$drift" -gt "$DRIFT_THRESHOLD" ]]; then
        warn "imagen desactualizada: repo backend/.laia-core es ${drift}s más nuevo; conviene rebuild-2"
      else
        ok "imagen '$IMAGE_ALIAS' fresca respecto a backend/.laia-core"
      fi
    else
      warn "no pude calcular frescura de imagen '$IMAGE_ALIAS'"
    fi
  fi
else
  warn "sin git repo/LXD; no calculo frescura de imagen"
fi

section "Permisos"
if [[ -d "$HOST_DATA_DIR" ]]; then
  owner="$(stat -c '%U:%G' "$HOST_DATA_DIR" 2>/dev/null || echo unknown:unknown)"
  mode="$(stat -c '%a' "$HOST_DATA_DIR" 2>/dev/null || echo unknown)"
  container_owner=""
  container_mode=""
  if have lxc && lxc info laia-agora >/dev/null 2>&1; then
    container_stat="$(lxc exec laia-agora -- stat -c '%U:%G %a' /opt/agora/data 2>/dev/null || true)"
    container_owner="${container_stat%% *}"
    container_mode="${container_stat##* }"
  fi
  if [[ "$container_owner" == "agora:agora" && "$container_mode" =~ ^(700|750|755)$ ]]; then
    ok "$HOST_DATA_DIR bind mount OK (host $owner mode=$mode → container $container_owner mode=$container_mode)"
  elif [[ "$owner" != "$EXPECTED_OWNER" || "$mode" != "755" ]]; then
    warn "$HOST_DATA_DIR está $owner mode=$mode (esperado $EXPECTED_OWNER 755). Fix: sudo chown -R $EXPECTED_OWNER $HOST_DATA_DIR && sudo chmod 755 $HOST_DATA_DIR"
    if [[ "$FIX" -eq 1 ]]; then
      if [[ "$EUID" -eq 0 ]]; then
        chown -R "$EXPECTED_OWNER" "$HOST_DATA_DIR" 2>/dev/null && chmod 755 "$HOST_DATA_DIR" && ok "$HOST_DATA_DIR corregido" || warn "no pude corregir $HOST_DATA_DIR"
      else
        warn "ejecuta con sudo para corregir $HOST_DATA_DIR"
      fi
    fi
  else
    ok "$HOST_DATA_DIR permisos OK"
  fi
else
  warn "$HOST_DATA_DIR no existe aún"
fi

if [[ -f "$AUTH_JSON_HOST" ]]; then
  auth_mode="$(stat -c '%a' "$AUTH_JSON_HOST" 2>/dev/null || echo unknown)"
  if [[ "$auth_mode" != "644" ]]; then
    warn "$AUTH_JSON_HOST está mode=$auth_mode (esperado 644 para bind read-only)"
    if [[ "$FIX" -eq 1 ]]; then
      chmod 644 "$AUTH_JSON_HOST" 2>/dev/null && ok "chmod 644 $AUTH_JSON_HOST aplicado" || warn "chmod 644 $AUTH_JSON_HOST falló"
    fi
  else
    ok "$AUTH_JSON_HOST mode 644"
  fi
else
  warn "$AUTH_JSON_HOST no existe"
fi

section "State files"
PERSIST_AGORA="$STATE_DIR/laia-agora-state.json"
TMP_AGORA="/tmp/laia-agora-state.json"
if have lxc; then
  AGORA_EXISTS=0
  lxc info laia-agora >/dev/null 2>&1 && AGORA_EXISTS=1
  if [[ -f "$TMP_AGORA" && "$AGORA_EXISTS" -eq 0 ]]; then
    warn "$TMP_AGORA existe pero laia-agora no: state stale"
  fi
  if [[ "$AGORA_EXISTS" -eq 1 && ! -f "$PERSIST_AGORA" ]]; then
    warn "laia-agora existe pero falta $PERSIST_AGORA; ejecuta infra/dev/rebuild-state.sh"
  elif [[ -f "$PERSIST_AGORA" ]]; then
    ok "state persistente de laia-agora presente"
  fi

  # Detect agent-* containers without a corresponding state file. After the
  # naming migration these are the new norm; a stray one means either the
  # user-provisioning script crashed mid-way, or someone deleted the state
  # by hand. Same check covers legacy ``laia-<slug>`` (excluding protected
  # names ``laia-agora`` and ``laia-jorge``).
  while read -r cname; do
    [[ -z "$cname" ]] && continue
    case "$cname" in
      laia-agora|laia-jorge|"") continue ;;
    esac
    if [[ "$cname" == agent-* ]]; then
      slug="${cname#agent-}"
    elif [[ "$cname" == laia-* ]]; then
      slug="${cname#laia-}"
    else
      continue
    fi
    state="$STATE_DIR/laia-state-${slug}.json"
    if [[ ! -f "$state" ]]; then
      warn "container '$cname' sin state file $state — ejecuta infra/dev/rebuild-state.sh --slug $slug (o lxc delete --force $cname)"
    fi
  done < <(lxc list --format csv -c n 2>/dev/null | awk -F, 'NR>=1{print $1}')
fi

section "Resumen"
printf "%s warnings, %s blockers\n" "$WARNINGS" "$BLOCKERS"
if [[ "$BLOCKERS" -gt 0 ]]; then
  exit 2
fi
exit 0
