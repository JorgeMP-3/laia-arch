#!/usr/bin/env bash
# build-base-image.sh — build the `laia-agent` LXD image with everything an agent
# child needs: code, venv, systemd units, healthcheck, user.
#
# Requirements:
#   - lxc CLI with admin permissions
#   - LXD profile `laia-employee` must exist (see ../profiles/)
#   - Repository LAIA checked out (env LAIA_ROOT, default ~/LAIA)
#
# Usage:
#   bash build-base-image.sh                     # build with defaults
#   ALIAS=laia-agent-v2 bash build-base-image.sh # custom alias
#   FORCE=1 bash build-base-image.sh             # rebuild even if alias exists
#
# Idempotent: refuses to overwrite an existing image alias unless FORCE=1.

set -euo pipefail

BASE_IMAGE="${BASE_IMAGE:-ubuntu:22.04}"
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
[[ -d "$LAIA_ROOT/.laia-core" ]] || die ".laia-core missing in $LAIA_ROOT"
[[ -d "$LAIA_ROOT/workspace_store" ]] || die "workspace_store missing in $LAIA_ROOT"
[[ -d "$LAIA_ROOT/services/laia-runtime/src" ]] || die "laia-runtime missing"

lxc profile show "$PROFILE" >/dev/null 2>&1 \
  || die "missing LXD profile: $PROFILE  (create with: lxc profile create $PROFILE; then apply infra/lxd/profiles/laia-employee.yaml)"

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

# ── prepare source tarball on host ───────────────────────────────────────────

info "preparing source tarball from $LAIA_ROOT"
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT
TAR="$TMPDIR/laia-agent-src.tar.gz"

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
    -czf "$TAR" \
      .laia-core \
      workspace_store \
      services/laia-runtime/src/laia_agent \
      services/laia-runtime/systemd \
      services/laia-runtime/healthcheck.sh )
ok "tarball ready: $(du -h "$TAR" | cut -f1)"

# ── launch base container ────────────────────────────────────────────────────

info "launching base container $BASE_CONTAINER from $BASE_IMAGE"
lxc launch "$BASE_IMAGE" "$BASE_CONTAINER" -p default -p "$PROFILE"
sleep 8

# ── install system deps + create user + structure ───────────────────────────

info "installing OS packages and creating laia-agent user"
lxc exec "$BASE_CONTAINER" -- bash -lc '
  set -euo pipefail
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip \
    git curl ca-certificates jq sqlite3 rsync less
  if ! id laia-agent >/dev/null 2>&1; then
    useradd -m -d /home/laia-agent -s /bin/bash laia-agent
  fi
  mkdir -p /opt/laia/agent /opt/laia/data /opt/laia/logs /opt/laia/runtime /opt/laia/workspaces/personal
  mkdir -p /opt/laia/data/profile /opt/laia/data/tasks/inbox /opt/laia/data/tasks/done /opt/laia/data/tasks/failed
'

# ── push source tarball ──────────────────────────────────────────────────────

info "pushing source tarball into container"
lxc file push "$TAR" "$BASE_CONTAINER/tmp/laia-agent-src.tar.gz"
lxc exec "$BASE_CONTAINER" -- bash -lc '
  set -euo pipefail
  tar -xzf /tmp/laia-agent-src.tar.gz -C /opt/laia/agent/
  rm /tmp/laia-agent-src.tar.gz

  # Reorganize: src/, systemd/, healthcheck at predictable paths.
  mkdir -p /opt/laia/agent/src
  mv /opt/laia/agent/services/laia-runtime/src/laia_agent /opt/laia/agent/src/laia_agent
  mv /opt/laia/agent/services/laia-runtime/systemd /opt/laia/agent/systemd
  install -m 0755 /opt/laia/agent/services/laia-runtime/healthcheck.sh /opt/laia/healthcheck.sh
  rm -rf /opt/laia/agent/services
'

# ── build python venv + install deps ────────────────────────────────────────

info "building python venv at /opt/laia/runtime/venv"
lxc exec "$BASE_CONTAINER" -- bash -lc '
  set -euo pipefail
  python3 -m venv /opt/laia/runtime/venv
  /opt/laia/runtime/venv/bin/pip install --upgrade pip
  /opt/laia/runtime/venv/bin/pip install \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.30" \
    "pydantic>=2.7"
'
ok "venv built"

# ── install systemd units ───────────────────────────────────────────────────

info "installing systemd units"
lxc exec "$BASE_CONTAINER" -- bash -lc '
  set -euo pipefail
  install -m 0644 /opt/laia/agent/systemd/laia-agent.service \
      /etc/systemd/system/laia-agent.service
  install -m 0644 /opt/laia/agent/systemd/laia-agent-api.service \
      /etc/systemd/system/laia-agent-api.service
  systemctl daemon-reload
  systemctl enable laia-agent.service laia-agent-api.service
  # Do NOT start now — per-container agent.json is missing in the image; created by create-agent.sh
'

# ── ownership + smoke import test ───────────────────────────────────────────

info "fixing ownership (sprint 2: root:laia-agent 0750 on agent code)"
lxc exec "$BASE_CONTAINER" -- bash -lc '
  set -euo pipefail
  # Data & plugins: agent + users (via API) can read/write
  chown -R laia-agent:laia-agent /opt/laia/data /opt/laia/logs /opt/laia/workspaces
  chmod -R 0750 /opt/laia/data /opt/laia/logs /opt/laia/workspaces

  # Plugins dir: agent reads + writes, user uploads via API
  mkdir -p /opt/laia/plugins
  chown -R laia-agent:laia-agent /opt/laia/plugins
  chmod -R 0750 /opt/laia/plugins

  # Agent code & venv: owned by root, readable only by laia-agent group.
  # Even if a user gained shell access, they could not cat .laia-core/* files.
  chown -R root:laia-agent /opt/laia/agent /opt/laia/runtime
  chmod -R 0750 /opt/laia/agent /opt/laia/runtime
  # The systemd unit files in /etc/systemd are root-only by default — keep that.

  # Verify a non-laia-agent user genuinely cannot read agent code.
  # Run as ubuntu (default unprivileged user in the base image) — must fail.
  if id ubuntu >/dev/null 2>&1; then
    if su -s /bin/sh ubuntu -c "cat /opt/laia/agent/.laia-core/run_agent.py" >/dev/null 2>&1; then
      echo "SECURITY ERROR: ubuntu user can read .laia-core/run_agent.py" >&2
      exit 1
    fi
    echo "ownership smoke test OK: ubuntu cannot read .laia-core/"
  fi

  # Smoke import (laia-agent IS in the file group, so import works)
  su -s /bin/sh laia-agent -c "/opt/laia/runtime/venv/bin/python -c \"import sys; sys.path.insert(0, \\\"/opt/laia/agent/src\\\"); import laia_agent; from laia_agent.api import create_app; print(\\\"import laia_agent.api OK\\\")\""
'
ok "import smoke test passed"

# ── publish image ───────────────────────────────────────────────────────────

info "stopping container and publishing as $ALIAS"
lxc stop "$BASE_CONTAINER"
lxc publish "$BASE_CONTAINER" --alias "$ALIAS" description="LAIA child agent base ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
lxc delete "$BASE_CONTAINER"

ok "Published image: $ALIAS"
info "Next: bash $LAIA_ROOT/infra/lxd/scripts/create-agent.sh <slug>"
