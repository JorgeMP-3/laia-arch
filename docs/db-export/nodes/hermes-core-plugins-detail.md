# Hermes Core — Plugin System

## Metadata

- ID: `76`
- Slug: `hermes-core-plugins-detail`
- Kind: `doc`
- Status: `active`
- Filename: `hermes-core-plugins-detail.md`
- Parent: `hermes-core-components`
- Source kind: `manual`
- Created at: `2026-05-08T08:24:00.088263+00:00`
- Updated at: `2026-05-19T11:33:14.566183+00:00`
- Aliases: `hermes-core-plugins-detail`

## Summary

Sistema de plugins: memory plugins, workspace context, skills, MCP tools y plugin discovery

## Body

# Hermes Core — Plugin System

Plugins extienden Hermes con providers de memoria, skills, y herramientas adicionales.

## Plugin Structure

~/.laia/plugins/ — directory raíz de plugins

## Memory Plugins

plugins/memory/ — providers de memoria external:
- mem0/ — mem0.ai v2
- holographic/ — holographic memory con store + retrieval
- honcho/ — Honcho CLI (cli.py, client.py, session.py)
- hindsight/ — hindsight provider
- openviking/ — OpenViking
- retaindb/ — retaindb
- supermemory/ — Supermemory

### Plugin Registration
MemoryManager acepta solo UN provider externo:
```python
self._memory_manager.add_provider(BuiltinMemoryProvider(...))
# Solo uno de estos:
self._memory_manager.add_provider(plugin_provider)
```

## Workspace Context Plugin

plugins/workspace-context/ — 20 tools para workspace DB:
- workspace_search_nodes, workspace_get_node, workspace_upsert_node
- workspace_link_nodes, workspace_list_all_nodes, workspace_scan_artifacts
- workspace_list_edges, workspace_list_events, workspace_export_markdown
- workspace_migrate_legacy

## Skill Plugins

~/.laia/skills/ — skills instalados:
- Cada skill = SKILL.md + scripts/ + references/
- agent/skill_commands.py escanea y inyecta como user message
- Skills se cargan en system prompt con platform conditions

## Hermes-CLI Plugin Commands

hermes_cli/plugins.py, hermes_cli/plugins_cmd.py:
- hermes plugins — list installed plugins
- Plugin discovery en ~/.laia/plugins/
- Enable/disable por platform

## Tool Plugin Discovery

tools/registry.py usa AST parsing para descubrir tools:
```python
def _module_registers_tools(module_path) -> bool:
    # Detecta registry.register() calls a nivel módulo
```

MCP tools: tools/mcp_tool.py (~1050 líneas)
- Dynamic discovery de servers MCP
- OAuth support (mcp_oauth.py)
- Structured content handling

## Plugin Context Engine

plugins/context_engine/ — Context Engine plugin con:
- WorkspaceStore en workspace_store/
- 20 tools en tools/
- FastAPI backend en workspace-ui/
- React frontend

## Example Plugin

plugins/example-dashboard/dashboard/plugin_api.py — template de ejemplo

> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `hermes-core-components` (Hermes Core Components) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Hermes Core — Plugin System

# Hermes Core — Plugin System

Plugins extienden Hermes con providers de memoria, skills, y herramientas adicionales.

## Plugin Structure

~/.laia/plugins/ — directory raíz de plugins

## Memory Plugins

plugins/memory/ — providers de memoria external:
- mem0/ — mem0.ai v2
- holographic/ — holographic memory con store + retrieval
- honcho/ — Honcho CLI (cli.py, client.py, session.py)
- hindsight/ — hindsight provider
- openviking/ — OpenViking
- retaindb/ — retaindb
- supermemory/ — Supermemory

### Plugin Registration
MemoryManager acepta solo UN provider externo:
```python
self._memory_manager.add_provider(BuiltinMemoryProvider(...))
# Solo uno de estos:
self._memory_manager.add_provider(plugin_provider)
```

## Workspace Context Plugin

plugins/workspace-context/ — 20 tools para workspace DB:
- workspace_search_nodes, workspace_get_node, workspace_upsert_node
- workspace_link_nodes, workspace_list_all_nodes, workspace_scan_artifacts
- workspace_list_edges, workspace_list_events, workspace_export_markdown
- workspace_migrate_legacy

## Skill Plugins

~/.laia/skills/ — skills instalados:
- Cada skill = SKILL.md + scripts/ + references/
- agent/skill_commands.py escanea y inyecta como user message
- Skills se cargan en system prompt con platform conditions

## Hermes-CLI Plugin Commands

hermes_cli/plugins.py, hermes_cli/plugins_cmd.py:
- hermes plugins — list installed plugins
- Plugin discovery en ~/.laia/plugins/
- Enable/disable por platform

## Tool Plugin Discovery

tools/registry.py usa AST parsing para descubrir tools:
```python
def _module_registers_tools(module_path) -> bool:
    # Detecta registry.register() calls a nivel módulo
```

MCP tools: tools/mcp_tool.py (~1050 líneas)
- Dynamic discovery de servers MCP
- OAuth support (mcp_oauth.py)
- Structured content handling

## Plugin Context Engine

plugins/context_engine/ — Context Engine plugin con:
- WorkspaceStore en workspace_store/
- 20 tools en tools/
- FastAPI backend en workspace-ui/
- React frontend

## Example Plugin

plugins/example-dashboard/dashboard/plugin_api.py — template de ejemplo

> 📅 Documentado: 2026-05-08
