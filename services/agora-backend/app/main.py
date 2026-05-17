from __future__ import annotations

import logging
import os
import re
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field as PydField

from .config import settings
from .auth import authenticate, can_access_user_scope, current_user, issue_tokens, public_user, require_roles
from .models import (
    Agent,
    AgentProfile,
    AgentProfileUpdate,
    AgentStatus,
    AgentTaskCreate,
    AgentUpdate,
    CoordinatorAssignRequest,
    CreateAgentRequest,
    RegisterAgentRequest,
    SecretsFetchRequest,
    SecretsFetchResponse,
    Event,
    EventCreate,
    LLMConfigUpdate,
    LLMConfigView,
    LLMProviderInfo,
    TelegramLinkStatus,
    TelegramLinkTokenResponse,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    SnapshotRequest,
    Task,
    TaskCreate,
    TaskUpdate,
    TokenRefreshRequest,
    User,
    UserCreateRequest,
    UserCreateResponse,
    UserUpdateRequest,
    UserResetPasswordResponse,
    WorkspaceNodeCreate,
    new_id,
    now_iso,
)
from .llm_config import (
    determine_api_mode as llm_determine_api_mode,
    get_provider as llm_get_provider,
    list_providers as llm_list_providers,
    mask_api_key as llm_mask_api_key,
)
from .orchestrator import OrchestratorError, orchestrator
from .coordinator import coordinator, drain_broadcasts
from .monitor import monitor
from .logging import RequestTimer, request_id_var, request_user_var, setup_logging
from .metrics import metrics
from .security import verify_password, hash_password, verify_token
from .config import settings
from .storage import store
from .websocket import ws_manager


def _resolve_agent_slug(user: User) -> str:
    """Given a user, find the slug of their personal agent container."""
    agents = store.agents()
    for a in agents:
        if a.user_id == user.id or a.id == user.agent_id:
            return a.container_name.removeprefix("laia-")
    for a in agents:
        if a.user_id == user.id:
            return a.container_name.removeprefix("laia-")
    raise HTTPException(status_code=404, detail="no agent assigned to this user")

