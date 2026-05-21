#!/usr/bin/env bash
# Test: fact_reset_imported_admin_password against a fresh sqlite fixture.
#
# Creates a minimal agora.db with an agora_admin user, runs the function,
# and asserts:
#   * password column has changed to a pbkdf2 hash matching backend security.py
#   * $DATA_DIR/.admin-credentials exists with mode 600
#   * AGORA_ADMIN_USERNAME / AGORA_ADMIN_PASSWORD are exported and verify
#     against the stored hash (round-trip via the backend's verify_password).
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
PASS=0; FAIL=0; FAILURES=()
assert() { local d="$1" s="$2"; if [[ "$s" == 0 ]]; then PASS=$((PASS+1)); printf '  ✓ %s\n' "$d"; else FAIL=$((FAIL+1)); FAILURES+=("$d"); printf '  ✗ %s\n' "$d"; fi; }

command -v sqlite3 >/dev/null 2>&1 || { echo "sqlite3 not installed — skipping"; exit 0; }
command -v python3 >/dev/null 2>&1 || { echo "python3 not installed — skipping"; exit 0; }

TMPDIR_TEST="$(mktemp -d "${HOME}/laia-admin-reset.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

AGORA_DIR="$TMPDIR_TEST/srv/agora"
DATA_DIR_TEST="$TMPDIR_TEST/LAIA-ARCH"
mkdir -p "$AGORA_DIR" "$DATA_DIR_TEST"

# Build minimal users table matching services/agora-backend/app/database.py:7-28
sqlite3 "$AGORA_DIR/agora.db" "
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'employee',
    agent_id TEXT,
    token TEXT,
    password TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
INSERT INTO users (id, username, display_name, role, password, active, created_at, updated_at)
VALUES ('u1', 'someadmin', 'Some Admin', 'agora_admin', '\$pbkdf2\$aabbcc\$ddeeff', 1, datetime('now'), datetime('now'));
INSERT INTO users (id, username, display_name, role, password, active, created_at, updated_at)
VALUES ('u2', 'jorge', 'Jorge', 'employee', '\$pbkdf2\$11\$22', 1, datetime('now'), datetime('now'));
"
ORIG_HASH="$(sqlite3 "$AGORA_DIR/agora.db" "select password from users where username='someadmin';")"

export NO_COLOR=1
export LAIA_HOME_OVERRIDE="$DATA_DIR_TEST"
export LAIA_AGORA_DIR_OVERRIDE="$AGORA_DIR"
export AGORA_DB_PATH="$AGORA_DIR/agora.db"

# Pull in lib stack mimicking what bin/laia-clone sources.
# shellcheck source=/dev/null
source "$LAIA_ROOT/infra/installer/lib/common.sh"
# shellcheck source=/dev/null
source "$LAIA_ROOT/infra/installer/lib/sudo.sh"
# shellcheck source=/dev/null
source "$LAIA_ROOT/infra/installer/lib/version.sh"
# shellcheck source=/dev/null
source "$LAIA_ROOT/infra/installer/lib/install.sh"
# shellcheck source=/dev/null
source "$LAIA_ROOT/infra/installer/lib/factory.sh"

# inst_compute_paths needs OPT_VERSION; fake it.
OPT_VERSION=v0.0.0-test
inst_compute_paths

fact_reset_imported_admin_password >"$TMPDIR_TEST/reset.log" 2>&1
rc=$?
assert "fact_reset_imported_admin_password exits 0" "$rc"

NEW_HASH="$(sqlite3 "$AGORA_DIR/agora.db" "select password from users where username='someadmin';")"
assert "admin password hash changed" "$([[ -n "$NEW_HASH" && "$NEW_HASH" != "$ORIG_HASH" ]] && echo 0 || echo 1)"
assert "hash format is pbkdf2" "$([[ "$NEW_HASH" == \$pbkdf2\$* ]] && echo 0 || echo 1)"
assert "non-admin user unchanged" "$([[ "$(sqlite3 "$AGORA_DIR/agora.db" "select password from users where username='jorge';")" == '$pbkdf2$11$22' ]] && echo 0 || echo 1)"
assert ".admin-credentials exists" "$([[ -f "$DATA_DIR_TEST/.admin-credentials" ]] && echo 0 || echo 1)"
assert ".admin-credentials mode 600" "$([[ "$(stat -c %a "$DATA_DIR_TEST/.admin-credentials" 2>/dev/null)" == "600" ]] && echo 0 || echo 1)"
assert "AGORA_ADMIN_USERNAME exported = someadmin" "$([[ "$AGORA_ADMIN_USERNAME" == "someadmin" ]] && echo 0 || echo 1)"
assert "AGORA_ADMIN_PASSWORD non-empty" "$([[ -n "$AGORA_ADMIN_PASSWORD" ]] && echo 0 || echo 1)"

# Round-trip: verify the exported password validates against the stored hash
# using the same algorithm as backend security.py::verify_password.
verified="$(python3 -c '
import hashlib, hmac, sys
plain = sys.argv[1]
hashed = sys.argv[2]
if not hashed.startswith("$pbkdf2$"):
    print("no")
    sys.exit(0)
_, _, salt_hex, dk_hex = hashed.split("$", 3)
salt = bytes.fromhex(salt_hex)
expected = bytes.fromhex(dk_hex)
actual = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, 600_000)
print("yes" if hmac.compare_digest(actual, expected) else "no")
' "$AGORA_ADMIN_PASSWORD" "$NEW_HASH")"
assert "verify_password round-trip succeeds" "$([[ "$verified" == "yes" ]] && echo 0 || echo 1)"

printf '\nPASS: %d FAIL: %d\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then printf '%s\n' "${FAILURES[@]}"; cat "$TMPDIR_TEST/reset.log"; exit 1; fi
