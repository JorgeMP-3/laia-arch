"""Tests for the AGORA scheduler (Fase A)."""

from __future__ import annotations

import hmac
import importlib.util
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def make_user():
    from app.storage import store

    def _make(prefix: str = "sched") -> str:
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


@pytest.fixture(scope="module")
def plugin_mod():
    init_py = Path(
        "/home/laia-arch/LAIA/.laia-core/plugins/agent-scheduler/__init__.py"
    )
    spec = importlib.util.spec_from_file_location("_agent_scheduler_test", init_py)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_agent_scheduler_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def _parse(out: str) -> dict:
    return json.loads(out)


# ── Cron parser ────────────────────────────────────────────────────────────


def test_compute_next_run_every_5_min_aligned():
    from app.scheduler import compute_next_run
    base = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)
    nxt = compute_next_run("*/5 * * * *", base=base)
    assert nxt is not None
    assert nxt.minute == 5
    assert nxt.hour == 12


def test_compute_next_run_at_daily_alias():
    from app.scheduler import compute_next_run
    base = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)
    nxt = compute_next_run("@daily", base=base)
    assert nxt is not None
    # @daily = "0 0 * * *" → siguiente medianoche UTC.
    assert nxt.hour == 0
    assert nxt.minute == 0
    assert nxt > base


def test_compute_next_run_one_shot_in_10m():
    from app.scheduler import compute_next_run, is_one_shot
    base = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)
    nxt = compute_next_run("in 10m", base=base)
    assert nxt == base + timedelta(minutes=10)
    assert is_one_shot("in 10m") is True
    assert is_one_shot("*/5 * * * *") is False


def test_compute_next_run_invalid_returns_none():
    from app.scheduler import compute_next_run
    assert compute_next_run("not-a-cron") is None
    assert compute_next_run("") is None
    assert compute_next_run("60 * * * *") is None  # minute>59 → empty set → never matches


# ── Job CRUD via plugin ────────────────────────────────────────────────────


def test_create_job_inserts_with_next_run_at(plugin_mod, make_user):
    uid = make_user("create")
    plugin_mod.set_session_context(uid)
    res = _parse(plugin_mod._schedule_create({
        "name": "hello-tick",
        "cron_expr": "*/5 * * * *",
        "prompt": "di hola",
    }))
    assert res["ok"] is True
    assert res["job"]["name"] == "hello-tick"
    assert res["job"]["next_run_at"] is not None
    assert res["job"]["status"] == "active"


def test_create_job_with_invalid_cron_rejected(plugin_mod, make_user):
    uid = make_user("invcron")
    plugin_mod.set_session_context(uid)
    res = _parse(plugin_mod._schedule_create({
        "name": "bad",
        "cron_expr": "not-a-cron-expr",
        "prompt": "hi",
    }))
    assert res["ok"] is False
    assert "invalid" in res["error"].lower()


def test_pause_and_resume_recomputes_next_run_at(plugin_mod, make_user):
    uid = make_user("pause")
    plugin_mod.set_session_context(uid)
    created = _parse(plugin_mod._schedule_create({
        "name": "pauseme", "cron_expr": "@hourly", "prompt": "p",
    }))
    jid = created["job"]["id"]

    paused = _parse(plugin_mod._schedule_pause({"job_id": jid}))
    assert paused["ok"] is True
    assert paused["job"]["status"] == "paused"
    assert paused["job"]["next_run_at"] is None

    resumed = _parse(plugin_mod._schedule_resume({"job_id": jid}))
    assert resumed["ok"] is True
    assert resumed["job"]["status"] == "active"
    assert resumed["job"]["next_run_at"] is not None


def test_cross_user_isolation_schedule_list(plugin_mod, make_user):
    a = make_user("alice")
    b = make_user("bob")
    plugin_mod.set_session_context(a)
    plugin_mod._schedule_create({"name": "secret-a", "cron_expr": "@daily", "prompt": "x"})

    plugin_mod.set_session_context(b)
    listed = _parse(plugin_mod._schedule_list({}))
    assert all(j["name"] != "secret-a" for j in listed["jobs"])


def test_pause_someone_elses_job_rejected(plugin_mod, make_user):
    owner = make_user("owner")
    other = make_user("other")
    plugin_mod.set_session_context(owner)
    job = _parse(plugin_mod._schedule_create({
        "name": "mine", "cron_expr": "@daily", "prompt": "x"}))
    jid = job["job"]["id"]

    plugin_mod.set_session_context(other)
    res = _parse(plugin_mod._schedule_pause({"job_id": jid}))
    assert res["ok"] is False
    assert "not yours" in res["error"]


