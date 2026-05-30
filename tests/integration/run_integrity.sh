#!/usr/bin/env bash
# Runner for LAIA integration/regression integrity checks.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/lib/integrity_runner.py" "$@"
