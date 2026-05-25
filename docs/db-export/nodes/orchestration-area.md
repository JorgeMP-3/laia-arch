# Orquestación y Command Center

## Metadata

- ID: `125`
- Slug: `orchestration-area`
- Kind: `topic`
- Status: `active`
- Filename: `orchestration-area.md`
- Parent: `hermes`
- Source kind: `manual`
- Created at: `2026-05-08T09:01:47.715212+00:00`
- Updated at: `2026-05-08T09:01:47.715212+00:00`
- Aliases: `orchestration-area`

## Summary

Sistemas de orquestación multi-agente y control

## Body

# Orquestación y Command Center

## Descripción

Sistemas que permiten la coordinación y control de múltiples agentes de forma autónoma.

## Componentes principales

### Command Center
Sistema PTY WebSocket multi-agente con 3 roles:
- **Planner**: Planifica tareas complejas
- **Worker**: Ejecuta tareas específicas
- **Supervisor**: Monitorea y corrige

Características:
- Arquitectura frontend moderna
- Cadena de delegación estructurada
- Control de flujo en tiempo real

### ToolContextInjector
Sistema genérico de dos capas para inyectar contexto:
- **Capa 1**: Contexto estático (app_context)
- **Capa 2**: Estado dinámico (variables de entorno)

Uso:
- Inyectar contexto en nuevas herramientas
- Mantener consistencia entre herramientas
- Reducir duplicación de código

## Documentos incluidos

- **command-center**: Orquestación multi-agente con 3 roles
- **tool-context-injection**: Sistema de inyección de contexto

## Casos de uso

1. **Delegación de tareas**: Un agente principal delega en sub-agentes
2. **Ejecución paralela**: Múltiples agentes trabajan simultáneamente
3. **Control de flujo**: Supervisión y corrección en tiempo real


## Relaciones salientes

- `contains` → `command-center` (Command Center — Multi-Agent Orchestration) [peso=1.00]
- `contains` → `tool-context-injection` (ToolContextInjector System) [peso=1.00]

## Relaciones entrantes

- `contains` ← `hermes` (Hermes — Núcleo técnico) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Orquestación y Command Center

# Orquestación y Command Center

## Descripción

Sistemas que permiten la coordinación y control de múltiples agentes de forma autónoma.

## Componentes principales

### Command Center
Sistema PTY WebSocket multi-agente con 3 roles:
- **Planner**: Planifica tareas complejas
- **Worker**: Ejecuta tareas específicas
- **Supervisor**: Monitorea y corrige

Características:
- Arquitectura frontend moderna
- Cadena de delegación estructurada
- Control de flujo en tiempo real

### ToolContextInjector
Sistema genérico de dos capas para inyectar contexto:
- **Capa 1**: Contexto estático (app_context)
- **Capa 2**: Estado dinámico (variables de entorno)

Uso:
- Inyectar contexto en nuevas herramientas
- Mantener consistencia entre herramientas
- Reducir duplicación de código

## Documentos incluidos

- **command-center**: Orquestación multi-agente con 3 roles
- **tool-context-injection**: Sistema de inyección de contexto

## Casos de uso

1. **Delegación de tareas**: Un agente principal delega en sub-agentes
2. **Ejecución paralela**: Múltiples agentes trabajan simultáneamente
3. **Control de flujo**: Supervisión y corrección en tiempo real

→ Command Center — Multi-Agent Orchestration: `command-center.md`
→ ToolContextInjector System: `tool-context-injection.md`
