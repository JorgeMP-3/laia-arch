# ─────────────────────────────────────────────────────────────────────────────
# version.sh — version detection and path resolution
#
# Resolves the version of a LAIA source tree, using (in order):
#   1. explicit --version flag (via $1 to detect_version)
#   2. a VERSION file at the root of the tree
#   3. `git describe --tags --exact-match HEAD` (if the tree is a git repo)
#   4. failure: caller must pass --version explicitly
#
# Exports (after install_paths):
#   LAIA_INSTALL_ROOT      : /opt
#   LAIA_INSTALL_PREFIX    : /opt/laia                  (the symlink)
#   LAIA_INSTALL_VERSIONED : /opt/laia-vX.Y.Z           (the actual install dir)
#   LAIA_USR_LOCAL_BIN     : /usr/local/bin
# ─────────────────────────────────────────────────────────────────────────────

[[ -n "${LAIA_LIB_VERSION_LOADED:-}" ]] && return 0
readonly LAIA_LIB_VERSION_LOADED=1

# Standard locations on the host.
readonly LAIA_INSTALL_ROOT="/opt"
readonly LAIA_INSTALL_PREFIX="/opt/laia"
readonly LAIA_USR_LOCAL_BIN="/usr/local/bin"
readonly LAIA_DATA_DIR_NAME="LAIA-ARCH"

# detect_version <src_tree> [explicit_version]
#   Prints the resolved version (e.g. "v0.3.0") to stdout. Exits 1 on failure.
detect_version() {
  local src="$1" explicit="${2:-}"

  if [[ -n "$explicit" ]]; then
    # Normalize: accept both "v0.3.0" and "0.3.0", emit "v0.3.0"
    [[ "$explicit" =~ ^v ]] || explicit="v$explicit"
    printf '%s\n' "$explicit"
    return 0
  fi

  if [[ -f "$src/VERSION" ]]; then
    local v
    v="$(tr -d '[:space:]' <"$src/VERSION")"
    [[ "$v" =~ ^v ]] || v="v$v"
    printf '%s\n' "$v"
    return 0
  fi

  if [[ -d "$src/.git" ]]; then
    local tag
    if tag="$(git -C "$src" describe --tags --exact-match HEAD 2>/dev/null)"; then
      printf '%s\n' "$tag"
      return 0
    fi
  fi

  return 1
}

# install_path_for_version <version>  →  prints "/opt/laia-vX.Y.Z"
install_path_for_version() {
  local v="$1"
  [[ "$v" =~ ^v ]] || v="v$v"
  printf '%s/laia-%s\n' "$LAIA_INSTALL_ROOT" "$v"
}

# current_installed_version  →  prints the version that /opt/laia currently points to, or empty
current_installed_version() {
  [[ -L "$LAIA_INSTALL_PREFIX" ]] || return 0
  local target
  target="$(readlink "$LAIA_INSTALL_PREFIX")"
  printf '%s\n' "${target##*/laia-}"
}

# list_installed_versions  →  prints all versions currently in /opt/laia-v*, sorted
list_installed_versions() {
  local d v
  for d in "$LAIA_INSTALL_ROOT"/laia-v*/; do
    [[ -d "$d" ]] || continue
    v="${d%/}"; v="${v##*/laia-}"
    printf '%s\n' "$v"
  done | sort -V
}
