#!/usr/bin/env bash
set -euo pipefail

POOL_NAME="${POOL_NAME:-default}"
NETWORK_NAME="${NETWORK_NAME:-lxdbr0}"
NETWORK_IPV4="${NETWORK_IPV4:-10.99.0.1/24}"

if ! command -v lxc >/dev/null 2>&1; then
  echo "lxc command not found" >&2
  exit 1
fi

if ! lxc version >/dev/null 2>&1; then
  echo "LXD is not responding" >&2
  exit 1
fi

if lxc storage list --format csv | cut -d, -f1 | grep -qx "$POOL_NAME"; then
  echo "Storage pool already exists: $POOL_NAME"
else
  lxc storage create "$POOL_NAME" dir
  echo "Created storage pool: $POOL_NAME (driver=dir)"
fi

if lxc network list --format csv | cut -d, -f1 | grep -qx "$NETWORK_NAME"; then
  echo "Network already exists: $NETWORK_NAME"
else
  lxc network create "$NETWORK_NAME" \
    ipv4.address="$NETWORK_IPV4" \
    ipv4.nat=true \
    ipv6.address=none
  echo "Created network: $NETWORK_NAME ($NETWORK_IPV4)"
fi

# UFW + LXD: si UFW está activo con política INPUT DROP, captura los
# DHCP DISCOVERs (udp/67) de los containers ANTES de que las reglas
# LXD los acepten. Causa raíz documentada del DHCP roto en hosts con
# UFW activo (típico Ubuntu LTS). Fix idempotente.
#
# Esto se hace AQUÍ (init-defaults siempre corre) en lugar de en
# rebuild-2-images.sh::ensure_lxd_egress porque rebuild-2 se salta si
# las imágenes ya están presentes — y entonces el fix nunca se aplica.
if command -v ufw >/dev/null 2>&1; then
  if [[ $EUID -ne 0 ]]; then
    SUDO_CMD="sudo"
  else
    SUDO_CMD=""
  fi
  if $SUDO_CMD ufw status 2>/dev/null | head -1 | grep -qi 'Status: active'; then
    if $SUDO_CMD ufw status 2>/dev/null | grep -qE "Anywhere on $NETWORK_NAME|on $NETWORK_NAME[[:space:]]+ALLOW IN"; then
      echo "UFW: regla 'allow in on $NETWORK_NAME' ya presente"
    else
      echo "UFW activo — añadiendo 'allow in on $NETWORK_NAME' (fix DHCP containers)"
      if $SUDO_CMD ufw allow in on "$NETWORK_NAME" >/dev/null 2>&1; then
        $SUDO_CMD ufw reload >/dev/null 2>&1 || true
        echo "UFW: regla 'allow in on $NETWORK_NAME' añadida"
      else
        echo "WARN: 'ufw allow in on $NETWORK_NAME' falló — añádela a mano: sudo ufw allow in on $NETWORK_NAME && sudo ufw reload" >&2
      fi
    fi
  fi
fi

echo "LXD defaults ready."

