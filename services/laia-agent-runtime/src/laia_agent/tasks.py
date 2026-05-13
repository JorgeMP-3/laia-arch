from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path
from typing import Any

from .config import AgentConfig
from .profile import ensure_profile, get_profile, set_skill, update_profile
from .status import read_json, utc_now, write_json
from .workspace import get_node, init_workspace, list_nodes, search_nodes, upsert_node


class TaskError(RuntimeError):
    pass


def ensure_task_dirs(config: AgentConfig) -> None:
    for name in ("inbox", "done", "failed"):
        (config.data_dir / "tasks" / name).mkdir(parents=True, exist_ok=True)


def process_once(config: AgentConfig) -> int:
    ensure_task_dirs(config)
    count = 0
    inbox = config.data_dir / "tasks" / "inbox"
    for task_path in sorted(inbox.glob("*.json")):
        count += 1
        _process_task(config, task_path)
    return count


def _process_task(config: AgentConfig, task_path: Path) -> None:
    started = utc_now()
    task = read_json(task_path)
    task_id = str(task.get("id") or task_path.stem)
    try:
        result = execute_task(config, task)
        payload = {
            "id": task_id,
            "status": "done",
            "started_at": started,
            "finished_at": utc_now(),
            "task": task,
            "result": result,
        }
        target = config.data_dir / "tasks" / "done" / f"{task_id}.json"
        write_json(target, payload)
        task_path.unlink()
    except Exception as exc:
        payload = {
            "id": task_id,
            "status": "failed",
            "started_at": started,
            "finished_at": utc_now(),
            "task": task,
            "error": str(exc),
        }
        target = config.data_dir / "tasks" / "failed" / f"{task_id}.json"
        write_json(target, payload)
        task_path.unlink()


def execute_task(config: AgentConfig, task: dict[str, Any]) -> dict[str, Any]:
    kind = str(task.get("type", ""))
    if kind == "ping":
        return {"pong": True, "time": utc_now()}
    if kind == "write_file":
        return _write_file(config, task)
    if kind == "read_file":
        return _read_file(config, task)
    if kind == "workspace_init":
        return init_workspace(config)
    if kind == "workspace_upsert_node":
        return upsert_node(config, dict(task.get("node") or task))
    if kind == "workspace_get_node":
        return {"node": get_node(config, task.get("ref", ""))}
    if kind == "workspace_list_nodes":
        return {"nodes": list_nodes(config, int(task.get("limit", 50)))}
    if kind == "workspace_search":
        return {"nodes": search_nodes(config, str(task.get("query", "")), int(task.get("limit", 8)))}
    if kind == "profile_init":
        return ensure_profile(config)
    if kind == "profile_get":
        return get_profile(config)
    if kind == "profile_update":
        return update_profile(config, dict(task.get("profile") or task))
    if kind == "skill_enable":
        return set_skill(config, str(task.get("skill_id", "")), True)
    if kind == "skill_disable":
        return set_skill(config, str(task.get("skill_id", "")), False)
    raise TaskError(f"Unsupported task type: {kind}")


def _safe_workspace_path(config: AgentConfig, relative: str) -> Path:
    if not relative or relative.startswith("/"):
        raise TaskError("Path must be relative to the personal workspace directory")
    base = config.workspace_dir.resolve()
    target = (base / relative).resolve()
    if base != target and base not in target.parents:
        raise TaskError("Path escapes the personal workspace directory")
    return target


def _write_file(config: AgentConfig, task: dict[str, Any]) -> dict[str, Any]:
    target = _safe_workspace_path(config, str(task.get("path", "")))
    encoding = str(task.get("encoding", "text"))
    target.parent.mkdir(parents=True, exist_ok=True)
    if encoding == "base64":
        target.write_bytes(base64.b64decode(str(task.get("content", ""))))
    else:
        target.write_text(str(task.get("content", "")), encoding="utf-8")
    return {"path": str(target), "bytes": target.stat().st_size}


def _read_file(config: AgentConfig, task: dict[str, Any]) -> dict[str, Any]:
    target = _safe_workspace_path(config, str(task.get("path", "")))
    if not target.exists():
        raise TaskError(f"File not found: {target}")
    if target.is_dir():
        raise TaskError(f"Path is a directory: {target}")
    max_bytes = int(task.get("max_bytes", 262144))
    data = target.read_bytes()
    truncated = len(data) > max_bytes
    data = data[:max_bytes]
    try:
        content = data.decode("utf-8")
        encoding = "text"
    except UnicodeDecodeError:
        content = base64.b64encode(data).decode("ascii")
        encoding = "base64"
    return {"path": str(target), "encoding": encoding, "content": content, "truncated": truncated}


def clear_inbox(config: AgentConfig) -> None:
    inbox = config.data_dir / "tasks" / "inbox"
    if inbox.exists():
        shutil.rmtree(inbox)
    ensure_task_dirs(config)
