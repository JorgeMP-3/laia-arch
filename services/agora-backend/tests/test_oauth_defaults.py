"""Tests for the OAuth-by-default LLM provider config.

Three behaviours under test:

1. ``POST /api/users`` populates ``llm_provider="openai-codex"`` (and
   model/api_mode) so new hires inherit the admin's ChatGPT Teams OAuth
   without anyone pasting a key.
2. ``chat_engine.provider_uses_oauth`` correctly identifies oauth_external
   providers, and ``chat_stream`` does NOT emit a "missing api key" error
   for them.
3. ``AGORA_DEFAULT_PROVIDER`` env var overrides the default — operators
   can pin a different provider org-wide.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import store
from app import chat_engine


ADMIN_HEADERS = {"Authorization": "Bearer dev-admin-token"}
client = TestClient(app)


# ---------------------------------------------------------------------------
# provider_uses_oauth
# ---------------------------------------------------------------------------


def test_oauth_providers_recognised():
    assert chat_engine.provider_uses_oauth("openai-codex")
    assert chat_engine.provider_uses_oauth("qwen-oauth")
    assert chat_engine.provider_uses_oauth("google-gemini-cli")
    assert chat_engine.provider_uses_oauth("copilot-acp")


def test_paid_api_providers_not_oauth():
    assert not chat_engine.provider_uses_oauth("anthropic")
    assert not chat_engine.provider_uses_oauth("deepseek")
    assert not chat_engine.provider_uses_oauth("openrouter")
    assert not chat_engine.provider_uses_oauth(None)
    assert not chat_engine.provider_uses_oauth("")


# ---------------------------------------------------------------------------
# POST /api/users defaults
# ---------------------------------------------------------------------------


def _create_user(username: str, **extra) -> dict:
    payload = {"username": username, "display_name": username.title(), "role": "employee"}
    payload.update(extra)
    r = client.post("/api/users", json=payload, headers=ADMIN_HEADERS)
    assert r.status_code in (200, 201), r.text
    return r.json()["user"]


def test_new_user_defaults_to_openai_codex():
    user = _create_user("oauth_default_a")
    assert user["llm_provider"] == "openai-codex"
    # gpt-5.5 is the current default; must be one of the OAuth-compatible
    # models from ARCH's _codex_curated_models (not gpt-5-codex which is
    # API-only).
    assert user["llm_model"] == "gpt-5.5"


def test_reactivate_after_soft_delete():
    """If a username was soft-deleted, POST /api/users revives it with new
    config instead of raising 409. Lets dev loops redeploy the same slug
    without bumping the timestamp."""
    user = _create_user("reactivate_loop_a")
    uid = user["id"]
    # Soft-delete via DELETE endpoint.
    r = client.delete(f"/api/users/{uid}", headers=ADMIN_HEADERS)
    assert r.status_code == 200, r.text
    # Re-creating the same username succeeds (no 409) and returns the same id.
    user2 = _create_user("reactivate_loop_a", display_name="Revived")
    assert user2["id"] == uid
    assert user2["display_name"] == "Revived"


def test_reactivate_does_not_steal_active_username():
    """When the existing user is *still active*, the conflict still fires."""
    _create_user("reactivate_loop_b")
    r = client.post(
        "/api/users",
        json={"username": "reactivate_loop_b", "display_name": "Other", "role": "employee"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 409


def test_reactivate_wipes_prior_credentials():
    """Reactivation must NOT leak the previous owner's api_key, base_url,
    extras, or JWT. The new operator reconfigures explicitly."""
    user = _create_user("reactivate_secret_a")
    uid = user["id"]

    # Populate sensitive fields the previous owner might have set.
    patch = client.patch(
        "/api/user/llm-config",
        json={
            "provider": "anthropic",
            "api_key": "sk-ant-secret-from-prev-owner",
            "base_url": "https://custom.example.com",
        },
        headers={"Authorization": f"Bearer {_bearer_for(uid)}"},
    )
    assert patch.status_code == 200, patch.text
    # Sanity check: the api_key got stored (we read it back via the row).
    row = store.user_by_id(uid)
    assert row.llm_api_key == "sk-ant-secret-from-prev-owner"
    assert row.llm_base_url == "https://custom.example.com"

    # Soft-delete + reactivate.
    r = client.delete(f"/api/users/{uid}", headers=ADMIN_HEADERS)
    assert r.status_code == 200, r.text
    _create_user("reactivate_secret_a", display_name="New Owner")

    # The wiped row must NOT carry the prior owner's secrets.
    row = store.user_by_id(uid)
    assert row.llm_api_key is None, "leaked llm_api_key into reactivated user"
    assert row.llm_base_url is None, "leaked llm_base_url into reactivated user"
    assert row.llm_extras_json is None, "leaked llm_extras_json into reactivated user"
    assert row.token is None, "leaked session JWT into reactivated user"


def _bearer_for(user_id: str) -> str:
    """Helper: mint an access token for ``user_id`` via the test JWT path.

    The test admin already authenticates via ``dev-admin-token``; for the
    user-scoped PATCH above we need a token tied to ``user_id``. We log in
    using the password the create endpoint returned in the dev seed.
    """
    user = store.user_by_id(user_id)
    assert user is not None
    # The create endpoint hashes the auto-generated password and persists
    # the hash, but does NOT keep the cleartext. In tests we reset to a
    # known value directly via the hashing primitive.
    from app.security import hash_password
    user.password = hash_password("test-pw-12345")
    store.save_user(user)
    r = client.post(
        "/api/login",
        json={"username": user.username, "password": "test-pw-12345"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_default_provider_overridable_via_env(monkeypatch):
    monkeypatch.setenv("AGORA_DEFAULT_PROVIDER", "anthropic")
    monkeypatch.setenv("AGORA_DEFAULT_MODEL", "claude-opus-4-6")
    user = _create_user("oauth_default_b")
    assert user["llm_provider"] == "anthropic"
    assert user["llm_model"] == "claude-opus-4-6"


# ---------------------------------------------------------------------------
# chat_engine no longer requires api_key for OAuth providers
# ---------------------------------------------------------------------------


async def _collect(stream) -> list[dict]:
    chunks = []
    async for chunk in stream:
        for line in chunk.decode("utf-8").splitlines():
            if line.startswith("data: "):
                chunks.append(json.loads(line[len("data: "):]))
    return chunks


def test_chat_engine_does_not_reject_oauth_user_without_api_key(monkeypatch):
    """A user with openai-codex and no llm_api_key should NOT short-circuit
    with "no LLM API key configured"."""
    from app.models import User, Agent, now_iso

    # Make sure the worker can build *something* without contacting OpenAI.
    sentinel_response = "OAuth flow OK (stub)"

    class _StubAgent:
        stream_delta_callback = None
        tool_start_callback = None
        tool_complete_callback = None

        def run_conversation(self, message, **_):
            return {"final_response": sentinel_response, "iterations": 0}

    monkeypatch.setattr(
        chat_engine, "get_pool",
        lambda: type("P", (), {
            "get_or_create": staticmethod(lambda *a, **k: type("S", (), {"aiagent": _StubAgent()})()),
        })(),
    )
    # No forwarder needed for this test.
    monkeypatch.setattr(chat_engine, "_load_forwarder", lambda: None)

    user = User(
        id="u-oauth", username="oauthtest", display_name="OAuth Test",
        role="employee", active=True, created_at=now_iso(), updated_at=now_iso(),
        llm_provider="openai-codex",
        llm_api_key=None,
        llm_model="gpt-5-codex",
    )
    agent = Agent(
        id="a-oauth", user_id="u-oauth", container_name="laia-oauthtest",
        status="running", workspace_path="/x",
        container_ip="127.0.0.1", api_token="tk",
        created_at=now_iso(), updated_at=now_iso(),
    )
    events = asyncio.run(_collect(chat_engine.chat_stream(
        user=user, agent=agent, message="hola", session_id=None,
    )))
    # No "no LLM API key" error must appear.
    errors = [e for e in events if e["type"] == "error"]
    assert not any("LLM" in (e.get("message") or "").upper() for e in errors), errors
    # And we got a `done` event with the stub's response.
    done = next(e for e in events if e["type"] == "done")
    assert done["response"] == sentinel_response


def test_chat_engine_still_rejects_paid_provider_without_api_key(monkeypatch):
    """For paid-API providers, the missing-key guard still fires."""
    from app.models import User, Agent, now_iso
    monkeypatch.setattr(chat_engine, "_load_forwarder", lambda: None)
    user = User(
        id="u-paid", username="paiduser", display_name="Paid",
        role="employee", active=True, created_at=now_iso(), updated_at=now_iso(),
        llm_provider="deepseek", llm_api_key=None,
    )
    agent = Agent(
        id="a-paid", user_id="u-paid", container_name="laia-paiduser",
        status="running", workspace_path="/x",
        container_ip="127.0.0.1", api_token="tk",
        created_at=now_iso(), updated_at=now_iso(),
    )
    events = asyncio.run(_collect(chat_engine.chat_stream(
        user=user, agent=agent, message="hola", session_id=None,
    )))
    assert events and events[0]["type"] == "error"
    assert "LLM" in events[0]["message"]
