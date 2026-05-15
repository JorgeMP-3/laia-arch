"""Pending-restarts tracker for laia-pathd (phase 5).

When a registered path changes and one or more systemd units declare
``X-LaiaPathDeps=<alias>`` in their ``[Unit]`` section, the daemon writes
an entry to ``~/.laia/state/pending-restarts.json``. The operator reviews
with ``laia-path pending-restarts`` and applies with
``laia-path apply-restarts [--yes]``.

No automatic restarts ever happen. This is intentional — false-positive
detection should not bounce production services without human confirmation.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


def _repo_systemd_dir() -> Path:
    """Locate the LAIA repo's systemd unit sources via the path registry.

    Falls back to ~/LAIA/infra/systemd if the env var is unset.
    """
    env = os.environ.get("LAIA_SYSTEMD_UNITS")
    if env:
        return Path(env)
    return Path.home() / "LAIA" / "infra" / "systemd"


# Standard locations where systemd unit files might live, in priority order.
DEFAULT_UNIT_SEARCH_PATHS = (
    Path("/etc/systemd/system"),
    Path("/lib/systemd/system"),
    Path("/usr/lib/systemd/system"),
    Path.home() / ".config/systemd/user",
    _repo_systemd_dir(),
)


@dataclass
class PendingRestart:
    unit: str
    alias: str
    old_path: str
    new_path: str
    detected_at: float = field(default_factory=time.time)
    reason: str = "path-change"


def parse_unit_deps(unit_file: Path) -> list[str]:
    """Return the list of aliases declared in ``X-LaiaPathDeps=`` of a unit.

    Format: ``X-LaiaPathDeps=alias1,alias2`` (comma- or space-separated).
    Returns ``[]`` if the file is unreadable or the directive is absent.
    """
    try:
        text = unit_file.read_text()
    except (FileNotFoundError, PermissionError, OSError):
        return []
    in_unit_section = False
    aliases: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            in_unit_section = line.lower() == "[unit]"
            continue
        if not in_unit_section:
            continue
        if line.startswith("X-LaiaPathDeps"):
            _, _, value = line.partition("=")
            for tok in re.split(r"[,\s]+", value.strip()):
                if tok:
                    aliases.append(tok)
    return aliases


def scan_units(search_paths: Iterable[Path] = DEFAULT_UNIT_SEARCH_PATHS) -> dict[str, list[str]]:
    """Scan all known unit files. Returns ``{unit_name: [alias, ...]}``.

    Only units that declare at least one ``X-LaiaPathDeps`` are included.
    A unit name like 'agora-backend.service' may appear in multiple search
    paths; the first occurrence wins.
    """
    seen: dict[str, list[str]] = {}
    for root in search_paths:
        if not root.is_dir():
            continue
        for unit_file in root.glob("*.service"):
            if unit_file.name in seen:
                continue
            deps = parse_unit_deps(unit_file)
            if deps:
                seen[unit_file.name] = deps
    return seen


class PendingRestartStore:
    """JSON file with a list of ``PendingRestart`` records.

    Operations are idempotent: queuing a restart for the same (unit, alias)
    pair while another entry is pending replaces the existing one (latest
    transition wins). Applying clears all entries.
    """

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[PendingRestart]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text())
            return [PendingRestart(**r) for r in raw]
        except (json.JSONDecodeError, TypeError, KeyError):
            return []

    def save(self, entries: list[PendingRestart]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps([asdict(e) for e in entries], indent=2))
        os.replace(tmp, self.path)

    def queue(self, entry: PendingRestart) -> None:
        entries = self.load()
        entries = [
            e for e in entries
            if not (e.unit == entry.unit and e.alias == entry.alias)
        ]
        entries.append(entry)
        self.save(entries)

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()


def queue_restarts_for_change(
    store: PendingRestartStore,
    *,
    alias: str,
    old_path: str,
    new_path: str,
    units_index: dict[str, list[str]] | None = None,
) -> list[str]:
    """For every unit depending on ``alias``, write a pending-restart entry.

    Returns the list of unit names queued.
    """
    if units_index is None:
        units_index = scan_units()
    queued: list[str] = []
    for unit, deps in units_index.items():
        if alias not in deps:
            continue
        store.queue(PendingRestart(
            unit=unit,
            alias=alias,
            old_path=old_path,
            new_path=new_path,
        ))
        queued.append(unit)
    return queued


def apply_restart(unit: str, *, user: bool = False) -> tuple[bool, str]:
    """Run ``systemctl reload-or-restart <unit>`` and return (ok, output)."""
    cmd = ["systemctl"]
    if user:
        cmd.append("--user")
    cmd += ["reload-or-restart", unit]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        ok = result.returncode == 0
        out = (result.stdout + result.stderr).strip()
        return ok, out or ("restarted" if ok else "failed")
    except FileNotFoundError:
        return False, "systemctl not available"
    except subprocess.TimeoutExpired:
        return False, "timeout"
