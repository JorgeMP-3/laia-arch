# ─────────────────────────────────────────────────────────────────────────────
# install.sh — orchestration helpers for laia-install and laia-release
#
# Each function below is a single phase of the install pipeline. Functions
# operate on these globals (set by laia-install):
#
#   OPT_FROM_LOCAL       Source tree path (e.g. ~/.laia or /tmp/laia-build)
#   OPT_VERSION          Resolved version (e.g. v0.1.0)
#   OPT_NO_SYSTEMD       Skip systemd unit installation
#   OPT_SKIP_PIP         Skip `pip install` inside the venv
#   OPT_SKIP_FRONTEND    Skip frontend build/copy
#   OPT_FORCE            Allow overwriting an existing version dir
#
# And these computed paths:
#
#   INST_DEST            /opt/laia-vX.Y.Z  (or override under tmpdir)
#   INST_PREFIX          /opt/laia         (or override under tmpdir)
#   INST_BIN_DIR         /usr/local/bin    (or override)
#   DATA_DIR             $LAIA_USER_HOME/LAIA-ARCH (or override)
#   SYSTEMD_DIR          /etc/systemd/system (or override)
#
# Env overrides (used by tests to redirect to a tmpdir):
#   LAIA_INSTALL_ROOT_OVERRIDE   instead of /opt
#   LAIA_BIN_DIR_OVERRIDE        instead of /usr/local/bin
#   LAIA_HOME_OVERRIDE           instead of $LAIA_USER_HOME/LAIA-ARCH
#   LAIA_SYSTEMD_DIR_OVERRIDE    instead of /etc/systemd/system
# ─────────────────────────────────────────────────────────────────────────────

[[ -n "${LAIA_LIB_INSTALL_LOADED:-}" ]] && return 0
readonly LAIA_LIB_INSTALL_LOADED=1

# ─── Globals (set by laia-install after parse_args) ─────────────────────────
INST_DEST=""
INST_PREFIX=""
INST_BIN_DIR=""
DATA_DIR=""
SYSTEMD_DIR=""
LAIA_HOST_ARCH=""

# inst_compute_paths — fills the INST_* globals based on overrides or defaults.
# Call once after OPT_VERSION is resolved.
inst_compute_paths() {
  local install_root="${LAIA_INSTALL_ROOT_OVERRIDE:-$LAIA_INSTALL_ROOT}"
  local v="$OPT_VERSION"
  [[ "$v" =~ ^v ]] || v="v$v"
  INST_DEST="${install_root}/laia-${v}"
  INST_PREFIX="${install_root}/laia"

  INST_BIN_DIR="${LAIA_BIN_DIR_OVERRIDE:-$LAIA_USR_LOCAL_BIN}"
  DATA_DIR="${LAIA_HOME_OVERRIDE:-$LAIA_USER_HOME/$LAIA_DATA_DIR_NAME}"
  SYSTEMD_DIR="${LAIA_SYSTEMD_DIR_OVERRIDE:-/etc/systemd/system}"
}

# inst_is_override_mode — true when any test override is set.
# Tests run as non-root in a tmpdir; skip require_root in that mode.
inst_is_override_mode() {
  [[ -n "${LAIA_INSTALL_ROOT_OVERRIDE:-}" \
     || -n "${LAIA_BIN_DIR_OVERRIDE:-}" \
     || -n "${LAIA_HOME_OVERRIDE:-}" \
     || -n "${LAIA_SYSTEMD_DIR_OVERRIDE:-}" \
     || -n "${LAIA_USERS_DIR_OVERRIDE:-}" \
     || -n "${LAIA_TOOLS_HOME_OVERRIDE:-}" ]]
}

# inst_install_root — install root respecting LAIA_INSTALL_ROOT_OVERRIDE.
# Use this instead of $LAIA_INSTALL_ROOT directly when paths must work in tests.
inst_install_root() {
  printf '%s\n' "${LAIA_INSTALL_ROOT_OVERRIDE:-$LAIA_INSTALL_ROOT}"
}

# inst_install_prefix — the symlink path, override-aware.
inst_install_prefix() {
  printf '%s/laia\n' "$(inst_install_root)"
}

# inst_current_version — version string the symlink points to, or empty.
# Override-aware variant of version.sh's current_installed_version().
# Tolerates either absolute or relative symlink targets.
inst_current_version() {
  local prefix
  prefix="$(inst_install_prefix)"
  [[ -L "$prefix" ]] || return 0
  local target
  target="$(basename "$(readlink "$prefix")")"
  printf '%s\n' "${target#laia-}"
}

