# Hermes Core — Multi-Agent System

## Metadata

- ID: `75`
- Slug: `hermes-core-multi-agent-detail`
- Kind: `doc`
- Status: `active`
- Filename: `hermes-core-multi-agent-detail.md`
- Parent: `hermes-core-components`
- Source kind: `manual`
- Created at: `2026-05-08T08:23:44.011775+00:00`
- Updated at: `2026-05-08T08:23:44.011775+00:00`
- Aliases: `hermes-core-multi-agent-detail`

## Summary

Sistema de subagentes: delegate tool, batch mode, MOA, ACP adapter, RL training y environment backends

## Body

# Hermes Core — Multi-Agent System

Sistema de subagentes con contexto aislado y toolsets restringidos.

## Delegate Tool (tools/delegate_tool.py)

Spawns child AIAgent instances:

### Características
- Contexto fresco (no parent history)
- task_id aislado (own terminal session, file ops cache)
- Toolset restringido (configurable, blocked tools siempre stripped)
- System prompt focalizado desde el goal + contexto
- Parent solo ve delegation call + summary result

### Bloqueos Fijos
```python
DELEGATE_BLOCKED_TOOLS = frozenset([
    "delegate_task",   # no recursive delegation
    "clarify",         # no user interaction
    "memory",          # no writes to shared MEMORY.md
    "send_message",    # no cross-platform side effects
    "execute_code",    # children should reason step-by-step
])
```

### Límites
- MAX_DEPTH = 2 — parent (0) → child (1) → grandchild rejected (2)
- DEFAULT_MAX_CONCURRENT_CHILDREN = 3 (configurable via config.yaml)
- DEFAULT_MAX_ITERATIONS = 50 por subagent

### Toolset Filter
Excluye toolsets: debugging, safe, delegation, moa, rl, hermes-*
Solo incluye toolsets donde no todas las tools están bloqueadas.

## Batch Mode

Parallel delegation con ThreadPoolExecutor:
- _get_max_concurrent_children() lee de config.yaml
- Fallback: env var → default 3
- Parent blocks hasta todos children completen

## Mixture of Agents (MOA)

tools/mixture_of_agents_tool.py:
- Top-K agent selection
- Collaborative routing

## ACP Adapter (acp_adapter/)

VS Code / Zed / JetBrains integration:
- server.py — ACP server
- session.py — session management
- auth.py — authentication
- tools.py — tool exposure
- permissions.py — permission system

## Trajectory Compression

trajectory_compressor.py (~63KB):
- Compress agent trajectories para RL training
- Token-budget aware
- Structured output processing

## RL Training

rl_cli.py + environments/:
- agentic_opd_env.py — agentic RL environment
- hermes_swe_env/ — SWE-bench style environment
- Tool call parsers: deepseek, glm, kimi, llama, qwen, mistral, etc.
- tool_call_parsers/ — per-model parsing

## Environment Backends

Soportados para code execution:
- local — ejecución local
- docker — contenedor Docker
- ssh — SSH remoted
- modal — Modal cloud
- daytona — Daytona cloud IDE
- singularity — Singularity containers

> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `hermes-core-components` (Hermes Core Components) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Hermes Core — Multi-Agent System

# Hermes Core — Multi-Agent System

Sistema de subagentes con contexto aislado y toolsets restringidos.

## Delegate Tool (tools/delegate_tool.py)

Spawns child AIAgent instances:

### Características
- Contexto fresco (no parent history)
- task_id aislado (own terminal session, file ops cache)
- Toolset restringido (configurable, blocked tools siempre stripped)
- System prompt focalizado desde el goal + contexto
- Parent solo ve delegation call + summary result

### Bloqueos Fijos
```python
DELEGATE_BLOCKED_TOOLS = frozenset([
    "delegate_task",   # no recursive delegation
    "clarify",         # no user interaction
    "memory",          # no writes to shared MEMORY.md
    "send_message",    # no cross-platform side effects
    "execute_code",    # children should reason step-by-step
])
```

### Límites
- MAX_DEPTH = 2 — parent (0) → child (1) → grandchild rejected (2)
- DEFAULT_MAX_CONCURRENT_CHILDREN = 3 (configurable via config.yaml)
- DEFAULT_MAX_ITERATIONS = 50 por subagent

### Toolset Filter
Excluye toolsets: debugging, safe, delegation, moa, rl, hermes-*
Solo incluye toolsets donde no todas las tools están bloqueadas.

## Batch Mode

Parallel delegation con ThreadPoolExecutor:
- _get_max_concurrent_children() lee de config.yaml
- Fallback: env var → default 3
- Parent blocks hasta todos children completen

## Mixture of Agents (MOA)

tools/mixture_of_agents_tool.py:
- Top-K agent selection
- Collaborative routing

## ACP Adapter (acp_adapter/)

VS Code / Zed / JetBrains integration:
- server.py — ACP server
- session.py — session management
- auth.py — authentication
- tools.py — tool exposure
- permissions.py — permission system

## Trajectory Compression

trajectory_compressor.py (~63KB):
- Compress agent trajectories para RL training
- Token-budget aware
- Structured output processing

## RL Training

rl_cli.py + environments/:
- agentic_opd_env.py — agentic RL environment
- hermes_swe_env/ — SWE-bench style environment
- Tool call parsers: deepseek, glm, kimi, llama, qwen, mistral, etc.
- tool_call_parsers/ — per-model parsing

## Environment Backends

Soportados para code execution:
- local — ejecución local
- docker — contenedor Docker
- ssh — SSH remoted
- modal — Modal cloud
- daytona — Daytona cloud IDE
- singularity — Singularity containers

> 📅 Documentado: 2026-05-08
