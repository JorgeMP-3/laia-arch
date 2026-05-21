#!/usr/bin/env bash
set -euo pipefail

# NOTE: This legacy script installs an unrendered systemd unit. The supported
# flow is `laia-install` which renders templates from infra/installer/systemd/*.tmpl
# via systemd_install_all. Keeping this for ad-hoc reinstallation only.
if [[ -z "${LAIA_ROOT:-}" ]]; then
  _script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  LAIA_ROOT="$(git -C "$_script_dir" rev-parse --show-toplevel 2>/dev/null || cd "$_script_dir/../.." && pwd)"
  unset _script_dir
fi
SERVICE_SRC="${SERVICE_SRC:-$LAIA_ROOT/infra/installer/systemd/agora-backend.service.tmpl}"
SERVICE_DST="/etc/systemd/system/agora-backend.service"
[[ -f "$SERVICE_SRC" ]] || { echo "Service template not found: $SERVICE_SRC" >&2; exit 1; }

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

install -m 0644 "$SERVICE_SRC" "$SERVICE_DST"
systemctl daemon-reload
systemctl enable agora-backend.service

echo "Installed agora-backend.service. Start with: systemctl start agora-backend"

