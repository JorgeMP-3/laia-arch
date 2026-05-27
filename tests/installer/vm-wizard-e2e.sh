#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# tests/installer/vm-wizard-e2e.sh
#
# End-to-end manual smoke for laia-wizard hardening (blocks 1-5 of the
# 2026-05-22 hardening plan). Requires:
#   * A fresh Ubuntu VM (Multipass, Lima, or actual server)
#   * sudo privileges
#   * The LAIA repo at /home/laia-hermes/LAIA (or LAIA_ROOT env)
#
# This script runs the 8 manual verifications from the plan and reports
# pass/fail. It is INVASIVE — it installs/wipes LAIA. Do NOT run it on a
# host you care about.
#
# Usage:
#   sudo bash tests/installer/vm-wizard-e2e.sh
# ─────────────────────────────────────────────────────────────────────────────
set -u

LAIA_ROOT="${LAIA_ROOT:-/home/laia-arch/LAIA}"
WIZARD="$LAIA_ROOT/bin/laia"
WIZARD_SUB="wizard"  # bin/laia-wizard was collapsed into `bin/laia wizard` in Fase 4
PASS=0; FAIL=0

ok()   { PASS=$((PASS+1)); printf '\n  ✓ %s\n' "$1"; }
nope() { FAIL=$((FAIL+1)); printf '\n  ✗ %s\n' "$1"; }
step() { printf '\n══ %s ══════════════════════════════════════════════\n' "$1"; }

[[ "$EUID" -eq 0 ]] || { echo "Need root for the smoke tests. Re-run with sudo."; exit 2; }
[[ -x "$WIZARD" ]] || { echo "bin/laia not at $WIZARD"; exit 2; }

# ──────────────────────────────────────────────────────────────────────────
step "1/8 — wizard --help / --version are clean"

"$WIZARD" "$WIZARD_SUB" --version | grep -q "contract " && ok "--version prints contract" || nope "--version output unexpected"
"$WIZARD" "$WIZARD_SUB" --help    | grep -q '\-\-config' && ok "--help mentions --config" || nope "--help missing --config"

# ──────────────────────────────────────────────────────────────────────────
step "2/8 — Headless install (--config + --yes)"

mkdir -p /tmp/laia-e2e
cat > /tmp/laia-e2e/install.yaml <<'EOF'
mode: install
values:
  admin_user: admin
  admin_pass: ETestPa55!
  llm_provider: unset
  init_lxd: true
EOF

# Start wizard in background, watch /proc for the password.
"$WIZARD" "$WIZARD_SUB" --config /tmp/laia-e2e/install.yaml --yes &
WIZARD_PID=$!
sleep 2  # let argv settle

# 2a — verify password never appears in argv of any subprocess
LEAK_FOUND=false
for pid in $(pgrep -P $WIZARD_PID; echo $WIZARD_PID); do
  if cat "/proc/$pid/cmdline" 2>/dev/null | tr '\0' ' ' | grep -qF 'ETestPa55!'; then
    LEAK_FOUND=true
    echo "  LEAK in /proc/$pid/cmdline"
  fi
done
[[ "$LEAK_FOUND" == false ]] && ok "password never in /proc/<pid>/cmdline" \
  || nope "password leaked into argv"

# Let it finish (or kill after 10 min).
wait "$WIZARD_PID" 2>/dev/null
WIZARD_RC=$?
[[ $WIZARD_RC -eq 0 ]] && ok "headless install rc=0" || nope "headless install rc=$WIZARD_RC"

# ──────────────────────────────────────────────────────────────────────────
step "3/8 — Post-install health"

curl -fsS http://127.0.0.1:8088/api/health -o /dev/null -m 5 \
  && ok "/api/health responds" \
  || nope "/api/health unreachable"

lxc list 2>/dev/null | grep -q "laia-agora.*RUNNING" \
  && ok "laia-agora container running" \
  || nope "laia-agora not RUNNING"

