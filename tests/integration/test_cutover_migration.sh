#!/usr/bin/env bash
# =============================================================================
# Cutover v1→v2 migration + rollback regression  (migrate-v1-to-v2.sh)
# =============================================================================
# Guards the 2026-05-30 PROD outage from recurring. Builds a FAITHFUL v1-state
# laia-agora replica from the LOCAL orchestrator image (no prod access needed),
# runs the real cutover script against it, and asserts the invariants that the
# four bugs violated:
#
#   #2/#4 auth: after a successful migrate the backend must serve the V2 SECRET
#          CONTENT (not a leftover/empty file) via the agora-auth FILE-mount —
#          the canonical fresh-install model (rebuild-3). auth_json_ready alone
#          is NOT enough: it only checks the file exists, not its content.
#   #1     no destroyed mountpoint: the live auth.json is never lost (the swap
#          modifies the device source in place, never remove+recreate).
#   #3     rollback restores the data-dir owner EXACTLY (never 0:0) and the
#          container comes back green — both on manual --rollback AND on the
#          auto-rollback fired by a failed verify.
#
# DESTRUCTIVE + needs LXD → vm/host profiles only. Builds and destroys its OWN
# container ($TEST_CONTAINER); it NEVER touches the prod `laia-agora`.
#
# Overrides (env): CUTOVER_TEST_IMAGE, CUTOVER_TEST_CONTAINER, CUTOVER_TEST_WORK,
#   CUTOVER_MIGRATE_SCRIPT, CUTOVER_ADMIN_USER, CUTOVER_TEST_JSON, AGORA_UID,
#   AGORA_GID, AGORA_DEFAULT_MAP_BASE.
#
# integrity:id=cutover_migration_regression
# integrity:name=Cutover v1->v2 migration + rollback regression
# integrity:level=e2e
# integrity:layers=lxd,agora,data
# integrity:profiles=vm
# integrity:requires=optional_lxd,optional_jq,optional_curl
# integrity:timeout=600
set -u

# ── Config (overridable) ─────────────────────────────────────────────────────
IMAGE="${CUTOVER_TEST_IMAGE:-laia-agora}"
TEST_CONTAINER="${CUTOVER_TEST_CONTAINER:-laia-cutover-regtest}"
WORK="${CUTOVER_TEST_WORK:-/root/cutover-regtest}"
ADMIN_USER="${CUTOVER_ADMIN_USER:-laia-arch}"
AGORA_UID="${AGORA_UID:-999}"
AGORA_GID="${AGORA_GID:-988}"
MAP_BASE="${AGORA_DEFAULT_MAP_BASE:-1000000}"   # LXD default idmap host base
JSON_OUT="${CUTOVER_TEST_JSON:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MIGRATE="${CUTOVER_MIGRATE_SCRIPT:-$REPO_ROOT/infra/lxd/scripts/migrate-v1-to-v2.sh}"

# Sandbox layout (all under $WORK, never under /srv or a real home).
DOTLAIA="$WORK/dot-laia"          # the v1 ~/.laia (secrets + runtime)
ARCH="$WORK/arch"                 # v2 runtime target
SECRETS="$ARCH/secrets"           # v2 secrets target
DATADIR="$WORK/agora-data"        # the agora-data mount (host side)
MARKER="$WORK/marker"             # migration resume markers
BACKUP="$WORK/backups"            # migration backup root

# The agora user (999/988) shifted by the default idmap base → host owner of the
# v1 data dir. This is the exact value the rollback must preserve (the bug grabbed
# 0:0 instead, locking the unprivileged agora user out → restart failed → outage).
V1_DATA_OWNER="$((MAP_BASE + AGORA_UID)):$((MAP_BASE + AGORA_GID))"
EMPTY_SHA="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
V1_MARKER='{"openai-codex":{"access_token":"REGTEST-V1-MARKER-not-real","refresh_token":"R","expires_at":9999999999}}'

