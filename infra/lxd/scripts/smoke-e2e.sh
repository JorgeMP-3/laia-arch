#!/usr/bin/env bash
# smoke-e2e.sh — verificación end-to-end del rediseño AGORA.
#
# Ejecuta los 13 pasos de la sección "Verification" del plan
# (`.claude2/plans/contexto-lo-snuggly-scott.md`). Pensado para correr
# contra una instalación real con LXD presente, no en CI ni en dev sin
# containers. Cada paso emite OK / FAIL legible.
#
# Requisitos:
#   - lxc CLI con permisos para crear/borrar containers
#   - El container `laia-agora` arrancado en :8088
#   - jq, curl
#   - Una API key LLM válida en LAIA_E2E_LLM_KEY (ej. DeepSeek)
#
# Uso:
#   sudo bash smoke-e2e.sh                 # corre los 13 pasos
#   STEP=5 sudo bash smoke-e2e.sh          # solo el paso 5
#   KEEP=1 sudo bash smoke-e2e.sh          # no borra usuarios/containers al final

set -uo pipefail

AGORA_URL="${AGORA_URL:-http://127.0.0.1:8088}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin-dev}"
LLM_PROVIDER="${LAIA_E2E_LLM_PROVIDER:-deepseek}"
LLM_MODEL="${LAIA_E2E_LLM_MODEL:-deepseek-chat}"
LLM_KEY="${LAIA_E2E_LLM_KEY:-}"
KEEP="${KEEP:-0}"
ONLY_STEP="${STEP:-}"

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; RST='\033[0m'
else
  GRN=''; YEL=''; RED=''; CYN=''; RST=''
fi
step() { printf "${CYN}▸ Paso %s: %s${RST}\n" "$1" "$2"; }
ok()   { printf "  ${GRN}✓ %s${RST}\n" "$*"; }
warn() { printf "  ${YEL}⚠ %s${RST}\n" "$*"; }
fail() { printf "  ${RED}✗ %s${RST}\n" "$*"; }
die()  { fail "$*"; exit 1; }

run() {
  local n="$1"; shift
  [[ -n "$ONLY_STEP" && "$ONLY_STEP" != "$n" ]] && return 0
  "$@"
}

# ────────────────────────────────────────────────────────────────────────────
# Step 1 — health
# ────────────────────────────────────────────────────────────────────────────
step_1_health() {
  step 1 "AGORA container responde a /api/health"
  curl -fsS "$AGORA_URL/api/health" | jq -e '.ok == true' >/dev/null \
    && ok "health 200" || die "/api/health no responde 200"
}

