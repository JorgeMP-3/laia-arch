from __future__ import annotations

import csv
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal
from urllib.error import URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .atlas_paths import resolved_path
from .auth import public_user, require_roles
from .agent_identity import (
    canonical_container_name,
    candidate_container_names,
    is_user_agent_container,
    legacy_container_name,
    normalize_container_name,
)
from .config import settings
from .health import auth_json_snapshot
from .models import Agent, Event, Role, User, new_id, now_iso
from .security import hash_password
from .storage import store


# Structured logger for every admin action. Goes through agora-backend's
# JSON formatter (logging.py) so each call leaves a trail with actor /
# action / outcome that operators can grep without parsing audit.log
# separately. The category is ``agora.admin`` so `journalctl -u
# agora-backend | grep agora.admin` filters to admin activity only.
logger = logging.getLogger("agora.admin")


router = APIRouter(prefix="/api/admin", tags=["admin"])

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")
CONTAINER_RE = re.compile(r"^(agent|laia)-[a-z0-9][a-z0-9_-]{1,40}$|^laia-agora$")

# Whitelist of LXD image aliases the admin endpoints may pass to
# create-agent.sh / lxc launch. ``laia-agent`` is the only image the
# rebuild scripts produce today; if you add more (e.g. an `arm-gpu`
# variant) include them here, otherwise the request gets rejected with
# 422 so an injected payload can't trick the script into pulling a
# random alias. Override via env for dev experiments.
_ALLOWED_IMAGE_ALIASES: frozenset[str] = frozenset(
    item.strip()
    for item in os.environ.get("AGORA_ADMIN_ALLOWED_IMAGES", "laia-agent").split(",")
    if item.strip()
)


_executor = ThreadPoolExecutor(max_workers=int(os.environ.get("AGORA_ADMIN_JOB_WORKERS", "2")))


# ──────────────────────────────────────────────────────────────────────────
# Rate limiter — separate bucket from the login rate limiter
# (security.should_rate_limit) so a noisy admin doesn't trip the login
# protection and vice-versa. Bucket key is the actor.id, max 30 mutating
# admin calls per minute by default. Read-only endpoints (status, logs,
# audit) are intentionally NOT rate-limited so the TUI can poll freely.
# ──────────────────────────────────────────────────────────────────────────


_admin_rate_lock = threading.RLock()
_admin_rate_buckets: dict[str, list[float]] = {}


def _admin_rate_window_seconds() -> int:
    try:
        return max(5, int(os.environ.get("AGORA_ADMIN_RATE_WINDOW_SECONDS", "60")))
    except ValueError:
        return 60


def _admin_rate_max_per_window() -> int:
    try:
        return max(1, int(os.environ.get("AGORA_ADMIN_RATE_MAX", "30")))
    except ValueError:
        return 30


def _admin_rate_limit(actor_id: str) -> None:
    """Raise 429 if ``actor_id`` has spent its mutate budget for the window.

    Sliding window: keep timestamps of the last calls, drop the ones older
    than ``window_seconds``. Cheap (lock + list filter) and good enough for
    a single-process backend; if AGORA ever scales horizontally swap for
    Redis.
    """
    if not actor_id:
        return
    now = time.monotonic()
    window = _admin_rate_window_seconds()
    limit = _admin_rate_max_per_window()
    with _admin_rate_lock:
        bucket = _admin_rate_buckets.setdefault(actor_id, [])
        cutoff = now - window
        bucket[:] = [t for t in bucket if t >= cutoff]
        if len(bucket) >= limit:
            retry_after = max(1, int(window - (now - bucket[0])))
            raise HTTPException(
                status_code=429,
                detail=f"admin rate limit: {limit} mutating actions per {window}s. retry in {retry_after}s",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)


def _warn_host_op_via_agora_admin(actor: User, action: str) -> None:
    """Emit a WARN audit event when ``actor`` triggers a host-LXD action.

    Rule ⑥ of the Definitive Document: AGORA admin does NOT manage
    infrastructure (LXD, systemd, host filesystem). Those endpoints
    are LAIA-ARCH territory and should require the ``host_admin`` role.
    They are still accepted with ``agora_admin`` for backwards compatibility —
    flipping the role-check would break Jorge's workflow without the associated
    migration (assigning the ``host_admin`` role to his ``users`` row).

    This function leaves an observable trail whenever a host
    operation is performed via ``agora_admin``, without blocking. Once the
    migration is done (Jorge marked as ``host_admin``), change
    ``require_roles("agora_admin")`` to ``require_roles("host_admin")`` in
    the 5 affected endpoints and remove this helper.
    """
    if getattr(actor, "role", None) == "host_admin":
        return  # caller is the right role, nothing to log.
    try:
        ev = Event(
            id=new_id("evt"),
            event_type="rule_6_host_op_via_agora_admin",
            actor_id=actor.id,
            summary=f"host op {action!r} executed by agora_admin (regla ⑥ deferred enforcement)",
            payload={"action": action, "actor_role": actor.role},
        )
        store.record_event(ev)
    except Exception:
        pass
    logger.warning(
        "regla⑥: host LXD op '%s' triggered by agora_admin %s "
        "(should require host_admin after migration)",
        action, getattr(actor, "username", actor.id),
        extra={"event": "rule_6_violation", "action": action,
               "actor_id": actor.id, "actor_role": actor.role},
    )


