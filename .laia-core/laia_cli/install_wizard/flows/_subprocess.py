"""Shared subprocess + log-streaming utilities for flows.

Both ``install.py`` and ``clone.py`` (and to a lesser extent ``diagnose.py``
and ``reset.py``) want the same plumbing: spawn ``bin/laia-*`` or any helper
script, tail its stdout/stderr, translate interesting lines into structured
:class:`contract.ProgressEvent`s.

The translation table lives here so a future iteration can refine which log
lines become ``step_start`` vs ``log_line`` without touching the flow code.
"""

from __future__ import annotations

import os
import re
import select
import signal
import subprocess
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Sequence

from ..contract import ProgressEvent

# Default upper bounds for any subprocess we launch. Callers can override
# via stream_command(timeout_s=..., idle_timeout_s=...). A negative value
# disables the limit.
DEFAULT_TIMEOUT_S = 2 * 60 * 60       # 2 hours absolute (install / clone)
DEFAULT_IDLE_TIMEOUT_S = 300          # 5 minutes without any output

# Anchors written by infra/installer/lib/common.sh::log_step. The installer
# emits ``═══ Phase H: agora data ═══════…`` lines for each phase boundary.
_STEP_LINE_RE = re.compile(r"═══ (?P<label>[^═]+?) ═══")

# Anchors for the build heartbeat (rebuild-2-images.sh::run_build).
_HEARTBEAT_RE = re.compile(r"sigue construyendo (?P<name>\S+)")

# Pattern of obvious progress dots / rsync stats lines we'd rather hide.
_NOISE_RES: tuple[re.Pattern, ...] = (
    re.compile(r"^\s*$"),                   # blank
    re.compile(r"^\s*\.\s*$"),              # lonely dot
    re.compile(r"^Number of files: "),       # rsync stats noise
    re.compile(r"^Total transferred "),
)


def _is_noise(line: str) -> bool:
    return any(p.match(line) for p in _NOISE_RES)


def repo_root() -> Path:
    """Locate the LAIA repo root.

    Priority: ``$LAIA_ROOT`` env > a parent dir with ``infra/installer`` >
    ``$HOME/LAIA``.
    """
    env = os.environ.get("LAIA_ROOT")
    if env and (Path(env) / "infra" / "installer").is_dir():
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "infra" / "installer").is_dir():
            return parent
    return Path(os.path.expanduser("~")) / "LAIA"


def _kill_tree(proc: subprocess.Popen) -> int:
    """Best-effort graceful shutdown: SIGINT → SIGTERM → SIGKILL.

    Returns the final returncode (negative if killed by a signal). All
    waits are bounded so a misbehaving child can never block the wizard
    indefinitely.
    """
    for sig, grace in ((signal.SIGINT, 5), (signal.SIGTERM, 5)):
        if proc.poll() is not None:
            return proc.returncode
        try:
            proc.send_signal(sig)
        except (ProcessLookupError, OSError):
            return proc.returncode if proc.returncode is not None else 0
        try:
            return proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            continue
    try:
        proc.kill()
        return proc.wait(timeout=3)
    except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
        return proc.returncode if proc.returncode is not None else -1


