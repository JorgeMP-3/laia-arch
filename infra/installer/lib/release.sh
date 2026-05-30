# ─────────────────────────────────────────────────────────────────────────────
# release.sh — phases specific to laia-release and laia-rollback
#
# Reuses the install pipeline from install.sh (copy, venv, frontend, symlink,
# wrappers, systemd) and adds:
#
#   rel_preflight_src_tree     git repo + working tree status (--allow-dirty)
#   rel_run_tests              pytest + (optional) frontend smoke
#   rel_capture_active_units   snapshot of currently running services
#   rel_record_previous        write .previous file beside /opt/laia symlink
#   rel_load_previous          read it back
#   rel_restart_active         systemctl restart of captured units
#   rel_healthcheck            poll is-active with timeout
#   rel_rollback_symlink       flip /opt/laia to a given version
#   rel_prune                  remove old versions, keep current + last N
#
# Override behaviour (for tests):
#   - In inst_is_override_mode, all systemctl calls are no-ops and no units
#     are ever captured (REL_ACTIVE_UNITS stays empty).
#   - LAIA_FORCE_HEALTHCHECK_FAIL=1 forces rel_healthcheck to return nonzero,
#     exercising the auto-rollback path even with no real services.
# ─────────────────────────────────────────────────────────────────────────────

[[ -n "${LAIA_LIB_RELEASE_LOADED:-}" ]] && return 0
readonly LAIA_LIB_RELEASE_LOADED=1

# Known LAIA systemd units (kept in sync with systemd/*.service.tmpl filenames).
LAIA_KNOWN_UNITS=(
  laia-gateway
  laia-pathd
  agora-backend
  laia-ui-server
)

# Populated by rel_capture_active_units. Read by restart/healthcheck.
REL_ACTIVE_UNITS=()
REL_PREV_VERSION=""

# ─── C.1: dev-tree pre-flight ──────────────────────────────────────────────
rel_ensure_safe_directory() {
  if ! is_root && [[ "${LAIA_TEST_FORCE_ROOT_SAFE_DIRECTORY:-}" != "1" ]]; then
    return 0
  fi

  local repo
  repo="$(readlink -f "$OPT_SRC")"
  if git config --global --get-all safe.directory 2>/dev/null | grep -Fxq "$repo"; then
    log_info "Git safe.directory already registered: $repo"
    return 0
  fi

  git config --global --add safe.directory "$repo" \
    || die "Could not register git safe.directory: $repo"
  log_info "Registered git safe.directory: $repo"
}

rel_preflight_src_tree() {
  log_step "Pre-flight: dev tree"

  [[ -d "$OPT_SRC" ]] || die "Source tree does not exist: $OPT_SRC"
  rel_ensure_safe_directory
  git -C "$OPT_SRC" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || die "Source tree is not a git repo: $OPT_SRC (release requires a git tree)"

  log_info "Source tree: $OPT_SRC"

  if ! git -C "$OPT_SRC" diff --quiet HEAD -- 2>/dev/null \
     || ! git -C "$OPT_SRC" diff --cached --quiet 2>/dev/null; then
    if [[ "$OPT_ALLOW_DIRTY" == true ]]; then
      log_warn "Working tree has uncommitted changes — continuing (--allow-dirty)"
    else
      die "Working tree is dirty. Commit/stash changes or pass --allow-dirty."
    fi
  else
    log_success "Working tree is clean"
  fi
}

# ─── C.1: smoke tests ──────────────────────────────────────────────────────
rel_run_tests() {
  if [[ "$OPT_SKIP_TESTS" == true ]]; then
    log_step "Tests (SKIPPED — --skip-tests)"
    return 0
  fi

  log_step "Smoke tests"

  # Bash installer self-tests live in tests/installer/ — fast, no network.
  local installer_tests="$OPT_SRC/tests/installer"
  if [[ -d "$installer_tests" ]]; then
    local t
    for t in "$installer_tests"/test_flags.sh "$installer_tests"/test_lib_common.sh; do
      [[ -x "$t" ]] || continue
      log_info "  $(basename "$t")"
      if ! bash "$t" >/dev/null 2>&1; then
        die "Test failed: $t — fix or pass --skip-tests"
      fi
    done
    log_success "Installer self-tests pass"
  else
    log_warn "No tests/installer directory at $installer_tests — skipping"
  fi

  # We deliberately do NOT run pytest on .laia-core or services/agora-backend
  # here: those need venvs that might not exist on the build host yet, and the
  # release pipeline rebuilds them later. Project tests run in CI / on the dev
  # machine before tagging.
}

