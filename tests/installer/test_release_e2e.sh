#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# tests/installer/test_release_e2e.sh
#
# Verifies the laia-release pipeline:
#   1. First install:  laia-install v0.0.0-a
#   2. Release:        laia-release v0.0.0-b
#
# Asserts:
#   - Both versions exist on disk after the release
#   - /opt/laia symlink (override) now resolves to laia-v0.0.0-b
#   - .previous file beside the symlink contains "v0.0.0-a"
#   - Wrappers in /usr/local/bin (override) still work (idempotent)
#   - shell rc still has exactly one block (release doesn't duplicate it)
#   - systemd units re-rendered with substituted paths
#
# No sudo, no real systemctl: runs entirely in $HOME tmpdir with all
# LAIA_*_OVERRIDE vars set. inst_is_override_mode keeps systemctl out of it.
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
# /tmp may be a small tmpfs — use $HOME so disk preflight passes.
TMPDIR_TEST="$(mktemp -d "${HOME}/laia-release-e2e.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

export LAIA_INSTALL_ROOT_OVERRIDE="$TMPDIR_TEST/opt"
export LAIA_BIN_DIR_OVERRIDE="$TMPDIR_TEST/usr-local-bin"
export LAIA_HOME_OVERRIDE="$TMPDIR_TEST/LAIA-ARCH"
export LAIA_SYSTEMD_DIR_OVERRIDE="$TMPDIR_TEST/systemd"
export LAIA_SHELL_RC_OVERRIDE="$TMPDIR_TEST/bashrc-test"
export LAIA_LOG_FILE="$TMPDIR_TEST/release.log"
export NO_COLOR=1

mkdir -p "$LAIA_INSTALL_ROOT_OVERRIDE"

# Pre-existing rc so we can check it's preserved.
cat >"$LAIA_SHELL_RC_OVERRIDE" <<'EOF'
export EXISTING_VAR=hello
EOF

VER_A="v0.0.0-a"
VER_B="v0.0.0-b"

# ── Step 1: initial install ────────────────────────────────────────────────
echo "→ Step 1: laia-install $VER_A"
if ! "$BIN/laia-install" \
    --from-local "$LAIA_ROOT" \
    --version "$VER_A" \
    --skip-pip --skip-frontend --yes \
    >"$TMPDIR_TEST/install.log" 2>&1; then
  echo "✗ initial install failed:"
  cat "$TMPDIR_TEST/install.log"
  exit 1
fi
assert "initial install exited 0" "0"

INST_DIR_A="$TMPDIR_TEST/opt/laia-$VER_A"
INST_DIR_B="$TMPDIR_TEST/opt/laia-$VER_B"
SYMLINK="$TMPDIR_TEST/opt/laia"
PREV_FILE="$SYMLINK.previous"

assert "v_a install dir present" "$([[ -d "$INST_DIR_A" ]] && echo 0 || echo 1)"
assert "symlink resolves to v_a" \
  "$([[ "$(readlink "$SYMLINK")" == "laia-$VER_A" ]] && echo 0 || echo 1)"
assert "no .previous file after first install (no previous yet)" \
  "$([[ ! -f "$PREV_FILE" ]] && echo 0 || echo 1)"

# Capture state after install for later comparison.
SYSTEMD_DIR="$TMPDIR_TEST/systemd"
gateway_unit_a_md5="$(md5sum "$SYSTEMD_DIR/laia-gateway.service" | awk '{print $1}')"

# ── Step 2: frontend artifact gate ─────────────────────────────────────────
echo
echo "→ Step 2: laia-release requires frontend dist unless --skip-frontend"
set +e
"$BIN/laia-release" \
    --version v0.0.0-frontend-missing \
    --allow-dirty \
    --skip-tests --skip-pip \
    --yes \
    "$LAIA_ROOT" \
    >"$TMPDIR_TEST/release_frontend_missing.log" 2>&1
frontend_rc=$?
set -e
assert "release without dist and without --skip-frontend fails" \
  "$([[ "$frontend_rc" -ne 0 ]] && echo 0 || echo 1)"
assert "failed frontend release did not move symlink" \
  "$([[ "$(readlink "$SYMLINK")" == "laia-$VER_A" ]] && echo 0 || echo 1)"
assert "frontend failure mentions --skip-frontend" \
  "$(grep -q -- '--skip-frontend' "$TMPDIR_TEST/release_frontend_missing.log" && echo 0 || echo 1)"

# ── Step 3: release v_b ────────────────────────────────────────────────────
echo
echo "→ Step 3: laia-release $VER_B with --skip-frontend"
if ! "$BIN/laia-release" \
    --version "$VER_B" \
    --allow-dirty \
    --skip-tests --skip-pip --skip-frontend \
    --yes \
    "$LAIA_ROOT" \
    >"$TMPDIR_TEST/release.log" 2>&1; then
  echo "✗ release failed:"
  cat "$TMPDIR_TEST/release.log"
  exit 1
