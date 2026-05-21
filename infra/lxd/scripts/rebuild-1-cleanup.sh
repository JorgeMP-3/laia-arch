#!/usr/bin/env bash
# rebuild-1-cleanup.sh — fase 1 de la reconstrucción total.
#
# Limpia el estado de iteración (containers de test, bind mounts, DB de
# AGORA, /tmp state) ANTES de reconstruir las imágenes con el código
# actualizado.
#
# PRESERVA:
#   - laia-jorge container + sus snapshots (sprint 2, fuera de scope)
#   - El user jorge en agora.db + su agent record agent_jorge
#   - /home/laia-hermes/.laia/* (config de ARCH)
#   - Tags git (sprint2-snapshot, etc.)
#
# BORRA:
#   - Containers laia-maria, laia-redesign-test (+ snapshots)
#   - Bind mounts /srv/laia/users/{maria,redesign-test,debugu,secretsor,verifyuser,...}
#   - Todos los users de agora.db excepto jorge
#   - Todos los agents excepto agent_jorge
#   - /tmp/laia-*.json
#   - PM2 agora-backend detenido si existe (no borra entries)
#   - Cualquier uvicorn app.main:app vivo en host
#
# Idempotente. Lánzalo varias veces sin problema.

set -uo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Necesito sudo (lxc delete + rm /srv/laia)." >&2
  exec sudo -E bash "$0" "$@"
fi

ORIG_USER="${SUDO_USER:-laia-hermes}"
ORIG_HOME=$(getent passwd "$ORIG_USER" | cut -d: -f6)
REPO="${LAIA_ROOT:-$ORIG_HOME/LAIA}"
PREFLIGHT="$REPO/infra/dev/preflight.sh"

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; BLD='\033[1m'; RST='\033[0m'
else GRN=''; YEL=''; RED=''; CYN=''; BLD=''; RST=''; fi
log()  { printf "${CYN}▸${RST} %s\n" "$*"; }
ok()   { printf "  ${GRN}✓${RST} %s\n" "$*"; }
warn() { printf "  ${YEL}⚠${RST} %s\n" "$*"; }
die()  { printf "  ${RED}✗${RST} %s\n" "$*" >&2; exit 1; }
section() { printf "\n${BLD}== %s ==${RST}\n" "$*"; }

# ────────────────────────────────────────────────────────────────────────────
section "0/6 Preflight operativo"
# ────────────────────────────────────────────────────────────────────────────
if [[ -x "$PREFLIGHT" ]]; then
  bash "$PREFLIGHT"
  rc=$?
  [[ "$rc" -eq 2 ]] && die "preflight encontró blockers; corrige antes de cleanup"
else
  warn "preflight no encontrado en $PREFLIGHT"
fi

