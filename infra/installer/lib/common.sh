# ─────────────────────────────────────────────────────────────────────────────
# common.sh — logging, colors, error helpers
#
# Source-safe: only defines functions and a few read-only globals. No side
# effects beyond exporting LAIA_LIB_COMMON_LOADED.
#
# Usage from a bin/ script:
#   source "$(dirname "${BASH_SOURCE[0]}")/../infra/installer/lib/common.sh"
#   log_info "Starting..."
#   die "Cannot find config"     # exits 1
# ─────────────────────────────────────────────────────────────────────────────

[[ -n "${LAIA_LIB_COMMON_LOADED:-}" ]] && return 0
readonly LAIA_LIB_COMMON_LOADED=1

# Colors — disabled when NO_COLOR is set or stdout is not a tty.
if [[ -z "${NO_COLOR:-}" && -t 1 ]]; then
  readonly C_RED=$'\033[1;31m'
  readonly C_GRN=$'\033[1;32m'
  readonly C_YEL=$'\033[1;33m'
  readonly C_BLU=$'\033[1;34m'
  readonly C_CYN=$'\033[1;36m'
  readonly C_DIM=$'\033[2m'
  readonly C_BLD=$'\033[1m'
  readonly C_RST=$'\033[0m'
else
  readonly C_RED='' C_GRN='' C_YEL='' C_BLU='' C_CYN='' C_DIM='' C_BLD='' C_RST=''
fi

# Log file (each bin/ script may override before sourcing).
LAIA_LOG_FILE="${LAIA_LOG_FILE:-${XDG_CACHE_HOME:-$HOME/.cache}/laia-installer.log}"
mkdir -p "$(dirname "$LAIA_LOG_FILE")" 2>/dev/null || true

_log_to_file() {
  printf '[%s] [%s] %s\n' "$(date -Iseconds)" "$1" "$2" >>"$LAIA_LOG_FILE" 2>/dev/null || true
}

log_info()    { printf '%s→%s %s\n' "$C_CYN" "$C_RST" "$1";        _log_to_file INFO  "$1"; }
log_success() { printf '%s✓%s %s\n' "$C_GRN" "$C_RST" "$1";        _log_to_file OK    "$1"; }
log_warn()    { printf '%s⚠%s %s\n' "$C_YEL" "$C_RST" "$1" >&2;    _log_to_file WARN  "$1"; }
log_error()   { printf '%s✗%s %s\n' "$C_RED" "$C_RST" "$1" >&2;    _log_to_file ERROR "$1"; }

log_step() {
  printf '\n%s%s═══ %s ═══════════════════════════════════════════════%s\n' \
    "$C_YEL" "$C_BLD" "$1" "$C_RST"
  _log_to_file STEP "$1"
}

# die <msg> [exit_code]
die() {
  log_error "$1"
  exit "${2:-1}"
}

# require_cmd <cmd> [hint]
require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1${2:+ — $2}"
}

# confirm <prompt> [default=n]   returns 0 if user said yes, 1 otherwise
confirm() {
  local prompt="$1" default="${2:-n}" suffix reply
  case "$default" in
    [yY]*) suffix="[Y/n]" ;;
    *)     suffix="[y/N]" ;;
  esac

  if [[ "${LAIA_NONINTERACTIVE:-false}" == true ]]; then
    case "$default" in [yY]*) return 0 ;; *) return 1 ;; esac
  fi

  if [[ -t 0 ]]; then
    read -r -p "$prompt $suffix " reply || reply=""
  elif [[ -r /dev/tty ]]; then
    printf '%s %s ' "$prompt" "$suffix" >/dev/tty
    IFS= read -r reply </dev/tty || reply=""
  else
    case "$default" in [yY]*) return 0 ;; *) return 1 ;; esac
  fi

  case "$reply" in
    [yY]|[yY][eE][sS]) return 0 ;;
    "") case "$default" in [yY]*) return 0 ;; *) return 1 ;; esac ;;
    *) return 1 ;;
  esac
}

# trap_errors — install ERR trap that prints location of failure
trap_errors() {
  set -E
  trap 'log_error "Failed at ${BASH_SOURCE[0]}:${LINENO} (exit $?)"' ERR
}
