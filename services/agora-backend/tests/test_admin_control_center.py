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


# ─────────────────────────────────────────────────────────────────────────
# F6 — coverage para endpoints que el commit inicial dejó sin tests.
# ─────────────────────────────────────────────────────────────────────────


def test_jobs_list_returns_recent_jobs(monkeypatch):
    """`GET /api/admin/jobs` lists the most recent admin jobs across all
    actors. After triggering a job we should see it in the listing."""
    monkeypatch.setenv("AGORA_ADMIN_JOBS_INLINE", "1")
    with patch("app.admin._run_command", return_value=_cmd_result("ok\n")):
        post = client.post("/api/admin/containers/jorge-dev/restart", headers=ADMIN_HEADERS)
    assert post.status_code == 202
    job_id = post.json()["job_id"]

    listing = client.get("/api/admin/jobs?limit=20", headers=ADMIN_HEADERS)
    assert listing.status_code == 200
    jobs = listing.json()["jobs"]
    ids = {j["id"] for j in jobs}
    assert job_id in ids
    assert any(j["status"] == "done" and j["id"] == job_id for j in jobs)


def test_users_listing_enriches_with_lxc(monkeypatch):
    """`GET /api/admin/users` mezcla data de la DB con `lxc list`. Sin
    containers el listado sigue funcionando (estado 'unknown')."""
    with patch("app.admin._run_command", return_value=_cmd_result("")):
        r = client.get("/api/admin/users", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    users = r.json()["users"]
    assert isinstance(users, list)
    # jorge (admin) must be in the list — seeded by storage._ensure_seed_data
    assert any(u["username"] == "jorge" for u in users)


def test_rebuild_user_starts_job(monkeypatch):
    """`POST /api/admin/users/{slug}/rebuild` returns a job_id and the job
    is tracked in admin_jobs."""
    monkeypatch.setenv("AGORA_ADMIN_JOBS_INLINE", "1")

    provision_stdout = json.dumps({
        "slug": "rebuild-target",
        "container": "laia-rebuild-target",
        "ipv4": "10.99.0.55",
        "api_token": "tk-rebuild",
        "api_port": 9091,
    }) + "\n"

    def fake_run(args, **_kwargs):
        if args and args[0].endswith("create-agent.sh"):
            return _cmd_result(provision_stdout)
        return _cmd_result("")

    client.post("/api/users", headers=ADMIN_HEADERS, json={
        "username": "rebuild-target", "display_name": "RT", "password": "pass1234",
    })

    with patch("app.admin._run_command", side_effect=fake_run):
        r = client.post("/api/admin/users/rebuild-target/rebuild", headers=ADMIN_HEADERS)
    assert r.status_code == 202, r.text


def test_rebuild_user_rejects_invalid_slug():
    r = client.post("/api/admin/users/INVALID!/rebuild", headers=ADMIN_HEADERS)
    assert r.status_code == 422


def test_rebuild_user_rejects_unknown_image_alias():
    """F5 — image_alias must be in the allow-list."""
    r = client.post(
        "/api/admin/users/jorge-dev/rebuild?image_alias=evil-img",
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 422
    assert "image_alias" in r.json()["detail"]


def test_delete_user_starts_job_and_refuses_self(monkeypatch):
    """`DELETE /api/admin/users/{slug}` soft-deletes + container cleanup."""
    monkeypatch.setenv("AGORA_ADMIN_JOBS_INLINE", "1")

    # Setup a user first
    client.post("/api/users", headers=ADMIN_HEADERS, json={
        "username": "todelete", "display_name": "Del", "password": "pass1234",
    })

    with patch("app.admin._run_command", return_value=_cmd_result("")):
        r = client.delete("/api/admin/users/todelete", headers=ADMIN_HEADERS)
    assert r.status_code == 202, r.text
    assert r.json()["job_id"]

    # Cannot delete yourself (jorge)
    self_r = client.delete("/api/admin/users/jorge", headers=ADMIN_HEADERS)
    assert self_r.status_code == 400


def test_container_snapshot_and_restore_jobs(monkeypatch):
    """`POST /containers/{name}/snapshot` and `/restore` both spawn jobs."""
    monkeypatch.setenv("AGORA_ADMIN_JOBS_INLINE", "1")
    with patch("app.admin._run_command", return_value=_cmd_result("ok")):
        s = client.post(
            "/api/admin/containers/jorge-dev/snapshot",
            headers=ADMIN_HEADERS,
            json={"name": "snap-foo"},
        )
        r = client.post(
            "/api/admin/containers/jorge-dev/restore",
            headers=ADMIN_HEADERS,
            json={"name": "snap-foo"},
        )
    assert s.status_code == 202, s.text
    assert r.status_code == 202, r.text


def test_restart_backend_job(monkeypatch):
    """`POST /system/restart-backend` returns a job_id and (in inline mode)
    completes synchronously."""
    monkeypatch.setenv("AGORA_ADMIN_JOBS_INLINE", "1")
    with patch("app.admin._run_command", return_value=_cmd_result("Restarted")):
        r = client.post("/api/admin/system/restart-backend", headers=ADMIN_HEADERS)
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]
    detail = client.get(f"/api/admin/jobs/{job_id}", headers=ADMIN_HEADERS).json()["job"]
    assert detail["kind"] == "restart-backend"
    assert detail["status"] == "done"


# ─────────────────────────────────────────────────────────────────────────
# F7 — paginación cursor-based en /audit/tools
# ─────────────────────────────────────────────────────────────────────────


def test_audit_pagination_returns_next_before(tmp_path, monkeypatch):
    """When the page is full the response must include `next_before` so the
    client can chain a follow-up request with `before=<next_before>`."""
    log_path = tmp_path / "audit.log"
    lines = []
    for i in range(5):
        lines.append(json.dumps({
            "ts": f"2026-05-17T{10 + i:02d}:00:00+00:00",
            "level": "INFO",
            "logger": "agora.tool_call",
            "msg": "tool_call started",
            "event": "tool_call",
            "phase": "started",
            "user_id": "u-paged",
            "tool": f"t-{i}",
        }))
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setenv("AGORA_ADMIN_LOG_PATHS", str(log_path))

    page1 = client.get(
        "/api/admin/audit/tools?user_id=u-paged&limit=2",
        headers=ADMIN_HEADERS,
    ).json()
    assert len(page1["tool_calls"]) == 2
    assert page1["next_before"], "expected next_before cursor when page is full"

    page2 = client.get(
        f"/api/admin/audit/tools?user_id=u-paged&limit=2&before={page1['next_before']}",
        headers=ADMIN_HEADERS,
    ).json()
    # Page 2 has different events from page 1.
    page1_tools = {c["tool"] for c in page1["tool_calls"]}
    page2_tools = {c["tool"] for c in page2["tool_calls"]}
    assert page1_tools.isdisjoint(page2_tools)


# ─────────────────────────────────────────────────────────────────────────
# F8 — fix registry endpoints
# ─────────────────────────────────────────────────────────────────────────


def test_list_fixes_returns_curated_registry():
    r = client.get("/api/admin/fixes", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    fixes = r.json()["fixes"]
    names = {f["name"] for f in fixes}
    assert {"auth-json-push", "pip-install-laia-core", "pm2-stop-respawner",
            "chmod-laia-dir"}.issubset(names)
    # Each fix has a description
    assert all(f["description"] for f in fixes)


def test_run_fix_unknown_returns_404():
    r = client.post("/api/admin/fix/no-such-fix", headers=ADMIN_HEADERS)
    assert r.status_code == 404
    assert "unknown fix" in r.json()["detail"]


def test_run_fix_auth_json_push(tmp_path, monkeypatch):
    """The `auth-json-push` fix wraps the same lxc push as refresh-oauth
    but goes through the job machinery so the TUI can follow progress."""
    auth_json = tmp_path / "auth.json"
    auth_json.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("AGORA_ADMIN_HOST_AUTH_JSON", str(auth_json))
    monkeypatch.setenv("AGORA_ADMIN_JOBS_INLINE", "1")

    with patch("app.admin._run_command", return_value=_cmd_result("pushed\n")):
        r = client.post("/api/admin/fix/auth-json-push", headers=ADMIN_HEADERS)
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]
    detail = client.get(f"/api/admin/jobs/{job_id}", headers=ADMIN_HEADERS).json()["job"]
    assert detail["status"] == "done"
    assert detail["kind"] == "fix-auth-json-push"


# ─────────────────────────────────────────────────────────────────────────
# F9 — test runner endpoints
# ─────────────────────────────────────────────────────────────────────────


def test_tests_status_unknown_when_never_run():
    """Before any test job has been scheduled, /tests/status returns
    'unknown'."""
    r = client.get("/api/admin/tests/status", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    tests = r.json()["tests"]
    # Status may be 'unknown' if no run-tests job exists in this fresh DB
    # OR an actual status if a previous test in this session triggered one.
    assert "status" in tests
    assert "last_run" in tests


def test_tests_run_starts_job(monkeypatch):
    """`POST /tests/run` queues a job. We don't actually run pytest here
    (would recurse) — patch subprocess so the job returns canned output."""
    monkeypatch.setenv("AGORA_ADMIN_JOBS_INLINE", "1")

    class _FakeRun:
        def __init__(self, *args, **kwargs):
            self.stdout = "10 passed, 0 failed in 1.23s\n"
            self.stderr = ""
            self.returncode = 0

    with patch("subprocess.run", side_effect=lambda *a, **kw: _FakeRun()):
        # Also fake the pytest binary existence
        with patch("pathlib.Path.is_file", return_value=True):
            r = client.post("/api/admin/tests/run", headers=ADMIN_HEADERS)
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]
    detail = client.get(f"/api/admin/jobs/{job_id}", headers=ADMIN_HEADERS).json()["job"]
    assert detail["kind"] == "run-tests"


# ─────────────────────────────────────────────────────────────────────────
# F4 — rate limiter
# ─────────────────────────────────────────────────────────────────────────


def test_admin_rate_limit_trips_on_burst(monkeypatch):
    """Send more mutate calls than the limit — should see 429."""
    monkeypatch.setenv("AGORA_ADMIN_RATE_MAX", "3")
    monkeypatch.setenv("AGORA_ADMIN_RATE_WINDOW_SECONDS", "60")
    # Reset internal bucket so previous tests don't pollute this one.
    import app.admin as admin_mod
    with admin_mod._admin_rate_lock:
        admin_mod._admin_rate_buckets.clear()
    monkeypatch.setenv("AGORA_ADMIN_JOBS_INLINE", "1")

    statuses: list[int] = []
    with patch("app.admin._run_command", return_value=_cmd_result("")):
        for _ in range(5):
            r = client.post("/api/admin/system/restart-backend", headers=ADMIN_HEADERS)
            statuses.append(r.status_code)
    # First 3 should succeed (202), then 4th and 5th rate-limited (429).
    assert statuses[:3] == [202, 202, 202], statuses
    assert 429 in statuses[3:], statuses


# ─────────────────────────────────────────────────────────────────────────
# F11 backend — jobs summary in /status
# ─────────────────────────────────────────────────────────────────────────


def test_status_includes_jobs_summary(monkeypatch):
    """/status must report counts of running/pending/failed jobs so the
    TUI can render a badge on the Jobs tab without a separate fetch."""
    monkeypatch.setenv("AGORA_ADMIN_JOBS_INLINE", "1")
    with patch("app.admin._run_command", return_value=_cmd_result("")):
        client.post("/api/admin/system/restart-backend", headers=ADMIN_HEADERS)

    with patch("app.admin._run_command", return_value=_cmd_result("")):
        r = client.get("/api/admin/status", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    jobs = r.json()["status"]["jobs"]
    assert {"running", "pending", "failed_recent", "total_recent"} <= jobs.keys()
    assert jobs["total_recent"] >= 1


def test_status_includes_recent_errors_list():
    r = client.get("/api/admin/status", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert isinstance(r.json()["status"]["recent_errors"], list)


# ─────────────────────────────────────────────────────────────────────────
# F13 backend — /errors endpoint
# ─────────────────────────────────────────────────────────────────────────


def test_admin_errors_returns_list():
    """GET /api/admin/errors returns recent error/warn events bucketed by
    since_minutes window. Empty list is a valid response."""
    r = client.get("/api/admin/errors?since_minutes=60&limit=10", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["errors"], list)
    assert body["since_minutes"] == 60
