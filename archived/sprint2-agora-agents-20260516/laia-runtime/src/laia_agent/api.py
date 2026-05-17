"""HTTP API of a LAIA child agent.

Each child container runs this FastAPI server on port 9090 (bridged on the
LXD network, not exposed to the outside world). AGORA reaches it from the
host over HTTP — replacing the previous `lxc exec` channel.

Endpoints:
  GET  /health             — readiness probe (no auth required)
  GET  /status             — runtime status (daemon, last task, errors)
  GET  /profile            — full profile (persona, instructions, skills, prefs)
  PUT  /profile            — partial update of profile
  POST /tasks              — enqueue a task in inbox/, returns {id, status:queued}
  GET  /tasks/{task_id}    — read result from done/ or failed/, or pending
  POST /chat               — start a conversational turn; returns SSE stream

Authentication: Bearer token from config (api_token). /health is unauthenticated.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Header, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .agent_wrapper import AgentWrapper, fetch_llm_secret_from_agora
from .config import AgentConfig, load_config
from .plugin_loader import DEFAULT_PLUGINS_ROOT
from .profile import ensure_profile, get_profile, update_profile
from .status import read_json
from .tasks import ensure_task_dirs

logger = logging.getLogger(__name__)


class ProfilePatch(BaseModel):
    persona: str | None = None
    instructions: str | None = None
    skills: dict | None = None
    preferences: dict | None = None
    model_config = {"extra": "allow"}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    session_id: str | None = None


class PluginUploadRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]{0,62}$")
    manifest: dict[str, Any] = Field(default_factory=dict)
    code_b64: str = Field(min_length=1, max_length=2_000_000)  # ~1.4MB raw cap


class TaskSubmit(BaseModel):
    type: str = Field(min_length=1, max_length=64)
    payload: dict = Field(default_factory=dict)


def create_app(
    config: AgentConfig | None = None,
    agent_wrapper_factory=None,
) -> FastAPI:
    """Build the FastAPI app for a given config (defaults to /opt/laia/agent.json)."""
    cfg = config or load_config()
    app = FastAPI(title=f"laia-agent ({cfg.employee})", version="0.1.0")

    # ── auth dependency ──────────────────────────────────────────────────────

    def require_token(authorization: str = Header(default="")) -> None:
        # Server with empty token = open mode (only for tests/dev; never set in prod).
        if not cfg.api_token:
            return
        prefix = "Bearer "
        if not authorization.startswith(prefix):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
        token = authorization[len(prefix):].strip()
        if token != cfg.api_token:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")

    # ── /health (unauthenticated) ────────────────────────────────────────────

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "slug": cfg.employee,
            "container": cfg.container,
        }

    # ── /status ──────────────────────────────────────────────────────────────

    @app.get("/status", dependencies=[Depends(require_token)])
    def status_endpoint() -> dict[str, Any]:
        status_file = cfg.data_dir / "status.json"
        last_status = read_json(status_file) if status_file.exists() else {}
        return {
            "slug": cfg.employee,
            "container": cfg.container,
            "runtime": last_status.get("status", "unknown"),
            "last_heartbeat": last_status.get("last_heartbeat"),
            "tasks_processed": last_status.get("tasks_processed", 0),
            "errors": last_status.get("errors", 0),
        }

    # ── /profile ─────────────────────────────────────────────────────────────

    @app.get("/profile", dependencies=[Depends(require_token)])
    def get_agent_profile() -> dict[str, Any]:
        ensure_profile(cfg)
        return get_profile(cfg)

    @app.put("/profile", dependencies=[Depends(require_token)])
    def put_agent_profile(patch: ProfilePatch) -> dict[str, Any]:
        ensure_profile(cfg)
        payload = patch.model_dump(exclude_unset=True)
        if not payload:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty patch")
        return update_profile(cfg, payload)

    # ── /tasks ───────────────────────────────────────────────────────────────

    @app.post("/tasks", dependencies=[Depends(require_token)])
    def submit_task(req: TaskSubmit) -> dict[str, Any]:
        ensure_task_dirs(cfg)
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        body = {
            "id": task_id,
            "type": req.type,
            "payload": req.payload,
            "created_at": int(time.time()),
        }
        target = cfg.data_dir / "tasks" / "inbox" / f"{task_id}.json"
        target.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        return {"id": task_id, "status": "queued"}

    @app.get("/tasks/{task_id}", dependencies=[Depends(require_token)])
    def get_task(task_id: str) -> dict[str, Any]:
        # Done / failed
        for folder in ("done", "failed"):
            p = cfg.data_dir / "tasks" / folder / f"{task_id}.json"
            if p.exists():
                try:
                    return json.loads(p.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                                        "result file is corrupted")
        # Still in inbox
        inbox = cfg.data_dir / "tasks" / "inbox" / f"{task_id}.json"
        if inbox.exists():
            return {"id": task_id, "status": "pending"}
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task not found")

    # ── /chat (SSE streaming, conversational) ────────────────────────────────

    # Map session_id -> AgentWrapper. Single-process; not shared across workers.
    _sessions: dict[str, "AgentWrapper"] = {}

    def _make_wrapper(slug: str) -> "AgentWrapper":
        if agent_wrapper_factory is not None:
            return agent_wrapper_factory(slug)
        # Fetch the real LLM API key from AGORA using bootstrap token
        llm_key, llm_provider = fetch_llm_secret_from_agora(
            slug=slug,
            bootstrap_token=cfg.api_token,
            agora_url=cfg.agora_backend_url,
        )
        logger.info("fetched LLM secret for %s: provider=%s", slug, llm_provider)
        return AgentWrapper(
            slug=slug,
            api_key=llm_key,
            provider=llm_provider,
            enabled_toolsets=["agora-agent"],
            workspace_dir=cfg.workspace_dir,
        )

    @app.post("/chat", dependencies=[Depends(require_token)])
    def chat(req: ChatRequest) -> StreamingResponse:
        sid = req.session_id or uuid.uuid4().hex[:12]
        wrapper = _sessions.get(sid)
        if wrapper is None:
            try:
                wrapper = _make_wrapper(cfg.employee)
            except Exception as exc:
                logger.exception("Failed to construct AgentWrapper")
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    f"agent unavailable: {exc}",
                )
            _sessions[sid] = wrapper

        async def event_stream() -> AsyncIterator[bytes]:
            # First line: send the session id so the client can resume.
            yield f"event: session\ndata: {json.dumps({'session_id': sid})}\n\n".encode()
            async for event in wrapper.chat_stream(req.message):
                payload = json.dumps(event, ensure_ascii=False)
                ev_type = event.get("type", "message")
                yield f"event: {ev_type}\ndata: {payload}\n\n".encode()

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # ── /plugins (Python tier 1) ────────────────────────────────────────────

    def _plugins_root() -> Path:
        # Allow override (tests); default to /opt/laia/plugins
        env_override = os.environ.get("LAIA_PLUGINS_ROOT")
        if env_override:
            return Path(env_override)
        return DEFAULT_PLUGINS_ROOT

    @app.get("/plugins", dependencies=[Depends(require_token)])
    def list_plugins_endpoint() -> dict[str, Any]:
        root = _plugins_root()
        if not root.is_dir():
            return {"plugins": []}
        items = []
        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name.startswith((".", "_")):
                continue
            manifest_path = child / "manifest.yaml"
            manifest = {}
            if manifest_path.is_file():
                try:
                    for line in manifest_path.read_text().splitlines():
                        if ":" in line and not line.strip().startswith("#"):
                            k, _, v = line.partition(":")
                            manifest[k.strip()] = v.strip().strip('"').strip("'")
                except Exception:
                    pass
            items.append({"name": child.name, "manifest": manifest})
        return {"plugins": items}

    @app.post("/plugins", dependencies=[Depends(require_token)])
    def upload_plugin(req: PluginUploadRequest) -> dict[str, Any]:
        import base64
        import io
        import zipfile

        root = _plugins_root()
        root.mkdir(parents=True, exist_ok=True)
        target = root / req.name
        if target.exists():
            raise HTTPException(status.HTTP_409_CONFLICT, f"plugin {req.name!r} already exists")
        try:
            zip_bytes = base64.b64decode(req.code_b64, validate=True)
        except Exception as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"invalid code_b64: {exc}")
        if len(zip_bytes) > 5_000_000:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "plugin too large (max 5MB)")
        try:
            zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        except zipfile.BadZipFile:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "code_b64 is not a valid zip")

        target.mkdir(parents=True)
        try:
            for member in zf.namelist():
                if member.startswith("/") or ".." in member.split("/"):
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unsafe zip entry: {member}")
                zf.extract(member, target)
        except HTTPException:
            import shutil
            shutil.rmtree(target, ignore_errors=True)
            raise

        # Write manifest from request body (overrides any in the zip).
        manifest = {**req.manifest, "name": req.name, "language": req.manifest.get("language", "python")}
        manifest_lines = [f"{k}: {v}" for k, v in manifest.items()]
        (target / "manifest.yaml").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

        return {"ok": True, "name": req.name, "path": str(target)}

    @app.delete("/plugins/{name}", dependencies=[Depends(require_token)])
    def delete_plugin(name: str) -> dict[str, Any]:
        import re
        import shutil

        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", name):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid plugin name")
        target = _plugins_root() / name
        if not target.is_dir():
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"plugin {name!r} not found")
        shutil.rmtree(target)
        return {"ok": True, "name": name}

    return app


# Module-level app for uvicorn entrypoint (`uvicorn laia_agent.api:app`).
app = create_app()
