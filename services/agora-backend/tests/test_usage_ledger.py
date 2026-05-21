"""Tests for usage_ledger + budget caps + pricing (Fase D)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

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
            "VALUES (?, ?, ?, 'employee', NULL, NULL, NULL, 1, ?, ?)",
            (uid, username, username, ts, ts),
        )
        store.db.conn.commit()
        return uid
    return _make


# ── Pricing ───────────────────────────────────────────────────────────────


def test_cost_for_known_provider_model():
    from app.pricing import cost_for
    # claude-haiku-4-5 = (0.80, 4.00) per 1M
    # 1_000_000 tokens_in + 1_000_000 tokens_out → 0.80 + 4.00 = 4.80
    c = cost_for("anthropic", "claude-haiku-4-5", 1_000_000, 1_000_000)
    assert c == pytest.approx(4.80)


def test_cost_for_unknown_returns_none():
    from app.pricing import cost_for
    assert cost_for("totallyfake", "modelx", 1000, 1000) is None
    assert cost_for("", "x", 100, 100) is None


def test_pricing_overrides_via_yaml(tmp_path, monkeypatch):
    from app.config import settings
    from app import pricing
    # Reset cache so the test sees a fresh load.
    pricing._OVERRIDES_CACHE = None
    pricing._OVERRIDES_MTIME = 0.0
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    (tmp_path / "pricing.yaml").write_text(
        "anthropic:\n"
        "  claude-haiku-4-5: [0.10, 0.20]\n",
        encoding="utf-8",
    )
    # Now cost_for should use the override.
    c = pricing.cost_for("anthropic", "claude-haiku-4-5", 1_000_000, 1_000_000)
    assert c == pytest.approx(0.30)


# ── Ledger ────────────────────────────────────────────────────────────────


def test_record_usage_inserts_with_cost(make_user):
    from app.storage import store
    uid = make_user("rec")
    rowid = store.record_usage(
        user_id=uid, provider="anthropic", model="claude-haiku-4-5",
        tokens_input=10_000, tokens_output=2_000,
        cost_usd=10_000 * 0.80 / 1e6 + 2_000 * 4.00 / 1e6,
        kind="chat",
    )
    assert rowid > 0


def test_record_usage_null_cost_ok(make_user):
    from app.storage import store
    uid = make_user("nocost")
    rowid = store.record_usage(
        user_id=uid, provider="unknown", model="ghost",
        tokens_input=1000, tokens_output=500, cost_usd=None,
    )
    assert rowid > 0


def test_usage_total_aggregates_within_window(make_user):
    from app.storage import store
    uid = make_user("agg")
    for i in range(3):
        store.record_usage(
            user_id=uid, provider="anthropic", model="claude-haiku-4-5",
            tokens_input=1000, tokens_output=500, cost_usd=0.01,
        )
    now = datetime.now(timezone.utc)
    since = (now - timedelta(hours=1)).isoformat()
    totals = store.usage_total_for(uid, since_iso=since)
    assert totals["calls"] == 3
    assert totals["tokens_input"] == 3000
    assert totals["tokens_output"] == 1500
    assert totals["cost_usd"] == pytest.approx(0.03)


def test_usage_breakdown_groups_by_provider_model(make_user):
    from app.storage import store
    uid = make_user("brk")
    store.record_usage(user_id=uid, provider="anthropic", model="claude-haiku-4-5",
                       tokens_input=100, tokens_output=50, cost_usd=0.001)
    store.record_usage(user_id=uid, provider="anthropic", model="claude-haiku-4-5",
                       tokens_input=200, tokens_output=100, cost_usd=0.002)
    store.record_usage(user_id=uid, provider="deepseek", model="deepseek-chat",
                       tokens_input=500, tokens_output=300, cost_usd=0.0003)
    since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    rows = store.usage_breakdown_for(uid, since_iso=since)
    by_model = {(r["provider"], r["model"]): r for r in rows}
    assert by_model[("anthropic", "claude-haiku-4-5")]["calls"] == 2
    assert by_model[("deepseek", "deepseek-chat")]["calls"] == 1


# ── Budget caps ───────────────────────────────────────────────────────────


def test_set_and_get_budget(make_user):
    from app.storage import store
    uid = make_user("bud")
    out = store.set_user_budget(uid, daily_usd=1.50, tokens_daily=10_000)
    assert out["daily_usd"] == 1.50
    assert out["monthly_usd"] is None  # unchanged
    assert out["tokens_daily"] == 10_000
    got = store.get_user_budget(uid)
    assert got["daily_usd"] == 1.50
    assert got["tokens_daily"] == 10_000


def test_set_budget_clear_with_none(make_user):
    from app.storage import store
    uid = make_user("budclr")
    store.set_user_budget(uid, daily_usd=1.0)
    store.set_user_budget(uid, daily_usd=None)
    assert store.get_user_budget(uid)["daily_usd"] is None


def test_budget_exceeded_daily_usd_cap(make_user):
    from app.storage import store
    uid = make_user("excd")
    store.set_user_budget(uid, daily_usd=0.005)  # half a cent
    store.record_usage(user_id=uid, provider="anthropic",
                       model="claude-haiku-4-5",
                       tokens_input=1_000_000, tokens_output=100,
                       cost_usd=0.01)  # > cap
    exceeded, reason = store.budget_exceeded(uid)
    assert exceeded is True
    assert "daily" in reason.lower()


def test_budget_under_cap_returns_false(make_user):
    from app.storage import store
    uid = make_user("under")
    store.set_user_budget(uid, daily_usd=10.0)
    store.record_usage(user_id=uid, provider="x", model="y",
                       tokens_input=100, tokens_output=50, cost_usd=0.001)
    exceeded, reason = store.budget_exceeded(uid)
    assert exceeded is False
    assert reason is None


def test_budget_exceeded_tokens_daily_cap(make_user):
    from app.storage import store
    uid = make_user("toks")
    store.set_user_budget(uid, tokens_daily=1_000)
    store.record_usage(user_id=uid, provider="x", model="y",
                       tokens_input=900, tokens_output=200, cost_usd=None)
    exceeded, reason = store.budget_exceeded(uid)
    assert exceeded is True
    assert "tokens" in reason.lower()


# ── Admin endpoints ───────────────────────────────────────────────────────


def test_admin_patch_budget_persists(app_client, make_user):
    uid = make_user("apb")
    r = app_client.patch(
        f"/api/admin/users/{uid}/budget", headers=ADMIN_HEADERS,
        json={"daily_usd": 2.5, "tokens_daily": 50_000},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["budget"]["daily_usd"] == 2.5
    assert body["budget"]["tokens_daily"] == 50_000
    # GET should return the same.
    r2 = app_client.get(f"/api/admin/users/{uid}/budget", headers=ADMIN_HEADERS)
    assert r2.status_code == 200
    assert r2.json()["budget"]["daily_usd"] == 2.5


def test_admin_patch_budget_unknown_user_404(app_client):
    r = app_client.patch(
        "/api/admin/users/user_does_not_exist/budget", headers=ADMIN_HEADERS,
        json={"daily_usd": 1.0},
    )
    assert r.status_code == 404


def test_admin_usage_endpoint_returns_breakdown(app_client, make_user):
    from app.storage import store
    uid = make_user("usg")
    store.record_usage(user_id=uid, provider="anthropic",
                       model="claude-haiku-4-5",
                       tokens_input=1000, tokens_output=500, cost_usd=0.001)
    r = app_client.get(f"/api/admin/usage?user_id={uid}&window=day",
                       headers=ADMIN_HEADERS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["totals"]["calls"] == 1
    assert any(b["provider"] == "anthropic" for b in body["breakdown"])


def test_admin_usage_all_users_lists_only_with_activity(app_client, make_user):
    from app.storage import store
    silent = make_user("silent")  # no usage
    active = make_user("active")
    store.record_usage(user_id=active, provider="x", model="y",
                       tokens_input=10, tokens_output=5, cost_usd=None)
    r = app_client.get("/api/admin/usage?window=day", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    user_ids = {u["user_id"] for u in body["users"]}
    assert active in user_ids
    assert silent not in user_ids


def test_admin_usage_requires_admin(app_client, make_user):
    uid = make_user("noadmin")
    # Login as a regular employee — no token, so just craft an invalid one.
    r = app_client.get("/api/admin/usage", headers={"Authorization": "Bearer not-admin"})
    assert r.status_code in (401, 403)