# ── Output / counters ────────────────────────────────────────────────────────
PASS=0; FAIL=0; SKIP=0
FAILURES=()
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  G='\033[1;32m'; R='\033[1;31m'; Y='\033[1;33m'; B='\033[1;34m'; D='\033[2m'; BLD='\033[1m'; RST='\033[0m'
else G=''; R=''; Y=''; B=''; D=''; BLD=''; RST=''; fi
section() { printf "\n${BLD}${B}== %s ==${RST}\n" "$*"; }
pass() { PASS=$((PASS+1)); printf "  ${G}✓ PASS${RST} %s\n" "$1"; }
fail() { FAIL=$((FAIL+1)); FAILURES+=("$1"); printf "  ${R}✗ FAIL${RST} %s\n" "$1"; }
skipt(){ SKIP=$((SKIP+1)); printf "  ${D}- SKIP %s (%s)${RST}\n" "$1" "${2:-n/a}"; }
info() { printf "  ${D}· %s${RST}\n" "$1"; }

have() { command -v "$1" >/dev/null 2>&1; }

# ── Hard safety: never operate on the real prod container ─────────────────────
if [[ "$TEST_CONTAINER" == "laia-agora" ]]; then
  echo "REFUSING: TEST_CONTAINER must not be 'laia-agora' (prod). Set CUTOVER_TEST_CONTAINER." >&2
  exit 2
fi

# ── Skip cleanly when the environment can't run this (CI without LXD) ─────────
if ! have lxc || ! have jq || ! have curl; then
  echo "SKIP cutover_migration_regression: needs lxc+jq+curl (vm/host profile only)"
  [[ -n "$JSON_OUT" ]] && echo '{"test":"cutover_migration_regression","status":"skip","reason":"no lxc/jq/curl","pass":0,"fail":0}' > "$JSON_OUT"
  exit 0
fi
if ! lxc image info "$IMAGE" >/dev/null 2>&1 && ! lxc image alias list 2>/dev/null | grep -q "$IMAGE"; then
  echo "SKIP cutover_migration_regression: image '$IMAGE' not found in this LXD"
  [[ -n "$JSON_OUT" ]] && echo '{"test":"cutover_migration_regression","status":"skip","reason":"no image","pass":0,"fail":0}' > "$JSON_OUT"
  exit 0
fi
if [[ ! -f "$MIGRATE" ]]; then
  echo "SKIP cutover_migration_regression: migrate script not found at $MIGRATE"
  [[ -n "$JSON_OUT" ]] && echo '{"test":"cutover_migration_regression","status":"skip","reason":"no migrate script","pass":0,"fail":0}' > "$JSON_OUT"
  exit 0
fi

# ── Helpers ───────────────────────────────────────────────────────────────────
container_ip() {
  lxc list "$TEST_CONTAINER" --format json 2>/dev/null \
    | jq -r '.[0].state.network.eth0.addresses[]? | select(.family=="inet") | .address' | head -1
}
health_json() {
  local ip; ip="$(container_ip)"; [[ -n "$ip" ]] || return 1
  curl -fsS -m 5 "http://${ip}:8000/api/health" 2>/dev/null
}
wait_green() {  # 0 if ok:true within timeout
  local j; for _ in $(seq 1 45); do
    j="$(health_json)" && [[ "$(echo "$j" | jq -r '.ok // false')" == "true" ]] && { echo "$j"; return 0; }
    sleep 1
  done; return 1
}
served_sha() {  # sha256 of the file the backend actually reads
  lxc exec "$TEST_CONTAINER" -- sha256sum /opt/agora/data/auth.json 2>/dev/null | awk '{print $1}'
}
data_owner() { stat -c '%u:%g' "$DATADIR" 2>/dev/null; }
dev_source() { lxc config device get "$TEST_CONTAINER" "$1" source 2>/dev/null; }
idmap()      { lxc config get "$TEST_CONTAINER" raw.idmap 2>/dev/null; }