def test_delete_removes_row(plugin_mod, make_user):
    uid = make_user("del")
    plugin_mod.set_session_context(uid)
    job = _parse(plugin_mod._schedule_create({
        "name": "dropme", "cron_expr": "@hourly", "prompt": "x"}))
    jid = job["job"]["id"]
    res = _parse(plugin_mod._schedule_delete({"job_id": jid}))
    assert res["ok"] is True
    listed = _parse(plugin_mod._schedule_list({}))
    assert all(j["id"] != jid for j in listed["jobs"])


# ── Webhook tools ──────────────────────────────────────────────────────────


def test_webhook_subscribe_returns_url_and_secret(plugin_mod, make_user):
    uid = make_user("wh")
    plugin_mod.set_session_context(uid)
    res = _parse(plugin_mod._webhook_subscribe({
        "slug": f"hook-{uuid.uuid4().hex[:6]}",
        "prompt": "Resume el body",
    }))
    assert res["ok"] is True
    assert res["subscription"]["secret"]
    assert "/api/webhooks/" in res["url"]


def test_webhook_subscribe_rejects_duplicate_slug(plugin_mod, make_user):
    uid = make_user("dup")
    plugin_mod.set_session_context(uid)
    slug = f"hook-{uuid.uuid4().hex[:6]}"
    plugin_mod._webhook_subscribe({"slug": slug, "prompt": "x"})
    res = _parse(plugin_mod._webhook_subscribe({"slug": slug, "prompt": "y"}))
    assert res["ok"] is False
    assert "taken" in res["error"]


def test_webhook_list_hides_secret(plugin_mod, make_user):
    uid = make_user("hide")
    plugin_mod.set_session_context(uid)
    plugin_mod._webhook_subscribe({
        "slug": f"hook-{uuid.uuid4().hex[:6]}", "prompt": "p",
    })
    listed = _parse(plugin_mod._webhook_list({}))
    assert listed["ok"] is True
    assert all(s["secret"] == "***" for s in listed["subscriptions"])


def test_webhook_endpoint_validates_hmac():
    from app.main import app
    from app.storage import store
    from app.models import WebhookSubscription
    from app.webhooks import generate_secret, compute_hmac

    # Make a user + subscription directly.
    user_id = f"user_whepu_{uuid.uuid4().hex[:6]}"
    ts = "2026-01-01T00:00:00+00:00"
    store.db.conn.execute(
        "INSERT INTO users (id, username, display_name, role, agent_id, token, "
        "password, active, created_at, updated_at) "
        "VALUES (?, ?, ?, 'employee', NULL, NULL, NULL, 1, ?, ?)",
        (user_id, user_id, user_id, ts, ts),
    )
    store.db.conn.commit()
    secret = generate_secret()
    slug = f"hooktest-{uuid.uuid4().hex[:6]}"
    sub = WebhookSubscription(user_id=user_id, slug=slug, secret=secret,
                               prompt="echo")
    store.create_webhook_subscription(sub)

    client = TestClient(app)
    body = b'{"event":"test"}'
    # No signature → 401.
    r = client.post(f"/api/webhooks/{slug}", content=body)
    assert r.status_code == 401

    # Bad signature → 401.
    r = client.post(f"/api/webhooks/{slug}", content=body,
                    headers={"X-Laia-Signature": "deadbeef"})
    assert r.status_code == 401

    # Correct signature → some non-401 (200 with ok=false because the LLM
    # call will fail in test, but the auth passed).
    sig = compute_hmac(secret, body)
    r = client.post(f"/api/webhooks/{slug}", content=body,
                    headers={"X-Laia-Signature": sig})
    assert r.status_code in (200,), r.text


def test_webhook_endpoint_unknown_slug_returns_404():
    from app.main import app
    client = TestClient(app)
    r = client.post("/api/webhooks/does-not-exist-zzz", content=b"{}",
                    headers={"X-Laia-Signature": "x"})
    assert r.status_code == 404


# ── Job runner (tick) ──────────────────────────────────────────────────────


