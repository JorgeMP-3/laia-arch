"""Private workspace handlers — the executor's per-user nodal memory.

Each user's container holds its own SQLite-backed workspace at
``${LAIA_EXECUTOR_WORKSPACE_ROOT}/workspaces/${name}/workspace.db`` (default
name: ``private``). This file lives on a host bind mount, so it survives
container rebuilds.

These handlers are exposed only via the ``private_workspace_*`` tool names.
They are namespaced explicitly so the LLM picks them when reasoning about
personal memory and leaves the un-namespaced ``workspace_*`` tools (which
live in laia-agora as the collective workspace) for shared knowledge.

The handlers wrap a small subset of :mod:`workspace_store` — the same
library used by the ``workspace-context`` memory provider. We import lazily
so environments without the library (e.g. unit tests without LAIA on the
PYTHONPATH) can still load the executor.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger(__name__)


_DEFAULT_PRIVATE_WORKSPACE_NAME = "private"
_PRIVATE_WORKSPACE_DESCRIPTION = (
    "Workspace personal del usuario dentro de su container AGORA. "
    "Persistencia local en SQLite."
)


# ---------------------------------------------------------------------------
# workspace_store loader  (lazy, with multiple fallback paths)
# ---------------------------------------------------------------------------

_workspace_store_module: Any = None
_store_cache: dict[Path, Any] = {}
_store_lock = threading.RLock()


def _candidate_workspace_store_paths() -> list[Path]:
    """Likely on-disk locations of the ``workspace_store`` package.

    Production install (inside the LXD container) places it at
    ``/opt/laia/lib/``; development pulls it from the LAIA repo root. We
    also honour ``LAIA_WORKSPACE_STORE_PATH`` for explicit overrides.
    """
    paths: list[Path] = []
    env_override = os.environ.get("LAIA_WORKSPACE_STORE_PATH")
    if env_override:
        paths.append(Path(env_override))
    paths.append(Path("/opt/laia/lib"))
    paths.append(Path.home() / "LAIA")
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "workspace_store").is_dir():
            paths.append(parent)
            break
    return paths


def _load_workspace_store() -> Any:
    """Import ``workspace_store`` lazily; cache the module."""
    global _workspace_store_module
    if _workspace_store_module is not None:
        return _workspace_store_module
    try:
        import workspace_store  # type: ignore[import-not-found]
        _workspace_store_module = workspace_store
        return _workspace_store_module
    except ImportError:
        pass
    for root in _candidate_workspace_store_paths():
        candidate = root / "workspace_store"
        if candidate.is_dir() and str(root) not in sys.path:
            sys.path.insert(0, str(root))
            try:
                import workspace_store  # type: ignore[import-not-found]
                _workspace_store_module = workspace_store
                return _workspace_store_module
            except ImportError:
                continue
    raise RuntimeError(
        "workspace_store package not importable. Set LAIA_WORKSPACE_STORE_PATH "
        "or install workspace_store on PYTHONPATH."
    )


# ---------------------------------------------------------------------------
# Configuration  (reads from process env so tests can override per-fixture)
# ---------------------------------------------------------------------------


def _workspace_root_dir() -> Path:
    """Base directory for the private workspace tree (parent of ``workspaces/``)."""
    return Path(os.environ.get("LAIA_EXECUTOR_WORKSPACE_ROOT", "/var/lib/laia/workspace"))


def _workspace_name() -> str:
    return os.environ.get("LAIA_EXECUTOR_PRIVATE_WORKSPACE_NAME", _DEFAULT_PRIVATE_WORKSPACE_NAME)


def _workspace_dir() -> Path:
    return _workspace_root_dir() / "workspaces" / _workspace_name()


def _get_store() -> Any:
    """Return a cached ``WorkspaceStore`` for the private workspace.

    First call creates the directory + schema and (if empty) seeds the index
    node so the workspace is immediately usable.
    """
    root = _workspace_dir()
    with _store_lock:
        existing = _store_cache.get(root)
        if existing is not None:
            return existing
        ws = _load_workspace_store()
        root.mkdir(parents=True, exist_ok=True)
        store = ws.WorkspaceStore(root)
        if not store.exists():
            store.ensure_workspace_layout()
            try:
                store.seed_workspace(
                    description=_PRIVATE_WORKSPACE_DESCRIPTION,
                    areas=[],
                )
            except Exception as exc:
                logger.warning("private_workspace: seed_workspace failed (%s); falling back to schema only", exc)
                store.ensure_schema()
                store.ensure_workspace_taxonomy()
        else:
            store.ensure_schema()
            store.ensure_workspace_taxonomy()
        _store_cache[root] = store
        return store


def _reset_cache_for_tests() -> None:
    """Drop cached stores so tests with temp dirs start clean."""
    with _store_lock:
        _store_cache.clear()


# ---------------------------------------------------------------------------
# Handlers — each returns a JSON string
# ---------------------------------------------------------------------------


def _ok(payload: dict[str, Any]) -> str:
    payload.setdefault("workspace", _workspace_name())
    return json.dumps(payload, ensure_ascii=False, default=str)


def _err(message: str, **extra: Any) -> str:
    payload = {"ok": False, "error": message, "workspace": _workspace_name()}
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False, default=str)


def _retry_on_db_locked(fn, *args, max_attempts: int = 3, base_delay: float = 0.05, **kwargs):
    """Run ``fn(*args, **kwargs)`` with exponential backoff on SQLite locks.

    Workspaces use a single-file SQLite DB. Concurrent writes from two tool
    calls on the same private workspace can race and one of them gets
    "database is locked". Retrying with a short backoff is the standard
    mitigation — SQLite write locks rarely last more than a few ms.
    """
    import sqlite3
    import time as _time
    last_exc: Exception | None = None
    delay = base_delay
    for attempt in range(max_attempts):
        try:
            return fn(*args, **kwargs)
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == max_attempts - 1:
                raise
            last_exc = exc
            _time.sleep(delay)
            delay *= 2
    if last_exc is not None:  # pragma: no cover — unreachable but keeps mypy happy
        raise last_exc


def private_workspace_search(
    query: str = "",
    limit: int = 8,
    kind: Optional[str] = None,
    include_index: bool = False,
    **_ignored: Any,
) -> str:
    """Search the private workspace by free-text query (FTS5 + fallback)."""
    if not query:
        return _err("query es obligatorio")
    try:
        store = _get_store()
        results = store.search_nodes(
            query,
            limit=int(limit),
            kinds=[kind] if kind else None,
            include_index=bool(include_index),
        )
    except Exception as exc:
        return _err(f"search failed: {exc}")
    return _ok({"ok": True, "results": results, "count": len(results)})


def private_workspace_read_node(ref: str = "", **_ignored: Any) -> str:
    """Read a node by slug, filename, alias or numeric id."""
    if not ref:
        return _err("ref es obligatorio")
    try:
        store = _get_store()
        node = store.get_node(ref)
        if node is None:
            return _err(f"nodo '{ref}' no encontrado")
        rendered = store.render_node_markdown(node).strip()
    except Exception as exc:
        return _err(f"read failed: {exc}")
    return _ok({"ok": True, "node": node, "rendered_markdown": rendered})


def private_workspace_add_node(
    slug: str = "",
    title: str = "",
    kind: str = "doc",
    summary: str = "",
    body: str = "",
    status: str = "active",
    parent: Optional[str] = None,
    aliases: Optional[list[str]] = None,
    filename: Optional[str] = None,
    **_ignored: Any,
) -> str:
    """Create or update a node in the private workspace."""
    if not slug or not title:
        return _err("slug y title son obligatorios")
    try:
        store = _get_store()
        node = _retry_on_db_locked(
            store.upsert_node,
            slug=slug,
            title=title,
            kind=kind,
            summary=summary,
            body=body,
            status=status,
            parent_ref=parent,
            aliases=aliases or [],
            filename=filename,
            source_kind="tool",
        )
    except Exception as exc:
        return _err(f"add_node failed: {exc}")
    return _ok({"ok": True, "node": node})


def private_workspace_find_related(
    ref: str = "",
    limit: int = 10,
    **_ignored: Any,
) -> str:
    """Return the neighbours of a node — the nodes connected by any edge.

    The store does not expose a direct neighbours-by-ref query, so we
    resolve the node, walk ``list_edges()`` and pick those touching it.
    """
    if not ref:
        return _err("ref es obligatorio")
    try:
        store = _get_store()
        node = store.get_node(ref)
        if node is None:
            return _err(f"nodo '{ref}' no encontrado")
        node_id = node.get("id")
        edges = [
            edge for edge in store.list_edges()
            if edge.get("from_node_id") == node_id or edge.get("to_node_id") == node_id
        ]
        neighbours: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        for edge in edges[: int(limit) * 2]:
            neighbour_id = edge["to_node_id"] if edge["from_node_id"] == node_id else edge["from_node_id"]
            if neighbour_id in seen_ids:
                continue
            seen_ids.add(neighbour_id)
            related = store.get_node(neighbour_id)
            if related is None:
                continue
            neighbours.append({
                "edge_type": edge.get("edge_type"),
                "weight": edge.get("weight"),
                "node": related,
            })
            if len(neighbours) >= int(limit):
                break
    except Exception as exc:
        return _err(f"find_related failed: {exc}")
    return _ok({"ok": True, "ref": ref, "neighbours": neighbours, "count": len(neighbours)})


__all__ = [
    "private_workspace_search",
    "private_workspace_read_node",
    "private_workspace_add_node",
    "private_workspace_find_related",
    "_reset_cache_for_tests",
]