def _log_admin_action(
    actor: User | None,
    action: str,
    *,
    outcome: str = "started",
    **fields: object,
) -> None:
    """Emit a structured log line for an admin action.

    The JSON formatter in app/logging.py picks up every non-standard
    LogRecord attribute via `extra=…`, so a call like
    ``_log_admin_action(actor, "provision-user", slug=slug)`` produces a
    one-liner JSON event with `actor_id`, `action`, `outcome`, `slug` —
    grep-friendly for incident review.
    """
    extra = {
        "event": "admin",
        "action": action,
        "outcome": outcome,
        "actor_id": getattr(actor, "id", None),
        "actor_username": getattr(actor, "username", None),
    }
    extra.update(fields)
    logger.info("admin action: %s outcome=%s", action, outcome, extra=extra)


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
        if name != "laia-agora" and not is_user_agent_container(name):
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


def _fallback_containers_from_store() -> list[dict]:
    """Best-effort container view when backend cannot access host LXD.

    In the deployed architecture, ``laia-agora`` runs inside an unprivileged
    container and may not be in the host ``lxd`` group. The admin dashboard
    should still report the orchestrator and registered executors from DB
    state instead of showing zero containers.
    """
    rows = [{
        "name": "laia-agora",
        "state": "RUNNING",
        "ipv4": "",
        "type": "CONTAINER",
        "snapshots": "0",
        "source": "db-fallback",
    }]
    for agent in store.agents():
        if agent.status != "running":
            continue
        rows.append({
            "name": agent.container_name,
            "state": "RUNNING",
            "ipv4": agent.container_ip or "",
            "type": "CONTAINER",
            "snapshots": "0",
            "source": "db-fallback",
        })
    return rows


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
    """Return admin-facing auth-store readiness without exposing secrets."""
    try:
        from . import agent_pool
        status = agent_pool.auth_json_status
        path = agent_pool.auth_json_path or str(settings.data_dir / "auth.json")
    except Exception:
        status = "unknown"
        path = str(settings.data_dir / "auth.json")
    return auth_json_snapshot(
        path,
        status,
        os.environ.get("AGORA_DEFAULT_PROVIDER", "openai-codex"),
    )


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
    try:
        container = "laia-agora" if name == "laia-agora" else normalize_container_name(name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
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
        container_name=canonical_container_name(slug),
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
        container = canonical_container_name(slug)
        _append_job_log(log_path, f"provisioning container {container}")
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
                cleanup = _run_command(["lxc", "delete", "--force", container], timeout=120)
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
        existing_agent = next((a for a in store.agents() if a.user_id == user.id or a.id == user.agent_id), None)
        container = existing_agent.container_name if existing_agent else canonical_container_name(slug)
        result = _run_command(["lxc", "delete", "--force", container], timeout=120)
        if not result["ok"]:
            _append_job_log(log_path, result["stderr"] or result["stdout"])
        user_dir = resolved_path("AGORA_ADMIN_USERS_ROOT", "srv_users", "/srv/laia/users") / slug
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
        existing_agent = next((a for a in store.agents() if a.user_id == user.id or a.id == user.agent_id), None)
        container = existing_agent.container_name if existing_agent else canonical_container_name(slug)
        _append_job_log(log_path, f"deleting old container {container}")
        delete_result = _run_command(["lxc", "delete", "--force", container], timeout=120)
        if not delete_result["ok"]:
            _append_job_log(log_path, delete_result["stderr"] or delete_result["stdout"])
        script = settings.laia_root / "infra" / "lxd" / "scripts" / "create-agent.sh"
        _append_job_log(log_path, f"recreating container {container}")
        create_result = _run_command([str(script), slug, params.get("image_alias", "laia-agent")], timeout=900)
        _append_job_log(log_path, create_result["stdout"])
        if create_result["stderr"]:
            _append_job_log(log_path, create_result["stderr"])
        if not create_result["ok"]:
            raise RuntimeError(create_result["stderr"] or create_result["stdout"] or "create-agent failed")
        provision = _extract_last_json_line(create_result["stdout"])
        for agent in store.agents():
            if (
                agent.user_id == user.id
                or agent.id == user.agent_id
                or agent.container_name in set(candidate_container_names(slug))
            ):
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
    """Handle GET /jobs."""
    return {"jobs": store.admin_jobs(status=status, limit=limit)}


@router.get("/jobs/{job_id}")
def get_admin_job(job_id: str, _: User = Depends(require_roles("agora_admin"))):
    """Handle GET /jobs/{job_id}."""
    job = store.admin_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    job["log_tail"] = _tail_file(job.get("log_path"), lines=80)
    return {"job": job}


def _jobs_summary() -> dict:
    """Compact roll-up of admin_jobs for the dashboard.

    Walks the most recent N jobs (default 100) and groups by status.
    The TUI consumes ``running`` / ``pending`` counts to draw a badge on
    the Jobs tab without hitting `/jobs` separately.
    """
    try:
        recent = store.admin_jobs(limit=200)
    except Exception:
        return {"running": 0, "pending": 0, "failed_recent": 0, "total_recent": 0}
    running = sum(1 for j in recent if j.get("status") == "running")
    pending = sum(1 for j in recent if j.get("status") == "pending")
    failed = sum(1 for j in recent if j.get("status") == "failed")
    return {
        "running": running,
        "pending": pending,
        "failed_recent": failed,
        "total_recent": len(recent),
    }


def _tests_snapshot() -> dict:
    """Last test-suite run, surfaced from the most recent admin_job of
    kind 'run-tests'. Returns ``{"status": "unknown", "last_run": None}``
    when no such job has ever been created."""
    try:
        recent = store.admin_jobs(limit=50)
    except Exception:
        return {"status": "unknown", "last_run": None}
    tests = [j for j in recent if j.get("kind") == "run-tests"]
    if not tests:
        return {"status": "unknown", "last_run": None}
    latest = tests[0]
    result = latest.get("result") or {}
    return {
        "status": latest.get("status"),
        "last_run": latest.get("finished_at") or latest.get("started_at") or latest.get("created_at"),
        "passed": result.get("passed"),
        "failed": result.get("failed"),
        "job_id": latest.get("id"),
    }


def _parse_lxd_time(value: str) -> datetime | None:
    value = value.strip().replace(" UTC", "+00:00")
    for fmt in ("%Y/%m/%d %H:%M%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(value, fmt).astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _image_freshness_snapshot() -> dict:
    image_alias = os.environ.get("AGORA_IMAGE_ALIAS", "laia-agora")
    threshold = int(os.environ.get("AGORA_IMAGE_DRIFT_WARNING_SECONDS", "0"))
    image = _run_command(["lxc", "image", "info", image_alias], timeout=10)
    git = _run_command(
        [
            "git", "-C", str(settings.laia_root), "log", "-1", "--format=%ct",
            "--", "services/agora-backend", ".laia-core",
        ],
        timeout=10,
    )
    built_at: str | None = None
    built_epoch: float | None = None
    if image["ok"]:
        uploaded = created = ""
        for line in image["stdout"].splitlines():
            stripped = line.strip()
            if stripped.startswith("Uploaded:"):
                uploaded = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("Created:"):
                created = stripped.split(":", 1)[1].strip()
        parsed = _parse_lxd_time(uploaded or created)
        if parsed:
            built_at = parsed.isoformat()
            built_epoch = parsed.timestamp()

    last_commit: str | None = None
    commit_epoch: float | None = None
    if git["ok"]:
        raw = git["stdout"].strip().splitlines()[-1:] or [""]
        if raw[0].isdigit():
            commit_epoch = float(raw[0])
            last_commit = datetime.fromtimestamp(commit_epoch, timezone.utc).isoformat()

    drift_seconds = None
    stale = False
    if built_epoch is not None and commit_epoch is not None:
        drift_seconds = int(commit_epoch - built_epoch)
        stale = drift_seconds > threshold

    return {
        "image_alias": image_alias,
        "built_at": built_at,
        "last_commit_touching_backend": last_commit,
        "drift_seconds": drift_seconds,
        "drift_warning_threshold": threshold,
        "stale": stale,
        "ok": image["ok"] and git["ok"] and built_at is not None and last_commit is not None,
        "image_error": None if image["ok"] else image["stderr"] or image["stdout"],
        "git_error": None if git["ok"] else git["stderr"] or git["stdout"],
    }


@router.get("/status")
def admin_status(_: User = Depends(require_roles("agora_admin"))):
    """Handle GET /status."""
    containers, container_error = _list_lxc_containers()
    if not containers and container_error:
        containers = _fallback_containers_from_store()
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
            "image": _image_freshness_snapshot(),
            "tests": _tests_snapshot(),
            "jobs": _jobs_summary(),
            "recent_errors": _recent_error_lines(),
        }
    }


