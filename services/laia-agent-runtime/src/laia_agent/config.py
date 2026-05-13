from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentConfig:
    employee: str
    container: str
    root: Path
    agent_dir: Path
    data_dir: Path
    logs_dir: Path
    profile_dir: Path
    workspace_dir: Path
    workspace_db: Path
    heartbeat_interval: int


def load_config(path: Path = Path("/opt/laia/agent.json")) -> AgentConfig:
    data: dict[str, Any] = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    root = Path(data.get("root", "/opt/laia"))
    workspace = Path(data.get("workspace", root / "workspaces" / "personal" / "workspace.db"))
    return AgentConfig(
        employee=str(data.get("employee", "unknown")),
        container=str(data.get("container", "unknown")),
        root=root,
        agent_dir=Path(data.get("agent_dir", root / "agent")),
        data_dir=Path(data.get("data_dir", root / "data")),
        logs_dir=Path(data.get("logs_dir", root / "logs")),
        profile_dir=Path(data.get("profile_dir", root / "data" / "profile")),
        workspace_dir=workspace.parent,
        workspace_db=workspace,
        heartbeat_interval=int(data.get("heartbeat_interval", 5)),
    )
