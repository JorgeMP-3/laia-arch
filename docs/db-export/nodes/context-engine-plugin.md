# Plugin workspace-context (20 Tools)

## Metadata

- ID: `81`
- Slug: `context-engine-plugin`
- Kind: `doc`
- Status: `active`
- Filename: `context-engine-plugin.md`
- Parent: `context-engine-area`
- Source kind: `manual`
- Created at: `2026-05-08T08:33:57.662252+00:00`
- Updated at: `2026-05-08T08:33:57.662252+00:00`
- Aliases: `context-engine-plugin`

## Summary

**Archivo fuente:** `plugins/workspace-context/__init__.py`

## Body

# Plugin workspace-context — 20 Tools

# Plugin workspace-context — MemoryProvider para Hermes

**Archivo fuente:** `plugins/workspace-context/__init__.py`
**Clase:** `WorkspaceContextProvider`
**Extiende:** `MemoryProvider`

Plugin DB-first que proporciona contexto nodal al agente en cada sesion. Reemplaza el sistema legacy basado en exports Markdown con lectura directa de SQLite.

---

## 1. Configuracion

### config.yaml

```yaml
plugins:
  workspace-context:
    workspace: "arete"              # Workspace principal para escrituras sin workspace explícito
    inject_mode: "all-indexes"      # index | all-indexes
    max_chars: 20000                # Caracteres máximos inyectados en system prompt
    active_workspaces:              # NUEVO: workspaces editables (escritura permitida)
    - arete
    workspaces:                      # Workspaces legibles en modo all-indexes
    - arete
    - doyouwin
    - pixelcore
    - laia_arch
    - servidor_jmp
```

### Campos del plugin

| Campo | Tipo | Descripcion |
|---|---|---|
| `workspace` | string | Workspace por defecto para escrituras |
| `inject_mode` | string | `index` (solo index activo) o `all-indexes` (todos los indices) |
| `max_chars` | int | Limite de caracteres en system prompt |
| `active_workspaces` | array | Lista de workspaces con escritura permitida |
| `workspaces` | array | Lista de workspaces legibles |

### Regla de active_workspaces

- Si `active_workspaces` esta vacio: se usa `[workspace]` (compatibilidad hacia atras)
- Los workspaces no listados en `active_workspaces` son de solo lectura
- El guard de escritura bloquea cualquier tool de escritura a workspaces inactivos

### Opciones de inject_mode

| Modo | Descripcion |
|---|---|
| `index` (default) | Solo el nodo index del workspace activo |
| `all-indexes` | Nodos index de TODOS los workspaces configurados |

---

## 2. Flujo de Inyeccion en Sesion

### initialize

1. Carga config desde `config.yaml`
2. Detecta cambios de mtime del archivo de config
3. Asegura que `workspace.db` existe en cada workspace
4. Rebuild del bloque cacheado

### system_prompt_block()

Retorna bloque HTML commentado inyectado al system prompt:

```
<!-- workspace context: {workspace} start -->
[WORKSPACE ACTIVO: {workspace} | MODO: {mode} | EDITABLES: {active_workspaces}]
Tienes cargado el nodo index de estos workspaces: {names}. Son brujulas, no fuentes suficientes para detalles.
Orden obligatorio: workspace_search_nodes -> workspace_get_node -> ...
Regla de escritura: solo puedes modificar workspaces incluidos en EDITABLES.
...
<!-- workspace context: {workspace} end -->
```

Clave: `EDITABLES` muestra la lista de workspaces con escritura permitida. El agente sabe en todo momento cuales puede modificar.

---

## 3. Sistema de Herramientas (20 tools)

### Consultas

#### workspace_list_workspaces
Lista todos los workspaces con estado DB, disponibilidad de index, y si son editables.

#### workspace_search_nodes
Entrada DB-first principal. Busca nodos con FTS5, aliases y relaciones.

**Parametros:** `query` (requerido), `workspace`, `limit` (default 8), `kind`

**Retorna:** `{workspace, results: [{id, slug, title, kind, summary, score}]}`

---

#### workspace_get_node
Lectura DB-first principal. Obtiene nodo por slug, filename, alias o id.

**Parametros:** `ref` (requerido), `workspace`

**Retorna:** `{workspace, node: {...}, rendered_markdown}`

---

#### workspace_list_all_nodes
Lista TODOS los nodos del workspace.

---

#### workspace_list_edges
Lista todas las relaciones entre nodos.

---

