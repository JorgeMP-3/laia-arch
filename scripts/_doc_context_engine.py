#!/usr/bin/env python3
"""Upsert full documentation for Context Engine nodes in laia_arch workspace."""

from __future__ import annotations
import sys
from pathlib import Path

import os
HERMES_HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
sys.path.insert(0, str(HERMES_HOME))

from workspace_store import WorkspaceStore

store = WorkspaceStore(Path(HERMES_HOME) / "workspaces" / "laia_arch")

body_00 = """# Context Engine — Índice General

Sistema de memoria nodal DB-first para Hermes. Fuente de verdad: `workspace.db` (SQLite). Exports Markdown: bajo demanda.

---

## 5 Áreas de Documentación

| Área | Nodo | Descripción |
|------|------|-------------|
| **WorkspaceStore** | `context-engine-docs/01-workspace-store` | Schema SQLite, API Python, FTS5 |
| **Plugin** | `context-engine-docs/02-plugin` | 20 tools, prefetch, inject modes |
| **WebUI** | `context-engine-docs/03-web-ui` | FastAPI + React, tema amber, puerto 8077 |
| **Migration** | `context-engine-docs/04-migration` | Legacy → DB-first, backups, verify |
| **Scripts** | `context-engine-docs/05-scripts` | create, health-check, show-injected, sync |

---

## Quick Reference

### Herramientas Principales

```
workspace_search_nodes(query)     → Buscar nodos (FTS5)
workspace_get_node(ref)           → Leer nodo por slug/id/alias
workspace_upsert_node(...)       → Crear/actualizar nodo
workspace_link_nodes(from, to, edge_type) → Crear relación
workspace_list_all_nodes()       → Ver todos los nodos
workspace_list_edges()           → Ver relaciones
workspace_list_events()          → Ver coordinación
workspace_scan_artifacts()       → Indexar code/
workspace_export_markdown()       → Exportar bajo demanda
workspace_migrate_legacy()       → Migrar legacy
```

### Config Plugin

```yaml
plugins:
  workspace-context:
    workspace: "laia_arch"
    inject_mode: "index"
    max_chars: 8000
```

### Inject Mode

| Modo | Qué se inyecta | Cuándo usarlo |
|------|-----------------|--------------|
| `index` (default) | Solo index del workspace activo | Workspaces grandes |
| `all-indexes` | Index de todos los workspaces | Coordinación multi-workspace |
| `full` | Todos los nodos | Workspaces pequeños |

### Edge Types

`contains` · `details` · `related_to` · `project_of` · `depends_on` · `references`

### Node Kinds

`index` · `project` · `topic` · `important` · `doc` · `script` · `reference` · `agent-note` · `agent-plan` · `agent-log`

### Scripts Útiles

```bash
python3 ~/.hermes/scripts/health-check.py
python3 ~/.hermes/scripts/show-injected.py --query "mi pregunta"
python3 ~/.hermes/scripts/sync-workspace-markdown.py --workspace laia_arch --watch
python3 ~/.hermes/scripts/workspace-daily-diagnostic.py
```

### Web UI

- URL: http://localhost:8077
- Backend: FastAPI en `~/.hermes/workspace-ui/backend/main.py`

### FUENTE DE VERDAD

**SQLite (`workspace.db`) es la fuente de verdad.**
`context/` y `docs/db-export/` son exports derivados, solo existen bajo demanda.
"""

