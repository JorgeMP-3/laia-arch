"""Per-user MCP server config (marketplace-v0.1 Fase H)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def app_client():
    from app.main import app
    return TestClient(app)


ADMIN_HEADERS = {"Authorization": "Bearer dev-admin-token"}


def _make_user(app_client: TestClient) -> dict[str, str]:
    username = f"mcp_{uuid.uuid4().hex[:6]}"
    password = f"pw_{uuid.uuid4().hex[:6]}"
    r = app_client.post(
        "/api/users", headers=ADMIN_HEADERS,
        json={"username": username, "display_name": username,
              "role": "employee", "password": password},
    )
    assert r.status_code in (200, 201), r.text
    tok = app_client.post("/api/login",
                          json={"username": username, "password": password})
    assert tok.status_code == 200, tok.text
    return {"Authorization": f"Bearer {tok.json()['access_token']}"}


def test_mcp_servers_roundtrip(app_client):
    user_h = _make_user(app_client)

    # Initial state — empty list.
    r = app_client.get("/api/user/llm-config", headers=user_h)
    assert r.status_code == 200, r.text
    assert r.json()["mcp_servers"] == []

    # Set two servers.
    servers = [
        {"name": "notion", "url": "https://mcp.notion.com",
         "headers": {"Authorization": "Bearer t1"}},
        {"name": "linear", "url": "https://mcp.linear.app", "headers": {}},
    ]
    r = app_client.patch("/api/user/llm-config", headers=user_h,
                         json={"mcp_servers": servers})
    assert r.status_code == 200, r.text
    got = r.json()["mcp_servers"]
    assert {s["name"] for s in got} == {"notion", "linear"}
    notion = next(s for s in got if s["name"] == "notion")
    assert notion["headers"]["Authorization"] == "Bearer t1"

    # Read back via GET to confirm persistence.
    r = app_client.get("/api/user/llm-config", headers=user_h)
    assert r.status_code == 200
    assert len(r.json()["mcp_servers"]) == 2


def test_mcp_servers_none_leaves_unchanged(app_client):
    user_h = _make_user(app_client)
    app_client.patch("/api/user/llm-config", headers=user_h,
                     json={"mcp_servers": [{"name": "a", "url": "https://a.com",
                                            "headers": {}}]})
    # Patch with no mcp_servers field — should not erase.
    app_client.patch("/api/user/llm-config", headers=user_h,
                     json={"model": "claude-opus-4-7"})
    r = app_client.get("/api/user/llm-config", headers=user_h)
    assert len(r.json()["mcp_servers"]) == 1
    assert r.json()["mcp_servers"][0]["name"] == "a"


def test_mcp_servers_empty_list_clears(app_client):
    user_h = _make_user(app_client)
    app_client.patch("/api/user/llm-config", headers=user_h,
                     json={"mcp_servers": [{"name": "a", "url": "https://a.com",
                                            "headers": {}}]})
    app_client.patch("/api/user/llm-config", headers=user_h,
                     json={"mcp_servers": []})
    r = app_client.get("/api/user/llm-config", headers=user_h)
    assert r.json()["mcp_servers"] == []


def test_mcp_servers_does_not_affect_api_key(app_client):
    user_h = _make_user(app_client)
    # Set an api key first.
    app_client.patch("/api/user/llm-config", headers=user_h,
                     json={"api_key": "sk-test-abc"})
    # Now patch only mcp_servers.
    app_client.patch("/api/user/llm-config", headers=user_h,
                     json={"mcp_servers": [{"name": "x", "url": "https://x", "headers": {}}]})
    r = app_client.get("/api/user/llm-config", headers=user_h)
    assert r.json()["has_key"] is True
