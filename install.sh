#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# LAIA bootstrap installer — production-grade entry point for a clean server
#
# Intended use, from a brand-new Ubuntu 22.04+ host (you SSH'd in as `jorge`
# or whoever will own LAIA on this machine):
#
#   # Interactive wizard (recommended for humans, asks everything):
#   curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-wizard/install.sh \
#     | sudo -E bash
#
#   # Headless clone of an existing LAIA host (CI / scripted):
#   curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-wizard/install.sh \
#     | sudo -E bash -s -- --mode clone --source laia-hermes@old.example.com --yes
#
#   # Headless fresh install:
#   curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-wizard/install.sh \
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
#   4. Hands off to bin/laia-wizard (interactive) or bin/laia-install /
#      bin/laia-clone (headless), depending on --mode.
#
# Anything destructive (apt-install, mkdir under $HOME, sudo write to /opt
# or /srv) is preceded by a one-shot summary the user must accept, unless
# --yes was passed.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ─── Defaults ────────────────────────────────────────────────────────────────
DEFAULT_REPO_URL="https://github.com/JorgeMP-3/laia-arch.git"
DEFAULT_BRANCH="feat/installer-wizard"   # switch to 'main' after the merge
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
                          Default: wizard (interactive TUI).
    --source user@host    Required when --mode=clone (the source server).
    --branch BRANCH       Git branch / tag to install from.
                          Default: $DEFAULT_BRANCH
    --laia-dir PATH       Where to clone the repo. Default: \$SUDO_USER's
                          \$HOME/LAIA, e.g. /home/jorge/LAIA.
    --config FILE         YAML/JSON config passed through to laia-wizard
                          for fully unattended runs.
    --yes, -y             Skip all confirmations (apt install, plan summary,
                          wizard prompts). Required for CI / curl|bash auto.
    --no-apt              Don't try to apt-install missing prereqs (assumes
                          they're already there; useful in containers).
    --                    Everything after this is passed verbatim to the
                          subcommand (bin/laia-install, bin/laia-clone,
                          bin/laia-wizard).
    -h, --help            Show this help.

ENVIRONMENT
    LAIA_REPO_URL         Git repo URL (default: $DEFAULT_REPO_URL).
    LAIA_BRANCH           Same as --branch.
    LAIA_GITHUB_TOKEN     GitHub token if the repo is private.

EXAMPLES
    # Most common: clone from an existing LAIA host onto this new server.
    curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/$DEFAULT_BRANCH/install.sh \\
      | sudo -E bash -s -- --mode clone --source laia-hermes@old-server --yes

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
        OPT_MODE="$2"; shift 2 ;;
      --source)
        [[ $# -ge 2 ]] || die "--source requires user@host"
        OPT_SOURCE="$2"; shift 2 ;;
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
  if [[ "$OPT_MODE" == "clone" && -z "$OPT_SOURCE" && -z "$OPT_CONFIG" ]]; then
    # Clone needs a source unless the wizard config provides one.
    die "--mode clone requires --source user@host (or --config FILE)"
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
    read -r -p "Proceed with apt install? [Y/n] " ans || ans=""
    case "${ans:-y}" in [nN]*) die "Aborted by user." ;; esac
  fi
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing[@]}"
  ok "Installed ${#missing[@]} packages."
}

# ─── Clone / update the repo ────────────────────────────────────────────────
clone_or_update() {
  step "LAIA source tree at $LAIA_DIR"
  if [[ -d "$LAIA_DIR/.git" ]]; then
    local current
    current="$(sudo -u "$LAIA_USER" git -C "$LAIA_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
    log "Existing repo found (branch: $current). Updating."
    sudo -u "$LAIA_USER" git -C "$LAIA_DIR" fetch --depth 1 origin "$LAIA_BRANCH"
    sudo -u "$LAIA_USER" git -C "$LAIA_DIR" checkout "$LAIA_BRANCH"
    sudo -u "$LAIA_USER" git -C "$LAIA_DIR" reset --hard "origin/$LAIA_BRANCH"
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
    sudo -u "$LAIA_USER" git -c "http.https://github.com/.extraheader=AUTHORIZATION: basic ${basic}" \
      clone --depth 1 --branch "$LAIA_BRANCH" "$LAIA_REPO_URL" "$LAIA_DIR"
  else
    sudo -u "$LAIA_USER" "${git_cmd[@]}"
  fi
  ok "Cloned."
}

# ─── Plan summary (shown before any destructive action other than apt) ──────
print_plan() {
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
    read -r -p "Continue? [Y/n] " ans || ans=""
    case "${ans:-y}" in [nN]*) die "Aborted by user." ;; esac
  fi
}

# ─── Sub-command handoff ─────────────────────────────────────────────────────
hand_off() {
  step "Running: $OPT_MODE"
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
      cmd=("$bin/laia-wizard")
      [[ -n "$OPT_CONFIG" ]] && cmd+=(--config "$OPT_CONFIG")
      $OPT_YES && cmd+=(--yes)
      [[ -n "$OPT_SOURCE" ]] && cmd+=(--mode clone)
      cmd+=("${PASSTHRU_ARGS[@]+"${PASSTHRU_ARGS[@]}"}")
      ;;
  esac

  log "Exec: ${cmd[*]}"
  # Preserve SUDO_USER so the subscripts can resolve $LAIA_USER properly.
  exec sudo -E -- "${cmd[@]}"
}

# ─── Main ────────────────────────────────────────────────────────────────────
main() {
  parse_args "$@"

  step "LAIA bootstrap — production server setup"
  echo "  $C_D(re-run with --help to see all options)$C_0"

  resolve_user
  detect_os
  ensure_prereqs
  clone_or_update
  print_plan
  hand_off
}

main "$@"
