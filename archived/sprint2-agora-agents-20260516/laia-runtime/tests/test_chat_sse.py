"""Tests for POST /chat — SSE stream from the AgentWrapper."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from laia_agent.api import create_app
from laia_agent.config import AgentConfig


class FakeWrapper:
    """Yields a fixed sequence of events when chat_stream is called."""

    def __init__(self, slug: str, events: list[dict] | None = None):
        self.slug = slug
        self.events = events or [
            {"type": "token", "text": "Hola "},
            {"type": "tool_start", "tool_id": "t1", "tool_name": "web_search", "args": {}},
            {"type": "tool_end", "tool_id": "t1", "tool_name": "web_search", "result": "ok"},
            {"type": "token", "text": "mundo."},
            {"type": "final", "reply": "Hola mundo."},
        ]

    async def chat_stream(self, message):
        for ev in self.events:
            yield ev


@pytest.fixture
def cfg(tmp_path: Path) -> AgentConfig:
    root = tmp_path / "laia"
    for d in ("agent", "data", "data/profile", "workspaces/personal"):
        (root / d).mkdir(parents=True)
    return AgentConfig(
        employee="nombrix",
        container="laia-nombrix",
        root=root,
        agent_dir=root / "agent",
        data_dir=root / "data",
        logs_dir=root / "logs",
        profile_dir=root / "data/profile",
        workspace_dir=root / "workspaces/personal",
        workspace_db=root / "workspaces/personal/workspace.db",
        heartbeat_interval=5,
        api_token="tk",
        api_port=9090,
    )


def _build_client(cfg, wrapper_events=None) -> TestClient:
    factory = lambda slug: FakeWrapper(slug, events=wrapper_events)
    app = create_app(cfg, agent_wrapper_factory=factory)
    return TestClient(app)


def auth() -> dict[str, str]:
    return {"Authorization": "Bearer tk"}


# ── SSE shape ─────────────────────────────────────────────────────────────────


def test_chat_returns_sse_media_type(cfg):
    client = _build_client(cfg)
    with client.stream("POST", "/chat", json={"message": "hola"}, headers=auth()) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")


def _collect_events(client, message="hola", session_id=None) -> list[dict]:
    body = {"message": message}
    if session_id:
        body["session_id"] = session_id
    events = []
    with client.stream("POST", "/chat", json=body, headers=auth()) as r:
        for raw in r.iter_lines():
            if not raw:
                continue
            if isinstance(raw, bytes):
                raw = raw.decode()
            if raw.startswith("data:"):
                payload = raw[len("data:"):].strip()
                events.append(json.loads(payload))
    return events


def test_chat_emits_session_event_first(cfg):
    client = _build_client(cfg)
    events = _collect_events(client)
    assert events[0].get("session_id") is not None


def test_chat_emits_token_events(cfg):
    client = _build_client(cfg)
    events = _collect_events(client)
    tokens = [e for e in events if e.get("type") == "token"]
    assert len(tokens) >= 1


def test_chat_emits_tool_events(cfg):
    client = _build_client(cfg)
    events = _collect_events(client)
    starts = [e for e in events if e.get("type") == "tool_start"]
    ends = [e for e in events if e.get("type") == "tool_end"]
    assert starts and ends
    assert starts[0]["tool_name"] == "web_search"


def test_chat_emits_final_last(cfg):
    client = _build_client(cfg)
    events = _collect_events(client)
    payload_events = [e for e in events if "type" in e]
    assert payload_events[-1]["type"] == "final"
    assert payload_events[-1]["reply"] == "Hola mundo."


# ── auth ──────────────────────────────────────────────────────────────────────


def test_chat_requires_token(cfg):
    client = _build_client(cfg)
    r = client.post("/chat", json={"message": "hola"})
    assert r.status_code == 401


# ── session reuse ─────────────────────────────────────────────────────────────


def test_chat_reuses_wrapper_for_same_session(cfg):
    """Same session_id → same wrapper instance kept across requests."""
    instances = []

    class TrackingWrapper(FakeWrapper):
        def __init__(self, slug, events=None):
            super().__init__(slug, events)
            instances.append(self)

    factory = lambda slug: TrackingWrapper(slug)
    app = create_app(cfg, agent_wrapper_factory=factory)
    client = TestClient(app)
    sid = "abc123"

    events_1 = _collect_events(client, session_id=sid)
    events_2 = _collect_events(client, session_id=sid)
    assert len(instances) == 1, "second turn must reuse the same wrapper"
    # Session id returned on both turns should be the same
    sid_1 = next(e["session_id"] for e in events_1 if "session_id" in e)
    sid_2 = next(e["session_id"] for e in events_2 if "session_id" in e)
    assert sid_1 == sid_2 == sid


def test_chat_creates_new_wrapper_for_new_session(cfg):
    instances = []

    class TrackingWrapper(FakeWrapper):
        def __init__(self, slug, events=None):
            super().__init__(slug, events)
            instances.append(self)

    factory = lambda slug: TrackingWrapper(slug)
    app = create_app(cfg, agent_wrapper_factory=factory)
    client = TestClient(app)
    _collect_events(client, session_id="a")
    _collect_events(client, session_id="b")
    assert len(instances) == 2
