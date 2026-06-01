from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'employee',
    agent_id TEXT,
    token TEXT,
    password TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    llm_provider TEXT,
    llm_api_key TEXT,
    llm_base_url TEXT,
    llm_model TEXT,
    llm_api_mode TEXT,
    llm_extras_json TEXT,
    mcp_servers_json TEXT,
    budget_daily_usd REAL,
    budget_monthly_usd REAL,
    budget_tokens_daily INTEGER
);

CREATE TABLE IF NOT EXISTS conversations (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    agent_slug TEXT NOT NULL,
    messages_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS telegram_links (
    telegram_user_id TEXT PRIMARY KEY,
    agora_user_id TEXT NOT NULL,
    linked_at TEXT NOT NULL,
    FOREIGN KEY (agora_user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at);
CREATE INDEX IF NOT EXISTS idx_telegram_links_agora_user ON telegram_links(agora_user_id);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    assignee_id TEXT,
    priority TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (assignee_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    container_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    workspace_path TEXT NOT NULL,
    container_ip TEXT,
    api_token TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    actor_id TEXT,
    summary TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_agents_user ON agents(user_id);

CREATE TABLE IF NOT EXISTS agent_areas (
    user_id TEXT PRIMARY KEY,
    agent_display_name TEXT NOT NULL,
    soul_md TEXT NOT NULL DEFAULT '',
    instructions_md TEXT NOT NULL DEFAULT '',
    memory_preferences_json TEXT NOT NULL DEFAULT '{}',
    behavior_preferences_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS admin_jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    params_json TEXT NOT NULL,
    result_json TEXT,
    error TEXT,
    log_path TEXT,
    progress INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY (actor_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_admin_jobs_status ON admin_jobs(status);
CREATE INDEX IF NOT EXISTS idx_admin_jobs_actor ON admin_jobs(actor_id);

CREATE TABLE IF NOT EXISTS plugin_registry (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    version TEXT NOT NULL,
    kind TEXT NOT NULL,
    manifest_yaml TEXT NOT NULL,
    blob_path TEXT NOT NULL,
    owner_user_id TEXT NOT NULL,
    visibility TEXT NOT NULL,
    status TEXT NOT NULL,
    forward_tools_json TEXT,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    rejected_reason TEXT,
    UNIQUE(slug, version, owner_user_id),
    FOREIGN KEY (owner_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS plugin_installs (
    user_id TEXT NOT NULL,
    plugin_id TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    settings_json TEXT,
    installed_at TEXT NOT NULL,
    PRIMARY KEY (user_id, plugin_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (plugin_id) REFERENCES plugin_registry(id)
);

CREATE TABLE IF NOT EXISTS skill_registry (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    owner_user_id TEXT NOT NULL,
    manifest_md TEXT NOT NULL,
    blob_path TEXT,
    visibility TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    rejected_reason TEXT,
    UNIQUE(slug, owner_user_id),
    FOREIGN KEY (owner_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS skill_installs (
    user_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    installed_at TEXT NOT NULL,
    PRIMARY KEY (user_id, skill_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (skill_id) REFERENCES skill_registry(id)
);

CREATE INDEX IF NOT EXISTS idx_plugin_registry_status ON plugin_registry(status);
CREATE INDEX IF NOT EXISTS idx_plugin_registry_visibility ON plugin_registry(visibility);
CREATE INDEX IF NOT EXISTS idx_plugin_registry_owner ON plugin_registry(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_plugin_installs_user ON plugin_installs(user_id);
CREATE INDEX IF NOT EXISTS idx_skill_registry_status ON skill_registry(status);
CREATE INDEX IF NOT EXISTS idx_skill_registry_visibility ON skill_registry(visibility);
CREATE INDEX IF NOT EXISTS idx_skill_registry_owner ON skill_registry(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_skill_installs_user ON skill_installs(user_id);

CREATE TABLE IF NOT EXISTS agent_learnings (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    content_md TEXT NOT NULL,
    tags TEXT,
    context_json TEXT,
    confidence REAL NOT NULL DEFAULT 0.5,
    times_referenced INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_agent_learnings_user ON agent_learnings(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_learnings_kind ON agent_learnings(user_id, kind);
CREATE INDEX IF NOT EXISTS idx_agent_learnings_created ON agent_learnings(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS agent_scheduled_jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    cron_expr TEXT NOT NULL,
    prompt TEXT NOT NULL,
    deliver TEXT NOT NULL DEFAULT 'local',
    status TEXT NOT NULL DEFAULT 'active',
    last_run_at TEXT,
    last_result TEXT,
    last_error TEXT,
    next_run_at TEXT,
    runs_total INTEGER NOT NULL DEFAULT 0,
    runs_failed INTEGER NOT NULL DEFAULT 0,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_sched_user ON agent_scheduled_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_sched_next ON agent_scheduled_jobs(status, next_run_at);

CREATE TABLE IF NOT EXISTS webhook_subscriptions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    secret TEXT NOT NULL,
    prompt TEXT NOT NULL,
    deliver TEXT NOT NULL DEFAULT 'local',
    last_trigger_at TEXT,
    last_status TEXT,
    triggers_total INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_webhook_user ON webhook_subscriptions(user_id);

CREATE TABLE IF NOT EXISTS auto_imports (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    config_json TEXT NOT NULL,
    last_synced_at TEXT,
    last_status TEXT,
    last_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    cron_expr TEXT NOT NULL DEFAULT '0 */6 * * *',
    target_workspace TEXT NOT NULL DEFAULT 'private',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_auto_imports_user ON auto_imports(user_id);
CREATE INDEX IF NOT EXISTS idx_auto_imports_enabled ON auto_imports(enabled);

CREATE TABLE IF NOT EXISTS agent_child_runs (
    id TEXT PRIMARY KEY,
    parent_user_id TEXT NOT NULL,
    parent_session_id TEXT NOT NULL,
    profile TEXT NOT NULL,
    purpose TEXT NOT NULL,
    prompt TEXT NOT NULL,
    response TEXT,
    tokens_used INTEGER,
    duration_ms INTEGER,
    status TEXT NOT NULL,
    error TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY (parent_user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_child_parent ON agent_child_runs(parent_user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_child_session ON agent_child_runs(parent_session_id);

CREATE TABLE IF NOT EXISTS usage_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    session_id TEXT,
    ts TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    tokens_input INTEGER NOT NULL DEFAULT 0,
    tokens_output INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL,
    kind TEXT NOT NULL DEFAULT 'chat',
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_ledger_user_ts ON usage_ledger(user_id, ts);
CREATE INDEX IF NOT EXISTS idx_ledger_user_kind ON usage_ledger(user_id, kind);

CREATE TABLE IF NOT EXISTS coordinator_messages (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    from_role TEXT NOT NULL DEFAULT 'laia',
    text TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    read_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_coord_msgs_user ON coordinator_messages(user_id, read);
CREATE INDEX IF NOT EXISTS idx_coord_msgs_created ON coordinator_messages(user_id, created_at DESC);
"""


class LockedConnection(sqlite3.Connection):
    """SQLite connection that serializes access from FastAPI worker threads."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._lock = threading.RLock()

    def execute(self, *args, **kwargs):
        """Execute a single statement while holding the connection lock."""
        with self._lock:
            return super().execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        """Execute a parameterized statement repeatedly under the lock."""
        with self._lock:
            return super().executemany(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        """Execute a multi-statement SQL script under the lock."""
        with self._lock:
            return super().executescript(*args, **kwargs)

    def commit(self) -> None:
        """Commit the current transaction under the lock."""
        with self._lock:
            super().commit()

    def rollback(self) -> None:
        """Roll back the current transaction under the lock."""
        with self._lock:
            super().rollback()

    def close(self) -> None:
        """Close the connection under the lock."""
        with self._lock:
            super().close()


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(
                str(self.path),
                check_same_thread=False,
                timeout=30,
                factory=LockedConnection,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA busy_timeout=30000")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def ensure_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        # Migrations for older DBs: add columns if missing (idempotent).
        existing = {row[1] for row in self.conn.execute("PRAGMA table_info(agents)").fetchall()}
        for col, ddl in (("container_ip", "ALTER TABLE agents ADD COLUMN container_ip TEXT"),
                         ("api_token",    "ALTER TABLE agents ADD COLUMN api_token TEXT")):
            if col not in existing:
                self.conn.execute(ddl)
        # Migrations for users table — LLM config columns added in the redesign,
        # mcp_servers_json added in marketplace-v0.1, budget cols in v0.3.
        users_cols = {row[1] for row in self.conn.execute("PRAGMA table_info(users)").fetchall()}
        for col in ("llm_provider", "llm_api_key", "llm_base_url",
                    "llm_model", "llm_api_mode", "llm_extras_json",
                    "mcp_servers_json"):
            if col not in users_cols:
                self.conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
        # Budget cap columns (v0.3 Fase D). NULL = unlimited.
        for col, ddl in (
            ("budget_daily_usd", "ALTER TABLE users ADD COLUMN budget_daily_usd REAL"),
            ("budget_monthly_usd", "ALTER TABLE users ADD COLUMN budget_monthly_usd REAL"),
            ("budget_tokens_daily", "ALTER TABLE users ADD COLUMN budget_tokens_daily INTEGER"),
        ):
            if col not in users_cols:
                self.conn.execute(ddl)
        # Token revocation cut-off (v0.5 Fase 1). POST /api/logout sets
        # this to int(time.time()); ``current_user`` rejects any JWT whose
        # ``iat`` is older. Kills all access AND refresh tokens for the
        # user in one stroke without keeping a JTI denylist.
        if "tokens_valid_since" not in users_cols:
            self.conn.execute(
                "ALTER TABLE users ADD COLUMN tokens_valid_since INTEGER NOT NULL DEFAULT 0"
            )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS agent_areas ("
            "user_id TEXT PRIMARY KEY, "
            "agent_display_name TEXT NOT NULL, "
            "soul_md TEXT NOT NULL DEFAULT '', "
            "instructions_md TEXT NOT NULL DEFAULT '', "
            "memory_preferences_json TEXT NOT NULL DEFAULT '{}', "
            "behavior_preferences_json TEXT NOT NULL DEFAULT '{}', "
            "created_at TEXT NOT NULL, "
            "updated_at TEXT NOT NULL, "
            "FOREIGN KEY (user_id) REFERENCES users(id)"
            ")"
        )
        self.conn.commit()

    def backup(self) -> Path:
        import shutil
        from datetime import datetime, timezone

        backup_path = self.path.with_suffix(
            f".db.bak-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        )
        if self._conn is not None:
            self._conn.commit()
        if self.path.exists():
            shutil.copy(str(self.path), str(backup_path))
        return backup_path

    def close(self) -> None:
        if self._conn is not None:
            self._conn.commit()
            self._conn.close()
            self._conn = None

    def is_empty(self) -> bool:
        cur = self.conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = cur.fetchone()[0]
        if tables == 0:
            return True
        cur = self.conn.execute("SELECT count(*) FROM users")
        return cur.fetchone()[0] == 0