migrate_env() {  # echo the override env the cutover runs under
  cat <<EOF
LAIA_ADMIN_USER=$ADMIN_USER
SRC_LAIA=$DOTLAIA
LAIA_ARCH_DIR_OVERRIDE=$ARCH
LAIA_ARCH_CREDS_DIR_OVERRIDE=$SECRETS
HOST_DATA_DIR=$DATADIR
CONTAINER=$TEST_CONTAINER
BACKUP_ROOT=$BACKUP
MARKER_DIR=$MARKER
AGORA_UID=$AGORA_UID
AGORA_GID=$AGORA_GID
EOF
}
run_migrate() {  # args passed to the script; returns its exit code
  ( set -a; eval "$(migrate_env)"; set +a; bash "$MIGRATE" "$@" ) >"$WORK/migrate.log" 2>&1
}

teardown() {
  lxc delete -f "$TEST_CONTAINER" >/dev/null 2>&1 || true
  rm -rf "$WORK" 2>/dev/null || true
}

build_baseline() {  # faithful v1 state: no raw.idmap, agora-auth file-mount, agora-owned data dir
  lxc delete -f "$TEST_CONTAINER" >/dev/null 2>&1 || true
  rm -rf "$WORK"
  mkdir -p "$DOTLAIA/state" "$DATADIR"
  # v1 ~/.laia secrets + runtime
  printf '%s\n' "$V1_MARKER" > "$DOTLAIA/auth.json"; chmod 644 "$DOTLAIA/auth.json"
  printf 'X=1\n' > "$DOTLAIA/.env"; chmod 600 "$DOTLAIA/.env"
  printf 'config: dummy\n' > "$DOTLAIA/config.yaml"
  printf 'atlas: dummy\n' > "$DOTLAIA/atlas.yaml"
  # data dir owned by the shifted agora user (v1: no raw.idmap, default map base)
  : > "$DATADIR/auth.json"                 # 0-byte mountpoint (shadowed by agora-auth)
  chmod 644 "$DATADIR/auth.json"
  chown -R "$V1_DATA_OWNER" "$DATADIR"
  chmod 700 "$DATADIR"
  # container from the local orchestrator image, v1 device set, NO raw.idmap
  lxc init "$IMAGE" "$TEST_CONTAINER" -p default -p laia-agora >/dev/null
  lxc config device add "$TEST_CONTAINER" agora-data disk source="$DATADIR" path=/opt/agora/data >/dev/null
  lxc config device add "$TEST_CONTAINER" agora-auth disk \
      source="$DOTLAIA/auth.json" path=/opt/agora/data/auth.json readonly=true >/dev/null
  lxc start "$TEST_CONTAINER" >/dev/null
}

