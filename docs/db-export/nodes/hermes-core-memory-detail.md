# Hermes Core — Memory System

## Metadata

- ID: `74`
- Slug: `hermes-core-memory-detail`
- Kind: `doc`
- Status: `active`
- Filename: `hermes-core-memory-detail.md`
- Parent: `hermes-core-components`
- Source kind: `manual`
- Created at: `2026-05-08T08:23:33.404628+00:00`
- Updated at: `2026-05-08T08:23:33.404628+00:00`
- Aliases: `hermes-core-memory-detail`

## Summary

Sistema de memoria en capas: MemoryManager, MEMORY.md/USER.md, frozen snapshot pattern y plugins externos

## Body

# Hermes Core — Memory System

Sistema de memoria en capas: built-in (file-based) + plugin provider opcional.

## Architecture: MemoryManager

agent/memory_manager.py — Orchestrator central:
- BuiltinMemoryProvider siempre registrado primero (no removable)
- Solo UN provider externo permitido — previene tool schema bloat y backends conflictivos
- API:
  - build_system_prompt() → string para injectar en system prompt
  - prefetch_all(user_message) → recall antes del turno
  - sync_all(user_msg, assistant_response) → persist después del turno
  - queue_prefetch_all(user_msg) → queue siguiente prefetch

## Builtin Memory: memory_tool.py

MEMORY.md + USER.md — file-backed, persist across sessions:

### MEMORY.md
Notas personales del agente: project conventions, tool quirks, environment facts

### USER.md
Perfil del usuario: preferencias, communication style, workflow habits

### Diseño Clave
- Entry delimiter: § (section sign)
- Mid-session writes → archivo en disco inmediato (durable)
- System prompt NO cambia mid-session → preserva prefix cache
- Snapshot se refresca en próximo session start
- Character limits (no tokens) — model-independent

### memory tool actions
- add — append entry con delimiter
- replace — short substring matching + replace
- remove — delete por substring match
- read — muestra ambas stores

### Security
- _MEMORY_THREAT_PATTERNS — detecta prompt injection, role hijack, exfiltration via curl/wget con secrets, authorized_keys backdoor
- Content con threats → bloqueado y logueado

## Frozen Snapshot Pattern

1. Session start: lee MEMORY.md + USER.md → string frozen
2. Inyecta en system prompt como <memory-context>...</memory-context> con fence tags
3. Mid-session writes van a archivo, NO a system prompt
4. Next session: fresh snapshot

## External Plugin Providers

Directorio plugins/memory/:
- mem0/ — mem0.ai v2 integration
- holographic/ — holographic memory (store + retrieval)
- honcho/ — Honcho CLI + session/client
- hindsight/ — hindsight provider
- openviking/ — OpenViking integration
- retaindb/ — retaindb plugin
- supermemory/ — Supermemory integration

Cada provider implementa MemoryProvider interface (agent/memory_provider.py).

## Context Fencing

_FENCE_TAG_RE — regex para strip fence tags
_INTERNAL_CONTEXT_RE — strip injected context blocks
_INTERNAL_NOTE_RE — strip "[System note: ...]" wrappers
sanitize_context() — limpia todo para que no se confunda con user input

## Context Engine Integration

agent/context_engine.py — workspace DB-first context management:
- WorkspaceStore: schema SQLite con FTS5
- 20 tools de workspace context engine
- Prefetch + inject modes
- Ver: plugins/workspace-context/ + workspaces/laia_arch/

> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `hermes-core-components` (Hermes Core Components) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Hermes Core — Memory System

# Hermes Core — Memory System

Sistema de memoria en capas: built-in (file-based) + plugin provider opcional.

## Architecture: MemoryManager

agent/memory_manager.py — Orchestrator central:
- BuiltinMemoryProvider siempre registrado primero (no removable)
- Solo UN provider externo permitido — previene tool schema bloat y backends conflictivos
- API:
  - build_system_prompt() → string para injectar en system prompt
  - prefetch_all(user_message) → recall antes del turno
  - sync_all(user_msg, assistant_response) → persist después del turno
  - queue_prefetch_all(user_msg) → queue siguiente prefetch

## Builtin Memory: memory_tool.py

MEMORY.md + USER.md — file-backed, persist across sessions:

### MEMORY.md
Notas personales del agente: project conventions, tool quirks, environment facts

### USER.md
Perfil del usuario: preferencias, communication style, workflow habits

### Diseño Clave
- Entry delimiter: § (section sign)
- Mid-session writes → archivo en disco inmediato (durable)
- System prompt NO cambia mid-session → preserva prefix cache
- Snapshot se refresca en próximo session start
- Character limits (no tokens) — model-independent

### memory tool actions
- add — append entry con delimiter
- replace — short substring matching + replace
- remove — delete por substring match
- read — muestra ambas stores

### Security
- _MEMORY_THREAT_PATTERNS — detecta prompt injection, role hijack, exfiltration via curl/wget con secrets, authorized_keys backdoor
- Content con threats → bloqueado y logueado

## Frozen Snapshot Pattern

1. Session start: lee MEMORY.md + USER.md → string frozen
2. Inyecta en system prompt como <memory-context>...</memory-context> con fence tags
3. Mid-session writes van a archivo, NO a system prompt
4. Next session: fresh snapshot

## External Plugin Providers

Directorio plugins/memory/:
- mem0/ — mem0.ai v2 integration
- holographic/ — holographic memory (store + retrieval)
- honcho/ — Honcho CLI + session/client
- hindsight/ — hindsight provider
- openviking/ — OpenViking integration
- retaindb/ — retaindb plugin
- supermemory/ — Supermemory integration

Cada provider implementa MemoryProvider interface (agent/memory_provider.py).

## Context Fencing

_FENCE_TAG_RE — regex para strip fence tags
_INTERNAL_CONTEXT_RE — strip injected context blocks
_INTERNAL_NOTE_RE — strip "[System note: ...]" wrappers
sanitize_context() — limpia todo para que no se confunda con user input

## Context Engine Integration

agent/context_engine.py — workspace DB-first context management:
- WorkspaceStore: schema SQLite con FTS5
- 20 tools de workspace context engine
- Prefetch + inject modes
- Ver: plugins/workspace-context/ + workspaces/laia_arch/

> 📅 Documentado: 2026-05-08
