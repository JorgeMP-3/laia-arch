#!/usr/bin/env bash
# =============================================================================
# D2 — Suite de integridad end-to-end del ecosistema LAIA (gate final)
# =============================================================================
# Verifica, READ-ONLY, que el ecosistema completo está sano, recorriendo las
# 6 capas del modelo (host → LXD → AGORA → executor por-usuario → datos en su
# sitio (modelo 2 zonas) → Atlas + backups). Slice D2 · módulo M7.
#
# Diseño:
#   - NO muta nada. Sólo lee (lxc list/info, curl /api/health, sqlite3 -readonly,
#     atlas doctor, stat). Seguro de correr contra el sistema vivo.
#   - Cada check reporta PASS / FAIL / PEND(iente) / SKIP. El gate falla (exit 1)
#     SÓLO si hay algún FAIL. PEND = el estado objetivo (v2) aún no aplicado a
#     este host (p.ej. prod pre-migración C3) — informativo, no error. SKIP =
#     no aplicable / dependencia ausente.
#   - Verde total esperado: en la VM `laia-dev` (ya v2) y en prod TRAS la
#     migración C3. En un host v1 las capas de layout-v2 salen PEND.
#
# Overrides (env): CONTAINER, LAIA_ARCH_DIR_OVERRIDE, LAIA_ARCH_CREDS_DIR_OVERRIDE,
#   LAIA_AGORA_DIR_OVERRIDE, AGORA_DB, LAIA_USERS_DIR_OVERRIDE, LAIA_BACKUP_DIR,
#   AGORA_HEALTH_PORT.
set -u

# ── Config (overridable) ─────────────────────────────────────────────────────
CONTAINER="${CONTAINER:-laia-agora}"
ARCH_DIR="${LAIA_ARCH_DIR_OVERRIDE:-/srv/laia/arch}"
ARCH_CREDS_DIR="${LAIA_ARCH_CREDS_DIR_OVERRIDE:-$ARCH_DIR/secrets}"
AGORA_DATA_DIR="${LAIA_AGORA_DIR_OVERRIDE:-/srv/laia/agora}"
AGORA_DB="${AGORA_DB:-$AGORA_DATA_DIR/agora.db}"
USERS_DIR="${LAIA_USERS_DIR_OVERRIDE:-/srv/laia/users}"
BACKUP_DIR="${LAIA_BACKUP_DIR:-/mnt/data/laia-backups}"
HEALTH_PORT="${AGORA_HEALTH_PORT:-8000}"

# ── Counters / output ────────────────────────────────────────────────────────
PASS=0; FAIL=0; PEND=0; SKIP=0
FAILURES=()
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  G='\033[1;32m'; R='\033[1;31m'; Y='\033[1;33m'; B='\033[1;34m'; D='\033[2m'; BLD='\033[1m'; RST='\033[0m'
else G=''; R=''; Y=''; B=''; D=''; BLD=''; RST=''; fi

section() { printf "\n${BLD}${B}== %s ==${RST}\n" "$*"; }
pass() { PASS=$((PASS+1)); printf "  ${G}✓ PASS${RST} %s\n" "$1"; }
fail() { FAIL=$((FAIL+1)); FAILURES+=("$1"); printf "  ${R}✗ FAIL${RST} %s\n" "$1"; }
pend() { PEND=$((PEND+1)); printf "  ${Y}• PEND${RST} %s ${D}(%s)${RST}\n" "$1" "${2:-pendiente}"; }
skip() { SKIP=$((SKIP+1)); printf "  ${D}- SKIP %s (%s)${RST}\n" "$1" "${2:-n/a}"; }

have() { command -v "$1" >/dev/null 2>&1; }

# ── Modo de layout: ¿este host ya está en v2? ────────────────────────────────
# v2 ⇔ existe el secrets dir del ARCH con auth.json. Si no, es v1 (pre-migración).
LAYOUT=v1
if [[ -d "$ARCH_CREDS_DIR" && -f "$ARCH_CREDS_DIR/auth.json" ]]; then
  LAYOUT=v2
fi

# ── Health JSON del laia-agora (read-only) ───────────────────────────────────
agora_health_json() {
  have lxc || return 1
  have curl || return 1
  local ip
  ip="$(lxc list "$CONTAINER" --format json 2>/dev/null \
        | { have jq && jq -r '.[0].state.network.eth0.addresses[]? | select(.family=="inet") | .address' 2>/dev/null | head -1; })"
  [[ -n "$ip" ]] || return 1
  curl -fsS -m 5 "http://${ip}:${HEALTH_PORT}/api/health" 2>/dev/null
}

