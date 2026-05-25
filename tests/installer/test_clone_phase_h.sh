#!/usr/bin/env bash
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
BIN="$LAIA_ROOT/bin"
PASS=0; FAIL=0; FAILURES=()
assert() { local d="$1" s="$2"; if [[ "$s" == 0 ]]; then PASS=$((PASS+1)); printf '  ✓ %s\n' "$d"; else FAIL=$((FAIL+1)); FAILURES+=("$d"); printf '  ✗ %s\n' "$d"; fi; }

TMPDIR_TEST="$(mktemp -d "${HOME}/laia-clone-h.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT
SRC="$TMPDIR_TEST/source"
mkdir -p "$SRC/agora" "$SRC/users/jorge/home" \
  "$SRC/home/.laia/workspaces" "$SRC/home/.laia/memories" \
  "$SRC/home/.laia/skills" "$SRC/home/.laia/plugins" \
  "$SRC/home/.laia/sessions" "$SRC/home/.laia/sandboxes" \
  "$SRC/home/.laia/atlas" "$SRC/home/.laia/cron" "$SRC/home/.laia/logs"
printf 'db\n' >"$SRC/agora/agora.db"
printf 'hello\n' >"$SRC/users/jorge/home/file.txt"
printf 'w\n' >"$SRC/home/.laia/workspaces/a.md"
printf 'm\n' >"$SRC/home/.laia/memories/m.md"
printf 's\n' >"$SRC/home/.laia/skills/s.md"
printf 'p\n' >"$SRC/home/.laia/plugins/p.py"
printf 'session\n' >"$SRC/home/.laia/sessions/s.json"
printf 'sandbox\n' >"$SRC/home/.laia/sandboxes/x"
printf 'atlas\n' >"$SRC/home/.laia/atlas/a"
printf 'cron\n' >"$SRC/home/.laia/cron/c"
printf 'log\n' >"$SRC/home/.laia/logs/l"
printf 'auth\n' >"$SRC/home/.laia/auth.json"
printf 'SECRET=1\n' >"$SRC/home/.laia/.env"
cat >"$SRC/home/.laia/config.yaml" <<'EOF'
paths:
  laia_root: /home/laia-hermes/LAIA
  laia_home: ${LAIA_HOME:-/home/laia-hermes/.laia}
  agora_data: ${paths.laia_home}/agora.db
  workspaces: ~/.laia/workspaces
  memories: /home/laia-hermes/.laia/memories
  skills: /home/laia-hermes/.laia/skills
  plugins: /home/laia-hermes/.laia/plugins
EOF

export NO_COLOR=1
export LAIA_HOME_OVERRIDE="$TMPDIR_TEST/LAIA-ARCH"
export LAIA_USERS_DIR_OVERRIDE="$TMPDIR_TEST/srv/users"
export LAIA_AGORA_DIR_OVERRIDE="$TMPDIR_TEST/srv/agora"
export LAIA_ARCH_DIR_OVERRIDE="$TMPDIR_TEST/srv/arch"
export LAIA_ARCH_CREDS_DIR_OVERRIDE="$TMPDIR_TEST/home/.laia"
export LAIA_LOG_FILE="$TMPDIR_TEST/log"
export LAIA_TEST_STUB_LOG="$TMPDIR_TEST/stub.log"

