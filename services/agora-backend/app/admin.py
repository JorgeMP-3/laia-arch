from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal
from urllib.error import URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .auth import public_user, require_roles
from .config import settings
from .models import Agent, Event, Role, User, new_id, now_iso
from .security import hash_password
from .storage import store


router = APIRouter(prefix="/api/admin", tags=["admin"])

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")
CONTAINER_RE = re.compile(r"^laia-[a-z0-9][a-z0-9-]{1,30}$|^laia-agora$")

_executor = ThreadPoolExecutor(max_workers=int(os.environ.get("AGORA_ADMIN_JOB_WORKERS", "2")))


class AdminProvisionUserRequest(BaseModel):
    slug: str = Field(min_length=2, max_length=32, pattern=r"^[a-z0-9][a-z0-9-]{1,30}$")
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    role: Role = "employee"
    password: str | None = Field(default=None, min_length=4, max_length=128)
    image_alias: str = Field(default="laia-agent", min_length=1, max_length=80)


class AdminContainerSnapshotRequest(BaseModel):
    name: str = Field(min_length=1, max_length=41, pattern=r"^[a-z0-9][a-z0-9-]{0,40}$")


class AdminJobResponse(BaseModel):
    job_id: str


def _run_command(args: list[str], *, timeout: int = 60, input_text: str | None = None) -> dict:
    env = os.environ.copy()
    env.setdefault("LAIA_ROOT", str(settings.laia_root))
    try:
        result = subprocess.run(
            args,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "command": args,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": f"command timed out after {timeout}s",
            "command": args,
        }
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "returncode": 127,
            "stdout": "",
            "stderr": str(exc),
            "command": args,
        }


def _append_job_log(log_path: str | None, message: str) -> None:
    if not log_path:
        return
    ts = datetime.now(timezone.utc).isoformat()
    try:
        with Path(log_path).open("a", encoding="utf-8") as fh:
            fh.write(f"[{ts}] {message.rstrip()}\n")
    except OSError:
        pass


def _tail_file(path: str | None, lines: int = 80) -> list[str]:
    if not path:
        return []
    p = Path(path)
    if not p.is_file():
        return []
    try:
        data = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return data[-max(1, min(lines, 1000)) :]


def _start_job(
    *,
    kind: str,
    actor: User,
    params: dict,
    fn: Callable[[dict, str], dict],
) -> str:
    job = store.create_admin_job(kind=kind, actor_id=actor.id, params=params)
    log_path = str(Path(tempfile.gettempdir()) / f"admin-job-{job['id']}.log")
    store.update_admin_job(job["id"], log_path=log_path)

    def runner() -> None:
        store.update_admin_job(job["id"], status="running", progress=5, mark_started=True)
        _append_job_log(log_path, f"job {kind} started")
        try:
            result = fn(params, log_path)
            store.update_admin_job(
                job["id"],
                status="done",
                result=result,
                progress=100,
                mark_finished=True,
            )
            _append_job_log(log_path, f"job {kind} done")
        except Exception as exc:
            store.update_admin_job(
                job["id"],
                status="failed",
                error=str(exc),
                progress=100,
                mark_finished=True,
            )
            _append_job_log(log_path, f"job {kind} failed: {exc}")

    if os.environ.get("AGORA_ADMIN_JOBS_INLINE") == "1":
        runner()
    else:
        _executor.submit(runner)
    return job["id"]


def _parse_lxc_csv(output: str) -> list[dict]:
    containers: list[dict] = []
    for row in csv.reader(output.splitlines()):
        if not row:
            continue
        name = row[0].strip()
        if not name.startswith("laia-"):
            continue
        containers.append({
            "name": name,
            "state": row[1].strip() if len(row) > 1 else "",
            "ipv4": row[2].strip() if len(row) > 2 else "",
            "type": row[3].strip() if len(row) > 3 else "",
            "snapshots": row[4].strip() if len(row) > 4 else "0",
        })
    return containers


