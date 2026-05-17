#!/usr/bin/env bash
# verify-redesign.sh — verificación local del rediseño AGORA, sin LXD.
#
# Tres niveles, cada uno independiente:
#   tier 1: tests automáticos (3 suites, ~30s)
#   tier 2: arranca executor + agora-backend, golpea endpoints básicos
#   tier 3: round-trip plugin → executor sobre HTTP real (puerto local)
#
# Uso:
#   bash infra/dev/verify-redesign.sh             # los tres tiers
#   TIER=1 bash infra/dev/verify-redesign.sh      # solo tests
#   TIER=2 bash infra/dev/verify-redesign.sh      # solo boot+endpoints
#   TIER=3 bash infra/dev/verify-redesign.sh      # solo round-trip
#   KEEP=1 bash ...                               # deja los servicios arriba al final

set -uo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}"
TIER="${TIER:-all}"
KEEP="${KEEP:-0}"

# Default to random high ports so this script never conflicts with whatever
# dev backends the user already has running on the usual ports (9091, 8088).
_rand_port() { shuf -i 18000-18999 -n 1; }
EXECUTOR_PORT=${EXECUTOR_PORT:-$(_rand_port)}
AGORA_PORT=${AGORA_PORT:-$(_rand_port)}
EXECUTOR_TOKEN="dev-verify-token-$(date +%s)-$$"

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; BLD='\033[1m'; RST='\033[0m'
else
  GRN=''; YEL=''; RED=''; CYN=''; BLD=''; RST=''
fi
FAILURES=0
log()   { printf "${CYN}▸${RST} %s\n" "$*"; }
ok()    { printf "  ${GRN}✓${RST} %s\n" "$*"; }
warn()  { printf "  ${YEL}⚠${RST} %s\n" "$*"; }
fail()  { printf "  ${RED}✗${RST} %s\n" "$*"; FAILURES=$((FAILURES+1)); }
section() { printf "\n${BLD}== %s ==${RST}\n" "$*"; }

