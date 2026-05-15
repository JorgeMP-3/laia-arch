---
name: context-engine-docs
description: >
  Documentar features del Context Engine desde analisis de codigo fuente hasta nodos
  en la BD de laia-arch. Workflow: leer BD existente -> investigar codigo real ->
  generar plan -> esperar aprobacion -> ejecutar. Solo para el workspace laia-arch.
version: "1.0.0"
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [context-engine, documentation, db-first, laia-arch, code-analysis]
    category: documentation
---

# Context Engine — Documentacion Desde Codigo Fuente

Skill para documentar implementaciones nuevas del Context Engine en la BD de laia-arch.
Usa esta skill cuando una implementacion de plugin/backend/frontend cambio el comportamiento
del Context Engine y hay que reflejarlo en la documentacion de la BD.

## Contexto

El Context Engine tiene su documentacion en `workspace laia-arch`.
La fuente de verdad para el codigo es:
- Plugin: `LAIA/.laia-core/plugins/memory/workspace-context/__init__.py`
- Backend: `/home/laia-arch/LAIA/.laia-arch/workspace-ui/backend/main.py`
- Config: `/home/laia-arch/LAIA/config.yaml`

## Flujo Completo

### 1. Leer la BD existente (OBLIGATORIO antes de todo)

No generar ningun plan hasta haber leido la documentacion actual.

```
workspace_get_node("context-engine")           # proyecto indice
workspace_search_nodes("nombre de feature", workspace="laia-arch", limit=8)
workspace_get_node("context-engine-docs-02-plugin")  # plugin actual
```

Solo si los nodos NO cubren la feature, se justifica documentar.
Si la BD ya describe correctamente lo que se implemento, no hacer nada.

### 2. Investigar el codigo fuente (ANTES de generar plan)

Leer con `read_file` (offset/limit), no con `search_files`. El plan debe basarse
en lo que el codigo REALMENTE hace, no en lo que se esperaba que hiciera.

Para el plugin Context Engine, las areas clave son:

| Seccion | Lineas aprox | Que buscar |
|---|---|---|
| Constantes de config | 23-42 | nuevos campos, nuevas constantes |
| `_active_workspace` / `_active_workspaces` | 175-187 | multi-workspace activo |
| `_resolve_prefetch` | 307-326 | algoritmo de prefetch |
| `handle_tool_call` | 710-750 | write guard, MUTATING_DB_TOOLS |
| `get_config_schema` | ~85-116 | schema de configuracion |
| `plugin.yaml` | completo | config_schema del plugin |

Para el backend:
| Seccion | Lineas aprox | Que buscar |
|---|---|---|
| `_context_engine_config` | 214-232 | campos de config del API |
| `_write_config` | 197-203 | persistencia de config |
| Nuevos endpoints | 923-950 | PUT /toggle-active |

Verificar constantes exactas (valores numericos, nombres de funciones) antes de documentarlas.

### 3. Generar plan de documentacion

El plan debe incluir:
- Que nodos de la BD estan desactualizados (listarlos con id y slug)
- Que contenido nuevo o reescrito necesitan
- Criterios de verificacion: como confirmar que la doc esta bien despues

**Nota sobre agentes**: documentar en laia-arch es trabajo para UN SOLO AGENTE por defecto.
Solo considerar multi-agente si el usuario pide explícitamente distribuir tareas o hay volumen que justifique paralelización real.

Regla: presentar plan ANTES de ejecutar. No documentar sin aprobacion.

### 4. Ejecutar solo lo aprobado

- Usar `workspace_upsert_node` para crear/actualizar nodos
- Usar `workspace_link_nodes` para enlazar nodos nuevos
- Verificar cada nodo con `workspace_get_node` tras crearlo
- Al terminar, `workspace_sync_agent_docs` para sincronizar agent-team y agent-log

## Errores Comunes

- **Generar plan multi-agente para trabajo monousuario**: el usuario lo ha corregido explicitamente.
  Documentar nodos en laia-arch es trabajo para UN SOLO AGENTE. No asignar trabajo a "Claude Code 2" o "Codex".
  Solo considerar multi-agente si el usuario pide explícitamente distribuir tareas o hay volumen que justifique paralelización real.
- **Generar plan sin leer la BD primero**: el usuario lo ha rechazado explicitamente.
  Siempre leer `context-engine` y la doc existente antes de hacer nada.
- **Generar plan sin verificar el codigo fuente**: el usuario pidio "verificar el codigo de verdad antes de crear el plan".
  Leer el codigo fuente con `read_file` (offset/limit) antes de generar cualquier plan.
- **Asumir que el issue/plan describe lo que se implemento**: el codigo fuente es la
  unica verdad. El issue puede estar desactualizado o la implementacion puede diferir.
- **Documentar sin verificar el codigo**: leer con `read_file`, no con `search_files`.
  Las funciones, constantes y endpoints reales estan en el codigo.
- **No distinguir entre nodos heredados y nodos reescritos**: un nodo reescrito necesita
  actualizarse completamente; no vale anadir una nota al final.

## Estructura De Nodos Esperada En laia-arch

```
laia-arch workspace (id=1)
├── context-engine                           kind=project
│   ├── context-engine-docs-02-plugin        kind=doc  (plugin + prefetch)
│   ├── context-engine-docs-03-web-ui        kind=doc  (backend + frontend)
│   ├── context-engine-docs-01-workspace-store kind=doc (WorkspaceStore)
│   ├── context-engine-docs-04-migration     kind=doc  (migracion)
│   └── context-engine-docs-05-scripts       kind=doc  (scripts)
├── hermes-core                              kind=project
│   ├── hermes-core-architecture             kind=doc
│   ├── hermes-core-agent                    kind=doc
│   ├── hermes-core-memory                   kind=doc  (incluye plugin provider)
│   └── ...
└── integrated-tools                         kind=project
    └── integrated-workspace-tools           kind=doc  (skills workspace-*)
```

## Configuracion Actual Del Plugin

Campos en `plugins.workspace-context` de `config.yaml`:

| Campo | Tipo | Descripcion |
|---|---|---|
| `workspace` | string | Workspace activo por defecto para escritura |
| `active_workspaces` | list | Workspaces donde se permiten escrituras |
| `workspaces` | list | Workspaces legibles en modo all-indexes |
| `inject_mode` | string | `index` o `all-indexes` |
| `max_chars` | int | Limite de caracteres para el bloque inyectado |

## Referencia Rapida: Constantes De Prefetch

```
MAX_PREFETCH_NODES = 5      # total legacy (ya no se usa directamente)
PREFETCH_FULL_NODES = 2     # nodos con body completo en prefetch
PREFETCH_SUMMARY_NODES = 6  # nodos con solo summary en prefetch
PREFETCH_MIN_SCORE = 0.05  # umbral BM25 minimo para incluir resultado
```

## Nodos De Contexto Relevantes

- `laia-arch/context-engine` (id=62) — proyecto indice del Context Engine
- `laia-arch/context-engine-docs-02-plugin` (id=63) — documentacion del plugin
- `laia-arch/integrated-workspace-tools` (id=55) — skills workspace-read/write
