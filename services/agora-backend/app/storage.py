from __future__ import annotations

import json
import logging
import os
import secrets
import sys
import threading
import uuid
from pathlib import Path

from .config import settings
from .database import Database
from .models import (
    Agent, AgentArea, AgentChildRun, AgentLearning, AutoImport,
    CoordinatorMessage, Event, ScheduledJob, Task, User, WebhookSubscription,
    new_id, now_iso,
)
from .laia_identity import (
    LAIA_USER_ID, LAIA_USERNAME, LAIA_DISPLAY_NAME,
    LAIA_SOUL, LAIA_INSTRUCTIONS,
)
from .security import hash_password


logger = logging.getLogger(__name__)


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


def _json_obj(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _agent_area_from_row(row) -> AgentArea:
    d = _row_to_dict(row)
    d["memory_preferences"] = _json_obj(d.pop("memory_preferences_json", None))
    d["behavior_preferences"] = _json_obj(d.pop("behavior_preferences_json", None))
    return AgentArea.model_validate(d)


def _event_from_row(row) -> Event:
    d = _row_to_dict(row)
    if isinstance(d.get("payload"), str):
        try:
            d["payload"] = json.loads(d["payload"])
        except (json.JSONDecodeError, TypeError):
            d["payload"] = {}
    return Event.model_validate(d)


def _admin_job_from_row(row) -> dict:
    d = _row_to_dict(row)
    params_raw = d.pop("params_json", "{}")
    result_raw = d.pop("result_json", None)
    try:
        d["params"] = json.loads(params_raw) if params_raw else {}
    except (json.JSONDecodeError, TypeError):
        d["params"] = {}
    try:
        d["result"] = json.loads(result_raw) if result_raw else None
    except (json.JSONDecodeError, TypeError):
        d["result"] = None
    return d


class AgoraStore:
    def __init__(self) -> None:
        self._admin_jobs_lock = threading.RLock()
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

        # Secondary read-only workspaces (e.g. ``doyouwin``). Each entry in
        # ``settings.secondary_workspaces`` is mounted only if the
        # ``workspace.db`` file actually exists on disk (so a fresh install
        # without the doyouwin import doesn't fail at boot).
        self.secondary_workspaces: dict[str, WorkspaceStore] = {}
        for entry in getattr(settings, "secondary_workspaces", []):
            root = entry.get("root")
            slug = entry.get("slug")
            if not root or not slug:
                continue
            db_path = Path(root) / "workspace.db"
            if not db_path.exists():
                continue
            try:
                ws = WorkspaceStore(root, read_only=bool(entry.get("read_only", True)))
                ws.ensure_schema()  # idempotent + verifies the .db is readable
            except Exception:
                continue
            self.secondary_workspaces[slug] = ws

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
            # Credenciales del admin seed: overridables por env SIEMPRE; los
            # literales dev-admin/dev-admin-token solo existen en AGORA_ENV=dev
            # (tests y scripts de infra/dev dependen de ellos). En cualquier
            # otro env un arranque limpio JAMÁS deja credenciales conocidas:
            # eso era admin instantáneo para cualquiera con red interna.
            # (Auditoría 2026-06-02, prod-db-seeds-hardcoded-jorge-credentials.)
            username = os.environ.get("AGORA_ADMIN_USERNAME", "jorge")
            password = os.environ.get("AGORA_ADMIN_PASSWORD") or ""
            token = os.environ.get("AGORA_ADMIN_TOKEN") or ""
            if settings.env == "dev":
                password = password or "dev-admin"
                token = token or "dev-admin-token"
            elif not password:
                # No se imprime: una password en el journal es un leak. El
                # operador define AGORA_ADMIN_PASSWORD antes del primer boot
                # o la resetea vía installer (factory.sh).
                password = secrets.token_urlsafe(24)
                logger.warning(
                    "seed: AGORA_ADMIN_PASSWORD no definido (AGORA_ENV=%s) — "
                    "admin %r creado con password aleatoria NO mostrada. "
                    "Definela por env o resetea con el installer.",
                    settings.env, username,
                )
            self.db.conn.execute(
                "INSERT INTO users (id, username, display_name, role, agent_id, token, password, active, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("user_jorge", username, username.capitalize(), "agora_admin",
                 "agent_jorge", token or None, hash_password(password), 1, ts, ts),
            )
            self.db.conn.execute(
                "INSERT INTO agents (id, user_id, container_name, status, workspace_path, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("agent_jorge", "user_jorge", "laia-jorge", "planned",
                 "/opt/laia/workspaces/personal/workspace.db", ts, ts),
            )
            self.db.conn.commit()

        # LAIA coordinator — always present, even in migrated DBs.
        # No agent_id → does not provision a container; lives inside
        # laia-agora. role=agora_admin so internal tools can read
        # events/users; /api/laia/chat endpoint validates that only
        # admins can send messages to it.
        existing = self.db.conn.execute(
            "SELECT 1 FROM users WHERE id = ?", (LAIA_USER_ID,),
        ).fetchone()
        if existing is None:
            ts = now_iso()
            self.db.conn.execute(
                "INSERT INTO users (id, username, display_name, role, agent_id, "
                "token, password, active, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, NULL, ?, NULL, 1, ?, ?)",
                # Token aleatorio por instalación. El literal anterior
                # ("laia-coordinator-token") era un bearer agora_admin
                # público en el repo y sin NINGÚN consumidor en el código —
                # mismo agujero que dev-admin-token. (Auditoría 2026-06-02.)
                (LAIA_USER_ID, LAIA_USERNAME, LAIA_DISPLAY_NAME,
                 "agora_admin", secrets.token_urlsafe(32), ts, ts),
            )
            self.db.conn.execute(
                "INSERT INTO agent_areas "
                "(user_id, agent_display_name, soul_md, instructions_md, "
                "memory_preferences_json, behavior_preferences_json, "
                "created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (LAIA_USER_ID, LAIA_DISPLAY_NAME, LAIA_SOUL, LAIA_INSTRUCTIONS,
                 "{}", '{"tone": "directo", "language": "es"}', ts, ts),
            )
            self.db.conn.commit()

    # ── users ──────────────────────────────────────────────────────────────

    def users(self) -> list[User]:
        # Sin self-heal de tokens: la versión anterior re-inyectaba el literal
        # "dev-admin-token" a jorge en cada lectura si su token estaba vacío —
        # rotar el token a mano era imposible. Un admin sin token estático
        # usa /api/login (JWT); el bearer es opt-in vía AGORA_ADMIN_TOKEN.
        rows = self.db.conn.execute("SELECT * FROM users WHERE active = 1 ORDER BY created_at").fetchall()
        return [_user_from_row(r) for r in rows]

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
            "llm_provider, llm_api_key, llm_base_url, llm_model, llm_api_mode, llm_extras_json, mcp_servers_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (d["id"], d["username"], d["display_name"], d.get("role", "employee"),
             d.get("agent_id"), d.get("token"), d.get("password"),
             1 if d.get("active", True) else 0,
             d.get("created_at", now_iso()), d.get("updated_at", now_iso()),
             d.get("llm_provider"), d.get("llm_api_key"), d.get("llm_base_url"),
             d.get("llm_model"), d.get("llm_api_mode"), d.get("llm_extras_json"),
             d.get("mcp_servers_json")),
        )
        self.db.conn.commit()

    def update_user_llm_config(self, user_id: str, *,
                               provider: str | None = None,
                               api_key: str | None = None,
                               base_url: str | None = None,
                               model: str | None = None,
                               api_mode: str | None = None,
                               extras_json: str | None = None,
                               mcp_servers_json: str | None = None) -> User | None:
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
        user.mcp_servers_json = _resolve(mcp_servers_json, user.mcp_servers_json)
        self.save_user(user)
        return user

    def save_users(self, users: list[User]) -> None:
        for u in users:
            self.save_user(u)

    def tokens_valid_since(self, user_id: str) -> int:
        """Return the unix timestamp after which tokens for this user are valid.

        Any JWT with ``iat < tokens_valid_since`` must be rejected. Returns
        0 (no revocation) when the user is unknown or the cut-off has never
        been set.
        """
        row = self.db.conn.execute(
            "SELECT tokens_valid_since FROM users WHERE id = ?", (user_id,),
        ).fetchone()
        if not row:
            return 0
        try:
            return int(row[0] or 0)
        except (TypeError, ValueError):
            return 0

    def revoke_user_tokens(self, user_id: str, cutoff: int | None = None) -> bool:
        """Invalidate every token issued at or before ``cutoff`` (default: now).

        Implements logout / "sign out everywhere" without keeping a JTI
        denylist. Returns True if a row was updated.
        """
        import time as _time
        cutoff = int(cutoff if cutoff is not None else _time.time())
        cur = self.db.conn.execute(
            "UPDATE users SET tokens_valid_since = ?, updated_at = ? "
            "WHERE id = ?",
            (cutoff, now_iso(), user_id),
        )
        self.db.conn.commit()
        return cur.rowcount > 0

    def disable_user(self, user_id: str) -> bool:
        """Soft-delete a user.

        We never ``DELETE FROM users`` — that would shatter audit trails
        (``events.actor_id``, ``usage_ledger.user_id``, ``tasks.assignee_id``,
        ``coordinator_messages.user_id``) that may point at this row long
        after the account is closed. Instead we flip ``active`` to 0; the
        login flow rejects inactive users, the admin job tears down the
        LXD container, and the bind-mount under ``/srv/laia/users/<slug>``
        is removed by that same job.

        Therefore the "no FK CASCADE" concern raised in audit reports is
        not an integrity problem: there is no hard delete to cascade from.
        Derived rows in ``user_plugins`` / ``user_skills`` / ``agent_areas``
        / ``agents`` remain by design and are filtered out of active
        listings via ``users.active = 1`` joins. If you need to truly
        purge a user (e.g. GDPR right-to-erasure), build a dedicated
        admin job that owns the full cleanup.
        """
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

    def delete_agent(self, agent_id: str) -> bool:
        cur = self.db.conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        self.db.conn.commit()
        return cur.rowcount > 0

    # ── agent areas ────────────────────────────────────────────────────────

    def agent_area_for_user(self, user: User | str, *, create: bool = True) -> AgentArea | None:
        user_obj = self.user_by_id(user) if isinstance(user, str) else user
        if user_obj is None:
            return None
        row = self.db.conn.execute(
            "SELECT * FROM agent_areas WHERE user_id = ?",
            (user_obj.id,),
        ).fetchone()
        if row is not None:
            return _agent_area_from_row(row)
        if not create:
            return None
        now = now_iso()
        area = AgentArea(
            user_id=user_obj.id,
            agent_display_name=user_obj.display_name or user_obj.username,
            soul_md="",
            instructions_md="",
            memory_preferences={},
            behavior_preferences={},
            created_at=now,
            updated_at=now,
        )
        self.save_agent_area(area)
        return area

    def save_agent_area(self, area: AgentArea) -> AgentArea:
        d = area.model_dump()
        now = now_iso()
        created = d.get("created_at") or now
        updated = d.get("updated_at") or now
        self.db.conn.execute(
            "INSERT OR REPLACE INTO agent_areas "
            "(user_id, agent_display_name, soul_md, instructions_md, "
            "memory_preferences_json, behavior_preferences_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                d["user_id"],
                d.get("agent_display_name") or "",
                d.get("soul_md") or "",
                d.get("instructions_md") or "",
                json.dumps(d.get("memory_preferences") or {}, ensure_ascii=False),
                json.dumps(d.get("behavior_preferences") or {}, ensure_ascii=False),
                created,
                updated,
            ),
        )
        self.db.conn.commit()
        saved = self.agent_area_for_user(d["user_id"], create=False)
        return saved or area

    def update_agent_area(self, user_id: str, **changes) -> AgentArea | None:
        user = self.user_by_id(user_id)
        if user is None:
            return None
        area = self.agent_area_for_user(user, create=True)
        if area is None:
            return None
        data = area.model_dump()
        for key, value in changes.items():
            if value is not None and key in data:
                data[key] = value
        data["updated_at"] = now_iso()
        return self.save_agent_area(AgentArea.model_validate(data))

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

    # ── admin jobs ─────────────────────────────────────────────────────────

    def create_admin_job(
        self,
        *,
        kind: str,
        actor_id: str,
        params: dict,
        log_path: str | None = None,
    ) -> dict:
        job_id = str(uuid.uuid4())
        ts = now_iso()
        with self._admin_jobs_lock:
            self.db.conn.execute(
                "INSERT INTO admin_jobs "
                "(id, kind, status, actor_id, params_json, log_path, progress, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    kind,
                    "pending",
                    actor_id,
                    json.dumps(params, ensure_ascii=False, sort_keys=True),
                    log_path,
                    0,
                    ts,
                ),
            )
            self.db.conn.commit()
        return self.admin_job(job_id) or {
            "id": job_id,
            "kind": kind,
            "status": "pending",
            "actor_id": actor_id,
            "params": params,
            "result": None,
            "error": None,
            "log_path": log_path,
            "progress": 0,
            "created_at": ts,
            "started_at": None,
            "finished_at": None,
        }

    def admin_job(self, job_id: str) -> dict | None:
        row = self.db.conn.execute("SELECT * FROM admin_jobs WHERE id = ?", (job_id,)).fetchone()
        return _admin_job_from_row(row) if row else None

    def admin_jobs(self, *, status: str | None = None, limit: int = 100) -> list[dict]:
        limit = max(1, min(limit, 500))
        if status:
            rows = self.db.conn.execute(
                "SELECT * FROM admin_jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self.db.conn.execute(
                "SELECT * FROM admin_jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_admin_job_from_row(r) for r in rows]

    def update_admin_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        result: dict | None = None,
        error: str | None = None,
        log_path: str | None = None,
        progress: int | None = None,
        mark_started: bool = False,
        mark_finished: bool = False,
    ) -> dict | None:
        assignments: list[str] = []
        values: list[object] = []
        if status is not None:
            assignments.append("status = ?")
            values.append(status)
        if result is not None:
            assignments.append("result_json = ?")
            values.append(json.dumps(result, ensure_ascii=False, sort_keys=True))
        if error is not None:
            assignments.append("error = ?")
            values.append(error)
        if log_path is not None:
            assignments.append("log_path = ?")
            values.append(log_path)
        if progress is not None:
            assignments.append("progress = ?")
            values.append(max(0, min(100, int(progress))))
        if mark_started:
            assignments.append("started_at = ?")
            values.append(now_iso())
        if mark_finished:
            assignments.append("finished_at = ?")
            values.append(now_iso())
        if not assignments:
            return self.admin_job(job_id)
        values.append(job_id)
        with self._admin_jobs_lock:
            self.db.conn.execute(
                f"UPDATE admin_jobs SET {', '.join(assignments)} WHERE id = ?",
                values,
            )
            self.db.conn.commit()
        return self.admin_job(job_id)


    # ── agent learnings ─────────────────────────────────────────────────────

    def _learning_from_row(self, row) -> AgentLearning:
        d = _row_to_dict(row)
        ctx_raw = d.pop("context_json", None)
        if isinstance(ctx_raw, str) and ctx_raw:
            try:
                ctx = json.loads(ctx_raw)
                d["context"] = ctx if isinstance(ctx, dict) else {}
            except (json.JSONDecodeError, TypeError):
                d["context"] = {}
        else:
            d["context"] = {}
        return AgentLearning.model_validate(d)

    def create_learning(
        self,
        *,
        user_id: str,
        kind: str,
        title: str,
        content_md: str,
        tags: str | None = None,
        context: dict | None = None,
    ) -> AgentLearning:
        learning = AgentLearning(
            user_id=user_id,
            kind=kind,
            title=title,
            content_md=content_md,
            tags=tags,
            context=context or {},
        )
        ctx_json = json.dumps(learning.context, ensure_ascii=False) if learning.context else None
        self.db.conn.execute(
            "INSERT INTO agent_learnings (id, user_id, kind, title, content_md, "
            "tags, context_json, confidence, times_referenced, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                learning.id, learning.user_id, learning.kind, learning.title,
                learning.content_md, learning.tags, ctx_json,
                learning.confidence, learning.times_referenced,
                learning.created_at, learning.updated_at,
            ),
        )
        self.db.conn.commit()
        return learning

    def list_learnings(
        self,
        *,
        user_id: str,
        kind: str | None = None,
        query: str | None = None,
        limit: int = 20,
    ) -> list[AgentLearning]:
        sql = "SELECT * FROM agent_learnings WHERE user_id = ?"
        params: list = [user_id]
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        if query:
            sql += " AND (title LIKE ? OR content_md LIKE ? OR IFNULL(tags,'') LIKE ?)"
            like = f"%{query}%"
            params.extend([like, like, like])
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 100)))
        rows = self.db.conn.execute(sql, params).fetchall()
        return [self._learning_from_row(r) for r in rows]

    def recent_learnings_for_user(
        self, user_id: str, *, limit: int = 10,
    ) -> list[AgentLearning]:
        # Order by updated_at desc + confidence (capped); SQL keeps it cheap.
        sql = (
            "SELECT * FROM agent_learnings WHERE user_id = ? "
            "ORDER BY (confidence * 0.7 + 0.3) DESC, updated_at DESC LIMIT ?"
        )
        rows = self.db.conn.execute(sql, (user_id, max(1, min(int(limit), 30)))).fetchall()
        return [self._learning_from_row(r) for r in rows]

    def bump_learning_referenced(self, learning_id: str) -> None:
        self.db.conn.execute(
            "UPDATE agent_learnings SET times_referenced = times_referenced + 1, "
            "updated_at = ? WHERE id = ?",
            (now_iso(), learning_id),
        )
        self.db.conn.commit()

    def delete_learning(self, learning_id: str, user_id: str) -> bool:
        cur = self.db.conn.execute(
            "DELETE FROM agent_learnings WHERE id = ? AND user_id = ?",
            (learning_id, user_id),
        )
        self.db.conn.commit()
        return cur.rowcount > 0


    # ── scheduled jobs (Fase A) ─────────────────────────────────────────────

    def _job_from_row(self, row) -> ScheduledJob:
        return ScheduledJob.model_validate(_row_to_dict(row))

    def create_scheduled_job(self, job: ScheduledJob) -> ScheduledJob:
        self.db.conn.execute(
            "INSERT INTO agent_scheduled_jobs "
            "(id, user_id, name, cron_expr, prompt, deliver, status, last_run_at, "
            "last_result, last_error, next_run_at, runs_total, runs_failed, "
            "consecutive_failures, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                job.id, job.user_id, job.name, job.cron_expr, job.prompt, job.deliver,
                job.status, job.last_run_at, job.last_result, job.last_error,
                job.next_run_at, job.runs_total, job.runs_failed,
                job.consecutive_failures, job.created_at, job.updated_at,
            ),
        )
        self.db.conn.commit()
        return job

    def get_scheduled_job(self, job_id: str) -> ScheduledJob | None:
        row = self.db.conn.execute(
            "SELECT * FROM agent_scheduled_jobs WHERE id = ?", (job_id,)
        ).fetchone()
        return self._job_from_row(row) if row else None

    def list_scheduled_jobs(self, user_id: str,
                            status: str | None = None) -> list[ScheduledJob]:
        sql = "SELECT * FROM agent_scheduled_jobs WHERE user_id = ?"
        params: list = [user_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC"
        rows = self.db.conn.execute(sql, params).fetchall()
        return [self._job_from_row(r) for r in rows]

    def list_due_scheduled_jobs(self, now_iso_str: str,
                                 limit: int = 20) -> list[ScheduledJob]:
        """Pick active jobs whose next_run_at has passed."""
        rows = self.db.conn.execute(
            "SELECT * FROM agent_scheduled_jobs "
            "WHERE status = 'active' AND next_run_at IS NOT NULL "
            "AND next_run_at <= ? ORDER BY next_run_at LIMIT ?",
            (now_iso_str, limit),
        ).fetchall()
        return [self._job_from_row(r) for r in rows]

    def update_scheduled_job(self, job_id: str, **fields) -> ScheduledJob | None:
        if not fields:
            return self.get_scheduled_job(job_id)
        keys = list(fields.keys())
        sql = (
            "UPDATE agent_scheduled_jobs SET "
            + ", ".join(f"{k} = ?" for k in keys)
            + ", updated_at = ? WHERE id = ?"
        )
        self.db.conn.execute(sql, [*fields.values(), now_iso(), job_id])
        self.db.conn.commit()
        return self.get_scheduled_job(job_id)

    def delete_scheduled_job(self, job_id: str, user_id: str) -> bool:
        cur = self.db.conn.execute(
            "DELETE FROM agent_scheduled_jobs WHERE id = ? AND user_id = ?",
            (job_id, user_id),
        )
        self.db.conn.commit()
        return cur.rowcount > 0

    # ── webhook subscriptions (Fase A) ──────────────────────────────────────

    def _webhook_from_row(self, row) -> WebhookSubscription:
        return WebhookSubscription.model_validate(_row_to_dict(row))

    def create_webhook_subscription(self, wh: WebhookSubscription) -> WebhookSubscription:
        self.db.conn.execute(
            "INSERT INTO webhook_subscriptions "
            "(id, user_id, slug, secret, prompt, deliver, last_trigger_at, "
            "last_status, triggers_total, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (wh.id, wh.user_id, wh.slug, wh.secret, wh.prompt, wh.deliver,
             wh.last_trigger_at, wh.last_status, wh.triggers_total,
             wh.created_at, wh.updated_at),
        )
        self.db.conn.commit()
        return wh

    def get_webhook_by_slug(self, slug: str) -> WebhookSubscription | None:
        row = self.db.conn.execute(
            "SELECT * FROM webhook_subscriptions WHERE slug = ?", (slug,)
        ).fetchone()
        return self._webhook_from_row(row) if row else None

    def get_webhook_by_id(self, wh_id: str) -> WebhookSubscription | None:
        row = self.db.conn.execute(
            "SELECT * FROM webhook_subscriptions WHERE id = ?", (wh_id,)
        ).fetchone()
        return self._webhook_from_row(row) if row else None

    def list_webhooks(self, user_id: str) -> list[WebhookSubscription]:
        rows = self.db.conn.execute(
            "SELECT * FROM webhook_subscriptions WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [self._webhook_from_row(r) for r in rows]

    def update_webhook(self, wh_id: str, **fields) -> WebhookSubscription | None:
        if not fields:
            return self.get_webhook_by_id(wh_id)
        keys = list(fields.keys())
        sql = (
            "UPDATE webhook_subscriptions SET "
            + ", ".join(f"{k} = ?" for k in keys)
            + ", updated_at = ? WHERE id = ?"
        )
        self.db.conn.execute(sql, [*fields.values(), now_iso(), wh_id])
        self.db.conn.commit()
        return self.get_webhook_by_id(wh_id)

    def delete_webhook(self, wh_id: str, user_id: str) -> bool:
        cur = self.db.conn.execute(
            "DELETE FROM webhook_subscriptions WHERE id = ? AND user_id = ?",
            (wh_id, user_id),
        )
        self.db.conn.commit()
        return cur.rowcount > 0


    # ── auto-imports (Fase B) ───────────────────────────────────────────────

    def _import_from_row(self, row) -> AutoImport:
        d = _row_to_dict(row)
        cfg_raw = d.pop("config_json", None)
        try:
            cfg = json.loads(cfg_raw) if cfg_raw else {}
            d["config"] = cfg if isinstance(cfg, dict) else {}
        except (json.JSONDecodeError, TypeError):
            d["config"] = {}
        d["enabled"] = bool(d.get("enabled", 1))
        return AutoImport.model_validate(d)

    def create_auto_import(self, imp: AutoImport) -> AutoImport:
        self.db.conn.execute(
            "INSERT INTO auto_imports "
            "(id, user_id, provider, config_json, last_synced_at, last_status, "
            "last_count, last_error, cron_expr, target_workspace, enabled, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (imp.id, imp.user_id, imp.provider,
             json.dumps(imp.config or {}, ensure_ascii=False),
             imp.last_synced_at, imp.last_status, imp.last_count, imp.last_error,
             imp.cron_expr, imp.target_workspace,
             1 if imp.enabled else 0, imp.created_at, imp.updated_at),
        )
        self.db.conn.commit()
        return imp

    def get_auto_import(self, imp_id: str) -> AutoImport | None:
        row = self.db.conn.execute(
            "SELECT * FROM auto_imports WHERE id = ?", (imp_id,),
        ).fetchone()
        return self._import_from_row(row) if row else None

    def list_auto_imports(self, user_id: str) -> list[AutoImport]:
        rows = self.db.conn.execute(
            "SELECT * FROM auto_imports WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [self._import_from_row(r) for r in rows]

    def update_auto_import(self, imp_id: str, **fields) -> AutoImport | None:
        if "config" in fields:
            fields["config_json"] = json.dumps(fields.pop("config") or {}, ensure_ascii=False)
        if "enabled" in fields:
            fields["enabled"] = 1 if fields["enabled"] else 0
        if not fields:
            return self.get_auto_import(imp_id)
        keys = list(fields.keys())
        sql = (
            "UPDATE auto_imports SET "
            + ", ".join(f"{k} = ?" for k in keys)
            + ", updated_at = ? WHERE id = ?"
        )
        self.db.conn.execute(sql, [*fields.values(), now_iso(), imp_id])
        self.db.conn.commit()
        return self.get_auto_import(imp_id)

    def delete_auto_import(self, imp_id: str, user_id: str) -> bool:
        cur = self.db.conn.execute(
            "DELETE FROM auto_imports WHERE id = ? AND user_id = ?",
            (imp_id, user_id),
        )
        self.db.conn.commit()
        return cur.rowcount > 0


    # ── child runs (Fase C) ────────────────────────────────────────────────

    def create_child_run(self, run: AgentChildRun) -> AgentChildRun:
        self.db.conn.execute(
            "INSERT INTO agent_child_runs "
            "(id, parent_user_id, parent_session_id, profile, purpose, prompt, "
            "response, tokens_used, duration_ms, status, error, "
            "started_at, finished_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run.id, run.parent_user_id, run.parent_session_id, run.profile,
             run.purpose, run.prompt, run.response, run.tokens_used,
             run.duration_ms, run.status, run.error,
             run.started_at, run.finished_at),
        )
        self.db.conn.commit()
        return run

    def update_child_run(self, run_id: str, **fields) -> AgentChildRun | None:
        if not fields:
            return self.get_child_run(run_id)
        keys = list(fields.keys())
        sql = (
            "UPDATE agent_child_runs SET "
            + ", ".join(f"{k} = ?" for k in keys)
            + " WHERE id = ?"
        )
        self.db.conn.execute(sql, [*fields.values(), run_id])
        self.db.conn.commit()
        return self.get_child_run(run_id)

    def get_child_run(self, run_id: str) -> AgentChildRun | None:
        row = self.db.conn.execute(
            "SELECT * FROM agent_child_runs WHERE id = ?", (run_id,),
        ).fetchone()
        if not row:
            return None
        return AgentChildRun.model_validate(_row_to_dict(row))

    def list_child_runs_for_session(self, parent_session_id: str,
                                     status: str | None = None) -> list[AgentChildRun]:
        sql = "SELECT * FROM agent_child_runs WHERE parent_session_id = ?"
        params: list = [parent_session_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY started_at DESC"
        rows = self.db.conn.execute(sql, params).fetchall()
        return [AgentChildRun.model_validate(_row_to_dict(r)) for r in rows]

    def list_child_runs_for_user(self, parent_user_id: str, *,
                                  limit: int = 20) -> list[AgentChildRun]:
        """All child runs ever spawned by a parent user, newest first.

        Used by the admin endpoint that powers the Childruns screen in
        the v2 control center.
        """
        limit = max(1, min(int(limit), 200))
        rows = self.db.conn.execute(
            "SELECT * FROM agent_child_runs WHERE parent_user_id = ? "
            "ORDER BY started_at DESC LIMIT ?",
            (parent_user_id, limit),
        ).fetchall()
        return [AgentChildRun.model_validate(_row_to_dict(r)) for r in rows]


    # ── usage ledger + budget (Fase D) ─────────────────────────────────────

    def record_usage(self, *, user_id: str, provider: str, model: str,
                     tokens_input: int, tokens_output: int,
                     cost_usd: float | None = None,
                     kind: str = "chat",
                     session_id: str | None = None) -> int:
        """Insert a usage row. Returns the new rowid. ``cost_usd`` may be
        ``None`` when pricing isn't configured for (provider, model)."""
        cur = self.db.conn.execute(
            "INSERT INTO usage_ledger "
            "(user_id, session_id, ts, provider, model, tokens_input, "
            "tokens_output, cost_usd, kind) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, session_id, now_iso(), provider or "", model or "",
             int(tokens_input or 0), int(tokens_output or 0),
             cost_usd, kind),
        )
        self.db.conn.commit()
        return cur.lastrowid

    def usage_total_for(self, user_id: str, *, since_iso: str,
                        kind: str | None = None) -> dict[str, Any]:
        """Aggregate usage since ``since_iso`` (inclusive)."""
        sql = ("SELECT COALESCE(SUM(tokens_input),0) AS tin, "
               "COALESCE(SUM(tokens_output),0) AS tout, "
               "COALESCE(SUM(cost_usd),0) AS cost, COUNT(*) AS n "
               "FROM usage_ledger WHERE user_id = ? AND ts >= ?")
        params: list = [user_id, since_iso]
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        row = self.db.conn.execute(sql, params).fetchone()
        return {
            "tokens_input": int(row["tin"] or 0),
            "tokens_output": int(row["tout"] or 0),
            "cost_usd": float(row["cost"] or 0.0),
            "calls": int(row["n"] or 0),
        }

    def usage_breakdown_for(self, user_id: str, *, since_iso: str,
                            ) -> list[dict[str, Any]]:
        """Per-(provider,model,kind) totals."""
        rows = self.db.conn.execute(
            "SELECT provider, model, kind, "
            "       COALESCE(SUM(tokens_input),0) AS tin, "
            "       COALESCE(SUM(tokens_output),0) AS tout, "
            "       COALESCE(SUM(cost_usd),0) AS cost, COUNT(*) AS n "
            "FROM usage_ledger WHERE user_id = ? AND ts >= ? "
            "GROUP BY provider, model, kind ORDER BY cost DESC",
            (user_id, since_iso),
        ).fetchall()
        return [
            {"provider": r["provider"], "model": r["model"], "kind": r["kind"],
             "tokens_input": int(r["tin"] or 0),
             "tokens_output": int(r["tout"] or 0),
             "cost_usd": float(r["cost"] or 0.0),
             "calls": int(r["n"] or 0)}
            for r in rows
        ]

    def get_user_budget(self, user_id: str) -> dict[str, Any]:
        """Return budget caps for the user (NULL when uncapped)."""
        row = self.db.conn.execute(
            "SELECT budget_daily_usd, budget_monthly_usd, budget_tokens_daily "
            "FROM users WHERE id = ?", (user_id,),
        ).fetchone()
        if row is None:
            return {"daily_usd": None, "monthly_usd": None, "tokens_daily": None}
        return {
            "daily_usd": row["budget_daily_usd"],
            "monthly_usd": row["budget_monthly_usd"],
            "tokens_daily": row["budget_tokens_daily"],
        }

    def set_user_budget(self, user_id: str, *,
                        daily_usd: float | None = ...,
                        monthly_usd: float | None = ...,
                        tokens_daily: int | None = ...) -> dict[str, Any]:
        """Patch budget cols. Use ``...`` to leave a field unchanged; pass
        ``None`` explicitly to clear."""
        cur = self.get_user_budget(user_id)
        new = {
            "daily_usd": cur["daily_usd"] if daily_usd is ... else daily_usd,
            "monthly_usd": cur["monthly_usd"] if monthly_usd is ... else monthly_usd,
            "tokens_daily": cur["tokens_daily"] if tokens_daily is ... else tokens_daily,
        }
        self.db.conn.execute(
            "UPDATE users SET budget_daily_usd = ?, budget_monthly_usd = ?, "
            "budget_tokens_daily = ?, updated_at = ? WHERE id = ?",
            (new["daily_usd"], new["monthly_usd"], new["tokens_daily"],
             now_iso(), user_id),
        )
        self.db.conn.commit()
        return new

    def budget_exceeded(self, user_id: str) -> tuple[bool, str | None]:
        """Return ``(exceeded, reason)``. Reason is None if within all caps."""
        budget = self.get_user_budget(user_id)
        # Daily window: from start-of-day UTC.
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

        if budget["daily_usd"] is not None:
            daily = self.usage_total_for(user_id, since_iso=start_of_day)
            if daily["cost_usd"] >= float(budget["daily_usd"]):
                return True, (
                    f"daily $ cap exceeded "
                    f"({daily['cost_usd']:.4f} >= {float(budget['daily_usd']):.4f})"
                )
        if budget["monthly_usd"] is not None:
            monthly = self.usage_total_for(user_id, since_iso=start_of_month)
            if monthly["cost_usd"] >= float(budget["monthly_usd"]):
                return True, (
                    f"monthly $ cap exceeded "
                    f"({monthly['cost_usd']:.4f} >= {float(budget['monthly_usd']):.4f})"
                )
        if budget["tokens_daily"] is not None:
            daily = self.usage_total_for(user_id, since_iso=start_of_day)
            total_tokens = daily["tokens_input"] + daily["tokens_output"]
            if total_tokens >= int(budget["tokens_daily"]):
                return True, (
                    f"daily tokens cap exceeded "
                    f"({total_tokens} >= {int(budget['tokens_daily'])})"
                )
        return False, None


    # ── coordinator inbox (Fase 1.3) ──────────────────────────────────────

    def create_coordinator_message(
        self,
        *,
        user_id: str,
        text: str,
        severity: str = "info",
        from_role: str = "laia",
    ) -> CoordinatorMessage:
        msg = CoordinatorMessage(
            id=new_id("coord"), user_id=user_id, text=text,
            severity=severity, from_role=from_role,
        )
        self.db.conn.execute(
            "INSERT INTO coordinator_messages "
            "(id, user_id, from_role, text, severity, read, created_at, read_at) "
            "VALUES (?, ?, ?, ?, ?, 0, ?, NULL)",
            (msg.id, msg.user_id, msg.from_role, msg.text,
             msg.severity, msg.created_at),
        )
        self.db.conn.commit()
        return msg

    def list_inbox(self, user_id: str, *, only_unread: bool = False,
                   limit: int = 50) -> list[CoordinatorMessage]:
        sql = "SELECT * FROM coordinator_messages WHERE user_id = ?"
        params: list = [user_id]
        if only_unread:
            sql += " AND read = 0"
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 200)))
        rows = self.db.conn.execute(sql, params).fetchall()
        out: list[CoordinatorMessage] = []
        for r in rows:
            d = _row_to_dict(r)
            d["read"] = bool(d.get("read", 0))
            out.append(CoordinatorMessage.model_validate(d))
        return out

    def mark_inbox_read(self, user_id: str,
                        message_ids: list[str] | None = None) -> int:
        """Mark messages as read. If ``message_ids`` is None, mark *all* unread
        for the user. Returns the number of rows updated."""
        ts = now_iso()
        if message_ids:
            placeholders = ",".join("?" * len(message_ids))
            cur = self.db.conn.execute(
                f"UPDATE coordinator_messages SET read = 1, read_at = ? "
                f"WHERE user_id = ? AND read = 0 AND id IN ({placeholders})",
                [ts, user_id, *message_ids],
            )
        else:
            cur = self.db.conn.execute(
                "UPDATE coordinator_messages SET read = 1, read_at = ? "
                "WHERE user_id = ? AND read = 0",
                (ts, user_id),
            )
        self.db.conn.commit()
        return cur.rowcount or 0

    def unread_count_for_user(self, user_id: str) -> int:
        row = self.db.conn.execute(
            "SELECT COUNT(*) AS n FROM coordinator_messages "
            "WHERE user_id = ? AND read = 0",
            (user_id,),
        ).fetchone()
        return int(row["n"] or 0) if row else 0


store = AgoraStore()
