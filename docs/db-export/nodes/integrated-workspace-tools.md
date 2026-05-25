# Workspace Skills

## Metadata

- ID: `94`
- Slug: `integrated-workspace-tools`
- Kind: `doc`
- Status: `active`
- Filename: `integrated-workspace-tools.md`
- Parent: `integrated-tools-area`
- Source kind: `manual`
- Created at: `2026-05-08T08:34:01.736646+00:00`
- Updated at: `2026-05-19T11:33:14.566183+00:00`
- Aliases: `integrated-workspace-tools`

## Summary

Workspace skills: gestion DB-first de conocimiento y codigo. Dos skills complementarias:

## Body

# Integrated Tools — Workspace Skills

# Integrated Tools — Workspace Skills

## Resumen

Workspace skills: gestion DB-first de conocimiento y codigo. Dos skills complementarias:

| Skill | Modo | Permisos |
|---|---|---|
| `workspace-read` | Solo lectura | Ninguna herramienta de escritura |
| `workspace-write` | Lectura + escritura | Todas las herramientas workspace_* |

## Workspace-Read (~/skills/workspace/workspace-read/SKILL.md)

### Regla absoluta

**Solo lectura. Nunca crear, modificar ni enlazar nodos.**

### Fuente de verdad

`workspace.db` (SQLite). Los archivos en `context/` y `docs/db-export/` son exports derivados.

### Estructura de un nodo

| Campo | Contenido |
|---|---|
| `slug` | Identificador unico estable |
| `kind` | `index`, `topic`, `detail`, `project`, `doc`, `agent-note`, `script` |
| `title` | Titulo del primer `# Heading` |
| `summary` | Resumen breve |
| `body` | Contenido completo Markdown |
| `aliases` | Nombres alternativos para busqueda |
| `parent` | Slug del nodo padre |
| `source_kind` | `seed`, `markdown-import`, `legacy-*`, `manual` |
| `status` | `active` o `archived` |

### Herramientas разрешенные

| Tool | Para que |
|---|---|
| `workspace_search_nodes` | Buscar con FTS5 |
| `workspace_get_node` | Leer nodo completo |
| `workspace_list_workspaces` | Ver workspaces disponibles |
| `workspace_list_folder` | Navegar `code/` |
| `workspace_read_workspace_file` | Leer archivo real en `code/` |

### Herramientas prohibidas

```
workspace_upsert_node, workspace_link_nodes, workspace_create_project,
workspace_claim_task, workspace_complete_task, workspace_export_markdown,
workspace_migrate_legacy, workspace_scan_artifacts, workspace_clean_exports,
workspace_verify_db_completeness
```

### Sintaxis FTS5

| Sintaxis | Ejemplo | Resultado |
|---|---|---|
| Palabras sueltas | `docker compose` | "docker" Y "compose" |
| OR explicito | `docker OR container` | Cualquiera de las dos |
| Frase exacta | `"nginx proxy"` | Frase exacta |
| Excluir | `docker NOT compose` | "docker" sin "compose" |
| Wildcards | `docker*` | Palabras que empiezan por "docker" |

### Flujo recomendado

```
1. workspace_list_workspaces()
2. workspace_get_node("index")
3. workspace_search_nodes("tema")
4. workspace_search_nodes("tema", kind="X")
5. workspace_get_node("slug")
6. workspace_list_folder("code/")
```

---

## Workspace-Write (~/skills/workspace/workspace-write/SKILL.md)

### Las dos capas del workspace

| Capa | Contiene | Se gestiona con |
|---|---|---|
| DB (workspace.db) | Nodos Markdown: docs, logs, team, behavior | `workspace_upsert_node`, `workspace_link_nodes` |
| `code/` | Codigo ejecutable: .py, .sh, .js, binarios | Terminal + `workspace_scan_artifacts` |

### Regla fundamental

| Contenido | Va en... |
|---|---|
| Documentacion, resumenes, contexto, conocimiento | DB (nodos) |
| Codigo ejecutable, scripts, binarios | `code/` |
| Logs, team, behavior de agentes | DB (nodos `agent-note`) |
| Documentacion de scripts | DB (nodo `kind=script`) |
| Script ejecutable en si mismo | `code/scripts/` |

### Herramientas disponibles

**Nodos (DB)**

| Tool | Accion |
|---|---|
| `workspace_upsert_node` | Crear o actualizar un nodo |
| `workspace_list_all_nodes` | Ver todos los nodos |
| `workspace_get_node` | Leer un nodo |
| `workspace_search_nodes` | Buscar nodos |

**Relaciones (edges)**

| Tool | Accion |
|---|---|
| `workspace_link_nodes` | Crear o actualizar una relacion |
| `workspace_list_edges` | Ver todas las relaciones |

**Artefactos (code/)**

| Tool | Accion |
|---|---|
| `workspace_list_folder` | Listar contenido de `code/` |
| `workspace_read_workspace_file` | Leer archivo real en `code/` |
| `workspace_scan_artifacts` | Indexar archivos en `code/` |

**Coordinacion**

