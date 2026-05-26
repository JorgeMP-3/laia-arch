#!/usr/bin/env bash
# build-agora-image.sh — build the `laia-agora` LXD image: the orchestrator
# container that hosts the agora-backend FastAPI service, the AIAgent pool,
# and the shared `.laia-core` runtime.
#
# This image does NOT include any user-facing tool sandbox — tools that run
# on user filesystems are forwarded to per-user `laia-executor` containers
# via HTTP. Tools that run locally (web, vision, image_gen, etc.) execute
# inside this container.
#
# Requirements:
#   - lxc CLI with admin permissions
#   - LXD profile `laia-agora` must exist (see ../profiles/laia-agora.yaml)
#   - Repository LAIA checked out (env LAIA_ROOT, default ~/LAIA)
#
# Usage:
#   bash build-agora-image.sh                     # build with defaults
#   ALIAS=laia-agora-v2 bash build-agora-image.sh # custom alias
#   FORCE=1 bash build-agora-image.sh             # rebuild even if alias exists

set -euo pipefail

BASE_IMAGE="${BASE_IMAGE:-ubuntu:24.04}"
BASE_CONTAINER="${BASE_CONTAINER:-laia-agora-base}"
ALIAS="${ALIAS:-laia-agora}"
PROFILE="${PROFILE:-laia-agora}"
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
[[ -d "$LAIA_ROOT/.laia-core" ]] || die ".laia-core missing in $LAIA_ROOT"
[[ -d "$LAIA_ROOT/services/agora-backend" ]] || die "agora-backend missing"
[[ -d "$LAIA_ROOT/workspace_store" ]] || die "workspace_store missing"

lxc profile show "$PROFILE" >/dev/null 2>&1 \
  || die "missing LXD profile: $PROFILE (apply infra/lxd/profiles/laia-agora.yaml)"

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

# ── prepare source tarball ───────────────────────────────────────────────────

info "preparing source tarball from $LAIA_ROOT"
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT
TAR="$TMPDIR/laia-agora-src.tar.gz"

( cd "$LAIA_ROOT" && tar \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='node_modules' \
    --exclude='.pytest_cache' \
    --exclude='.mypy_cache' \
    --exclude='.ruff_cache' \
    --exclude='.venv' \
    --exclude='venv' \
    --exclude='archived' \
    -czf "$TAR" \
      .laia-core \
      workspace_store \
      services/agora-backend \
      services/laia-executor )
ok "tarball ready: $(du -h "$TAR" | cut -f1)"

# ── launch base container ────────────────────────────────────────────────────

info "launching base container $BASE_CONTAINER from $BASE_IMAGE"
lxc launch "$BASE_IMAGE" "$BASE_CONTAINER" -p default -p "$PROFILE"
sleep 8

