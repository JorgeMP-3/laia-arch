# Hermes Context Engine — Master Index

**Version:** 1.0.0 | **Schema:** DB-first (SQLite) | **Source:** `workspace.db`

The Hermes Context Engine is a DB-first nodal memory system. SQLite databases serve as the single source of truth for workspace knowledge, replacing legacy markdown-based documentation. Full-text search, node relationships, artifact indexing, and multi-agent coordination are all built on top of `WorkspaceStore`.

---

## Part 1: Master Index — Documentation Files

| # | File | Lines | Description | Covers |
|---|------|-------|-------------|--------|
| 01 | `01-workspace-store.md` | 990 | SQLite data layer API | Schema tables, node kinds, edge types, FTS5 config, Python API, migration helpers, export system |
| 02 | `02-plugin.md` | 1046 | Hermes MemoryProvider plugin | 3 inject modes, 20 tools (nodal/compatibility/coordination), prefetch ranking, config schema |
| 03 | `03-web-ui.md` | 1006 | FastAPI + React web interface | Architecture, API endpoints, frontend structure, `api.ts` client, theme, running locally |
| 04 | `04-migration.md` | 723 | Legacy workspace migration | Steps to migrate, backup creation, `code/` structure, DB verification, legacy folder mapping |
| 05 | `05-scripts.md` | 626 | Script ecosystem reference | `create-workspace.py` (all modes), `run-agent.sh`, `run-all-agents.sh`, `doctor.py`, `export-docs.py` |

---

## Part 2: Quick Reference Cards

### DB Schema Quick Ref

**Tables**

| Table | Purpose |
|-------|---------|
| `workspace_meta` | Key-value metadata (`schema_version`, `workspace_name`, `updated_at`, `last_export_at`, `last_organized_export_at`) |
| `nodes` | All nodal content — title, slug, kind, content, artifact path, timestamps, FTS5 body |
| `edges` | Relationships between nodes — `from_id`, `to_id`, `edge_type` |
| `artifacts` | File inventory for `code/` — path, name, size, hash, MIME type |
| `events` | Multi-agent task log — agent_id, description, status, timestamps |

**Node Kinds**

| Kind | Prefix | Example Slug |
|------|--------|--------------|
| `index` | — | `00-index` |
| `area` | `NN-` | `01-area-proyectos` |
| `topic` | `NN-` | `02-topic-arquitectura` |
| `detail` | `NNa-` | `02a-detail-api-rest` |
| `doc` | — | slug-based |
| `script` | — | slug-based |
| `task` | — | slug-based |
| `artifact` | — | slug-based |

**Edge Types**

| Type | Direction | Use |
|------|-----------|-----|
| `contains` | parent → child | Area/topic contains detail or doc |
| `links` | any → any | Cross-reference between nodes |
| `next` | prev → next | Sequence/ordering |
| `started` | agent → task | Agent claimed a task |
| `completed` | agent → task | Agent finished a task |
| `updated` | agent → node | Agent modified a node |
| `imported_from` | node → file | Node was migrated from a file |

**FTS5 Configuration**

- Virtual table: `nodes_fts` on `title`, `slug`, `content`
- `tokenize = 'unicode61 remove_diacritics 1'`
- Rank: `bm25(nodes_fts)` for relevance scoring
- Prefix indexes: 2 and 3-character prefixes for autocomplete

---

### Plugin Quick Ref

**3 Inject Modes**

| Mode | Behavior |
|------|----------|
| `index` (default) | Injects only the root `index` node into system prompts |
| `all-indexes` | Injects all `index`-kind nodes across all configured workspace stores |
| `full` | Injects all nodes up to `max_chars` limit, ranked by prefetch formula |

**20 Tools Grouped by Purpose**

*Nodal (core DB operations)*

| Tool | Purpose |
|------|---------|
| `workspace_search_nodes` | FTS5 search across node title/slug/content |
| `workspace_get_node` | Read a single node by slug, filename, or ID |
| `workspace_upsert_node` | Create or update a node in `workspace.db` |
| `workspace_link_nodes` | Create an edge between two nodes |
| `workspace_list_nodes` | List nodes filtered by kind, area, or parent |
| `workspace_delete_node` | Remove a node (does not cascade to children) |
| `workspace_list_events` | List all agent task events |
| `workspace_claim_task` | Mark a task as in-progress by an agent |
| `workspace_complete_task` | Mark a task as completed by an agent |
| `workspace_get_stats` | Return workspace statistics |

