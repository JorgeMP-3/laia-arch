from __future__ import annotations

import os
import secrets
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        self.env = os.environ.get("AGORA_ENV", "dev")
        self.laia_root = Path(os.environ.get("LAIA_ROOT", str(Path.home() / "LAIA")))

        # ── AGORA data dir ────────────────────────────────────────────────────
        self.prod_data_dir = Path(os.environ.get("AGORA_DATA_DIR", "/srv/laia/agora"))
        self.dev_data_dir = Path(
            os.environ.get(
                "AGORA_DEV_DATA_DIR",
                str(self.laia_root / "services" / "agora-backend" / "data"),
            )
        )
        self.data_dir = self.prod_data_dir if self.prod_data_dir.exists() else self.dev_data_dir
        self.db_path = self.data_dir / "agora.db"
        # Collective workspace shared by every AGORA AIAgent. We follow the
        # `workspace-context` plugin layout (LAIA_HOME/workspaces/{name}/) so
        # the same path is discoverable both from agora-backend (direct
        # WorkspaceStore access) and from the AIAgent pool (via the memory
        # provider plugin).
        self.collective_workspace_name = os.environ.get(
            "AGORA_COLLECTIVE_WORKSPACE", "collective"
        )
        self.workspaces_root = self.data_dir / "workspaces"
        self.workspace_root = self.workspaces_root / self.collective_workspace_name
        self.events_path = self.data_dir / "events.jsonl"
        self.tasks_path = self.data_dir / "tasks.json"
        self.users_path = self.data_dir / "users.json"
        self.agents_path = self.data_dir / "agents.json"

        # ── Auth ──────────────────────────────────────────────────────────────
        self.jwt_secret = os.environ.get("AGORA_JWT_SECRET", secrets.token_hex(32))
        self.access_token_minutes = int(os.environ.get("AGORA_ACCESS_MINUTES", "30"))
        self.refresh_token_days = int(os.environ.get("AGORA_REFRESH_DAYS", "7"))

        # ── LXD orchestrator state ────────────────────────────────────────────
        _prod_state = Path(os.environ.get("LAIA_STATE_ROOT", "/srv/laia/state"))
        _dev_state = self.laia_root / ".laia" / "state"
        self.lxd_state_dir = _prod_state if _prod_state.exists() else _dev_state
        self.lxd_state_path = self.lxd_state_dir / "agents.json"

        # ── laiactl binary ────────────────────────────────────────────────────
        self.laiactl_path = Path(
            os.environ.get("LAIACTL_PATH", str(self.laia_root / "infra" / "laiactl"))
        )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.workspaces_root.mkdir(parents=True, exist_ok=True)
        self.workspace_root.mkdir(parents=True, exist_ok=True)


settings = Settings()

