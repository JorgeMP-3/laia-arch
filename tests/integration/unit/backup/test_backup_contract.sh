#!/usr/bin/env bash
# integrity:id=backup_contract_fixture
# integrity:name=Backup contract fixture
# integrity:level=unit
# integrity:layers=backups
# integrity:profiles=ci,host,vm
# integrity:requires=python3
# integrity:timeout=45
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../lib/integrity_shell.sh
source "$SCRIPT_DIR/../../lib/integrity_shell.sh"

BACKUP_BIN="$INTEGRITY_REPO_ROOT/infra/bin/laia-backup"
[[ -x "$BACKUP_BIN" ]] || integ_fail "missing executable: $BACKUP_BIN"

files_under() {
  find "$1" -type f -printf '%P\n' 2>/dev/null | sort
}

contains_file_matching() {
  local root="$1" pattern="$2"
  files_under "$root" | grep -Eiq "$pattern"
}

TMPDIR_TEST="$(mktemp -d "${TMPDIR:-/tmp}/laia-integrity-backup.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

export NO_COLOR=1
export LAIA_BACKUP_DIR="$TMPDIR_TEST/backups"

SRV_ROOT="$TMPDIR_TEST/srv/laia"
AGORA_DIR="$SRV_ROOT/agora"
USERS_DIR="$SRV_ROOT/users"
ARCH_DIR="$SRV_ROOT/arch"

mkdir -p "$AGORA_DIR" "$USERS_DIR/jorge/home" "$ARCH_DIR/secrets" "$LAIA_BACKUP_DIR"
printf 'sqlite fixture\n' >"$AGORA_DIR/agora.db"
printf 'user fixture\n' >"$USERS_DIR/jorge/home/readme.txt"
printf 'arch state fixture\n' >"$ARCH_DIR/state.db"
printf '{"provider":"test"}\n' >"$ARCH_DIR/secrets/auth.json"

export LAIA_AGORA_DIR_OVERRIDE="$AGORA_DIR"
export LAIA_USERS_DIR_OVERRIDE="$USERS_DIR"
export LAIA_ARCH_DIR_OVERRIDE="$ARCH_DIR"
export AGORA_DB="$AGORA_DIR/agora.db"

timeout 30 "$BACKUP_BIN" all >"$TMPDIR_TEST/backup-all.out" 2>&1 \
  || integ_fail "laia-backup all failed: $(tail -20 "$TMPDIR_TEST/backup-all.out" | tr '\n' ' ')"

contains_file_matching "$LAIA_BACKUP_DIR" '(^|/)agora[^/]*\.(db|sqlite|tar|tgz|tar\.gz|zst|backup)$' \
  || integ_fail "missing agora backup artifact"
contains_file_matching "$LAIA_BACKUP_DIR" '(^|/)users?[^/]*\.(tar|tgz|tar\.gz|zst|backup)$' \
  || integ_fail "missing users backup artifact"
contains_file_matching "$LAIA_BACKUP_DIR" '(^|/)arch[^/]*\.(tar|tgz|tar\.gz|zst|backup)$' \
  || integ_fail "missing arch backup artifact"

integ_info "backup contract OK in tmp fixture"
