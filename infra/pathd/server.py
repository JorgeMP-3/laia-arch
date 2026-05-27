"""laia-pathd asyncio orchestrator.

Phase 2 responsibilities:
- Load ~/.laia/config.yaml, resolve all paths.
- Poll config.yaml mtime every 2s; on change, re-resolve and emit side effects.
- Serve JSON-RPC over Unix socket: resolve, resolve_all, status, reload.
- Persist state to ~/.laia/state/path-cache.json.
- Write ~/.laia/.env.paths and sync ~/.laia/atlas/ symlinks on each change.

Phase 3 adds the inotify watcher on the resolved paths themselves.
"""
from __future__ import annotations

import asyncio
import logging
import signal
import time
from pathlib import Path
from typing import Any

# Make .laia-core importable for the resolver.
import sys as _sys
_CORE = Path(__file__).resolve().parents[2] / ".laia-core"
if str(_CORE) not in _sys.path:
    _sys.path.insert(0, str(_CORE))

try:
    from laia_paths import load_config, resolve  # noqa: E402
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        f"laia-pathd: cannot import laia_paths from {_CORE}. "
        f"Ensure .laia-core/ exists and is readable. Original error: {exc}"
    ) from exc

from . import notifier
from .ipc import IpcServer
from .restarts import (
    PendingRestartStore,
    queue_restarts_for_change,
    scan_units,
)
from .state import State, StateStore, PathEntry, record_change, stat_inode
from .watcher import FsEvent, FsWatcher

logger = logging.getLogger(__name__)