@router.get("/image/freshness")
def image_freshness(_: User = Depends(require_roles("agora_admin"))):
    """Handle GET /image/freshness."""
    return {"image": _image_freshness_snapshot()}


@router.get("/containers")
def admin_containers(_: User = Depends(require_roles("agora_admin"))):
    """Handle GET /containers."""
    containers, error = _list_lxc_containers()
    if not containers and error:
        containers = _fallback_containers_from_store()
    return {"containers": _enrich_containers(containers), "error": error}


@router.get("/logs/{name}")
def admin_logs(
    name: str,
    lines: int = Query(default=100, ge=1, le=2000),
    since: str | None = None,
    _: User = Depends(require_roles("agora_admin")),
):
    """Handle GET /logs/{name}."""
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
    before: str | None = Query(default=None, description="ISO timestamp — return events strictly older than this; pair with `limit` to page back in time"),
    _: User = Depends(require_roles("agora_admin")),
):
    """Tool-call audit events from the structured log file.

    Pagination model is cursor-based on timestamp: pass ``before=<ts>`` to
    retrieve the next older page. Returns ``next_before`` (the oldest ``ts``
    in the current batch) when the page is full so the caller can chain
    requests without managing offsets.
    """
    effective_to = before or to
    events = _audit_events(user_id=user_id, from_ts=from_, to_ts=effective_to, limit=limit)
    # Events come back chronologically ascending (oldest first, newest
    # last after the `[-limit:]` trim). To page BACKWARDS in time the
    # cursor must be the ts of the OLDEST event on this page (events[0]),
    # not the newest — otherwise the next request would re-include the
    # boundary event because the filter is `ts > to_ts` (exclusive).
    next_before = events[0].get("ts") if len(events) >= limit and events else None
    return {"tool_calls": events, "next_before": next_before, "page_size": limit}


