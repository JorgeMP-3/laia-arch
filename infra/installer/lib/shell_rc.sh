# ─────────────────────────────────────────────────────────────────────────────
# shell_rc.sh — manage idempotent blocks in user shell rc files
#
# Reads/writes a marker-delimited block in ~/.bashrc and ~/.zshrc:
#
#   # >>> laia >>>
#   export LAIA_HOME="/home/.../LAIA-ARCH"
#   # <<< laia <<<
#
# Re-running the install only updates the block — never duplicates it.
#
# Override path with LAIA_SHELL_RC_OVERRIDE (used by tests to redirect to a
# tmpdir file). When set, only that single file is updated.
# ─────────────────────────────────────────────────────────────────────────────

[[ -n "${LAIA_LIB_SHELL_RC_LOADED:-}" ]] && return 0
readonly LAIA_LIB_SHELL_RC_LOADED=1

readonly LAIA_RC_MARKER_BEGIN='# >>> laia >>>'
readonly LAIA_RC_MARKER_END='# <<< laia <<<'

# shell_rc_targets — prints the list of rc files to update
shell_rc_targets() {
  if [[ -n "${LAIA_SHELL_RC_OVERRIDE:-}" ]]; then
    printf '%s\n' "$LAIA_SHELL_RC_OVERRIDE"
    return
  fi
  local f
  for f in "$LAIA_USER_HOME/.bashrc" "$LAIA_USER_HOME/.zshrc"; do
    [[ -f "$f" ]] && printf '%s\n' "$f"
  done
}

# shell_rc_restore_meta <rc> [mode] — restore ownership/mode after a write
#
# We rewrite rc files via mktemp + mv. mv replaces the target with the tmp file,
# inheriting its metadata — root:root 0600 when the installer runs under sudo.
# These files live in the admin user's HOME; left root-owned, the next login
# shell cannot source them (the user loses their whole .bashrc, not just
# LAIA_HOME). Restore the admin user as owner and the original mode. Mirrors the
# HOME-file ownership pattern in factory.sh.
shell_rc_restore_meta() {
  local rc="$1" mode="${2:-644}"
  local owner="${LAIA_USER:-$(id -un)}"
  if [[ "$(id -u)" -eq 0 && "$owner" != "root" ]]; then
    chown "$owner:$(id -gn "$owner" 2>/dev/null || echo "$owner")" "$rc" 2>/dev/null || true
  fi
  chmod "$mode" "$rc" 2>/dev/null || true
}

# shell_rc_render_block <data_dir> — prints the block to insert
shell_rc_render_block() {
  local data_dir="$1"
  cat <<EOF
$LAIA_RC_MARKER_BEGIN
# Managed by laia-install — do not edit between these markers.
export LAIA_HOME="$data_dir"
$LAIA_RC_MARKER_END
EOF
}

# shell_rc_apply <data_dir> — writes/updates the LAIA block in each rc file
shell_rc_apply() {
  local data_dir="$1"
  local rc tmp new_block

  new_block="$(shell_rc_render_block "$data_dir")"

  while IFS= read -r rc; do
    [[ -z "$rc" ]] && continue
    mkdir -p "$(dirname "$rc")" 2>/dev/null || true

    # Capture the original mode before mv clobbers it; default 644 for a new rc.
    local rc_mode=644
    [[ -e "$rc" ]] && rc_mode="$(stat -c '%a' "$rc" 2>/dev/null || echo 644)"

    [[ -f "$rc" ]] || : >"$rc"
    tmp="$(mktemp "${rc}.laia-tmp.XXXXXX")" || die "mktemp failed"

    if grep -qF "$LAIA_RC_MARKER_BEGIN" "$rc" 2>/dev/null; then
      # Replace existing block. Use awk for portability — sed -i flavors differ.
      awk -v begin="$LAIA_RC_MARKER_BEGIN" -v end="$LAIA_RC_MARKER_END" -v block="$new_block" '
        $0 == begin { in_block = 1; print block; next }
        $0 == end   { in_block = 0; next }
        !in_block   { print }
      ' "$rc" >"$tmp"
      mv "$tmp" "$rc"
      log_info "Updated LAIA block in $rc"
    else
      # Append fresh block, separated by a blank line if file does not end on one.
      cp "$rc" "$tmp"
      [[ -s "$tmp" && "$(tail -c1 "$tmp" 2>/dev/null)" != $'\n' ]] && printf '\n' >>"$tmp"
      printf '\n%s\n' "$new_block" >>"$tmp"
      mv "$tmp" "$rc"
      log_info "Added LAIA block to $rc"
    fi

    shell_rc_restore_meta "$rc" "$rc_mode"
  done <<<"$(shell_rc_targets)"
}

# shell_rc_remove — removes the LAIA block (used by laia-uninstall in the future)
shell_rc_remove() {
  local rc tmp
  while IFS= read -r rc; do
    [[ -z "$rc" ]] && continue
    grep -qF "$LAIA_RC_MARKER_BEGIN" "$rc" 2>/dev/null || continue
    local rc_mode=644
    [[ -e "$rc" ]] && rc_mode="$(stat -c '%a' "$rc" 2>/dev/null || echo 644)"
    tmp="$(mktemp "${rc}.laia-tmp.XXXXXX")" || die "mktemp failed"
    awk -v begin="$LAIA_RC_MARKER_BEGIN" -v end="$LAIA_RC_MARKER_END" '
      $0 == begin { in_block = 1; next }
      $0 == end   { in_block = 0; next }
      !in_block   { print }
    ' "$rc" >"$tmp"
    mv "$tmp" "$rc"
    shell_rc_restore_meta "$rc" "$rc_mode"
    log_info "Removed LAIA block from $rc"
  done <<<"$(shell_rc_targets)"
}
