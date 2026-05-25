# ─────────────────────────────────────────────────────────────────────────────
# factory.sh — factory-default seeders for laia-install
# ─────────────────────────────────────────────────────────────────────────────

[[ -n "${LAIA_LIB_FACTORY_LOADED:-}" ]] && return 0
readonly LAIA_LIB_FACTORY_LOADED=1

fact_write_file() {
  local path="$1" mode="$2" content="$3"
  if inst_is_override_mode; then
    mkdir -p "$(dirname "$path")"
    printf '%s\n' "$content" >"$path"
    chmod "$mode" "$path"
  else
    sudo -u "$LAIA_USER" mkdir -p "$(dirname "$path")"
    printf '%s\n' "$content" | sudo -u "$LAIA_USER" tee "$path" >/dev/null
    sudo -u "$LAIA_USER" chmod "$mode" "$path"
  fi
}

fact_copy_once() {
  local src="$1" dst="$2" mode="${3:-600}"
  if [[ -f "$dst" ]]; then
    log_info "Already exists: $dst"
    return 0
  fi
  [[ -f "$src" ]] || die "Template not found: $src"
  if inst_is_override_mode; then
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
    chmod "$mode" "$dst"
  else
    sudo -u "$LAIA_USER" mkdir -p "$(dirname "$dst")"
    sudo cp -a "$src" "$dst"
    sudo chown "$LAIA_USER:$(id -gn "$LAIA_USER")" "$dst" 2>/dev/null || true
    sudo -u "$LAIA_USER" chmod "$mode" "$dst"
  fi
  log_success "Seeded $(basename "$dst")"
}

fact_seed_cli_config() {
  log_step "Factory: CLI config"
  fact_copy_once "$LAIA_ROOT/.laia-core/cli-config.yaml.example" "$DATA_DIR/cli-config.yaml" 600
  fact_copy_once "$LAIA_ROOT/.laia-core/.env.example" "$DATA_DIR/.env" 600
}

fact_seed_authjson() {
  log_step "Factory: auth.json"
  local dst="$DATA_DIR/auth.json"
  if [[ -f "$dst" ]]; then
    log_info "Already exists: $dst"
    return 0
  fi

  if [[ -n "${OPT_AUTH_FILE:-}" ]]; then
    [[ -f "$OPT_AUTH_FILE" ]] || die "--auth-file does not exist: $OPT_AUTH_FILE"
    if inst_is_override_mode; then
      mkdir -p "$(dirname "$dst")"
      cp -a "$OPT_AUTH_FILE" "$dst"
      chmod 600 "$dst"
    else
      sudo -u "$LAIA_USER" mkdir -p "$(dirname "$dst")"
      sudo cp -a "$OPT_AUTH_FILE" "$dst"
      sudo chown "$LAIA_USER:$(id -gn "$LAIA_USER")" "$dst" 2>/dev/null || true
      sudo -u "$LAIA_USER" chmod 600 "$dst"
    fi
    log_success "Pre-staged auth.json"
    return 0
  fi

  fact_write_file "$dst" 600 '{"provider":"unset","instructions":"Configure via UI or '\''laia auth'\''"}'
  log_success "Created auth.json placeholder"
}

fact_random_password() {
  if command -v openssl >/dev/null 2>&1; then
    local raw
    raw="$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9')"
    printf '%s\n' "${raw:0:20}"
  else
    local raw
    raw="$(date +%s%N | sha256sum)"
    printf '%s\n' "${raw:0:20}"
  fi
}

fact_resolve_admin_creds() {
  FACT_ADMIN_USER="${OPT_ADMIN_USER:-${LAIA_ARCH_USERNAME:-}}"
  FACT_ADMIN_PASS="${OPT_ADMIN_PASS:-${LAIA_ARCH_PASSWORD:-}}"

  if [[ -z "$FACT_ADMIN_USER" ]]; then
    if [[ "${OPT_YES:-false}" == true || "${LAIA_NONINTERACTIVE:-false}" == true ]]; then
      FACT_ADMIN_USER="admin"
    else
      read -r -p "LAIA admin username [admin]: " FACT_ADMIN_USER
      FACT_ADMIN_USER="${FACT_ADMIN_USER:-admin}"
    fi
  fi

  if [[ -z "$FACT_ADMIN_PASS" ]]; then
    if [[ "${OPT_YES:-false}" == true || "${LAIA_NONINTERACTIVE:-false}" == true ]]; then
      FACT_ADMIN_PASS="$(fact_random_password)"
    else
      read -r -s -p "LAIA admin password: " FACT_ADMIN_PASS
      printf '\n'
      [[ -n "$FACT_ADMIN_PASS" ]] || die "Admin password cannot be empty"
    fi
  fi
  export FACT_ADMIN_USER FACT_ADMIN_PASS
}

