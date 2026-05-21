#!/usr/bin/env bash
# smoke-test.sh — end-to-end verification for deployed AGORA.

set -uo pipefail

SLUG="${SLUG:-jorge-dev}"
API_URL="${AGORA_API_URL:-http://127.0.0.1:8088}"
DRY_RUN=0
TIMEOUT_TESTS="${AGORA_SMOKE_TEST_TIMEOUT:-60}"
TIMEOUT_CHAT="${AGORA_SMOKE_CHAT_TIMEOUT:-30}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --slug) SLUG="$2"; shift 2;;
    --api-url) API_URL="$2"; shift 2;;
    --dry-run) DRY_RUN=1; shift;;
    -h|--help)
      sed -n '1,35p' "$0"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

API_URL="${API_URL%/}"
STATE_DIR="${LAIA_STATE_DIR:-$HOME/.laia/state}"
STATE_FILE="$STATE_DIR/laia-state-${SLUG}.json"
[[ -f "$STATE_FILE" ]] || STATE_FILE="/tmp/laia-state-${SLUG}.json"

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; RST='\033[0m'
else GRN=''; YEL=''; RED=''; CYN=''; RST=''; fi

FAILURES=()
ok() { printf "  ${GRN}✓${RST} %s\n" "$*"; }
log() { printf "${CYN}▸${RST} %s\n" "$*"; }
fail() { FAILURES+=("$*"); printf "  ${RED}✗${RST} %s\n" "$*" >&2; }
warn() { printf "  ${YEL}⚠${RST} %s\n" "$*"; }

need() {
  command -v "$1" >/dev/null 2>&1 || fail "$1 no encontrado"
}

if [[ "$DRY_RUN" -eq 1 ]]; then
  cat <<EOF
DRY RUN smoke-test
API:   $API_URL
Slug:  $SLUG
State: $STATE_FILE
Pasos:
  1. GET /api/health
  2. POST /api/login admin jorge/dev-admin
  3. GET /api/admin/status
  4. POST /api/admin/tests/run + poll job
  5. Login user desde state + POST /api/agents/me/chat SSE
EOF
  exit 0
fi