*Compatibility (legacy filesystem access)*

| Tool | Purpose |
|------|---------|
| `workspace_list_files` | List files in workspace root (legacy `context/`, `docs/`, etc.) |
| `workspace_read_file` | Read any file in workspace by path |
| `workspace_search_files` | Grep/regex search across workspace files |
| `workspace_list_folder` | List directory contents |
| `workspace_write_file` | Write a file to `code/` |

*New / Coordination*

| Tool | Purpose |
|------|---------|
| `workspace_export_markdown` | Export nodes to `context/*.md` on demand |
| `workspace_create_project` | Create a project subtree with README, docs, references |
| `workspace_scan_artifacts` | Re-scan `code/` and update the `artifacts` table |
| `workspace_read_workspace_file` | Read a file relative to workspace root |
| `workspace_get_path` | Return the resolved absolute path to `workspaces/{name}/` |

**Prefetch Ranking Formula (for `full` inject mode)**

```
relevance = bm25(nodes_fts) 
          + (5 × contains_keyword)        // node kind matches query domain
          + (3 × updated_recently)        // touched in last 7 days
          + (2 × has_outgoing_edges)      // is hub/connector node
          + (1 × is_index_or_area)        // structural anchor nodes
```

Result is sorted descending; top-N nodes selected until `max_chars` (default 8000) is reached.

---

### Web UI Quick Ref

**Ports**

| Service | Port |
|---------|------|
| Backend (FastAPI) | `8077` |
| Frontend dev (Vite) | `5173` |
| Production | Served as static files by FastAPI |

**API Endpoints Grouped by Type**

*Health & Config*

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/workspaces` | GET | List available workspaces |
| `/api/workspaces/{ws}` | GET | Get workspace metadata |

*Nodes*

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/nodes` | GET | List/search nodes |
| `/api/nodes/{id}` | GET | Get single node |
| `/api/nodes` | POST | Create node |
| `/api/nodes/{id}` | PUT | Update node |
| `/api/nodes/{id}` | DELETE | Delete node |
| `/api/nodes/{id}/edges` | GET | Get edges from a node |

*Edges*

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/edges` | GET | List edges |
| `/api/edges` | POST | Create edge |
| `/api/edges/{id}` | DELETE | Delete edge |

*Artifacts & Events*

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/artifacts` | GET | List artifacts |
| `/api/events` | GET | List events |
| `/api/stats` | GET | Workspace statistics |

*Export*

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/export` | GET | Export full workspace to JSON |
| `/api/export/markdown` | POST | Trigger markdown export |

**UI Pages**

| Route | Component | Purpose |
|-------|-----------|---------|
| `/` | Dashboard | Workspace overview, recent activity |
| `/graph` | GraphView | Interactive node graph (React Flow) |
| `/nodes` | NodeBrowser | Searchable node list |
| `/nodes/:id` | NodeDetail | Single node view + edit |
| `/export` | ExportView | Markdown export controls |

**Theme Colors**

| Token | Value | Use |
|-------|-------|-----|
| `--bg-primary` | `#0a0e17` | Main background |
| `--bg-secondary` | `#111827` | Cards, panels |
| `--accent` | `#38bdf8` | Links, highlights |
| `--accent-secondary` | `#818CF8` | Secondary actions |
| `--text-primary` | `#F9FAFB` | Main text |
| `--text-secondary` | `#9CA3AF` | Muted text |
| `--border` | `#1F2937` | Borders, dividers |
| `--success` | `#22C55E` | Success states |
| `--warning` | `#F59E0B` | Warning states |
| `--error` | `#EF4444` | Error states |

---

### Migration Quick Ref

**Migration Steps**

```
1. scan_workspace()       → Detect legacy folders (context/, agents/, docs/, projects/, scripts/)
2. import_nodes()         → Parse all context/*.md files into nodes table
3. move_code()            → Copy scripts/ and project code → code/scripts/ and code/projects/
4. create_backup()        → tar.gz archive at {backup-root}/{workspace}-{timestamp}.tar.gz
5. verify_db()            → Compare node count, edge count, artifact count vs expected
6. cleanup()              → Remove legacy folders only after verify_db passes
```

**Backup Location**