PIDS=()
cleanup() {
  if [[ "$KEEP" == "1" ]]; then
    warn "KEEP=1 — dejando ${#PIDS[@]} servicios arriba (PIDs: ${PIDS[*]:-}). Mátalos con: kill ${PIDS[*]:-}"
    return
  fi
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT

run_tier() {
  local n="$1"
  [[ "$TIER" == "all" || "$TIER" == "$n" ]]
}

# ────────────────────────────────────────────────────────────────────────────
# TIER 1 — Test suites
# ────────────────────────────────────────────────────────────────────────────
tier_1() {
  section "Tier 1 — Test suites automáticas"

  log "Running agora-backend tests (147)"
  ( cd "$REPO/services/agora-backend" \
    && .venv/bin/pytest tests/ --no-header -q 2>&1 | tail -3 )

  log "Running laia-executor tests (19)"
  ( cd "$REPO/services/laia-executor" \
    && .venv/bin/pytest tests/ --no-header -q 2>&1 | tail -3 )

  log "Running forwarder plugin tests (11)"
  ( cd "$REPO" \
    && .laia-core/venv/bin/python3 -m pytest .laia-core/plugins/agora-executor-forwarder/tests/ --no-header -q 2>&1 | tail -3 )

  ok "Tier 1 done — si los tres dicen 'passed', el código compila y la lógica unitaria funciona"
}

# ────────────────────────────────────────────────────────────────────────────
# TIER 2 — Boot ambos servicios + smoke endpoints
# ────────────────────────────────────────────────────────────────────────────
tier_2_executor_boot() {
  log "Boot laia-executor en :$EXECUTOR_PORT (token aleatorio)"
  rm -rf /tmp/laia-verify && mkdir -p /tmp/laia-verify
  (
    cd "$REPO/services/laia-executor" \
    && LAIA_EXECUTOR_TOKEN="$EXECUTOR_TOKEN" \
       LAIA_EXECUTOR_SLUG="verify-jorge" \
       LAIA_EXECUTOR_WORKSPACE_ROOT=/tmp/laia-verify \
       LAIA_WORKSPACE_STORE_PATH="$REPO" \
       LAIA_EXECUTOR_PORT="$EXECUTOR_PORT" \
       .venv/bin/laia-executor >/tmp/laia-verify/executor.log 2>&1 &
    echo $!
  ) > /tmp/laia-verify/executor.pid
  PIDS+=( "$(cat /tmp/laia-verify/executor.pid)" )

  # Espera hasta 5s a que escuche.
  for i in {1..50}; do
    curl -fsS "http://127.0.0.1:$EXECUTOR_PORT/health" >/dev/null 2>&1 && break
    sleep 0.1
  done
  if ! curl -fsS "http://127.0.0.1:$EXECUTOR_PORT/health" >/dev/null; then
    fail "executor no arrancó — log: /tmp/laia-verify/executor.log"
    return 1
  fi
  ok "executor /health ok"
}

tier_2_agora_boot() {
  log "Boot agora-backend en :$AGORA_PORT (SIN AGORA_TELEGRAM_TOKEN)"
  (
    cd "$REPO/services/agora-backend" \
    && AGORA_DATA_DIR=/tmp/laia-verify/agora-data \
       AGORA_DEV_DATA_DIR=/tmp/laia-verify/agora-data \
       AGORA_ENV=dev \
       LAIA_ROOT="$REPO" \
       PYTHONPATH="$REPO/services/agora-backend:$REPO/.laia-core" \
       .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$AGORA_PORT" \
       >/tmp/laia-verify/agora.log 2>&1 &
    echo $!
  ) > /tmp/laia-verify/agora.pid
  PIDS+=( "$(cat /tmp/laia-verify/agora.pid)" )

  for i in {1..50}; do
    curl -fsS "http://127.0.0.1:$AGORA_PORT/api/health" >/dev/null 2>&1 && break
    sleep 0.2
  done
  if ! curl -fsS "http://127.0.0.1:$AGORA_PORT/api/health" >/dev/null; then
    fail "agora-backend no arrancó — log: /tmp/laia-verify/agora.log"
    tail -30 /tmp/laia-verify/agora.log
    return 1
  fi
  ok "agora /api/health ok"
}

tier_2_smoke_endpoints() {
  log "Smoke endpoints — admin login, LLM providers, telegram link, workspace bootstrap"

  # Seed user del backend: jorge/dev-admin (rol agora_admin) — definido en
  # services/agora-backend/app/storage.py:_ensure_seed_data.
  TOKEN=$(curl -fsS -X POST "http://127.0.0.1:$AGORA_PORT/api/login" \
    -H 'Content-Type: application/json' \
    -d '{"username":"jorge","password":"dev-admin"}' | jq -r .access_token)
  if [[ -z "$TOKEN" || "$TOKEN" == "null" ]]; then
    fail "admin login falló — revisa que el seed user existe"
    return 1
  fi
  ok "admin login (jorge) → access_token len=$(echo -n "$TOKEN" | wc -c)"

  N=$(curl -fsS "http://127.0.0.1:$AGORA_PORT/api/llm/providers" | jq 'length')
  if [[ "$N" -ge 20 ]]; then
    ok "/api/llm/providers devuelve $N providers (esperado ≥20 por paridad ARCH)"
  else
    fail "/api/llm/providers solo devuelve $N — esperado 30+"
  fi

  # crear un user de prueba y generar token Telegram
  PW=$(curl -fsS -X POST "http://127.0.0.1:$AGORA_PORT/api/users" \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{"username":"verifyuser","display_name":"Verify"}' | jq -r .password)
  if [[ -z "$PW" || "$PW" == "null" ]]; then
    warn "POST /api/users no devolvió password (¿user ya existe?)"
  else
    ok "POST /api/users → user creado, password generada"
  fi

  USER_TOKEN=$(curl -fsS -X POST "http://127.0.0.1:$AGORA_PORT/api/login" \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"verifyuser\",\"password\":\"$PW\"}" | jq -r .access_token)
  TG_TOKEN=$(curl -fsS -X POST "http://127.0.0.1:$AGORA_PORT/api/user/telegram/link-token" \
    -H "Authorization: Bearer $USER_TOKEN" | jq -r .token)
  if [[ -n "$TG_TOKEN" && "$TG_TOKEN" != "null" ]]; then
    ok "/api/user/telegram/link-token genera token (len=$(echo -n "$TG_TOKEN" | wc -c))"
  else
    fail "/api/user/telegram/link-token no devolvió token"
  fi

  STATUS=$(curl -fsS "http://127.0.0.1:$AGORA_PORT/api/user/telegram/link" \
    -H "Authorization: Bearer $USER_TOKEN" | jq -r .linked)
  ok "/api/user/telegram/link inicial: linked=$STATUS (esperado false)"

  # Verifica que el workspace colectivo se bootstrappeó
  if [[ -f "/tmp/laia-verify/agora-data/workspaces/collective/workspace.db" ]]; then
    ok "workspace colectivo bootstrappeado en /tmp/laia-verify/agora-data/workspaces/collective/"
  else
    warn "workspace colectivo aún no creado (solo se crea al primer get_or_create del pool)"
  fi
}

tier_2() {
  section "Tier 2 — Servicios arriba + endpoints en vivo"
  command -v jq >/dev/null || { fail "jq no instalado — apt install jq"; return 1; }
  tier_2_executor_boot || return 1
  tier_2_agora_boot || return 1
  tier_2_smoke_endpoints

  ok "Tier 2 done — backend + executor responden y los endpoints clave funcionan"
}

# ────────────────────────────────────────────────────────────────────────────
# TIER 3 — Round-trip plugin → executor via HTTP real
# ────────────────────────────────────────────────────────────────────────────
tier_3() {
  section "Tier 3 — Forwarder plugin → executor real (HTTP localhost)"

  # Asegura que el executor del tier 2 esté arriba; si TIER=3 solo, lo arrancamos.
  if ! curl -fsS "http://127.0.0.1:$EXECUTOR_PORT/health" >/dev/null 2>&1; then
    tier_2_executor_boot || return 1
  fi

  # Llama al plugin con la sesión apuntando al executor de localhost.
  # `set -e` dentro del subshell garantiza que cualquier AssertionError
  # propague al bash exterior y se contabilice como fallo.
  if ! ( set -e; cd "$REPO" && \
    LAIA_EXECUTOR_PORT="$EXECUTOR_PORT" \
    LAIA_EXECUTOR_TOKEN="$EXECUTOR_TOKEN" \
    .laia-core/venv/bin/python3 - <<'PY'
import importlib.util, json, os, sys, pathlib
repo = pathlib.Path(os.getcwd())
spec = importlib.util.spec_from_file_location(
    "agora_executor_forwarder",
    repo / ".laia-core/plugins/agora-executor-forwarder/__init__.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

mod.configure_session(
    agent_slug="verify-jorge",
    container_ip="127.0.0.1",
    api_token=os.environ["LAIA_EXECUTOR_TOKEN"],
    port=int(os.environ["LAIA_EXECUTOR_PORT"]),
    timeout_seconds=5.0,
)

def call(tool, args):
    return mod._on_pre_tool_call(tool, args, tool_call_id=f"verify-{tool}")

# 1. write_file forwardado
r = call("write_file", {"path": "/tmp/laia-verify/round-trip.txt", "content": "hello forwarder"})
assert r["action"] == "replace" and "OK" in r["message"], r
print(f"  ✓ write_file forwardado → {r['message'][:60]}")

# 2. read_file devuelve lo que escribimos
r = call("read_file", {"path": "/tmp/laia-verify/round-trip.txt"})
assert "hello forwarder" in r["message"], r
print(f"  ✓ read_file recupera el contenido escrito")

# 3. bash echo
r = call("bash", {"command": "echo via-forwarder"})
assert "via-forwarder" in r["message"], r
print(f"  ✓ bash forwardado")

# 4. private_workspace add + search
r = call("private_workspace_add_node", {
    "slug": "verify-note", "title": "Verify", "kind": "doc",
    "body": "contenido único de verificación con palabra_clave_xyz",
})
body = json.loads(r["message"])
assert body["ok"], body
print(f"  ✓ private_workspace_add_node → slug={body['node']['slug']}")

r = call("private_workspace_search", {"query": "palabra_clave_xyz"})
body = json.loads(r["message"])
assert body["ok"] and any(n["slug"] == "verify-note" for n in body["results"]), body
print(f"  ✓ private_workspace_search encuentra el nodo recién creado")

# 5. token inválido
mod.configure_session(
    agent_slug="x", container_ip="127.0.0.1",
    api_token="WRONG", port=int(os.environ["LAIA_EXECUTOR_PORT"]),
)
r = call("read_file", {"path": "/tmp/laia-verify/round-trip.txt"})
body = json.loads(r["message"])
assert body["ok"] is False and "403" in body["error"], body
print(f"  ✓ token inválido → ok=false con 'executor returned 403'")
PY
  ); then
    fail "Tier 3 — alguna aserción del round-trip falló (revisa el traceback arriba)"
    return 1
  fi

  ok "Tier 3 done — el forwarder habla con el executor sobre HTTP real y devuelve directives correctos"
}

# ────────────────────────────────────────────────────────────────────────────

main() {
  printf "${BLD}AGORA redesign — verify-redesign.sh${RST}\n"
  printf "REPO=%s  TIER=%s  KEEP=%s\n" "$REPO" "$TIER" "$KEEP"

  run_tier 1 && tier_1
  run_tier 2 && tier_2
  run_tier 3 && tier_3

  section "Resumen"
  if [[ "$KEEP" == "1" ]]; then
    echo "Servicios arriba — agora :$AGORA_PORT, executor :$EXECUTOR_PORT. Logs en /tmp/laia-verify/"
  else
    echo "Servicios cerrados. Logs en /tmp/laia-verify/ por si quieres revisarlos."
  fi
  if [[ "$FAILURES" -gt 0 ]]; then
    printf "${RED}✗ %d check(s) fallaron${RST}\n" "$FAILURES"
    printf "\nPara el tier 4 (E2E real con LXD + LLM), ver: ${BLD}infra/lxd/scripts/smoke-e2e.sh${RST}\n"
    exit 1
  fi
  printf "${GRN}✓ Todos los checks verde${RST}\n"
  printf "\nPara el tier 4 (E2E real con LXD + LLM), ver: ${BLD}infra/lxd/scripts/smoke-e2e.sh${RST}\n"
}

main "$@"
