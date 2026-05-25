# Hermes Core — Tools

## Metadata

- ID: `77`
- Slug: `hermes-core-tools-detail`
- Kind: `doc`
- Status: `active`
- Filename: `hermes-core-tools-detail.md`
- Parent: `hermes-core-components`
- Source kind: `manual`
- Created at: `2026-05-08T08:24:12.711676+00:00`
- Updated at: `2026-05-08T08:24:12.711676+00:00`
- Aliases: `hermes-core-tools-detail`

## Summary

Sistema de herramientas auto-registrantes: ToolRegistry, built-in tools, execution flow y toolset distribution

## Body

# Hermes Core — Tools

Sistema de herramientas auto-registrantes con registry centralizado.

## Tool Registry (tools/registry.py)

Singleton ToolRegistry — cada tool file llama registry.register() al importar:

```python
def register(name, toolset, schema, handler, check_fn=None,
             requires_env=None, is_async=False, description="",
             emoji="", max_result_size_chars=None)
```

### ToolEntry Fields
- name, toolset, schema (JSON schema)
- handler (función)
- check_fn — availability check (ej: HASS_TOKEN para HomeAssistant)
- requires_env — env vars necesarias
- is_async — handler es async
- emoji — para display

## Built-in Tools (~30 files en tools/)

### Web
- web_tools.py — web_search, web_extract (Parallel + Firecrawl)
- Config: config.yaml → auxiliary.web_search, auxiliary.web_extract

### Terminal + Process
- terminal_tool.py — shell execution con PTY, compound commands, background
- process_registry.py — background process management

### File Operations
- file_tools.py — read_file, write_file, patch, search_files
- file_operations.py — sync operations con file locking (fcntl/msvcrt)
- path_security.py — path traversal guards

### Vision
- vision_tools.py — vision_analyze (base64 image from URL)
- image_generation_tool.py — image_generate (Stable Diffusion via FAL)

### Skills
- skills_tool.py — skill_manager_tool (load, reload, disable)
- skills_hub.py — browse/search/install skills

### Browser Automation
- browser_tool.py — browser_navigate, browser_snapshot, browser_click, etc.
- browser_cdp_tool.py — CDP commands
- browser_camofox.py — Camofox provider

### Code Execution
- code_execution_tool.py — execute_code sandbox
- Entornos: Docker, SSH, Modal, Daytona, Singularity, Local

### Delegation
- delegate_tool.py — subagent spawning con restricted toolsets
- MAX_DEPTH = 2 (parent → child → grandchild rejected)

### Memory
- memory_tool.py — MEMORY.md + USER.md management

### Home Assistant
- homeassistant_tool.py — ha_list_entities, ha_get_state, ha_call_service

### Cron
- cronjob_tools.py — cronjob management

### Messaging
- send_message_tool.py — cross-platform messaging (Telegram, Discord, etc.)
- discord_tool.py — Discord-specific

### Transcription + TTS
- transcription_tools.py — speech-to-text
- tts_tool.py — text-to-speech (Edge TTS, Nous TTS, Gemini TTS, Mistral TTS)

### MCP
- mcp_tool.py — MCP client (~1050 líneas)
- mcp_oauth.py, mcp_oauth_manager.py — OAuth flows
- Dynamic discovery + structured content

### Other
- approval.py — dangerous command detection
- clarify_tool.py — user clarification questions
- todo_tool.py — task tracking
- session_search_tool.py — FTS5 search en state.db
- transcription_tools.py — audio transcription
- env_passthrough.py — env var injection

## Tool Execution Flow

1. model_tools.get_tool_definitions() → lista de schemas (OpenAI format)
2. LLM returns tool_call
3. handle_function_call(name, args, task_id) → registry.dispatch()
4. _run_async() bridge → persistent event loop
5. Result → string

## Environment Checks

check_fn en cada tool:
- send_message — check: gateway running
- ha_list_entities — check: HASS_TOKEN env var
- browser_navigate — check: browser available

