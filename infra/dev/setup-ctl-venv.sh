#!/usr/bin/env bash
# setup-ctl-venv.sh — create / refresh the .ctl-venv used by the
# Textual-based AGORA control center (`python -m ctl`).
#
# Idempotent: if the venv already exists with the right Python interpreter
# and the locked deps are satisfied, this is a near-no-op. The wrapper
# script ``agora-control-center.sh`` calls this on demand.
#
# Flags:
#   --force   recreate the venv from scratch
#   -q        quiet pip output
#
# Exit codes:
#   0  → ready
#   1  → blocker (missing python3-venv, missing requirements file, …)
#   2  → bad usage

set -uo pipefail

FORCE=0
QUIET=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift;;
    -q|--quiet) QUIET=1; shift;;
    -h|--help) sed -n '1,17p' "$0"; exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ="$SCRIPT_DIR/requirements-ctl.txt"
VENV="$SCRIPT_DIR/.ctl-venv"

if [[ -t 1 ]]; then
  GRN=$'\033[1;32m'; YEL=$'\033[1;33m'; RED=$'\033[1;31m'; CYN=$'\033[1;36m'; RST=$'\033[0m'
else
  GRN=''; YEL=''; RED=''; CYN=''; RST=''
fi
ok()    { printf "  ${GRN}\xe2\x9c\x93${RST} %s\n" "$*"; }
warn()  { printf "  ${YEL}\xe2\x9a\xa0${RST} %s\n" "$*"; }
block() { printf "  ${RED}\xe2\x9c\x97${RST} %s\n" "$*" >&2; }
log()   { printf "${CYN}\xe2\x96\xb8${RST} %s\n" "$*"; }

[[ -f "$REQ" ]] || { block "$REQ no existe"; exit 1; }

if ! command -v python3 >/dev/null 2>&1; then
  block "python3 no instalado"; exit 1
fi

# Detect whether the active python3 ships venv. The error message of
# ``python3 -m venv --help`` exits non-zero only on ancient versions or
# Debian's stripped builds; we test by attempting a dry-run in /tmp.
if ! python3 -c 'import venv' >/dev/null 2>&1; then
  block "python3-venv no instalado (apt install python3-venv)"
  exit 1
fi

if [[ $FORCE -eq 1 && -d "$VENV" ]]; then
  log "borrando venv previo ($VENV)"
  rm -rf "$VENV"
fi

if [[ ! -d "$VENV" ]]; then
  log "creando venv en $VENV"
  python3 -m venv "$VENV" || { block "python3 -m venv fall\xc3\xb3"; exit 1; }
fi

# shellcheck disable=SC1091
. "$VENV/bin/activate"

PIP_QUIET=""
[[ $QUIET -eq 1 ]] && PIP_QUIET="-q"

log "actualizando pip (silencioso)"
python -m pip install $PIP_QUIET --upgrade pip >/dev/null 2>&1 || warn "pip upgrade fall\xc3\xb3"

# Hash file to short-circuit when requirements haven't changed.
HASH_FILE="$VENV/.requirements.sha256"
NEW_HASH="$(sha256sum "$REQ" | awk '{print $1}')"
if [[ -f "$HASH_FILE" && "$(cat "$HASH_FILE")" == "$NEW_HASH" && $FORCE -eq 0 ]]; then
  ok "deps al d\xc3\xada (hash match)"
else
  log "instalando requirements"
  if ! python -m pip install $PIP_QUIET -r "$REQ"; then
    block "pip install fall\xc3\xb3"; exit 1
  fi
  echo "$NEW_HASH" > "$HASH_FILE"
  ok "deps instaladas/actualizadas"
fi

# Sanity: imports clave funcionan
if ! python -c "import textual, httpx, yaml" 2>/dev/null; then
  block "imports b\xc3\xa1sicos fallan tras install"
  exit 1
fi

ok "$VENV listo (textual + httpx + pyyaml)"
echo
echo "Lanzar con:"
echo "  bash $SCRIPT_DIR/agora-control-center.sh"