body_01 = """# WorkspaceStore — Capa de Datos del Context Engine

**Archivo fuente:** `~/.hermes/workspace_store/__init__.py`
**Versión schema:** 1
**Total líneas:** ~2059

WorkspaceStore es la clase central del Context Engine. Gestiona una base de datos SQLite que sirve como fuente única de verdad para el conocimiento del workspace, reemplazando sistemas legacy basados en archivos Markdown.

---

## 1. Schema SQLite

Todas las tablas se crean con `CREATE TABLE IF NOT EXISTS`. Foreign keys con `PRAGMA foreign_keys = ON` y `ON DELETE SET NULL`.

### workspace_meta

Almacén clave-valor para metadatos del workspace.

```sql
CREATE TABLE IF NOT EXISTS workspace_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

**Claves estándar:** `schema_version`, `workspace_name`, `updated_at`, `last_export_at`, `last_organized_export_at`, `agent_docs_synced_at`.

---

### nodes

Tabla central. Todo conocimiento es un nodo.

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

**Kinds válidos:** `index`, `project`, `topic`, `important`, `doc`, `script`, `reference`, `agent-note`, `agent-plan`, `agent-log`.

**source_kind valores:** `manual`, `markdown-import`, `legacy-context`, `legacy-readme`, `legacy-agents`, `legacy-docs`, `legacy-projects`, `legacy-scripts`, `project-create`, `seed`, `tool`, `agent-coordination`, `agent-documenter`.

---

### edges

Relaciones dirigidas ponderadas entre nodos. Forma el grafo de conocimiento.

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

**edge_types:** `contains`, `details`, `related_to`, `project_of`, `depends_on`, `references`.

---

### aliases

Tabla de búsqueda flexible. Cada nodo puede tener múltiples aliases.

```sql
CREATE TABLE IF NOT EXISTS aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL,
    alias TEXT NOT NULL UNIQUE,
    alias_kind TEXT NOT NULL DEFAULT 'general',
    FOREIGN KEY(node_id) REFERENCES nodes(id) ON DELETE CASCADE
);
```

- `alias_kind = 'filename'`: mapeo filename derivado (ej. `00-index.md`)
- `alias_kind = 'general'`: slugs alternativos para búsqueda

---

### artifacts

Rastrea archivos en `code/` enlazados a nodos.

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

---

### events

Log de auditoría append-only para acciones, coordinación de agentes y migraciones.

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

**event_types comunes:** `node_created`, `node_updated`, `edge_linked`, `artifacts_scanned`, `markdown_exported`, `organized_markdown_exported`, `exports_cleaned`, `agent_task_start`, `agent_task_done`, `agent_docs_synced`, `legacy_migration_done`, `legacy_migration_failed`.

---

## 2. FTS5 — Búsqueda de Texto Completo

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS node_fts
USING fts5(title, slug, summary, body, aliases,
            tokenize='unicode61 remove_diacritics 2');
```

**Columnas indexadas:** `title`, `slug`, `summary`, `body`, `aliases`

**Tokenizer:** `unicode61 remove_diacritics 2`
- `unicode61`: tokenización consciente de Unicode
- `remove_diacritics`: elimina tildes (á→a, é→e)
- `2`: longitud mínima de token 2 caracteres

**Búsqueda:** BM25 ranking via `-bm25(node_fts)` — mayor score = mejor match.

**Fallback:** si FTS5 no devuelve resultados, usa LIKE en `title`, `summary`, `body`.

**Stopwords:** `de`, `la`, `el`, `en`, `los`, `las`, `un`, `una`, `y`, `a`, `que`, `es`, `por`, `con`, `del`, `al`, `se`, `su`, `hay`, `son`, `si`, `me`, `te`, `le`, `nos`, `les`, `mas`, `más`, `pero`, `como`, `para`, `este`, `esta`, `estos`, `estas`, `mi`, `tu`, `qué`, `quien`, `quién`, `quienes`, `donde`, `dónde`, `cuando`, `cuándo`.

---

## 3. API Python Principal

### ensure_schema()

```python
def ensure_schema(self) -> None
```

Crea el layout del workspace (`code/`, `code/scripts/`), inicializa SQLite y crea todas las tablas. Seguro llamarlo múltiples veces.

---

### upsert_node(...)

```python
def upsert_node(
    self, *, slug: str, title: str, kind: str,
    summary: str = "", body: str = "", status: str = "active",
    parent_ref: str | int | None = None,
    source_kind: str = "manual",
    aliases: Iterable[str] | None = None,
    filename: str | None = None,
) -> dict
```

**Create vs Update:** si `slug` ya existe → UPDATE; si no → INSERT. Sincroniza FTS5 y registra evento.

---

### search_nodes(query, *, limit=8, kinds=None, include_index=False)

```python
def search_nodes(self, query: str, *, limit: int = 8,
                 kinds: Iterable[str] | None = None,
                 include_index: bool = False) -> list[dict]
```

1. Tokeniza query (remueve stopwords, tokens < 3 chars)
2. FTS5 search con BM25 ranking
3. Fallback LIKE si FTS no encuentra
4. Boost de vecinos: nodos conectados получивают 35% del score del nodo original
5. Ordena por score descendente, luego por id

---

### prefetch(query, *, limit=2)

```python
def prefetch(self, query: str, *, limit: int = 2) -> str
```

Retorna los `limit` nodos mejores como Markdown renderizado, separados por `---`.

**Prefetch mode 'index':** solo busca en workspace activo.
**Prefetch mode 'all-indexes':** busca en todos los workspaces, normaliza scores con mention_boost (1.5x) y active_boost (1.1x).

---

### render_node_markdown(node)

```python
def render_node_markdown(self, node: dict | str | int) -> str
```

Genera Markdown renderizado: `# title` + body + indicadores (→ links a otros nodos).

---

### link_nodes(from_ref, to_ref, edge_type, *, weight=1.0)

```python
def link_nodes(self, from_ref, to_ref, edge_type, *, weight=1.0) -> dict
```

Crea o actualiza una relación. On conflict actualiza el weight.

---

### migrate_from_markdown(*, force=False)

```python
def migrate_from_markdown(self, *, force: bool = False) -> dict
```

Importa archivos Markdown existentes en `context/` y `projects/` a SQLite.

---

### migrate_legacy_to_db(*, backup_root=None, archive=True, remove_legacy=True)

```python
def migrate_legacy_to_db(self, *, backup_root=None, archive=True, remove_legacy=True) -> dict
```

Migra estructura legacy completa:
1. Backup en tar.gz
2. Import: README.md, context/, agents/, docs/, projects/, scripts/
3. Mueve código no-MD a `code/`
4. Verifica con `verify_db_completeness()`
5. Elimina originals solo si verified=True

---

### sync_markdown_exports(output_dir=None)

```python
def sync_markdown_exports(self, output_dir=None) -> dict
```

Genera `context/` (plano) y `docs/db-export/` (organizado) desde SQLite. Solo bajo demanda.

---

### verify_db_completeness()

```python
def verify_db_completeness(self) -> dict
```

Verifica ligera antes de limpiar: node_count > 0, index_count > 0, body_count > 0.

---

### scan_artifacts()

```python
def scan_artifacts() -> dict
```

Escanea `code/` recursivamente, indexa archivos en tabla `artifacts`.

---

### audit()

```python
def audit() -> dict
```

Verificación estructural completa: db existe, schema_version correcto, exactly one index, no orphans, no broken edges.

---

## 4. Helpers Internos

| Función | Propósito |
|---------|-----------|
| `_slugify(value)` | Convierte string a slug URL-safe |
| `_humanize_slug(slug)` | Convierte slug a título legible |
| `_tokenize_query(query)` | Tokeniza para FTS5, remueve stopwords |
| `_first_meaningful_paragraph(text)` | Extrae primer párrafo no-indicador |
| `_infer_kind_from_filename(name)` | Infiere kind desde nombre de archivo |
| `_strip_heading_and_indicators(content)` | Separa body de indicadores → |
| `_resolve_node_id(conn, ref)` | Resuelve slug/id/alias a integer node_id |
| `_sync_fts(conn, node_id)` | Mantiene FTS5 sincronizado con nodes |
| `_record_event(conn, event_type, node_id, payload)` | Inserta evento en tabla events |
| `_fts_search(conn, tokens, limit, kinds, include_index)` | Búsqueda FTS5 con BM25 |
| `_fallback_search(conn, terms, limit, kinds, include_index)` | Búsqueda LIKE cuando FTS falla |
"""