# ─── C.2: service capture / restart ────────────────────────────────────────
rel_capture_active_units() {
  REL_ACTIVE_UNITS=()
  if inst_is_override_mode; then
    log_info "Override mode: skipping systemctl probing"
    return 0
  fi
  command -v systemctl >/dev/null 2>&1 || {
    log_warn "systemctl not available — no services will be restarted"
    return 0
  }
  local u
  for u in "${LAIA_KNOWN_UNITS[@]}"; do
    if systemctl is-active --quiet "$u" 2>/dev/null; then
      REL_ACTIVE_UNITS+=("$u")
    fi
  done
  if [[ "${#REL_ACTIVE_UNITS[@]}" -eq 0 ]]; then
    log_info "No LAIA services currently active — nothing to restart"
  else
    log_info "Currently active: ${REL_ACTIVE_UNITS[*]}"
  fi
}

rel_restart_active() {
  if [[ "${#REL_ACTIVE_UNITS[@]}" -eq 0 ]]; then
    log_step "Restart (no services were active)"
    return 0
  fi
  log_step "Restarting services"
  local u rc
  for u in "${REL_ACTIVE_UNITS[@]}"; do
    log_info "  systemctl restart $u"
    if is_root; then
      systemctl restart "$u"; rc=$?
    else
      sudo systemctl restart "$u"; rc=$?
    fi
    if [[ "$rc" -ne 0 ]]; then
      log_warn "  $u failed to restart (exit $rc)"
    fi
  done
}

# ─── C.3: healthcheck ──────────────────────────────────────────────────────
# Returns 0 if all REL_ACTIVE_UNITS report active within the timeout, 1 otherwise.
# Honours LAIA_FORCE_HEALTHCHECK_FAIL for testing the auto-rollback path.
rel_healthcheck() {
  if [[ -n "${LAIA_FORCE_HEALTHCHECK_FAIL:-}" ]]; then
    log_step "Healthcheck"
    log_error "LAIA_FORCE_HEALTHCHECK_FAIL set — simulating failure"
    return 1
  fi
  if [[ "${#REL_ACTIVE_UNITS[@]}" -eq 0 ]]; then
    log_step "Healthcheck (no active units to check)"
    return 0
  fi
  log_step "Healthcheck"

  local retries="${LAIA_HEALTHCHECK_RETRIES:-20}"
  local wait="${LAIA_HEALTHCHECK_WAIT:-2}"
  local u i active failed=0
  for u in "${REL_ACTIVE_UNITS[@]}"; do
    active=false
    for ((i=0; i<retries; i++)); do
      if systemctl is-active --quiet "$u" 2>/dev/null; then
        active=true
        break
      fi
      sleep "$wait"
    done
    if [[ "$active" == true ]]; then
      log_success "  $u is active"
    else
      log_error   "  $u NOT active after $((retries * wait))s"
      failed=$((failed + 1))
    fi
  done
  [[ "$failed" -eq 0 ]]
}

# ─── Previous-version tracking ─────────────────────────────────────────────
# Writes the previous version string to ${INST_PREFIX}.previous so rollback
# can find it without scanning. Called AFTER a successful symlink switch.
rel_record_previous() {
  local prev="$1"
  [[ -n "$prev" ]] || return 0   # first install: nothing to record

  local file="${INST_PREFIX}.previous"
  if inst_is_override_mode; then
    printf '%s\n' "$prev" >"$file"
  else
    printf '%s\n' "$prev" | sudo tee "$file" >/dev/null
  fi
  log_info "Recorded previous version: $prev → $file"
}

