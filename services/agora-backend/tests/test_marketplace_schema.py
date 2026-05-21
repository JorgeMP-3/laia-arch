"""Tests for marketplace-v0.1 DB schema additions (Fase A).

Verifies the new tables (plugin_registry, plugin_installs, skill_registry,
skill_installs) and the mcp_servers_json column exist after schema bootstrap,
and that migrations on a pre-marketplace DB are idempotent.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.database import Database


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def test_marketplace_tables_created_on_fresh_db(tmp_path: Path) -> None:
    db = Database(tmp_path / "agora.db")
    db.ensure_schema()

    tables = _tables(db.conn)
    for required in ("plugin_registry", "plugin_installs", "skill_registry", "skill_installs"):
        assert required in tables, f"missing {required}"


def test_users_table_has_mcp_servers_column_on_fresh_db(tmp_path: Path) -> None:
    db = Database(tmp_path / "agora.db")
    db.ensure_schema()
    assert "mcp_servers_json" in _columns(db.conn, "users")


def test_agent_areas_table_exists_on_fresh_db(tmp_path: Path) -> None:
    db = Database(tmp_path / "agora.db")
    db.ensure_schema()
    cols = _columns(db.conn, "agent_areas")
    assert {
        "user_id",
        "agent_display_name",
        "soul_md",
        "instructions_md",
        "memory_preferences_json",
        "behavior_preferences_json",
    }.issubset(cols)


def test_migration_adds_mcp_servers_column_on_legacy_db(tmp_path: Path) -> None:
    """A DB created before marketplace-v0.1 must gain the new column on next boot."""
    path = tmp_path / "agora.db"
    legacy = sqlite3.connect(str(path))
    legacy.executescript(
        """
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee',
            agent_id TEXT,
            token TEXT,
            password TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    legacy.commit()
    legacy.close()

    db = Database(path)
    db.ensure_schema()

    cols = _columns(db.conn, "users")
    # Both the legacy LLM columns and the new mcp column should now exist.
    for required in ("llm_provider", "llm_api_key", "llm_extras_json", "mcp_servers_json"):
        assert required in cols, f"missing migrated column {required}"
    assert "agent_areas" in _tables(db.conn)


def test_schema_migration_is_idempotent(tmp_path: Path) -> None:
    db = Database(tmp_path / "agora.db")
    db.ensure_schema()
    db.ensure_schema()  # second pass must not raise
    db.ensure_schema()  # nor a third

    # Sanity: tables and columns still intact.
    assert "plugin_registry" in _tables(db.conn)
    assert "mcp_servers_json" in _columns(db.conn, "users")


def test_plugin_registry_uniqueness_constraint(tmp_path: Path) -> None:
    db = Database(tmp_path / "agora.db")
    db.ensure_schema()
    db.conn.execute("INSERT INTO users (id, username, display_name, role, active, created_at, updated_at) "
                    "VALUES ('u1', 'alice', 'Alice', 'employee', 1, '2026-01-01', '2026-01-01')")
    db.conn.execute(
        "INSERT INTO plugin_registry "
        "(id, slug, version, kind, manifest_yaml, blob_path, owner_user_id, visibility, status, created_at) "
        "VALUES ('p1', 'hello', '0.1.0', 'standalone', 'slug: hello', '/p/hello-0.1.0.tgz', 'u1', 'personal', 'draft', '2026-01-01')"
    )
    db.conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.conn.execute(
            "INSERT INTO plugin_registry "
            "(id, slug, version, kind, manifest_yaml, blob_path, owner_user_id, visibility, status, created_at) "
            "VALUES ('p2', 'hello', '0.1.0', 'standalone', 'slug: hello', '/p/hello-0.1.0.tgz', 'u1', 'personal', 'draft', '2026-01-01')"
        )
        db.conn.commit()


def test_plugin_install_pk_prevents_double_install(tmp_path: Path) -> None:
    db = Database(tmp_path / "agora.db")
    db.ensure_schema()
    db.conn.execute("INSERT INTO users (id, username, display_name, role, active, created_at, updated_at) "
                    "VALUES ('u1', 'alice', 'Alice', 'employee', 1, '2026-01-01', '2026-01-01')")
    db.conn.execute(
        "INSERT INTO plugin_registry "
        "(id, slug, version, kind, manifest_yaml, blob_path, owner_user_id, visibility, status, created_at) "
        "VALUES ('p1', 'hello', '0.1.0', 'standalone', 'm', '/p/hello.tgz', 'u1', 'published', 'approved', '2026-01-01')"
    )
    db.conn.execute(
        "INSERT INTO plugin_installs (user_id, plugin_id, installed_at) VALUES ('u1', 'p1', '2026-01-01')"
    )
    db.conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.conn.execute(
            "INSERT INTO plugin_installs (user_id, plugin_id, installed_at) VALUES ('u1', 'p1', '2026-01-02')"
        )
        db.conn.commit()
