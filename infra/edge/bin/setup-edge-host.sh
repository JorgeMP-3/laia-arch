#!/usr/bin/env bash
# FASE 2 del edge — layout /srv/laia/web, permisos, binds a laia-uis/laia-edge, Caddyfile.
# NO toca el túnel (Odoo sigue por el cloudflared del host). DEBE correr como root:
#   sudo bash ~/laia-edge/bin/setup-edge-host.sh
# Idempotente.
set -euo pipefail
[[ "$EUID" -eq 0 ]] || { echo "Debe correr como root: sudo bash $0" >&2; exit 1; }
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE=/srv/laia/web
# laia-uis y laia-edge son unprivileged con base idmap 1000000; laia-uis compila como root
# (host 1000000) y escribe estáticos world-readable → el caddy de laia-edge los lee por "other".
MAP=1000000

echo "== layout $BASE =="
mkdir -p "$BASE"/{sites/agora,edge/secrets,src}
chown -R "$MAP:$MAP" "$BASE/sites" "$BASE/src"      # laia-uis (root) escribe aquí
chmod -R u=rwX,go=rX "$BASE/sites" "$BASE/src"       # world-readable → caddy de laia-edge lee
chown root:root "$BASE/edge"; chmod 0755 "$BASE/edge"

# placeholder de la raíz hasta que se compile la UI de AGORA
if [[ ! -f "$BASE/sites/agora/index.html" ]]; then
  cat > "$BASE/sites/agora/index.html" <<'H'
<!doctype html><meta charset=utf-8><title>laiajmp.org</title>
<h1>laiajmp.org — edge operativo</h1><p>UI de AGORA pendiente de desplegar (build en laia-uis).</p>
H
  chown "$MAP:$MAP" "$BASE/sites/agora/index.html"; chmod 0644 "$BASE/sites/agora/index.html"
fi

# Caddyfile (config, no secreto → world-readable; el caddy lo lee por "other")
install -m 0644 "$REPO/config/Caddyfile" "$BASE/edge/Caddyfile"

echo "== binds LXC (idempotentes) =="
dev() { lxc config device get "$1" "$2" source >/dev/null 2>&1 || lxc config device add "$@"; }
dev laia-uis  web-sites disk source="$BASE/sites" path=/srv/web/sites
dev laia-uis  web-src   disk source="$BASE/src"   path=/srv/web/src
dev laia-edge web-sites disk source="$BASE/sites" path=/srv/web/sites readonly=true
dev laia-edge caddyfile disk source="$BASE/edge/Caddyfile" path=/etc/caddy/Caddyfile readonly=true

echo "== arrancar Caddy =="
lxc exec laia-edge -- systemctl enable --now caddy >/dev/null 2>&1 || true
lxc exec laia-edge -- systemctl restart caddy
sleep 3

echo "== VERIFICACIÓN (probando el Caddy del edge directo, sin tocar el túnel) =="
echo -n "  caddy: "; lxc exec laia-edge -- systemctl is-active caddy
echo -n "  odoo vía edge (Host: odoo.laiajmp.org → Caddy → 10.99.0.50:8069): "
curl -s -H 'Host: odoo.laiajmp.org' -o /dev/null -w '%{http_code}\n' --max-time 12 http://10.99.0.51/web/login
echo -n "  raíz vía edge (Host: laiajmp.org → estáticos AGORA): "
curl -s -H 'Host: laiajmp.org' -o /dev/null -w '%{http_code}\n' --max-time 12 http://10.99.0.51/
echo "== Si ambos dan 200/303/200, el edge enruta bien. Siguiente: cutover-tunnel.sh =="
