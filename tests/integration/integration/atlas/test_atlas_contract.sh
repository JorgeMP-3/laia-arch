#!/usr/bin/env bash
# integrity:id=atlas_contract
# integrity:name=Atlas reference contract
# integrity:level=integration
# integrity:layers=atlas
# integrity:profiles=vm
# integrity:requires=atlas
# integrity:timeout=60
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../lib/integrity_shell.sh
source "$SCRIPT_DIR/../../lib/integrity_shell.sh"

ATLAS_BIN="${ATLAS_BIN:-}"
if [[ -z "$ATLAS_BIN" ]]; then
  if [[ -x "$INTEGRITY_REPO_ROOT/bin/atlas" ]]; then
    ATLAS_BIN="$INTEGRITY_REPO_ROOT/bin/atlas"
  elif [[ -x "$INTEGRITY_REPO_ROOT/infra/bin/laia-path" ]]; then
    ATLAS_BIN="$INTEGRITY_REPO_ROOT/infra/bin/laia-path"
  elif command -v atlas >/dev/null 2>&1; then
    ATLAS_BIN="atlas"
  elif command -v laia-path >/dev/null 2>&1; then
    ATLAS_BIN="laia-path"
  else
    integ_skip "atlas/laia-path binary unavailable"
  fi
fi

out="$("$ATLAS_BIN" doctor 2>&1)" || integ_fail "atlas doctor failed: $(printf '%s' "$out" | tail -3 | tr '\n' ' ')"
integ_info "Atlas contract OK"