def _list_lxc_containers() -> tuple[list[dict], str | None]:
    result = _run_command(["lxc", "list", "--format=csv", "-c", "ns4tS"], timeout=15)
    if not result["ok"]:
        return [], result["stderr"] or result["stdout"] or "lxc list failed"
    return _parse_lxc_csv(result["stdout"]), None


def _http_json(url: str, *, headers: dict[str, str] | None = None, timeout: float = 2.0) -> dict:
    req = UrlRequest(url, headers=headers or {})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except (OSError, URLError) as exc:
        return {"ok": False, "error": str(exc)}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "error": "non-json response", "raw": raw[:500]}
    if isinstance(data, dict):
        data.setdefault("ok", True)
        return data
    return {"ok": True, "data": data}


def _auth_snapshot() -> dict:
    try:
        from . import agent_pool
        status = agent_pool.auth_json_status
        path = agent_pool.auth_json_path or str(settings.data_dir / "auth.json")
    except Exception:
        status = "unknown"
        path = str(settings.data_dir / "auth.json")
    present = Path(path).is_file()
    if present and status in {"unknown", "missing"}:
        status = "linked"
    return {
        "ready": present or status == "linked",
        "status": status,
        "path": path,
        "present": present,
    }


def _backend_health_snapshot() -> dict:
    lxd = _run_command(["lxc", "version"], timeout=5)
    return {
        "ok": True,
        "service": "agora-backend",
        "version": "0.2.0",
        "env": settings.env,
        "data_dir": str(settings.data_dir),
        "db": "sqlite",
        "lxd_available": bool(lxd["ok"]),
        "laiactl_available": settings.laiactl_path.exists(),
        "auth": _auth_snapshot(),
        "default_llm_provider": os.environ.get("AGORA_DEFAULT_PROVIDER", "openai-codex"),
        "time": now_iso(),
    }


def _enrich_containers(containers: list[dict], *, include_health: bool = False) -> list[dict]:
    agents = store.agents()
    users_by_id = {u.id: u for u in store.all_users()}
    enriched = []
    for item in containers:
        row = dict(item)
        agent = next((a for a in agents if a.container_name == item["name"]), None)
        if agent:
            user = users_by_id.get(agent.user_id)
            row.update({
                "agent_id": agent.id,
                "user_id": agent.user_id,
                "username": user.username if user else None,
                "registered_status": agent.status,
                "container_ip": agent.container_ip,
            })
            if include_health and agent.container_ip:
                row["health"] = _http_json(f"http://{agent.container_ip}:9091/health", timeout=1.5)
                if agent.api_token:
                    row["profile"] = _http_json(
                        f"http://{agent.container_ip}:9091/profile",
                        headers={"Authorization": f"Bearer {agent.api_token}"},
                        timeout=1.5,
                    )
        else:
            row.update({
                "agent_id": None,
                "user_id": None,
                "username": None,
                "registered_status": None,
                "container_ip": None,
            })
            if include_health and item["name"] == "laia-agora":
                row["health"] = {"ok": True, "service": "agora-backend"}
        enriched.append(row)
    return enriched


def _recent_error_lines(limit: int = 20) -> list[str]:
    lines = _journal_lines("agora-backend", lines=300)[0]
    errors = [line for line in lines if "ERROR" in line or '"level": "ERROR"' in line]
    return errors[-limit:]


def _journal_lines(name: str, *, lines: int, since: str | None = None) -> tuple[list[str], str | None]:
    safe_lines = max(1, min(lines, 2000))
    args: list[str]
    if name in {"agora-backend", "laia-agora"}:
        args = ["journalctl", "-u", "agora-backend", "--no-pager", "-n", str(safe_lines)]
    else:
        container = _normalize_container_name(name)
        args = [
            "lxc",
            "exec",
            container,
            "--",
            "journalctl",
            "-u",
            "laia-executor",
            "--no-pager",
            "-n",
            str(safe_lines),
        ]
    if since:
        args.extend(["--since", since])
    result = _run_command(args, timeout=20)
    if result["ok"]:
        return result["stdout"].splitlines(), None
    if name in {"agora-backend", "laia-agora"}:
        fallback = _run_command(
            [
                "lxc",
                "exec",
                "laia-agora",
                "--",
                "journalctl",
                "-u",
                "agora-backend",
                "--no-pager",
                "-n",
                str(safe_lines),
            ],
            timeout=20,
        )
        if fallback["ok"]:
            return fallback["stdout"].splitlines(), None
    return [], result["stderr"] or result["stdout"] or "journalctl failed"


