# Workspace UI — Hermes Context Engine

**FastAPI backend + React frontend** for browsing, editing, and visualizing the Hermes knowledge graph.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Backend API](#2-backend-api)
3. [Frontend Structure](#3-frontend-structure)
4. [API Client (`api.ts`)](#4-api-client-apits)
5. [Theme and Styling](#5-theme-and-styling)
6. [Running the UI](#6-running-the-ui)

---

## 1. Architecture Overview

### System Layout

```
Browser (React SPA)
    │
    │  HTTP /api/*  (same-origin, CORS open)
    ▼
FastAPI backend  (port 8077)
    │
    │  WorkspaceStore API
    ▼
SQLite database  (one .db file per workspace at ~/.hermes/workspaces/{ws}/workspace.db)
```

### Technology Stack

| Layer | Technology | Port |
|-------|------------|------|
| Frontend | React 18 + Vite + TypeScript | Dev: 5173, Prod: served as static files |
| Backend | FastAPI (Python) | 8077 |
| Storage | SQLite via `WorkspaceStore` | — |
| Graph visualization | `@xyflow/react` (React Flow) | — |
| Styling | Tailwind CSS + custom CSS variables | — |

### Request Flow

1. The browser loads the React SPA from FastAPI's static file mount (`/`)
2. React router (`react-router-dom`) maps URL paths to page components
3. Page components call functions from `src/lib/api.ts`
4. `api.ts` issues `fetch()` calls to `/api/*` on the same origin
5. FastAPI receives the request, validates the workspace name, creates a `WorkspaceStore` instance pointing at `~/.hermes/workspaces/{ws}/`
6. `WorkspaceStore` queries or mutates the SQLite `.db` file
7. FastAPI serializes the result and returns JSON
8. The React component updates state and re-renders

### Backend Startup Behaviour

On every request to a workspace endpoint, `_get_store(ws)` is called:

```python
def _get_store(ws: str) -> WorkspaceStore:
    path = HERMES_HOME / "workspaces" / ws
    if not path.is_dir():
        raise HTTPException(status_code=404, detail=f"Workspace '{ws}' not found")
    store = WorkspaceStore(path)
    if not store.exists():
        store.migrate_from_markdown(force=False)   # auto-migrate on first access
    return store
```

This means:
- If a workspace directory exists but has no SQLite DB yet, the store is auto-migrated from legacy Markdown files.
- No explicit "create workspace" API exists — workspaces appear automatically when their directory is present.

### Frontend Routing

Routes are defined in `App.tsx` (`src/App.tsx`):

| URL | Component | Purpose |
|-----|-----------|---------|
| `/` | `WorkspaceList` | Landing page — grid of all workspaces |
| `/ws/:ws` | `NodeBrowser` | Table view of all nodes in a workspace |
| `/ws/:ws/new` | `NodeEditor` | Create a new node |
| `/ws/:ws/nodes/:slug` | `NodeEditor` | Edit an existing node |
| `/ws/:ws/graph` | `GraphView` | Interactive graph visualization |

---

## 2. Backend API

Base URL: `http://localhost:8077/api`

All responses are JSON. Errors return `{ "detail": "..." }` with an appropriate HTTP status code.

### Internal Helper: `_node_to_api`

Every node response passes through this transformer before being returned:

```python
def _node_to_api(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node["id"],
        "slug": node["slug"],
        "title": node["title"],
        "kind": node["kind"],
        "summary": node.get("summary", ""),
        "content": node.get("body", ""),        # stored as "body" in DB, "content" in API
        "status": node.get("status", "active"),
        "parent_id": node.get("parent_id"),
        "tags": node.get("aliases", []),        # stored as "aliases", "tags" in API
        "updated_at": node.get("updated_at", ""),
        "created_at": node.get("created_at", ""),
        "filename": node.get("filename", ""),
    }
```

---

### `GET /api/workspaces`

List all workspaces with summary statistics.

**Response** `list[dict]` — one object per workspace:

```json
[
  {
    "name": "my-workspace",
    "node_count": 42,
    "edge_count": 137,
    "updated_at": "2025-03-15T10:30:00+00:00"
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Directory name (workspace identifier) |
| `node_count` | `int` | Total nodes in this workspace |
| `edge_count` | `int` | Total edges (relationships) |
| `updated_at` | `string\|null` | ISO-8601 timestamp of the DB file's last modification |

**WorkspaceStore method:** `list_all_nodes()` + `list_edges()` + `db_mtime()`

---

### `GET /api/workspaces/{ws}/nodes`

List all nodes in a workspace (lightweight summary, no content).

**Path parameters:**
- `ws` — workspace name (directory name)

**Response** `list[dict]`:

```json
[
  {
    "id": 1,
    "slug": "getting-started",
    "title": "Getting Started",
    "kind": "topic",
    "summary": "Initial setup guide",
    "updated_at": "2025-03-14T08:00:00+00:00"
  }
]
```

**WorkspaceStore method:** `list_all_nodes()` — only selected fields are returned.

---

### `GET /api/workspaces/{ws}/nodes/{ref}`

Fetch a single node by its slug (or any primary-key identifier), including its outgoing links.

**Path parameters:**
- `ws` — workspace name
- `ref` — node slug (or numeric ID)

**Response** `dict` (full `Node` shape):

```json
{
  "id": 1,
  "slug": "getting-started",
  "title": "Getting Started",
  "kind": "topic",
  "summary": "Initial setup guide",
  "content": "# Getting Started\n\nWelcome...",
  "status": "active",
  "parent_id": null,
  "tags": ["start", "onboarding"],
  "updated_at": "2025-03-14T08:00:00+00:00",
  "created_at": "2025-03-01T12:00:00+00:00",
  "filename": "getting-started.md",
  "links": [
    { "slug": "installation", "title": "Installation", "kind": "doc", "rel": "contains" }
  ]
}
```

The `links` array is built at request time from `store.list_edges()` — all edges where `from_node_id` matches the current node's ID.

**WorkspaceStore method:** `get_node(ref)` + `list_edges()`

---

### `GET /api/workspaces/{ws}/search`

Full-text search across node titles, content, and tags.

**Query parameters:**
- `q` — search string (required, min length 1)

**Response** `list[dict]`:

```json
[
  {
    "slug": "installation",
    "title": "Installation Guide",
    "kind": "doc",
    "score": 0.95,
    "summary": "How to install the package"
  }
]
```

Results are ordered by relevance score descending, limited to 20.

**WorkspaceStore method:** `search_nodes(q, limit=20)`

---

### `GET /api/workspaces/{ws}/graph`

Return the complete node-edge graph for visualization.

**Response** `dict`:

```json
{
  "nodes": [
    { "id": "getting-started", "label": "Getting Started", "kind": "topic" }
  ],
  "edges": [
    { "source": "getting-started", "target": "installation", "rel": "contains" }
  ]
}
```

- `nodes[].id` is the node slug
- `edges[].source` / `edges[].target` are slugs
- `edges[].rel` is the edge type (e.g. `contains`, `related_to`, `depends_on`)

**WorkspaceStore method:** `list_all_nodes()` + `list_edges()`

---

### `GET /api/workspaces/{ws}/events`

Return the most recent 50 events recorded in the workspace event log.

**Response** `list[dict]`:

```json
[
  {
    "id": 12,
    "event_type": "node_created",
    "node_id": 5,
    "node_slug": "new-feature",
    "node_title": "New Feature",
    "payload": {},
    "created_at": "2025-03-15T11:00:00+00:00"
  }
]
```

**WorkspaceStore method:** `list_events()[:50]`

---

### `POST /api/workspaces/{ws}/nodes`

Create a new node.

**Path parameters:**
- `ws` — workspace name

**Request body** `NodePayload`:

```json
{
  "title": "My New Node",
  "kind": "doc",
  "content": "# My New Node\n\nContent here...",
  "summary": "Brief description",
  "tags": ["tag1", "tag2"],
  "parent_ref": null,
  "status": "active"
}
```

| Field | Default | Description |
|-------|---------|-------------|
| `title` | (required) | Display title |
| `kind` | `"doc"` | Node type (see `kind.ts`) |
| `content` | `""` | Markdown body |
| `summary` | `""` | Short description |
| `tags` | `[]` | Aliases / tags |
| `parent_ref` | `null` | Slug of parent node |
| `status` | `"active"` | `active` or `archived` |

**Slug generation:** `title` is slugified via `workspace_store._slugify()` (dashes, lowercase).

**Response:** The created node object (same shape as `GET /nodes/{ref}`).

**WorkspaceStore method:** `upsert_node(slug=..., ...)` — creates new row.

---

### `PUT /api/workspaces/{ws}/nodes/{ref}`

Update an existing node. The slug cannot be changed (it is fixed at creation time).

**Path parameters:**
- `ws` — workspace name
- `ref` — current node slug

**Request body** `NodePayload` — same as POST.

**Response:** The updated node object.

**WorkspaceStore method:** `upsert_node(slug=existing_slug, ...)`

---

### `DELETE /api/workspaces/{ws}/nodes/{ref}`

Permanently delete a node.

**Path parameters:**
- `ws` — workspace name
- `ref` — node slug

**Response:**

```json
{ "ok": true, "deleted": "node-slug" }
```

**WorkspaceStore method:** Direct SQL `DELETE FROM nodes WHERE id = ?` via `store.connect()`.

---

### `POST /api/workspaces/{ws}/export-markdown`

Regenerate Markdown export files for the workspace. Exports are written back to the workspace directory.

**Path parameters:**
- `ws` — workspace name

**Response** `MarkdownExportResult`:

```json
{
  "context": {
    "root": "context",
    "written": ["guide.md", "index.md"],
    "removed": ["old.md"]
  },
  "organized": {
    "root": "organized",
    "written": ["project-a/index.md"],
    "removed": []
  }
}
```

**WorkspaceStore method:** `sync_markdown_exports()`

---

### `POST /api/workspaces/{ws}/clean-exports`

Delete all derived/export Markdown files from a workspace. The DB is verified first.

**Path parameters:**
- `ws` — workspace name

**Response** `CleanExportsResult`:

```json
{
  "verification": {
    "verified": true,
    "node_count": 42,
    "missing": [],
    "summary": "OK"
  },
  "deleted": ["context/exported.md", "organized/file.md"]
}
```

If `verification.verified` is `false`, the request returns HTTP 409 and nothing is deleted.

**WorkspaceStore method:** `verify_db_completeness()` + `clean_exports()`

---

### `POST /api/workspaces/{ws}/migrate-legacy`

Import legacy Markdown files (pre-SQLite format) into the SQLite database.

**Path parameters:**
- `ws` — workspace name

**Response** `LegacyMigrationResult`:

```json
{
  "manifest": {
    "workspace": "my-workspace",
    "imported": { "guide.md": "guide" },
    "moved": { "notes/": "_archive/" },
    "skipped": {},
    "removed": ["tmp/broken.md"],
    "backup": "/path/to/backup.tar.gz",
    "verified": true,
    "node_count": 38,
    "missing": [],
    "generated": []
  }
}
```

**WorkspaceStore method:** `migrate_legacy_to_db()`

---

### `GET /api/workspaces/{ws}/verify-db`

Verify that the SQLite database for a workspace is self-consistent.

**Path parameters:**
- `ws` — workspace name

**Response** `VerifyDbResult`:

```json
{
  "verified": true,
  "node_count": 42,
  "missing": [],
  "summary": "OK — 42 nodes verified"
}
```

**WorkspaceStore method:** `verify_db_completeness()`

---

### `POST /api/workspaces/{ws}/nodes/{ref}/links` *(utility)*

Create a directed edge from one node to another.

**Path parameters:**
- `ws` — workspace name
- `ref` — source node slug

**Request body** `LinkPayload`:

```json
{
  "target_ref": "installation",
  "rel": "contains"
}
```

**Valid `rel` values:** `contains`, `details`, `related_to`, `project_of`, `depends_on`, `references`

**Response:** Result of `store.link_nodes()`.

**WorkspaceStore method:** `link_nodes(ref, target_ref, edge_type=rel)`

---

## 3. Frontend Structure

### `src/App.tsx`

Entry point. Sets up:
- `BrowserRouter` from `react-router-dom`
- `Header` component (logo + "API online" indicator) — hidden on graph/editor/new routes
- `NeuralBackground` canvas (full-screen animated background)
- Route definitions (see table above)

**Key design decisions:**
- The header is hidden for routes that have their own persistent navigation (graph view, node editor) to maximise screen space.
- The header shows a pulsing amber dot when the API is reachable.

---

### `src/pages/WorkspaceList.tsx`

Landing page. Fetches all workspaces via `api.getWorkspaces()` and displays them as a grid of glass cards.

**Features:**
- Animated gradient avatar (2-letter abbreviation, unique gradient per workspace name)
- Node count + edge count per workspace
- Last-updated timestamp using `relativeTime()`
- Stats bar showing totals across all workspaces (total nodes, total edges, total workspaces)
- Staggered fade-up animation on card grid (45ms delay per card)
- Empty state and loading skeleton states

**State:**
- `workspaces: Workspace[]`
- `loading: boolean`
- `error: string`

---

### `src/pages/NodeBrowser.tsx`

Table view of all nodes in a workspace.

**Features:**
- Search bar with 300ms debounce — calls `api.searchNodes()` and replaces table rows with results; pressing `/` focuses it
- Kind filter chips (all, or one specific kind) with per-kind node counts
- Sortable table columns: Type, Title, Slug, Updated
- Row hover highlight (amber tint)
- "Nuevo nodo" button (navigates to `/ws/:ws/new`)
- "Grafo" button (navigates to `/ws/:ws/graph`)
- `WorkspaceActions` dropdown menu (export, clean, migrate)
- Toast notification system for errors
- Striped rows (alternating background)

**State:**
- `nodes: NodeSummary[]` — all nodes
- `results: SearchResult[] | null` — search results (null = show all)
- `query: string`
- `kindFilter: string | null`
- `loading: boolean`

**Row type union:** `Row = NodeSummary | SearchResult` — both share `slug`, `title`, `kind`; search results additionally have `score`.

---

### `src/pages/NodeEditor.tsx`

Split-pane Markdown editor for creating and editing nodes.

**Layout:**
- **Left sidebar (320px):** Metadata form — title, kind, summary, parent_ref, tags, links
- **Right panel:** Markdown textarea or rendered preview, toggled by "Editar" / "Preview" buttons

**Metadata fields:**
| Field | Input type | Notes |
|-------|-----------|-------|
| Título | text input | Required, auto-focused on new |
| Tipo | `<select>` | One of `ALL_KINDS` |
| Resumen | textarea (3 rows) | Short description |
| Nodo padre | text input (mono) | Slug of parent node |
| Tags / aliases | tag input + chips | Press Enter or comma to add; clicking × removes |
| Enlaces | expandable list + add form | Shows outgoing edges; add by target slug + rel type |

**Content area:**
- Raw Markdown textarea (JetBrains Mono font, 13.5px, no spellcheck)
- Or rendered HTML preview (custom `renderMarkdown()` supporting headings, bold, italic, code, lists, blockquotes, links)

**Keyboard shortcuts:**
- `Cmd/Ctrl+S` — save (disabled if saving or title empty)

**Status indicators (header bar):**
- Red "Error: ..." if last operation failed
- Green "Guardado" briefly after successful save (fades after 1.8s)
- Amber "Cambios sin guardar" when form is dirty
- Muted "Actualizado X" when clean and loaded

**Deletion:** Requires confirmation dialog, then calls `api.deleteNode()` and navigates back to `/ws/:ws`.

---

### `src/pages/GraphView.tsx`

Interactive node graph using `@xyflow/react` (React Flow).

**Layout algorithm:**
- Nodes grouped by `kind` into vertical columns
- Column width: 230px, row height: 78px
- Within each column, nodes are stacked top-to-bottom in creation order

**Node styling:**
- Rounded rectangle (border-radius: 10px)
- Background: linear gradient from kind color to 75% opacity
- Color-coded per kind (see `KIND_NODE_COLOR` in `kind.ts`)
- Box shadow with color glow

**Edge styling:**
- Light slate stroke (`rgba(148, 163, 184, 0.45)`)
- Arrow closed marker at target end
- Optional edge label (relationship type) toggled by "Mostrar/Ocultar etiquetas" button

**Interactive features:**
- Click node → side panel opens (shows kind, title, slug, "Editar nodo" button)
- Click pane / press Escape → close panel
- Click kind legend item → toggle visibility of that kind's nodes
- MiniMap (bottom-right) — color-coded by kind
- Controls (zoom in/out, fit view)
- Fit-to-view on initial load

**State:**
- `raw: GraphData | null` — raw API response
- `hiddenKinds: Set<string>` — filtered-out kinds
- `showLabels: boolean`
- `panel: NodeData & { id: string } | null`

---

### `src/components/NeuralBackground.tsx`

Full-screen canvas animation providing an ambient "neural network" background effect.

**Visual description:**
- ~150 amber nodes scattered across the canvas, connected by faint amber lines when within 180px
- 40 "pulses" (light particles) travel along connections between nodes, leaving a fading trail
- Nodes gently drift toward random targets; if the mouse comes within 300px, nodes are pushed away (tether effect)
- A radial fog gradient adds depth (slightly brighter at center)

**Technical details:**
- `nodeCount: 150` — base node count; scales with screen density
- `pulseCount: 40` — number of independent pulse particles
- `connDist: 180` — maximum connection distance
- `tetherRange: 50` — maximum mouse push distance
- `mouseRadius: 300` — mouse influence radius
- Colors: `AMBER = { r:255, g:196, b:90 }` and `AMBER_LIGHT = { r:255, g:220, b:150 }`
- Mouse position tracked via `mousemove`; `mouseout` sets `onScreen = false`
- Canvas uses `alpha: true` context for proper compositing

**Performance:**
- Density-scaled node/pulse count: `Math.max(0.3, Math.min(1.5, (W*H)/(1920*1080)))`
- `requestAnimationFrame` loop; cleanup on unmount

---

### `src/components/WorkspaceActions.tsx`

Overflow menu for workspace-level actions (export, clean, migrate).

**Actions:**

| Action | API call | Danger? |
|--------|----------|---------|
| Exportar a Markdown | `POST /export-markdown` | No |
| Limpiar exports | `POST /clean-exports` | Yes (HTTP 409 if DB incomplete) |
| Migrar legacy a DB | `POST /migrate-legacy` | No |

**UX pattern:**
- Three-dot icon button → dropdown menu
- Clicking an action shows a confirmation modal with title, description, and Cancel/Confirm buttons
- During execution a spinner is shown; on success/error a toast is fired via `onToast` callback
- `migrate` action also calls `onMigrated()` to refresh the node list

---

### `src/components/Toast.tsx`

Lightweight toast notification system (success / error / info tones).

---

## 4. API Client (`api.ts`)

**File:** `src/lib/api.ts`

### Error Handling

All requests go through the `req<T>()` wrapper:

```typescript
async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    // ... throw ApiError
  }
  return res.json()
}
```

`ApiError` extends `Error` with `status: number` and `detail: unknown`.

### TypeScript Interfaces

```typescript
// A workspace (list item)
interface Workspace {
  name: string
  node_count: number
  edge_count: number
  updated_at: string | null
}

// Lightweight node summary (list view)
interface NodeSummary {
  id: number
  slug: string
  title: string
  kind: string
  summary: string
  updated_at: string
}

// Outgoing link on a node
interface NodeLink {
  slug: string
  title: string
  kind: string
  rel: string
}

// Full node (detail view)
interface Node extends NodeSummary {
  content: string        // Markdown body
  status: string        // "active" | "archived"
  parent_id: number | null
  tags: string[]         // aliases
  created_at: string
  filename: string
  links: NodeLink[]       // outgoing edges (populated server-side)
}

// Search result
interface SearchResult {
  slug: string
  title: string
  kind: string
  score: number
  summary: string
}

// Graph data
interface GraphData {
  nodes: { id: string; label: string; kind: string }[]
  edges: { source: string; target: string; rel: string }[]
}

// Payload for create/update
interface NodePayload {
  title: string
  kind?: string
  content?: string
  summary?: string
  tags?: string[]
  parent_ref?: string | null
  status?: string
}

// Event log entry
interface Event {
  id: number
  event_type: string
  node_id: number | null
  node_slug: string | null
  node_title: string | null
  payload: Record<string, unknown>
  created_at: string
}

// Markdown export result
interface MarkdownExportSection {
  root?: string
  written: string[]
  removed: string[]
}
interface MarkdownExportResult {
  context: MarkdownExportSection
  organized: MarkdownExportSection & { root: string }
}

// DB verification
interface VerifyDbResult {
  verified: boolean
  node_count: number
  missing: string[]
  summary: string
}

// Clean exports result
interface CleanExportsResult {
  verification: VerifyDbResult
  deleted: string[]
}

// Legacy migration
type MigrationEntry = Record<string, string>
interface LegacyMigrationManifest {
  workspace: string
  imported: MigrationEntry[]
  moved: MigrationEntry[]
  skipped: MigrationEntry[]
  removed: string[]
  backup: string | null
  verified: boolean
  node_count: number
  missing: string[]
  generated: string[]
}
interface LegacyMigrationResult {
  manifest: LegacyMigrationManifest
}
```

### Exported API Functions

```typescript
export const api = {
  getWorkspaces: () =>                         req<Workspace[]>       ('GET',    '/workspaces'),
  getNodes:      (ws: string) =>              req<NodeSummary[]>     ('GET',    `/workspaces/${ws}/nodes`),
  getNode:       (ws: string, ref: string) =>  req<Node>              ('GET',    `/workspaces/${ws}/nodes/${ref}`),
  updateNode:    (ws: string, ref: string, data: NodePayload) =>
                                            req<Node>              ('PUT',    `/workspaces/${ws}/nodes/${ref}`, data),
  createNode:    (ws: string, data: NodePayload) =>
                                            req<Node>              ('POST',   `/workspaces/${ws}/nodes`, data),
  deleteNode:    (ws: string, ref: string) => req<{ ok: boolean }> ('DELETE', `/workspaces/${ws}/nodes/${ref}`),
  searchNodes:   (ws: string, q: string) =>
                                            req<SearchResult[]>     ('GET',    `/workspaces/${ws}/search?q=${encodeURIComponent(q)}`),
  getGraph:      (ws: string) =>              req<GraphData>         ('GET',    `/workspaces/${ws}/graph`),
  addLink:       (ws: string, ref: string, data: { target_ref: string; rel: string }) =>
                                            req                     ('POST',   `/workspaces/${ws}/nodes/${ref}/links`, data),
  getEvents:     (ws: string) =>              req<Event[]>           ('GET',    `/workspaces/${ws}/events`),
  exportMarkdown:(ws: string) =>
                                            req<MarkdownExportResult>('POST',  `/workspaces/${ws}/export-markdown`),
  cleanExports:  (ws: string) =>
                                            req<CleanExportsResult> ('POST',  `/workspaces/${ws}/clean-exports`),
  migrateLegacy: (ws: string) =>
                                            req<LegacyMigrationResult>('POST', `/workspaces/${ws}/migrate-legacy`),
  verifyDb:      (ws: string) =>
                                            req<VerifyDbResult>     ('GET',    `/workspaces/${ws}/verify-db`),
}
```

---

## 5. Theme and Styling

### CSS Variables (`src/index.css`)

```css
:root {
  --brand:      #ffc45a;        /* Amber primary */
  --brand-dark: #e0a830;       /* Darker amber for hover */
  --brand-glow: rgba(255, 196, 90, 0.4);
  --bg:         #050505;       /* Near-black background */
  --surface:    rgba(255, 255, 255, 0.03);
  --surface-hover: rgba(255, 255, 255, 0.06);
  --border:     rgba(255, 255, 255, 0.1);
  --text-main:  #ffffff;
  --text-muted: #a0a0a0;
}
```

### Color Palette

| Token | Hex | Use |
|-------|-----|-----|
| `--brand` | `#ffc45a` | Primary actions, highlights, logo |
| `--brand-dark` | `#e0a830` | Button hover state |
| `--bg` | `#050505` | Page background |
| `--surface` | `rgba(255,255,255,0.03)` | Glass card background |
| `--surface-hover` | `rgba(255,255,255,0.06)` | Glass card hover |
| `--border` | `rgba(255,255,255,0.1)` | All borders |
| `--text-main` | `#ffffff` | Primary text |
| `--text-muted` | `#a0a0a0` | Secondary text, placeholders |

### Typography

- **UI font:** `Inter` (Google Fonts) — weights 400, 500, 600, 700, 800
- **Monospace:** `JetBrains Mono` — for slugs, code, raw Markdown textarea

### Glass Card

```css
.glass {
  background: var(--surface);          /* rgba(255,255,255,0.03) */
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid var(--border);     /* rgba(255,255,255,0.1) */
}
.glass-hover:hover {
  background: var(--surface-hover);    /* rgba(255,255,255,0.06) */
  border-color: var(--brand);          /* amber border on hover */
}
```

### Button Styles

| Class | Appearance |
|-------|------------|
| `.btn-primary` | Amber background, black text, amber glow shadow, lifts on hover |
| `.btn-ghost` | Transparent with subtle border, amber border on hover |
| `.btn-danger-ghost` | Red-tinted text/border, dark red background on hover |

### Kind Color System (`src/lib/kind.ts`)

Each node `kind` has three associated colors:

| Kind | Chip (bg/text/ring) | Node graph color | Dot color |
|------|---------------------|------------------|-----------|
| `index` | amber | `#ffc45a` | amber |
| `topic` | emerald | `#10b981` | emerald |
| `detail` | zinc | `#71717a` | zinc |
| `project` | orange | `#f97316` | orange |
| `doc` | zinc | `#52525b` | zinc |
| `person` | purple | `#a855f7` | purple |
| `script` | yellow | `#eab308` | yellow |
| `reference` | cyan | `#06b6d4` | cyan |
| `agent-note` | pink | `#ec4899` | pink |

Unknown kinds fall back to the `doc` palette.

### NeuralBackground Canvas Animation

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `nodeCount` | 150 (density-scaled) | Amber dot nodes |
| `pulseCount` | 40 (density-scaled) | Traveling light pulses |
| `connDist` | 180px | Max distance to draw a connection line |
| `tetherRange` | 50px | Max mouse push offset |
| `mouseRadius` | 300px | Mouse influence radius |
| `AMBER` | `rgb(255,196,90)` | Node and pulse color |
| `AMBER_LIGHT` | `rgb(255,220,150)` | Pulse glow peak color |

---

## 6. Running the UI

### Prerequisites

- Python 3.10+ with `fastapi`, `uvicorn`, `workspace-store` (the `WorkspaceStore` library)
- Node.js 18+ with npm

### Start the Backend

```bash
cd ~/.hermes/workspace-ui/backend
python -m uvicorn main:app --host 0.0.0.0 --port 8077 --reload
```

Or, to run in the background:

```bash
nohup python -m uvicorn main:app --host 0.0.0.0 --port 8077 > /tmp/hermes-ui.log 2>&1 &
```

The backend serves the built frontend automatically — no separate frontend server needed in production.

### Build the Frontend (for production)

```bash
cd ~/.hermes/workspace-ui/frontend
npm install
npm run build
```

The output goes to `~/.hermes/workspace-ui/frontend/dist/`. The backend serves it from there.

### Run Frontend in Development Mode

```bash
cd ~/.hermes/workspace-ui/frontend
npm run dev
```

This starts a Vite dev server (typically on `http://localhost:5173`). In dev mode, API calls still go to `localhost:8077` (FastAPI), so the backend must be running separately.

### Access the UI

Open your browser at:

```
http://localhost:8077/
```

The FastAPI backend will either:
- Serve the built React SPA from `frontend/dist/`
- Return a 503 with a hint to build the frontend if `dist/` doesn't exist

### Troubleshooting

| Issue | Solution |
|-------|----------|
| "Frontend not built yet" at `/` | Run `npm run build` in the frontend directory |
| 404 on `/api/workspaces/{ws}/nodes` | The workspace directory must exist at `~/.hermes/workspaces/{ws}/` |
| Empty node list | Try the **Migrate legacy to DB** action from the `WorkspaceActions` menu to import Markdown files |
| Graph shows no edges | Ensure nodes have relationships in the SQLite DB (`edges` table) |
| Amber pulse animation is jerky | Reduce screen resolution or close other browser tabs |

---

*End of Workspace UI documentation.*
