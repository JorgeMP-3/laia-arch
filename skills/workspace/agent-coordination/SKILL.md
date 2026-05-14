---
name: agent-coordination
description: >
  Usa esta skill cuando un agente de LAIA vaya a coordinar trabajo multi-agente,
  consultar o actualizar estado agentico, registrar planes/eventos, repartir tareas,
  o mantener los nodos `agent-team` (agent-note), `agent-log` (agent-log) y planes `agent-plan` desde workspace.db.
version: "1.0.0"
author: LAIA Agent
license: MIT
metadata:
  hermes:
    tags: [workspace, agents, coordination, orchestration, db-first, realtime]
    category: workspace
---

# Agent Coordination — LAIA DB-first

## Regla central

La fuente de verdad es `workspace.db`.

No trates `team.md` ni `log.md` como archivos fisicos canonicos. En LAIA son nodos:

- `agent-team` (`kind="agent-note"`)
- `agent-log` (`kind="agent-log"`)

La futura web debe poder leer el estado desde la DB: `events` para timeline realtime, `agent-team` para reparto de trabajo, `agent-log` para historial humano.

## Skill obligatoria adicional

Si el agente va a crear, modificar, enlazar o sincronizar cualquier dato en `workspace.db`, debe leer tambien:

```
~/.hermes/skills/workspace/workspace-write/SKILL.md
```

Esto es obligatorio para:

- subagentes encargados de documentacion o mantenimiento de DB
- agentes que actualicen `agent-team` o `agent-log`
- agentes que creen `agent-team`/`agent-behavior`, `agent-plan` o `agent-log`
- agentes que enlacen planes, tareas, decisiones o handoffs
- agentes que usen `workspace_upsert_node`, `workspace_link_nodes`, `workspace_claim_task`, `workspace_complete_task`, `workspace_record_agent_event` o `workspace_sync_agent_docs`

Esta skill define la coordinacion agentica; `workspace-write` define las reglas de escritura segura en el grafo.

## Codigo De Verificacion Para Tools Agenticas

Las herramientas agenticas que escriben en `workspace.db` usan el grupo
Coordinacion Agentica de `workspace-write`.

Codigo:

```text
verification_code="bitacora-nube-8"
```

Aplica a:

```text
workspace_claim_task
workspace_complete_task
workspace_record_agent_event
workspace_sync_agent_docs
```

Si ademas vas a crear nodos `agent-plan` o `agent-log` con
`workspace_upsert_node` o enlazarlos con `workspace_link_nodes`, esas tools usan
el grupo Nodos Y Enlaces:

```text
verification_code="brujula-cobre-17"
```

Si falta el codigo, la tool debe rechazar la llamada. Lee `workspace-write`
antes de usar el codigo de cada grupo.

## Skills obligatorias por agente externo

Antes de configurar o ejecutar un agente externo, lee su skill especifica:

| Agente | Skill obligatoria | Notas clave |
|---|---|---|
| Claude Code | `~/.hermes/skills/autonomous-ai-agents/claude-code/SKILL.md` | Preferir `claude -p` para automatizacion one-shot |
| Claude accounts | `~/.hermes/skills/devops/claude-code-accounts/SKILL.md` | Host usa Jorge; Docker usa Maribel con cuidado |
| Codex | `~/.hermes/skills/autonomous-ai-agents/codex/SKILL.md` | Requiere repo Git y PTY |
| OpenCode | `~/.hermes/skills/autonomous-ai-agents/opencode/SKILL.md` | Preferir `opencode run` para tareas acotadas |
| Subagentes | `~/.hermes/skills/software-development/subagent-driven-development/SKILL.md` | Usar tareas pequenas, contexto completo y revisiones |

No lances Claude Code, Codex u OpenCode desde el orquestador sin haber respetado la skill correspondiente.

## Herramientas principales

| Tool | Uso |
|---|---|
| `workspace_list_events` | Ver actividad reciente de agentes |
| `workspace_claim_task` | Registrar que tomas una tarea |
| `workspace_complete_task` | Registrar cierre de tarea |
| `workspace_record_agent_event` | Registrar eventos estructurados: planes, aprobaciones, handoffs, revisiones |
| `workspace_sync_agent_docs` | Actualizar `agent-team` y `agent-log` desde `events` |
| `workspace_agent_status` | Obtener estado resumido para LAIA/UI |
| `workspace_get_node` | Leer `agent-team`, `agent-log` u otro nodo |
| `workspace_upsert_node` | Crear planes como `agent-plan`, logs como `agent-log`; `agent-note` solo para `agent-team`/`agent-behavior` |
| `workspace_link_nodes` | Enlazar tareas, planes, docs y proyectos |