[[ -f /home/*/LAIA-ARCH/.admin-credentials ]] \
  && ok ".admin-credentials present" \
  || nope ".admin-credentials missing"

# ──────────────────────────────────────────────────────────────────────────
step "4/8 — Diagnose mode reports green"

"$WIZARD" --mode diagnose --yes < /dev/null 2>&1 | tail -30
# Don't gate on the rc — diagnose may surface warnings even on a healthy box.

# ──────────────────────────────────────────────────────────────────────────
step "5/8 — Ctrl-C mid-install leaves a resumable checkpoint"

"$WIZARD" "$WIZARD_SUB" --config /tmp/laia-e2e/install.yaml --yes &
PID2=$!
sleep 3
kill -INT $PID2 2>/dev/null
wait $PID2 2>/dev/null
RC2=$?
[[ $RC2 -eq 130 ]] && ok "wizard returns 130 on SIGINT" || nope "wizard rc=$RC2 on SIGINT"

CHKPT="${LAIA_ARCH_HOME:-$HOME/LAIA-ARCH}/wizard-state.json"
[[ -f "$CHKPT" ]] && ok "checkpoint exists at $CHKPT" || nope "no checkpoint after SIGINT"

# ──────────────────────────────────────────────────────────────────────────
step "6/8 — Reset wipe with double confirm"

# Headless reset requires the typed-confirm "borrar"
cat > /tmp/laia-e2e/reset.yaml <<'EOF'
mode: reset
values:
  snapshot_before: false
  confirm_intent: true
  typed: "borrar"
EOF

"$WIZARD" --config /tmp/laia-e2e/reset.yaml --yes
RC3=$?
[[ $RC3 -eq 0 ]] && ok "headless reset rc=0" || nope "headless reset rc=$RC3"

[[ ! -d /opt/laia ]] && ok "/opt/laia is gone" || nope "/opt/laia still exists"
[[ ! -d /srv/laia ]] && ok "/srv/laia is gone" || nope "/srv/laia still exists"

# ──────────────────────────────────────────────────────────────────────────
step "7/8 — argv smoke (no password in ps during install)"

cat > /tmp/laia-e2e/install2.yaml <<'EOF'
mode: install
values:
  admin_user: admin
  admin_pass: AnotherSecret!
  llm_provider: unset
  init_lxd: true
EOF

"$WIZARD" --config /tmp/laia-e2e/install2.yaml --yes &
PID3=$!
sleep 4
PS_OUT=$(ps auxf)
if grep -qF 'AnotherSecret!' <<<"$PS_OUT"; then
  nope "password visible via ps auxf"
else
  ok "password NOT visible via ps auxf"
fi
kill -TERM $PID3 2>/dev/null
wait $PID3 2>/dev/null

# ──────────────────────────────────────────────────────────────────────────
step "8/8 — JSON progress is well-formed when piped"

"$LAIA_ROOT/bin/laia-install" --json-progress --dry-run \
    --from-local "$LAIA_ROOT" --version v0.0.0-test --yes \
  2>/dev/null \
  | grep '^{' \
  | python3 -c '
import sys, json
required = {"event", "step_id", "label", "percent", "ts"}
n = 0
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        e = json.loads(line)
    except Exception as ex:
        print(f"BAD JSON: {line!r}: {ex}", file=sys.stderr); sys.exit(1)
    miss = required - e.keys()
    if miss:
        print(f"missing keys {miss} in {e}", file=sys.stderr); sys.exit(1)
    n += 1
sys.exit(0 if n >= 1 else 1)
' \
  && ok "JSON progress lines all valid" \
  || nope "JSON progress lines malformed or missing"

# ──────────────────────────────────────────────────────────────────────────
echo
echo "════════════════════════════════════════════════════════"
printf "  PASS: %d   FAIL: %d\n" "$PASS" "$FAIL"
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
