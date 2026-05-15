"""Tests for pathd.state — persistence + change recording."""
from __future__ import annotations

from pathd.state import (
    PathEntry,
    State,
    StateStore,
    record_change,
)


class TestRoundtrip:
    def test_empty(self, tmp_path):
        store = StateStore(tmp_path / "cache.json")
        s = State()
        s.paths["agora"] = PathEntry(alias="agora", current_path="/x")
        store.save(s)
        loaded = store.load()
        assert "agora" in loaded.paths
        assert loaded.paths["agora"].current_path == "/x"

    def test_missing_file_returns_empty(self, tmp_path):
        store = StateStore(tmp_path / "cache.json")
        s = store.load()
        assert s.paths == {}

    def test_corrupted_file_recovers(self, tmp_path):
        p = tmp_path / "cache.json"
        p.write_text("{not valid json")
        store = StateStore(p)
        s = store.load()
        assert s.paths == {}


class TestRecordChange:
    def test_records_transition(self):
        e = PathEntry(alias="x", current_path="/old")
        record_change(e, "/new", reason="test")
        assert e.current_path == "/new"
        assert len(e.history) == 1
        assert e.history[0]["from"] == "/old"
        assert e.history[0]["to"] == "/new"
        assert e.history[0]["reason"] == "test"

    def test_noop_when_same_path(self):
        e = PathEntry(alias="x", current_path="/p")
        record_change(e, "/p")
        assert e.history == []

    def test_history_truncates(self):
        e = PathEntry(alias="x", current_path="/start")
        for i in range(30):
            record_change(e, f"/p{i}")
        assert len(e.history) == 20
        # most recent kept
        assert e.history[-1]["to"] == "/p29"
