#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# LAIA bootstrap installer — production-grade entry point for a clean server
#
# Intended use, from a brand-new Ubuntu 22.04+ host (you SSH'd in as `jorge`
# or whoever will own LAIA on this machine):
#
#   # Interactive wizard (recommended for humans, asks everything):
#   curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/stable/install.sh \
#     | sudo -E bash
#
#   # Headless clone of an existing LAIA host (CI / scripted):
#   curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/stable/install.sh \
#     | sudo -E bash -s -- --mode clone --source laia-hermes@old.example.com --yes
#
#   # Headless fresh install:
#   curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/stable/install.sh \
#     | sudo -E bash -s -- --mode install --yes
#
# What this script does, in order:
#
#   1. Detects the invoking non-root user (must run via `sudo -E`) and target
#      directory layout: ~/LAIA (code), ~/.laia (runtime), /srv/laia (data),
#      /opt/laia (versioned install — created later by bin/laia-install).
#   2. Installs apt prerequisites idempotently.
#   3. Clones (or fast-forwards) the LAIA repo into ~/LAIA so the host has
#      a permanent dev tree — `laia-release`, future updates, and bug-report
#      reproduction all need it.
#   4. Hands off to bin/laia (wizard | install | clone subcommand) or bin/laia-install /
#      bin/laia-clone (headless), depending on --mode.
#
# Anything destructive (apt-install, mkdir under $HOME, sudo write to /opt
# or /srv) is preceded by a one-shot summary the user must accept, unless
# --yes was passed.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ─── Defaults ────────────────────────────────────────────────────────────────
DEFAULT_REPO_URL="https://github.com/JorgeMP-3/laia-arch.git"
DEFAULT_BRANCH="stable"
DEFAULT_MODE="wizard"

LAIA_REPO_URL="${LAIA_REPO_URL:-$DEFAULT_REPO_URL}"
LAIA_BRANCH="${LAIA_BRANCH:-$DEFAULT_BRANCH}"

OPT_MODE="$DEFAULT_MODE"
OPT_SOURCE=""
OPT_LAIA_DIR=""
OPT_CONFIG=""
OPT_YES=false
OPT_NO_APT=false
OPT_PRESERVE_BRANCH=false
OPT_MODE_EXPLICIT=false
OPT_SOURCE_EXPLICIT=false
PASSTHRU_ARGS=()

# Colors (off when not a TTY or NO_COLOR is set).
if [[ -z "${NO_COLOR:-}" && -t 1 ]]; then
  C_R=$'\033[1;31m'; C_G=$'\033[1;32m'; C_Y=$'\033[1;33m'
  C_B=$'\033[1;34m'; C_C=$'\033[1;36m'; C_D=$'\033[2m'; C_0=$'\033[0m'
else
  C_R=''; C_G=''; C_Y=''; C_B=''; C_C=''; C_D=''; C_0=''
fi

log()   { printf '%s→%s %s\n' "$C_C"  "$C_0" "$*"; }
ok()    { printf '%s✓%s %s\n' "$C_G"  "$C_0" "$*"; }
warn()  { printf '%s⚠%s %s\n' "$C_Y"  "$C_0" "$*" >&2; }
err()   { printf '%s✗%s %s\n' "$C_R"  "$C_0" "$*" >&2; }
die()   { err "$@"; exit 1; }
step()  { printf '\n%s%s═══ %s ═══════════════════════════════════════════════%s\n' \
           "$C_Y" "$C_B" "$1" "$C_0"; }

descendant_pids() {
  command -v pgrep >/dev/null 2>&1 || return 0
  local parent="$1" child
  while IFS= read -r child; do
    [[ -n "$child" ]] || continue
    printf '%s\n' "$child"
    descendant_pids "$child"
  done < <(pgrep -P "$parent" 2>/dev/null || true)
}

