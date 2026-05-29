#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# tests/installer/test_install_e2e.sh
#
# Full pipeline test of laia-install with all LAIA_*_OVERRIDE vars pointing
# at a tmpdir. No sudo, no /opt mutations, no .bashrc mutations.
#
# Skips:
#   --skip-pip       (creating venvs + pip install takes 1-2 min, needs network)
#   --skip-frontend  (only checks for dist/ anyway, but explicit for speed)
#
# Verifies:
#   - Versioned install dir is created and stamped with VERSION file
#   - Symlink (/opt/laia override) points to the versioned dir
#   - Wrappers (/usr/local/bin override) are symlinks to .../bin/laia*
#   - Data dir (~/LAIA-ARCH override) exists with 700 perms
#   - Shell rc file has exactly one LAIA block with the correct LAIA_HOME
#   - Systemd units are rendered with substituted paths
#   - A second invocation with --force does not duplicate the rc block
# ─────────────────────────────────────────────────────────────────────────────
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
BIN="$LAIA_ROOT/bin"

PASS=0
FAIL=0
FAILURES=()

assert() {
  local desc="$1" status="$2"
  if [[ "$status" == "0" ]]; then
    PASS=$((PASS + 1))
    printf '  ✓ %s\n' "$desc"
  else
    FAIL=$((FAIL + 1))
    FAILURES+=("$desc")
    printf '  ✗ %s\n' "$desc"
  fi
}

# ── Tmpdir + overrides ─────────────────────────────────────────────────────
# Use $HOME for the tmpdir: /tmp on CI/dev boxes can be a small tmpfs and
# ensure_disk_free_gb will refuse with <5G free.
TMPDIR_TEST="$(mktemp -d "${HOME}/laia-e2e.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

export LAIA_INSTALL_ROOT_OVERRIDE="$TMPDIR_TEST/opt"
export LAIA_BIN_DIR_OVERRIDE="$TMPDIR_TEST/usr-local-bin"
export LAIA_HOME_OVERRIDE="$TMPDIR_TEST/LAIA-ARCH"
export LAIA_SYSTEMD_DIR_OVERRIDE="$TMPDIR_TEST/systemd"
export LAIA_SHELL_RC_OVERRIDE="$TMPDIR_TEST/bashrc-test"
export LAIA_LOG_FILE="$TMPDIR_TEST/install.log"
export NO_COLOR=1

# ensure_disk_free_gb needs the install root to exist (df can't stat a missing
# path). Pre-create it; the installer will populate it below.
mkdir -p "$LAIA_INSTALL_ROOT_OVERRIDE"

# Pre-create the rc file with some existing content so we can assert that the
# installer doesn't clobber it.
cat >"$LAIA_SHELL_RC_OVERRIDE" <<'EOF'
# user's existing rc
export EXISTING_VAR=hello
EOF

VERSION="v0.0.0-test"

# ── Run the installer ──────────────────────────────────────────────────────
echo "→ Running laia-install in tmpdir:"
echo "    $TMPDIR_TEST"
echo

if ! "$BIN/laia-install" \
    --from-local "$LAIA_ROOT" \
    --version "$VERSION" \
    --skip-pip \
    --skip-frontend \
    --yes \
    >"$TMPDIR_TEST/run1.log" 2>&1; then
  echo "✗ laia-install FAILED — log follows:"
  cat "$TMPDIR_TEST/run1.log"
  exit 1
fi
assert "installer exited 0" "0"

# ── Layout assertions ──────────────────────────────────────────────────────
echo
echo "→ Install layout"
INST_DEST="$TMPDIR_TEST/opt/laia-$VERSION"
INST_PREFIX="$TMPDIR_TEST/opt/laia"
WRAPPER_DIR="$TMPDIR_TEST/usr-local-bin"
DATA_DIR="$TMPDIR_TEST/LAIA-ARCH"
SYSTEMD_DIR="$TMPDIR_TEST/systemd"

assert "install dir exists: $INST_DEST" \
  "$([[ -d "$INST_DEST" ]] && echo 0 || echo 1)"
assert "VERSION file stamped" \
  "$([[ -f "$INST_DEST/VERSION" ]] && echo 0 || echo 1)"
assert "VERSION file content matches" \
  "$([[ "$(cat "$INST_DEST/VERSION" 2>/dev/null)" == "$VERSION" ]] && echo 0 || echo 1)"
assert "bin/ copied into install dir" \
  "$([[ -d "$INST_DEST/bin" ]] && echo 0 || echo 1)"
assert "bin/laia-install in install dir" \
  "$([[ -f "$INST_DEST/bin/laia-install" ]] && echo 0 || echo 1)"

# rsync excludes — these MUST NOT be present in the install dir.
assert ".git/ excluded from install dir" \
  "$([[ ! -d "$INST_DEST/.git" ]] && echo 0 || echo 1)"
assert "archived/ excluded from install dir" \
  "$([[ ! -d "$INST_DEST/archived" ]] && echo 0 || echo 1)"

