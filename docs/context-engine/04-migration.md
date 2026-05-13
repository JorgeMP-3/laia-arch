# Migration System — Legacy to DB-First Model

**Chapter 4 of the Hermes Context Engine documentation**

---

## Overview

The Hermes Context Engine evolved from a pure filesystem model (Markdown files in `context/`, `agents/`, `projects/`, etc.) to a **DB-first model** where SQLite (`workspace.db`) is the single source of truth, and Markdown exports are derived on demand.

The migration system handles the transition: it scans the old workspace structure, imports all content into the DB, moves code artifacts to `code/` and `code/scripts/`, creates a backup archive, and verifies the DB is complete before removing legacy folders.

---

## 1. Legacy Workspace Structure (Before Migration)

Before migration, a legacy workspace had the following filesystem layout:

```
workspace-name/
├── README.md                    # Workspace index/overview
├── context/                     # Node Markdown files (the core knowledge base)
│   ├── 00-index.md              # Root index node
│   ├── 01-topic-architecture.md # Topic-level nodes (prefix: NN-)
│   └── 01a-detail-something.md   # Detail-level nodes (prefix: NNa-)
├── docs/                        # Documentation
│   ├── references/              # Reference documents
│   └── *.md                     # General docs
├── agents/                      # Agent-related documents
│   ├── log.md                   # Agent activity log
│   ├── team.md                  # Team coordination notes
│   └── behavior.md             # Agent behavior guidelines
├── projects/                    # Project folders (each is a subdirectory)
│   ├── api-v2/                  # Named project
│   │   ├── README.md            # or info.md or 00-index.md
│   │   ├── docs/
│   │   └── references/
│   └── landing-page/
│       └── ...
├── scripts/                     # Build/deploy/tool scripts
│   ├── build.sh
│   ├── deploy.py
│   └── tools/
│       └── ...
└── workspace.db                 # (may or may not exist yet)
```

### Folder Purposes

| Folder | Purpose |
|--------|---------|
| `context/` | Node Markdown files forming the knowledge graph |
| `docs/` | Reference and general documentation |
| `agents/` | Agent logs, team notes, behavior docs |
| `projects/` | Project subdirectories with their own docs/refs |
| `scripts/` | Shell scripts, Python tools, build utilities |

### File Classification

The migration distinguishes between **content** and **code**:

- **Content (imported as nodes):** `.md` files (Markdown)
- **Code (moved to code/):** `.py`, `.sh`, `.js`, `.ts`, or any non-Markdown file

---

## 2. Migration Process — `migrate_legacy_to_db()`

The main entry point is `WorkspaceStore.migrate_legacy_to_db()`. It performs a sequenced migration with verification gates.

### Flow Diagram

```
migrate_legacy_to_db()
│
├── 1. ensure_schema()            # Create DB if needed
├── 2. seed index node            # Ensure root index exists
│
├── 3. Scan legacy_paths          # README.md, context/, agents/, docs/, projects/, scripts/
│   │
│   ├── For each path that exists:
│   │   └── archive to backup_root/{workspace}-{timestamp}.tar.gz
│   │
├── 4. Import README.md           # As doc node, link: index → references
│   │
├── 5. Import context/*.md        # Each .md → node with kind inferred from filename
│   │   └── Link: index → details (unless kind=index)
│   │
├── 6. Import agents/**/*.md       # Each .md → agent-note node
│   │   └── Link: index → contains
│   │
├── 7. Import docs/**/*.md        # Each .md → doc or reference node
│   │   └── Link: index → references
│   │
├── 8. Import projects/*/         # Each project dir → project node
│   │   ├── Look for info.md / README.md / 00-index.md inside
│   │   ├── .md files inside → doc nodes linked to project
│   │   ├── Non-.md files → moved to code/{project_name}/
│   │   └── Link: index → project_of
│   │
├── 9. Import scripts/            # Scripts folder
│   │   ├── .md files → script nodes linked to index
│   │   └── Non-.md files → moved to code/scripts/
│   │
├── 10. verify_db_completeness()  # Safety gate
│   │
├── 11. IF verified AND remove_legacy:
│   │   └── Delete legacy folders (context/, agents/, docs/, projects/, scripts/, README.md)
│   │
├── 12. scan_artifacts()          # Index all files under code/
│   │
├── 13. generate_workspace_doc()  # Create workspace-doc.md
│   │
└── 14. generate_claude_md()      # Create CLAUDE.md
```

### Step-by-Step Details

#### Step 1-2: Schema & Index Bootstrap