def stream_command(
    cmd: Sequence[str],
    *,
    step_id: str,
    label: str,
    cwd: Path | None = None,
    env_extra: dict[str, str] | None = None,
    line_filter: Callable[[str], bool] | None = None,
    timeout_s: float | None = None,
    idle_timeout_s: float | None = None,
) -> Iterator[ProgressEvent]:
    """Run ``cmd`` and yield ProgressEvent for the visible parts of its output.

    Emits, in order:
      * one ``step_start``
      * many ``log_line`` (and ``step_progress`` when a section banner appears)
      * one ``step_done`` or ``step_error`` with the exit code in ``extra``

    Timeouts (in seconds; pass a negative number to disable):

    * ``timeout_s``       — absolute upper bound on the whole command
                            (default 2 hours, matches install/clone reality)
    * ``idle_timeout_s``  — max time without ANY stdout output
                            (default 5 minutes; protects against
                             silently-stuck processes)
    """
    if timeout_s is None:
        timeout_s = DEFAULT_TIMEOUT_S
    if idle_timeout_s is None:
        idle_timeout_s = DEFAULT_IDLE_TIMEOUT_S

    started = time.time()
    yield ProgressEvent(
        type="step_start",
        step_id=step_id,
        label=label,
        extra={"cmd": list(cmd)},
    )

    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)

    try:
        proc = subprocess.Popen(
            list(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(cwd) if cwd else None,
            env=env,
            bufsize=1,
            text=True,
            # New process group so we can SIGINT just the child without
            # the wizard receiving it back from the kernel.
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        yield ProgressEvent(
            type="step_error",
            step_id=step_id,
            label=f"Comando no encontrado: {cmd[0]}",
            elapsed_s=time.time() - started,
            extra={"hint": str(exc)},
        )
        return

    assert proc.stdout is not None
    interrupted = False
    timed_out = False
    last_output_at = time.time()
    rc: int | None = None

    def _emit_for(line: str) -> Iterator[ProgressEvent]:
        if _is_noise(line):
            return
        if line_filter and not line_filter(line):
            return
        m_step = _STEP_LINE_RE.search(line)
        if m_step:
            yield ProgressEvent(
                type="step_progress",
                step_id=step_id,
                label=m_step.group("label").strip(),
                elapsed_s=time.time() - started,
            )
            return
        m_hb = _HEARTBEAT_RE.search(line)
        if m_hb:
            yield ProgressEvent(
                type="step_progress",
                step_id=step_id,
                label=f"construyendo {m_hb.group('name')}…",
                elapsed_s=time.time() - started,
            )
            return
        yield ProgressEvent(
            type="log_line",
            step_id=step_id,
            label=line[:300],
            elapsed_s=time.time() - started,
        )

    try:
        # We can't use `for line in proc.stdout` because it blocks
        # indefinitely; we need select-based polling so the idle timeout
        # can fire even when the child has stopped emitting.
        fd = proc.stdout.fileno()
        os.set_blocking(fd, False)
        buf = ""
        poll_interval = 1.0

        while True:
            # Absolute timeout?
            if timeout_s and timeout_s > 0 and (time.time() - started) > timeout_s:
                timed_out = True
                yield ProgressEvent(
                    type="step_error",
                    step_id=step_id,
                    label=(
                        f"{label} excedió el tiempo máximo "
                        f"({int(timeout_s)}s); abortando."
                    ),
                    elapsed_s=time.time() - started,
                    extra={"hint": "Aumenta timeout_s o investiga el cuelgue."},
                )
                rc = _kill_tree(proc)
                break

            # Idle timeout?
            if (
                idle_timeout_s
                and idle_timeout_s > 0
                and (time.time() - last_output_at) > idle_timeout_s
                and proc.poll() is None
            ):
                yield ProgressEvent(
                    type="warning",
                    step_id=step_id,
                    label=(
                        f"{label}: sin output por {int(idle_timeout_s)}s "
                        f"(el proceso sigue vivo)."
                    ),
                    elapsed_s=time.time() - started,
                )
                last_output_at = time.time()  # don't spam the same warning

            ready, _, _ = select.select([fd], [], [], poll_interval)
            if ready:
                try:
                    chunk = os.read(fd, 4096).decode("utf-8", errors="replace")
                except OSError:
                    chunk = ""
                if chunk:
                    last_output_at = time.time()
                    buf += chunk
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        yield from _emit_for(line.rstrip("\r"))
                elif proc.poll() is not None:
                    # EOF and child exited — flush remaining buffer.
                    if buf:
                        yield from _emit_for(buf.rstrip("\r"))
                        buf = ""
                    rc = proc.wait()
                    break
            else:
                # No data within poll_interval; check if child exited.
                if proc.poll() is not None:
                    # Drain any pending output one last time.
                    try:
                        chunk = proc.stdout.read() or ""
                    except OSError:
                        chunk = ""
                    if chunk:
                        buf += chunk
                        while "\n" in buf:
                            line, buf = buf.split("\n", 1)
                            yield from _emit_for(line.rstrip("\r"))
                        if buf:
                            yield from _emit_for(buf.rstrip("\r"))
                    rc = proc.returncode
                    break
    except KeyboardInterrupt:
        interrupted = True
        yield ProgressEvent(
            type="step_error",
            step_id=step_id,
            label=f"{label} interrumpido por el usuario",
            elapsed_s=time.time() - started,
            extra={"hint": "Re-ejecuta laia-wizard --resume para continuar."},
        )
        rc = _kill_tree(proc)
        raise
    finally:
        if rc is None:
            try:
                rc = proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                rc = _kill_tree(proc)

    elapsed = time.time() - started
    if timed_out:
        # We already emitted the error event in the timeout path; nothing
        # extra to do here. The done/error decision below is suppressed.
        return
    if interrupted:
        return
    if rc == 0:
        yield ProgressEvent(
            type="step_done",
            step_id=step_id,
            label=f"{label} OK",
            elapsed_s=elapsed,
            extra={"returncode": 0},
        )
    else:
        yield ProgressEvent(
            type="step_error",
            step_id=step_id,
            label=f"{label} falló (exit {rc})",
            elapsed_s=elapsed,
            extra={"returncode": rc, "hint": "ver ~/.cache/laia-installer.log y /tmp/build-*.log"},
        )


__all__ = ["stream_command", "repo_root"]
