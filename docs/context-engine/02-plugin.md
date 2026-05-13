# Workspace-Context Plugin (MemoryProvider for Hermes)

## Overview

**workspace-context** is a DB-first nodal workspace memory provider for Hermes. It provides structured, queryable context to the AI by reading from SQLite databases (`workspace.db`) located within each workspace directory.

**Plugin Metadata:**
- **Name:** `workspace-context`
- **Version:** 3.0.0
- **Plugin File:** `/Users/servidor_jmp/.hermes/plugins/workspace-context/__init__.py`
- **Config File:** `/Users/servidor_jmp/.hermes/plugins/workspace-context/plugin.yaml`

### What It Provides

The plugin provides two main capabilities:

1. **System Prompt Injection** — Injects nodal context (a rendered block of workspace information) into every system prompt, guiding the AI on how to work with workspace data.
2. **Tool Suite** — 20 tools for listing, reading, searching, creating, and linking workspace nodes, plus file system operations and multi-agent coordination.

### When It Loads

The plugin activates when Hermes is configured with:
```yaml
memory:
  provider: workspace-context
```

At that point, `WorkspaceContextProvider` is instantiated and `initialize()` is called, which:
1. Resolves the Hermes home directory
2. Ensures the active workspace store exists (and all workspace stores for `all-indexes` mode)
3. Rebuilds the cached prompt block

---

## Configuration Schema

The plugin schema is declared via `get_config_schema()` and supports four keys:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `workspace` | string | `"doyouwin"` | Active workspace name. Resolves to `workspaces/{workspace}/workspace.db` |
| `inject_mode` | string | `"index"` | How much context to inject: `"index"`, `"all-indexes"`, or `"full"` |
| `max_chars` | integer | `8000` | Maximum total characters to inject into the system prompt (truncation limit) |
| `recursive` | boolean | _(not in schema)_ | Reserved for future use (not currently implemented) |

### Config File Location

Configuration is persisted to `{hermes_home}/config.yaml` under `plugins.workspace-context`:

```yaml
plugins:
  workspace-context:
    workspace: "pixelcore"
    inject_mode: "index"
    max_chars: 12000
```

---

## Three Inject Modes

The `inject_mode` setting controls what gets embedded in the system prompt block and how prefetch behaves.

### Mode: `index` (Default)

- **What gets injected:** Only the index node of the active workspace, rendered as Markdown
- **Prefetch behavior:** Performs a targeted prefetch within the active workspace only
- **Best for:** Large workspaces where you want orientation but need to fetch details on demand
- **Instruction emphasis:** "Search first, then open details"

### Mode: `all-indexes`

- **What gets injected:** Index node from every discovered workspace, each labeled with `[WORKSPACE: name]` and `[ACTIVO]` for the active one
- **Prefetch behavior:** Cross-workspace ranking with normalization, mention boost, and active workspace boost
- **Best for:** Multi-workspace setups where the AI needs to understand which workspace to operate in
- **Instruction emphasis:** "You only have index nodes — search to get details"

### Mode: `full`

- **What gets injected:** ALL context nodes from the active workspace, rendered as Markdown, separated by `---` dividers
- **Prefetch behavior:** No prefetch — all context is already in the prompt
- **Best for:** Small workspaces or when offline/disconnected operation is needed
- **Instruction emphasis:** "SQLite is your source of truth — think nodal first"

---

## system_prompt_block()

This method returns the full injected block inserted into every system prompt. It uses an HTML comment sentinel (`<!-- workspace context: ... -->`) for easy extraction.

### `index` Mode Output

```
<!-- workspace context: {workspace} start -->
[WORKSPACE ACTIVO: {workspace}]
Tienes cargado el nodo index del workspace desde `workspace.db`: te orienta, pero no basta para detalles.
Orden obligatorio: `workspace_search_nodes` -> `workspace_get_node` -> `workspace_list_folder`/`workspace_read_workspace_file` si necesitas archivos reales en `code/` -> `workspace_read_file` solo como compatibilidad.
Ejemplo: si te preguntan por un detalle del workspace, busca con `workspace_search_nodes` y luego abre el nodo con `workspace_get_node`. No uses `session_search`, `search_files` ni exports Markdown como primer recurso.

{rendered_index_node_markdown}
<!-- workspace context: {workspace} end -->
```

