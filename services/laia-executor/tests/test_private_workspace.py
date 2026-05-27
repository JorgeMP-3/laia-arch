"""Tests for the executor's private_workspace_* tool handlers.

The handlers wrap the ``workspace_store`` library (shipped under
``workspace_store``). Tests skip cleanly if the
library is not importable so the executor remains testable in stripped
environments.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest


# Make sure workspace_store from the surrounding LAIA repo is reachable for
# the executor's lazy loader. The loader also probes several fallback paths,
# but the fixture below sets the explicit env var anyway.
_LAIA_REPO_ROOT = Path(__file__).resolve().parents[3]
_HAS_WORKSPACE_STORE = (_LAIA_REPO_ROOT / "workspace_store").is_dir()

pytestmark = pytest.mark.skipif(
    not _HAS_WORKSPACE_STORE,
    reason="workspace_store package not present in this repo checkout",
)


@pytest.fixture(autouse=True)
def _isolated_workspace(tmp_path, monkeypatch):
    """Point the private workspace at a fresh tmp dir and clear caches."""
    monkeypatch.setenv("LAIA_EXECUTOR_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("LAIA_EXECUTOR_PRIVATE_WORKSPACE_NAME", "private")
    monkeypatch.setenv("LAIA_WORKSPACE_STORE_PATH", str(_LAIA_REPO_ROOT))

    if str(_LAIA_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_LAIA_REPO_ROOT))

    # Reset the module-level caches and re-import so env changes apply.
    import importlib
    from laia_executor.tools import private_workspace as pw

    pw._reset_cache_for_tests()
    importlib.reload(pw)
    yield pw
    pw._reset_cache_for_tests()


def _payload(s: str) -> dict:
    return json.loads(s)


def test_add_then_search_node(_isolated_workspace):
    pw = _isolated_workspace
    add = _payload(pw.private_workspace_add_node(
        slug="my-note",
        title="Mi nota personal",
        kind="doc",
        summary="apunte rápido",
        body="contenido importante sobre mariposas y bicicletas",
    ))
    assert add["ok"] is True
    assert add["node"]["slug"] == "my-note"

    search = _payload(pw.private_workspace_search(query="mariposas", limit=5))
    assert search["ok"] is True
    slugs = [n["slug"] for n in search["results"]]
    assert "my-note" in slugs


def test_read_node_by_slug(_isolated_workspace):
    pw = _isolated_workspace
    pw.private_workspace_add_node(
        slug="agenda",
        title="Agenda",
        kind="doc",
        body="día 1: comprar pan",
    )
    res = _payload(pw.private_workspace_read_node(ref="agenda"))
    assert res["ok"] is True
    assert res["node"]["slug"] == "agenda"
    assert "comprar pan" in res["rendered_markdown"]


def test_read_unknown_node_returns_error(_isolated_workspace):
    pw = _isolated_workspace
    res = _payload(pw.private_workspace_read_node(ref="does-not-exist"))
    assert res["ok"] is False
    assert "no encontrado" in res["error"]


def test_search_requires_query(_isolated_workspace):
    pw = _isolated_workspace
    res = _payload(pw.private_workspace_search(query=""))
    assert res["ok"] is False
    assert "query" in res["error"]


def test_add_requires_slug_and_title(_isolated_workspace):
    pw = _isolated_workspace
    res = _payload(pw.private_workspace_add_node(slug="", title=""))
    assert res["ok"] is False


def test_find_related_walks_edges(_isolated_workspace):
    pw = _isolated_workspace
    pw.private_workspace_add_node(slug="alpha", title="Alpha", kind="doc", body="root")
    pw.private_workspace_add_node(slug="beta", title="Beta", kind="doc", body="child")

    # Link them via the underlying store (no public tool yet for linking).
    from laia_executor.tools.private_workspace import _get_store
    store = _get_store()
    store.link_nodes("alpha", "beta", "related_to", weight=1.0)

    res = _payload(pw.private_workspace_find_related(ref="alpha"))
    assert res["ok"] is True
    slugs = [n["node"]["slug"] for n in res["neighbours"]]
    assert "beta" in slugs


def test_workspace_dir_isolated(tmp_path, _isolated_workspace):
    pw = _isolated_workspace
    pw.private_workspace_add_node(slug="only-here", title="Only Here", kind="doc")
    db_path = tmp_path / "workspaces" / "private" / "workspace.db"
    assert db_path.exists(), "expected DB inside isolated workspace_root"


def test_registered_in_default_registry():
    """The executor's default registry exposes the private_workspace_* tools."""
    from laia_executor.tools.registry import default_registry
    names = default_registry.list_tools()
    for expected in (
        "private_workspace_search",
        "private_workspace_read_node",
        "private_workspace_add_node",
        "private_workspace_find_related",
    ):
        assert expected in names, f"missing tool {expected!r}; got {names!r}"
