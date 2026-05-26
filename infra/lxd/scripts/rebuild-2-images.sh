#!/usr/bin/env bash
# rebuild-2-images.sh — fase 2: construir imágenes LXD desde cero.
#
# Borra las imágenes laia-agent y laia-agora si existen y las
# reconstruye con el código actual del repo. Las imágenes son blobs
# inmutables — cualquier cambio en services/{agora-backend,laia-executor}
# o en .laia-core/ requiere rebuild para entrar en efecto dentro de los
# containers.
#
# Tardas ~3-6 min cada imagen en amd64, ~5-10 min en arm64 (apt + pip).
# Total esperado: 6-12 min (amd64), 10-20 min (arm64).
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

ensure_lxd_egress() {
  # Preflight informativo, NO bloqueante. Si los checks fallan, dejamos
  # warnings claros y continuamos — el build de imagen real (apt-get,
  # pip) producirá errores visibles si la red está rota de verdad.
  #
  # Env vars:
  #   LAIA_LXD_NETWORK         (default: lxdbr0)
  #   LAIA_LXD_SUBNET          (default: 10.99.0.0/24)
  #   LAIA_LXD_ADDRESS         (default: 10.99.0.1/24)
  #   LAIA_LXD_EGRESS_IMAGE    (default: ubuntu:24.04)
  #   LAIA_LXD_DEEP_PROBE=1    Lanza un contenedor temporal para validar
  #                            egress end-to-end (lento, descarga imagen
  #                            si no está cacheada; default: skip).
  #   LAIA_LXD_LAUNCH_TIMEOUT  (default: 180s) — sólo aplica si deep probe.
  #   LAIA_LXD_SKIP_EGRESS=1   Salta la sección completa.
  local net="${LAIA_LXD_NETWORK:-lxdbr0}"
  local subnet="${LAIA_LXD_SUBNET:-10.99.0.0/24}"
  local address="${LAIA_LXD_ADDRESS:-10.99.0.1/24}"
  local image="${LAIA_LXD_EGRESS_IMAGE:-ubuntu:24.04}"
  local probe_log="${LAIA_LXD_PROBE_LOG:-/tmp/laia-egress-probe.log}"

  section "1.5/4 Verificar red LXD hacia internet (preflight informativo)"

  if [[ "${LAIA_LXD_SKIP_EGRESS:-0}" == "1" ]]; then
    warn "LAIA_LXD_SKIP_EGRESS=1 — saltando preflight de egress"
    return 0
  fi

  lxd_apply_network_config() {
    log "asegurando forwarding/NAT/DNS en $net"
    sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true
    if [[ -w /etc/sysctl.d ]]; then
      printf '%s\n' 'net.ipv4.ip_forward=1' >/etc/sysctl.d/99-laia-lxd-forward.conf 2>/dev/null || true
    fi
    lxc network set "$net" ipv4.address "$address" >/dev/null 2>&1 || true
    lxc network set "$net" ipv4.nat true >/dev/null 2>&1 || true
    lxc network set "$net" ipv6.address none >/dev/null 2>&1 || true
    lxc network set "$net" dns.mode managed >/dev/null 2>&1 || true
    ip link set "$net" up >/dev/null 2>&1 || true

    local out_if
    out_if="$(ip route show default 2>/dev/null | awk 'NR == 1 {print $5}')"
    if [[ -n "$out_if" ]] && command -v iptables >/dev/null 2>&1; then
      iptables -t nat -C POSTROUTING -s "$subnet" -o "$out_if" -j MASQUERADE 2>/dev/null \
        || iptables -t nat -A POSTROUTING -s "$subnet" -o "$out_if" -j MASQUERADE 2>/dev/null || true
      iptables -C FORWARD -i "$net" -o "$out_if" -j ACCEPT 2>/dev/null \
        || iptables -I FORWARD 1 -i "$net" -o "$out_if" -j ACCEPT 2>/dev/null || true
      iptables -C FORWARD -i "$out_if" -o "$net" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null \
        || iptables -I FORWARD 1 -i "$out_if" -o "$net" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true
    fi
  }

  lxd_delete_partial_instances() {
    local name
    while IFS= read -r name; do
      case "$name" in
        laia-egress-check-*|laia-agent-base|laia-agora-base)
          lxc delete --force "$name" >/dev/null 2>&1 || true
          ;;
      esac
    done < <(lxc list --format csv -c n 2>/dev/null || true)
  }

  # Check host-level — barato, en menos de 5 s, sin contenedores.
  # Devuelve 0 si TODO pasa, ≠0 si algo falla. Siempre informa.
  lxd_host_egress_check() {
    local rc=0

    # 1. lxdbr0 existe y tiene IP. (Bridges Linux suelen reportar
    # state UNKNOWN aunque sean funcionales — el flag IFF_UP en los
    # flags `<...,UP,...>` de `ip link show` es la señal real.)
    if ip link show "$net" 2>/dev/null | grep -qE '(<|,)UP(,|>)'; then
      ok "$net existe y está UP"
    else
      warn "$net no existe o no está UP"
      rc=1
    fi

    if ip -4 addr show dev "$net" 2>/dev/null | grep -q ' inet '; then
      ok "$net tiene IPv4 asignada"
    else
      warn "$net no tiene IPv4 asignada — DHCP/managed network puede estar roto"
      rc=1
    fi

    # 2. Host alcanza archive.ubuntu.com (DNS + ruta + HTTPS).
    if command -v curl >/dev/null 2>&1; then
      if curl --max-time 8 -sSf -o /dev/null https://archive.ubuntu.com/ 2>/dev/null; then
        ok "host alcanza https://archive.ubuntu.com"
      else
        warn "host NO alcanza https://archive.ubuntu.com (DNS/ruta/firewall)"
        rc=1
      fi
    elif command -v getent >/dev/null 2>&1; then
      if getent hosts archive.ubuntu.com >/dev/null 2>&1; then
        ok "host resuelve archive.ubuntu.com (curl no disponible)"
      else
        warn "host NO resuelve archive.ubuntu.com"
        rc=1
      fi
    fi

    # 3. NAT MASQUERADE existe para la subnet LXD (NFT o IPTables).
    local out_if
    out_if="$(ip route show default 2>/dev/null | awk 'NR == 1 {print $5}')"
    if [[ -n "$out_if" ]] && command -v iptables >/dev/null 2>&1; then
      if iptables -t nat -C POSTROUTING -s "$subnet" -o "$out_if" -j MASQUERADE 2>/dev/null; then
        ok "NAT MASQUERADE $subnet → $out_if presente"
      else
        warn "NAT MASQUERADE $subnet → $out_if NO presente (intenté añadirlo arriba)"
        rc=1
      fi
    fi

    # 4. LXD control plane responde para el remoto público.
    if lxc image list "${image%:*}:" --format csv 2>/dev/null | head -n 1 >/dev/null; then
      ok "remoto LXD '${image%:*}:' responde"
    else
      warn "remoto LXD '${image%:*}:' no responde (no fatal: imagen puede estar cacheada)"
      # No marcar como rc=1: la imagen puede estar local.
    fi

    return "$rc"
  }

  # Container probe end-to-end (DEEP). Opt-in vía LAIA_LXD_DEEP_PROBE=1.
  # Descarga 200-300 MB la primera vez. NO fatal: warn + return.
  lxd_deep_probe() {
    local probe="laia-egress-check-$$-deep"
    local launch_timeout="${LAIA_LXD_LAUNCH_TIMEOUT:-180s}"
    local launch_limit
    local ok_route=false ok_dns=false

    case "$launch_timeout" in
      *m) launch_limit="$(( ${launch_timeout%m} * 60 ))" ;;
      *s) launch_limit="${launch_timeout%s}" ;;
      *) launch_limit="$launch_timeout" ;;
    esac
    [[ "$launch_limit" =~ ^[0-9]+$ ]] || launch_limit=180

    lxc delete --force "$probe" >/dev/null 2>&1 || true
    log "deep probe: lanzando $probe ($image, timeout ${launch_timeout}) — log: $probe_log"
    : >"$probe_log"
    lxc launch "$image" "$probe" -p default -p laia-employee >>"$probe_log" 2>&1 &
    local launch_pid=$!
    local waited=0
    while kill -0 "$launch_pid" >/dev/null 2>&1; do
      sleep 5
      waited=$((waited + 5))
      if (( waited >= launch_limit )); then
        warn "lxc launch sigue bloqueado tras ${waited}s; matando cliente LXD y limpiando $probe"
        kill "$launch_pid" >/dev/null 2>&1 || true
        sleep 2
        kill -KILL "$launch_pid" >/dev/null 2>&1 || true
        wait "$launch_pid" >/dev/null 2>&1 || true
        lxc delete --force "$probe" >/dev/null 2>&1 || true
        return 20
      fi
      if (( waited % 15 == 0 )); then
        warn "esperando lxc launch de $probe (${waited}s/${launch_limit}s) — tail $probe_log"
      fi
    done

    if ! wait "$launch_pid"; then
      warn "no pude lanzar contenedor temporal en ${launch_timeout} — ver $probe_log"
      lxc delete --force "$probe" >/dev/null 2>&1 || true
      return 20
    fi

    for _ in {1..45}; do
      if lxc exec -T "$probe" -- sh -lc 'ip -4 addr show dev eth0 | grep -q " inet " && ip route | grep -q "^default "' >/dev/null 2>&1; then
        ok_route=true
        break
      fi
      lxc exec -T "$probe" -- sh -lc 'systemctl restart systemd-networkd 2>/dev/null || true; networkctl renew eth0 2>/dev/null || true; dhclient -4 -v eth0 2>/dev/null || true' >/dev/null 2>&1 || true
      sleep 1
    done

    if [[ "$ok_route" != true ]]; then
      warn "contenedor temporal no obtuvo IPv4/ruta por defecto"
      lxc exec -T "$probe" -- sh -lc 'ip addr; ip route; cat /etc/resolv.conf 2>/dev/null || true' >>"$probe_log" 2>&1 || true
      lxc delete --force "$probe" >/dev/null 2>&1 || true
      return 10
    fi
    ok "contenedor temporal tiene IPv4 y ruta por defecto"

    for _ in {1..25}; do
      if lxc exec -T "$probe" -- getent hosts archive.ubuntu.com >/dev/null 2>&1; then
        ok_dns=true
        break
      fi
      sleep 1
    done

    if [[ "$ok_dns" != true ]]; then
      warn "contenedor temporal no resuelve archive.ubuntu.com"
      lxc exec -T "$probe" -- sh -lc 'cat /etc/resolv.conf; ip route' >>"$probe_log" 2>&1 || true
      lxc delete --force "$probe" >/dev/null 2>&1 || true
      return 11
    fi
    ok "contenedor temporal resuelve archive.ubuntu.com"
    lxc delete --force "$probe" >/dev/null 2>&1 || true
    return 0
  }

  # Flujo principal: aplicar config de red, luego host-level check.
  # Sólo deep probe si LAIA_LXD_DEEP_PROBE=1 o si el host check falló y
  # queremos confirmar end-to-end. NUNCA `die` — el build real catchea.
  lxd_delete_partial_instances
  lxd_apply_network_config

  if lxd_host_egress_check; then
    ok "egress LXD (host-level) verificado"
  else
    warn "checks host-level reportaron problemas (ver arriba)"
    warn "continúo igualmente — el build de imagen catchará errores reales con stdout visible"
  fi

  if [[ "${LAIA_LXD_DEEP_PROBE:-0}" == "1" ]]; then
    if lxd_deep_probe; then
      ok "deep probe OK — contenedor temporal tiene egress end-to-end"
    else
      warn "deep probe falló (rc=$?) — ver $probe_log"
      warn "continúo igualmente; revisa el log si el build subsiguiente falla"
    fi
  else
    log "deep probe (contenedor temporal) desactivado — export LAIA_LXD_DEEP_PROBE=1 para activarlo"
  fi

  return 0
}

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

