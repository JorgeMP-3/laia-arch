"""Tests for laia_agent.api — the HTTP server exposed by each child container.

Uses fastapi.testclient.TestClient against a config pointing to a tmpdir.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from laia_agent.api import create_app
from laia_agent.config import AgentConfig


@pytest.fixture
def cfg(tmp_path: Path) -> AgentConfig:
    """Minimal agent config rooted at a tmpdir, with a fixed API token."""
    root = tmp_path / "laia"
    agent_dir = root / "agent"
    data_dir = root / "data"
    profile_dir = data_dir / "profile"
    workspace_dir = root / "workspaces" / "personal"
    for d in (agent_dir, data_dir, profile_dir, workspace_dir):
        d.mkdir(parents=True)
    return AgentConfig(
        employee="nombrix",
        container="laia-nombrix",
        root=root,
        agent_dir=agent_dir,
        data_dir=data_dir,
        logs_dir=root / "logs",
        profile_dir=profile_dir,
        workspace_dir=workspace_dir,
        workspace_db=workspace_dir / "workspace.db",
        heartbeat_interval=5,
        api_token="test-token-xyz",
        api_port=9090,
    )


@pytest.fixture
def client(cfg) -> TestClient:
    return TestClient(create_app(cfg))


def auth() -> dict[str, str]:
    return {"Authorization": "Bearer test-token-xyz"}


# ── /health (unauthenticated) ────────────────────────────────────────────────


def test_health_is_unauthenticated(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["slug"] == "nombrix"
    assert body["container"] == "laia-nombrix"


# ── auth ─────────────────────────────────────────────────────────────────────


def test_status_requires_token(client):
    r = client.get("/status")
    assert r.status_code == 401


def test_status_rejects_wrong_token(client):
    r = client.get("/status", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_status_with_correct_token(client):
    r = client.get("/status", headers=auth())
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "nombrix"


# ── /profile ─────────────────────────────────────────────────────────────────


def test_get_profile_creates_defaults_on_first_read(client, cfg):
    r = client.get("/profile", headers=auth())
    assert r.status_code == 200
    body = r.json()
    # ensure_profile creates the default files; persona should exist
    assert "persona" in body
    assert "instructions" in body
    assert (cfg.profile_dir / "persona.md").exists()


def test_put_profile_persists(client, cfg):
    client.get("/profile", headers=auth())  # initialize
    r = client.put("/profile", json={"persona": "Hola mundo"}, headers=auth())
    assert r.status_code == 200
    # The persona file is stored with a trailing newline by write_text; strip on compare.
    assert r.json()["persona"].strip() == "Hola mundo"
    # Re-read to confirm persistence
    r2 = client.get("/profile", headers=auth())
    assert r2.json()["persona"].strip() == "Hola mundo"


def test_put_profile_rejects_empty_patch(client):
    r = client.put("/profile", json={}, headers=auth())
    assert r.status_code == 400


# ── /tasks ───────────────────────────────────────────────────────────────────


def test_submit_task_creates_inbox_file(client, cfg):
    r = client.post("/tasks", json={"type": "ping", "payload": {}}, headers=auth())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "queued"
    assert body["id"].startswith("task_")
    # Verify the JSON landed in inbox
    inbox = cfg.data_dir / "tasks" / "inbox"
    files = list(inbox.glob("*.json"))
    assert len(files) == 1
    saved = json.loads(files[0].read_text())
    assert saved["type"] == "ping"
    assert saved["id"] == body["id"]


def test_get_task_pending_in_inbox(client, cfg):
    sub = client.post("/tasks", json={"type": "ping", "payload": {}}, headers=auth())
    task_id = sub.json()["id"]
    r = client.get(f"/tasks/{task_id}", headers=auth())
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


def test_get_task_done(client, cfg):
    task_id = "task_aaaaaaaaaaaa"
    done = cfg.data_dir / "tasks" / "done"
    done.mkdir(parents=True, exist_ok=True)
    payload = {"id": task_id, "status": "done", "result": {"pong": True}}
    (done / f"{task_id}.json").write_text(json.dumps(payload))

    r = client.get(f"/tasks/{task_id}", headers=auth())
    assert r.status_code == 200
    assert r.json()["status"] == "done"
    assert r.json()["result"] == {"pong": True}


def test_get_task_failed(client, cfg):
    task_id = "task_bbbbbbbbbbbb"
    failed = cfg.data_dir / "tasks" / "failed"
    failed.mkdir(parents=True, exist_ok=True)
    (failed / f"{task_id}.json").write_text(json.dumps({"id": task_id, "status": "failed", "error": "boom"}))

    r = client.get(f"/tasks/{task_id}", headers=auth())
    assert r.status_code == 200
    assert r.json()["status"] == "failed"


def test_get_task_404_when_unknown(client):
    r = client.get("/tasks/task_zzzzzzzzzzzz", headers=auth())
    assert r.status_code == 404


# ── open mode (empty token) ──────────────────────────────────────────────────


def test_open_mode_when_token_empty(cfg):
    """If api_token is empty, /status is reachable without bearer."""
    open_cfg = AgentConfig(
        employee=cfg.employee, container=cfg.container, root=cfg.root,
        agent_dir=cfg.agent_dir, data_dir=cfg.data_dir, logs_dir=cfg.logs_dir,
        profile_dir=cfg.profile_dir, workspace_dir=cfg.workspace_dir,
        workspace_db=cfg.workspace_db, heartbeat_interval=cfg.heartbeat_interval,
        api_token="", api_port=cfg.api_port,
    )
    c = TestClient(create_app(open_cfg))
    r = c.get("/status")
    assert r.status_code == 200
