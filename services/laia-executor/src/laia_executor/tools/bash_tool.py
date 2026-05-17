"""Bash execution. User is root inside the container — no blacklist."""

from __future__ import annotations

import os
import subprocess


BASH_TIMEOUT_DEFAULT = 120
BASH_TIMEOUT_MAX = 600


def bash(command: str, cwd: str | None = None, timeout: int = BASH_TIMEOUT_DEFAULT, env: dict | None = None) -> str:
    """Run a shell command and return combined stdout+stderr.

    No command blacklist. The user is root inside their container.
    """
    timeout = min(max(1, int(timeout)), BASH_TIMEOUT_MAX)
    run_env = os.environ.copy()
    if env:
        run_env.update({str(k): str(v) for k, v in env.items()})
    try:
        result = subprocess.run(
            command,
            shell=True,
            executable="/bin/bash",
            cwd=cwd,
            env=run_env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"ERROR: command timed out after {timeout}s"
    except Exception as exc:
        return f"ERROR: command failed to launch: {exc}"

    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        return f"[exit={result.returncode}]\n{output}"
    return output if output else "(no output)"
