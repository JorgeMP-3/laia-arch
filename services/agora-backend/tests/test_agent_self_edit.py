"""Tests for the agent-self-edit plugin (Fase 2)."""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
import uuid
from pathlib import Path

import pytest


# Load the plugin module by file path — the plugin manager isn't running in
# unit-test context, so ``laia_plugins.agent_self_edit`` isn't resolvable
# from sys.modules.

@pytest.fixture(scope="module")
def plugin_mod():
    from tests._laia_core import load_plugin_or_skip

    return load_plugin_or_skip("agent-self-edit/__init__.py", "_agent_self_edit_test")


@pytest.fixture
def fresh_user():
    """Create a real user in agora.db and return its id. The plugin module
    only knows how to talk to ``app.storage.store``, so we use the live
    test store."""
    from app.storage import store

    username = f"selfedit_{uuid.uuid4().hex[:6]}"
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


def _parse(out: str) -> dict:
    return json.loads(out)


def test_no_user_in_context_returns_error(plugin_mod):
    plugin_mod.clear_session_context()
    res = _parse(plugin_mod._agent_set_soul({"soul": "anything"}))
    assert res["ok"] is False
    assert "user" in res["error"].lower()


def test_set_soul_updates_db_and_invalidates_pool(plugin_mod, fresh_user, monkeypatch):
    plugin_mod.set_session_context(fresh_user)
    invalidated: list[str] = []
    from app.agent_pool import AgentPool
    monkeypatch.setattr(
        AgentPool, "invalidate_user_static",
        staticmethod(lambda uid: invalidated.append(uid) or 1),
    )

    res = _parse(plugin_mod._agent_set_soul({"soul": "Soy un agente de prueba."}))
    assert res["ok"] is True
    assert res["area"]["soul_md"] == "Soy un agente de prueba."

    # Verify persistence.
    from app.storage import store
    user = store.user_by_id(fresh_user)
    area = store.agent_area_for_user(user, create=False)
    assert area.soul_md == "Soy un agente de prueba."

    # And the pool was invalidated.
    assert fresh_user in invalidated


def test_append_soul_concatenates(plugin_mod, fresh_user):
    plugin_mod.set_session_context(fresh_user)
    plugin_mod._agent_set_soul({"soul": "Línea 1."})
    res = _parse(plugin_mod._agent_append_soul({"text": "Línea 2."}))
    assert res["ok"] is True
    assert "Línea 1." in res["area"]["soul_md"]
    assert "Línea 2." in res["area"]["soul_md"]


def test_set_soul_rejects_oversized_payload(plugin_mod, fresh_user):
    plugin_mod.set_session_context(fresh_user)
    big = "x" * 60_000
    res = _parse(plugin_mod._agent_set_soul({"soul": big}))
    assert res["ok"] is False
    assert "exceeds" in res["error"]


def test_set_preference_roundtrip_and_remove(plugin_mod, fresh_user):
    plugin_mod.set_session_context(fresh_user)
    res = _parse(plugin_mod._agent_set_preference(
        {"key": "tone", "value": "directo", "scope": "behavior"}
    ))
    assert res["ok"] is True
    assert res["area"]["behavior_preferences"]["tone"] == "directo"

    # Remove.
    res = _parse(plugin_mod._agent_remove_preference(
        {"key": "tone", "scope": "behavior"}
    ))
    assert res["ok"] is True
    assert "tone" not in res["area"]["behavior_preferences"]


def test_set_name_validates_length(plugin_mod, fresh_user):
    plugin_mod.set_session_context(fresh_user)
    res = _parse(plugin_mod._agent_set_name({"name": ""}))
    assert res["ok"] is False
    res = _parse(plugin_mod._agent_set_name({"name": "x" * 100}))
    assert res["ok"] is False
    res = _parse(plugin_mod._agent_set_name({"name": "Nombrix"}))
    assert res["ok"] is True
    assert res["area"]["agent_display_name"] == "Nombrix"


def test_threading_local_isolated_between_users(plugin_mod):
    """Two concurrent threads with different user_ids must not see each other.

    We don't actually mutate the DB — we just verify the threading.local
    binding is per-thread.
    """
    seen: dict[str, str] = {}
    barrier = threading.Barrier(2)

    def worker(uid: str) -> None:
        plugin_mod.set_session_context(uid)
        barrier.wait()  # both threads here at the same time
        seen[uid] = plugin_mod._current_user_id()

    t1 = threading.Thread(target=worker, args=("user_A",))
    t2 = threading.Thread(target=worker, args=("user_B",))
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert seen["user_A"] == "user_A"
    assert seen["user_B"] == "user_B"