def _normalize_container_name(name: str) -> str:
    container = name if name.startswith("laia-") else f"laia-{name}"
    if not CONTAINER_RE.fullmatch(container):
        raise HTTPException(status_code=422, detail="invalid container name")
    return container


def _audit_log_paths() -> list[Path]:
    configured = os.environ.get("AGORA_ADMIN_LOG_PATHS", "")
    raw = [p for p in configured.split(":") if p] if configured else []
    raw.extend([
        "/tmp/agora-backend-chat.log",
        "/tmp/agora-backend.log",
        "/var/log/agora-backend.log",
    ])
    seen: set[str] = set()
    paths: list[Path] = []
    for item in raw:
        if item in seen:
            continue
        seen.add(item)
        paths.append(Path(item))
    return paths


def _parse_audit_line(line: str) -> dict | None:
    text = line.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        if "tool_call" not in text and "tool_forward" not in text:
            return None
        return {"raw": text}
    logger = str(payload.get("logger", ""))
    msg = str(payload.get("msg", ""))
    if payload.get("event") != "tool_call" and "tool_call" not in msg and "tool_forward" not in msg and not logger.startswith("agora.forwarder"):
        return None
    return payload


def _audit_events(*, user_id: str | None, from_ts: str | None, to_ts: str | None, limit: int) -> list[dict]:
    events: list[dict] = []
    for path in _audit_log_paths():
        for line in _tail_file(str(path), lines=2000):
            event = _parse_audit_line(line)
            if event is not None:
                events.append(event)
    if not events:
        lines, _ = _journal_lines("agora-backend", lines=2000)
        for line in lines:
            event = _parse_audit_line(line)
            if event is not None:
                events.append(event)

    def in_range(event: dict) -> bool:
        if user_id and event.get("user_id") != user_id:
            return False
        ts = event.get("ts")
        if isinstance(ts, str):
            if from_ts and ts < from_ts:
                return False
            if to_ts and ts > to_ts:
                return False
        return True

    return [e for e in events if in_range(e)][-max(1, min(limit, 500)) :]


