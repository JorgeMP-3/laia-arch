# ─────────────────────────────────────────────────────────────────────────────
# clone.sh — phases for laia-clone (data-only path; LXD is Fase E)
#
# Two source modes:
#   (a) Remote:    OPT_SOURCE = "user@host"  (SSH, plus rsync via ssh)
#   (b) Local:     OPT_SOURCE_DIR = "/path"  (no SSH; useful for migrations on
#                                             the same machine and for tests)
#
# Both modes expect this layout on the source side:
#
#   <root>/
#     LAIA-ARCH/             # → local LAIA_HOME      (Phase 1)
#     users/                 # → /srv/laia/users      (Phase 3)
#     home/                  # → $HOME (per-CLI files) (Phase 4, --with-tools)
#
# For the SSH variant, <root> is implicit (each phase queries a different
# absolute path on the remote box). For the local variant the layout above
# is rooted at $OPT_SOURCE_DIR.
#
# Service handling reuses the helpers from release.sh:
#   rel_capture_active_units   → snapshot what's running before we touch state
#   rel_restart_active         → start the captured units again after sync
#
# Override behaviour (for tests):
#   LAIA_HOME_OVERRIDE         dest LAIA_HOME (also set by laia-install)
#   LAIA_USERS_DIR_OVERRIDE    dest /srv/laia/users
#   LAIA_TOOLS_HOME_OVERRIDE   dest $HOME for personal CLIs
#
# When any of these is set, inst_is_override_mode is true and we skip:
#   - sudo for /srv/laia/users writes
#   - systemctl stop/start
#   - smoke-test systemctl probes
# ─────────────────────────────────────────────────────────────────────────────

[[ -n "${LAIA_LIB_CLONE_LOADED:-}" ]] && return 0
readonly LAIA_LIB_CLONE_LOADED=1

readonly LAIA_USERS_DIR_DEFAULT="/srv/laia/users"
readonly LAIA_AGORA_DIR_DEFAULT="/srv/laia/agora"
readonly LAIA_ARCH_DIR_DEFAULT="/srv/laia/arch"
readonly LAIA_AGORA_HEALTH_URL="http://127.0.0.1:8088/api/health"

# Populated by clone_detect_paths.
REMOTE_HOME=""
REMOTE_LAIA_HOME=""
REMOTE_LAIA_VER=""
REMOTE_ARCH=""
CLONE_SSH_USE_PASSWORD=false

# ─── Path helpers (override-aware) ─────────────────────────────────────────
clone_dest_laia_home() {
  printf '%s\n' "${LAIA_HOME_OVERRIDE:-$LAIA_USER_HOME/$LAIA_DATA_DIR_NAME}"
}
clone_dest_users_dir() {
  printf '%s\n' "${LAIA_USERS_DIR_OVERRIDE:-$LAIA_USERS_DIR_DEFAULT}"
}
clone_dest_agora_dir() {
  printf '%s\n' "${LAIA_AGORA_DIR_OVERRIDE:-$LAIA_AGORA_DIR_DEFAULT}"
}
clone_dest_arch_dir() {
  printf '%s\n' "${LAIA_ARCH_DIR_OVERRIDE:-$LAIA_ARCH_DIR_DEFAULT}"
}
clone_dest_arch_creds_dir() {
  printf '%s\n' "${LAIA_ARCH_CREDS_DIR_OVERRIDE:-$LAIA_USER_HOME/.laia}"
}
clone_dest_tools_home() {
  printf '%s\n' "${LAIA_TOOLS_HOME_OVERRIDE:-$LAIA_USER_HOME}"
}

# True iff using --source-dir instead of user@host.
clone_is_local_source() {
  [[ -n "${OPT_SOURCE_DIR:-}" ]]
}

# clone_src_for <kind>  →  rsync-compatible source URL ending in '/'
clone_src_for() {
  local kind="$1"
  if clone_is_local_source; then
    case "$kind" in
      laia_home) printf '%s/LAIA-ARCH/\n' "$OPT_SOURCE_DIR" ;;
      agora)     printf '%s/agora/\n'      "$OPT_SOURCE_DIR" ;;
      users)     printf '%s/users/\n'     "$OPT_SOURCE_DIR" ;;
      home)      printf '%s/home/\n'      "$OPT_SOURCE_DIR" ;;
      arch)      printf '%s/arch/\n'      "$OPT_SOURCE_DIR" ;;
      legacy_laia) printf '%s/home/.laia/\n' "$OPT_SOURCE_DIR" ;;
    esac
  else
    case "$kind" in
      laia_home) printf '%s:%s/\n' "$OPT_SOURCE" "$REMOTE_LAIA_HOME" ;;
      agora)     printf '%s:%s/\n' "$OPT_SOURCE" "$LAIA_AGORA_DIR_DEFAULT" ;;
      users)     printf '%s:%s/\n' "$OPT_SOURCE" "$LAIA_USERS_DIR_DEFAULT" ;;
      home)      printf '%s:%s/\n' "$OPT_SOURCE" "$REMOTE_HOME" ;;
      arch)      printf '%s:%s/\n' "$OPT_SOURCE" "$LAIA_ARCH_DIR_DEFAULT" ;;
      legacy_laia) printf '%s:%s/.laia/\n' "$OPT_SOURCE" "$REMOTE_HOME" ;;
    esac
  fi
}