printf "${BLD}D2 — Integridad del ecosistema LAIA${RST}  (layout detectado: ${BLD}%s${RST})\n" "$LAYOUT"
printf "${D}  container=%s · arch=%s · agora=%s · backups=%s${RST}\n" "$CONTAINER" "$ARCH_DIR" "$AGORA_DATA_DIR" "$BACKUP_DIR"

# ─────────────────────────────────────────────────────────────────────────────
section "Capa 1/6 — Host & estructura /srv/laia"
# ─────────────────────────────────────────────────────────────────────────────
if [[ -d /srv/laia ]]; then
  pass "/srv/laia existe"
  # /srv/laia/agora es el dir operacional núcleo — debe existir en cualquier
  # host instalado (lo crea el install/clone).
  if [[ -d "$AGORA_DATA_DIR" ]]; then
    pass "dir operacional $AGORA_DATA_DIR presente"
  elif [[ "$LAYOUT" == "v2" ]]; then
    fail "falta dir operacional $AGORA_DATA_DIR"
  else
    pend "dir operacional $AGORA_DATA_DIR" "host v1 — lo crea setup-prod-dirs/migración"
  fi
  # users/ y state/ se pueblan al provisionar el primer usuario/agente; en un
  # install fresco sin usuarios son legítimamente ausentes → PEND, no FAIL. El
  # caso roto (agentes vivos pero su dir ausente) lo detecta la capa 4.
  for d in "$USERS_DIR" /srv/laia/state; do
    if [[ -d "$d" ]]; then
      pass "dir operacional $d presente"
    else
      pend "dir operacional $d" "se crea al provisionar el primer usuario/agente"
    fi
  done
else
  skip "/srv/laia (host no instalado en layout factory; ¿dev?)" "sin /srv/laia"
fi

# ─────────────────────────────────────────────────────────────────────────────
section "Capa 2/6 — Containers LXD"
# ─────────────────────────────────────────────────────────────────────────────
if have lxc; then
  state="$(lxc list "$CONTAINER" -c s --format csv 2>/dev/null | head -1)"
  if [[ "$state" == "RUNNING" ]]; then
    pass "container $CONTAINER RUNNING"
  elif [[ -n "$state" ]]; then
    fail "container $CONTAINER existe pero estado=$state (esperado RUNNING)"
  else
    fail "container $CONTAINER no existe"
  fi
else
  skip "LXD (lxc no disponible)" "sin lxc"
fi

# ─────────────────────────────────────────────────────────────────────────────
section "Capa 3/6 — AGORA (/api/health + agora.db íntegra)"
# ─────────────────────────────────────────────────────────────────────────────
if health="$(agora_health_json)"; then
  ok="$(printf '%s' "$health" | { have jq && jq -r '.ok // false' 2>/dev/null; })"
  [[ "$ok" == "true" ]] && pass "/api/health ok:true" || fail "/api/health no reporta ok:true ($health)"
else
  if have lxc && have curl; then
    fail "/api/health inaccesible (container sin IP o backend caído)"
  else
    skip "/api/health" "faltan lxc/curl"
  fi
fi
if [[ -f "$AGORA_DB" && -r "$AGORA_DB" ]] && have sqlite3; then
  # Host-side: fixtures/VM/override donde el ARCH user puede leer la db.
  res="$(sqlite3 "file:$AGORA_DB?mode=ro" 'PRAGMA integrity_check;' 2>/dev/null | head -1)"
  [[ "$res" == "ok" ]] && pass "agora.db integrity_check = ok (host-side)" \
                       || fail "agora.db integrity_check = '${res:-<error>}'"
elif [[ "${D2_DB_VIA_EXEC:-0}" == "1" ]] && have lxc; then
  # En prod los datos van idmap-shifted (no legibles por el ARCH user); el check
  # se hace DENTRO del container. Opt-in: lxc exec = shell a producción.
  res="$(lxc exec "$CONTAINER" -- sqlite3 "file:${AGORA_DB_IN_CONTAINER:-/opt/agora/data/agora.db}?mode=ro" 'PRAGMA integrity_check;' 2>/dev/null | head -1)"
  [[ "$res" == "ok" ]] && pass "agora.db integrity_check = ok (in-container)" \
                       || fail "agora.db integrity_check (in-container) = '${res:-<error>}'"
else
  skip "agora.db integrity_check" "db no legible host-side (idmap); D2_DB_VIA_EXEC=1 la checa dentro del container — /api/health ok:true ya confirma acceso del backend a la db"
fi