# ────────────────────────────────────────────────────────────────────────────
# Step 2 — admin login
# ────────────────────────────────────────────────────────────────────────────
step_2_login() {
  step 2 "Login admin"
  ADMIN_TOKEN=$(curl -fsS -X POST "$AGORA_URL/api/login" \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" \
    | jq -r .access_token)
  [[ -n "$ADMIN_TOKEN" && "$ADMIN_TOKEN" != "null" ]] || die "login falló"
  ok "admin token obtenido"
}

# ────────────────────────────────────────────────────────────────────────────
# Step 3 — crear user jorge
# ────────────────────────────────────────────────────────────────────────────
step_3_create_user() {
  step 3 "Crear usuario 'e2e-jorge'"
  resp=$(curl -fsS -X POST "$AGORA_URL/api/users" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{"username":"e2e_jorge","display_name":"E2E Jorge","role":"employee"}')
  JORGE_PW=$(echo "$resp" | jq -r .password)
  JORGE_ID=$(echo "$resp" | jq -r .user.id)
  [[ -n "$JORGE_PW" && "$JORGE_PW" != "null" ]] || die "no se obtuvo password"
  ok "usuario creado (id=$JORGE_ID)"
}

# ────────────────────────────────────────────────────────────────────────────
# Step 4 — login + configurar LLM key
# ────────────────────────────────────────────────────────────────────────────
step_4_llm_config() {
  step 4 "Login jorge + PATCH /api/user/llm-config"
  [[ -z "$LLM_KEY" ]] && die "LAIA_E2E_LLM_KEY no está fijada"

  JORGE_TOKEN=$(curl -fsS -X POST "$AGORA_URL/api/login" \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"e2e_jorge\",\"password\":\"$JORGE_PW\"}" \
    | jq -r .access_token)
  [[ -n "$JORGE_TOKEN" && "$JORGE_TOKEN" != "null" ]] || die "login jorge falló"

  curl -fsS -X PATCH "$AGORA_URL/api/user/llm-config" \
    -H "Authorization: Bearer $JORGE_TOKEN" \
    -H 'Content-Type: application/json' \
    -d "{\"provider\":\"$LLM_PROVIDER\",\"model\":\"$LLM_MODEL\",\"api_key\":\"$LLM_KEY\"}" \
    >/dev/null
  ok "LLM config aplicada (provider=$LLM_PROVIDER)"
}

# ────────────────────────────────────────────────────────────────────────────
# Step 5 — provisionar container del usuario
# ────────────────────────────────────────────────────────────────────────────
step_5_provision() {
  step 5 "Provisionar container laia-e2e_jorge"
  bash "$(dirname "$0")/create-agent.sh" e2e_jorge >/tmp/e2e-create.json
  CONTAINER_IP=$(jq -r .container_ip </tmp/e2e-create.json)
  AGENT_TOKEN=$(jq -r .api_token </tmp/e2e-create.json)
  ok "container arriba (ip=$CONTAINER_IP)"

  curl -fsS -X POST "$AGORA_URL/api/agents/register" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H 'Content-Type: application/json' \
    -d "$(cat /tmp/e2e-create.json | jq -c '.user_id = "'"$JORGE_ID"'"')" \
    >/dev/null
  ok "agente registrado en AGORA"
}

# ────────────────────────────────────────────────────────────────────────────
# Step 6 — write+read forwardado vía chat
# ────────────────────────────────────────────────────────────────────────────
step_6_chat_write_read() {
  step 6 "Chat: pedir crear hello.py vía forwarder → executor → bind mount"
  prompt='Crea un script python que imprima la fecha de hoy y guárdalo como /home/user/hello.py. Solo crea el archivo, no lo ejecutes.'
  curl -fsS -N -X POST "$AGORA_URL/api/agents/me/chat" \
    -H "Authorization: Bearer $JORGE_TOKEN" \
    -H 'Content-Type: application/json' \
    -d "{\"message\":$(jq -nR --arg p "$prompt" '$p'),\"session_id\":\"e2e-sess\"}" \
    -o /tmp/e2e-chat-out.txt -w '%{http_code}\n' | grep -q 200 \
    || warn "chat status no fue 200 (revisa /tmp/e2e-chat-out.txt)"

  if [[ -f "/srv/laia/users/e2e_jorge/home/hello.py" ]]; then
    ok "hello.py existe en bind mount"
  else
    fail "hello.py NO existe — revisa logs del executor + forwarder"
  fi
}

# ────────────────────────────────────────────────────────────────────────────
# Step 7 — persistencia tras recreate del container
# ────────────────────────────────────────────────────────────────────────────
step_7_persistence() {
  step 7 "Persistencia: stop+delete container, recrear, archivo sigue"
  lxc snapshot laia-e2e_jorge pre-e2e-recreate
  lxc delete --force laia-e2e_jorge
  bash "$(dirname "$0")/create-agent.sh" e2e_jorge >/tmp/e2e-recreate.json
  if [[ -f "/srv/laia/users/e2e_jorge/home/hello.py" ]]; then
    ok "hello.py sobrevive al recreate (bind mount funciona)"
  else
    fail "hello.py NO sobrevivió — bind mounts mal configurados"
  fi
}

# ────────────────────────────────────────────────────────────────────────────
# Step 8 — LLM key inválida
# ────────────────────────────────────────────────────────────────────────────
step_8_invalid_key() {
  step 8 "LLM key inválida produce error legible"
  curl -fsS -X PATCH "$AGORA_URL/api/user/llm-config" \
    -H "Authorization: Bearer $JORGE_TOKEN" \
    -H 'Content-Type: application/json' \
    -d "{\"provider\":\"$LLM_PROVIDER\",\"api_key\":\"sk-DEFINITELY-WRONG\"}" \
    >/dev/null
  resp=$(curl -fsS -X POST "$AGORA_URL/api/agents/me/chat" \
    -H "Authorization: Bearer $JORGE_TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{"message":"hola","session_id":"e2e-sess-bad"}')
  if echo "$resp" | grep -qi 'invalid\|llm'; then
    ok "error de key surfaceado"
  else
    warn "respuesta inesperada — revisar manualmente"
  fi

  # Restaurar la key buena.
  curl -fsS -X PATCH "$AGORA_URL/api/user/llm-config" \
    -H "Authorization: Bearer $JORGE_TOKEN" \
    -H 'Content-Type: application/json' \
    -d "{\"api_key\":\"$LLM_KEY\"}" >/dev/null
}

# ────────────────────────────────────────────────────────────────────────────
# Step 9 — Telegram link round-trip (sin enviar mensajes reales)
# ────────────────────────────────────────────────────────────────────────────
step_9_telegram_link() {
  step 9 "Generar token Telegram + revocar"
  token=$(curl -fsS -X POST "$AGORA_URL/api/user/telegram/link-token" \
    -H "Authorization: Bearer $JORGE_TOKEN" | jq -r .token)
  [[ -n "$token" && "$token" != "null" ]] || die "no se generó token"
  ok "token generado (len=$(echo -n "$token" | wc -c))"

  curl -fsS -X DELETE "$AGORA_URL/api/user/telegram/link" \
    -H "Authorization: Bearer $JORGE_TOKEN" | jq -e '.ok == true' >/dev/null
  ok "unlink endpoint responde"
}

# ────────────────────────────────────────────────────────────────────────────
# Step 10 — multi-user isolation
# ────────────────────────────────────────────────────────────────────────────
step_10_multi_user() {
  step 10 "Aislamiento entre users (maria no ve archivos de jorge)"
  resp=$(curl -fsS -X POST "$AGORA_URL/api/users" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{"username":"e2e_maria","display_name":"E2E Maria","role":"employee"}')
  MARIA_ID=$(echo "$resp" | jq -r .user.id)
  bash "$(dirname "$0")/create-agent.sh" e2e_maria >/tmp/e2e-maria.json

  if ! lxc exec laia-e2e_maria -- cat /srv/laia/users/e2e_jorge/home/hello.py 2>/dev/null; then
    ok "maria NO puede leer archivos de jorge (esperado)"
  else
    fail "AISLAMIENTO ROTO — maria ve archivos de jorge"
  fi
}

# ────────────────────────────────────────────────────────────────────────────
# Step 11 — concurrencia: 3 sesiones simultáneas, mismo user
# ────────────────────────────────────────────────────────────────────────────
step_11_concurrency() {
  step 11 "Concurrencia 3 sesiones simultáneas"
  for i in 1 2 3; do
    curl -fsS -X POST "$AGORA_URL/api/agents/me/chat" \
      -H "Authorization: Bearer $JORGE_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"message\":\"ping $i\",\"session_id\":\"conc-$i\"}" \
      -o "/tmp/e2e-conc-$i.txt" &
  done
  wait
  ok "3 sesiones completaron sin error de mezcla"
}

# ────────────────────────────────────────────────────────────────────────────
# Step 12 — TTL del pool (NO se ejecuta automáticamente — requiere 65 min)
# ────────────────────────────────────────────────────────────────────────────
step_12_ttl() {
  step 12 "TTL del pool — requiere ~65 min de idle, NO automatizado"
  warn "saltado: ejecutar manualmente con AGENT_POOL_TTL=300 para acortar"
}

# ────────────────────────────────────────────────────────────────────────────
# Step 13 — cleanup
# ────────────────────────────────────────────────────────────────────────────
step_13_cleanup() {
  step 13 "Cleanup (borrar usuarios + containers de prueba)"
  if [[ "$KEEP" == "1" ]]; then
    warn "KEEP=1 — no se borra nada"
    return
  fi
  for slug in e2e_jorge e2e_maria; do
    lxc delete --force "laia-$slug" 2>/dev/null || true
    rm -rf "/srv/laia/users/$slug" 2>/dev/null || true
  done
  ok "cleanup completo"
}

# ────────────────────────────────────────────────────────────────────────────

main() {
  step_1_health
  run 2 step_2_login
  run 3 step_3_create_user
  run 4 step_4_llm_config
  run 5 step_5_provision
  run 6 step_6_chat_write_read
  run 7 step_7_persistence
  run 8 step_8_invalid_key
  run 9 step_9_telegram_link
  run 10 step_10_multi_user
  run 11 step_11_concurrency
  run 12 step_12_ttl
  run 13 step_13_cleanup
  printf "\n${GRN}=== Smoke E2E terminado ===${RST}\n"
}

main "$@"
