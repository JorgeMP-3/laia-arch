#!/usr/bin/env bash
# build-base-image.sh — build the `laia-agent` LXD image: per-user containers
# that run ONLY `laia-executor` (FastAPI :9091).
#
# Architecture (post-redesign):
#   - NO `.laia-core/` inside the user container — the AIAgent lives in the
#     `laia-agora` orchestrator container instead.
#   - NO `services/laia-runtime/` either — it's been archived; the executor
#     replaces it with a much thinner surface.
#   - The user is root inside the container; this image is minimal so the
#     user can apt-install freely on top of it.
#
# Requirements:
#   - lxc CLI with admin permissions
#   - LXD profile `laia-employee` must exist (see ../profiles/laia-employee.yaml)
#   - Repository LAIA checked out (env LAIA_ROOT, default ~/LAIA)
#
# Usage:
#   bash build-base-image.sh                     # build with defaults
#   ALIAS=laia-agent-v2 bash build-base-image.sh # custom alias
#   FORCE=1 bash build-base-image.sh             # rebuild even if alias exists
#
# Idempotent: refuses to overwrite an existing image alias unless FORCE=1.

set -euo pipefail

BASE_IMAGE="${BASE_IMAGE:-ubuntu:24.04}"
BASE_CONTAINER="${BASE_CONTAINER:-laia-agent-base}"
ALIAS="${ALIAS:-laia-agent}"
PROFILE="${PROFILE:-laia-employee}"
LAIA_ROOT="${LAIA_ROOT:-$HOME/LAIA}"
FORCE="${FORCE:-0}"

if [[ -t 1 ]]; then
  GRN='\033[1;32m'; YEL='\033[1;33m'; RED='\033[1;31m'; CYN='\033[1;36m'; RST='\033[0m'
else
  GRN=''; YEL=''; RED=''; CYN=''; RST=''
fi
info() { printf "${CYN}→${RST} %s\n" "$*"; }
ok()   { printf "${GRN}✓${RST} %s\n" "$*"; }
warn() { printf "${YEL}⚠${RST} %s\n" "$*"; }
die()  { printf "${RED}✗${RST} %s\n" "$*" >&2; exit 1; }

# ── preflight ────────────────────────────────────────────────────────────────

command -v lxc >/dev/null 2>&1 || die "lxc command not found"
[[ -d "$LAIA_ROOT" ]] || die "LAIA_ROOT not found: $LAIA_ROOT"
[[ -d "$LAIA_ROOT/services/laia-executor" ]] || die "services/laia-executor missing in $LAIA_ROOT"

lxc profile show "$PROFILE" >/dev/null 2>&1 \
  || die "missing LXD profile: $PROFILE (apply infra/lxd/profiles/laia-employee.yaml)"

if lxc info "$BASE_CONTAINER" >/dev/null 2>&1; then
  warn "stale base container $BASE_CONTAINER present — removing"
  lxc delete --force "$BASE_CONTAINER"
fi

if lxc image info "$ALIAS" >/dev/null 2>&1; then
  if [[ "$FORCE" == "1" ]]; then
    warn "deleting existing image $ALIAS (FORCE=1)"
    lxc image delete "$ALIAS"
  else
    die "image alias already exists: $ALIAS  (set FORCE=1 to rebuild)"
  fi
fi

# ── prepare executor source tarball ─────────────────────────────────────────

info "preparing source tarball from $LAIA_ROOT/services/laia-executor"
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT
TAR="$TMPDIR/laia-executor-src.tar.gz"

( cd "$LAIA_ROOT" && tar \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='.mypy_cache' \
    --exclude='.ruff_cache' \
    --exclude='.venv' \
    --exclude='venv' \
    -czf "$TAR" \
      services/laia-executor )
ok "tarball ready: $(du -h "$TAR" | cut -f1)"

# ── launch base container ────────────────────────────────────────────────────

info "launching base container $BASE_CONTAINER from $BASE_IMAGE"
lxc launch "$BASE_IMAGE" "$BASE_CONTAINER" -p default -p "$PROFILE"
sleep 8

# ── wait for container DNS (with static fallback) ───────────────────────────
# On some hosts (Ubuntu 24.04+ with NetworkManager or broken dnsmasq on
# lxdbr0), the container's resolved/DHCP-provided DNS fails to reach
# upstream, causing "Temporary failure resolving 'archive.ubuntu.com'".
# We wait up to 20 s for DNS to work; if it doesn't, we drop a static
# /etc/resolv.conf inside the container so the build can proceed.
info "waiting for container DNS"
dns_ok=false
for i in $(seq 1 20); do
  if lxc exec -T "$BASE_CONTAINER" -- getent hosts archive.ubuntu.com >/dev/null 2>&1; then
    dns_ok=true
    break
  fi
  sleep 1