need curl
need jq
if [[ ${#FAILURES[@]} -gt 0 ]]; then
  exit 1
fi

log "1/5 health $API_URL/api/health"
if curl -fsS "$API_URL/api/health" >/tmp/laia-smoke-health.json 2>/tmp/laia-smoke-health.err; then
  ok "health responde"
else
  fail "health no responde: $(cat /tmp/laia-smoke-health.err 2>/dev/null)"
fi

log "2/5 login admin"
ADMIN_JSON="$(curl -fsS -X POST "$API_URL/api/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"jorge","password":"dev-admin"}' 2>/tmp/laia-smoke-admin.err || true)"
ADMIN_TOKEN="$(printf '%s' "$ADMIN_JSON" | jq -r '.access_token // empty' 2>/dev/null)"
if [[ -n "$ADMIN_TOKEN" ]]; then ok "admin token obtenido"; else fail "admin login falló: $(cat /tmp/laia-smoke-admin.err 2>/dev/null)"; fi

if [[ -n "$ADMIN_TOKEN" ]]; then
  log "3/5 admin status"
  STATUS_JSON="$(curl -fsS "$API_URL/api/admin/status" -H "Authorization: Bearer $ADMIN_TOKEN" 2>/tmp/laia-smoke-status.err || true)"
  if [[ -z "$STATUS_JSON" ]]; then
    err="$(cat /tmp/laia-smoke-status.err 2>/dev/null)"
    if grep -q '404' /tmp/laia-smoke-status.err 2>/dev/null; then
      fail "imagen no incluye control center, corre rebuild-2"
    else
      fail "admin status falló: $err"
    fi
  else
    if printf '%s' "$STATUS_JSON" | jq -e '.status.health.ok == true and (.status.containers.running >= 2) and (.status.users.total >= 1)' >/dev/null 2>&1; then
      ok "admin status saludable"
    else
      fail "admin status no cumple health.ok/containers/users: $(printf '%s' "$STATUS_JSON" | jq -c '.status' 2>/dev/null)"
    fi
  fi

  log "4/5 backend tests via /api/admin/tests/run"
  RUN_JSON="$(curl -fsS -X POST "$API_URL/api/admin/tests/run" -H "Authorization: Bearer $ADMIN_TOKEN" 2>/tmp/laia-smoke-tests.err || true)"
  JOB_ID="$(printf '%s' "$RUN_JSON" | jq -r '.job_id // empty' 2>/dev/null)"
  if [[ -z "$JOB_ID" ]]; then
    fail "no pude lanzar tests: $(cat /tmp/laia-smoke-tests.err 2>/dev/null)"
  else
    deadline=$((SECONDS + TIMEOUT_TESTS))
    JOB_JSON=""
    while [[ "$SECONDS" -le "$deadline" ]]; do
      JOB_JSON="$(curl -fsS "$API_URL/api/admin/jobs/$JOB_ID" -H "Authorization: Bearer $ADMIN_TOKEN" 2>/dev/null || true)"
      status="$(printf '%s' "$JOB_JSON" | jq -r '.job.status // empty' 2>/dev/null)"
      [[ "$status" == "done" || "$status" == "completed" || "$status" == "failed" ]] && break
      sleep 2
    done
    status="$(printf '%s' "$JOB_JSON" | jq -r '.job.status // empty' 2>/dev/null)"
    rc="$(printf '%s' "$JOB_JSON" | jq -r '.job.result.returncode // empty' 2>/dev/null)"
    if [[ ( "$status" == "done" || "$status" == "completed" ) && "$rc" == "0" ]]; then
      ok "tests job $JOB_ID verde"
    else
      fail "tests job $JOB_ID no terminó verde (status=${status:-?}, returncode=${rc:-?})"
    fi
  fi
fi

log "5/5 chat SSE como $SLUG"
if [[ ! -f "$STATE_FILE" ]]; then
  fail "no encuentro state de user: $STATE_FILE"
else
  USERNAME="$(jq -r '.username // .slug // empty' "$STATE_FILE")"
  PASSWORD="$(jq -r '.password // empty' "$STATE_FILE")"
  if [[ -z "$USERNAME" || -z "$PASSWORD" ]]; then
    fail "state sin username/password: $STATE_FILE"
  else
    USER_JSON="$(curl -fsS -X POST "$API_URL/api/login" \
      -H 'Content-Type: application/json' \
      -d "$(jq -nc --arg u "$USERNAME" --arg p "$PASSWORD" '{username:$u,password:$p}')" 2>/tmp/laia-smoke-user.err || true)"
    USER_TOKEN="$(printf '%s' "$USER_JSON" | jq -r '.access_token // empty' 2>/dev/null)"
    if [[ -z "$USER_TOKEN" ]]; then
      fail "login user $USERNAME falló: $(cat /tmp/laia-smoke-user.err 2>/dev/null)"
    else
      STREAM="$(timeout "$TIMEOUT_CHAT" curl -sN -X POST "$API_URL/api/agents/me/chat" \
        -H "Authorization: Bearer $USER_TOKEN" \
        -H 'Content-Type: application/json' \
        -d "$(jq -nc --arg m "di hola" --arg s "smoke-$SLUG" '{message:$m,session_id:$s}')" 2>/tmp/laia-smoke-chat.err || true)"
      if printf '%s' "$STREAM" | grep -q "AIAgent placeholder cannot run a conversation"; then
        fail "venv del container sin .laia-core instalado, aplicar fix pip-reinstall-laia-core"
      elif printf '%s' "$STREAM" | grep -q '"type"[[:space:]]*:[[:space:]]*"error"'; then
        fail "chat devolvió error: $(printf '%s' "$STREAM" | tail -5)"
      elif printf '%s' "$STREAM" | grep -Eq '"type"[[:space:]]*:[[:space:]]*"(token|done|assistant_message)"'; then
        ok "chat emitió stream de assistant"
      else
        fail "chat no emitió assistant antes de ${TIMEOUT_CHAT}s"
      fi
    fi
  fi
fi

if [[ ${#FAILURES[@]} -eq 0 ]]; then
  printf "\n${GRN}✓ Smoke test verde.${RST}\n"
  exit 0
fi

printf "\n${RED}Smoke test falló:${RST}\n" >&2
for item in "${FAILURES[@]}"; do
  printf " - %s\n" "$item" >&2
done
exit 1
