#!/usr/bin/env bash
set -euo pipefail

SERVICE_SRC="${SERVICE_SRC:-/home/laia-hermes/LAIA/infra/systemd/agora-backend.service}"
SERVICE_DST="/etc/systemd/system/agora-backend.service"

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

install -m 0644 "$SERVICE_SRC" "$SERVICE_DST"
systemctl daemon-reload
systemctl enable agora-backend.service

echo "Installed agora-backend.service. Start with: systemctl start agora-backend"

