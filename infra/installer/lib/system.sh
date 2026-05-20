# ─────────────────────────────────────────────────────────────────────────────
# system.sh — OS / distro detection and prereq checks
#
# Exports (after detect_os):
#   LAIA_OS         : linux | macos | unknown
#   LAIA_DISTRO     : debian | fedora | arch | macos | unknown
#   LAIA_PKG_MGR    : apt-get | dnf | pacman | brew | "" (empty if unknown)
#
# Usage:
#   detect_os
#   require_ubuntu_min 22.04
#   ensure_disk_free_gb /opt 15
# ─────────────────────────────────────────────────────────────────────────────

[[ -n "${LAIA_LIB_SYSTEM_LOADED:-}" ]] && return 0
readonly LAIA_LIB_SYSTEM_LOADED=1

LAIA_OS=""
LAIA_DISTRO=""
LAIA_PKG_MGR=""

detect_os() {
  case "$(uname -s)" in
    Linux)
      LAIA_OS="linux"
      if   command -v apt-get >/dev/null 2>&1; then LAIA_DISTRO="debian"; LAIA_PKG_MGR="apt-get"
      elif command -v dnf     >/dev/null 2>&1; then LAIA_DISTRO="fedora"; LAIA_PKG_MGR="dnf"
      elif command -v pacman  >/dev/null 2>&1; then LAIA_DISTRO="arch";   LAIA_PKG_MGR="pacman"
      else LAIA_DISTRO="unknown"; LAIA_PKG_MGR=""
      fi
      ;;
    Darwin)
      LAIA_OS="macos"; LAIA_DISTRO="macos"
      LAIA_PKG_MGR="$(command -v brew >/dev/null 2>&1 && echo brew || echo '')"
      ;;
    *)
      LAIA_OS="unknown"; LAIA_DISTRO="unknown"; LAIA_PKG_MGR=""
      ;;
  esac
  export LAIA_OS LAIA_DISTRO LAIA_PKG_MGR
}

# require_ubuntu_min <min-version>  e.g. 22.04
require_ubuntu_min() {
  local min="$1"
  [[ -f /etc/os-release ]] || die "Cannot read /etc/os-release"
  # shellcheck source=/dev/null
  . /etc/os-release
  [[ "${ID:-}" == "ubuntu" ]] || die "This installer requires Ubuntu (found ID=$ID)"

  local cur="${VERSION_ID:-0}"
  # Lexicographic compare works for X.Y format (22.04 < 23.10 < 24.04)
  if [[ "$(printf '%s\n%s\n' "$min" "$cur" | sort -V | head -1)" != "$min" ]]; then
    die "Ubuntu $min or newer required (found $cur)"
  fi
}

# require_kernel_min <min-version>  e.g. 5.15
require_kernel_min() {
  local min="$1" cur
  cur="$(uname -r | cut -d- -f1)"
  if [[ "$(printf '%s\n%s\n' "$min" "$cur" | sort -V | head -1)" != "$min" ]]; then
    die "Kernel $min or newer required (found $cur)"
  fi
}

# require_python_min <min>  e.g. 3.11
require_python_min() {
  local min="$1"
  command -v python3 >/dev/null 2>&1 || die "python3 not found"
  local cur
  cur="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  if [[ "$(printf '%s\n%s\n' "$min" "$cur" | sort -V | head -1)" != "$min" ]]; then
    die "Python $min or newer required (found $cur)"
  fi
}

# ensure_disk_free_gb <path> <min_gb>
ensure_disk_free_gb() {
  local path="$1" min_gb="$2" avail_gb
  mkdir -p "$(dirname "$path")" 2>/dev/null || true
  avail_gb="$(df -BG --output=avail "$path" 2>/dev/null | tail -1 | tr -dc '0-9' || echo 0)"
  [[ -n "$avail_gb" && "$avail_gb" -ge "$min_gb" ]] || \
    die "Not enough disk space at $path: ${avail_gb:-0} GB free, ${min_gb} GB required"
}

# missing_cmds <cmd1> <cmd2> ... — prints (one per line) the commands not on PATH
missing_cmds() {
  local c
  for c in "$@"; do
    command -v "$c" >/dev/null 2>&1 || echo "$c"
  done
}