# clone_rsync_base — common rsync options array. Mode-aware for -e ssh.
# Sets a global array CLONE_RSYNC_OPTS the callers can extend.
clone_rsync_base_opts() {
  CLONE_RSYNC_OPTS=(-a --info=progress2,stats1,name1 --human-readable --outbuf=L)
  [[ -n "${OPT_BWLIMIT:-}" ]] && CLONE_RSYNC_OPTS+=(--bwlimit="$OPT_BWLIMIT")
  if ! clone_is_local_source; then
    CLONE_RSYNC_OPTS+=(-e "$(clone_ssh_transport)")
  fi
}

clone_rsync() {
  local label="$1"
  shift
  local log_file rc
  log_file="$(mktemp)"
  log_info "  rsync: $label"
  set +e
  if [[ "${1:-}" == "sudo" ]]; then
    "$@" 2>&1 | tee "$log_file"
  else
    rsync "$@" 2>&1 | tee "$log_file"
  fi
  rc="${PIPESTATUS[0]}"
  set -e
  if [[ "$rc" -ne 0 ]]; then
    log_error "rsync failed for $label (exit $rc)"
    log_error "Last rsync output:"
    tail -40 "$log_file" >&2 || true
    rm -f "$log_file"
    return "$rc"
  fi
  rm -f "$log_file"
  return 0
}

clone_stub_log() {
  [[ -n "${LAIA_TEST_STUB_LOG:-}" ]] && printf '%s\n' "$*" >>"$LAIA_TEST_STUB_LOG"
  return 0
}

clone_invoking_user_home() {
  [[ "$(id -u)" == "0" ]] || return 1

  local user="${SUDO_USER:-}"
  if [[ -z "$user" || "$user" == "root" ]]; then
    # Fallback: pick the first regular user (UID >= 1000) so SSH keys can be
    # reused even when SUDO_USER was not preserved (e.g., bare `sudo bash` no -E).
    user="$(getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 {print $1; exit}')"
    [[ -n "$user" ]] || return 1
  fi

  local entry
  entry="$(getent passwd "$user" 2>/dev/null || true)"
  [[ -n "$entry" ]] || return 1
  printf '%s\n' "$entry" | cut -d: -f6
}

clone_invoking_user() {
  # Symmetric to clone_invoking_user_home — returns the username (not the home).
  [[ "$(id -u)" == "0" ]] || return 1
  local user="${SUDO_USER:-}"
  if [[ -z "$user" || "$user" == "root" ]]; then
    user="$(getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 {print $1; exit}')"
  fi
  [[ -n "$user" ]] || return 1
  printf '%s\n' "$user"
}

clone_use_invoking_user_ssh() {
  local home
  home="$(clone_invoking_user_home)" || return 1
  [[ -d "$home/.ssh" ]]
}

clone_ssh_transport() {
  if [[ "${CLONE_SSH_USE_PASSWORD:-false}" == "true" ]]; then
    printf 'sshpass -e ssh -o BatchMode=no -o StrictHostKeyChecking=accept-new'
    return 0
  fi

  if clone_use_invoking_user_ssh; then
    local user
    user="$(clone_invoking_user)" || user="$SUDO_USER"
    printf 'sudo -H -u %s ssh -o BatchMode=yes' "$user"
  else
    printf 'ssh -o BatchMode=yes'
  fi
}

clone_ssh() {
  if [[ "${CLONE_SSH_USE_PASSWORD:-false}" == "true" ]]; then
    sshpass -e ssh -o BatchMode=no -o StrictHostKeyChecking=accept-new "$@"
    return $?
  fi

  if clone_use_invoking_user_ssh; then
    local user
    user="$(clone_invoking_user)" || user="$SUDO_USER"
    sudo -H -u "$user" ssh -o BatchMode=yes "$@"
  else
    ssh -o BatchMode=yes "$@"
  fi
}

clone_ensure_sshpass() {
  command -v sshpass >/dev/null 2>&1 && return 0

  if [[ "$(id -u)" != "0" ]]; then
    die "sshpass not installed. Install it or configure SSH keys first." 3
  fi
  if ! command -v apt-get >/dev/null 2>&1; then
    die "sshpass not installed and automatic install is only supported with apt-get" 3
  fi

  log_info "Installing sshpass for SSH password authentication"
  laia_run_interruptible apt-get update
  laia_run_interruptible env DEBIAN_FRONTEND=noninteractive apt-get install -y sshpass
}

clone_source_path_exists() {
  local path="$1"
  if clone_is_local_source; then
    [[ -e "$path" ]]
  else
    clone_ssh "$OPT_SOURCE" "test -e '$path'" >/dev/null 2>&1
  fi
}

