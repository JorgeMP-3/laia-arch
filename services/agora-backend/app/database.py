from __future__ import annotations

import sqlite3
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
    updated_at TEXT NOT NULL
);

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
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
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
