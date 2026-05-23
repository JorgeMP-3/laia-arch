#!/usr/bin/env bash
# Regression tests for the curl|sudo bootstrap prompts.
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

echo "-> bootstrap default mode"

default_output="$(
  bash -c "
    source '$bootstrap_lib'
    OPT_CONFIG=''
    OPT_MODE_EXPLICIT=false
    OPT_YES=false
    OPT_MODE=wizard
    OPT_SOURCE=''
    collect_interactive_intent
    print_plan
    echo AFTER:\$OPT_MODE
  "
)"

if [[ "$default_output" == *"AFTER:wizard"* ]]; then
  ok "default bootstrap selects wizard without asking mode"
else
  fail "default bootstrap did not leave OPT_MODE=wizard"
fi

if [[ "$default_output" != *"What do you want to do?"* && "$default_output" != *"Choose 1, 2 or 3"* ]]; then
  ok "default bootstrap does not duplicate the wizard mode menu"
else
  fail "default bootstrap still printed the old mode menu"
fi

if [[ "$default_output" != *"Continue? [Y/n]"* ]]; then
  ok "default wizard bootstrap skips the extra plan confirmation"
else
  fail "default wizard bootstrap still asks for plan confirmation"
fi

run_apt_interrupt_case() {
  python3 - "$bootstrap_lib" <<'PY'
import errno
import os
import pty
import select
import shlex
import signal
import sys
import time

script = sys.argv[1]
cmd = (
    f"source {shlex.quote(script)}; "
    "install_signal_traps; "
    "OPT_YES=false; OPT_NO_APT=false; "
    "APT_PACKAGES=(fake-laia-test-package); "
    "apt_missing(){ printf 'fake-laia-test-package\\n'; }; "
    "ensure_prereqs"
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
while b"Proceed with apt install?" not in buf and time.time() < deadline:
    buf += read_some()

if b"Proceed with apt install?" not in buf:
    os.kill(pid, signal.SIGKILL)
    os.waitpid(pid, 0)
    print("NOT_READY")
    sys.exit(1)

os.write(fd, b"\x03")

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

if os.WIFEXITED(status):
    code = os.WEXITSTATUS(status)
    print(f"EXIT:{code}")
    sys.exit(0 if code == 130 and b"Interrupted by SIGINT" in buf else 1)

print(f"SIGNAL:{os.WTERMSIG(status)}")
sys.exit(1)
PY
}

echo
echo "-> bootstrap interrupt"

if interrupt_output="$(run_apt_interrupt_case)"; then
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
