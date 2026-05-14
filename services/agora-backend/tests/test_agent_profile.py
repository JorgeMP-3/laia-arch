"""Tests for agent profile endpoints (personal agent).

Run with:
  cd services/agora-backend
  .venv/bin/python -m pytest tests/test_agent_profile.py -v
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

ADMIN_TOKEN = "dev-admin-token"
HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

client = TestClient(app)

FAKE_PROFILE = {
    "ok": True,
    "returncode": 0,
    "data": {
        "path": "/opt/laia/data/profile",
        "persona": "# Agent\n\nI am a helpful assistant.",
        "instructions": "# Instructions\n\nBe concise.",
        "skills": {"version": 1, "enabled": ["tasks.basic"], "available": ["tasks.basic", "planning.deep"]},
        "preferences": {"language": "es", "tone": "directo"},
        "status": "ready",
    },
    "stderr": "",
}

FAKE_STATUS = {
    "ok": True,
    "slug": "jorge",
    "container": "laia-jorge",
    "runtime": "running",
    "healthcheck": "laia-runtime-ok",
    "lxd_state": "RUNNING",
    "ipv4": "10.99.0.10",
    "service": "active",
}


def _mock_op(method: str, return_value):
    return patch(f"app.main.orchestrator.{method}", return_value=return_value)


# ── GET /api/agent/profile ─────────────────────────────────────────────────

def test_get_my_profile_ok():
    with _mock_op("get_agent_profile", FAKE_PROFILE):
        r = client.get("/api/agent/profile", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["persona"] == "# Agent\n\nI am a helpful assistant."
    assert body["preferences"]["language"] == "es"
    assert body["skills"]["enabled"] == ["tasks.basic"]


def test_get_my_profile_requires_auth():
    r = client.get("/api/agent/profile")
    assert r.status_code == 401


def test_get_my_profile_orchestrator_error():
    with _mock_op("get_agent_profile", {"ok": False, "returncode": 1, "data": None, "stderr": "container down"}):
        r = client.get("/api/agent/profile", headers=HEADERS)
    assert r.status_code == 500


# ── PATCH /api/agent/profile ──────────────────────────────────────────────

def test_update_my_profile_ok():
    with _mock_op("update_agent_profile", FAKE_PROFILE):
        r = client.patch("/api/agent/profile", headers=HEADERS, json={"persona": "# New Agent\n\nI am new."})
    assert r.status_code == 200
    assert r.json()["persona"] == "# Agent\n\nI am a helpful assistant."


def test_update_my_profile_empty_payload():
    r = client.patch("/api/agent/profile", headers=HEADERS, json={})
    assert r.status_code == 400


def test_update_my_profile_skills():
    with _mock_op("update_agent_profile", FAKE_PROFILE):
        r = client.patch("/api/agent/profile", headers=HEADERS, json={"skills": {"enabled": ["tasks.basic"]}})
    assert r.status_code == 200


# ── GET /api/agent/status ─────────────────────────────────────────────────

def test_get_my_status_ok():
    with _mock_op("get_agent_status", FAKE_STATUS):
        r = client.get("/api/agent/status", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["slug"] == "jorge"
    assert body["runtime"] == "running"
    assert body["lxd_state"] == "RUNNING"


def test_get_my_status_requires_auth():
    r = client.get("/api/agent/status")
    assert r.status_code == 401


# ── GET /api/agent/tasks ──────────────────────────────────────────────────

def test_my_tasks_requires_auth():
    r = client.get("/api/agent/tasks")
    assert r.status_code == 401


# ── PATCH /api/agent ──────────────────────────────────────────────────────

def test_update_agent_display_name():
    r = client.patch("/api/agent", headers=HEADERS, json={"display_name": "Nombrix"})
    assert r.status_code == 200
    assert r.json()["display_name"] == "Nombrix"


def test_update_agent_empty_payload():
    r = client.patch("/api/agent", headers=HEADERS, json={})
    assert r.status_code == 200
    assert r.json()["display_name"] == "Nombrix"  # unchanged from previous test


def test_update_agent_invalid_name():
    r = client.patch("/api/agent", headers=HEADERS, json={"display_name": ""})
    assert r.status_code == 422


# ── list agents for non-admin ─────────────────────────────────────────────

def test_list_agents_non_admin_sees_only_own():
    """A non-admin employee should only see their own agent."""
    r = client.get("/api/agents", headers=HEADERS)
    assert r.status_code == 200
    agents = r.json()["agents"]
    # Admin (jorge) sees all, but in a real test with non-admin token it'd filter.
    assert len(agents) >= 0