### `all-indexes` Mode Output

```
<!-- workspace context: {workspace} start -->
[WORKSPACES DISPONIBLES: ws1, ws2, ws3, ...] [ACTIVO: {workspace}]
Tienes cargados solo los nodos index de cada workspace desde SQLite: sirven para orientarte, no para responder detalles finos por sí solos.
Orden obligatorio: `workspace_search_nodes` -> `workspace_get_node` -> `workspace_list_folder`/`workspace_read_workspace_file` si necesitas archivos reales en `code/` -> `workspace_read_file` solo como compatibilidad.
Si te preguntan por un detalle del workspace, primero busca con `workspace_search_nodes` y luego abre el nodo con `workspace_get_node`. No uses `session_search`, `search_files` ni exports Markdown como fuente de verdad.

[WORKSPACE: pixelcore] [ACTIVO]
{rendered_index_node}

---

[WORKSPACE: infraestructura]
{rendered_index_node}

---

[WORKSPACE: marketing]
{rendered_index_node}
<!-- workspace context: {workspace} end -->
```

### `full` Mode Output

```
<!-- workspace context: {workspace} start -->
[WORKSPACE ACTIVO: {workspace}]
Tienes cargados todos los nodos de contexto renderizados desde `workspace.db`; la fuente de verdad es SQLite.
Piensa primero en flujo nodal: `workspace_search_nodes` -> `workspace_get_node`. Usa archivos reales en `code/` solo si el nodo no basta. No uses `session_search`, `search_files` ni exports Markdown como fuente principal.

[Source: 00-index.md]
{rendered_node}

---

[Source: 01-intro.md]
{rendered_node}

---

[Source: project-x.md]
{rendered_node}
<!-- workspace context: {workspace} end -->
```

### Restrictions Imposed

Each mode includes mandatory instructions:

1. **Mandatory tool order:** `workspace_search_nodes` -> `workspace_get_node` -> file operations
2. **Deprecated tool warnings:** `session_search`, `search_files`, and Markdown exports are marked as "not first resource" or "not source of truth"
3. **Source of truth declaration:** SQLite is always the authoritative source; files/exports are secondary
4. **Code path emphasis:** Real code lives under `code/` — use `workspace_list_folder`/`workspace_read_workspace_file` to access it

---

## Prefetch System

The prefetch system pre-loads relevant nodes into a cache before the AI needs them, reducing round-trips.

### `_resolve_prefetch()` — Detailed Logic

#### Single Workspace Mode (`index`)

When `inject_mode` is `index` (or not `full`), prefetch runs against **only the active workspace**:

```python
store = self._ensure_store(self._active_workspace())
return store.prefetch(query, limit=MAX_PREFETCH_NODES, include_workspace_label=False)
```

The underlying `WorkspaceStore.prefetch()` performs FTS5 search and returns the top N nodes as rendered Markdown.

#### Cross-Workspace Mode (`all-indexes`)

When `inject_mode` is `all-indexes`, prefetch performs **cross-workspace ranking**:

```
For each workspace:
  1. Tokenize query and workspace name
  2. Compute mention_boost = 1.5 if query tokens overlap workspace name tokens
  3. Compute active_boost = 1.1 if workspace == active workspace
  4. Search nodes with FTS5
  5. If mention_boost > 1.0, ALSO search with stripped tokens (query minus workspace tokens)
  6. Normalize BM25 scores within workspace: score_normalizado = (raw / max_in_workspace) * mention_boost * active_boost
  7. Collect all candidates, sort by (-score, workspace, slug)
  8. Return top 5 as rendered Markdown
```

### Normalization Formula

```python
score_normalizado = (raw_score / max_del_workspace) * mention_boost * active_boost
```

Where:
- `raw_score` = BM25 score from FTS5 search within that workspace
- `max_del_workspace` = Maximum BM25 score among all results in that workspace (or 1.0 if empty)
- `mention_boost` = 1.5 if the query names this workspace, else 1.0
- `active_boost` = 1.1 if this workspace is the active one, else 1.0

