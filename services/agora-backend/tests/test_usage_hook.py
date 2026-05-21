"""Tests for the automatic usage-tracking hook (Fase 0.1) and the chat
budget pre-check (Fase 0.2).

The hook lives in ``app.agent_pool.record_usage_for_session`` and is
called from chat_engine / scheduler / webhooks after every successful
``run_conversation``. We don't need a live LLM: we drive the hook
directly with synthetic outputs that mirror what each provider returns.
"""

from __future__ import annotations

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
            "VALUES (?, ?, ?, 'employee', NULL, ?, NULL, 1, ?, ?)",
            (uid, username, username, f"tok-{username}", ts, ts),
        )
        store.db.conn.commit()
        return uid
    return _make


# ── _extract_tokens ─────────────────────────────────────────────────────


def test_extract_tokens_anthropic_style():
    from app.agent_pool import _extract_tokens
    out = {"response": "hi", "usage": {"input_tokens": 42, "output_tokens": 7}}
    tin, tout, est = _extract_tokens(out)
    assert (tin, tout, est) == (42, 7, False)


def test_extract_tokens_openai_style():
    from app.agent_pool import _extract_tokens
    out = {"response": "hi", "usage": {"prompt_tokens": 100, "completion_tokens": 50}}
    tin, tout, est = _extract_tokens(out)
    assert (tin, tout, est) == (100, 50, False)


def test_extract_tokens_fallback_estimate_marks_estimated():
    from app.agent_pool import _extract_tokens
    out = {"response": "a" * 400}  # no usage block at all
    tin, tout, est = _extract_tokens(out)
    assert est is True
    assert tin == 0
    assert tout >= 1  # 400 // 4 = 100, but the floor of max(1, …) keeps it >0


def test_extract_tokens_nested_usage_under_response():
    from app.agent_pool import _extract_tokens
    out = {"response": {"text": "ok", "usage": {"input_tokens": 9, "output_tokens": 2}}}
    tin, tout, est = _extract_tokens(out)
    assert (tin, tout, est) == (9, 2, False)


# ── record_usage_for_session ───────────────────────────────────────────


def test_record_usage_persists_row(make_user):
    from app.agent_pool import LLMSessionConfig, record_usage_for_session
    from app.storage import store

    uid = make_user("hook")
    cfg = LLMSessionConfig(
        provider="anthropic", api_key=None, base_url=None,
        model="claude-haiku-4-5", api_mode=None,
    )
    run_output = {"response": "ok", "usage": {"input_tokens": 100, "output_tokens": 50}}
    record_usage_for_session(
        user_id=uid, session_id="s-test",
        llm_config=cfg, run_output=run_output, kind="chat",
    )
    since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    totals = store.usage_total_for(uid, since_iso=since)
    assert totals["calls"] == 1
    assert totals["tokens_input"] == 100
    assert totals["tokens_output"] == 50
    # Cost should be computed (haiku is in the pricing table).
    assert totals["cost_usd"] > 0


def test_record_usage_uses_est_suffix_when_estimated(make_user):
    from app.agent_pool import LLMSessionConfig, record_usage_for_session
    from app.storage import store

    uid = make_user("est")
    cfg = LLMSessionConfig(
        provider="unknown-prov", api_key=None, base_url=None,
        model="mystery", api_mode=None,
    )
    record_usage_for_session(
        user_id=uid, session_id=None,
        llm_config=cfg,
        run_output={"response": "x" * 200},  # no usage → estimate
        kind="chat",
    )
    row = store.db.conn.execute(
        "SELECT kind FROM usage_ledger WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (uid,),
    ).fetchone()
    assert row is not None
    assert row["kind"] == "chat:est"


def test_record_usage_never_raises_on_bad_input(make_user):
    """Hook is best-effort; bad shape must be swallowed."""
    from app.agent_pool import LLMSessionConfig, record_usage_for_session
    uid = make_user("safe")
    cfg = LLMSessionConfig(
        provider=None, api_key=None, base_url=None, model=None, api_mode=None,
    )
    # Pass garbage — should not raise.
    record_usage_for_session(
        user_id=uid, session_id=None, llm_config=cfg,
        run_output=object(),  # not a dict / str
        kind="chat",
    )


# ── Budget pre-check on chat endpoint (Fase 0.2) ────────────────────────


def test_chat_returns_429_when_budget_exceeded(app_client, make_user):
    """When ``store.budget_exceeded`` returns True, /api/agents/me/chat
    must reject with 429 *before* invoking the LLM."""
    from app.storage import store
    from app.models import Agent, now_iso

    # Seed a user with a tiny daily cap + agent + token + recorded usage
    # already past the cap, so the pre-check trips on the very first chat.
    uid = make_user("over")
    user = store.user_by_id(uid)
    assert user is not None
    user.token = f"tok-{uid}"
    user.llm_provider = "anthropic"
    user.llm_api_key = "sk-test"
    user.llm_model = "claude-haiku-4-5"
    # Provision a placeholder agent so chat doesn't 404 first.
    agent_id = f"agent_{uid}"
    store.save_agent(Agent(
        id=agent_id, user_id=uid, container_name=f"laia-{user.username}",
        status="running", workspace_path="/tmp/x", container_ip="127.0.0.1",
        api_token="exec-tok", created_at=now_iso(), updated_at=now_iso(),
    ))
    user.agent_id = agent_id
    store.save_user(user)

    store.set_user_budget(uid, daily_usd=0.001)
    store.record_usage(
        user_id=uid, provider="anthropic", model="claude-haiku-4-5",
        tokens_input=1_000_000, tokens_output=1_000_000, cost_usd=1.0,
    )

    r = app_client.post(
        "/api/agents/me/chat",
        headers={"Authorization": f"Bearer {user.token}"},
        json={"message": "hello"},
    )
    assert r.status_code == 429, r.text
    detail = r.json().get("detail") or {}
    assert isinstance(detail, dict)
    assert detail.get("error") == "budget exceeded"
    assert "daily" in (detail.get("reason") or "").lower()