@router.get("/errors")
def admin_errors(
    limit: int = Query(default=50, ge=1, le=500),
    since_minutes: int = Query(default=60, ge=1, le=24 * 60 * 7),
    _: User = Depends(require_roles("agora_admin")),
):
    """Recent error/warn lines from the backend log.

    Reads ``_recent_error_lines`` (same source the dashboard uses) but
    paginates and parses each line into structured fields when possible.
    Dedicated tab in the TUI consumes this — operators see exactly what
    failed without grepping journalctl.
    """
    raw = _recent_error_lines(limit=limit * 2)  # request more, filter below
    cutoff = datetime.now(timezone.utc).timestamp() - since_minutes * 60
    parsed: list[dict] = []
    for line in raw:
        item = _parse_audit_line(line) or {"raw": line}
        ts_str = item.get("ts") or item.get("asctime") or ""
        try:
            ts_epoch = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            ts_epoch = 0.0
        if ts_epoch and ts_epoch < cutoff:
            continue
        parsed.append(item)
        if len(parsed) >= limit:
            break
    return {
        "errors": parsed,
        "since_minutes": since_minutes,
        "count": len(parsed),
    }


@router.post("/system/refresh-oauth")
def refresh_oauth(actor: User = Depends(require_roles("agora_admin"))):
    """Handle POST /system/refresh-oauth."""
    _admin_rate_limit(actor.id)
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
        _log_admin_action(actor, "refresh-oauth", outcome="failed", error=(result["stderr"] or result["stdout"])[:200])
        raise HTTPException(status_code=500, detail=result["stderr"] or result["stdout"])
    _log_admin_action(actor, "refresh-oauth", outcome="ok", target=f"{container}{target}")
    return {"ok": True, "result": {"target": f"{container}{target}", "output": result["stdout"]}}


@router.post("/users/provision", response_model=AdminJobResponse, status_code=202)
def provision_user(payload: AdminProvisionUserRequest, actor: User = Depends(require_roles("agora_admin"))):
    """Handle POST /users/provision."""
    _admin_rate_limit(actor.id)
    if payload.image_alias not in _ALLOWED_IMAGE_ALIASES:
        raise HTTPException(
            status_code=422,
            detail=f"image_alias {payload.image_alias!r} not in allow-list {sorted(_ALLOWED_IMAGE_ALIASES)}",
        )
    params = payload.model_dump()
    job_id = _start_job(
        kind="provision-user",
        actor=actor,
        params=params,
        fn=_provision_user_job(actor.id),
    )
    _log_admin_action(actor, "provision-user", job_id=job_id, slug=payload.slug)
    return AdminJobResponse(job_id=job_id)


@router.get("/users")
def admin_users(_: User = Depends(require_roles("agora_admin"))):
    """Handle GET /users."""
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


# ── Budget caps + usage ledger (Fase D) ───────────────────────────────────


from pydantic import BaseModel as _BaseModel
from typing import Optional as _Optional


class _BudgetPatch(_BaseModel):
    daily_usd: _Optional[float] = None
    monthly_usd: _Optional[float] = None
    tokens_daily: _Optional[int] = None
    # Sentinel keys: any field set explicitly to ``None`` clears; missing
    # fields are left unchanged. Pydantic exposes ``model_fields_set`` to
    # tell which keys arrived in the request body.


