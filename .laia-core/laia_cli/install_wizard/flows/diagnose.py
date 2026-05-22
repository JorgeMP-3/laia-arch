"""Diagnose flow — read-only health check.

Runs the two existing diagnostic scripts and exposes each check as a
structured event so the UI can render a row with ✓ / ⚠ / ✗ instead of a
wall of bash output:

* ``tests/installer/vm-smoke.sh`` — covers LXD containers + agora.db + API.
* ``infra/dev/preflight.sh``      — covers host prereqs, ports, image freshness.

Both scripts already use the same emoji vocabulary (``✓``, ``⚠``, ``✗``), so
we parse those line prefixes into ``step_done`` / ``warning`` /
``step_error`` events.

No fields, no prompts — just one informational screen and then execute().
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..contract import (
    ACTION_BACK,
    Action,
    Field,
    ProgressEvent,
    WizardScreen,
)
from ._subprocess import repo_root, stream_command

flow_id = "diagnose"
first_screen_id = "intro"


_INTRO = WizardScreen(
    id="intro",
    title="Diagnóstico de la instalación",
    description=(
        "Corre los chequeos read-only del producto:\n"
        "  • vm-smoke.sh — containers, /api/health, agora.db, paths.\n"
        "  • preflight.sh — host prereqs, puertos, drift de imagen.\n"
        "No modifica nada en el sistema."
    ),
    fields=(
        Field(name="_info", type="info", label="Listo para ejecutar", default=""),
    ),
    actions=(
        ACTION_BACK,
        Action(name="run", label="Ejecutar diagnóstico", kind="submit"),
    ),
)


screens: dict[str, Any] = {"intro": _INTRO}


def next_screen_id(_screen_id: str, _state) -> str | None:
    return None  # single-screen flow


# ---------------------------------------------------------------------------
# Execution + line parsing
# ---------------------------------------------------------------------------

_CHECK_OK_RE = re.compile(r"^\s*✓\s*(?P<label>.+?)\s*$")
_CHECK_WARN_RE = re.compile(r"^\s*⚠\s*(?P<label>.+?)\s*$")
_CHECK_ERR_RE = re.compile(r"^\s*✗\s*(?P<label>.+?)\s*$")
_SECTION_RE = re.compile(r"^===\s*(?P<label>.+?)\s*===\s*$")


def _classify(line: str) -> ProgressEvent | None:
    m = _CHECK_OK_RE.match(line)
    if m:
        return ProgressEvent(type="step_done", step_id="check",
                             label=m.group("label"))
    m = _CHECK_WARN_RE.match(line)
    if m:
        return ProgressEvent(type="warning", step_id="check",
                             label=m.group("label"))
    m = _CHECK_ERR_RE.match(line)
    if m:
        return ProgressEvent(type="step_error", step_id="check",
                             label=m.group("label"))
    m = _SECTION_RE.match(line)
    if m:
        return ProgressEvent(type="step_progress", step_id="diagnose",
                             label=m.group("label"))
    return None


def _run_script(path: str, label: str) -> Iterator[ProgressEvent]:
    """Run a bash script and translate its emoji lines to events."""
    seen_ok = seen_warn = seen_err = 0
    started_emitted = False

    # We use stream_command to spawn but consume its log_line events to
    # classify further — so we just wrap it.
    for ev in stream_command(["bash", path], step_id=label, label=label):
        if ev.type == "step_start":
            started_emitted = True
            yield ev
            continue
        if ev.type in ("step_done", "step_error"):
            # bubble the script-level outcome at the end
            yield ProgressEvent(
                type="summary",
                step_id=label,
                label=f"{label} terminado",
                extra={"rows": [
                    ("OK", str(seen_ok)),
                    ("Warnings", str(seen_warn)),
                    ("Errors", str(seen_err)),
                    ("Exit", str(ev.extra.get("returncode") if ev.extra else "?")),
                ]},
            )
            yield ev
            continue
        if ev.type == "log_line":
            classified = _classify(ev.label)
            if classified is None:
                yield ev
                continue
            if classified.type == "step_done":
                seen_ok += 1
            elif classified.type == "warning":
                seen_warn += 1
            elif classified.type == "step_error":
                seen_err += 1
            yield classified
            continue
        yield ev
    if not started_emitted:
        # Defensive — should never happen, but at least surface something.
        yield ProgressEvent(
            type="step_error",
            step_id=label,
            label=f"{label} no produjo output",
        )


def _diagnose_dir() -> Path:
    cache = Path(
        os.environ.get("XDG_CACHE_HOME") or
        os.path.join(os.path.expanduser("~"), ".cache")
    )
    path = cache / "laia-wizard" / "diagnose"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _capture(cmd: list[str], *, timeout: int = 20) -> str:
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return f"$ {' '.join(cmd)}\nCOMMAND NOT FOUND\n"
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        return f"$ {' '.join(cmd)}\nTIMEOUT after {timeout}s\n{out}\n"
    return f"$ {' '.join(cmd)}\n(exit {proc.returncode})\n{proc.stdout}\n"


def _write_diagnostic_bundle(root: Path) -> Path:
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = _diagnose_dir() / f"laia-diagnose-{ts}.log"
    commands = [
        ["uname", "-a"],
        ["python3", "--version"],
        ["df", "-h", "/opt", "/srv", os.path.expanduser("~")],
        ["bash", str(root / "bin" / "laia-install"), "--version"],
        ["bash", str(root / "bin" / "laia-clone"), "--help"],
        ["lxc", "list"],
        ["lxc", "image", "list"],
        ["curl", "-fsS", "--max-time", "5", "http://127.0.0.1:8088/api/health"],
        ["systemctl", "--no-pager", "--full", "status", "laia-pathd", "agora-backend", "laia-ui-server"],
        ["journalctl", "--no-pager", "-n", "80", "-u", "agora-backend", "-u", "laia-pathd", "-u", "laia-ui-server"],
    ]
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# LAIA diagnostic bundle\n")
        fh.write(f"# generated: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n")
        fh.write(f"# repo root: {root}\n\n")
        installer_log = Path(os.environ.get("LAIA_LOG_FILE") or Path.home() / ".cache" / "laia-installer.log")
        for cmd in commands:
            fh.write("".join(("=" * 72, "\n")))
            fh.write(_capture(cmd))
            fh.write("\n")
        if installer_log.is_file():
            fh.write("".join(("=" * 72, "\n")))
            fh.write(f"$ tail -120 {installer_log}\n")
            try:
                lines = installer_log.read_text(encoding="utf-8", errors="replace").splitlines()
                fh.write("\n".join(lines[-120:]))
                fh.write("\n")
            except OSError as exc:
                fh.write(f"Could not read installer log: {exc}\n")
    return path


def execute(_state) -> Iterator[ProgressEvent]:
    root = repo_root()
    vm_smoke = root / "tests" / "installer" / "vm-smoke.sh"
    preflight = root / "infra" / "dev" / "preflight.sh"

    for label, path in (("vm-smoke", vm_smoke), ("preflight", preflight)):
        if not path.is_file():
            yield ProgressEvent(
                type="warning",
                step_id=label,
                label=f"No encuentro {path} — saltando",
            )
            continue
        yield from _run_script(str(path), label=label)

    bundle = _write_diagnostic_bundle(root)
    yield ProgressEvent(
        type="summary",
        step_id="diagnose-bundle",
        label="Paquete de diagnóstico",
        extra={"rows": [
            ("Archivo", str(bundle)),
            ("Uso", "Pásame este log si install/clone falla en servidor real"),
        ]},
    )


__all__ = ["flow_id", "first_screen_id", "screens", "next_screen_id", "execute"]