| Tool | Accion |
|---|---|
| `workspace_claim_task` | Registrar que tomas una tarea |
| `workspace_complete_task` | Registrar que terminaste |
| `workspace_list_events` | Ver eventos activos |

### Crear un nodo

```python
workspace_upsert_node(
  slug="mi-nuevo-nodo",
  title="Mi Nuevo Nodo",
  kind="doc",
  summary="Breve descripcion",
  body="# Mi Nuevo Nodo\n\nContenido..."
)
```

### Tipos de relaciones

| Tipo | Significado |
|---|---|
| `contains` | A contiene a B (jerarquico) |
| `details` | A es detalle especifico de B |
| `references` | A menciona o referencia a B |
| `project_of` | A es proyecto de B |
| `depends_on` | A depende funcionalmente de B |

### Crear un workspace nuevo

```bash
python3 ~/.laia/scripts/create-workspace.py --name mi-workspace --activate
```

### Estructura de code/

```
workspaces/{nombre}/
├── workspace.db
├── code/
│   ├── scripts/           # scripts sueltos
│   ├── {proyecto1}/       # proyecto completo
│   └── {proyecto2}/
```

### Patrones de nodos

| Patron | Descripcion |
|---|---|
| Hub | Tema central conectado a muchos |
| Leaf | Nodo terminal sin salidas |
| Puente | Conecta dos areas distintas |
| Huerfano | Sin relaciones entrantes ni salientes |

---

## Agent-Coordination (~/skills/workspace/agent-coordination/SKILL.md)

Skill para coordinacion multi-agente. Obligatoria cuando:

- Se van a crear/modificar/enlazar datos en `workspace.db`
- Se van a actualizar `agent-team` o `agent-log`
- Se van a usar herramientas de tarea/evento

### Flujo obligatorio para tareas

```
1. workspace_agent_status()
2. workspace_list_events(limit=30)
3. workspace_claim_task(agent_id="mi-agente", description="...")
4. [trabajar]
5. workspace_complete_task(event_id=ID, agent_id="mi-agente", result="...")
6. workspace_sync_agent_docs()
```

### Orquestador multi-IA

```bash
python3 ~/.laia/scripts/ai-orchestrator.py brief --workspace NOMBRE --objective "..."
python3 ~/.laia/scripts/ai-orchestrator.py request-plan --workspace NOMBRE --request ... --agent claude-code-planner
python3 ~/.laia/scripts/ai-orchestrator.py assign-worker --workspace NOMBRE --agent opencode-worker --description "..."
```

## Nodos relacionados

- `integrated-tools` — indice maestro de todas las herramientas integradas
- `context-engine-docs/01-workspace-store` — schema SQLite, API Python, FTS5
- `context-engine-docs/02-plugin` — plugin: 20 tools, prefetch, inject modes
- `agent-team`, `agent-log` — nodos de coordinacion agentica


## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `integrated-tools-area` (Integrated Tools) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Workspace Skills

# Integrated Tools — Workspace Skills

# Integrated Tools — Workspace Skills

## Resumen

Workspace skills: gestion DB-first de conocimiento y codigo. Dos skills complementarias:

| Skill | Modo | Permisos |
|---|---|---|
| `workspace-read` | Solo lectura | Ninguna herramienta de escritura |
| `workspace-write` | Lectura + escritura | Todas las herramientas workspace_* |

## Workspace-Read (~/skills/workspace/workspace-read/SKILL.md)

### Regla absoluta

**Solo lectura. Nunca crear, modificar ni enlazar nodos.**

### Fuente de verdad

`workspace.db` (SQLite). Los archivos en `context/` y `docs/db-export/` son exports derivados.

### Estructura de un nodo

| Campo | Contenido |
|---|---|
| `slug` | Identificador unico estable |
| `kind` | `index`, `topic`, `detail`, `project`, `doc`, `agent-note`, `script` |
| `title` | Titulo del primer `# Heading` |
| `summary` | Resumen breve |
| `body` | Contenido completo Markdown |
| `aliases` | Nombres alternativos para busqueda |
| `parent` | Slug del nodo padre |
| `source_kind` | `seed`, `markdown-import`, `legacy-*`, `manual` |
| `status` | `active` o `archived` |

### Herramientas разрешенные

| Tool | Para que |
|---|---|
| `workspace_search_nodes` | Buscar con FTS5 |
| `workspace_get_node` | Leer nodo completo |
| `workspace_list_workspaces` | Ver workspaces disponibles |
| `workspace_list_folder` | Navegar `code/` |
| `workspace_read_workspace_file` | Leer archivo real en `code/` |

### Herramientas prohibidas

```
workspace_upsert_node, workspace_link_nodes, workspace_create_project,
workspace_claim_task, workspace_complete_task, workspace_export_markdown,
workspace_migrate_legacy, workspace_scan_artifacts, workspace_clean_exports,
workspace_verify_db_completeness
```

### Sintaxis FTS5