# ── wait for container DNS (with static fallback) ───────────────────────────
# See build-base-image.sh for rationale. Same recovery pattern: wait for
# the LXD bridge dnsmasq/DHCP-provided DNS to work; if it doesn't within
# 20 s, fall back to static public resolvers so apt-get can proceed.
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
  apt-get update -y
  apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip \
    sqlite3 \
    ca-certificates curl jq \
    ripgrep \
    git
  apt-get clean
  rm -rf /var/lib/apt/lists/*

  # Non-privileged service account — the systemd unit runs as this user
  # instead of root so a prompt-injected LLM cannot pivot to container
  # admin (write /etc, chown, modprobe, ...). The container is already
  # LXD-unprivileged so even root inside maps to uid 100000 on the host;
  # this adds a second layer (UID separation inside the container).
  if ! id agora >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /usr/sbin/nologin --home /opt/agora agora
  fi
' </dev/null

# ── upload + extract source ─────────────────────────────────────────────────

info "uploading source to container"
lxc file push "$TAR" "$BASE_CONTAINER/tmp/laia-agora-src.tar.gz"

info "extracting source to /opt/agora/app"
lxc exec -T "$BASE_CONTAINER" -- bash -lc '
  set -euo pipefail
  mkdir -p /opt/agora/app /opt/agora/data /opt/agora/data/workspaces
  tar -xzf /tmp/laia-agora-src.tar.gz -C /opt/agora/app
  rm /tmp/laia-agora-src.tar.gz
  ls /opt/agora/app
' </dev/null

# ── seed config.yaml so workspace-context activates with the collective ws ──

info "seeding /opt/agora/data/config.yaml (workspace-context active = collective)"
lxc exec -T "$BASE_CONTAINER" -- bash -lc '
  set -euo pipefail
  cat > /opt/agora/data/config.yaml <<"EOF"
# Bootstrapped by build-agora-image.sh — overridden on first config edit.
plugins:
  workspace-context:
    workspace: collective
    inject_mode: index
    active_workspaces:
      - collective
memory:
  provider: workspace-context
EOF
' </dev/null

# ── build venv ──────────────────────────────────────────────────────────────

info "building Python venv with agora-backend + .laia-core deps"
lxc exec -T "$BASE_CONTAINER" -- bash -lc '
  set -euo pipefail
  python3 -m venv /opt/agora/venv
  /opt/agora/venv/bin/pip install --upgrade pip setuptools wheel
  /opt/agora/venv/bin/pip install pytest
  # Install agora-backend (FastAPI service)
  if [[ -f /opt/agora/app/services/agora-backend/pyproject.toml ]]; then
    /opt/agora/venv/bin/pip install -e /opt/agora/app/services/agora-backend
  elif [[ -f /opt/agora/app/services/agora-backend/requirements.txt ]]; then
    /opt/agora/venv/bin/pip install -r /opt/agora/app/services/agora-backend/requirements.txt
  fi
  # Install laia-executor too: backend integration tests instantiate its ASGI
  # app directly to verify tool forwarding, even though production tool calls
  # are sent to separate per-user executor containers.
  if [[ -f /opt/agora/app/services/laia-executor/pyproject.toml ]]; then
    /opt/agora/venv/bin/pip install -e /opt/agora/app/services/laia-executor
  fi
  # Install .laia-core (motor AIAgent) and its deps. ARCH migrated from
  # requirements.txt to pyproject.toml so we try both — first the
  # package install (pulls deps from pyproject), then fallback to the
  # legacy requirements.txt for backward compat.
  if [[ -f /opt/agora/app/.laia-core/pyproject.toml ]]; then
    /opt/agora/venv/bin/pip install /opt/agora/app/.laia-core
  elif [[ -f /opt/agora/app/.laia-core/requirements.txt ]]; then
    /opt/agora/venv/bin/pip install -r /opt/agora/app/.laia-core/requirements.txt
  fi
' </dev/null

# ── install systemd unit ────────────────────────────────────────────────────

info "fixing ownership for agora user (data dir + venv + app)"
lxc exec -T "$BASE_CONTAINER" -- bash -lc '
  set -euo pipefail
  # The agora user needs RW on /opt/agora/data (bind mount source from
  # /srv/laia/agora — gets chowned again by create-agora.sh post-mount)
  # and R on /opt/agora/{app,venv}.
  chown -R agora:agora /opt/agora/data
  chown -R root:agora /opt/agora/app /opt/agora/venv
  chmod -R g+rX /opt/agora/app /opt/agora/venv
' </dev/null

info "installing hardened systemd unit for agora-backend"
lxc exec -T "$BASE_CONTAINER" -- bash -lc '
  cat > /etc/systemd/system/agora-backend.service <<"EOF"
[Unit]
Description=AGORA Backend — orchestrator API + AIAgent pool
Documentation=file:///opt/agora/app/services/agora-backend/README.md
After=network.target
Wants=network.target

[Service]
Type=simple
User=agora
Group=agora
WorkingDirectory=/opt/agora/app/services/agora-backend
Environment="AGORA_DATA_DIR=/opt/agora/data"
Environment="LAIA_HOME=/opt/agora/data"
Environment="LAIA_ROOT=/opt/agora/app"
Environment="AGORA_COLLECTIVE_WORKSPACE=collective"
Environment="PYTHONPATH=/opt/agora/app:/opt/agora/app/.laia-core"
# Optional operator overrides — file lives in the bind-mounted data dir
# (host: /srv/laia/agora/.env) so the wizard / admin can drop secrets in
# without rebuilding the image. The "-" prefix makes the file optional;
# common keys: AGORA_TELEGRAM_TOKEN, AGORA_DEFAULT_PROVIDER, …
EnvironmentFile=-/opt/agora/data/.env
ExecStart=/opt/agora/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=3
StandardOutput=journal
StandardError=journal

# ─── Hardening (A3) ─────────────────────────────────────────────────────
# Goal: even if the LLM is prompt-injected to ask for destructive
# operations, the systemd unit denies the underlying primitives. The
# container itself is LXD-unprivileged (root inside maps to uid 100000
# on host); these flags add a second wall.
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectClock=yes
ProtectHostname=yes
RestrictNamespaces=yes
RestrictRealtime=yes
RestrictSUIDSGID=yes
LockPersonality=yes
# The backend only writes to /opt/agora/data (bind mount) plus
# transient /tmp and /run (PrivateTmp creates a private namespace).
ReadWritePaths=/opt/agora/data
# Drop all capabilities — the service neither needs to bind privileged
# ports (it listens on :8000, proxy-forwarded by LXD) nor change uids.
CapabilityBoundingSet=
AmbientCapabilities=
# Note: we deliberately keep MemoryDenyWriteExecute=no because uvloop
# and some Pydantic backends use ctypes / dlopen which break under that
# flag. Re-evaluate per environment.

LimitNOFILE=65536
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable agora-backend.service
' </dev/null

# ── snapshot + publish ──────────────────────────────────────────────────────

info "stopping base container for image publish"
lxc stop "$BASE_CONTAINER"

info "publishing image $ALIAS"
lxc publish "$BASE_CONTAINER" --alias "$ALIAS" \
  description="LAIA AGORA orchestrator image (built $(date -u +%Y-%m-%dT%H:%M:%SZ))"

info "cleaning up base container"
lxc delete "$BASE_CONTAINER"

ok "image $ALIAS ready"
echo
echo "Next: create the AGORA orchestrator container with:"
echo "  bash $(dirname "$0")/../scripts/create-agora.sh"