fact_seed_admin_user() {
  log_step "Factory: LAIA admin user"
  fact_resolve_admin_creds

  local cred_file="$DATA_DIR/.admin-credentials"
  if [[ ! -f "$cred_file" ]]; then
    fact_write_file "$cred_file" 600 "username=$FACT_ADMIN_USER
password=$FACT_ADMIN_PASS"
    printf '\nLAIA admin credentials:\n'
    printf '  username: %s\n' "$FACT_ADMIN_USER"
    printf '  password: %s\n\n' "$FACT_ADMIN_PASS"
  else
    log_info "Admin credentials file already exists: $cred_file"
  fi

  if inst_is_override_mode && [[ -z "${LAIA_TEST_STUB_PATH:-}" ]]; then
    log_info "Override mode: skipping admin API seed"
    return 0
  fi

  local api="${AGORA_API:-http://127.0.0.1:8088}"
  local payload
  payload=$(printf '{"username":"%s","display_name":"%s","role":"agora_admin","password":"%s"}' \
    "$FACT_ADMIN_USER" "$FACT_ADMIN_USER" "$FACT_ADMIN_PASS")

  curl -sS -X POST "$api/api/users" \
    -H "Authorization: Bearer ${AGORA_TOKEN:-dev-admin-token}" \
    -H 'Content-Type: application/json' \
    -d "$payload" >/dev/null || log_warn "Admin API seed failed; credentials were still written"
}

fact_seed_base_skills() {
  log_step "Factory: base skills"
  if inst_is_override_mode || [[ -n "${LAIA_TEST_STUB_PATH:-}" ]]; then
    log_info "[stub] skipping fact_seed_base_skills"
    return 0
  fi
  local script="$LAIA_ROOT/infra/dev/seed-base-skills.sh"
  [[ -x "$script" || -f "$script" ]] || die "Missing seed script: $script"
  REPO_ROOT="$LAIA_ROOT" bash "$script" || die "seed-base-skills.sh failed"
}

fact_reset_imported_admin_password() {
  # After a clone-time rsync of /srv/laia/agora/agora.db, the admin's password
  # hash in `users` is unreachable (pbkdf2 one-way). Without action, rebuild-4
  # cannot log in to register agents. We mint a fresh password, hash it in
  # the same scheme the backend uses (security.py::hash_password), update the
  # DB directly via sqlite3, persist creds to $DATA_DIR/.admin-credentials,
  # and export AGORA_ADMIN_USERNAME / AGORA_ADMIN_PASSWORD so the rebuild-*
  # scripts pick them up via sudo -E.
  log_step "Factory: reset imported admin password"

  # Skip cleanly under test stubs (no real backend, no real DB to mutate).
  if [[ -n "${LAIA_TEST_STUB_PATH:-}" ]]; then
    log_info "[stub] skipping fact_reset_imported_admin_password"
    return 0
  fi

  local db
  db="${AGORA_DB_PATH:-${LAIA_AGORA_DIR_OVERRIDE:-/srv/laia/agora}/agora.db}"
  if [[ ! -f "$db" ]]; then
    log_warn "$db does not exist — nothing to reset (skipping)"
    return 0
  fi
  # In override mode (tests) without an explicit AGORA_DB_PATH or with a
  # placeholder DB, skip — fixtures provide their own real sqlite db where
  # the function is exercised in isolation.
  if inst_is_override_mode && [[ -z "${AGORA_DB_PATH:-}" ]]; then
    log_info "[override] skipping admin reset (no AGORA_DB_PATH set)"
    return 0
  fi
  if ! command -v sqlite3 >/dev/null 2>&1; then
    log_warn "sqlite3 not installed → cannot reset admin password automatically"
    log_warn "  → apt install sqlite3 and rerun:"
    log_warn "  →   sudo -E bash -c 'source $LAIA_ROOT/infra/installer/lib/factory.sh && fact_reset_imported_admin_password'"
    return 0
  fi

  # Schema sanity: refuse to UPDATE if the users table doesn't have the
  # columns we're about to mutate. A pre-pbkdf2 legacy DB or a corrupted
  # clone would otherwise hit `sqlite3 UPDATE failed` with a vague message;
  # we'd rather die clearly here so the operator knows the source DB is
  # incompatible.
  local users_cols
  users_cols="$(sqlite3 "$db" "PRAGMA table_info(users);" 2>/dev/null || true)"
  if [[ -z "$users_cols" ]]; then
    die "agora.db has no 'users' table or sqlite3 cannot read it. The imported DB is incompatible with this LAIA version." 6
  fi
  for required in username password; do
    if ! grep -qw "$required" <<<"$users_cols"; then
      die "agora.db 'users' table is missing required column '$required'. Source DB schema is incompatible with this LAIA version." 6
    fi
  done

  # Find the canonical agora admin (first row by id; usernames may vary by deployment).
  local admin
  admin="$(sqlite3 "$db" "select username from users where role='agora_admin' and coalesce(active,1)=1 order by id limit 1;" 2>/dev/null || true)"
  if [[ -z "$admin" ]]; then
    # Fall back to any active user if no role='agora_admin' is present (legacy).
    admin="$(sqlite3 "$db" "select username from users where coalesce(active,1)=1 order by id limit 1;" 2>/dev/null || true)"
  fi
  if [[ -z "$admin" ]]; then
    log_warn "No active user found in $db — cannot reset admin password"
    return 0
  fi
  log_info "Imported admin username: $admin"

  local new_pass
  new_pass="$(fact_random_password)"

  # Hash with the same algorithm as services/agora-backend/app/security.py:
  # $pbkdf2$<salt_hex>$<dk_hex>  with salt=16 random bytes, 600k iterations.
  local hash
  hash="$(python3 -c '
import hashlib, os, sys
pw = sys.argv[1]
salt = os.urandom(16)
dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 600_000)
print(f"$pbkdf2${salt.hex()}${dk.hex()}")
' "$new_pass")"
  [[ -n "$hash" && "$hash" == \$pbkdf2\$* ]] || die "Failed to generate pbkdf2 hash → check python3 availability"

  # Use a temp file for the SQL to avoid quoting the hash in shell.
  local sqlfile
  sqlfile="$(mktemp)"
  printf "UPDATE users SET password = '%s', updated_at = datetime('now') WHERE username = '%s';\n" \
    "$hash" "$admin" >"$sqlfile"
  if inst_is_override_mode; then
    sqlite3 "$db" <"$sqlfile" || { rm -f "$sqlfile"; die "sqlite3 UPDATE failed on $db"; }
  else
    sudo sqlite3 "$db" <"$sqlfile" || { rm -f "$sqlfile"; die "sqlite3 UPDATE failed on $db"; }
  fi
  rm -f "$sqlfile"

  # Persist creds where the operator can read them.
  local data_dir
  data_dir="${DATA_DIR:-${LAIA_HOME_OVERRIDE:-$LAIA_USER_HOME/$LAIA_DATA_DIR_NAME}}"
  mkdir -p "$data_dir" 2>/dev/null || true
  fact_write_file "$data_dir/.admin-credentials" 600 "username=$admin