```python
self.ensure_schema()  # Creates workspace.db, tables, FTS index
index_node = self.get_index_node()
if index_node is None:
    index_node = self.seed_workspace(f"Workspace {self.workspace}.", [])["index"]
```

The index node is the root of the knowledge graph. If no legacy content exists, a minimal seed index is created.

#### Step 3: Backup Creation

Before touching anything, existing legacy paths are archived:

```python
legacy_paths = [
    self.root / "README.md",
    self.root / "context",
    self.root / "agents",
    self.root / "docs",
    self.root / "projects",
    self.root / "scripts",
]
existing_legacy = [path for path in legacy_paths if path.exists()]
backup_path = self._archive_legacy_paths(existing_legacy, backup_root=backup_root)
```

The archive is a `.tar.gz` stored in `{hermes_root}/backups/legacy-workspaces/` (or a custom `backup_root`).

#### Step 4-8: Content Import

Each legacy folder is scanned and its contents migrated:

**README.md:**
```python
node = self._import_markdown_node(readme_path, slug="readme", kind="doc", source_kind="legacy-readme")
self.link_nodes(index_node["id"], node["id"], "references")
```

**context/*.md:**
```python
for md_file in sorted(context_dir.glob("*.md")):
    if md_file.name.startswith("."):
        continue
    node = self._import_markdown_node(
        md_file,
        slug=_slugify(md_file.stem),
        kind=_infer_kind_from_filename(md_file.name),  # index/topic/detail/project
        source_kind="legacy-context",
        filename=md_file.name,
    )
    if node["kind"] != "index":
        self.link_nodes(index_node["id"], node["id"], "details")
```

**agents/**/*.md:**
```python
for md_file in sorted(agents_dir.rglob("*.md")):
    node = self._import_markdown_node(
        md_file,
        slug=f"agent-{_slugify(str(rel.with_suffix('')))}",
        kind="agent-note",
        source_kind="legacy-agents",
    )
    self.link_nodes(index_node["id"], node["id"], "contains")
```

**docs/**/*.md:**
```python
for md_file in sorted(docs_dir.rglob("*.md")):
    if "db-export" in md_file.relative_to(docs_dir).parts:
        continue  # Skip derived exports
    kind = "reference" if "references" in rel.parts else "doc"
    node = self._import_markdown_node(...)
    self.link_nodes(index_node["id"], node["id"], "references")
```

