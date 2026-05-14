# WorkspaceStore Data Layer

**Module:** `workspace_store`
**File:** `/Users/servidor-jmp/.hermes/workspace_store/__init__.py`
**Schema Version:** 1
**Total Lines:** 1727

The `WorkspaceStore` class is the central data layer for the Hermes Context Engine. It manages a SQLite database that serves as the single source of truth for workspace knowledge, replacing legacy markdown-based documentation systems. All node content, relationships, artifacts, and events are persisted in SQLite with FTS5 full-text search support.

---

## Table of Contents

1. [Schema (SQLite Tables)](#1-schema-sqlite-tables)
2. [Node Kinds](#2-node-kinds)
3. [Edge Types](#3-edge-types)
4. [Key Python API](#4-key-python-api)
5. [Internal Helpers](#5-internal-helpers)
6. [FTS5 Configuration](#6-fts5-configuration)
7. [Migration from Markdown](#7-migration-from-markdown)
8. [Export System](#8-export-system)

---

## 1. Schema (SQLite Tables)

The schema is created lazily by `ensure_schema()`. SQLite with `PRAGMA foreign_keys = ON` is used; all foreign keys use `ON DELETE SET NULL` to prevent cascade deletions of parent nodes.

### `workspace_meta`

Key-value store for workspace-level metadata.

```sql
CREATE TABLE IF NOT EXISTS workspace_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

| Column | Type | Purpose |
|--------|------|---------|
| `key` | TEXT PRIMARY KEY | Metadata key name |
| `value` | TEXT NOT NULL | Metadata value |

**Standard keys:** `schema_version`, `workspace_name`, `updated_at`, `last_export_at`, `last_organized_export_at`.

---

### `nodes`

Core content table. Every piece of knowledge is a node.

```sql
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
```

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PRIMARY KEY | Auto-incrementing node ID |
| `slug` | TEXT NOT NULL UNIQUE | URL-safe identifier, unique across workspace |
| `title` | TEXT NOT NULL | Human-readable title |
| `kind` | TEXT NOT NULL | Node type (see Node Kinds section) |
| `summary` | TEXT DEFAULT '' | One-line description |
| `body` | TEXT DEFAULT '' | Full markdown content |
| `status` | TEXT DEFAULT 'active' | Node lifecycle state |
| `parent_id` | INTEGER | Optional parent node reference |
| `source_kind` | TEXT DEFAULT 'manual' | Origin of the node (see Migration section) |
| `created_at` | TEXT (ISO8601) | Creation timestamp in UTC |
| `updated_at` | TEXT (ISO8601) | Last modification timestamp in UTC |

---

### `edges`

Directed weighted relationships between nodes. Forms the knowledge graph.

```sql
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
```

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PRIMARY KEY | Auto-incrementing edge ID |
| `from_node_id` | INTEGER NOT NULL | Source node |
| `to_node_id` | INTEGER NOT NULL | Target node |
| `edge_type` | TEXT NOT NULL | Relationship type (see Edge Types section) |
| `weight` | REAL DEFAULT 1.0 | Relationship strength for ranking |
| `created_at` | TEXT (ISO8601) | Creation timestamp in UTC |

**Constraint:** `UNIQUE(from_node_id, to_node_id, edge_type)` means only one edge of each type can exist between any two nodes. Upsert behavior updates the weight on conflict.

---

### `aliases`

Flexible lookup table. Each node can have multiple aliases, including a special filename alias.

```sql
CREATE TABLE IF NOT EXISTS aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL,
    alias TEXT NOT NULL UNIQUE,
    alias_kind TEXT NOT NULL DEFAULT 'general',
    FOREIGN KEY(node_id) REFERENCES nodes(id) ON DELETE CASCADE
);
```

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PRIMARY KEY | Auto-incrementing alias ID |
| `node_id` | INTEGER NOT NULL | Referenced node |
| `alias` | TEXT NOT NULL UNIQUE | Alias string |
| `alias_kind` | TEXT DEFAULT 'general' | `'general'` for normal aliases, `'filename'` for filename mapping |

**Filename aliases** are used so a node can be retrieved by its exported markdown filename (e.g., `00-index.md`). **General aliases** are alternative slugs for searching.

---

### `artifacts`

Tracks files in the `code/` directory linked to nodes.

```sql
CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER,
    path TEXT NOT NULL UNIQUE,
    artifact_type TEXT NOT NULL DEFAULT 'file',
    description TEXT NOT NULL DEFAULT '',
    mtime REAL NOT NULL DEFAULT 0,
    FOREIGN KEY(node_id) REFERENCES nodes(id) ON DELETE SET NULL
);
```

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PRIMARY KEY | Auto-incrementing artifact ID |
| `node_id` | INTEGER | Optional linked node |
| `path` | TEXT NOT NULL UNIQUE | Path relative to workspace root |
| `artifact_type` | TEXT DEFAULT 'file' | Category (always `'file'` currently) |
| `description` | TEXT DEFAULT '' | First meaningful paragraph from markdown files |
| `mtime` | REAL | File modification timestamp |

---

### `events`

Append-only audit log for workspace actions, agent coordination, and migrations.

```sql
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    node_id INTEGER,
    payload TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(node_id) REFERENCES nodes(id) ON DELETE SET NULL
);
```

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PRIMARY KEY | Auto-incrementing event ID |
| `event_type` | TEXT NOT NULL | Event category (e.g., `node_created`, `edge_linked`, `agent_task_start`) |
| `node_id` | INTEGER | Optional related node |
| `payload` | TEXT (JSON) | Event data as JSON string |
| `created_at` | TEXT (ISO8601) | Event timestamp in UTC |

**Standard event types:** `node_created`, `node_updated`, `edge_linked`, `artifacts_scanned`, `markdown_exported`, `organized_markdown_exported`, `exports_cleaned`, `agent_task_start`, `agent_task_done`, `legacy_migration_done`, `legacy_migration_failed`.

---

### `node_fts` (FTS5 Virtual Table)

Full-text search index for fast natural language queries.

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS node_fts
USING fts5(title, slug, summary, body, aliases, tokenize='unicode61 remove_diacritics 2')
```

**Indexed columns:** `title`, `slug`, `summary`, `body`, `aliases`

**Tokenizer:** `unicode61 remove_diacritics 2`
- `unicode61` — Unicode-aware tokenization
- `remove_diacritics` — Strips accent marks (e -> e, n -> n)
- `2` — Minimum token length of 2 characters

The FTS table is kept synchronized with `nodes` via `_sync_fts()` which runs after every upsert. The table uses `rowid` as the node ID for efficient joins.

---

## 2. Node Kinds

**Valid `kind` values** (defined by `NODE_KINDS` constant):

| Kind | Meaning | Slug Pattern | Filename Convention |
|------|---------|--------------|---------------------|
| `index` | Root entry point — always read first | `index` | `00-index.md` |
| `topic` | Thematic grouping of details | `\d{2}-...` | `NN-name.md` |
| `detail` | Atomic piece of knowledge | slugified title | `NN[a-z]-slug.md` or `slug.md` |
| `project` | Code project or application | `project-{name}` | `project-{name}.md` |
| `doc` | General documentation | slugified | `slug.md` |
| `agent-note` | Notes created by agents | `agent-{slug}` | `agent-{slug}.md` |
| `script` | Script or automation | `script-doc-{name}` | derived from path |
| `reference` | Reference material | `{kind}-{slug}` | derived |

**Filename inference rules** (`_infer_kind_from_filename`):

```
if name == "00-index.md"           → "index"
if stem matches r"^\d{2}[a-z]-"   → "detail"
if stem matches r"^\d{2}-"         → "topic"
if stem.startswith("project-")    → "project"
otherwise                          → "detail"
```

**Exported kinds** (written to `context/`): `{"index", "topic", "detail", "project"}` — these are the primary navigation kinds.

---

## 3. Edge Types

**Valid `edge_type` values** (defined by `EDGE_TYPES` constant):

| Edge Type | Meaning | Typical Direction |
|-----------|---------|-------------------|
| `contains` | Node A contains Node B as a part | index/project -> doc/script |
| `details` | Node A provides details about Node B | index/topic -> detail |
| `related_to` | Nodes are loosely associated | any -> any |
| `project_of` | Node A is the project for Node B | index -> project |
| `depends_on` | Node A depends on Node B | doc -> reference |
| `references` | Node A references Node B | doc -> reference |

Edges are **directed** (`from_node_id` -> `to_node_id`). The `_render_indicators()` method renders outgoing edges with the `→` prefix in markdown exports.

---

## 4. Key Python API

### `ensure_schema()`

```python
def ensure_schema(self) -> None:
```

Creates the workspace directory layout, initializes the SQLite database, and creates all tables if they do not exist. Called implicitly by most other methods. Safe to call multiple times — uses `CREATE TABLE IF NOT EXISTS`.

**Side effects:**
- Creates `code/` and `code/scripts/` directories via `ensure_workspace_layout()`
- Sets `schema_version`, `workspace_name`, and `updated_at` metadata keys on first run

---

### `upsert_node()`

```python
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
) -> dict[str, Any]:
```

Creates a new node or updates an existing one by `slug`. All string fields are slugified or normalized appropriately.

**Parameters:**

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `slug` | str | required | URL-safe identifier, slugified via `_slugify()` |
| `title` | str | required | Human-readable title |
| `kind` | str | required | Node kind (validated against `NODE_KINDS`) |
| `summary` | str | `""` | One-line description |
| `body` | str | `""` | Full markdown content |
| `status` | str | `"active"` | Lifecycle state |
| `parent_ref` | str \| int \| None | `None` | Parent node reference (resolved via `_resolve_node_id`) |
| `source_kind` | str | `"manual"` | How the node was created |
| `aliases` | Iterable[str] \| None | `None` | Additional lookup aliases |
| `filename` | str \| None | `None` | Override the default filename alias |

**Returns:** The created/updated node as a dict including `id`, `slug`, `title`, `kind`, `summary`, `body`, `status`, `parent_id`, `source_kind`, `created_at`, `updated_at`, `filename`, `aliases`.

**Behavior:**
- On insert: generates `created_at` and `updated_at` timestamps
- On update: only updates `updated_at`, preserves `created_at`
- Deletes and recreates general aliases, sets filename alias
- Syncs FTS index via `_sync_fts()`
- Records a `node_created` or `node_updated` event

---

### `link_nodes()`

```python
def link_nodes(
    self,
    from_ref: str | int,
    to_ref: str | int,
    edge_type: str,
    *,
    weight: float = 1.0,
) -> dict[str, Any]:
```

Creates or updates a directed edge between two nodes.

**Parameters:**

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `from_ref` | str \| int | required | Source node (slug, alias, or ID) |
| `to_ref` | str \| int | required | Target node (slug, alias, or ID) |
| `edge_type` | str | required | Relationship type (must be in `EDGE_TYPES`) |
| `weight` | float | `1.0` | Relationship strength for BM25 ranking boost |

**Returns:** `{"from": from_ref, "to": to_ref, "edge_type": edge_type, "weight": weight}`

**Raises:** `ValueError` if `edge_type` is invalid or either node cannot be resolved.

**Note:** Uses `ON CONFLICT` to upsert — if the edge already exists, only the weight is updated.

---

### `get_node()`

```python
def get_node(self, ref: str | int) -> Optional[dict[str, Any]]:
```

Retrieves a single node by ID, slug, or filename alias.

**Resolution order:**
1. If `ref` is an integer or numeric string → lookup by `nodes.id`
2. Else lookup by `nodes.slug`
3. Else lookup by `aliases.alias` (filename or general alias)

**Returns:** Node dict (same shape as `upsert_node` return value) or `None` if not found.

---

### `search_nodes()`

```python
def search_nodes(
    self,
    query: str,
    *,
    limit: int = 8,
    kinds: Optional[Iterable[str]] = None,
    include_index: bool = False,
) -> list[dict[str, Any]]:
```

Full-text search with BM25 ranking, neighbor boosting, and kind filtering.

**Parameters:**

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `query` | str | required | Natural language search query |
| `limit` | int | `8` | Maximum results (clamped to 1-25) |
| `kinds` | Iterable[str] \| None | `None` | Filter to specific kinds only |
| `include_index` | bool | `False` | Whether to include `index` kind in results |

**Returns:** List of node dicts with an added `score` field (BM25-derived, rounded to 4 decimals).

**Algorithm:**
1. Tokenize query via `_tokenize_query()`, removing stopwords and short tokens
2. Attempt FTS5 search via `_fts_search()` with BM25 scoring
3. Fall back to `_fallback_search()` (LIKE-based) if FTS returns nothing
4. Build neighbor score map: for each result, boost connected nodes by `score * 0.35`
5. Sort by descending score, ascending node ID as tiebreaker
6. Filter by `kinds` and `include_index`

---

### `get_index_node()`

```python
def get_index_node(self) -> Optional[dict[str, Any]]:
```

Convenience method. Returns the node with slug `index` or filename `00-index.md`. This is the workspace root entry point.

---

### `list_context_nodes()`

```python
def list_context_nodes(self) -> list[dict[str, Any]]:
```

Returns all nodes of kinds `{"index", "topic", "detail", "project"}` — the nodes that form the primary navigation hierarchy.

**Ordering:** `index` first, then `topic`, then `detail`, then `project`, then alphabetically by title within each kind, then by ID.

**Returns:** List of node dicts.

---

### `prefetch()`

```python
def prefetch(self, query: str, *, limit: int = 2, include_workspace_label: bool = False) -> str:
```

Builds a compact context block for an agent by searching, rendering, and concatenating nodes.

**Parameters:**

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `query` | str | required | Search query |
| `limit` | int | `2` | Maximum nodes to include |
| `include_workspace_label` | bool | `False` | Include workspace name in label |

**Returns:** A string of format `"[{filename}]\n\n{rendered_markdown}"` joined by `\n\n---\n\n`. Falls back to `include_index=True` if no results found without index.

---

### `render_node_markdown()`

```python
def render_node_markdown(self, node: dict[str, Any] | str | int) -> str:
```

Converts a node into a markdown string suitable for agent consumption.

**Algorithm:**
1. Resolves `node` to a node dict if it's a slug or ID
2. Extracts `body` (stripped)
3. Appends `_render_indicators(node["id"])` — outgoing edges as `→ Title: \`filename.md\`` lines
4. Formats as `"# {title}\n\n{body}\n\n{indicators}"`

**Returns:** Rendered markdown string (empty string if node not found).

---

### `sync_markdown_exports()`

```python
def sync_markdown_exports(self, output_dir: Path | str | None = None) -> dict[str, Any]:
```

Triggers both export targets simultaneously.

**Returns:** `{"context": <context export result>, "organized": <organized export result>}`.

See Export System section below for details on each target.

---

### `clean_exports()`

```python
def clean_exports(self) -> dict[str, Any]:
```

Removes all derived markdown files (`context/` and `docs/db-export/`). SQLite remains untouched as the source of truth.

**Deletes:**
- `context/` directory and all contents
- `docs/db-export/` directory and all contents
- `docs/` directory if empty after removal

**Returns:** `{"deleted": [list of removed paths relative to workspace root]}`.

---

### `verify_db_completeness()`

```python
def verify_db_completeness(self) -> dict[str, Any]:
```

Safety check before deleting derived or legacy files. Ensures the database has sufficient content.

**Pass conditions (all must be true):**
- `node_count > 0` — at least one node exists
- `index_count > 0` — an index node exists
- `body_count > 0` — at least one node has non-empty `summary` or `body`

**Returns:** `{"verified": bool, "node_count": int, "missing": [list of failed checks], "summary": str}`

---

### `migrate_legacy_to_db()`

```python
def migrate_legacy_to_db(
    self,
    *,
    backup_root: Path | str | None = None,
    archive: bool = True,
    remove_legacy: bool = True,
) -> dict[str, Any]:
```

Imports all legacy workspace files into SQLite and organizes real code under `code/`.

**Legacy paths scanned:** `README.md`, `context/`, `agents/`, `docs/`, `projects/`, `scripts/`

**For each file:**
- `README.md` → node kind `doc`, slug `readme`, linked via `references` to index
- `context/*.md` → kind inferred from filename, linked via `details` to index
- `agents/**/*.md` → kind `agent-note`, slug `agent-{path}`, linked via `contains` to index
- `docs/**/*.md` → kind `reference` or `doc`, linked via `references` to index
- `projects/{name}/*` → kind `project` with `project-{name}` slug; child `.md` files become `doc` nodes linked via `contains`; non-markdown files moved to `code/{name}/`
- `scripts/**/*` → `.md` files become `script` nodes linked via `contains`; other files moved to `code/scripts/`

**Parameters:**

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `backup_root` | Path \| str \| None | `None` | Override backup directory |
| `archive` | bool | `True` | Create tar.gz backup before import |
| `remove_legacy` | bool | `True` | Delete original files after successful import |

**Returns:** `{"workspace": str, "imported": list, "moved": list, "skipped": list, "removed": list, "backup": str | None, "verified": bool, "node_count": int, "missing": list, "generated": list}`

---

### `scan_artifacts()`

```python
def scan_artifacts(self) -> dict[str, int]:
```

Scans the `code/` directory and indexes all files into the `artifacts` table.

**Behavior:**
- Deletes existing `code/` artifacts before rescanning
- For each `.md` file: uses first meaningful paragraph as description
- Uses `ON CONFLICT(path)` to update existing artifacts
- Removes artifacts whose paths no longer exist
- Records `artifacts_scanned` event

**Returns:** `{"artifacts": <count of indexed files>}`

---

### `seed_workspace()`

```python
def seed_workspace(self, description: str, areas: Iterable[str]) -> dict[str, Any]:
```

Creates the initial structure for a new workspace: an index node and one topic node per area.

**Parameters:**

| Parameter | Type | Purpose |
|-----------|------|---------|
| `description` | str | Workspace description (used in index body) |
| `areas` | Iterable[str] | Area names, optionally with `: description` suffix |

**Creates:**
1. Index node (`kind=index`, slug=`index`, filename=`00-index.md`) with description body and area list
2. One topic node per area, linked via `details` edge from index
3. Standard folders via `ensure_workspace_layout()`

**After creation:** calls `scan_artifacts()` and generates `workspace-doc.md` and `CLAUDE.md`.

**Returns:** `{"index": <index node dict>, "export": <empty export result>, "generated": [files]}`

---

### `create_project()`

```python
def create_project(self, name: str, description: str = "") -> dict[str, Any]:
```

Creates a project node and its directory structure.

**Creates:**
- Directory `code/{name}/`
- Node `kind=project`, slug=`project-{name}`, filename=`project-{name}.md`
- Linked from index via `project_of` edge

**Returns:** `{"project": <project node dict>, "path": str, "export": <empty export result>}`

---

### `audit()`

```python
def audit(self) -> dict[str, Any]:
```

Structural integrity check. Returns all detected issues.

**Checks performed:**
1. `workspace.db` exists (critical)
2. `schema_version` matches expected `SCHEMA_VERSION` (critical)
3. At least one index node exists (critical)
4. No more than one index node (broken)
5. No orphan nodes (`parent_id` points to non-existent node)
6. No broken edges (from_node_id or to_node_id is NULL)

**Returns:** `{"issues": [list of WorkspaceIssue], "stats": {"nodes": int, "edges": int, "artifacts": int}}`

**WorkspaceIssue dataclass fields:** `severity` (one of `"critical"`, `"broken"`), `message` (string description)

---

### `claim_task()` / `complete_task()`

```python
def claim_task(self, agent_id: str, description: str) -> dict[str, Any]:
def complete_task(self, event_id: int, agent_id: str, result: str) -> dict[str, Any]:
```

Agent coordination pair for long-running tasks.

**`claim_task`** creates an `agent_task_start` event with `{"agent": agent_id, "task": description, "started_at": iso8601}`.

**`complete_task`** creates an `agent_task_done` event with `{"agent": agent_id, "start_event_id": event_id, "result": result, "completed_at": iso8601}`.

**Returns (claim_task):** `{"event_id": int, "agent": str, "task": str, "started_at": str}`

**Returns (complete_task):** `{"event_id": int, "agent": str, "start_event_id": int, "result": str, "completed_at": str}`

---

### `generate_workspace_doc()` / `generate_claude_md()`

```python
def generate_workspace_doc(self) -> str:
def generate_claude_md(self) -> str:
```

Regenerate onboarding files that guide agents in using the workspace.

**`generate_workspace_doc`** writes `workspace-doc.md` — a prompt instructing an agent to document the workspace by:
1. Reading existing nodes via `workspace_list_all_nodes()`
2. Scanning artifacts via `workspace_scan_artifacts()`
3. Comparing against actual `code/` files to find gaps
4. Creating/updating nodes for undocumented elements
5. Updating the index

**`generate_claude_md`** writes `CLAUDE.md` — a quick-start guide that includes:
- Tool reference (`workspace_*` function names)
- Skill references (`workspace-daily`, `context-engine`, `workspace-doc.md`)
- Multi-agent coordination instructions
- Current index body

**Both return:** Path relative to workspace root of the generated file.

---

## 5. Internal Helpers

### `_fts_search()`

```python
def _fts_search(
    self,
    conn: sqlite3.Connection,
    tokens: list[str],
    limit: int,
    kinds: tuple[str, ...],
    include_index: bool,
) -> list[dict[str, Any]]:
```

Executes FTS5 search with BM25 ranking. Builds an `AND`-joined MATCH query from tokens.

**Query format:** `MATCH '"token1" "token2" ...'`

**SQL:** Uses `MAX(0.1, -bm25(node_fts))` for score — BM25 is negative in SQLite FTS5, so negated and clamped.

**Returns:** List of `{"id": int, "score": float}` dicts.

---

### `_fallback_search()`

```python
def _fallback_search(
    self,
    conn: sqlite3.Connection,
    terms: list[str],
    limit: int,
    kinds: tuple[str, ...],
    include_index: bool,
) -> list[dict[str, Any]]:
```

LIKE-based search when FTS returns no results. Searches `lower(title)`, `lower(summary)`, and `lower(body)` for each term.

**Scoring:** `max(0.1, 1.0 - rank * 0.05)` — linear decay from 1.0 by 0.05 per result position.

**Returns:** List of `{"id": int, "score": float}` dicts.

---

### `_sync_fts()`

```python
def _sync_fts(self, conn: sqlite3.Connection, node_id: int) -> None:
```

Keeps the FTS5 index synchronized with a node. Called after every `upsert_node()`.

**Behavior:**
1. Fetches the node row
2. Collects all aliases (space-joined) for the node
3. Deletes any existing FTS entry for `rowid = node_id`
4. Inserts fresh FTS entry with all indexed columns

---

### `_tokenize_query()`

```python
def _tokenize_query(query: str) -> list[str]:
```

Extracts search tokens from a natural language query using `TOKEN_RE` regex.

**Regex:** `[a-z0-9][a-z0-9_\-]{1,}` (case-insensitive, minimum 2 chars)

**Filters out:** tokens in `STOPWORDS` set or shorter than 3 characters.

**Returns:** Lowercase list of valid tokens.

**STOPWORDS:** Spanish common words (`de`, `la`, `el`, `en`, `los`, `las`, `un`, `una`, `y`, `a`, `que`, `es`, `por`, `con`, `del`, `al`, `se`, `su`, `hay`, `son`, `si`, `me`, `te`, `le`, `nos`, `les`, `mas`, `más`, `pero`, `como`, `para`, `este`, `esta`, `estos`, `estas`, `mi`, `tu`, `qué`, `quien`, `quién`, `quienes`, `quiénes`, `donde`, `dónde`, `cuando`, `cuándo`, `como`)

---

### `_slugify()`

```python
def _slugify(value: str) -> str:
```

Converts any string to a URL-safe lowercase slug.

**Algorithm:**
1. `strip()` whitespace
2. `lower()` case
3. Replace any run of non-alphanumeric characters with `-` via `re.sub(r"[^a-z0-9]+", "-", value)`
4. Collapse consecutive dashes via `re.sub(r"-{2,}", "-", value)`
5. Strip leading/trailing dashes
6. Return `"node"` if result is empty

---

### `_infer_kind_from_filename()`

```python
def _infer_kind_from_filename(name: str) -> str:
```

Determines the node kind from a markdown filename.

**Decision tree:**
```
name == "00-index.md"              → "index"
stem matches r"^\d{2}[a-z]-"       → "detail"
stem matches r"^\d{2}-"            → "topic"
stem.startswith("project-")        → "project"
otherwise                          → "detail"
```

---

## 6. FTS5 Configuration

**Table definition:**

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS node_fts
USING fts5(title, slug, summary, body, aliases, tokenize='unicode61 remove_diacritics 2')
```

**Indexed fields:** `title`, `slug`, `summary`, `body`, `aliases` (space-joined from the aliases table)

**Tokenizer:** `unicode61 remove_diacritics 2`

| Option | Meaning |
|--------|---------|
| `unicode61` | Unicode-aware tokenizer compliant with UAX#29 |
| `remove_diacritics` | Strips diacritical marks (accents) before indexing and querying |
| `2` | Minimum token length of 2 characters |

**BM25 Ranking:**

SQLite FTS5 returns BM25 as a negative floating-point value (lower is better relevance). The implementation negates it (`-bm25(node_fts)`) so higher scores = better relevance. Clamped to `MAX(0.1, ...)` to ensure a minimum score even for poor matches.

BM25 parameters used by SQLite FTS5: `k1=1.2, b=0.75` (standard FTS5 defaults).

**Search flow:**
1. Raw query → `_tokenize_query()` → tokens
2. Tokens joined with ` AND `" quoted" → FTS5 MATCH query
3. FTS5 returns rows ranked by BM25
4. Neighbor nodes receive `score * 0.35` boost (propagated one hop)
5. Final ranking: descending score, ascending node ID

---

## 7. Migration from Markdown

### `migrate_from_markdown()`

```python
def migrate_from_markdown(self, *, force: bool = False) -> dict[str, Any]:
```

One-time import of legacy `context/` directory into SQLite. Used when setting up a new workspace DB from existing markdown files.

**Behavior (non-empty DB without `force`):** Returns `{"imported": False, "reason": "db-not-empty"}`

**With `force=True`:** Truncates all tables before importing.

**Algorithm:**

1. **Scan `context/` directory** for `*.md` files
   - Parse title from first `# heading` line via `TITLE_RE`
   - Strip heading and `→ target: \`filename.md\`` indicators via `_strip_heading_and_indicators()`
   - Infer kind from filename via `_infer_kind_from_filename()`
   - `summary` = first meaningful paragraph of body
   - Create node with `source_kind = "markdown-import"`

2. **Resolve pending edges** from indicators
   - For each `source_slug → target_filename` indicator pair
   - Look up target node by filename alias
   - Create `details` edge from source to target

3. **Scan `projects/` directory** (if exists)
   - Each subdirectory = a `project` node
   - `slug = f"project-{slugify(dirname)}"`
   - Linked to index via `project_of` edge

4. **Seed** if no nodes imported → calls `seed_workspace()`

5. **Post-import:** `scan_artifacts()`, generate `workspace-doc.md`, generate `CLAUDE.md`

### `source_kind` Values

| Value | Meaning |
|-------|---------|
| `manual` | Node created via `upsert_node()` directly |
| `seed` | Node created by `seed_workspace()` |
| `markdown-import` | Node imported from `context/*.md` via `migrate_from_markdown()` |
| `project-import` | Node imported from `projects/` via `migrate_from_markdown()` |
| `legacy-readme` | Node imported from `README.md` via `migrate_legacy_to_db()` |
| `legacy-context` | Node imported from `context/*.md` via `migrate_legacy_to_db()` |
| `legacy-agents` | Node imported from `agents/*.md` via `migrate_legacy_to_db()` |
| `legacy-docs` | Node imported from `docs/*.md` via `migrate_legacy_to_db()` |
| `legacy-projects` | Node imported from `projects/` via `migrate_legacy_to_db()` |
| `legacy-scripts` | Node imported from `scripts/*.md` via `migrate_legacy_to_db()` |
| `project-create` | Node created by `create_project()` |

---

## 8. Export System

The workspace has two distinct markdown export targets, both derived from SQLite. Neither is the source of truth.

### Target 1: `context/` — Compact Export

**Root:** `{workspace_root}/context/`

Generated by `export_markdown()` (called via `sync_markdown_exports()`).

**Characteristics:**
- Flat-ish structure: nodes of kinds `{"index", "topic", "detail", "project"}`
- Minimal metadata — just `# Title\n\n{body}\n\n→ Related: \`filename.md\``
- Filenames derived from `filename` alias or `slug + .md`
- Overwrites existing files, removes files not in current node set
- Records `markdown_exported` event and `last_export_at` metadata

**Use case:** Compact context block for embedding in agent prompts or external systems.

### Target 2: `docs/db-export/` — Organized Export

**Root:** `{workspace_root}/docs/db-export/` (or custom `output_dir`)

Generated by `export_organized_markdown()` (called via `sync_markdown_exports()`).

**Structure:**
```
docs/db-export/
├── 00-index.md              # Overview with stats, node counts, event counts
├── 01-nodes.md              # Table of all nodes with metadata
├── 02-relations.md          # Table of all edges
├── 03-events.md             # Table of recent events
├── artifacts/
│   ├── 00-index.md           # Artifact group index
│   └── {type}.md             # One file per artifact type
└── nodes/
    └── {filename}            # One file per node with full detail
```

**Each node file includes:**
- Full metadata table (ID, slug, kind, status, filename, parent, source_kind, timestamps, aliases)
- Summary section
- Body section
- Outgoing relations as `→ \`edge_type\` \`to_slug\` (to_title) [weight=X.XX]`
- Incoming relations as `← \`edge_type\` \`from_slug\` (from_title) [weight=X.XX]`
- Associated artifacts list
- Rendered markdown preview

**Use case:** Human-readable audit of the full database state.

### Relationship Rendering (→ Indicators)

In both export targets, outgoing edges from a node appear as navigation indicators at the bottom:

```markdown
→ Topic Name: `topic-name.md`
→ Project Name: `project-name.md`
→ Related Detail: `detail-name.md`
```

**Indicator sorting** (by `_render_indicators`):
```
details (0) → contains (1) → project_of (2) → references (3) → related_to (4) → depends_on (5) → other (6)
```

Within each edge type, sorted alphabetically by target title, then by target ID.

### Filename Generation

| Kind | Default Filename |
|------|-----------------|
| `index` | `00-index.md` |
| Any other | `{slug}.md` |

The filename is stored as a special `alias_kind = 'filename'` alias so nodes can be retrieved by filename as well as slug.

---

## Module-Level Constants

```python
SCHEMA_VERSION = 1
EXPORTED_KINDS = {"index", "topic", "detail", "project"}
DEFAULT_NODE_STATUS = "active"
STANDARD_FOLDERS = ["code", "code/scripts"]
STOPWORDS = {"de", "la", "el", "en", "los", "las", "un", "una", "y", "a", "que", ...}
EDGE_TYPES = {"contains", "details", "related_to", "project_of", "depends_on", "references"}
NODE_KINDS = {"index", "topic", "detail", "project", "doc", "agent-note", "script", "reference"}
```

## Dataclasses

```python
@dataclass
class WorkspaceIssue:
    severity: str   # "critical" | "broken"
    message: str
```

Used by `audit()` to report structural issues.
