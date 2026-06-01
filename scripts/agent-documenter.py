#!/usr/bin/env python3
# Synchronizes DB-first agent documentation from Hermes workspaces.
"""agent-documenter.py — maintains agent-team and agent-log from workspace.db."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import os
from _laia_runtime_paths import add_workspace_store_to_path, laia_home, workspaces_dir

LAIA_HOME = laia_home()
add_workspace_store_to_path()

from workspace_store import WorkspaceStore, list_workspaces

WORKSPACES_DIR = workspaces_dir()
CONFIG_PATH = LAIA_HOME / "config.yaml"


def get_active_workspace() -> str:
    if not CONFIG_PATH.exists():
        return ""
    try:
        import yaml

        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("plugins", {}).get("workspace-context", {}).get("workspace", "")
    except Exception:
        return ""


def workspace_names(requested: str | None, all_workspaces: bool) -> list[str]:
    """Decide which workspace DBs should be synchronized this run."""
    if requested:
        return [requested]
    if all_workspaces:
        return [path.name for path in WORKSPACES_DIR.iterdir() if path.is_dir() and not path.name.startswith(".")]
    active = get_active_workspace()
    return [active] if active else []


def sync_workspace(name: str, *, max_events: int, export: bool) -> dict:
    """Run the documenter pass for one workspace.

    The sync is idempotent: if `agent-team` and `agent-log` already match the
    event timeline, WorkspaceStore reports `changed=False` and no new event is
    written.
    """
    ws_path = WORKSPACES_DIR / name
    if not ws_path.exists():
        return {"workspace": name, "error": "workspace no encontrado"}
    store = WorkspaceStore(ws_path)
    result = store.sync_agent_coordination(max_events=max_events)
    if export:
        result["export"] = store.sync_markdown_exports()
    return {"workspace": name, **result}


def print_result(result: dict) -> None:
    if result.get("error"):
        print(f"✗ {result['workspace']}: {result['error']}")
        return
    marker = "actualizado" if result.get("changed") else "sin cambios"
    print(
        f"✓ {result['workspace']}: "
        f"{result['events_considered']} eventos, "
        f"{len(result['active_tasks'])} tareas activas, "
        f"nodos {result['team_node']}/{result['log_node']} ({marker})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mantiene `agent-team` y `agent-log` desde la tabla events de workspace.db."
    )
    parser.add_argument("--workspace", metavar="NOMBRE", help="Sincronizar un workspace concreto")
    parser.add_argument("--all", action="store_true", help="Sincronizar todos los workspaces")
    parser.add_argument("--watch", action="store_true", help="Mantener el documentador corriendo")
    parser.add_argument("--interval", type=float, default=5.0, help="Segundos entre sincronizaciones en --watch")
    parser.add_argument("--max-events", type=int, default=200, help="Eventos recientes considerados por workspace")
    parser.add_argument("--export", action="store_true", help="Regenerar exports Markdown derivados tras sincronizar")
    args = parser.parse_args()

    names = workspace_names(args.workspace, args.all)
    if not names:
        print("ERROR: no hay workspace activo y no se especifico --workspace ni --all")
        sys.exit(1)

    while True:
        # In watch mode this is the lightweight background "documenter agent":
        # it keeps human-readable coordination nodes fresh while raw events
        # remain the source of truth for realtime UIs.
        for name in names:
            print_result(sync_workspace(name, max_events=args.max_events, export=args.export))
        if not args.watch:
            break
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    main()
