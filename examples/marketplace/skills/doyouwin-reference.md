---
name: doyouwin-reference
description: >
  Acceso de solo lectura al workspace `doyouwin` montado en AGORA — la
  base de conocimiento del proyecto J.R. Valle Automoción.
version: 0.1.0
---

# Workspace `doyouwin` (read-only)

Tienes acceso de lectura a un workspace adicional llamado `doyouwin` con
información sobre el proyecto **J.R. Valle Automoción** (jrvalle.com):
concesionario oficial SEAT, ŠKODA y CUPRA en Valencia. Incluye contexto
del cliente, modelos de referencia (Grupo Sala) y plataforma de renting
(Motorflash).

## Tools disponibles (toolset `secondary_workspace`)

| Tool | Args | Cuándo |
|---|---|---|
| `secondary_workspace_list` | `{}` | Para ver qué workspaces secundarios tienes montados |
| `secondary_workspace_search` | `{workspace="doyouwin", query, limit?}` | Búsqueda FTS sobre title+body+tags |
| `secondary_workspace_get_node` | `{workspace="doyouwin", slug_or_id}` | Leer un nodo por slug |
| `secondary_workspace_list_all_nodes` | `{workspace="doyouwin"}` | Vista de todo el grafo |
| `secondary_workspace_list_edges` | `{workspace="doyouwin"}` | Relaciones entre nodos |

## Convenciones del workspace

Slugs típicos en `doyouwin`:
- `index` — índice general del proyecto.
- `jrvalle-web-info` — requisitos del audio del cliente.
- `jrvalle-web-referencia` — análisis de webs de referencia.
- `jrvalle-web-spec` — especificación funcional.

Tipos de nodos: `index`, `project`, `topic`, `important`, `doc`,
`reference`, `script`, `agent-note`, `agent-plan`, `agent-log`.

## Reglas

- **No puedes modificar nada.** Las tools `_upsert`, `_link`, etc. no
  existen para este workspace. Si necesitas anotar algo nuevo, hazlo en
  tu `agent_area` o como `learning_record` — esos son los espacios de
  escritura del agente.
- Cuando el usuario pregunte por el proyecto jrvalle, SEAT, ŠKODA,
  CUPRA, Motorflash o Grupo Sala, considera buscar primero en
  `doyouwin` antes de improvisar.
- Cita el slug del nodo cuando uses información del workspace, para que
  el usuario pueda contrastarlo.
