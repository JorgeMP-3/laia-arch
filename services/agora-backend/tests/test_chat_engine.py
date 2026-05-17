"""Direct tests for app.chat_engine.

These tests exercise the dispatcher in isolation: they assert that the
forwarder is configured with the right session, the AgentPool is consulted
correctly, and SSE events have the expected shape. The AIAgent itself is
replaced with a stub that emits canned tokens/tool events, so the suite
doesn't need the .laia-core engine installed.
"""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace
from typing import Any

import pytest

from app.agent_pool import AgentPool, AgentSession, LLMSessionConfig
from app import chat_engine
from app.models import Agent, User, now_iso


class _StubAIAgent:
    """Mimics the few attributes/methods of AIAgent the engine touches."""

    def __init__(self) -> None:
        self.stream_delta_callback = None
        self.tool_start_callback = None
        self.tool_complete_callback = None
        self.run_calls: list[str] = []

    def run_conversation(self, message: str, **_) -> dict[str, Any]:
        self.run_calls.append(message)
        # Simulate streaming tokens through stream_delta_callback.
        if self.stream_delta_callback:
            self.stream_delta_callback("hola ")
            self.stream_delta_callback("mundo")
        if self.tool_start_callback:
            self.tool_start_callback("call-1", "write_file", {"path": "x"})
        if self.tool_complete_callback:
            self.tool_complete_callback("call-1", "write_file", {"path": "x"}, "OK")
        return {"final_response": "hola mundo", "iterations": 2}


def _build_user(*, with_key: bool = True) -> User:
    return User(
        id="u-1",
        username="jorge",
        display_name="Jorge",
        role="employee",
        active=True,
        created_at=now_iso(),
        updated_at=now_iso(),
        llm_provider="deepseek",
        llm_api_key=("sk-real" if with_key else None),
        llm_base_url=None,
        llm_model="deepseek-chat",
        llm_api_mode=None,
    )


def _build_agent(*, provisioned: bool = True) -> Agent:
    return Agent(
        id="a-1",
        user_id="u-1",
        container_name="laia-jorge",
        status="running",
        workspace_path="/x",
        container_ip=("10.0.0.5" if provisioned else ""),
        api_token=("tk" if provisioned else ""),
        created_at=now_iso(),
        updated_at=now_iso(),
    )


async def _collect(stream) -> list[dict[str, Any]]:
    """Read an SSE stream and parse out the JSON payloads."""
    chunks = []
    async for chunk in stream:
        text = chunk.decode("utf-8")
        for line in text.splitlines():
            if line.startswith("data: "):
                chunks.append(json.loads(line[len("data: "):]))
    return chunks


@pytest.fixture(autouse=True)
def _isolated_pool_with_stub_agent(monkeypatch):
    """Build a fresh AgentPool that returns _StubAIAgent for every session."""
    pool = AgentPool()
    stub = _StubAIAgent()

    def _fake_get_or_create(user_id, session_id, agent_slug, llm_config):
        session = AgentSession(
            user_id=user_id,
            session_id=session_id,
            agent_slug=agent_slug,
            aiagent=stub,
            llm_config=llm_config,
            created_at=time.time(),
            last_active=time.time(),
        )
        return session

    monkeypatch.setattr(pool, "get_or_create", _fake_get_or_create)
    chat_engine.set_pool(pool)
    monkeypatch.setattr(chat_engine, "_forwarder_module", None)  # force re-discovery
    yield stub


def test_emits_tokens_and_done(_isolated_pool_with_stub_agent):
    stub = _isolated_pool_with_stub_agent
    user = _build_user()
    agent = _build_agent()

    events = asyncio.run(_collect(chat_engine.chat_stream(
        user=user, agent=agent, message="hola", session_id=None,
    )))
    types = [e["type"] for e in events]
    assert "token" in types
    assert "tool" in types
    assert "done" in types
    assert any(e.get("value", "").startswith("hola") for e in events if e["type"] == "token")
    done = next(e for e in events if e["type"] == "done")
    assert done["response"] == "hola mundo"
    assert done["iterations"] == 2
    assert stub.run_calls == ["hola"]


def test_error_when_no_llm_key():
    user = _build_user(with_key=False)
    agent = _build_agent()
    events = asyncio.run(_collect(chat_engine.chat_stream(
        user=user, agent=agent, message="hola", session_id=None,
    )))
    assert events and events[0]["type"] == "error"
    assert "LLM" in events[0]["message"]


def test_error_when_agent_not_provisioned():
    user = _build_user()
    agent = _build_agent(provisioned=False)
    events = asyncio.run(_collect(chat_engine.chat_stream(
        user=user, agent=agent, message="hola", session_id=None,
    )))
    assert events and events[0]["type"] == "error"
    assert "provision" in events[0]["message"]


def test_forwarder_configure_session_called_when_plugin_loaded(monkeypatch, _isolated_pool_with_stub_agent):
    """If the plugin is on disk, chat_stream must call configure_session and
    clear_session with the right (slug, container_ip, api_token)."""
    captured: dict[str, Any] = {}

    class _FakeForwarder:
        @staticmethod
        def configure_session(*, agent_slug, container_ip, api_token, **_):
            captured["configure"] = (agent_slug, container_ip, api_token)

        @staticmethod
        def clear_session():
            captured["clear"] = True

    monkeypatch.setattr(chat_engine, "_forwarder_module", _FakeForwarder)
    user = _build_user()
    agent = _build_agent()
    asyncio.run(_collect(chat_engine.chat_stream(
        user=user, agent=agent, message="hola", session_id="sess-x",
    )))
    assert captured["configure"] == ("jorge", "10.0.0.5", "tk")
    assert captured.get("clear") is True


def test_run_conversation_exception_surfaces_as_error_event(monkeypatch, _isolated_pool_with_stub_agent):
    stub = _isolated_pool_with_stub_agent

    def _boom(*a, **kw):
        raise RuntimeError("LLM down")

    stub.run_conversation = _boom
    user = _build_user()
    agent = _build_agent()
    events = asyncio.run(_collect(chat_engine.chat_stream(
        user=user, agent=agent, message="hola", session_id=None,
    )))
    error_events = [e for e in events if e["type"] == "error"]
    assert error_events
    assert "LLM down" in error_events[0]["message"]


def test_session_id_defaults_to_user_scoped():
    """When the client omits session_id we should still get a consistent
    per-user fallback so subsequent turns reuse the cached AIAgent."""
    user = _build_user()
    agent = _build_agent()
    captured_sids: list[str] = []

    pool = AgentPool()
    def _capture(user_id, session_id, agent_slug, llm_config):
        captured_sids.append(session_id)
        return AgentSession(
            user_id=user_id, session_id=session_id, agent_slug=agent_slug,
            aiagent=_StubAIAgent(), llm_config=llm_config,
            created_at=time.time(), last_active=time.time(),
        )
    pool.get_or_create = _capture  # type: ignore[assignment]
    chat_engine.set_pool(pool)

    asyncio.run(_collect(chat_engine.chat_stream(
        user=user, agent=agent, message="m1", session_id=None,
    )))
    asyncio.run(_collect(chat_engine.chat_stream(
        user=user, agent=agent, message="m2", session_id=None,
    )))
    assert captured_sids[0] == captured_sids[1] == f"u-{user.id}"