# ─── D.1: pre-flight ───────────────────────────────────────────────────────
clone_preflight() {
  log_step "Pre-flight"

  command -v rsync >/dev/null 2>&1 || die "rsync not installed (apt install rsync)" 3

  if clone_is_local_source; then
    [[ -d "$OPT_SOURCE_DIR" ]] || die "Source directory not found: $OPT_SOURCE_DIR" 3
    [[ -d "$OPT_SOURCE_DIR/LAIA-ARCH" || -d "$OPT_SOURCE_DIR/agora" || -d "$OPT_SOURCE_DIR/users" || -d "$OPT_SOURCE_DIR/home" || -d "$OPT_SOURCE_DIR/arch" ]] \
      || die "Source dir layout invalid: expected one of LAIA-ARCH/, agora/, users/, home/, arch/" 3
    log_success "Source (local): $OPT_SOURCE_DIR"
  else
    command -v ssh >/dev/null 2>&1 || die "ssh not installed (apt install openssh-client)" 3
    if ! clone_ssh -o ConnectTimeout=5 "$OPT_SOURCE" true 2>/dev/null; then
      if [[ "${CLONE_SSH_USE_PASSWORD:-false}" == "true" ]]; then
        unset SSHPASS
        die "SSH to $OPT_SOURCE failed with the supplied password. Re-run the wizard and verify the credentials." 3
      fi
      die "SSH key auth to $OPT_SOURCE failed. Re-run the wizard and choose 'Password SSH' or 'Generate and copy key'. (Test: $(clone_ssh_transport) $OPT_SOURCE true)" 3
    fi
    log_success "SSH to $OPT_SOURCE works"
  fi

  # Local LAIA_HOME must exist — i.e. laia-install must have run.
  local dest_home
  dest_home="$(clone_dest_laia_home)"
  if [[ ! -d "$dest_home" ]]; then
    if inst_is_override_mode; then
      mkdir -p "$dest_home"
    else
      die "Destination $dest_home does not exist. Run laia-install first." 3
    fi
  fi
  log_info "Destination LAIA_HOME: $dest_home"
}

# ─── D.1: detect remote paths (or local equivalents) ───────────────────────
clone_detect_paths() {
  log_step "Detecting source paths"

  if clone_is_local_source; then
    REMOTE_HOME="$OPT_SOURCE_DIR/home"
    REMOTE_LAIA_HOME="$OPT_SOURCE_DIR/LAIA-ARCH"
    REMOTE_LAIA_VER="(local)"
    REMOTE_ARCH="$(dpkg --print-architecture 2>/dev/null || echo unknown)"
  else
    local out
    out="$(clone_ssh "$OPT_SOURCE" '
      printf "HOME=%s\n"      "$HOME"
      bash -lc "printf LAIA_HOME=%s\\\\n \"\${LAIA_HOME:-}\""
      printf "ARCH=%s\n"      "$(dpkg --print-architecture 2>/dev/null || echo unknown)"
      readlink /opt/laia 2>/dev/null || true
    ' 2>/dev/null)" || die "Remote path detection failed (SSH error)"

    REMOTE_HOME="$(printf '%s\n' "$out" | grep '^HOME='      | head -1 | cut -d= -f2-)"
    REMOTE_LAIA_HOME="$(printf '%s\n' "$out" | grep '^LAIA_HOME=' | head -1 | cut -d= -f2-)"
    REMOTE_ARCH="$(printf '%s\n' "$out" | grep '^ARCH='      | head -1 | cut -d= -f2-)"
    [[ -n "$REMOTE_LAIA_HOME" ]] || REMOTE_LAIA_HOME="$REMOTE_HOME/$LAIA_DATA_DIR_NAME"
    REMOTE_LAIA_VER="$(printf '%s\n' "$out" | grep '^laia-' | head -1 || true)"
    [[ -n "$REMOTE_LAIA_VER" ]] || REMOTE_LAIA_VER="<not installed>"
    [[ -n "$REMOTE_ARCH" ]] || REMOTE_ARCH="unknown"
  fi

  log_info "Source HOME:       $REMOTE_HOME"
  log_info "Source LAIA_HOME:  $REMOTE_LAIA_HOME"
  log_info "Source LAIA ver:   $REMOTE_LAIA_VER"
  log_info "Source arch:       $REMOTE_ARCH"
  log_info "Destination arch:  ${LAIA_HOST_ARCH:-unknown}"

  if [[ -n "${LAIA_HOST_ARCH:-}" && "$REMOTE_ARCH" != "unknown" && "$REMOTE_ARCH" != "$LAIA_HOST_ARCH" ]]; then
    log_warn "Cross-arch clone detected: $REMOTE_ARCH → $LAIA_HOST_ARCH"
    log_warn "  Containers are rebuilt locally on the destination; data is portable."
    log_warn "  If anything fails post-clone, the most likely cause is venv/wheel mismatch;"
    log_warn "  rerun with /opt/laia removed if needed."
  fi
}

# ─── Excludes per phase ────────────────────────────────────────────────────
_clone_excludes_laia_home() {
  cat <<'EOF'
cache/
logs/
*.log
*.lock
gateway.pid
.DS_Store
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
.venv-*/
node_modules/
.tmp/
*.swp
EOF
  if [[ "$OPT_WITH_MLX_MODELS" != true ]]; then
    # Heavy local models — 1.4 GB on the dev box. Re-downloadable.
    cat <<'EOF'
mlx-servers/
EOF
  fi
}

_clone_excludes_users() {
  cat <<'EOF'
__pycache__/
*.pyc
.DS_Store
*.lock
EOF
}

_clone_arch_legacy_dir_specs() {
  cat <<'EOF'
workspaces
memories
cron
sessions
atlas
platforms
plugins
sandboxes
orchestrator-runs
pastes
migration
whatsapp
EOF
}

