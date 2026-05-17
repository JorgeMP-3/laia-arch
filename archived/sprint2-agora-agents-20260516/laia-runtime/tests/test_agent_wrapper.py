"""Tests for laia_agent.agent_wrapper — AsyncIterator over AIAgent callbacks.

Uses a fake AIAgent class injected via the ``agent_class`` constructor arg
so we don't need .laia-core installed in the test environment.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from laia_agent.agent_wrapper import AgentWrapper


class FakeAIAgent:
    """Drop-in for AIAgent. Fires the three callbacks on run_conversation."""

    def __init__(self, *, api_key, enabled_toolsets,
                 stream_delta_callback, tool_start_callback, tool_complete_callback):
        self.api_key = api_key
        self.enabled_toolsets = list(enabled_toolsets)
        self.tok = stream_delta_callback
        self.ts = tool_start_callback
        self.te = tool_complete_callback
        self.calls: list[str] = []

    def run_conversation(self, message: str) -> dict:
        self.calls.append(message)
        for chunk in ("Hola", " ", "mundo", "."):
            self.tok(chunk)
        self.ts("tool-1", "web_search", {"q": "foo"})
        self.te("tool-1", "web_search", {"q": "foo"}, {"results": ["a", "b"]})
        self.tok(" Final.")
        return {"final_response": "Hola mundo. Final."}


class FakeAIAgentRaising(FakeAIAgent):
    def run_conversation(self, message):
        raise RuntimeError("LLM provider down")


def _wrapper(agent_class=FakeAIAgent) -> AgentWrapper:
    return AgentWrapper(
        slug="nombrix",
        api_key="fake-key",
        enabled_toolsets=["agora-agent"],
        agent_class=agent_class,
    )


def _drain(wrapper, message) -> list[dict]:
    async def _go():
        events = []
        async for ev in wrapper.chat_stream(message):
            events.append(ev)
        return events

    return asyncio.run(_go())


# ── basic event flow ─────────────────────────────────────────────────────────


def test_chat_stream_yields_tokens():
    wrapper = _wrapper()
    events = _drain(wrapper, "hola")
    tokens = [e["text"] for e in events if e["type"] == "token"]
    assert "".join(tokens) == "Hola mundo. Final."


def test_chat_stream_yields_tool_events():
    wrapper = _wrapper()
    events = _drain(wrapper, "?")
    starts = [e for e in events if e["type"] == "tool_start"]
    ends = [e for e in events if e["type"] == "tool_end"]
    assert len(starts) == 1
    assert len(ends) == 1
    assert starts[0]["tool_name"] == "web_search"
    assert ends[0]["result"] == {"results": ["a", "b"]}


def test_chat_stream_yields_final_last():
    wrapper = _wrapper()
    events = _drain(wrapper, "test")
    assert events[-1]["type"] == "final"
    assert events[-1]["reply"] == "Hola mundo. Final."


def test_chat_stream_passes_message_to_agent():
    wrapper = _wrapper()
    _drain(wrapper, "first")
    _drain(wrapper, "second")
    assert wrapper._agent.calls == ["first", "second"]


def test_chat_stream_uses_agora_agent_toolset_by_default():
    wrapper = _wrapper()
    assert wrapper._agent.enabled_toolsets == ["agora-agent"]


# ── error path ───────────────────────────────────────────────────────────────


def test_chat_stream_emits_error_when_agent_raises():
    wrapper = _wrapper(FakeAIAgentRaising)
    events = _drain(wrapper, "go")
    assert any(e["type"] == "error" and "LLM provider down" in e["message"] for e in events)


# ── reply extraction shapes ──────────────────────────────────────────────────


@pytest.mark.parametrize("result, expected", [
    ({"final_response": "abc"}, "abc"),
    ({"response": "xyz"}, "xyz"),
    ({"reply": "yo"}, "yo"),
    ("raw string", "raw string"),
    ({"messages": [{"role": "user", "content": "q"},
                   {"role": "assistant", "content": "a"}]}, "a"),
    ({}, ""),
])
def test_extract_reply_handles_shapes(result, expected):
    assert AgentWrapper._extract_reply(result) == expected
