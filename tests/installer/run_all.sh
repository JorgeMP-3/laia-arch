#!/usr/bin/env bash
set -euo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_ROOT="$TEST_DIR/../../.test-tmp"
mkdir -p "$RUN_ROOT"
RUN_HOME="$(mktemp -d "$RUN_ROOT/laia-installer-tests.XXXXXX")"
trap 'rm -rf "$RUN_HOME"' EXIT
export HOME="$RUN_HOME"

# Optional skip-list (backward-compatible: empty by default → runs everything).
# INSTALLER_SKIP accepts space- or comma-separated test basenames, e.g.
#   INSTALLER_SKIP="test_install_native_layout.sh"
# Skips are printed LOUDLY (never silent) so a CI log shows exactly what was
# left out. Used by .github/workflows/ci.yml to drop tests that need host
# artifacts a bare runner doesn't have (see that file + README for the why).
declare -A SKIP_SET=()
if [[ -n "${INSTALLER_SKIP:-}" ]]; then
  for s in ${INSTALLER_SKIP//,/ }; do
    SKIP_SET["$s"]=1
  done
fi

fail=0
skipped=0
for t in "$TEST_DIR"/test_*.sh; do
  [[ -f "$t" ]] || continue
  base="$(basename "$t")"
  if [[ -n "${SKIP_SET[$base]:-}" ]]; then
    printf '\n== %s ==\n' "$base"
    printf 'SKIPPED (INSTALLER_SKIP): %s — requires host artifacts not present in this environment\n' "$base"
    skipped=$((skipped + 1))
    continue
  fi
  printf '\n== %s ==\n' "$base"
  if bash "$t"; then
    printf 'ok: %s\n' "$base"
  else
    printf 'FAILED: %s\n' "$base" >&2
    fail=1
  fi
done

if (( skipped > 0 )); then
  printf '\n%d test(s) skipped via INSTALLER_SKIP (see lines above).\n' "$skipped" >&2
fi

exit "$fail"
