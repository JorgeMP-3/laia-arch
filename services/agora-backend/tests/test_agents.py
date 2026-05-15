"""Tests for agent control endpoints (Agent 4).

Run with:
  cd services/agora-backend
  .venv/bin/python -m pytest tests/test_agents.py -v
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

# ── fixture: admin token ──────────────────────────────────────────────────────

ADMIN_TOKEN = "dev-admin-token"
HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

client = TestClient(app)


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_orchestrator(method: str, return_value):
    return patch(f"app.main.orchestrator.{method}", return_value=return_value)


# ── health ────────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── auth guard ────────────────────────────────────────────────────────────────

def test_agents_requires_auth():
    r = client.get("/api/agents")
    assert r.status_code == 401


def test_agent_control_requires_admin():
    r = client.post("/api/agents/jorge/start", headers={"Authorization": "Bearer bad-token"})
    assert r.status_code == 401


# ── list agents ───────────────────────────────────────────────────────────────

def test_list_agents_empty():
    with _mock_orchestrator("list_agents", []):
        r = client.get("/api/agents", headers=HEADERS)
    assert r.status_code == 200
    assert isinstance(r.json()["agents"], list)


def test_list_agents_returns_data():
    fake = [{"slug": "jorge", "container": "laia-jorge", "status": "verified", "lxd_state": "RUNNING", "ipv4": "10.99.0.10"}]
    with _mock_orchestrator("list_agents", fake):
        r = client.get("/api/agents", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["agents"][0]["slug"] == "jorge"


# ── get single agent ──────────────────────────────────────────────────────────

def test_get_agent_not_found():
    with _mock_orchestrator("get_agent", None):
        r = client.get("/api/agents/nonexistent", headers=HEADERS)
    assert r.status_code == 404


def test_get_agent_ok():
    fake = {"slug": "jorge", "container": "laia-jorge", "status": "verified"}
    with _mock_orchestrator("get_agent", fake):
        r = client.get("/api/agents/jorge", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["slug"] == "jorge"


# ── start / stop / restart ────────────────────────────────────────────────────

@pytest.mark.parametrize("action", ["start", "stop", "restart"])
def test_agent_lifecycle_ok(action: str):
    method = f"{action}_agent"
    with _mock_orchestrator(method, {"ok": True, "returncode": 0, "output": "", "error": ""}):
        r = client.post(f"/api/agents/jorge/{action}", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.parametrize("action", ["start", "stop", "restart"])
def test_agent_lifecycle_fail(action: str):
    method = f"{action}_agent"
    with _mock_orchestrator(method, {"ok": False, "returncode": 1, "output": "", "error": "container not found"}):
        r = client.post(f"/api/agents/jorge/{action}", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["ok"] is False


# ── snapshot ──────────────────────────────────────────────────────────────────

def test_snapshot_ok():
    with _mock_orchestrator("snapshot_agent", {"ok": True, "returncode": 0, "output": "", "error": ""}):
        r = client.post("/api/agents/jorge/snapshot", headers=HEADERS, json={"name": "before-update"})
    assert r.status_code == 200


def test_snapshot_invalid_name():
    r = client.post("/api/agents/jorge/snapshot", headers=HEADERS, json={"name": "INVALID NAME!"})
    assert r.status_code == 422


# ── logs ──────────────────────────────────────────────────────────────────────

def test_get_logs():
    with _mock_orchestrator("get_agent_logs", {"ok": True, "output": "log line 1\nlog line 2\n", "error": ""}):
        r = client.get("/api/agents/jorge/logs", headers=HEADERS)
    assert r.status_code == 200
    assert "log" in r.json().get("output", "")


# ── send task ─────────────────────────────────────────────────────────────────

def test_send_task_ok():
    with _mock_orchestrator("send_task", {"ok": True, "task_id": "task_abc123def456", "error": ""}):
        r = client.post("/api/agents/jorge/tasks", headers=HEADERS, json={"task_type": "ping", "payload": {}})
    assert r.status_code == 202
    assert r.json()["ok"] is True


def test_send_task_invalid_type():
    r = client.post("/api/agents/jorge/tasks", headers=HEADERS, json={"task_type": "INVALID TYPE!", "payload": {}})
    assert r.status_code == 422


# ── create agent ──────────────────────────────────────────────────────────────

def test_create_agent_ok():
    with (
        _mock_orchestrator("create_agent", {"ok": True, "returncode": 0, "output": "", "error": ""}),
        _mock_orchestrator("install_runtime", {"ok": True, "returncode": 0, "output": "", "error": ""}),
        _mock_orchestrator("init_workspace", {"ok": True, "returncode": 0, "output": "", "error": ""}),
        _mock_orchestrator("snapshot_agent", {"ok": True, "returncode": 0, "output": "", "error": ""}),
    ):
        r = client.post("/api/agents", headers=HEADERS, json={"slug": "testuser"})
    assert r.status_code == 201
    assert r.json()["ok"] is True


def test_create_agent_invalid_slug():
    r = client.post("/api/agents", headers=HEADERS, json={"slug": "UPPER_CASE!"})
    assert r.status_code == 422


# ── /api/agents/register ─────────────────────────────────────────────────────


def _create_employee(username: str) -> str:
    """Create an employee via the API and return its user_id."""
    r = client.post(
        "/api/users",
        json={"username": username, "display_name": username.title(), "role": "employee", "password": "test1234"},
        headers=HEADERS,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["user"]["id"]


def test_register_provisioned_agent_creates_record():
    uid = _create_employee("alicereg")
    body = {"slug": "alicereg", "user_id": uid, "container_ip": "10.0.0.42", "api_token": "test-token-xyz"}
    r = client.post("/api/agents/register", json=body, headers=HEADERS)
    assert r.status_code == 201, r.text
    agent = r.json()["agent"]
    assert agent["container_ip"] == "10.0.0.42"
    assert agent["api_token"] == "test-token-xyz"
    assert agent["status"] == "running"
    assert agent["container_name"] == "laia-alicereg"


def test_register_rejects_duplicate():
    uid = _create_employee("bobreg")
    body = {"slug": "bobreg", "user_id": uid, "container_ip": "10.0.0.43", "api_token": "tk1"}
    r = client.post("/api/agents/register", json=body, headers=HEADERS)
    assert r.status_code == 201
    r2 = client.post("/api/agents/register", json={**body, "api_token": "tk2"}, headers=HEADERS)
    assert r2.status_code == 409


def test_register_404_when_user_missing():
    body = {
        "slug": "ghost",
        "user_id": "user_doesnotexist",
        "container_ip": "10.0.0.99",
        "api_token": "tk",
    }
    r = client.post("/api/agents/register", json=body, headers=HEADERS)
    assert r.status_code == 404
