#!/usr/bin/env python3
# Readable DB-first agentic orchestration monitor for Hermes.
"""agent-monitor.py — shows active tasks, recent events, and agentic nodes."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


def resolve_workspace(name: str | None) -> str:
    if name:
        return name
    active = get_active_workspace()
    if active:
        return active
    workspaces = [path.name for path in WORKSPACES_DIR.iterdir() if path.is_dir() and not path.name.startswith(".")]
    if not workspaces:
        raise SystemExit("ERROR: no hay workspaces disponibles")
    return workspaces[0]


def parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def short_time(value: str) -> str:
    parsed = parse_time(value)
    if not parsed:
        return value[:19]
    return parsed.astimezone().strftime("%H:%M:%S")


def age(value: str) -> str:
    parsed = parse_time(value)
    if not parsed:
        return "?"
    seconds = max(0, int((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()))
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    return f"{hours}h"


def truncate(value: Any, width: int) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= width:
        return text
    return text[: max(0, width - 1)] + "…"


def terminal_width() -> int:
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 100


def collect_status(workspace: str, *, limit: int) -> dict[str, Any]:
    """Collect the compact state shown in the CLI and exported as JSON.

    This is intentionally close to what the future web dashboard needs:
    active tasks, recent events and important agent coordination nodes.
    """
    path = WORKSPACES_DIR / workspace
    if not path.exists():
        raise SystemExit(f"ERROR: workspace no encontrado: {workspace}")
    store = WorkspaceStore(path)
    status = store.agent_status(max_events=max(limit, 50))
    events = store.list_events()[:limit]
    nodes = store.list_all_nodes()
    agent_notes = [
        {
            "slug": node["slug"],
            "title": node["title"],
            "updated_at": node["updated_at"],
            "summary": node["summary"],
        }
        for node in nodes
        if node["kind"] in {"agent-note", "agent-plan", "agent-log"}
    ]
    return {
        "workspace": workspace,
        "db_path": str(store.db_path),
        "active_tasks": status["active_tasks"],
        "events": events,
        "agent_team": status["agent_team"],
        "agent_log": status["agent_log"],
        "agent_notes": agent_notes,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def event_summary(event: dict[str, Any]) -> tuple[str, str, str]:
    """Convert a raw event payload into one readable monitor row."""
    payload = event.get("payload_obj") or {}
    event_type = event.get("event_type", "")
    agent = payload.get("agent") or payload.get("agent_id") or "—"
    if event_type == "agent_task_start":
        return event_type, agent, payload.get("task", "—")
    if event_type == "agent_task_done":
        return event_type, agent, payload.get("result", "—")
    if event_type == "worker_assigned":
        return event_type, agent, payload.get("summary") or payload.get("task_id", "—")
    if event_type in {"plan_requested", "plan_submitted", "plan_approved"}:
        return event_type, agent, payload.get("summary") or payload.get("task_id", "—")
    if event_type == "orchestration_request_created":
        return event_type, agent, payload.get("summary", "—")
    if event_type == "agent_docs_synced":
        return event_type, "documenter", f"{payload.get('events_considered', '?')} eventos, {payload.get('active_tasks', '?')} activas"
    return event_type, agent, payload.get("summary") or payload.get("task") or payload.get("result") or event.get("node_slug") or "—"


def render_text(data: dict[str, Any], *, limit: int) -> str:
    """Render a terminal-friendly dashboard without requiring a web UI."""
    width = terminal_width()
    line = "─" * min(width, 110)
    active = data["active_tasks"]
    agent_notes = sorted(data["agent_notes"], key=lambda item: item["updated_at"], reverse=True)
    lines = [
        line,
        f"Hermes Agent Monitor | workspace={data['workspace']} | active={len(active)} | {short_time(data['generated_at'])}",
        line,
        "",
        "ACTIVE TASKS",
    ]
    if active:
        for task in active:
            lines.append(
                f"  • #{task['event_id']} {task.get('agent') or '—'} | "
                f"{truncate(task.get('task'), 70)} | age={age(task.get('started_at', ''))}"
            )
    else:
        lines.append("  • Sin tareas activas")

    lines.extend(["", "RECENT EVENTS"])
    for event in data["events"][:limit]:
        kind, agent, summary = event_summary(event)
        lines.append(
            f"  [{short_time(event['created_at'])}] #{event['id']} {kind} | "
            f"{agent} | {truncate(summary, max(30, width - 48))}"
        )

    lines.extend(["", "AGENT NOTES"])
    for node in agent_notes[:8]:
        marker = ""
        if node["slug"] in {"agent-team", "agent-log"}:
            marker = " *"
        lines.append(
            f"  • {node['slug']}{marker} | updated={short_time(node['updated_at'])} | "
            f"{truncate(node.get('summary'), max(30, width - 55))}"
        )

    team = data.get("agent_team")
    log = data.get("agent_log")
    lines.extend(["", "KEY NODES"])
    lines.append(f"  • agent-team: {'OK' if team else 'MISSING'}")
    lines.append(f"  • agent-log:  {'OK' if log else 'MISSING'}")
    return "\n".join(lines)


def clear_screen() -> None:
    print("\033[2J\033[H", end="")


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor de estado agentico Hermes DB-first.")
    parser.add_argument("--workspace", help="Workspace a monitorizar; por defecto usa el activo")
    parser.add_argument("--limit", type=int, default=20, help="Eventos recientes a mostrar")
    parser.add_argument("--watch", action="store_true", help="Refrescar continuamente")
    parser.add_argument("--interval", type=float, default=2.0, help="Segundos entre refrescos en --watch")
    parser.add_argument("--json", action="store_true", help="Salida JSON para integraciones o futura web")
    args = parser.parse_args()

    workspace = resolve_workspace(args.workspace)
    while True:
        data = collect_status(workspace, limit=max(1, args.limit))
        if args.json:
            # Stable machine-readable shape for scripts and the future web UI.
            print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        else:
            if args.watch:
                clear_screen()
            print(render_text(data, limit=max(1, args.limit)))
        if not args.watch:
            break
        time.sleep(max(0.5, args.interval))


if __name__ == "__main__":
    main()
