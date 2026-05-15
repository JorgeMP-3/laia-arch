"""Persistent state for laia-pathd.

Stores resolved path cache and (in phase 5) pending restart markers.
JSON on disk — small, debuggable, atomic writes.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class PathEntry:
    alias: str
    current_path: str
    inode: int | None = None
    last_verified: float = 0.0
    status: str = "ok"  # "ok" | "stale" | "missing"
    history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class State:
    paths: dict[str, PathEntry] = field(default_factory=dict)
    config_mtime: float = 0.0
    started_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "paths": {k: asdict(v) for k, v in self.paths.items()},
            "config_mtime": self.config_mtime,
            "started_at": self.started_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "State":
        paths = {k: PathEntry(**v) for k, v in d.get("paths", {}).items()}
        return cls(
            paths=paths,
            config_mtime=d.get("config_mtime", 0.0),
            started_at=d.get("started_at", time.time()),
        )


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    os.replace(tmp, path)


class StateStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> State:
        if not self.path.exists():
            return State()
        try:
            return State.from_dict(json.loads(self.path.read_text()))
        except (json.JSONDecodeError, TypeError, KeyError):
            return State()

    def save(self, state: State) -> None:
        _atomic_write(self.path, json.dumps(state.to_dict(), indent=2))


def stat_inode(p: str | Path) -> int | None:
    try:
        return os.stat(p).st_ino
    except (FileNotFoundError, PermissionError):
        return None


def record_change(
    entry: PathEntry,
    new_path: str,
    *,
    reason: str = "unknown",
    keep_history: int = 20,
) -> None:
    """Append a transition to entry.history and mutate current state."""
    if new_path == entry.current_path:
        return
    entry.history.append({
        "ts": time.time(),
        "from": entry.current_path,
        "to": new_path,
        "reason": reason,
    })
    entry.history = entry.history[-keep_history:]
    entry.current_path = new_path
    entry.inode = stat_inode(new_path)
    entry.last_verified = time.time()
    entry.status = "ok" if entry.inode is not None else "missing"
