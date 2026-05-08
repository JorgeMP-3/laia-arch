from __future__ import annotations

import asyncio
import base64
import contextlib
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
import pty
import re
import secrets
import select
import shutil
import signal
import struct
import sys
import termios
import time
import uuid
from pathlib import Path
from typing import Any, Optional

_ANSI_RE = re.compile(rb'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

HERMES_HOME = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
HERMES_AGENT_ROOT = HERMES_HOME / "hermes-agent"
HERMES_AGENT_PYTHON = HERMES_AGENT_ROOT / "venv" / "bin" / "python"
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
AREA_SESSION_INDEX_PATH = HERMES_HOME / "workspace-ui-session-areas.json"

if str(HERMES_HOME) not in sys.path:
    sys.path.insert(0, str(HERMES_HOME))

from workspace_store import WorkspaceStore, _slugify, list_workspaces


CONTROL_ALLOWED_METHODS = {
    "session.create",
    "session.list",
    "session.resume",
    "session.branch",
    "session.close",
    "session.interrupt",
    "session.undo",
    "session.compress",
    "session.usage",
    "session.history",
    "session.title",
    "session.steer",
    "prompt.submit",
    "prompt.background",
    "prompt.btw",
    "commands.catalog",
    "slash.exec",
    "command.dispatch",
    "approval.respond",
    "clarify.respond",
    "sudo.respond",
    "secret.respond",
    "model.options",
    "config.get",
    "config.set",
    "tools.list",
    "tools.show",
    "tools.configure",
    "toolsets.list",
    "rollback.list",
    "rollback.diff",
    "rollback.restore",
    "agents.list",
    "process.stop",
    "personality",
    "skin",
    "voice.toggle",
    "cron.manage",
    "skills.manage",
    "insights.get",
    "plugins.list",
    "browser.manage",
    "reload.mcp",
    "complete.slash",
}

CONTROL_SESSION_METHODS = {
    "prompt.submit",
    "prompt.background",
    "prompt.btw",
    "session.interrupt",
    "session.undo",
    "session.compress",
    "session.usage",
    "session.history",
    "session.title",
    "session.branch",
    "session.steer",
    "slash.exec",
    "command.dispatch",
}

DEFAULT_AGENT_AREA_ID = "workspace"


def _normalize_area_id(area_id: str | None) -> str:
    raw = (area_id or DEFAULT_AGENT_AREA_ID).strip().lower()
    clean = "".join(ch for ch in raw if ch.isalnum() or ch in {"-", "_"})
    return clean or DEFAULT_AGENT_AREA_ID


def _app_context_hash(app_context: str | None) -> str:
    text = (app_context or "").strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def _session_ids_from_item(item: dict[str, Any]) -> set[str]:
    ids = {
        str(item.get("id") or ""),
        str(item.get("session_id") or ""),
        str(item.get("session_key") or ""),
    }
    return {sid for sid in ids if sid}


def _load_area_session_index() -> dict[str, set[str]]:
    try:
        raw = json.loads(AREA_SESSION_INDEX_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    areas = raw.get("areas") if isinstance(raw, dict) else raw
    if not isinstance(areas, dict):
        return {}
    result: dict[str, set[str]] = {}
    for area, ids in areas.items():
        clean_area = _normalize_area_id(str(area))
        if isinstance(ids, list):
            result[clean_area] = {str(sid) for sid in ids if str(sid)}
    return result


def _save_area_session_index(index: dict[str, set[str]]) -> None:
    data = {
        "areas": {area: sorted(ids) for area, ids in sorted(index.items())},
        "updated_at": _now(),
    }
    try:
        AREA_SESSION_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        AREA_SESSION_INDEX_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _register_area_session(area_id: str | None, *session_ids: str | None) -> None:
    area = _normalize_area_id(area_id)
    ids = {str(sid) for sid in session_ids if sid and str(sid)}
    if not ids:
        return
    index = _load_area_session_index()
    index.setdefault(area, set()).update(ids)
    _save_area_session_index(index)


def _indexed_area_for_session(session_id: str, index: dict[str, set[str]] | None = None) -> str | None:
    sid = str(session_id or "")
    if not sid:
        return None
    data = index if index is not None else _load_area_session_index()
    for area, ids in data.items():
        if sid in ids:
            return area
    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workspace_path(name: str) -> Path:
    clean = Path(name).name
    path = HERMES_HOME / "workspaces" / clean
    if not path.exists():
        raise HTTPException(status_code=404, detail="Workspace not found")
    return path


def _store(name: str) -> WorkspaceStore:
    return WorkspaceStore(_workspace_path(name))


def _node_summary(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node["id"],
        "slug": node["slug"],
        "title": node["title"],
        "kind": node["kind"],
        "summary": node.get("summary", ""),
        "updated_at": node.get("updated_at", ""),
        "is_container": bool(node.get("is_container", False)),
    }


def _event_payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload_obj")
    if payload is None:
        try:
            payload = json.loads(event.get("payload") or "{}")
        except Exception:
            payload = {"raw": event.get("payload", "")}
    return {
        "id": event["id"],
        "event_type": event["event_type"],
        "node_id": event.get("node_id"),
        "node_slug": event.get("node_slug"),
        "node_title": event.get("node_title"),
        "payload": payload,
        "created_at": event.get("created_at", ""),
    }


def _node_links(store: WorkspaceStore, node: dict[str, Any]) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for edge in store.list_edges():
        if edge["from_node_id"] == node["id"]:
            links.append(
                {
                    "slug": edge["to_slug"],
                    "title": edge["to_title"],
                    "kind": (store.get_node(edge["to_slug"]) or {}).get("kind", ""),
                    "rel": edge["edge_type"],
                }
            )
        elif edge["to_node_id"] == node["id"]:
            links.append(
                {
                    "slug": edge["from_slug"],
                    "title": edge["from_title"],
                    "kind": (store.get_node(edge["from_slug"]) or {}).get("kind", ""),
                    "rel": edge["edge_type"],
                }
            )
    return links


def _node_detail(store: WorkspaceStore, node: dict[str, Any]) -> dict[str, Any]:
    return {
        **_node_summary(node),
        "content": node.get("body", ""),
        "status": node.get("status", "active"),
        "parent_id": node.get("parent_id"),
        "tags": node.get("aliases", []),
        "created_at": node.get("created_at", ""),
        "filename": node.get("filename", f"{node['slug']}.md"),
        "links": _node_links(store, node),
    }


def _read_config() -> dict[str, Any]:
    path = HERMES_HOME / "config.yaml"
    if not path.exists():
        return {}
    try:
        import yaml

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _write_config(cfg: dict[str, Any]) -> None:
    import yaml

    path = HERMES_HOME / "config.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _as_name_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _append_unique(items: list[str], name: str) -> list[str]:
    return items if name in items else [*items, name]


def _register_workspace_config(name: str, *, writable: bool = True) -> None:
    cfg = _read_config()
    plugin = cfg.setdefault("plugins", {}).setdefault("workspace-context", {})
    plugin["workspaces"] = _append_unique(_as_name_list(plugin.get("workspaces")), name)
    if writable:
        primary = str(plugin.get("workspace", "doyouwin"))
        active = _as_name_list(plugin.get("active_workspaces")) or [primary]
        plugin["active_workspaces"] = _append_unique(active, name)
    _write_config(cfg)


def _active_workspace() -> str:
    cfg = _read_config()
    workspace = cfg.get("plugins", {}).get("workspace-context", {}).get("workspace")
    if workspace:
        return str(workspace)
    workspaces = list_workspaces(HERMES_HOME)
    return workspaces[0].name if workspaces else ""


def _context_engine_config() -> dict[str, Any]:
    cfg = _read_config()
    plugin = cfg.get("plugins", {}).get("workspace-context", {})
    configured = plugin.get("workspaces") or []
    if isinstance(configured, str):
        configured = [w.strip() for w in configured.split(",") if w.strip()]
    active_ws = plugin.get("active_workspaces") or []
    if isinstance(active_ws, str):
        active_ws = [w.strip() for w in active_ws.split(",") if w.strip()]
    primary = str(plugin.get("workspace") or _active_workspace())
    if not active_ws:
        active_ws = [primary]
    return {
        "workspace": primary,
        "inject_mode": str(plugin.get("inject_mode") or "index"),
        "max_chars": int(plugin.get("max_chars") or 24000),
        "workspaces": [str(w) for w in configured],
        "active_workspaces": [str(w) for w in active_ws],
    }


def _configured_workspace_names() -> list[str]:
    cfg = _context_engine_config()
    names = [str(w) for w in cfg.get("workspaces") or [] if str(w)]
    active = str(cfg.get("workspace") or "")
    if active and active not in names:
        names.insert(0, active)
    if not names:
        names = [path.name for path in list_workspaces(HERMES_HOME)]
    seen: set[str] = set()
    return [name for name in names if not (name in seen or seen.add(name))]


class NodePayload(BaseModel):
    title: str
    kind: str
    content: str = ""
    summary: str = ""
    tags: list[str] = []
    parent_ref: Optional[str] = None
    status: str = "active"


class LinkPayload(BaseModel):
    target_ref: str
    rel: str = "references"


class AgentWorkspacePlanPayload(BaseModel):
    title: str
    body: str
    summary: str = ""
    task_id: Optional[str] = None

    class Config:
        extra = "forbid"


class AgentWorkspaceLogPayload(BaseModel):
    summary: str
    details: str = ""
    task_id: Optional[str] = None
    node_ref: Optional[str] = None

    class Config:
        extra = "forbid"


class SessionResumePayload(BaseModel):
    session_key: str


class TitlePayload(BaseModel):
    title: str


class BranchPayload(BaseModel):
    name: Optional[str] = None


class CommandPayload(BaseModel):
    command: str
    session_id: Optional[str] = None


class ConfigPatchPayload(BaseModel):
    key: str
    value: Any


class CreateWorkspacePayload(BaseModel):
    name: str
    description: str = ""
    areas: list[str] = []


class ModelPayload(BaseModel):
    model: str


class ReasoningPayload(BaseModel):
    effort: str


class ToolTogglePayload(BaseModel):
    enabled: bool = True


class PersonalityPayload(BaseModel):
    name: str


class SkillInstallPayload(BaseModel):
    name: str
    category: Optional[str] = None


class RollbackPayload(BaseModel):
    rollback_id: str


class CronPayload(BaseModel):
    schedule: Optional[str] = None
    command: Optional[str] = None
    name: Optional[str] = None


class ChatMessagePayload(BaseModel):
    role: str
    content: str


class ChatPayload(BaseModel):
    messages: list[ChatMessagePayload] = []
    workspace: Optional[str] = None


class HermesWebSession:
    def __init__(self) -> None:
        self.proc: asyncio.subprocess.Process | None = None
        self.pending: dict[str, asyncio.Future] = {}
        self.clients: set[asyncio.Queue] = set()
        self.area_sessions: dict[str, dict[str, str]] = {}
        # Compatibility field for legacy status/read paths. The area_sessions
        # mapping is the source of truth for routing new requests.
        self.control_session_id: str | None = None
        self._stdout_task: asyncio.Task | None = None
        self._stderr_task: asyncio.Task | None = None
        self._start_lock = asyncio.Lock()
        self._seq = 0
        self._last_client_left_at: float | None = None
        self._session_list_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    def add_client(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=2000)
        self.clients.add(queue)
        self._last_client_left_at = None
        return queue

    def remove_client(self, queue: asyncio.Queue) -> None:
        self.clients.discard(queue)
        if not self.clients:
            self._last_client_left_at = asyncio.get_running_loop().time()
            asyncio.create_task(self._maybe_idle_close())

    async def _maybe_idle_close(self) -> None:
        try:
            seconds = float(os.environ.get("HERMES_WEB_IDLE_CLOSE_SECONDS", "0"))
        except ValueError:
            seconds = 0
        if seconds <= 0:
            return
        await asyncio.sleep(seconds)
        if self.clients:
            return
        await self.stop()

    async def start(self) -> None:
        async with self._start_lock:
            if self.proc and self.proc.returncode is None:
                return

            custom = os.environ.get("HERMES_WEB_GATEWAY_CMD", "").strip()
            if custom:
                self.proc = await asyncio.create_subprocess_shell(
                    custom,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(HERMES_AGENT_ROOT if HERMES_AGENT_ROOT.exists() else HERMES_HOME),
                )
            else:
                python = str(HERMES_AGENT_PYTHON if HERMES_AGENT_PYTHON.exists() else sys.executable)
                self.proc = await asyncio.create_subprocess_exec(
                    python,
                    "-m",
                    "tui_gateway.entry",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(HERMES_AGENT_ROOT if HERMES_AGENT_ROOT.exists() else HERMES_HOME),
                )
            self._stdout_task = asyncio.create_task(self._read_stdout())
            self._stderr_task = asyncio.create_task(self._read_stderr())

    async def stop(self) -> None:
        proc = self.proc
        self.proc = None
        for task in (self._stdout_task, self._stderr_task):
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._stdout_task = None
        self._stderr_task = None
        for fut in list(self.pending.values()):
            if not fut.done():
                fut.set_exception(RuntimeError("Gateway stopped"))
        self.pending.clear()
        if proc and proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                await proc.wait()

    def session_id_for_area(self, area_id: str | None) -> str | None:
        area = _normalize_area_id(area_id)
        entry = self.area_sessions.get(area) or {}
        return entry.get("session_id")

    async def ensure_session(
        self,
        area_id: str | None = None,
        app_context: str | None = None,
        notify_ready: bool = True,
    ) -> str:
        await self.start()
        area = _normalize_area_id(area_id)
        context_hash = _app_context_hash(app_context)
        existing = self.area_sessions.get(area)
        if existing and (not context_hash or existing.get("app_context_hash", "") == context_hash):
            sid = existing.get("session_id", "")
            if sid:
                self.control_session_id = sid
                _register_area_session(area, sid)
                if notify_ready:
                    await self.broadcast(
                        {
                            "type": "event",
                            "event": "control.ready",
                            "session_id": sid,
                            "payload": {"area_id": area, "session_id": sid},
                        }
                    )
                return sid
        create_params: dict[str, Any] = {}
        if app_context:
            create_params["app_context"] = app_context
        create_params["area_id"] = area
        result = await self.rpc("session.create", create_params)
        session_id = str(result.get("session_id") or result.get("session_key") or "")
        if not session_id:
            session_id = f"web-{uuid.uuid4().hex[:8]}"
        self.area_sessions[area] = {
            "session_id": session_id,
            "app_context_hash": context_hash,
        }
        _register_area_session(area, session_id, str(result.get("session_key") or ""))
        self.invalidate_session_list_cache()
        self.control_session_id = session_id
        if notify_ready:
            await self.broadcast(
                {
                    "type": "event",
                    "event": "control.ready",
                    "session_id": session_id,
                    "payload": {"area_id": area, "session_id": session_id},
                }
            )
        return session_id

    def invalidate_session_list_cache(self) -> None:
        self._session_list_cache.clear()

    async def list_sessions_cached(self, area_id: str | None = None) -> list[dict[str, Any]]:
        now = time.monotonic()
        area = _normalize_area_id(area_id)
        cached = self._session_list_cache.get(area)
        if cached and now - cached[0] < 3:
            return cached[1]
        result = await self.rpc("session.list", {"limit": 200, "area_id": area})
        sessions = result.get("sessions") or result.get("items") or []
        if not isinstance(sessions, list):
            sessions = []
        normalized: list[dict[str, Any]] = []
        for item in sessions:
            if not isinstance(item, dict):
                continue
            session_id = str(item.get("session_id") or item.get("session_key") or item.get("id") or "")
            if not session_id:
                continue
            normalized.append(
                {
                    **item,
                    "id": item.get("id") or session_id,
                    "session_id": session_id,
                    "session_key": item.get("session_key") or session_id,
                    "updated_at": item.get("updated_at") or item.get("started_at"),
                }
            )
        self._session_list_cache[area] = (now, normalized)
        return normalized

    async def rpc(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        session_id: str | None = None,
        area_id: str | None = None,
        app_context: str | None = None,
    ) -> dict[str, Any]:
        if method not in CONTROL_ALLOWED_METHODS:
            raise HTTPException(status_code=403, detail=f"Method not allowed: {method}")
        await self.start()
        if not self.proc or not self.proc.stdin:
            raise HTTPException(status_code=503, detail="Gateway is not running")

        payload = dict(params or {})
        if session_id:
            payload.setdefault("session_id", session_id)
        elif method in CONTROL_SESSION_METHODS:
            payload.setdefault(
                "session_id",
                await self.ensure_session(
                    area_id=area_id,
                    app_context=app_context,
                    notify_ready=False,
                ),
            )

        self._seq += 1
        req_id = f"web-{self._seq}"
        future = asyncio.get_running_loop().create_future()
        self.pending[req_id] = future
        frame = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": payload}
        self.proc.stdin.write((json.dumps(frame, ensure_ascii=False) + "\n").encode("utf-8"))
        await self.proc.stdin.drain()
        try:
            return await asyncio.wait_for(future, timeout=120)
        finally:
            self.pending.pop(req_id, None)

    async def _read_stdout(self) -> None:
        assert self.proc and self.proc.stdout
        while True:
            line = await self.proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                await self.broadcast({"type": "event", "event": "gateway.stdout", "payload": {"line": text}})
                continue
            await self._handle_gateway_message(msg)
        await self.broadcast({"type": "event", "event": "gateway.exit", "payload": {"returncode": self.proc.returncode if self.proc else None}})

    async def _read_stderr(self) -> None:
        assert self.proc and self.proc.stderr
        while True:
            line = await self.proc.stderr.readline()
            if not line:
                break
            await self.broadcast(
                {
                    "type": "event",
                    "event": "gateway.stderr",
                    "payload": {"line": line.decode("utf-8", errors="replace").rstrip()},
                }
            )

    async def _handle_gateway_message(self, msg: dict[str, Any]) -> None:
        if "id" in msg and ("result" in msg or "error" in msg):
            future = self.pending.get(str(msg["id"]))
            if future and not future.done():
                if "error" in msg:
                    future.set_exception(RuntimeError(json.dumps(msg["error"], ensure_ascii=False)))
                else:
                    future.set_result(msg.get("result") or {})
            return

        if msg.get("method") == "event":
            params = msg.get("params") or {}
            event = str(params.get("type") or "event")
            session_id = params.get("session_id")
            payload = params.get("payload") or {}
            if event == "session.info" and session_id:
                self.control_session_id = str(session_id)
            await self.broadcast({"type": "event", "event": event, "session_id": session_id, "payload": payload})
            return

        await self.broadcast({"type": "event", "event": "gateway.message", "payload": msg})

    async def broadcast(self, frame: dict[str, Any]) -> None:
        stale: list[asyncio.Queue] = []
        for queue in list(self.clients):
            try:
                queue.put_nowait(frame)
            except asyncio.QueueFull:
                stale.append(queue)
        for queue in stale:
            self.clients.discard(queue)


_control = HermesWebSession()


class TerminalSession:
    def __init__(
        self,
        *,
        terminal_id: str,
        agent_type: str,
        command: list[str],
        cwd: Optional[str],
        cols: int,
        rows: int,
        label: Optional[str] = None,
        permission_mode: str = "default",
        agent_token: str = "",
        active_workspace: str = "",
        sandboxed: bool = False,
        sandbox_warning: str = "",
    ) -> None:
        self.terminal_id = terminal_id
        self.agent_type = agent_type
        self.label: str = (label or agent_type).strip()
        self.permission_mode = permission_mode if permission_mode in {"default", "bypass"} else "default"
        self.agent_token = agent_token
        self.active_workspace = active_workspace
        self.sandboxed = sandboxed
        self.sandbox_warning = sandbox_warning
        self.command = command
        self.cwd = str(Path(cwd).expanduser()) if cwd else str(HERMES_AGENT_ROOT if HERMES_AGENT_ROOT.exists() else HERMES_HOME)
        self.cols = max(20, int(cols or 220))
        self.rows = max(5, int(rows or 50))
        self.fd: int | None = None
        self.pid: int | None = None
        self.exit_code: int | None = None
        self.clients: set[asyncio.Queue] = set()
        self._reader_task: asyncio.Task | None = None
        self._exit_task: asyncio.Task | None = None
        self.created_at = _now()
        self._scrollback: bytearray = bytearray()  # ring buffer ~256 KB
        self._scrollback_limit: int = 256 * 1024

    def _make_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        env["COLUMNS"] = str(self.cols)
        env["LINES"] = str(self.rows)
        env["COMMAND_CENTER_API"] = _command_center_api_base()
        env["COMMAND_CENTER_TERMINAL_ID"] = self.terminal_id
        env["COMMAND_CENTER_AGENT_TOKEN"] = self.agent_token
        env["COMMAND_CENTER_ACTIVE_WORKSPACE"] = self.active_workspace
        env["COMMAND_CENTER_CCW"] = str(Path(__file__).parent / "bin" / "ccw")
        env["PATH"] = f"{Path(__file__).parent / 'bin'}:{env.get('PATH', '')}"
        return env

    async def start(self) -> None:
        self.pid, self.fd = self._spawn()
        os.set_blocking(self.fd, False)
        self._reader_task = asyncio.create_task(self._read_pty())
        self._exit_task = asyncio.create_task(self._watch_exit())
        asyncio.create_task(self._trigger_initial_render())

    def _spawn(self) -> tuple[int, int]:
        pid, fd = pty.fork()
        if pid == 0:
            try:
                winsize = struct.pack("HHHH", self.rows, self.cols, 0, 0)
                fcntl.ioctl(0, termios.TIOCSWINSZ, winsize)
                os.chdir(self.cwd)
                os.execvpe(self.command[0], self.command, self._make_env())
            except Exception as exc:
                os.write(2, f"failed to exec {self.command!r}: {exc}\n".encode())
                os._exit(127)
        winsize = struct.pack("HHHH", self.rows, self.cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
        return pid, fd

    async def _read_pty(self) -> None:
        while self.fd is not None:
            data = await asyncio.to_thread(self._blocking_read)
            if not data:
                await asyncio.sleep(0.02)
                continue
            self._scrollback.extend(data)
            if len(self._scrollback) > self._scrollback_limit:
                del self._scrollback[:len(self._scrollback) - self._scrollback_limit]
            await self._broadcast({"t": "o", "d": base64.b64encode(data).decode("ascii")})

    def _blocking_read(self) -> bytes:
        if self.fd is None:
            return b""
        try:
            ready, _, _ = select.select([self.fd], [], [], 0.1)
            if not ready:
                return b""
            return os.read(self.fd, 65536)
        except OSError:
            return b""

    async def _trigger_initial_render(self) -> None:
        for delay in (0.4, 1.2):
            await asyncio.sleep(delay)
            if self.pid and self.exit_code is None:
                with contextlib.suppress(ProcessLookupError):
                    os.kill(self.pid, signal.SIGWINCH)

    async def _watch_exit(self) -> None:
        if self.pid is None:
            return
        try:
            _, status = await asyncio.to_thread(os.waitpid, self.pid, 0)
            if os.WIFEXITED(status):
                self.exit_code = os.WEXITSTATUS(status)
            elif os.WIFSIGNALED(status):
                self.exit_code = 128 + os.WTERMSIG(status)
            else:
                self.exit_code = status
        finally:
            fd = self.fd
            self.fd = None
            if fd is not None:
                with contextlib.suppress(OSError):
                    os.close(fd)
            await self._broadcast({"t": "exit", "code": self.exit_code})
            await self._notify_hermes_exit()

    async def _notify_hermes_exit(self) -> None:
        session_id = _control.session_id_for_area("command-center")
        if not session_id:
            return
        with contextlib.suppress(Exception):
            await _control.rpc(
                "prompt.btw",
                {
                    "text": (
                        f"[Command Center] Terminal {self.terminal_id[:8]} ({self.agent_type}) "
                        f"finalizó con exit code {self.exit_code}. "
                        f"Usa command_center_list para ver el estado actualizado."
                    )
                },
                session_id=session_id,
            )

    async def resize(self, cols: int, rows: int) -> None:
        self.cols = max(20, int(cols))
        self.rows = max(5, int(rows))
        if self.fd is None:
            return
        winsize = struct.pack("HHHH", self.rows, self.cols, 0, 0)
        with contextlib.suppress(OSError):
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)
        if self.pid:
            with contextlib.suppress(ProcessLookupError):
                os.kill(self.pid, signal.SIGWINCH)

    async def write(self, data: bytes) -> None:
        if self.fd is None:
            raise HTTPException(status_code=410, detail="Terminal process has exited")
        await asyncio.to_thread(os.write, self.fd, data)

    async def kill(self) -> None:
        if self.pid and self.exit_code is None:
            with contextlib.suppress(ProcessLookupError):
                os.kill(self.pid, signal.SIGTERM)
        for task in (self._reader_task, self._exit_task):
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        fd = self.fd
        self.fd = None
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)
        if self.exit_code is None:
            self.exit_code = -15
        await self._broadcast({"t": "exit", "code": self.exit_code})

    async def add_client(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=2000)
        # Replay scrollback so new clients see existing terminal content
        if self._scrollback:
            queue.put_nowait({"t": "o", "d": base64.b64encode(bytes(self._scrollback)).decode("ascii")})
        self.clients.add(queue)
        return queue

    def remove_client(self, queue: asyncio.Queue) -> None:
        self.clients.discard(queue)

    async def _broadcast(self, frame: dict[str, Any]) -> None:
        stale: list[asyncio.Queue] = []
        for queue in list(self.clients):
            try:
                queue.put_nowait(frame)
            except asyncio.QueueFull:
                stale.append(queue)
        for queue in stale:
            self.clients.discard(queue)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.terminal_id,
            "agent_type": self.agent_type,
            "label": self.label,
            "permission_mode": self.permission_mode,
            "active_workspace": self.active_workspace,
            "sandboxed": self.sandboxed,
            "sandbox_warning": self.sandbox_warning,
            "synapse": _terminal_synapse.get(self.terminal_id, {}),
            "command": self.command,
            "cwd": self.cwd,
            "cols": self.cols,
            "rows": self.rows,
            "pid": self.pid,
            "exit_code": self.exit_code,
            "alive": self.fd is not None and self.exit_code is None,
            "created_at": self.created_at,
        }