# ─────────────────────────────────────────────────────────────────────────────
section "Capa 4/6 — Executor por-usuario (agent-<slug>)"
# ─────────────────────────────────────────────────────────────────────────────
if have lxc; then
  mapfile -t agents < <(lxc list -c ns --format csv 2>/dev/null | awk -F, '$1 ~ /^agent-/ {print}')
  if [[ "${#agents[@]}" -eq 0 ]]; then
    skip "executors por-usuario" "0 containers agent-* provisionados"
  else
    for row in "${agents[@]}"; do
      name="${row%%,*}"; st="${row##*,}"
      [[ "$st" == "RUNNING" ]] && pass "executor $name RUNNING" || fail "executor $name estado=$st"
    done
  fi
else
  skip "executors por-usuario" "sin lxc"
fi

# ─────────────────────────────────────────────────────────────────────────────
section "Capa 5/6 — Datos en su sitio (modelo 2 zonas)"
# ─────────────────────────────────────────────────────────────────────────────
# Zona ARCH (secrets 0700, auth.json 0600) — el estado objetivo v2.
if [[ "$LAYOUT" == "v2" ]]; then
  m="$(stat -c '%a' "$ARCH_CREDS_DIR" 2>/dev/null)"
  [[ "$m" == "700" ]] && pass "$ARCH_CREDS_DIR mode 0700" || fail "$ARCH_CREDS_DIR mode=$m (esperado 700)"
  am="$(stat -c '%a' "$ARCH_CREDS_DIR/auth.json" 2>/dev/null)"
  [[ "$am" == "600" ]] && pass "auth.json mode 0600 (cerrado el 644)" || fail "auth.json mode=$am (esperado 600)"
else
  pend "secrets del ARCH en $ARCH_CREDS_DIR (0700/0600)" "host v1 — aplicar migración C3"
fi
# Zona usuarios (modelo 2 zonas: home/workspace por slug).
if [[ -d "$USERS_DIR" ]]; then
  n="$(find "$USERS_DIR" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l)"
  pass "zona de usuarios presente ($n slug(s) en $USERS_DIR)"
else
  pend "zona de usuarios $USERS_DIR" "aún sin usuarios o host no migrado"
fi

# ─────────────────────────────────────────────────────────────────────────────
section "Capa 6/6 — Atlas (doctor sin refs rotas) + Backups"
# ─────────────────────────────────────────────────────────────────────────────
ATLAS_BIN=""
for cand in "$(dirname "$0")/../../bin/atlas" atlas laia-path; do
  have "$cand" && { ATLAS_BIN="$cand"; break; }
  [[ -x "$cand" ]] && { ATLAS_BIN="$cand"; break; }
done
if [[ -n "$ATLAS_BIN" ]]; then
  if out="$("$ATLAS_BIN" doctor 2>&1)"; then
    pass "atlas doctor sin refs rotas"
  else
    # doctor devuelve !=0 si hay refs rotas; en host v1 puede no resolver v2 aún.
    if [[ "$LAYOUT" == "v1" ]]; then
      pend "atlas doctor" "host v1 — refs v2 aún no aplicadas"
    else
      fail "atlas doctor reporta problemas: $(printf '%s' "$out" | tail -3 | tr '\n' ' ')"
    fi
  fi
else
  skip "atlas doctor" "binario atlas/laia-path no encontrado"
fi
if [[ -d "$BACKUP_DIR" ]]; then
  arts="$(find "$BACKUP_DIR" -maxdepth 1 -type f 2>/dev/null | wc -l)"
  [[ "$arts" -gt 0 ]] && pass "backups presentes ($arts artefacto(s) en $BACKUP_DIR)" \
                      || pend "artefactos de backup en $BACKUP_DIR" "dir vacío — timer aún sin correr"
else
  pend "backups en $BACKUP_DIR" "dir ausente — timer laia-backup desactivado o sin migrar"
fi

# ── Resumen ──────────────────────────────────────────────────────────────────
printf "\n${BLD}═══════════════════════════════════════════════════${RST}\n"
printf "  ${G}PASS:%d${RST}  ${R}FAIL:%d${RST}  ${Y}PEND:%d${RST}  ${D}SKIP:%d${RST}\n" "$PASS" "$FAIL" "$PEND" "$SKIP"
if [[ "$FAIL" -gt 0 ]]; then
  printf "\n${R}Fallos:${RST}\n"
  for f in "${FAILURES[@]}"; do printf "  - %s\n" "$f"; done
  printf "\n${R}D2 NO verde — el ecosistema tiene integridad rota.${RST}\n"
  exit 1
fi
if [[ "$PEND" -gt 0 ]]; then
  printf "\n${Y}D2 sin fallos, pero %d check(s) PENDientes${RST} — estado objetivo v2 no aplicado del todo.\n" "$PEND"
  printf "${D}  (verde total esperado en la VM laia-dev y en prod tras la migración C3.)${RST}\n"
fi
exit 0
