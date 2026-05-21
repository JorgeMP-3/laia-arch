#!/usr/bin/env bash
# install-systemd-units.sh — DEPRECATED legacy unit installer.
#
# As of installer-v2 (2026-05-21) systemd units are rendered from
# infra/installer/systemd/*.service.tmpl by `laia-install` and friends.
# The raw infra/systemd/*.service files were archived to
# archived/legacy-systemd-units-pre-installer-v2.20260521/.
#
# Use the proper flow instead:
#     sudo -E laia-install --from-local "$PWD" [--minimal]
# or for templates only:
#     sudo bash -c 'source infra/installer/lib/{common,sudo,version,install,systemd}.sh; \
#                   inst_compute_paths; systemd_install_all'
#
# This wrapper now refuses to run to prevent surprise regressions.
set -euo pipefail

echo "install-systemd-units.sh is DEPRECATED — use laia-install (see comment block at top of this file)." >&2
exit 2

# (Legacy logic preserved below for reference, but unreachable.)

# Detect the real user home — under sudo, $HOME points to /root.
if [ -n "${SUDO_USER:-}" ]; then
    REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
    REAL_HOME="$HOME"
fi

# Source the path registry from the real user's .laia (best effort).
ENV_PATHS="${LAIA_HOME:-$REAL_HOME/.laia}/.env.paths"
# shellcheck disable=SC1090
[ -f "$ENV_PATHS" ] && source "$ENV_PATHS"

SRC="${LAIA_SYSTEMD_UNITS:-$REAL_HOME/LAIA/infra/systemd}"
DST="/etc/systemd/system"

# Mapping: source filename -> installed filename.
# The UI service ships as laia-ui-server.service in the repo but lives as
# workspace-ui.service on disk for historical reasons.
declare -A UNIT_MAP=(
    [agora-backend.service]=agora-backend.service
    [laia-gateway.service]=laia-gateway.service
    [laia-ui-server.service]=workspace-ui.service
)

if [ ! -d "$SRC" ]; then
    echo "error: source dir not found: $SRC" >&2
    exit 1
fi

echo "Source: $SRC"
echo "Target: $DST"
echo "Units:"
for src_name in "${!UNIT_MAP[@]}"; do
    echo "  $src_name -> $DST/${UNIT_MAP[$src_name]}"
done
echo

for src_name in "${!UNIT_MAP[@]}"; do
    dst_name="${UNIT_MAP[$src_name]}"
    if [ ! -f "$SRC/$src_name" ]; then
        echo "warn: $src_name not found in $SRC, skipping" >&2
        continue
    fi
    # Quick backup of the current installed unit
    if [ -f "$DST/$dst_name" ]; then
        sudo cp "$DST/$dst_name" "$DST/$dst_name.bak.$(date +%s)"
    fi
    echo "  copying $src_name -> $dst_name..."
    sudo cp "$SRC/$src_name" "$DST/$dst_name"
done

echo
echo "Reloading systemd..."
sudo systemctl daemon-reload

echo "Restarting services..."
# Map unit filename -> service name (workspace-ui is the running name for laia-ui-server)
sudo systemctl restart agora-backend.service laia-gateway.service workspace-ui.service

echo
echo "Status:"
systemctl status agora-backend laia-gateway workspace-ui --no-pager | head -40 || true
