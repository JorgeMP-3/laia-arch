#!/usr/bin/env bash
set -euo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_ROOT="$TEST_DIR/../../.test-tmp"
mkdir -p "$RUN_ROOT"
RUN_HOME="$(mktemp -d "$RUN_ROOT/laia-installer-tests.XXXXXX")"
trap 'rm -rf "$RUN_HOME"' EXIT
export HOME="$RUN_HOME"

fail=0
for t in "$TEST_DIR"/test_*.sh; do
  [[ -f "$t" ]] || continue
  printf '\n== %s ==\n' "$(basename "$t")"
  if bash "$t"; then
    printf 'ok: %s\n' "$(basename "$t")"
  else
    printf 'FAILED: %s\n' "$(basename "$t")" >&2
    fail=1
  fi
done

exit "$fail"