password=$new_pass
note=Generated by clone admin reset on $(date -Iseconds)"

  # Export for rebuild-4-first-user.sh to pick up via sudo -E.
  export AGORA_ADMIN_USERNAME="$admin"
  export AGORA_ADMIN_PASSWORD="$new_pass"

  printf '\n%s%s═══════════════════════════════════════════════════════════════%s\n' "$C_YEL" "$C_BLD" "$C_RST"
  printf '%s LAIA admin credentials (RESET BY CLONE) %s\n' "$C_BLD" "$C_RST"
  printf '   username: %s\n' "$admin"
  printf '   password: %s\n' "$new_pass"
  printf '   stored at: %s/.admin-credentials (mode 600)\n' "$data_dir"
  printf '%s%s═══════════════════════════════════════════════════════════════%s\n\n' "$C_YEL" "$C_BLD" "$C_RST"

  log_success "Admin '$admin' password reset; creds persisted"
}

fact_persist_env_to_container() {
  log_step "Factory: AGORA environment"
  local env_host_file="${LAIA_AGORA_ENV_FILE_OVERRIDE:-/srv/laia/agora/.env}"
  local token="${AGORA_TELEGRAM_TOKEN:-${TELEGRAM_TOKEN:-}}"
  if [[ -z "$token" ]]; then
    log_info "No AGORA env secrets provided"
    return 0
  fi

  if inst_is_override_mode; then
    mkdir -p "$(dirname "$env_host_file")"
    grep -v '^AGORA_TELEGRAM_TOKEN=' "$env_host_file" >"$env_host_file.tmp" 2>/dev/null || true
    printf 'AGORA_TELEGRAM_TOKEN=%s\n' "$token" >>"$env_host_file.tmp"
    mv "$env_host_file.tmp" "$env_host_file"
    chmod 600 "$env_host_file"
  else
    sudo mkdir -p "$(dirname "$env_host_file")"
    sudo bash -c "
      tmp=\$(mktemp)
      if [[ -f '$env_host_file' ]]; then
        grep -v '^AGORA_TELEGRAM_TOKEN=' '$env_host_file' > \$tmp || true
      fi
      printf 'AGORA_TELEGRAM_TOKEN=%s\n' '$token' >> \$tmp
      mv \$tmp '$env_host_file'
      chmod 600 '$env_host_file'
    "
  fi
  log_success "AGORA env persisted"
}
