# Agent Team — doyouwin

## Metadata

- ID: `101`
- Slug: `agent-team`
- Kind: `doc`
- Status: `active`
- Filename: `agent-team.md`
- Parent: `coordinador`
- Source kind: `manual`
- Created at: `2026-05-08T08:34:04.336706+00:00`
- Updated at: `2026-05-08T08:34:04.336706+00:00`
- Aliases: `agent-team`

## Summary

Roles asignados en este workspace. Define quién hace qué y cómo colaboran los agentes.

## Body

# agents/team.md — doyouwin

Roles asignados en este workspace. Define quién hace qué y cómo colaboran los agentes.

---

## Roles activos

Asigna aquí qué IA tiene qué rol en este workspace.
Un agente puede tener más de un rol si el equipo es pequeño.

| IA | Rol | Responsabilidad principal |
|----|-----|---------------------------|
| _(sin asignaciones — editar manualmente)_ | | |

---

## Roles disponibles

### Planificador
Diseña el plan antes de ejecutar. Parte del contexto nodal DB-first, entiende el
scope, identifica dependencias y riesgos, y produce un plan claro que el Ejecutor puede seguir.
**Cuándo actúa:** al inicio de cada sesión o tarea compleja.
**Output esperado:** plan estructurado en `agents/sessions/{id}/plan.md`

### Ejecutor
Implementa lo que el Planificador diseñó. No improvisa scope — si encuentra algo
no contemplado en el plan, lo documenta y consulta antes de actuar.
**Cuándo actúa:** tras el Planificador, o directamente en tareas pequeñas sin plan.
**Output esperado:** cambios en archivos + entrada en `agents/log.md`

### Revisor
Verifica el trabajo del Ejecutor antes de cerrar la sesión. Comprueba que el output
cumple el objetivo, que no hay archivos rotos, que los indicadores `→` son válidos
y que `agents/log.md` está actualizado.
**Cuándo actúa:** al final de cada sesión significativa.
**Output esperado:** aprobación explícita en log.md o lista de correcciones

### Documentador
Mantiene el contexto actualizado. Tras cambios importantes, actualiza `workspace.db`,
sus nodos y relaciones, y regenera `context/` cuando haga falta. Añade nodos si hay áreas nuevas.
**Cuándo actúa:** tras sesiones que cambian arquitectura, estado o decisiones clave.
**Output esperado:** `workspace.db` coherente, export actualizado e indicadores `→` correctos

---

## Protocolo de traspaso entre agentes

1. El agente saliente escribe en `agents/log.md`: qué hizo, qué archivos tocó, qué queda pendiente
2. El agente entrante lee `agents/log.md` antes de empezar
3. Si hay ambigüedad en el scope, documentar la duda en log.md y esperar instrucción
4. No sobreescribir trabajo reciente sin leer primero la entrada correspondiente en el log

<!-- hermes:agent-team-state:start -->

## Estado operativo automático

- Último evento considerado: `2026-05-04 15:34 UTC`
- Eventos considerados: `200`
- Tareas activas: `0`

| Agente | Tarea | Inicio | Evento |
|---|---|---|---|
| — | Sin tareas activas registradas | — | — |

<!-- hermes:agent-team-state:end -->

→ Plan — agent-request-web-flow-smoke-20260427154514 — claude-code-planner: `agent-plan-agent-request-web-flow-smoke-20260427154514-claude-code-planner.md`
→ Plan: LAIA Tools — Mejora y Nuevas Herramientas: `laia-tools-plan.md`
→ Request — agent-request-orchestrator-smoke: `agent-request-orchestrator-smoke.md`
→ Request — agent-request-web-flow-smoke-20260427154514: `agent-request-web-flow-smoke-20260427154514.md`
→ Request — Prueba flujo multi-IA DB-first: `agent-request-prueba-flujo-multia-db-first.md`
→ Task — agent-task-agent-request-web-flow-smoke-20260427154514-codex-dry: `agent-task-agent-request-web-flow-smoke-20260427154514-codex-dry.md`
→ Task — agent-task-orchestrator-smoke: `agent-task-orchestrator-smoke.md`


