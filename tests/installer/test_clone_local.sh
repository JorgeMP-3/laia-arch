#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# tests/installer/test_clone_local.sh
#
# End-to-end test of laia-clone in --source-dir mode (no SSH).
#
# Builds a fake source tree under $TMPDIR/source with the expected layout:
#
#   source/
#     LAIA-ARCH/
#       SOUL.md, agents/jorge/file.md, db.sqlite,
#       cache/junk        ← excluded by Phase 1
#       logs/x.log        ← excluded
#       gateway.pid       ← excluded
#       __pycache__/x.pyc ← excluded
#       mlx-servers/big   ← excluded unless --with-mlx-models
#     users/
#       jorge/home/.bashrc, jorge/home/.profile
#       jorge/__pycache__/x.pyc  ← excluded by Phase 3
#     home/
#       .gitconfig
#       .claude/config.json
#       .claude/shell-snapshots/x ← excluded
#       .claude/ide/x             ← excluded
#       .codex/auth.json
#       .codex/sessions/x         ← excluded
#       .opencode/config.json
#       .opencode/bin/opencode    ← excluded
#       .claude.json
#       .gemini/state
#
# Runs clone with all LAIA_*_OVERRIDE vars set so nothing real is touched.
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
TMPDIR_TEST="$(mktemp -d "${HOME}/laia-clone.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

SRC="$TMPDIR_TEST/source"
DEST="$TMPDIR_TEST/dest"

mkdir -p "$DEST/LAIA-ARCH" "$DEST/srv-users" "$DEST/tools-home"

export LAIA_HOME_OVERRIDE="$DEST/LAIA-ARCH"
export LAIA_USERS_DIR_OVERRIDE="$DEST/srv-users"
export LAIA_TOOLS_HOME_OVERRIDE="$DEST/tools-home"
export LAIA_LOG_FILE="$TMPDIR_TEST/run.log"
export NO_COLOR=1

# ── Build fake source ──────────────────────────────────────────────────────
build_source() {
  # Phase 1 source (LAIA-ARCH)
  mkdir -p "$SRC/LAIA-ARCH"/{agents/jorge,cache,logs,__pycache__,mlx-servers}
  printf 'SOUL\n' >"$SRC/LAIA-ARCH/SOUL.md"
  printf 'agent\n' >"$SRC/LAIA-ARCH/agents/jorge/file.md"
  printf 'db\n' >"$SRC/LAIA-ARCH/db.sqlite"
  printf 'junk\n' >"$SRC/LAIA-ARCH/cache/junk"
  printf 'log\n' >"$SRC/LAIA-ARCH/logs/x.log"
  printf 'pid\n' >"$SRC/LAIA-ARCH/gateway.pid"
  printf 'pyc\n' >"$SRC/LAIA-ARCH/__pycache__/x.pyc"
  printf 'heavy\n' >"$SRC/LAIA-ARCH/mlx-servers/big"

  # Phase 3 source (users)
  mkdir -p "$SRC/users/jorge/home" "$SRC/users/jorge/__pycache__"
  printf 'bashrc\n' >"$SRC/users/jorge/home/.bashrc"
  printf 'profile\n' >"$SRC/users/jorge/home/.profile"
  printf 'pyc\n' >"$SRC/users/jorge/__pycache__/x.pyc"

  # Phase 4 source (home / tools)
  mkdir -p "$SRC/home/.claude/shell-snapshots" \
           "$SRC/home/.claude/ide" \
           "$SRC/home/.codex/sessions" \
           "$SRC/home/.opencode/bin" \
           "$SRC/home/.gemini"
  printf 'gitcfg\n' >"$SRC/home/.gitconfig"
  printf '{}\n' >"$SRC/home/.claude.json"
  printf '{c1}\n' >"$SRC/home/.claude/config.json"
  printf 'snap\n' >"$SRC/home/.claude/shell-snapshots/x"
  printf 'ide\n' >"$SRC/home/.claude/ide/x"
  printf 'auth\n' >"$SRC/home/.codex/auth.json"
  printf 'sess\n' >"$SRC/home/.codex/sessions/x"
  printf 'occfg\n' >"$SRC/home/.opencode/config.json"
  printf 'bigbin\n' >"$SRC/home/.opencode/bin/opencode"
  printf 'state\n' >"$SRC/home/.gemini/state"
}

