# AGORA Rediseno — Cerebro Centralizado + Executors Finos

## Metadata

- ID: `201`
- Slug: `agora-rediseno`
- Kind: `doc`
- Status: `active`
- Filename: `agora-rediseno.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-18T11:03:34.611369+00:00`
- Updated at: `2026-05-18T16:10:02.472798+00:00`
- Aliases: `agora-rediseno`

## Summary

Documenta el cambio arquitectonico de sprint 2 al rediseno v2.1. Cerebro en laia-agora, executors ligeros en containers de usuario.

## Body

# AGORA Rediseno v2.1

## Sprint 2 tenia .laia-core/ DENTRO de cada container -> forzaba sandbox -> usuario enjaulado.
## Solucion: separar cerebro (AIAgent, LLM) del cuerpo (ejecucion).

**laia-agora**: UNICO container con .laia-core/, AGORA Backend, AgentPool, tool forwarder
**laia-executor**: FastAPI (~300 LOC) en cada container de usuario. POST /exec, 22 tools, root.

## Flujo de un chat

1. Usuario -> AGORA UI -> POST /api/agents/me/chat
2. AGORA -> AgentPool.get_or_create(session_id) -> AIAgent
3. AIAgent.run_conversation() -> LLM (DeepSeek/Anthropic/OpenAI)
4. LLM decide: write_file("/home/user/script.py", "...")
5. ToolForwarder intercepta -> POST http://container_ip:9091/exec
6. laia-executor ejecuta write_file como root
7. AIAgent recibe resultado -> LLM continua
8. SSE stream -> AGORA UI -> usuario

## Archivos clave

| Archivo | Proposito |
|---------|-----------|
| .laia-core/plugins/agora-executor-forwarder/__init__.py | Plugin forwarder (740 LOC) |
| services/laia-executor/src/laia_executor/api.py | FastAPI executor (POST /exec) |
| services/agora-backend/app/agent_pool.py | Pool de AIAgent (TTL 60min) |
| services/agora-backend/app/admin.py | Control Center (/api/admin/*) |
| infra/lxd/image-build/build-agora-image.sh | Imagen LXD del cerebro |
| infra/lxd/scripts/rebuild-1-2-3-4.sh | Reconstruccion total |

## Eliminado del sprint 2

services/laia-runtime/ entero (daemon, tasks, agent_wrapper, sandbox), .laia-core/tools/agora_sandbox.py, LAIA_PROFILE=agora-agent

## Naming v2 — agent-<slug> (Mayo 2026)

Contenedores nuevos: `agent-<slug>` (antes `laia-<slug>`).
`laia-agora` y `laia-jorge` legacy protegidos, no renombrados.
Ver `agora-naming-v2` para detalle.

> 📅 Actualizado: 2026-05-18

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# AGORA Rediseno — Cerebro Centralizado + Executors Finos

# AGORA Rediseno v2.1

## Sprint 2 tenia .laia-core/ DENTRO de cada container -> forzaba sandbox -> usuario enjaulado.
## Solucion: separar cerebro (AIAgent, LLM) del cuerpo (ejecucion).

**laia-agora**: UNICO container con .laia-core/, AGORA Backend, AgentPool, tool forwarder
**laia-executor**: FastAPI (~300 LOC) en cada container de usuario. POST /exec, 22 tools, root.

## Flujo de un chat

1. Usuario -> AGORA UI -> POST /api/agents/me/chat
2. AGORA -> AgentPool.get_or_create(session_id) -> AIAgent
3. AIAgent.run_conversation() -> LLM (DeepSeek/Anthropic/OpenAI)
4. LLM decide: write_file("/home/user/script.py", "...")
5. ToolForwarder intercepta -> POST http://container_ip:9091/exec
6. laia-executor ejecuta write_file como root
7. AIAgent recibe resultado -> LLM continua
8. SSE stream -> AGORA UI -> usuario

## Archivos clave

| Archivo | Proposito |
|---------|-----------|
| .laia-core/plugins/agora-executor-forwarder/__init__.py | Plugin forwarder (740 LOC) |
| services/laia-executor/src/laia_executor/api.py | FastAPI executor (POST /exec) |
| services/agora-backend/app/agent_pool.py | Pool de AIAgent (TTL 60min) |
| services/agora-backend/app/admin.py | Control Center (/api/admin/*) |
| infra/lxd/image-build/build-agora-image.sh | Imagen LXD del cerebro |
| infra/lxd/scripts/rebuild-1-2-3-4.sh | Reconstruccion total |

## Eliminado del sprint 2

services/laia-runtime/ entero (daemon, tasks, agent_wrapper, sandbox), .laia-core/tools/agora_sandbox.py, LAIA_PROFILE=agora-agent

## Naming v2 — agent-<slug> (Mayo 2026)

Contenedores nuevos: `agent-<slug>` (antes `laia-<slug>`).
`laia-agora` y `laia-jorge` legacy protegidos, no renombrados.
Ver `agora-naming-v2` para detalle.

> 📅 Actualizado: 2026-05-18