This normalizes scores to be comparable across workspaces with different corpus sizes.

### Mention Boost (1.5x)

When the user's query mentions a workspace name, that workspace receives a 1.5x score multiplier. Example: if the query contains "pixelcore", the `pixelcore` workspace gets `mention_boost = 1.5`.

### Active Workspace Boost (1.1x)

The currently active workspace always receives a 1.1x multiplier, making it slightly more likely to appear first even when not explicitly named.

### The "Stripped Query" Trick

When `mention_boost > 1.0` (query names the workspace), a second search is performed **without the workspace name token**. This finds nodes that don't repeat the workspace name in their body.

**Example:** Query = "pixelcore infraestructura"
- First search: "pixelcore infraestructura" in `pixelcore` workspace
- Stripped search: "infraestructura" in `pixelcore` workspace
- Reason: A node file named `40-infraestructura.md` inside the `pixelcore` folder may not say "pixelcore" in its body, but it IS about infraestructura

```python
if mention_boost > 1.0:
    stripped_tokens = query_tokens - ws_tokens
    if stripped_tokens:
        stripped_nodes = store.search_nodes(
            " ".join(stripped_tokens), limit=4, include_index=False
        )
        # Merge, deduplicating by slug
```

### `full` Mode

No prefetch is performed. The system prompt already contains all nodes, so prefetch would be redundant.

```python
if mode == "full":
    return ""  # No prefetch needed
```

### Prefetch Cache

Results are cached per-query in `_prefetch_cache` with thread-safe access via `_prefetch_lock`. Cache is cleared on:
- `shutdown()`
- Rebuilt block when changes are detected

---

## Tool Schemas

All 20 tools are documented below. Each tool returns a JSON string.

---

### 1. workspace_list_workspaces

**Description:** Lists all available workspaces, including DB-first status and index node availability.

**Parameters:** None required.

**Returns:**
```json
{
  "workspaces": [
    {
      "name": "pixelcore",
      "active": true,
      "has_db": true,
      "has_index": true,
      "issues": ["issue message 1", "..."]
    }
  ],
  "active": "pixelcore"
}
```

**When to use:** When you need to understand which workspaces exist and their current state. Typically called during initialization or when the user asks "what workspaces do I have?"

---

### 2. workspace_list_files

**Description:** Legacy compatibility tool. Lists nodes that would have a Markdown-derived filename. Prefer `workspace_search_nodes`.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `workspace` | string | No | Workspace name (defaults to active) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "files": [
    {
      "file": "00-index.md",
      "description": "Index of everything",
      "slug": "index",
      "kind": "index"
    }
  ]
}
```

**When to use:** Legacy compatibility only. Use `workspace_search_nodes` instead for DB-first lookups.

---

### 3. workspace_read_file

**Description:** Legacy compatibility tool. Reads a node by its derived filename or slug from SQLite. Prefer `workspace_get_node`.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `filename` | string | **Yes** | Derived filename (`00-index.md`) or node slug |
| `workspace` | string | No | Workspace name (defaults to active) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "file": "00-index.md",
  "slug": "index",
  "kind": "index",
  "content": "# Index\n\nWelcome to the workspace..."
}
```

**When to use:** Legacy compatibility only. Use `workspace_get_node` for DB-first reads.

---

### 4. workspace_list_folder

**Description:** Lists real folders and files in the workspace. Uses `code/` as the main root for programs and scripts.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `folder` | string | No | Relative safe path inside workspace (default: `code`) |
| `workspace` | string | No | Workspace name (defaults to active) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "folder": "code",
  "subdirs": ["api", "cli", "shared"],
  "files": [
    {"file": "README.md", "description": "Project overview"}
  ],
  "source_of_truth": "workspace.db"
}
```

**When to use:** When exploring the actual file system structure of the workspace, particularly under `code/` for programs/scripts.

---

### 5. workspace_read_workspace_file

**Description:** Reads a real file from the workspace with a safe relative path. For code and programs, use paths under `code/`.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | string | **Yes** | Safe relative path inside workspace |
| `workspace` | string | No | Workspace name (defaults to active) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "path": "code/api/main.py",
  "content": "import sys\n\ndef main():\n    ..."
}
```

