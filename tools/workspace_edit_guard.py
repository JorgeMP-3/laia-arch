"""Workspace editability guard shared by generic file and terminal tools.

The workspace-context plugin enforces read-only workspaces for its own DB-first
write tools. This module adds the same signal to generic tools so the model
does not bypass the policy with terminal/Python/sqlite or raw file edits.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


MUTATING_COMMAND_RE = re.compile(
    r"("
    r"\b(rm|mv|cp|touch|mkdir|chmod|chown)\b|"
    r"\bsed\s+-i\b|\bperl\s+-pi\b|"
    r">\s*[^&]|\btee\b|"
    r"\b(INSERT|UPDATE|DELETE|REPLACE|CREATE|DROP|ALTER|TRUNCATE|VACUUM)\b|"
    r"\b(commit|executemany|executescript)\s*\(|"
    r"\b(write_text|write_bytes|open)\s*\(|"
    r"\b(add|upsert|migrate|sync|repair|delete|remove|write|patch|edit)\b"
    r")",
    re.IGNORECASE,
)


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))


def _read_workspace_config() -> dict[str, Any]:
    config_path = _hermes_home() / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml

        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return cfg.get("plugins", {}).get("workspace-context", {}) or {}


def _as_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def workspace_policy() -> dict[str, Any]:
    plugin = _read_workspace_config()
    primary = str(plugin.get("workspace") or "doyouwin")
    readable = _as_list(plugin.get("workspaces"))
    if primary and primary not in readable:
        readable.insert(0, primary)
    active = _as_list(plugin.get("active_workspaces")) or [primary]
    return {
        "workspace": primary,
        "workspaces": readable,
        "active_workspaces": active,
        "readonly_workspaces": [name for name in readable if name not in active],
    }


def _referenced_workspaces(text: str, names: list[str]) -> list[str]:
    refs: list[str] = []
    for name in names:
        if not name:
            continue
        if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(name)}(?![A-Za-z0-9_-])", text):
            refs.append(name)
    return refs


def _error(workspace: str, action: str, policy: dict[str, Any]) -> str:
    return json.dumps(
        {
            "error": f"El workspace '{workspace}' es de solo lectura; {action} bloqueada.",
            "active_workspaces": policy["active_workspaces"],
            "readonly_workspaces": policy["readonly_workspaces"],
            "hint": (
                "Activa el workspace en Context Engine -> Configuracion o usa "
                "workspace_list_workspaces antes de intentar editar."
            ),
        },
        ensure_ascii=False,
    )


def block_file_edit_if_readonly(text: str, *, action: str) -> str | None:
    policy = workspace_policy()
    refs = _referenced_workspaces(text, policy["readonly_workspaces"])
    if refs:
        return _error(refs[0], action, policy)
    return None


def block_terminal_if_readonly(command: str, *, workdir: str | None = None) -> str | None:
    policy = workspace_policy()
    haystack = f"{command}\n{workdir or ''}"
    refs = _referenced_workspaces(haystack, policy["readonly_workspaces"])
    if refs and MUTATING_COMMAND_RE.search(command):
        return _error(refs[0], "edicion por terminal", policy)
    return None

