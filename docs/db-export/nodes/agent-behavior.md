# Agent Behavior — General

## Metadata

- ID: `100`
- Slug: `agent-behavior`
- Kind: `doc`
- Status: `active`
- Filename: `agent-behavior.md`
- Parent: `coordinador`
- Source kind: `manual`
- Created at: `2026-05-08T08:34:03.967683+00:00`
- Updated at: `2026-05-08T08:34:03.967683+00:00`
- Aliases: `agent-behavior`

## Summary

Normas de trabajo para todos los agentes de este workspace.

## Body

# agents/behavior.md — Comportamiento general

Normas de trabajo para todos los agentes de este workspace.

---

## Antes de empezar cualquier sesión

1. Lee `agents/log.md` — qué se hizo antes y qué queda pendiente
2. Lee `agents/team.md` — qué rol tienes y quién hace qué
3. Usa `workspace_search_nodes` para orientarte en el workspace
4. Usa `workspace_get_node` para leer el nodo relevante

## Flujo de contexto nodal

**Orden obligatorio:**
`workspace_search_nodes` -> `workspace_get_node` -> artefactos reales si hace falta

- Fuente de verdad: `workspace.db`
- `context/*.md` y `docs/db-export/` son exports derivados — no los edites ni los uses como primer recurso
- `workspace_list_folder` / `workspace_read_workspace_file` — solo para logs, docs o scripts reales
- `workspace_read_file` — compatibilidad únicamente
- No uses `search_files` ni `session_search` para responder preguntas del workspace

## Al terminar cada sesión

1. Registra tu actividad en `agents/log.md`
2. Marca explícitamente qué queda pendiente
3. Si modificaste nodos, regenera el export Markdown

## Coordinación

- Scope exacto: haz lo que se pidió, ni más ni menos
- Si encuentras algo inesperado, repórtalo antes de actuar
- Si hay conflicto con otro agente, documéntalo en `log.md` y espera instrucción

---

→ Flujo diario de tools: skill `workspace-daily`


> 📅 Documentado: 2026-05-12

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `coordinador` (LAIA AGORA — Coordinador) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Agent Behavior — General

# agents/behavior.md — Comportamiento general

Normas de trabajo para todos los agentes de este workspace.

---

## Antes de empezar cualquier sesión

1. Lee `agents/log.md` — qué se hizo antes y qué queda pendiente
2. Lee `agents/team.md` — qué rol tienes y quién hace qué
3. Usa `workspace_search_nodes` para orientarte en el workspace
4. Usa `workspace_get_node` para leer el nodo relevante

## Flujo de contexto nodal

**Orden obligatorio:**
`workspace_search_nodes` -> `workspace_get_node` -> artefactos reales si hace falta

- Fuente de verdad: `workspace.db`
- `context/*.md` y `docs/db-export/` son exports derivados — no los edites ni los uses como primer recurso
- `workspace_list_folder` / `workspace_read_workspace_file` — solo para logs, docs o scripts reales
- `workspace_read_file` — compatibilidad únicamente
- No uses `search_files` ni `session_search` para responder preguntas del workspace

## Al terminar cada sesión

1. Registra tu actividad en `agents/log.md`
2. Marca explícitamente qué queda pendiente
3. Si modificaste nodos, regenera el export Markdown

## Coordinación

- Scope exacto: haz lo que se pidió, ni más ni menos
- Si encuentras algo inesperado, repórtalo antes de actuar
- Si hay conflicto con otro agente, documéntalo en `log.md` y espera instrucción

---

→ Flujo diario de tools: skill `workspace-daily`


> 📅 Documentado: 2026-05-12