**When to use:** Reading actual source code, scripts, configs, or any non-node file from the workspace.

---

### 6. workspace_get_node

**Description:** Primary DB-first read. Gets a node by slug, derived filename, alias, or ID.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `ref` | string | **Yes** | Slug, derived filename, or node ID |
| `workspace` | string | No | Workspace name (defaults to active) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "node": {
    "id": 1,
    "slug": "index",
    "title": "Workspace Index",
    "kind": "index",
    "summary": "...",
    "body": "...",
    "status": "active",
    "filename": "00-index.md",
    "aliases": ["home", "start"],
    "created_at": "...",
    "updated_at": "..."
  },
  "rendered_markdown": "# Workspace Index\n\nWelcome..."
}
```

**When to use:** After finding a relevant slug via `workspace_search_nodes`, retrieve the full node details.

---

### 7. workspace_search_nodes

**Description:** Primary DB-first entry point. Searches workspace nodes using FTS5, aliases, and relationships to discover what to read.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | **Yes** | Search query |
| `workspace` | string | No | Workspace name (defaults to active) |
| `limit` | integer | No | Maximum results (default: 8) |
| `kind` | string | No | Filter by node kind (`topic`, `detail`, `project`, etc.) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "results": [
    {
      "slug": "api-design",
      "title": "API Design Guidelines",
      "kind": "topic",
      "summary": "Standards for REST APIs",
      "score": 2.34,
      "filename": "03-api-design.md"
    }
  ]
}
```

**When to use:** First step in any nodal workflow. Always search before getting node details.

---

### 8. workspace_upsert_node

**Description:** Creates or updates a node in the workspace's SQLite DB. Does not generate Markdown exports.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `slug` | string | **Yes** | Stable node slug |
| `title` | string | **Yes** | Node title |
| `kind` | string | **Yes** | Node type (`index`, `topic`, `detail`, `project`, `doc`, `agent-note`, `script`, `reference`) |
| `summary` | string | No | Brief summary |
| `body` | string | No | Main body in Markdown |
| `status` | string | No | Node status (default: `"active"`) |
| `parent` | string | No | Parent node slug, filename, or ID |
| `aliases` | array[string] | No | Additional aliases |
| `filename` | string | No | Optional derived filename for Markdown compat |
| `workspace` | string | No | Workspace name (defaults to active) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "node": {
    "id": 42,
    "slug": "new-node",
    "title": "New Node",
    "kind": "topic",
    ...
  }
}
```

**When to use:** Creating or updating workspace knowledge nodes. Does not touch files.

---

### 9. workspace_link_nodes

**Description:** Creates or updates a relationship between two nodes in SQLite. Does not generate Markdown exports.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `from_ref` | string | **Yes** | Source node (slug, filename, or ID) |
| `to_ref` | string | **Yes** | Destination node (slug, filename, or ID) |
| `edge_type` | string | **Yes** | Relationship type: `contains`, `details`, `related_to`, `project_of`, `depends_on`, `references` |
| `weight` | number | No | Optional relationship weight (default: 1.0) |
| `workspace` | string | No | Workspace name (defaults to active) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "link": {
    "id": 15,
    "from_id": 1,
    "to_id": 5,
    "edge_type": "details",
    "weight": 1.0
  }
}
```

**When to use:** Establishing relationships between nodes to enable graph traversal and discovery.

---

### 10. workspace_create_project

**Description:** Creates a real project in `code/{name}/`, its DB-first node, and necessary relationships.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | **Yes** | Project name |
| `description` | string | No | Brief project description |
| `workspace` | string | No | Workspace name (defaults to active) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "project": {
    "name": "new-feature",
    "path": "code/new-feature",
    "node_slug": "project-new-feature"
  }
}
```

**When to use:** Bootstrapping a new project within the workspace. Creates both the filesystem directory and the associated DB node.

---

### 11. workspace_export_markdown

**Description:** Regenerates `context/` and `docs/db-export/` as Markdown exports derived from `workspace.db`.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `workspace` | string | No | Workspace name (defaults to active) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "export": {
    "context_files": 12,
    "docs_files": 5
  }
}
```

