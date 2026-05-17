from __future__ import annotations

import json
import sys
from pathlib import Path

from .config import settings
from .database import Database
from .models import Agent, Event, Task, User, now_iso


def _row_to_dict(row) -> dict:
    return dict(row)


def _user_from_row(row) -> User:
    d = _row_to_dict(row)
    d["password"] = d.get("password") or None
    d["active"] = bool(d.get("active", 1))
    return User.model_validate(d)


def _task_from_row(row) -> Task:
    return Task.model_validate(_row_to_dict(row))


def _agent_from_row(row) -> Agent:
    return Agent.model_validate(_row_to_dict(row))


def _event_from_row(row) -> Event:
    d = _row_to_dict(row)
    if isinstance(d.get("payload"), str):
        try:
            d["payload"] = json.loads(d["payload"])
        except (json.JSONDecodeError, TypeError):
            d["payload"] = {}
    return Event.model_validate(d)


class AgoraStore:
    def __init__(self) -> None:
        settings.ensure_dirs()
        self.db = Database(settings.db_path)
        self.db.ensure_schema()
        self._migrate_from_json()
        self._ensure_seed_data()

        sys.path.insert(0, str(settings.laia_root))
        from workspace_store import WorkspaceStore

        self.workspace = WorkspaceStore(settings.workspace_root)
        self.workspace.ensure_schema()
        self._ensure_workspace_index()

    def _migrate_from_json(self) -> None:
        if not self.db.is_empty():
            return
        migrated = False
        if settings.users_path.exists():
            try:
                data = json.loads(settings.users_path.read_text(encoding="utf-8"))
                for item in data:
                    self.db.conn.execute(
                        "INSERT OR IGNORE INTO users (id, username, display_name, role, agent_id, token, password, active, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                        (item["id"], item["username"], item.get("display_name", item["username"]),
                         item.get("role", "employee"), item.get("agent_id"), item.get("token"),
                         item.get("password"), item.get("created_at", now_iso()), item.get("updated_at", now_iso())),
                    )
                settings.users_path.rename(settings.users_path.with_suffix(".json.bak"))
                migrated = True
            except Exception:
                pass
        if settings.tasks_path.exists():
            try:
                data = json.loads(settings.tasks_path.read_text(encoding="utf-8"))
                for item in data:
                    self.db.conn.execute(
                        "INSERT OR IGNORE INTO tasks (id, title, description, assignee_id, priority, status, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (item["id"], item["title"], item.get("description", ""),
                         item.get("assignee_id"), item.get("priority", "medium"),
                         item.get("status", "pending"), item.get("created_at", now_iso()), item.get("updated_at", now_iso())),
                    )
                settings.tasks_path.rename(settings.tasks_path.with_suffix(".json.bak"))
                migrated = True
            except Exception:
                pass
        if settings.agents_path.exists():
            try:
                data = json.loads(settings.agents_path.read_text(encoding="utf-8"))
                for item in data:
                    self.db.conn.execute(
                        "INSERT OR IGNORE INTO agents (id, user_id, container_name, status, workspace_path, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (item["id"], item["user_id"], item["container_name"],
                         item.get("status", "planned"), item.get("workspace_path", ""),
                         item.get("created_at", now_iso()), item.get("updated_at", now_iso())),
                    )
                settings.agents_path.rename(settings.agents_path.with_suffix(".json.bak"))
                migrated = True
            except Exception:
                pass
        if settings.events_path.exists():
            try:
                for line in settings.events_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    self.db.conn.execute(
                        "INSERT OR IGNORE INTO events (id, event_type, actor_id, summary, payload, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (item["id"], item["event_type"], item.get("actor_id"),
                         item.get("summary", ""), json.dumps(item.get("payload", {})),
                         item.get("created_at", now_iso())),
                    )
                settings.events_path.rename(settings.events_path.with_suffix(".jsonl.bak"))
                migrated = True
            except Exception:
                pass
        if migrated:
            self.db.conn.commit()

    def _ensure_workspace_index(self) -> None:
        if self.workspace.get_index_node():
            return
        self.workspace.upsert_node(
            slug="index",
            title="AGORA — Workspace colectivo",
            kind="index",
            summary="Workspace colectivo de AGORA.",
            body="# AGORA\n\nWorkspace colectivo para tareas, coordinacion y conocimiento publicado.",
            source_kind="manual",
        )

    def _ensure_seed_data(self) -> None:
        cur = self.db.conn.execute("SELECT count(*) FROM users")
        if cur.fetchone()[0] == 0:
            ts = now_iso()
            self.db.conn.execute(
                "INSERT INTO users (id, username, display_name, role, agent_id, token, password, active, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("user_jorge", "jorge", "Jorge", "agora_admin", "agent_jorge", "dev-admin-token", "dev-admin", 1, ts, ts),
            )
            self.db.conn.execute(
                "INSERT INTO agents (id, user_id, container_name, status, workspace_path, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("agent_jorge", "user_jorge", "laia-jorge", "planned",
                 "/opt/laia/workspaces/personal/workspace.db", ts, ts),
            )
            self.db.conn.commit()

    # ── users ──────────────────────────────────────────────────────────────

    def users(self) -> list[User]:
        rows = self.db.conn.execute("SELECT * FROM users WHERE active = 1 ORDER BY created_at").fetchall()
        users = [_user_from_row(r) for r in rows]
        for user in users:
            if user.username == "jorge" and not user.token:
                user.token = "dev-admin-token"
                self.save_user(user)
        return users

    def all_users(self) -> list[User]:
        rows = self.db.conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
        return [_user_from_row(r) for r in rows]

    def user_by_token(self, token: str) -> User | None:
        row = self.db.conn.execute("SELECT * FROM users WHERE token = ?", (token,)).fetchone()
        return _user_from_row(row) if row else None

    def user_by_id(self, user_id: str) -> User | None:
        row = self.db.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _user_from_row(row) if row else None

    def user_by_username(self, username: str) -> User | None:
        row = self.db.conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return _user_from_row(row) if row else None

    def save_user(self, user: User) -> None:
        d = user.model_dump()
        self.db.conn.execute(
            "INSERT OR REPLACE INTO users (id, username, display_name, role, agent_id, token, password, active, created_at, updated_at, "
            "llm_provider, llm_api_key, llm_base_url, llm_model, llm_api_mode, llm_extras_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (d["id"], d["username"], d["display_name"], d.get("role", "employee"),
             d.get("agent_id"), d.get("token"), d.get("password"),
             1 if d.get("active", True) else 0,
             d.get("created_at", now_iso()), d.get("updated_at", now_iso()),
             d.get("llm_provider"), d.get("llm_api_key"), d.get("llm_base_url"),
             d.get("llm_model"), d.get("llm_api_mode"), d.get("llm_extras_json")),
        )
        self.db.conn.commit()

    def update_user_llm_config(self, user_id: str, *,
                               provider: str | None = None,
                               api_key: str | None = None,
                               base_url: str | None = None,
                               model: str | None = None,
                               api_mode: str | None = None,
                               extras_json: str | None = None) -> User | None:
        """Patch LLM config fields for a user. Pass None to leave a field unchanged.

        To clear a field, pass an empty string (we treat "" as explicit-clear).
        """
        user = self.user_by_id(user_id)
        if user is None:
            return None

        def _resolve(new_val: str | None, current: str | None) -> str | None:
            if new_val is None:
                return current
            if new_val == "":
                return None
            return new_val

        user.llm_provider = _resolve(provider, user.llm_provider)
        user.llm_api_key = _resolve(api_key, user.llm_api_key)
        user.llm_base_url = _resolve(base_url, user.llm_base_url)
        user.llm_model = _resolve(model, user.llm_model)
        user.llm_api_mode = _resolve(api_mode, user.llm_api_mode)
        user.llm_extras_json = _resolve(extras_json, user.llm_extras_json)
        self.save_user(user)
        return user

    def save_users(self, users: list[User]) -> None:
        for u in users:
            self.save_user(u)

    def disable_user(self, user_id: str) -> bool:
        cur = self.db.conn.execute("UPDATE users SET active = 0, updated_at = ? WHERE id = ?", (now_iso(), user_id))
        self.db.conn.commit()
        return cur.rowcount > 0

    # ── tasks ──────────────────────────────────────────────────────────────

    def tasks(self) -> list[Task]:
        rows = self.db.conn.execute("SELECT * FROM tasks ORDER BY created_at").fetchall()
        return [_task_from_row(r) for r in rows]

    def save_tasks(self, tasks: list[Task]) -> None:
        for t in tasks:
            self.save_task(t)

    def save_task(self, task: Task) -> None:
        d = task.model_dump()
        self.db.conn.execute(
            "INSERT OR REPLACE INTO tasks (id, title, description, assignee_id, priority, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (d["id"], d["title"], d.get("description", ""), d.get("assignee_id"),
             d.get("priority", "medium"), d.get("status", "pending"),
             d.get("created_at", now_iso()), d.get("updated_at", now_iso())),
        )
        self.db.conn.commit()

    def delete_task(self, task_id: str) -> bool:
        cur = self.db.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.db.conn.commit()
        return cur.rowcount > 0

    def update_task(self, task_id: str, **changes) -> Task | None:
        existing = self.db.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not existing:
            return None
        data = _row_to_dict(existing)
        data.update({k: v for k, v in changes.items() if v is not None})
        data["updated_at"] = now_iso()
        self.db.conn.execute(
            "UPDATE tasks SET title=?, description=?, assignee_id=?, priority=?, status=?, updated_at=? WHERE id=?",
            (data["title"], data.get("description", ""), data.get("assignee_id"),
             data.get("priority", "medium"), data.get("status", "pending"),
             data["updated_at"], task_id),
        )
        self.db.conn.commit()
        return _task_from_row(self.db.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())

    # ── agents ─────────────────────────────────────────────────────────────

    def agents(self) -> list[Agent]:
        rows = self.db.conn.execute("SELECT * FROM agents ORDER BY created_at").fetchall()
        return [_agent_from_row(r) for r in rows]

    def save_agent(self, agent: Agent) -> None:
        d = agent.model_dump()
        self.db.conn.execute(
            "INSERT OR REPLACE INTO agents "
            "(id, user_id, container_name, status, workspace_path, container_ip, api_token, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (d["id"], d["user_id"], d["container_name"], d.get("status", "planned"),
             d.get("workspace_path", ""), d.get("container_ip"), d.get("api_token"),
             d.get("created_at", now_iso()), d.get("updated_at", now_iso())),
        )
        self.db.conn.commit()

    # ── events ─────────────────────────────────────────────────────────────

    def events(self) -> list[Event]:
        rows = self.db.conn.execute("SELECT * FROM events ORDER BY created_at DESC LIMIT 1000").fetchall()
        return [_event_from_row(r) for r in reversed(rows)]

    def record_event(self, event: Event) -> Event:
        d = event.model_dump()
        payload = json.dumps(d.get("payload", {}), ensure_ascii=False)
        self.db.conn.execute(
            "INSERT INTO events (id, event_type, actor_id, summary, payload, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (d["id"], d["event_type"], d.get("actor_id"), d.get("summary", ""),
             payload, d.get("created_at", now_iso())),
        )
        self.db.conn.commit()
        return event

    # ── telegram links ─────────────────────────────────────────────────────

    def link_telegram_user(self, telegram_user_id: str, agora_user_id: str) -> None:
        """Bind a Telegram chat identity to an AGORA user. Upserts on conflict."""
        self.db.conn.execute(
            "INSERT INTO telegram_links (telegram_user_id, agora_user_id, linked_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(telegram_user_id) DO UPDATE SET "
            "agora_user_id=excluded.agora_user_id, linked_at=excluded.linked_at",
            (str(telegram_user_id), agora_user_id, now_iso()),
        )
        self.db.conn.commit()

    def unlink_telegram_user(self, *, telegram_user_id: str | None = None,
                              agora_user_id: str | None = None) -> int:
        """Drop any link matching either identifier. Returns rows affected.

        Passing both narrows the match; passing one drops every row for it.
        """
        if telegram_user_id is None and agora_user_id is None:
            raise ValueError("provide telegram_user_id or agora_user_id")
        clauses: list[str] = []
        params: list[str] = []
        if telegram_user_id is not None:
            clauses.append("telegram_user_id = ?")
            params.append(str(telegram_user_id))
        if agora_user_id is not None:
            clauses.append("agora_user_id = ?")
            params.append(agora_user_id)
        sql = "DELETE FROM telegram_links WHERE " + " AND ".join(clauses)
        cur = self.db.conn.execute(sql, params)
        self.db.conn.commit()
        return cur.rowcount or 0

    def agora_user_for_telegram(self, telegram_user_id: str) -> str | None:
        """Return the AGORA user id linked to a Telegram user, or None."""
        row = self.db.conn.execute(
            "SELECT agora_user_id FROM telegram_links WHERE telegram_user_id = ?",
            (str(telegram_user_id),),
        ).fetchone()
        return row["agora_user_id"] if row else None

    def telegram_ids_for_user(self, agora_user_id: str) -> list[str]:
        rows = self.db.conn.execute(
            "SELECT telegram_user_id FROM telegram_links WHERE agora_user_id = ? "
            "ORDER BY linked_at",
            (agora_user_id,),
        ).fetchall()
        return [r["telegram_user_id"] for r in rows]


store = AgoraStore()
