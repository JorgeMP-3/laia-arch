#!/usr/bin/env bash
# integrity:id=cross_consistency_reconciler
# integrity:name=T4 cross-consistency reconciler (fixture)
# integrity:level=unit
# integrity:layers=cross,data
# integrity:profiles=ci,host,vm
# integrity:requires=python3,sqlite3
# integrity:timeout=45
#
# T4 unit test. Builds a synthetic agora.db + user-zone + container inventory
# with deliberate orphans in every direction, then asserts the reconciler
# catches exactly those orphans and reports a clean system as clean. Hermetic:
# never touches LXD or the live ecosystem.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../lib/integrity_shell.sh
source "$SCRIPT_DIR/../../lib/integrity_shell.sh"

require_cmds python3 sqlite3

RECONCILE="$INTEGRITY_REPO_ROOT/tests/integration/lib/reconcile.py"
assert_file "$RECONCILE"

FIX="$(mktemp -d "${TMPDIR:-/tmp}/laia-t4.XXXXXX")"
trap 'rm -rf "$FIX"' EXIT

DB="$FIX/agora.db"
USERS="$FIX/users"
mkdir -p "$USERS"

# ── Build a synthetic agora.db with the real users/agents shape ──────────────
sqlite3 "$DB" <<'SQL'
CREATE TABLE users (
  id TEXT PRIMARY KEY, username TEXT, display_name TEXT, role TEXT,
  agent_id TEXT, token TEXT, password TEXT, active INTEGER,
  created_at TEXT, updated_at TEXT
);
CREATE TABLE agents (
  id TEXT PRIMARY KEY, user_id TEXT, container_name TEXT, status TEXT,
  workspace_path TEXT, created_at TEXT, updated_at TEXT
);
-- maria: fully consistent (running, has container + fs dir).
INSERT INTO users VALUES ('u_maria','maria','Maria','employee','a_maria','t1','p',1,'now','now');
INSERT INTO agents VALUES ('a_maria','u_maria','agent-maria','running','/srv/laia/users/maria/workspace','now','now');
-- bob: running in DB but NO container and NO fs dir (interrupted provision).
INSERT INTO users VALUES ('u_bob','bob','Bob','employee','a_bob','t2','p',1,'now','now');
INSERT INTO agents VALUES ('a_bob','u_bob','agent-bob','running','/srv/laia/users/bob/workspace','now','now');
-- carol: only planned → no container/fs expected (must NOT be an orphan).
INSERT INTO users VALUES ('u_carol','carol','Carol','employee','a_carol','t3','p',1,'now','now');
INSERT INTO agents VALUES ('a_carol','u_carol','agent-carol','planned','/srv/laia/users/carol/workspace','now','now');
SQL

# maria's fs dir exists; an orphan fs dir 'ghost' has no DB row.
mkdir -p "$USERS/maria/home" "$USERS/maria/workspace"
mkdir -p "$USERS/ghost/home"

# Container inventory: maria present (consistent); 'agent-rogue' has no DB row;
# reserved containers must be ignored.
cat >"$FIX/containers.txt" <<'EOF'
laia-agora
agent-maria
agent-rogue
EOF

OUT="$FIX/report.json"
set +e
python3 "$RECONCILE" --db "$DB" --users-dir "$USERS" --containers-file "$FIX/containers.txt" --json "$OUT" >"$FIX/run.out" 2>&1
rc=$?
set -e
[[ "$rc" == "1" ]] || integ_fail "reconciler should exit 1 with seeded orphans (got $rc): $(cat "$FIX/run.out")"

python3 - "$OUT" <<'PY' || integ_fail "reconciler did not report the expected orphan set"
import json
import sys

doc = json.load(open(sys.argv[1], encoding="utf-8"))
assert doc["db_provisioned_without_container"] == ["bob"], doc
assert doc["db_provisioned_without_fs"] == ["bob"], doc
assert doc["container_without_db_agent"] == ["agent-rogue"], doc
assert doc["fs_dir_without_db"] == ["ghost"], doc
# 'carol' is planned → must not appear anywhere; reserved laia-agora ignored.
flat = (
    doc["db_provisioned_without_container"]
    + doc["db_provisioned_without_fs"]
    + doc["container_without_db_agent"]
    + doc["fs_dir_without_db"]
)
assert "carol" not in flat, doc
assert "laia-agora" not in doc["container_without_db_agent"], doc
PY
integ_info "reconciler catches orphans in all four directions"

# ── Now make it fully consistent and assert a clean exit 0 ───────────────────
rm -rf "$USERS/ghost"
mkdir -p "$USERS/bob/home" "$USERS/bob/workspace"
cat >"$FIX/containers_ok.txt" <<'EOF'
agent-maria
agent-bob
EOF
if python3 "$RECONCILE" --db "$DB" --users-dir "$USERS" --containers-file "$FIX/containers_ok.txt" >/dev/null 2>&1; then
  integ_info "reconciler reports a consistent system as clean"
else
  integ_fail "reconciler should exit 0 once DB/FS/containers agree"
fi

integ_info "T4 reconciler OK"
