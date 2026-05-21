#!/usr/bin/env bash
# laia-init-checks.sh — read-only pre-flight for the AGORA wizard.
#
# Reports the host's readiness to run ``laia-init.sh`` without mutating
# anything. The wizard calls this on entry; CI / tests invoke it via
# ``tests/test_laia_init_checks.sh`` with a PATH overlay to mock LXD.
#
# Exit codes:
#   0  → ready (no blockers; warnings may exist)
#   1  → at least one blocker (e.g. LXD missing)
#   2  → invalid arguments
#
# Usage:
#   bash infra/dev/laia-init-checks.sh
#   bash infra/dev/laia-init-checks.sh --json     # machine-readable

set -uo pipefail

OUTPUT_JSON=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json) OUTPUT_JSON=1; shift;;
    -h|--help)
      sed -n '1,18p' "$0"
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
AUTH_JSON="${AUTH_JSON_HOST:-$ORIG_HOME/.laia/auth.json}"
HOST_DATA_DIR="${HOST_DATA_DIR:-/srv/laia/agora}"

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; RST='\033[0m'
else
  GRN=''; YEL=''; RED=''; CYN=''; RST=''
fi
log()   { [[ $OUTPUT_JSON -eq 1 ]] || printf "${CYN}▸${RST} %s\n" "$*"; }
ok()    { [[ $OUTPUT_JSON -eq 1 ]] || printf "  ${GRN}✓${RST} %s\n" "$*"; }
warn()  { [[ $OUTPUT_JSON -eq 1 ]] || printf "  ${YEL}⚠${RST} %s\n" "$*"; WARNS=$((WARNS+1)); }
block() { [[ $OUTPUT_JSON -eq 1 ]] || printf "  ${RED}✗${RST} %s\n" "$*" >&2; BLOCKS=$((BLOCKS+1)); }

WARNS=0
BLOCKS=0
RESULTS=()
add_result() { RESULTS+=("\"$1\":\"$2\""); }

log "Pre-flight checks (read-only)"

# LXD
if command -v lxc >/dev/null 2>&1; then
  ok "LXD client (lxc) presente"
  add_result lxd ok
else
  block "LXD client no instalado — instala lxd (5.x)"
  add_result lxd missing
fi

# jq
if command -v jq >/dev/null 2>&1; then
  ok "jq disponible"; add_result jq ok
else
  block "jq no instalado"; add_result jq missing
fi

# curl
if command -v curl >/dev/null 2>&1; then
  ok "curl disponible"; add_result curl ok
else
  block "curl no instalado"; add_result curl missing
fi

# python3
if command -v python3 >/dev/null 2>&1; then
  ok "python3 disponible"; add_result python3 ok
else
  block "python3 no instalado"; add_result python3 missing
fi

# sudo
if command -v sudo >/dev/null 2>&1; then
  ok "sudo disponible"; add_result sudo ok
else
  warn "sudo no encontrado — algunos pasos del wizard requieren root"
  add_result sudo missing
fi

# AGORA data dir
if [[ -d "$HOST_DATA_DIR" ]]; then
  ok "$HOST_DATA_DIR existe"; add_result data_dir ok
else
  warn "$HOST_DATA_DIR no existe (lo crea rebuild-3)"
  add_result data_dir missing
fi

# auth.json
if [[ -f "$AUTH_JSON" ]]; then
  ok "$AUTH_JSON presente"; add_result auth_json ok
else
  warn "$AUTH_JSON ausente — el wizard pedirá cómo obtenerlo"
  add_result auth_json missing
fi

if [[ $OUTPUT_JSON -eq 1 ]]; then
  # Crude but dependency-free JSON.
  joined="$(IFS=,; echo "${RESULTS[*]}")"
  printf '{"warnings":%d,"blockers":%d,%s}\n' "$WARNS" "$BLOCKS" "$joined"
fi

[[ $BLOCKS -gt 0 ]] && exit 1
exit 0
