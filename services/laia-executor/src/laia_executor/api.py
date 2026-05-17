"""FastAPI app for the executor."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from laia_executor import __version__
from laia_executor.auth import require_bearer_token
from laia_executor.config import ExecutorConfig
from laia_executor.tools.registry import default_registry, ToolRegistry


START_TIME = time.time()

# Maximum body size accepted by /exec. AGORA never legitimately sends more
# than a few MB (file contents, patches). Bigger is either misuse or attack
# (memory exhaustion). 10 MB is generous enough for `apply_patch` on large
# files but small enough to refuse runaway clients.
MAX_REQUEST_BODY_BYTES = int(os.environ.get("LAIA_EXECUTOR_MAX_BODY_BYTES", 10 * 1024 * 1024))


class _BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose body exceeds ``MAX_REQUEST_BODY_BYTES``.

    Checks ``Content-Length`` upfront, falls back to reading the body to
    enforce the limit when the header is missing. Returns 413 (Payload Too
    Large) so the forwarder can surface a clear error to the LLM instead
    of OOMing the executor.
    """

    def __init__(self, app, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_bytes:
                    return Response(
                        status_code=413,
                        content=f"request body exceeds {self.max_bytes} bytes",
                        media_type="text/plain",
                    )
            except ValueError:
                pass  # malformed header: let downstream handle it
        return await call_next(request)


class ExecRequest(BaseModel):
    tool: str = Field(..., min_length=1)
    args: dict[str, Any] = Field(default_factory=dict)
    request_id: str = Field(..., min_length=1)


class ExecResponse(BaseModel):
    ok: bool
    result: str | None = None
    error: str | None = None
    request_id: str


class ProfileResponse(BaseModel):
    slug: str
    version: str
    uptime_seconds: float
    bind_host: str
    bind_port: int
    tools: list[str]


def build_app(config: ExecutorConfig | None = None, registry: ToolRegistry | None = None) -> FastAPI:
    cfg = config or ExecutorConfig.load()
    reg = registry or default_registry
    require_token = require_bearer_token(cfg.token)

    app = FastAPI(title="laia-executor", version=__version__)
    app.add_middleware(_BodySizeLimitMiddleware, max_bytes=MAX_REQUEST_BODY_BYTES)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/profile", response_model=ProfileResponse, dependencies=[Depends(require_token)])
    async def profile() -> ProfileResponse:
        return ProfileResponse(
            slug=cfg.slug,
            version=__version__,
            uptime_seconds=time.time() - START_TIME,
            bind_host=cfg.bind_host,
            bind_port=cfg.bind_port,
            tools=reg.list_tools(),
        )

    @app.post("/exec", response_model=ExecResponse, dependencies=[Depends(require_token)])
    async def exec_tool(req: ExecRequest) -> ExecResponse:
        if not reg.has(req.tool):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"unknown tool: {req.tool}",
            )
        try:
            result = await reg.call(req.tool, req.args)
        except TypeError as exc:
            return ExecResponse(ok=False, error=f"bad args: {exc}", request_id=req.request_id)
        except Exception as exc:
            return ExecResponse(ok=False, error=f"tool raised: {exc}", request_id=req.request_id)
        return ExecResponse(ok=True, result=result, request_id=req.request_id)

    @app.get("/workspace/files", dependencies=[Depends(require_token)])
    async def workspace_files(path: str = "/home/user") -> dict[str, Any]:
        p = Path(os.path.expanduser(path))
        if not p.exists():
            raise HTTPException(status_code=404, detail="path not found")
        if not p.is_dir():
            raise HTTPException(status_code=400, detail="not a directory")
        entries = []
        for entry in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
            entries.append({
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else None,
            })
        return {"path": str(p), "entries": entries}

    return app
