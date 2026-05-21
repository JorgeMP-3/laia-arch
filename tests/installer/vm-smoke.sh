#!/usr/bin/env bash
set -euo pipefail

API="${AGORA_API:-http://127.0.0.1:8088}"
DB="${AGORA_DB:-/srv/laia/agora/agora.db}"

fail() { printf '✗ %s\n' "$*" >&2; exit 1; }
ok() { printf '✓ %s\n' "$*"; }

command -v lxc >/dev/null 2>&1 || fail "lxc not found"
command -v curl >/dev/null 2>&1 || fail "curl not found"

lxc info laia-agora >/dev/null 2>&1 || fail "laia-agora missing"
lxc list laia-agora | grep -q RUNNING || fail "laia-agora not RUNNING"
ok "laia-agora RUNNING"

curl -fsS "$API/api/health" >/dev/null || fail "$API/api/health failed"
ok "/api/health responds"

if [[ -f "$DB" ]] && command -v sqlite3 >/dev/null 2>&1; then
  users="$(sqlite3 "$DB" 'select count(*) from users;' 2>/dev/null || echo 0)"
  skills="$(sqlite3 "$DB" 'select count(*) from skill_registry;' 2>/dev/null || echo 0)"
  [[ "$users" -ge 1 ]] || fail "users table is empty"
  [[ "$skills" -ge 10 ]] || fail "skill_registry has fewer than 10 skills"
  ok "agora.db users=$users skills=$skills"

  while IFS= read -r slug; do
    [[ -n "$slug" ]] || continue
    lxc list "agent-$slug" | grep -q RUNNING || fail "agent-$slug not RUNNING"
    ok "agent-$slug RUNNING"
  done < <(sqlite3 "$DB" "select username from users where coalesce(active,1)=1 and role <> 'agora_admin';")
else
  printf '⚠ skipping DB assertions; sqlite3 or %s missing\n' "$DB" >&2
fi