_clone_arch_legacy_file_specs() {
  cat <<'EOF'
state.db
SOUL.md
config.yaml
EOF
}

# Tab-separated: path<TAB>exclude1<TAB>exclude2 ... (no trailing newline tabs)
# Per plan §3.2 step 6. Order matters only for readability.
_clone_tool_specs() {
  cat <<'EOF'
.claude.json
.claude/	shell-snapshots/	ide/	statsig/	logs/	*.log
.claude-cuenta2/	shell-snapshots/	ide/	statsig/
.codex/	log/	logs/	sessions/
.opencode/	bin/opencode
.copilot/
.gemini/
.gitconfig
.pm2/dump.pm2
.docker/config.json
EOF
}

# ─── D.1.5: service stop/start (reuses release.sh) ─────────────────────────
clone_stop_services() {
  if [[ "${#REL_ACTIVE_UNITS[@]}" -eq 0 ]]; then
    log_info "No active LAIA services — nothing to stop"
    return 0
  fi
  log_step "Stopping services: ${REL_ACTIVE_UNITS[*]}"
  local u
  for u in "${REL_ACTIVE_UNITS[@]}"; do
    log_info "  systemctl stop $u"
    if is_root; then
      systemctl stop "$u" || log_warn "  stop $u failed"
    else
      sudo systemctl stop "$u" || log_warn "  stop $u failed"
    fi
  done
}

# ─── D.2: Phase 1 — rsync LAIA_HOME ────────────────────────────────────────
clone_phase1_laia_home() {
  log_step "Phase 1: LAIA_HOME (data)"
  emit_json_event step_start clone:laia-home "Rsync LAIA_HOME"

  local src dst excludes_file
  src="$(clone_src_for laia_home)"
  dst="$(clone_dest_laia_home)/"

  excludes_file="$(mktemp)"
  _clone_excludes_laia_home >"$excludes_file"

  mkdir -p "$dst"

  clone_rsync_base_opts
  CLONE_RSYNC_OPTS+=(--exclude-from="$excludes_file")

  log_info "  rsync $src → $dst"
  if ! clone_rsync "LAIA_HOME" "${CLONE_RSYNC_OPTS[@]}" "$src" "$dst"; then
    rm -f "$excludes_file"
    die "Phase 1 rsync failed"
  fi

  rm -f "$excludes_file"
  emit_json_event step_done clone:laia-home "LAIA_HOME copied"
  log_success "Phase 1 complete"
}

# ─── D.3: Phase 3 — rsync /srv/laia/users ──────────────────────────────────
clone_phase3_users() {
  log_step "Phase 3: /srv/laia/users (PA-AGORA bind mounts)"
  emit_json_event step_start clone:users "Rsync /srv/laia/users"

  local src dst excludes_file
  src="$(clone_src_for users)"
  dst="$(clone_dest_users_dir)/"

  # If the source dir doesn't have users/ at all, treat as "nothing to clone"
  # (a brand-new origin may not have any agents yet).
  if clone_is_local_source && [[ ! -d "$OPT_SOURCE_DIR/users" ]]; then
    log_info "  Source has no users/ directory — skipping Phase 3"
    emit_json_event step_done clone:users "No users directory at source"
    return 0
  fi

  excludes_file="$(mktemp)"
  _clone_excludes_users >"$excludes_file"

  clone_rsync_base_opts
  CLONE_RSYNC_OPTS+=(--exclude-from="$excludes_file")

  if clone_is_local_source; then
    # Local: rsync directly with sudo for the write.
    if inst_is_override_mode; then
      mkdir -p "$dst"
      clone_rsync "users" "${CLONE_RSYNC_OPTS[@]}" "$src" "$dst" \
        || { rm -f "$excludes_file"; die "Phase 3 rsync failed"; }
    else
      sudo mkdir -p "$dst"
      clone_rsync "users" sudo rsync "${CLONE_RSYNC_OPTS[@]}" "$src" "$dst" \
        || { rm -f "$excludes_file"; die "Phase 3 rsync failed"; }
    fi
  else
    # Remote: stage to $HOME first (so SSH runs as $LAIA_USER with their keys),
    # then promote to /srv with sudo. Avoids root-needs-SSH-keys.
    local stage="$LAIA_USER_HOME/.laia-clone-stage/users"
    rm -rf "$stage" 2>/dev/null || true
    mkdir -p "$stage"

    log_info "  Staging in $stage"
    clone_rsync "users stage" "${CLONE_RSYNC_OPTS[@]}" "$src" "$stage/" \
      || { rm -f "$excludes_file"; die "Phase 3 stage rsync failed"; }

    log_info "  Promoting to $dst"
    if inst_is_override_mode; then
      mkdir -p "$dst"
      clone_rsync "users promote" -a --info=progress2,stats1,name1 --human-readable --outbuf=L "$stage/" "$dst"
    else
      sudo mkdir -p "$dst"
      clone_rsync "users promote" sudo rsync -a --info=progress2,stats1,name1 --human-readable --outbuf=L "$stage/" "$dst"
    fi
    rm -rf "$stage" 2>/dev/null || true
  fi

  rm -f "$excludes_file"
  emit_json_event step_done clone:users "Users data copied"
  log_success "Phase 3 complete"
}

