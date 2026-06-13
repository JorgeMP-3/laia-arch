#!/usr/bin/env bash
# FASE 3 del edge — migra el túnel `doyouwin` del host al LXC laia-edge.
# cloudflared pasa a correr en laia-edge enviando TODO a su Caddy (localhost:80).
# DEBE correr como root:  sudo bash ~/laia-edge/bin/cutover-tunnel.sh
# Cutover con solape (Cloudflare admite varias conexiones por túnel) → corte ~nulo.
set -euo pipefail
[[ "$EUID" -eq 0 ]] || { echo "Debe correr como root: sudo bash $0" >&2; exit 1; }

HOST_CFG=/etc/cloudflared/config.yml
[[ -f "$HOST_CFG" ]] || { echo "No hay $HOST_CFG (¿cloudflared del host?)" >&2; exit 1; }
TID="$(awk '/^tunnel:/{print $2}' "$HOST_CFG")"
CREDS="/etc/cloudflared/$TID.json"
[[ -f "$CREDS" ]] || { echo "No encuentro credenciales $CREDS" >&2; exit 1; }
echo "[*] túnel: $TID"

echo "[*] copiar credenciales al laia-edge"
lxc exec laia-edge -- mkdir -p /etc/cloudflared
lxc file push "$CREDS" "laia-edge/etc/cloudflared/$TID.json" --mode 0600

echo "[*] escribir config de cloudflared en laia-edge (todo → Caddy local)"
lxc exec laia-edge -- bash -c "cat > /etc/cloudflared/config.yml <<EOF
tunnel: $TID
credentials-file: /etc/cloudflared/$TID.json
ingress:
  - service: http://localhost:80
EOF"

echo "[*] systemd cloudflared en laia-edge"
lxc exec laia-edge -- bash -c 'cat > /etc/systemd/system/cloudflared.service <<EOF
[Unit]
Description=cloudflared tunnel (doyouwin) — edge
After=network-online.target
Wants=network-online.target
[Service]
ExecStart=/usr/bin/cloudflared --no-autoupdate --config /etc/cloudflared/config.yml tunnel run
Restart=on-failure
RestartSec=5
User=root
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable --now cloudflared'
sleep 7

echo "[*] el edge ya sirve el túnel; verificación con solape:"
curl -s -o /dev/null -w '  odoo (solape) → %{http_code}\n' --max-time 15 https://odoo.laiajmp.org/web/login || true

echo "[*] parar cloudflared del HOST (cutover)"
systemctl stop cloudflared && systemctl disable cloudflared >/dev/null 2>&1 || true
sleep 5

echo "== VERIFICACIÓN FINAL (ya solo por laia-edge) =="
echo -n "  cloudflared@laia-edge: "; lxc exec laia-edge -- systemctl is-active cloudflared
echo -n "  cloudflared@host (debe estar inactive): "; systemctl is-active cloudflared || true
for i in 1 2 3 4; do
  o=$(curl -s -o /dev/null -w '%{http_code}' --max-time 12 https://odoo.laiajmp.org/web/login || true)
  r=$(curl -s -o /dev/null -w '%{http_code}' --max-time 12 https://laiajmp.org/ || true)
  echo "  odoo.laiajmp.org=$o  ·  laiajmp.org=$r"
  [[ "$o" =~ ^(200|303)$ && "$r" == "200" ]] && { echo "  ✅ edge operativo"; break; }
  sleep 6
done
echo "== Cutover hecho. El edge (laia-edge) es ahora el único punto: cloudflared + Caddy. =="