abort_now() {
  local sig="${1:-INT}" pids active="${LAIA_ACTIVE_CHILD_PID:-}"
  trap - INT TERM QUIT
  warn "Interrupted by SIG$sig — cancelling LAIA bootstrap now."
  pids="$(
    [[ -n "$active" ]] && printf '%s\n' "$active"
    [[ -n "$active" ]] && descendant_pids "$active" 2>/dev/null || true
    jobs -pr 2>/dev/null
    descendant_pids "$$" 2>/dev/null || true
  )"
  if [[ -n "$pids" ]]; then
    kill -TERM $pids 2>/dev/null || true
    sleep 1
    kill -KILL $pids 2>/dev/null || true
  fi
  exit 130
}

install_signal_traps() {
  trap 'abort_now INT; exit 130' INT
  trap 'abort_now TERM; exit 130' TERM
  trap 'abort_now QUIT; exit 130' QUIT
}

run_interruptible() {
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

# Read from /dev/tty when stdin is not a terminal — typical when invoked
# via `curl … | sudo -E bash`, where bash's stdin is the (drained) curl
# pipe. Without this, all interactive prompts return empty immediately
# and the user doesn't even see them.
ask_tty_into() {
  local __var="$1" prompt="$2" ans=""
  if [[ -t 0 ]]; then
    read -r -p "$prompt" ans || ans=""
  elif [[ -r /dev/tty ]]; then
    printf '%s' "$prompt" >/dev/tty
    IFS= read -r ans </dev/tty || ans=""
  fi
  printf -v "$__var" '%s' "$ans"
}

# ─── Help ────────────────────────────────────────────────────────────────────
usage() {
  cat <<EOF
LAIA bootstrap installer — production-grade server setup

USAGE
    sudo -E bash install.sh [OPTIONS]
    curl -fsSL .../install.sh | sudo -E bash -s -- [OPTIONS]

OPTIONS
    --mode {wizard|install|clone}
                          What to run after prereqs + clone.
                          If omitted in an interactive terminal, this script
                          asks whether to install from zero or clone.
    --source user@host    Source server for --mode=clone. If omitted
                          interactively, the script asks user + IP/hostname.
    --branch BRANCH       Git branch / tag to install from.
                          Default: $DEFAULT_BRANCH
    --laia-dir PATH       Where to clone the repo. Default: \$SUDO_USER's
                          \$HOME/LAIA, e.g. /home/jorge/LAIA.
    --config FILE         YAML/JSON config passed through to laia wizard
                          for fully unattended runs.
    --yes, -y             Skip all confirmations (apt install, plan summary,
                          wizard prompts). Required for CI / curl|bash auto.
    --no-apt              Don't try to apt-install missing prereqs (assumes
                          they're already there; useful in containers).
    --                    Everything after this is passed verbatim to the
                          subcommand (bin/laia-install, bin/laia-clone,
                          bin/laia wizard).
    -h, --help            Show this help.

ENVIRONMENT
    LAIA_REPO_URL         Git repo URL (default: $DEFAULT_REPO_URL).
    LAIA_BRANCH           Same as --branch.
    LAIA_GITHUB_TOKEN     GitHub token if the repo is private.

EXAMPLES
    # Most common: clone from an existing LAIA host onto this new server.
    curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/$DEFAULT_BRANCH/install.sh \\
      | sudo bash -s -- --mode clone --source usuario@192.0.2.10 --yes

    # Or interactive (asks everything in the TUI):
    curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/$DEFAULT_BRANCH/install.sh \\
      | sudo -E bash

    # CI: fully unattended, all answers in a YAML file ahead of time.
    sudo -E bash install.sh --config /tmp/laia-install.yaml --yes

EXIT CODES
    0  Success
    1  Generic failure (most often from a sub-command)
    2  Bad arguments / pre-flight failed (no destructive action taken)
    3  Missing prerequisites we couldn't auto-install
EOF
}

# ─── Argument parsing ────────────────────────────────────────────────────────
parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)        usage; exit 0 ;;
      --mode)
        [[ $# -ge 2 ]] || die "--mode requires a value"
        OPT_MODE="$2"; OPT_MODE_EXPLICIT=true; shift 2 ;;
      --source)
        [[ $# -ge 2 ]] || die "--source requires user@host"
        OPT_SOURCE="$2"; OPT_SOURCE_EXPLICIT=true; shift 2 ;;
      --branch)
        [[ $# -ge 2 ]] || die "--branch requires a name"
        LAIA_BRANCH="$2"; OPT_PRESERVE_BRANCH=true; shift 2 ;;
      --laia-dir)
        [[ $# -ge 2 ]] || die "--laia-dir requires a path"
        OPT_LAIA_DIR="$2"; shift 2 ;;
      --config)
        [[ $# -ge 2 ]] || die "--config requires a path"
        OPT_CONFIG="$2"; shift 2 ;;
      -y|--yes)         OPT_YES=true; shift ;;
      --no-apt)         OPT_NO_APT=true; shift ;;
      --)               shift; PASSTHRU_ARGS=("$@"); break ;;
      *)
        # Anything we don't recognize after the known flags is also passthrough.
        PASSTHRU_ARGS+=("$1"); shift ;;
    esac
  done

  case "$OPT_MODE" in
    wizard|install|clone) ;;
    *) die "Unknown --mode: $OPT_MODE (expected wizard|install|clone)" ;;
  esac
}