# inst_list_versions — every installed version, sorted ascending.
inst_list_versions() {
  local root d v
  root="$(inst_install_root)"
  for d in "$root"/laia-v*/; do
    [[ -d "$d" ]] || continue
    v="${d%/}"; v="${v##*/laia-}"
    printf '%s\n' "$v"
  done | sort -V
}

# ─── B.1: Pre-flight ────────────────────────────────────────────────────────
inst_preflight() {
  log_step "Pre-flight checks"

  detect_os
  log_info "OS:           $LAIA_OS ($LAIA_DISTRO)"

  if [[ "$LAIA_OS" != "linux" ]]; then
    die "LAIA only supports Linux (detected: $LAIA_OS)"
  fi
  if [[ "$LAIA_DISTRO" != "debian" ]]; then
    log_warn "Untested distro: $LAIA_DISTRO. Continuing anyway."
  fi

  # Ubuntu version (only enforced on Ubuntu)
  if [[ -f /etc/os-release ]]; then
    # shellcheck source=/dev/null
    . /etc/os-release
    if [[ "${ID:-}" == "ubuntu" ]]; then
      require_ubuntu_min 22.04
      log_info "Ubuntu:       ${VERSION_ID:-?}"
    fi
  fi

  require_kernel_min 5.15
  log_info "Kernel:       $(uname -r)"

  require_python_min 3.11
  log_info "Python:       $(python3 -V 2>&1 | awk '{print $2}')"

  LAIA_HOST_ARCH="${LAIA_HOST_ARCH_OVERRIDE:-}"
  if [[ -z "$LAIA_HOST_ARCH" ]]; then
    command -v dpkg >/dev/null 2>&1 || die "dpkg not found; cannot detect host architecture"
    LAIA_HOST_ARCH="$(dpkg --print-architecture)"
  fi
  case "$LAIA_HOST_ARCH" in
    amd64|arm64) log_info "Architecture: $LAIA_HOST_ARCH" ;;
    *) die "Unsupported architecture: $LAIA_HOST_ARCH (supported: amd64, arm64)" ;;
  esac
  export LAIA_HOST_ARCH

  # Disk space at install root
  local install_root="${LAIA_INSTALL_ROOT_OVERRIDE:-$LAIA_INSTALL_ROOT}"
  ensure_disk_free_gb "$install_root" 5   # minimal — full builds need more
  log_info "Disk free:    $(df -h "$install_root" 2>/dev/null | awk 'NR==2 {print $4}') at $install_root"

  # Required commands
  local missing
  missing="$(missing_cmds rsync git python3)"
  if [[ -n "$missing" ]]; then
    die "Missing required commands: $missing — install them and re-run"
  fi
  log_success "All required commands available"

  # Sudo (skipped in override/test mode and in --dry-run)
  if ! inst_is_override_mode && [[ "${OPT_DRY_RUN:-false}" != true ]]; then
    require_root "laia-install writes to /opt and /usr/local/bin"
  fi
}

# ─── B.2: Source resolution ─────────────────────────────────────────────────
inst_resolve_source() {
  log_step "Resolving source tree"

  if [[ -z "$OPT_FROM_LOCAL" ]]; then
    # TODO Fase B.next: git clone https://github.com/JorgeMP-3/laia-arch
    # For now, require --from-local explicitly.
    die "Remote install (from GitHub) not yet implemented. Use --from-local PATH."
  fi

  [[ -d "$OPT_FROM_LOCAL" ]] || die "Source directory does not exist: $OPT_FROM_LOCAL"
  [[ -d "$OPT_FROM_LOCAL/.laia-core" || -d "$OPT_FROM_LOCAL/.git" ]] \
    || die "Does not look like a LAIA source tree: $OPT_FROM_LOCAL"

  log_success "Source tree:  $OPT_FROM_LOCAL"
}

inst_resolve_version() {
  if [[ -z "$OPT_VERSION" ]]; then
    if ! OPT_VERSION="$(detect_version "$OPT_FROM_LOCAL" 2>/dev/null)"; then
      die "Cannot detect version. Either tag HEAD (git tag vX.Y.Z), add a VERSION file, or pass --version vX.Y.Z"
    fi
  else
    # Normalize
    [[ "$OPT_VERSION" =~ ^v ]] || OPT_VERSION="v$OPT_VERSION"
  fi
  log_success "Version:      $OPT_VERSION"
}

inst_resolve_paths() {
  inst_compute_paths
  log_info "Will install to:   $INST_DEST"
  log_info "Symlink to update: $INST_PREFIX → $(basename "$INST_DEST")"
  log_info "Wrappers in:       $INST_BIN_DIR"
  log_info "Data dir:          $DATA_DIR"
  if [[ "$OPT_NO_SYSTEMD" != true ]]; then
    log_info "Systemd units in:  $SYSTEMD_DIR"
  fi
}

