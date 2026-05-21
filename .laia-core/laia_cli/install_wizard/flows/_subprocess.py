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
import subprocess
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Sequence

from ..contract import ProgressEvent

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


def stream_command(
    cmd: Sequence[str],
    *,
    step_id: str,
    label: str,
    cwd: Path | None = None,
    env_extra: dict[str, str] | None = None,
    line_filter: Callable[[str], bool] | None = None,
) -> Iterator[ProgressEvent]:
    """Run ``cmd`` and yield ProgressEvent for the visible parts of its output.

    Emits, in order:
      * one ``step_start``
      * many ``log_line`` (and ``step_progress`` when a section banner appears)
      * one ``step_done`` or ``step_error`` with the exit code in ``extra``
    """
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
    try:
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            if _is_noise(line):
                continue
            if line_filter and not line_filter(line):
                continue

            m_step = _STEP_LINE_RE.search(line)
            if m_step:
                yield ProgressEvent(
                    type="step_progress",
                    step_id=step_id,
                    label=m_step.group("label").strip(),
                    elapsed_s=time.time() - started,
                )
                continue

            m_hb = _HEARTBEAT_RE.search(line)
            if m_hb:
                yield ProgressEvent(
                    type="step_progress",
                    step_id=step_id,
                    label=f"construyendo {m_hb.group('name')}…",
                    elapsed_s=time.time() - started,
                )
                continue

            yield ProgressEvent(
                type="log_line",
                step_id=step_id,
                label=line[:300],  # bound the event size
                elapsed_s=time.time() - started,
            )
    except KeyboardInterrupt:
        interrupted = True
        # Forward the signal to the child, then wait briefly. If it doesn't
        # exit we kill -9. The main loop's KeyboardInterrupt handler still
        # runs after this generator unwinds.
        try:
            proc.send_signal(__import__("signal").SIGINT)
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        yield ProgressEvent(
            type="step_error",
            step_id=step_id,
            label=f"{label} interrumpido por el usuario",
            elapsed_s=time.time() - started,
            extra={"hint": "Re-ejecuta laia-wizard --resume para continuar."},
        )
        raise
    finally:
        if not interrupted:
            rc = proc.wait()
        else:
            try:
                rc = proc.wait(timeout=1)
            except Exception:
                rc = -1

    elapsed = time.time() - started
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
