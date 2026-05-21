"""Tests for the auto-import framework + decay learnings (Fase B)."""

from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def make_user():
    from app.storage import store

    def _make(prefix: str = "imp") -> str:
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
        "/home/laia-hermes/LAIA/.laia-core/plugins/agent-scheduler/__init__.py"
    )
    spec = importlib.util.spec_from_file_location("_imp_test", init_py)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_imp_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def _parse(out: str) -> dict:
    return json.loads(out)


# ── Echo provider ──────────────────────────────────────────────────────────


def test_echo_provider_returns_count():
    from app.auto_import.echo_provider import EchoProvider

    class _FakeWS:
        upserts: list = []
        def upsert_node(self, **kw):
            self.upserts.append(kw)

    ws = _FakeWS()
    result = EchoProvider().sync(user_id="u1", config={"count": 5}, target_ws=ws)
    assert result["count"] == 5
    assert len(ws.upserts) == 5
    assert ws.upserts[0]["slug"].startswith("echo-")


def test_echo_provider_clamps_count():
    from app.auto_import.echo_provider import EchoProvider

    class _NoopWS:
        def upsert_node(self, **kw):
            return None

    # n=999 should clamp to 10.
    result = EchoProvider().sync(user_id="u1", config={"count": 999}, target_ws=_NoopWS())
    assert result["count"] == 10


def test_provider_registry_lists_echo():
    from app.auto_import import list_providers, get_provider
    names = list_providers()
    assert "echo" in names
    assert get_provider("echo") is not None
    assert get_provider("nonexistent") is None


# ── Plugin tools ──────────────────────────────────────────────────────────


def test_auto_import_register_runs_first_sync(plugin_mod, make_user):
    uid = make_user("reg")
    plugin_mod.set_session_context(uid)
    res = _parse(plugin_mod._auto_import_register({
        "provider": "echo",
        "config": {"count": 3, "prefix": "regtest"},
    }))
    assert res["ok"] is True
    assert res["import"]["provider"] == "echo"
    assert res["first_sync"]["count"] == 3
    assert res["import"]["last_status"] == "ok"
    assert res["import"]["last_count"] == 3


def test_auto_import_register_unknown_provider_rejected(plugin_mod, make_user):
    uid = make_user("unk")
    plugin_mod.set_session_context(uid)
    res = _parse(plugin_mod._auto_import_register({"provider": "ghost"}))
    assert res["ok"] is False
    assert "unknown provider" in res["error"]


def test_auto_import_trigger_forces_sync(plugin_mod, make_user):
    uid = make_user("trg")
    plugin_mod.set_session_context(uid)
    created = _parse(plugin_mod._auto_import_register({
        "provider": "echo", "config": {"count": 2},
    }))
    iid = created["import"]["id"]
    # Trigger explicitly — should still be ok.
    res = _parse(plugin_mod._auto_import_trigger({"id": iid}))
    assert res["ok"] is True
    assert res["import"]["last_status"] == "ok"


def test_auto_import_cross_user_isolation(plugin_mod, make_user):
    a = make_user("alice")
    b = make_user("bob")
    plugin_mod.set_session_context(a)
    plugin_mod._auto_import_register({"provider": "echo", "config": {"count": 1}})

    plugin_mod.set_session_context(b)
    listed = _parse(plugin_mod._auto_import_list({}))
    assert listed["count"] == 0


def test_auto_import_remove_only_by_owner(plugin_mod, make_user):
    owner = make_user("owner")
    other = make_user("other")
    plugin_mod.set_session_context(owner)
    created = _parse(plugin_mod._auto_import_register({
        "provider": "echo", "config": {"count": 1}}))
    iid = created["import"]["id"]

    plugin_mod.set_session_context(other)
    res = _parse(plugin_mod._auto_import_remove({"id": iid}))
    assert res["ok"] is False

    plugin_mod.set_session_context(owner)
    res = _parse(plugin_mod._auto_import_remove({"id": iid}))
    assert res["ok"] is True


# ── Decay learnings (piggyback on scheduler) ──────────────────────────────


def test_decay_lowers_confidence_of_old_learnings():
    from app.storage import store
    from app.scheduler import _decay_learnings

    # Create user + ancient learning.
    uid = f"user_decay_{uuid.uuid4().hex[:6]}"
    ts = "2026-01-01T00:00:00+00:00"
    store.db.conn.execute(
        "INSERT INTO users (id, username, display_name, role, agent_id, token, "
        "password, active, created_at, updated_at) "
        "VALUES (?, ?, ?, 'employee', NULL, NULL, NULL, 1, ?, ?)",
        (uid, uid, uid, ts, ts),
    )
    L = store.create_learning(
        user_id=uid, kind="insight", title="aged", content_md="old fact",
    )
    # Force updated_at to 60 days ago.
    store.db.conn.execute(
        "UPDATE agent_learnings SET updated_at = datetime('now', '-60 days') "
        "WHERE id = ?", (L.id,),
    )
    store.db.conn.commit()

    _decay_learnings()
    row = store.db.conn.execute(
        "SELECT confidence FROM agent_learnings WHERE id = ?", (L.id,),
    ).fetchone()
    # Either decayed (0.5 * 0.95 = 0.475) or pruned (deleted).
    if row is not None:
        assert row[0] < 0.5


def test_decay_prunes_below_floor():
    from app.storage import store
    from app.scheduler import _decay_learnings

    uid = f"user_prune_{uuid.uuid4().hex[:6]}"
    ts = "2026-01-01T00:00:00+00:00"
    store.db.conn.execute(
        "INSERT INTO users (id, username, display_name, role, agent_id, token, "
        "password, active, created_at, updated_at) "
        "VALUES (?, ?, ?, 'employee', NULL, NULL, NULL, 1, ?, ?)",
        (uid, uid, uid, ts, ts),
    )
    # Insert a learning with confidence already at the floor.
    store.db.conn.execute(
        "INSERT INTO agent_learnings "
        "(id, user_id, kind, title, content_md, confidence, times_referenced, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("lrn_floor", uid, "insight", "weak", "x", 0.04, 0,
         ts, ts),
    )
    store.db.conn.commit()

    _decay_learnings()
    row = store.db.conn.execute(
        "SELECT 1 FROM agent_learnings WHERE id = 'lrn_floor'",
    ).fetchone()
    assert row is None  # pruned