#### workspace_list_events
Lista eventos recientes para coordinacion multi-agente.

**Parametros:** `workspace`, `limit` (default 50, max 200)

---

### Archivos (compatibilidad)

#### workspace_list_folder
Lista carpetas y archivos reales del workspace. Raiz: `code/`.

---

#### workspace_read_workspace_file
Lee archivo real con ruta relativa segura.

**Validacion:** rechaza `..`, paths absolutos, paths que escapan del workspace root.

---

#### workspace_list_files (legacy compat)
Lista nodos que tendrian filename Markdown derivado.

---

#### workspace_read_file (legacy compat)
Lee nodo por filename o slug.

---

### Escritura

#### workspace_upsert_node
Crea o actualiza un nodo en SQLite. No genera exports Markdown.

**Parametros:**
- `slug` (requerido), `title` (requerido), `kind` (requerido)
- `summary`, `body`, `status` (default `active`)
- `parent`, `aliases`, `filename`
- `workspace`

**Validacion:** si el workspace objetivo no esta en `active_workspaces`, devuelve error.

---

#### workspace_link_nodes
Crea o actualiza una relacion entre nodos en SQLite.

**Parametros:** `from_ref` (requerido), `to_ref` (requerido), `edge_type` (requerido), `weight` (default 1.0), `workspace`

**edge_types:** `contains`, `details`, `related_to`, `project_of`, `depends_on`, `references`

---

### Proyectos

#### workspace_create_project
Crea directorio `code/{name}/`, su nodo DB y relaciones.

---

### Exports y Migracion

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
Migra carpetas legacy a SQLite, mueve codigo a `code/`, archiva originales.

---

### Coordinacion Agente

#### workspace_sync_agent_docs
Actualiza nodos `agent-team` y `agent-log` desde tabla events.

---

#### workspace_agent_status
Estado agentico resumido para UI/monitor.

---

#### workspace_record_agent_event
Registra evento estructurado para orquestacion.

**Parametros:** `event_type` (requerido), `agent_id`, `task_id`, `summary`, `details`, `node_ref`, `extra`, `workspace`

---

#### workspace_scan_artifacts
Escanea `code/` y actualiza tabla artifacts.

---

#### workspace_claim_task
Registra que un agente toma una tarea.

---

#### workspace_complete_task
Registra que una tarea termino.

---

## 4. Prefetch — Algoritmo de Dos Niveles

El prefetch se dispara antes de cada turno del agente. Objetivo: que el LLM pueda responder preguntas simples sin necesidad de llamar a tools.

### Constantes (definidas en el codigo)

```python
PREFETCH_FULL_NODES = 2     # Primeros resultados: contenido completo
PREFETCH_SUMMARY_NODES = 6  # Resultados restantes: solo titulo + summary
PREFETCH_MIN_SCORE = 0.05   # Umbral minimo BM25 para filtrar ruido
```

### Flujo

```
Query del usuario
        ↓
_cross_workspace_search(query, limit=8, include_index=False)
        ↓
Filtrado por score >= 0.05
        ↓
[:8] primeros resultados
        ↓
Para i, nodo in enumerate(resultados):
    si i < 2 (PREFETCH_FULL_NODES):
        → contenido COMPLETO renderizado como Markdown
    sino:
        → solo "titulo — summary"
        ↓
Join con "\n\n---\n\n"
```

### Ejemplo de salida inyectada

```
[arete/10-que-es-arete] (score: 0.142)

# Aretê — Filosofia y Sistema

Contenido completo del nodo...

---

[laia_arch/hermes-core-architecture.md] (score: 0.089)

# Arquitectura General de Hermes Agent

Contenido completo del nodo...

---

[arete/20-arquitectura.md] (score: 0.071) — Arquitectura del sistema. Contiene docs de backend...
[doyouwin/readme.md] (score: 0.055) — Readme: DoYouWin...
[pixelcore/readme.md] (score: 0.048) — PixelCore — Indice...
```

### Modo no-all-indexes

Si `inject_mode` es `index` (no `all-indexes`), el prefetch usa `store.prefetch(query, limit=2)` del WorkspaceStore directamente.

---

## 5. Write Guard — Active Workspaces

Antes de ejecutar cualquier tool de escritura, el plugin verifica que el workspace objetivo este en `active_workspaces`.

### Tools protegidas (MUTATING_DB_TOOLS)

