#!/usr/bin/env bash
# D1 backup executable spec.
#
# This is intentionally a RED acceptance test until D1 lands. Keep it included
# in run_all.sh, but skip by default so today's green suite does not regress
# while C1/C2/C4 still gate the final host layout.
#
# Remove the LAIA_D1_READY guard when D1 is implemented; at that point this
# becomes the backup gate for the D5 contract:
#   - laia-backup all writes artifacts to LAIA_BACKUP_DIR
#   - covered sources are agora.db, /srv/laia/users, and /srv/laia/arch
#   - clean N prunes artifacts older than N days
#   - no dead PostgreSQL/arete backup path and no legacy Hermes coupling
#
# The test uses tmpdir-backed source overrides instead of /srv/laia or
# /mnt/data. D1 should keep the public interface simple while allowing these
# overrides for installer tests.
set -u

if [[ "${LAIA_D1_READY:-}" != "1" ]]; then
  echo "SKIP: pending D1 impl"
  exit 0
fi

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
BACKUP_BIN="$LAIA_ROOT/infra/bin/laia-backup"

PASS=0
FAIL=0
FAILURES=()

assert() {
  local desc="$1" status="$2"
  if [[ "$status" == "0" ]]; then
    PASS=$((PASS + 1))
    printf '  PASS %s\n' "$desc"
  else
    FAIL=$((FAIL + 1))
    FAILURES+=("$desc")
    printf '  FAIL %s\n' "$desc"
  fi
}

files_under() {
  find "$1" -type f -printf '%P\n' 2>/dev/null | sort
}

contains_file_matching() {
  local root="$1" pattern="$2"
  files_under "$root" | grep -Eiq "$pattern"
}

TMPDIR_TEST="$(mktemp -d "${TMPDIR:-/tmp}/laia-backup-d1.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

export NO_COLOR=1
export LAIA_BACKUP_DIR="$TMPDIR_TEST/backups"

SRV_ROOT="$TMPDIR_TEST/srv/laia"
AGORA_DIR="$SRV_ROOT/agora"
USERS_DIR="$SRV_ROOT/users"
ARCH_DIR="$SRV_ROOT/arch"

mkdir -p "$AGORA_DIR" "$USERS_DIR/jorge/home" "$ARCH_DIR/secrets" "$LAIA_BACKUP_DIR"
printf 'sqlite fixture\n' > "$AGORA_DIR/agora.db"
printf 'user fixture\n' > "$USERS_DIR/jorge/home/readme.txt"
printf 'arch state fixture\n' > "$ARCH_DIR/state.db"
printf '{"provider":"test"}\n' > "$ARCH_DIR/secrets/auth.json"

# D1 may choose either whole-directory overrides or a direct DB override. The
# spec exports both so tests never touch /srv/laia on a developer machine.
export LAIA_AGORA_DIR_OVERRIDE="$AGORA_DIR"
export LAIA_USERS_DIR_OVERRIDE="$USERS_DIR"
export LAIA_ARCH_DIR_OVERRIDE="$ARCH_DIR"
export AGORA_DB="$AGORA_DIR/agora.db"

echo "-> D1 laia-backup all"
if timeout 30 "$BACKUP_BIN" all >"$TMPDIR_TEST/backup-all.out" 2>&1; then
  assert "laia-backup all exits 0" 0
else
  assert "laia-backup all exits 0" 1
fi

assert "backup destination is the LAIA_BACKUP_DIR override" \
  "$([[ -d "$LAIA_BACKUP_DIR" ]] && echo 0 || echo 1)"
assert "agora.db backup artifact exists" \
  "$(contains_file_matching "$LAIA_BACKUP_DIR" '(^|/)agora[^/]*\.(db|sqlite|tar|tgz|tar\.gz|zst|backup)$' && echo 0 || echo 1)"
assert "users backup artifact exists" \
  "$(contains_file_matching "$LAIA_BACKUP_DIR" '(^|/)users?[^/]*\.(tar|tgz|tar\.gz|zst|backup)$' && echo 0 || echo 1)"
assert "arch backup artifact exists" \
  "$(contains_file_matching "$LAIA_BACKUP_DIR" '(^|/)arch[^/]*\.(tar|tgz|tar\.gz|zst|backup)$' && echo 0 || echo 1)"

echo
echo "-> D1 laia-backup clean"
printf 'old\n' > "$LAIA_BACKUP_DIR/manual-old-artifact.tar.gz"
printf 'new\n' > "$LAIA_BACKUP_DIR/manual-new-artifact.tar.gz"
touch -d '10 days ago' "$LAIA_BACKUP_DIR/manual-old-artifact.tar.gz"
touch -d '1 day ago' "$LAIA_BACKUP_DIR/manual-new-artifact.tar.gz"

if timeout 30 "$BACKUP_BIN" clean 7 >"$TMPDIR_TEST/backup-clean.out" 2>&1; then
  assert "laia-backup clean 7 exits 0" 0
else
  assert "laia-backup clean 7 exits 0" 1
fi

assert "clean removes artifacts older than N days" \
  "$([[ ! -e "$LAIA_BACKUP_DIR/manual-old-artifact.tar.gz" ]] && echo 0 || echo 1)"
assert "clean keeps artifacts newer than N days" \
  "$([[ -e "$LAIA_BACKUP_DIR/manual-new-artifact.tar.gz" ]] && echo 0 || echo 1)"

echo
echo "-> D1 legacy backup paths are absent"
LEGACY_HERMES_NAME="laia-hermes"
assert "laia-backup source does not call pg_dump" \
  "$(! grep -q 'pg_dump' "$BACKUP_BIN" && echo 0 || echo 1)"
assert "laia-backup source/output does not mention arete" \
  "$(! grep -qi 'arete' "$BACKUP_BIN" "$TMPDIR_TEST/backup-all.out" "$TMPDIR_TEST/backup-clean.out" 2>/dev/null && echo 0 || echo 1)"
assert "laia-backup source/output has no legacy Hermes coupling" \
  "$(! grep -qi "$LEGACY_HERMES_NAME" "$BACKUP_BIN" "$TMPDIR_TEST/backup-all.out" "$TMPDIR_TEST/backup-clean.out" 2>/dev/null && echo 0 || echo 1)"

echo
echo "=================================================="
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  echo
  echo "Failures:"
  for f in "${FAILURES[@]}"; do
    printf "  - %s\n" "$f"
  done
  echo
  echo "Backup artifacts:"
  files_under "$LAIA_BACKUP_DIR" || true
  echo
  echo "laia-backup all output:"
  cat "$TMPDIR_TEST/backup-all.out" 2>/dev/null || true
  echo
  echo "laia-backup clean output:"
  cat "$TMPDIR_TEST/backup-clean.out" 2>/dev/null || true
  exit 1
fi
exit 0
