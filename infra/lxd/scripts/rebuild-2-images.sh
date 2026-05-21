#!/usr/bin/env bash
# rebuild-2-images.sh — fase 2: construir imágenes LXD desde cero.
#
# Borra las imágenes laia-agent y laia-agora si existen y las
# reconstruye con el código actual del repo. Las imágenes son blobs
# inmutables — cualquier cambio en services/{agora-backend,laia-executor}
# o en .laia-core/ requiere rebuild para entrar en efecto dentro de los
# containers.
#
# Tardas ~5-8 min cada imagen en ARM aarch64 (apt update + pip install).
# Total esperado: 10-15 min.
#
# Logs detallados: /tmp/build-base.log y /tmp/build-agora.log.

set -uo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Necesito sudo (lxc image build)." >&2
  exec sudo -E bash "$0" "$@"
fi

ORIG_USER="${SUDO_USER:-${LAIA_ADMIN_USER:-}}"
if [[ -z "$ORIG_USER" || "$ORIG_USER" == "root" ]]; then
  # Fallback: first regular user (UID >= 1000, not nobody)
  ORIG_USER=$(getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 {print $1; exit}')
fi
[[ -n "$ORIG_USER" ]] || { echo "Cannot determine ORIG_USER (set SUDO_USER or LAIA_ADMIN_USER)" >&2; exit 1; }
ORIG_HOME=$(getent passwd "$ORIG_USER" | cut -d: -f6)
[[ -n "$ORIG_HOME" ]] || { echo "Cannot resolve home for user '$ORIG_USER'" >&2; exit 1; }
REPO="${LAIA_ROOT:-$ORIG_HOME/LAIA}"

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; BLD='\033[1m'; RST='\033[0m'
else GRN=''; YEL=''; RED=''; CYN=''; BLD=''; RST=''; fi
log()  { printf "${CYN}▸${RST} %s\n" "$*"; }
ok()   { printf "  ${GRN}✓${RST} %s\n" "$*"; }
warn() { printf "  ${YEL}⚠${RST} %s\n" "$*"; }
die()  { printf "  ${RED}✗${RST} %s\n" "$*" >&2; exit 1; }
section() { printf "\n${BLD}== %s ==${RST}\n" "$*"; }

command -v lxc >/dev/null || die "lxc no encontrado en PATH"
[[ -d "$REPO" ]] || die "LAIA_ROOT not found: $REPO"

# ────────────────────────────────────────────────────────────────────────────
section "1/4 Verificar pre-requisitos"
# ────────────────────────────────────────────────────────────────────────────
[[ -d "$REPO/services/laia-executor" ]] || die "services/laia-executor missing"
[[ -d "$REPO/services/agora-backend" ]] || die "services/agora-backend missing"
[[ -d "$REPO/.laia-core" ]] || die ".laia-core missing"
[[ -d "$REPO/workspace_store" ]] || die "workspace_store missing"
ok "estructura del repo OK"

# Profile laia-employee (lo necesita create-agent.sh para usuarios).
if ! lxc profile show laia-employee >/dev/null 2>&1; then
  log "creando profile laia-employee"
  lxc profile create laia-employee 2>/dev/null || true
  lxc profile edit laia-employee < "$REPO/infra/lxd/profiles/laia-employee.yaml"
  ok "profile laia-employee aplicado"
else
  ok "profile laia-employee ya existe"
fi

# Profile laia-agora (lo necesita create-agora.sh y rebuild-3).
if ! lxc profile show laia-agora >/dev/null 2>&1; then
  log "creando profile laia-agora"
  lxc profile create laia-agora 2>/dev/null || true
  if [[ -f "$REPO/infra/lxd/profiles/laia-agora.yaml" ]]; then
    lxc profile edit laia-agora < "$REPO/infra/lxd/profiles/laia-agora.yaml"
    ok "profile laia-agora aplicado"
  else
    warn "profiles/laia-agora.yaml no encontrado — usaré profile default"
  fi
else
  ok "profile laia-agora ya existe"
fi

# ────────────────────────────────────────────────────────────────────────────
section "2/4 Borrar imágenes previas"
# ────────────────────────────────────────────────────────────────────────────
for img in laia-agent laia-agora; do
  if lxc image info "$img" >/dev/null 2>&1; then
    log "borrando imagen previa $img"
    lxc image delete "$img" || warn "delete imagen $img falló (continúo)"
    ok "imagen $img eliminada"
  else
    ok "imagen $img no existe (skip)"
  fi
done

# ────────────────────────────────────────────────────────────────────────────
section "3/4 Construir imagen laia-agent (executor + E1 tools)"
# ────────────────────────────────────────────────────────────────────────────
log "ejecutando build-base-image.sh — log: /tmp/build-base.log (~5-8 min)"
if ! LAIA_ROOT="$REPO" bash "$REPO/infra/lxd/image-build/build-base-image.sh" >/tmp/build-base.log 2>&1; then
  echo ""
  echo "--- últimas 30 líneas de /tmp/build-base.log ---"
  tail -30 /tmp/build-base.log
  die "build-base-image.sh falló — ver /tmp/build-base.log"
fi
ok "imagen 'laia-agent' construida"

# ────────────────────────────────────────────────────────────────────────────
section "4/4 Construir imagen laia-agora (cerebro hardened)"
# ────────────────────────────────────────────────────────────────────────────
log "ejecutando build-agora-image.sh — log: /tmp/build-agora.log (~6-10 min)"
if ! LAIA_ROOT="$REPO" bash "$REPO/infra/lxd/image-build/build-agora-image.sh" >/tmp/build-agora.log 2>&1; then
  echo ""
  echo "--- últimas 30 líneas de /tmp/build-agora.log ---"
  tail -30 /tmp/build-agora.log
  die "build-agora-image.sh falló — ver /tmp/build-agora.log"
fi
ok "imagen 'laia-agora' construida"

printf "\n${BLD}Resumen — imágenes disponibles${RST}\n"
lxc image list laia-agent laia-agora --format csv -c lnsdat 2>/dev/null | awk -F, '{printf "    %-15s size=%-10s desc=%s\n", $1, $4, $5}'

printf "\n${GRN}✓ Imágenes listas.${RST} Siguiente paso:\n"
printf "    sudo bash %s/infra/lxd/scripts/rebuild-3-provision-agora.sh\n" "$REPO"
