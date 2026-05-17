"""Tests for /plugins endpoints — upload, list, delete."""
from __future__ import annotations

import base64
import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from laia_agent.api import create_app
from laia_agent.config import AgentConfig


@pytest.fixture
def cfg(tmp_path: Path) -> AgentConfig:
    root = tmp_path / "laia"
    for d in ("agent", "data", "data/profile", "workspaces/personal"):
        (root / d).mkdir(parents=True)
    return AgentConfig(
        employee="nombrix",
        container="laia-nombrix",
        root=root,
        agent_dir=root / "agent",
        data_dir=root / "data",
        logs_dir=root / "logs",
        profile_dir=root / "data/profile",
        workspace_dir=root / "workspaces/personal",
        workspace_db=root / "workspaces/personal/workspace.db",
        heartbeat_interval=5,
        api_token="tk",
        api_port=9090,
    )


@pytest.fixture
def client(cfg, tmp_path, monkeypatch) -> TestClient:
    plugins_root = tmp_path / "plugins"
    monkeypatch.setenv("LAIA_PLUGINS_ROOT", str(plugins_root))
    return TestClient(create_app(cfg))


def auth():
    return {"Authorization": "Bearer tk"}


def _make_zip(files: dict[str, str]) -> str:
    """Build an in-memory zip and return its base64 representation."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return base64.b64encode(buf.getvalue()).decode()


# ── upload ───────────────────────────────────────────────────────────────────


def test_upload_creates_plugin(client, tmp_path):
    code_b64 = _make_zip({"__init__.py": "def register(ctx):\n    pass\n"})
    r = client.post(
        "/plugins",
        json={"name": "hello", "manifest": {"version": "1.0.0", "language": "python"}, "code_b64": code_b64},
        headers=auth(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "hello"
    target = Path(body["path"])
    assert (target / "__init__.py").exists()
    assert (target / "manifest.yaml").exists()


def test_upload_rejects_existing(client):
    code_b64 = _make_zip({"__init__.py": "def register(ctx): pass\n"})
    r1 = client.post("/plugins", json={"name": "dup", "manifest": {}, "code_b64": code_b64}, headers=auth())
    assert r1.status_code == 200
    r2 = client.post("/plugins", json={"name": "dup", "manifest": {}, "code_b64": code_b64}, headers=auth())
    assert r2.status_code == 409


def test_upload_rejects_invalid_name(client):
    code_b64 = _make_zip({"__init__.py": "pass\n"})
    r = client.post("/plugins", json={"name": "INVALID!", "manifest": {}, "code_b64": code_b64}, headers=auth())
    assert r.status_code == 422  # pydantic validation


def test_upload_rejects_bad_b64(client):
    r = client.post("/plugins", json={"name": "bad", "manifest": {}, "code_b64": "not-base64!"}, headers=auth())
    assert r.status_code == 400


def test_upload_rejects_non_zip(client):
    raw_b64 = base64.b64encode(b"hello world not a zip").decode()
    r = client.post("/plugins", json={"name": "notzip", "manifest": {}, "code_b64": raw_b64}, headers=auth())
    assert r.status_code == 400


def test_upload_rejects_zip_traversal(client):
    code_b64 = _make_zip({"../evil.py": "pass\n"})
    r = client.post("/plugins", json={"name": "evil", "manifest": {}, "code_b64": code_b64}, headers=auth())
    assert r.status_code == 400


def test_upload_requires_token(client):
    code_b64 = _make_zip({"__init__.py": "pass\n"})
    r = client.post("/plugins", json={"name": "x", "manifest": {}, "code_b64": code_b64})
    assert r.status_code == 401


# ── list ─────────────────────────────────────────────────────────────────────


def test_list_empty_when_no_plugins(client):
    r = client.get("/plugins", headers=auth())
    assert r.status_code == 200
    assert r.json()["plugins"] == []


def test_list_returns_uploaded(client):
    code_b64 = _make_zip({"__init__.py": "def register(ctx): pass\n"})
    client.post("/plugins", json={"name": "alpha", "manifest": {"version": "1.0.0"}, "code_b64": code_b64}, headers=auth())
    client.post("/plugins", json={"name": "beta", "manifest": {"version": "2.0.0"}, "code_b64": code_b64}, headers=auth())
    r = client.get("/plugins", headers=auth())
    names = [p["name"] for p in r.json()["plugins"]]
    assert "alpha" in names and "beta" in names


# ── delete ───────────────────────────────────────────────────────────────────


def test_delete_removes_plugin(client):
    code_b64 = _make_zip({"__init__.py": "def register(ctx): pass\n"})
    client.post("/plugins", json={"name": "todelete", "manifest": {}, "code_b64": code_b64}, headers=auth())
    r = client.delete("/plugins/todelete", headers=auth())
    assert r.status_code == 200
    r2 = client.get("/plugins", headers=auth())
    assert all(p["name"] != "todelete" for p in r2.json()["plugins"])


def test_delete_404_when_missing(client):
    r = client.delete("/plugins/nonexistent", headers=auth())
    assert r.status_code == 404


def test_delete_rejects_invalid_name(client):
    r = client.delete("/plugins/INVALID!", headers=auth())
    assert r.status_code == 400
