#!/usr/bin/env bash
set -euo pipefail

failures=0

ok() { printf '[OK] %s\n' "$1"; }
warn() { printf '[WARN] %s\n' "$1"; }
fail() { printf '[FAIL] %s\n' "$1"; failures=$((failures + 1)); }

if command -v lxc >/dev/null 2>&1; then
  ok "lxc command found: $(command -v lxc)"
else
  fail "lxc command not found"
fi

if command -v lxd >/dev/null 2>&1; then
  ok "lxd command found: $(command -v lxd)"
else
  warn "lxd command not found directly; this can be normal on snap installs"
fi

if lxc version >/dev/null 2>&1; then
  ok "LXD responds to lxc version"
  lxc version
else
  fail "LXD does not respond to lxc version"
fi

if lxc storage list --format csv 2>/dev/null | cut -d, -f1 | grep -qx 'default'; then
  ok "storage pool exists: default"
else
  fail "missing storage pool: default"
fi

if lxc network list --format csv 2>/dev/null | cut -d, -f1 | grep -qx 'lxdbr0'; then
  ok "network exists: lxdbr0"
else
  fail "missing network: lxdbr0"
fi

if lxc profile show default >/dev/null 2>&1; then
  ok "profile exists: default"
else
  fail "missing profile: default"
fi

if lxc profile show laia-employee >/dev/null 2>&1; then
  ok "profile exists: laia-employee"
else
  warn "profile missing: laia-employee"
fi

if [[ $failures -gt 0 ]]; then
  echo "Host check failed with $failures blocking issue(s)." >&2
  exit 1
fi

echo "Host check passed."

