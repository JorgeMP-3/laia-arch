"""v0.5 admin endpoints — backend support for the v2 control center.

* ``GET /api/admin/users-overview?window=…``  — single-shot per-user
  roll-up (kills the N+1 of the legacy Cost/Areas tabs).
* ``PATCH /api/admin/users/{user_id}/llm-config`` — admin counterpart
  of the self-side ``/api/user/llm-config``. Powers the new-user wizard.
* ``GET /api/admin/users/{user_id}/scheduled-jobs`` — jobs + webhooks.
* ``GET /api/admin/users/{user_id}/child-runs`` — agent_child_runs for
  one parent user (uses the new ``store.list_child_runs_for_user``).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


ADMIN_HEADERS = {"Authorization": "Bearer dev-admin-token"}


@pytest.fixture(scope="module")
def app_client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def make_user():
    from app.storage import store

    def _make(prefix: str = "u") -> str:
        username = f"{prefix}_{uuid.uuid4().hex[:6]}"
        ts = "2026-01-01T00:00:00+00:00"
        uid = f"user_{username}"
        store.db.conn.execute(
            "INSERT INTO users (id, username, display_name, role, agent_id, token, "
            "password, active, created_at, updated_at) "
            "VALUES (?, ?, ?, 'employee', NULL, ?, NULL, 1, ?, ?)",
            (uid, username, username, f"tok-{username}", ts, ts),
        )
        store.db.conn.commit()
        return uid
    return _make


# ── users-overview ─────────────────────────────────────────────────────


def test_users_overview_returns_one_row_per_user_with_usage_and_budget(
        app_client, make_user):
    from app.storage import store
    uid = make_user("ov")
    store.set_user_budget(uid, daily_usd=3.0)
    store.record_usage(user_id=uid, provider="anthropic",
                       model="claude-haiku-4-5",
                       tokens_input=100, tokens_output=50, cost_usd=0.001)
    r = app_client.get("/api/admin/users-overview?window=day",
                       headers=ADMIN_HEADERS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["window"] == "day"
    assert "since" in body
    rows = body["users"]
    row = next((x for x in rows if x["id"] == uid), None)
    assert row is not None
    assert row["budget"]["daily_usd"] == 3.0
    assert row["usage"]["calls"] == 1
    assert row["usage"]["tokens_input"] == 100
    assert "container_name" in row
    assert "llm_provider" in row
    assert "unread_inbox" in row


def test_users_overview_returns_active_users_inc_laia(app_client):
    r = app_client.get("/api/admin/users-overview", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    usernames = {u["username"] for u in body["users"]}
    # Seeded users that should always be there.
    assert "jorge" in usernames or "laia" in usernames


def test_users_overview_requires_admin(app_client):
    r = app_client.get("/api/admin/users-overview",
                       headers={"Authorization": "Bearer not-admin"})
    assert r.status_code in (401, 403)


def test_users_overview_supports_week_and_month_windows(app_client):
    for window in ("week", "month"):
        r = app_client.get(f"/api/admin/users-overview?window={window}",
                           headers=ADMIN_HEADERS)
        assert r.status_code == 200
        assert r.json()["window"] == window


# ── admin PATCH /users/{id}/llm-config ─────────────────────────────────


def test_admin_patch_user_llm_config_persists(app_client, make_user):
    uid = make_user("llm")
    r = app_client.patch(
        f"/api/admin/users/{uid}/llm-config",
        headers=ADMIN_HEADERS,
        json={"provider": "anthropic", "model": "claude-haiku-4-5",
              "api_key": "sk-test"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "anthropic"
    assert body["model"] == "claude-haiku-4-5"
    assert body["has_key"] is True
    # Read back via users-overview.
    r2 = app_client.get("/api/admin/users-overview", headers=ADMIN_HEADERS)
    row = next(u for u in r2.json()["users"] if u["id"] == uid)
    assert row["llm_provider"] == "anthropic"
    assert row["llm_model"] == "claude-haiku-4-5"


def test_admin_patch_user_llm_config_clears_with_empty_string(app_client, make_user):
    uid = make_user("clr")
    app_client.patch(f"/api/admin/users/{uid}/llm-config",
                     headers=ADMIN_HEADERS,
                     json={"api_key": "x"})
    # Clear by passing "".
    r = app_client.patch(f"/api/admin/users/{uid}/llm-config",
                         headers=ADMIN_HEADERS,
                         json={"api_key": ""})
    assert r.status_code == 200
    assert r.json()["has_key"] is False


def test_admin_patch_user_llm_config_unknown_user_404(app_client):
    r = app_client.patch("/api/admin/users/user_nope/llm-config",
                         headers=ADMIN_HEADERS,
                         json={"provider": "anthropic"})
    assert r.status_code == 404


def test_admin_patch_user_llm_config_requires_admin(app_client, make_user):
    uid = make_user("noauth")
    r = app_client.patch(f"/api/admin/users/{uid}/llm-config",
                         headers={"Authorization": "Bearer wrong"},
                         json={"provider": "anthropic"})
    assert r.status_code in (401, 403)


# ── scheduled-jobs admin ───────────────────────────────────────────────


def test_admin_scheduled_jobs_returns_user_jobs_and_webhooks(
        app_client, make_user):
    from app.storage import store
    from app.models import ScheduledJob, WebhookSubscription
    uid = make_user("sch")
    store.create_scheduled_job(ScheduledJob(
        user_id=uid, name="daily-report",
        cron_expr="0 9 * * *", prompt="resumen", deliver="local",
    ))
    store.create_webhook_subscription(WebhookSubscription(
        user_id=uid, slug=f"wh-{uid[-6:]}", secret="x" * 64,
        prompt="webhook", deliver="local",
    ))
    r = app_client.get(f"/api/admin/users/{uid}/scheduled-jobs",
                       headers=ADMIN_HEADERS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_id"] == uid
    assert len(body["scheduled_jobs"]) >= 1
    assert any(j["name"] == "daily-report" for j in body["scheduled_jobs"])
    assert len(body["webhooks"]) >= 1


def test_admin_scheduled_jobs_unknown_user_404(app_client):
    r = app_client.get("/api/admin/users/user_nope/scheduled-jobs",
                       headers=ADMIN_HEADERS)
    assert r.status_code == 404


# ── child-runs admin ───────────────────────────────────────────────────


def test_admin_child_runs_returns_user_runs(app_client, make_user):
    from app.storage import store
    from app.models import AgentChildRun
    uid = make_user("cr")
    store.create_child_run(AgentChildRun(
        parent_user_id=uid, parent_session_id="sess-1", profile="general",
        purpose="test", prompt="hi", status="done",
    ))
    r = app_client.get(f"/api/admin/users/{uid}/child-runs?limit=5",
                       headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    assert all(c["parent_user_id"] == uid for c in body["child_runs"])


def test_admin_child_runs_respects_limit(app_client, make_user):
    from app.storage import store
    from app.models import AgentChildRun
    uid = make_user("cr2")
    for i in range(3):
        store.create_child_run(AgentChildRun(
            parent_user_id=uid, parent_session_id=f"sess-{i}",
            profile="general", purpose=f"p{i}", prompt="x",
            status="done",
        ))
    r = app_client.get(f"/api/admin/users/{uid}/child-runs?limit=2",
                       headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json()["count"] == 2


def test_list_child_runs_for_user_storage_helper(make_user):
    """Direct test of the new ``store.list_child_runs_for_user``."""
    from app.storage import store
    from app.models import AgentChildRun
    uid = make_user("crh")
    for _ in range(2):
        store.create_child_run(AgentChildRun(
            parent_user_id=uid, parent_session_id="s", profile="general",
            purpose="p", prompt="x", status="done",
        ))
    rows = store.list_child_runs_for_user(uid, limit=10)
    assert len(rows) == 2
    assert all(r.parent_user_id == uid for r in rows)