**projects/*/:**
```python
for project_dir in sorted(projects_dir.iterdir()):
    project_slug = f"project-{_slugify(project_dir.name)}"
    # Find info file
    info_path = next((p for p in [project_dir / "README.md", project_dir / "info.md", ...] if p.exists()), None)
    # Create project node
    project = self.upsert_node(slug=project_slug, kind="project", ...)
    # Migrate .md files inside project
    for md_file in sorted(project_dir.rglob("*.md")):
        node = self._import_markdown_node(...)
        self.link_nodes(project["id"], node["id"], "contains")
    # Move non-.md files to code/
    for path in sorted(project_dir.rglob("*")):
        if path.is_file() and path.suffix != ".md":
            target = self.root / "code" / project_dir.name / path.relative_to(project_dir)
            self._move_legacy_file(path, target)
```

**scripts/:**
```python
for path in sorted(scripts_dir.rglob("*")):
    if path.suffix == ".md":
        # Script documentation → script node
        node = self._import_markdown_node(...)
        self.link_nodes(index_node["id"], node["id"], "contains")
    else:
        # Code → code/scripts/
        target = self.root / "code" / "scripts" / rel
        self._move_legacy_file(path, target)
```

#### Step 9: Determining Node Kind from Filename

The function `_infer_kind_from_filename()` maps filenames to node kinds:

```python
def _infer_kind_from_filename(name: str) -> str:
    if name == "00-index.md":
        return "index"          # Root index
    stem = name[:-3] if name.endswith(".md") else name
    if re.match(r"^\d{2}[a-z]-", stem):
        return "detail"         # e.g., "01a-architecture.md"
    if re.match(r"^\d{2}-", stem):
        return "topic"          # e.g., "01-architecture.md"
    if stem.startswith("project-"):
        return "project"
    return "detail"             # Default
```

#### Step 10: Title Extraction

Title is extracted from the first `# Heading` line using a regex:

```python
TITLE_RE = re.compile(r"^\s*#\s+(.+?)\s*$")

title_match = TITLE_RE.match(content.splitlines()[0])
title = title_match.group(1).strip() if title_match else _humanize_slug(md_file.stem)
```

If no `#` heading is found, the title is humanized from the filename stem (e.g., `api-architecture.md` → "Api Architecture").

#### Step 11: Navigation Indicators → Edges

During import, navigation indicators in Markdown are parsed into edges. The regex:

```python
INDICATOR_RE = re.compile(r"^[\-\s]*[→>-]+\s*(.+?):\s*`?([\w\-.]+\.md)`?\s*$", re.UNICODE)
```

Example indicators that become edges:
```
→ Arquitectura: `02-architecture.md`
→ Detalles: `02a-details.md`
```

For `migrate_legacy_to_db()`, indicators are stripped from the body but are **not** re-imported as edges (since the graph structure is already created through explicit `link_nodes()` calls). However, for `migrate_from_markdown()`, pending indicators are resolved:

```python
for source_slug, indicators in pending_edges:
    for _, target_name in indicators:
        target_node = self.get_node(target_name)
        if target_node is None:
            continue
        self.link_nodes(source_slug, target_node["id"], "details")
```

#### Step 12: Code Movement

Non-Markdown files are moved from legacy locations to the `code/` hierarchy:

```
legacy projects/api-v2/src/main.py  →  code/api-v2/src/main.py
legacy scripts/deploy.sh            →  code/scripts/deploy.sh
```

Files are moved with `shutil.move()`. If a target already exists, the file is **skipped** (not overwritten).

#### Step 13: DB Completeness Verification

Before deleting legacy files, `verify_db_completeness()` is called. If it returns `verified=False`, legacy files are **preserved** (not deleted).

See Section 8 for full details.

#### Step 14: Post-Migration Generation

After migration:
```python
self.scan_artifacts()              # Index all files under code/
generated = [
    self.generate_workspace_doc(), # Creates workspace-doc.md
    self.generate_claude_md(),     # Creates CLAUDE.md
]
```

---

## 3. Source Kind Values

Every node has a `source_kind` field indicating how it entered the DB:

| source_kind | Description |
|-------------|-------------|
| `markdown-import` | Content migrated from `.md` files via `migrate_from_markdown()` |
| `legacy-context` | Imported from `context/*.md` during `migrate_legacy_to_db()` |
| `legacy-agents` | Imported from `agents/**/*.md` during legacy migration |
| `legacy-docs` | Imported from `docs/**/*.md` during legacy migration |
| `legacy-projects` | Imported from `projects/*/` during legacy migration |
| `legacy-readme` | Imported from `README.md` during legacy migration |
| `legacy-scripts` | Imported from `scripts/*.md` during legacy migration |
| `project-import` | Project folders migrated via `migrate_from_markdown()` |
| `seed` | Created by `seed_workspace()` for new DB-first workspaces |
| `manual` | Created by user/tool via `workspace_upsert_node()` |
| `tool` | Created via `workspace_upsert_node()` from tool calls |
| `interactive` | Created during interactive editing in `create-workspace.py` |
| `project-create` | Created via `create_project()` |

The `source_kind` field is immutable in the current implementation (upserts do not change it). It serves as a record of provenance.

---

## 4. Backup System

### How the Backup is Created

When `migrate_legacy_to_db()` is called with `archive=True` (the default), all existing legacy paths are gathered and archived **before** any import begins:

```python
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
```

### Where Backups Are Stored

- **Default location:** `{hermes_root}/backups/legacy-workspaces/`
- **Custom location:** `backup_root` argument passed to `migrate_legacy_to_db()`

The workspace parent hierarchy is used to determine `hermes_root`:
```python
hermes_root = self.root.parent.parent if self.root.root.name == "workspaces" else self.root.parent
```
This means for a workspace at `~/.hermes/workspaces/my-workspace/`, the backup goes to `~/.hermes/backups/legacy-workspaces/`.

### Backup Filename Format

```
{workspace-name}-{ISO8601-timestamp}.tar.gz
Example: mi-proyecto-20260424T143052Z.tar.gz
```

### What the Backup Contains

The `.tar.gz` contains the original legacy files and folders, stored by their leaf name (not the full path):

```
my-workspace-20260424T143052Z.tar.gz
├── README.md
├── context/
│   ├── 00-index.md
│   └── ...
├── agents/
├── docs/
├── projects/
└── scripts/
```

### Restoring from Backup

The backup is a standard `.tar.gz` archive. To restore:

```bash
cd ~/.hermes/workspaces/mi-proyecto
tar -xzf ~/.hermes/backups/legacy-workspaces/mi-proyecto-20260424T143052Z.tar.gz
```

**Important:** Restoration overwrites the current state. The DB is NOT automatically restored — you would need to re-run `migrate_legacy_to_db()` after restoring the legacy files.

---

## 5. New Workspace Creation (DB-Only)

When creating a new workspace with `create-workspace.py` or `store.seed_workspace()`, the system is **DB-first from the start** — there is no legacy structure to migrate.

### Folders Created

```python
STANDARD_FOLDERS = ["code", "code/scripts"]
```

The `ensure_workspace_layout()` method creates these directories:

```
workspace-name/
├── code/               # Projects and artifacts
│   └── scripts/        # Utility scripts
└── workspace.db       # Source of truth (created by ensure_schema())
```

**What is NOT created anymore:**
- `context/` (derived on demand via `sync_markdown_exports()`)
- `docs/db-export/` (derived on demand)
- `agents/` (log.md, team.md, behavior.md — no longer a structural requirement)
- `projects/` (now subdirectories of `code/`)
- `scripts/` (now `code/scripts/`)
- `README.md` (replaced by `workspace-doc.md` and `CLAUDE.md`)

### Seed Nodes

`seed_workspace()` creates a minimal starting state:

1. **Index node** (`kind="index"`, slug=`"index"`, filename=`"00-index.md"`):
   - Title: `{workspace-name} — Índice Base`
   - Body includes description and area list
   - `source_kind="seed"`

2. **Topic nodes** for each area (if provided):
   - `kind="topic"`
   - Linked: `index --details--> topic`
   - `source_kind="seed"`

### Generated Files

After seeding, two documentation files are generated:

**`workspace-doc.md`** — Prompt for documenting the workspace:
```
# workspace-doc — {workspace}

Prompt para que una IA documente exhaustivamente este workspace.

## Cuándo usar
Cuando se ha integrado código, creado proyectos, o añadido información
que aún no está reflejada en la base de conocimiento del workspace.
...
```

**`CLAUDE.md`** — AI agent instructions:
```
# {workspace} — Workspace de Hermes

Fuente de verdad: `workspace.db` (SQLite). No uses ni edites context/ ni docs/ si existen.
Código y programas: `code/`

## Herramientas de base de datos
workspace_search_nodes(query), workspace_get_node(ref), ...
```

---

## 6. The Two Export Modes

The DB-first model keeps Markdown files as **derived output**, not source. There are two export modes:

### Mode 1: `context/` — Compact Export

**Location:** `{workspace}/context/`

**Purpose:** One file per node, matching the legacy structure. Compact and readable.

```python
def export_markdown(self) -> dict[str, Any]:
    context_dir = self.root / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    nodes = self.list_context_nodes()  # kind in {index, topic, detail, project}

    for node in nodes:
        filename = node["filename"] or self._default_filename(node)
        path = context_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render_node_markdown(node), encoding="utf-8")
```

**Slug → Filename mapping:**
```python
def _default_filename(self, node: dict[str, Any]) -> str:
    if node["kind"] == "index":
        return "00-index.md"
    return f"{node['slug']}.md"
```

The `filename` alias is set during `upsert_node()` for index and explicit filename cases.

**Edges → Navigation Indicators:**

```python
def _render_indicators(self, node_id: int) -> str:
    rows = conn.execute("""
        SELECT e.edge_type, n.*
        FROM edges e
        JOIN nodes n ON n.id = e.to_node_id
        WHERE e.from_node_id = ?
        ORDER BY edge_type preference order
    """, (node_id,)).fetchall()
    # Output:
    # → Title: `filename.md`
```

Example output in `context/02-architecture.md`:
```markdown
# Arquitectura

Contenido del nodo...

→ Detalles: `02a-details.md`
→ Componentes: `03-components.md`
```

**Cleanup:** Files in `context/` that are not in the current node set are deleted. Empty directories are removed.

### Mode 2: `docs/db-export/` — Organized Export

**Location:** `{workspace}/docs/db-export/`

**Purpose:** Comprehensive organized view with index, relationship tables, metadata per node, and a node directory.

```
docs/db-export/
├── 00-index.md                    # Overview with stats
├── 01-nodes.md                    # All nodes table
├── 02-relations.md                # All edges table
├── 03-events.md                  # Recent events
├── artifacts/
│   ├── 00-index.md               # Artifact groups
│   └── {type}.md                 # Per-type artifact lists
└── nodes/
    ├── 00-index.md               # Node with id=1 (index node)
    ├── topic-slug.md
    └── detail-slug.md
```

**Index file** (`00-index.md`) contains:
- Workspace name, DB path, schema version
- Node/edge/artifact/event counts
- Last export timestamps
- Navigation links to other files

**Node files** contain:
- Full metadata (id, slug, kind, status, filename, parent, source_kind, timestamps, aliases)
- Summary and body
- Outgoing and incoming relations with weights
- Associated artifacts
- Rendered Markdown preview

### Unified Export: `sync_markdown_exports()`

```python
def sync_markdown_exports(self, output_dir: Path | str | None = None) -> dict[str, Any]:
    context_export = self.export_markdown()
    organized_export = self.export_organized_markdown(output_dir=output_dir)
    return {"context": context_export, "organized": organized_export}
```

Both exports are derived from the same DB source. The `docs/db-export/` is always written to the default organized export root unless `output_dir` is specified.

**When to use each:**

| Export | Use Case |
|--------|----------|
| `context/` | Lightweight, legacy-compatible view. Fast. Good for editors that edit Markdown directly. |
| `docs/db-export/` | Comprehensive audit. Full metadata. Good for review, debugging, or exporting to other systems. |

---

## 7. `clean_exports()`

```python
def clean_exports(self) -> dict[str, Any]:
    """Remove derived Markdown exports. SQLite remains the source of truth."""
    targets = [self.root / "context", self.root / "docs" / "db-export"]
```

### What It Removes

1. **`context/` folder** — All `.md` files and subdirectories within `context/`
2. **`docs/db-export/` folder** — The entire organized export tree
3. **`docs/` folder itself** — If it becomes empty after removing `db-export/`

### What It Does NOT Remove

- `workspace.db` — The source of truth
- `code/` or `code/scripts/` — Code artifacts
- `workspace-doc.md` or `CLAUDE.md` — Generated documentation
- Any node or edge data in the DB

### How It Works

```python
for target in targets:
    if target.is_file():
        target.unlink()           # Delete file directly
        continue
    for path in sorted(target.rglob("*"), reverse=True):
        # Delete files first (deepest first)
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            try:
                path.rmdir()      # Remove empty dir
            except OSError:
                pass
    try:
        target.rmdir()             # Remove the root target dir
    except OSError:
        pass
```

The reverse iteration ensures files are deleted before their parent directories.

### When to Call `clean_exports()`

- Before a full re-export to ensure clean state
- When disk space is constrained (exports can be regenerated on demand)
- As part of a workspace "compaction" workflow

---

## 8. DB Completeness Verification

```python
def verify_db_completeness(self) -> dict[str, Any]:
    """Lightweight safety check before deleting derived or legacy files."""
```

### What It Checks

| Check | Requirement |
|-------|-------------|
| `workspace.db` exists | The DB file must be present |
| `node_count > 0` | At least one node must exist |
| `index_count > 0` | At least one node of `kind='index'` must exist |
| `body_count > 0` | At least one node must have non-empty `summary` or `body` |

```python
with self.connect() as conn:
    node_count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()["count"]
    index_count = conn.execute("SELECT COUNT(*) FROM nodes WHERE kind='index'").fetchone()["count"]
    body_count = conn.execute("""
        SELECT COUNT(*) FROM nodes
        WHERE length(trim(summary || body)) > 0
    """).fetchone()["count"]

if node_count == 0:   missing.append("nodes")
if index_count == 0:  missing.append("index")
if body_count == 0:  missing.append("documented_nodes")
```

### Verification Result

```python
{
    "verified": True,           # False if any check failed
    "node_count": 15,
    "missing": [],              # List of failed checks (empty if verified=True)
    "summary": "DB completa para limpieza"
}
```

### Why These Checks?

- **No nodes:** The migration imported nothing — likely a bug or empty workspace.
- **No index:** The graph has no root — navigation will fail.
- **No documented nodes:** All nodes are empty — content was not migrated properly.

### Usage in Migration

```python
verification = self.verify_db_completeness()
removed: list[str] = []
if remove_legacy and verification["verified"]:
    # Safe to delete legacy files
    for path in existing_legacy:
        shutil.rmtree(path)  # or path.unlink()
        removed.append(...)
else:
    # Legacy files preserved — migration incomplete
    pass
```

If `verify_db_completeness()` returns `verified=False`, the legacy files are **preserved**. This prevents data loss if the migration partially fails.

---

## Summary

| Concern | Legacy Model | DB-First Model |
|---------|-------------|----------------|
| Source of truth | Files in `context/` | `workspace.db` (SQLite) |
| Edges stored as | Navigation indicators in Markdown | Explicit edges table |
| Code location | `projects/`, `scripts/` | `code/`, `code/scripts/` |
| Exports | The actual files | Derived on demand |
| Backup | Manual | Automatic `.tar.gz` before migration |
| New workspace | Folder structure | DB + seed nodes |

The migration system ensures a safe, verifiable transition from the legacy filesystem model to the robust DB-first model while preserving all content and providing fallbacks.
