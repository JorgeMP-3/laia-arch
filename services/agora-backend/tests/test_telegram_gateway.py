"""Tests for the AGORA Telegram gateway — uses a fake HTTP client."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.storage import store
from app.telegram_gateway import (
    HELP_TEXT,
    ONBOARDING_HINT,
    ALREADY_LINKED_HINT,
    TelegramGateway,
    TelegramHTTPClient,
    TelegramUpdate,
)
from app.telegram_links import link_token_store


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeClient:
    """Minimal stand-in for TelegramHTTPClient — captures sends and feeds updates."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.queued: list[list[dict[str, Any]]] = []

    async def get_updates(self, offset: int, timeout: int = 0) -> list[dict[str, Any]]:
        if self.queued:
            return self.queued.pop(0)
        return []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))

    async def close(self) -> None:
        return


def _msg(update_id: int, *, user_id: int, chat_id: int, text: str) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "message": {
            "text": text,
            "chat": {"id": chat_id},
            "from": {"id": user_id},
        },
    }


def _seed_user(username: str) -> str:
    existing = store.user_by_username(username)
    if existing:
        return existing.id
    from app.models import User, new_id, now_iso

    user = User(
        id=new_id("usr"),
        username=username,
        display_name=username.title(),
        role="employee",
        active=True,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    store.save_user(user)
    return user.id


async def _drive_once(gw: TelegramGateway, client: _FakeClient, updates: list[dict[str, Any]]) -> None:
    """Feed a single batch and drive the handler manually (no long-poll loop)."""
    client.queued.append(updates)
    raw = await client.get_updates(0)
    for payload in raw:
        u = TelegramUpdate.from_payload(payload)
        if u is None:
            continue
        await gw._handle_update(u)


# ---------------------------------------------------------------------------
# Update parsing
# ---------------------------------------------------------------------------


def test_update_parser_skips_non_text():
    assert TelegramUpdate.from_payload({"update_id": 1, "message": {}}) is None
    assert TelegramUpdate.from_payload({"update_id": 1}) is None


def test_update_parser_accepts_edited_message():
    u = TelegramUpdate.from_payload({
        "update_id": 2,
        "edited_message": {"text": "hola", "chat": {"id": 5}, "from": {"id": 9}},
    })
    assert u is not None
    assert u.message_text == "hola"


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def test_start_sends_onboarding_when_not_linked():
    client = _FakeClient()
    gw = TelegramGateway(client, turn_fn=lambda *_: asyncio.sleep(0, result="x"))
    asyncio.run(_drive_once(gw, client, [_msg(1, user_id=8001, chat_id=8001, text="/start")]))
    assert client.sent == [(8001, ONBOARDING_HINT)]


def test_start_sends_linked_hint_when_already_linked():
    uid = _seed_user("tg_already_linked")
    store.link_telegram_user("8002", uid)
    client = _FakeClient()
    gw = TelegramGateway(client)
    asyncio.run(_drive_once(gw, client, [_msg(2, user_id=8002, chat_id=8002, text="/start")]))
    assert client.sent == [(8002, ALREADY_LINKED_HINT)]
    store.unlink_telegram_user(telegram_user_id="8002")


def test_help_returns_help_text():
    client = _FakeClient()
    gw = TelegramGateway(client)
    asyncio.run(_drive_once(gw, client, [_msg(3, user_id=8003, chat_id=8003, text="/help")]))
    assert client.sent == [(8003, HELP_TEXT)]


def test_link_with_no_token_returns_usage():
    client = _FakeClient()
    gw = TelegramGateway(client)
    asyncio.run(_drive_once(gw, client, [_msg(4, user_id=8004, chat_id=8004, text="/link")]))
    assert "Uso:" in client.sent[0][1]


def test_link_with_invalid_token():
    client = _FakeClient()
    gw = TelegramGateway(client)
    asyncio.run(_drive_once(gw, client, [_msg(5, user_id=8005, chat_id=8005, text="/link bogus")]))
    assert "inválido" in client.sent[0][1]


def test_link_with_valid_token_binds_user():
    uid = _seed_user("tg_link_valid")
    issued = link_token_store.issue(uid)
    client = _FakeClient()
    gw = TelegramGateway(client)
    asyncio.run(_drive_once(gw, client, [
        _msg(6, user_id=8006, chat_id=8006, text=f"/link {issued.token}"),
    ]))
    assert any("enlazado" in t for _, t in client.sent)
    assert store.agora_user_for_telegram("8006") == uid
    store.unlink_telegram_user(telegram_user_id="8006")


def test_link_accepts_deep_link_prefix():
    """Telegram delivers ``/start link_<token>`` for the t.me deep-link UX —
    the /link handler should also accept a bare ``link_<token>`` argument."""
    uid = _seed_user("tg_link_deep")
    issued = link_token_store.issue(uid)
    client = _FakeClient()
    gw = TelegramGateway(client)
    asyncio.run(_drive_once(gw, client, [
        _msg(7, user_id=8007, chat_id=8007, text=f"/link link_{issued.token}"),
    ]))
    assert store.agora_user_for_telegram("8007") == uid
    store.unlink_telegram_user(telegram_user_id="8007")


def test_unlink_removes_binding():
    uid = _seed_user("tg_unlink_flow")
    store.link_telegram_user("8008", uid)
    client = _FakeClient()
    gw = TelegramGateway(client)
    asyncio.run(_drive_once(gw, client, [_msg(8, user_id=8008, chat_id=8008, text="/unlink")]))
    assert "Desvinculado" in client.sent[0][1]
    assert store.agora_user_for_telegram("8008") is None


def test_unlink_when_not_linked_returns_onboarding():
    client = _FakeClient()
    gw = TelegramGateway(client)
    asyncio.run(_drive_once(gw, client, [_msg(9, user_id=8009, chat_id=8009, text="/unlink")]))
    assert client.sent == [(8009, ONBOARDING_HINT)]


def test_chat_message_when_unlinked_returns_onboarding():
    called: list[str] = []

    async def fake_turn(agora_user_id: str, text: str) -> str:
        called.append(agora_user_id)
        return "should not be called"

    client = _FakeClient()
    gw = TelegramGateway(client, turn_fn=fake_turn)
    asyncio.run(_drive_once(gw, client, [_msg(10, user_id=8010, chat_id=8010, text="hola")]))
    assert client.sent == [(8010, ONBOARDING_HINT)]
    assert called == []


def test_chat_message_when_linked_calls_turn_fn():
    uid = _seed_user("tg_chat_flow")
    store.link_telegram_user("8011", uid)

    received: list[tuple[str, str]] = []

    async def fake_turn(agora_user_id: str, text: str) -> str:
        received.append((agora_user_id, text))
        return f"echo: {text}"

    client = _FakeClient()
    gw = TelegramGateway(client, turn_fn=fake_turn)
    asyncio.run(_drive_once(gw, client, [_msg(11, user_id=8011, chat_id=8011, text="hola mundo")]))
    assert received == [(uid, "hola mundo")]
    assert client.sent == [(8011, "echo: hola mundo")]
    store.unlink_telegram_user(telegram_user_id="8011")


def test_chat_turn_failure_is_surfaced_to_user():
    uid = _seed_user("tg_chat_fail")
    store.link_telegram_user("8012", uid)

    async def fake_turn(agora_user_id: str, text: str) -> str:
        raise RuntimeError("boom")

    client = _FakeClient()
    gw = TelegramGateway(client, turn_fn=fake_turn)
    asyncio.run(_drive_once(gw, client, [_msg(12, user_id=8012, chat_id=8012, text="trigger")]))
    assert "Error" in client.sent[0][1] and "boom" in client.sent[0][1]
    store.unlink_telegram_user(telegram_user_id="8012")


def test_agent_pool_turn_returns_final_response_string_not_dict(monkeypatch):
    """Regression: the gateway used to ``return run(message)`` directly,
    which is a dict, so Telegram users got the raw AIAgent trace dumped
    into the chat. After the fix the gateway extracts ``final_response``.
    """
    from app import telegram_gateway as tg

    uid = _seed_user("tg_dict_extract")
    user = store.user_by_id(uid)
    assert user is not None
    user.llm_provider = "openai-codex"
    user.llm_model = "gpt-5.5"
    store.save_user(user)

    fake_run_output = {
        "final_response": "Hola, soy jorge-dev.",
        "messages": [
            {"role": "user", "content": "hola"},
            {"role": "assistant", "content": "Hola, soy jorge-dev."},
        ],
        "input_tokens": 100, "output_tokens": 7,
    }

    class _FakeSession:
        class _AI:
            def run_conversation(self, *a, **kw):
                return fake_run_output
        aiagent = _AI()

    class _FakePool:
        def get_or_create(self, **_): return _FakeSession()

    monkeypatch.setattr(tg, "_shared_pool", lambda: _FakePool())
    result = asyncio.run(tg._agent_pool_turn(uid, "hola"))
    assert result == "Hola, soy jorge-dev.", f"got: {result!r}"
    assert "{" not in result, "raw dict leaked into chat reply"


def test_agent_pool_turn_falls_back_to_last_assistant_message(monkeypatch):
    """When ``final_response``/``response`` are missing the gateway must
    still extract the last assistant content from ``messages``."""
    from app import telegram_gateway as tg

    uid = _seed_user("tg_fallback")
    user = store.user_by_id(uid)
    assert user is not None
    user.llm_provider = "openai-codex"
    store.save_user(user)

    class _FakeSession:
        class _AI:
            def run_conversation(self, *a, **kw):
                return {
                    "messages": [
                        {"role": "user", "content": "hola"},
                        {"role": "assistant", "content": "respuesta-final"},
                    ],
                }
        aiagent = _AI()

    class _FakePool:
        def get_or_create(self, **_): return _FakeSession()

    monkeypatch.setattr(tg, "_shared_pool", lambda: _FakePool())
    result = asyncio.run(tg._agent_pool_turn(uid, "hola"))
    assert result == "respuesta-final"


def test_agent_pool_turn_oauth_provider_doesnt_require_api_key(monkeypatch):
    """Regression: telegram_gateway._agent_pool_turn rejected OAuth users
    because the guard only checked llm_api_key. After the fix it must
    accept providers like ``openai-codex`` even with api_key=None."""
    from app import telegram_gateway as tg

    uid = _seed_user("tg_oauth")
    user = store.user_by_id(uid)
    assert user is not None
    user.llm_provider = "openai-codex"
    user.llm_api_key = None
    user.llm_model = "gpt-5.5"
    store.save_user(user)

    # Force the pool path to skip actual AIAgent construction so the test
    # doesn't need a live LLM. We just need the gate to NOT short-circuit.
    class _FakeSession:
        class _AI:
            def run_conversation(self, *a, **kw):
                return "ok"
        aiagent = _AI()

    class _FakePool:
        def get_or_create(self, **_): return _FakeSession()

    monkeypatch.setattr(tg, "_shared_pool", lambda: _FakePool())

    result = asyncio.run(tg._agent_pool_turn(uid, "hola"))
    assert "API key del LLM" not in result, (
        "OAuth user shouldn't trip the api_key guard"
    )


def test_agent_pool_turn_still_rejects_non_oauth_without_api_key():
    """Counterpart: a user on a non-OAuth provider with no api_key must
    still get the configuration warning."""
    from app import telegram_gateway as tg
    uid = _seed_user("tg_noapi")
    user = store.user_by_id(uid)
    assert user is not None
    user.llm_provider = "anthropic"   # not in OAUTH_PROVIDERS
    user.llm_api_key = None
    store.save_user(user)
    result = asyncio.run(tg._agent_pool_turn(uid, "hola"))
    assert "API key del LLM" in result


def test_build_gateway_from_env_returns_none_without_token(monkeypatch):
    monkeypatch.delenv("AGORA_TELEGRAM_TOKEN", raising=False)
    from app.telegram_gateway import build_gateway_from_env
    assert build_gateway_from_env() is None


def test_build_gateway_from_env_returns_instance_with_token(monkeypatch):
    monkeypatch.setenv("AGORA_TELEGRAM_TOKEN", "fake:token")
    from app.telegram_gateway import build_gateway_from_env
    gw = build_gateway_from_env()
    assert gw is not None
    assert isinstance(gw, TelegramGateway)


def test_lifespan_without_token_does_not_attach_gateway(monkeypatch):
    """FastAPI app lifespan should skip the bot when AGORA_TELEGRAM_TOKEN is empty."""
    monkeypatch.delenv("AGORA_TELEGRAM_TOKEN", raising=False)
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        r = c.get("/api/health")
        assert r.status_code == 200
        assert getattr(app.state, "telegram_gateway", "missing") is None


# ---------------------------------------------------------------------------
# Long-poll lifecycle (smoke)
# ---------------------------------------------------------------------------
# NOTE: the polling-loop lifecycle (start/stop) is intentionally not unit-
# tested. The mechanical `while not stop: get_updates(); for u in
# updates: handle(u)` loop is a thin wrapper and hard to test deterministically
# without a real asyncio fixture. Every handler the loop dispatches into is
# covered exhaustively above via _drive_once.
