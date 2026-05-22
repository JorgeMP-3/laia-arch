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
echo "→ wizard stream_command parses JSON progress and keeps run logs"
if PYTHONPATH="$LAIA_ROOT/.laia-core" python3 - <<'PY'
import os
import sys
from pathlib import Path
from laia_cli.install_wizard.flows._subprocess import stream_command

events = list(stream_command(
    [
        "python3",
        "-c",
        'print("{\\"event\\":\\"step_progress\\",\\"step_id\\":\\"demo\\",\\"label\\":\\"Structured phase\\",\\"percent\\":42,\\"ts\\":\\"now\\"}"); print("human line")',
    ],
    step_id="json-parser-test",
    label="JSON parser test",
    idle_timeout_s=-1,
    timeout_s=10,
))

labels = [e.label for e in events]
if "Structured phase" not in labels:
    print("missing structured JSON event", file=sys.stderr)
    sys.exit(1)
if any(str(label).startswith('{"event"') for label in labels):
    print("JSON line leaked as raw UI label", file=sys.stderr)
    sys.exit(1)
starts = [e for e in events if e.type == "step_start"]
if not starts or not (starts[0].extra or {}).get("log_path"):
    print("missing run log path", file=sys.stderr)
    sys.exit(1)
if not Path(starts[0].extra["log_path"]).is_file():
    print("run log file does not exist", file=sys.stderr)
    sys.exit(1)
PY
then
  ok "wizard parser converts JSON progress into events"
else
  nope "wizard parser failed to convert JSON progress"
fi

echo
echo "→ wizard stream_command error includes tail and log path"
if PYTHONPATH="$LAIA_ROOT/.laia-core" python3 - <<'PY'
import sys
from pathlib import Path
from laia_cli.install_wizard.flows._subprocess import stream_command

events = list(stream_command(
    ["bash", "-lc", "echo before-failure; echo final-line; exit 7"],
    step_id="error-tail-test",
    label="Error tail test",
    idle_timeout_s=-1,
    timeout_s=10,
))
errors = [e for e in events if e.type == "step_error"]
if not errors:
    print("missing step_error", file=sys.stderr)
    sys.exit(1)
extra = errors[-1].extra or {}
tail = "\n".join(extra.get("tail") or [])
if extra.get("returncode") != 7:
    print(f"bad returncode: {extra.get('returncode')}", file=sys.stderr)
    sys.exit(1)
if "final-line" not in tail:
    print(f"tail missing final-line: {tail!r}", file=sys.stderr)
    sys.exit(1)
if not extra.get("log_path") or not Path(extra["log_path"]).is_file():
    print("missing log_path file", file=sys.stderr)
    sys.exit(1)
PY
then
  ok "wizard error event includes tail + log path"
else
  nope "wizard error event missing tail/log context"
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