inst_check_existing_version() {
  if [[ -d "$INST_DEST" ]]; then
    if [[ "$OPT_FORCE" != true ]]; then
      die "Version already installed at $INST_DEST. Re-run with --force to overwrite."
    fi
    log_warn "--force given: will overwrite existing $INST_DEST"
  fi
}

# ─── B.3: Build to /opt ─────────────────────────────────────────────────────
# Excludes: vcs metadata, virtualenvs (we rebuild them), node_modules, caches,
# test artifacts, and historical archives. Tuned for the LAIA repo layout.
_inst_rsync_excludes() {
  cat <<'EOF'
.git/
.gitignore
.gitmodules
.github/
.pytest_cache/
__pycache__/
*.pyc
*.pyo
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
node_modules/
.turbo/
.next/
.cache/
.test-tmp/
.vscode/
.idea/
.DS_Store
*.swp
*.swo
*.bak
*.bak.*
*.lock
gateway.pid
.venv/
.venv-*/
venv/
.envrc
# Heavy dev-only or local-only trees:
archived/
.plans/
.claude/
EOF
}

inst_copy_source_to_dest() {
  log_step "Copying source tree to $INST_DEST"

  local excludes_file
  excludes_file="$(mktemp)"
  _inst_rsync_excludes >"$excludes_file"

  # Remove existing dest (when --force) so old files don't linger.
  if [[ -d "$INST_DEST" ]]; then
    log_info "Removing previous $INST_DEST"
    if inst_is_override_mode; then
      rm -rf "$INST_DEST"
    else
      sudo rm -rf "$INST_DEST"
    fi
  fi

  local mkdir_cmd=(mkdir -p "$INST_DEST")
  local rsync_cmd=(rsync -a --info=stats1 --exclude-from="$excludes_file" \
                   "$OPT_FROM_LOCAL/" "$INST_DEST/")

  if inst_is_override_mode; then
    "${mkdir_cmd[@]}" || die "mkdir failed for $INST_DEST"
    "${rsync_cmd[@]}" >/dev/null || die "rsync failed"
  else
    sudo "${mkdir_cmd[@]}" || die "mkdir failed for $INST_DEST"
    sudo "${rsync_cmd[@]}" >/dev/null || die "rsync failed"
  fi

  rm -f "$excludes_file"

  # Stamp the VERSION file inside dest so consumers can read it.
  local version_file="$INST_DEST/VERSION"
  if inst_is_override_mode; then
    printf '%s\n' "$OPT_VERSION" >"$version_file"
  else
    printf '%s\n' "$OPT_VERSION" | sudo tee "$version_file" >/dev/null
  fi

  log_success "Tree copied"
}

# ─── B.4: Python venvs ──────────────────────────────────────────────────────
inst_create_venvs() {
  if [[ "$OPT_SKIP_PIP" == true ]]; then
    log_step "Python venvs (SKIPPED — --skip-pip)"
    return 0
  fi

  log_step "Creating Python venvs"

  # Two venvs: one for .laia-core (Hermes fork), one for agora-backend.
  # We pip-install each independently so they can have divergent deps.
  local venv_core="$INST_DEST/.laia-core/venv"
  local venv_agora="$INST_DEST/services/agora-backend/.venv"

  if [[ -d "$INST_DEST/.laia-core" ]]; then
    emit_json_event step_start install:pip-core "Python deps: core venv"
    _inst_create_venv_at "$venv_core" "core"
    _inst_pip_install_pkg "$venv_core" "$INST_DEST/.laia-core" ""
    emit_json_event step_done install:pip-core "Python deps: core ready"
  else
    log_warn "$INST_DEST/.laia-core not found, skipping core venv"
  fi

  if [[ -d "$INST_DEST/services/agora-backend" ]]; then
    emit_json_event step_start install:pip-agora "Python deps: agora-backend venv"
    _inst_create_venv_at "$venv_agora" "agora-backend"
    local req="$INST_DEST/services/agora-backend/requirements.txt"
    if [[ -f "$req" ]]; then
      _inst_pip_install_req "$venv_agora" "$req"
    else
      log_warn "No requirements.txt at $req, skipping pip install for agora-backend"
    fi
    emit_json_event step_done install:pip-agora "Python deps: agora-backend ready"
  else
    log_warn "$INST_DEST/services/agora-backend not found, skipping backend venv"
  fi
}

