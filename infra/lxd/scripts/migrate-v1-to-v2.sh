#!/usr/bin/env bash
# migrate-v1-to-v2.sh — in-place migration of a LAIA-ARCH host from layout v1
# (secrets + runtime mixed under ~/.laia) to layout v2 (/srv/laia/arch for
# runtime, /srv/laia/arch/secrets for credentials, read by laia-agora via the
# C2 raw.idmap mount). Slice C3 · module M6 · decision T2.
#
# Design contract (see workflow/plans/estabilizacion/ T2 and slices.md C3):
#   1. BACKUP one-shot first (tar of /srv/laia + ~/.laia + ~/LAIA-ARCH to
#      $BACKUP_ROOT; optional `lxc snapshot` when run inside the dev VM).
#   2. Create /srv/laia/arch{,/secrets} with perms (laia-arch:laia-arch 0750;
#      secrets 0700, files 0600).
#   3. rsync data with the ORIGIN INTACT: runtime → /srv/laia/arch, secrets →
#      /srv/laia/arch/secrets.
#   4. Repoint anchors (reload pathd at /srv/laia/arch — the C1 default).
#   5. ADD-BEFORE-REMOVE: set raw.idmap + chown agora data, swap the laia-agora
#      secrets mount to /srv/laia/arch/secrets (reuses rebuild-3b), restart and
#      verify /api/health. ON GREEN ONLY: retire the old ~/.laia.
#   6. Idempotent + resumable via markers; rollback reverts the device + idmap
#      and leaves ~/.laia untouched until the migration is verified green.
#
# This script is AFK-built and rehearsed in the dev VM. Applying it to PROD is a
# HITL step (backup + planned laia-agora restart window) — NOT done here.
#
# Usage:
#   sudo bash migrate-v1-to-v2.sh [--resume] [--dry-run] [--yes]
#                                 [--rollback] [--purge-old] [--no-snapshot]
#   Overrides (env): LAIA_ARCH_DIR_OVERRIDE, LAIA_ARCH_CREDS_DIR_OVERRIDE,
#                    BACKUP_ROOT, CONTAINER, SRC_LAIA, AGORA_UID, AGORA_GID
set -uo pipefail

# ── Help (works without root) ────────────────────────────────────────────────
for a in "$@"; do
  case "$a" in -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac
done

# ── Root re-exec (preserve env) ──────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
  exec sudo -E bash "$0" "$@"
fi

# ── Admin user / home ────────────────────────────────────────────────────────
ORIG_USER="${SUDO_USER:-${LAIA_ADMIN_USER:-}}"
if [[ -z "$ORIG_USER" || "$ORIG_USER" == "root" ]]; then
  ORIG_USER=$(getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 {print $1; exit}')
fi
[[ -n "$ORIG_USER" ]] || { echo "Cannot determine ORIG_USER (set SUDO_USER or LAIA_ADMIN_USER)" >&2; exit 1; }
ORIG_HOME=$(getent passwd "$ORIG_USER" | cut -d: -f6)
[[ -n "$ORIG_HOME" ]] || { echo "Cannot resolve home for '$ORIG_USER'" >&2; exit 1; }
ARCH_UID="$(id -u "$ORIG_USER")"
ARCH_GID="$(id -g "$ORIG_USER")"

# ── Config (overridable) ─────────────────────────────────────────────────────
CONTAINER="${CONTAINER:-laia-agora}"
SRC_LAIA="${SRC_LAIA:-$ORIG_HOME/.laia}"
ARCH_DIR="${LAIA_ARCH_DIR_OVERRIDE:-/srv/laia/arch}"
SECRETS_DIR="${LAIA_ARCH_CREDS_DIR_OVERRIDE:-$ARCH_DIR/secrets}"
AGORA_DATA_DIR="${HOST_DATA_DIR:-/srv/laia/agora}"
BACKUP_ROOT="${BACKUP_ROOT:-/mnt/data/laia-migration-backups}"
AGORA_UID="${AGORA_UID:-999}"     # user `agora` in the orchestrator image (C2)
AGORA_GID="${AGORA_GID:-988}"
# Marker dir lives OUTSIDE the trees we move/retire, so resume state survives.
MARKER_DIR="${MARKER_DIR:-/srv/laia/.laia-migration-state}"
ROLLBACK_ENV="$MARKER_DIR/rollback.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REBUILD_3B="$SCRIPT_DIR/rebuild-3b-fix-authjson.sh"

# Secret files (live under SRC_LAIA in v1) vs everything-else (runtime).
SECRET_FILES=(auth.json .env admin-session.json)

# ── Flags ────────────────────────────────────────────────────────────────────
RESUME=0; DRY_RUN=0; ASSUME_YES=0; MODE=migrate; PURGE_OLD=0; DO_SNAPSHOT=auto
while [[ $# -gt 0 ]]; do
  case "$1" in
    --resume) RESUME=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --yes|-y) ASSUME_YES=1 ;;
    --rollback) MODE=rollback ;;
    --purge-old) PURGE_OLD=1 ;;
    --no-snapshot) DO_SNAPSHOT=no ;;
    --snapshot) DO_SNAPSHOT=yes ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