**When to use:** Periodically syncing the DB state back to Markdown for human readability or external tools.

---

### 12. workspace_list_all_nodes

**Description:** Lists all nodes in the workspace from SQLite.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `workspace` | string | No | Workspace name (defaults to active) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "nodes": [
    {
      "id": 1,
      "slug": "index",
      "title": "Index",
      "kind": "index",
      "status": "active",
      ...
    }
  ]
}
```

**When to use:** Auditing all nodes, bulk operations, or when you need the complete node list.

---

### 13. workspace_list_edges

**Description:** Lists all relationships between nodes from SQLite.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `workspace` | string | No | Workspace name (defaults to active) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "edges": [
    {
      "id": 1,
      "from_id": 1,
      "to_id": 5,
      "edge_type": "contains",
      "weight": 1.0
    }
  ]
}
```

**When to use:** Understanding the node graph structure, finding related nodes, or auditing relationships.

---

### 14. workspace_list_events

**Description:** Lists recent workspace events for multi-agent coordination.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `workspace` | string | No | Workspace name (defaults to active) |
| `limit` | integer | No | Maximum events (default: 50, max: 200) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "events": [
    {
      "id": 1,
      "type": "task_claimed",
      "agent_id": "agent-42",
      "description": "Implementing feature X",
      "timestamp": "2026-01-15T10:30:00Z"
    }
  ]
}
```

**When to use:** Multi-agent coordination, tracking task ownership, and understanding recent activity.

---

### 15. workspace_scan_artifacts

**Description:** Scans real files under `code/` and updates the artifacts table.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `workspace` | string | No | Workspace name (defaults to active) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "scanned": 42,
  "artifacts": [
    {
      "id": 1,
      "path": "code/api/main.py",
      "type": "python",
      "size": 1234
    }
  ]
}
```

**When to use:** Indexing code artifacts for discovery, tracking file metadata, or keeping the artifact registry current.

---

### 16. workspace_migrate_legacy

**Description:** Migrates legacy folders to SQLite, moves code to `code/`, archives originals compressed, and optionally removes legacy.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `workspace` | string | No | Workspace name (defaults to active) |
| `remove_legacy` | boolean | No | Remove legacy after migration (default: `true`) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "migrated_nodes": 10,
  "moved_files": 5,
  "archived": ["old-folder.zip"],
  "legacy_removed": true
}
```

**When to use:** Onboarding old workspace data into the DB-first system.

---

### 17. workspace_clean_exports

**Description:** Deletes derived Markdown exports (`context/` and `docs/db-export/`) after verifying SQLite is sufficient.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `workspace` | string | No | Workspace name (defaults to active) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "verified": true,
  "deleted_context": 12,
  "deleted_docs": 5
}
```

**Error response** (if DB incomplete):
```json
{
  "workspace": "pixelcore",
  "error": "DB incompleta para limpiar exports",
  "verified": false,
  "node_count": 3,
  "minimum_required": 10
}
```

**When to use:** After verifying the DB is complete and you want to clean up redundant Markdown exports.

---

### 18. workspace_verify_db_completeness

**Description:** Audits whether `workspace.db` has sufficient nodes before cleaning exports or legacy.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `workspace` | string | No | Workspace name (defaults to active) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "verified": true,
  "node_count": 42,
  "has_index": true,
  "has_nodes": true
}
```

**When to use:** Pre-flight check before destructive operations like cleaning exports or removing legacy.

---

### 19. workspace_claim_task

**Description:** Registers in events that an agent is taking a task for parallel work coordination.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `agent_id` | string | **Yes** | Agent identifier |
| `description` | string | **Yes** | Brief task description |
| `workspace` | string | No | Workspace name (defaults to active) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "event": {
    "id": 15,
    "type": "task_claimed",
    "agent_id": "agent-42",
    "description": "Implementing login flow",
    "timestamp": "2026-01-15T10:30:00Z"
  }
}
```

**When to use:** Multi-agent coordination where multiple agents might compete for the same task. Call before starting work on a shared task.

---

### 20. workspace_complete_task

