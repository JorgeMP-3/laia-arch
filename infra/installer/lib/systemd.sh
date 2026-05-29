# ─────────────────────────────────────────────────────────────────────────────
# systemd.sh — render systemd unit templates and install them
#
# Templates live in $LAIA_ROOT/infra/installer/systemd/*.tmpl (.service and
# .timer units) with placeholders: ${LAIA_USER}, ${LAIA_USER_HOME}, ${LAIA_HOME},
# ${LAIA_INSTALL_PREFIX}.
#
# We use `envsubst` with an explicit variable list — never bare envsubst —
# because the templates legitimately contain $-prefixed environment variables
# (HOME=$HOME, etc.) that we want to PRESERVE for systemd to expand at
# runtime, not substitute at install time.
# ─────────────────────────────────────────────────────────────────────────────

[[ -n "${LAIA_LIB_SYSTEMD_LOADED:-}" ]] && return 0
readonly LAIA_LIB_SYSTEMD_LOADED=1

readonly LAIA_SYSTEMD_VARS='${LAIA_USER} ${LAIA_USER_HOME} ${LAIA_HOME} ${LAIA_INSTALL_PREFIX}'

# systemd_template_dir — where the .tmpl files live in the source tree
systemd_template_dir() {
  printf '%s\n' "$LAIA_ROOT/infra/installer/systemd"
}

# systemd_list_templates — prints all unit-template basenames (without .tmpl).
# Globs *.tmpl so .service AND .timer (and any future unit type) are included.
systemd_list_templates() {
  local tdir f
  tdir="$(systemd_template_dir)"
  [[ -d "$tdir" ]] || return 0
  for f in "$tdir"/*.tmpl; do
    [[ -f "$f" ]] || continue
    printf '%s\n' "$(basename "$f" .tmpl)"
  done
}

# systemd_render <template_path> <output_path>  — envsubst with explicit vars
systemd_render() {
  local in="$1" out="$2"

  command -v envsubst >/dev/null 2>&1 || die "envsubst not installed (apt install gettext-base)"

  # We use /usr/bin/env so we can pass LAIA_INSTALL_PREFIX as a child-env var
  # even though version.sh declares it readonly in the current shell.
  env -i \
      PATH="$PATH" \
      LAIA_USER="$LAIA_USER" \
      LAIA_USER_HOME="$LAIA_USER_HOME" \
      LAIA_HOME="$DATA_DIR" \
      LAIA_INSTALL_PREFIX="$INST_PREFIX" \
      envsubst "$LAIA_SYSTEMD_VARS" <"$in" >"$out"
}

# systemd_install_all — render every template into $SYSTEMD_DIR
systemd_install_all() {
  if [[ "$OPT_NO_SYSTEMD" == true ]]; then
    log_step "Systemd units (SKIPPED — --no-systemd)"
    return 0
  fi

  log_step "Installing systemd units → $SYSTEMD_DIR"

  local tdir
  tdir="$(systemd_template_dir)"
  if [[ ! -d "$tdir" ]]; then
    log_warn "No template directory at $tdir — skipping"
    return 0
  fi

  if inst_is_override_mode; then
    mkdir -p "$SYSTEMD_DIR"
  else
    sudo mkdir -p "$SYSTEMD_DIR"
  fi

  local f base tmp_out
  for f in "$tdir"/*.tmpl; do
    [[ -f "$f" ]] || continue
    base="$(basename "$f" .tmpl)"
    tmp_out="$(mktemp)"
    systemd_render "$f" "$tmp_out"
    if inst_is_override_mode; then
      mv "$tmp_out" "$SYSTEMD_DIR/$base"
    else
      sudo mv "$tmp_out" "$SYSTEMD_DIR/$base"
      sudo chown root:root "$SYSTEMD_DIR/$base"
      sudo chmod 644 "$SYSTEMD_DIR/$base"
    fi
    log_info "  Installed $base"
  done

  # daemon-reload so systemd picks up the new units. Skip in override mode
  # (tests don't have a real systemd to talk to).
  if ! inst_is_override_mode; then
    if command -v systemctl >/dev/null 2>&1; then
      sudo systemctl daemon-reload || log_warn "systemctl daemon-reload failed (continuing)"
      log_success "systemctl daemon-reload completed"
    else
      log_warn "systemctl not available — units installed but not loaded"
    fi
  fi

  log_info "Units installed but NOT enabled or started — run:"
  log_info "  sudo systemctl enable --now laia-gateway laia-pathd"
}
