# AGORA Tool Forwarder — Plugin de Redireccion

## Metadata

- ID: `203`
- Slug: `agora-forwarder`
- Kind: `doc`
- Status: `active`
- Filename: `agora-forwarder.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-18T11:03:34.645662+00:00`
- Updated at: `2026-05-18T12:01:07.613016+00:00`
- Aliases: `agora-forwarder`

## Summary

Plugin en .laia-core/plugins/agora-executor-forwarder/ (740 LOC). Intercepta tool calls. Filesystem/bash -> executor. Web/vision -> local AGORA.

## Body

# AGORA Tool Forwarder Plugin

## .laia-core/plugins/agora-executor-forwarder/__init__.py (740 LOC)

## Constantes
EXECUTOR_TOOLS: 22 tools que se forwardean (file ops, bash, patch, private_workspace_*, python_exec, process_*, cron_*)
AGORA_LOCAL_DENY: 6 tools BLOQUEADAS (execute_code, process, cronjob, skill_manage, delegate_task, moa)
MAX_REGISTRY_SIZE: 1024 soft cap cross-thread

## Mecanismo cross-thread
AIAgent ejecuta en ThreadPoolExecutor. Forwarder usa registro compartido via sys.modules para saber a QUE container enviar cada tool call.
Funciones: register_context(task_id, slug, ip, token, port) / unregister_context(task_id).

## Flujo
LLM decide write_file -> hook pre_tool_call -> EXECUTOR_TOOLS? SI -> POST http://ip:9091/exec -> executor ejecuta -> resultado -> AIAgent

## Timeouts: bash/process_* 180s, apply_patch 60s, workspace_* 60s, resto 30s
## Auditoria: agora.forwarder.audit: decision (forwarded|denied|timeout|network_error), tool, slug, latency_ms

## Marketplace v0.1 (Fase G)

_extra_forwarded_tools(): lee LAIA_FORWARDED_TOOLS_EXTRA del entorno. Si un plugin instalado registra tools nuevas que deben forwardearse al executor, se añaden via esta variable. El AgentPool la setea al materializar el marketplace.

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# AGORA Tool Forwarder — Plugin de Redireccion

# AGORA Tool Forwarder Plugin

## .laia-core/plugins/agora-executor-forwarder/__init__.py (740 LOC)

## Constantes
EXECUTOR_TOOLS: 22 tools que se forwardean (file ops, bash, patch, private_workspace_*, python_exec, process_*, cron_*)
AGORA_LOCAL_DENY: 6 tools BLOQUEADAS (execute_code, process, cronjob, skill_manage, delegate_task, moa)
MAX_REGISTRY_SIZE: 1024 soft cap cross-thread

## Mecanismo cross-thread
AIAgent ejecuta en ThreadPoolExecutor. Forwarder usa registro compartido via sys.modules para saber a QUE container enviar cada tool call.
Funciones: register_context(task_id, slug, ip, token, port) / unregister_context(task_id).

## Flujo
LLM decide write_file -> hook pre_tool_call -> EXECUTOR_TOOLS? SI -> POST http://ip:9091/exec -> executor ejecuta -> resultado -> AIAgent

## Timeouts: bash/process_* 180s, apply_patch 60s, workspace_* 60s, resto 30s
## Auditoria: agora.forwarder.audit: decision (forwarded|denied|timeout|network_error), tool, slug, latency_ms

## Marketplace v0.1 (Fase G)

_extra_forwarded_tools(): lee LAIA_FORWARDED_TOOLS_EXTRA del entorno. Si un plugin instalado registra tools nuevas que deben forwardearse al executor, se añaden via esta variable. El AgentPool la setea al materializar el marketplace.
