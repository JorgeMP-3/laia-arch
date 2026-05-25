#!/usr/bin/env bash
# Test: clone_phase_h_rewrite_config_paths handles cross-user paths.
#
# Origin user is "laia-hermes" (whose config.yaml has /home/laia-hermes/...
# literals), destination user is "jorge" (LAIA_USER_HOME=/home/jorge).
# After rewrite, the destination config.yaml must contain ZERO references to
# the source user's HOME and must use the Atlas canonical anchors.
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
PASS=0; FAIL=0; FAILURES=()
assert() { local d="$1" s="$2"; if [[ "$s" == 0 ]]; then PASS=$((PASS+1)); printf '  ✓ %s\n' "$d"; else FAIL=$((FAIL+1)); FAILURES+=("$d"); printf '  ✗ %s\n' "$d"; fi; }

TMPDIR_TEST="$(mktemp -d "${HOME}/laia-path-rewrite.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

ARCH_DIR="$TMPDIR_TEST/srv/arch"
mkdir -p "$ARCH_DIR"
# Realistic source config.yaml: paths with /home/laia-hermes/... (origin user)
# while the test runner is some other user.
cat >"$ARCH_DIR/config.yaml" <<'EOF'
# LAIA path registry
paths:
  laia_root: /home/laia-hermes/LAIA
  laia_home: ${LAIA_HOME:-/home/laia-hermes/.laia}
  laia_core: ${paths.laia_root}/.laia-core
  agora: ${paths.laia_root}/services/agora-backend
  agora_data: ${paths.laia_home}/agora.db
  workspaces: ~/.laia/workspaces
  memories: /home/laia-hermes/.laia/memories
  skills: /home/laia-hermes/.laia/skills
  plugins: /home/laia-hermes/.laia/plugins
  state_db: /home/laia-hermes/.laia/state.db
  laia_root_alt: /home/someother/LAIA
other_section:
  foo: bar
EOF

# Simulate cross-user: destination home is /home/jorge
export NO_COLOR=1
export LAIA_HOME_OVERRIDE="$TMPDIR_TEST/LAIA-ARCH"
export LAIA_ARCH_DIR_OVERRIDE="$ARCH_DIR"
export LAIA_USER_HOME="/home/jorge"

# Source the lib stack the way bin/laia-clone does, then invoke just the
# function under test. common.sh sets NO_COLOR-aware globals; the others
# define the shape of the override mode.
# shellcheck source=/dev/null
source "$LAIA_ROOT/infra/installer/lib/common.sh"
# shellcheck source=/dev/null
source "$LAIA_ROOT/infra/installer/lib/sudo.sh"
# shellcheck source=/dev/null
source "$LAIA_ROOT/infra/installer/lib/version.sh"
# shellcheck source=/dev/null
source "$LAIA_ROOT/infra/installer/lib/install.sh"
# shellcheck source=/dev/null
source "$LAIA_ROOT/infra/installer/lib/clone.sh"

clone_phase_h_rewrite_config_paths >/dev/null

cfg="$ARCH_DIR/config.yaml"
assert "laia_root anchored to /opt/laia"      "$(grep -Eq '^[[:space:]]*laia_root:[[:space:]]*/opt/laia[[:space:]]*$' "$cfg" && echo 0 || echo 1)"
assert "laia_home anchored to live LAIA_HOME" "$(grep -Fq "  laia_home: \${LAIA_HOME:-$LAIA_HOME_OVERRIDE}" "$cfg" && echo 0 || echo 1)"
assert "agora_data anchored to canonical DB"  "$(grep -Eq '^[[:space:]]*agora_data:[[:space:]]*/srv/laia/agora/agora\.db[[:space:]]*$' "$cfg" && echo 0 || echo 1)"
assert "no legacy /home/laia-hermes/.laia left" "$(grep -q '/home/laia-hermes/.laia' "$cfg" && echo 1 || echo 0)"
assert "no /home/someother left"              "$(grep -q '/home/someother' "$cfg" && echo 1 || echo 0)"
assert "~/.laia/ swept to /srv/laia/arch"     "$(grep -q '~/.laia/' "$cfg" && echo 1 || echo 0)"
assert "workspaces points to live LAIA_HOME"  "$(grep -Fq "  workspaces: \${LAIA_HOME:-$LAIA_HOME_OVERRIDE}/workspaces" "$cfg" && echo 0 || echo 1)"
assert "memories points to live LAIA_HOME"    "$(grep -Fq "  memories: \${LAIA_HOME:-$LAIA_HOME_OVERRIDE}/memories" "$cfg" && echo 0 || echo 1)"
assert "skills points to live LAIA_HOME"      "$(grep -Fq "  skills: \${LAIA_HOME:-$LAIA_HOME_OVERRIDE}/skills" "$cfg" && echo 0 || echo 1)"
assert "plugins points to live LAIA_HOME"     "$(grep -Fq "  plugins: \${LAIA_HOME:-$LAIA_HOME_OVERRIDE}/plugins" "$cfg" && echo 0 || echo 1)"
assert "state_db defaults to /srv/laia/arch"  "$(grep -Eq '^[[:space:]]*state_db:[[:space:]]*/srv/laia/arch/state.db[[:space:]]*$' "$cfg" && echo 0 || echo 1)"
assert "other_section preserved"              "$(grep -q 'other_section:' "$cfg" && grep -q 'foo: bar' "$cfg" && echo 0 || echo 1)"

printf '\nPASS: %d FAIL: %d\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then printf '%s\n' "${FAILURES[@]}"; cat "$cfg"; exit 1; fi
