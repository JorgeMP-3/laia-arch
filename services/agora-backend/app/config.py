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

        # ── Marketplace storage (marketplace-v0.1) ────────────────────────────
        # Publicly-served blobs (plugin tarballs, skill markdowns) and the
        # per-user extraction area used by the AgentPool to build
        # `LAIA_EXTRA_PLUGIN_DIRS` for each session.
        self.plugin_store_dir = self.data_dir / "plugin-store"
        self.skill_store_dir = self.data_dir / "skill-store"
        self.installed_plugins_root = self.data_dir / "installed-plugins"
        self.installed_skills_root = self.data_dir / "installed-skills"
        # Hard cap on the size of a single uploaded plugin tarball (bytes).
        self.plugin_upload_max_bytes = int(os.environ.get("AGORA_PLUGIN_MAX_BYTES", str(5 * 1024 * 1024)))
        # Hard cap on the size of a single uploaded skill markdown.
        self.skill_upload_max_bytes = int(os.environ.get("AGORA_SKILL_MAX_BYTES", str(256 * 1024)))

        # ── Secondary read-only workspaces ──────────────────────────────────
        # AGORA can mount additional read-only workspaces alongside the
        # collective one. Each entry is loaded into ``store.secondary_workspaces``
        # at boot if the .db file is present. Today: ``doyouwin`` (the ARCH
        # operational workspace, exposed read-only to agents).
        self.secondary_workspaces: list[dict] = [
            {
                "slug": "doyouwin",
                "root": self.workspaces_root / "doyouwin",
                "read_only": True,
            },
        ]

        # ── Auth ──────────────────────────────────────────────────────────────
        # AGORA_JWT_SECRET must be stable across restarts — a random fallback
        # would invalidate all active sessions on every restart.
        # Priority: env var → persistent secret file → generate+persist.
        self.jwt_secret = os.environ.get("AGORA_JWT_SECRET") or self._load_or_create_jwt_secret()
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

    def _load_or_create_jwt_secret(self) -> str:
        secret_file = self.prod_data_dir / "jwt-secret"
        try:
            if secret_file.exists():
                return secret_file.read_text().strip()
            secret = secrets.token_hex(32)
            secret_file.parent.mkdir(parents=True, exist_ok=True)
            secret_file.write_text(secret)
            secret_file.chmod(0o600)
            return secret
        except OSError:
            # Data dir not writable (tests, CI) — fall back to a session secret.
            return secrets.token_hex(32)

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.workspaces_root.mkdir(parents=True, exist_ok=True)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.plugin_store_dir.mkdir(parents=True, exist_ok=True)
        self.skill_store_dir.mkdir(parents=True, exist_ok=True)
        self.installed_plugins_root.mkdir(parents=True, exist_ok=True)
        self.installed_skills_root.mkdir(parents=True, exist_ok=True)


settings = Settings()