from contextlib import asynccontextmanager
from .telegram_gateway import TelegramGateway, build_gateway_from_env


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI startup/shutdown — replaces the deprecated @app.on_event hooks."""
    setup_logging()
    coordinator.start()
    monitor.start()

    # Share one AgentPool across web chat + Telegram dispatch so a user that
    # chats from both surfaces sees the same cached AIAgent / context.
    try:
        from .agent_pool import AgentPool
        from .chat_engine import set_pool as _set_chat_pool
        from .telegram_gateway import _shared_pool_instance as _tg_pool_holder
        pool = AgentPool()
        _set_chat_pool(pool)
        # Wire the same pool into telegram_gateway's lazy default so both
        # dispatch surfaces share session state.
        import app.telegram_gateway as _tg_mod
        _tg_mod._shared_pool_instance = pool
    except Exception:
        logging.getLogger(__name__).exception("failed to build AgentPool")

    # CRITICAL ORDER: (1) point LAIA_HOME at AGORA's data dir, (2) seed
    # config.yaml with plugins.enabled=[agora-executor-forwarder], (3) THEN
    # call discover_plugins. If we do them in any other order the plugin
    # manager scans an empty/stale config and the forwarder hook never
    # registers — every filesystem/bash tool call from the LLM runs on the
    # host instead of being forwarded to the user's executor container.
    try:
        from .config import settings as _agora_settings
        import os as _os
        # Force the env var even if something already set ~/.laia as default
        # during an earlier import. ``setdefault`` would leave a stale value
        # alone — assign unconditionally so the plugin manager scans AGORA's
        # config.yaml, not ARCH's.
        _os.environ["LAIA_HOME"] = str(_agora_settings.data_dir)
        # Some import paths (memory_provider lazy load, etc.) may have
        # already invoked ``load_config`` before this point, which cached the
        # ``~/.laia/config.yaml`` contents under that path. Invalidate the
        # cache so the next ``load_config`` call sees AGORA's config.
        try:
            from laia_cli.config import _LOAD_CONFIG_CACHE  # type: ignore[import-not-found]
            _LOAD_CONFIG_CACHE.clear()
        except Exception:
            pass
    except Exception:
        pass
    try:
        from .agent_pool import seed_agora_config_yaml
        seed_agora_config_yaml()
    except Exception:
        logging.getLogger(__name__).warning("config.yaml seed skipped at startup")

    try:
        from laia_cli.plugins import discover_plugins  # type: ignore[import-not-found]
        # Force=True so we re-scan if discover_plugins already ran during
        # an earlier import path (e.g. via memory_provider lazy loading).
        discover_plugins(force=True)
    except Exception as _e:
        logging.getLogger(__name__).warning("plugin discovery skipped: %s", _e)

    # Optional Telegram bot: starts only when AGORA_TELEGRAM_TOKEN is set.
    gw: TelegramGateway | None = build_gateway_from_env()
    if gw is not None:
        try:
            await gw.start()
            app.state.telegram_gateway = gw
        except Exception:
            logging.getLogger(__name__).exception("telegram gateway failed to start")
            app.state.telegram_gateway = None
    else:
        app.state.telegram_gateway = None

    try:
        yield
    finally:
        gw = getattr(app.state, "telegram_gateway", None)
        if gw is not None:
            try:
                await gw.stop()
            except Exception:
                logging.getLogger(__name__).exception("telegram gateway failed to stop cleanly")
        coordinator.stop()
        monitor.stop()
        store.db.close()


app = FastAPI(
    title="LAIA AGORA Backend",
    description="Backend oficial de AGORA: empleados, tareas, eventos, coordinacion y workspace colectivo.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
    request_id_var.set(rid)
    timer = RequestTimer(request.method, request.url.path)
    response = await call_next(request)
    elapsed = timer.finish(response.status_code)
    metrics.record(request.method, request.url.path, response.status_code, elapsed)
    response.headers["X-Request-ID"] = rid
    return response


@app.get("/api/health")
def health():
    import subprocess
    lxd_ok = False
    try:
        r = subprocess.run(["lxc", "version"], capture_output=True, text=True, timeout=5)
        lxd_ok = r.returncode == 0
    except Exception:
        pass
    laiactl_ok = settings.laiactl_path.exists()
    # Report whether OAuth credentials are reachable. If the operator selected
    # an OAuth default provider but ~/.laia/auth.json isn't linked yet, this
    # surfaces in /api/health so the operator notices before the first chat.
    try:
        from . import agent_pool as _ap
        auth_status = _ap.auth_json_status
        auth_ready = auth_status == "linked"
        auth_path = _ap.auth_json_path
    except Exception:
        auth_status = "unknown"
        auth_ready = False
        auth_path = None
    return {
        "ok": True,
        "service": "agora-backend",
        "version": "0.2.0",
        "env": settings.env,
        "data_dir": str(settings.data_dir),
        "db": "sqlite",
        "coordinator": coordinator.is_running,
        "lxd_available": lxd_ok,
        "laiactl_available": laiactl_ok,
        "auth_json_ready": auth_ready,
        "auth_json_status": auth_status,
        "auth_json_path": auth_path,
        "default_llm_provider": os.environ.get("AGORA_DEFAULT_PROVIDER", "openai-codex"),
        "time": now_iso(),
    }


@app.get("/api/metrics")
def get_metrics(_: User = Depends(require_roles("agora_admin"))):
    return metrics.snapshot()


@app.post("/api/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request):
    from .security import should_rate_limit
    client_ip = request.client.host if request.client else "unknown"
    if should_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="too many requests. wait 5 minutes")
    user = authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="invalid credentials")
    store.record_event(Event(event_type="auth_login", actor_id=user.id, summary=f"{user.username} login"))
    tokens = issue_tokens(user)
    return LoginResponse(**tokens, user=public_user(user))


@app.post("/api/refresh")
def refresh_token(payload: TokenRefreshRequest):
    try:
        data = verify_token(payload.refresh_token, settings.jwt_secret)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="not a refresh token")
    user = store.user_by_id(data["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    tokens = issue_tokens(user)
    store.record_event(Event(event_type="auth_refresh", actor_id=user.id, summary=f"{user.username} token refresh"))
    return tokens


@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return public_user(user)


# ── LLM provider catalog + per-user LLM config ───────────────────────────────


@app.get("/api/llm/providers", response_model=list[LLMProviderInfo])
def list_llm_providers():
    """List all LLM providers AGORA supports (parity with LAIA ARCH)."""
    return llm_list_providers()


@app.get("/api/llm/providers/{provider_id}/models")
def list_llm_provider_models(provider_id: str):
    p = llm_get_provider(provider_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"unknown provider: {provider_id}")
    return {"provider": provider_id, "models": p.default_models}


@app.get("/api/user/llm-config", response_model=LLMConfigView)
def get_llm_config(user: User = Depends(current_user)):
    return LLMConfigView(
        provider=user.llm_provider,
        base_url=user.llm_base_url,
        model=user.llm_model,
        api_mode=user.llm_api_mode,
        api_key_masked=llm_mask_api_key(user.llm_api_key),
        has_key=bool(user.llm_api_key),
    )


@app.patch("/api/user/llm-config", response_model=LLMConfigView)
def patch_llm_config(payload: LLMConfigUpdate, user: User = Depends(current_user)):
    if payload.provider and llm_get_provider(payload.provider) is None:
        raise HTTPException(status_code=400, detail=f"unknown provider: {payload.provider}")
    import json as _json
    extras_json = _json.dumps(payload.extras) if payload.extras is not None else None
    updated = store.update_user_llm_config(
        user.id,
        provider=payload.provider,
        api_key=payload.api_key,
        base_url=payload.base_url,
        model=payload.model,
        api_mode=payload.api_mode,
        extras_json=extras_json,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="user not found")
    store.record_event(Event(
        event_type="user_llm_config_updated",
        actor_id=user.id,
        summary=f"{user.username} updated LLM config",
    ))
    return LLMConfigView(
        provider=updated.llm_provider,
        base_url=updated.llm_base_url,
        model=updated.llm_model,
        api_mode=updated.llm_api_mode,
        api_key_masked=llm_mask_api_key(updated.llm_api_key),
        has_key=bool(updated.llm_api_key),
    )


@app.post("/api/user/telegram/link-token", response_model=TelegramLinkTokenResponse)
def post_telegram_link_token(user: User = Depends(current_user)) -> TelegramLinkTokenResponse:
    """Mint an ephemeral token the user pastes into Telegram as ``/link <token>``.

    Each new call supersedes any previous outstanding token for the same user,
    so a user that lost the previous code just needs to ask for another one.
    """
    from .telegram_links import link_token_store
    import time as _time

    issued = link_token_store.issue(user.id)
    bot_username = os.environ.get("AGORA_TELEGRAM_BOT_USERNAME", "").lstrip("@")
    deep_link = (
        f"https://t.me/{bot_username}?start=link_{issued.token}" if bot_username else None
    )
    store.record_event(Event(
        event_type="telegram_link_token_issued",
        actor_id=user.id,
        summary=f"{user.username} requested a Telegram link token",
    ))
    return TelegramLinkTokenResponse(
        token=issued.token,
        expires_at=issued.expires_at,
        expires_in_seconds=max(0, int(issued.expires_at - _time.time())),
        deep_link=deep_link,
    )


@app.get("/api/user/telegram/link", response_model=TelegramLinkStatus)
def get_telegram_link(user: User = Depends(current_user)) -> TelegramLinkStatus:
    ids = store.telegram_ids_for_user(user.id)
    return TelegramLinkStatus(linked=bool(ids), telegram_user_ids=ids)


@app.delete("/api/user/telegram/link")
def delete_telegram_link(user: User = Depends(current_user)) -> dict:
    from .telegram_links import link_token_store
    link_token_store.revoke_for_user(user.id)
    dropped = store.unlink_telegram_user(agora_user_id=user.id)
    if dropped:
        store.record_event(Event(
            event_type="telegram_link_removed",
            actor_id=user.id,
            summary=f"{user.username} unlinked Telegram ({dropped} binding(s))",
        ))
    return {"ok": True, "dropped": dropped}


@app.post("/api/me/password")
def change_password(payload: PasswordChangeRequest, user: User = Depends(current_user)):
    if not user.password or not user.password.startswith("$pbkdf2$"):
        if (user.password or "") != payload.old_password:
            raise HTTPException(status_code=403, detail="invalid current password")
    elif not verify_password(payload.old_password, user.password):
        raise HTTPException(status_code=403, detail="invalid current password")
    user.password = hash_password(payload.new_password)
    store.save_user(user)
    store.record_event(Event(event_type="auth_password_changed", actor_id=user.id, summary=f"{user.username} changed password"))
    return {"ok": True, "message": "password changed"}


@app.get("/api/users")
def list_users(_: User = Depends(require_roles("agora_admin"))):
    return {"users": [public_user(user) for user in store.users()]}


@app.post("/api/users", status_code=201, response_model=UserCreateResponse)
def create_user(payload: UserCreateRequest, actor: User = Depends(require_roles("agora_admin"))):
    # Default LLM config — operators can override via AGORA_DEFAULT_PROVIDER /
    # _MODEL / _API_MODE. Defaulting to ``openai-codex`` means new users
    # inherit the admin's ChatGPT Teams subscription (OAuth token from
    # ~/.laia/auth.json) and the operator does not have to paste an API key
    # for each new hire. Switch back to a paid-API provider by setting
    # AGORA_DEFAULT_PROVIDER=anthropic (or any other ARCH provider id).
    # Default model for openai-codex: must be one ChatGPT-account OAuth
    # accepts (validated by ARCH's _codex_curated_models in
    # .laia-core/laia_cli/codex_models.py). "gpt-5-codex" is API-only and
    # fails with HTTP 400 for OAuth callers.
    default_provider = os.environ.get("AGORA_DEFAULT_PROVIDER", "openai-codex")
    default_model = os.environ.get("AGORA_DEFAULT_MODEL", "gpt-5.5")
    default_api_mode = os.environ.get("AGORA_DEFAULT_API_MODE") or None

    password = payload.password or f"laia-{now_iso()[:19]}"
    hashed = hash_password(password)

    # Reactivation path: ``DELETE /api/users/<id>`` is a soft-delete that
    # leaves the row with ``active=0``. If the operator re-creates the same
    # username afterwards, treat it as "revive" rather than 409 — far
    # friendlier UX for dev/test loops where you redeploy the same slug.
    existing = store.user_by_username(payload.username)
    if existing:
        if existing.active:
            raise HTTPException(status_code=409, detail="username already exists")
        existing.active = True
        existing.display_name = payload.display_name
        existing.role = payload.role
        existing.password = hashed
        existing.llm_provider = default_provider or None
        existing.llm_model = default_model or None
        existing.llm_api_mode = default_api_mode
        # Wipe credentials from the prior owner — a re-created username must
        # NOT inherit a paid API key, a custom base_url, or a still-valid JWT.
        # The new operator reconfigures explicitly via PATCH /api/user/llm-config.
        existing.llm_api_key = None
        existing.llm_base_url = None
        existing.llm_extras_json = None
        existing.token = None
        # Re-creating with a different operator: drop any prior agent binding.
        existing.agent_id = None
        store.save_user(existing)
        store.record_event(Event(
            event_type="user_reactivated", actor_id=actor.id,
            summary=f"{payload.username} ({payload.role})",
            payload={"user_id": existing.id},
        ))
        return UserCreateResponse(
            ok=True, user=public_user(existing),
            password=password if not payload.password else None,
        )

    user = User(
        id=f"user_{payload.username}",
        username=payload.username,
        display_name=payload.display_name,
        role=payload.role,
        token=None,
        password=hashed,
        active=True,
        llm_provider=default_provider or None,
        llm_model=default_model or None,
        llm_api_mode=default_api_mode,
    )
    store.save_user(user)
    agent = None
    if payload.create_agent:
        from .models import Agent
        agent = Agent(
            id=f"agent_{payload.username}",
            user_id=user.id,
            container_name=f"laia-{payload.username}",
            status="planned",
            workspace_path="/opt/laia/workspaces/personal/workspace.db",
        )
        store.save_agent(agent)
        user.agent_id = agent.id
        store.save_user(user)
    store.record_event(Event(event_type="user_created", actor_id=actor.id,
                             summary=f"{payload.username} ({payload.role})",
                             payload={"user_id": user.id, "agent_created": payload.create_agent}))
    return UserCreateResponse(ok=True, user=public_user(user),
                              password=password if not payload.password else None)


@app.get("/api/users/{user_id}")
def get_user(user_id: str, _: User = Depends(require_roles("agora_admin"))):
    user = store.user_by_id(user_id)
    if not user or not user.active:
        raise HTTPException(status_code=404, detail="user not found")
    agents = [a for a in store.agents() if a.user_id == user_id]
    return {"user": public_user(user), "agents": agents}


@app.patch("/api/users/{user_id}")
def update_user(user_id: str, payload: UserUpdateRequest, actor: User = Depends(require_roles("agora_admin"))):
    user = store.user_by_id(user_id)
    if not user or not user.active:
        raise HTTPException(status_code=404, detail="user not found")
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.role is not None:
        user.role = payload.role
    store.save_user(user)
    store.record_event(Event(event_type="user_updated", actor_id=actor.id,
                             summary=f"{user.username} updated",
                             payload={"user_id": user.id}))
    return public_user(user)


@app.delete("/api/users/{user_id}")
def delete_user(user_id: str, actor: User = Depends(require_roles("agora_admin"))):
    if user_id == actor.id:
        raise HTTPException(status_code=400, detail="cannot delete yourself")
    user = store.user_by_id(user_id)
    if not user or not user.active:
        raise HTTPException(status_code=404, detail="user not found")
    store.disable_user(user_id)
    store.record_event(Event(event_type="user_disabled", actor_id=actor.id,
                             summary=f"{user.username} disabled",
                             payload={"user_id": user_id}))
    return {"ok": True}


@app.post("/api/users/{user_id}/reset-password", response_model=UserResetPasswordResponse)
def reset_user_password(user_id: str, actor: User = Depends(require_roles("agora_admin"))):
    user = store.user_by_id(user_id)
    if not user or not user.active:
        raise HTTPException(status_code=404, detail="user not found")
    new_pass = f"laia-{now_iso()[:19]}"
    user.password = hash_password(new_pass)
    store.save_user(user)
    store.record_event(Event(event_type="user_password_reset", actor_id=actor.id,
                             summary=f"{user.username} password reset",
                             payload={"user_id": user_id}))
    return UserResetPasswordResponse(ok=True, new_password=new_pass)


@app.get("/api/tasks")
def list_tasks(user: User = Depends(current_user)):
    tasks = store.tasks()
    if user.role != "agora_admin":
        tasks = [task for task in tasks if task.assignee_id in {None, user.id}]
    return {"tasks": tasks}


@app.post("/api/tasks")
def create_task(payload: TaskCreate, user: User = Depends(require_roles("agora_admin", "employee"))):
    if not can_access_user_scope(user, payload.assignee_id):
        raise HTTPException(status_code=403, detail="cannot assign task outside user scope")
    task = Task(**payload.model_dump())
    tasks = store.tasks()
    tasks.append(task)
    store.save_tasks(tasks)
    store.record_event(Event(event_type="task_created", actor_id=user.id, summary=task.title, payload={"task_id": task.id}))
    return task


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: str, payload: TaskUpdate, user: User = Depends(current_user)):
    existing = next((task for task in store.tasks() if task.id == task_id), None)
    if not existing:
        raise HTTPException(status_code=404, detail="task not found")
    if not can_access_user_scope(user, existing.assignee_id):
        raise HTTPException(status_code=403, detail="cannot update task outside user scope")
    if payload.assignee_id and not can_access_user_scope(user, payload.assignee_id):
        raise HTTPException(status_code=403, detail="cannot assign task outside user scope")
    task = store.update_task(task_id, **payload.model_dump(exclude_unset=True))
    store.record_event(Event(event_type="task_updated", actor_id=user.id, summary=task.title, payload={"task_id": task.id}))
    return task


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str, user: User = Depends(current_user)):
    existing = next((task for task in store.tasks() if task.id == task_id), None)
    if not existing:
        raise HTTPException(status_code=404, detail="task not found")
    if not can_access_user_scope(user, existing.assignee_id):
        raise HTTPException(status_code=403, detail="cannot delete task outside user scope")
    store.delete_task(task_id)
    store.record_event(Event(event_type="task_deleted", actor_id=user.id, summary=existing.title, payload={"task_id": task_id}))
    return {"ok": True}


@app.get("/api/events")
def list_events(limit: int = 100, user: User = Depends(require_roles("agora_admin", "agent"))):
    events = store.events()
    return {"events": events[-limit:]}


@app.post("/api/events")
def create_event(payload: EventCreate, user: User = Depends(current_user)):
    actor_id = payload.actor_id if user.role == "agora_admin" else user.id
    return store.record_event(Event(**payload.model_dump(exclude={"actor_id"}), actor_id=actor_id))


@app.get("/api/workspace/nodes")
def list_workspace_nodes(q: str | None = None, _: User = Depends(current_user)):
    if q:
        return {"nodes": store.workspace.search_nodes(q)}
    return {"nodes": store.workspace.list_all_nodes()}


@app.get("/api/workspace/nodes/{slug}")
def get_workspace_node(slug: str, _: User = Depends(current_user)):
    node = store.workspace.get_node(slug)
    if not node:
        raise HTTPException(status_code=404, detail="node not found")
    return node


@app.post("/api/workspace/nodes")
def create_workspace_node(payload: WorkspaceNodeCreate, user: User = Depends(require_roles("agora_admin", "employee"))):
    node = store.workspace.upsert_node(**payload.model_dump(), source_kind="manual")
    store.record_event(Event(event_type="workspace_node_upserted", actor_id=user.id, summary=node["title"], payload={"slug": node["slug"]}))
    return node


# ── Coordinator (LAIA AGORA) ──────────────────────────────────────────────

@app.get("/api/coordinator/report")
def coordinator_report(_: User = Depends(require_roles("agora_admin"))):
    tasks = store.tasks()
    agents_list = store.agents()
    try:
        lxd_agents = orchestrator.list_agents()
    except OrchestratorError:
        lxd_agents = []

    per_status: dict[str, int] = {}
    for t in tasks:
        per_status[t.status] = per_status.get(t.status, 0) + 1

    running = sum(1 for a in lxd_agents if (a.get("lxd_state") or "").upper() == "RUNNING")
    stopped = sum(1 for a in lxd_agents if (a.get("lxd_state") or "").upper() not in {"RUNNING", "unknown", ""})

    return {
        "coordinator": "LAIA AGORA",
        "container": "laia-agora",
        "status": "online",
        "tasks": {
            "total": len(tasks),
            "pending": per_status.get("pending", 0),
            "active": per_status.get("active", 0),
            "blocked": per_status.get("blocked", 0),
            "done": per_status.get("done", 0),
            "cancelled": per_status.get("cancelled", 0),
        },
        "agents": {
            "registered": len(agents_list),
            "running": running,
            "stopped": stopped,
            "planned": sum(1 for a in agents_list if a.status == "planned"),
            "details": [{
                "user_id": a.user_id,
                "container": a.container_name,
                "status": a.status,
                "lxd_state": next((la.get("lxd_state", "unknown") for la in lxd_agents if la.get("slug") == a.container_name.removeprefix("laia-")), "unknown"),
            } for a in agents_list],
        },
        "alerts": [
            f"Agente {a.container_name} con estado LXD '{(next((la.get('lxd_state','unknown') for la in lxd_agents if la.get('slug')==a.container_name.removeprefix('laia-')), 'unknown'))}' y status '{a.status}'"
            for a in agents_list
            if a.status != "running"
        ] if any(a.status != "running" for a in agents_list) else [],
        "recommendations": [
            "Crear el primer agente LXD real antes de abrir beta."
            if not agents_list or agents_list[0].status == "planned"
            else "Revisar agentes inactivos y tareas bloqueadas."
        ],
    }


@app.post("/api/coordinator/assign", status_code=201)
def coordinator_assign(payload: CoordinatorAssignRequest, _: User = Depends(require_roles("agora_admin"))):
    task = Task(
        title=payload.title,
        description=payload.description,
        assignee_id=None,
        priority=payload.priority,
    )
    tasks = store.tasks()
    tasks.append(task)
    store.save_tasks(tasks)
    store.record_event(Event(
        event_type="coordinator_task_assigned",
        actor_id="coordinator",
        summary=payload.title,
        payload={"task_id": task.id, "priority": payload.priority},
    ))
    return {"ok": True, "task": task}


@app.get("/api/coordinator/health")
def coordinator_health():
    return {
        "coordinator": "LAIA AGORA",
        "running": coordinator.is_running,
        "last_check": coordinator._last_check or "not yet",
        "check_interval_seconds": coordinator._check_interval,
    }


@app.get("/api/coordinator/alerts")
def coordinator_alerts(limit: int = 50, _: User = Depends(require_roles("agora_admin"))):
    return {"alerts": coordinator.get_alerts(limit=limit)}


@app.post("/api/coordinator/check")
def coordinator_force_check(_: User = Depends(require_roles("agora_admin"))):
    result = coordinator.run_check()
    store.record_event(Event(
        event_type="coordinator_check_forced",
        actor_id="coordinator",
        summary=f"Check manual: {result['agents_scanned']} agents, {result['alerts_generated']} alerts",
    ))
    return result


@app.get("/api/monitor/health")
def monitor_health():
    return monitor.health()


@app.post("/api/monitor/check")
def monitor_force_check(_: User = Depends(require_roles("agora_admin"))):
    result = monitor.run_check()
    return result


# ── Agent personal (current user) ──────────────────────────────────────────

@app.get("/api/agent/profile", response_model=AgentProfile)
def get_my_agent_profile(user: User = Depends(current_user)):
    slug = _resolve_agent_slug(user)
    try:
        result = orchestrator.get_agent_profile(slug)
    except OrchestratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result.get("stderr", "unknown error"))
    data = result["data"] or {}
    store.record_event(Event(event_type="agent_profile_read", actor_id=user.id, summary=f"{slug} profile read"))
    return AgentProfile(**data)


@app.patch("/api/agent/profile", response_model=AgentProfile)
def update_my_agent_profile(payload: AgentProfileUpdate, user: User = Depends(current_user)):
    slug = _resolve_agent_slug(user)
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="nothing to update")
    try:
        result = orchestrator.update_agent_profile(slug, update_data)
    except OrchestratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result.get("stderr", "unknown error"))
    data = result["data"] or {}
    store.record_event(Event(event_type="agent_profile_updated", actor_id=user.id, summary=f"{slug} profile updated", payload={"fields": list(update_data.keys())}))
    return AgentProfile(**data)


@app.get("/api/agent/status", response_model=AgentStatus)
def get_my_agent_status(user: User = Depends(current_user)):
    slug = _resolve_agent_slug(user)
    try:
        result = orchestrator.get_agent_status(slug)
    except OrchestratorError as exc:
        return AgentStatus(ok=False, slug=slug, container=f"laia-{slug}", runtime="error", healthcheck=str(exc))
    return AgentStatus(**result)


@app.get("/api/agent/tasks")
def list_my_agent_tasks(user: User = Depends(current_user)):
    slug = _resolve_agent_slug(user)
    container = f"laia-{slug}"
    import subprocess
    result = subprocess.run(
        ["lxc", "exec", container, "--",
         "sh", "-c",
         "for d in inbox done failed; do "
         "echo \"=== $d ===\"; "
         "ls /opt/laia/data/tasks/$d/ 2>/dev/null || true; "
         "done"],
        capture_output=True, text=True, timeout=10,
    )
    tasks = {"inbox": [], "done": [], "failed": []}
    current = None
    for line in result.stdout.strip().split("\n"):
        if line.startswith("=== "):
            section = line.replace("===", "").strip()
            current = tasks.get(section)
        elif line.strip().endswith(".json") and current is not None:
            current.append(line.strip().replace(".json", ""))
    return {"slug": slug, "tasks": tasks}


@app.patch("/api/agent", response_model=User)
def update_my_agent(payload: AgentUpdate, user: User = Depends(current_user)):
    if payload.display_name:
        user.display_name = payload.display_name
        users = store.users()
        for u in users:
            if u.id == user.id:
                u.display_name = payload.display_name
        store.save_users(users)
        store.record_event(Event(event_type="agent_updated", actor_id=user.id, summary=f"agent renamed to {payload.display_name}"))
    return public_user(user)


# ── Agents (admin fleet view) ────────────────────────────────────────────

@app.get("/api/agents")
def list_agents(user: User = Depends(current_user)):
    try:
        lxd_agents = orchestrator.list_agents()
    except OrchestratorError:
        lxd_agents = []
    agora_agents = store.agents()
    if user.role != "agora_admin":
        meu = next((a for a in agora_agents if a.user_id == user.id or a.id == user.agent_id), None)
        if meu is None:
            return {"agents": []}
        my_container = meu.container_name
        my_slug = my_container.removeprefix("laia-")
        lxd_agents = [a for a in lxd_agents if a.get("slug") == my_slug]
        if not lxd_agents:
            lxd_agents = [{"slug": my_slug, "container": my_container, "lxd_state": "unknown"}]
            try:
                result = orchestrator.get_agent_status(my_slug)
                if result.get("ok"):
                    lxd_agents[0].update(result)
            except OrchestratorError:
                pass
    return {"agents": lxd_agents}


@app.get("/api/agents/{slug}")
def get_agent(slug: str, _: User = Depends(require_roles("agora_admin"))):
    try:
        agent = orchestrator.get_agent(slug)
    except OrchestratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return agent


@app.post("/api/agents/register", status_code=201)
def register_provisioned_agent(payload: RegisterAgentRequest, user: User = Depends(require_roles("agora_admin"))):
    """Register an already-provisioned LXD container in the AGORA DB.

    The admin first runs `bash infra/lxd/scripts/create-agent.sh <slug>` on the host
    (which produces a JSON line with container_ip + api_token), then posts that JSON
    here. AGORA from that point onward talks to the child over HTTP using the token.
    """
    target_user = next((u for u in store.users() if u.id == payload.user_id), None)
    if target_user is None:
        raise HTTPException(status_code=404, detail=f"user not found: {payload.user_id}")
    if target_user.agent_id:
        raise HTTPException(
            status_code=409,
            detail=(
                f"user {target_user.username!r} already has agent "
                f"{target_user.agent_id!r}. Unlink first with "
                f"PATCH /api/users/{target_user.id} (set agent_id=null) "
                f"or DELETE /api/agents/{target_user.agent_id} before re-registering."
            ),
        )
    agent = Agent(
        id=new_id("agent"),
        user_id=payload.user_id,
        container_name=f"laia-{payload.slug}",
        status="running",
        workspace_path="/opt/laia/workspaces/personal/workspace.db",
        container_ip=payload.container_ip,
        api_token=payload.api_token,
    )
    store.save_agent(agent)
    target_user.agent_id = agent.id
    store.save_user(target_user)
    store.record_event(Event(
        event_type="agent_registered",
        actor_id=user.id,
        summary=payload.slug,
        payload={"agent_id": agent.id, "user_id": payload.user_id, "ip": payload.container_ip},
    ))
    return {"ok": True, "agent": agent}


@app.post("/api/agents/{slug}/secrets", response_model=SecretsFetchResponse)
def fetch_agent_secrets(slug: str, payload: SecretsFetchRequest):
    """Agora Agent calls this on startup to fetch its LLM API key.

    Auth: payload.bootstrap_token must match the api_token registered for the
    agent in the DB. NOT a JWT-protected endpoint because the child container
    has no JWT — it only has its bootstrap token from agent.json.
    """
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,30}", slug):
        raise HTTPException(status_code=400, detail="invalid slug")

    container_name = f"laia-{slug}"
    target = next(
        (a for a in store.agents() if a.container_name == container_name),
        None,
    )
    if target is None:
        # Don't reveal whether the agent exists — same response as bad token.
        raise HTTPException(status_code=401, detail="invalid bootstrap token")
    if not target.api_token or target.api_token != payload.bootstrap_token:
        raise HTTPException(status_code=401, detail="invalid bootstrap token")

    # Pick the first LLM key available on this host. Sprint 2 shares one key
    # across all Agora Agents; sprint 3+ can introduce per-agent keys.
    for provider, env_var in (
        ("deepseek", "DEEPSEEK_API_KEY"),
        ("openrouter", "OPENROUTER_API_KEY"),
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("openai", "OPENAI_API_KEY"),
    ):
        key = os.environ.get(env_var, "").strip()
        if key:
            store.record_event(Event(
                event_type="agent_secret_fetched",
                actor_id=None,
                summary=slug,
                payload={"provider": provider, "agent_id": target.id},
            ))
            return SecretsFetchResponse(llm_api_key=key, llm_provider=provider)

    raise HTTPException(
        status_code=503,
        detail="no LLM API key configured on AGORA host (set OPENROUTER_API_KEY)",
    )


@app.post("/api/agents", status_code=201)
def create_agent(payload: CreateAgentRequest, user: User = Depends(require_roles("agora_admin"))):
    try:
        result = orchestrator.create_agent(payload.slug)
    except OrchestratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result.get("error") or result.get("output"))
    store.record_event(Event(event_type="agent_created", actor_id=user.id, summary=payload.slug))
    if payload.install_runtime:
        try:
            rt = orchestrator.install_runtime(payload.slug)
        except OrchestratorError as exc:
            return {"ok": True, "slug": payload.slug, "runtime_warning": str(exc)}
        if not rt["ok"]:
            return {"ok": True, "slug": payload.slug, "runtime_warning": rt.get("error")}
    if payload.init_workspace:
        try:
            orchestrator.init_workspace(payload.slug)
        except OrchestratorError:
            pass
    if payload.initial_snapshot:
        try:
            orchestrator.snapshot_agent(payload.slug, "initial")
        except OrchestratorError:
            pass
    return {"ok": True, "slug": payload.slug}


@app.post("/api/agents/{slug}/start")
def start_agent(slug: str, _: User = Depends(require_roles("agora_admin"))):
    try:
        return orchestrator.start_agent(slug)
    except OrchestratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/agents/{slug}/stop")
def stop_agent(slug: str, _: User = Depends(require_roles("agora_admin"))):
    try:
        return orchestrator.stop_agent(slug)
    except OrchestratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/agents/{slug}/restart")
def restart_agent(slug: str, _: User = Depends(require_roles("agora_admin"))):
    try:
        return orchestrator.restart_agent(slug)
    except OrchestratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class ChatProxyRequest(BaseModel):
    message: str = PydField(min_length=1, max_length=20_000)
    session_id: str | None = None


def _agent_client_for_slug(slug: str):
    """Locate the Agent record for slug and build an AgentClient (HTTPS to child)."""
    from .agent_client import AgentClient
    container = f"laia-{slug}"
    target = next((a for a in store.agents() if a.container_name == container), None)
    if target is None:
        raise HTTPException(status_code=404, detail=f"agent {slug!r} not registered")
    if not target.container_ip or not target.api_token:
        raise HTTPException(
            status_code=503,
            detail=f"agent {slug!r} not provisioned yet (no container_ip / api_token)",
        )
    return AgentClient(slug=slug, host=target.container_ip, token=target.api_token)


# Note: /api/agents/me/chat must be declared BEFORE /api/agents/{slug}/chat
# so FastAPI doesn't match "me" as a slug.
@app.post("/api/agents/me/chat")
async def chat_with_my_agent(payload: ChatProxyRequest, user: User = Depends(current_user)):
    """Employee path: chat with the agent linked to the current user.

    Replaces the sprint-2 relay (proxy SSE to ``/chat`` on the user's
    container, which no longer exists). The handler now drives an in-process
    AIAgent from :class:`AgentPool`; tool calls are routed back to the
    user's executor through the forwarder plugin.
    """
    if not user.agent_id:
        raise HTTPException(status_code=404, detail="no agent linked to your user")
    agent = next((a for a in store.agents() if a.id == user.agent_id), None)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent record missing")

    from .chat_engine import chat_stream
    return StreamingResponse(
        chat_stream(user=user, agent=agent, message=payload.message, session_id=payload.session_id),
        media_type="text/event-stream",
    )


@app.post("/api/agents/{slug}/chat")
async def chat_with_agent_admin(
    slug: str,
    payload: ChatProxyRequest,
    user: User = Depends(require_roles("agora_admin")),
):
    """Admin path: chat with any registered agent.

    The admin acts as the LLM identity but the tool calls still hit the
    target user's executor, so the admin can debug a user's agent without
    touching the user's password.
    """
    container = f"laia-{slug}"
    agent = next((a for a in store.agents() if a.container_name == container), None)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"agent {slug!r} not registered")
    target_user = store.user_by_id(agent.user_id) if agent.user_id else user
    if target_user is None:
        target_user = user

    from .chat_engine import chat_stream
    return StreamingResponse(
        chat_stream(user=target_user, agent=agent, message=payload.message, session_id=payload.session_id),
        media_type="text/event-stream",
    )


@app.post("/api/agents/{slug}/snapshot")
def snapshot_agent(slug: str, payload: SnapshotRequest, _: User = Depends(require_roles("agora_admin"))):
    try:
        return orchestrator.snapshot_agent(slug, payload.name)
    except OrchestratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/agents/{slug}/snapshots")
def list_snapshots(slug: str, _: User = Depends(require_roles("agora_admin"))):
    import subprocess, re
    container = f"laia-{slug}"
    try:
        r = subprocess.run(["lxc", "info", container], capture_output=True, text=True, timeout=10)
        snapshots = []
        for line in r.stdout.split("\n"):
            m = re.match(r"\s+(\S+)\s+\(taken at (.+?)\s+\S+\)", line)
            if m:
                snapshots.append({"name": m.group(1), "taken_at": m.group(2)})
        return {"snapshots": snapshots}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="lxc timeout")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/agents/{slug}/restore")
def restore_snapshot(slug: str, payload: SnapshotRequest, _: User = Depends(require_roles("agora_admin"))):
    import subprocess
    container = f"laia-{slug}"
    try:
        r = subprocess.run(
            ["lxc", "restore", container, payload.name],
            capture_output=True, text=True, timeout=60,
        )
        return {"ok": r.returncode == 0, "output": r.stdout, "error": r.stderr}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/agents/{slug}/logs")
def get_agent_logs(slug: str, _: User = Depends(require_roles("agora_admin"))):
    try:
        return orchestrator.get_agent_logs(slug)
    except OrchestratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/agents/{slug}/tasks", status_code=202)
def send_agent_task(slug: str, payload: AgentTaskCreate, user: User = Depends(require_roles("agora_admin"))):
    try:
        result = orchestrator.send_task(slug, payload.task_type, payload.payload)
    except OrchestratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result.get("error"))
    store.record_event(Event(event_type="agent_task_sent", actor_id=user.id, summary=f"{slug}/{payload.task_type}", payload={"task_id": result.get("task_id")}))
    return result


@app.get("/api/agents/{slug}/tasks/{task_id}")
def get_agent_task_result(slug: str, task_id: str, _: User = Depends(require_roles("agora_admin"))):
    try:
        result = orchestrator.read_task_result(slug, task_id)
    except OrchestratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail="task result not yet available")
    return result


@app.post("/api/agents/{slug}/install-runtime")
def install_agent_runtime(slug: str, _: User = Depends(require_roles("agora_admin"))):
    try:
        return orchestrator.install_runtime(slug)
    except OrchestratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/api/agents/{slug}")
def delete_agent(slug: str, _: User = Depends(require_roles("agora_admin"))):
    try:
        return orchestrator.delete_agent(slug)
    except OrchestratorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/fleet/status")
def fleet_status_endpoint(_: User = Depends(require_roles("agora_admin"))):
    agents_list = store.agents()
    try:
        lxd_agents = orchestrator.list_agents()
    except OrchestratorError:
        lxd_agents = []
    result = []
    for a in agents_list:
        slug = a.container_name.removeprefix("laia-")
        lxd = next((la for la in lxd_agents if la.get("slug") == slug), {})
        result.append({
            "slug": slug,
            "container": a.container_name,
            "user_id": a.user_id,
            "status": a.status,
            "lxd_state": lxd.get("lxd_state", "unknown"),
            "ipv4": lxd.get("ipv4", ""),
            "snapshots": lxd.get("snapshots", "0"),
        })
    return {"agents": result, "total": len(result)}


# ── SPA fallback (serve frontend) ─────────────────────────────────────────

from fastapi.staticfiles import StaticFiles
from pathlib import Path

_frontend_dist = settings.laia_root / "laia-ui" / "packages" / "agora-app" / "dist"

if _frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="assets")

    @app.get("/{catchall:path}")
    async def serve_spa(catchall: str):
        index_path = _frontend_dist / "index.html"
        if index_path.exists() and not catchall.startswith("api/"):
            return FileResponse(str(index_path))
        raise HTTPException(status_code=404, detail="not found")


# ── WebSocket ──────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = ""):
    if not token:
        await ws.close(code=4001, reason="missing token")
        return
    try:
        payload = verify_token(token, settings.jwt_secret)
    except ValueError:
        await ws.close(code=4001, reason="invalid token")
        return
    user_id = payload.get("sub")
    if not user_id:
        await ws.close(code=4001, reason="invalid token payload")
        return

    user = store.user_by_id(user_id)
    if not user:
        await ws.close(code=4001, reason="user not found")
        return

    await ws_manager.connect(ws, user_id)
    await ws.send_json({"type": "connected", "user_id": user_id, "role": user.role})

    import asyncio

    async def _push():
        while True:
            items = drain_broadcasts()
            for item in items:
                if item["type"] == "coordinator_alert" and user.role == "agora_admin":
                    await ws.send_json(item)
            await asyncio.sleep(3)

    push_task = asyncio.create_task(_push())

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "")
            if msg_type == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        push_task.cancel()
        await ws_manager.disconnect(ws, user_id)


async def broadcast_agent_alert(summary: str, level: str = "info", agent: str = "") -> None:
    await ws_manager.broadcast_event(
        "coordinator_alert",
        {"level": level, "message": summary, "agent": agent},
        target_roles={"agora_admin"},
    )