ensure_lxd_egress

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

# run_build <name> <script> <log>
#   Streams output to stdout AND tee'd to log file, with a periodic heartbeat
#   that shows elapsed time and the last log line so the operator sees real
#   progress (apt/pip don't emit anything for minutes at a time).
#   Env:
#     LAIA_BUILD_QUIET=1     → silent-with-log (legacy, for CI)
#     LAIA_BUILD_HEARTBEAT=N → seconds between heartbeats (default 15)
run_build() {
  local name="$1" script="$2" logf="$3"
  local quiet="${LAIA_BUILD_QUIET:-0}"
  local interval="${LAIA_BUILD_HEARTBEAT:-15}"
  log "ejecutando $(basename "$script") — log: $logf (~5-10 min)"
  : >"$logf"
  if [[ "$quiet" == "1" ]]; then
    if ! LAIA_ROOT="$REPO" bash "$script" >"$logf" 2>&1; then
      echo "--- últimas 30 líneas de $logf ---"; tail -30 "$logf"
      die "$(basename "$script") falló — ver $logf"
    fi
    ok "imagen '$name' construida"
    return 0
  fi
  # Heartbeat watchdog: every $interval seconds while the parent is alive,
  # print elapsed [MM:SS] + last non-empty line of $logf (ANSI-stripped,
  # truncated to 100 chars). Self-terminates when parent dies.
  local start_epoch
  start_epoch="$(date +%s)"
  ( ppid=$$
    while kill -0 "$ppid" 2>/dev/null; do
      sleep "$interval"
      kill -0 "$ppid" 2>/dev/null || break
      local now elapsed mm ss last
      now="$(date +%s)"
      elapsed=$(( now - start_epoch ))
      mm=$(( elapsed / 60 )); ss=$(( elapsed % 60 ))
      last="$(tail -n 5 "$logf" 2>/dev/null \
              | tr -d '\r' \
              | sed -E 's/\x1b\[[0-9;]*[a-zA-Z]//g' \
              | grep -v '^[[:space:]]*$' \
              | tail -n 1 \
              | cut -c1-100)"
      [[ -z "$last" ]] && last="(aún sin salida — apt/pip en silencio)"
      printf "  ${CYN}…${RST} [%02d:%02d] %s · %s\n" "$mm" "$ss" "$name" "$last"
    done
  ) &
  local hb=$!
  local rc=0
  LAIA_ROOT="$REPO" bash "$script" 2>&1 | tee "$logf" || rc=$?
  kill "$hb" 2>/dev/null || true
  wait "$hb" 2>/dev/null || true
  local total mm ss
  total=$(( $(date +%s) - start_epoch ))
  mm=$(( total / 60 )); ss=$(( total % 60 ))
  if [[ "$rc" -ne 0 ]]; then
    echo "--- últimas 30 líneas de $logf ---"; tail -30 "$logf"
    die "$(basename "$script") falló tras ${mm}m${ss}s — ver $logf"
  fi
  ok "imagen '$name' construida en ${mm}m${ss}s"
}

# ────────────────────────────────────────────────────────────────────────────
section "3/4 Construir imagen laia-agent (executor + E1 tools)"
# ────────────────────────────────────────────────────────────────────────────
run_build laia-agent "$REPO/infra/lxd/image-build/build-base-image.sh" /tmp/build-base.log

# ────────────────────────────────────────────────────────────────────────────
section "4/4 Construir imagen laia-agora (cerebro hardened)"
# ────────────────────────────────────────────────────────────────────────────
run_build laia-agora "$REPO/infra/lxd/image-build/build-agora-image.sh" /tmp/build-agora.log

printf "\n${BLD}Resumen — imágenes disponibles${RST}\n"
lxc image list laia-agent laia-agora --format csv -c lnsdat 2>/dev/null | awk -F, '{printf "    %-15s size=%-10s desc=%s\n", $1, $4, $5}'

printf "\n${GRN}✓ Imágenes listas.${RST} Siguiente paso:\n"
printf "    sudo bash %s/infra/lxd/scripts/rebuild-3-provision-agora.sh\n" "$REPO"
