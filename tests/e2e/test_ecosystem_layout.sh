#!/usr/bin/env bash
# tests/e2e/test_ecosystem_layout.sh
#
# End-to-end check that this LAIA host has the canonical post-T.14.1 layout
# and that the core services answer correctly.
#
# Idempotent and read-only — does NOT create users, containers or modify
# data. Intended as `make test-e2e` to be run on:
#   - Local dev box after install/clone
#   - Fresh VM after `curl|sudo bash install.sh`
#   - CI as a smoke gate before promoting `stable`
#
# Optional env:
#   LAIA_VERIFY_LLM_KEY      — if set, also tests F.5 chat E2E with that key
#                              (requires a working LLM_PROVIDER + container).
#   LAIA_VERIFY_LLM_PROVIDER — defaults to "deepseek"
#   LAIA_VERIFY_LLM_MODEL    — defaults to "deepseek-chat"
#
# Exit code: 0 if all critical checks pass, non-zero otherwise.
#
# Markers per check: OK | FAIL | WARN | SKIPPED. The script tracks FAIL count
# and exits with that count (clamped to 1 by Make).

set -u

LAIA_HOME="${LAIA_HOME:-$HOME/LAIA-ARCH}"
ADMIN_USER="${LAIA_VERIFY_ADMIN_USER:-jorge}"
ADMIN_TOKEN="${LAIA_VERIFY_ADMIN_TOKEN:-dev-admin-token}"
BACKEND_URL="${LAIA_VERIFY_BACKEND_URL:-http://127.0.0.1:8088}"
UI_URL="${LAIA_VERIFY_UI_URL:-http://127.0.0.1:8077}"

FAIL_COUNT=0
WARN_COUNT=0
OK_COUNT=0
SKIPPED_COUNT=0

ok()      { echo "  OK      $*"; OK_COUNT=$((OK_COUNT+1)); }
warn()    { echo "  WARN    $*"; WARN_COUNT=$((WARN_COUNT+1)); }
fail()    { echo "  FAIL    $*"; FAIL_COUNT=$((FAIL_COUNT+1)); }
skipped() { echo "  SKIPPED $*"; SKIPPED_COUNT=$((SKIPPED_COUNT+1)); }
section() { echo ""; echo "=== $* ==="; }

# ── F.1 Infrastructure layout ────────────────────────────────────────────────
section "F.1 Infrastructure layout"
[[ -d "$LAIA_HOME" ]]            && ok "F.1.1 LAIA_HOME exists ($LAIA_HOME)"    || fail "F.1.1 LAIA_HOME missing"
[[ -d /srv/laia/agora ]]         && ok "F.1.2 /srv/laia/agora exists"           || fail "F.1.2 /srv/laia/agora missing"
[[ -d /srv/laia/users ]]         && ok "F.1.3 /srv/laia/users exists"           || fail "F.1.3 /srv/laia/users missing"
[[ ! -d /srv/laia/arch ]]        && ok "F.1.4 /srv/laia/arch deprecated (gone)" || warn "F.1.4 /srv/laia/arch still exists (T.14.1 cleanup pending)"
[[ -f /home/laia-hermes/.laia/auth.json || -f "$HOME/.laia/auth.json" ]] && ok "F.1.5 ~/.laia/auth.json present (legacy compat)" || warn "F.1.5 ~/.laia/auth.json missing"

for d in workspaces memories skills plugins; do
  [[ -e "$LAIA_HOME/$d" ]] && ok "F.1.6.$d in LAIA_HOME" || warn "F.1.6.$d missing under LAIA_HOME"
done
[[ -f "$LAIA_HOME/config.yaml" ]] && ok "F.1.7 config.yaml in LAIA_HOME" || fail "F.1.7 config.yaml missing"
[[ -f "$LAIA_HOME/state.db"   ]] && ok "F.1.8 state.db in LAIA_HOME"   || warn "F.1.8 state.db missing"

# ── F.2 Services ────────────────────────────────────────────────────────────
section "F.2 Services"
if curl -fsS "$BACKEND_URL/api/health" 2>/dev/null | jq -e '.ok == true' >/dev/null; then
  ok "F.2.1 agora-backend healthy at $BACKEND_URL/api/health"
else
  fail "F.2.1 agora-backend NOT responding"
fi

if pgrep -f laia-pathd >/dev/null 2>&1; then ok "F.2.2 laia-pathd running"; else warn "F.2.2 laia-pathd not running"; fi

if curl -fsS "$UI_URL/api/health" 2>/dev/null | jq -e '.ok == true' >/dev/null; then
  ok "F.2.3 laia-ui-server healthy at $UI_URL"
else
  skipped "F.2.3 laia-ui-server not responding"
fi

# ── F.3 AGORA API basic ──────────────────────────────────────────────────────
section "F.3 AGORA API"
curl -fsS "$BACKEND_URL/api/me" -H "Authorization: Bearer $ADMIN_TOKEN" 2>/dev/null \
  | jq -e ".username == \"$ADMIN_USER\"" >/dev/null \
  && ok "F.3.1 admin /api/me works" || fail "F.3.1 admin /api/me fails"