def _extract_last_json_line(output: str) -> dict:
    for line in reversed(output.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    raise RuntimeError("command did not emit a JSON object")


def _create_or_reactivate_user(payload: dict, actor_id: str) -> tuple[User, str | None]:
    slug = payload["slug"]
    display_name = payload.get("display_name") or slug
    role = payload.get("role") or "employee"
    password = payload.get("password") or f"laia-{now_iso()[:19]}"
    hashed = hash_password(password)
    default_provider = os.environ.get("AGORA_DEFAULT_PROVIDER", "openai-codex")
    default_model = os.environ.get("AGORA_DEFAULT_MODEL", "gpt-5.5")
    default_api_mode = os.environ.get("AGORA_DEFAULT_API_MODE") or None

    existing = store.user_by_username(slug)
    if existing:
        if existing.active and existing.agent_id:
            raise RuntimeError(f"user {slug!r} already has an agent")
        existing.active = True
        existing.display_name = display_name
        existing.role = role
        existing.password = hashed
        existing.llm_provider = default_provider or None
        existing.llm_model = default_model or None
        existing.llm_api_mode = default_api_mode
        existing.llm_api_key = None
        existing.llm_base_url = None
        existing.llm_extras_json = None
        existing.token = None
        existing.agent_id = None
        store.save_user(existing)
        store.record_event(Event(
            event_type="admin_user_reactivated",
            actor_id=actor_id,
            summary=slug,
            payload={"user_id": existing.id},
        ))
        return existing, password if not payload.get("password") else None

    user = User(
        id=f"user_{slug}",
        username=slug,
        display_name=display_name,
        role=role,
        token=None,
        password=hashed,
        active=True,
        llm_provider=default_provider or None,
        llm_model=default_model or None,
        llm_api_mode=default_api_mode,
    )
    store.save_user(user)
    store.record_event(Event(
        event_type="admin_user_created",
        actor_id=actor_id,
        summary=slug,
        payload={"user_id": user.id},
    ))
    return user, password if not payload.get("password") else None


def _register_agent_for_user(slug: str, user: User, provision: dict, actor_id: str) -> Agent:
    agent = Agent(
        id=new_id("agent"),
        user_id=user.id,
        container_name=f"laia-{slug}",
        status="running",
        workspace_path="/opt/laia/workspaces/personal/workspace.db",
        container_ip=provision.get("ipv4") or provision.get("container_ip"),
        api_token=provision.get("api_token"),
    )
    if not agent.container_ip or not agent.api_token:
        raise RuntimeError("provision output missing ipv4/api_token")
    store.save_agent(agent)
    user.agent_id = agent.id
    store.save_user(user)
    store.record_event(Event(
        event_type="admin_agent_registered",
        actor_id=actor_id,
        summary=slug,
        payload={"agent_id": agent.id, "user_id": user.id, "ip": agent.container_ip},
    ))
    return agent


def _provision_user_job(actor_id: str) -> Callable[[dict, str], dict]:
    def run(params: dict, log_path: str) -> dict:
        slug = params["slug"]
        script = settings.laia_root / "infra" / "lxd" / "scripts" / "create-agent.sh"
        existing = store.user_by_username(slug)
        provision: dict | None = None
        user: User | None = None
        _append_job_log(log_path, f"provisioning container laia-{slug}")
        try:
            result = _run_command([str(script), slug, params.get("image_alias", "laia-agent")], timeout=900)
            _append_job_log(log_path, result["stdout"])
            if result["stderr"]:
                _append_job_log(log_path, result["stderr"])
            if not result["ok"]:
                raise RuntimeError(result["stderr"] or result["stdout"] or "create-agent failed")
            provision = _extract_last_json_line(result["stdout"])
            _append_job_log(log_path, f"creating user {slug}")
            user, generated_password = _create_or_reactivate_user(params, actor_id)
            agent = _register_agent_for_user(slug, user, provision, actor_id)
            return {
                "user": public_user(user).model_dump(),
                "agent": agent.model_dump(),
                "password": generated_password,
            }
        except Exception:
            if provision is not None:
                cleanup = _run_command(["lxc", "delete", "--force", f"laia-{slug}"], timeout=120)
                if not cleanup["ok"]:
                    _append_job_log(log_path, cleanup["stderr"] or cleanup["stdout"])
            if user is not None and (existing is None or not existing.active):
                store.disable_user(user.id)
            raise
    return run


def _delete_user_job(actor_id: str) -> Callable[[dict, str], dict]:
    def run(params: dict, log_path: str) -> dict:
        slug = params["slug"]
        user = store.user_by_username(slug)
        if not user:
            raise RuntimeError(f"user not found: {slug}")
        store.disable_user(user.id)
        _append_job_log(log_path, f"disabled user {slug}")
        result = _run_command(["lxc", "delete", "--force", f"laia-{slug}"], timeout=120)
        if not result["ok"]:
            _append_job_log(log_path, result["stderr"] or result["stdout"])
        user_dir = Path(os.environ.get("AGORA_ADMIN_USERS_ROOT", "/srv/laia/users")) / slug
        rm_result = _run_command(["rm", "-rf", str(user_dir)], timeout=60)
        if not rm_result["ok"]:
            _append_job_log(log_path, rm_result["stderr"] or rm_result["stdout"])
        store.record_event(Event(
            event_type="admin_user_deleted",
            actor_id=actor_id,
            summary=slug,
            payload={
                "user_id": user.id,
                "container_deleted": result["ok"],
                "bind_mount_removed": rm_result["ok"],
            },
        ))
        return {
            "ok": result["ok"] and rm_result["ok"],
            "container": {"output": result["stdout"], "error": result["stderr"]},
            "bind_mount": {"path": str(user_dir), "output": rm_result["stdout"], "error": rm_result["stderr"]},
        }
    return run


def _rebuild_user_job(actor_id: str) -> Callable[[dict, str], dict]:
    def run(params: dict, log_path: str) -> dict:
        slug = params["slug"]
        user = store.user_by_username(slug)
        if not user or not user.active:
            raise RuntimeError(f"user not found: {slug}")
        _append_job_log(log_path, f"deleting old container laia-{slug}")
        delete_result = _run_command(["lxc", "delete", "--force", f"laia-{slug}"], timeout=120)
        if not delete_result["ok"]:
            _append_job_log(log_path, delete_result["stderr"] or delete_result["stdout"])
        script = settings.laia_root / "infra" / "lxd" / "scripts" / "create-agent.sh"
        _append_job_log(log_path, f"recreating container laia-{slug}")
        create_result = _run_command([str(script), slug, params.get("image_alias", "laia-agent")], timeout=900)
        _append_job_log(log_path, create_result["stdout"])
        if create_result["stderr"]:
            _append_job_log(log_path, create_result["stderr"])
        if not create_result["ok"]:
            raise RuntimeError(create_result["stderr"] or create_result["stdout"] or "create-agent failed")
        provision = _extract_last_json_line(create_result["stdout"])
        for agent in store.agents():
            if agent.user_id == user.id or agent.id == user.agent_id or agent.container_name == f"laia-{slug}":
                agent.status = "running"
                agent.container_ip = provision.get("ipv4") or provision.get("container_ip")
                agent.api_token = provision.get("api_token")
                store.save_agent(agent)
                user.agent_id = agent.id
                store.save_user(user)
                return {"ok": True, "user_id": user.id, "agent": agent.model_dump()}
        agent = _register_agent_for_user(slug, user, provision, actor_id)
        return {"ok": True, "user_id": user.id, "agent": agent.model_dump()}
    return run


def _container_command_job(action: Literal["restart", "snapshot", "restore"], actor_id: str) -> Callable[[dict, str], dict]:
    def run(params: dict, log_path: str) -> dict:
        container = _normalize_container_name(params["container"])
        if action == "restart":
            args = ["lxc", "restart", container]
        elif action == "snapshot":
            args = ["lxc", "snapshot", container, params["snapshot"]]
        else:
            args = ["lxc", "restore", container, params["snapshot"]]
        _append_job_log(log_path, " ".join(args))
        result = _run_command(args, timeout=180)
        if not result["ok"]:
            raise RuntimeError(result["stderr"] or result["stdout"] or f"{action} failed")
        store.record_event(Event(
            event_type=f"admin_container_{action}",
            actor_id=actor_id,
            summary=container,
            payload={"snapshot": params.get("snapshot")},
        ))
        return {"ok": True, "output": result["stdout"], "error": result["stderr"]}
    return run


@router.get("/jobs")
def list_admin_jobs(
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(require_roles("agora_admin")),
):
    return {"jobs": store.admin_jobs(status=status, limit=limit)}


@router.get("/jobs/{job_id}")
def get_admin_job(job_id: str, _: User = Depends(require_roles("agora_admin"))):
    job = store.admin_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    job["log_tail"] = _tail_file(job.get("log_path"), lines=80)
    return {"job": job}


@router.get("/status")
def admin_status(_: User = Depends(require_roles("agora_admin"))):
    containers, container_error = _list_lxc_containers()
    enriched = _enrich_containers(containers, include_health=True)
    users = store.users()
    agents = store.agents()
    return {
        "status": {
            "ok": True,
            "health": _backend_health_snapshot(),
            "containers": {
                "total": len(enriched),
                "running": sum(1 for c in enriched if c.get("state") == "RUNNING"),
                "items": enriched,
                "error": container_error,
            },
            "users": {
                "total": len(users),
                "active": sum(1 for u in users if u.active),
            },
            "agents": {
                "registered": len(agents),
                "running": sum(1 for a in agents if a.status == "running"),
            },
            "auth": _auth_snapshot(),
            "tests": {
                "status": "unknown",
                "last_run": None,
            },
            "recent_errors": _recent_error_lines(),
        }
    }


@router.get("/containers")
def admin_containers(_: User = Depends(require_roles("agora_admin"))):
    containers, error = _list_lxc_containers()
    return {"containers": _enrich_containers(containers), "error": error}


@router.get("/logs/{name}")
def admin_logs(
    name: str,
    lines: int = Query(default=100, ge=1, le=2000),
    since: str | None = None,
    _: User = Depends(require_roles("agora_admin")),
):
    output, error = _journal_lines(name, lines=lines, since=since)
    return {
        "logs": {
            "name": name,
            "ok": error is None,
            "source": "journalctl",
            "lines": output,
            "error": error,
        }
    }


@router.get("/audit/tools")
def admin_tool_audit(
    user_id: str | None = None,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(require_roles("agora_admin")),
):
    return {"tool_calls": _audit_events(user_id=user_id, from_ts=from_, to_ts=to, limit=limit)}


@router.post("/system/refresh-oauth")
def refresh_oauth(actor: User = Depends(require_roles("agora_admin"))):
    host_auth = Path(
        os.environ.get("AGORA_ADMIN_HOST_AUTH_JSON")
        or os.environ.get("AGORA_ARCH_AUTH_JSON")
        or str(Path.home() / ".laia" / "auth.json")
    )
    if not host_auth.is_file():
        raise HTTPException(status_code=404, detail=f"auth.json not found: {host_auth}")
    container = os.environ.get("AGORA_ADMIN_AUTH_CONTAINER", "laia-agora")
    target = os.environ.get("AGORA_ADMIN_AUTH_TARGET", "/opt/agora/data/auth.json")
    result = _run_command(
        [
            "lxc",
            "file",
            "push",
            str(host_auth),
            f"{container}{target}",
            "--uid",
            os.environ.get("AGORA_ADMIN_AUTH_UID", "999"),
            "--gid",
            os.environ.get("AGORA_ADMIN_AUTH_GID", "988"),
            "--mode",
            os.environ.get("AGORA_ADMIN_AUTH_MODE", "644"),
        ],
        timeout=30,
    )
    store.record_event(Event(
        event_type="admin_refresh_oauth",
        actor_id=actor.id,
        summary=container,
        payload={"ok": result["ok"], "target": target},
    ))
    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result["stderr"] or result["stdout"])
    return {"ok": True, "result": {"target": f"{container}{target}", "output": result["stdout"]}}