_terminals: dict[str, TerminalSession] = {}
_agent_tokens: dict[str, str] = {}
_terminal_synapse: dict[str, dict[str, Any]] = {}
_terminal_approvals: dict[str, dict[str, Any]] = {}
_terminal_approval_settings: dict[str, bool] = {"prompt_approval_required": True}


def _command_center_api_base() -> str:
    base = os.environ.get("WORKSPACE_UI_URL", "http://127.0.0.1:8077").rstrip("/")
    return f"{base}/api"


def _workspace_db_paths() -> list[Path]:
    paths: list[Path] = []
    for name in _configured_workspace_names():
        db_path = HERMES_HOME / "workspaces" / name / "workspace.db"
        if db_path.exists():
            paths.append(db_path)
    return paths


def _wrap_command_with_workspace_sandbox(command: list[str], cwd: Optional[str]) -> tuple[list[str], bool, str]:
    bwrap = shutil.which("bwrap")
    if not bwrap:
        return command, False, "bwrap no está disponible; se usa política API/prompt sin sandbox de filesystem."

    args = [
        bwrap,
        "--new-session",
        "--die-with-parent",
        "--ro-bind", "/", "/",
        "--dev", "/dev",
        "--proc", "/proc",
    ]
    for path in (Path.home(), Path("/tmp")):
        if path.exists():
            args.extend(["--bind", str(path), str(path)])
    if cwd:
        cwd_path = Path(cwd).expanduser()
        if cwd_path.exists():
            args.extend(["--bind", str(cwd_path), str(cwd_path)])

    config_path = HERMES_HOME / "config.yaml"
    if config_path.exists():
        args.extend(["--ro-bind", str(config_path), str(config_path)])
    for db_path in _workspace_db_paths():
        args.extend(["--ro-bind", str(db_path), str(db_path)])

    args.extend(["--", *command])
    return args, True, ""