validate_source() {
  local source="$1" user host
  [[ -n "$source" ]] || die "Clone source is empty."

  case "$source" in
    *IP_DEL*|*IP-DEL*|*old-server*|*viejo-server*|*example.com*|*"<"*|*">"*)
      die "Source '$source' looks like a documentation placeholder. Use the real user and IP/hostname, e.g. jorge@192.168.1.50"
      ;;
  esac

  if [[ "$source" != *@* ]]; then
    die "Source must be user@host, got: $source"
  fi
  user="${source%@*}"
  host="${source#*@}"
  if [[ ! "$user" =~ ^[A-Za-z_][A-Za-z0-9_.-]{0,31}$ ]]; then
    die "Invalid source user '$user'. Use a normal SSH username, e.g. jorge"
  fi
  if [[ -z "$host" || "$host" =~ [[:space:]\;\|\&\$\(\)\<\>\\\'\"] ]]; then
    die "Invalid source host '$host'. Use a real IP, DNS name, or Tailscale hostname."
  fi
}

collect_interactive_intent() {
  [[ -n "$OPT_CONFIG" ]] && return 0

  if [[ "$OPT_MODE_EXPLICIT" == false ]]; then
    OPT_MODE="wizard"
    log "Bootstrap mode: opening the full wizard after prerequisites."
  fi

  if [[ "$OPT_MODE" == "clone" && -z "$OPT_SOURCE" ]]; then
    if [[ "$OPT_YES" == true ]]; then
      die "--mode clone with --yes requires --source user@host. Refusing to guess."
    fi
    step "Source server to clone from"
    local src_user src_host
    ask_tty_into src_user 'SSH username on the OLD server: '
    ask_tty_into src_host 'IP/hostname of the OLD server: '
    [[ -n "$src_user" ]] || die "Source SSH username is required."
    [[ -n "$src_host" ]] || die "Source IP/hostname is required."
    OPT_SOURCE="${src_user}@${src_host}"
  fi

  if [[ "$OPT_MODE" == "clone" || -n "$OPT_SOURCE" ]]; then
    validate_source "$OPT_SOURCE"
  fi
}

# ─── User / paths resolution ─────────────────────────────────────────────────
resolve_user() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    die "Run through sudo: sudo -E bash install.sh ... (or curl ... | sudo -E bash)"
  fi
  LAIA_USER="${SUDO_USER:-}"
  if [[ -z "$LAIA_USER" || "$LAIA_USER" == "root" ]]; then
    die "Refusing to install LAIA as root. SSH in as a non-root user with sudo and re-run."
  fi
  LAIA_USER_HOME="$(getent passwd "$LAIA_USER" | cut -d: -f6)"
  [[ -d "$LAIA_USER_HOME" ]] || die "Home directory not found for $LAIA_USER: $LAIA_USER_HOME"

  if [[ -z "$OPT_LAIA_DIR" ]]; then
    OPT_LAIA_DIR="$LAIA_USER_HOME/LAIA"
  fi
  LAIA_DIR="$OPT_LAIA_DIR"
}

# ─── Prereqs ─────────────────────────────────────────────────────────────────
detect_os() {
  if [[ ! -r /etc/os-release ]]; then
    warn "No /etc/os-release — proceeding without OS detection."
    return 0
  fi
  # shellcheck disable=SC1091
  . /etc/os-release
  case "${ID:-}:${VERSION_ID:-}" in
    ubuntu:22.*|ubuntu:24.*|debian:12*|debian:13*) ;;
    *)
      warn "OS $ID $VERSION_ID is untested. Proceeding anyway."
      ;;
  esac
}

