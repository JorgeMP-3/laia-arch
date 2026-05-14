from __future__ import annotations

import json
import re
import shutil
import sqlite3
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

SCHEMA_VERSION = 1
DEFAULT_NODE_STATUS = "active"
STANDARD_FOLDERS = [
    "code",
    "code/scripts",
]
STOPWORDS = {
    "de", "la", "el", "en", "los", "las", "un", "una", "y", "a", "que",
    "es", "por", "con", "del", "al", "se", "su", "hay", "son", "si",
    "me", "te", "le", "nos", "les", "mas", "más", "pero", "como", "para",
    "este", "esta", "estos", "estas", "mi", "tu", "qué", "quien", "quién",
    "quienes", "quiénes", "donde", "dónde", "cuando", "cuándo", "como",
}
EDGE_TYPES = {"contains", "details", "related_to", "project_of", "depends_on", "references"}
CANONICAL_NODE_KINDS = {
    "index",
    "project",
    "topic",
    "important",
    "doc",
    "agent-note",
    "agent-plan",
    "agent-log",
    "script",
    "reference",
}
LEGACY_NODE_KINDS = {"detail", "agent-node"}
NODE_KINDS = CANONICAL_NODE_KINDS | LEGACY_NODE_KINDS
EXPORTED_KINDS = CANONICAL_NODE_KINDS
KIND_ORDER = {
    "index": 0,
    "project": 1,
    "topic": 2,
    "important": 3,
    "doc": 4,
    "script": 5,
    "reference": 6,
    "agent-note": 7,
    "agent-plan": 8,
    "agent-log": 9,
    "agent-node": 10,
    "detail": 11,
}
ARTIFICIAL_GLOBAL_CONTAINER_SLUGS = {
    "projects",
    "topics",
    "important",
    "agent-notes",
    "scripts",
    "references",
    "docs",
}
ARTIFICIAL_CONTAINER_SUFFIXES = (
    "-topics",
    "-topic",
    "-docs",
    "-important",
    "-scripts",
    "-references",
)
INDICATOR_RE = re.compile(r"^[\-\s]*[→>-]+\s*(.+?):\s*`?([\w\-.]+\.md)`?\s*$", re.UNICODE)
TITLE_RE = re.compile(r"^\s*#\s+(.+?)\s*$")
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_\-]{1,}", re.IGNORECASE)


@dataclass
class WorkspaceIssue:
    severity: str
    message: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "node"


def _humanize_slug(slug: str) -> str:
    words = slug.replace("_", " ").replace("-", " ").split()
    return " ".join(word.capitalize() for word in words) or "Nodo"


def _first_meaningful_paragraph(text: str) -> str:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    for block in blocks:
        if block.startswith("→") or block.startswith("->"):
            continue
        return block
    return ""


