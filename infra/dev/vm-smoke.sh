#!/usr/bin/env bash
set -euo pipefail

DB="${AGORA_DB:-/srv/laia/agora/agora.db}"

fail() { printf '✗ %s\n' "$*" >&2; exit 1; }
ok() { printf '✓ %s\n' "$*"; }

command -v lxc >/dev/null 2>&1 || fail "lxc not found"
command -v curl >/dev/null 2>&1 || fail "curl not found"

lxc info laia-agora >/dev/null 2>&1 || fail "laia-agora missing"
lxc list laia-agora | grep -q RUNNING || fail "laia-agora not RUNNING"
ok "laia-agora RUNNING"

# API base: explicit AGORA_API wins; otherwise probe localhost (single-host
# installs) and then the laia-agora container IP — the brain listens inside
# the container, not on the host loopback (the old 127.0.0.1:8088 default
# pre-dates the container topology). IP via csv, jq-free (see
# problems.md::d2-health-check-requiere-jq-y-privilegios-lxc).
resolve_api() {
  # Explicit override: honored, but still probed — an unreachable override
  # must fail loud, never report a green health it did not check.
  if [[ -n "${AGORA_API:-}" ]]; then
    if curl -fsS --max-time 3 "${AGORA_API}/api/health" >/dev/null 2>&1; then
      echo "$AGORA_API"; return 0
    fi
    return 1
  fi
  local cand ip
  for cand in "http://127.0.0.1:8088" "http://127.0.0.1:8000"; do
    if curl -fsS --max-time 3 "$cand/api/health" >/dev/null 2>&1; then
      echo "$cand"; return 0
    fi
  done
  ip="$(lxc list laia-agora -c4 --format csv 2>/dev/null | awk '{print $1}' | head -1)"
  if [[ -n "$ip" ]]; then
    for cand in "http://$ip:8000" "http://$ip:8088"; do
      if curl -fsS --max-time 3 "$cand/api/health" >/dev/null 2>&1; then
        echo "$cand"; return 0
      fi
    done
  fi
  return 1
}

API="$(resolve_api)" \
  || fail "AGORA API unreachable (tried localhost + container IP; set AGORA_API=http://<ip>:<port> to override)"
ok "/api/health responds ($API)"

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