**Description:** Registers in events that a task claimed by an agent has finished.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `event_id` | integer | **Yes** | ID from `workspace_claim_task` event |
| `agent_id` | string | **Yes** | Agent identifier |
| `result` | string | **Yes** | Completion result or summary |
| `workspace` | string | No | Workspace name (defaults to active) |

**Returns:**
```json
{
  "workspace": "pixelcore",
  "event": {
    "id": 15,
    "type": "task_completed",
    "agent_id": "agent-42",
    "result": "Login flow implemented successfully",
    "timestamp": "2026-01-15T11:45:00Z"
  }
}
```

**When to use:** Finishing a claimed task, releasing it for others or marking completion.

---

## Cache Invalidation

### `_check_for_changes()` — How It Works

The plugin monitors modification times of workspace database files to detect when the cached prompt block needs rebuilding:

```python
def _check_for_changes(self) -> bool:
    watched = self._watched_stores()
    current = {workspace: store.db_mtime() for workspace, store in watched}
    if current != self._watched_mtimes:
        return True
    return False
```

**What it monitors:**
- Returns `True` (invalidated) when any watched workspace's `workspace.db` has a different mtime than stored in `_watched_mtimes`

**Watched stores by mode:**
- `index` mode: Only the active workspace
- `all-indexes` mode: All discovered workspaces
- `full` mode: Only the active workspace

**Limitation:**
> **Does NOT detect file deletions.** The mtime check only fires on writes/updates. If a database file is deleted, the cached block remains until the next successful write triggers a new mtime.

### `_rebuild_block()` — Rebuild Logic

When `system_prompt_block()` is called:
1. Checks if `_cached_block` is None OR `_check_for_changes()` returns True
2. If so, calls `_rebuild_block()`:
   - Fetches the appropriate nodes (index node, all indexes, or all nodes)
   - Renders each as Markdown
   - Joins with `\n\n---\n\n`
   - Truncates to `max_chars`
   - Stores in `_cached_block` and updates `_watched_mtimes`

---

## Path Security

### `_sanitize_rel_path()` — Path Traversal Prevention

```python
def _sanitize_rel_path(rel_path: str) -> Optional[str]:
    rel_path = rel_path.strip().strip("/")
    if not rel_path or rel_path.startswith("/") or ".." in Path(rel_path).parts:
        return None
    return rel_path
```

**Security checks applied:**
1. Strips leading/trailing whitespace
2. Strips leading `/` (no absolute paths)
3. Rejects empty strings
4. Rejects paths containing `..` (parent directory traversal)

**Returns:** The sanitized relative path, or `None` if any check fails.

**Additional enforcement in tools:**
After sanitization, tools perform a second check:
```python
target.resolve().relative_to(workspace_root.resolve())
```
This confirms the final resolved path is still within the workspace root, catching any remaining traversal attempts.

### Tools Using Path Sanitization

| Tool | Path Parameter | Sanitization Method |
|------|---------------|---------------------|
| `workspace_list_folder` | `folder` | `_sanitize_rel_path()` + `relative_to()` check |
| `workspace_read_workspace_file` | `path` | `_sanitize_rel_path()` + `relative_to()` check |

---

## Tool Call Routing

The `handle_tool_call()` method dispatches to the appropriate handler using a series of `if` statements. The routing is linear and deterministic.

### Routing Flow

```
handle_tool_call(tool_name, args)
    |
    +-- "workspace_list_workspaces" --> list_workspaces() (no workspace needed)
    |
    +-- _resolve_workspace(args) --> (workspace, store)
    |
    +-- "workspace_list_files" --> store.list_context_nodes()
    +-- "workspace_read_file" --> store.get_node(filename) [with legacy validation]
    +-- "workspace_list_folder" --> _list_folder(workspace_root, folder)
    +-- "workspace_read_workspace_file" --> read_file() [with sanitization]
    +-- "workspace_get_node" --> store.get_node(ref)
    +-- "workspace_search_nodes" --> store.search_nodes(query, limit, kind)
    +-- "workspace_upsert_node" --> store.upsert_node(...)
    +-- "workspace_link_nodes" --> store.link_nodes(...)
    +-- "workspace_create_project" --> store.create_project(...)
    +-- "workspace_export_markdown" --> store.sync_markdown_exports()
    +-- "workspace_clean_exports" --> verify + clean_exports()
    +-- "workspace_verify_db_completeness" --> store.verify_db_completeness()
    +-- "workspace_migrate_legacy" --> store.migrate_legacy_to_db()
    +-- "workspace_list_all_nodes" --> store.list_all_nodes()
    +-- "workspace_list_edges" --> store.list_edges()
    +-- "workspace_list_events" --> store.list_events() [with limit clamp]
    +-- "workspace_scan_artifacts" --> store.scan_artifacts()
    +-- "workspace_claim_task" --> store.claim_task(agent_id, description)
    +-- "workspace_complete_task" --> store.complete_task(event_id, agent_id, result)
    |
    +-- (unknown) --> {"error": f"Tool desconocido: {tool_name}"}
    |
    +-- (exception) --> {"error": str(exc)} [logged]
```