done
if [[ "$dns_ok" != true ]]; then
  warn "container DNS no responde tras 20s — fijando /etc/resolv.conf estático (1.1.1.1, 8.8.8.8)"
  lxc exec -T "$BASE_CONTAINER" -- bash -lc '
    set -uo pipefail
    systemctl stop systemd-resolved 2>/dev/null || true
    systemctl disable systemd-resolved 2>/dev/null || true
    rm -f /etc/resolv.conf
    cat > /etc/resolv.conf <<EOF
nameserver 1.1.1.1
nameserver 8.8.8.8
nameserver 9.9.9.9
EOF
    # Re-test
    getent hosts archive.ubuntu.com >/dev/null 2>&1 || {
      echo "DNS still failing with static resolvers — check host egress" >&2
      exit 1
    }
  ' </dev/null || die "container has no working DNS even with static fallback — check host egress and lxdbr0 NAT"
else
  ok "container DNS OK"
fi

# ── install OS deps ─────────────────────────────────────────────────────────

info "installing OS packages"
lxc exec -T "$BASE_CONTAINER" -- bash -lc '
  set -euo pipefail
  export DEBIAN_FRONTEND=noninteractive
  # stdbuf -oL -eL forces line-buffered stdout/stderr so progress reaches the
  # log in real time (without it, lxc exec keeps everything in apt buffers
  # until the command finishes, making the build look hung from outside).
  stdbuf -oL -eL apt-get update -y
  stdbuf -oL -eL apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip \
    git curl ca-certificates jq sqlite3 ripgrep less \
    sudo
  mkdir -p /opt/laia-executor /etc/laia /var/lib/laia/workspace /opt/laia/plugins
  # The user inside the container is root (LXD unprivileged maps to uid 100000
  # on the host). Provide a /home/user for bind-mounted personal files.
  mkdir -p /home/user
  apt-get clean
  rm -rf /var/lib/apt/lists/*
' </dev/null

# ── push executor source + install ──────────────────────────────────────────

info "uploading executor source"
lxc file push "$TAR" "$BASE_CONTAINER/tmp/laia-executor-src.tar.gz"

info "installing laia-executor into /opt/laia-executor"
lxc exec -T "$BASE_CONTAINER" -- bash -lc '
  set -euo pipefail
  tar -xzf /tmp/laia-executor-src.tar.gz -C /tmp/
  rm /tmp/laia-executor-src.tar.gz
  cp -a /tmp/services/laia-executor/. /opt/laia-executor/
  rm -rf /tmp/services
' </dev/null

info "building python venv at /opt/laia-executor/venv"
lxc exec -T "$BASE_CONTAINER" -- bash -lc '
  set -euo pipefail
  python3 -m venv /opt/laia-executor/venv
  /opt/laia-executor/venv/bin/pip install --upgrade pip setuptools wheel
  /opt/laia-executor/venv/bin/pip install -e /opt/laia-executor
' </dev/null
ok "venv built"

# ── install systemd unit ────────────────────────────────────────────────────

info "installing laia-executor.service"
lxc exec -T "$BASE_CONTAINER" -- bash -lc '
  set -euo pipefail
  install -m 0644 /opt/laia-executor/systemd/laia-executor.service \
      /etc/systemd/system/laia-executor.service
  systemctl daemon-reload
  systemctl enable laia-executor.service
  # Do NOT start now — the per-container token at /etc/laia/executor-token
  # is written by create-agent.sh at provisioning time.
' </dev/null

# ── smoke test (import only — service starts in create-agent.sh) ────────────

info "smoke test: import laia_executor"
lxc exec -T "$BASE_CONTAINER" -- bash -lc '
  set -euo pipefail
  /opt/laia-executor/venv/bin/python -c "
import laia_executor
from laia_executor.api import build_app
from laia_executor.tools.registry import default_registry
assert default_registry.has(\"read_file\")
assert default_registry.has(\"bash\")
print(\"laia-executor import OK; tools=\", len(default_registry.list_tools()))
"
' </dev/null
ok "import smoke test passed"

# ── publish image ───────────────────────────────────────────────────────────

info "stopping container and publishing as $ALIAS"
lxc stop "$BASE_CONTAINER"
lxc publish "$BASE_CONTAINER" --alias "$ALIAS" \
    description="LAIA per-user container image — laia-executor only ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
lxc delete "$BASE_CONTAINER"

ok "Published image: $ALIAS"
info "Next: sudo bash $LAIA_ROOT/infra/lxd/scripts/create-agent.sh <slug>"
