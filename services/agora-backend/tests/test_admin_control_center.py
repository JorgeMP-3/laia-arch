from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.security import create_access_token


client = TestClient(app)

ADMIN_HEADERS = {"Authorization": "Bearer dev-admin-token"}


def _cmd_result(stdout: str = "", stderr: str = "", ok: bool = True) -> dict:
    return {
        "ok": ok,
        "returncode": 0 if ok else 1,
        "stdout": stdout,
        "stderr": stderr,
        "command": [],
    }


def _employee_headers(username: str | None = None) -> dict:
    username = username or f"ccemp{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/api/users",
        headers=ADMIN_HEADERS,
        json={"username": username, "display_name": username, "password": "pass1234"},
    )
    assert r.status_code == 201, r.text
    user_id = r.json()["user"]["id"]
    token = create_access_token(user_id, "employee", settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


def test_admin_endpoints_require_admin_role():
    assert client.get("/api/admin/status").status_code == 401
    r = client.get("/api/admin/status", headers=_employee_headers())
    assert r.status_code == 403


def test_admin_status_and_containers_are_enriched():
    lxc_csv = "laia-agora,RUNNING,10.99.0.219,CONTAINER,0\nlaia-jorge-dev,RUNNING,10.99.0.92,CONTAINER,0\n"

    def fake_run(args, **_kwargs):
        if args[:2] == ["lxc", "list"]:
            return _cmd_result(lxc_csv)
        if args[:2] == ["lxc", "version"]:
            return _cmd_result("5.0\n")
        if args and args[0] == "journalctl":
            return _cmd_result("")
        return _cmd_result("")

    with patch("app.admin._run_command", side_effect=fake_run):
        status = client.get("/api/admin/status", headers=ADMIN_HEADERS)
        containers = client.get("/api/admin/containers", headers=ADMIN_HEADERS)

    assert status.status_code == 200, status.text
    data = status.json()["status"]
    assert data["health"]["lxd_available"] is True
    assert data["containers"]["total"] == 2
    assert data["auth"]["path"]

    assert containers.status_code == 200
    names = [item["name"] for item in containers.json()["containers"]]
    assert "laia-agora" in names
    assert "laia-jorge-dev" in names


def test_admin_logs_reads_journal_lines():
    with patch("app.admin._run_command", return_value=_cmd_result("line 1\nline 2\n")):
        r = client.get("/api/admin/logs/agora-backend?lines=2", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()["logs"]
    assert body["ok"] is True
    assert body["lines"] == ["line 1", "line 2"]


def test_admin_tool_audit_reads_structured_log_file(tmp_path, monkeypatch):
    log_path = tmp_path / "audit.log"
    log_path.write_text(
        json.dumps({
            "ts": "2026-05-17T00:00:00+00:00",
            "level": "INFO",
            "logger": "agora.tool_call",
            "msg": "tool_call started",
            "event": "tool_call",
            "phase": "started",
            "user_id": "user_audit",
            "tool": "read_file",
        })
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGORA_ADMIN_LOG_PATHS", str(log_path))

    r = client.get("/api/admin/audit/tools?user_id=user_audit", headers=ADMIN_HEADERS)

    assert r.status_code == 200
    calls = r.json()["tool_calls"]
    assert len(calls) == 1
    assert calls[0]["tool"] == "read_file"


def test_container_restart_job_persists_status(monkeypatch):
    monkeypatch.setenv("AGORA_ADMIN_JOBS_INLINE", "1")
    with patch("app.admin._run_command", return_value=_cmd_result("restarted\n")):
        r = client.post("/api/admin/containers/jorge-dev/restart", headers=ADMIN_HEADERS)
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]

    job = client.get(f"/api/admin/jobs/{job_id}", headers=ADMIN_HEADERS)

    assert job.status_code == 200
    body = job.json()["job"]
    assert body["kind"] == "container-restart"
    assert body["status"] == "done"
    assert body["result"]["ok"] is True
    assert body["log_tail"]


def test_provision_user_job_creates_user_and_agent(monkeypatch):
    monkeypatch.setenv("AGORA_ADMIN_JOBS_INLINE", "1")
    slug = f"ccprov-{uuid.uuid4().hex[:6]}"
    provision_stdout = (
        "Provisioned container\n"
        + json.dumps({
            "slug": slug,
            "container": f"laia-{slug}",
            "ipv4": "10.99.0.50",
            "api_token": "token-123456789012345678901234567890",
            "api_port": 9091,
        })
        + "\n"
    )

    def fake_run(args, **_kwargs):
        if args and args[0].endswith("create-agent.sh"):
            return _cmd_result(provision_stdout)
        return _cmd_result("")

    with patch("app.admin._run_command", side_effect=fake_run):
        r = client.post(
            "/api/admin/users/provision",
            headers=ADMIN_HEADERS,
            json={"slug": slug, "display_name": "Control Center Provision"},
        )
    assert r.status_code == 202, r.text

    job = client.get(f"/api/admin/jobs/{r.json()['job_id']}", headers=ADMIN_HEADERS).json()["job"]

    assert job["status"] == "done", job
    assert job["result"]["user"]["username"] == slug
    assert job["result"]["agent"]["container_name"] == f"laia-{slug}"
    assert job["result"]["agent"]["container_ip"] == "10.99.0.50"


def test_refresh_oauth_pushes_current_auth_json(tmp_path, monkeypatch):
    auth_json = Path(tmp_path) / "auth.json"
    auth_json.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("AGORA_ADMIN_HOST_AUTH_JSON", str(auth_json))

    with patch("app.admin._run_command", return_value=_cmd_result("pushed\n")) as run:
        r = client.post("/api/admin/system/refresh-oauth", headers=ADMIN_HEADERS)

    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    args = run.call_args.args[0]
    assert args[:3] == ["lxc", "file", "push"]
    assert str(auth_json) in args
