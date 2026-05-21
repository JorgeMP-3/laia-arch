#!/usr/bin/env bash
# Launcher for the AGORA control center v2 (Textual).
#
# The legacy curses TUI is in archived/control-center-v1/. If you want
# the old behaviour, run it directly with `python3 archived/...`. This
# wrapper only knows about v2.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.ctl-venv"

if [[ ! -x "$VENV/bin/python" ]]; then
  cat <<EOF >&2
[agora-control-center] .ctl-venv ausente.
Bootstrap:
    bash $SCRIPT_DIR/setup-ctl-venv.sh
y vuelve a ejecutar este wrapper.
EOF
  exit 1
fi

export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"
exec "$VENV/bin/python" -m ctl "$@"