## Orquestador multi-IA

Para maniobrar agentes externos como Claude Code, Codex u OpenCode desde LAIA, usa:

```
~/.hermes/scripts/ai-orchestrator.py
```

Este script no sustituye `workspace.db`: lo usa como centro logistico.

Comandos principales:

| Comando | Uso |
|---|---|
| `init-config` | Crear registry `~/.hermes/ai-agents.json` |
| `list-agents` | Ver planners/workers configurados |
| `brief` | Crear request de LAIA como nodo `agent-plan` bajo `agent-team` |
| `request-plan` | Pedir plan a un planner fuerte |
| `approve-plan` | Registrar validacion de LAIA |
| `assign-worker` | Crear tarea y asignarla a un worker |
| `status` | Ver estado agentico del workspace |

Flujo recomendado:

```
python3 ~/.hermes/scripts/ai-orchestrator.py brief \
  --workspace NOMBRE \
  --objective "Objetivo de LAIA"

python3 ~/.hermes/scripts/ai-orchestrator.py request-plan \
  --workspace NOMBRE \
  --request agent-request-... \
  --agent claude-code-planner \
  --workdir code/PROYECTO

python3 ~/.hermes/scripts/ai-orchestrator.py approve-plan \
  --workspace NOMBRE \
  --plan agent-plan-...

python3 ~/.hermes/scripts/ai-orchestrator.py assign-worker \
  --workspace NOMBRE \
  --agent opencode-worker \
  --description "Tarea acotada para worker" \
  --workdir code/PROYECTO
```

Sin `--execute`, el orquestador prepara prompts y registra eventos. Con `--execute`, intenta lanzar el comando configurado para el agente en `~/.hermes/ai-agents.json`.

Para Codex, `--workdir` debe apuntar a un repositorio Git. Para Claude Code y OpenCode tambien es recomendable apuntar al proyecto real, no a la raiz de `~/.hermes`.

## Flujo obligatorio para tareas

Antes de trabajar:

1. Lee estado:
   ```
   workspace_agent_status()
   workspace_list_events(limit=30)
   ```
2. Reclama la tarea si vas a tocar algo relevante:
   ```
   workspace_claim_task(agent_id="codex", description="Implementar X")
   ```
3. Si hay plan, decision o handoff, registralo como evento o nodo `agent-plan`.
4. Al terminar:
   ```
   workspace_complete_task(event_id=ID_DE_CLAIM, agent_id="codex", result="Resumen breve")
   workspace_sync_agent_docs()
   ```

## Protocolo para reviews o busqueda de bugs

Cuando el usuario pida revisar una app, buscar bugs, incoherencias o problemas:

1. Registra la investigacion antes de hacer scans largos:
   ```
   workspace_claim_task(agent_id="laia", description="Review de bugs en AREA/RUTA")
   ```
2. Orientate con DB-first:
   ```
   workspace_search_nodes("nombre del proyecto area review")
   workspace_get_node("nodo-relevante")
   workspace_agent_status()
   ```
3. Valida la ruta real de codigo una sola vez. Si el usuario da `/Volumes/...` pero el workspace real esta en `~/.hermes/workspaces/...`, deja constancia de la equivalencia y usa una sola ruta canonica.
4. Para codigo real usa busqueda acotada antes de leer archivos grandes:
   - preferir `rg` sobre `grep`
   - buscar rutas, handlers, TODO/FIXME, errores, auth, fechas, null/undefined
   - leer solo los rangos relevantes despues de encontrar lineas
5. Evita leer repetidamente el mismo archivo completo. Si un archivo es grande, extrae secciones por linea.
6. No modifiques archivos durante una review salvo que el usuario lo pida explicitamente.
7. Registra hallazgos persistentes como nodo `agent-plan` si tienen valor:
   ```
   workspace_upsert_node(
     slug="agent-review-...",
     kind="agent-plan",
     summary="Bugs/riesgos detectados en ...",
     body="...",
     parent="agent-team"
   )
   ```
