"""python_exec — run a Python snippet inside the user's container.

Replaces the old ``execute_code`` tool that was disabled in laia-agora
(it would have run Python in the orchestrator's address space; see
``agora-executor-forwarder/AGORA_LOCAL_DENY``). The flow is now:

    LLM emits  python_exec("import json; print(...)")
      → forwarder routes to laia-executor :9091/exec on the user's container
        → this handler spawns python3 -c <code> as root inside the container
        → captures stdout / stderr / exit_code and returns them
    → the model sees the result as if it had run the snippet locally

CWD is fixed to ``/home/user`` (the user's home in the bind-mounted
filesystem) so relative paths in the snippet land in their workspace.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


# Fixed working directory. The user owns /home/user via the host bind mount.
# Keeping this fixed (vs configurable) means relative paths in the snippet
# always land somewhere persistent and intentional; the LLM can still
# os.chdir() inside the code if it really needs another dir.
PYTHON_EXEC_CWD = "/home/user"

# Cap individual snippet execution. Anything longer is almost certainly the
# LLM losing the plot — use ``terminal`` + ``write_file`` for long tasks.
DEFAULT_TIMEOUT_SECONDS = 60
MAX_TIMEOUT_SECONDS = 600

# Truncate captured stdout/stderr so a runaway print loop doesn't OOM the
# executor or eat the LLM's context. 100k chars covers typical pandas
# `print(df)` debug; bigger output should be written to a file.
MAX_OUTPUT_CHARS = 100_000


def python_exec(code: str = "", timeout: int = DEFAULT_TIMEOUT_SECONDS, **_ignored) -> str:
    """Execute ``code`` with ``python3 -c`` inside the user's container.

    Args:
        code: Python source to execute. Runs in a fresh interpreter — no
              state survives between calls. Use ``write_file`` if you
              need persistent modules.
        timeout: Seconds before SIGKILL. Capped at MAX_TIMEOUT_SECONDS.

    Returns:
        JSON string: ``{"stdout": ..., "stderr": ..., "exit_code": int,
        "truncated": bool}``. ``exit_code`` mirrors python3's: 0 ok,
        non-zero on exception.
    """
    if not isinstance(code, str) or not code.strip():
        return json.dumps({"ok": False, "error": "code is required (non-empty string)"})

    try:
        timeout = int(timeout)
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT_SECONDS
    timeout = max(1, min(timeout, MAX_TIMEOUT_SECONDS))

    # Ensure the cwd exists. If the bind mount somehow lost it (fresh
    # container, missing dir), fall back to /tmp so we still execute and
    # the LLM can recover.
    cwd = PYTHON_EXEC_CWD
    if not Path(cwd).is_dir():
        cwd = "/tmp"

    try:
        proc = subprocess.run(
            ["python3", "-c", code],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    except subprocess.TimeoutExpired as exc:
        # The child was SIGKILLed at the timeout. Report what we have.
        stdout = (exc.stdout or "")[:MAX_OUTPUT_CHARS] if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "")[:MAX_OUTPUT_CHARS] if isinstance(exc.stderr, str) else ""
        return json.dumps({
            "ok": False,
            "error": f"python_exec timed out after {timeout}s",
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": -1,
            "truncated": False,
        }, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"ok": False, "error": f"python_exec spawn failed: {exc}"}, ensure_ascii=False)

    truncated = False
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    if len(stdout) > MAX_OUTPUT_CHARS:
        stdout = stdout[:MAX_OUTPUT_CHARS] + f"\n…(stdout truncated at {MAX_OUTPUT_CHARS} chars)"
        truncated = True
    if len(stderr) > MAX_OUTPUT_CHARS:
        stderr = stderr[:MAX_OUTPUT_CHARS] + f"\n…(stderr truncated at {MAX_OUTPUT_CHARS} chars)"
        truncated = True

    return json.dumps({
        "ok": proc.returncode == 0,
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": proc.returncode,
        "cwd": cwd,
        "truncated": truncated,
    }, ensure_ascii=False)


__all__ = ["python_exec", "PYTHON_EXEC_CWD", "DEFAULT_TIMEOUT_SECONDS", "MAX_TIMEOUT_SECONDS"]