def _agent_protocol_prompt(task: str, session: TerminalSession) -> str:
    return (
        "[COMMAND CENTER WORKSPACE SYNAPSE]\n"
        f"- Terminal ID: {session.terminal_id}\n"
        f"- Workspace activo para planes/logs: {session.active_workspace}\n"
        "- Puedes leer cualquier workspace necesario con `ccw workspaces`, `ccw search`, `ccw node`, `ccw events`.\n"
        "- Puedes editar código según la tarea, pero NO edites `workspace.db`, config.yaml ni reconfigures workspaces.\n"
        "- Para coordinación persistente usa solo append-only: `ccw plan --title ... --body ...` y `ccw log --summary ... --details ...`.\n"
        "- No uses sqlite3/Python/curl para modificar la DB general; Hermes documenta y fusiona el conocimiento final.\n"
        + (f"- Aviso sandbox: {session.sandbox_warning}\n" if session.sandbox_warning else "")
        + "\n[TAREA]\n"
        f"{task.strip()}"
    )


def _extract_agent_token(authorization: Optional[str], x_command_center_agent_token: Optional[str]) -> str:
    token = (x_command_center_agent_token or "").strip()
    if not token and authorization:
        prefix = "Bearer "
        if authorization.startswith(prefix):
            token = authorization[len(prefix):].strip()
    return token


def _reject_agent_token_capability(
    authorization: Optional[str],
    x_command_center_agent_token: Optional[str],
) -> None:
    token = _extract_agent_token(authorization, x_command_center_agent_token)
    if token and token in _agent_tokens:
        raise HTTPException(
            status_code=403,
            detail="Terminal agent tokens can write only through /api/agent-workspace/plan and /api/agent-workspace/log.",
        )