```python
MUTATING_DB_TOOLS = {
    "workspace_upsert_node",
    "workspace_link_nodes",
    "workspace_create_project",
    "workspace_ensure_structure",
    "workspace_migrate_legacy",
    "workspace_scan_artifacts",
    "workspace_record_agent_event",
    "workspace_claim_task",
    "workspace_complete_task",
    "workspace_sync_agent_docs",
}
```

### Logica de verificacion

```python
def _is_writable(self, workspace: str) -> bool:
    return workspace in self._active_workspaces()

# En handle_tool_call(), justo despues de resolver el workspace:
if tool_name in MUTATING_DB_TOOLS and not self._is_writable(workspace):
    return json.dumps({
        "error": f"El workspace '{workspace}' es de solo lectura.",
        "active_workspaces": self._active_workspaces(),
        "hint": "Usa workspace_list_workspaces para ver los workspaces editables.",
    })
```

### Respuesta de error

```json
{
  "error": "El workspace 'doyouwin' es de solo lectura.",
  "active_workspaces": ["arete"],
  "hint": "Usa workspace_list_workspaces para ver los workspaces editables."
}
```

---

## 6. Cacheo y Watch

- `_watched_mtimes`: dict `{workspace: db_mtime}` para detectar cambios
- `_check_for_changes()`: compara mtimes, rebuild si changed
- `_cached_block`: bloque renderizado cacheado
- `_prefetch_cache`: dict `{query: resultado}` con lock

Rebuild automatico cuando:
1. `system_prompt_block()` y `_cached_block is None`
2. `_check_for_changes()` retorna `True`
3. Cualquier tool que modifica la DB llama `_rebuild_block()`
4. El archivo `config.yaml` cambia de mtime

---

## 7. Modelo de Eventos

| Evento | Cuando |
|---|---|
| `node_created` | `workspace_upsert_node` crea nuevo |
| `node_updated` | `workspace_upsert_node` actualiza existente |
| `edge_linked` | `workspace_link_nodes` crea relacion |
| `artifacts_scanned` | `workspace_scan_artifacts` corre |
| `markdown_exported` | `workspace_export_markdown` genera context/ |
| `organized_markdown_exported` | genera docs/db-export/ |
| `exports_cleaned` | `workspace_clean_exports` corre |
| `agent_task_start` | `workspace_claim_task` |
| `agent_task_done` | `workspace_complete_task` |
| `agent_docs_synced` | `workspace_sync_agent_docs` regenera notas |
| `legacy_migration_done` | `workspace_migrate_legacy` termina OK |
| `legacy_migration_failed` | migracion termina sin verificar |


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `context-engine-area` (Context Engine) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Plugin workspace-context (20 Tools)

# Plugin workspace-context — 20 Tools

# Plugin workspace-context — MemoryProvider para Hermes

**Archivo fuente:** `plugins/workspace-context/__init__.py`
**Clase:** `WorkspaceContextProvider`
**Extiende:** `MemoryProvider`

Plugin DB-first que proporciona contexto nodal al agente en cada sesion. Reemplaza el sistema legacy basado en exports Markdown con lectura directa de SQLite.

---

## 1. Configuracion

### config.yaml

```yaml
plugins:
  workspace-context:
    workspace: "arete"              # Workspace principal para escrituras sin workspace explícito
    inject_mode: "all-indexes"      # index | all-indexes
    max_chars: 20000                # Caracteres máximos inyectados en system prompt
    active_workspaces:              # NUEVO: workspaces editables (escritura permitida)
    - arete
    workspaces:                      # Workspaces legibles en modo all-indexes
    - arete
    - doyouwin
    - pixelcore
    - laia_arch
    - servidor_jmp
```

### Campos del plugin

| Campo | Tipo | Descripcion |
|---|---|---|
| `workspace` | string | Workspace por defecto para escrituras |
| `inject_mode` | string | `index` (solo index activo) o `all-indexes` (todos los indices) |
| `max_chars` | int | Limite de caracteres en system prompt |
| `active_workspaces` | array | Lista de workspaces con escritura permitida |
| `workspaces` | array | Lista de workspaces legibles |

### Regla de active_workspaces

- Si `active_workspaces` esta vacio: se usa `[workspace]` (compatibilidad hacia atras)
- Los workspaces no listados en `active_workspaces` son de solo lectura
- El guard de escritura bloquea cualquier tool de escritura a workspaces inactivos

### Opciones de inject_mode

| Modo | Descripcion |
|---|---|
| `index` (default) | Solo el nodo index del workspace activo |
| `all-indexes` | Nodos index de TODOS los workspaces configurados |