@router.get("/users/{user_id}/budget")
def get_user_budget(user_id: str, _: User = Depends(require_roles("agora_admin"))):
    """Handle GET /users/{user_id}/budget."""
    if store.user_by_id(user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")
    return {"user_id": user_id, "budget": store.get_user_budget(user_id)}


@router.patch("/users/{user_id}/budget")
def patch_user_budget(user_id: str, payload: _BudgetPatch,
                      actor: User = Depends(require_roles("agora_admin"))):
    """Handle PATCH /users/{user_id}/budget."""
    if store.user_by_id(user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")
    kwargs: dict = {}
    if "daily_usd" in payload.model_fields_set:
        kwargs["daily_usd"] = payload.daily_usd
    if "monthly_usd" in payload.model_fields_set:
        kwargs["monthly_usd"] = payload.monthly_usd
    if "tokens_daily" in payload.model_fields_set:
        kwargs["tokens_daily"] = payload.tokens_daily
    new = store.set_user_budget(user_id, **kwargs)
    _log_admin_action(actor, "budget-set", target=user_id, **new)
    return {"user_id": user_id, "budget": new}


@router.get("/usage")
def admin_usage_breakdown(
    user_id: str | None = None,
    window: str = "day",
    _: User = Depends(require_roles("agora_admin")),
):
    """Return per-user (or single-user) usage breakdown for the window
    ``day`` / ``week`` / ``month``. Default: day."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    if window == "month":
        since = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif window == "week":
        since = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    since_iso = since.isoformat()

    if user_id is not None:
        if store.user_by_id(user_id) is None:
            raise HTTPException(status_code=404, detail="user not found")
        return {
            "window": window, "since": since_iso, "user_id": user_id,
            "totals": store.usage_total_for(user_id, since_iso=since_iso),
            "breakdown": store.usage_breakdown_for(user_id, since_iso=since_iso),
        }
    # All users.
    users_rows = []
    for u in store.users():
        totals = store.usage_total_for(u.id, since_iso=since_iso)
        if totals["calls"] > 0:
            users_rows.append({
                "user_id": u.id, "username": u.username,
                "totals": totals,
            })
    return {"window": window, "since": since_iso, "users": users_rows}


@router.get("/users-overview")
def users_overview(
    window: str = "day",
    _: User = Depends(require_roles("agora_admin")),
):
    """Single-shot per-user roll-up: profile + container + LLM cfg + budget
    + usage for the window. Replaces the N+1 pattern in the legacy TUI
    (Cost + Areas tabs used to fan out 50+ requests for 50 users).
    """
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    if window == "month":
        since = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif window == "week":
        since = (now - timedelta(days=7)).replace(
            hour=0, minute=0, second=0, microsecond=0)
    else:
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    since_iso = since.isoformat()

    agents_by_user = {a.user_id: a for a in store.agents()}

    rows: list[dict] = []
    for u in store.users():
        agent = agents_by_user.get(u.id)
        # Cheap path: budget + usage + inbox + learnings all hit indexed
        # cols in agora.db; the heaviest query is usage_total_for, but it
        # uses idx_ledger_user_ts so it stays sub-ms even with thousands
        # of rows per user.
        try:
            usage = store.usage_total_for(u.id, since_iso=since_iso)
        except Exception:
            usage = {"tokens_input": 0, "tokens_output": 0,
                     "cost_usd": 0.0, "calls": 0}
        try:
            budget = store.get_user_budget(u.id)
        except Exception:
            budget = {"daily_usd": None, "monthly_usd": None, "tokens_daily": None}
        try:
            unread = store.unread_count_for_user(u.id)
        except Exception:
            unread = 0
        try:
            lcount_row = store.db.conn.execute(
                "SELECT COUNT(*) FROM agent_learnings WHERE user_id = ?",
                (u.id,),
            ).fetchone()
            lcount = int(lcount_row[0] or 0)
        except Exception:
            lcount = 0
        rows.append({
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "role": u.role,
            "active": bool(u.active),
            "agent_id": u.agent_id,
            "container_name": agent.container_name if agent else None,
            "container_ip": agent.container_ip if agent else None,
            "container_status": agent.status if agent else None,
            "llm_provider": u.llm_provider,
            "llm_model": u.llm_model,
            "budget": budget,
            "usage": usage,
            "unread_inbox": unread,
            "learnings_count": lcount,
        })
    return {"window": window, "since": since_iso, "users": rows}


class _LLMConfigUpdateAdmin(BaseModel):
    provider: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_mode: str | None = None
    extras: dict | None = None
    mcp_servers: list[dict] | None = None


@router.patch("/users/{user_id}/llm-config")
def patch_user_llm_config_admin(
    user_id: str,
    payload: _LLMConfigUpdateAdmin,
    actor: User = Depends(require_roles("agora_admin")),
):
    """Admin counterpart to ``PATCH /api/user/llm-config``. Lets an admin
    set the LLM provider/api_key/model/mode for any user — used by the
    new-user wizard in the v2 control center."""
    if store.user_by_id(user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")
    fields = payload.model_fields_set
    extras_json: str | None
    if "extras" in fields:
        if payload.extras is None:
            extras_json = ""
        else:
            extras_json = json.dumps(payload.extras, ensure_ascii=False, sort_keys=True)
    else:
        extras_json = None
    mcp_json: str | None
    if "mcp_servers" in fields:
        if payload.mcp_servers is None:
            mcp_json = ""
        else:
            mcp_json = json.dumps(payload.mcp_servers, ensure_ascii=False, sort_keys=True)
    else:
        mcp_json = None
    updated = store.update_user_llm_config(
        user_id,
        provider=payload.provider if "provider" in fields else None,
        api_key=payload.api_key if "api_key" in fields else None,
        base_url=payload.base_url if "base_url" in fields else None,
        model=payload.model if "model" in fields else None,
        api_mode=payload.api_mode if "api_mode" in fields else None,
        extras_json=extras_json,
        mcp_servers_json=mcp_json,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="user not found")
    _log_admin_action(actor, "llm-config-set", target=user_id,
                      provider=updated.llm_provider, model=updated.llm_model)
    return {
        "user_id": user_id,
        "provider": updated.llm_provider,
        "model": updated.llm_model,
        "base_url": updated.llm_base_url,
        "api_mode": updated.llm_api_mode,
        "has_key": bool(updated.llm_api_key),
    }


@router.get("/users/{user_id}/scheduled-jobs")
def user_scheduled_jobs(
    user_id: str,
    _: User = Depends(require_roles("agora_admin")),
):
    """Handle GET /users/{user_id}/scheduled-jobs."""
    if store.user_by_id(user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")
    jobs = store.list_scheduled_jobs(user_id)
    webhooks = store.list_webhooks(user_id)
    return {
        "user_id": user_id,
        "scheduled_jobs": [j.model_dump() for j in jobs],
        "webhooks": [w.model_dump() for w in webhooks],
    }


@router.get("/users/{user_id}/child-runs")
def user_child_runs(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    _: User = Depends(require_roles("agora_admin")),
):
    """Handle GET /users/{user_id}/child-runs."""
    if store.user_by_id(user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")
    runs = store.list_child_runs_for_user(user_id, limit=limit)
    return {"user_id": user_id, "count": len(runs),
            "child_runs": [r.model_dump() for r in runs]}


@router.delete("/users/{slug}", response_model=AdminJobResponse, status_code=202)
def delete_admin_user(slug: str, actor: User = Depends(require_roles("agora_admin"))):
    """Handle DELETE /users/{slug}."""
    _admin_rate_limit(actor.id)
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
    _log_admin_action(actor, "delete-user", job_id=job_id, slug=slug)
    return AdminJobResponse(job_id=job_id)


# Rule ⑥: this endpoint runs `lxc delete --force` + `create-agent.sh`
# on the host. After the host_admin migration it should require that
# role. For now we audit + accept.
@router.post("/users/{slug}/rebuild", response_model=AdminJobResponse, status_code=202)
def rebuild_admin_user(
    slug: str,
    image_alias: str = "laia-agent",
    actor: User = Depends(require_roles("agora_admin")),
):
    """Handle POST /users/{slug}/rebuild."""
    _warn_host_op_via_agora_admin(actor, "rebuild-user")  # regla ⑥
    _admin_rate_limit(actor.id)
    if not SLUG_RE.fullmatch(slug):
        raise HTTPException(status_code=422, detail="invalid slug")
    if image_alias not in _ALLOWED_IMAGE_ALIASES:
        raise HTTPException(
            status_code=422,
            detail=f"image_alias {image_alias!r} not in allow-list {sorted(_ALLOWED_IMAGE_ALIASES)}",
        )
    job_id = _start_job(
        kind="rebuild-user",
        actor=actor,
        params={"slug": slug, "image_alias": image_alias},
        fn=_rebuild_user_job(actor.id),
    )
    _log_admin_action(actor, "rebuild-user", job_id=job_id, slug=slug, image_alias=image_alias)
    return AdminJobResponse(job_id=job_id)


@router.post("/containers/{name}/restart", response_model=AdminJobResponse, status_code=202)
def restart_container(name: str, actor: User = Depends(require_roles("agora_admin"))):
    # Rule ⑥: this is LXD host territory, should require host_admin
    # post-migration. See _warn_host_op_via_agora_admin docstring.
    """Handle POST /containers/{name}/restart."""
    _warn_host_op_via_agora_admin(actor, "container-restart")
    _admin_rate_limit(actor.id)
    container = _normalize_container_name(name)
    job_id = _start_job(
        kind="container-restart",
        actor=actor,
        params={"container": container},
        fn=_container_command_job("restart", actor.id),
    )
    _log_admin_action(actor, "container-restart", job_id=job_id, container=container)
    return AdminJobResponse(job_id=job_id)


@router.post("/containers/{name}/snapshot", response_model=AdminJobResponse, status_code=202)
def snapshot_container(
    name: str,
    payload: AdminContainerSnapshotRequest,
    actor: User = Depends(require_roles("agora_admin")),
):
    """Handle POST /containers/{name}/snapshot."""
    _warn_host_op_via_agora_admin(actor, "container-snapshot")  # Rule ⑥
    _admin_rate_limit(actor.id)
    container = _normalize_container_name(name)
    job_id = _start_job(
        kind="container-snapshot",
        actor=actor,
        params={"container": container, "snapshot": payload.name},
        fn=_container_command_job("snapshot", actor.id),
    )
    _log_admin_action(actor, "container-snapshot", job_id=job_id, container=container, snapshot=payload.name)
    return AdminJobResponse(job_id=job_id)


@router.post("/containers/{name}/restore", response_model=AdminJobResponse, status_code=202)
def restore_container(
    name: str,
    payload: AdminContainerSnapshotRequest,
    actor: User = Depends(require_roles("agora_admin")),
):
    """Handle POST /containers/{name}/restore."""
    _warn_host_op_via_agora_admin(actor, "container-restore")  # Rule ⑥
    _admin_rate_limit(actor.id)
    container = _normalize_container_name(name)
    job_id = _start_job(
        kind="container-restore",
        actor=actor,
        params={"container": container, "snapshot": payload.name},
        fn=_container_command_job("restore", actor.id),
    )
    _log_admin_action(actor, "container-restore", job_id=job_id, container=container, snapshot=payload.name)
    return AdminJobResponse(job_id=job_id)


@router.post("/system/restart-backend", response_model=AdminJobResponse, status_code=202)
def restart_backend(actor: User = Depends(require_roles("agora_admin"))):
    """Handle POST /system/restart-backend."""
    _warn_host_op_via_agora_admin(actor, "restart-backend")  # Rule ⑥
    _admin_rate_limit(actor.id)

    def run(_params: dict, log_path: str) -> dict:
        args = ["lxc", "exec", "laia-agora", "--", "systemctl", "restart", "agora-backend"]
        _append_job_log(log_path, " ".join(args))
        result = _run_command(args, timeout=60)
        if not result["ok"]:
            raise RuntimeError(result["stderr"] or result["stdout"] or "restart failed")
        return {"ok": True, "output": result["stdout"], "error": result["stderr"]}

    job_id = _start_job(kind="restart-backend", actor=actor, params={}, fn=run)
    _log_admin_action(actor, "restart-backend", job_id=job_id)
    return AdminJobResponse(job_id=job_id)


# ──────────────────────────────────────────────────────────────────────────
# Self-heal fixes (F8)
#
# A curated registry of one-shot scripts that resolve specific known
# failure modes. Each fix is keyed by a short slug; the body is a
# callable that does the work and returns a dict. The handler wraps it
# in the standard job machinery so the TUI can follow progress.
#
# Why curated (vs an arbitrary command runner): the admin endpoints
# already let any agora_admin run lxc/systemctl. The fix registry exists
# so common recipes don't have to be reinvented or copy-pasted from
# docs/HANDOFF_*.md each time an operator hits them — they show up as
# `POST /api/admin/fix/{name}` with a one-line description.
# ──────────────────────────────────────────────────────────────────────────


def _fix_auth_json_push(actor_id: str, log_path: str) -> dict:
    """G1 from the handoff: re-push host ~/.laia/auth.json to laia-agora."""
    host_auth = Path(
        os.environ.get("AGORA_ADMIN_HOST_AUTH_JSON")
        or os.environ.get("AGORA_ARCH_AUTH_JSON")
        or str(Path.home() / ".laia" / "auth.json")
    )
    if not host_auth.is_file():
        raise RuntimeError(f"host auth.json not found at {host_auth}")
    container = os.environ.get("AGORA_ADMIN_AUTH_CONTAINER", "laia-agora")
    target = os.environ.get("AGORA_ADMIN_AUTH_TARGET", "/opt/agora/data/auth.json")
    _append_job_log(log_path, f"lxc file push {host_auth} {container}{target}")
    result = _run_command(
        [
            "lxc", "file", "push", str(host_auth), f"{container}{target}",
            "--uid", os.environ.get("AGORA_ADMIN_AUTH_UID", "999"),
            "--gid", os.environ.get("AGORA_ADMIN_AUTH_GID", "988"),
            "--mode", os.environ.get("AGORA_ADMIN_AUTH_MODE", "644"),
        ],
        timeout=30,
    )
    if not result["ok"]:
        raise RuntimeError(result["stderr"] or result["stdout"] or "lxc file push failed")
    return {"target": f"{container}{target}", "output": result["stdout"]}


def _fix_pip_reinstall_laia_core(actor_id: str, log_path: str) -> dict:
    """Reinstall `.laia-core` inside laia-agora for upgrade repair.

    Fresh images install the package from pyproject.toml during build; this
    curated fix remains for future in-place upgrades or damaged venvs.
    """
    container = os.environ.get("AGORA_ADMIN_AGORA_CONTAINER", "laia-agora")
    args = [
        "lxc", "exec", container, "--",
        "/opt/agora/venv/bin/pip", "install", "/opt/agora/app/.laia-core",
    ]
    _append_job_log(log_path, " ".join(args))
    result = _run_command(args, timeout=600)
    if not result["ok"]:
        raise RuntimeError(result["stderr"] or result["stdout"] or "pip install failed")
    return {"output": result["stdout"][-2000:], "container": container}


def _fix_pm2_stop_respawner(actor_id: str, log_path: str) -> dict:
    """G4 from the handoff: a stray PM2 daemon respawns an old uvicorn
    on host :8088 even after kill. Stop + delete the PM2 entry."""
    # PM2 lives in the operator's HOME, so this needs to run as that user.
    pm2_user = os.environ.get("AGORA_ADMIN_PM2_USER", "laia-arch")
    args = ["sudo", "-u", pm2_user, "pm2", "delete", "agora-backend"]
    _append_job_log(log_path, " ".join(args))
    result = _run_command(args, timeout=10)
    save_args = ["sudo", "-u", pm2_user, "pm2", "save"]
    _run_command(save_args, timeout=10)
    return {
        "deleted": result["ok"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }


def _fix_chmod_laia_dir(actor_id: str, log_path: str) -> dict:
    """G1 sub-issue: ~/.laia keeps reverting to 0700 (some tool resets
    it). Re-applies 0755 + chmod 644 auth.json so the LXD bind mount
    is readable from inside the container.

    Note: requires the script to run as the file owner OR as root.
    Typically AGORA backend has neither, so this fix is best-effort.
    """
    home_laia = Path(
        os.environ.get("AGORA_ADMIN_HOST_LAIA_DIR")
        or str(Path.home() / ".laia")
    )
    if not home_laia.is_dir():
        raise RuntimeError(f"{home_laia} is not a directory")
    auth = home_laia / "auth.json"
    _append_job_log(log_path, f"chmod 0755 {home_laia} && chmod 0644 {auth}")
    try:
        os.chmod(home_laia, 0o755)
        if auth.is_file():
            os.chmod(auth, 0o644)
    except PermissionError as exc:
        raise RuntimeError(f"chmod failed: {exc} — run as the file owner")
    return {"dir": str(home_laia), "auth": str(auth) if auth.is_file() else None}


_FIX_REGISTRY: dict[str, dict] = {
    "auth-json-push": {
        "description": "Push host ~/.laia/auth.json to laia-agora (OAuth refresh)",
        "fn": _fix_auth_json_push,
        "timeout": 60,
    },
    "pip-reinstall-laia-core": {
        "description": "Reinstall .laia-core package inside laia-agora venv",
        "fn": _fix_pip_reinstall_laia_core,
        "timeout": 700,
    },
    "pm2-stop-respawner": {
        "description": "Stop + delete PM2 entry that respawns old agora-backend",
        "fn": _fix_pm2_stop_respawner,
        "timeout": 30,
    },
    "chmod-laia-dir": {
        "description": "Re-apply 0755 to ~/.laia + 0644 to auth.json",
        "fn": _fix_chmod_laia_dir,
        "timeout": 5,
    },
}


@router.get("/fixes")
def list_fixes(_: User = Depends(require_roles("agora_admin"))):
    """Handle GET /fixes."""
    return {
        "fixes": [
            {"name": name, "description": info["description"]}
            for name, info in _FIX_REGISTRY.items()
        ]
    }


@router.post("/fix/{name}", response_model=AdminJobResponse, status_code=202)
def run_fix(name: str, actor: User = Depends(require_roles("agora_admin"))):
    """Handle POST /fix/{name}."""
    _admin_rate_limit(actor.id)
    fix = _FIX_REGISTRY.get(name)
    if not fix:
        raise HTTPException(status_code=404, detail=f"unknown fix: {name!r}. Try GET /api/admin/fixes")
    timeout = fix.get("timeout", 60)
    fn = fix["fn"]
    description = fix["description"]

    def run(_params: dict, log_path: str) -> dict:
        _append_job_log(log_path, f"running fix: {name} — {description}")
        try:
            result = fn(actor.id, log_path)
        except Exception as exc:
            _append_job_log(log_path, f"fix failed: {exc}")
            raise
        _append_job_log(log_path, "fix completed OK")
        return {"name": name, **result}

    job_id = _start_job(kind=f"fix-{name}", actor=actor, params={"fix": name}, fn=run)
    _log_admin_action(actor, f"fix-{name}", job_id=job_id, description=description)
    return AdminJobResponse(job_id=job_id)


# ──────────────────────────────────────────────────────────────────────────
# Test suite runner (F9)
# ──────────────────────────────────────────────────────────────────────────


@router.get("/tests/status")
def tests_status(_: User = Depends(require_roles("agora_admin"))):
    """Last test-suite run (or 'unknown' if never run via the admin)."""
    return {"tests": _tests_snapshot()}


@router.post("/tests/run", response_model=AdminJobResponse, status_code=202)
def run_tests(actor: User = Depends(require_roles("agora_admin"))):
    """Trigger the agora-backend pytest suite as a background job.

    Operators use this to confirm the system is still green after an
    auto-fix or upgrade — no SSH needed.
    """
    _admin_rate_limit(actor.id)

    def run(_params: dict, log_path: str) -> dict:
        backend_dir = settings.laia_root / "services" / "agora-backend"
        python_bin = Path(sys.executable)
        if not python_bin.is_file():
            raise RuntimeError(f"python binary not found at {python_bin}")
        pythonpath = os.pathsep.join([
            str(settings.laia_root),
            str(settings.laia_root / ".laia-core"),
            str(settings.laia_root / "services" / "laia-executor" / "src"),
        ])
        env_extra = {
            "PYTHONPATH": pythonpath,
            "PYTEST_ADDOPTS": "-p no:cacheprovider",
        }
        cmd = [
            str(python_bin), "-m", "pytest", "tests/", "-q", "--no-header",
            "--maxfail", "5",
        ]
        _append_job_log(log_path, "$ " + " ".join(cmd))
        result = subprocess.run(
            cmd, cwd=str(backend_dir),
            capture_output=True, text=True, timeout=600,
            env={**os.environ, **env_extra},
        )
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        for line in output.splitlines()[-40:]:
            _append_job_log(log_path, line)
        # Parse pytest summary "X passed, Y failed" (best-effort)
        passed = failed = 0
        for line in output.splitlines():
            m = re.search(r"(\d+)\s+passed", line)
            if m:
                passed = int(m.group(1))
            m = re.search(r"(\d+)\s+failed", line)
            if m:
                failed = int(m.group(1))
        return {
            "passed": passed,
            "failed": failed,
            "returncode": result.returncode,
            "tail": output.splitlines()[-15:],
        }

    job_id = _start_job(kind="run-tests", actor=actor, params={}, fn=run)
    _log_admin_action(actor, "run-tests", job_id=job_id)
    return AdminJobResponse(job_id=job_id)