def test_run_one_job_increments_runs_total_on_success(monkeypatch, make_user):
    from app import scheduler as sched_mod
    from app.scheduler import create_job_with_next_run, _run_one_job
    from app.storage import store

    uid = make_user("runok")
    # Stub AgentPool.get_or_create → fake session whose aiagent.run_conversation
    # returns a string. Avoids LLM/OAuth entirely.
    class _FakeAgent:
        def run_conversation(self, prompt):
            return "scheduled job ran"
    class _FakeSession:
        aiagent = _FakeAgent()
    class _FakePool:
        def get_or_create(self, **_):
            return _FakeSession()
        def evict(self, *_a, **_k):
            return True
    monkeypatch.setattr("app.chat_engine.get_pool", lambda: _FakePool())

    job = create_job_with_next_run(
        user_id=uid, name="t1", cron_expr="@hourly",
        prompt="run me", deliver="local",
    )
    _run_one_job(job.id)

    updated = store.get_scheduled_job(job.id)
    assert updated.runs_total == 1
    assert updated.runs_failed == 0
    assert updated.last_error is None
    assert "scheduled job ran" in (updated.last_result or "")


def test_run_one_job_failure_increments_runs_failed(monkeypatch, make_user):
    from app.scheduler import create_job_with_next_run, _run_one_job
    from app.storage import store

    uid = make_user("runerr")
    class _BoomAgent:
        def run_conversation(self, prompt):
            raise RuntimeError("LLM offline")
    class _BoomSession:
        aiagent = _BoomAgent()
    class _BoomPool:
        def get_or_create(self, **_):
            return _BoomSession()
        def evict(self, *_a, **_k):
            return True
    monkeypatch.setattr("app.chat_engine.get_pool", lambda: _BoomPool())

    job = create_job_with_next_run(
        user_id=uid, name="t2", cron_expr="@hourly",
        prompt="run me", deliver="local",
    )
    _run_one_job(job.id)

    updated = store.get_scheduled_job(job.id)
    assert updated.runs_failed == 1
    assert updated.consecutive_failures == 1
    assert "LLM offline" in (updated.last_error or "")
    assert updated.status == "active"  # not yet 5 failures


def test_five_consecutive_failures_marks_error(monkeypatch, make_user):
    from app.scheduler import create_job_with_next_run, _run_one_job
    from app.storage import store

    uid = make_user("fivefail")
    class _BoomAgent:
        def run_conversation(self, prompt):
            raise RuntimeError("nope")
    class _BoomSession:
        aiagent = _BoomAgent()
    class _BoomPool:
        def get_or_create(self, **_):
            return _BoomSession()
        def evict(self, *_a, **_k):
            return True
    monkeypatch.setattr("app.chat_engine.get_pool", lambda: _BoomPool())

    job = create_job_with_next_run(
        user_id=uid, name="t3", cron_expr="@hourly", prompt="x", deliver="local",
    )
    for _ in range(5):
        _run_one_job(job.id)

    updated = store.get_scheduled_job(job.id)
    assert updated.status == "error"
    assert updated.consecutive_failures == 5


def test_one_shot_job_pauses_after_run(monkeypatch, make_user):
    from app.scheduler import create_job_with_next_run, _run_one_job
    from app.storage import store

    uid = make_user("oneshot")
    class _OkAgent:
        def run_conversation(self, prompt):
            return "done"
    class _S:
        aiagent = _OkAgent()
    class _P:
        def get_or_create(self, **_):
            return _S()
        def evict(self, *_a, **_k):
            return True
    monkeypatch.setattr("app.chat_engine.get_pool", lambda: _P())

    job = create_job_with_next_run(
        user_id=uid, name="oneshot", cron_expr="in 1m",
        prompt="run me once", deliver="local",
    )
    _run_one_job(job.id)
    updated = store.get_scheduled_job(job.id)
    assert updated.status == "paused"
    assert updated.next_run_at is None


# ── Deliver ────────────────────────────────────────────────────────────────


def test_deliver_local_logs_only():
    from app.scheduler import deliver_result
    assert deliver_result("hello", "local") == "local"


def test_deliver_unknown_spec_falls_back_to_local():
    from app.scheduler import deliver_result
    assert deliver_result("hello", "nonsense:1234") == "local"


def test_deliver_origin_with_no_telegram_falls_back(make_user):
    from app.scheduler import deliver_result
    uid = make_user("noorigin")
    assert deliver_result("hi", "origin", user_id=uid) == "local"