class PathDaemon:
    def __init__(
        self,
        *,
        config_path: Path,
        env_file: Path,
        socket_path: Path,
        state_path: Path,
        farm_dir: Path,
        pending_restarts_path: Path | None = None,
        poll_interval: float = 2.0,
    ):
        self.config_path = config_path
        self.env_file = env_file
        self.socket_path = socket_path
        self.state_path = state_path
        self.farm_dir = farm_dir
        self.pending_restarts_path = (
            pending_restarts_path
            or state_path.parent / "pending-restarts.json"
        )
        self.poll_interval = poll_interval

        self.store = StateStore(state_path)
        self.state: State = self.store.load()
        self.restarts = PendingRestartStore(self.pending_restarts_path)
        self._units_index: dict[str, list[str]] = {}
        self._lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
        self._ipc: IpcServer | None = None
        self._fs_watcher: FsWatcher | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._fs_event_queue: asyncio.Queue[FsEvent] = asyncio.Queue()

    # --- public API exposed over IPC -----------------------------------------

    async def _rpc_resolve(self, params: dict[str, Any]) -> str:
        key = params.get("key", "")
        async with self._lock:
            entry = self.state.paths.get(key)
            if entry is None:
                raise KeyError(f"unknown path alias: {key}")
            return entry.current_path

    async def _rpc_resolve_all(self, _: dict[str, Any]) -> dict[str, str]:
        async with self._lock:
            return {k: v.current_path for k, v in self.state.paths.items()}

    async def _rpc_status(self, _: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            return {
                "uptime_s": time.time() - self.state.started_at,
                "config_mtime": self.state.config_mtime,
                "paths_count": len(self.state.paths),
                "config_path": str(self.config_path),
                "env_file": str(self.env_file),
                "socket": str(self.socket_path),
            }

    async def _rpc_reload(self, _: dict[str, Any]) -> dict[str, Any]:
        changed = await self._reload(force=True)
        return {"changed": changed}

    async def _rpc_doctor(self, _: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            report = {}
            for k, e in self.state.paths.items():
                exists = Path(e.current_path).exists()
                report[k] = {
                    "path": e.current_path,
                    "exists": exists,
                    "status": e.status,
                    "last_verified": e.last_verified,
                }
            return {"paths": report, "ok": all(r["exists"] for r in report.values())}

    async def _rpc_history(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        alias = params.get("alias")
        if not alias:
            raise ValueError("alias is required")
        async with self._lock:
            entry = self.state.paths.get(alias)
            if entry is None:
                raise KeyError(f"unknown alias: {alias}")
            return list(entry.history)

    async def _rpc_pending_restarts(self, _: dict[str, Any]) -> list[dict[str, Any]]:
        from dataclasses import asdict
        return [asdict(e) for e in self.restarts.load()]

    async def _rpc_clear_pending(self, _: dict[str, Any]) -> dict[str, Any]:
        self.restarts.clear()
        return {"cleared": True}

    # --- internals -----------------------------------------------------------

    async def _reload(self, *, force: bool = False) -> bool:
        """Re-read config.yaml and update state. Returns True if state changed."""
        try:
            mtime = self.config_path.stat().st_mtime
        except FileNotFoundError:
            logger.warning("config not found: %s", self.config_path)
            return False
        if not force and mtime == self.state.config_mtime:
            return False

        try:
            cfg = load_config(self.config_path)
            resolved = resolve(cfg)
        except Exception as e:
            logger.error("resolve failed: %s", e)
            return False

        changed = False
        async with self._lock:
            self.state.config_mtime = mtime

            # update / add entries
            for alias, path in resolved.items():
                entry = self.state.paths.get(alias)
                if entry is None:
                    self.state.paths[alias] = PathEntry(
                        alias=alias,
                        current_path=path,
                        inode=stat_inode(path),
                        last_verified=time.time(),
                        status="ok" if Path(path).exists() else "missing",
                    )
                    changed = True
                elif entry.current_path != path:
                    record_change(entry, path, reason="config-change")
                    changed = True

            # remove aliases no longer in config
            stale_keys = [k for k in self.state.paths if k not in resolved]
            for k in stale_keys:
                del self.state.paths[k]
                changed = True

        if changed:
            self.store.save(self.state)
            notifier.write_env_file(
                {k: e.current_path for k, e in self.state.paths.items()},
                self.env_file,
                source_path=self.config_path,
            )
            notifier.sync_symlink_farm(
                {k: e.current_path for k, e in self.state.paths.items()},
                self.farm_dir,
            )
        return changed

    async def _config_poller(self) -> None:
        while not self._stop_event.is_set():
            await self._reload()
            self._update_fs_watches()
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.poll_interval
                )
            except asyncio.TimeoutError:
                pass

    # --- filesystem watcher integration -------------------------------------

    def _fs_callback(self, event: FsEvent) -> None:
        """Bridge: watchdog thread -> asyncio queue."""
        if self._loop is None:
            return
        try:
            self._loop.call_soon_threadsafe(
                self._fs_event_queue.put_nowait, event
            )
        except RuntimeError:
            pass  # loop closing

    def _update_fs_watches(self) -> None:
        if self._fs_watcher is None:
            return
        paths = [e.current_path for e in self.state.paths.values()]
        try:
            self._fs_watcher.watch_parents(paths)
        except Exception as e:
            logger.warning("fs watcher update failed: %s", e)

    async def _fs_event_consumer(self) -> None:
        while not self._stop_event.is_set():
            try:
                event = await asyncio.wait_for(
                    self._fs_event_queue.get(), timeout=0.5
                )
            except asyncio.TimeoutError:
                continue
            await self._handle_fs_event(event)

    async def _handle_fs_event(self, event: FsEvent) -> None:
        """Apply a filesystem event to the registry."""
        transitions: list[tuple[str, str, str]] = []  # (alias, old, new)
        async with self._lock:
            changed = False
            if event.kind == "moved" and event.src and event.dst:
                for alias, entry in self.state.paths.items():
                    if entry.current_path == event.src:
                        transitions.append((alias, event.src, event.dst))
                        record_change(entry, event.dst, reason="fs-rename")
                        changed = True
                        logger.info("alias %s renamed: %s -> %s",
                                    alias, event.src, event.dst)
            elif event.kind == "deleted" and event.src:
                for alias, entry in self.state.paths.items():
                    if entry.current_path == event.src:
                        entry.status = "missing"
                        entry.last_verified = time.time()
                        changed = True
                        logger.warning("alias %s vanished: %s",
                                       alias, event.src)

        if changed:
            self.store.save(self.state)
            notifier.write_env_file(
                {k: e.current_path for k, e in self.state.paths.items()},
                self.env_file,
                source_path=self.config_path,
            )
            notifier.sync_symlink_farm(
                {k: e.current_path for k, e in self.state.paths.items()},
                self.farm_dir,
            )
            self._update_fs_watches()

            # Queue pending restarts (phase 5) — NO automatic restart
            for alias, old, new in transitions:
                queued = queue_restarts_for_change(
                    self.restarts,
                    alias=alias,
                    old_path=old,
                    new_path=new,
                    units_index=self._units_index,
                )
                if queued:
                    logger.info(
                        "queued restart marker for %d unit(s) (alias=%s): %s",
                        len(queued), alias, ", ".join(queued),
                    )

    async def run(self) -> None:
        self._loop = asyncio.get_running_loop()
        self.state.started_at = time.time()
        await self._reload(force=True)  # initial load

        # Ensure side-effect outputs exist even when the state was already in
        # sync with config (e.g. daemon restart with no config changes).
        async with self._lock:
            paths_snapshot = {k: e.current_path for k, e in self.state.paths.items()}
        if paths_snapshot:
            notifier.write_env_file(paths_snapshot, self.env_file, source_path=self.config_path)
            notifier.sync_symlink_farm(paths_snapshot, self.farm_dir)

        # Start filesystem watcher (phase 3)
        self._fs_watcher = FsWatcher(self._fs_callback)
        try:
            self._fs_watcher.start()
            self._update_fs_watches()
        except Exception as e:
            logger.warning("fs watcher disabled: %s", e)
            self._fs_watcher = None

        # Phase 5 — scan systemd units for X-LaiaPathDeps directives.
        try:
            self._units_index = scan_units()
            logger.info("indexed %d unit(s) with X-LaiaPathDeps", len(self._units_index))
        except Exception as e:
            logger.warning("unit scan failed: %s", e)
            self._units_index = {}

        handlers = {
            "resolve": self._rpc_resolve,
            "resolve_all": self._rpc_resolve_all,
            "status": self._rpc_status,
            "reload": self._rpc_reload,
            "doctor": self._rpc_doctor,
            "history": self._rpc_history,
            "pending_restarts": self._rpc_pending_restarts,
            "clear_pending": self._rpc_clear_pending,
        }
        self._ipc = IpcServer(self.socket_path, handlers)
        await self._ipc.start()

        for sig in (signal.SIGTERM, signal.SIGINT):
            self._loop.add_signal_handler(sig, lambda: self._stop_event.set())
        self._loop.add_signal_handler(
            signal.SIGHUP,
            lambda: asyncio.create_task(self._reload(force=True)),
        )

        poller = asyncio.create_task(self._config_poller())
        consumer = asyncio.create_task(self._fs_event_consumer())
        ipc_task = asyncio.create_task(self._ipc.serve_forever())
        try:
            await self._stop_event.wait()
        finally:
            poller.cancel()
            consumer.cancel()
            ipc_task.cancel()
            if self._fs_watcher is not None:
                self._fs_watcher.stop()
            await self._ipc.stop()
            self.store.save(self.state)
            logger.info("laia-pathd shutdown complete")
