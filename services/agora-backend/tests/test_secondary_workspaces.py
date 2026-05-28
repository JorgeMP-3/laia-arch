"""Tests for read-only secondary workspaces (Fase 4)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


# WorkspaceStore lives at LAIA repo root; the test conftest already injects
# AGORA_DATA_DIR, but the ``workspace_store`` package import is best-effort.

@pytest.fixture(scope="module")
def WorkspaceStore():
    sys.path.insert(0, "/home/laia-arch/LAIA")
    from workspace_store import WorkspaceStore as WS  # type: ignore
    return WS


@pytest.fixture
def writable_workspace(tmp_path, WorkspaceStore):
    """Build a tiny workspace.db on disk with 2 nodes so the read-only
    tests have something to read."""
    root = tmp_path / "fixture-ws"
    root.mkdir()
    ws = WorkspaceStore(root)
    ws.ensure_schema()
    ws.upsert_node(slug="index", title="Index", kind="index",
                   summary="entrada", body="")
    ws.upsert_node(slug="hello", title="Hello node", kind="doc",
                   summary="testing", body="contenido de prueba")
    return root


def test_read_only_blocks_upsert(WorkspaceStore, writable_workspace):
    ro = WorkspaceStore(writable_workspace, read_only=True)
    with pytest.raises(PermissionError):
        ro.upsert_node(slug="x", title="X", kind="doc")


def test_read_only_blocks_link_nodes(WorkspaceStore, writable_workspace):
    ro = WorkspaceStore(writable_workspace, read_only=True)
    with pytest.raises(PermissionError):
        ro.link_nodes("index", "hello", "contains")


def test_read_only_blocks_task_mutations(WorkspaceStore, writable_workspace):
    ro = WorkspaceStore(writable_workspace, read_only=True)
    with pytest.raises(PermissionError):
        ro.claim_task("agent-x", "do something")
    with pytest.raises(PermissionError):
        ro.complete_task(1, "agent-x", "ok")


def test_read_only_pragma_query_only_set(WorkspaceStore, writable_workspace):
    ro = WorkspaceStore(writable_workspace, read_only=True)
    conn = ro.connect()
    val = conn.execute("PRAGMA query_only").fetchone()[0]
    assert val == 1
    conn.close()


def test_read_only_can_read(WorkspaceStore, writable_workspace):
    ro = WorkspaceStore(writable_workspace, read_only=True)
    nodes = ro.list_all_nodes()
    slugs = {n["slug"] for n in nodes}
    assert "index" in slugs
    assert "hello" in slugs
    node = ro.get_node("hello")
    assert node is not None
    assert node["title"] == "Hello node"


def test_plugin_lists_no_workspaces_if_unmounted(monkeypatch):
    """Plugin returns empty list when no secondary workspaces are mounted."""
    init_py = Path(
        "/home/laia-arch/LAIA/.laia-core/plugins/secondary-workspaces/__init__.py"
    )
    spec = importlib.util.spec_from_file_location("_sw_test", init_py)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_sw_test"] = mod
    spec.loader.exec_module(mod)

    from app import storage as _store_mod
    # Ensure the store has no secondaries for this assertion.
    _store_mod.store.secondary_workspaces = {}
    res = json.loads(mod._list_workspaces({}))
    assert res["ok"] is True
    assert res["workspaces"] == []


def test_plugin_search_and_get_against_mounted_workspace(
    monkeypatch, writable_workspace, WorkspaceStore,
):
    """Mount a writable_workspace as secondary read-only, then exercise
    search + get + list_all_nodes + list_edges tools."""
    init_py = Path(
        "/home/laia-arch/LAIA/.laia-core/plugins/secondary-workspaces/__init__.py"
    )
    spec = importlib.util.spec_from_file_location("_sw_test_real", init_py)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_sw_test_real"] = mod
    spec.loader.exec_module(mod)

    from app.storage import store
    ro = WorkspaceStore(writable_workspace, read_only=True)
    monkeypatch.setitem(store.__dict__, "secondary_workspaces", {"doyouwin": ro})

    listed = json.loads(mod._list_workspaces({}))
    assert listed["workspaces"][0]["slug"] == "doyouwin"
    assert listed["workspaces"][0]["read_only"] is True

    got = json.loads(mod._get_node({"workspace": "doyouwin", "slug_or_id": "hello"}))
    assert got["ok"] is True
    assert got["node"]["title"] == "Hello node"

    miss = json.loads(mod._get_node({"workspace": "doyouwin", "slug_or_id": "nope"}))
    assert miss["ok"] is False

    all_nodes = json.loads(mod._list_all_nodes({"workspace": "doyouwin"}))
    assert all_nodes["ok"] is True
    assert all_nodes["count"] >= 2

    search = json.loads(mod._search({"workspace": "doyouwin", "query": "Hello"}))
    assert search["ok"] is True
    assert isinstance(search.get("results"), list)


def test_plugin_rejects_unknown_workspace():
    init_py = Path(
        "/home/laia-arch/LAIA/.laia-core/plugins/secondary-workspaces/__init__.py"
    )
    spec = importlib.util.spec_from_file_location("_sw_unknown", init_py)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_sw_unknown"] = mod
    spec.loader.exec_module(mod)

    from app.storage import store
    store.secondary_workspaces = {}

    res = json.loads(mod._search({"workspace": "ghost", "query": "x"}))
    assert res["ok"] is False
    assert "not mounted" in res["error"]
