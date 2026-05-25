# WorkspaceStore Data Layer

## Metadata

- ID: `80`
- Slug: `context-engine-workspace-store`
- Kind: `doc`
- Status: `active`
- Filename: `context-engine-workspace-store.md`
- Parent: `context-engine-area`
- Source kind: `manual`
- Created at: `2026-05-08T08:33:57.344719+00:00`
- Updated at: `2026-05-19T11:33:14.566183+00:00`
- Aliases: `context-engine-workspace-store`

## Summary

**Archivo fuente:** `~/.hermes/workspace_store/__init__.py`

## Body

# WorkspaceStore Data Layer

# WorkspaceStore — Capa de Datos del Context Engine

**Archivo fuente:** `~/.laia/workspace_store/__init__.py`
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

**Kinds válidos:** `index`, `topic`, `detail`, `project`, `doc`, `agent-note`, `script`, `reference`.

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


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `context-engine-area` (Context Engine) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# WorkspaceStore Data Layer

# WorkspaceStore Data Layer

# WorkspaceStore — Capa de Datos del Context Engine

**Archivo fuente:** `~/.laia/workspace_store/__init__.py`
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

**Kinds válidos:** `index`, `topic`, `detail`, `project`, `doc`, `agent-note`, `script`, `reference`.

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


> 📅 Documentado: 2026-05-08