## Toolset Distribution

toolset_distributions.py:
- Define qué tools van en cada toolset
- toolsets.py: TOOLSETS dict (web, search, vision, terminal, moa, etc.)

> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `hermes-core-components` (Hermes Core Components) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Hermes Core — Tools

# Hermes Core — Tools

Sistema de herramientas auto-registrantes con registry centralizado.

## Tool Registry (tools/registry.py)

Singleton ToolRegistry — cada tool file llama registry.register() al importar:

```python
def register(name, toolset, schema, handler, check_fn=None,
             requires_env=None, is_async=False, description="",
             emoji="", max_result_size_chars=None)
```

### ToolEntry Fields
- name, toolset, schema (JSON schema)
- handler (función)
- check_fn — availability check (ej: HASS_TOKEN para HomeAssistant)
- requires_env — env vars necesarias
- is_async — handler es async
- emoji — para display

## Built-in Tools (~30 files en tools/)

### Web
- web_tools.py — web_search, web_extract (Parallel + Firecrawl)
- Config: config.yaml → auxiliary.web_search, auxiliary.web_extract

### Terminal + Process
- terminal_tool.py — shell execution con PTY, compound commands, background
- process_registry.py — background process management

### File Operations
- file_tools.py — read_file, write_file, patch, search_files
- file_operations.py — sync operations con file locking (fcntl/msvcrt)
- path_security.py — path traversal guards

### Vision
- vision_tools.py — vision_analyze (base64 image from URL)
- image_generation_tool.py — image_generate (Stable Diffusion via FAL)

### Skills
- skills_tool.py — skill_manager_tool (load, reload, disable)
- skills_hub.py — browse/search/install skills

### Browser Automation
- browser_tool.py — browser_navigate, browser_snapshot, browser_click, etc.
- browser_cdp_tool.py — CDP commands
- browser_camofox.py — Camofox provider

### Code Execution
- code_execution_tool.py — execute_code sandbox
- Entornos: Docker, SSH, Modal, Daytona, Singularity, Local

### Delegation
- delegate_tool.py — subagent spawning con restricted toolsets
- MAX_DEPTH = 2 (parent → child → grandchild rejected)

### Memory
- memory_tool.py — MEMORY.md + USER.md management

### Home Assistant
- homeassistant_tool.py — ha_list_entities, ha_get_state, ha_call_service

### Cron
- cronjob_tools.py — cronjob management

### Messaging
- send_message_tool.py — cross-platform messaging (Telegram, Discord, etc.)
- discord_tool.py — Discord-specific

### Transcription + TTS
- transcription_tools.py — speech-to-text
- tts_tool.py — text-to-speech (Edge TTS, Nous TTS, Gemini TTS, Mistral TTS)

### MCP
- mcp_tool.py — MCP client (~1050 líneas)
- mcp_oauth.py, mcp_oauth_manager.py — OAuth flows
- Dynamic discovery + structured content

### Other
- approval.py — dangerous command detection
- clarify_tool.py — user clarification questions
- todo_tool.py — task tracking
- session_search_tool.py — FTS5 search en state.db
- transcription_tools.py — audio transcription
- env_passthrough.py — env var injection

## Tool Execution Flow

1. model_tools.get_tool_definitions() → lista de schemas (OpenAI format)
2. LLM returns tool_call
3. handle_function_call(name, args, task_id) → registry.dispatch()
4. _run_async() bridge → persistent event loop
5. Result → string

## Environment Checks

check_fn en cada tool:
- send_message — check: gateway running
- ha_list_entities — check: HASS_TOKEN env var
- browser_navigate — check: browser available

## Toolset Distribution

toolset_distributions.py:
- Define qué tools van en cada toolset
- toolsets.py: TOOLSETS dict (web, search, vision, terminal, moa, etc.)

> 📅 Documentado: 2026-05-08
