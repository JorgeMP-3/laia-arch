#!/usr/bin/env bash
# Atlas-aware start script. Resolves working dir + venv via the path registry.
# shellcheck disable=SC1091
[ -f "${LAIA_HOME:-$HOME/.laia}/.env.paths" ] && source "${LAIA_HOME:-$HOME/.laia}/.env.paths"
cd "${LAIA_AGORA:-$HOME/LAIA/services/agora-backend}"
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8088