body_02 = """# Plugin workspace-context — MemoryProvider para Hermes

**Archivo fuente:** `~/.hermes/plugins/workspace-context/__init__.py`
**Clase:** `WorkspaceContextProvider`
**Extiende:** `MemoryProvider`

Plugin DB-first que proporciona contexto nodal al agente en cada sesión. Reemplaza el sistema legacy basado en exports Markdown con lectura directa de SQLite.

---

## 1. Configuración

### config.yaml

```yaml
plugins:
  workspace-context:
    workspace: "laia_arch"
    inject_mode: "index"
    max_chars: 8000
```

### Opciones de inject_mode

| Modo | Descripción |
|------|-------------|
| `index` (default) | Solo el nodo index del workspace activo |
| `all-indexes` | Nodos index de TODOS los workspaces |
| `full` | Todos los nodos del workspace activo |

---

## 2. Flujo de Inyección en Sesión

### initialize

1. Carga workspace activo desde config
2. Asegura que `workspace.db` existe
3. Rebuild del bloque cacheado

### system_prompt_block()

Retorna bloque HTML commentado inyectado al system prompt:

```
<!-- workspace context: {workspace} start -->
{WORKSPACE ACTIVO: ...}
{instrucciones de uso}
{nodo(s) renderizado(s)}
<!-- workspace context: {workspace} end -->
```

---

## 3. Sistema de Herramientas (20 tools)

### Consultas

#### workspace_list_workspaces
Lista todos los workspaces con estado DB, disponibilidad de index, y issues.

#### workspace_search_nodes
Entrada DB-first principal. Busca nodos con FTS5, aliases y relaciones.

**Parámetros:** `query` (requerido), `workspace`, `limit` (default 8), `kind`

**Retorna:** `{workspace, results: [{id, slug, title, kind, summary, score}]}`

---

#### workspace_get_node
Lectura DB-first principal. Obtiene nodo por slug, filename, alias o id.

**Parámetros:** `ref` (requerido), `workspace`

**Retorna:** `{workspace, node: {...}, rendered_markdown}`

---

#### workspace_list_all_nodes
Lista TODOS los nodos del workspace.

---

#### workspace_list_edges
Lista todas las relaciones entre nodos.

---

#### workspace_list_events
Lista eventos recientes para coordinación multi-agente.

**Parámetros:** `workspace`, `limit` (default 50, max 200)

---

### Archivos (compatibilidad)

#### workspace_list_folder
Lista carpetas y archivos reales del workspace. Raíz: `code/`.

---

#### workspace_read_workspace_file
Lee archivo real con ruta relativa segura.

**Validación:**拒绝 `..`, paths absolutos, paths que escapan del workspace root.

---

#### workspace_list_files (legacy compat)
Lista nodos que tendrían filename Markdown derivado.

---

#### workspace_read_file (legacy compat)
Lee nodo por filename o slug.

---

### Escritura

#### workspace_upsert_node
Crea o actualiza un nodo en SQLite. No genera exports Markdown.

**Parámetros:**
- `slug` (requerido), `title` (requerido), `kind` (requerido)
- `summary`, `body`, `status` (default `active`)
- `parent`, `aliases`, `filename`
- `workspace`

---

#### workspace_link_nodes
Crea o actualiza una relación entre nodos en SQLite.

**Parámetros:** `from_ref` (requerido), `to_ref` (requerido), `edge_type` (requerido), `weight` (default 1.0), `workspace`

**edge_types:** `contains`, `details`, `related_to`, `project_of`, `depends_on`, `references`

---

### Proyectos

#### workspace_create_project
Crea directorio `code/{name}/`, su nodo DB y relaciones.

---

### Exports y Migración

#### workspace_export_markdown
Regenera `context/` y `docs/db-export/` desde SQLite (bajo demanda).

---

#### workspace_clean_exports
Borra exports Markdown derivados tras verificar completitud DB.

---

#### workspace_verify_db_completeness
Audita si la DB tiene nodos suficientes antes de limpiar.

---

#### workspace_migrate_legacy
Migra carpetas legacy a SQLite, mueve código a `code/`, archiva originales.

---

### Coordinación Agente

#### workspace_sync_agent_docs
Actualiza nodos `agent-team` y `agent-log` desde tabla events.

---

#### workspace_agent_status
Estado agentico resumido para UI/monitor.

---

#### workspace_record_agent_event
Registra evento estructurado para orquestación.

**Parámetros:** `event_type` (requerido), `agent_id`, `task_id`, `summary`, `details`, `node_ref`, `extra`, `workspace`

---

#### workspace_scan_artifacts
Escanea `code/` y actualiza tabla artifacts.

---

#### workspace_claim_task
Registra que un agente toma una tarea.

---

#### workspace_complete_task
Registra que una tarea terminó.

---

## 4. Prefetch — Algoritmo

```
query_tokens = tokenize(query) - stopwords

Para cada workspace:
  ws_tokens = tokenize(workspace_name)
  mention_boost = 1.5 if query_tokens ∩ ws_tokens else 1.0
  active_boost = 1.1 if workspace == active_workspace else 1.0
  
  nodes = search_nodes(query, limit=4, include_index=False)
  
  if mention_boost > 1.0:
    stripped = query_tokens - ws_tokens
    extra_nodes = search_nodes(" ".join(stripped), limit=4)
    merge sin duplicados
  
  normalized_score = (raw_score / max_score) * mention_boost * active_boost

Ranking cruzado: ordenar por score descendente, workspace, slug
Retornar top 5 nodos como Markdown renderizado
```

---

## 5. Cacheo y Watch

- `_watched_mtimes`: dict `{workspace: db_mtime}` para detectar cambios
- `_check_for_changes()`: compara mtimes, rebuild si cambió
- `_cached_block`: bloque renderizado cacheado
- `_prefetch_cache`: dict `{query: resultado}` con lock

Rebuild automático cuando:
1. `system_prompt_block()` y `_cached_block is None`
2. `_check_for_changes()` retorna `True`
3. Cualquier tool que modifica la DB llama `_rebuild_block()`

---

## 6. Modelo de Eventos

| Evento | Cuándo |
|--------|--------|
| `node_created` | `workspace_upsert_node` crea nuevo |
| `node_updated` | `workspace_upsert_node` actualiza existente |
| `edge_linked` | `workspace_link_nodes` crea relación |
| `artifacts_scanned` | `workspace_scan_artifacts` corre |
| `markdown_exported` | `workspace_export_markdown` genera context/ |
| `organized_markdown_exported` | genera docs/db-export/ |
| `exports_cleaned` | `workspace_clean_exports` corre |
| `agent_task_start` | `workspace_claim_task` |
| `agent_task_done` | `workspace_complete_task` |
| `agent_docs_synced` | `workspace_sync_agent_docs` regenera notas |
| `legacy_migration_done` | `workspace_migrate_legacy` termina OK |
| `legacy_migration_failed` | migración termina sin verificar |
"""