# Loads the previous-version pointer, or empty if missing.
rel_load_previous() {
  local file="${INST_PREFIX}.previous"
  [[ -f "$file" ]] || return 0
  tr -d '[:space:]' <"$file"
}

# ─── Rollback symlink to a given version ───────────────────────────────────
# Sets INST_DEST and calls inst_switch_symlink. The caller must have INST_PREFIX
# already set (via inst_compute_paths or rel_setup_paths).
rel_rollback_symlink() {
  local target="$1"
  [[ "$target" =~ ^v ]] || target="v$target"
  local root
  root="$(inst_install_root)"
  INST_DEST="$root/laia-$target"

  [[ -d "$INST_DEST" ]] || die "Cannot roll back: $INST_DEST does not exist"

  log_step "Rolling back symlink → laia-$target"
  inst_switch_symlink
}

# ─── C.5: prune ────────────────────────────────────────────────────────────
# Removes installed versions, keeping the current one and the $OPT_KEEP newest
# others. The currently active version is NEVER deleted regardless of N.
rel_prune() {
  local keep="$OPT_KEEP" current root
  current="$(inst_current_version)"
  root="$(inst_install_root)"

  log_step "Pruning old versions (keeping current + last $keep)"

  local versions=() v
  while IFS= read -r v; do
    [[ -n "$v" ]] && versions+=("$v")
  done < <(inst_list_versions | sort -Vr)   # newest first

  if [[ "${#versions[@]}" -eq 0 ]]; then
    log_info "No installed versions found at $root — nothing to prune"
    return 0
  fi

  local kept=0 keep_set=" $current "
  for v in "${versions[@]}"; do
    [[ "$v" == "$current" ]] && continue
    if [[ "$kept" -lt "$keep" ]]; then
      keep_set+=" $v "
      kept=$((kept + 1))
    fi
  done

  local removed=0
  for v in "${versions[@]}"; do
    if [[ "$keep_set" != *" $v "* ]]; then
      log_info "  removing $root/laia-$v"
      if inst_is_override_mode; then
        rm -rf "$root/laia-$v"
      else
        sudo rm -rf "$root/laia-$v"
      fi
      removed=$((removed + 1))
    fi
  done

  if [[ "$removed" -eq 0 ]]; then
    log_info "Nothing to prune"
  else
    log_success "Pruned $removed old version(s)"
  fi
}

# ─── Summary ───────────────────────────────────────────────────────────────
rel_print_summary() {
  log_step "Release complete"
  printf '\n'
  printf '  %sNow active:%s        %s\n' "$C_BLD" "$C_RST" "$OPT_VERSION"
  if [[ -n "$REL_PREV_VERSION" ]]; then
    printf '  %sPrevious:%s          %s  (rollback: sudo laia-rollback)\n' \
      "$C_BLD" "$C_RST" "$REL_PREV_VERSION"
  else
    printf '  %sPrevious:%s          <none>\n' "$C_BLD" "$C_RST"
  fi
  printf '  %sInstall directory:%s %s\n' "$C_BLD" "$C_RST" "$INST_DEST"

  if [[ "${#REL_ACTIVE_UNITS[@]}" -gt 0 ]]; then
    printf '  %sRestarted:%s         %s\n' "$C_BLD" "$C_RST" \
      "${REL_ACTIVE_UNITS[*]}"
  fi
  printf '\n'
}

rollback_print_summary() {
  log_step "Rollback complete"
  printf '\n'
  printf '  %sNow active:%s   %s\n' "$C_BLD" "$C_RST" "$(inst_current_version)"
  if [[ "${#REL_ACTIVE_UNITS[@]}" -gt 0 ]]; then
    printf '  %sRestarted:%s    %s\n' "$C_BLD" "$C_RST" "${REL_ACTIVE_UNITS[*]}"
  fi
  printf '\n'
  printf '  %sNote:%s rollback only flips the symlink. If the bad release made\n' \
    "$C_YEL" "$C_RST"
  printf '         schema changes or wrote to %s, you may need to restore\n' "$DATA_DIR"
  printf '         from snapshot instead.\n'
  printf '\n'
}
