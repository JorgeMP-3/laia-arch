"""Tests for app/agent_client.py — HTTP client to child agents.

Uses httpx MockTransport to simulate the child's FastAPI responses without
needing a real LXD container. Each test wraps the async call in asyncio.run
to avoid the pytest-asyncio dependency.
"""
from __future__ import annotations

import asyncio
import json
from typing import Callable

import httpx
import pytest

from app.agent_client import (
    AgentAuthError,
    AgentClient,
    AgentClientError,
    AgentNotFoundError,
    AgentUnreachableError,
    is_reachable,
)


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    slug: str = "nombrix",
    host: str = "10.0.0.5",
    token: str = "test-token-abc",
) -> AgentClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(base_url=f"http://{host}:9090", transport=transport, timeout=5.0)
    return AgentClient(slug=slug, host=host, token=token, client=http)


async def _with_client(handler, coro_factory):
    async with make_client(handler) as c:
        return await coro_factory(c)


def run_async(handler, coro_factory):
    return asyncio.run(_with_client(handler, coro_factory))


# ── construction validation ──────────────────────────────────────────────────


def test_constructor_rejects_empty_host():
    with pytest.raises(AgentClientError):
        AgentClient(slug="x", host="", token="t")


def test_constructor_rejects_empty_token():
    with pytest.raises(AgentClientError):
        AgentClient(slug="x", host="10.0.0.5", token="")


# ── happy path ───────────────────────────────────────────────────────────────


def test_health_returns_payload():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/health"
        assert req.headers["authorization"] == "Bearer test-token-abc"
        return httpx.Response(200, json={"status": "ok", "slug": "nombrix"})

    result = run_async(handler, lambda c: c.health())
    assert result == {"status": "ok", "slug": "nombrix"}


def test_submit_task_returns_id():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        assert req.url.path == "/tasks"
        body = json.loads(req.content)
        assert body == {"type": "ping", "payload": {}}
        return httpx.Response(200, json={"id": "task_abc123", "status": "queued"})

    result = run_async(handler, lambda c: c.submit_task("ping", {}))
    assert result["id"] == "task_abc123"
    assert result["status"] == "queued"


def test_get_task_pending():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "task_abc123", "status": "pending"})

    result = run_async(handler, lambda c: c.get_task("task_abc123"))
    assert result["status"] == "pending"


def test_get_task_not_found_returns_none():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    result = run_async(handler, lambda c: c.get_task("task_missing"))
    assert result is None


def test_get_profile_returns_full_payload():
    profile = {"persona": "Hi", "instructions": "Do X", "skills": {"a": True}, "preferences": {}}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/profile"
        return httpx.Response(200, json=profile)

    result = run_async(handler, lambda c: c.get_profile())
    assert result == profile


def test_update_profile_sends_patch():
    patch = {"persona": "New persona"}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "PUT"
        assert req.url.path == "/profile"
        assert json.loads(req.content) == patch
        return httpx.Response(200, json={"persona": "New persona", "instructions": "Do X"})

    result = run_async(handler, lambda c: c.update_profile(patch))
    assert result["persona"] == "New persona"


# ── error paths ──────────────────────────────────────────────────────────────


def test_auth_error_on_401():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "invalid token"})

    with pytest.raises(AgentAuthError):
        run_async(handler, lambda c: c.health())


def test_unreachable_on_connect_error():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(AgentUnreachableError):
        run_async(handler, lambda c: c.health())


def test_unreachable_on_timeout():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    with pytest.raises(AgentUnreachableError):
        run_async(handler, lambda c: c.health())


def test_server_error_raises_generic():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    with pytest.raises(AgentClientError):
        run_async(handler, lambda c: c.status())


# ── is_reachable helper ──────────────────────────────────────────────────────


def test_is_reachable_returns_false_on_no_host():
    assert asyncio.run(is_reachable("")) is False


def test_is_reachable_returns_false_on_unreachable_host():
    # Real call to an unroutable IP — confirms the exception is swallowed.
    assert asyncio.run(is_reachable("127.0.0.1", port=1, timeout=0.5)) is False
