# ─────────────────────────────────────────────────────────────────────────────
# sudo.sh — sudo guard and privilege helpers
#
# Conventions:
#   - LAIA_USER     : the unprivileged admin user (the LAIA-ARCH admin).
#                     When called via sudo this is SUDO_USER.
#                     When called directly this is whoever ran the script.
#   - LAIA_USER_HOME: that user's $HOME (NOT root's /root).
#   - We escalate to root only for /opt and /usr/local/bin operations.
#
# require_root [<reason>]
#   Aborts unless running as uid 0. Use at the top of laia-install/release/rollback.
#
# run_as_user <cmd...>
#   Runs <cmd> as LAIA_USER. Used when root needs to invoke pnpm/git/etc. that
#   should not produce root-owned files in the user's home.
# ─────────────────────────────────────────────────────────────────────────────

[[ -n "${LAIA_LIB_SUDO_LOADED:-}" ]] && return 0
readonly LAIA_LIB_SUDO_LOADED=1

# Resolve the admin user — even when invoked via sudo.
if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != "root" ]]; then
  LAIA_USER="$SUDO_USER"
  LAIA_USER_HOME="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
else
  LAIA_USER="$(id -un)"
  LAIA_USER_HOME="$HOME"
fi
export LAIA_USER LAIA_USER_HOME

is_root() {
  [[ "$(id -u)" -eq 0 ]]
}

require_root() {
  local reason="${1:-this operation writes to /opt and /usr/local/bin}"
  if ! is_root; then
    log_error "Must run as root: $reason"
    log_info  "Re-run with: sudo -E $0 $*"
    exit 1
  fi
  if [[ "$LAIA_USER" == "root" ]]; then
    log_warn "Running as actual root (no SUDO_USER set)."
    log_warn "LAIA-ARCH is single-user-admin and expects to run under a regular"
    log_warn "user via sudo. Set SUDO_USER or run as that user via 'sudo -E'."
  fi
}

require_not_root() {
  if is_root; then
    die "Must NOT run as root for this operation. Run as the admin user."
  fi
}

# run_as_user <cmd...> — execute as the admin user even if we are root.
run_as_user() {
  if is_root && [[ "$LAIA_USER" != "root" ]]; then
    sudo -u "$LAIA_USER" -H "$@"
  else
    "$@"
  fi
}

# ensure_sudo_cached — warm up sudo timestamp so prompts don't appear mid-script
ensure_sudo_cached() {
  if ! is_root; then
    sudo -v || die "sudo authentication required"
  fi
}