---

## 2. Flujo de Inyeccion en Sesion

### initialize

1. Carga config desde `config.yaml`
2. Detecta cambios de mtime del archivo de config
3. Asegura que `workspace.db` existe en cada workspace
4. Rebuild del bloque cacheado

### system_prompt_block()

Retorna bloque HTML commentado inyectado al system prompt:

```
<!-- workspace context: {workspace} start -->
[WORKSPACE ACTIVO: {workspace} | MODO: {mode} | EDITABLES: {active_workspaces}]
Tienes cargado el nodo index de estos workspaces: {names}. Son brujulas, no fuentes suficientes para detalles.
Orden obligatorio: workspace_search_nodes -> workspace_get_node -> ...
Regla de escritura: solo puedes modificar workspaces incluidos en EDITABLES.
...
<!-- workspace context: {workspace} end -->
```

Clave: `EDITABLES` muestra la lista de workspaces con escritura permitida. El agente sabe en todo momento cuales puede modificar.

---

## 3. Sistema de Herramientas (20 tools)

### Consultas

#### workspace_list_workspaces
Lista todos los workspaces con estado DB, disponibilidad de index, y si son editables.

#### workspace_search_nodes
Entrada DB-first principal. Busca nodos con FTS5, aliases y relaciones.

**Parametros:** `query` (requerido), `workspace`, `limit` (default 8), `kind`

**Retorna:** `{workspace, results: [{id, slug, title, kind, summary, score}]}`

---

#### workspace_get_node
Lectura DB-first principal. Obtiene nodo por slug, filename, alias o id.

**Parametros:** `ref` (requerido), `workspace`

**Retorna:** `{workspace, node: {...}, rendered_markdown}`

---

#### workspace_list_all_nodes
Lista TODOS los nodos del workspace.

---

#### workspace_list_edges
Lista todas las relaciones entre nodos.

---

#### workspace_list_events
Lista eventos recientes para coordinacion multi-agente.

**Parametros:** `workspace`, `limit` (default 50, max 200)

---

### Archivos (compatibilidad)

#### workspace_list_folder
Lista carpetas y archivos reales del workspace. Raiz: `code/`.

---

#### workspace_read_workspace_file
Lee archivo real con ruta relativa segura.

**Validacion:** rechaza `..`, paths absolutos, paths que escapan del workspace root.

---

#### workspace_list_files (legacy compat)
Lista nodos que tendrian filename Markdown derivado.

---

#### workspace_read_file (legacy compat)
Lee nodo por filename o slug.

---

### Escritura

#### workspace_upsert_node
Crea o actualiza un nodo en SQLite. No genera exports Markdown.

**Parametros:**
- `slug` (requerido), `title` (requerido), `kind` (requerido)
- `summary`, `body`, `status` (default `active`)
- `parent`, `aliases`, `filename`
- `workspace`

**Validacion:** si el workspace objetivo no esta en `active_workspaces`, devuelve error.

---

#### workspace_link_nodes
Crea o actualiza una relacion entre nodos en SQLite.

**Parametros:** `from_ref` (requerido), `to_ref` (requerido), `edge_type` (requerido), `weight` (default 1.0), `workspace`

**edge_types:** `contains`, `details`, `related_to`, `project_of`, `depends_on`, `references`

---

### Proyectos

#### workspace_create_project
Crea directorio `code/{name}/`, su nodo DB y relaciones.

---

### Exports y Migracion

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
Migra carpetas legacy a SQLite, mueve codigo a `code/`, archiva originales.

---

### Coordinacion Agente

#### workspace_sync_agent_docs
Actualiza nodos `agent-team` y `agent-log` desde tabla events.

---

#### workspace_agent_status
Estado agentico resumido para UI/monitor.

---

#### workspace_record_agent_event
Registra evento estructurado para orquestacion.

**Parametros:** `event_type` (requerido), `agent_id`, `task_id`, `summary`, `details`, `node_ref`, `extra`, `workspace`

---

#### workspace_scan_artifacts
Escanea `code/` y actualiza tabla artifacts.

---

#### workspace_claim_task
Registra que un agente toma una tarea.

---

#### workspace_complete_task
Registra que una tarea termino.

---

## 4. Prefetch — Algoritmo de Dos Niveles

El prefetch se dispara antes de cada turno del agente. Objetivo: que el LLM pueda responder preguntas simples sin necesidad de llamar a tools.

### Constantes (definidas en el codigo)