# Packages we need on the host (BEFORE laia-install runs). The installer itself
# handles its own venv prereqs (python3-venv used by .laia-core).
APT_PACKAGES=(
  git
  python3
  python3-venv
  python3-pip
  sqlite3
  rsync
  curl
  ca-certificates
  openssh-client
  snapd
  build-essential
)

apt_missing() {
  local missing=()
  for pkg in "${APT_PACKAGES[@]}"; do
    # dpkg returns 0 when the package is installed.
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
      missing+=("$pkg")
    fi
  done
  printf '%s\n' "${missing[@]}"
}

ensure_prereqs() {
  step "Pre-flight: apt prerequisites"
  local missing
  mapfile -t missing < <(apt_missing)
  if [[ "${#missing[@]}" -eq 0 ]] || [[ "${#missing[@]}" -eq 1 && -z "${missing[0]}" ]]; then
    ok "All ${#APT_PACKAGES[@]} prerequisites already installed."
    return 0
  fi
  if $OPT_NO_APT; then
    die "Missing packages: ${missing[*]}  (--no-apt was set, install them yourself)"
  fi
  if ! command -v apt-get >/dev/null 2>&1; then
    die "Missing packages: ${missing[*]}  and apt-get not available."
  fi
  log "Will apt-install: ${missing[*]}"
  if ! $OPT_YES; then
    ask_tty_into ans 'Proceed with apt install? [Y/n] '
    case "${ans:-y}" in [nN]*) die "Aborted by user." ;; esac
  fi

  # Show apt's own progress (no -qq, no -y on a silent pipe). This is
  # what tells the user "yes, something is happening" while packages
  # download and configure. Each line apt prints is a visible
  # heartbeat; without it the user sees a blank screen for 30-60s
  # and (justifiably) thinks the script froze.
  log "Running 'apt-get update' (refresh package lists)..."
  if ! run_interruptible apt-get update; then
    die "apt-get update failed — check your internet connection / proxy."
  fi
  log "Running 'apt-get install' for ${#missing[@]} package(s)..."
  if ! run_interruptible env DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing[@]}"; then
    die "apt-get install failed — see output above for the offending package."
  fi
  ok "Installed ${#missing[@]} packages: ${missing[*]}"
}