build_source

# ──────────────────────────────────────────────────────────────────────────
# (A) Clone WITHOUT --with-tools — Phases 1 + 3 only
# ──────────────────────────────────────────────────────────────────────────
echo "=== (A) clone without --with-tools ==================================="
if ! "$BIN/laia-clone" \
    --source-dir "$SRC" --yes --no-lxd \
    >"$TMPDIR_TEST/run-A.log" 2>&1; then
  echo "✗ laia-clone failed:"
  cat "$TMPDIR_TEST/run-A.log"
  exit 1
fi
assert "clone exited 0" "0"

# ── Phase 1 layout ────────────────────────────────────────────────────────
echo
echo "→ Phase 1 (LAIA-ARCH) destination"
DLA="$DEST/LAIA-ARCH"
assert "SOUL.md copied"           "$([[ -f $DLA/SOUL.md ]] && echo 0 || echo 1)"
assert "agents/jorge/file.md copied" "$([[ -f $DLA/agents/jorge/file.md ]] && echo 0 || echo 1)"
assert "db.sqlite copied"          "$([[ -f $DLA/db.sqlite ]] && echo 0 || echo 1)"
assert "cache/ excluded"           "$([[ ! -d $DLA/cache ]] && echo 0 || echo 1)"
assert "logs/ excluded"            "$([[ ! -d $DLA/logs ]] && echo 0 || echo 1)"
assert "gateway.pid excluded"      "$([[ ! -f $DLA/gateway.pid ]] && echo 0 || echo 1)"
assert "__pycache__ excluded"      "$([[ ! -d $DLA/__pycache__ ]] && echo 0 || echo 1)"
assert "mlx-servers/ excluded (default)" "$([[ ! -d $DLA/mlx-servers ]] && echo 0 || echo 1)"

# ── Phase 3 layout ────────────────────────────────────────────────────────
echo
echo "→ Phase 3 (/srv/laia/users override) destination"
DSU="$DEST/srv-users"
assert "jorge/home/.bashrc copied"  "$([[ -f $DSU/jorge/home/.bashrc ]] && echo 0 || echo 1)"
assert "jorge/home/.profile copied" "$([[ -f $DSU/jorge/home/.profile ]] && echo 0 || echo 1)"
assert "jorge/__pycache__ excluded" "$([[ ! -d $DSU/jorge/__pycache__ ]] && echo 0 || echo 1)"

# ── Phase 4 not run (no --with-tools) ─────────────────────────────────────
echo
echo "→ Phase 4 should be a no-op without --with-tools"
DTH="$DEST/tools-home"
# DTH was pre-created but should be empty / have no copied files.
assert "tools dest has no .gitconfig (skipped)" \
  "$([[ ! -f $DTH/.gitconfig ]] && echo 0 || echo 1)"
assert "tools dest has no .claude.json (skipped)" \
  "$([[ ! -f $DTH/.claude.json ]] && echo 0 || echo 1)"

# ──────────────────────────────────────────────────────────────────────────
# (B) Re-clone with --with-tools — Phase 4 included
# ──────────────────────────────────────────────────────────────────────────
echo
echo "=== (B) re-clone with --with-tools ==================================="
if ! "$BIN/laia-clone" \
    --source-dir "$SRC" --yes --no-lxd --with-tools \
    >"$TMPDIR_TEST/run-B.log" 2>&1; then
  echo "✗ laia-clone (with-tools) failed:"
  cat "$TMPDIR_TEST/run-B.log"
  exit 1
fi
assert "clone with --with-tools exited 0" "0"

echo
echo "→ Phase 4 tools destination"
assert ".gitconfig copied"                "$([[ -f $DTH/.gitconfig ]] && echo 0 || echo 1)"
assert ".claude.json copied"              "$([[ -f $DTH/.claude.json ]] && echo 0 || echo 1)"
assert ".claude/config.json copied"       "$([[ -f $DTH/.claude/config.json ]] && echo 0 || echo 1)"
assert ".codex/auth.json copied"          "$([[ -f $DTH/.codex/auth.json ]] && echo 0 || echo 1)"
assert ".opencode/config.json copied"     "$([[ -f $DTH/.opencode/config.json ]] && echo 0 || echo 1)"
assert ".gemini/state copied"             "$([[ -f $DTH/.gemini/state ]] && echo 0 || echo 1)"

