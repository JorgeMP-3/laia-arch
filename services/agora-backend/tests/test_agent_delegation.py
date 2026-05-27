"""Tests for the agent-delegation plugin (Fase C)."""

from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def plugin_mod():
    init_py = Path(
        "/home/laia-arch/LAIA/.laia-core/plugins/agent-delegation/__init__.py"
    )
    spec = importlib.util.spec_from_file_location("_delegation_test", init_py)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_delegation_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def make_user():
    from app.storage import store

    def _make(prefix: str = "del") -> str:
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


def _parse(out: str) -> dict:
    return json.loads(out)


# ── Profile config ─────────────────────────────────────────────────────────


def test_profile_config_loaded():
    from app.child_profiles import CHILD_PROFILES, DEFAULT_PROFILE
    assert DEFAULT_PROFILE == "general"
    for name in ("general", "coder", "researcher", "writer"):
        assert name in CHILD_PROFILES
        assert isinstance(CHILD_PROFILES[name]["toolsets"], list)
        # No profile should grant the recursion / self-edit / scheduler toolsets.
        for forbidden in ("agent_delegation", "agent_self", "agent_scheduler"):
            assert forbidden not in CHILD_PROFILES[name]["toolsets"], (
                f"profile {name} must not include {forbidden} (depth=1 invariant)"
            )


# ── Plugin behavior (sync path mocked) ────────────────────────────────────


def test_spawn_child_requires_user_context(plugin_mod):
    plugin_mod.clear_session_context()
    res = _parse(plugin_mod._spawn_child({
        "purpose": "p", "prompt": "q",
    }))
    assert res["ok"] is False


def test_spawn_child_runs_synchronously(plugin_mod, make_user, monkeypatch):
    uid = make_user("spawn")
    plugin_mod.set_session_context(uid, "sess-spawn-1")

    # Patch the internal _run_child_sync so we don't actually build an
    # AIAgent (no LLM, no plugin discovery).
    def _fake_run(*, user_id, prompt, profile, timeout):
        return f"echo:{prompt}", 42

    monkeypatch.setattr(plugin_mod, "_run_child_sync", _fake_run)

    res = _parse(plugin_mod._spawn_child({
        "purpose": "test-spawn",
        "prompt": "say hi",
        "profile": "writer",
    }))
    assert res["ok"] is True
    assert res["status"] == "done"
    assert res["profile"] == "writer"
    assert "echo:say hi" in res["response"]
    assert res["tokens_used"] == 42


def test_spawn_child_failure_marks_failed_status(plugin_mod, make_user, monkeypatch):
    uid = make_user("fail")
    plugin_mod.set_session_context(uid, "sess-spawn-fail")

    def _boom(**_):
        raise RuntimeError("LLM offline")

    monkeypatch.setattr(plugin_mod, "_run_child_sync", _boom)

    res = _parse(plugin_mod._spawn_child({"purpose": "p", "prompt": "q"}))
    assert res["ok"] is False
    assert res["status"] == "failed"
    assert "LLM offline" in (res["error"] or "")

    # Audit row should exist.
    from app.storage import store
    row = store.get_child_run(res["child_id"])
    assert row is not None
    assert row.status == "failed"


def test_spawn_child_timeout_marks_timeout(plugin_mod, make_user, monkeypatch):
    uid = make_user("tout")
    plugin_mod.set_session_context(uid, "sess-spawn-tout")

    def _slow(**_):
        raise TimeoutError("child run exceeded 1s")

    monkeypatch.setattr(plugin_mod, "_run_child_sync", _slow)

    res = _parse(plugin_mod._spawn_child({"purpose": "p", "prompt": "q"}))
    assert res["status"] == "timeout"
    assert "timeout" in (res["error"] or "").lower()


def test_max_concurrent_children_enforced(plugin_mod, make_user, monkeypatch):
    """If we have 3 children in 'running' status, the 4th is rejected."""
    from app.storage import store
    from app.models import AgentChildRun

    uid = make_user("conc")
    sid = "sess-spawn-conc"
    plugin_mod.set_session_context(uid, sid)

    # Insert 3 fake running children for this session.
    for i in range(3):
        store.create_child_run(AgentChildRun(
            parent_user_id=uid, parent_session_id=sid,
            profile="general", purpose=f"p{i}", prompt="x",
            status="running",
        ))

    res = _parse(plugin_mod._spawn_child({"purpose": "extra", "prompt": "y"}))
    assert res["ok"] is False
    assert "too many" in res["error"]


def test_kill_child_only_by_owner(plugin_mod, make_user, monkeypatch):
    from app.storage import store
    from app.models import AgentChildRun

    owner = make_user("ownerk")
    thief = make_user("thiefk")
    run = store.create_child_run(AgentChildRun(
        parent_user_id=owner, parent_session_id="s-kill",
        profile="general", purpose="x", prompt="y", status="running",
    ))

    plugin_mod.set_session_context(thief, "s-kill")
    res = _parse(plugin_mod._kill_child({"child_id": run.id}))
    assert res["ok"] is False

    plugin_mod.set_session_context(owner, "s-kill")
    res = _parse(plugin_mod._kill_child({"child_id": run.id}))
    assert res["ok"] is True


def test_list_active_children_filters_by_session(plugin_mod, make_user):
    from app.storage import store
    from app.models import AgentChildRun

    uid = make_user("lac")
    sid_a = "sess-A"
    sid_b = "sess-B"
    store.create_child_run(AgentChildRun(
        parent_user_id=uid, parent_session_id=sid_a, profile="general",
        purpose="a", prompt="x", status="running",
    ))
    store.create_child_run(AgentChildRun(
        parent_user_id=uid, parent_session_id=sid_b, profile="general",
        purpose="b", prompt="y", status="running",
    ))

    plugin_mod.set_session_context(uid, sid_a)
    res = _parse(plugin_mod._list_active_children({}))
    assert res["count"] >= 1
    # All should belong to sess-A only.
    assert all(c["parent_session_id"] == sid_a for c in res["children"])


def test_audit_event_emitted_on_spawn(plugin_mod, make_user, monkeypatch):
    from app.storage import store
    uid = make_user("aud")
    plugin_mod.set_session_context(uid, "sess-aud")
    monkeypatch.setattr(plugin_mod, "_run_child_sync",
                         lambda **_: ("ok", None))
    plugin_mod._spawn_child({"purpose": "x", "prompt": "y"})

    rows = store.db.conn.execute(
        "SELECT event_type FROM events WHERE actor_id = ? "
        "AND event_type = 'child_spawned'", (uid,),
    ).fetchall()
    assert len(rows) >= 1