@router.post("/users/provision", response_model=AdminJobResponse, status_code=202)
def provision_user(payload: AdminProvisionUserRequest, actor: User = Depends(require_roles("agora_admin"))):
    params = payload.model_dump()
    job_id = _start_job(
        kind="provision-user",
        actor=actor,
        params=params,
        fn=_provision_user_job(actor.id),
    )
    return AdminJobResponse(job_id=job_id)


@router.get("/users")
def admin_users(_: User = Depends(require_roles("agora_admin"))):
    containers, _ = _list_lxc_containers()
    containers_by_name = {c["name"]: c for c in containers}
    agents = store.agents()
    rows = []
    for user in store.users():
        agent = next((a for a in agents if a.user_id == user.id or a.id == user.agent_id), None)
        container = containers_by_name.get(agent.container_name if agent else "")
        last_chat = None
        for event in reversed(store.events()):
            if event.actor_id == user.id and event.event_type.startswith("chat"):
                last_chat = event.created_at
                break
        row = public_user(user).model_dump()
        row.update({
            "agent_id": agent.id if agent else None,
            "container_name": agent.container_name if agent else None,
            "container_state": container.get("state") if container else "unknown",
            "container_ip": (container.get("ipv4") if container else None) or (agent.container_ip if agent else None),
            "llm_provider": user.llm_provider,
            "last_chat": last_chat,
        })
        rows.append(row)
    return {"users": rows}


