"""Smoke tests for executor API endpoints."""

from __future__ import annotations

from pathlib import Path


def test_health_no_auth(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_profile_requires_auth(client):
    res = client.get("/profile")
    assert res.status_code == 401


def test_profile_with_auth(client, auth_headers):
    res = client.get("/profile", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["slug"] == "test-slug"
    assert "read_file" in data["tools"]
    assert "bash" in data["tools"]


def test_exec_invalid_token(client):
    res = client.post(
        "/exec",
        json={"tool": "read_file", "args": {"path": "/etc/hostname"}, "request_id": "x1"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert res.status_code == 403


def test_exec_unknown_tool(client, auth_headers):
    res = client.post(
        "/exec",
        json={"tool": "does_not_exist", "args": {}, "request_id": "x2"},
        headers=auth_headers,
    )
    assert res.status_code == 400


def test_exec_write_then_read(client, auth_headers, tmp_path):
    target = tmp_path / "hello.txt"
    res = client.post(
        "/exec",
        json={
            "tool": "write_file",
            "args": {"path": str(target), "content": "hola mundo"},
            "request_id": "w1",
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "wrote" in body["result"]
    assert target.read_text() == "hola mundo"

    res = client.post(
        "/exec",
        json={
            "tool": "read_file",
            "args": {"path": str(target)},
            "request_id": "r1",
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "hola mundo" in body["result"]


def test_exec_bash(client, auth_headers):
    res = client.post(
        "/exec",
        json={"tool": "bash", "args": {"command": "echo testing-bash"}, "request_id": "b1"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "testing-bash" in body["result"]


def test_exec_apply_patch(client, auth_headers, tmp_path):
    target = tmp_path / "p.txt"
    target.write_text("foo bar baz")
    res = client.post(
        "/exec",
        json={
            "tool": "apply_patch",
            "args": {"path": str(target), "old_string": "bar", "new_string": "BAR"},
            "request_id": "p1",
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert target.read_text() == "foo BAR baz"


def test_exec_list_dir(client, auth_headers, tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "subdir").mkdir()
    res = client.post(
        "/exec",
        json={"tool": "list_dir", "args": {"path": str(tmp_path)}, "request_id": "l1"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "subdir/" in body["result"]
    assert "a.txt" in body["result"]


def test_exec_bad_args(client, auth_headers):
    res = client.post(
        "/exec",
        json={"tool": "read_file", "args": {"wrong_arg": "x"}, "request_id": "e1"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert "bad args" in body["error"]


def test_workspace_files(client, auth_headers, tmp_path):
    (tmp_path / "file.txt").write_text("x")
    res = client.get(f"/workspace/files?path={tmp_path}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert any(e["name"] == "file.txt" for e in data["entries"])


def test_exec_body_too_large_rejected(client, auth_headers, monkeypatch):
    """Bodies larger than the configured limit get 413 (not OOM)."""
    # Lower the limit so the test stays fast. The middleware reads the value
    # at app-build time, so we rebuild the app with the patched env.
    from laia_executor import api as api_mod
    from laia_executor.config import ExecutorConfig
    monkeypatch.setattr(api_mod, "MAX_REQUEST_BODY_BYTES", 1024)
    cfg = ExecutorConfig(
        bind_host="127.0.0.1", bind_port=9091,
        token="tt", slug="t",
        workspace_root="/tmp", plugins_root="/tmp",
    )
    from fastapi.testclient import TestClient
    small_app = api_mod.build_app(cfg)
    small_client = TestClient(small_app)
    big_payload = {
        "tool": "write_file",
        "args": {"path": "/tmp/x", "content": "A" * 5000},
        "request_id": "big",
    }
    res = small_client.post(
        "/exec", json=big_payload,
        headers={"Authorization": f"Bearer {cfg.token}"},
    )
    assert res.status_code == 413
    assert "exceeds" in res.text