clone_rsync_to_privileged_dest() {
  local src="$1" dst="$2" label="$3"
  shift 3
  local extra=("$@")

  clone_rsync_base_opts
  CLONE_RSYNC_OPTS+=(--numeric-ids "${extra[@]}")

  if clone_is_local_source; then
    [[ -e "${src%/}" ]] || { log_info "  Source missing for $label — skipping"; return 0; }
    if inst_is_override_mode; then
      mkdir -p "$dst"
      clone_rsync "$label" "${CLONE_RSYNC_OPTS[@]}" "$src" "$dst/" || die "$label rsync failed"
    else
      sudo mkdir -p "$dst"
      clone_rsync "$label" sudo rsync "${CLONE_RSYNC_OPTS[@]}" "$src" "$dst/" || die "$label rsync failed"
    fi
  else
    local stage="$LAIA_USER_HOME/.laia-clone-stage/$(basename "$dst")"
    rm -rf "$stage" 2>/dev/null || true
    mkdir -p "$stage"
    clone_rsync "$label stage" "${CLONE_RSYNC_OPTS[@]}" "$src" "$stage/" || die "$label stage rsync failed"
    if inst_is_override_mode; then
      mkdir -p "$dst"
      clone_rsync "$label promote" -a --numeric-ids --info=progress2,stats1,name1 --human-readable --outbuf=L "$stage/" "$dst/" || die "$label promote failed"
    else
      sudo mkdir -p "$dst"
      clone_rsync "$label promote" sudo rsync -a --numeric-ids --info=progress2,stats1,name1 --human-readable --outbuf=L "$stage/" "$dst/" || die "$label promote failed"
    fi
    rm -rf "$stage" 2>/dev/null || true
  fi
}

clone_phase_h_rsync_agora_data() {
  log_step "Phase H: /srv/laia/agora"
  emit_json_event step_start clone:rsync-agora "Rsync /srv/laia/agora"
  clone_rsync_to_privileged_dest "$(clone_src_for agora)" "$(clone_dest_agora_dir)" "agora data"
  emit_json_event step_done clone:rsync-agora "AGORA data copied"
  log_success "Phase H agora data complete"
}

clone_phase_h_rsync_users_data() {
  log_step "Phase H: /srv/laia/users"
  clone_phase3_users
}

clone_phase_h_rsync_arch_data() {
  log_step "Phase H: LAIA-ARCH operational data"
  emit_json_event step_start clone:rsync-arch "Rsync LAIA-ARCH operational data"
  local dst
  dst="$(clone_dest_arch_dir)"

  if clone_is_local_source && [[ -d "$OPT_SOURCE_DIR/arch" ]]; then
    clone_rsync_to_privileged_dest "$(clone_src_for arch)" "$dst" "arch data"
    clone_phase_h_rewrite_config_paths
    emit_json_event step_done clone:rsync-arch "ARCH data copied"
    return 0
  fi
  if ! clone_is_local_source && clone_source_path_exists "$LAIA_ARCH_DIR_DEFAULT"; then
    clone_rsync_to_privileged_dest "$(clone_src_for arch)" "$dst" "arch data"
    clone_phase_h_rewrite_config_paths
    emit_json_event step_done clone:rsync-arch "ARCH data copied"
    return 0
  fi
  if clone_is_local_source && [[ ! -d "$OPT_SOURCE_DIR/home/.laia" ]]; then
    log_info "  Source has no ARCH operational data — skipping"
    emit_json_event step_done clone:rsync-arch "No ARCH operational data at source"
    return 0
  fi

  if inst_is_override_mode; then
    mkdir -p "$dst"
  else
    sudo mkdir -p "$dst"
  fi

  local rel src_base src dst_path
  src_base="$(clone_src_for legacy_laia)"
  while IFS= read -r rel; do
    [[ -z "$rel" ]] && continue
    if clone_is_local_source && [[ ! -d "$OPT_SOURCE_DIR/home/.laia/$rel" ]]; then
      log_info "  skip ~/.laia/$rel (missing)"
      continue
    fi
    src="${src_base}${rel}/"
    dst_path="$dst/$rel"
    clone_rsync_to_privileged_dest "$src" "$dst_path" "arch data $rel"
  done < <(_clone_arch_legacy_dir_specs)

  while IFS= read -r rel; do
    [[ -z "$rel" ]] && continue
    if clone_is_local_source && [[ ! -f "$OPT_SOURCE_DIR/home/.laia/$rel" ]]; then
      log_info "  skip ~/.laia/$rel (missing)"
      continue
    fi
    clone_rsync_base_opts
    CLONE_RSYNC_OPTS+=(--numeric-ids)
    if clone_is_local_source; then
      mkdir -p "$dst"
      clone_rsync "arch file $rel" "${CLONE_RSYNC_OPTS[@]}" "$OPT_SOURCE_DIR/home/.laia/$rel" "$dst/$rel" || true
    else
      local stage="$LAIA_USER_HOME/.laia-clone-stage/arch-files"
      mkdir -p "$stage"
      clone_rsync "arch file $rel stage" "${CLONE_RSYNC_OPTS[@]}" "${src_base}${rel}" "$stage/$rel" || true
      if [[ -f "$stage/$rel" ]]; then
        if inst_is_override_mode; then
          mkdir -p "$dst"
          clone_rsync "arch file $rel promote" -a --info=progress2,stats1,name1 --human-readable --outbuf=L "$stage/$rel" "$dst/$rel"
        else
          sudo mkdir -p "$dst"
          clone_rsync "arch file $rel promote" sudo rsync -a --info=progress2,stats1,name1 --human-readable --outbuf=L "$stage/$rel" "$dst/$rel"
        fi
      fi
    fi
  done < <(_clone_arch_legacy_file_specs)

  clone_phase_h_rewrite_config_paths
  emit_json_event step_done clone:rsync-arch "ARCH data copied"
}