@router.delete("/users/{slug}", response_model=AdminJobResponse, status_code=202)
def delete_admin_user(slug: str, actor: User = Depends(require_roles("agora_admin"))):
    if not SLUG_RE.fullmatch(slug):
        raise HTTPException(status_code=422, detail="invalid slug")
    if slug == actor.username:
        raise HTTPException(status_code=400, detail="cannot delete yourself")
    job_id = _start_job(
        kind="delete-user",
        actor=actor,
        params={"slug": slug},
        fn=_delete_user_job(actor.id),
    )
    return AdminJobResponse(job_id=job_id)


@router.post("/users/{slug}/rebuild", response_model=AdminJobResponse, status_code=202)
def rebuild_admin_user(
    slug: str,
    image_alias: str = "laia-agent",
    actor: User = Depends(require_roles("agora_admin")),
):
    if not SLUG_RE.fullmatch(slug):
        raise HTTPException(status_code=422, detail="invalid slug")
    job_id = _start_job(
        kind="rebuild-user",
        actor=actor,
        params={"slug": slug, "image_alias": image_alias},
        fn=_rebuild_user_job(actor.id),
    )
    return AdminJobResponse(job_id=job_id)


@router.post("/containers/{name}/restart", response_model=AdminJobResponse, status_code=202)
def restart_container(name: str, actor: User = Depends(require_roles("agora_admin"))):
    container = _normalize_container_name(name)
    job_id = _start_job(
        kind="container-restart",
        actor=actor,
        params={"container": container},
        fn=_container_command_job("restart", actor.id),
    )
    return AdminJobResponse(job_id=job_id)