_inst_create_venv_at() {
  local venv="$1" label="$2"
  log_info "Creating venv ($label) at $venv"
  if inst_is_override_mode; then
    python3 -m venv "$venv" || die "venv creation failed at $venv"
  else
    sudo python3 -m venv "$venv" || die "venv creation failed at $venv"
  fi
  log_success "Venv ready ($label)"
}

_inst_pip_install_pkg() {
  local venv="$1" pkg_dir="$2" extras="${3:-}"
  local target="$pkg_dir"
  [[ -n "$extras" ]] && target="${pkg_dir}[${extras}]"
  log_info "pip install -e $target  (this can take several minutes)"
  emit_json_event step_start install:pip-upgrade "pip upgrade: $(basename "$pkg_dir")"
  if inst_is_override_mode; then
    _inst_run_pip "upgrade pip/wheel for $(basename "$pkg_dir")" \
      "$venv/bin/pip" install --progress-bar off --upgrade pip wheel || true
    emit_json_event step_start install:pip-package "pip install package: $(basename "$pkg_dir")"
    _inst_run_pip "install -e $target" \
      "$venv/bin/pip" install --progress-bar off -e "$target"
  else
    _inst_run_pip "upgrade pip/wheel for $(basename "$pkg_dir")" \
      sudo "$venv/bin/pip" install --progress-bar off --upgrade pip wheel || true
    emit_json_event step_start install:pip-package "pip install package: $(basename "$pkg_dir")"
    _inst_run_pip "install -e $target" \
      sudo "$venv/bin/pip" install --progress-bar off -e "$target"
  fi
  emit_json_event step_done install:pip-package "pip package installed: $(basename "$pkg_dir")"
  log_success "Installed $pkg_dir"
}

_inst_pip_install_req() {
  local venv="$1" req="$2"
  log_info "pip install -r $req"
  emit_json_event step_start install:pip-upgrade "pip upgrade: requirements"
  if inst_is_override_mode; then
    _inst_run_pip "upgrade pip/wheel for requirements" \
      "$venv/bin/pip" install --progress-bar off --upgrade pip wheel || true
    emit_json_event step_start install:pip-requirements "pip install requirements"
    _inst_run_pip "install -r $req" \
      "$venv/bin/pip" install --progress-bar off -r "$req"
  else
    _inst_run_pip "upgrade pip/wheel for requirements" \
      sudo "$venv/bin/pip" install --progress-bar off --upgrade pip wheel || true
    emit_json_event step_start install:pip-requirements "pip install requirements"
    _inst_run_pip "install -r $req" \
      sudo "$venv/bin/pip" install --progress-bar off -r "$req"
  fi
  emit_json_event step_done install:pip-requirements "pip requirements installed"
  log_success "Installed requirements"
}

_inst_run_pip() {
  local label="$1"
  shift
  local log_file rc
  log_file="$(mktemp)"
  log_info "  $*"
  set +e
  "$@" 2>&1 | tee "$log_file"
  rc="${PIPESTATUS[0]}"
  set -e
  if [[ "$rc" -ne 0 ]]; then
    log_error "pip failed during: $label (exit $rc)"
    log_error "Last pip output:"
    tail -40 "$log_file" >&2 || true
    rm -f "$log_file"
    die "pip failed during: $label"
  fi
  rm -f "$log_file"
}

# ─── B.4 (continued): Frontend build ────────────────────────────────────────
# Strategy: if laia-ui/ ships pre-built dist/, accept it as-is. Otherwise warn
# and continue — laia-release should produce the build before promoting.
inst_check_frontend() {
  if [[ "$OPT_SKIP_FRONTEND" == true ]]; then
    log_step "Frontend (SKIPPED — --skip-frontend)"
    return 0
  fi

  log_step "Frontend"

  if [[ ! -d "$INST_DEST/laia-ui" ]]; then
    log_info "No laia-ui/ in source tree — nothing to do"
    return 0
  fi

  local has_dist=false
  if find "$INST_DEST/laia-ui" -mindepth 2 -maxdepth 4 -type d -name dist 2>/dev/null \
       | head -1 | grep -q .; then
    has_dist=true
  fi

  if [[ "$has_dist" == true ]]; then
    log_success "Pre-built dist/ directories detected — leaving as-is"
  else
    log_warn "No frontend build artifacts found."
    log_warn "Run pnpm build in the source tree before laia-release, or pass --skip-frontend."
    log_warn "Continuing — services depending on laia-ui will fail until this is fixed."
  fi
}

