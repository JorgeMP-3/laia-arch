#!/usr/bin/env bash
set -euo pipefail

# ── deploy-agora.sh ───────────────────────────────────────────────────────
# Deploy completo de AGORA: backend + frontend + nginx + systemd
# Uso: ./deploy-agora.sh [--check]
#
#   --check   Solo verifica, no despliega

if [[ -z "${LAIA_ROOT:-}" ]]; then
  _script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  LAIA_ROOT="$(git -C "$_script_dir" rev-parse --show-toplevel 2>/dev/null || cd "$_script_dir/../.." && pwd)"
  unset _script_dir
fi
INFRA_DIR="$LAIA_ROOT/infra"
BACKEND_DIR="$LAIA_ROOT/services/agora-backend"
FRONTEND_DIR="$LAIA_ROOT/laia-ui"
DST_FRONTEND="${AGORA_FRONTEND_DIST:-/srv/laia/agora/frontend/dist}"
DST_DATA="${AGORA_DATA_DIR:-/srv/laia/agora}"
DST_STATE="${LAIA_STATE_ROOT:-/srv/laia/state}"
NGINX_SRC="$INFRA_DIR/nginx/agora.conf"
NGINX_DST="/etc/nginx/sites-enabled/agora.laiajmp.org"
SYSTEMD_SRC="$INFRA_DIR/systemd/agora-backend.service"
SYSTEMD_DST="/etc/systemd/system/agora-backend.service"

CHECK_ONLY=false
if [[ "${1:-}" == "--check" ]]; then
  CHECK_ONLY=true
  echo "=== VERIFICACION (sin desplegar) ==="
fi

# ── 1. Directorios de datos productivos ──────────────────────────────────

echo ""
echo "--- 1. Directorios ---"
if $CHECK_ONLY; then
  for d in "$DST_DATA" "$DST_STATE" "$DST_FRONTEND"; do
    if [[ -d "$d" ]]; then
      echo "  OK  $d"
    else
      echo "  FALTA  $d"
    fi
  done
else
  sudo mkdir -p "$DST_DATA" "$DST_STATE" "$DST_FRONTEND"
  sudo chown -R "${LAIA_DEPLOY_USER:-laia-arch}:${LAIA_DEPLOY_USER:-laia-arch}" "$DST_DATA" "$DST_STATE" "$(dirname "$DST_FRONTEND")"
  echo "  Directorios creados en /srv/laia/"
fi

# ── 2. Backend (Python venv) ─────────────────────────────────────────────

echo ""
echo "--- 2. Backend ---"
if [[ -d "$BACKEND_DIR/.venv" ]]; then
  echo "  OK  venv existe"
else
  echo "  Creando venv..."
  $CHECK_ONLY || python3 -m venv "$BACKEND_DIR/.venv"
fi
$CHECK_ONLY || "$BACKEND_DIR/.venv/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"
echo "  OK  dependencias instaladas"

# ── 3. systemd service ───────────────────────────────────────────────────

echo ""
echo "--- 3. systemd ---"
if $CHECK_ONLY; then
  if [[ -f "$SYSTEMD_DST" ]]; then
    echo "  OK  $SYSTEMD_DST"
  else
    echo "  FALTA  $SYSTEMD_DST"
  fi
else
  sudo cp "$SYSTEMD_SRC" "$SYSTEMD_DST"
  sudo systemctl daemon-reload
  sudo systemctl enable agora-backend.service
  sudo systemctl restart agora-backend.service
  echo "  Servicio instalado y reiniciado"
fi

# ── 4. Frontend build ────────────────────────────────────────────────────

echo ""
echo "--- 4. Frontend ---"
if $CHECK_ONLY; then
  if [[ -f "$DST_FRONTEND/index.html" ]]; then
    echo "  OK  $DST_FRONTEND/index.html"
  else
    echo "  FALTA  build frontend"
  fi
else
  cd "$FRONTEND_DIR"
  pnpm build:agora
  rm -rf "$DST_FRONTEND"
  mkdir -p "$(dirname "$DST_FRONTEND")"
  cp -r "$FRONTEND_DIR/packages/agora-app/dist" "$DST_FRONTEND"
  echo "  Frontend desplegado en $DST_FRONTEND"
fi

# ── 5. nginx ─────────────────────────────────────────────────────────────

echo ""
echo "--- 5. nginx ---"
if $CHECK_ONLY; then
  if [[ -f "$NGINX_DST" ]] || [[ -L "$NGINX_DST" ]]; then
    echo "  OK  $NGINX_DST"
  else
    echo "  FALTA  $NGINX_DST"
  fi
  sudo nginx -t 2>&1 | head -1
else
  sudo cp "$NGINX_SRC" "$NGINX_DST"
  sudo nginx -t && sudo systemctl reload nginx
  echo "  nginx config activada y recargada"
fi

# ── 6. Verificar ─────────────────────────────────────────────────────────

echo ""
echo "--- 6. Verificacion ---"
sleep 1
if curl -sf http://127.0.0.1:8088/api/health > /dev/null 2>&1; then
  echo "  OK  backend responde en :8088"
else
  echo "  ERR backend no responde"
fi
if curl -sf -H "Host: agora.laiajmp.org" http://127.0.0.1:8090/ > /dev/null 2>&1; then
  echo "  OK  frontend responde en :8090"
else
  echo "  ERR frontend no responde (puede necesitar reinicio nginx)"
fi

echo ""
echo "=== Deploy AGORA completado ==="
echo ""
echo "Endpoints:"
echo "  AGORA backend:  http://127.0.0.1:8088/api/health"
echo "  AGORA frontend: http://127.0.0.1:8090 (via nginx)"
echo "  Dominio publico: https://agora.laiajmp.org (via Cloudflare Tunnel)"
echo ""
echo "Logs:"
echo "  journalctl -u agora-backend -f"
echo "  journalctl -u nginx -f"