@router.post("/containers/{name}/snapshot", response_model=AdminJobResponse, status_code=202)
def snapshot_container(
    name: str,
    payload: AdminContainerSnapshotRequest,
    actor: User = Depends(require_roles("agora_admin")),
):
    container = _normalize_container_name(name)
    job_id = _start_job(
        kind="container-snapshot",
        actor=actor,
        params={"container": container, "snapshot": payload.name},
        fn=_container_command_job("snapshot", actor.id),
    )
    return AdminJobResponse(job_id=job_id)


@router.post("/containers/{name}/restore", response_model=AdminJobResponse, status_code=202)
def restore_container(
    name: str,
    payload: AdminContainerSnapshotRequest,
    actor: User = Depends(require_roles("agora_admin")),
):
    container = _normalize_container_name(name)
    job_id = _start_job(
        kind="container-restore",
        actor=actor,
        params={"container": container, "snapshot": payload.name},
        fn=_container_command_job("restore", actor.id),
    )
    return AdminJobResponse(job_id=job_id)


@router.post("/system/restart-backend", response_model=AdminJobResponse, status_code=202)
def restart_backend(actor: User = Depends(require_roles("agora_admin"))):
    def run(_params: dict, log_path: str) -> dict:
        args = ["lxc", "exec", "laia-agora", "--", "systemctl", "restart", "agora-backend"]
        _append_job_log(log_path, " ".join(args))
        result = _run_command(args, timeout=60)
        if not result["ok"]:
            raise RuntimeError(result["stderr"] or result["stdout"] or "restart failed")
        return {"ok": True, "output": result["stdout"], "error": result["stderr"]}

    job_id = _start_job(kind="restart-backend", actor=actor, params={}, fn=run)
    return AdminJobResponse(job_id=job_id)