body_03 = """# Workspace UI — Hermes Context Engine

**Backend:** `~/.hermes/workspace-ui/backend/main.py` (FastAPI)
**Frontend:** `~/.hermes/workspace-ui/frontend/` (React + Vite + TypeScript)
**Puerto por defecto:** 8077

Interfaz web para controlar sesiones Hermes y visualizar el estado del Context Engine.

---

## 1. Arquitectura General

```
Browser (React)
    │
    ▼ WebSocket / HTTP
FastAPI Backend (port 8077)
    │
    ▼ stdio JSON-RPC
hermes-agent (tui_gateway.entry)
    │
    ▼ control bridge
LAIA (TUI gateway)
```

El backend es un bridge: recibe conexiones web y las convierte en llamadas JSON-RPC al gateway de Hermes.

---

## 2. Backend FastAPI

### Endpoints

#### GET /
Sirve el frontend compilado (`frontend/dist/index.html`).

---

#### WebSocket /ws
Bridge bidireccional entre web UI y hermes-agent gateway.

**Flujo:**
1. Browser conecta WebSocket → FastAPI
2. FastAPI lanza proceso `hermes-agent` (o usa existente)
3. stdin/stdout del proceso ←→ WebSocket del browser
4. Mensajes JSON-RPC en ambos direcciones

**Control de sesión:** ciertos methods requieren una `session_id` activa:
- `prompt.submit`, `prompt.background`, `prompt.btw`
- `session.interrupt`, `session.undo`, `session.compress`
- `session.title`, `session.branch`, `session.steer`
- Tools deapproval/respond, slash.exec, command.dispatch

---

#### GET /api/workspaces
Lista workspaces disponibles con sus stores.

---

#### GET /api/health
Health check del backend.

---

### LAIA Control Center Bridge

**Clase:** `HermesWebSession`

Gestiona el proceso `hermes-agent` como subprocess async:

```python
class HermesWebSession:
    proc: asyncio.subprocess.Process | None
    pending: dict[str, asyncio.Future]
    clients: set[asyncio.Queue]
    control_session_id: str | None
```

**Métodos principales:**
- `start()`: lanza gateway si no está corriendo
- `stop()`: termina el proceso
- `rpc(method, params, session_id)`: envía JSON-RPC y espera respuesta
- `_read_stdout()`: lee stdout del gateway y despacha a clients
- `_read_stderr()`: loguea stderr

**Métodos de gateway permitidos** (`CONTROL_ALLOWED_METHODS`):
- Session: `session.create`, `session.list`, `session.resume`, `session.branch`, `session.close`, `session.interrupt`, `session.undo`, `session.compress`, `session.usage`, `session.history`, `session.title`, `session.steer`
- Prompt: `prompt.submit`, `prompt.background`, `prompt.btw`
- Commands: `commands.catalog`, `slash.exec`, `command.dispatch`
- Approvals: `approval.respond`, `clarify.respond`, `sudo.respond`, `secret.respond`
- Model: `model.options`, `config.get`, `config.set`
- Tools: `tools.list`, `tools.show`, `tools.configure`, `toolsets.list`
- Rollback: `rollback.list`, `rollback.diff`, `rollback.restore`
- Agents: `agents.list`
- Process: `process.stop`
- Personality: `personality`, `skin`
- Voice: `voice.toggle`
- Cron: `cron.manage`
- Skills: `skills.manage`
- Insights: `insights.get`
- Plugins: `plugins.list`
- Browser: `browser.manage`
- Reload: `reload.mcp`
- Completion: `complete.slash`, `complete.path`

---

### Resolución de Rutas

```python
HERMES_AGENT_ROOT = HERMES_HOME / "hermes-agent"
HERMES_AGENT_PYTHON = HERMES_AGENT_ROOT / "venv" / "bin" / "python"
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
```

---

## 3. Frontend React

### Stack

- **React 19** + **TypeScript**
- **Vite** — build tool
- **TanStack Query** — gestión de estado async
- **shiki** — syntax highlighting

### Tema Visual

- **Primary:** amber (#F59E0B)
- **Background:** zinc-900 (#18181B)
- **Text:** zinc-100
- **Accent:** cyan-400
- **Error:** red-500

### Archivo de Configuración

```json
{
  "hermes_web_url": "ws://localhost:8077/ws",
  "theme": "amber"
}
```

---

## 4. API REST (workspace)

### GET /api/workspaces

```json
{
  "workspaces": [
    {
      "name": "laia_arch",
      "path": "/home/familiamp/.hermes/workspaces/laia_arch",
      "has_db": true,
      "has_index": true
    }
  ],
  "active": "laia_arch"
}
```

---

## 5. Iniciar la UI

```bash
cd ~/.hermes/workspace-ui/backend
python3 main.py
# http://localhost:8077
```
"""