"$BIN/laia-clone" --source-dir "$SRC" --yes >"$TMPDIR_TEST/run.log" 2>&1
assert "clone phase H exits 0" "$?"
assert "agora data copied" "$([[ -f "$LAIA_AGORA_DIR_OVERRIDE/agora.db" ]] && echo 0 || echo 1)"
assert "users data copied" "$([[ -f "$LAIA_USERS_DIR_OVERRIDE/jorge/home/file.txt" ]] && echo 0 || echo 1)"
assert "arch workspace copied to live LAIA_HOME" "$([[ -f "$LAIA_HOME_OVERRIDE/workspaces/a.md" ]] && echo 0 || echo 1)"
assert "arch memory copied to live LAIA_HOME" "$([[ -f "$LAIA_HOME_OVERRIDE/memories/m.md" ]] && echo 0 || echo 1)"
assert "arch skill copied to live LAIA_HOME" "$([[ -f "$LAIA_HOME_OVERRIDE/skills/s.md" ]] && echo 0 || echo 1)"
assert "arch plugin copied to live LAIA_HOME" "$([[ -f "$LAIA_HOME_OVERRIDE/plugins/p.py" ]] && echo 0 || echo 1)"
assert "operational sessions copied to /srv/laia/arch" "$([[ -f "$LAIA_ARCH_DIR_OVERRIDE/sessions/s.json" ]] && echo 0 || echo 1)"
assert "operational sandboxes copied to /srv/laia/arch" "$([[ -f "$LAIA_ARCH_DIR_OVERRIDE/sandboxes/x" ]] && echo 0 || echo 1)"
assert "operational atlas copied to /srv/laia/arch" "$([[ -f "$LAIA_ARCH_DIR_OVERRIDE/atlas/a" ]] && echo 0 || echo 1)"
assert "operational cron copied to /srv/laia/arch" "$([[ -f "$LAIA_ARCH_DIR_OVERRIDE/cron/c" ]] && echo 0 || echo 1)"
assert "operational logs copied to /srv/laia/arch" "$([[ -f "$LAIA_ARCH_DIR_OVERRIDE/logs/l" ]] && echo 0 || echo 1)"
assert "interactive workspaces not copied to /srv/laia/arch" "$([[ ! -e "$LAIA_ARCH_DIR_OVERRIDE/workspaces/a.md" ]] && echo 0 || echo 1)"
assert "config laia_root → /opt/laia" "$(grep -Eq '^[[:space:]]*laia_root:[[:space:]]*/opt/laia[[:space:]]*$' "$LAIA_ARCH_DIR_OVERRIDE/config.yaml" && echo 0 || echo 1)"
assert "config laia_home → live LAIA_HOME fallback" "$(grep -Fq "  laia_home: \${LAIA_HOME:-$LAIA_HOME_OVERRIDE}" "$LAIA_ARCH_DIR_OVERRIDE/config.yaml" && echo 0 || echo 1)"
assert "config agora_data → /srv/laia/agora/agora.db" "$(grep -Eq '^[[:space:]]*agora_data:[[:space:]]*/srv/laia/agora/agora.db[[:space:]]*$' "$LAIA_ARCH_DIR_OVERRIDE/config.yaml" && echo 0 || echo 1)"
assert "config workspaces → live LAIA_HOME" "$(grep -Fq "  workspaces: \${LAIA_HOME:-$LAIA_HOME_OVERRIDE}/workspaces" "$LAIA_ARCH_DIR_OVERRIDE/config.yaml" && echo 0 || echo 1)"
assert "config memories → live LAIA_HOME" "$(grep -Fq "  memories: \${LAIA_HOME:-$LAIA_HOME_OVERRIDE}/memories" "$LAIA_ARCH_DIR_OVERRIDE/config.yaml" && echo 0 || echo 1)"
assert "config skills → live LAIA_HOME" "$(grep -Fq "  skills: \${LAIA_HOME:-$LAIA_HOME_OVERRIDE}/skills" "$LAIA_ARCH_DIR_OVERRIDE/config.yaml" && echo 0 || echo 1)"
assert "config plugins → live LAIA_HOME" "$(grep -Fq "  plugins: \${LAIA_HOME:-$LAIA_HOME_OVERRIDE}/plugins" "$LAIA_ARCH_DIR_OVERRIDE/config.yaml" && echo 0 || echo 1)"
assert "no legacy /home/laia-hermes/.laia residue in config.yaml" "$(grep -q '/home/laia-hermes/.laia' "$LAIA_ARCH_DIR_OVERRIDE/config.yaml" && echo 1 || echo 0)"
assert "auth credential copied" "$([[ -f "$LAIA_ARCH_CREDS_DIR_OVERRIDE/auth.json" ]] && echo 0 || echo 1)"
assert "auth credential mode 600" "$([[ "$(stat -c %a "$LAIA_ARCH_CREDS_DIR_OVERRIDE/auth.json")" == 600 ]] && echo 0 || echo 1)"
assert "rebuild-3 logged in stub log" "$(grep -q 'rebuild-3-provision-agora.sh' "$LAIA_TEST_STUB_LOG" && echo 0 || echo 1)"
assert "rebuild-4 logged for jorge" "$(grep -q 'rebuild-4-first-user.sh --slug jorge --existing-user-only' "$LAIA_TEST_STUB_LOG" && echo 0 || echo 1)"

printf '\nPASS: %d FAIL: %d\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then cat "$TMPDIR_TEST/run.log"; printf '%s\n' "${FAILURES[@]}"; exit 1; fi
