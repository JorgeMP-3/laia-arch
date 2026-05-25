# Agent Delegation — Agentes Hijos Efimeros

## Metadata

- ID: `214`
- Slug: `agora-agent-delegation`
- Kind: `doc`
- Status: `active`
- Filename: `agora-agent-delegation.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-19T08:33:53.493336+00:00`
- Updated at: `2026-05-19T08:33:53.493336+00:00`
- Aliases: `agora-agent-delegation`

## Summary

Perfiles de sub-agentes (child_profiles.py). Un agente puede spawnear hijos con toolset restringido via spawn_child. Max 3 concurrentes, timeout 5min.

## Body

# Agent Delegation — Agentes Hijos Efimeros

> 📅 Documentado: 2026-05-18 | 342 tests backend

## Proposito

Un agente de usuario puede delegar tareas a sub-agentes efimeros (child agents) con
perfiles predefinidos y herramientas restringidas. Util para dividir trabajo complejo.

## Archivos

| Archivo | Rol |
|---------|-----|
| `app/child_profiles.py` | Define perfiles: general, coder, researcher, writer |
| `app/chat_engine.py` | Tool `spawn_child` ejecuta la delegacion |
| DB: `agent_child_runs` | Track de ejecuciones hijas |

## Perfiles

```python
CHILD_PROFILES = {
    "general":    {"toolsets": ["clarify","todo"], "max_iterations": 5},
    "coder":      {"toolsets": ["file","terminal","clarify"], "max_iterations": 10},
    "researcher": {"toolsets": ["web","fetch_url","clarify"], "max_iterations": 10},
    "writer":     {"toolsets": ["clarify","todo"], "max_iterations": 5},
}
DEFAULT_PROFILE = "general"
MAX_CONCURRENT_CHILDREN = 3
CHILD_TIMEOUT_SECONDS = 300  # 5 minutos
```

## Restricciones

Los hijos **nunca** tienen acceso a:
- `agent_self` — no pueden modificarse
- `agent_scheduler` — no pueden programar tareas
- `agent_delegation` — no pueden spawnear mas hijos (previene recursion)

## DB: agent_child_runs

```sql
agent_child_runs(parent_user_id, parent_session_id, profile, purpose,
    prompt, response, tokens_used, duration_ms, status, error,
    started_at, finished_at)
```

Indexado por `(parent_user_id, started_at)` y `parent_session_id`.

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Agent Delegation — Agentes Hijos Efimeros

# Agent Delegation — Agentes Hijos Efimeros

> 📅 Documentado: 2026-05-18 | 342 tests backend

## Proposito

Un agente de usuario puede delegar tareas a sub-agentes efimeros (child agents) con
perfiles predefinidos y herramientas restringidas. Util para dividir trabajo complejo.

## Archivos

| Archivo | Rol |
|---------|-----|
| `app/child_profiles.py` | Define perfiles: general, coder, researcher, writer |
| `app/chat_engine.py` | Tool `spawn_child` ejecuta la delegacion |
| DB: `agent_child_runs` | Track de ejecuciones hijas |

## Perfiles

```python
CHILD_PROFILES = {
    "general":    {"toolsets": ["clarify","todo"], "max_iterations": 5},
    "coder":      {"toolsets": ["file","terminal","clarify"], "max_iterations": 10},
    "researcher": {"toolsets": ["web","fetch_url","clarify"], "max_iterations": 10},
    "writer":     {"toolsets": ["clarify","todo"], "max_iterations": 5},
}
DEFAULT_PROFILE = "general"
MAX_CONCURRENT_CHILDREN = 3
CHILD_TIMEOUT_SECONDS = 300  # 5 minutos
```

## Restricciones

Los hijos **nunca** tienen acceso a:
- `agent_self` — no pueden modificarse
- `agent_scheduler` — no pueden programar tareas
- `agent_delegation` — no pueden spawnear mas hijos (previene recursion)

## DB: agent_child_runs

```sql
agent_child_runs(parent_user_id, parent_session_id, profile, purpose,
    prompt, response, tokens_used, duration_ms, status, error,
    started_at, finished_at)
```

Indexado por `(parent_user_id, started_at)` y `parent_session_id`.