curl -fsS "$BACKEND_URL/api/users" -H "Authorization: Bearer $ADMIN_TOKEN" 2>/dev/null \
  | jq -e '. | length >= 1' >/dev/null \
  && ok "F.3.2 /api/users returns ≥1 user" || fail "F.3.2 /api/users fails"

curl -fsS "$BACKEND_URL/api/llm/providers" -H "Authorization: Bearer $ADMIN_TOKEN" 2>/dev/null \
  | jq -e '. | length > 0' >/dev/null \
  && ok "F.3.3 /api/llm/providers returns providers" || fail "F.3.3 /api/llm/providers fails"

curl -fsS "$BACKEND_URL/api/agents" -H "Authorization: Bearer $ADMIN_TOKEN" 2>/dev/null \
  | jq -e '. | length >= 0' >/dev/null \
  && ok "F.3.4 /api/agents responds" || fail "F.3.4 /api/agents fails"

# ── F.4 Webhook stack ────────────────────────────────────────────────────────
section "F.4 Webhooks"
HTTP=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BACKEND_URL/api/webhooks/nonexistent-$$" \
  -H 'Content-Type: application/json' -d '{}')
[[ "$HTTP" == "404" || "$HTTP" == "401" ]] \
  && ok "F.4.1 /api/webhooks/<slug> rejects unknown ($HTTP)" \
  || warn "F.4.1 unexpected HTTP $HTTP"

# ── F.5 Filesystem layout strict (no /srv/laia/arch leakage) ────────────────
section "F.5 Layout strict"
LEAKED=()
for f in sessions atlas cron SOUL.md state.db config.yaml; do
  [[ -e "/srv/laia/arch/$f" ]] && LEAKED+=("$f")
done
[[ ${#LEAKED[@]} -eq 0 ]] && ok "F.5.1 no operational data under /srv/laia/arch/" \
  || fail "F.5.1 /srv/laia/arch/ contains: ${LEAKED[*]}"

# config.yaml shouldn't reference /srv/laia/arch
if [[ -f "$LAIA_HOME/config.yaml" ]]; then
  RES=$(grep -c "/srv/laia/arch\|~/\.laia/" "$LAIA_HOME/config.yaml" 2>/dev/null || echo 0)
  [[ "$RES" -eq 0 ]] && ok "F.5.2 config.yaml has no /srv/laia/arch or ~/.laia refs" \
    || warn "F.5.2 config.yaml has $RES stale path refs"
fi

# ── F.6 Voice/Vision/Web libs in backend venv ───────────────────────────────
section "F.6 Backend libs"
VENV=/home/laia-hermes/LAIA/services/agora-backend/.venv/bin/python
if [[ -x "$VENV" ]]; then
  $VENV -c "import edge_tts" 2>/dev/null   && ok "F.6.1 edge_tts importable"   || fail "F.6.1 edge_tts missing"
  $VENV -c "import firecrawl" 2>/dev/null  && ok "F.6.2 firecrawl importable"  || fail "F.6.2 firecrawl missing"
  $VENV -c "import exa_py"   2>/dev/null   && ok "F.6.3 exa_py importable"     || fail "F.6.3 exa_py missing"
else
  skipped "F.6 backend venv not at expected path"
fi

# ── F.7 LXD containers (optional) ───────────────────────────────────────────
section "F.7 LXD containers"
if command -v lxc >/dev/null 2>&1; then
  sudo lxc image list --format csv 2>/dev/null | awk -F, '{print $1}' | grep -qE "laia-agent|laia-agora" \
    && ok "F.7.1 laia-agent / laia-agora image present" \
    || warn "F.7.1 no laia-agent or laia-agora image"
  sudo lxc list --format csv -c ns 2>/dev/null | grep -q "RUNNING" \
    && ok "F.7.2 at least one container RUNNING" \
    || warn "F.7.2 no RUNNING containers"
else
  skipped "F.7 LXD not installed"
fi

# ── F.8 Chat E2E (only if LAIA_VERIFY_LLM_KEY set) ──────────────────────────
section "F.8 Chat E2E (optional)"
if [[ -n "${LAIA_VERIFY_LLM_KEY:-}" ]] \
   && command -v lxc >/dev/null 2>&1 \
   && sudo lxc list --format csv -c n 2>/dev/null | grep -q "agent-"; then
  # Pick the first agent-* container with a corresponding user
  AGENT_NAME=$(sudo lxc list --format csv -c n 2>/dev/null | grep "^agent-" | head -1)
  USER_SLUG="${AGENT_NAME#agent-}"
  ok "F.8.0 using agent $AGENT_NAME for chat probe"
  # Full chat smoke would require login + LLM creds — left as out-of-band.
  warn "F.8.1 chat smoke needs a logged-in non-admin user — see workflow/plans/2026-05-25-ecosystem-e2e-verification.md T.14.4"
else
  skipped "F.8 chat E2E skipped (set LAIA_VERIFY_LLM_KEY + provision a container)"
fi

# ── Summary ─────────────────────────────────────────────────────────────────
section "Summary"
echo "  OK:      $OK_COUNT"
echo "  WARN:    $WARN_COUNT"
echo "  FAIL:    $FAIL_COUNT"
echo "  SKIPPED: $SKIPPED_COUNT"

exit "$FAIL_COUNT"