body_04 = """# Sistema de Migración — Legacy a DB-First

**Método principal:** `WorkspaceStore.migrate_legacy_to_db()`
**Script helper:** `create-workspace.py --migrate-legacy`
**Tool plugin:** `workspace_migrate_legacy`

---

## 1. Modelo Legacy vs DB-First

| Aspecto | Legacy | DB-First |
|---------|--------|----------|
| Fuente de verdad | Archivos Markdown | `workspace.db` (SQLite) |
| Buscar | `context/*.md` | FTS5 en SQLite |
| Relaciones | Indicadores `→` en MD | Tabla `edges` con tipos |
| Código | Raíz disperso | Centralizado en `code/` |
| Coordenación | Archivos en `agents/` | Tabla `events` |
| Exporte | Manual | Bajo demanda |

---

## 2. Paths Legacy Recognizados

```python
legacy_paths = [
    "README.md",
    "context/",
    "agents/",
    "docs/",
    "projects/",
    "scripts/",
]
```

---

## 3. Proceso de Migración Completo

### Paso 1: Backup

```python
backup_dir = "$HERMES_HOME/backups/legacy-workspaces/"
archive = f"{workspace}-{timestamp}.tar.gz"
```

Todos los paths se comprimen ANTES de tocar nada.

---

### Paso 2: Import de README.md

- Nodo `kind='doc'`, `slug='readme'`
- Título desde primer `# heading`
- Body completo
- Enlaza al index con `references`

---

### Paso 3: Import de context/

Para cada `*.md` en `context/`:
1. Lee contenido, extrae título desde `# heading`
2. Infiere `kind` desde nombre de archivo:
   - `00-index.md` → `index`
   - `NN-name.md` → `topic`
   - `NN[a-z]-name.md` → `detail`
   - `project-*.md` → `project`
3. Crea nodo con `source_kind='legacy-context'`
4. Resuelve indicadores `→ Target: slug.md` → edges `details`
5. Si no es `index`, enlaza al index con `details`

---

### Paso 4: Import de agents/

Para cada `*.md` en `agents/` recursivo:
- `kind='agent-note'`
- Slug: `agent-{path_relativo_slugified}`
- `source_kind='legacy-agents'`
- Enlaza al index con `contains`

---

### Paso 5: Import de docs/

Archivos en `docs/` → nodos `kind='doc'` o `kind='reference'`. Excluye `docs/db-export/`.

---

### Paso 6: Import de projects/

Para cada directorio en `projects/`:
1. Busca info: `info.md`, `README.md`, o `00-index.md`
2. Crea nodo `kind='project'`, slug `project-{name}`
3. Enlaza al index con `project_of`
4. Archivos `.md` internos → nodos `doc` hijos con `contains`
5. Archivos no-MD → movidos a `code/{project_name}/`

---

### Paso 7: Import de scripts/

- `.md` en scripts/ → nodos `kind='script'`, `source_kind='legacy-scripts'`
- Otros archivos → movidos a `code/scripts/`

---

### Paso 8: Mover Código a code/

Archivos no-MD de projects/scripts se mueven a `code/`.

---

### Paso 9: Verificación

```python
verification = store.verify_db_completeness()
# Verifica: node_count > 0, index_count > 0, body_count > 0
```

---

### Paso 10: Limpieza (opcional)

Si `remove_legacy=True` Y `verified=True`: borra originals.
Si `verified=False`: no borra nada, registra `legacy_migration_failed`.

---

## 4. Método: migrate_from_markdown

Solo importa desde `context/` y `projects/` (no toca agents/docs/scripts):

```python
def migrate_from_markdown(self, *, force: bool = False) -> dict
```

---

## 5. Bootstrap de Workspace Nuevo

```python
def seed_workspace(self, description: str, areas: Iterable[str]) -> dict
```

1. Crea nodo `index` con descripción
2. Crea un nodo `topic` por cada área
3. Enlaza topics al index con `details`
4. Escanea artifacts en `code/`
5. Genera `workspace-doc.md` y `CLAUDE.md`

---

## 6. Scripts Relacionados

### create-workspace.py

```bash
# Crear workspace nuevo
python3 ~/.hermes/scripts/create-workspace.py --name mi-workspace --bootstrap "Descripción"

# Migrar estructura legacy
python3 ~/.hermes/scripts/create-workspace.py --name mi-workspace --migrate-legacy

# Reparar workspace
python3 ~/.hermes/scripts/create-workspace.py --name mi-workspace --repair
```

### health-check.py

Verifica que migración está completa.

---

## 7. Estructura Post-Migración

```
workspace/
├── workspace.db          # Fuente de verdad
├── code/                 # Código (migrado o nuevo)
│   ├── scripts/
│   └── {projects}/
├── context/              # [vacío o regenerado bajo demanda]
├── docs/
│   └── db-export/        # [vacío o regenerado bajo demanda]
└── (legacy paths)         # [eliminados tras verificación]
```

---

## 8. Notas sobre Backups

- Ubicación: `~/.hermes/backups/legacy-workspaces/`
- Formato: `workspace-YYYYMMDDTHHMMSSZ.tar.gz`
- Se crean ANTES de cualquier modificación
- Nunca se borran automáticamente

---

## 9. Casos de Fallo

| Problema | Comportamiento |
|----------|----------------|
| DB ya tiene nodos | `migrate_from_markdown` refuse `force=False` |
| Verificación fails | No borra legacy, registra `failed` |
| Archivo destino ya existe | Skip (no sobreescribe) |
| Path no existe | Omite silenciosamente |
"""

