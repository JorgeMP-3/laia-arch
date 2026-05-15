"""Tests for `laia-path history`: state-cache read and human/JSON formatting."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from pathd.cli import _format_history
from pathd.state import PathEntry, State, StateStore, record_change


@pytest.fixture
def store_with_history(tmp_path: Path) -> tuple[StateStore, State, str]:
    """A state store with one alias that has 3 recorded transitions."""
    p = tmp_path / "state.json"
    store = StateStore(p)
    entry = PathEntry(alias="agora", current_path="/orig")
    state = State(paths={"agora": entry})
    for i in range(3):
        record_change(entry, f"/v{i}", reason=f"step-{i}")
    store.save(state)
    return store, state, "agora"


def test_history_persisted_and_reloaded(store_with_history):
    store, _, alias = store_with_history
    reloaded = store.load()
    assert alias in reloaded.paths
    hist = reloaded.paths[alias].history
    assert len(hist) == 3
    assert hist[-1]["to"] == "/v2"
    assert hist[-1]["reason"] == "step-2"


def test_format_history_human():
    transitions = [
        {"ts": time.time(), "from": "/a", "to": "/b", "reason": "moved"},
    ]
    text = _format_history(transitions, as_json=False, alias="foo")
    assert "/a" in text and "/b" in text and "moved" in text


def test_format_history_json():
    transitions = [{"ts": 0, "from": "/a", "to": "/b", "reason": "x"}]
    text = _format_history(transitions, as_json=True, alias="foo")
    parsed = json.loads(text)
    assert parsed == transitions


def test_format_empty_history_human():
    text = _format_history([], as_json=False, alias="foo")
    assert "no transitions recorded" in text
    assert "foo" in text


def test_format_empty_history_json():
    text = _format_history([], as_json=True, alias="foo")
    assert json.loads(text) == []


def test_record_change_caps_history():
    entry = PathEntry(alias="x", current_path="/start")
    for i in range(25):
        record_change(entry, f"/p{i}", reason=f"r{i}", keep_history=20)
    assert len(entry.history) == 20
    # Oldest entries dropped first
    assert entry.history[0]["to"] == "/p5"
    assert entry.history[-1]["to"] == "/p24"


def test_record_change_noop_if_path_unchanged():
    entry = PathEntry(alias="x", current_path="/same")
    record_change(entry, "/same", reason="redundant")
    assert entry.history == []
