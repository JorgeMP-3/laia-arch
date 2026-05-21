# ─────────────────────────────────────────────────────────────────────────────
# bootstrap.sh — factory bootstrap helpers for laia-install / laia-clone
#
# These functions intentionally wrap the existing LXD rebuild scripts instead
# of reimplementing their internals. In installer tests they short-circuit when
# override mode or LAIA_TEST_STUB_PATH is active.
# ─────────────────────────────────────────────────────────────────────────────

[[ -n "${LAIA_LIB_BOOTSTRAP_LOADED:-}" ]] && return 0
readonly LAIA_LIB_BOOTSTRAP_LOADED=1

LAIA_HOST_ARCH=""

boot_is_stub_mode() {
  inst_is_override_mode || [[ -n "${LAIA_TEST_STUB_PATH:-}" ]]
}

boot_script_path() {
  local name="$1"
  printf '%s/infra/lxd/scripts/%s\n' "$LAIA_ROOT" "$name"
}

boot_detect_arch() {
  log_step "Bootstrap: host architecture"

  LAIA_HOST_ARCH="${LAIA_HOST_ARCH_OVERRIDE:-}"
  if [[ -z "$LAIA_HOST_ARCH" ]]; then
    command -v dpkg >/dev/null 2>&1 || die "dpkg not found; cannot detect host architecture"
    LAIA_HOST_ARCH="$(dpkg --print-architecture)"
  fi

  case "$LAIA_HOST_ARCH" in
    amd64|arm64) ;;
    *) die "Unsupported architecture: $LAIA_HOST_ARCH (supported: amd64, arm64)" ;;
  esac

  export LAIA_HOST_ARCH
  log_success "Host architecture: $LAIA_HOST_ARCH"
}

boot_check_lxd_installed() {
  log_step "Bootstrap: LXD"
  if boot_is_stub_mode; then
    log_info "[stub] skipping boot_check_lxd_installed"
    return 0
  fi

  if command -v lxc >/dev/null 2>&1 && lxc remote list >/dev/null 2>&1; then
    log_success "LXD is available"
    return 0
  fi

  if [[ "${OPT_INIT_LXD:-false}" == true || "${OPT_YES:-false}" == true ]]; then
    log_info "Installing and initializing LXD"
  elif confirm "LXD is not initialized. Install LXD now?" "y"; then
    log_info "Installing and initializing LXD"
  else
    die "LXD is required. Install it with: sudo snap install lxd && sudo lxd init --auto"
  fi

  if is_root; then
    snap install lxd || die "snap install lxd failed"
    lxd init --auto || die "lxd init --auto failed"
  else
    sudo snap install lxd || die "snap install lxd failed"
    sudo lxd init --auto || die "lxd init --auto failed"
  fi
  log_success "LXD initialized"
}

boot_init_defaults() {
  log_step "Bootstrap: LXD defaults"
  if boot_is_stub_mode; then
    log_info "[stub] skipping boot_init_defaults"
    return 0
  fi
  local script
  script="$(boot_script_path init-defaults.sh)"
  [[ -x "$script" || -f "$script" ]] || die "Missing bootstrap script: $script"
  bash "$script" || die "init-defaults.sh failed"
}

boot_build_images() {
  log_step "Bootstrap: LXD images"
  if boot_is_stub_mode; then
    log_info "[stub] skipping boot_build_images"
    return 0
  fi

  if lxc image list --format csv 2>/dev/null | grep -Eq '(^|,)(laia-agora-base|laia-agora)(,|$)'; then
    log_success "LAIA LXD images already present"
    return 0
  fi

  local script
  script="$(boot_script_path rebuild-2-images.sh)"
  [[ -x "$script" || -f "$script" ]] || die "Missing bootstrap script: $script"
  LAIA_ROOT="$LAIA_ROOT" bash "$script" || die "rebuild-2-images.sh failed"
}

boot_provision_agora() {
  log_step "Bootstrap: laia-agora container"
  if boot_is_stub_mode; then
    log_info "[stub] skipping boot_provision_agora"
    return 0
  fi

  if lxc info laia-agora >/dev/null 2>&1; then
    log_success "Container laia-agora already exists"
    if ! lxc config device show laia-agora 2>/dev/null | grep -q '^agora-data:'; then
      local data_dir="${LAIA_AGORA_DATA_DIR_OVERRIDE:-/srv/laia/agora}"
      mkdir -p "$data_dir"
      lxc config device add laia-agora agora-data disk source="$data_dir" path=/opt/agora/data \
        || log_warn "Could not add agora-data bind mount; continuing"
    fi
    return 0
  fi

  local script
  script="$(boot_script_path rebuild-3-provision-agora.sh)"
  [[ -x "$script" || -f "$script" ]] || die "Missing bootstrap script: $script"
  LAIA_ROOT="$LAIA_ROOT" bash "$script" || die "rebuild-3-provision-agora.sh failed"
}

boot_wait_for_agora_health() {
  log_step "Bootstrap: AGORA health"
  if boot_is_stub_mode; then
    log_info "[stub] skipping boot_wait_for_agora_health"
    return 0
  fi

  local url="${LAIA_AGORA_HEALTH_URL:-http://127.0.0.1:8088/api/health}"
  local timeout="${LAIA_AGORA_HEALTH_TIMEOUT:-60}"
  local i
  for ((i = 0; i < timeout; i++)); do
    if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
      log_success "$url responds"
      return 0
    fi
    sleep 1
  done
  die "AGORA health endpoint did not respond after ${timeout}s: $url"
}