body_05 = r"""# Scripts del Context Engine

**Directorio:** `~/.hermes/scripts/`
**Workspaces:** `~/.hermes/workspaces/{name}/code/scripts/`

---

## 1. create-workspace.py

**Ruta:** `~/.hermes/scripts/create-workspace.py`
**Propósito:** Crear, reparar y migrar workspaces DB-only.

### Uso

```bash
# Crear workspace nuevo
python3 ~/.hermes/scripts/create-workspace.py --name mi-workspace --bootstrap "Descripción"

# Migrar estructura legacy
python3 ~/.hermes/scripts/create-workspace.py --name mi-workspace --migrate-legacy

# Reparar workspace
python3 ~/.hermes/scripts/create-workspace.py --name mi-workspace --repair
```

### Flags

| Flag | Descripción |
|------|-------------|
| `--name` | Nombre del workspace (alfanumérico + guiones) |
| `--bootstrap` | Descripción inicial del workspace |
| `--areas` | Áreas temáticas separadas por pipe `\|` |
| `--migrate-legacy` | Migra estructura legacy existente |
| `--repair` | Repara estructura mínima y DB |
| `--interactive` | Modo interactivo con prompts |

---

## 2. health-check.py

**Ruta:** `~/.hermes/scripts/health-check.py`
**Propósito:** Verificar estado estructural y DB-only de todos los workspaces.

### Uso

```bash
python3 ~/.hermes/scripts/health-check.py
python3 ~/.hermes/scripts/health-check.py --workspace laia_arch
python3 ~/.hermes/scripts/health-check.py --fix
```

### Lo que Verifica

**Estructura de carpetas:** `code/`, `code/scripts/` existen

**Audit de DB:**
- `workspace.db` existe
- Exactly one nodo `kind='index'`
- Sin orphan nodes ni broken edges
- `schema_version` correcto

---

## 3. show-injected.py

**Ruta:** `~/.hermes/scripts/show-injected.py`
**Propósito:** Debug de qué nodos se inyectan al agente en cada sesión.

### Uso

```bash
python3 ~/.hermes/scripts/show-injected.py
python3 ~/.hermes/scripts/show-injected.py --query "infraestructura"
python3 ~/.hermes/scripts/show-injected.py --full
python3 ~/.hermes/scripts/show-injected.py --workspace pixelcore
```

### Secciones de Salida

**Sección 1: Auto-Inyectado** — según `inject_mode`: `index`, `full`, o `all-indexes`

**Sección 2: Nodos Disponibles para Prefetch** — hasta 12 por workspace

**Sección 3: Simulación de Prefetch** (con `--query`) — mention_boost, active_boost, ranking cruzado

**Sección 4: Código del Workspace** — contenido de `code/` y `code/scripts/`

**Sección 5: Export Markdown Bajo Demanda** — estado de `docs/db-export/`

---

## 4. sync-workspace-markdown.py

**Ruta:** `~/.hermes/scripts/sync-workspace-markdown.py`
**Propósito:** Exportar `workspace.db` a Markdown bajo demanda.

### Uso

```bash
# Sincronizar un workspace
python3 ~/.hermes/scripts/sync-workspace-markdown.py --workspace laia_arch

# Sincronizar todos
python3 ~/.hermes/scripts/sync-workspace-markdown.py --all

# Modo watch
python3 ~/.hermes/scripts/sync-workspace-markdown.py --workspace laia_arch --watch

# Output dir personalizado
python3 ~/.hermes/scripts/sync-workspace-markdown.py --workspace laia_arch --output-dir /tmp/snapshot
```

### Dos Vistas Exportadas

**`context/` — Exporto plano:** un archivo por nodo

**`docs/db-export/` — Snapshot organizado:**
- `00-index.md` — Resumen con stats
- `01-nodes.md` — Tabla de todos los nodos
- `02-relations.md` — Tabla de relaciones
- `03-events.md` — Tabla de eventos
- `nodes/` — Detalle por nodo
- `artifacts/` — Índice de artefactos

---

## 5. workspace-daily-diagnostic.py

**Ruta:** `~/.hermes/scripts/workspace-daily-diagnostic.py`
**Propósito:** Validar que el flujo DB-first funciona para queries reales.

### Uso

```bash
python3 ~/.hermes/scripts/workspace-daily-diagnostic.py
python3 ~/.hermes/scripts/workspace-daily-diagnostic.py --case metodo-doyouwin
```

### Casos de Prueba Predefinidos

| ID | Query | Workspace | Nodo Esperado |
|----|-------|-----------|---------------|
| `metodo-doyouwin` | `metodo doyouwin fases` | doyouwin | `02b-metodo-doyouwin` |
| `pixelcore-infra` | `infraestructura pixelcore` | pixelcore | `40-infraestructura` |
| `laia-arch-honesty` | `arquitectura laia` | laia_arch | `00-index` |
| `pixelcore-servidor` | `pixelcore servidor infraestructura` | pixelcore | `40-infraestructura` |

---

## 6. index-scripts.py

**Ruta:** `~/.hermes/scripts/index-scripts.py`
**Propósito:** Generar índice de todos los scripts disponibles.

```bash
python3 ~/.hermes/scripts/index-scripts.py
python3 ~/.hermes/scripts/index-scripts.py --dry-run
python3 ~/.hermes/scripts/index-scripts.py --workspace pixelcore
```

---

## 7. cleanup-sessions.py

**Ruta:** `~/.hermes/scripts/cleanup-sessions.py`
**Propósito:** Archivar y eliminar sesiones antiguas.

```bash
python3 ~/.hermes/scripts/cleanup-sessions.py
python3 ~/.hermes/scripts/cleanup-sessions.py --execute
python3 ~/.hermes/scripts/cleanup-sessions.py --keep-days 7 --archive-days 30 --execute
```

### Clasificación

| Categoría | Criterio | Acción |
|-----------|----------|--------|
| Conservar | < 30 días | No tocar |
| Archivar | 30-90 días | Comprimir .tar.gz |
| Eliminar | > 90 días | Borrar (si no --archive-all) |

---

## 8. Scripts Globales Adicionales

### datasette-start.sh

Lanza Datasette para consultar workspaces como bases SQLite.

```bash
bash ~/.hermes/scripts/datasette-start.sh
# http://localhost:8076
```

### start_mlx_servers.sh

Inicia servidores MLX para visión y TTS.

```bash
bash ~/.hermes/scripts/start_mlx_servers.sh
```

---

## 9. Resumen de Uso Rápido

| Tarea | Comando |
|-------|---------|
| Crear workspace | `python3 scripts/create-workspace.py --name X --bootstrap "desc"` |
| Health check | `python3 scripts/health-check.py [--workspace X] [--fix]` |
| Ver qué se inyecta | `python3 scripts/show-injected.py [--query X] [--full]` |
| Exportar a MD | `python3 scripts/sync-workspace-markdown.py --all [--watch]` |
| Diagnosticar DB | `python3 scripts/workspace-daily-diagnostic.py` |
| Indizar scripts | `python3 scripts/index-scripts.py` |
| Limpiar sesiones | `python3 scripts/cleanup-sessions.py [--execute]` |
"""

