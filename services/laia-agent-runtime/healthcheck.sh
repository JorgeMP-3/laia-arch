#!/usr/bin/env bash
set -euo pipefail

test -d /opt/laia/agent/src/laia_agent
test -d /opt/laia/data
test -d /opt/laia/logs
test -d /opt/laia/data/profile
test -d /opt/laia/workspaces/personal
test -d /opt/laia/agent/vendor/workspace_store
test -x /opt/laia/runtime/venv/bin/python
/opt/laia/runtime/venv/bin/python -m pip --version >/dev/null

run_agent() {
  if [ "$(id -u)" = "0" ] && command -v runuser >/dev/null 2>&1; then
    runuser -u laia-agent -- "$@"
  else
    "$@"
  fi
}

run_agent env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/opt/laia/agent/src /opt/laia/runtime/venv/bin/python -m laia_agent --status
test -s /opt/laia/data/status.json
run_agent env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/opt/laia/agent/src /opt/laia/runtime/venv/bin/python -m laia_agent --profile-init
test -s /opt/laia/data/profile/persona.md
test -s /opt/laia/data/profile/instructions.md
test -s /opt/laia/data/profile/skills.json
test -s /opt/laia/data/profile/preferences.json
run_agent env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/opt/laia/agent/src /opt/laia/runtime/venv/bin/python -m laia_agent --workspace-init
test -s /opt/laia/workspaces/personal/workspace.db
echo "laia-agent-runtime-ok"