### Workspace Resolution Pattern

Most tools follow this pattern:
```python
workspace, store = self._resolve_workspace(args)
workspace_root = self._workspace_root(workspace)
```

`resolve_workspace` defaults to the active workspace if none specified:
```python
def _resolve_workspace(self, args: Dict[str, Any]) -> tuple[str, WorkspaceStore]:
    workspace = args.get("workspace") or self._active_workspace()
    return workspace, self._ensure_store(workspace)
```

---

## Initialization

### `initialize()` — What Happens

```python
def initialize(self, session_id: str, **kwargs) -> None:
    hermes_home = kwargs.get("hermes_home")
    if not hermes_home:
        from hermes_constants import get_hermes_home
        hermes_home = str(get_hermes_home())
    self._hermes_home = hermes_home
    self._ensure_store(self._active_workspace())
    if self._inject_mode() == "all-indexes":
        for workspace in self._workspace_names():
            self._ensure_store(workspace)
    self._rebuild_block()
```

**Step-by-step:**

1. **Resolve `hermes_home`**
   - From `kwargs.get("hermes_home")` if provided
   - Otherwise from `hermes_constants.get_hermes_home()`

2. **Store `hermes_home`** in `self._hermes_home` for later path operations

3. **Ensure active workspace store**
   - Calls `_ensure_store(active_workspace)`
   - Which calls `WorkspaceStore(workspace_root)`
   - If DB doesn't exist: `store.migrate_from_markdown(force=False)`
   - If DB exists: `store.ensure_schema()`

4. **For `all-indexes` mode: ensure ALL workspace stores**
   - Discovers all workspaces via `_workspace_names()`
   - Calls `_ensure_store()` for each

5. **Build the initial cached block**
   - Calls `_rebuild_block()`
   - Which renders nodes, truncates, and stores in `_cached_block`
   - Also populates `_watched_mtimes` for change detection

### Store Ensurance Pattern

```python
def _ensure_store(self, workspace: str) -> WorkspaceStore:
    store = WorkspaceStore(self._workspace_root(workspace))
    if not store.exists():
        store.migrate_from_markdown(force=False)
    else:
        store.ensure_schema()
    return store
```

This lazy initialization pattern:
- Migrates Markdown to DB on first access (if no DB exists)
- Ensures schema is current (runs migrations if needed)
- Returns the ready-to-use store

---

## Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `DEFAULT_WORKSPACE` | `"doyouwin"` | Fallback workspace name |
| `DEFAULT_INJECT_MODE` | `"index"` | Fallback inject mode |
| `DEFAULT_MAX_CHARS` | `8000` | Default truncation limit |
| `MAX_PREFETCH_NODES` | `5` | Maximum nodes to prefetch per query |

---

## Summary

The workspace-context plugin provides a complete DB-first nodal memory system for Hermes:

- **Injection modes** control how much context appears in the system prompt
- **Prefetch system** pre-loads relevant nodes with cross-workspace normalization
- **20 tools** cover the full nodal lifecycle (CRUD, search, link, coordinate)
- **Path security** prevents traversal attacks on file operations
- **Cache invalidation** keeps the prompt block current via mtime monitoring
- **Change tracking** triggers block rebuilds automatically

The plugin is registered via the standard `register(ctx)` function and activated through Hermes configuration with `memory.provider: workspace-context`.