# ── Scenario 1: happy path serves the V2 secret content (#2, #4, #1) ──────────
scenario_happy() {
  section "Scenario 1 — migrate serves the V2 secret (bugs #2/#4/#1)"
  build_baseline
  if ! wait_green >/dev/null; then fail "baseline did not come up green"; return; fi
  local base_sha; base_sha="$(served_sha)"
  [[ "$base_sha" != "$EMPTY_SHA" && -n "$base_sha" ]] \
    && pass "baseline green, backend serves a non-empty auth.json" \
    || { fail "baseline auth.json empty/unreadable (sha=$base_sha)"; return; }

  if run_migrate --yes --no-snapshot; then pass "migrate exited 0"; else fail "migrate exited non-zero (see $WORK/migrate.log)"; fi
  wait_green >/dev/null || { fail "container not green after migrate"; return; }

  # The backend must now serve the V2 secret CONTENT, not a leftover/empty file.
  local secret_sha serve_sha
  secret_sha="$(sha256sum "$SECRETS/auth.json" 2>/dev/null | awk '{print $1}')"
  serve_sha="$(served_sha)"
  [[ "$serve_sha" != "$EMPTY_SHA" && -n "$serve_sha" ]] \
    && pass "served auth.json is non-empty after migrate" \
    || fail "served auth.json is EMPTY after migrate (the false-green bug #2): sha=$serve_sha"
  [[ -n "$secret_sha" && "$serve_sha" == "$secret_sha" ]] \
    && pass "backend serves the V2 secret content ($SECRETS/auth.json)" \
    || fail "backend does NOT serve the V2 secret (serve=$serve_sha secret=$secret_sha) — bug #2"

  # End-state matches a fresh v2 install (rebuild-3): agora-auth → v2 secret.
  [[ "$(dev_source agora-auth)" == "$SECRETS/auth.json" ]] \
    && pass "agora-auth device source points at the V2 secret (rebuild-3 model)" \
    || fail "agora-auth source != V2 secret (got '$(dev_source agora-auth)') — bug #4 (used arch-laia/env instead)"
  [[ -n "$(dev_source agora-data)" ]] \
    && pass "agora-data mount intact (live data not destroyed) — bug #1" \
    || fail "agora-data device missing after migrate — bug #1"
  [[ -n "$(idmap)" ]] && pass "raw.idmap applied" || fail "raw.idmap not set after migrate"
}

# ── Scenario 2: manual rollback restores EXACT owner + v1 auth (#3, #1) ───────
scenario_manual_rollback() {
  section "Scenario 2 — manual --rollback restores v1 exactly (bug #3)"
  build_baseline
  wait_green >/dev/null || { fail "baseline not green"; return; }
  # --no-cleanup: migrate + verify but KEEP v1 (~/.laia) so the device-level
  # --rollback is available (manual rollback is for a paused/pre-cleanup state;
  # after cleanup it correctly refuses and points at the snapshot).
  run_migrate --yes --no-snapshot --no-cleanup || { fail "migrate failed in setup"; return; }
  wait_green >/dev/null || { fail "not green after migrate (setup)"; return; }

  run_migrate --rollback
  wait_green >/dev/null || { fail "container NOT green after rollback (the outage signature)"; return; }
  pass "container green again after rollback"

  local owner; owner="$(data_owner)"
  [[ "$owner" == "$V1_DATA_OWNER" ]] \
    && pass "data dir owner restored EXACTLY to $V1_DATA_OWNER" \
    || fail "data dir owner is '$owner', expected '$V1_DATA_OWNER' (bug #3: rollback wrote wrong owner)"
  [[ "$owner" != "0:0" ]] || fail "data dir left root:root (0:0) — the exact outage bug"
  [[ -z "$(idmap)" ]] && pass "raw.idmap removed (v1 had none)" || fail "raw.idmap still set after rollback: $(idmap)"
  [[ "$(dev_source agora-auth)" == "$DOTLAIA/auth.json" ]] \
    && pass "agora-auth source restored to v1 (~/.laia)" \
    || fail "agora-auth source not restored to v1 (got '$(dev_source agora-auth)')"
  local serve_sha v1_sha
  serve_sha="$(served_sha)"; v1_sha="$(sha256sum "$DOTLAIA/auth.json" | awk '{print $1}')"
  [[ "$serve_sha" == "$v1_sha" ]] \
    && pass "backend serves the v1 auth again after rollback" \
    || fail "backend not serving v1 auth after rollback (serve=$serve_sha v1=$v1_sha)"
}