# ── Write all nodes ──────────────────────────────────────────────────────────
nodes = [
    ("context-engine-docs/00-index", "Context Engine — Índice General", "index", None, body_00),
    ("context-engine-docs/01-workspace-store", "WorkspaceStore Data Layer", "doc", "context-engine-docs", body_01),
    ("context-engine-docs/02-plugin", "Plugin workspace-context — 20 Tools", "doc", "context-engine-docs", body_02),
    ("context-engine-docs/03-web-ui", "Workspace UI — FastAPI + React", "doc", "context-engine-docs", body_03),
    ("context-engine-docs/04-migration", "Migration System — Legacy to DB", "doc", "context-engine-docs", body_04),
    ("context-engine-docs/05-scripts", "Scripts — create, health-check, show-injected, sync", "doc", "context-engine-docs", body_05),
]

for slug, title, kind, parent_slug, body in nodes:
    node = store.upsert_node(
        slug=slug,
        title=title,
        kind=kind,
        summary=f"Documentación: {title}",
        body=body,
        status="active",
        parent_ref=parent_slug,
        source_kind="tool",
    )
    print(f"✓ {slug} (id={node['id']}, body_len={len(body)})")

# Link children to parent
try:
    parent = store.get_node("context-engine-docs")
    for slug in ["01-workspace-store", "02-plugin", "03-web-ui", "04-migration", "05-scripts"]:
        child = store.get_node(f"context-engine-docs/{slug}")
        if child and parent:
            try:
                store.link_nodes(parent["id"], child["id"], "contains")
                print(f"  ↳ linked: {slug}")
            except Exception as e:
                print(f"  ↳ link skip {slug}: {e}")
except Exception as e:
    print(f"Link error: {e}")

print("\nDone.")
