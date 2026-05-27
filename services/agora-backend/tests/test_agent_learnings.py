"""Tests for the agent_learnings table + plugin tools (Fase 3)."""

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
        "/home/laia-arch/LAIA/.laia-core/plugins/agent-self-edit/__init__.py"
    )
    spec = importlib.util.spec_from_file_location("_self_edit_lrn", init_py)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_self_edit_lrn"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def make_user():
    """Factory: create a fresh user and return its id."""
    from app.storage import store

    def _make(prefix: str = "lrn") -> str:
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


def test_create_and_list_learning(plugin_mod, make_user):
    uid = make_user("create")
    plugin_mod.set_session_context(uid)

    res = _parse(plugin_mod._learning_record({
        "kind": "insight",
        "title": "Probar learnings funciona",
        "content": "El agente puede grabar aprendizajes via learning_record.",
        "tags": ["meta", "test"],
    }))
    assert res["ok"] is True
    assert res["learning"]["kind"] == "insight"

    listed = _parse(plugin_mod._learning_list_recent({}))
    assert listed["ok"] is True
    assert listed["count"] >= 1
    assert any(L["title"] == "Probar learnings funciona" for L in listed["results"])


def test_recent_learnings_appear_in_agent_area_prompt(make_user):
    from app.storage import store
    from app.agent_pool import _build_agent_area_prompt

    uid = make_user("inject")
    store.create_learning(
        user_id=uid, kind="pattern",
        title="El usuario prefiere bullets para resúmenes largos",
        content_md="Cuando piden resumen >5 líneas, formatea como lista.",
    )
    prompt = _build_agent_area_prompt(uid) or ""
    assert "Aprendizajes recientes" in prompt
    assert "prefiere bullets" in prompt


def test_learning_max_content_rejected(plugin_mod, make_user):
    uid = make_user("big")
    plugin_mod.set_session_context(uid)
    big = "x" * (9 * 1024)
    res = _parse(plugin_mod._learning_record({
        "kind": "insight", "title": "big one", "content": big,
    }))
    assert res["ok"] is False
    assert "exceeds" in res["error"]


def test_cross_user_isolation(plugin_mod, make_user):
    uid_a = make_user("alice")
    uid_b = make_user("bob")
    plugin_mod.set_session_context(uid_a)
    plugin_mod._learning_record({
        "kind": "insight", "title": "Secreto de Alice",
        "content": "Solo Alice debería ver esto.",
    })

    plugin_mod.set_session_context(uid_b)
    listed = _parse(plugin_mod._learning_list_recent({}))
    assert all("Secreto de Alice" not in L["title"] for L in listed["results"])


def test_forget_only_by_owner(plugin_mod, make_user):
    uid_a = make_user("owner")
    uid_b = make_user("thief")
    plugin_mod.set_session_context(uid_a)
    rec = _parse(plugin_mod._learning_record({
        "kind": "error", "title": "Solo borrable por owner",
        "content": "test",
    }))
    lid = rec["learning"]["id"]

    plugin_mod.set_session_context(uid_b)
    res = _parse(plugin_mod._learning_forget({"learning_id": lid}))
    assert res["ok"] is False

    plugin_mod.set_session_context(uid_a)
    res = _parse(plugin_mod._learning_forget({"learning_id": lid}))
    assert res["ok"] is True


def test_learning_invalid_kind_rejected(plugin_mod, make_user):
    uid = make_user("enum")
    plugin_mod.set_session_context(uid)
    res = _parse(plugin_mod._learning_record({
        "kind": "not-a-kind",
        "title": "x", "content": "y",
    }))
    assert res["ok"] is False


def test_learning_recall_bumps_referenced(plugin_mod, make_user):
    from app.storage import store
    uid = make_user("ref")
    plugin_mod.set_session_context(uid)
    rec = _parse(plugin_mod._learning_record({
        "kind": "insight",
        "title": "Referenciable",
        "content": "match-keyword",
    }))
    lid = rec["learning"]["id"]
    before = store.list_learnings(user_id=uid, query="match-keyword", limit=5)
    assert before[0].times_referenced == 0
    plugin_mod._learning_recall({"query": "match-keyword"})
    after = store.list_learnings(user_id=uid, query="match-keyword", limit=5)
    assert after[0].times_referenced == 1
