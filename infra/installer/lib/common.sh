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
  # Skip silently when the log isn't writable — e.g. a root-owned log left by
  # `sudo laia install`, later read by a non-root invocation. Guarding here
  # avoids leaking the shell's "Permission denied" redirection error to stderr
  # (the `2>/dev/null` on the printf can't suppress a failed `>>` open).
  if [[ -e "$LAIA_LOG_FILE" ]]; then
    [[ -w "$LAIA_LOG_FILE" ]] || return 0
  else
    [[ -w "$(dirname "$LAIA_LOG_FILE")" ]] || return 0
  fi
  printf '[%s] [%s] %s\n' "$(date -Iseconds)" "$1" "$2" >>"$LAIA_LOG_FILE" 2>/dev/null || true
}

log_info()    { printf '%s→%s %s\n' "$C_CYN" "$C_RST" "$1";        _log_to_file INFO  "$1"; }
log_success() { printf '%s✓%s %s\n' "$C_GRN" "$C_RST" "$1";        _log_to_file OK    "$1"; }
log_warn()    { printf '%s⚠%s %s\n' "$C_YEL" "$C_RST" "$1" >&2;    _log_to_file WARN  "$1"; }
log_error()   { printf '%s✗%s %s\n' "$C_RED" "$C_RST" "$1" >&2;    _log_to_file ERROR "$1"; }

# log_step <label> [step_id]
# Print the phase banner AND auto-emit a step_start JSON event when
# LAIA_JSON_PROGRESS=1 — that way every phase boundary surfaces to the
# wizard parser without each caller having to remember a paired
# emit_json_event call (a recurring source of drift before this).
# step_id defaults to a slug derived from the label.
log_step() {
  local label="$1" step_id="${2:-}"
  if [[ -z "$step_id" ]]; then
    # Derive a stable id: lower-case, non-alnum → '-', collapse runs of '-'.
    step_id="$(printf '%s' "$label" \
      | tr '[:upper:]' '[:lower:]' \
      | tr -c 'a-z0-9' '-' \
      | sed 's/--*/-/g; s/^-//; s/-$//')"
    [[ -n "$step_id" ]] || step_id="step"
  fi
  printf '\n%s%s═══ %s ═══════════════════════════════════════════════%s\n' \
    "$C_YEL" "$C_BLD" "$label" "$C_RST"
  _log_to_file STEP "$label"
  emit_json_event step_start "$step_id" "$label"
}

# log_step_done [label] [step_id]
# Symmetric closer for log_step — emits step_done JSON when JSON mode is
# on, and prints a brief success banner. Defaults to the most recent
# LAIA_CURRENT_STEP so callers can just write `log_step_done` after the
# matching log_step.
log_step_done() {
  local label="${1:-OK}" step_id="${2:-${LAIA_CURRENT_STEP:-}}"
  if [[ -n "$label" && "$label" != "OK" ]]; then
    log_success "$label"
  fi
  emit_json_event step_done "$step_id" "$label"
}

# emit_json_event <event_type> <step_id> <label> [percent]
# Emits a structured JSON event line to stdout when LAIA_JSON_PROGRESS=1.
# Used by the laia-wizard frontend to render progress reliably without
# having to scrape the human-readable log. The four event types match
# install_wizard.contract.ProgressEvent.type:
#   step_start | step_progress | step_done | step_error
# When LAIA_JSON_PROGRESS is unset, this is a no-op so the binary's
# normal CLI experience is unchanged.
emit_json_event() {
  [[ "${LAIA_JSON_PROGRESS:-0}" != "1" ]] && return 0
  local event_type="${1:-step_progress}"
  local step_id="${2:-}"
  local label="${3:-}"
  local percent="${4:-null}"
  if [[ "$event_type" == "step_start" || "$event_type" == "step_progress" ]]; then
    export LAIA_CURRENT_STEP="$step_id"
  fi
  # Escape the few characters that must be escaped in JSON strings.
  # We keep this in pure bash to avoid taking a hard dependency on jq.
  _json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
  }
  printf '{"event":"%s","step_id":"%s","label":"%s","percent":%s,"ts":"%s","run_id":"%s"}\n' \
    "$(_json_escape "$event_type")" \
    "$(_json_escape "$step_id")" \
    "$(_json_escape "$label")" \
    "$percent" \
    "$(date -Iseconds)" \
    "$(_json_escape "${LAIA_RUN_ID:-}")"
}

# die <msg> [exit_code]
die() {
  emit_json_event step_error "${LAIA_CURRENT_STEP:-fatal}" "$1" null
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
  trap 'rc=$?; msg="Failed at ${BASH_SOURCE[0]}:${LINENO} (exit $rc)"; emit_json_event step_error "${LAIA_CURRENT_STEP:-fatal}" "$msg" null; log_error "$msg"; exit "$rc"' ERR
}

_laia_descendant_pids() {
  command -v pgrep >/dev/null 2>&1 || return 0
  local parent="$1" child
  while IFS= read -r child; do
    [[ -n "$child" ]] || continue
    printf '%s\n' "$child"
    _laia_descendant_pids "$child"
  done < <(pgrep -P "$parent" 2>/dev/null || true)
}

_laia_signal_abort() {
  local sig="${1:-INT}" pids active="${LAIA_ACTIVE_CHILD_PID:-}"
  trap - INT TERM QUIT
  emit_json_event step_error "${LAIA_CURRENT_STEP:-interrupted}" "Interrupted by SIG$sig; cancelling" null
  log_warn "Interrupted by SIG$sig — cancelling LAIA operation now."

  pids="$(
    [[ -n "$active" ]] && printf '%s\n' "$active"
    [[ -n "$active" ]] && _laia_descendant_pids "$active" 2>/dev/null || true
    jobs -pr 2>/dev/null
    _laia_descendant_pids "$$" 2>/dev/null || true
  )"
  if [[ -n "$pids" ]]; then
    # TERM first so apt/dpkg/ssh/rsync can unwind; KILL after a short grace.
    kill -TERM $pids 2>/dev/null || true
    sleep 1
    kill -KILL $pids 2>/dev/null || true
  fi
  exit 130
}

install_signal_traps() {
  trap '_laia_signal_abort INT; exit 130' INT
  trap '_laia_signal_abort TERM; exit 130' TERM
  trap '_laia_signal_abort QUIT; exit 130' QUIT
}

laia_run_interruptible() {
  "$@" &
  local pid=$! rc
  LAIA_ACTIVE_CHILD_PID="$pid"
  set +e
  wait "$pid"
  rc=$?
  set -e
  LAIA_ACTIVE_CHILD_PID=""
  return "$rc"
}