- Default: `~/.hermes/backups/`
- Custom: `--backup-root <path>` flag
- Filename format: `{workspace_name}-{YYYYMMDD-HHMMSS}.tar.gz`

**What Gets Moved to `code/`**

| Legacy Location | New Location |
|-----------------|---------------|
| `scripts/` | `code/scripts/` |
| `projects/{name}/` | `code/projects/{name}/` |
| `docs/` (non-reference) | `code/docs/` |
| `agents/log.md`, `team.md`, `behavior.md` | `code/agents/` |

**What Becomes Nodes (DB entries)**

| Legacy | Becomes |
|--------|---------|
| `context/00-index.md` | `index` kind node, slug `00-index` |
| `context/NN-*.md` | `area` or `topic` kind node |
| `context/NNa-*.md` | `detail` kind node |
| Any `.md` in `context/` | `doc` kind node |
| Any `.py`/`.sh`/`.js` in `scripts/` | `artifact` entries (not nodes) |

---

### Scripts Quick Ref

| Script | Purpose | Key Flags |
|--------|---------|-----------|
| `create-workspace.py` | Create, edit, repair, migrate workspaces | `--name`, `--activate`, `--restart`, `--repair`, `--migrate-legacy`, `--force-import`, `--keep-legacy`, `--backup-root`, `--no-archive` |
| `run-agent.sh` | Execute a single agent with workspace context | `AGENT_NAME`, `WORKSPACE` env vars |
| `run-all-agents.sh` | Launch all agents in sequence | `WORKSPACE` env var |
| `doctor.py` | Diagnose Hermes system health | `--verbose`, `--fix` |
| `export-docs.py` | Export workspace to markdown | `--workspace`, `--output`, `--format` |

---

## Part 3: Cross-Reference Table

| Topic | Files | Where |
|-------|-------|-------|
| **FTS5 search** | 01-workspace-store.md, 02-plugin.md | Schema config + `workspace_search_nodes` tool |
| **Node kinds** | 01-workspace-store.md, 04-migration.md | Full list + legacy mapping |
| **Edge types** | 01-workspace-store.md | Full list with descriptions |
| **Export Markdown** | 01-workspace-store.md, 02-plugin.md, 03-web-ui.md | Python API + `workspace_export_markdown` tool + `/api/export/markdown` |
| **Prefetch ranking** | 02-plugin.md | Formula under "Prefetch Ranking" |
| **Migration** | 04-migration.md, 05-scripts.md | Steps + `create-workspace.py --migrate-legacy` |
| **Clean exports** | 01-workspace-store.md | "Export System" section |
| **Artifact indexing** | 01-workspace-store.md, 02-plugin.md, 05-scripts.md | `artifacts` table + `workspace_scan_artifacts` tool |
| **Multi-agent coordination** | 01-workspace-store.md, 02-plugin.md, 05-scripts.md | `events` table + claim/complete tools |
| **Web UI API** | 03-web-ui.md | Full endpoint table |
| **Plugin config** | 02-plugin.md | `inject_mode`, `max_chars`, `workspace` keys |
| **Schema version** | 01-workspace-store.md | `workspace_meta.schema_version` |
| **Backup / archive** | 04-migration.md, 05-scripts.md | `create_backup()` + `--backup-root` |
| **code/ structure** | 04-migration.md, SOUL.md | What goes where after migration |
| **Legacy folders** | 04-migration.md | `context/`, `agents/`, `docs/`, `projects/`, `scripts/` |
| **DB verification** | 04-migration.md | `verify_db()` step |

---

## Part 4: Skill and SOUL References

**Operational Guidance Locations**

| Document | Purpose | Path |
|----------|---------|------|
| **SOUL.md** (lines 61-79) | Agent workspace context contract — mandatory tool order | `/Users/servidor_jmp/.hermes/SOUL.md` |
| **workspace-daily skill** | Daily usage guide — search/read/update workflow, multi-agent tips, migration command | `/Users/servidor_jmp/.hermes/skills/workspace-daily/SKILL.md` |
| **context-engine skill** | Technical reference — plugin architecture, full tool list, prefetch formula | `/Users/servidor_jmp/.hermes/skills/context-engine/SKILL.md` |
| **workspace-doc.md** | Per-workspace integration documentation prompt | `workspaces/{name}/workspace-doc.md` |
| **CLAUDE.md** | Per-workspace agent instructions | `workspaces/{name}/CLAUDE.md` |