clone_phase_h_rewrite_config_paths() {
  local cfg
  cfg="$(clone_dest_arch_dir)/config.yaml"
  [[ -f "$cfg" ]] || return 0

  # Atlas-aware rewrite: only the three canonical anchors need to be set;
  # every other ${paths.X} alias derives from these. laia-pathd picks up the
  # change on next reload.
  #   - laia_root   → /opt/laia        (installed product tree)
  #   - laia_home   → ${LAIA_HOME:-/srv/laia/arch}  (operational data dir)
  #   - agora_data  → /srv/laia/agora/agora.db      (real bind-mounted DB)
  # Additionally, sweep any leftover /home/<user>/.laia/ literals to
  # /srv/laia/arch/ (covers other path keys the user may have customized).
  local sed_prog
  sed_prog='
    s#^([[:space:]]*laia_root:[[:space:]]*).*#\1/opt/laia#
    s#^([[:space:]]*laia_home:[[:space:]]*).*#\1${LAIA_HOME:-/srv/laia/arch}#
    s#^([[:space:]]*agora_data:[[:space:]]*).*#\1/srv/laia/agora/agora.db#
    s#~/\.laia/#/srv/laia/arch/#g
    s#/home/[^/[:space:]"]+/\.laia/#/srv/laia/arch/#g
    s#/home/[^/[:space:]"]+/\.laia([[:space:]"]|$)#/srv/laia/arch\1#g
    s#/home/[^/[:space:]"]+/LAIA/#/opt/laia/#g
    s#/home/[^/[:space:]"]+/LAIA([[:space:]"]|$)#/opt/laia\1#g
  '
  if inst_is_override_mode; then
    sed -i -E "$sed_prog" "$cfg"
  else
    sudo sed -i -E "$sed_prog" "$cfg"
  fi

  # If laia-pathd is running on the destination, ask it to reload so the
  # snapshot at ~/.laia/.env.paths picks up the new anchors.
  if command -v laia-path >/dev/null 2>&1; then
    laia-path reload >/dev/null 2>&1 || true
  fi

  log_success "Rewrote config.yaml paths (laia_root → /opt/laia, laia_home → /srv/laia/arch, agora_data → /srv/laia/agora/agora.db)"
}

clone_phase_h_rsync_arch_creds() {
  log_step "Phase H: LAIA-ARCH credentials"
  emit_json_event step_start clone:rsync-arch-creds "Rsync LAIA-ARCH credentials"
  local dst src_base rel src_file dst_file
  if clone_is_local_source && [[ ! -d "$OPT_SOURCE_DIR/home/.laia" ]]; then
    log_info "  Source has no ~/.laia credentials — skipping"
    emit_json_event step_done clone:rsync-arch-creds "No legacy ~/.laia credentials at source"
    return 0
  fi
  dst="$(clone_dest_arch_creds_dir)"
  src_base="$(clone_src_for legacy_laia)"
  mkdir -p "$dst"
  for rel in auth.json .env; do
    if clone_is_local_source && [[ ! -f "$OPT_SOURCE_DIR/home/.laia/$rel" ]]; then
      log_info "  skip ~/.laia/$rel (missing)"
      continue
    fi
    src_file="${src_base}${rel}"
    dst_file="$dst/$rel"
    clone_rsync_base_opts
    clone_rsync "arch credential $rel" "${CLONE_RSYNC_OPTS[@]}" "$src_file" "$dst_file" || true
    [[ -f "$dst_file" ]] && chmod 600 "$dst_file"
  done
  if [[ "${OPT_KEEP_SESSION:-false}" == true ]]; then
    rel="admin-session.json"
    if ! clone_is_local_source || [[ -f "$OPT_SOURCE_DIR/home/.laia/$rel" ]]; then
      clone_rsync_base_opts
      clone_rsync "arch credential $rel" "${CLONE_RSYNC_OPTS[@]}" "${src_base}${rel}" "$dst/$rel" || true
      [[ -f "$dst/$rel" ]] && chmod 600 "$dst/$rel"
    fi
  fi
  emit_json_event step_done clone:rsync-arch-creds "ARCH credentials copied"
}

