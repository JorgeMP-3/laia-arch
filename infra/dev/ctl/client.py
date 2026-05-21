"""Async HTTP client for the AGORA backend.

Mirrors the API surface of the legacy ``AgoraAdminClient`` in
``agora-control-center-tui.py`` but is built on ``httpx.AsyncClient`` so
each call doesn't block the Textual event loop, and shares a TTL cache
so back-to-back screen mounts don't refetch unchanged data.

Cache contract
--------------
* GETs go through the cache (default TTL 5 s).
* Mutating verbs (POST/PATCH/DELETE/PUT) bypass the cache *and* invalidate
  every cached entry whose path starts with the request path's parent —
  conservative but cheap, and avoids stale reads after admin operations.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from .cache import TTLCache


logger = logging.getLogger(__name__)

DEFAULT_API_URL = os.environ.get("AGORA_API_URL", "http://127.0.0.1:8088")
SESSION_PATH = Path(os.environ.get(
    "AGORA_SESSION_PATH",
    str(Path.home() / ".laia" / "admin-session.json"),
))


class ApiError(RuntimeError):
    def __init__(self, status: int | None, message: str) -> None:
        super().__init__(message)
        self.status = status


def load_session_token() -> str | None:
    """Read the admin token from ``~/.laia/admin-session.json`` if present."""
    try:
        data = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    tok = data.get("token") or data.get("access_token")
    return str(tok) if tok else None


def save_session_token(token: str) -> None:
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSION_PATH.write_text(
        json.dumps({"token": token}, ensure_ascii=False),
        encoding="utf-8",
    )
    try:
        SESSION_PATH.chmod(0o600)
    except OSError:
        pass


def clear_session_token() -> None:
    try:
        SESSION_PATH.unlink()
    except FileNotFoundError:
        pass


class AgoraClient:
    """Async client. One instance per Textual App."""

    def __init__(self, api_url: str = DEFAULT_API_URL,
                 token: str | None = None,
                 timeout: float = 10.0,
                 cache_ttl_seconds: float = 5.0) -> None:
        self.api_url = api_url.rstrip("/")
        self.token = token
        self._cache = TTLCache(default_ttl_seconds=cache_ttl_seconds)
        self._http = httpx.AsyncClient(base_url=self.api_url, timeout=timeout)

    async def close(self) -> None:
        await self._http.aclose()

    # ── auth ──────────────────────────────────────────────────────────────

    async def login(self, username: str, password: str) -> dict[str, Any]:
        body = await self._raw("POST", "/api/login",
                                payload={"username": username, "password": password},
                                auth=False)
        tok = body.get("access_token")
        if not tok:
            raise ApiError(None, "login response missing access_token")
        self.token = str(tok)
        self._cache.invalidate()
        return body

    # ── core request ──────────────────────────────────────────────────────

    async def _raw(self, method: str, path: str, *,
                   payload: dict[str, Any] | None = None,
                   auth: bool = True) -> dict[str, Any]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if auth:
            if not self.token:
                raise ApiError(401, "missing admin token")
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            if payload is None:
                resp = await self._http.request(method, path, headers=headers)
            else:
                resp = await self._http.request(method, path,
                                                 headers=headers, json=payload)
        except httpx.RequestError as exc:
            raise ApiError(None, str(exc)) from exc
        if resp.status_code >= 400:
            raw = resp.text
            try:
                detail = resp.json().get("detail")
                if isinstance(detail, dict):
                    msg = detail.get("error") or json.dumps(detail)
                else:
                    msg = detail or raw
            except Exception:
                msg = raw or resp.reason_phrase
            raise ApiError(resp.status_code, str(msg))
        if not resp.content:
            return {}
        try:
            data = resp.json()
        except Exception:
            return {"raw": resp.text}
        # Always return a dict for caller ergonomics; wrap top-level lists.
        if isinstance(data, list):
            return {"data": data}
        return data

    async def request(self, method: str, path: str, *,
                      payload: dict[str, Any] | None = None,
                      auth: bool = True,
                      cache: bool = True,
                      cache_ttl: float | None = None) -> dict[str, Any]:
        method_u = method.upper()
        if method_u == "GET" and cache:
            hit = self._cache.get(method_u, path)
            if hit is not None:
                return hit
        result = await self._raw(method_u, path, payload=payload, auth=auth)
        if method_u == "GET" and cache:
            self._cache.set(method_u, path, result, ttl=cache_ttl)
        else:
            # Mutation: invalidate the parent path so subsequent reads
            # see the new state. E.g. PATCH /api/admin/users/X/budget
            # invalidates /api/admin/users and /api/admin/usage too.
            self._cache.invalidate(path_prefix="/api/admin")
            self._cache.invalidate(path_prefix="/api/me")
        return result

    # ── thin wrappers used across screens (parity with curses TUI) ────────

    async def health(self) -> dict[str, Any]:
        return await self.request("GET", "/api/health", auth=False)

    async def status(self) -> dict[str, Any]:
        return await self.request("GET", "/api/admin/status")

    async def users(self) -> dict[str, Any]:
        return await self.request("GET", "/api/admin/users")

    async def containers(self) -> dict[str, Any]:
        return await self.request("GET", "/api/admin/containers")

    async def jobs(self) -> dict[str, Any]:
        return await self.request("GET", "/api/admin/jobs?limit=100")

    async def usage(self, *, user_id: str | None = None,
                    window: str = "day") -> dict[str, Any]:
        suffix = f"?window={window}"
        if user_id:
            from urllib.parse import quote
            suffix += f"&user_id={quote(user_id, safe='')}"
        return await self.request("GET", f"/api/admin/usage{suffix}")

    async def user_budget(self, user_id: str) -> dict[str, Any]:
        return await self.request(
            "GET", f"/api/admin/users/{user_id}/budget")

    # v2 batch endpoints (Phase B) — kill the N+1 of the legacy TUI.

    async def users_overview(self, *, window: str = "day") -> dict[str, Any]:
        return await self.request(
            "GET", f"/api/admin/users-overview?window={window}")

    async def scheduled_jobs(self, user_id: str) -> dict[str, Any]:
        return await self.request(
            "GET", f"/api/admin/users/{user_id}/scheduled-jobs")

    async def child_runs(self, user_id: str, *, limit: int = 20) -> dict[str, Any]:
        return await self.request(
            "GET", f"/api/admin/users/{user_id}/child-runs?limit={limit}")

    # ── shared read endpoints ─────────────────────────────────────────────

    async def logs(self, source: str, *, lines: int = 120) -> dict[str, Any]:
        return await self.request(
            "GET", f"/api/admin/logs/{source}?lines={lines}")

    async def audit(self, *, user_id: str | None = None,
                    limit: int = 120) -> dict[str, Any]:
        suffix = f"?limit={limit}"
        if user_id:
            from urllib.parse import quote
            suffix += f"&user_id={quote(user_id, safe='')}"
        return await self.request("GET", f"/api/admin/audit/tools{suffix}")

    async def errors(self, *, limit: int = 100) -> dict[str, Any]:
        return await self.request(
            "GET", f"/api/admin/errors?limit={limit}")

    async def containers_list(self) -> dict[str, Any]:
        return await self.containers()

    async def marketplace_pending(self) -> dict[str, Any]:
        return await self.request("GET", "/api/admin/marketplace/pending")

    async def plugins_catalog(self) -> dict[str, Any]:
        return await self.request("GET", "/api/plugins/catalog")

    async def skills_catalog(self) -> dict[str, Any]:
        return await self.request("GET", "/api/skills/catalog")

    async def agent_area_for_user(self, user_id: str) -> dict[str, Any]:
        return await self.request(
            "GET", f"/api/admin/users/{user_id}/agent-area")

    async def laia_inbox_count(self) -> dict[str, Any]:
        return await self.request("GET", "/api/laia/inbox-count")