# ── Scenario 3: auto-rollback after a forced verify failure (#3) ──────────────
scenario_auto_rollback() {
  section "Scenario 3 — failed verify auto-rolls-back cleanly (bug #3)"
  build_baseline
  wait_green >/dev/null || { fail "baseline not green"; return; }
  # Force the verify to fail: empty the v1 auth so the migrated secret is empty
  # → the content-aware verify must reject it and auto-rollback.
  : > "$DOTLAIA/auth.json"; chown "$V1_DATA_OWNER" "$DOTLAIA/auth.json" 2>/dev/null || true

  if run_migrate --yes --no-snapshot; then
    fail "migrate exited 0 on an empty secret (false green — verify is content-blind, bug #2)"
  else
    pass "migrate failed (non-zero) on the empty/invalid secret"
  fi
  wait_green >/dev/null || { fail "container NOT green after auto-rollback (outage signature)"; return; }
  pass "container green after auto-rollback"
  local owner; owner="$(data_owner)"
  [[ "$owner" == "$V1_DATA_OWNER" ]] \
    && pass "auto-rollback restored data dir owner EXACTLY to $V1_DATA_OWNER" \
    || fail "auto-rollback left owner '$owner', expected '$V1_DATA_OWNER' (bug #3)"
  [[ "$owner" != "0:0" ]] || fail "auto-rollback left data dir root:root (0:0) — the exact outage"
  [[ -z "$(idmap)" ]] && pass "raw.idmap reverted after auto-rollback" || fail "raw.idmap still set: $(idmap)"
}

# ── Scenario 4: after cleanup, --rollback REFUSES (no half-restore) ───────────
scenario_post_cleanup_refusal() {
  section "Scenario 4 — post-cleanup --rollback refuses safely (no half-restore)"
  build_baseline
  wait_green >/dev/null || { fail "baseline not green"; return; }
  run_migrate --yes --no-snapshot || { fail "full migrate failed in setup"; return; }   # includes cleanup (archives ~/.laia)
  wait_green >/dev/null || { fail "not green after full migrate"; return; }
  local secret_sha pre_sha
  secret_sha="$(sha256sum "$SECRETS/auth.json" 2>/dev/null | awk '{print $1}')"
  pre_sha="$(served_sha)"

  # ~/.laia archived → device rollback is unsafe → must REFUSE, not half-restore.
  if run_migrate --rollback; then
    fail "post-cleanup --rollback exited 0 (should refuse: v1 source archived)"
  else
    pass "post-cleanup --rollback refused (non-zero), as designed"
  fi
  wait_green >/dev/null || { fail "container not green after refused rollback (it damaged state!)"; return; }
  local post_sha; post_sha="$(served_sha)"
  [[ "$post_sha" == "$secret_sha" && "$post_sha" == "$pre_sha" ]] \
    && pass "refused rollback left the migrated v2 state intact (still serving v2 secret)" \
    || fail "refused rollback altered state (pre=$pre_sha post=$post_sha secret=$secret_sha)"
  ls -d "$DOTLAIA".v1-migrated-* >/dev/null 2>&1 \
    && pass "v1 ~/.laia was archived (reversible) by cleanup" \
    || fail "expected an archived ~/.laia (dot-laia.v1-migrated-*)"
}

# ── Run ───────────────────────────────────────────────────────────────────────
section "Cutover v1→v2 regression — image=$IMAGE container=$TEST_CONTAINER"
info "migrate script: $MIGRATE"
info "v1 data owner (expected): $V1_DATA_OWNER"
trap teardown EXIT

scenario_happy
scenario_manual_rollback
scenario_auto_rollback
scenario_post_cleanup_refusal

section "Summary"
printf "  ${G}PASS=%d${RST}  ${R}FAIL=%d${RST}  ${D}SKIP=%d${RST}\n" "$PASS" "$FAIL" "$SKIP"
for f in "${FAILURES[@]:-}"; do [[ -n "$f" ]] && printf "    ${R}✗${RST} %s\n" "$f"; done

if [[ -n "$JSON_OUT" ]]; then
  status="pass"; [[ $FAIL -gt 0 ]] && status="fail"
  printf '{"test":"cutover_migration_regression","status":"%s","pass":%d,"fail":%d,"skip":%d}\n' \
    "$status" "$PASS" "$FAIL" "$SKIP" > "$JSON_OUT"
fi

[[ $FAIL -eq 0 ]] && exit 0 || exit 1
