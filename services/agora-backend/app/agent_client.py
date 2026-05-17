"""HTTP client for talking to a child agent's API.

Each child agent (laia-{slug} container) exposes a FastAPI server on port 9090
inside the LXD bridge network. AGORA reaches it over HTTP — never via `lxc exec`.

This module is the only place where HTTP requests to children are made.
Authentication is per-agent Bearer token (stored on the Agent model).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_PORT = 9091
DEFAULT_TIMEOUT = 10.0  # seconds — short because children are on local bridge
DEFAULT_TASK_POLL_TIMEOUT = 30.0  # how long get_task_result waits before giving up


class AgentClientError(Exception):
    """Raised when an HTTP call to a child agent fails."""


class AgentUnreachableError(AgentClientError):
    """Connection refused / DNS / timeout — the child is not responding."""


class AgentAuthError(AgentClientError):
    """401/403 — bad or missing token."""


class AgentNotFoundError(AgentClientError):
    """404 — resource (task, profile) not found at the child."""


class AgentClient:
    """Async HTTP client for a single child agent.

    Construct one per (slug, ip, token) triplet. Reuse the underlying httpx
    AsyncClient via the orchestrator-level pool if many requests are needed.
    """

    def __init__(
        self,
        slug: str,
        host: str,
        token: str,
        *,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not host:
            raise AgentClientError(f"agent {slug!r} has no host/IP")
        if not token:
            raise AgentClientError(f"agent {slug!r} has no api_token")
        self.slug = slug
        self.host = host
        self.port = port
        self.token = token
        self.timeout = timeout
        self._client = client
        self._owns_client = client is None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    # ── lifecycle ─────────────────────────────────────────────────────────────

    async def __aenter__(self) -> "AgentClient":
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self

    async def __aexit__(self, *args) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── low-level helper ──────────────────────────────────────────────────────

    async def _request(self, method: str, path: str, **kw) -> httpx.Response:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
            self._owns_client = True
        try:
            resp = await self._client.request(method, path, headers=self._headers, **kw)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            raise AgentUnreachableError(
                f"{self.slug}: {method} {path} unreachable: {exc}"
            ) from exc
        except httpx.HTTPError as exc:
            raise AgentClientError(
                f"{self.slug}: {method} {path} failed: {exc}"
            ) from exc
        if resp.status_code in (401, 403):
            raise AgentAuthError(f"{self.slug}: auth failed ({resp.status_code})")
        if resp.status_code == 404:
            raise AgentNotFoundError(f"{self.slug}: {path} not found")
        if resp.status_code >= 500:
            raise AgentClientError(
                f"{self.slug}: {method} {path} returned {resp.status_code}: {resp.text[:200]}"
            )
        return resp

    # ── public API ────────────────────────────────────────────────────────────

    async def health(self) -> dict[str, Any]:
        """GET /health — readiness probe. Returns {status, slug, version?}."""
        resp = await self._request("GET", "/health")
        return resp.json()

    async def status(self) -> dict[str, Any]:
        """GET /status — runtime status (daemon vivo, last task, error count)."""
        resp = await self._request("GET", "/status")
        return resp.json()

    async def get_profile(self) -> dict[str, Any]:
        """GET /profile — full agent profile (persona, instructions, skills, prefs)."""
        resp = await self._request("GET", "/profile")
        return resp.json()

    async def update_profile(self, patch: dict[str, Any]) -> dict[str, Any]:
        """PUT /profile — partial update of the profile."""
        resp = await self._request("PUT", "/profile", json=patch)
        return resp.json()

    async def submit_task(self, task_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST /tasks — enqueue a task. Returns {id, status='queued'}."""
        body = {"type": task_type, "payload": payload}
        resp = await self._request("POST", "/tasks", json=body)
        return resp.json()

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        """GET /tasks/{id} — returns result dict, or None if still pending."""
        try:
            resp = await self._request("GET", f"/tasks/{task_id}")
        except AgentNotFoundError:
            return None
        data = resp.json()
        # Server convention: returns 200 with {status: "pending"} while in inbox.
        return data

    async def chat_stream(
        self,
        message: str,
        session_id: str | None = None,
    ):
        """Open POST /chat and yield raw SSE chunks as bytes.

        Returns an async iterator of bytes. The caller is responsible for
        forwarding these chunks to the eventual HTTP client (AGORA UI) — the
        bytes are already in ``text/event-stream`` format.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=None)
            self._owns_client = True
        body: dict[str, Any] = {"message": message}
        if session_id:
            body["session_id"] = session_id
        async with self._client.stream(
            "POST", "/chat", headers=self._headers, json=body
        ) as resp:
            if resp.status_code in (401, 403):
                raise AgentAuthError(f"{self.slug}: chat auth failed ({resp.status_code})")
            if resp.status_code >= 500:
                text = await resp.aread()
                raise AgentClientError(f"{self.slug}: chat server error: {text[:200]!r}")
            async for chunk in resp.aiter_bytes():
                yield chunk


async def is_reachable(host: str, port: int = DEFAULT_PORT, timeout: float = 2.0) -> bool:
    """Quick liveness check without raising on connection errors.

    Returns True if /health responds with 2xx within `timeout` seconds.
    Used by AGORA's polling to detect when a freshly-provisioned child is ready.
    """
    if not host:
        return False
    try:
        async with httpx.AsyncClient(base_url=f"http://{host}:{port}", timeout=timeout) as c:
            resp = await c.get("/health")
            return resp.status_code < 300
    except Exception:
        return False
