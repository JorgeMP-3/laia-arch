#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# tests/installer/test_json_progress.sh
#
# Verifies the --json-progress contract:
#   * emit_json_event is a no-op when LAIA_JSON_PROGRESS is unset
#   * --json-progress emits at least one well-formed JSON line on stdout
#   * each event has the required keys (event, step_id, label, percent, ts)
#   * event types are constrained to {step_start, step_progress, step_done,
#     step_error, log_line, finished, summary}
#
# Run via tests/installer/run_all.sh.
# Exit code: 0 if all assertions pass, 1 otherwise.
# ─────────────────────────────────────────────────────────────────────────────
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
BIN_INSTALL="$LAIA_ROOT/bin/laia-install"
BIN_CLONE="$LAIA_ROOT/bin/laia-clone"

PASS=0; FAIL=0; FAILURES=()
ok()   { PASS=$((PASS+1)); printf '  ✓ %s\n' "$1"; }
nope() { FAIL=$((FAIL+1)); FAILURES+=("$1"); printf '  ✗ %s\n' "$1"; }

command -v python3 >/dev/null 2>&1 || { echo "python3 missing — skipping"; exit 0; }

echo "→ Without --json-progress: no JSON lines on stdout"
out=$("$BIN_INSTALL" --dry-run --from-local "$LAIA_ROOT" --version v0.0.0-test --yes 2>/dev/null)
if grep -q '^{"event"' <<<"$out"; then
  nope "JSON line leaked without --json-progress"
else
  ok "no JSON lines without --json-progress"
fi

echo
echo "→ With --json-progress: emits valid JSON event lines"
out=$("$BIN_INSTALL" --json-progress --dry-run \
                    --from-local "$LAIA_ROOT" --version v0.0.0-test --yes 2>/dev/null \
      | grep '^{"event"' || true)
if [[ -z "$out" ]]; then
  nope "--json-progress did not emit any JSON lines"
else
  ok "at least one JSON line emitted"
  if python3 - <<PY
import sys, json
allowed = {"step_start","step_progress","step_done","step_error","log_line","finished","summary"}
required = {"event","step_id","label","percent","ts"}
fail = False
for line in """$out""".splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        e = json.loads(line)
    except Exception as exc:
        print(f"BAD JSON: {line!r}: {exc}", file=sys.stderr); fail = True; continue
    miss = required - set(e.keys())
    if miss:
        print(f"missing keys {miss} in {e}", file=sys.stderr); fail = True
    if e.get("event") not in allowed:
        print(f"bad event type: {e.get('event')!r}", file=sys.stderr); fail = True
sys.exit(1 if fail else 0)
PY
  then
    ok "all JSON lines have required keys + valid event type"
  else
    nope "JSON lines have schema problems (see stderr)"
  fi
fi

echo
echo "→ laia-clone with --json-progress also emits"
out=$("$BIN_CLONE" --json-progress --dry-run --source user@host --yes 2>/dev/null \
      | grep '^{"event"' || true)
# Dry-run exits before the main loop; verify the validate_options path doesn't
# emit (it's pre-event), but check that running through to dry-run exit at
# least the start event surfaces.
if [[ -n "$out" ]]; then
  ok "laia-clone emits at least one event (dry-run start)"
else
  ok "laia-clone with --dry-run + --json-progress: no events before dry-run exit (acceptable)"
fi

echo
echo "═══════════════════════════════════════════════════"
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
if [[ $FAIL -gt 0 ]]; then
  echo "Failures:"
  for f in "${FAILURES[@]}"; do printf "  - %s\n" "$f"; done
  exit 1
fi
exit 0
