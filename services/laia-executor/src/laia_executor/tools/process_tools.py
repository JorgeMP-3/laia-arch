"""process_* — background process management inside the user's container.

Replaces the old ``process`` tool that was disabled in laia-agora (would
have spawned long-lived processes in the orchestrator). The user's
container is the right place to put them: it's their root, their CPU
quota, their failure domain.

Four tools:
  - ``process_start(command, name?)`` — spawn in background, capture
    output to a log file under ``/var/log/laia-processes/``.
  - ``process_list()`` — alive processes started by this executor + their
    output sizes.
  - ``process_status(name_or_pid)`` — current state + tail of log.
  - ``process_kill(name_or_pid)`` — SIGTERM then SIGKILL after grace.

State lives in a module-level dict; survives across HTTP requests in the
same executor process but NOT across restarts (the executor reboots fresh,
which is fine — when AGORA restarts a user's container, runaway processes
die with it).
"""

from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional


# Where stdout/stderr of background processes lives. The executor runs as
# root inside the container, so /var/log/ writes work without sudo. The
# bind mount /home/user is for user-facing files; logs go elsewhere on
# purpose so a stray ``rm -rf /home/user/*`` doesn't wipe debug history.
PROCESS_LOG_DIR = Path("/var/log/laia-processes")

# Tail length when ``process_status`` returns log preview. Bigger is
# truncated. Same constant as python_exec for consistency.
PROCESS_LOG_TAIL_CHARS = 16_000

# Grace period between SIGTERM and SIGKILL on ``process_kill``.
KILL_GRACE_SECONDS = 3.0


# ──────────────────────────────────────────────────────────────────────────
# Registry of processes spawned by this executor instance
# ──────────────────────────────────────────────────────────────────────────


_processes: dict[str, dict[str, Any]] = {}
_processes_lock = threading.RLock()


def _safe_name(name: str | None) -> str:
    """Sanitise/generate a process name. The name is used as a log filename
    component, so we strip anything that isn't filesystem-friendly."""
    if not name:
        return f"proc-{uuid.uuid4().hex[:8]}"
    out = "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(name))
    return out[:48] or f"proc-{uuid.uuid4().hex[:8]}"


def _log_path(name: str) -> Path:
    return PROCESS_LOG_DIR / f"{name}.log"


def _resolve(name_or_pid: str) -> Optional[tuple[str, dict[str, Any]]]:
    """Look up an entry by either its name or PID (as string)."""
    with _processes_lock:
        if name_or_pid in _processes:
            return name_or_pid, _processes[name_or_pid]
        # Try by PID
        try:
            pid = int(name_or_pid)
        except (TypeError, ValueError):
            return None
        for n, entry in _processes.items():
            if entry["pid"] == pid:
                return n, entry
        return None


def _refresh_state(entry: dict[str, Any]) -> dict[str, Any]:
    """Update entry's alive/returncode from the underlying Popen object."""
    popen: subprocess.Popen = entry["popen"]
    rc = popen.poll()
    if rc is None:
        entry["alive"] = True
    else:
        entry["alive"] = False
        entry["returncode"] = rc
    return entry


def _tail_log(name: str, max_chars: int = PROCESS_LOG_TAIL_CHARS) -> str:
    path = _log_path(name)
    if not path.exists():
        return ""
    try:
        data = path.read_bytes()
    except Exception:
        return ""
    if len(data) <= max_chars:
        return data.decode("utf-8", errors="replace")
    return "…(truncated)\n" + data[-max_chars:].decode("utf-8", errors="replace")


# ──────────────────────────────────────────────────────────────────────────
# Public handlers
# ──────────────────────────────────────────────────────────────────────────


