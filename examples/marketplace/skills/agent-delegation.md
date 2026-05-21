---
name: agent-delegation
description: >
  Permite delegar sub-tareas a sub-agentes efímeros con scope estrecho
  (profile=general/coder/researcher/writer).
version: 0.1.0
---

# Delegación a sub-agentes

Tienes 3 tools del toolset `agent_delegation`:

| Tool | Cuándo |
|---|---|
| `spawn_child(purpose, prompt, profile?)` | Cuando una task tiene dos sub-tareas claramente separables. |
| `list_active_children()` | Ver los que aún están corriendo en esta sesión. |
| `kill_child(child_id)` | Cancelar uno colgado. |

## Profiles disponibles

| Profile | Toolset | Cuándo |
|---|---|---|
| `general` | clarify, todo | Por defecto. Pensar, plan, escribir. Sin I/O. |
| `coder` | file, terminal, clarify | Modificar código, ejecutar scripts. |
| `researcher` | web, fetch_url, clarify | Investigar online. |
| `writer` | clarify, todo | Redactar texto largo y limpio. |

## Reglas duras (no se pueden saltar)

1. **Depth=1**: el child NO tiene `agent_delegation` toolset, no puede spawn-ear otro child.
2. **Max 3 children concurrentes** por sesión. Si llegas al límite, cierra uno con `kill_child` antes de spawn-ear otro.
3. **TTL 5 min** por child. Si se cuelga, status pasa a `timeout`.
4. **Sync**: `spawn_child` BLOQUEA tu turno hasta que el child termine. No es fire-and-forget. Si la sub-tarea es muy larga, mejor schedule un job (`schedule_create`) que delegar.

## Buenas prácticas

- **Purpose corto y descriptivo**: "investigar requisitos Motorflash" es bueno, "haz algo" es malo.
- **Prompt completo y self-contained**: el child no ve tu conversación, solo tu prompt. Inclúyele el contexto necesario.
- **Combina profiles**: para "investiga X y resume", spawnea primero `researcher` con el prompt de investigación, luego pasa su respuesta como contexto a un `writer`.
- **No abuses**: 3 children por sesión es el límite, pero usar 2-3 children en una sola conversación ya es agresivo. Si lo necesitas, considera si la task merece un `schedule_create` en su lugar.

## Audit

Cada spawn deja una fila en `agent_child_runs` con purpose, profile,
prompt, response, tokens, duration, status. El admin lo ve en `events`
(event_type=`child_spawned`) y en el TUI futuro.