| Sintaxis | Ejemplo | Resultado |
|---|---|---|
| Palabras sueltas | `docker compose` | "docker" Y "compose" |
| OR explicito | `docker OR container` | Cualquiera de las dos |
| Frase exacta | `"nginx proxy"` | Frase exacta |
| Excluir | `docker NOT compose` | "docker" sin "compose" |
| Wildcards | `docker*` | Palabras que empiezan por "docker" |

### Flujo recomendado

```
1. workspace_list_workspaces()
2. workspace_get_node("index")
3. workspace_search_nodes("tema")
4. workspace_search_nodes("tema", kind="X")
5. workspace_get_node("slug")
6. workspace_list_folder("code/")
```

---

## Workspace-Write (~/skills/workspace/workspace-write/SKILL.md)

### Las dos capas del workspace

| Capa | Contiene | Se gestiona con |
|---|---|---|
| DB (workspace.db) | Nodos Markdown: docs, logs, team, behavior | `workspace_upsert_node`, `workspace_link_nodes` |
| `code/` | Codigo ejecutable: .py, .sh, .js, binarios | Terminal + `workspace_scan_artifacts` |

### Regla fundamental

| Contenido | Va en... |
|---|---|
| Documentacion, resumenes, contexto, conocimiento | DB (nodos) |
| Codigo ejecutable, scripts, binarios | `code/` |
| Logs, team, behavior de agentes | DB (nodos `agent-note`) |
| Documentacion de scripts | DB (nodo `kind=script`) |
| Script ejecutable en si mismo | `code/scripts/` |

### Herramientas disponibles

**Nodos (DB)**

| Tool | Accion |
|---|---|
| `workspace_upsert_node` | Crear o actualizar un nodo |
| `workspace_list_all_nodes` | Ver todos los nodos |
| `workspace_get_node` | Leer un nodo |
| `workspace_search_nodes` | Buscar nodos |

**Relaciones (edges)**

| Tool | Accion |
|---|---|
| `workspace_link_nodes` | Crear o actualizar una relacion |
| `workspace_list_edges` | Ver todas las relaciones |

**Artefactos (code/)**

| Tool | Accion |
|---|---|
| `workspace_list_folder` | Listar contenido de `code/` |
| `workspace_read_workspace_file` | Leer archivo real en `code/` |
| `workspace_scan_artifacts` | Indexar archivos en `code/` |

**Coordinacion**

| Tool | Accion |
|---|---|
| `workspace_claim_task` | Registrar que tomas una tarea |
| `workspace_complete_task` | Registrar que terminaste |
| `workspace_list_events` | Ver eventos activos |

### Crear un nodo

```python
workspace_upsert_node(
  slug="mi-nuevo-nodo",
  title="Mi Nuevo Nodo",
  kind="doc",
  summary="Breve descripcion",
  body="# Mi Nuevo Nodo\n\nContenido..."
)
```

### Tipos de relaciones

| Tipo | Significado |
|---|---|
| `contains` | A contiene a B (jerarquico) |
| `details` | A es detalle especifico de B |
| `references` | A menciona o referencia a B |
| `project_of` | A es proyecto de B |
| `depends_on` | A depende funcionalmente de B |

### Crear un workspace nuevo

```bash
python3 ~/.laia/scripts/create-workspace.py --name mi-workspace --activate
```

### Estructura de code/

```
workspaces/{nombre}/
├── workspace.db
├── code/
│   ├── scripts/           # scripts sueltos
│   ├── {proyecto1}/       # proyecto completo
│   └── {proyecto2}/
```

### Patrones de nodos

| Patron | Descripcion |
|---|---|
| Hub | Tema central conectado a muchos |
| Leaf | Nodo terminal sin salidas |
| Puente | Conecta dos areas distintas |
| Huerfano | Sin relaciones entrantes ni salientes |

---

## Agent-Coordination (~/skills/workspace/agent-coordination/SKILL.md)

Skill para coordinacion multi-agente. Obligatoria cuando:

- Se van a crear/modificar/enlazar datos en `workspace.db`
- Se van a actualizar `agent-team` o `agent-log`
- Se van a usar herramientas de tarea/evento

### Flujo obligatorio para tareas

```
1. workspace_agent_status()
2. workspace_list_events(limit=30)
3. workspace_claim_task(agent_id="mi-agente", description="...")
4. [trabajar]
5. workspace_complete_task(event_id=ID, agent_id="mi-agente", result="...")
6. workspace_sync_agent_docs()
```

### Orquestador multi-IA

```bash
python3 ~/.laia/scripts/ai-orchestrator.py brief --workspace NOMBRE --objective "..."
python3 ~/.laia/scripts/ai-orchestrator.py request-plan --workspace NOMBRE --request ... --agent claude-code-planner
python3 ~/.laia/scripts/ai-orchestrator.py assign-worker --workspace NOMBRE --agent opencode-worker --description "..."
```

## Nodos relacionados

- `integrated-tools` — indice maestro de todas las herramientas integradas
- `context-engine-docs/01-workspace-store` — schema SQLite, API Python, FTS5
- `context-engine-docs/02-plugin` — plugin: 20 tools, prefetch, inject modes
- `agent-team`, `agent-log` — nodos de coordinacion agentica