clone_phase_h_enumerate_slugs() {
  log_step "Phase H: enumerate users"
  CLONE_PHASE_H_SLUGS=()
  local db
  db="$(clone_dest_agora_dir)/agora.db"
  if [[ -f "$db" ]] && command -v sqlite3 >/dev/null 2>&1; then
    local slug
    while IFS= read -r slug; do
      [[ -n "$slug" ]] && CLONE_PHASE_H_SLUGS+=("$slug")
    done < <(sqlite3 "$db" "select username from users where coalesce(active,1)=1 and role <> 'agora_admin' order by username;" 2>/dev/null || true)
  fi
  if [[ "${#CLONE_PHASE_H_SLUGS[@]}" -eq 0 ]]; then
    local users_dir d
    users_dir="$(clone_dest_users_dir)"
    for d in "$users_dir"/*; do
      [[ -d "$d" ]] || continue
      CLONE_PHASE_H_SLUGS+=("$(basename "$d")")
    done
  fi
  log_info "Slugs: ${CLONE_PHASE_H_SLUGS[*]:-<none>}"
}

clone_phase_h_rebuild_agora_container() {
  log_step "Phase H: rebuild laia-agora locally"
  emit_json_event step_start clone:rebuild-agora "Rebuild laia-agora"
  if inst_is_override_mode || [[ -n "${LAIA_TEST_STUB_PATH:-}" ]]; then
    clone_stub_log "rebuild-3-provision-agora.sh"
    log_info "[stub] skipping rebuild-3-provision-agora.sh"
    emit_json_event step_done clone:rebuild-agora "Rebuild laia-agora skipped in stub"
    return 0
  fi
  LAIA_ROOT="$LAIA_ROOT" bash "$LAIA_ROOT/infra/lxd/scripts/rebuild-3-provision-agora.sh"
  emit_json_event step_done clone:rebuild-agora "laia-agora rebuilt"
}

clone_phase_h_rebuild_agent_container() {
  local slug="$1"
  log_step "Phase H: rebuild agent-$slug locally"
  emit_json_event step_start "clone:rebuild-agent:$slug" "Rebuild agent-$slug"
  if inst_is_override_mode || [[ -n "${LAIA_TEST_STUB_PATH:-}" ]]; then
    clone_stub_log "rebuild-4-first-user.sh --slug $slug --existing-user-only"
    log_info "[stub] skipping rebuild-4-first-user.sh --slug $slug --existing-user-only"
    emit_json_event step_done "clone:rebuild-agent:$slug" "Rebuild agent-$slug skipped in stub"
    return 0
  fi
  LAIA_ROOT="$LAIA_ROOT" bash "$LAIA_ROOT/infra/lxd/scripts/rebuild-4-first-user.sh" \
    --slug "$slug" --existing-user-only
  emit_json_event step_done "clone:rebuild-agent:$slug" "agent-$slug rebuilt"
}

clone_phase_h_fix_uid_mapping() {
  log_step "Phase H: fix uid mappings"
  emit_json_event step_start clone:uid-map "Fix LXD uid mappings"
  if inst_is_override_mode || [[ -n "${LAIA_TEST_STUB_PATH:-}" ]]; then
    log_info "[stub] skipping uid mapping fix"
    emit_json_event step_done clone:uid-map "UID mapping skipped in stub"
    return 0
  fi
  # Probe the actual idmap base for the laia-agora container. If isolated or
  # not yet set, fall back to the LXD default unprivileged base (1000000).
  local base
  base="$(lxc config get laia-agora volatile.idmap.base 2>/dev/null || true)"
  if [[ -z "$base" || ! "$base" =~ ^[0-9]+$ ]]; then
    base=1000000
  fi
  log_info "  chown base: $base (LXD idmap)"
  sudo chown -R "$base:$base" "$(clone_dest_agora_dir)" "$(clone_dest_users_dir)" 2>/dev/null \
    || log_warn "  chown reported partial failures (may be safe; verify with 'lxc exec laia-agora -- ls /opt/agora/data')"
  emit_json_event step_done clone:uid-map "UID mappings fixed"
}

clone_phase_h_verify() {
  log_step "Phase H: verify"
  emit_json_event step_start clone:verify-live "Verify live containers and health"
  if inst_is_override_mode || [[ -n "${LAIA_TEST_STUB_PATH:-}" ]]; then
    log_info "[stub] skipping live verify"
    emit_json_event step_done clone:verify-live "Live verify skipped in stub"
    return 0
  fi
  lxc list
  curl -fsS "$LAIA_AGORA_HEALTH_URL" >/dev/null || die "AGORA health check failed"
  emit_json_event step_done clone:verify-live "Live verify passed"
  log_success "Phase H verify passed"
}

# ─── D.4: Phase 4 — --with-tools (personal CLIs) ───────────────────────────
clone_phase4_tools() {
  if [[ "$OPT_WITH_TOOLS" != true ]]; then
    log_step "Phase 4: tools (SKIPPED — pass --with-tools to include)"
    return 0
  fi

  log_step "Phase 4: personal CLI tools"

  local dst_home count=0
  dst_home="$(clone_dest_tools_home)"
  mkdir -p "$dst_home"

  while IFS= read -r spec; do
    [[ -z "$spec" ]] && continue
    local path excludes
    path="$(printf '%s\n' "$spec" | cut -f1)"
    excludes="$(printf '%s\n' "$spec" | cut -f2- -s)"
    _clone_rsync_tool "$path" "$excludes" "$dst_home" && count=$((count + 1)) || true
  done < <(_clone_tool_specs)

  log_success "Phase 4: processed $count tool specs"
}

# _clone_rsync_tool <rel> <tab-separated-excludes> <dest_home>
# Returns 0 if rsync ran, 1 if skipped (source missing).
_clone_rsync_tool() {
  local rel="$1" excludes="$2" dst_home="$3"

  local src exc_args=()
  if [[ -n "$excludes" ]]; then
    local e
    while IFS= read -r e; do
      [[ -n "$e" ]] && exc_args+=(--exclude="$e")
    done < <(printf '%s\n' "$excludes" | tr '\t' '\n')
  fi

  local src_full dst_target is_dir=false
  if clone_is_local_source; then
    src_full="$OPT_SOURCE_DIR/home/$rel"
    if [[ ! -e "$src_full" ]]; then
      log_info "  skip $rel (not at source)"
      return 1
    fi
    [[ -d "$src_full" ]] && is_dir=true
  else
    src_full="$OPT_SOURCE:$REMOTE_HOME/$rel"
    # We don't probe over SSH; rsync will report "no such file" gracefully.
    # Best-effort: assume dir if ends with /, else file. _clone_tool_specs
    # never has trailing /, so heuristic: presence of "." in last segment.
    if [[ "${rel##*/}" == .* && "${rel##*/}" != *.* ]]; then
      is_dir=true
    elif [[ "$rel" == */* && "${rel##*/}" != *.* ]]; then
      is_dir=true
    fi
  fi

  dst_target="$dst_home/$rel"
  if [[ "$is_dir" == true ]]; then
    mkdir -p "$dst_target"
    src_full="${src_full%/}/"      # ensure trailing slash for "contents into dst"
    dst_target="${dst_target%/}/"
  else
    mkdir -p "$(dirname "$dst_target")"
  fi

  local rsync_opts=(-a --info=progress2,stats1,name1 --human-readable --outbuf=L "${exc_args[@]}")
  clone_is_local_source || rsync_opts+=(-e "$(clone_ssh_transport)")

  log_info "  $rel"
  if clone_rsync "tool $rel" "${rsync_opts[@]}" "$src_full" "$dst_target"; then
    return 0
  else
    log_warn "    (rsync of $rel returned nonzero — likely missing at source)"
    return 1
  fi
}

# ─── D.5: Phase 5 — smoke test ─────────────────────────────────────────────
# Returns 0 on success, nonzero if any captured unit is inactive.
clone_phase5_smoke() {
  if inst_is_override_mode; then
    log_step "Phase 5: smoke test (override mode — skipped)"
    return 0
  fi

  log_step "Phase 5: smoke test"

  local failed=0 u
  if [[ "${#REL_ACTIVE_UNITS[@]}" -gt 0 ]] && command -v systemctl >/dev/null 2>&1; then
    for u in "${REL_ACTIVE_UNITS[@]}"; do
      if systemctl is-active --quiet "$u" 2>/dev/null; then
        log_success "  $u active"
      else
        log_error   "  $u NOT active"
        failed=$((failed + 1))
      fi
    done
  else
    log_info "  No services were stopped — nothing to re-verify"
  fi

  if command -v curl >/dev/null 2>&1; then
    if curl -fsS --max-time 5 "$LAIA_AGORA_HEALTH_URL" >/dev/null 2>&1; then
      log_success "  $LAIA_AGORA_HEALTH_URL responds"
    else
      log_warn    "  $LAIA_AGORA_HEALTH_URL not reachable (backend may be off)"
    fi
  fi

  [[ "$failed" -eq 0 ]]
}

# ─── Summary ───────────────────────────────────────────────────────────────
clone_print_summary() {
  log_step "Clone complete"
  printf '\n'
  printf '  %sSource:%s          %s\n' "$C_BLD" "$C_RST" "${OPT_SOURCE_DIR:-$OPT_SOURCE}"
  printf '  %sLAIA_HOME:%s       %s\n' "$C_BLD" "$C_RST" "$(clone_dest_laia_home)"
  printf '  %sAGORA data:%s      %s\n' "$C_BLD" "$C_RST" "$(clone_dest_agora_dir)"
  printf '  %sUsers dir:%s       %s\n' "$C_BLD" "$C_RST" "$(clone_dest_users_dir)"
  printf '  %sARCH data:%s       %s\n' "$C_BLD" "$C_RST" "$(clone_dest_arch_dir)"
  printf '  %sARCH creds:%s      %s\n' "$C_BLD" "$C_RST" "$(clone_dest_arch_creds_dir)"
  if [[ "$OPT_WITH_TOOLS" == true ]]; then
    printf '  %sTools (home):%s    %s\n' "$C_BLD" "$C_RST" "$(clone_dest_tools_home)"
  fi
  printf '\n'

  printf '  %sLXD containers:%s  rebuilt locally from destination images\n' "$C_BLD" "$C_RST"
  if [[ -n "$OPT_ONLY_AGENT" ]]; then
    printf '  %sOnly agent:%s      %s\n' "$C_BLD" "$C_RST" "$OPT_ONLY_AGENT"
  fi
  if [[ "$OPT_WITH_MLX_MODELS" == true ]]; then
    printf '  %sMLX models:%s      included (heavy — %s\n)' "$C_BLD" "$C_RST" "mlx-servers/"
  fi
  printf '\n'
}