def process_start(
    command: str = "",
    name: str | None = None,
    cwd: str = "/home/user",
    env: dict[str, str] | None = None,
    **_ignored,
) -> str:
    """Spawn ``command`` in the background.

    Args:
        command: Shell command to run. Executed via ``/bin/bash -c`` so
                 pipes/redirects/&& are honored.
        name: Optional friendly name; auto-generated if omitted.
        cwd: Working directory; defaults to /home/user.
        env: Extra env vars merged on top of the executor's environment.
    """
    if not command or not isinstance(command, str):
        return json.dumps({"ok": False, "error": "command is required (non-empty string)"})

    PROCESS_LOG_DIR.mkdir(parents=True, exist_ok=True)

    final_name = _safe_name(name)
    # If the user reuses a name and the previous process is still alive,
    # refuse — they should kill or pick a new name. Lets them iterate on
    # "dev-server" reliably without accidentally double-spawning.
    with _processes_lock:
        existing = _processes.get(final_name)
        if existing is not None:
            _refresh_state(existing)
            if existing["alive"]:
                return json.dumps({
                    "ok": False,
                    "error": f"a process named {final_name!r} is already running (pid={existing['pid']}). "
                             "Pick a different name or call process_kill first.",
                })

    log_path = _log_path(final_name)
    if not Path(cwd).is_dir():
        cwd = "/home/user" if Path("/home/user").is_dir() else "/tmp"
    full_env = {**os.environ}
    if isinstance(env, dict):
        full_env.update({str(k): str(v) for k, v in env.items()})

    try:
        log_fh = log_path.open("ab")  # append-binary, so re-uses survive restart of the cmd
    except Exception as exc:
        return json.dumps({"ok": False, "error": f"could not open log file {log_path}: {exc}"})

    try:
        popen = subprocess.Popen(
            ["/bin/bash", "-c", command],
            cwd=cwd,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=full_env,
            start_new_session=True,  # detach from executor's process group so it survives
        )
    except Exception as exc:
        log_fh.close()
        return json.dumps({"ok": False, "error": f"spawn failed: {exc}"})

    # Popen dup'd the descriptor into the child: the child writes through
    # its OWN fd, so the parent's copy is dead weight. Close it now —
    # keeping it open leaked one fd per process_start until the executor
    # hit `ulimit -n` and died (audit 2026-06-02, executor-log-fh-fd-leak).
    log_fh.close()

    entry = {
        "name": final_name,
        "command": command,
        "pid": popen.pid,
        "cwd": cwd,
        "started_at": time.time(),
        "alive": True,
        "returncode": None,
        "log_path": str(log_path),
        "popen": popen,
    }
    with _processes_lock:
        _processes[final_name] = entry

    # Don't include the Popen handle in the JSON response.
    public = {k: v for k, v in entry.items() if not k.startswith("_") and k != "popen"}
    return json.dumps({"ok": True, "process": public}, ensure_ascii=False, default=str)


def process_list(**_ignored) -> str:
    """Return all known processes (alive or terminated, this executor instance)."""
    with _processes_lock:
        snapshot = []
        for entry in _processes.values():
            _refresh_state(entry)
            public = {k: v for k, v in entry.items() if not k.startswith("_") and k != "popen"}
            snapshot.append(public)
    return json.dumps({"ok": True, "processes": snapshot, "count": len(snapshot)}, ensure_ascii=False, default=str)


def process_status(name_or_pid: str = "", tail_chars: int | None = None, **_ignored) -> str:
    """Inspect one process + tail its output log."""
    if not name_or_pid:
        return json.dumps({"ok": False, "error": "name_or_pid is required"})
    found = _resolve(str(name_or_pid))
    if not found:
        return json.dumps({"ok": False, "error": f"no process matched {name_or_pid!r}. Run process_list to see names."})
    name, entry = found
    _refresh_state(entry)
    public = {k: v for k, v in entry.items() if not k.startswith("_") and k != "popen"}
    log_tail = _tail_log(name, max_chars=int(tail_chars) if tail_chars else PROCESS_LOG_TAIL_CHARS)
    return json.dumps({"ok": True, "process": public, "log_tail": log_tail}, ensure_ascii=False, default=str)


def process_kill(name_or_pid: str = "", **_ignored) -> str:
    """Send SIGTERM, then SIGKILL after a grace period."""
    if not name_or_pid:
        return json.dumps({"ok": False, "error": "name_or_pid is required"})
    found = _resolve(str(name_or_pid))
    if not found:
        return json.dumps({"ok": False, "error": f"no process matched {name_or_pid!r}"})
    name, entry = found
    popen: subprocess.Popen = entry["popen"]

    if popen.poll() is not None:
        return json.dumps({"ok": True, "killed": False, "reason": "already exited", "returncode": popen.returncode,
                           "name": name})

    try:
        # Kill the whole process group (we spawned with start_new_session=True).
        os.killpg(os.getpgid(popen.pid), signal.SIGTERM)
    except Exception:
        try:
            popen.terminate()
        except Exception as exc:
            return json.dumps({"ok": False, "error": f"terminate failed: {exc}"})

    deadline = time.time() + KILL_GRACE_SECONDS
    while time.time() < deadline:
        if popen.poll() is not None:
            return json.dumps({"ok": True, "killed": True, "signal": "SIGTERM", "name": name,
                               "returncode": popen.returncode})
        time.sleep(0.1)

    # Didn't exit on SIGTERM → SIGKILL.
    try:
        os.killpg(os.getpgid(popen.pid), signal.SIGKILL)
    except Exception:
        try:
            popen.kill()
        except Exception:
            pass
    popen.wait(timeout=2)
    return json.dumps({"ok": True, "killed": True, "signal": "SIGKILL", "name": name,
                       "returncode": popen.returncode}, ensure_ascii=False, default=str)


def _reset_for_tests() -> None:
    """Tear down state — used by the test suite, not by production."""
    with _processes_lock:
        for entry in _processes.values():
            try:
                entry["popen"].kill()
            except Exception:
                pass
        _processes.clear()


__all__ = [
    "process_start", "process_list", "process_status", "process_kill",
    "PROCESS_LOG_DIR", "_reset_for_tests",
]