def _utc_display(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return value


def _tokenize_query(query: str) -> list[str]:
    tokens = []
    for token in TOKEN_RE.findall(query.lower()):
        if token in STOPWORDS or len(token) < 3:
            continue
        tokens.append(token)
    return tokens


def _replace_managed_section(body: str, section_id: str, title: str, content: str) -> str:
    """Replace an auto-managed Markdown block without touching manual text.

    `agent-team` and `agent-log` can contain human-written notes. Hermes only
    owns sections delimited by these comments, so agents can sync status safely.
    """
    start = f"<!-- hermes:{section_id}:start -->"
    end = f"<!-- hermes:{section_id}:end -->"
    section = f"{start}\n\n## {title}\n\n{content.strip()}\n\n{end}"
    body = body.rstrip()
    pattern = re.compile(
        rf"\n*{re.escape(start)}.*?{re.escape(end)}",
        re.DOTALL,
    )
    if pattern.search(body):
        # Use a replacement function so literal backslashes in Markdown, such
        # as JSON unicode escapes (`\u00f3`), are not interpreted by re.sub.
        return pattern.sub(lambda _: "\n\n" + section, body).strip()
    return (body + "\n\n" + section).strip() if body else section


def _infer_kind_from_filename(name: str) -> str:
    if name == "00-index.md":
        return "index"
    stem = name[:-3] if name.endswith(".md") else name
    if "important" in stem:
        return "important"
    if re.match(r"^\d{2}[a-z]-", stem):
        return "detail"
    if re.match(r"^\d{2}-", stem):
        return "topic"
    if stem.startswith("project-"):
        return "project"
    return "detail"


def _strip_heading_and_indicators(content: str) -> tuple[str, list[tuple[str, str]]]:
    lines = content.splitlines()
    body_lines: list[str] = []
    indicators: list[tuple[str, str]] = []

    for idx, line in enumerate(lines):
        if idx == 0 and TITLE_RE.match(line):
            continue
        match = INDICATOR_RE.match(line.strip())
        if match:
            indicators.append((match.group(1).strip(), match.group(2).strip()))
            continue
        body_lines.append(line)

    body = "\n".join(body_lines).strip()
    return body, indicators


def _is_legacy_source(source_kind: str) -> bool:
    return (
        source_kind == "markdown-import"
        or source_kind.startswith("legacy-")
        or source_kind == "legacy"
    )


class WorkspaceStore:
    def __init__(self, workspace_root: Path | str):
        self.root = Path(workspace_root)
        self.workspace = self.root.name
        self.db_path = self.root / "workspace.db"

    # -- Low-level ---------------------------------------------------------

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def exists(self) -> bool:
        return self.db_path.exists()

    def db_mtime(self) -> float:
        if not self.db_path.exists():
            return 0.0
        return self.db_path.stat().st_mtime

    def ensure_workspace_layout(self) -> list[str]:
        created = []
        for folder in STANDARD_FOLDERS:
            path = self.root / folder
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                created.append(folder)
        return created

    def ensure_schema(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.ensure_workspace_layout()
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS workspace_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    body TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    parent_id INTEGER,
                    source_kind TEXT NOT NULL DEFAULT 'manual',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(parent_id) REFERENCES nodes(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_node_id INTEGER NOT NULL,
                    to_node_id INTEGER NOT NULL,
                    edge_type TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    UNIQUE(from_node_id, to_node_id, edge_type),
                    FOREIGN KEY(from_node_id) REFERENCES nodes(id) ON DELETE CASCADE,
                    FOREIGN KEY(to_node_id) REFERENCES nodes(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id INTEGER NOT NULL,
                    alias TEXT NOT NULL UNIQUE,
                    alias_kind TEXT NOT NULL DEFAULT 'general',
                    FOREIGN KEY(node_id) REFERENCES nodes(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id INTEGER,
                    path TEXT NOT NULL UNIQUE,
                    artifact_type TEXT NOT NULL DEFAULT 'file',
                    description TEXT NOT NULL DEFAULT '',
                    mtime REAL NOT NULL DEFAULT 0,
                    FOREIGN KEY(node_id) REFERENCES nodes(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    node_id INTEGER,
                    payload TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(node_id) REFERENCES nodes(id) ON DELETE SET NULL
                );
                """
            )
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS node_fts
                USING fts5(title, slug, summary, body, aliases, tokenize='unicode61 remove_diacritics 2')
                """
            )
            self._set_meta(conn, "schema_version", str(SCHEMA_VERSION))
            self._set_meta(conn, "workspace_name", self.workspace)
            has_updated = conn.execute(
                "SELECT value FROM workspace_meta WHERE key = 'updated_at' LIMIT 1"
            ).fetchone()
            if has_updated is None:
                self._set_meta(conn, "updated_at", _now())

    def _set_meta(self, conn: sqlite3.Connection, key: str, value: str) -> None:
        conn.execute(
            """
            INSERT INTO workspace_meta(key, value)
            VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (key, value),
        )

    def meta(self) -> dict[str, str]:
        if not self.exists():
            return {}
        with self.connect() as conn:
            rows = conn.execute("SELECT key, value FROM workspace_meta").fetchall()
        return {row["key"]: row["value"] for row in rows}

    # -- Node CRUD ---------------------------------------------------------

    def _normalize_kind(self, kind: str, *, source_kind: str = "manual") -> str:
        kind = (kind or "").strip()
        if kind not in NODE_KINDS:
            raise ValueError(f"kind inválido: {kind}")
        if kind == "agent-node" and not _is_legacy_source(source_kind):
            raise ValueError("kind='agent-node' es legacy; usa 'agent-note', 'agent-plan' o 'agent-log'")
        if kind == "detail" and not _is_legacy_source(source_kind):
            raise ValueError("kind='detail' es legacy; usa 'important', 'doc' o 'topic' según el contenido")
        return kind

    def get_node(self, ref: str | int) -> Optional[dict[str, Any]]:
        if not self.exists():
            return None
        with self.connect() as conn:
            if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
                row = conn.execute("SELECT * FROM nodes WHERE id = ?", (int(ref),)).fetchone()
            else:
                row = conn.execute("SELECT * FROM nodes WHERE slug = ?", (str(ref),)).fetchone()
                if row is None:
                    row = conn.execute(
                        """
                        SELECT n.*
                        FROM aliases a
                        JOIN nodes n ON n.id = a.node_id
                        WHERE a.alias = ?
                        """,
                        (str(ref),),
                    ).fetchone()
            if row is None:
                return None
            return self._row_to_node(conn, row)

    def get_index_node(self) -> Optional[dict[str, Any]]:
        return self.get_node("00-index.md") or self.get_node("index")

    def list_context_nodes(self) -> list[dict[str, Any]]:
        if not self.exists():
            return []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM nodes
                WHERE kind IN ('index', 'project', 'topic', 'important', 'doc', 'agent-note', 'agent-plan', 'agent-log', 'script', 'reference')
                ORDER BY CASE kind
                    WHEN 'index' THEN 0
                    WHEN 'project' THEN 1
                    WHEN 'topic' THEN 2
                    WHEN 'important' THEN 3
                    WHEN 'doc' THEN 4
                    WHEN 'script' THEN 5
                    WHEN 'reference' THEN 6
                    WHEN 'agent-note' THEN 7
                    WHEN 'agent-plan' THEN 8
                    WHEN 'agent-log' THEN 9
                    ELSE 10
                END, lower(title), id
                """
            ).fetchall()
            return [self._row_to_node(conn, row) for row in rows]

    def upsert_node(
        self,
        *,
        slug: str,
        title: str,
        kind: str,
        summary: str = "",
        body: str = "",
        status: str = DEFAULT_NODE_STATUS,
        parent_ref: str | int | None = None,
        source_kind: str = "manual",
        aliases: Optional[Iterable[str]] = None,
        filename: str | None = None,
        ensure_taxonomy: bool = True,
    ) -> dict[str, Any]:
        self.ensure_schema()
        slug = _slugify(slug)
        kind = self._normalize_kind(kind, source_kind=source_kind)
        if ensure_taxonomy and source_kind != "taxonomy" and kind != "index" and not _is_legacy_source(source_kind):
            self.ensure_workspace_taxonomy()
        now = _now()

        with self.connect() as conn:
            if parent_ref is None and source_kind in {"manual", "tool", "interactive"} and kind != "index":
                parent_ref = self._default_parent_ref_for_kind(kind)
            parent_id = self._resolve_node_id(conn, parent_ref)
            self._validate_node_write(conn, slug, kind, parent_id, source_kind)
            existing = conn.execute("SELECT id FROM nodes WHERE slug = ?", (slug,)).fetchone()
            if existing:
                node_id = existing["id"]
                conn.execute(
                    """
                    UPDATE nodes
                    SET title=?, kind=?, summary=?, body=?, status=?, parent_id=?, source_kind=?, updated_at=?
                    WHERE id=?
                    """,
                    (title, kind, summary, body, status, parent_id, source_kind, now, node_id),
                )
                event_type = "node_updated"
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO nodes(slug, title, kind, summary, body, status, parent_id, source_kind, created_at, updated_at)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (slug, title, kind, summary, body, status, parent_id, source_kind, now, now),
                )
                node_id = cursor.lastrowid
                event_type = "node_created"

            conn.execute("DELETE FROM aliases WHERE node_id = ? AND alias_kind = 'general'", (node_id,))
            for alias in sorted({_slugify(slug), *(aliases or [])}):
                if not alias:
                    continue
                conn.execute(
                    """
                    INSERT INTO aliases(node_id, alias, alias_kind)
                    VALUES(?, ?, 'general')
                    ON CONFLICT(alias) DO UPDATE SET node_id=excluded.node_id, alias_kind='general'
                    """,
                    (node_id, alias),
                )

            if filename:
                self._set_filename_alias(conn, node_id, filename)
            elif kind == "index":
                self._set_filename_alias(conn, node_id, "00-index.md")

            self._record_event(conn, event_type, node_id, {"slug": slug, "kind": kind})
            self._sync_fts(conn, node_id)
            self._set_meta(conn, "updated_at", now)
            row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
            node = self._row_to_node(conn, row)

        if ensure_taxonomy and source_kind != "taxonomy":
            self.repair_contains_edges()
        return node

    def _default_parent_ref_for_kind(self, kind: str) -> str | None:
        if kind == "index":
            return None
        return "00-index.md"

    def _is_container_row(self, row: sqlite3.Row | dict[str, Any]) -> bool:
        return False

    def _validate_node_write(
        self,
        conn: sqlite3.Connection,
        slug: str,
        kind: str,
        parent_id: Optional[int],
        source_kind: str,
    ) -> None:
        if source_kind == "taxonomy" or _is_legacy_source(source_kind):
            return

        existing_node = conn.execute(
            "SELECT kind, parent_id, source_kind FROM nodes WHERE slug = ?",
            (slug,),
        ).fetchone()

        if kind == "index":
            existing = conn.execute("SELECT id, slug FROM nodes WHERE kind = 'index'").fetchone()
            if existing and existing["slug"] != slug:
                raise ValueError("Solo puede existir un nodo kind='index' por workspace")
            if parent_id is not None:
                raise ValueError("El nodo index no puede tener padre")

        if parent_id is None:
            return

        parent = conn.execute("SELECT slug, kind, source_kind FROM nodes WHERE id = ?", (parent_id,)).fetchone()
        if parent is None:
            raise ValueError("parent inválido")

        parent_slug = parent["slug"]
        parent_kind = parent["kind"]

        if parent_slug in ARTIFICIAL_GLOBAL_CONTAINER_SLUGS or parent_slug.endswith(ARTIFICIAL_CONTAINER_SUFFIXES):
            raise ValueError("No uses nodos contenedor artificiales; cuelga el nodo del index o del project real")

        if kind == "project" and parent_kind != "index":
            raise ValueError("Los nodos project deben vivir directamente bajo el index")

        if kind == "topic":
            if parent_kind == "topic":
                raise ValueError("Un topic real no puede contener subtopics")
            if parent_kind not in {"index", "project"}:
                raise ValueError("Los topics deben vivir directamente bajo el index o bajo un project")

        if kind in {"doc", "important", "script", "reference"} and parent_kind not in {"index", "project", "topic"}:
            raise ValueError("Los nodos de contenido deben vivir bajo index, project o topic")

        if kind == "agent-note" and slug not in {"agent-behavior", "agent-team"}:
            raise ValueError("agent-note se reserva para agent-behavior y agent-team")
        if kind == "agent-note" and parent_kind not in {"index", "project"}:
            raise ValueError("Los agent-note base viven bajo index o bajo el project relevante")

        if kind == "agent-plan":
            if parent_kind != "agent-note" or parent_slug != "agent-team":
                raise ValueError("Los agent-plan deben vivir bajo agent-team")

        if kind == "agent-log":
            if slug == "agent-log" and parent_kind in {"index", "project"}:
                return
            if parent_kind != "agent-plan":
                raise ValueError("Los agent-log viven como agent-log global bajo index/project o como hijos de un agent-plan")

    def ensure_workspace_taxonomy(self) -> dict[str, Any]:
        self.ensure_schema()
        index_node = self.get_index_node()
        if index_node is None:
            index_node = self.upsert_node(
                slug="index",
                title=f"{_humanize_slug(self.workspace)} — Índice Base",
                kind="index",
                summary=f"Workspace {self.workspace}.",
                body=self._default_index_body(f"Workspace {self.workspace}."),
                source_kind="taxonomy",
                filename="00-index.md",
                ensure_taxonomy=False,
            )

        cleanup = self.repair_flat_taxonomy()
        self.repair_contains_edges()
        return {"index": self.get_index_node(), "containers": [], "cleanup": cleanup}

    def _is_artificial_container_slug(self, slug: str) -> bool:
        return slug in ARTIFICIAL_GLOBAL_CONTAINER_SLUGS or slug.endswith(ARTIFICIAL_CONTAINER_SUFFIXES)

    def repair_flat_taxonomy(self) -> dict[str, int]:
        """Remove old container nodes and reparent their children to real parents."""
        self.ensure_schema()
        reparented = 0
        deleted = 0
        converted = 0
        renamed = 0
        with self.connect() as conn:
            index = conn.execute("SELECT id FROM nodes WHERE kind = 'index' ORDER BY id LIMIT 1").fetchone()
            if index is None:
                return {"reparented": 0, "deleted": 0, "converted": 0}
            index_id = index["id"]

            before = conn.total_changes
            conn.execute(
                """
                UPDATE nodes
                SET kind = CASE
                    WHEN slug = 'agent-log' THEN 'agent-log'
                    WHEN slug IN ('agent-behavior', 'agent-team') THEN 'agent-note'
                    WHEN slug LIKE 'agent-plan-%' THEN 'agent-plan'
                    WHEN slug LIKE 'agent-request-%' THEN 'agent-plan'
                    WHEN slug LIKE 'agent-task-%' THEN 'agent-plan'
                    WHEN slug LIKE 'agent-review-%' THEN 'agent-plan'
                    WHEN slug LIKE 'agent-handoff-%' THEN 'agent-plan'
                    ELSE 'doc'
                END,
                updated_at = ?
                WHERE kind = 'agent-node'
                """,
                (_now(),),
            )
            converted += conn.total_changes - before

            container_rows = conn.execute(
                """
                SELECT id, slug, parent_id
                FROM nodes
                WHERE (source_kind = 'taxonomy' AND kind != 'index')
                   OR slug IN ('projects', 'topics', 'important', 'agent-notes', 'scripts', 'references', 'docs')
                   OR slug LIKE '%-topics'
                   OR slug LIKE '%-topic'
                   OR slug LIKE '%-docs'
                   OR slug LIKE '%-important'
                   OR slug LIKE '%-scripts'
                   OR slug LIKE '%-references'
                ORDER BY length(slug) DESC, id DESC
                """
            ).fetchall()

            for row in container_rows:
                container_id = row["id"]
                if row["slug"] == "agent-node":
                    continue
                new_parent_id = row["parent_id"] or index_id
                children = conn.execute("SELECT id FROM nodes WHERE parent_id = ?", (container_id,)).fetchall()
                for child in children:
                    conn.execute("UPDATE nodes SET parent_id = ?, updated_at = ? WHERE id = ?", (new_parent_id, _now(), child["id"]))
                    reparented += 1
                conn.execute("DELETE FROM edges WHERE from_node_id = ? OR to_node_id = ?", (container_id, container_id))
                conn.execute("DELETE FROM aliases WHERE node_id = ?", (container_id,))
                conn.execute("DELETE FROM artifacts WHERE node_id = ?", (container_id,))
                conn.execute("DELETE FROM node_fts WHERE rowid = ?", (container_id,))
                conn.execute("DELETE FROM nodes WHERE id = ?", (container_id,))
                deleted += 1

            project_rows = conn.execute(
                "SELECT id, slug FROM nodes WHERE kind = 'project' AND slug LIKE 'project-%' ORDER BY id"
            ).fetchall()
            for row in project_rows:
                new_slug = row["slug"].removeprefix("project-")
                if not new_slug:
                    continue
                conflict = conn.execute("SELECT id FROM nodes WHERE slug = ? AND id != ?", (new_slug, row["id"])).fetchone()
                if conflict:
                    continue
                conn.execute("UPDATE nodes SET slug = ?, updated_at = ? WHERE id = ?", (new_slug, _now(), row["id"]))
                conn.execute("DELETE FROM aliases WHERE node_id = ? AND alias_kind = 'filename'", (row["id"],))
                conn.execute(
                    """
                    INSERT INTO aliases(node_id, alias, alias_kind)
                    VALUES(?, ?, 'filename')
                    ON CONFLICT(alias) DO UPDATE SET node_id=excluded.node_id, alias_kind='filename'
                    """,
                    (row["id"], f"{new_slug}.md"),
                )
                renamed += 1
                self._sync_fts(conn, row["id"])

            duplicate_index_projects = conn.execute(
                "SELECT id, slug FROM nodes WHERE kind = 'project' AND slug LIKE '%-index' ORDER BY id"
            ).fetchall()
            for row in duplicate_index_projects:
                base_slug = row["slug"][: -len("-index")]
                base = conn.execute("SELECT id FROM nodes WHERE slug = ? AND kind = 'project'", (base_slug,)).fetchone()
                if base is None:
                    continue
                conn.execute(
                    "UPDATE nodes SET kind = 'doc', parent_id = ?, updated_at = ? WHERE id = ?",
                    (base["id"], _now(), row["id"]),
                )
                converted += 1
                self._sync_fts(conn, row["id"])

            team_row = conn.execute("SELECT id FROM nodes WHERE slug = 'agent-team' LIMIT 1").fetchone()
            if team_row:
                plan_rows = conn.execute(
                    "SELECT id FROM nodes WHERE kind = 'agent-plan' AND (parent_id IS NULL OR parent_id != ?)",
                    (team_row["id"],),
                ).fetchall()
                for row in plan_rows:
                    conn.execute("UPDATE nodes SET parent_id = ?, updated_at = ? WHERE id = ?", (team_row["id"], _now(), row["id"]))
                    reparented += 1

            log_row = conn.execute("SELECT id, kind, parent_id FROM nodes WHERE slug = 'agent-log' LIMIT 1").fetchone()
            if log_row:
                if log_row["kind"] != "agent-log" or log_row["parent_id"] != index_id:
                    conn.execute("UPDATE nodes SET kind = 'agent-log', parent_id = ?, updated_at = ? WHERE id = ?", (index_id, _now(), log_row["id"]))
                    converted += 1

            if reparented or deleted or converted or renamed:
                self._record_event(conn, "flat_taxonomy_repaired", None, {"reparented": reparented, "deleted": deleted, "converted": converted, "renamed": renamed})
                self._set_meta(conn, "updated_at", _now())
        return {"reparented": reparented, "deleted": deleted, "converted": converted, "renamed": renamed}

    def repair_contains_edges(self) -> dict[str, int]:
        """Make structural `contains` edges match node parent_id values."""
        self.ensure_schema()
        inserted = 0
        removed = 0
        with self.connect() as conn:
            mismatched = conn.execute(
                """
                SELECT e.id
                FROM edges e
                JOIN nodes child ON child.id = e.to_node_id
                WHERE e.edge_type = 'contains'
                  AND (
                    child.parent_id IS NULL
                    OR child.parent_id != e.from_node_id
                  )
                """
            ).fetchall()
            for row in mismatched:
                conn.execute("DELETE FROM edges WHERE id = ?", (row["id"],))
                removed += 1

            rows = conn.execute(
                """
                SELECT id, parent_id
                FROM nodes
                WHERE parent_id IS NOT NULL
                """
            ).fetchall()
            for row in rows:
                existing = conn.execute(
                    """
                    SELECT 1 FROM edges
                    WHERE from_node_id = ?
                      AND to_node_id = ?
                      AND edge_type = 'contains'
                    """,
                    (row["parent_id"], row["id"]),
                ).fetchone()
                if existing:
                    continue
                conn.execute(
                    """
                    INSERT INTO edges(from_node_id, to_node_id, edge_type, weight, created_at)
                    VALUES(?, ?, 'contains', 1.0, ?)
                    """,
                    (row["parent_id"], row["id"], _now()),
                )
                inserted += 1

            if inserted or removed:
                self._record_event(conn, "taxonomy_repaired", None, {"contains_inserted": inserted, "contains_removed": removed})
                self._set_meta(conn, "updated_at", _now())
        return {"contains_inserted": inserted, "contains_removed": removed}

    def ensure_project_taxonomy(self, project_ref: str | int) -> dict[str, Any]:
        project = self.get_node(project_ref)
        if not project or project["kind"] != "project":
            raise ValueError("ensure_project_taxonomy requiere un nodo project")
        self.repair_contains_edges()
        return {"project": project, "containers": []}

    def ensure_topic_taxonomy(self, topic_ref: str | int) -> dict[str, Any]:
        topic = self.get_node(topic_ref)
        if not topic or topic["kind"] != "topic":
            raise ValueError("ensure_topic_taxonomy requiere un nodo topic")
        self.repair_contains_edges()
        return {"topic": topic, "containers": []}

    def link_nodes(
        self,
        from_ref: str | int,
        to_ref: str | int,
        edge_type: str,
        *,
        weight: float = 1.0,
    ) -> dict[str, Any]:
        if edge_type not in EDGE_TYPES:
            raise ValueError(f"edge_type inválido: {edge_type}")
        self.ensure_schema()
        with self.connect() as conn:
            from_id = self._resolve_node_id(conn, from_ref)
            to_id = self._resolve_node_id(conn, to_ref)
            if from_id is None or to_id is None:
                raise ValueError("No se pudo resolver alguno de los nodos")
            conn.execute(
                """
                INSERT INTO edges(from_node_id, to_node_id, edge_type, weight, created_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(from_node_id, to_node_id, edge_type)
                DO UPDATE SET weight=excluded.weight
                """,
                (from_id, to_id, edge_type, weight, _now()),
            )
            self._record_event(conn, "edge_linked", from_id, {"to": to_id, "edge_type": edge_type, "weight": weight})
            self._set_meta(conn, "updated_at", _now())
        return {"from": from_ref, "to": to_ref, "edge_type": edge_type, "weight": weight}

    def search_nodes(
        self,
        query: str,
        *,
        limit: int = 8,
        kinds: Optional[Iterable[str]] = None,
        include_index: bool = False,
    ) -> list[dict[str, Any]]:
        if not self.exists():
            return []
        limit = max(1, min(limit, 25))
        kind_filter = tuple(kind for kind in (kinds or []) if kind in NODE_KINDS)
        tokens = _tokenize_query(query)
        with self.connect() as conn:
            base_rows = self._fts_search(conn, tokens, limit * 4, kind_filter, include_index)
            if not base_rows:
                base_rows = self._fallback_search(conn, tokens or [query.lower()], limit * 4, kind_filter, include_index)
            if not base_rows:
                return []

            score_map: dict[int, float] = {}
            for row in base_rows:
                score_map[row["id"]] = max(score_map.get(row["id"], 0.0), float(row["score"]))

            for node_id, score in list(score_map.items()):
                neighbors = conn.execute(
                    """
                    SELECT CASE
                        WHEN from_node_id = ? THEN to_node_id
                        ELSE from_node_id
                    END AS node_id
                    FROM edges
                    WHERE from_node_id = ? OR to_node_id = ?
                    """,
                    (node_id, node_id, node_id),
                ).fetchall()
                for neighbor in neighbors:
                    score_map[neighbor["node_id"]] = max(score_map.get(neighbor["node_id"], 0.0), score * 0.35)

            ordered_ids = [node_id for node_id, _ in sorted(score_map.items(), key=lambda item: (-item[1], item[0]))]
            results = []
            for node_id in ordered_ids:
                row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
                if row is None:
                    continue
                node = self._row_to_node(conn, row)
                if not include_index and node["kind"] == "index":
                    continue
                if kind_filter and node["kind"] not in kind_filter:
                    continue
                node["score"] = round(score_map[node_id], 4)
                results.append(node)
                if len(results) >= limit:
                    break
            return results

    def prefetch(self, query: str, *, limit: int = 2, include_workspace_label: bool = False) -> str:
        nodes = self.search_nodes(query, limit=limit, include_index=False)
        if not nodes:
            nodes = self.search_nodes(query, limit=limit, include_index=True)
        parts = []
        for node in nodes[:limit]:
            label = f"[{self.workspace}/{node['filename']}]" if include_workspace_label else f"[{node['filename']}]"
            parts.append(f"{label}\n\n{self.render_node_markdown(node)}")
        return "\n\n---\n\n".join(parts)

    # -- Rendering / export ------------------------------------------------

    def render_node_markdown(self, node: dict[str, Any] | str | int) -> str:
        node_data = self.get_node(node) if not isinstance(node, dict) else node
        if not node_data:
            return ""
        body = (node_data.get("body") or "").strip()
        indicators = self._render_indicators(node_data["id"])
        parts = [f"# {node_data['title']}"]
        if body:
            parts.append(body)
        if indicators:
            parts.append(indicators)
        return "\n\n".join(parts).strip() + "\n"

    def export_markdown(self) -> dict[str, Any]:
        self.ensure_schema()
        context_dir = self.root / "context"
        context_dir.mkdir(parents=True, exist_ok=True)
        nodes = self.list_context_nodes()
        written: list[str] = []
        expected: set[str] = set()

        for node in nodes:
            filename = node["filename"] or self._default_filename(node)
            expected.add(filename)
            path = context_dir / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.render_node_markdown(node), encoding="utf-8")
            written.append(filename)

        removed: list[str] = []
        for md_file in sorted(context_dir.rglob("*.md")):
            rel_path = str(md_file.relative_to(context_dir))
            if any(part.startswith(".") for part in md_file.relative_to(context_dir).parts):
                continue
            if rel_path not in expected:
                md_file.unlink()
                removed.append(rel_path)

        for directory in sorted((path for path in context_dir.rglob("*") if path.is_dir()), reverse=True):
            if not any(directory.iterdir()):
                directory.rmdir()

        with self.connect() as conn:
            self._record_event(conn, "markdown_exported", None, {"written": written, "removed": removed})
            self._set_meta(conn, "last_export_at", _now())

        return {"written": written, "removed": removed}

    def organized_export_root(self, output_dir: Path | str | None = None) -> Path:
        if output_dir is None:
            return self.root / "docs" / "db-export"
        output_path = Path(output_dir)
        return output_path if output_path.is_absolute() else self.root / output_path

    def organized_export_mtime(self, output_dir: Path | str | None = None) -> float:
        root = self.organized_export_root(output_dir)
        if not root.exists():
            return 0.0
        mtimes = [path.stat().st_mtime for path in root.rglob("*.md") if path.is_file()]
        return max(mtimes) if mtimes else 0.0

    def organized_export_is_stale(self) -> bool:
        meta = self.meta()
        updated_at = meta.get("updated_at")
        last_export_at = meta.get("last_organized_export_at")
        if not last_export_at:
            return True
        if not updated_at:
            return False
        return updated_at > last_export_at

    def list_all_nodes(self) -> list[dict[str, Any]]:
        if not self.exists():
            return []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM nodes
                ORDER BY CASE kind
                    WHEN 'index' THEN 0
                    WHEN 'project' THEN 1
                    WHEN 'topic' THEN 2
                    WHEN 'important' THEN 3
                    WHEN 'doc' THEN 4
                    WHEN 'script' THEN 5
                    WHEN 'reference' THEN 6
                    WHEN 'agent-note' THEN 7
                    WHEN 'agent-plan' THEN 8
                    WHEN 'agent-log' THEN 9
                    WHEN 'agent-node' THEN 10
                    WHEN 'detail' THEN 11
                    ELSE 12
                END, lower(title), id
                """
            ).fetchall()
            return [self._row_to_node(conn, row) for row in rows]

    def list_edges(self) -> list[dict[str, Any]]:
        if not self.exists():
            return []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    e.id,
                    e.edge_type,
                    e.weight,
                    e.created_at,
                    e.from_node_id,
                    e.to_node_id,
                    nf.slug AS from_slug,
                    nf.title AS from_title,
                    nt.slug AS to_slug,
                    nt.title AS to_title
                FROM edges e
                JOIN nodes nf ON nf.id = e.from_node_id
                JOIN nodes nt ON nt.id = e.to_node_id
                ORDER BY lower(nf.title), e.edge_type, lower(nt.title), e.id
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def list_artifacts(self) -> list[dict[str, Any]]:
        if not self.exists():
            return []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    a.id,
                    a.node_id,
                    a.path,
                    a.artifact_type,
                    a.description,
                    a.mtime,
                    n.slug AS node_slug,
                    n.title AS node_title
                FROM artifacts a
                LEFT JOIN nodes n ON n.id = a.node_id
                ORDER BY a.artifact_type, a.path
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def list_events(self) -> list[dict[str, Any]]:
        if not self.exists():
            return []
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    e.id,
                    e.event_type,
                    e.payload,
                    e.created_at,
                    e.node_id,
                    n.slug AS node_slug,
                    n.title AS node_title
                FROM events e
                LEFT JOIN nodes n ON n.id = e.node_id
                ORDER BY e.created_at DESC, e.id DESC
                """
            ).fetchall()
            events: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                try:
                    item["payload_obj"] = json.loads(item["payload"] or "{}")
                except Exception:
                    item["payload_obj"] = {"raw": item["payload"]}
                events.append(item)
            return events

    # -- Agent coordination ------------------------------------------------

    def ensure_agent_coordination_nodes(self) -> dict[str, dict[str, Any]]:
        """Ensure the canonical coordination notes exist.

        These nodes are the DB-first equivalents of legacy `agents/team.md` and
        `agents/log.md`. They are linked from the index so agents and the UI can
        discover them without relying on filesystem Markdown.
        """
        self.ensure_schema()
        self.ensure_workspace_taxonomy()
        index_node = self.get_index_node()
        team = self.get_node("agent-team")
        if team is None:
            team = self.upsert_node(
                slug="agent-team",
                title=f"agents/team.md — {self.workspace}",
                kind="agent-note",
                summary="Roles, estado y reparto de trabajo entre agentes.",
                body=self._default_agent_team_body(),
                source_kind="agent-coordination",
                aliases=["agent-team", "agents-team", "team-md"],
                filename="agent-team.md",
            )
        elif team.get("kind") != "agent-note":
            team = self.upsert_node(
                slug="agent-team",
                title=team["title"],
                kind="agent-note",
                summary=team.get("summary", ""),
                body=team.get("body", ""),
                status=team.get("status", DEFAULT_NODE_STATUS),
                source_kind="agent-coordination",
                aliases=["agent-team", "agents-team", "team-md"],
                filename="agent-team.md",
            )
        log = self.get_node("agent-log")
        if log is None:
            log = self.upsert_node(
                slug="agent-log",
                title="Log de actividad entre IAs",
                kind="agent-log",
                summary="Registro cronológico de coordinación y actividad agentica.",
                body="# Log de actividad entre IAs\n",
                source_kind="agent-coordination",
                aliases=["agent-log", "agents-log", "log-md"],
                filename="agent-log.md",
            )
        elif log.get("kind") != "agent-log":
            log = self.upsert_node(
                slug="agent-log",
                title=log["title"],
                kind="agent-log",
                summary=log.get("summary", ""),
                body=log.get("body", ""),
                status=log.get("status", DEFAULT_NODE_STATUS),
                source_kind="agent-coordination",
                aliases=["agent-log", "agents-log", "log-md"],
                filename="agent-log.md",
            )
        if index_node:
            self._ensure_edge(index_node["id"], team["id"], "contains")
            self._ensure_edge(index_node["id"], log["id"], "contains")
        return {"team": self.get_node("agent-team") or team, "log": self.get_node("agent-log") or log}

    def sync_agent_coordination(self, *, max_events: int = 200) -> dict[str, Any]:
        """Regenerate managed agent-note/agent-log sections from the events table.

        The raw `events` table stays the timeline for realtime UIs. These nodes
        are the human-readable operational layer that agents can read quickly.
        """
        nodes = self.ensure_agent_coordination_nodes()
        # Pull more raw rows than we render because the documenter itself also
        # writes housekeeping events. Filtering first keeps the visible log
        # focused on useful coordination activity.
        raw_limit = max(1, max_events) * 5
        filtered_events = [
            event for event in self.list_events()[:raw_limit] if not self._is_agent_documenter_noise(event)
        ][: max(1, max_events)]
        events = list(reversed(filtered_events))
        active_tasks = self._active_agent_tasks(events)

        # Only the managed sections are rewritten. Manual role notes and legacy
        # history remain intact above/below the markers.
        team_body = _replace_managed_section(
            nodes["team"].get("body") or self._default_agent_team_body(),
            "agent-team-state",
            "Estado operativo automático",
            self._render_agent_team_state(events, active_tasks),
        )
        log_body = _replace_managed_section(
            nodes["log"].get("body") or "# Log de actividad entre IAs\n",
            "agent-log-events",
            "Registro automático desde events",
            self._render_agent_log_events(events),
        )

        changed = False
        team = nodes["team"]
        log = nodes["log"]
        if team_body != (nodes["team"].get("body") or "").strip():
            team = self.upsert_node(
                slug="agent-team",
                title=nodes["team"]["title"],
                kind="agent-note",
                summary="Roles, estado y reparto de trabajo entre agentes.",
                body=team_body,
                status=nodes["team"].get("status", DEFAULT_NODE_STATUS),
                source_kind="agent-documenter",
                aliases=["agent-team", "agents-team", "team-md"],
                filename="agent-team.md",
            )
            changed = True
        if log_body != (nodes["log"].get("body") or "").strip():
            log = self.upsert_node(
                slug="agent-log",
                title=nodes["log"]["title"],
                kind="agent-log",
                summary="Registro cronológico de coordinación y actividad agentica.",
                body=log_body,
                status=nodes["log"].get("status", DEFAULT_NODE_STATUS),
                source_kind="agent-documenter",
                aliases=["agent-log", "agents-log", "log-md"],
                filename="agent-log.md",
            )
            changed = True

        if changed:
            # Record a sync event only when the generated notes actually change;
            # this keeps watch mode from creating infinite no-op history.
            with self.connect() as conn:
                self._record_event(
                    conn,
                    "agent_docs_synced",
                    log["id"],
                    {
                        "events_considered": len(events),
                        "active_tasks": len(active_tasks),
                        "team_node": team["slug"],
                        "log_node": log["slug"],
                    },
                )
                self._set_meta(conn, "agent_docs_synced_at", _now())
                self._set_meta(conn, "updated_at", _now())

        return {
            "team_node": team["slug"],
            "log_node": log["slug"],
            "events_considered": len(events),
            "active_tasks": active_tasks,
            "changed": changed,
        }

    def record_agent_event(
        self,
        event_type: str,
        *,
        agent_id: str = "",
        task_id: str = "",
        summary: str = "",
        details: str = "",
        node_ref: str | int | None = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Record a structured coordination event for planners, workers or UI."""
        self.ensure_schema()
        payload = {
            "agent": agent_id,
            "task_id": task_id,
            "summary": summary,
            "details": details,
            "recorded_at": _now(),
        }
        if extra:
            payload.update(extra)
        with self.connect() as conn:
            node_id = self._resolve_node_id(conn, node_ref)
            event_id = self._record_event(conn, event_type, node_id, payload)
            self._set_meta(conn, "updated_at", _now())
        return {"event_id": event_id, "event_type": event_type, **payload}

    def agent_status(self, *, max_events: int = 100) -> dict[str, Any]:
        """Return the compact state used by the monitor and future web UI."""
        raw_limit = max(1, max_events) * 5
        recent_raw = self.list_events()[:raw_limit]
        coordination_events = list(
            reversed([event for event in recent_raw if not self._is_agent_documenter_noise(event)][: max(1, max_events)])
        )
        events = list(reversed(recent_raw[: max(1, max_events)]))
        return {
            "workspace": self.workspace,
            "active_tasks": self._active_agent_tasks(coordination_events),
            "recent_events": events[-20:],
            "agent_team": self.get_node("agent-team"),
            "agent_log": self.get_node("agent-log"),
        }

    def _default_agent_team_body(self) -> str:
        return """Roles asignados en este workspace. Define quién hace qué y cómo colaboran los agentes.

---

## Roles activos

| IA | Rol | Responsabilidad principal |
|----|-----|---------------------------|
| Hermes | Orquestador | Decide objetivos, valida planes, controla estado DB-first y reparte trabajo. |
| Planificadores | Arquitectura | Convierten objetivos en planes técnicos y tareas verificables. |
| Ejecutores | Implementación | Ejecutan tareas acotadas y reportan resultados mediante eventos. |
| Documentador | Memoria | Actualiza `agent-log`, `agent-team`, `agent-plan` y logs derivados de eventos. |

---

## Protocolo de traspaso entre agentes

1. Registrar inicio con `workspace_claim_task`.
2. Trabajar dentro del scope asignado.
3. Registrar cierre con `workspace_complete_task`.
4. Sincronizar documentación con `workspace_sync_agent_docs` o `scripts/agent-documenter.py`.
"""

    def _active_agent_tasks(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Derive open tasks from start/done event pairs."""
        starts: dict[int, dict[str, Any]] = {}
        completed: set[int] = set()
        for event in events:
            payload = event.get("payload_obj") or {}
            if event["event_type"] == "agent_task_start":
                starts[event["id"]] = {
                    "event_id": event["id"],
                    "agent": payload.get("agent", ""),
                    "task": payload.get("task", ""),
                    "started_at": payload.get("started_at", event.get("created_at", "")),
                }
            elif event["event_type"] == "agent_task_done":
                start_id = payload.get("start_event_id")
                if isinstance(start_id, int):
                    completed.add(start_id)
        return [task for event_id, task in sorted(starts.items()) if event_id not in completed]

    def _is_agent_documenter_noise(self, event: dict[str, Any]) -> bool:
        """Hide self-generated sync noise from human-facing coordination views."""
        if event["event_type"] == "agent_docs_synced":
            return True
        if event["event_type"] in {"node_created", "node_updated"}:
            payload = event.get("payload_obj") or {}
            return payload.get("slug") in {"agent-team", "agent-log"}
        return False

    def _render_agent_team_state(self, events: list[dict[str, Any]], active_tasks: list[dict[str, Any]]) -> str:
        last_event = events[-1] if events else None
        last_event_at = _utc_display(last_event["created_at"]) if last_event else "—"
        lines = [
            f"- Último evento considerado: `{last_event_at}`",
            f"- Eventos considerados: `{len(events)}`",
            f"- Tareas activas: `{len(active_tasks)}`",
            "",
            "| Agente | Tarea | Inicio | Evento |",
            "|---|---|---|---|",
        ]
        if active_tasks:
            for task in active_tasks:
                lines.append(
                    f"| {task.get('agent') or '—'} | {task.get('task') or '—'} | "
                    f"`{_utc_display(task.get('started_at', ''))}` | `{task.get('event_id')}` |"
                )
        else:
            lines.append("| — | Sin tareas activas registradas | — | — |")
        return "\n".join(lines)

    def _render_agent_log_events(self, events: list[dict[str, Any]]) -> str:
        if not events:
            return "_Sin eventos registrados todavía._"
        lines: list[str] = []
        for event in events:
            payload = event.get("payload_obj") or {}
            created = _utc_display(event.get("created_at", ""))
            if event["event_type"] == "agent_task_start":
                lines.append(
                    f"### {created} — {payload.get('agent', 'agente')} — tarea iniciada\n"
                    f"- Evento: `{event['id']}`\n"
                    f"- Tarea: {payload.get('task', '—')}"
                )
            elif event["event_type"] == "agent_task_done":
                lines.append(
                    f"### {created} — {payload.get('agent', 'agente')} — tarea completada\n"
                    f"- Evento: `{event['id']}`\n"
                    f"- Inicio: `{payload.get('start_event_id', '—')}`\n"
                    f"- Resultado: {payload.get('result', '—')}"
                )
            elif event["event_type"] in {"agent_docs_synced", "node_updated"}:
                continue
            else:
                summary = payload.get("summary") or payload.get("task") or payload.get("result") or event["event_type"]
                lines.append(
                    f"### {created} — {event['event_type']}\n"
                    f"- Evento: `{event['id']}`\n"
                    f"- Resumen: {summary}"
                )
        return "\n\n".join(lines).strip() or "_Sin eventos agenticos relevantes._"

    def export_organized_markdown(self, output_dir: Path | str | None = None) -> dict[str, Any]:
        self.ensure_schema()
        root = self.organized_export_root(output_dir)
        root.mkdir(parents=True, exist_ok=True)

        meta = self.meta()
        nodes = self.list_all_nodes()
        edges = self.list_edges()
        artifacts = self.list_artifacts()
        events = self.list_events()

        node_by_id = {node["id"]: node for node in nodes}
        outgoing: dict[int, list[dict[str, Any]]] = {}
        incoming: dict[int, list[dict[str, Any]]] = {}
        for edge in edges:
            outgoing.setdefault(edge["from_node_id"], []).append(edge)
            incoming.setdefault(edge["to_node_id"], []).append(edge)

        artifact_groups: dict[str, list[dict[str, Any]]] = {}
        for artifact in artifacts:
            artifact_groups.setdefault(artifact["artifact_type"], []).append(artifact)

        def _ts(value: float | int | str) -> str:
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(value, timezone.utc).isoformat()
            return str(value)

        files: dict[str, str] = {}

        overview_lines = [
            f"# DB Export — {self.workspace}",
            "",
            "Snapshot Markdown generado automáticamente desde `workspace.db`.",
            "",
            "## Resumen",
            "",
            f"- Workspace: `{self.workspace}`",
            f"- Source of truth: `{self.db_path}`",
            f"- Export generado en: `{root}`",
            f"- Schema version: `{meta.get('schema_version', 'desconocido')}`",
            f"- Updated at: `{meta.get('updated_at', 'desconocido')}`",
            f"- Último export de context/: `{meta.get('last_export_at', 'desconocido')}`",
            f"- Nodos: `{len(nodes)}`",
            f"- Relaciones: `{len(edges)}`",
            f"- Artefactos: `{len(artifacts)}`",
            f"- Eventos: `{len(events)}`",
            "",
            "## Navegación",
            "",
            "- Vista general de nodos: `01-nodes.md`",
            "- Relaciones: `02-relations.md`",
            "- Eventos: `03-events.md`",
            "- Artefactos: `artifacts/00-index.md`",
            "- Nodos detallados: `nodes/`",
            "",
            "## Notas",
            "",
            "- `context/` es una exportación compacta derivada, generada solo bajo demanda.",
            "- `docs/db-export/` es una vista organizada derivada, generada solo bajo demanda.",
        ]
        files["00-index.md"] = "\n".join(overview_lines).strip() + "\n"

        node_lines = [
            f"# Nodos — {self.workspace}",
            "",
            f"Total: **{len(nodes)}** nodos.",
            "",
            "| ID | Kind | Slug | Archivo | Título | Parent | Updated |",
            "|---|---|---|---|---|---|---|",
        ]
        for node in nodes:
            parent_slug = node_by_id.get(node["parent_id"], {}).get("slug", "—") if node["parent_id"] else "—"
            title_safe = node['title'].replace('|', r'\|')
            node_lines.append(
                f"| {node['id']} | `{node['kind']}` | `{node['slug']}` | `{node['filename']}` | "
                f"{title_safe} | `{parent_slug}` | `{node['updated_at']}` |"
            )
        files["01-nodes.md"] = "\n".join(node_lines).strip() + "\n"

        relation_lines = [
            f"# Relaciones — {self.workspace}",
            "",
            f"Total: **{len(edges)}** relaciones.",
            "",
            "| ID | From | Tipo | To | Peso | Created |",
            "|---|---|---|---|---|---|",
        ]
        for edge in edges:
            relation_lines.append(
                f"| {edge['id']} | `{edge['from_slug']}` | `{edge['edge_type']}` | `{edge['to_slug']}` | "
                f"{edge['weight']:.2f} | `{edge['created_at']}` |"
            )
        files["02-relations.md"] = "\n".join(relation_lines).strip() + "\n"

        event_lines = [
            f"# Eventos — {self.workspace}",
            "",
            f"Total: **{len(events)}** eventos.",
            "",
            "| ID | Tipo | Nodo | Created | Payload |",
            "|---|---|---|---|---|",
        ]
        for event in events:
            payload = json.dumps(event["payload_obj"], ensure_ascii=False, sort_keys=True)
            payload = payload.replace("|", "\\|")
            if len(payload) > 140:
                payload = payload[:137] + "..."
            node_ref = event["node_slug"] or "—"
            event_lines.append(
                f"| {event['id']} | `{event['event_type']}` | `{node_ref}` | `{event['created_at']}` | `{payload}` |"
            )
        files["03-events.md"] = "\n".join(event_lines).strip() + "\n"

        artifact_index_lines = [
            f"# Artefactos — {self.workspace}",
            "",
            f"Total: **{len(artifacts)}** artefactos.",
            "",
            "| Grupo | Cantidad | Archivo |",
            "|---|---|---|",
        ]
        for artifact_type, items in sorted(artifact_groups.items()):
            artifact_index_lines.append(
                f"| `{artifact_type}` | {len(items)} | `artifacts/{artifact_type}.md` |"
            )
        files["artifacts/00-index.md"] = "\n".join(artifact_index_lines).strip() + "\n"

        for artifact_type, items in sorted(artifact_groups.items()):
            artifact_lines = [
                f"# Artefactos `{artifact_type}` — {self.workspace}",
                "",
                f"Total: **{len(items)}** artefactos.",
                "",
                "| Path | Descripción | Nodo | Modified |",
                "|---|---|---|---|",
            ]
            for artifact in items:
                description = (artifact["description"] or "—").replace("|", "\\|")
                node_ref = artifact["node_slug"] or "—"
                artifact_lines.append(
                    f"| `{artifact['path']}` | {description} | `{node_ref}` | `{_ts(artifact['mtime'])}` |"
                )
            files[f"artifacts/{artifact_type}.md"] = "\n".join(artifact_lines).strip() + "\n"

        for node in nodes:
            aliases = ", ".join(f"`{alias}`" for alias in node["aliases"]) if node["aliases"] else "—"
            parent_slug = node_by_id.get(node["parent_id"], {}).get("slug", "—") if node["parent_id"] else "—"
            node_file_lines = [
                f"# {node['title']}",
                "",
                "## Metadata",
                "",
                f"- ID: `{node['id']}`",
                f"- Slug: `{node['slug']}`",
                f"- Kind: `{node['kind']}`",
                f"- Status: `{node['status']}`",
                f"- Filename: `{node['filename']}`",
                f"- Parent: `{parent_slug}`",
                f"- Source kind: `{node['source_kind']}`",
                f"- Created at: `{node['created_at']}`",
                f"- Updated at: `{node['updated_at']}`",
                f"- Aliases: {aliases}",
                "",
                "## Summary",
                "",
                node["summary"] or "_(sin summary)_",
                "",
                "## Body",
                "",
                node["body"] or "_(sin body)_",
                "",
                "## Relaciones salientes",
                "",
            ]
            out_edges = outgoing.get(node["id"], [])
            if out_edges:
                for edge in out_edges:
                    node_file_lines.append(
                        f"- `{edge['edge_type']}` → `{edge['to_slug']}` ({edge['to_title']}) [peso={edge['weight']:.2f}]"
                    )
            else:
                node_file_lines.append("- _(sin relaciones salientes)_")

            node_file_lines.extend(["", "## Relaciones entrantes", ""])
            in_edges = incoming.get(node["id"], [])
            if in_edges:
                for edge in in_edges:
                    node_file_lines.append(
                        f"- `{edge['edge_type']}` ← `{edge['from_slug']}` ({edge['from_title']}) [peso={edge['weight']:.2f}]"
                    )
            else:
                node_file_lines.append("- _(sin relaciones entrantes)_")

            node_artifacts = [artifact for artifact in artifacts if artifact.get("node_id") == node["id"]]
            node_file_lines.extend(["", "## Artefactos asociados", ""])
            if node_artifacts:
                for artifact in node_artifacts:
                    node_file_lines.append(f"- `{artifact['path']}`")
            else:
                node_file_lines.append("- _(sin artefactos asociados)_")

            node_file_lines.extend(["", "## Render Markdown", "", self.render_node_markdown(node).strip()])
            files[f"nodes/{node['filename']}"] = "\n".join(node_file_lines).strip() + "\n"

        written: list[str] = []
        expected = set(files.keys())
        for rel_path, content in files.items():
            path = root / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            written.append(rel_path)

        removed: list[str] = []
        for md_file in sorted(root.rglob("*.md")):
            rel_path = str(md_file.relative_to(root))
            if rel_path not in expected:
                md_file.unlink()
                removed.append(rel_path)

        for directory in sorted((path for path in root.rglob("*") if path.is_dir()), reverse=True):
            if not any(directory.iterdir()):
                directory.rmdir()

        with self.connect() as conn:
            self._record_event(conn, "organized_markdown_exported", None, {"written": written, "removed": removed})
            self._set_meta(conn, "last_organized_export_at", _now())

        return {"root": str(root), "written": written, "removed": removed}

    def sync_markdown_exports(self, output_dir: Path | str | None = None) -> dict[str, Any]:
        context_export = self.export_markdown()
        organized_export = self.export_organized_markdown(output_dir=output_dir)
        return {"context": context_export, "organized": organized_export}

    def _empty_export_result(self) -> dict[str, Any]:
        return {
            "context": {"written": [], "removed": []},
            "organized": {"root": str(self.organized_export_root()), "written": [], "removed": []},
        }

    def clean_exports(self) -> dict[str, Any]:
        """Remove derived Markdown exports. SQLite remains the source of truth."""
        self.ensure_schema()
        targets = [self.root / "context", self.root / "docs" / "db-export"]
        deleted: list[str] = []

        for target in targets:
            if not target.exists():
                continue
            if target.is_file():
                deleted.append(str(target.relative_to(self.root)))
                target.unlink()
                continue
            for path in sorted(target.rglob("*"), reverse=True):
                rel_path = str(path.relative_to(self.root))
                if path.is_file():
                    path.unlink()
                    deleted.append(rel_path)
                elif path.is_dir():
                    try:
                        path.rmdir()
                        deleted.append(rel_path + "/")
                    except OSError:
                        pass
            try:
                target.rmdir()
                deleted.append(str(target.relative_to(self.root)) + "/")
            except OSError:
                pass

        docs_dir = self.root / "docs"
        try:
            if docs_dir.exists() and not any(docs_dir.iterdir()):
                docs_dir.rmdir()
                deleted.append("docs/")
        except OSError:
            pass

        with self.connect() as conn:
            self._record_event(conn, "exports_cleaned", None, {"deleted": deleted})
            self._set_meta(conn, "updated_at", _now())
        return {"deleted": deleted}

    def verify_db_completeness(self) -> dict[str, Any]:
        """Lightweight safety check before deleting derived or legacy files."""
        if not self.exists():
            return {
                "verified": False,
                "node_count": 0,
                "missing": ["workspace.db"],
                "summary": "workspace.db no existe",
            }

        missing: list[str] = []
        self.ensure_schema()
        with self.connect() as conn:
            node_count = conn.execute("SELECT COUNT(*) AS count FROM nodes").fetchone()["count"]
            index_count = conn.execute("SELECT COUNT(*) AS count FROM nodes WHERE kind='index'").fetchone()["count"]
            artificial_count = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM nodes
                WHERE source_kind = 'taxonomy'
                   OR slug IN ('projects', 'topics', 'important', 'agent-notes', 'scripts', 'references', 'docs')
                   OR slug LIKE '%-topics'
                   OR slug LIKE '%-topic'
                   OR slug LIKE '%-docs'
                   OR slug LIKE '%-important'
                   OR slug LIKE '%-scripts'
                   OR slug LIKE '%-references'
                """
            ).fetchone()["count"]
            body_count = conn.execute(
                "SELECT COUNT(*) AS count FROM nodes WHERE length(trim(summary || body)) > 0"
            ).fetchone()["count"]

        if node_count == 0:
            missing.append("nodes")
        if index_count == 0:
            missing.append("index")
        if artificial_count:
            missing.append("flat_taxonomy")
        if body_count == 0:
            missing.append("documented_nodes")

        verified = not missing
        return {
            "verified": verified,
            "node_count": node_count,
            "missing": missing,
            "summary": "DB completa para limpieza" if verified else "DB incompleta para limpieza",
        }

    # -- Workspace bootstrap / migration ----------------------------------

    def _default_index_body(self, description: str, areas: Iterable[str] | None = None) -> str:
        areas = list(areas or [])
        lines = [
            "> Punto de entrada. Es el unico nodo que debe inyectarse al inicio de sesion.",
            "",
            "---",
            "",
            "## Que es este workspace",
            "",
            description.strip() or f"Workspace {self.workspace}.",
            "",
            "---",
            "",
            "## Estructura principal",
            "",
            "- Los hijos directos son nodos reales clasificados por kind.",
            "- `project`: areas de trabajo internas; actuan como indices locales.",
            "- `topic`: mapas de conocimiento; no contienen subtopics.",
            "- `important`: advertencias, errores conocidos y decisiones criticas.",
            "- `agent-note`: comportamiento, equipo y notas estables para agentes.",
            "- `agent-plan`: planes persistentes bajo `agent-team`.",
            "- `agent-log`: logs generales o logs hijos de un `agent-plan`.",
            "- `script`, `reference` y `doc`: automatizaciones, fuentes y documentacion desarrollada.",
        ]
        if areas:
            lines.extend(["", "---", "", "## Areas iniciales", ""])
            for area in areas:
                if ":" in area:
                    area_name, area_desc = area.split(":", 1)
                    lines.append(f"- **{area_name.strip()}**: {area_desc.strip()}")
                else:
                    lines.append(f"- **{area.strip()}**")
        return "\n".join(lines).strip()

    def seed_workspace(self, description: str, areas: Iterable[str]) -> dict[str, Any]:
        self.ensure_schema()
        areas = list(areas)

        index_node = self.upsert_node(
            slug="index",
            title=f"{_humanize_slug(self.workspace)} — Índice Base",
            kind="index",
            summary=description.strip() or f"Workspace {self.workspace}.",
            body=self._default_index_body(description, areas),
            source_kind="seed",
            filename="00-index.md",
            ensure_taxonomy=False,
        )
        self.ensure_workspace_taxonomy()

        for area in areas:
            area_name = area.split(":", 1)[0].strip()
            topic = self.upsert_node(
                slug=_slugify(area_name),
                title=f"{area_name} — Topic",
                kind="topic",
                summary=area.strip(),
                body=(
                    "> Mapa tematico. No se inyecta al inicio; se consulta bajo demanda.\n\n"
                    "---\n\n"
                    "## Guia\n\n"
                    "_Añade aqui el mapa del area y enlaza docs, important y references._"
                ),
                source_kind="seed",
                filename=f"{_slugify(area_name)}.md",
                parent_ref=index_node["id"],
            )
            self.link_nodes(index_node["id"], topic["id"], "contains")

        self.scan_artifacts()
        generated = [self.generate_workspace_doc(), self.generate_claude_md()]
        return {"index": index_node, "export": self._empty_export_result(), "generated": generated}

    def migrate_from_markdown(self, *, force: bool = False) -> dict[str, Any]:
        self.ensure_schema()
        with self.connect() as conn:
            node_count = conn.execute("SELECT COUNT(*) AS count FROM nodes").fetchone()["count"]
            if node_count and not force:
                return {"imported": False, "reason": "db-not-empty"}
            if force:
                conn.executescript(
                    """
                    DELETE FROM edges;
                    DELETE FROM aliases;
                    DELETE FROM artifacts;
                    DELETE FROM events;
                    DELETE FROM nodes;
                    DELETE FROM node_fts;
                    """
                )

        context_dir = self.root / "context"
        imported_nodes: list[dict[str, Any]] = []
        pending_edges: list[tuple[str, list[tuple[str, str]]]] = []

        if context_dir.exists():
            for md_file in sorted(context_dir.glob("*.md")):
                if md_file.name.startswith("."):
                    continue
                content = md_file.read_text(encoding="utf-8").strip()
                title_match = TITLE_RE.match(content.splitlines()[0]) if content else None
                title = title_match.group(1).strip() if title_match else _humanize_slug(md_file.stem)
                body, indicators = _strip_heading_and_indicators(content)
                kind = _infer_kind_from_filename(md_file.name)
                node = self.upsert_node(
                    slug=_slugify(md_file.stem),
                    title=title,
                    kind=kind,
                    summary=_first_meaningful_paragraph(body) or title,
                    body=body,
                    source_kind="markdown-import",
                    filename=md_file.name,
                )
                imported_nodes.append(node)
                pending_edges.append((node["slug"], indicators))

        if not imported_nodes:
            description = f"Workspace {self.workspace}."
            imported = self.seed_workspace(description, [])
            imported_nodes = [imported["index"]]
        else:
            self.ensure_workspace_taxonomy()

        index_node = self.get_index_node()

        for source_slug, indicators in pending_edges:
            for _, target_name in indicators:
                target_node = self.get_node(target_name)
                if target_node is None:
                    continue
                self.link_nodes(source_slug, target_node["id"], "contains")

        projects_dir = self.root / "projects"
        if projects_dir.exists():
            for project_dir in sorted(projects_dir.iterdir()):
                if not project_dir.is_dir() or project_dir.name.startswith("."):
                    continue
                info_path = project_dir / "info.md"
                summary = ""
                if info_path.exists():
                    summary = _first_meaningful_paragraph(info_path.read_text(encoding="utf-8"))
                project = self.upsert_node(
                    slug=_slugify(project_dir.name),
                    title=project_dir.name.replace("-", " ").replace("_", " ").title(),
                    kind="project",
                    summary=summary or f"Proyecto {project_dir.name}.",
                    body=summary or f"Proyecto {project_dir.name}.",
                    source_kind="project-import",
                    filename=f"{_slugify(project_dir.name)}.md",
                    parent_ref=index_node["id"] if index_node else None,
                )
                if index_node:
                    self.link_nodes(index_node["id"], project["id"], "contains")

        self.scan_artifacts()
        generated = [self.generate_workspace_doc(), self.generate_claude_md()]
        return {"imported": True, "nodes": len(imported_nodes), "export": self._empty_export_result(), "generated": generated}

    def migrate_legacy_to_db(
        self,
        *,
        backup_root: Path | str | None = None,
        archive: bool = True,
        remove_legacy: bool = True,
    ) -> dict[str, Any]:
        """Import legacy workspace files into SQLite, move real code under code/, and archive originals."""
        self.ensure_schema()
        index_node = self.get_index_node()
        if index_node is None:
            index_node = self.seed_workspace(f"Workspace {self.workspace}.", [])["index"]
        self.ensure_workspace_taxonomy()

        imported: list[dict[str, str]] = []
        moved: list[dict[str, str]] = []
        skipped: list[dict[str, str]] = []

        legacy_paths = [
            self.root / "README.md",
            self.root / "context",
            self.root / "agents",
            self.root / "docs",
            self.root / "projects",
            self.root / "scripts",
        ]
        existing_legacy = [path for path in legacy_paths if path.exists()]
        backup_path = self._archive_legacy_paths(existing_legacy, backup_root=backup_root) if archive and existing_legacy else None

        readme_path = self.root / "README.md"
        if readme_path.exists():
            node = self._import_markdown_node(readme_path, slug="readme", kind="doc", source_kind="legacy-readme")
            self.link_nodes(index_node["id"], node["id"], "contains")
            imported.append({"path": "README.md", "node": node["slug"], "kind": node["kind"]})

        context_dir = self.root / "context"
        if context_dir.exists():
            for md_file in sorted(context_dir.glob("*.md")):
                if md_file.name.startswith("."):
                    continue
                node = self._import_markdown_node(
                    md_file,
                    slug=_slugify(md_file.stem),
                    kind=_infer_kind_from_filename(md_file.name),
                    source_kind="legacy-context",
                    filename=md_file.name,
                )
                if node["kind"] != "index":
                    parent_ref = self._default_parent_ref_for_kind(node["kind"]) or index_node["id"]
                    self.link_nodes(parent_ref, node["id"], "contains")
                imported.append({"path": str(md_file.relative_to(self.root)), "node": node["slug"], "kind": node["kind"]})

        agents_dir = self.root / "agents"
        if agents_dir.exists():
            for md_file in sorted(agents_dir.rglob("*.md")):
                if md_file.name.startswith("."):
                    continue
                rel = md_file.relative_to(agents_dir)
                stem = _slugify(str(rel.with_suffix("")))
                agent_kind = "agent-log" if stem == "log" else "agent-note"
                node = self._import_markdown_node(
                    md_file,
                    slug=f"agent-{stem}",
                    kind=agent_kind,
                    source_kind="legacy-agents",
                )
                self.link_nodes(index_node["id"], node["id"], "contains")
                imported.append({"path": str(md_file.relative_to(self.root)), "node": node["slug"], "kind": node["kind"]})

        docs_dir = self.root / "docs"
        if docs_dir.exists():
            for md_file in sorted(docs_dir.rglob("*.md")):
                if md_file.name.startswith(".") or "db-export" in md_file.relative_to(docs_dir).parts:
                    continue
                rel = md_file.relative_to(docs_dir)
                kind = "reference" if "references" in rel.parts else "doc"
                node = self._import_markdown_node(
                    md_file,
                    slug=f"{kind}-{_slugify(str(rel.with_suffix('')))}",
                    kind=kind,
                    source_kind="legacy-docs",
                )
                self.link_nodes(index_node["id"], node["id"], "contains")
                imported.append({"path": str(md_file.relative_to(self.root)), "node": node["slug"], "kind": node["kind"]})

        projects_dir = self.root / "projects"
        if projects_dir.exists():
            for project_dir in sorted(projects_dir.iterdir()):
                if not project_dir.is_dir() or project_dir.name.startswith("."):
                    continue
                project_slug = _slugify(project_dir.name)
                info_path = next((p for p in [project_dir / "README.md", project_dir / "info.md", project_dir / "00-index.md"] if p.exists()), None)
                if info_path:
                    text = info_path.read_text(encoding="utf-8", errors="ignore").strip()
                    body, _ = _strip_heading_and_indicators(text)
                    summary = _first_meaningful_paragraph(body) or f"Proyecto {project_dir.name}."
                else:
                    body = f"Proyecto migrado desde `{project_dir.relative_to(self.root)}`."
                    summary = f"Proyecto {project_dir.name}."
                project = self.upsert_node(
                    slug=project_slug,
                    title=project_dir.name.replace("-", " ").replace("_", " ").title(),
                    kind="project",
                    summary=summary,
                    body=body,
                    source_kind="legacy-projects",
                    filename=f"{project_slug}.md",
                )
                self.link_nodes(index_node["id"], project["id"], "contains")
                imported.append({"path": str(project_dir.relative_to(self.root)), "node": project["slug"], "kind": "project"})

                for md_file in sorted(project_dir.rglob("*.md")):
                    if md_file.name.startswith(".") or md_file == info_path:
                        continue
                    rel = md_file.relative_to(project_dir)
                    node = self._import_markdown_node(
                        md_file,
                        slug=f"{project_slug}-{_slugify(str(rel.with_suffix('')))}",
                        kind="doc",
                        source_kind="legacy-projects",
                    )
                    self.link_nodes(project["id"], node["id"], "contains")
                    imported.append({"path": str(md_file.relative_to(self.root)), "node": node["slug"], "kind": node["kind"]})

                for path in sorted(project_dir.rglob("*")):
                    if not path.is_file() or path.name.startswith(".") or path.suffix == ".md":
                        continue
                    target = self.root / "code" / project_dir.name / path.relative_to(project_dir)
                    move_result = self._move_legacy_file(path, target)
                    (moved if move_result["status"] == "moved" else skipped).append(move_result)

        scripts_dir = self.root / "scripts"
        if scripts_dir.exists():
            for path in sorted(scripts_dir.rglob("*")):
                if not path.is_file() or path.name.startswith("."):
                    continue
                rel = path.relative_to(scripts_dir)
                if path.suffix == ".md":
                    node = self._import_markdown_node(
                        path,
                        slug=f"script-doc-{_slugify(str(rel.with_suffix('')))}",
                        kind="script",
                        source_kind="legacy-scripts",
                    )
                    self.link_nodes(index_node["id"], node["id"], "contains")
                    imported.append({"path": str(path.relative_to(self.root)), "node": node["slug"], "kind": node["kind"]})
                    continue
                target = self.root / "code" / "scripts" / rel
                move_result = self._move_legacy_file(path, target)
                (moved if move_result["status"] == "moved" else skipped).append(move_result)

        verification = self.verify_db_completeness()
        removed: list[str] = []
        if remove_legacy and verification["verified"]:
            for path in existing_legacy:
                if not path.exists():
                    continue
                rel_path = str(path.relative_to(self.root))
                if path.is_dir():
                    shutil.rmtree(path)
                    removed.append(rel_path + "/")
                else:
                    path.unlink()
                    removed.append(rel_path)

        self.scan_artifacts()
        generated = [self.generate_workspace_doc(), self.generate_claude_md()]
        result = {
            "workspace": self.workspace,
            "imported": imported,
            "moved": moved,
            "skipped": skipped,
            "removed": removed,
            "backup": str(backup_path) if backup_path else None,
            "verified": verification["verified"],
            "node_count": verification["node_count"],
            "missing": verification["missing"],
            "generated": generated,
        }
        with self.connect() as conn:
            event_type = "legacy_migration_done" if verification["verified"] else "legacy_migration_failed"
            self._record_event(conn, event_type, None, result)
            self._set_meta(conn, "updated_at", _now())
        return result

    def generate_workspace_doc(self) -> str:
        self.ensure_schema()
        path = self.root / "workspace-doc.md"
        content = f"""# workspace-doc — {self.workspace}

Prompt para que una IA documente exhaustivamente este workspace.

## Cuándo usar
Cuando se ha integrado código, creado proyectos, o añadido información
que aún no está reflejada en la base de conocimiento del workspace.

## Proceso

### 1. Estado actual — leer primero
- workspace_list_all_nodes() → entender qué ya está documentado
- workspace_scan_artifacts() → indexar todos los archivos en code/
- workspace_list_edges() → ver relaciones existentes

### 2. Analizar gaps
Comparar artefactos en code/ con nodos existentes.
Identificar archivos sin nodo asociado, nodos sin body y proyectos sin enlace al índice.
Antes de modificar un area, revisar el nodo `important` global o local si existe.

### 3. Documentar cada elemento
Para cada archivo/proyecto sin nodo:
- workspace_upsert_node(slug=..., title=..., kind="doc" o "script", summary="una línea", body="descripción completa en markdown")
- workspace_link_nodes(from=project_slug, to=new_node, edge_type="contains")

Para proyectos completos en code/{{proyecto}}/:
- Leer README o main file del proyecto
- Crear nodo kind="project" con descripción completa
- Colgar directamente sus nodos reales: topic, doc, important, script, reference
- Enlazar con `contains`: index → proyecto → nodos reales

### 4. Actualizar el índice
- workspace_get_node("index") → leer estado actual
- workspace_upsert_node(slug="index", body=body_actualizado)
- Mantener el índice breve: propósito del workspace y mención de sus hijos directos reales

### 5. Verificar
- workspace_list_all_nodes() → confirmar cobertura
- workspace_list_edges() → confirmar que el grafo tiene sentido

## Fuente de información
1. Archivos en code/ leídos directamente
2. Nodos existentes en workspace.db
3. Eventos recientes: workspace_list_events()
4. NUNCA usar context/ ni docs/db-export/ como fuente: son derivados obsoletos

## Formato de documentación
- summary: 1 línea, qué hace el elemento
- body: markdown con secciones — Descripción, Uso, Dependencias, Ejemplos
- Para scripts: incluir ejemplo de invocación
- Para proyectos: incluir stack, propósito, estado
"""
        path.write_text(content, encoding="utf-8")
        return str(path.relative_to(self.root))

    def generate_claude_md(self) -> str:
        self.ensure_schema()
        index_node = self.get_index_node()
        index_body = (index_node or {}).get("body") or "_(sin índice todavía)_"
        path = self.root / "CLAUDE.md"
        content = f"""# {self.workspace} — Workspace de Hermes

Fuente de verdad: `workspace.db` (SQLite). No uses ni edites context/ ni docs/ si existen.
Código y programas: `code/`

## Herramientas de base de datos

Para leer y escribir conocimiento en este workspace usa las herramientas workspace_*:
- workspace_search_nodes(query) — buscar nodos
- workspace_get_node(ref) — leer un nodo por slug/id
- workspace_upsert_node(...) — crear o actualizar nodo
- workspace_link_nodes(from, to, edge_type) — enlazar nodos
- workspace_ensure_structure() — reparar estructura plana y eliminar contenedores artificiales
- workspace_list_all_nodes() — ver todo el grafo
- workspace_scan_artifacts() — indexar archivos en code/
- workspace_list_events() — revisar coordinación reciente

## Skills relevantes

Lee estos skills antes de empezar:
- `workspace-daily` — flujo diario de trabajo con el workspace
- `context-engine` — documentación técnica completa del sistema DB
- `workspace-doc.md` — prompt para documentar integraciones

## Coordinación multi-agente

Antes de hacer cambios importantes:
1. Lee eventos recientes con workspace_list_events()
2. Si vas a modificar un área grande, usa workspace_claim_task(agent_id, description)
3. Haz una secuencia atómica: upsert del nodo, enlaces, actualización del índice
4. Si el área es sensible, revisa o actualiza el nodo `important` correspondiente
5. Al terminar, usa workspace_complete_task(event_id, agent_id, result)

Convenciones:
- Codex → implementación, features, lógica y operaciones DB
- Claude Code → refinamiento, calidad y UI
- Si hay conflicto en un nodo: el más reciente gana

## Índice del workspace

{index_body}
"""
        path.write_text(content, encoding="utf-8")
        return str(path.relative_to(self.root))

    def claim_task(self, agent_id: str, description: str) -> dict[str, Any]:
        self.ensure_schema()
        payload = {"agent": agent_id, "task": description, "started_at": _now()}
        with self.connect() as conn:
            event_id = self._record_event(conn, "agent_task_start", None, payload)
            self._set_meta(conn, "updated_at", _now())
        return {"event_id": event_id, **payload}

    def complete_task(self, event_id: int, agent_id: str, result: str) -> dict[str, Any]:
        self.ensure_schema()
        payload = {"agent": agent_id, "start_event_id": event_id, "result": result, "completed_at": _now()}
        with self.connect() as conn:
            done_id = self._record_event(conn, "agent_task_done", None, payload)
            self._set_meta(conn, "updated_at", _now())
        return {"event_id": done_id, **payload}

    def create_project(self, name: str, description: str = "") -> dict[str, Any]:
        self.ensure_workspace_layout()
        self.ensure_workspace_taxonomy()
        project_dir = self.root / "code" / name
        project_dir.mkdir(parents=True, exist_ok=True)

        project = self.upsert_node(
            slug=_slugify(name),
            title=name.replace("-", " ").replace("_", " ").title(),
            kind="project",
            summary=description or f"Proyecto {name}.",
            body=description or f"Proyecto {name}.",
            source_kind="project-create",
            filename=f"{_slugify(name)}.md",
            parent_ref=(self.get_index_node() or {}).get("id"),
        )
        index_node = self.get_index_node()
        if index_node:
            self.link_nodes(index_node["id"], project["id"], "contains")
        taxonomy = self.ensure_project_taxonomy(project["id"])

        self.scan_artifacts()
        return {"project": self.get_node(project["id"]) or project, "containers": taxonomy["containers"], "path": str(project_dir), "export": self._empty_export_result()}

    def scan_artifacts(self) -> dict[str, int]:
        self.ensure_schema()
        count = 0
        expected: set[str] = set()
        with self.connect() as conn:
            conn.execute("DELETE FROM artifacts WHERE path NOT LIKE 'code/%'")
            for folder in ("code",):
                root = self.root / folder
                if not root.exists():
                    continue
                for path in sorted(root.rglob("*")):
                    if not path.is_file() or path.name.startswith("."):
                        continue
                    rel_path = str(path.relative_to(self.root))
                    expected.add(rel_path)
                    description = ""
                    if path.suffix == ".md":
                        text = path.read_text(encoding="utf-8", errors="ignore").strip()
                        description = _first_meaningful_paragraph(text)
                    conn.execute(
                        """
                        INSERT INTO artifacts(node_id, path, artifact_type, description, mtime)
                        VALUES(NULL, ?, ?, ?, ?)
                        ON CONFLICT(path) DO UPDATE SET
                            artifact_type=excluded.artifact_type,
                            description=excluded.description,
                            mtime=excluded.mtime
                        """,
                        (rel_path, folder, description, path.stat().st_mtime),
                    )
                    count += 1
            if expected:
                placeholders = ",".join("?" for _ in expected)
                conn.execute(f"DELETE FROM artifacts WHERE path LIKE 'code/%' AND path NOT IN ({placeholders})", sorted(expected))
            else:
                conn.execute("DELETE FROM artifacts WHERE path LIKE 'code/%'")
            self._record_event(conn, "artifacts_scanned", None, {"count": count})
            self._set_meta(conn, "updated_at", _now())
        return {"artifacts": count}

    # -- Audit -------------------------------------------------------------

    def audit(self) -> dict[str, Any]:
        issues: list[WorkspaceIssue] = []
        stats = {"nodes": 0, "edges": 0, "artifacts": 0}
        if not self.exists():
            issues.append(WorkspaceIssue("critical", "workspace.db no existe"))
            return {"issues": issues, "stats": stats}

        meta = self.meta()
        if meta.get("schema_version") != str(SCHEMA_VERSION):
            issues.append(WorkspaceIssue("critical", f"schema_version inesperado: {meta.get('schema_version') or 'sin valor'}"))

        with self.connect() as conn:
            node_count = conn.execute("SELECT COUNT(*) AS count FROM nodes").fetchone()["count"]
            edge_count = conn.execute("SELECT COUNT(*) AS count FROM edges").fetchone()["count"]
            artifact_count = conn.execute("SELECT COUNT(*) AS count FROM artifacts").fetchone()["count"]
            stats.update({"nodes": node_count, "edges": edge_count, "artifacts": artifact_count})

            index_count = conn.execute("SELECT COUNT(*) AS count FROM nodes WHERE kind='index'").fetchone()["count"]
            if index_count == 0:
                issues.append(WorkspaceIssue("critical", "Falta nodo raíz de tipo index"))
            elif index_count > 1:
                issues.append(WorkspaceIssue("broken", "Hay más de un nodo raíz de tipo index"))

            detail_count = conn.execute("SELECT COUNT(*) AS count FROM nodes WHERE kind='detail'").fetchone()["count"]
            if detail_count:
                issues.append(WorkspaceIssue("warning", f"Hay {detail_count} nodo(s) legacy kind=detail; no crear nuevos"))

            agent_node_count = conn.execute("SELECT COUNT(*) AS count FROM nodes WHERE kind='agent-node'").fetchone()["count"]
            if agent_node_count:
                issues.append(WorkspaceIssue("broken", f"Hay {agent_node_count} nodo(s) legacy kind=agent-node; usar agent-note/agent-plan/agent-log"))

            bad_agent_notes = conn.execute(
                "SELECT slug FROM nodes WHERE kind='agent-note' AND slug NOT IN ('agent-behavior', 'agent-team') ORDER BY slug"
            ).fetchall()
            for row in bad_agent_notes:
                issues.append(WorkspaceIssue("broken", f"agent-note reservado mal usado: {row['slug']}"))

            invalid_kind_rows = conn.execute(
                f"SELECT slug, kind FROM nodes WHERE kind NOT IN ({','.join('?' for _ in NODE_KINDS)})",
                sorted(NODE_KINDS),
            ).fetchall()
            for row in invalid_kind_rows:
                issues.append(WorkspaceIssue("broken", f"Kind inválido en nodo {row['slug']}: {row['kind']}"))

            artificial_rows = conn.execute(
                """
                SELECT slug FROM nodes
                WHERE source_kind = 'taxonomy'
                   OR slug IN ('projects', 'topics', 'important', 'agent-notes', 'scripts', 'references', 'docs')
                   OR slug LIKE '%-topics'
                   OR slug LIKE '%-topic'
                   OR slug LIKE '%-docs'
                   OR slug LIKE '%-important'
                   OR slug LIKE '%-scripts'
                   OR slug LIKE '%-references'
                ORDER BY slug
                """
            ).fetchall()
            for row in artificial_rows:
                issues.append(WorkspaceIssue("broken", f"Contenedor artificial no permitido: {row['slug']}"))

            prefixed_projects = conn.execute(
                "SELECT slug FROM nodes WHERE kind = 'project' AND slug LIKE 'project-%' ORDER BY slug"
            ).fetchall()
            for row in prefixed_projects:
                issues.append(WorkspaceIssue("broken", f"Slug de proyecto redundante: {row['slug']}"))

            nested_topics = conn.execute(
                """
                SELECT child.slug AS child_slug, parent.slug AS parent_slug
                FROM nodes child
                JOIN nodes parent ON parent.id = child.parent_id
                WHERE child.kind = 'topic'
                  AND parent.kind = 'topic'
                """
            ).fetchall()
            for row in nested_topics:
                issues.append(WorkspaceIssue("broken", f"Subtopic no permitido: {row['child_slug']} dentro de {row['parent_slug']}"))

            empty_topics = conn.execute(
                """
                SELECT t.slug
                FROM nodes t
                LEFT JOIN nodes child ON child.parent_id = t.id
                WHERE t.kind = 'topic'
                GROUP BY t.id
                HAVING COUNT(child.id) = 0
                ORDER BY t.slug
                """
            ).fetchall()
            for row in empty_topics:
                issues.append(WorkspaceIssue("broken", f"Topic sin hijos: {row['slug']}"))

            orphan_rows = conn.execute(
                """
                SELECT slug FROM nodes
                WHERE parent_id IS NOT NULL
                  AND parent_id NOT IN (SELECT id FROM nodes)
                """
            ).fetchall()
            for row in orphan_rows:
                issues.append(WorkspaceIssue("broken", f"Nodo huérfano: {row['slug']}"))

            broken_edges = conn.execute(
                """
                SELECT e.id AS edge_id, e.edge_type, n1.slug AS from_slug, n2.slug AS to_slug
                FROM edges e
                LEFT JOIN nodes n1 ON n1.id = e.from_node_id
                LEFT JOIN nodes n2 ON n2.id = e.to_node_id
                WHERE n1.id IS NULL OR n2.id IS NULL
                """
            ).fetchall()
            for row in broken_edges:
                issues.append(WorkspaceIssue("broken", f"Relación rota #{row['edge_id']} ({row['edge_type']})"))

            missing_contains = conn.execute(
                """
                SELECT child.slug AS child_slug, parent.slug AS parent_slug
                FROM nodes child
                JOIN nodes parent ON parent.id = child.parent_id
                LEFT JOIN edges e
                  ON e.from_node_id = child.parent_id
                 AND e.to_node_id = child.id
                 AND e.edge_type = 'contains'
                WHERE child.parent_id IS NOT NULL
                  AND e.id IS NULL
                ORDER BY parent.slug, child.slug
                """
            ).fetchall()
            for row in missing_contains:
                issues.append(WorkspaceIssue("broken", f"Falta contains: {row['parent_slug']} -> {row['child_slug']}"))

            mismatched_contains = conn.execute(
                """
                SELECT parent.slug AS parent_slug, child.slug AS child_slug, actual.slug AS actual_parent_slug
                FROM edges e
                JOIN nodes parent ON parent.id = e.from_node_id
                JOIN nodes child ON child.id = e.to_node_id
                LEFT JOIN nodes actual ON actual.id = child.parent_id
                WHERE e.edge_type = 'contains'
                  AND (
                    child.parent_id IS NULL
                    OR child.parent_id != e.from_node_id
                  )
                ORDER BY parent.slug, child.slug
                """
            ).fetchall()
            for row in mismatched_contains:
                expected = row["actual_parent_slug"] or "sin parent_id"
                issues.append(WorkspaceIssue("broken", f"Contains contradice parent_id: {row['parent_slug']} -> {row['child_slug']} (parent real: {expected})"))

        return {"issues": issues, "stats": stats}

    # -- Internal helpers --------------------------------------------------

    def _row_to_node(self, conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        filename = self._get_filename_alias(conn, row["id"]) or self._default_filename(dict(row))
        aliases = [
            alias["alias"]
            for alias in conn.execute("SELECT alias FROM aliases WHERE node_id = ? ORDER BY alias", (row["id"],)).fetchall()
            if alias["alias"] != filename
        ]
        return {
            "id": row["id"],
            "slug": row["slug"],
            "title": row["title"],
            "kind": row["kind"],
            "summary": row["summary"],
            "body": row["body"],
            "status": row["status"],
            "parent_id": row["parent_id"],
            "source_kind": row["source_kind"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "filename": filename,
            "aliases": aliases,
            "is_container": self._is_container_row(row),
        }

    def _import_markdown_node(
        self,
        path: Path,
        *,
        slug: str,
        kind: str,
        source_kind: str,
        filename: str | None = None,
    ) -> dict[str, Any]:
        content = path.read_text(encoding="utf-8", errors="ignore").strip()
        title_match = TITLE_RE.match(content.splitlines()[0]) if content else None
        title = title_match.group(1).strip() if title_match else _humanize_slug(Path(slug).stem)
        body, _ = _strip_heading_and_indicators(content)
        return self.upsert_node(
            slug=slug,
            title=title,
            kind=kind,
            summary=_first_meaningful_paragraph(body) or title,
            body=body,
            source_kind=source_kind,
            filename=filename,
        )

    def _archive_legacy_paths(self, paths: list[Path], *, backup_root: Path | str | None = None) -> Path:
        if backup_root is None:
            hermes_root = self.root.parent.parent if self.root.parent.name == "workspaces" else self.root.parent
            backup_dir = hermes_root / "backups" / "legacy-workspaces"
        else:
            backup_dir = Path(backup_root)
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive_path = backup_dir / f"{self.workspace}-{stamp}.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            for path in paths:
                if path.exists():
                    tar.add(path, arcname=path.name)
        return archive_path

    def _move_legacy_file(self, source: Path, target: Path) -> dict[str, str]:
        rel_source = str(source.relative_to(self.root))
        rel_target = str(target.relative_to(self.root))
        if target.exists():
            return {"status": "skipped", "source": rel_source, "target": rel_target, "reason": "target-exists"}
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        return {"status": "moved", "source": rel_source, "target": rel_target}

    def _default_filename(self, node: dict[str, Any]) -> str:
        if node["kind"] == "index":
            return "00-index.md"
        return f"{node['slug']}.md"

    def _get_filename_alias(self, conn: sqlite3.Connection, node_id: int) -> Optional[str]:
        row = conn.execute(
            "SELECT alias FROM aliases WHERE node_id = ? AND alias_kind = 'filename' LIMIT 1",
            (node_id,),
        ).fetchone()
        return row["alias"] if row else None

    def _set_filename_alias(self, conn: sqlite3.Connection, node_id: int, filename: str) -> None:
        filename = filename.strip()
        conn.execute("DELETE FROM aliases WHERE node_id = ? AND alias_kind = 'filename'", (node_id,))
        conn.execute(
            """
            INSERT INTO aliases(node_id, alias, alias_kind)
            VALUES(?, ?, 'filename')
            ON CONFLICT(alias) DO UPDATE SET node_id=excluded.node_id, alias_kind='filename'
            """,
            (node_id, filename),
        )

    def _ensure_edge(self, from_ref: str | int, to_ref: str | int, edge_type: str, *, weight: float = 1.0) -> None:
        if edge_type not in EDGE_TYPES:
            raise ValueError(f"edge_type inválido: {edge_type}")
        with self.connect() as conn:
            from_id = self._resolve_node_id(conn, from_ref)
            to_id = self._resolve_node_id(conn, to_ref)
            if from_id is None or to_id is None:
                return
            existing = conn.execute(
                """
                SELECT id FROM edges
                WHERE from_node_id = ? AND to_node_id = ? AND edge_type = ?
                """,
                (from_id, to_id, edge_type),
            ).fetchone()
            if existing:
                return
            conn.execute(
                """
                INSERT INTO edges(from_node_id, to_node_id, edge_type, weight, created_at)
                VALUES(?, ?, ?, ?, ?)
                """,
                (from_id, to_id, edge_type, weight, _now()),
            )
            self._record_event(conn, "edge_linked", from_id, {"to": to_id, "edge_type": edge_type, "weight": weight})
            self._set_meta(conn, "updated_at", _now())

    def _resolve_node_id(self, conn: sqlite3.Connection, ref: str | int | None) -> Optional[int]:
        if ref is None:
            return None
        if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
            row = conn.execute("SELECT id FROM nodes WHERE id = ?", (int(ref),)).fetchone()
            return row["id"] if row else None
        row = conn.execute("SELECT id FROM nodes WHERE slug = ?", (_slugify(str(ref)),)).fetchone()
        if row:
            return row["id"]
        row = conn.execute("SELECT node_id AS id FROM aliases WHERE alias = ?", (str(ref),)).fetchone()
        return row["id"] if row else None

    def _record_event(self, conn: sqlite3.Connection, event_type: str, node_id: Optional[int], payload: dict[str, Any]) -> int:
        cursor = conn.execute(
            """
            INSERT INTO events(event_type, node_id, payload, created_at)
            VALUES(?, ?, ?, ?)
            """,
            (event_type, node_id, json.dumps(payload, ensure_ascii=True), _now()),
        )
        return int(cursor.lastrowid)

    def _sync_fts(self, conn: sqlite3.Connection, node_id: int) -> None:
        row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if row is None:
            conn.execute("DELETE FROM node_fts WHERE rowid = ?", (node_id,))
            return
        aliases = " ".join(
            alias["alias"]
            for alias in conn.execute("SELECT alias FROM aliases WHERE node_id = ?", (node_id,)).fetchall()
        )
        conn.execute("DELETE FROM node_fts WHERE rowid = ?", (node_id,))
        conn.execute(
            """
            INSERT INTO node_fts(rowid, title, slug, summary, body, aliases)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (node_id, row["title"], row["slug"], row["summary"], row["body"], aliases),
        )

    def _fts_search(
        self,
        conn: sqlite3.Connection,
        tokens: list[str],
        limit: int,
        kinds: tuple[str, ...],
        include_index: bool,
    ) -> list[dict[str, Any]]:
        if not tokens:
            return []
        match_query = " AND ".join(f'"{token}"' for token in tokens)
        where = ["n.status = 'active'"]
        params: list[Any] = [match_query]
        if kinds:
            where.append(f"n.kind IN ({','.join('?' for _ in kinds)})")
            params.extend(kinds)
        if not include_index:
            where.append("n.kind != 'index'")
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT n.id, MAX(0.1, -bm25(node_fts)) AS score
            FROM node_fts
            JOIN nodes n ON n.id = node_fts.rowid
            WHERE node_fts MATCH ?
              AND {' AND '.join(where)}
            ORDER BY score DESC, n.id ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def _fallback_search(
        self,
        conn: sqlite3.Connection,
        terms: list[str],
        limit: int,
        kinds: tuple[str, ...],
        include_index: bool,
    ) -> list[dict[str, Any]]:
        like_clauses = []
        params: list[Any] = []
        for term in terms:
            like = f"%{term}%"
            like_clauses.append("(lower(title) LIKE ? OR lower(summary) LIKE ? OR lower(body) LIKE ?)")
            params.extend([like, like, like])
        where = ["status = 'active'"]
        if kinds:
            where.append(f"kind IN ({','.join('?' for _ in kinds)})")
            params.extend(kinds)
        if not include_index:
            where.append("kind != 'index'")
        rows = conn.execute(
            f"""
            SELECT id
            FROM nodes
            WHERE {' AND '.join(where)}
              AND ({' OR '.join(like_clauses)})
            ORDER BY lower(title), id
            LIMIT ?
            """,
            params + [limit],
        ).fetchall()
        results = []
        for rank, row in enumerate(rows):
            results.append({"id": row["id"], "score": max(0.1, 1.0 - rank * 0.05)})
        return results

    def _render_indicators(self, node_id: int) -> str:
        if not self.exists():
            return ""
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT e.edge_type, n.*
                FROM edges e
                JOIN nodes n ON n.id = e.to_node_id
                WHERE e.from_node_id = ?
                ORDER BY CASE e.edge_type
                    WHEN 'contains' THEN 0
                    WHEN 'references' THEN 1
                    WHEN 'depends_on' THEN 2
                    WHEN 'related_to' THEN 3
                    WHEN 'details' THEN 4
                    WHEN 'project_of' THEN 5
                    ELSE 6
                END, lower(n.title), n.id
                """,
                (node_id,),
            ).fetchall()
            lines = []
            for row in rows:
                node = self._row_to_node(conn, row)
                filename = node["filename"]
                if not filename:
                    continue
                prefix = "→"
                lines.append(f"{prefix} {node['title']}: `{filename}`")
            return "\n".join(lines)


def list_workspaces(hermes_home: Path | str) -> list[Path]:
    ws_root = Path(hermes_home) / "workspaces"
    if not ws_root.exists():
        return []
    return sorted(path for path in ws_root.iterdir() if path.is_dir() and not path.name.startswith("."))