echo
echo "→ Phase 4 excludes"
assert ".claude/shell-snapshots/ excluded" "$([[ ! -d $DTH/.claude/shell-snapshots ]] && echo 0 || echo 1)"
assert ".claude/ide/ excluded"             "$([[ ! -d $DTH/.claude/ide ]] && echo 0 || echo 1)"
assert ".codex/sessions/ excluded"         "$([[ ! -d $DTH/.codex/sessions ]] && echo 0 || echo 1)"
assert ".opencode/bin/opencode excluded"   "$([[ ! -f $DTH/.opencode/bin/opencode ]] && echo 0 || echo 1)"

# ──────────────────────────────────────────────────────────────────────────
# (C) Idempotency — running again leaves things unchanged
# ──────────────────────────────────────────────────────────────────────────
echo
echo "=== (C) idempotency =================================================="
md5_before="$(find "$DEST" -type f | sort | xargs md5sum 2>/dev/null | md5sum | awk '{print $1}')"

if ! "$BIN/laia-clone" \
    --source-dir "$SRC" --yes --no-lxd --with-tools \
    >"$TMPDIR_TEST/run-C.log" 2>&1; then
  echo "✗ third clone failed:"
  cat "$TMPDIR_TEST/run-C.log"
  exit 1
fi

md5_after="$(find "$DEST" -type f | sort | xargs md5sum 2>/dev/null | md5sum | awk '{print $1}')"
assert "all-file md5 unchanged across re-run (rsync is additive but stable)" \
  "$([[ "$md5_before" == "$md5_after" ]] && echo 0 || echo 1)"

# ──────────────────────────────────────────────────────────────────────────
# (D) --with-mlx-models flips the mlx-servers/ exclude
# ──────────────────────────────────────────────────────────────────────────
echo
echo "=== (D) --with-mlx-models includes heavy models ======================"

# Wipe the LAIA-ARCH dest mlx-servers dir to confirm the next run creates it.
rm -rf "$DLA/mlx-servers"

if ! "$BIN/laia-clone" \
    --source-dir "$SRC" --yes --no-lxd --with-mlx-models \
    >"$TMPDIR_TEST/run-D.log" 2>&1; then
  echo "✗ clone --with-mlx-models failed:"
  cat "$TMPDIR_TEST/run-D.log"
  exit 1
fi
assert "mlx-servers/big now copied (no longer excluded)" \
  "$([[ -f $DLA/mlx-servers/big ]] && echo 0 || echo 1)"

# ──────────────────────────────────────────────────────────────────────────
# (E) Argument validation
# ──────────────────────────────────────────────────────────────────────────
echo
echo "=== (E) argument validation =========================================="

# --source-dir + user@host together → error
if "$BIN/laia-clone" --source-dir "$SRC" dummy@example.com --yes >/dev/null 2>&1; then
  assert "--source-dir + user@host together refused" "1"
else
  assert "--source-dir + user@host together refused" "0"
fi

# Neither source given → error
if "$BIN/laia-clone" --yes >/dev/null 2>&1; then
  assert "no source refused" "1"
else
  assert "no source refused" "0"
fi

# --source-dir to a non-existent path → error (preflight catches it)
if "$BIN/laia-clone" --source-dir /tmp/no-such-laia-source --yes >/dev/null 2>&1; then
  assert "missing --source-dir path refused" "1"
else
  assert "missing --source-dir path refused" "0"
fi

# --source-dir to a dir without LAIA-ARCH/ subtree → error (preflight)
empty_dir="$TMPDIR_TEST/empty-source"
mkdir -p "$empty_dir"
if "$BIN/laia-clone" --source-dir "$empty_dir" --yes >/dev/null 2>&1; then
  assert "invalid --source-dir layout refused" "1"
else
  assert "invalid --source-dir layout refused" "0"
fi

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