_INTERACTIVE_COMMANDS: dict[str, list[str]] = {
    "bash": ["bash", "-l"],
    "claude-code-planner": ["bash", "-lc", "exec claude"],
    "claude-code-cc2":     ["bash", "-lc", 'export HOME="$HOME/.claude-cuenta2"; exec claude'],
    "codex-worker": ["bash", "-lc", "git rev-parse --git-dir >/dev/null 2>&1 || git init -q; exec codex"],
    "opencode-worker": ["bash", "-lc", 'export PATH="$HOME/.opencode/bin:$PATH"; exec opencode'],
}


_BYPASS_PERMISSION_COMMANDS: dict[str, list[str]] = {
    "claude-code-planner": ["bash", "-lc", "exec claude --dangerously-skip-permissions"],
    "claude-code-cc2": ["bash", "-lc", 'export HOME="$HOME/.claude-cuenta2"; exec claude --dangerously-skip-permissions'],
    "codex-worker": ["bash", "-lc", "git rev-parse --git-dir >/dev/null 2>&1 || git init -q; exec codex --dangerously-bypass-approvals-and-sandbox"],
}


def _resolve_agent_command(agent_type: str, permission_mode: str = "default") -> list[str]:
    if permission_mode == "bypass" and agent_type in _BYPASS_PERMISSION_COMMANDS:
        return _BYPASS_PERMISSION_COMMANDS[agent_type]
    if agent_type in _INTERACTIVE_COMMANDS:
        return _INTERACTIVE_COMMANDS[agent_type]
    config_path = HERMES_HOME / "ai-agents.json"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            agent = (cfg.get("agents") or {}).get(agent_type) or {}
            command = agent.get("interactive_command") or agent.get("command")
            if isinstance(command, list) and command:
                return [str(part) for part in command]
        except Exception:
            pass
    return ["bash", "-l"]


class SpawnTerminalPayload(BaseModel):
    agent_type: str = "bash"
    cwd: Optional[str] = None
    cols: int = 220
    rows: int = 50
    prompt: Optional[str] = None
    label: Optional[str] = None
    permission_mode: str = "default"
    require_prompt_approval: bool = False


class InjectPayload(BaseModel):
    text: str
    press_enter: bool = True
    require_approval: bool = False
    requested_by: Optional[str] = None


class TerminalApprovalSettingsPayload(BaseModel):
    prompt_approval_required: bool


def _pending_terminal_approvals() -> list[dict[str, Any]]:
    return [
        approval
        for approval in sorted(_terminal_approvals.values(), key=lambda a: a["created_at"])
        if approval.get("status") == "pending"
    ]


def _create_terminal_approval(
    *,
    action: str,
    terminal: TerminalSession,
    text: str,
    press_enter: bool,
    requested_by: str | None,
) -> dict[str, Any]:
    approval_id = str(uuid.uuid4())[:8]
    approval = {
        "id": approval_id,
        "action": action,
        "terminal_id": terminal.terminal_id,
        "terminal_label": terminal.label,
        "agent_type": terminal.agent_type,
        "text": text,
        "press_enter": press_enter,
        "requested_by": requested_by or "hermes",
        "status": "pending",
        "created_at": _now(),
    }
    _terminal_approvals[approval_id] = approval
    return approval


async def _apply_terminal_approval(approval: dict[str, Any]) -> int:
    session = _terminals.get(str(approval.get("terminal_id")))
    if session is None:
        raise HTTPException(status_code=404, detail="Terminal not found")
    text = str(approval.get("text") or "")
    payload = text + ("\r" if approval.get("press_enter", True) else "")
    await session.write(payload.encode("utf-8"))
    approval["status"] = "approved"
    approval["resolved_at"] = _now()
    approval["injected"] = len(payload)
    return len(payload)


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    try:
        yield
    finally:
        for terminal_id in list(_terminals):
            session = _terminals.pop(terminal_id, None)
            if session:
                await session.kill()
        await _control.stop()


app = FastAPI(title="Hermes Workspace UI", lifespan=app_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "service": "workspace-ui", "time": _now()}


@app.post("/api/chat")
async def chat(payload: ChatPayload) -> StreamingResponse:
    async def _stream():
        message = (
            "El chat flotante legacy esta desactivado. Usa el chat oficial de la herramienta "
            "activa, montado con ToolShell/AgentProvider."
        )
        yield "data: " + json.dumps({"type": "error", "message": message}, ensure_ascii=False) + "\n\n"
        yield "data: " + json.dumps({"type": "done"}) + "\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@app.get("/api/workspaces")
async def get_workspaces() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in list_workspaces(HERMES_HOME):
        store = WorkspaceStore(path)
        meta = store.meta()
        items.append(
            {
                "name": path.name,
                "node_count": len(store.list_all_nodes()),
                "edge_count": len(store.list_edges()),
                "updated_at": meta.get("updated_at"),
            }
        )
    return items


@app.post("/api/workspaces")
async def create_workspace(payload: CreateWorkspacePayload) -> dict[str, Any]:
    import re
    name = payload.name.strip().lower()
    if not re.match(r'^[a-z0-9_-]+$', name):
        raise HTTPException(status_code=400, detail="Workspace name must be lowercase alphanumeric with hyphens/underscores only")
    ws_path = HERMES_HOME / "workspaces" / name
    if ws_path.exists() and (ws_path / "workspace.db").exists():
        raise HTTPException(status_code=409, detail=f"Workspace '{name}' already exists")
    store = WorkspaceStore(ws_path)
    store.ensure_workspace_layout()
    result = store.seed_workspace(description=payload.description or f"Workspace {name}.", areas=payload.areas)
    _register_workspace_config(name, writable=True)
    index_node = result.get("index_node") or result.get("index") or {}
    return {
        "ok": True,
        "name": name,
        "path": str(ws_path),
        "index_slug": index_node.get("slug", "index"),
        "writable": True,
    }


@app.get("/api/workspaces/{workspace}/nodes")
async def get_nodes(workspace: str) -> list[dict[str, Any]]:
    return [_node_summary(node) for node in _store(workspace).list_all_nodes()]


@app.get("/api/workspaces/{workspace}/nodes/{ref}")
async def get_node(workspace: str, ref: str) -> dict[str, Any]:
    store = _store(workspace)
    node = store.get_node(ref)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return _node_detail(store, node)