# ─── Clone / update the repo ────────────────────────────────────────────────
clone_or_update() {
  step "LAIA source tree at $LAIA_DIR"
  if [[ -d "$LAIA_DIR/.git" ]]; then
    local current
    current="$(sudo -u "$LAIA_USER" git -C "$LAIA_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
    log "Existing repo found (branch: $current). Updating."
    run_interruptible sudo -u "$LAIA_USER" git -C "$LAIA_DIR" fetch --depth 1 origin "$LAIA_BRANCH"
    run_interruptible sudo -u "$LAIA_USER" git -C "$LAIA_DIR" checkout "$LAIA_BRANCH"
    run_interruptible sudo -u "$LAIA_USER" git -C "$LAIA_DIR" reset --hard "origin/$LAIA_BRANCH"
    ok "Updated to origin/$LAIA_BRANCH"
    return 0
  fi

  if [[ -e "$LAIA_DIR" ]]; then
    die "$LAIA_DIR exists but is not a git repo. Move it aside and re-run."
  fi

  log "Cloning $LAIA_REPO_URL ($LAIA_BRANCH) → $LAIA_DIR"
  install -d -o "$LAIA_USER" -g "$LAIA_USER" "$(dirname "$LAIA_DIR")"
  local git_cmd=(git clone --depth 1 --branch "$LAIA_BRANCH" "$LAIA_REPO_URL" "$LAIA_DIR")
  if [[ -n "${LAIA_GITHUB_TOKEN:-${GITHUB_TOKEN:-}}" ]]; then
    local token="${LAIA_GITHUB_TOKEN:-${GITHUB_TOKEN:-}}"
    local basic
    basic="$(printf 'x-access-token:%s' "$token" | base64 | tr -d '\n')"
    run_interruptible sudo -u "$LAIA_USER" git -c "http.https://github.com/.extraheader=AUTHORIZATION: basic ${basic}" \
      clone --depth 1 --branch "$LAIA_BRANCH" "$LAIA_REPO_URL" "$LAIA_DIR"
  else
    run_interruptible sudo -u "$LAIA_USER" "${git_cmd[@]}"
  fi
  ok "Cloned."
}

# ─── Plan summary (shown before any destructive action other than apt) ──────
print_plan() {
  if [[ "$OPT_MODE" == "wizard" && "$OPT_MODE_EXPLICIT" == false && -z "$OPT_CONFIG" ]]; then
    return 0
  fi

  step "Plan"
  local source_line=""
  if [[ "$OPT_MODE" == "clone" ]]; then
    source_line="  Source server:    $OPT_SOURCE"
  fi
  cat <<EOF
  Action:           $OPT_MODE
  Repo:             $LAIA_REPO_URL ($LAIA_BRANCH)
  Code tree:        $LAIA_DIR
  Owner:            $LAIA_USER ($LAIA_USER_HOME)
$([ -n "$source_line" ] && echo "$source_line")
$([ -n "$OPT_CONFIG" ] && echo "  Config file:      $OPT_CONFIG")
  Will install to:  /opt/laia → /opt/laia-vX.Y.Z (managed by bin/laia-install)
  Data dir:         /srv/laia (factory state + agora.db)
  Admin home:       $LAIA_USER_HOME/LAIA-ARCH
  Unattended:       $OPT_YES
EOF
  if ! $OPT_YES; then
    ask_tty_into ans 'Continue? [Y/n] '
    case "${ans:-y}" in [nN]*) die "Aborted by user." ;; esac
  fi
}

# ─── Pre-hand-off cleanup ──────────────────────────────────────────────────
# Earlier install attempts that ran as root may have left files in the
# user's home owned by root (e.g. ~/.bashrc, ~/.cache/, ~/.laia/). The
# user then can't even SSH back in cleanly. Fix that here, idempotently.
chown_user_home() {
  local target="$LAIA_USER_HOME"
  [[ -d "$target" ]] || return 0
  local fixed=0
  for f in "$target/.bashrc" "$target/.profile" "$target/.bash_logout" \
           "$target/.cache" "$target/.laia" "$target/.ssh" \
           "$target/LAIA" "$target/LAIA-ARCH"; do
    [[ -e "$f" ]] || continue
    if [[ "$(stat -c '%U' "$f" 2>/dev/null)" != "$LAIA_USER" ]]; then
      chown -R "$LAIA_USER:$LAIA_USER" "$f" 2>/dev/null && fixed=$((fixed+1)) || true
    fi
  done
  [[ $fixed -gt 0 ]] && log "Fixed ownership of $fixed item(s) under $target."
  return 0
}

