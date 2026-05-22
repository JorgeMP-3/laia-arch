#!/usr/bin/env bash
# Regression tests for the curl|sudo bootstrap prompt.
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
BOOT="$LAIA_ROOT/install.sh"

PASS=0
FAIL=0
FAILURES=()

ok() {
  PASS=$((PASS + 1))
  printf '  ok: %s\n' "$1"
}

fail() {
  FAIL=$((FAIL + 1))
  FAILURES+=("$1")
  printf '  fail: %s\n' "$1"
}

bootstrap_lib="$(mktemp)"
trap 'rm -f "$bootstrap_lib"' EXIT
sed '/^main "\$@"/,$d' "$BOOT" >"$bootstrap_lib"

run_pty_case() {
  local mode="$1"
  python3 - "$bootstrap_lib" "$mode" <<'PY'
import errno
import os
import pty
import select
import shlex
import signal
import sys
import time

script, mode = sys.argv[1], sys.argv[2]
cmd = (
    f"source {shlex.quote(script)}; "
    "install_signal_traps; "
    "OPT_CONFIG=''; OPT_MODE_EXPLICIT=false; OPT_YES=false; "
    "OPT_MODE=wizard; OPT_SOURCE=''; "
    "collect_interactive_intent; "
    "echo AFTER:$OPT_MODE"
)

pid, fd = pty.fork()
if pid == 0:
    os.execvp("bash", ["bash", "-c", cmd])

def read_some(timeout=0.1):
    chunks = []
    ready, _, _ = select.select([fd], [], [], timeout)
    if ready:
        try:
            chunks.append(os.read(fd, 4096))
        except OSError as exc:
            if exc.errno != errno.EIO:
                raise
    return b"".join(chunks)

buf = b""
deadline = time.time() + 5
while b"Choose 1, 2 or 3" not in buf and time.time() < deadline:
    buf += read_some()

if b"Choose 1, 2 or 3" not in buf:
    os.kill(pid, signal.SIGKILL)
    os.waitpid(pid, 0)
    print("NOT_READY")
    sys.exit(1)

if mode == "choose":
    os.write(fd, b"3\n")
    want = b"AFTER:wizard"
else:
    os.write(fd, b"\x03")
    want = b"Interrupted by SIGINT"

status = None
deadline = time.time() + 5
while time.time() < deadline:
    buf += read_some()
    done, status = os.waitpid(pid, os.WNOHANG)
    if done:
        break
else:
    os.kill(pid, signal.SIGKILL)
    os.waitpid(pid, 0)
    print("TIMEOUT")
    sys.exit(1)

sys.stdout.write(buf.decode(errors="replace"))

if mode == "choose":
    sys.exit(0 if want in buf else 1)

if os.WIFEXITED(status):
    code = os.WEXITSTATUS(status)
    print(f"EXIT:{code}")
    sys.exit(0 if code == 130 and want in buf else 1)

print(f"SIGNAL:{os.WTERMSIG(status)}")
sys.exit(1)
PY
}

echo "-> bootstrap menu"

if choose_output="$(run_pty_case choose)"; then
  if [[ "$choose_output" == *"Selected: full wizard"* && "$choose_output" == *"AFTER:wizard"* ]]; then
    ok "choice 3 returns from prompt and selects wizard"
  else
    fail "choice 3 output missing selected wizard marker"
  fi
else
  fail "choice 3 pty case failed"
fi

if interrupt_output="$(run_pty_case interrupt)"; then
  if [[ "$interrupt_output" == *"EXIT:130"* ]]; then
    ok "Ctrl-C during bootstrap prompt exits 130"
  else
    fail "Ctrl-C output did not include EXIT:130"
  fi
else
  fail "Ctrl-C pty case failed"
fi

echo
printf 'PASS: %d FAIL: %d\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  printf 'Failures:\n'
  for failure in "${FAILURES[@]}"; do
    printf '  - %s\n' "$failure"
  done
  exit 1
fi
exit 0
