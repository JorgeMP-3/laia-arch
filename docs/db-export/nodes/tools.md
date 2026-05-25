# Tools — Herramientas disponibles

## Metadata

- ID: `58`
- Slug: `tools`
- Kind: `doc`
- Status: `active`
- Filename: `tools.md`
- Parent: `hermes-core-components`
- Source kind: `manual`
- Created at: `2026-05-08T08:05:51.560044+00:00`
- Updated at: `2026-05-08T08:05:51.560044+00:00`
- Aliases: `tools`

## Summary

Sistema de herramientas del agente

## Body

# Tools — Herramientas disponibles

## Ubicación
~/LAIA/.laia-arch/tools/

## Categorías de herramientas

| Categoría | Ejemplos | Descripción |
|---|---|---|
| Filesystem | read_file, write_file, search_files | Operaciones con archivos |
| Code | execute_code, lint_code | Ejecución y análisis de código |
| Web | web_search, web_fetch | Búsqueda y obtención de web |
| Memory | session_search, memory_search | Búsqueda en memoria |
| Workspace | workspace_* | Gestión de workspaces |
| System | terminal_tool, process_tool | Operaciones del sistema |

## Toolsets
Los toolsets definen qué herramientas están disponibles en cada contexto:
- toolset_distributions.py: Distribuciones predefinidas
- toolsets.py: Definición de toolsets

## Crear nuevas herramientas
1. Crear archivo en tools/
2. Definir función con decorador @tool
3. Registrar en el toolset correspondiente


## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `hermes-core-components` (Hermes Core Components) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Tools — Herramientas disponibles

# Tools — Herramientas disponibles

## Ubicación
~/LAIA/.laia-arch/tools/

## Categorías de herramientas

| Categoría | Ejemplos | Descripción |
|---|---|---|
| Filesystem | read_file, write_file, search_files | Operaciones con archivos |
| Code | execute_code, lint_code | Ejecución y análisis de código |
| Web | web_search, web_fetch | Búsqueda y obtención de web |
| Memory | session_search, memory_search | Búsqueda en memoria |
| Workspace | workspace_* | Gestión de workspaces |
| System | terminal_tool, process_tool | Operaciones del sistema |

## Toolsets
Los toolsets definen qué herramientas están disponibles en cada contexto:
- toolset_distributions.py: Distribuciones predefinidas
- toolsets.py: Definición de toolsets

## Crear nuevas herramientas
1. Crear archivo en tools/
2. Definir función con decorador @tool
3. Registrar en el toolset correspondiente
