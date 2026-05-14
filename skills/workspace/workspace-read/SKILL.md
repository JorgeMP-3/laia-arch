---
name: workspace-read
description: >
  Lectura y busqueda efectiva en workspaces Hermes DB-first. Usar cuando el
  agente necesite entender un workspace, localizar contexto, leer nodos,
  inspeccionar relaciones o consultar archivos reales sin modificar nada.
version: "6.0.0"
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [workspace, read-only, db-first, search, consulta]
    category: workspace
---

# Workspace — Lectura Y Busqueda

## Regla Absoluta

Solo lectura. No crees, modifiques, enlaces, borres, exportes, migres, repares
ni reorganices nodos.

Si necesitas cambiar algo, deja esta skill y carga `workspace-write`.

## Fuente De Verdad

La fuente de verdad es `workspace.db`.

`context/` y `docs/db-export/` son exports derivados para inspeccion o diff. No
los uses como entrada principal ni para decidir la estructura real.

## Modelo Mental Correcto

No hay nodos carpeta tipo `projects`, `topics`, `docs`, `references`,
`scripts`, `important` o `agent-notes`.

Los hijos directos del `index` son nodos reales con `kind` propio:

```text
index                                  kind=index
├── jrvalle-web                        kind=project
│   ├── jrvalle-web-mapa               kind=topic
│   │   ├── requisitos                 kind=doc
│   │   └── referencias-ui             kind=doc
│   ├── jrvalle-web-riesgos            kind=important
│   ├── deploy-jrvalle                 kind=script
│   └── grupo-sala                     kind=reference
├── arquitectura                       kind=topic
│   ├── api                            kind=doc
│   └── base-datos                     kind=doc
├── errores-globales                   kind=important
├── readme                             kind=doc
├── agent-behavior                     kind=agent-note
├── agent-team                         kind=agent-note
│   └── agent-plan-home                kind=agent-plan
│       └── agent-log-home             kind=agent-log
└── agent-log                          kind=agent-log
```

Nunca expliques la organizacion como carpetas pluralizadas. Aunque sea visual,
ese patron induce a crear nodos artificiales.

## Kinds

| Kind | Como leerlo |
|---|---|
| `index` | Punto de entrada unico. Orienta, no contiene todo el detalle. |
| `project` | Area de trabajo propia. Funciona como mini-index local. Leerlo antes de trabajar dentro del proyecto. |
| `topic` | Mapa de conocimiento con hijos. Debe guiar hacia docs relacionados. |
| `important` | Riesgos, errores pasados, advertencias, decisiones criticas y soluciones que evitan romper cosas. |
| `doc` | Informacion desarrollada sobre un tema concreto. |
| `script` | Automatizaciones, comandos o procesos ejecutables documentados. |
| `reference` | Fuentes externas, URLs, APIs o material de apoyo. |
| `agent-note` | Comportamiento/equipo estable: normalmente `agent-behavior` y `agent-team`. |
| `agent-plan` | Planes, requests, tasks o handoffs persistentes de agentes. |
| `agent-log` | Historial general o historial de un plan. |

`detail` y `agent-node` son legacy. Si aparecen, interpretalos con cuidado y no
los propagues en respuestas.

## Herramientas Permitidas

| Tool | Uso |
|---|---|
| `workspace_list_workspaces` | Ver workspaces disponibles. |
| `workspace_get_node` | Leer un nodo completo por slug, filename o id. |
| `workspace_search_nodes` | Buscar por concepto usando la DB/FTS. |
| `workspace_list_all_nodes` | Inventario de nodos. |
| `workspace_list_edges` | Ver relaciones del grafo. |
| `workspace_list_folder` | Navegar archivos reales bajo el workspace. |
| `workspace_read_workspace_file` | Leer archivos reales bajo el workspace. |
| `workspace_list_events` | Consultar actividad reciente. |
| `workspace_agent_status` | Consultar estado agentico. |

## Herramientas Prohibidas En Esta Skill

```text
workspace_upsert_node
workspace_link_nodes
workspace_create_project
workspace_ensure_structure
workspace_claim_task
workspace_complete_task
workspace_record_agent_event
workspace_sync_agent_docs
workspace_export_markdown
workspace_migrate_legacy
workspace_scan_artifacts
workspace_clean_exports
workspace_verify_db_completeness
```

## Flujo De Consulta

1. Orientate:
   ```text
   workspace_get_node("index")
   ```

2. Busca por concepto, no por carpetas imaginarias:
   ```text
   workspace_search_nodes("tema proyecto riesgo error decision")
   ```

3. Abre los nodos relevantes:
   ```text
   workspace_get_node("slug-encontrado")
   ```

4. Si vas a trabajar en un proyecto:
   ```text
   workspace_get_node("slug-del-project")
   workspace_search_nodes("riesgos errores decisiones", kind="important")
   ```

5. Si necesitas codigo real:
   ```text
   workspace_list_folder("code")
   workspace_read_workspace_file("code/ruta/relevante")
   ```

## Busqueda Efectiva

- Para entender un area: busca el nombre del area y abre primero `project` o
  `topic`.
- Para no romper nada: busca siempre `important` relacionado.
- Para detalle tecnico: abre `doc` hijos del `project` o `topic`.
- Para ejecucion: busca `script` y despues revisa archivos reales en `code/`.
- Para fuentes: busca `reference`.
- Para trabajo agentico: lee `agent-team`, `agent-behavior`, `agent-plan` y
  `agent-log` segun corresponda.

## Respuesta Al Usuario

Si el usuario pregunta como se organiza un workspace, responde con nodos reales
y `kind` explicito. No dibujes `projects/`, `topics/`, `docs/` ni otras
categorias pluralizadas.
