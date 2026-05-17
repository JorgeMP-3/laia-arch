"""cron_* — schedule recurring tasks inside the user's container.

Replaces the old ``cronjob`` tool (disabled in laia-agora; would have
scheduled persistent jobs in the orchestrator). The user's container is
the right home: when ``lxc delete laia-{slug}`` runs, all their crons
die with it. No orphaned jobs in the brain.

Implementation note. We use **systemd timers** rather than crontab:

  - systemd is the executor's PID 1 — already there, no apt-get.
  - ``systemctl status laia-cron-foo.timer`` gives full observability.
  - One unit per cron → simpler delete, no shared file parsing.
  - OnCalendar expressions are richer than 5-field cron and easier for
    an LLM to generate (it's just ``YYYY-MM-DD HH:MM:SS`` with
    wildcards).

For each cron we create two files in /etc/systemd/system/:

    laia-cron-<name>.service       — runs the command once
    laia-cron-<name>.timer         — triggers the service per schedule

The handler is idempotent: re-creating with the same name replaces the
old pair atomically (stop → write → daemon-reload → enable).
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any


SYSTEMD_UNIT_DIR = Path("/etc/systemd/system")
CRON_UNIT_PREFIX = "laia-cron-"


# Friendly name → safe filename component. Same rules as process_tools
# (alnum/dash/underscore) so the systemd unit name is predictable.
_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,47}$")


def _validate_name(name: str) -> str | None:
    """Return None if name is valid, else an error string."""
    if not name or not isinstance(name, str):
        return "name is required (non-empty string)"
    if not _NAME_RE.match(name):
        return ("name must start with a letter/digit and contain only "
                "letters, digits, '-' or '_' (max 48 chars)")
    return None


def _unit_paths(name: str) -> tuple[Path, Path]:
    return (
        SYSTEMD_UNIT_DIR / f"{CRON_UNIT_PREFIX}{name}.service",
        SYSTEMD_UNIT_DIR / f"{CRON_UNIT_PREFIX}{name}.timer",
    )


def _systemctl(*args: str) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["systemctl", *args],
            capture_output=True, text=True, timeout=15,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return 127, "", "systemctl not found — container missing systemd?"
    except subprocess.TimeoutExpired:
        return 124, "", "systemctl timed out after 15s"
    except Exception as exc:
        return 1, "", f"systemctl spawn failed: {exc}"


# ──────────────────────────────────────────────────────────────────────────
# Public handlers
# ──────────────────────────────────────────────────────────────────────────


def cron_create(
    name: str = "",
    schedule: str = "",
    command: str = "",
    description: str = "",
    cwd: str = "/home/user",
    **_ignored,
) -> str:
    """Create or replace a recurring task.

    Args:
        name: Identifier, used as ``laia-cron-<name>.timer`` in systemd.
        schedule: Systemd ``OnCalendar`` expression. Examples:
                  ``"daily"`` (00:00 every day),
                  ``"*-*-* 09:00:00"`` (every day 9am),
                  ``"Mon..Fri 08:30:00"``,
                  ``"hourly"``.
                  See ``man systemd.time``.
        command: Shell command to run, executed via ``/bin/bash -c``.
        description: Optional human label shown in ``systemctl status``.
        cwd: Working directory; defaults to /home/user.
    """
    name_err = _validate_name(name)
    if name_err:
        return json.dumps({"ok": False, "error": name_err})
    if not schedule or not isinstance(schedule, str):
        return json.dumps({"ok": False, "error": "schedule is required (OnCalendar expression)"})
    if not command or not isinstance(command, str):
        return json.dumps({"ok": False, "error": "command is required"})

    service_path, timer_path = _unit_paths(name)

    # If the timer already exists, stop+disable first so we don't end up
    # with two timers triggering the same unit during the rewrite.
    if timer_path.exists():
        _systemctl("stop", timer_path.name)
        _systemctl("disable", timer_path.name)

    description_safe = description or f"LAIA-managed cron: {name}"
    # Service unit
    service_content = (
        "[Unit]\n"
        f"Description={description_safe}\n"
        "After=network.target\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"WorkingDirectory={cwd}\n"
        f"ExecStart=/bin/bash -lc {shlex.quote(command)}\n"
        # Persist some output to journal for ``cron_status``-like flows.
        "StandardOutput=journal\n"
        "StandardError=journal\n"
    )
    # Timer unit
    timer_content = (
        "[Unit]\n"
        f"Description=Timer for {description_safe}\n"
        "\n"
        "[Timer]\n"
        f"OnCalendar={schedule}\n"
        "Persistent=true\n"
        f"Unit={service_path.name}\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )

    try:
        SYSTEMD_UNIT_DIR.mkdir(parents=True, exist_ok=True)
        service_path.write_text(service_content)
        timer_path.write_text(timer_content)
    except Exception as exc:
        return json.dumps({"ok": False, "error": f"could not write unit files: {exc}"})

    rc, out, err = _systemctl("daemon-reload")
    if rc != 0:
        return json.dumps({"ok": False, "error": f"daemon-reload failed: {err or out}"})

    rc, out, err = _systemctl("enable", "--now", timer_path.name)
    if rc != 0:
        # Roll back unit files so we don't leave half-broken state.
        try:
            service_path.unlink()
            timer_path.unlink()
        except Exception:
            pass
        _systemctl("daemon-reload")
        return json.dumps({"ok": False, "error": f"enable --now failed: {err or out}"})

    return json.dumps({
        "ok": True,
        "name": name,
        "service": service_path.name,
        "timer": timer_path.name,
        "schedule": schedule,
    }, ensure_ascii=False)


def cron_list(**_ignored) -> str:
    """List every laia-cron-*.timer and its next trigger."""
    if not SYSTEMD_UNIT_DIR.is_dir():
        return json.dumps({"ok": True, "crons": [], "count": 0})

    timers = sorted(
        p for p in SYSTEMD_UNIT_DIR.iterdir()
        if p.is_file() and p.name.startswith(CRON_UNIT_PREFIX) and p.name.endswith(".timer")
    )
    if not timers:
        return json.dumps({"ok": True, "crons": [], "count": 0})

    out_crons: list[dict[str, Any]] = []
    # ``systemctl list-timers --all`` gives a nice next/last column. Parse
    # the names we care about out of it.
    rc, list_out, _ = _systemctl("list-timers", "--all", "--no-pager", "--no-legend")
    parsed: dict[str, dict[str, str]] = {}
    if rc == 0:
        for line in list_out.splitlines():
            parts = line.strip().split()
            # next  left  last  passed  unit  activates
            for p in parts:
                if p.endswith(".timer") and p.startswith(CRON_UNIT_PREFIX):
                    parsed[p] = {"raw": line.strip()}
                    break

    for tpath in timers:
        name = tpath.stem[len(CRON_UNIT_PREFIX):]
        spath = SYSTEMD_UNIT_DIR / f"{CRON_UNIT_PREFIX}{name}.service"
        schedule = ""
        command = ""
        description = ""
        try:
            for line in tpath.read_text().splitlines():
                if line.startswith("OnCalendar="):
                    schedule = line.split("=", 1)[1].strip()
                if line.startswith("Description="):
                    description = line.split("=", 1)[1].strip()
        except Exception:
            pass
        if spath.exists():
            try:
                for line in spath.read_text().splitlines():
                    if line.startswith("ExecStart="):
                        command = line.split("=", 1)[1].strip()
            except Exception:
                pass
        out_crons.append({
            "name": name,
            "schedule": schedule,
            "command": command,
            "description": description,
            "systemd_status": parsed.get(tpath.name, {}).get("raw", ""),
            "service": spath.name,
            "timer": tpath.name,
        })
    return json.dumps({"ok": True, "crons": out_crons, "count": len(out_crons)}, ensure_ascii=False)


def cron_delete(name: str = "", **_ignored) -> str:
    """Stop, disable and remove the cron with ``name``."""
    name_err = _validate_name(name)
    if name_err:
        return json.dumps({"ok": False, "error": name_err})

    service_path, timer_path = _unit_paths(name)
    if not timer_path.exists() and not service_path.exists():
        return json.dumps({"ok": False, "error": f"no cron named {name!r} found"})

    _systemctl("stop", timer_path.name)
    _systemctl("disable", timer_path.name)
    removed = []
    for p in (timer_path, service_path):
        if p.exists():
            try:
                p.unlink()
                removed.append(p.name)
            except Exception as exc:
                return json.dumps({"ok": False, "error": f"could not remove {p}: {exc}"})

    rc, _out, err = _systemctl("daemon-reload")
    if rc != 0:
        return json.dumps({"ok": False, "error": f"daemon-reload after delete failed: {err}"})

    return json.dumps({"ok": True, "name": name, "removed": removed}, ensure_ascii=False)


__all__ = ["cron_create", "cron_list", "cron_delete",
           "SYSTEMD_UNIT_DIR", "CRON_UNIT_PREFIX"]