```python
PREFETCH_FULL_NODES = 2     # Primeros resultados: contenido completo
PREFETCH_SUMMARY_NODES = 6  # Resultados restantes: solo titulo + summary
PREFETCH_MIN_SCORE = 0.05   # Umbral minimo BM25 para filtrar ruido
```

### Flujo

```
Query del usuario
        ↓
_cross_workspace_search(query, limit=8, include_index=False)
        ↓
Filtrado por score >= 0.05
        ↓
[:8] primeros resultados
        ↓
Para i, nodo in enumerate(resultados):
    si i < 2 (PREFETCH_FULL_NODES):
        → contenido COMPLETO renderizado como Markdown
    sino:
        → solo "titulo — summary"
        ↓
Join con "\n\n---\n\n"
```

### Ejemplo de salida inyectada

```
[arete/10-que-es-arete] (score: 0.142)

# Aretê — Filosofia y Sistema

Contenido completo del nodo...

---

[laia_arch/hermes-core-architecture.md] (score: 0.089)

# Arquitectura General de Hermes Agent

Contenido completo del nodo...

---

[arete/20-arquitectura.md] (score: 0.071) — Arquitectura del sistema. Contiene docs de backend...
[doyouwin/readme.md] (score: 0.055) — Readme: DoYouWin...
[pixelcore/readme.md] (score: 0.048) — PixelCore — Indice...
```

### Modo no-all-indexes

Si `inject_mode` es `index` (no `all-indexes`), el prefetch usa `store.prefetch(query, limit=2)` del WorkspaceStore directamente.

---

## 5. Write Guard — Active Workspaces

Antes de ejecutar cualquier tool de escritura, el plugin verifica que el workspace objetivo este en `active_workspaces`.

### Tools protegidas (MUTATING_DB_TOOLS)

```python
MUTATING_DB_TOOLS = {
    "workspace_upsert_node",
    "workspace_link_nodes",
    "workspace_create_project",
    "workspace_ensure_structure",
    "workspace_migrate_legacy",
    "workspace_scan_artifacts",
    "workspace_record_agent_event",
    "workspace_claim_task",
    "workspace_complete_task",
    "workspace_sync_agent_docs",
}
```

### Logica de verificacion

```python
def _is_writable(self, workspace: str) -> bool:
    return workspace in self._active_workspaces()

# En handle_tool_call(), justo despues de resolver el workspace:
if tool_name in MUTATING_DB_TOOLS and not self._is_writable(workspace):
    return json.dumps({
        "error": f"El workspace '{workspace}' es de solo lectura.",
        "active_workspaces": self._active_workspaces(),
        "hint": "Usa workspace_list_workspaces para ver los workspaces editables.",
    })
```

### Respuesta de error

```json
{
  "error": "El workspace 'doyouwin' es de solo lectura.",
  "active_workspaces": ["arete"],
  "hint": "Usa workspace_list_workspaces para ver los workspaces editables."
}
```

---

## 6. Cacheo y Watch

- `_watched_mtimes`: dict `{workspace: db_mtime}` para detectar cambios
- `_check_for_changes()`: compara mtimes, rebuild si changed
- `_cached_block`: bloque renderizado cacheado
- `_prefetch_cache`: dict `{query: resultado}` con lock

Rebuild automatico cuando:
1. `system_prompt_block()` y `_cached_block is None`
2. `_check_for_changes()` retorna `True`
3. Cualquier tool que modifica la DB llama `_rebuild_block()`
4. El archivo `config.yaml` cambia de mtime

---

## 7. Modelo de Eventos

| Evento | Cuando |
|---|---|
| `node_created` | `workspace_upsert_node` crea nuevo |
| `node_updated` | `workspace_upsert_node` actualiza existente |
| `edge_linked` | `workspace_link_nodes` crea relacion |
| `artifacts_scanned` | `workspace_scan_artifacts` corre |
| `markdown_exported` | `workspace_export_markdown` genera context/ |
| `organized_markdown_exported` | genera docs/db-export/ |
| `exports_cleaned` | `workspace_clean_exports` corre |
| `agent_task_start` | `workspace_claim_task` |
| `agent_task_done` | `workspace_complete_task` |
| `agent_docs_synced` | `workspace_sync_agent_docs` regenera notas |
| `legacy_migration_done` | `workspace_migrate_legacy` termina OK |
| `legacy_migration_failed` | migracion termina sin verificar |


> 📅 Documentado: 2026-05-08
