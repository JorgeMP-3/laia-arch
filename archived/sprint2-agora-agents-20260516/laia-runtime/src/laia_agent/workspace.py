from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .config import AgentConfig


def _load_workspace_store():
    vendor = Path("/opt/laia/agent/vendor")
    if vendor.exists() and str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))
    from workspace_store import WorkspaceStore

    return WorkspaceStore


def store(config: AgentConfig):
    workspace_store = _load_workspace_store()
    return workspace_store(config.workspace_dir)


def init_workspace(config: AgentConfig) -> dict[str, Any]:
    ws = store(config)
    ws.ensure_schema()
    if not ws.get_index_node():
        ws.upsert_node(
            slug="index",
            title=f"Workspace personal de {config.employee}",
            kind="index",
            summary=f"Workspace personal aislado para el agente {config.employee}.",
            body=f"# Workspace personal de {config.employee}\n\nEste workspace vive dentro de {config.container}.",
            source_kind="manual",
        )
    return workspace_status(config)


def workspace_status(config: AgentConfig) -> dict[str, Any]:
    ws = store(config)
    exists = ws.exists()
    nodes = ws.list_all_nodes() if exists else []
    return {
        "path": str(config.workspace_db),
        "exists": exists,
        "node_count": len(nodes),
        "index": ws.get_index_node() if exists else None,
    }


def upsert_node(config: AgentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    ws = store(config)
    ws.ensure_schema()
    return ws.upsert_node(
        slug=str(payload["slug"]),
        title=str(payload["title"]),
        kind=str(payload.get("kind", "agent-note")),
        summary=str(payload.get("summary", "")),
        body=str(payload.get("body", "")),
        source_kind=str(payload.get("source_kind", "tool")),
        parent_ref=payload.get("parent_ref"),
    )


def get_node(config: AgentConfig, ref: str | int) -> dict[str, Any] | None:
    return store(config).get_node(ref)


def list_nodes(config: AgentConfig, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    return store(config).list_all_nodes()[:limit]


def search_nodes(config: AgentConfig, query: str, limit: int = 8) -> list[dict[str, Any]]:
    return store(config).search_nodes(query, limit=limit)