# ── Output helpers ───────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; BLD='\033[1m'; RST='\033[0m'
else GRN=''; YEL=''; RED=''; CYN=''; BLD=''; RST=''; fi
log()  { printf "${CYN}▸${RST} %s\n" "$*"; }
ok()   { printf "  ${GRN}✓${RST} %s\n" "$*"; }
warn() { printf "  ${YEL}⚠${RST} %s\n" "$*"; }
die()  { printf "  ${RED}✗${RST} %s\n" "$*" >&2; exit 1; }
section() { printf "\n${BLD}== %s ==${RST}\n" "$*"; }
run() {  # echo + execute, or just echo under --dry-run
  if [[ $DRY_RUN -eq 1 ]]; then printf "  ${YEL}[dry-run]${RST} %s\n" "$*"; return 0; fi
  eval "$@"
}

# ── Marker helpers (resume-safe) ─────────────────────────────────────────────
phase_done()  { [[ -f "$MARKER_DIR/$1.done" ]]; }
mark_done()   { [[ $DRY_RUN -eq 1 ]] && return 0; mkdir -p "$MARKER_DIR"; : > "$MARKER_DIR/$1.done"; }
clear_marks() { rm -f "$MARKER_DIR"/*.done 2>/dev/null || true; }
should_skip() { # skip if --resume AND already done
  if [[ $RESUME -eq 1 ]] && phase_done "$1"; then ok "phase '$1' already done (resume) — skip"; return 0; fi
  return 1
}

# ── Rollback journal (records pre-migration container state) ─────────────────
_device_exists() { lxc config device list "$CONTAINER" 2>/dev/null | grep -qx "$1"; }

record_rollback_state() {
  [[ -f "$ROLLBACK_ENV" ]] && return 0   # only capture once (the true v1 state)
  # Capture the EXISTING secrets device generically — v1 may use the file mount
  # `agora-auth` (→ /opt/agora/data/auth.json) or the dir mount `arch-laia`
  # (→ /var/lib/laia-host). Whatever it is, rollback restores it verbatim.
  local idmap dev="" src="" path="" ro="" owner d
  idmap="$(lxc config get "$CONTAINER" raw.idmap 2>/dev/null || true)"
  for d in arch-laia agora-auth; do
    if _device_exists "$d"; then
      dev="$d"
      src="$(lxc config device get "$CONTAINER" "$d" source 2>/dev/null || true)"
      path="$(lxc config device get "$CONTAINER" "$d" path 2>/dev/null || true)"
      ro="$(lxc config device get "$CONTAINER" "$d" readonly 2>/dev/null || true)"
      break
    fi
  done
  owner="$(stat -c '%u:%g' "$AGORA_DATA_DIR" 2>/dev/null || true)"
  if [[ $DRY_RUN -eq 1 ]]; then
    ok "[dry-run] capturaría rollback (idmap=${idmap:-none}, secret-dev=${dev:-none}→${src:-none})"
    return 0
  fi
  mkdir -p "$MARKER_DIR"
  {
    echo "# Pre-migration laia-agora state — used by --rollback. Do not edit."
    echo "PRE_RAW_IDMAP=$(printf '%q' "$idmap")"
    echo "PRE_SECRET_DEV=$(printf '%q' "$dev")"
    echo "PRE_SECRET_SOURCE=$(printf '%q' "$src")"
    echo "PRE_SECRET_PATH=$(printf '%q' "$path")"
    echo "PRE_SECRET_RO=$(printf '%q' "$ro")"
    echo "PRE_AGORA_DATA_OWNER=$(printf '%q' "$owner")"
  } > "$ROLLBACK_ENV"
  ok "rollback state recorded → $ROLLBACK_ENV (secret-dev=${dev:-none})"
}

# ── Health check ─────────────────────────────────────────────────────────────
agora_health_json() {
  local ip
  ip="$(lxc list "$CONTAINER" --format json 2>/dev/null | jq -r '.[0].state.network.eth0.addresses[]? | select(.family=="inet") | .address' | head -1)"
  [[ -n "$ip" ]] || return 1
  curl -fsS -m 5 "http://${ip}:8000/api/health" 2>/dev/null
}
wait_for_health() {  # returns 0 if auth_json_ready==true within timeout
  local j ready
  for _ in $(seq 1 40); do
    j="$(agora_health_json)" || { sleep 0.5; continue; }
    ready="$(echo "$j" | jq -r '.auth_json_ready // false')"
    if [[ "$(echo "$j" | jq -r '.ok // false')" == "true" ]]; then
      echo "$j"; [[ "$ready" == "true" ]] && return 0 || return 3
    fi
    sleep 0.5
  done
  return 1
}

# ─────────────────────────────────────────────────────────────────────────────
# PHASES
# ─────────────────────────────────────────────────────────────────────────────

phase_preflight() {
  section "1) Preflight"
  for bin in lxc jq rsync tar curl install; do command -v "$bin" >/dev/null || die "$bin no encontrado"; done
  # Idempotency: if the migration already finished (cleanup marker) or the host
  # is plainly already v2 (no ~/.laia and secrets present in /srv/laia/arch),
  # there is nothing to do — exit cleanly instead of dying on the v1 check.
  if phase_done cleanup || { [[ ! -d "$SRC_LAIA" ]] && [[ -f "$SECRETS_DIR/auth.json" ]]; }; then
    ok "host ya en v2 (cleanup hecho o ~/.laia ausente + secretos en $SECRETS_DIR) — nada que migrar"
    exit 0
  fi
  [[ -d "$SRC_LAIA" ]] || die "no existe $SRC_LAIA — ¿este host ya es v2 o no es un ARCH v1?"
  [[ -f "$SRC_LAIA/auth.json" ]] || warn "no hay $SRC_LAIA/auth.json (¿secretos ya migrados?)"
  lxc info "$CONTAINER" >/dev/null 2>&1 || die "container $CONTAINER no existe"
  # Disk space sanity on the backup target.
  mkdir -p "$BACKUP_ROOT" 2>/dev/null || die "no puedo crear $BACKUP_ROOT"
  ok "deps OK · origen v1 $SRC_LAIA · container $CONTAINER · backup → $BACKUP_ROOT"
  record_rollback_state
  mark_done preflight
}

phase_backup() {
  should_skip backup && return 0
  section "2) Backup one-shot (origen intacto)"
  local ts dest
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  dest="$BACKUP_ROOT/$ts"
  run "mkdir -p '$dest'"
  # Optional lxc snapshot (instant rollback when inside the dev VM with a
  # snapshottable laia-agora; harmless on prod where it just snapshots the
  # container if the pool supports it).
  if [[ "$DO_SNAPSHOT" != "no" ]]; then
    if [[ $DRY_RUN -eq 1 ]]; then
      ok "[dry-run] lxc snapshot $CONTAINER/pre-v2-migration-$ts"
    elif lxc snapshot "$CONTAINER" "pre-v2-migration-$ts" >/dev/null 2>&1; then
      ok "lxc snapshot $CONTAINER/pre-v2-migration-$ts"
    elif [[ "$DO_SNAPSHOT" == "yes" ]]; then
      die "lxc snapshot falló (--snapshot exigido)"
    else
      warn "lxc snapshot no disponible — sigo solo con tar"
    fi
  fi
  for tree in "$AGORA_DATA_DIR" "$SRC_LAIA" "$ORIG_HOME/LAIA-ARCH"; do
    [[ -e "$tree" ]] || { warn "no existe $tree — me lo salto"; continue; }
    local name; name="$(echo "$tree" | tr '/' '_' | sed 's/^_//')"
    run "tar -C '$(dirname "$tree")' -czf '$dest/${name}.tar.gz' '$(basename "$tree")'"
    ok "backup $tree → $dest/${name}.tar.gz"
  done
  echo "$dest" > "$MARKER_DIR/backup-path.txt" 2>/dev/null || true
  mark_done backup
}

phase_mkdirs() {
  should_skip mkdirs && return 0
  section "3) Crear /srv/laia/arch{,/secrets} con perms"
  run "install -d -o '$ARCH_UID' -g '$ARCH_GID' -m 0750 '$ARCH_DIR'"
  run "install -d -o '$ARCH_UID' -g '$ARCH_GID' -m 0700 '$SECRETS_DIR'"
  run "install -d -o '$ARCH_UID' -g '$ARCH_GID' -m 0700 '$ARCH_DIR/state'"
  ok "$ARCH_DIR (0750) · $SECRETS_DIR (0700) — owned $ORIG_USER"
  mark_done mkdirs
}

# rsync excludes: secrets (handled separately), marker dir, junk.
_runtime_excludes() {
  local ex=()
  for f in "${SECRET_FILES[@]}"; do ex+=(--exclude="/$f"); done
  ex+=(--exclude='.laia-migration-state' --exclude='atlas.yaml.bak-*' --exclude='*.lock' --exclude='pathd.sock')
  printf '%s ' "${ex[@]}"
}

phase_sync_runtime() {
  should_skip sync-runtime && return 0
  section "4) rsync runtime $SRC_LAIA → $ARCH_DIR (origen intacto)"
  # No --delete, no source removal: the origin stays byte-for-byte until green.
  run "rsync -a $(_runtime_excludes) '$SRC_LAIA/' '$ARCH_DIR/'"
  run "chown -R '$ARCH_UID:$ARCH_GID' '$ARCH_DIR'"
  ok "runtime copiado (config.yaml, atlas.yaml, .env.paths, state/, …)"
  mark_done sync-runtime
}

phase_sync_secrets() {
  should_skip sync-secrets && return 0
  section "5) rsync secretos → $SECRETS_DIR (0600, origen intacto)"
  local f
  for f in "${SECRET_FILES[@]}"; do
    if [[ -f "$SRC_LAIA/$f" ]]; then
      run "install -o '$ARCH_UID' -g '$ARCH_GID' -m 0600 '$SRC_LAIA/$f' '$SECRETS_DIR/$f'"
      ok "secreto $f → $SECRETS_DIR/$f (0600)"
    fi
  done
  mark_done sync-secrets
}

phase_anchors() {
  should_skip anchors && return 0
  section "6) Repuntar anclas (pathd → $ARCH_DIR)"
  # C1 already makes the code default to /srv/laia/arch (LAIA_CONFIG_HOME).
  # Here we just nudge a running daemon to re-read from the new home.
  if command -v laia-path >/dev/null 2>&1; then
    run "LAIA_CONFIG_HOME='$ARCH_DIR' laia-path reload >/dev/null 2>&1 || true"
    ok "laia-path reload (LAIA_CONFIG_HOME=$ARCH_DIR)"
  else
    warn "laia-path no en PATH — el daemon tomará $ARCH_DIR por el default de C1 al reiniciar"
  fi
  mark_done anchors
}

phase_swap_mount() {
  should_skip swap-mount && return 0
  section "7) ADD-BEFORE-REMOVE: raw.idmap + swap del mount de secretos"
  record_rollback_state   # ensure captured even on --resume from here

  # 7a. raw.idmap (C2): map host admin uid/gid ↔ container agora uid/gid so the
  # 0600 secrets are readable without world-read. Applied to the EXISTING
  # container (no recreate); LXD re-shifts the rootfs on the next restart.
  local cur_idmap want_idmap
  cur_idmap="$(lxc config get "$CONTAINER" raw.idmap 2>/dev/null || true)"
  want_idmap=$'uid '"$ARCH_UID $AGORA_UID"$'\ngid '"$ARCH_GID $AGORA_GID"
  if [[ "$cur_idmap" == "$want_idmap" ]]; then
    ok "raw.idmap ya fijado"
  else
    log "raw.idmap: host $ARCH_UID/$ARCH_GID ↔ agora $AGORA_UID/$AGORA_GID"
    run "lxc config set '$CONTAINER' raw.idmap 'uid $ARCH_UID $AGORA_UID
gid $ARCH_GID $AGORA_GID'"
  fi
  # The shifted agora user must own its data dir on the host.
  run "chown -R '$ARCH_UID:$ARCH_GID' '$AGORA_DATA_DIR' 2>/dev/null || true"

  # 7a-bis. raw.idmap only takes effect on a container (re)start — LXD re-shifts
  # the rootfs then. rebuild-3b restarts only the backend service, so we must
  # bounce the CONTAINER here first, or its readability check runs before the
  # shift is live. The old ~/.laia mount (0755/644) stays readable through the
  # shift (host uid maps to agora), so this restart is non-destructive.
  if [[ "$cur_idmap" != "$want_idmap" ]]; then
    log "restart $CONTAINER para aplicar raw.idmap (re-shift del rootfs)"
    run "lxc restart '$CONTAINER'"
    if [[ $DRY_RUN -eq 0 ]]; then
      for _ in $(seq 1 30); do
        lxc list "$CONTAINER" -c s --format csv 2>/dev/null | grep -q RUNNING && break; sleep 1
      done
    fi
  fi

  # 7b. Swap the secrets mount to the v2 dir. rebuild-3b is idempotent: it
  # recreates the arch-laia dir-mount from HOST_LAIA_DIR, writes the systemd
  # drop-in, restarts agora and verifies auth_json_ready. The OLD ~/.laia is
  # NOT touched here — only the device source changes — so rollback is a device
  # swap-back.
  if [[ $DRY_RUN -eq 1 ]]; then
    run "HOST_LAIA_DIR='$SECRETS_DIR' bash '$REBUILD_3B'"
  else
    log "swap mount → $SECRETS_DIR (vía rebuild-3b)"
    if ! HOST_LAIA_DIR="$SECRETS_DIR" CONTAINER="$CONTAINER" bash "$REBUILD_3B"; then
      warn "rebuild-3b falló — auto-rollback de este paso"
      do_rollback "fallo en swap-mount"
      die "swap-mount falló; se revirtió al estado v1 (~/.laia intacto)"
    fi
  fi
  mark_done swap-mount
}

phase_verify() {
  should_skip verify && return 0
  section "8) Verificar /api/health (auth_json_ready)"
  if [[ $DRY_RUN -eq 1 ]]; then ok "[dry-run] saltando verify real"; mark_done verify; return 0; fi
  local j rc
  j="$(wait_for_health)"; rc=$?
  echo "$j" | jq '{ok, auth_json_ready, auth_json_status, auth_json_path}' 2>/dev/null || echo "$j"
  if [[ $rc -eq 0 ]]; then
    ok "AGORA verde con secretos en $SECRETS_DIR ✓"
    mark_done verify
  else
    warn "health no verde (rc=$rc) — auto-rollback"
    do_rollback "verify no verde"
    die "verify falló; revertido a v1 (~/.laia intacto)"
  fi
}

phase_cleanup() {
  should_skip cleanup && return 0
  section "9) Retirar el layout viejo (solo en verde)"
  # Safety: re-confirm green before retiring ~/.laia.
  if [[ $DRY_RUN -eq 0 ]]; then
    wait_for_health >/dev/null || die "rehúso retirar ~/.laia: health no verde"
  fi
  local ts archived; ts="$(date -u +%Y%m%dT%H%M%SZ)"; archived="$SRC_LAIA.v1-migrated-$ts"
  if [[ $PURGE_OLD -eq 1 ]]; then
    run "rm -rf '$SRC_LAIA'"
    ok "~/.laia BORRADO (--purge-old)"
  else
    run "mv '$SRC_LAIA' '$archived'"
    ok "~/.laia → $archived (reversible; borra con --purge-old o a mano tras backup)"
  fi
  mark_done cleanup
  section "✅ Migración v1 → v2 COMPLETA"
  echo "  runtime → $ARCH_DIR · secretos → $SECRETS_DIR (0600 vía raw.idmap)"
}

# ── Rollback ─────────────────────────────────────────────────────────────────
do_rollback() {
  local reason="${1:-manual}"
  section "ROLLBACK ($reason)"
  [[ -f "$ROLLBACK_ENV" ]] || die "no hay $ROLLBACK_ENV — no puedo revertir con seguridad"
  # shellcheck source=/dev/null
  source "$ROLLBACK_ENV"
  # Post-cleanup guard: the device-level rollback only works while the v1 source
  # is still on disk (i.e. BEFORE phase_cleanup retired ~/.laia). If cleanup
  # already ran, the source is gone — refuse and point at the backup/snapshot,
  # which is the correct recovery path once the migration completed.
  if [[ -n "${PRE_SECRET_SOURCE:-}" && ! -e "${PRE_SECRET_SOURCE}" ]]; then
    warn "el origen v1 '$PRE_SECRET_SOURCE' ya no existe (cleanup lo retiró)."
    local arch; arch="$(ls -d "${SRC_LAIA}".v1-migrated-* 2>/dev/null | sort | tail -1)"
    [[ -n "$arch" ]] && warn "  restáuralo a mano: mv '$arch' '$SRC_LAIA' antes de --rollback"
    warn "  o usa el snapshot: lxc restore $CONTAINER pre-v2-migration-<ts>"
    warn "  o el tar en $BACKUP_ROOT/<ts>/"
    die "rollback de dispositivo no seguro tras cleanup — usa backup/snapshot"
  fi
  # Revert raw.idmap to its pre-migration value (unset if it had none).
  if [[ -z "${PRE_RAW_IDMAP:-}" ]]; then
    run "lxc config unset '$CONTAINER' raw.idmap 2>/dev/null || true"
    ok "raw.idmap removido (v1 no tenía)"
  else
    run "lxc config set '$CONTAINER' raw.idmap '$PRE_RAW_IDMAP'"
    ok "raw.idmap restaurado"
  fi
  # Revert the agora data ownership.
  if [[ -n "${PRE_AGORA_DATA_OWNER:-}" ]]; then
    run "chown -R '$PRE_AGORA_DATA_OWNER' '$AGORA_DATA_DIR' 2>/dev/null || true"
  fi
  # Drop the v2 secrets mount (rebuild-3b always lands on arch-laia) and restore
  # the exact pre-migration device, whatever its name/source/type was.
  run "lxc stop '$CONTAINER' 2>/dev/null || true"
  for d in arch-laia agora-auth; do
    _device_exists "$d" && run "lxc config device remove '$CONTAINER' '$d' 2>/dev/null || true"
  done
  if [[ -n "${PRE_SECRET_DEV:-}" && -n "${PRE_SECRET_SOURCE:-}" ]]; then
    local addcmd="lxc config device add '$CONTAINER' '$PRE_SECRET_DEV' disk source='$PRE_SECRET_SOURCE' path='$PRE_SECRET_PATH'"
    [[ "${PRE_SECRET_RO:-}" == "true" ]] && addcmd="$addcmd readonly=true"
    run "$addcmd"
    ok "device $PRE_SECRET_DEV restaurado → $PRE_SECRET_SOURCE"
  else
    warn "no había device de secretos registrado — solo reinicio"
  fi
  run "lxc start '$CONTAINER'"
  # ~/.laia is never deleted before 'cleanup', so v1 is intact here.
  clear_marks
  ok "rollback completo · ~/.laia intacto: $([[ -d "$SRC_LAIA" ]] && echo sí || echo NO)"
}

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
main() {
  [[ $DRY_RUN -eq 1 ]] || mkdir -p "$MARKER_DIR"
  printf "${BLD}LAIA migración in-place v1 → v2${RST}\n"
  echo "  user=$ORIG_USER  arch=$ARCH_DIR  secrets=$SECRETS_DIR  container=$CONTAINER"
  [[ $DRY_RUN -eq 1 ]] && warn "DRY-RUN: no se ejecuta nada"

  if [[ "$MODE" == "rollback" ]]; then
    do_rollback "manual (--rollback)"
    return 0
  fi

  if [[ $ASSUME_YES -ne 1 && $DRY_RUN -ne 1 ]]; then
    read -rp "Proceder con la migración in-place? [y/N] " a
    [[ "$a" =~ ^[Yy] ]] || die "abortado por el usuario"
  fi

  phase_preflight
  phase_backup
  phase_mkdirs
  phase_sync_runtime
  phase_sync_secrets
  phase_anchors
  phase_swap_mount
  phase_verify
  phase_cleanup
}

main "$@"
