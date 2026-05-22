#!/usr/bin/env bash
# Verifies that installer signal traps cancel a long-running child process.
set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAIA_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
LIB="$LAIA_ROOT/infra/installer/lib"

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

echo "-> Ctrl-C through a real pty"

pty_result="$(
  python3 - "$LIB/common.sh" <<'PY'
import errno
import os
import pty
import select
import shlex
import signal
import sys
import time

lib = sys.argv[1]
cmd = (
    f"source {shlex.quote(lib)}; "
    "install_signal_traps; "
    "echo READY; "
    "laia_run_interruptible sleep 30"
)

pid, fd = pty.fork()
if pid == 0:
    os.execvp("bash", ["bash", "-c", cmd])

def read_available(timeout=0.1):
    chunks = []
    try:
        ready, _, _ = select.select([fd], [], [], timeout)
        if ready:
            chunks.append(os.read(fd, 4096))
    except OSError as exc:
        if exc.errno != errno.EIO:
            raise
    return b"".join(chunks)

buf = b""
deadline = time.time() + 5
while b"READY" not in buf and time.time() < deadline:
    buf += read_available()

if b"READY" not in buf:
    os.kill(pid, signal.SIGKILL)
    os.waitpid(pid, 0)
    print("NOT_READY")
    sys.exit(1)

started = time.time()
os.write(fd, b"\x03")

status = None
deadline = time.time() + 5
while time.time() < deadline:
    buf += read_available()
    done, status = os.waitpid(pid, os.WNOHANG)
    if done:
        break
else:
    os.kill(pid, signal.SIGKILL)
    os.waitpid(pid, 0)
    print("TIMEOUT")
    sys.exit(1)

elapsed = time.time() - started
buf += read_available(0)

if os.WIFEXITED(status):
    code = os.WEXITSTATUS(status)
    print(f"EXIT:{code}:ELAPSED:{elapsed:.2f}")
    sys.exit(0 if code == 130 and elapsed < 5 else 1)

if os.WIFSIGNALED(status):
    print(f"SIGNAL:{os.WTERMSIG(status)}:ELAPSED:{elapsed:.2f}")
else:
    print(f"UNKNOWN:{status}:ELAPSED:{elapsed:.2f}")
sys.exit(1)
PY
)"
pty_rc=$?

if [[ "$pty_rc" -eq 0 && "$pty_result" == EXIT:130:* ]]; then
  ok "Ctrl-C exits with code 130"
else
  fail "Ctrl-C pty result was '$pty_result'"
fi

elapsed="${pty_result##*:}"
if [[ "$pty_rc" -eq 0 ]]; then
  ok "Ctrl-C cancels long-running child quickly (${elapsed}s)"
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