**SOUL.md Core Mandate (workspace section)**

> When a workspace is active, work DB-first. `workspace.db` is source of truth; `context/*.md` is a derived export.
> 
> **Mandatory order when needing context:**
> 1. `workspace_search_nodes`
> 2. `workspace_get_node`
> 3. `workspace_upsert_node` / `workspace_link_nodes`
> 4. `workspace_list_folder` / `workspace_read_workspace_file`
> 5. `workspace_read_file` / `workspace_list_files` — compatibility only
> 
> Do **not** use `search_files` or `session_search` for workspace questions.
> Do **not** start with `context/*.md` or `docs/db-export/`.

---

## Part 5: File Locations Reference

**Core Module**

| Component | Path |
|-----------|------|
| WorkspaceStore (Python) | `/Users/servidor_jmp/.hermes/workspace_store/__init__.py` |
| Schema version | Line 5 of above — `SCHEMA_VERSION = 1` |

**Plugin**

| Component | Path |
|-----------|------|
| Plugin entry point | `/Users/servidor_jmp/.hermes/plugins/workspace-context/__init__.py` |
| Plugin config schema | `/Users/servidor_jmp/.hermes/plugins/workspace-context/plugin.yaml` |
| Provider class | `WorkspaceContextProvider` in above |
| 20 tools | Defined in plugin `get_tools()` |

**Web UI**

| Component | Path |
|-----------|------|
| FastAPI backend | `/Users/servidor_jmp/.hermes/workspace-ui/backend/main.py` |
| Frontend API client | `/Users/servidor_jmp/.hermes/workspace-ui/frontend/src/lib/api.ts` |
| React app entry | `/Users/servidor_jmp/.hermes/workspace-ui/frontend/src/main.tsx` |
| Theme/styling | `/Users/servidor_jmp/.hermes/workspace-ui/frontend/src/index.css` |

**Scripts**

| Script | Path |
|--------|------|
| create-workspace | `/Users/servidor_jmp/.hermes/scripts/create-workspace.py` |
| run-agent | `/Users/servidor_jmp/.hermes/scripts/run-agent.sh` |
| run-all-agents | `/Users/servidor_jmp/.hermes/scripts/run-all-agents.sh` |
| doctor | `/Users/servidor_jmp/.hermes/scripts/doctor.py` |
| export-docs | `/Users/servidor_jmp/.hermes/scripts/export-docs.py` |
| All scripts dir | `/Users/servidor_jmp/.hermes/scripts/` |

**Skills**

| Skill | Path |
|-------|------|
| workspace-daily | `/Users/servidor_jmp/.hermes/skills/workspace-daily/SKILL.md` |
| context-engine | `/Users/servidor_jmp/.hermes/skills/context-engine/SKILL.md` |

**Config**

| File | Path |
|------|------|
| Main config | `/Users/servidor_jmp/.hermes/config.yaml` |
| Active workspace key | `plugins.workspace-context.workspace` |
| Inject mode key | `plugins.workspace-context.inject_mode` |

**Workspace Storage**

| Resource | Path |
|----------|------|
| All workspaces | `/Users/servidor_jmp/.hermes/workspaces/` |
| Per-workspace DB | `/Users/servidor_jmp/.hermes/workspaces/{name}/workspace.db` |
| Per-workspace code | `/Users/servidor_jmp/.hermes/workspaces/{name}/code/` |
| Backups | `/Users/servidor_jmp/.hermes/backups/` (or custom `--backup-root`) |

**Documentation**

| Doc | Path |
|-----|------|
| This index | `/Users/servidor_jmp/.hermes/docs/context-engine/00-index.md` |
| WorkspaceStore | `/Users/servidor_jmp/.hermes/docs/context-engine/01-workspace-store.md` |
| Plugin | `/Users/servidor_jmp/.hermes/docs/context-engine/02-plugin.md` |
| Web UI | `/Users/servidor_jmp/.hermes/docs/context-engine/03-web-ui.md` |
| Migration | `/Users/servidor_jmp/.hermes/docs/context-engine/04-migration.md` |
| Scripts | `/Users/servidor_jmp/.hermes/docs/context-engine/05-scripts.md` |

---

*Last updated: 2026-04-24 | Hermes Context Engine v1.0.0*