# ─── B.3 (finalize): permissions ────────────────────────────────────────────
inst_finalize_permissions() {
  log_step "Finalizing permissions on $INST_DEST"
  if inst_is_override_mode; then
    chmod -R go-w "$INST_DEST" 2>/dev/null || true
    log_info "Override mode: skipped chown root:root"
  else
    sudo chown -R root:root "$INST_DEST"
    sudo chmod -R go-w "$INST_DEST"
  fi
  log_success "Permissions applied"
}

# ─── B.5: Symlink switch ────────────────────────────────────────────────────
# Atomic via `ln -sfn` to a temp name, then rename. ln -sfn alone is not
# fully atomic if the symlink already exists pointing elsewhere, so we use the
# rename trick: create symlink with a tmp name in the same dir, then rename
# over the canonical path.
inst_switch_symlink() {
  log_step "Switching $INST_PREFIX → $(basename "$INST_DEST")"

  local target dir tmp
  target="$(basename "$INST_DEST")"
  dir="$(dirname "$INST_PREFIX")"
  tmp="$INST_PREFIX.tmp.$$"

  if inst_is_override_mode; then
    ln -s "$target" "$tmp"
    mv -T "$tmp" "$INST_PREFIX"
  else
    sudo ln -s "$target" "$tmp"
    sudo mv -T "$tmp" "$INST_PREFIX"
  fi
  log_success "Symlink updated"
}

# ─── B.6: /usr/local/bin wrappers ───────────────────────────────────────────
INST_WRAPPER_BINARIES=(laia laia-install laia-clone laia-release laia-rollback)

inst_install_wrappers() {
  log_step "Installing wrappers in $INST_BIN_DIR"

  local b dst src
  if inst_is_override_mode; then
    mkdir -p "$INST_BIN_DIR"
  else
    sudo mkdir -p "$INST_BIN_DIR"
  fi

  for b in "${INST_WRAPPER_BINARIES[@]}"; do
    src="$INST_PREFIX/bin/$b"
    dst="$INST_BIN_DIR/$b"
    if inst_is_override_mode; then
      ln -sfn "$src" "$dst"
    else
      sudo ln -sfn "$src" "$dst"
    fi
    log_info "  $dst → $src"
  done
  log_success "Wrappers installed"
}

# ─── B.7: Data dir ──────────────────────────────────────────────────────────
inst_ensure_data_dir() {
  log_step "Ensuring data directory $DATA_DIR"
  if [[ -d "$DATA_DIR" ]]; then
    log_info "Already exists — leaving contents intact"
  else
    if inst_is_override_mode; then
      mkdir -p "$DATA_DIR"
      chmod 700 "$DATA_DIR"
    else
      sudo -u "$LAIA_USER" mkdir -p "$DATA_DIR"
      sudo -u "$LAIA_USER" chmod 700 "$DATA_DIR"
    fi
    log_success "Created $DATA_DIR (mode 700, owner $LAIA_USER)"
  fi
}

# ─── B.9: Systemd units ────────────────────────────────────────────────────
# See systemd.sh

# ─── Summary ───────────────────────────────────────────────────────────────
inst_print_summary() {
  log_step "Install complete"
  printf '\n'
  printf '  %sVersion installed:%s   %s\n' "$C_BLD" "$C_RST" "$OPT_VERSION"
  printf '  %sInstall directory:%s   %s\n' "$C_BLD" "$C_RST" "$INST_DEST"
  printf '  %sActive symlink:%s      %s → %s\n' "$C_BLD" "$C_RST" \
    "$INST_PREFIX" "$(basename "$INST_DEST")"
  printf '  %sData directory:%s      %s\n' "$C_BLD" "$C_RST" "$DATA_DIR"
  printf '\n'

  printf '  %sCommands available in %s:%s\n' "$C_BLD" "$INST_BIN_DIR" "$C_RST"
  local b
  for b in "${INST_WRAPPER_BINARIES[@]}"; do
    printf '    %s\n' "$INST_BIN_DIR/$b"
  done
  printf '\n'

  if [[ "$OPT_NO_SYSTEMD" != true ]]; then
    printf '  %sStart the core services with:%s\n' "$C_BLD" "$C_RST"
    printf '    sudo systemctl enable --now laia-gateway laia-pathd\n'
    printf '    sudo systemctl enable --now agora-backend laia-ui-server\n'
    printf '\n'
  fi

  printf '  %sNext steps:%s\n' "$C_BLD" "$C_RST"
  printf '    • Open a new shell (or `source ~/.bashrc`) so LAIA_HOME is exported\n'
  printf '    • Run `laia init` to bootstrap LAIA-ARCH\n'
  printf '    • Or `laia clone user@host` to migrate from an existing host\n'
  printf '\n'
}