fi
assert "release exited 0" "0"

# ── Layout after release ───────────────────────────────────────────────────
echo
echo "→ Post-release layout"
assert "v_b install dir present" "$([[ -d "$INST_DIR_B" ]] && echo 0 || echo 1)"
assert "v_a install dir STILL present (no auto-prune)" \
  "$([[ -d "$INST_DIR_A" ]] && echo 0 || echo 1)"
assert "symlink moved to v_b" \
  "$([[ "$(readlink "$SYMLINK")" == "laia-$VER_B" ]] && echo 0 || echo 1)"
assert "VERSION file inside v_b matches" \
  "$([[ "$(cat "$INST_DIR_B/VERSION" 2>/dev/null)" == "$VER_B" ]] && echo 0 || echo 1)"
assert "VERSION file inside v_a still matches" \
  "$([[ "$(cat "$INST_DIR_A/VERSION" 2>/dev/null)" == "$VER_A" ]] && echo 0 || echo 1)"

# ── Previous-version tracking ──────────────────────────────────────────────
echo
echo "→ Previous-version tracking"
assert ".previous file written" "$([[ -f "$PREV_FILE" ]] && echo 0 || echo 1)"
assert ".previous file content == v_a" \
  "$([[ "$(cat "$PREV_FILE" 2>/dev/null)" == "$VER_A" ]] && echo 0 || echo 1)"

# ── Shell rc not duplicated ────────────────────────────────────────────────
echo
echo "→ Shell rc not duplicated (release should not touch it again, but install did)"
begin_count=$(grep -c '^# >>> laia >>>$' "$LAIA_SHELL_RC_OVERRIDE" 2>/dev/null || echo 0)
assert "exactly one LAIA block after install+release (count=$begin_count)" \
  "$([[ "$begin_count" == "1" ]] && echo 0 || echo 1)"
assert "pre-existing user var preserved" \
  "$(grep -q '^export EXISTING_VAR=hello$' "$LAIA_SHELL_RC_OVERRIDE" && echo 0 || echo 1)"

# ── Wrappers still valid ───────────────────────────────────────────────────
echo
echo "→ Wrappers still pointing at /opt/laia/bin (stable across releases)"
for w in laia laia-install laia-clone laia-release laia-rollback; do
  assert "wrapper $w still a symlink" \
    "$([[ -L "$TMPDIR_TEST/usr-local-bin/$w" ]] && echo 0 || echo 1)"
done

# ── systemd unit re-rendered ───────────────────────────────────────────────
echo
echo "→ Systemd units re-rendered"
assert "laia-gateway.service still exists" \
  "$([[ -f "$SYSTEMD_DIR/laia-gateway.service" ]] && echo 0 || echo 1)"
assert "no leftover \${LAIA_*} placeholders" \
  "$(! grep -RIq '\${LAIA_' "$SYSTEMD_DIR"/*.service && echo 0 || echo 1)"
# Content should still be the same (paths and templates didn't change between
# the install and the release in this test):
gateway_unit_b_md5="$(md5sum "$SYSTEMD_DIR/laia-gateway.service" | awk '{print $1}')"
assert "unit md5 unchanged across install+release (deterministic render)" \
  "$([[ "$gateway_unit_a_md5" == "$gateway_unit_b_md5" ]] && echo 0 || echo 1)"

# ── Re-release v_b with --force is idempotent ──────────────────────────────
echo
echo "→ Re-release of v_b with --force is idempotent"
if ! "$BIN/laia-release" \
    --version "$VER_B" \
    --allow-dirty --force \
    --skip-tests --skip-pip --skip-frontend \
    --yes \
    "$LAIA_ROOT" \
    >"$TMPDIR_TEST/release2.log" 2>&1; then
  echo "✗ re-release failed:"
  cat "$TMPDIR_TEST/release2.log"
  exit 1
fi
assert "re-release exited 0" "0"
assert "symlink still resolves to v_b" \
  "$([[ "$(readlink "$SYMLINK")" == "laia-$VER_B" ]] && echo 0 || echo 1)"
# After re-release of the same version, .previous should be "v_b" (we rolled
# FROM v_b TO v_b — effectively the previous version is v_b itself). The
# release records whatever was current before the switch.
assert ".previous file now points to v_b (we released over v_b)" \
  "$([[ "$(cat "$PREV_FILE" 2>/dev/null)" == "$VER_B" ]] && echo 0 || echo 1)"

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
  echo "Logs in: $TMPDIR_TEST"
  exit 1
fi
exit 0