# ── Symlink ────────────────────────────────────────────────────────────────
echo
echo "→ /opt/laia symlink"
assert "symlink exists" \
  "$([[ -L "$INST_PREFIX" ]] && echo 0 || echo 1)"
assert "symlink resolves to versioned dir" \
  "$([[ "$(readlink "$INST_PREFIX")" == "laia-$VERSION" ]] && echo 0 || echo 1)"

# ── Wrappers ───────────────────────────────────────────────────────────────
echo
echo "→ /usr/local/bin wrappers"
for w in laia laia-install laia-clone laia-release laia-rollback; do
  assert "wrapper $w is a symlink" \
    "$([[ -L "$WRAPPER_DIR/$w" ]] && echo 0 || echo 1)"
  assert "wrapper $w points to /opt/laia/bin/$w (override)" \
    "$([[ "$(readlink "$WRAPPER_DIR/$w")" == "$INST_PREFIX/bin/$w" ]] && echo 0 || echo 1)"
done

# ── Data dir ───────────────────────────────────────────────────────────────
echo
echo "→ Data directory"
assert "data dir exists" \
  "$([[ -d "$DATA_DIR" ]] && echo 0 || echo 1)"
assert "data dir mode 700" \
  "$([[ "$(stat -c %a "$DATA_DIR")" == "700" ]] && echo 0 || echo 1)"

# ── Shell rc ───────────────────────────────────────────────────────────────
echo
echo "→ Shell rc file"
assert "rc file still exists" \
  "$([[ -f "$LAIA_SHELL_RC_OVERRIDE" ]] && echo 0 || echo 1)"
assert "pre-existing user var preserved" \
  "$(grep -q '^export EXISTING_VAR=hello$' "$LAIA_SHELL_RC_OVERRIDE" && echo 0 || echo 1)"
assert "LAIA block begin marker present" \
  "$(grep -q '^# >>> laia >>>$' "$LAIA_SHELL_RC_OVERRIDE" && echo 0 || echo 1)"
assert "LAIA_HOME points to override data dir" \
  "$(grep -qF "export LAIA_HOME=\"$DATA_DIR\"" "$LAIA_SHELL_RC_OVERRIDE" && echo 0 || echo 1)"
begin_count=$(grep -c '^# >>> laia >>>$' "$LAIA_SHELL_RC_OVERRIDE" 2>/dev/null || echo 0)
assert "exactly one LAIA block (count=$begin_count)" \
  "$([[ "$begin_count" == "1" ]] && echo 0 || echo 1)"

# ── Systemd units ──────────────────────────────────────────────────────────
echo
echo "→ Systemd units"
for unit in laia-gateway.service laia-pathd.service agora-backend.service laia-ui-server.service; do
  assert "$unit rendered" \
    "$([[ -f "$SYSTEMD_DIR/$unit" ]] && echo 0 || echo 1)"
done
assert "laia-gateway substitutes INST_PREFIX path" \
  "$(grep -qF "$INST_PREFIX/.laia-core" "$SYSTEMD_DIR/laia-gateway.service" && echo 0 || echo 1)"
assert "laia-gateway sources .env.paths from v2 ARCH runtime home" \
  "$(grep -qF "EnvironmentFile=-/srv/laia/arch/.env.paths" "$SYSTEMD_DIR/laia-gateway.service" && echo 0 || echo 1)"
assert "no leftover \${LAIA_*} placeholders in any unit" \
  "$(! grep -RIq '\${LAIA_' "$SYSTEMD_DIR"/*.service && echo 0 || echo 1)"

# ── Re-run for idempotency ─────────────────────────────────────────────────
echo
echo "→ Re-run with --force (idempotency)"
if ! "$BIN/laia-install" \
    --from-local "$LAIA_ROOT" \
    --version "$VERSION" \
    --skip-pip \
    --skip-frontend \
    --force \
    --yes \
    >"$TMPDIR_TEST/run2.log" 2>&1; then
  echo "✗ second laia-install FAILED — log follows:"
  cat "$TMPDIR_TEST/run2.log"
  exit 1
fi
assert "second installer run exited 0" "0"

begin_count_2=$(grep -c '^# >>> laia >>>$' "$LAIA_SHELL_RC_OVERRIDE" 2>/dev/null || echo 0)
assert "still exactly one LAIA block after re-install (count=$begin_count_2)" \
  "$([[ "$begin_count_2" == "1" ]] && echo 0 || echo 1)"
assert "data dir still 700 after re-install" \
  "$([[ "$(stat -c %a "$DATA_DIR")" == "700" ]] && echo 0 || echo 1)"
assert "symlink still resolves to versioned dir" \
  "$([[ "$(readlink "$INST_PREFIX")" == "laia-$VERSION" ]] && echo 0 || echo 1)"

# ── Summary ────────────────────────────────────────────────────────────────
echo
echo "═══════════════════════════════════════════════════"
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
if [[ $FAIL -gt 0 ]]; then
  echo
  echo "Failures:"
  for f in "${FAILURES[@]}"; do
    printf "  - %s\n" "$f"
  done
  echo
  echo "Last installer log: $TMPDIR_TEST"
  exit 1
fi
exit 0