@app.post("/api/workspaces/{workspace}/nodes")
async def create_node(
    workspace: str,
    payload: NodePayload,
    authorization: Optional[str] = Header(default=None),
    x_command_center_agent_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _reject_agent_token_capability(authorization, x_command_center_agent_token)
    store = _store(workspace)
    slug = _slugify(payload.title)
    node = store.upsert_node(
        slug=slug,
        title=payload.title,
        kind=payload.kind,
        summary=payload.summary,
        body=payload.content,
        status=payload.status,
        parent_ref=payload.parent_ref,
        aliases=payload.tags,
        source_kind="interactive",
    )
    return _node_detail(store, node)


@app.put("/api/workspaces/{workspace}/nodes/{ref}")
async def update_node(
    workspace: str,
    ref: str,
    payload: NodePayload,
    authorization: Optional[str] = Header(default=None),
    x_command_center_agent_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _reject_agent_token_capability(authorization, x_command_center_agent_token)
    store = _store(workspace)
    existing = store.get_node(ref)
    if not existing:
        raise HTTPException(status_code=404, detail="Node not found")
    node = store.upsert_node(
        slug=existing["slug"],
        title=payload.title,
        kind=payload.kind,
        summary=payload.summary,
        body=payload.content,
        status=payload.status,
        parent_ref=payload.parent_ref if payload.parent_ref is not None else existing.get("parent_id"),
        aliases=payload.tags,
        source_kind="interactive",
        filename=existing.get("filename"),
    )
    return _node_detail(store, node)


@app.delete("/api/workspaces/{workspace}/nodes/{ref}")
async def delete_node(
    workspace: str,
    ref: str,
    authorization: Optional[str] = Header(default=None),
    x_command_center_agent_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _reject_agent_token_capability(authorization, x_command_center_agent_token)
    store = _store(workspace)
    node = store.get_node(ref)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    with store.connect() as conn:
        node_id = node["id"]
        conn.execute("DELETE FROM edges WHERE from_node_id = ? OR to_node_id = ?", (node_id, node_id))
        conn.execute("DELETE FROM aliases WHERE node_id = ?", (node_id,))
        conn.execute("DELETE FROM artifacts WHERE node_id = ?", (node_id,))
        conn.execute("DELETE FROM node_fts WHERE rowid = ?", (node_id,))
        conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        store._record_event(conn, "node_deleted", None, {"slug": node["slug"], "kind": node["kind"]})
        store._set_meta(conn, "updated_at", _now())
    return {"ok": True}


@app.get("/api/workspaces/{workspace}/search")
async def search_nodes(workspace: str, q: str = Query("")) -> list[dict[str, Any]]:
    return [
        {
            "slug": node["slug"],
            "title": node["title"],
            "kind": node["kind"],
            "score": float(node.get("score", 0.0)),
            "summary": node.get("summary", ""),
            "is_container": bool(node.get("is_container", False)),
        }
        for node in _store(workspace).search_nodes(q, limit=25)
    ]


@app.get("/api/workspaces/{workspace}/graph")
async def get_graph(workspace: str) -> dict[str, Any]:
    store = _store(workspace)
    nodes = [{"id": node["slug"], "label": node["title"], "kind": node["kind"]} for node in store.list_all_nodes()]
    edges = [{"source": edge["from_slug"], "target": edge["to_slug"], "rel": edge["edge_type"]} for edge in store.list_edges()]
    return {"nodes": nodes, "edges": edges}


@app.post("/api/workspaces/{workspace}/nodes/{ref}/links")
async def add_link(
    workspace: str,
    ref: str,
    payload: LinkPayload,
    authorization: Optional[str] = Header(default=None),
    x_command_center_agent_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _reject_agent_token_capability(authorization, x_command_center_agent_token)
    return _store(workspace).link_nodes(ref, payload.target_ref, payload.rel)


@app.get("/api/workspaces/{workspace}/events")
async def get_events(workspace: str) -> list[dict[str, Any]]:
    return [_event_payload(event) for event in _store(workspace).list_events()[:200]]


def _terminal_from_agent_token(
    authorization: Optional[str],
    x_command_center_agent_token: Optional[str],
) -> TerminalSession:
    token = _extract_agent_token(authorization, x_command_center_agent_token)
    terminal_id = _agent_tokens.get(token)
    if not terminal_id:
        raise HTTPException(status_code=403, detail="Invalid Command Center agent token")
    session = _terminals.get(terminal_id)
    if session is None:
        raise HTTPException(status_code=403, detail="Terminal session is not active")
    return session


def _workspace_allowed_for_read(workspace: str) -> bool:
    return workspace in _configured_workspace_names()


def _require_readable_workspace(workspace: str) -> WorkspaceStore:
    if not _workspace_allowed_for_read(workspace):
        raise HTTPException(status_code=404, detail="Workspace not configured for Command Center agents")
    return _store(workspace)


def _agent_workspace_headers(
    authorization: Optional[str] = Header(default=None),
    x_command_center_agent_token: Optional[str] = Header(default=None),
) -> TerminalSession:
    return _terminal_from_agent_token(authorization, x_command_center_agent_token)


def _agent_workspace_event(event: dict[str, Any]) -> dict[str, Any]:
    item = _event_payload(event)
    payload = item.get("payload") or {}
    item["terminal_id"] = payload.get("terminal_id") or payload.get("terminal")
    item["agent_id"] = payload.get("agent") or payload.get("agent_id")
    item["summary"] = payload.get("summary") or payload.get("task") or payload.get("result") or ""
    return item


@app.get("/api/agent-workspace/workspaces")
async def agent_workspace_workspaces(
    authorization: Optional[str] = Header(default=None),
    x_command_center_agent_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    terminal = _terminal_from_agent_token(authorization, x_command_center_agent_token)
    active = terminal.active_workspace or _active_workspace()
    items: list[dict[str, Any]] = []
    for name in _configured_workspace_names():
        store = _store(name)
        meta = store.meta()
        items.append(
            {
                "name": name,
                "active": name == active,
                "readable": True,
                "agent_append_only": name == active,
                "node_count": len(store.list_all_nodes()),
                "edge_count": len(store.list_edges()),
                "updated_at": meta.get("updated_at"),
            }
        )
    return {"active_workspace": active, "terminal_id": terminal.terminal_id, "workspaces": items}


@app.get("/api/agent-workspace/{workspace}/nodes")
async def agent_workspace_nodes(
    workspace: str,
    query: str = Query(default=""),
    kind: str = Query(default=""),
    limit: int = Query(default=25, ge=1, le=100),
    authorization: Optional[str] = Header(default=None),
    x_command_center_agent_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _terminal_from_agent_token(authorization, x_command_center_agent_token)
    store = _require_readable_workspace(workspace)
    if query.strip():
        nodes = store.search_nodes(query.strip(), limit=limit, kinds=[kind] if kind else None, include_index=True)
    else:
        nodes = store.list_all_nodes()
        if kind:
            nodes = [node for node in nodes if node.get("kind") == kind]
        nodes = nodes[:limit]
    return {"workspace": workspace, "nodes": [_node_summary(node) for node in nodes]}


@app.get("/api/agent-workspace/{workspace}/nodes/{ref}")
async def agent_workspace_node(
    workspace: str,
    ref: str,
    authorization: Optional[str] = Header(default=None),
    x_command_center_agent_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _terminal_from_agent_token(authorization, x_command_center_agent_token)
    store = _require_readable_workspace(workspace)
    node = store.get_node(ref)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"workspace": workspace, "node": _node_detail(store, node), "rendered_markdown": store.render_node_markdown(node).strip()}


@app.get("/api/agent-workspace/{workspace}/events")
async def agent_workspace_events(
    workspace: str,
    limit: int = Query(default=50, ge=1, le=200),
    authorization: Optional[str] = Header(default=None),
    x_command_center_agent_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _terminal_from_agent_token(authorization, x_command_center_agent_token)
    store = _require_readable_workspace(workspace)
    return {"workspace": workspace, "events": [_agent_workspace_event(event) for event in store.list_events()[:limit]]}


@app.get("/api/agent-workspace/{workspace}/graph")
async def agent_workspace_graph(
    workspace: str,
    authorization: Optional[str] = Header(default=None),
    x_command_center_agent_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _terminal_from_agent_token(authorization, x_command_center_agent_token)
    store = _require_readable_workspace(workspace)
    nodes = [{"id": node["slug"], "label": node["title"], "kind": node["kind"]} for node in store.list_all_nodes()]
    edges = [{"source": edge["from_slug"], "target": edge["to_slug"], "rel": edge["edge_type"]} for edge in store.list_edges()]
    return {"workspace": workspace, "nodes": nodes, "edges": edges}


@app.post("/api/agent-workspace/plan")
async def agent_workspace_plan(
    payload: AgentWorkspacePlanPayload,
    authorization: Optional[str] = Header(default=None),
    x_command_center_agent_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    terminal = _terminal_from_agent_token(authorization, x_command_center_agent_token)
    workspace = terminal.active_workspace or _active_workspace()
    store = _store(workspace)
    store.ensure_agent_coordination_nodes()
    title = payload.title.strip()
    body = payload.body.strip()
    if not title or not body:
        raise HTTPException(status_code=400, detail="title and body are required")
    slug = _slugify(f"agent-plan-{terminal.terminal_id}-{int(time.time())}-{title}")[:96]
    node = store.upsert_node(
        slug=slug,
        title=title,
        kind="agent-plan",
        summary=payload.summary.strip() or body[:220],
        body=body,
        parent_ref="agent-team",
        aliases=[terminal.terminal_id, f"{terminal.terminal_id}-plan"],
        source_kind="agent-coordination",
        ensure_taxonomy=False,
    )
    event = store.record_agent_event(
        "agent_plan_submitted",
        agent_id=terminal.label or terminal.agent_type,
        task_id=payload.task_id or "",
        summary=title,
        details=body,
        node_ref=node["slug"],
        extra={"terminal_id": terminal.terminal_id, "agent_type": terminal.agent_type, "plan_slug": node["slug"]},
    )
    _terminal_synapse.setdefault(terminal.terminal_id, {})["last_plan"] = {
        "workspace": workspace,
        "slug": node["slug"],
        "title": node["title"],
        "created_at": event.get("recorded_at") or _now(),
    }
    return {"ok": True, "workspace": workspace, "terminal_id": terminal.terminal_id, "node": _node_detail(store, node), "event": event}


@app.post("/api/agent-workspace/log")
async def agent_workspace_log(
    payload: AgentWorkspaceLogPayload,
    authorization: Optional[str] = Header(default=None),
    x_command_center_agent_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    terminal = _terminal_from_agent_token(authorization, x_command_center_agent_token)
    workspace = terminal.active_workspace or _active_workspace()
    store = _store(workspace)
    summary = payload.summary.strip()
    if not summary:
        raise HTTPException(status_code=400, detail="summary is required")
    event = store.record_agent_event(
        "agent_log_entry",
        agent_id=terminal.label or terminal.agent_type,
        task_id=payload.task_id or "",
        summary=summary,
        details=payload.details.strip(),
        node_ref=payload.node_ref,
        extra={"terminal_id": terminal.terminal_id, "agent_type": terminal.agent_type},
    )
    sync: dict[str, Any] = {"changed": False}
    try:
        sync = store.sync_agent_coordination(max_events=200)
    except Exception as exc:
        sync = {"changed": False, "warning": f"agent-log sync skipped: {exc}"}
    _terminal_synapse.setdefault(terminal.terminal_id, {})["last_log"] = {
        "workspace": workspace,
        "summary": summary,
        "created_at": event.get("recorded_at") or _now(),
    }
    return {"ok": True, "workspace": workspace, "terminal_id": terminal.terminal_id, "event": event, "sync": sync}


@app.get("/api/agent-workspace/synapse")
async def agent_workspace_synapse() -> dict[str, Any]:
    cfg = _context_engine_config()
    active = str(cfg.get("workspace") or _active_workspace())
    store = _store(active) if active else None
    events = []
    agent_nodes = []
    if store:
        events = [_agent_workspace_event(event) for event in store.list_events()[:80]]
        agent_nodes = [
            _node_summary(node)
            for node in store.list_all_nodes()
            if node.get("kind") in {"agent-note", "agent-plan", "agent-log"}
        ][:80]
    return {
        "active_workspace": active,
        "readable_workspaces": _configured_workspace_names(),
        "terminal_synapse": _terminal_synapse,
        "recent_events": events,
        "agent_nodes": agent_nodes,
        "sandbox_available": bool(shutil.which("bwrap")),
    }


@app.post("/api/workspaces/{workspace}/export-markdown")
async def export_markdown(
    workspace: str,
    authorization: Optional[str] = Header(default=None),
    x_command_center_agent_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _reject_agent_token_capability(authorization, x_command_center_agent_token)
    return _store(workspace).sync_markdown_exports()


@app.post("/api/workspaces/{workspace}/clean-exports")
async def clean_exports(
    workspace: str,
    authorization: Optional[str] = Header(default=None),
    x_command_center_agent_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _reject_agent_token_capability(authorization, x_command_center_agent_token)
    store = _store(workspace)
    return {"verification": store.verify_db_completeness(), **store.clean_exports()}


@app.post("/api/workspaces/{workspace}/migrate-legacy")
async def migrate_legacy(
    workspace: str,
    authorization: Optional[str] = Header(default=None),
    x_command_center_agent_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _reject_agent_token_capability(authorization, x_command_center_agent_token)
    return {"manifest": _store(workspace).migrate_legacy_to_db(remove_legacy=True)}


@app.get("/api/workspaces/{workspace}/verify-db")
async def verify_db(workspace: str) -> dict[str, Any]:
    return _store(workspace).verify_db_completeness()


@app.get("/api/context-engine/config")
async def context_engine_config() -> dict[str, Any]:
    return _context_engine_config()


@app.put("/api/context-engine/config")
async def update_context_engine_config(
    body: dict[str, Any],
    authorization: Optional[str] = Header(default=None),
    x_command_center_agent_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _reject_agent_token_capability(authorization, x_command_center_agent_token)
    cfg = _read_config()
    plugin = cfg.setdefault("plugins", {}).setdefault("workspace-context", {})
    allowed = {"workspace", "inject_mode", "max_chars", "active_workspaces", "workspaces"}
    for key, value in body.items():
        if key in allowed:
            plugin[key] = value
    _write_config(cfg)
    return _context_engine_config()


@app.post("/api/context-engine/workspace/{name}/toggle-active")
async def toggle_active_workspace(
    name: str,
    authorization: Optional[str] = Header(default=None),
    x_command_center_agent_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _reject_agent_token_capability(authorization, x_command_center_agent_token)
    cfg = _read_config()
    plugin = cfg.setdefault("plugins", {}).setdefault("workspace-context", {})
    primary = str(plugin.get("workspace", "doyouwin"))
    current: list[str] = list(plugin.get("active_workspaces") or [primary])
    if name in current:
        current.remove(name)
    else:
        current.append(name)
    plugin["active_workspaces"] = current
    _write_config(cfg)
    return _context_engine_config()


@app.get("/api/context-engine/injected")
async def context_engine_injected() -> dict[str, Any]:
    cfg = _context_engine_config()
    workspace = cfg["workspace"]
    inject_mode = cfg["inject_mode"]

    if inject_mode == "all-indexes":
        names = list(cfg["workspaces"]) or sorted(p.name for p in list_workspaces(HERMES_HOME))
        if workspace not in names:
            names.insert(0, workspace)
    else:
        names = [workspace]

    nodes: list[dict[str, Any]] = []
    total = 0
    for name in names:
        try:
            store = _store(name)
        except Exception:
            continue
        index = store.get_index_node()
        if not index:
            continue
        content = store.render_node_markdown(index)
        if inject_mode == "all-indexes":
            content = f"# Workspace: {name}\n\n{content}"
        remaining = max(0, cfg["max_chars"] - total)
        if remaining <= 0:
            break
        content = content[:remaining]
        total += len(content)
        nodes.append({
            "workspace": name,
            "title": index["title"],
            "kind": index["kind"],
            "slug": index["slug"],
            "content": content,
            "chars": len(content),
        })

    grouped: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        grouped.setdefault(node["workspace"], []).append(node)
    total_chars = sum(node["chars"] for node in nodes)
    instruction = "Usa estos nodos como contexto DB-first de Hermes."
    return {
        **cfg,
        "instruction": instruction,
        "instruction_chars": len(instruction),
        "nodes_injected": nodes,
        "nodes_by_workspace": grouped,
        "total_chars": total_chars,
        "pct_used": round(total_chars / max(1, cfg["max_chars"]) * 100, 2),
    }


@app.get("/api/context-engine/prefetch-nodes")
async def context_engine_prefetch_nodes() -> dict[str, Any]:
    cfg = _context_engine_config()
    out: list[dict[str, Any]] = []
    for path in list_workspaces(HERMES_HOME):
        store = WorkspaceStore(path)
        for node in store.list_all_nodes():
            out.append({"workspace": path.name, "slug": node["slug"], "title": node["title"], "kind": node["kind"]})
    return {"workspace": cfg["workspace"], "inject_mode": cfg["inject_mode"], "nodes": out}


@app.get("/api/context-engine/prefetch")
async def context_engine_prefetch(q: str = Query("")) -> dict[str, Any]:
    cfg = _context_engine_config()
    results: list[dict[str, Any]] = []
    for path in list_workspaces(HERMES_HOME):
        store = WorkspaceStore(path)
        for node in store.search_nodes(q, limit=6, include_index=True):
            content = store.render_node_markdown(node)
            results.append(
                {
                    "workspace": path.name,
                    "slug": node["slug"],
                    "title": node["title"],
                    "kind": node["kind"],
                    "score": float(node.get("score", 0)),
                    "content": content[:4000],
                    "chars": min(len(content), 4000),
                }
            )
    return {"workspace": cfg["workspace"], "query": q, "results": results[:20]}


@app.get("/api/context-engine/skills")
async def context_engine_skills() -> dict[str, Any]:
    by_category: dict[str, list[dict[str, Any]]] = {}
    total = 0
    for root in (HERMES_HOME / "skills", HERMES_AGENT_ROOT / "skills"):
        if not root.exists():
            continue
        for skill in root.glob("*/*/SKILL.md"):
            category = skill.parent.parent.name
            name = skill.parent.name
            text = skill.read_text(encoding="utf-8", errors="ignore")
            description = ""
            for line in text.splitlines():
                if line.lower().startswith("description:"):
                    description = line.split(":", 1)[1].strip()
                    break
            by_category.setdefault(category, []).append(
                {"name": name, "category": category, "description": description, "path": str(skill), "tags": []}
            )
            total += 1
    return {"total": total, "by_category": by_category}


async def _control_rpc(
    method: str,
    params: dict[str, Any] | None = None,
    session_id: str | None = None,
    area_id: str | None = None,
    app_context: str | None = None,
) -> dict[str, Any]:
    try:
        return await _control.rpc(
            method,
            params or {},
            session_id=session_id,
            area_id=area_id,
            app_context=app_context,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.websocket("/api/control/ws")
async def control_ws(
    websocket: WebSocket,
    area_id: str = Query(default=DEFAULT_AGENT_AREA_ID),
    app_context: str = Query(default=""),
) -> None:
    await websocket.accept()
    queue = _control.add_client()
    sender: asyncio.Task | None = None
    area = _normalize_area_id(area_id)
    context = app_context.strip() or None

    async def _send_loop() -> None:
        while True:
            frame = await queue.get()
            await websocket.send_json(frame)

    try:
        await _control.start()
        sender = asyncio.create_task(_send_loop())
        await _control.ensure_session(area_id=area, app_context=context)
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue
            if msg.get("type") != "request":
                continue
            req_id = str(msg.get("id") or uuid.uuid4().hex)
            method = str(msg.get("method") or "")
            params = msg.get("params") or {}
            try:
                result = await _control.rpc(
                    method,
                    params if isinstance(params, dict) else {},
                    area_id=area,
                    app_context=context,
                )
                await websocket.send_json({"type": "response", "id": req_id, "ok": True, "result": result})
            except Exception as exc:
                await websocket.send_json({"type": "response", "id": req_id, "ok": False, "message": str(exc)})
    except WebSocketDisconnect:
        pass
    finally:
        if sender:
            sender.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sender
        _control.remove_client(queue)


@app.get("/api/agent/status")
async def agent_status() -> dict[str, Any]:
    state_path = HERMES_HOME / "gateway-runtime.json"
    state: dict[str, Any] = {}
    if state_path.exists():
        with contextlib.suppress(Exception):
            state = json.loads(state_path.read_text(encoding="utf-8"))
    return {
        "tui_gateway": {
            "running": _control.proc is not None and _control.proc.returncode is None,
            "session_id": _control.control_session_id,
            "sessions_by_area": {
                area: entry.get("session_id")
                for area, entry in _control.area_sessions.items()
            },
        },
        "gateway": {"running": bool(state.get("pid")), "pid": state.get("pid"), "state": state},
        "telegram": {"home_channel": None, "channels": {}},
        "platforms": state.get("platforms", {}),
    }


@app.get("/api/agent/sessions")
async def agent_sessions(area_id: str = Query(default=DEFAULT_AGENT_AREA_ID)) -> list[dict[str, Any]]:
    area = _normalize_area_id(area_id)
    sessions = await _control.list_sessions_cached(area)
    index = _load_area_session_index()
    current_id = _control.session_id_for_area(area)
    area_ids = set(index.get(area, set()))
    if current_id:
        area_ids.add(current_id)

    if area == DEFAULT_AGENT_AREA_ID:
        # Exclude sessions known to belong to other development areas.
        other_area_ids: set[str] = set()
        for other_area, ids in index.items():
            if other_area != DEFAULT_AGENT_AREA_ID:
                other_area_ids.update(ids)
        return [{**s, "area_id": area} for s in sessions if not (_session_ids_from_item(s) & other_area_ids)]

    # Non-default area: only expose sessions indexed to this area.
    if not area_ids:
        return []
    return [{**s, "area_id": area} for s in sessions if _session_ids_from_item(s) & area_ids]


@app.post("/api/agent/sessions")
async def create_agent_session(
    area_id: str = Query(default=DEFAULT_AGENT_AREA_ID),
    app_context: str = Query(default=""),
) -> dict[str, Any]:
    area = _normalize_area_id(area_id)
    context = app_context.strip()
    params: dict[str, Any] = {}
    if context:
        params["app_context"] = context
    params["area_id"] = area
    result = await _control_rpc("session.create", params)
    session_id = str(result.get("session_id") or result.get("session_key") or "")
    session_key = str(result.get("session_key") or "")
    if session_id:
        _control.area_sessions[area] = {
            "session_id": session_id,
            "app_context_hash": _app_context_hash(context),
        }
        _register_area_session(area, session_id, session_key)
        _control.invalidate_session_list_cache()
        _control.control_session_id = session_id
    return result


@app.post("/api/agent/sessions/resume")
async def resume_agent_session(
    payload: SessionResumePayload,
    area_id: str = Query(default=DEFAULT_AGENT_AREA_ID),
    app_context: str = Query(default=""),
) -> dict[str, Any]:
    area = _normalize_area_id(area_id)
    context = app_context.strip()
    indexed_area = _indexed_area_for_session(payload.session_key)
    if indexed_area and indexed_area != area:
        raise HTTPException(
            status_code=409,
            detail={
                "summary": "Session belongs to another development area",
                "session_key": payload.session_key,
                "requested_area": area,
                "session_area": indexed_area,
            },
        )
    params: dict[str, Any] = {"session_id": payload.session_key, "area_id": area}
    if context:
        params["app_context"] = context
    result = await _control_rpc("session.resume", params)
    session_id = str(result.get("session_id") or payload.session_key)
    session_key = str(result.get("session_key") or payload.session_key)
    _control.area_sessions[area] = {
        "session_id": session_id,
        "app_context_hash": _app_context_hash(context),
    }
    _register_area_session(area, session_id, session_key)
    _control.invalidate_session_list_cache()
    _control.control_session_id = session_id
    return result


@app.get("/api/agent/sessions/current")
async def current_agent_session(area_id: str = Query(default=DEFAULT_AGENT_AREA_ID)) -> dict[str, Any]:
    sid = await _control.ensure_session(area_id=area_id)
    history = await _control_rpc("session.history", {}, session_id=sid)
    usage = await _control_rpc("session.usage", {}, session_id=sid)
    return {"session_id": sid, "history": history.get("history", []), "usage": usage}


@app.post("/api/agent/sessions/{session_id}/interrupt")
async def interrupt_session(session_id: str) -> dict[str, Any]:
    await _control_rpc("session.interrupt", {}, session_id=session_id)
    return {"ok": True}


@app.post("/api/agent/sessions/{session_id}/undo")
async def undo_session(session_id: str) -> dict[str, Any]:
    await _control_rpc("session.undo", {}, session_id=session_id)
    return {"ok": True}


@app.post("/api/agent/sessions/{session_id}/compress")
async def compress_session(session_id: str) -> dict[str, Any]:
    await _control_rpc("session.compress", {}, session_id=session_id)
    return {"ok": True}


@app.get("/api/agent/sessions/{session_id}/usage")
async def session_usage(session_id: str) -> dict[str, Any]:
    return await _control_rpc("session.usage", {}, session_id=session_id)


@app.get("/api/agent/sessions/{session_id}/history")
async def session_history(session_id: str) -> dict[str, Any]:
    return await _control_rpc("session.history", {}, session_id=session_id)


@app.put("/api/agent/sessions/{session_id}/title")
async def session_title(session_id: str, payload: TitlePayload) -> dict[str, Any]:
    return await _control_rpc("session.title", {"title": payload.title}, session_id=session_id)


@app.post("/api/agent/sessions/{session_id}/branch")
async def session_branch(session_id: str, payload: BranchPayload) -> dict[str, Any]:
    return await _control_rpc("session.branch", {"name": payload.name}, session_id=session_id)


@app.get("/api/agent/commands")
async def agent_commands() -> list[dict[str, Any]]:
    result = await _control_rpc("commands.catalog", {})
    commands = result.get("commands") or result.get("items") or []
    return commands if isinstance(commands, list) else []


@app.get("/api/agent/commands/search")
async def agent_commands_search(q: str = Query("")) -> list[dict[str, Any]]:
    commands = await agent_commands()
    query = q.lower()
    return [cmd for cmd in commands if query in json.dumps(cmd).lower()]


@app.post("/api/agent/commands/execute")
async def execute_command(payload: CommandPayload) -> dict[str, Any]:
    return await _control_rpc("slash.exec", {"command": payload.command}, session_id=payload.session_id)


@app.get("/api/agent/models")
async def agent_models() -> dict[str, Any]:
    raw = await _control_rpc("model.options", {})
    # Gateway returns {providers:[{slug,name,is_current,models:[...],source,...}], model, provider}
    # Transform to flat {current, options:[{id,name,provider,is_current}]} for the frontend.
    current_model = raw.get("model") or ""
    options: list[dict[str, Any]] = []
    for prov in raw.get("providers", []):
        slug = prov.get("slug") or prov.get("name") or ""
        prov_name = prov.get("name") or slug
        for m in prov.get("models", []):
            mid = m if isinstance(m, str) else (m.get("id") or "")
            mname = mid if isinstance(m, str) else (m.get("name") or mid)
            if not mid:
                continue
            options.append({"id": mid, "name": mname, "provider": prov_name, "is_current": mid == current_model})
    return {"current": current_model, "options": options}


@app.post("/api/agent/model")
async def switch_model(
    payload: ModelPayload,
    area_id: str = Query(default=DEFAULT_AGENT_AREA_ID),
) -> dict[str, Any]:
    area = _normalize_area_id(area_id)
    session_id = _control.session_id_for_area(area)
    params: dict[str, Any] = {"key": "model", "value": payload.model}
    if session_id:
        params["session_id"] = session_id
    return await _control_rpc("config.set", params)


async def _get_raw_config(area_id: str | None = None) -> dict[str, Any]:
    """Read current model + reasoning effort from the gateway (two RPC calls)."""
    area = _normalize_area_id(area_id)
    session_id = _control.session_id_for_area(area)
    base_params: dict[str, Any] = {"session_id": session_id} if session_id else {}

    model_str = ""
    try:
        mo = await _control_rpc("model.options", {})
        model_str = mo.get("model") or ""
    except Exception:
        pass

    reasoning_effort = "medium"
    try:
        rd = await _control_rpc("config.get", {**base_params, "key": "reasoning"})
        reasoning_effort = str(rd.get("value") or "medium")
    except Exception:
        pass

    return {"model": model_str, "reasoning_effort": reasoning_effort}


@app.get("/api/agent/config")
async def agent_config(area_id: str = Query(default=DEFAULT_AGENT_AREA_ID)) -> dict[str, Any]:
    cfg = await _get_raw_config(area_id)
    return {
        "model": cfg.get("model", ""),
        "provider": "",
        "reasoning_effort": cfg.get("reasoning_effort", "medium"),
        "max_turns": 0,
        "streaming": True,
        "tool_progress": "auto",
        "personality": "default",
        "yolo": False,
        "plan_mode": False,
        "ask_before_edit": False,
        "auto_mode": False,
    }


@app.patch("/api/agent/config")
async def set_agent_config(
    payload: ConfigPatchPayload,
    area_id: str = Query(default=DEFAULT_AGENT_AREA_ID),
) -> dict[str, Any]:
    area = _normalize_area_id(area_id)
    session_id = _control.session_id_for_area(area)
    params: dict[str, Any] = {"key": payload.key, "value": payload.value}
    if session_id:
        params["session_id"] = session_id
    return await _control_rpc("config.set", params)


@app.get("/api/agent/reasoning")
async def agent_reasoning(area_id: str = Query(default=DEFAULT_AGENT_AREA_ID)) -> dict[str, Any]:
    cfg = await _get_raw_config(area_id)
    return {"effort": cfg.get("reasoning_effort", "medium"), "options": ["none", "minimal", "low", "medium", "high", "xhigh"]}


@app.post("/api/agent/reasoning")
async def set_reasoning(
    payload: ReasoningPayload,
    area_id: str = Query(default=DEFAULT_AGENT_AREA_ID),
) -> dict[str, Any]:
    area = _normalize_area_id(area_id)
    session_id = _control.session_id_for_area(area)
    params: dict[str, Any] = {"key": "reasoning", "value": payload.effort}
    if session_id:
        params["session_id"] = session_id
    return await _control_rpc("config.set", params)


@app.get("/api/agent/modes")
async def agent_modes(area_id: str = Query(default=DEFAULT_AGENT_AREA_ID)) -> dict[str, Any]:
    cfg = await _get_raw_config(area_id)
    return {
        "plan_mode": False,
        "auto_mode": False,
        "ask_before_edit": False,
        "yolo": False,
        "reasoning_effort": cfg.get("reasoning_effort", "medium"),
    }


@app.post("/api/agent/modes")
async def set_agent_modes(
    modes: dict[str, Any],
    area_id: str = Query(default=DEFAULT_AGENT_AREA_ID),
) -> dict[str, Any]:
    area = _normalize_area_id(area_id)
    session_id = _control.session_id_for_area(area)
    base_params: dict[str, Any] = {"session_id": session_id} if session_id else {}
    updated: dict[str, Any] = {}
    # Only reasoning_effort and yolo are supported by the gateway config API.
    if "reasoning_effort" in modes:
        effort = str(modes["reasoning_effort"])
        await _control_rpc("config.set", {**base_params, "key": "reasoning", "value": effort})
        updated["reasoning_effort"] = effort
    if "yolo" in modes:
        await _control_rpc("config.set", {**base_params, "key": "yolo"})
        updated["yolo"] = modes["yolo"]
    return {"updated": updated}


@app.get("/api/agent/tools")
async def agent_tools() -> dict[str, Any]:
    return await _control_rpc("tools.list", {})


@app.post("/api/agent/tools/{name}/toggle")
async def toggle_tool(name: str, payload: ToolTogglePayload) -> dict[str, Any]:
    return await _control_rpc("tools.configure", {"name": name, "enabled": payload.enabled})


@app.get("/api/agent/agents")
async def agent_agents() -> dict[str, Any]:
    return await _control_rpc("agents.list", {})


@app.delete("/api/agent/agents/{agent_id}")
async def stop_agent(agent_id: str) -> dict[str, Any]:
    return await _control_rpc("process.stop", {"agent_id": agent_id})


@app.get("/api/agent/approvals")
async def agent_approvals() -> list[dict[str, Any]]:
    return []


@app.post("/api/agent/approvals/{request_id}/approve")
async def approve_command(request_id: str) -> dict[str, Any]:
    return await _control_rpc("approval.respond", {"request_id": request_id, "choice": "approve"})


@app.post("/api/agent/approvals/{request_id}/deny")
async def deny_command(request_id: str) -> dict[str, Any]:
    return await _control_rpc("approval.respond", {"request_id": request_id, "choice": "deny"})


@app.get("/api/agent/file-edits")
async def file_edits(session_id: Optional[str] = None) -> list[dict[str, Any]]:
    return []


@app.delete("/api/agent/file-edits")
async def clear_file_edits() -> dict[str, Any]:
    return {"ok": True}


@app.get("/api/agent/file-edits/{edit_id}/diff")
async def file_edit_diff(edit_id: str) -> dict[str, Any]:
    raise HTTPException(status_code=404, detail="File edit not found")


@app.get("/api/agent/rollbacks")
async def agent_rollbacks() -> dict[str, Any]:
    return await _control_rpc("rollback.list", {})


@app.get("/api/agent/rollbacks/{rollback_id}/diff")
async def rollback_diff(rollback_id: str) -> dict[str, Any]:
    return await _control_rpc("rollback.diff", {"rollback_id": rollback_id})


@app.post("/api/agent/rollbacks/restore")
async def rollback_restore(payload: RollbackPayload) -> dict[str, Any]:
    return await _control_rpc("rollback.restore", {"rollback_id": payload.rollback_id})


@app.get("/api/agent/cron")
async def cron_jobs() -> dict[str, Any]:
    return await _control_rpc("cron.manage", {"action": "list"})


@app.post("/api/agent/cron")
async def create_cron(payload: CronPayload) -> dict[str, Any]:
    return await _control_rpc("cron.manage", {"action": "create", **payload.model_dump(exclude_none=True)})


@app.delete("/api/agent/cron/{job_id}")
async def delete_cron(job_id: str) -> dict[str, Any]:
    return await _control_rpc("cron.manage", {"action": "remove", "job_id": job_id})


@app.post("/api/agent/cron/{job_id}/pause")
async def pause_cron(job_id: str) -> dict[str, Any]:
    return await _control_rpc("cron.manage", {"action": "pause", "job_id": job_id})


@app.post("/api/agent/cron/{job_id}/resume")
async def resume_cron(job_id: str) -> dict[str, Any]:
    return await _control_rpc("cron.manage", {"action": "resume", "job_id": job_id})


@app.post("/api/agent/cron/{job_id}/run")
async def run_cron(job_id: str) -> dict[str, Any]:
    return await _control_rpc("cron.manage", {"action": "run", "job_id": job_id})


@app.get("/api/agent/usage")
async def agent_usage() -> dict[str, Any]:
    return await _control_rpc("session.usage", {})


@app.get("/api/agent/insights")
async def agent_insights(days: int = Query(7)) -> dict[str, Any]:
    return await _control_rpc("insights.get", {"days": days})


@app.get("/api/agent/personalities")
async def personalities() -> dict[str, Any]:
    return await _control_rpc("personality", {"action": "list"})


@app.post("/api/agent/personality")
async def set_personality(payload: PersonalityPayload) -> dict[str, Any]:
    return await _control_rpc("personality", {"action": "set", "name": payload.name})


@app.get("/api/agent/skills")
async def agent_skills() -> dict[str, Any]:
    return await _control_rpc("skills.manage", {"action": "list"})


@app.get("/api/agent/skills/{name}")
async def skill_detail(name: str) -> dict[str, Any]:
    for root in (HERMES_HOME / "skills", HERMES_AGENT_ROOT / "skills"):
        for skill in root.glob(f"*/*/SKILL.md") if root.exists() else []:
            if skill.parent.name == name:
                body = skill.read_text(encoding="utf-8", errors="ignore")
                return {
                    "name": name,
                    "category": skill.parent.parent.name,
                    "description": "",
                    "body": body,
                    "path": str(skill),
                    "metadata": {},
                }
    raise HTTPException(status_code=404, detail="Skill not found")


@app.post("/api/agent/skills/install")
async def install_skill(payload: SkillInstallPayload) -> dict[str, Any]:
    return await _control_rpc("skills.manage", {"action": "install", "name": payload.name, "category": payload.category})


@app.get("/api/terminals")
async def list_terminals() -> list[dict[str, Any]]:
    return [terminal.to_dict() for terminal in _terminals.values()]


@app.post("/api/terminals")
async def spawn_terminal(payload: SpawnTerminalPayload) -> dict[str, Any]:
    terminal_id = str(uuid.uuid4())[:8]
    agent_token = secrets.token_urlsafe(24)
    active_workspace = _active_workspace()
    base_command = _resolve_agent_command(payload.agent_type, payload.permission_mode)
    if payload.permission_mode == "bypass":
        command, sandboxed, sandbox_warning = base_command, False, ""
    else:
        command, sandboxed, sandbox_warning = _wrap_command_with_workspace_sandbox(base_command, payload.cwd)
    session = TerminalSession(
        terminal_id=terminal_id,
        agent_type=payload.agent_type,
        command=command,
        cwd=payload.cwd,
        cols=payload.cols,
        rows=payload.rows,
        label=payload.label,
        permission_mode=payload.permission_mode,
        agent_token=agent_token,
        active_workspace=active_workspace,
        sandboxed=sandboxed,
        sandbox_warning=sandbox_warning,
    )
    _terminals[terminal_id] = session
    _agent_tokens[agent_token] = terminal_id
    _terminal_synapse[terminal_id] = {
        "active_workspace": active_workspace,
        "sandboxed": sandboxed,
        "sandbox_warning": sandbox_warning,
        "created_at": session.created_at,
    }
    await session.start()
    if payload.prompt:
        prompt_text = _agent_protocol_prompt(payload.prompt, session)
        if payload.require_prompt_approval and _terminal_approval_settings["prompt_approval_required"]:
            approval = _create_terminal_approval(
                action="spawn_prompt",
                terminal=session,
                text=prompt_text,
                press_enter=True,
                requested_by="hermes",
            )
            result = session.to_dict()
            result["pending_approval"] = True
            result["approval_id"] = approval["id"]
            return result
        else:
            async def _inject_prompt() -> None:
                await asyncio.sleep(0.8)
                with contextlib.suppress(Exception):
                    await session.write((prompt_text + "\r").encode("utf-8"))

            asyncio.create_task(_inject_prompt())
    return session.to_dict()


@app.post("/api/terminals/{terminal_id}/inject")
async def inject_terminal(terminal_id: str, payload: InjectPayload) -> dict[str, Any]:
    session = _terminals.get(terminal_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Terminal not found")
    if payload.require_approval and _terminal_approval_settings["prompt_approval_required"]:
        approval = _create_terminal_approval(
            action="inject",
            terminal=session,
            text=payload.text,
            press_enter=payload.press_enter,
            requested_by=payload.requested_by,
        )
        return {
            "ok": True,
            "id": terminal_id,
            "injected": 0,
            "pending_approval": True,
            "approval_id": approval["id"],
        }
    text = payload.text + ("\r" if payload.press_enter else "")
    await session.write(text.encode("utf-8"))
    return {"ok": True, "id": terminal_id, "injected": len(text)}


@app.get("/api/terminals/approvals/settings")
async def terminal_approval_settings() -> dict[str, Any]:
    return dict(_terminal_approval_settings)


@app.post("/api/terminals/approvals/settings")
async def set_terminal_approval_settings(payload: TerminalApprovalSettingsPayload) -> dict[str, Any]:
    _terminal_approval_settings["prompt_approval_required"] = bool(payload.prompt_approval_required)
    return dict(_terminal_approval_settings)


@app.get("/api/terminals/approvals")
async def list_terminal_approvals() -> list[dict[str, Any]]:
    return _pending_terminal_approvals()


@app.post("/api/terminals/approvals/{approval_id}/approve")
async def approve_terminal_prompt(approval_id: str) -> dict[str, Any]:
    approval = _terminal_approvals.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.get("status") != "pending":
        return {"ok": True, "approval": approval, "injected": approval.get("injected", 0)}
    injected = await _apply_terminal_approval(approval)
    return {"ok": True, "approval": approval, "injected": injected}


@app.post("/api/terminals/approvals/{approval_id}/reject")
async def reject_terminal_prompt(approval_id: str) -> dict[str, Any]:
    approval = _terminal_approvals.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    approval["status"] = "rejected"
    approval["resolved_at"] = _now()
    return {"ok": True, "approval": approval}


@app.get("/api/terminals/{terminal_id}/output")
async def terminal_output(terminal_id: str, tail_bytes: int = Query(default=8192, le=65536)) -> dict[str, Any]:
    session = _terminals.get(terminal_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Terminal not found")
    raw = bytes(session._scrollback[-tail_bytes:]) if session._scrollback else b""
    clean = _ANSI_RE.sub(b"", raw).decode("utf-8", errors="replace")
    return {
        "terminal_id": terminal_id,
        "agent_type": session.agent_type,
        "alive": session.exit_code is None and session.fd is not None,
        "output": clean,
        "bytes": len(raw),
    }


@app.delete("/api/terminals/{terminal_id}")
async def kill_terminal(terminal_id: str) -> dict[str, Any]:
    session = _terminals.pop(terminal_id, None)
    if session is None:
        raise HTTPException(status_code=404, detail="Terminal not found")
    if session.agent_token:
        _agent_tokens.pop(session.agent_token, None)
    await session.kill()
    return {"ok": True, "id": terminal_id}


@app.websocket("/api/terminals/{terminal_id}/ws")
async def terminal_ws(websocket: WebSocket, terminal_id: str) -> None:
    session = _terminals.get(terminal_id)
    if session is None:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    queue = await session.add_client()
    await websocket.send_json({"t": "connected", "cols": session.cols, "rows": session.rows})

    async def _send_loop() -> None:
        while True:
            frame = await queue.get()
            await websocket.send_json(frame)

    sender = asyncio.create_task(_send_loop())
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("t") == "i":
                try:
                    data = base64.b64decode(msg.get("d", ""))
                except Exception:
                    data = str(msg.get("d", "") or "").encode("utf-8")
                await session.write(data)
            elif msg.get("t") == "r":
                await session.resize(int(msg.get("cols", session.cols)), int(msg.get("rows", session.rows)))
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sender
        session.remove_client(queue)


@app.get("/")
async def index() -> Any:
    path = FRONTEND_DIST / "index.html"
    if path.exists():
        return FileResponse(path)
    return JSONResponse({"ok": True, "service": "workspace-ui"})


@app.get("/{full_path:path}")
async def spa(full_path: str) -> Any:
    requested = FRONTEND_DIST / full_path
    if requested.exists() and requested.is_file():
        return FileResponse(requested)
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Not found")


if FRONTEND_DIST.exists():
    assets = FRONTEND_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8077")))