8. Cierra la tarea y sincroniza:
   ```
   workspace_complete_task(event_id=ID, agent_id="laia", result="Resumen de findings")
   workspace_sync_agent_docs()
   ```

Formato recomendado de salida:

```
Findings críticos
Findings importantes
Riesgos menores
Archivos revisados
Pruebas o comandos ejecutados
Siguiente acción recomendada
```

## Eventos recomendados

Usa `workspace_record_agent_event` para eventos que no son solo inicio/cierre:

| Event type | Cuando usarlo |
|---|---|
| `plan_submitted` | Un planificador entrega un plan |
| `plan_approved` | LAIA aprueba un plan |
| `worker_assigned` | LAIA asigna una tarea a un ejecutor |
| `handoff_recorded` | Un agente deja contexto para otro |
| `review_done` | Un revisor aprueba o pide correcciones |
| `blocked` | Una tarea queda bloqueada |
| `decision_recorded` | Se toma una decision importante |

Ejemplo:

```
workspace_record_agent_event(
  event_type="plan_approved",
  agent_id="hermes",
  task_id="task-123",
  summary="Plan aprobado para implementar sincronizacion agentica",
  details="Se aprueba fase 1: eventos + agent-team + agent-log."
)
```

## Planes y documentacion agentica

Si el contenido tiene valor persistente de plan/request/task/handoff, crea un nodo `agent-plan`:

```
workspace_upsert_node(
  slug="agent-plan-task-123",
  title="Plan — task-123",
  kind="agent-plan",
  summary="Plan tecnico aprobado para task-123",
  body="...",
  parent="agent-team"
)
workspace_link_nodes(
  from_ref="agent-team",
  to_ref="agent-plan-task-123",
  edge_type="contains"
)
```

No metas planes largos solo en payloads de eventos. Los eventos son timeline; los nodos son memoria navegable.

## Documentador automatico

Despues de cambios agenticos importantes, ejecuta:

```
workspace_sync_agent_docs()
```

O desde shell:

```
python3 ~/.hermes/scripts/agent-documenter.py --workspace NOMBRE
```

Modo continuo:

```
python3 ~/.hermes/scripts/agent-documenter.py --workspace NOMBRE --watch --interval 5
```

El documentador es idempotente: si no hay cambios relevantes, no debe ensuciar la DB.

## Convenciones de roles

| Rol | Responsabilidad |
|---|---|
| LAIA | Orquesta, valida, aprueba planes, reparte tareas y controla estado DB-first |
| Planificador | Convierte objetivos en planes tecnicos y tareas verificables |
| Ejecutor | Implementa tareas acotadas y reporta mediante eventos |
| Revisor | Verifica diff, tests, scope y registra `review_done` |
| Documentador | Sincroniza `agent-team`, `agent-log` y docs agenticas |

## Buenas practicas

- Mantener tareas pequenas, con scope claro y agente responsable.
- Registrar eventos estructurados antes que texto libre suelto.
- Crear nodos `agent-plan` o `agent-log` para planes, decisiones y handoffs persistentes. `agent-note` queda reservado para `agent-team` y `agent-behavior`.
- Enlazar nodos relacionados para que el grafo explique el trabajo.
- Sincronizar `agent-team` y `agent-log` al final de cada bloque de trabajo.
- No regenerar exports Markdown salvo que el usuario o la UI los necesiten.

## Para la futura web

La UI debe leer:

- `events` para timeline realtime.
- `workspace_agent_status` para vista rapida.
- nodo `agent-team` para reparto de trabajo.
- nodo `agent-log` para historial humano.
- nodos `agent-plan` y `agent-log` enlazados para planes, revisiones, decisiones y handoffs.

## Encaje con la taxonomia actual

- `agent-node` es legacy; usa `agent-note`, `agent-plan` o `agent-log` segun el proposito.
- `agent-note` vive bajo `index` o proyecto; `agent-plan` vive bajo `agent-team`; `agent-log` vive bajo `index` si es global o bajo un `agent-plan` si es log de plan.
- Para trabajo nuevo, usa `contains`; `details` y `project_of` son legacy.
- Antes de coordinar cambios sensibles, revisa `important` global o del proyecto/topic afectado.
- Si falta estructura base, usa `workspace_ensure_structure()` antes de crear nodos agenticos.