# ────────────────────────────────────────────────────────────────────────────
section "1/6 Detener procesos host"
# ────────────────────────────────────────────────────────────────────────────
# Cualquier agora-backend corriendo como uvicorn en el host, mátalo.
mapfile -t UV_PIDS < <(pgrep -f "uvicorn app.main:app" 2>/dev/null || true)
if [[ ${#UV_PIDS[@]} -eq 0 ]]; then
  ok "no hay uvicorn agora-backend vivo en host"
else
  for pid in "${UV_PIDS[@]}"; do
    log "killing PID $pid"
    kill "$pid" 2>/dev/null || true
  done
  sleep 1
  ok "procesos host detenidos"
fi

# PM2 entry: si tiene "agora-backend", deténlo. No lo borramos ni tocamos
# persistencia; eso queda como decisión explícita del operador.
if sudo -u "$ORIG_USER" command -v pm2 >/dev/null 2>&1; then
  if sudo -u "$ORIG_USER" pm2 jlist 2>/dev/null | grep -q '"name":"agora-backend"'; then
    log "deteniendo entry pm2 'agora-backend'"
    sudo -u "$ORIG_USER" pm2 stop agora-backend 2>/dev/null || true
    ok "pm2 agora-backend detenido"
  else
    ok "pm2 sin entry 'agora-backend'"
  fi
else
  ok "pm2 no instalado (skip)"
fi

# ────────────────────────────────────────────────────────────────────────────
section "2/6 Borrar containers LXD de test (preservando laia-jorge)"
# ────────────────────────────────────────────────────────────────────────────
TEST_CONTAINERS=(laia-maria laia-redesign-test)

for c in "${TEST_CONTAINERS[@]}"; do
  if lxc info "$c" >/dev/null 2>&1; then
    log "borrando $c (incluye sus snapshots)"
    lxc delete --force "$c" || warn "delete $c falló (continúo)"
    ok "$c eliminado"
  else
    ok "$c no existe (skip)"
  fi
done

# También cualquier laia-* o agent-* que NO sea jorge ni laia-agora ni de la
# lista anterior (residuos de runs experimentales o de la migración de
# naming agent-*). laia-jorge y laia-agora son intocables.
mapfile -t STRAY < <(lxc list -c n --format csv 2>/dev/null \
  | grep -E '^(laia-|agent-)' \
  | grep -vE '^(laia-jorge|laia-agora)$' || true)
for s in "${STRAY[@]}"; do
  if [[ " ${TEST_CONTAINERS[*]} " != *" $s "* ]]; then
    log "container stray '$s' detectado — borrándolo"
    lxc delete --force "$s" 2>/dev/null || true
    ok "$s eliminado"
  fi
done

# ────────────────────────────────────────────────────────────────────────────
section "3/6 Limpiar bind mounts /srv/laia/users/"
# ────────────────────────────────────────────────────────────────────────────
if [[ -d /srv/laia/users ]]; then
  for d in /srv/laia/users/*; do
    [[ -d "$d" ]] || continue
    name=$(basename "$d")
    if [[ "$name" == "jorge" ]]; then
      ok "preservando /srv/laia/users/jorge"
      continue
    fi
    log "rm -rf $d"
    rm -rf "$d"
    ok "$d borrado"
  done
else
  ok "/srv/laia/users no existe (skip)"
fi

# ────────────────────────────────────────────────────────────────────────────
section "4/6 Limpiar agora.db (preservar solo jorge + agent_jorge)"
# ────────────────────────────────────────────────────────────────────────────
DB_PATHS=(
  /srv/laia/agora/agora.db
  "$ORIG_HOME/LAIA/services/agora-backend/data/agora.db"
)
DB=""
for p in "${DB_PATHS[@]}"; do
  [[ -f "$p" ]] && { DB="$p"; break; }
done
if [[ -z "$DB" ]]; then
  ok "agora.db no encontrado (skip)"
else
  log "limpiando $DB"
  # Backup defensivo del .db antes de tocar.
  cp -a "$DB" "${DB}.bak-pre-cleanup-$(date +%Y%m%d-%H%M%S)" 2>/dev/null || true
  python3 <<PY || warn "DB cleanup falló (continúo)"
import sqlite3, sys
db = sqlite3.connect("$DB")
db.execute("PRAGMA foreign_keys=OFF")
for table in ("agents", "users"):
    try:
        # Preserve only jorge / agent_jorge.
        if table == "users":
            db.execute("DELETE FROM users WHERE username != 'jorge'")
        elif table == "agents":
            db.execute("DELETE FROM agents WHERE id != 'agent_jorge'")
    except sqlite3.Error as exc:
        print(f"[DB] {table}: {exc}", file=sys.stderr)
# Borra tablas auxiliares que se llenan de basura de testing.
for table in ("conversations", "telegram_links", "events", "tasks"):
    try:
        db.execute(f"DELETE FROM {table}")
    except sqlite3.Error:
        pass
db.commit()
print("[DB] users:", db.execute("SELECT count(*) FROM users").fetchone()[0])
print("[DB] agents:", db.execute("SELECT count(*) FROM agents").fetchone()[0])
db.close()
PY
  ok "agora.db limpio (backup en ${DB}.bak-pre-cleanup-*)"
fi

# ────────────────────────────────────────────────────────────────────────────
section "5/6 Limpiar /tmp state files"
# ────────────────────────────────────────────────────────────────────────────
mapfile -t TMP_FILES < <(find /tmp -maxdepth 1 -name 'laia-*state*.json' 2>/dev/null)
if [[ ${#TMP_FILES[@]} -eq 0 ]]; then
  ok "no hay /tmp/laia-*state*.json"
else
  for f in "${TMP_FILES[@]}"; do
    rm -f "$f"
  done
  ok "borrados ${#TMP_FILES[@]} state files"
fi

# Logs viejos del backend (no críticos)
rm -f /tmp/agora-backend-chat.log /tmp/build-base.log /tmp/build-agora.log

# ────────────────────────────────────────────────────────────────────────────
section "6/6 Resumen"
# ────────────────────────────────────────────────────────────────────────────
printf "\nEstado tras cleanup:\n\n"
echo "▸ Containers:"
lxc list -c n,s --format csv 2>/dev/null | awk -F, '{printf "    %-25s %s\n", $1, $2}'
echo ""
if [[ -n "$DB" ]]; then
  echo "▸ agora.db users:"
  sqlite3 "$DB" 'SELECT username, role FROM users' 2>/dev/null | awk -F'|' '{printf "    %-20s %s\n", $1, $2}'
  echo ""
fi
printf "${GRN}✓ Cleanup completado.${RST} Siguiente paso:\n"
printf "    sudo bash %s/infra/lxd/scripts/rebuild-2-images.sh\n" "$REPO"
