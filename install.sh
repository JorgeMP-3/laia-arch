#!/usr/bin/env bash
# LAIA bootstrap installer.
#
# Intended entrypoint from a clean server:
#   curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/<branch>/install.sh \
#     | sudo -E bash -s -- install --yes
#
# Or install + clone in one shot:
#   curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/<branch>/install.sh \
#     | sudo -E bash -s -- clone --source user@old-host --yes

set -euo pipefail

DEFAULT_REPO_URL="https://github.com/JorgeMP-3/laia-arch.git"
DEFAULT_BRANCH="feat/installer-cloner-v2"

LAIA_REPO_URL="${LAIA_REPO_URL:-$DEFAULT_REPO_URL}"
LAIA_BRANCH="${LAIA_BRANCH:-$DEFAULT_BRANCH}"
LAIA_BOOTSTRAP_KEEP="${LAIA_BOOTSTRAP_KEEP:-0}"

usage() {
  cat <<'EOF'
LAIA bootstrap installer

USAGE
    sudo bash install.sh wizard                            # interactive (recommended)
    sudo bash install.sh install [laia-install options]   # headless install
    sudo bash install.sh clone --source user@host [opts]  # headless clone

ACTIONS
    wizard    Launches laia-wizard — the interactive TUI for install / clone
              / diagnose / reset / connectivity. Best for humans.
    install   Runs bin/laia-install directly (CI / scripts / power users).
    clone     Runs bin/laia-clone directly (CI / scripts / power users).

ENVIRONMENT
    LAIA_REPO_URL     Git repository URL to clone.
    LAIA_BRANCH       Git branch/tag to clone.
    LAIA_GITHUB_TOKEN GitHub token for private repositories.
    LAIA_BOOTSTRAP_KEEP=1 keeps the temporary checkout for debugging.

EXAMPLES
    # Interactive (wizard):
    curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-wizard/install.sh \
      | sudo bash -s -- wizard

    # Headless install:
    curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-wizard/install.sh \
      | sudo bash -s -- install --yes

    # Headless clone:
    curl -fsSL https://raw.githubusercontent.com/JorgeMP-3/laia-arch/feat/installer-wizard/install.sh \
      | sudo bash -s -- clone --source laia-hermes@old-host --yes
EOF
}

log() { printf '→ %s\n' "$*"; }
die() { printf '✗ %s\n' "$*" >&2; exit 1; }

ensure_root() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "Run through sudo: curl ... | sudo -E bash -s -- install"
}

ensure_prereqs() {
  local missing=()
  local cmd
  # sqlite3 is needed by clone-time admin reset (fact_reset_imported_admin_password)
  # and by clone_phase_h_enumerate_slugs. python3 is needed for pbkdf2 hashing.
  for cmd in git rsync python3 sqlite3; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done
  if [[ "${#missing[@]}" -eq 0 ]]; then
    return 0
  fi
  command -v apt-get >/dev/null 2>&1 || die "Missing commands: ${missing[*]} (install them and re-run)"
  log "Installing prerequisites: ${missing[*]}"
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing[@]}"
}

clone_repo() {
  LAIA_BOOTSTRAP_DIR="$(mktemp -d /tmp/laia-bootstrap.XXXXXX)"
  export LAIA_BOOTSTRAP_DIR
  log "Cloning $LAIA_REPO_URL ($LAIA_BRANCH)"
  if [[ -n "${LAIA_GITHUB_TOKEN:-${GITHUB_TOKEN:-}}" ]]; then
    local token="${LAIA_GITHUB_TOKEN:-${GITHUB_TOKEN:-}}"
    local basic
    basic="$(printf 'x-access-token:%s' "$token" | base64 | tr -d '\n')"
    git -c "http.https://github.com/.extraheader=AUTHORIZATION: basic ${basic}" \
      clone --depth 1 --branch "$LAIA_BRANCH" "$LAIA_REPO_URL" "$LAIA_BOOTSTRAP_DIR"
  else
    git clone --depth 1 --branch "$LAIA_BRANCH" "$LAIA_REPO_URL" "$LAIA_BOOTSTRAP_DIR"
  fi
}

cleanup() {
  if [[ "${LAIA_BOOTSTRAP_KEEP:-0}" == "1" ]]; then
    log "Keeping bootstrap checkout: ${LAIA_BOOTSTRAP_DIR:-}"
    return 0
  fi
  [[ -n "${LAIA_BOOTSTRAP_DIR:-}" && -d "$LAIA_BOOTSTRAP_DIR" ]] && rm -rf "$LAIA_BOOTSTRAP_DIR"
}

main() {
  local action="${1:-}"
  case "$action" in
    -h|--help|help|"")
      usage
      exit 0
      ;;
    install|clone|wizard)
      shift
      ;;
    *)
      usage >&2
      die "Unknown action: $action"
      ;;
  esac

  ensure_root
  ensure_prereqs
  clone_repo
  trap cleanup EXIT

  case "$action" in
    install)
      "$LAIA_BOOTSTRAP_DIR/bin/laia-install" --from-local "$LAIA_BOOTSTRAP_DIR" "$@"
      ;;
    clone)
      "$LAIA_BOOTSTRAP_DIR/bin/laia-clone" "$@"
      ;;
    wizard)
      "$LAIA_BOOTSTRAP_DIR/bin/laia-wizard" "$@"
      ;;
  esac
}

main "$@"
