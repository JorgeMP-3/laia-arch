# lib-build.sh — helpers compartidos por build-{base,agora}-image.sh y
# por rebuild-3-provision-agora.sh.
#
# Source-only (no shebang, no main). El script consumidor debe definir
# ok/warn/die y (uno de) info|log. Si sólo define `log`, aliasamos info → log.

declare -f info >/dev/null 2>&1 || info() {
  if declare -f log >/dev/null 2>&1; then log "$@"
  else printf "→ %s\n" "$*"
  fi
}

# ensure_container_network <container> [<bridge>]
#
# Garantiza que el container tiene IPv4 + ruta default + DNS funcional.
# Estrategia escalonada:
#   1. Espera hasta 30 s a IPv4 vía DHCP.
#   2. Si no llega, fuerza dhclient/networkctl renew + 5 s más.
#   3. Si sigue sin venir, configura IP estática derivada del bridge.
#   4. Espera hasta 15 s a DNS funcional.
#   5. Si DNS falla, sobrescribe /etc/resolv.conf con 1.1.1.1/8.8.8.8.
#   6. Si DNS sigue fallando con estático, `die` con diagnóstico.
#
# Variables de entorno:
#   LAIA_LXD_FORCE_STATIC_NET=1  Salta DHCP, directamente static IP.
#   LAIA_LXD_STATIC_IP_SUFFIX    Octeto final para IP estática (default: 249).
ensure_container_network() {
  local container="$1"
  local bridge="${2:-lxdbr0}"
  local force_static="${LAIA_LXD_FORCE_STATIC_NET:-0}"
  local static_suffix="${LAIA_LXD_STATIC_IP_SUFFIX:-249}"

  _ec_has_ipv4() {
    lxc exec -T "$container" -- sh -lc 'ip -4 addr show eth0 2>/dev/null | grep -q " inet "' >/dev/null 2>&1
  }

  _ec_has_route() {
    lxc exec -T "$container" -- sh -lc 'ip route 2>/dev/null | grep -q "^default "' >/dev/null 2>&1
  }

  _ec_has_dns() {
    lxc exec -T "$container" -- getent hosts archive.ubuntu.com >/dev/null 2>&1
  }

  _ec_diag_dump() {
    warn "diagnóstico de red del container $container:"
    lxc exec -T "$container" -- sh -lc 'echo "--- ip -4 addr ---"; ip -4 addr; echo "--- ip route ---"; ip route; echo "--- resolv.conf ---"; cat /etc/resolv.conf 2>/dev/null || true' 2>&1 || true
    warn "diagnóstico del bridge $bridge:"
    lxc network show "$bridge" 2>&1 | sed -e 's/^/    /' || true
  }

  # ── 1. Esperar DHCP (a menos que el usuario fuerce estático) ──────────
  if [[ "$force_static" != "1" ]]; then
    info "waiting for container IPv4 (DHCP)"
    local i ipv4_ok=false
    for i in $(seq 1 30); do
      if _ec_has_ipv4; then
        ipv4_ok=true
        break
      fi
      sleep 1
    done

    # 2. Si no llegó, intentar dhclient/networkctl manual (con timeout
    # corto: dhclient sin servidor se cuelga hasta su timeout de ~60s,
    # que no nos sirve — si el DHCP no respondió en 30s no lo va a hacer).
    if [[ "$ipv4_ok" != true ]]; then
      warn "no IPv4 tras 30s — intentando dhclient/networkctl manual (timeout 8s)"
      lxc exec -T "$container" -- bash -lc '
        set +e
        systemctl restart systemd-networkd 2>/dev/null
        timeout 5 networkctl renew eth0 2>/dev/null
        timeout 8 dhclient -1 -4 -v eth0 2>/dev/null
      ' </dev/null >/dev/null 2>&1 || true
      for i in $(seq 1 5); do
        if _ec_has_ipv4; then
          ipv4_ok=true
          break
        fi
        sleep 1
      done
    fi
  else
    warn "LAIA_LXD_FORCE_STATIC_NET=1 — saltando DHCP, directo a estático"
    local ipv4_ok=false
  fi

  # ── 3. Fallback: IP estática derivada del bridge ──────────────────────
  if [[ "$ipv4_ok" != true ]]; then
    local bridge_addr bridge_ip bridge_prefix bridge_net static_ip
    bridge_addr=$(lxc network get "$bridge" ipv4.address 2>/dev/null || true)
    # bridge_addr e.g. "10.99.0.1/24"
    if [[ "$bridge_addr" =~ ^([0-9]+\.[0-9]+\.[0-9]+)\.([0-9]+)/([0-9]+)$ ]]; then
      bridge_net="${BASH_REMATCH[1]}"
      bridge_ip="${bridge_net}.${BASH_REMATCH[2]}"
      bridge_prefix="${BASH_REMATCH[3]}"
      static_ip="${bridge_net}.${static_suffix}/${bridge_prefix}"
    else
      bridge_net="10.99.0"; bridge_ip="10.99.0.1"; bridge_prefix=24
      static_ip="10.99.0.${static_suffix}/24"
      warn "no pude parsear ipv4.address del bridge $bridge — usando default $static_ip"
    fi

    warn "DHCP no asignó IPv4; configurando estático $static_ip → gw $bridge_ip"
    lxc exec -T "$container" -- bash -lc "
      set +e
      ip link set eth0 up
      # Quita IPs previas en eth0 para evitar duplicado.
      for a in \$(ip -4 -o addr show eth0 2>/dev/null | awk '{print \$4}'); do
        ip addr del \"\$a\" dev eth0 2>/dev/null
      done
      ip addr add $static_ip dev eth0 2>/dev/null
      ip route del default 2>/dev/null
      ip route add default via $bridge_ip 2>/dev/null
    " </dev/null >/dev/null 2>&1 || true

    if _ec_has_ipv4 && _ec_has_route; then
      ok "IP estática $static_ip aplicada al container"
    else
      _ec_diag_dump
      die "container sigue sin IPv4/ruta tras fallback estático — bridge $bridge probablemente roto"
    fi
  else
    ok "container tiene IPv4 vía DHCP"
  fi

  # ── 4. Esperar DNS funcional ──────────────────────────────────────────
  info "waiting for container DNS"
  local dns_ok=false j
  for j in $(seq 1 15); do
    if _ec_has_dns; then
      dns_ok=true
      break
    fi
    sleep 1
  done

  # ── 5. Fallback: resolv.conf estático ─────────────────────────────────
  if [[ "$dns_ok" != true ]]; then
    warn "DNS no resuelve tras 15s — fijando /etc/resolv.conf estático (1.1.1.1, 8.8.8.8, 9.9.9.9)"
    lxc exec -T "$container" -- bash -lc '
      set +e
      systemctl stop systemd-resolved 2>/dev/null
      systemctl disable systemd-resolved 2>/dev/null
      # /etc/resolv.conf puede ser un symlink al stub de systemd-resolved.
      rm -f /etc/resolv.conf
      cat > /etc/resolv.conf <<EOF
nameserver 1.1.1.1
nameserver 8.8.8.8
nameserver 9.9.9.9
EOF
    ' </dev/null >/dev/null 2>&1 || true

    if _ec_has_dns; then
      ok "DNS estático funcionando"
    else
      _ec_diag_dump
      die "container sin DNS funcional ni con resolvers estáticos — revisa NAT host y conectividad real"
    fi
  else
    ok "container DNS OK"
  fi
}