> 📅 Documentado: 2026-05-12

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `coordinador` (LAIA AGORA — Coordinador) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Agent Team — doyouwin

# agents/team.md — doyouwin

Roles asignados en este workspace. Define quién hace qué y cómo colaboran los agentes.

---

## Roles activos

Asigna aquí qué IA tiene qué rol en este workspace.
Un agente puede tener más de un rol si el equipo es pequeño.

| IA | Rol | Responsabilidad principal |
|----|-----|---------------------------|
| _(sin asignaciones — editar manualmente)_ | | |

---

## Roles disponibles

### Planificador
Diseña el plan antes de ejecutar. Parte del contexto nodal DB-first, entiende el
scope, identifica dependencias y riesgos, y produce un plan claro que el Ejecutor puede seguir.
**Cuándo actúa:** al inicio de cada sesión o tarea compleja.
**Output esperado:** plan estructurado en `agents/sessions/{id}/plan.md`

### Ejecutor
Implementa lo que el Planificador diseñó. No improvisa scope — si encuentra algo
no contemplado en el plan, lo documenta y consulta antes de actuar.
**Cuándo actúa:** tras el Planificador, o directamente en tareas pequeñas sin plan.
**Output esperado:** cambios en archivos + entrada en `agents/log.md`

### Revisor
Verifica el trabajo del Ejecutor antes de cerrar la sesión. Comprueba que el output
cumple el objetivo, que no hay archivos rotos, que los indicadores `→` son válidos
y que `agents/log.md` está actualizado.
**Cuándo actúa:** al final de cada sesión significativa.
**Output esperado:** aprobación explícita en log.md o lista de correcciones

### Documentador
Mantiene el contexto actualizado. Tras cambios importantes, actualiza `workspace.db`,
sus nodos y relaciones, y regenera `context/` cuando haga falta. Añade nodos si hay áreas nuevas.
**Cuándo actúa:** tras sesiones que cambian arquitectura, estado o decisiones clave.
**Output esperado:** `workspace.db` coherente, export actualizado e indicadores `→` correctos

---

## Protocolo de traspaso entre agentes

1. El agente saliente escribe en `agents/log.md`: qué hizo, qué archivos tocó, qué queda pendiente
2. El agente entrante lee `agents/log.md` antes de empezar
3. Si hay ambigüedad en el scope, documentar la duda en log.md y esperar instrucción
4. No sobreescribir trabajo reciente sin leer primero la entrada correspondiente en el log

<!-- hermes:agent-team-state:start -->

## Estado operativo automático

- Último evento considerado: `2026-05-04 15:34 UTC`
- Eventos considerados: `200`
- Tareas activas: `0`

| Agente | Tarea | Inicio | Evento |
|---|---|---|---|
| — | Sin tareas activas registradas | — | — |

<!-- hermes:agent-team-state:end -->

→ Plan — agent-request-web-flow-smoke-20260427154514 — claude-code-planner: `agent-plan-agent-request-web-flow-smoke-20260427154514-claude-code-planner.md`
→ Plan: LAIA Tools — Mejora y Nuevas Herramientas: `laia-tools-plan.md`
→ Request — agent-request-orchestrator-smoke: `agent-request-orchestrator-smoke.md`
→ Request — agent-request-web-flow-smoke-20260427154514: `agent-request-web-flow-smoke-20260427154514.md`
→ Request — Prueba flujo multi-IA DB-first: `agent-request-prueba-flujo-multia-db-first.md`
→ Task — agent-task-agent-request-web-flow-smoke-20260427154514-codex-dry: `agent-task-agent-request-web-flow-smoke-20260427154514-codex-dry.md`
→ Task — agent-task-orchestrator-smoke: `agent-task-orchestrator-smoke.md`


> 📅 Documentado: 2026-05-12
