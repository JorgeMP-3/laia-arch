# Plan de documentacion multi-agente

## Metadata

- ID: `70`
- Slug: `coordinador-agentes`
- Kind: `doc`
- Status: `active`
- Filename: `coordinador-agentes.md`
- Parent: `coordinador`
- Source kind: `manual`
- Created at: `2026-05-08T08:21:08.912062+00:00`
- Updated at: `2026-05-19T11:13:52.675710`
- Aliases: `coordinador-agentes`

## Summary

Plan para coordinar agentes (MiniMax, Claude, etc.) en la documentacion del ecosistema LAIA. NO confundir con LAIA AGORA (coordinador).

## Body

# Plan de documentacion multi-agente

> **NOTA**: Este documento NO describe a LAIA AGORA (el coordinador del ecosistema). Describe un plan para usar multiples agentes de IA (MiniMax, Claude, etc.) para documentar el ecosistema LAIA en este workspace. Para el coordinador, ver `coordinador.md`.

## Objetivo
Coordinar agentes (MiniMax, Claude, etc.) para documentar exhaustivamente el ecosistema LAIA en laia-ecosystem.

## Fuentes de documentacion

### 1. Base de datos laia_arch (45 nodos)
- **Hermes Core**: 9 documentos (agent, architecture, commands, memory, multi-agent, plugins, tools, vision, voice)
- **Context Engine**: 5 documentos (workspace-store, plugin, web-ui, migration, scripts)
- **Workspace UI**: 4 documentos (overview, backend, frontend, general)
- **Integrated Tools**: 4 documentos (openclaw, usageai, workspace-tools, general)
- **Skills**: 3 documentos (apple, dogfood, workhard)
- **Agentes**: 4 documentos (behavior, team, log, master-plan)
- **Otros**: command-center, tool-context-injection, laia-tools

### 2. Documentacion en ~/LAIA/docs/docs/ (13 archivos)
- arquitectura, servicios, nginx, cloudflare, laia-arch, docker, arranque, mantenimiento, samba, migracion-familiamp, command-center, tool-context-injection, tool-ui-architecture

### 3. Documentacion en ~/LAIA/docs/context-engine/ (6 archivos)

## Plan de distribucion de tareas

### Agente 1: Hermes Core (9 documentos)
### Agente 2: Context Engine + Workspace UI (9 documentos)
### Agente 3: Infraestructura ARCH (13 documentos)
### Agente 4: Skills y herramientas (7 documentos)
### Agente 5: Coordinacion y AGORA (6 documentos)

## Coordinacion

### Antes de empezar
1. Cada agente lee su asignacion
2. Verifica que el nodo no existe ya en laia-ecosystem
3. Usa workspace_upsert_node para crear el nodo
4. Usa workspace_link_nodes para enlazar al padre correcto

### Durante el trabajo
- Leer el archivo fuente completo
- Crear nodo con summary y body completos
- Enlazar al padre correcto (project o topic)
- Verificar con workspace_get_node

### Al terminar
- Reportar nodos creados
- Verificar que todos los enlaces estan correctos
- Actualizar este documento con el estado

> 📅 Documentado: 2026-05-12

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `coordinador` (LAIA AGORA — Coordinador) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Plan de documentacion multi-agente

# Plan de documentacion multi-agente

> **NOTA**: Este documento NO describe a LAIA AGORA (el coordinador del ecosistema). Describe un plan para usar multiples agentes de IA (MiniMax, Claude, etc.) para documentar el ecosistema LAIA en este workspace. Para el coordinador, ver `coordinador.md`.

## Objetivo
Coordinar agentes (MiniMax, Claude, etc.) para documentar exhaustivamente el ecosistema LAIA en laia-ecosystem.

## Fuentes de documentacion

### 1. Base de datos laia_arch (45 nodos)
- **Hermes Core**: 9 documentos (agent, architecture, commands, memory, multi-agent, plugins, tools, vision, voice)
- **Context Engine**: 5 documentos (workspace-store, plugin, web-ui, migration, scripts)
- **Workspace UI**: 4 documentos (overview, backend, frontend, general)
- **Integrated Tools**: 4 documentos (openclaw, usageai, workspace-tools, general)
- **Skills**: 3 documentos (apple, dogfood, workhard)
- **Agentes**: 4 documentos (behavior, team, log, master-plan)
- **Otros**: command-center, tool-context-injection, laia-tools

### 2. Documentacion en ~/LAIA/docs/docs/ (13 archivos)
- arquitectura, servicios, nginx, cloudflare, laia-arch, docker, arranque, mantenimiento, samba, migracion-familiamp, command-center, tool-context-injection, tool-ui-architecture

### 3. Documentacion en ~/LAIA/docs/context-engine/ (6 archivos)

## Plan de distribucion de tareas

### Agente 1: Hermes Core (9 documentos)
### Agente 2: Context Engine + Workspace UI (9 documentos)
### Agente 3: Infraestructura ARCH (13 documentos)
### Agente 4: Skills y herramientas (7 documentos)
### Agente 5: Coordinacion y AGORA (6 documentos)

## Coordinacion

### Antes de empezar
1. Cada agente lee su asignacion
2. Verifica que el nodo no existe ya en laia-ecosystem
3. Usa workspace_upsert_node para crear el nodo
4. Usa workspace_link_nodes para enlazar al padre correcto

### Durante el trabajo
- Leer el archivo fuente completo
- Crear nodo con summary y body completos
- Enlazar al padre correcto (project o topic)
- Verificar con workspace_get_node

### Al terminar
- Reportar nodos creados
- Verificar que todos los enlaces estan correctos
- Actualizar este documento con el estado

> 📅 Documentado: 2026-05-12
