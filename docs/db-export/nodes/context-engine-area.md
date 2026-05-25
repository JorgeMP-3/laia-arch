# Context Engine

## Metadata

- ID: `120`
- Slug: `context-engine-area`
- Kind: `topic`
- Status: `active`
- Filename: `context-engine-area.md`
- Parent: `hermes`
- Source kind: `manual`
- Created at: `2026-05-08T08:49:11.984670+00:00`
- Updated at: `2026-05-08T09:03:49.266082+00:00`
- Aliases: `context-engine-area`

## Summary

Sistema de memoria DB-first: WorkspaceStore, Plugin, UI, Migration

## Body

# Context Engine

## Descripción

Sistema de memoria nodal DB-first para Hermes. Fuente de verdad: `workspace.db` (SQLite). Exports Markdown bajo demanda.

## Arquitectura

```
┌─────────────────────────────────────┐
│           Context Engine            │
├─────────────────────────────────────┤
│  WorkspaceStore (SQLite + FTS5)    │
│  ├── nodes (contenido)             │
│  ├── edges (relaciones)            │
│  ├── aliases (búsqueda)            │
│  ├── artifacts (archivos)          │
│  └── events (coordinación)         │
├─────────────────────────────────────┤
│  Plugin workspace-context          │
│  ├── 20 herramientas               │
│  ├── 3 modos de inyección          │
│  └── Prefetch system               │
├─────────────────────────────────────┤
│  Workspace UI (FastAPI + React)    │
│  ├── Navegación de nodos           │
│  ├── Visualización de grafo        │
│  └── Chat con agente               │
└─────────────────────────────────────┘
```

## Componentes principales

### WorkspaceStore
- Schema SQLite con 6 tablas
- Búsqueda FTS5 con ranking BM25
- API Python completa
- Migración desde Markdown

### Plugin workspace-context
- 20 herramientas para gestión de nodos
- 3 modos de inyección (index, all-indexes, full)
- Sistema de prefetch
- Cache invalidation

## Documentos incluidos

- **context-engine-workspace-store**: Schema SQLite, API Python, FTS5
- **context-engine-plugin**: 20 tools, prefetch, inject modes
- **context-engine-web-ui**: FastAPI + React, tema amber
- **context-engine-migration**: Legacy → DB-first, backups
- **plugin-workspace-context-detail**: Documentación detallada del plugin
- **migration-detail**: Sistema de migración detallado

## Quick Reference

```bash
# Buscar nodos
workspace_search_nodes(query)

# Leer nodo
workspace_get_node(ref)

# Crear/actualizar nodo
workspace_upsert_node(...)

# Enlazar nodos
workspace_link_nodes(from, to, edge_type)
```


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- `contains` → `migration-detail` (Migration System (Detailed)) [peso=1.00]
- `contains` → `context-engine-migration` (Migration System (Legacy to DB)) [peso=1.00]
- `contains` → `context-engine-plugin` (Plugin workspace-context (20 Tools)) [peso=1.00]
- `contains` → `plugin-workspace-context-detail` (Plugin workspace-context (Detailed)) [peso=1.00]
- `contains` → `context-engine-web-ui` (Workspace UI (FastAPI + React)) [peso=1.00]
- `contains` → `context-engine-workspace-store` (WorkspaceStore Data Layer) [peso=1.00]

## Relaciones entrantes

- `contains` ← `hermes` (Hermes — Núcleo técnico) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Context Engine

# Context Engine

## Descripción

Sistema de memoria nodal DB-first para Hermes. Fuente de verdad: `workspace.db` (SQLite). Exports Markdown bajo demanda.

## Arquitectura

```
┌─────────────────────────────────────┐
│           Context Engine            │
├─────────────────────────────────────┤
│  WorkspaceStore (SQLite + FTS5)    │
│  ├── nodes (contenido)             │
│  ├── edges (relaciones)            │
│  ├── aliases (búsqueda)            │
│  ├── artifacts (archivos)          │
│  └── events (coordinación)         │
├─────────────────────────────────────┤
│  Plugin workspace-context          │
│  ├── 20 herramientas               │
│  ├── 3 modos de inyección          │
│  └── Prefetch system               │
├─────────────────────────────────────┤
│  Workspace UI (FastAPI + React)    │
│  ├── Navegación de nodos           │
│  ├── Visualización de grafo        │
│  └── Chat con agente               │
└─────────────────────────────────────┘
```

## Componentes principales

### WorkspaceStore
- Schema SQLite con 6 tablas
- Búsqueda FTS5 con ranking BM25
- API Python completa
- Migración desde Markdown

### Plugin workspace-context
- 20 herramientas para gestión de nodos
- 3 modos de inyección (index, all-indexes, full)
- Sistema de prefetch
- Cache invalidation

## Documentos incluidos

- **context-engine-workspace-store**: Schema SQLite, API Python, FTS5
- **context-engine-plugin**: 20 tools, prefetch, inject modes
- **context-engine-web-ui**: FastAPI + React, tema amber
- **context-engine-migration**: Legacy → DB-first, backups
- **plugin-workspace-context-detail**: Documentación detallada del plugin
- **migration-detail**: Sistema de migración detallado

## Quick Reference

```bash
# Buscar nodos
workspace_search_nodes(query)

# Leer nodo
workspace_get_node(ref)

# Crear/actualizar nodo
workspace_upsert_node(...)

# Enlazar nodos
workspace_link_nodes(from, to, edge_type)
```


> 📅 Documentado: 2026-05-08

→ Migration System (Detailed): `migration-detail.md`
→ Migration System (Legacy to DB): `context-engine-migration.md`
→ Plugin workspace-context (20 Tools): `context-engine-plugin.md`
→ Plugin workspace-context (Detailed): `plugin-workspace-context-detail.md`
→ Workspace UI (FastAPI + React): `context-engine-web-ui.md`
→ WorkspaceStore Data Layer: `context-engine-workspace-store.md`
