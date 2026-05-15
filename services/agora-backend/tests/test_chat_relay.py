"""Tests for AGORA chat relay endpoints (admin + employee paths)."""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx
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
    assert client.post(
        "/api/agents/register",
        json={"slug": slug, "user_id": uid, "container_ip": ip, "api_token": token},
        headers=ADMIN_HEADERS,
    ).status_code == 201
    # Login as the employee to get their JWT
    r2 = client.post("/api/login", json={"username": slug, "password": "test1234"})
    assert r2.status_code == 200, r2.text
    jwt = r2.json()["access_token"]
    return uid, jwt


class _StubClient:
    """Mimics AgentClient enough for the relay to stream a fixed payload."""

    def __init__(self, *args, **kwargs):
        pass

    async def chat_stream(self, message, session_id=None) -> AsyncIterator[bytes]:
        yield b"event: session\ndata: {\"session_id\": \"sid1\"}\n\n"
        yield b"event: token\ndata: {\"type\": \"token\", \"text\": \"hi\"}\n\n"
        yield b"event: final\ndata: {\"type\": \"final\", \"reply\": \"hi\"}\n\n"


@pytest.fixture(autouse=True)
def patch_agent_client(monkeypatch):
    monkeypatch.setattr("app.main._agent_client_for_slug", lambda slug: _StubClient())


# ── admin path ───────────────────────────────────────────────────────────────


def test_admin_chat_returns_sse(monkeypatch):
    _provision_agent("chatadmin", "10.0.1.1", "tk-chatadmin")
    with client.stream(
        "POST", "/api/agents/chatadmin/chat",
        json={"message": "hola"},
        headers=ADMIN_HEADERS,
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = b"".join(r.iter_bytes())
    assert b"event: token" in body
    assert b"event: final" in body


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
    assert b"event: token" in body


def test_employee_chat_404_without_linked_agent():
    # Create a user WITHOUT an agent
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


def test_admin_chat_404_when_agent_not_registered(monkeypatch):
    # Override the autouse stub so the real lookup runs and raises 404.
    def real_lookup(slug: str):
        from fastapi import HTTPException
        from app.storage import store
        container = f"laia-{slug}"
        target = next((a for a in store.agents() if a.container_name == container), None)
        if target is None:
            raise HTTPException(status_code=404, detail=f"agent {slug!r} not registered")
        return _StubClient()

    monkeypatch.setattr("app.main._agent_client_for_slug", real_lookup)
    r = client.post(
        "/api/agents/neverexists/chat",
        json={"message": "hola"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 404
