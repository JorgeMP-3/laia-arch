"""Filesystem watcher for laia-pathd.

Watches the parent directory of each registered path. When a sibling is
renamed/moved/deleted, fires a callback so the daemon can update its mapping.

Strategy:
- Watch parent dir, not the path itself — moves out of the parent fire
  the same events whether the path is a file or directory.
- Group registered aliases by parent, install one ObservedWatch per parent.
- For each event, decide which alias (if any) is affected:
    * MOVED_FROM(old) + MOVED_TO(new) within same parent  → rename
    * MOVED_FROM(old) without matching MOVED_TO            → moved away
    * DELETE(old)                                          → vanished
    * CREATE(new)                                          → potential recreate

The watcher does NOT decide the new path — it only emits events. Resolution
of "did the old alias just become this new path?" lives in the daemon, which
holds the full registry context (inodes, history, discovery rules).
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class FsEvent:
    kind: str  # "moved" | "deleted" | "created"
    src: str | None  # for moved/deleted
    dst: str | None  # for moved/created
    parent: str


EventCallback = Callable[[FsEvent], None]


class FsWatcher:
    """Wraps watchdog.Observer to expose a simple callback API.

    The callback runs in watchdog's internal thread — do not block.
    """

    def __init__(self, callback: EventCallback):
        self._callback = callback
        self._observer = None  # type: ignore[assignment]
        self._watches: dict[str, object] = {}  # parent -> watch handle
        self._lock = threading.Lock()

    def start(self) -> None:
        from watchdog.observers import Observer
        self._observer = Observer()
        self._observer.start()

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2.0)
            self._observer = None
            self._watches.clear()

    def watch_parents(self, paths: list[str]) -> None:
        """Ensure a watch is installed on the parent of every path.

        Idempotent. Removes watches for parents no longer needed.
        """
        if self._observer is None:
            raise RuntimeError("FsWatcher not started")
        from watchdog.events import FileSystemEventHandler

        needed_parents: set[str] = set()
        for p in paths:
            parent = str(Path(p).parent)
            if Path(parent).is_dir():
                needed_parents.add(parent)

        with self._lock:
            # remove obsolete
            for old in list(self._watches.keys()):
                if old not in needed_parents:
                    self._observer.unschedule(self._watches[old])
                    del self._watches[old]
                    logger.debug("unwatched %s", old)

            # add new
            for parent in needed_parents:
                if parent in self._watches:
                    continue
                handler = _make_handler(parent, self._callback)
                handle = self._observer.schedule(handler, parent, recursive=False)
                self._watches[parent] = handle
                logger.info("watching %s", parent)


def _make_handler(parent: str, callback: EventCallback):
    """Build a watchdog handler that maps low-level events to FsEvents."""
    from watchdog.events import FileSystemEventHandler

    class _Handler(FileSystemEventHandler):
        def on_moved(self, event):  # type: ignore[override]
            callback(FsEvent(kind="moved", src=event.src_path,
                             dst=event.dest_path, parent=parent))

        def on_deleted(self, event):  # type: ignore[override]
            callback(FsEvent(kind="deleted", src=event.src_path,
                             dst=None, parent=parent))

        def on_created(self, event):  # type: ignore[override]
            callback(FsEvent(kind="created", src=None,
                             dst=event.src_path, parent=parent))

    return _Handler()
