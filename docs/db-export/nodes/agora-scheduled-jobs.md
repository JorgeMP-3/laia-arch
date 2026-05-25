# Scheduled Jobs — Tareas Programadas por Usuario

## Metadata

- ID: `216`
- Slug: `agora-scheduled-jobs`
- Kind: `doc`
- Status: `active`
- Filename: `agora-scheduled-jobs.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-19T08:33:53.525173+00:00`
- Updated at: `2026-05-19T08:33:53.525173+00:00`
- Aliases: `agora-scheduled-jobs`

## Summary

Usuarios pueden programar tareas con expresiones cron. El AgentScheduler (tick cada 30s) ejecuta jobs via AgentPool. Soporta one-shot, delivery local/telegram, auto-pause tras 5 fallos.

## Body

# Scheduled Jobs — Tareas Programadas por Usuario

> 📅 Documentado: 2026-05-18 | 342 tests backend

## Proposito

Cada usuario puede programar tareas recurrentes que su agente ejecutara automaticamente.
El scheduler corre como parte del ciclo de vida de FastAPI (lifespan).

## Archivos

| Archivo | Rol |
|---------|-----|
| `app/scheduler.py` | AgentScheduler: tick loop, cron parser, delivery, decay |
| DB: `agent_scheduled_jobs` | Estado de cada job |

## DB: agent_scheduled_jobs

```sql
agent_scheduled_jobs(id, user_id, name, cron_expr, prompt, deliver DEFAULT 'local',
    status DEFAULT 'active', last_run_at, last_result, last_error, next_run_at,
    runs_total, runs_failed, consecutive_failures, created_at, updated_at)
```

Indexado por `user_id` y `(status, next_run_at)`.

## Cron

Soporta expresiones cron de 5 campos + aliases:
- `@hourly`, `@daily`, `@weekly`
- One-shot: `in 5m`, `in 1h`, `in 30s`

## Ciclo de vida

1. `AgentScheduler._tick()` — cada 30s busca jobs con `next_run_at <= now()`
2. `_run_one_job()` — crea una sesion AIAgent via AgentPool, ejecuta el prompt
3. `deliver_result()` — entrega resultado via `local` (inbox) o `telegram` (async)
4. Tras cada ejecucion: `compute_next_run()` recalcula la proxima
5. Auto-pause: 5 fallos consecutivos → `status='paused'`
6. Al terminar: evicta la sesion del pool para no contaminar

## Delivery

| Modo | Descripcion |
|------|-------------|
| `local` | Resultado via inbox (coordinator_messages) |
| `telegram` | Envio async via Telegram gateway (asyncio.ensure_future) |
| `origin` | Resultado devuelto en el contexto original |

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Scheduled Jobs — Tareas Programadas por Usuario

# Scheduled Jobs — Tareas Programadas por Usuario

> 📅 Documentado: 2026-05-18 | 342 tests backend

## Proposito

Cada usuario puede programar tareas recurrentes que su agente ejecutara automaticamente.
El scheduler corre como parte del ciclo de vida de FastAPI (lifespan).

## Archivos

| Archivo | Rol |
|---------|-----|
| `app/scheduler.py` | AgentScheduler: tick loop, cron parser, delivery, decay |
| DB: `agent_scheduled_jobs` | Estado de cada job |

## DB: agent_scheduled_jobs

```sql
agent_scheduled_jobs(id, user_id, name, cron_expr, prompt, deliver DEFAULT 'local',
    status DEFAULT 'active', last_run_at, last_result, last_error, next_run_at,
    runs_total, runs_failed, consecutive_failures, created_at, updated_at)
```

Indexado por `user_id` y `(status, next_run_at)`.

## Cron

Soporta expresiones cron de 5 campos + aliases:
- `@hourly`, `@daily`, `@weekly`
- One-shot: `in 5m`, `in 1h`, `in 30s`

## Ciclo de vida

1. `AgentScheduler._tick()` — cada 30s busca jobs con `next_run_at <= now()`
2. `_run_one_job()` — crea una sesion AIAgent via AgentPool, ejecuta el prompt
3. `deliver_result()` — entrega resultado via `local` (inbox) o `telegram` (async)
4. Tras cada ejecucion: `compute_next_run()` recalcula la proxima
5. Auto-pause: 5 fallos consecutivos → `status='paused'`
6. Al terminar: evicta la sesion del pool para no contaminar

## Delivery

| Modo | Descripcion |
|------|-------------|
| `local` | Resultado via inbox (coordinator_messages) |
| `telegram` | Envio async via Telegram gateway (asyncio.ensure_future) |
| `origin` | Resultado devuelto en el contexto original |
