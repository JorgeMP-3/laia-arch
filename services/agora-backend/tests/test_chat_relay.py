"""Tests for AGORA chat endpoints (admin + employee paths).

The sprint-2 implementation proxied SSE from the user's container. The
redesign drives an in-process AIAgent from :class:`AgentPool` and only
forwards filesystem/bash tool calls to the executor. These tests stub the
``chat_stream`` async generator so we exercise routing, auth and error
paths without touching the real AIAgent (covered separately).
"""
from __future__ import annotations

import json
from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import store


ADMIN_HEADERS = {"Authorization": "Bearer dev-admin-token"}
client = TestClient(app)


def _provision_agent(slug: str, ip: str, token: str) -> tuple[str, str]:
    """Create employee + register agent; return (user_id, jwt_token)."""
    r = client.post(
        "/api/users",
        json={"username": slug, "display_name": slug.title(), "role": "employee", "password": "test1234"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code in (200, 201), r.text
    uid = r.json()["user"]["id"]
    # Configure a fake LLM key so chat_stream's "no LLM key" guard doesn't
    # short-circuit before our stub is reached.
    client.patch(
        f"/api/users/{uid}",
        json={"role": "employee"},
        headers=ADMIN_HEADERS,
    )
    # Login as the employee to set their LLM key.
    r2 = client.post("/api/login", json={"username": slug, "password": "test1234"})
    assert r2.status_code == 200, r2.text
    jwt = r2.json()["access_token"]
    client.patch(
        "/api/user/llm-config",
        json={"provider": "deepseek", "api_key": "sk-test-key"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert client.post(
        "/api/agents/register",
        json={"slug": slug, "user_id": uid, "container_ip": ip, "api_token": token},
        headers=ADMIN_HEADERS,
    ).status_code == 201
    return uid, jwt


async def _fake_chat_stream(**_kwargs) -> AsyncIterator[bytes]:
    """Stub for app.chat_engine.chat_stream — emits 3 canned SSE events."""
    yield b'data: {"type": "tool", "name": "write_file", "status": "started"}\n\n'
    yield b'data: {"type": "token", "value": "hola"}\n\n'
    yield b'data: {"type": "done", "response": "hola desde stub", "iterations": 1}\n\n'


@pytest.fixture(autouse=True)
def patch_chat_stream(monkeypatch):
    """Replace the real chat dispatcher with a stub for every test."""
    import app.chat_engine
    monkeypatch.setattr(app.chat_engine, "chat_stream", _fake_chat_stream)


# ── admin path ───────────────────────────────────────────────────────────────


def test_admin_chat_returns_sse():
    _provision_agent("chatadmin", "10.0.1.1", "tk-chatadmin")
    with client.stream(
        "POST", "/api/agents/chatadmin/chat",
        json={"message": "hola"},
        headers=ADMIN_HEADERS,
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = b"".join(r.iter_bytes())
    assert b'"type": "token"' in body
    assert b'"type": "done"' in body


def test_admin_chat_requires_admin_role():
    _, jwt = _provision_agent("chatnonadmin", "10.0.1.2", "tk-chatnonadmin")
    r = client.post(
        "/api/agents/chatnonadmin/chat",
        json={"message": "hola"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert r.status_code == 403


# ── employee path ────────────────────────────────────────────────────────────


def test_employee_chat_returns_sse():
    _, jwt = _provision_agent("chatemp", "10.0.1.3", "tk-chatemp")
    with client.stream(
        "POST", "/api/agents/me/chat",
        json={"message": "hola"},
        headers={"Authorization": f"Bearer {jwt}"},
    ) as r:
        assert r.status_code == 200
        body = b"".join(r.iter_bytes())
    assert b'"type": "token"' in body
    assert b'"type": "done"' in body


def test_employee_chat_404_without_linked_agent():
    r = client.post(
        "/api/users",
        json={"username": "lonelyuser", "display_name": "Lonely", "role": "employee", "password": "test1234"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code in (200, 201)
    jwt = client.post("/api/login", json={"username": "lonelyuser", "password": "test1234"}).json()["access_token"]
    r = client.post(
        "/api/agents/me/chat",
        json={"message": "hola"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert r.status_code == 404


def test_admin_chat_404_when_agent_not_registered():
    r = client.post(
        "/api/agents/neverexists/chat",
        json={"message": "hola"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 404


# ── unhappy paths — exercise the real chat_engine (no stub) ─────────────────


# NOTE: the old `test_real_chat_engine_emits_error_without_llm_key` test
# was retired when new users started defaulting to ``openai-codex`` (OAuth
# via ChatGPT Teams). Its replacement —
# ``test_chat_engine_still_rejects_paid_provider_without_api_key`` in
# test_oauth_defaults.py — covers the same guard for paid-API providers.


def test_real_chat_engine_error_without_provisioned_agent(monkeypatch):
    """Agent registered without container_ip / api_token → 'error' event."""
    import app.chat_engine
    monkeypatch.undo()

    r = client.post(
        "/api/users",
        json={"username": "noprov", "display_name": "NoProv", "role": "employee", "password": "test1234"},
        headers=ADMIN_HEADERS,
    )
    uid = r.json()["user"]["id"]
    # Register agent without container_ip / api_token.
    client.post(
        "/api/agents/register",
        json={"slug": "noprov", "user_id": uid, "container_ip": "", "api_token": ""},
        headers=ADMIN_HEADERS,
    )
    jwt = client.post("/api/login", json={"username": "noprov", "password": "test1234"}).json()["access_token"]
    # Set a key so the LLM check passes and we reach the provision guard.
    client.patch(
        "/api/user/llm-config",
        json={"provider": "deepseek", "api_key": "sk-test"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    with client.stream(
        "POST", "/api/agents/me/chat",
        json={"message": "hola"},
        headers={"Authorization": f"Bearer {jwt}"},
    ) as r:
        body = b"".join(r.iter_bytes())
    assert b'"type": "error"' in body
    assert b'not provisioned' in body