# ─── Sub-command handoff ─────────────────────────────────────────────────────
hand_off() {
  step "Running: $OPT_MODE"
  chown_user_home

  local bin="$LAIA_DIR/bin"
  local cmd=()

  case "$OPT_MODE" in
    install)
      cmd=("$bin/laia-install" --from-local "$LAIA_DIR")
      $OPT_YES && cmd+=(--yes)
      cmd+=("${PASSTHRU_ARGS[@]+"${PASSTHRU_ARGS[@]}"}")
      ;;
    clone)
      cmd=("$bin/laia-clone")
      [[ -n "$OPT_SOURCE" ]] && cmd+=(--source "$OPT_SOURCE")
      $OPT_YES && cmd+=(--yes)
      cmd+=("${PASSTHRU_ARGS[@]+"${PASSTHRU_ARGS[@]}"}")
      ;;
    wizard)
      # bin/laia-wizard was collapsed into `bin/laia wizard` in Fase 4
      # of the wizard remake — single public entry point for the host CLI.
      cmd=("$bin/laia" "wizard")
      [[ -n "$OPT_CONFIG" ]] && cmd+=(--config "$OPT_CONFIG")
      $OPT_YES && cmd+=(--yes)
      [[ -n "$OPT_SOURCE" ]] && cmd+=(--mode clone)
      cmd+=("${PASSTHRU_ARGS[@]+"${PASSTHRU_ARGS[@]}"}")
      ;;
  esac

  log "About to exec:"
  log "  ${cmd[*]}"

  # We are ALREADY root at this point (resolve_user verified EUID=0).
  # In the previous version this function did `exec sudo -E -- …`, a
  # second sudo (root→root) that on Ubuntu 26+ silently swallows the
  # env *and* drops the controlling tty connection in some setups,
  # leaving the wizard with no input. We don't need a second sudo —
  # we just exec the command directly, preserving env explicitly so
  # the sub-scripts can resolve $SUDO_USER / $HOME correctly.
  export SUDO_USER="${SUDO_USER:-$LAIA_USER}"
  export LAIA_USER="$LAIA_USER"
  export LAIA_USER_HOME="$LAIA_USER_HOME"
  # Point HOME at the real user's home so the wizard's log file lands
  # at /home/$user/.cache/laia-wizard.log (not /root/.cache/).
  export HOME="$LAIA_USER_HOME"
  export LAIA_ROOT="$LAIA_DIR"

  # Only the interactive wizard should inherit /dev/tty. Headless install/clone
  # runs must not pass a controlling terminal down to LXD image builds: that
  # path previously let `lxc exec`/apt inherit terminal state and appear frozen
  # at "installing OS packages" on Ubuntu 26.04 arm64.
  if [[ "$OPT_MODE" == "wizard" && "$OPT_YES" != true && ! -t 0 && -r /dev/tty ]]; then
    log "Reopening /dev/tty for interactive input."
    exec "${cmd[@]}" </dev/tty
  elif [[ "$OPT_YES" == true || "$OPT_MODE" != "wizard" ]]; then
    exec "${cmd[@]}" </dev/null
  fi
  exec "${cmd[@]}"
}

# ─── Main ────────────────────────────────────────────────────────────────────
main() {
  install_signal_traps
  parse_args "$@"

  step "LAIA bootstrap — production server setup"
  echo "  $C_D(re-run with --help to see all options)$C_0"

  resolve_user
  chown_user_home
  collect_interactive_intent
  detect_os
  ensure_prereqs
  clone_or_update
  print_plan
  hand_off
}

main "$@"
