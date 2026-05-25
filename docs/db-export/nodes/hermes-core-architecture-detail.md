# Hermes Core — Arquitectura General

## Metadata

- ID: `72`
- Slug: `hermes-core-architecture-detail`
- Kind: `doc`
- Status: `active`
- Filename: `hermes-core-architecture-detail.md`
- Parent: `hermes-core-components`
- Source kind: `manual`
- Created at: `2026-05-08T08:23:10.937988+00:00`
- Updated at: `2026-05-19T11:33:14.566183+00:00`
- Aliases: `hermes-core-architecture-detail`

## Summary

Arquitectura modular de Hermes: stack tecnológico, componentes principales, flujo de datos y plataformas soportadas

## Body

# Hermes Core — Arquitectura General

Hermes es un agente de IA políglota, multi-plataforma y extensible construido sobre una arquitectura modular de componentes separados.

## Stack Tecnológico

- **Lenguaje**: Python 3 (hermes-agent/)
- **IA**: OpenAI-compatible API (Anthropic, OpenRouter, Ollama, Azure, Gemini, etc.)
- **Almacenamiento**: SQLite (state.db — sesiones, FTS5 search), JSON (config.yaml)
- **Comunicación**: Gateway polling para 13+ plataformas (Telegram, Discord, Slack, WhatsApp, SMS, Email, Matrix, etc.)
- **UI**: CLI interactiva (prompt_toolkit + Rich), TUI (Ink/React), Web (FastAPI + React)

## Componentes Principales

### 1. run_agent.py — AIAgent (Núcleo del Agente)
La clase AIAgent es el loop principal de conversación. Maneja:
- Iteración de llamadas a herramientas hasta completitud (max_iterations default 90)
- IterationBudget — contador thread-safe de iteraciones (execute_code hace refund)
- Conversión de mensajes a formato OpenAI (system/user/assistant/tool)
- Parallelización de herramientas — hasta 8 workers para herramientas read-only independientes
- Sanitización de surrogates UTF-16 (byte-level reasoning models como xiaomi/mimo, kimi, glm)
- Control de mensajes destructive con patrones rm/mv/sed -i/dd/shred
- Compression hook: cuando se acerca al límite de contexto, invoca ContextCompressor

### 2. hermes_state.py — SessionDB (Persistencia)
SQLite con WAL mode para sesiones concurrentes (gateway multi-plataforma):
- Tabla sessions: metadata, model config, system prompt, parent_session_id
- Tabla messages: role, content, tool_calls, token_count, reasoning, reasoning_details
- FTS5 virtual table para búsqueda full-text cross-session
- Triggers para mantener sincronizado FTS con mensajes
- Write contention: 15 retries con jitter 20-150ms en vez de SQLite busy handler

### 3. model_tools.py — Tool Orchestration
Capa delgada sobre el tool registry. API pública:
- get_tool_definitions(enabled_toolsets, disabled_toolsets, quiet) → lista de schemas
- handle_function_call(name, args, task_id) → resultado como string
- TOOL_TO_TOOLSET_MAP, TOOLSET_REQUIREMENTS
- _run_async(coro) — single source of truth para sync→async bridging
- Persistent event loop por worker thread (thread-local) para evitar "Event loop is closed"
- Main thread loop persistente para CLI (evita cerrar clientes httpx cached)

### 4. tools/registry.py — ToolRegistry (Singleton)
Registro central de todas las herramientas:
- discover_builtin_tools() — AST parsing para detectar registry.register() calls
- ToolEntry con: name, toolset, schema, handler, check_fn, requires_env, is_async, emoji
- Thread-safe: RLocks para mutaciones, snapshots para lectores
- MCP dynamic refresh-safe (puede mutar mientras otros threads leen)

### 5. toolsets.py — Toolset Definitions
TOOLSETS dict con tools e includes (composición):
- _HERMES_CORE_TOOLS: 28 herramientas del core (web, terminal, file, vision, skills, browser, TTS, todo, memory, session_search, clarify, execute_code, delegate, cronjob, send_message, HomeAssistant)
- Herramientas agrupadas en toolsets: web, search, vision, image_gen, terminal, moa (Mixture of Agents), delegation, safe, debugging, hermes-*

### 6. gateway/run.py — GatewayRunner
Gestiona el lifecycle del gateway de mensajería:
- LRU agent cache con 128 slots y 1h idle TTL
- Platform adapters (telegram.py, discord.py, slack.py, etc.)
- Slash command dispatch desde MESSAGE_GATEWAY_COMMANDS
- Session routing por user_id/platform
- SSL cert auto-detection (NixOS, macOS, Debian, RHEL, Alpine)

### 7. hermes_cli/ — CLI Completa
- commands.py: COMMAND_REGISTRY (40+ CommandDef) — fuente única para CLI, gateway, Telegram BotCommands, Slack
- config.py: DEFAULT_CONFIG, load_cli_config() mergeando defaults + YAML
- skin_engine.py: data-driven theming de CLI
- setup.py: interactive setup wizard
- model_switch.py: pipeline compartido /model switch
- skills_config.py, tools_config.py: enable/disable por platform
- auth.py: resolución de credenciales de providers

## Flujo de Datos

User Message
    ↓
HermesCLI.process_command() / Gateway dispatch
    ↓
AIAgent.run_conversation()
    ├─ build_system_prompt() — identity, platform hints, skills, context files, memory
    ├─ memory_manager.prefetch_all() — built-in + plugin memory
    ├─ API call (chat.completions.create) con tools
    ├─ while tool_calls:
    │    ├─ parallel-safe? → ThreadPoolExecutor (≤8 workers)
    │    ├─ handle_function_call() → tool registry dispatch
    │    └─ compress if near context limit
    └─ return final_response

## Configuración

~/.laia/config.yaml — settings centralizados
~/.laia/.env — API keys (cargadas por env_loader.py antes de todo)
~/.laia/state.db — sesiones SQLite con FTS5
~/.laia/memories/ — MEMORY.md y USER.md (frozen snapshot en system prompt)

## Plataformas Soportadas

Telegram, Discord, Slack, WhatsApp, SMS (via Twilio), Email (IMAP/SMTP), 
Matrix, Signal, Mattermost, DingTalk, Feishu, WeChat Work (Wecom), 
Home Assistant, QQBot, BlueBubbles, API Server, Webhook

> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `hermes-core-components` (Hermes Core Components) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Hermes Core — Arquitectura General

# Hermes Core — Arquitectura General

Hermes es un agente de IA políglota, multi-plataforma y extensible construido sobre una arquitectura modular de componentes separados.

## Stack Tecnológico

- **Lenguaje**: Python 3 (hermes-agent/)
- **IA**: OpenAI-compatible API (Anthropic, OpenRouter, Ollama, Azure, Gemini, etc.)
- **Almacenamiento**: SQLite (state.db — sesiones, FTS5 search), JSON (config.yaml)
- **Comunicación**: Gateway polling para 13+ plataformas (Telegram, Discord, Slack, WhatsApp, SMS, Email, Matrix, etc.)
- **UI**: CLI interactiva (prompt_toolkit + Rich), TUI (Ink/React), Web (FastAPI + React)

## Componentes Principales

### 1. run_agent.py — AIAgent (Núcleo del Agente)
La clase AIAgent es el loop principal de conversación. Maneja:
- Iteración de llamadas a herramientas hasta completitud (max_iterations default 90)
- IterationBudget — contador thread-safe de iteraciones (execute_code hace refund)
- Conversión de mensajes a formato OpenAI (system/user/assistant/tool)
- Parallelización de herramientas — hasta 8 workers para herramientas read-only independientes
- Sanitización de surrogates UTF-16 (byte-level reasoning models como xiaomi/mimo, kimi, glm)
- Control de mensajes destructive con patrones rm/mv/sed -i/dd/shred
- Compression hook: cuando se acerca al límite de contexto, invoca ContextCompressor

### 2. hermes_state.py — SessionDB (Persistencia)
SQLite con WAL mode para sesiones concurrentes (gateway multi-plataforma):
- Tabla sessions: metadata, model config, system prompt, parent_session_id
- Tabla messages: role, content, tool_calls, token_count, reasoning, reasoning_details
- FTS5 virtual table para búsqueda full-text cross-session
- Triggers para mantener sincronizado FTS con mensajes
- Write contention: 15 retries con jitter 20-150ms en vez de SQLite busy handler

### 3. model_tools.py — Tool Orchestration
Capa delgada sobre el tool registry. API pública:
- get_tool_definitions(enabled_toolsets, disabled_toolsets, quiet) → lista de schemas
- handle_function_call(name, args, task_id) → resultado como string
- TOOL_TO_TOOLSET_MAP, TOOLSET_REQUIREMENTS
- _run_async(coro) — single source of truth para sync→async bridging
- Persistent event loop por worker thread (thread-local) para evitar "Event loop is closed"
- Main thread loop persistente para CLI (evita cerrar clientes httpx cached)

### 4. tools/registry.py — ToolRegistry (Singleton)
Registro central de todas las herramientas:
- discover_builtin_tools() — AST parsing para detectar registry.register() calls
- ToolEntry con: name, toolset, schema, handler, check_fn, requires_env, is_async, emoji
- Thread-safe: RLocks para mutaciones, snapshots para lectores
- MCP dynamic refresh-safe (puede mutar mientras otros threads leen)

### 5. toolsets.py — Toolset Definitions
TOOLSETS dict con tools e includes (composición):
- _HERMES_CORE_TOOLS: 28 herramientas del core (web, terminal, file, vision, skills, browser, TTS, todo, memory, session_search, clarify, execute_code, delegate, cronjob, send_message, HomeAssistant)
- Herramientas agrupadas en toolsets: web, search, vision, image_gen, terminal, moa (Mixture of Agents), delegation, safe, debugging, hermes-*

### 6. gateway/run.py — GatewayRunner
Gestiona el lifecycle del gateway de mensajería:
- LRU agent cache con 128 slots y 1h idle TTL
- Platform adapters (telegram.py, discord.py, slack.py, etc.)
- Slash command dispatch desde MESSAGE_GATEWAY_COMMANDS
- Session routing por user_id/platform
- SSL cert auto-detection (NixOS, macOS, Debian, RHEL, Alpine)

### 7. hermes_cli/ — CLI Completa
- commands.py: COMMAND_REGISTRY (40+ CommandDef) — fuente única para CLI, gateway, Telegram BotCommands, Slack
- config.py: DEFAULT_CONFIG, load_cli_config() mergeando defaults + YAML
- skin_engine.py: data-driven theming de CLI
- setup.py: interactive setup wizard
- model_switch.py: pipeline compartido /model switch
- skills_config.py, tools_config.py: enable/disable por platform
- auth.py: resolución de credenciales de providers

## Flujo de Datos

User Message
    ↓
HermesCLI.process_command() / Gateway dispatch
    ↓
AIAgent.run_conversation()
    ├─ build_system_prompt() — identity, platform hints, skills, context files, memory
    ├─ memory_manager.prefetch_all() — built-in + plugin memory
    ├─ API call (chat.completions.create) con tools
    ├─ while tool_calls:
    │    ├─ parallel-safe? → ThreadPoolExecutor (≤8 workers)
    │    ├─ handle_function_call() → tool registry dispatch
    │    └─ compress if near context limit
    └─ return final_response

## Configuración

~/.laia/config.yaml — settings centralizados
~/.laia/.env — API keys (cargadas por env_loader.py antes de todo)
~/.laia/state.db — sesiones SQLite con FTS5
~/.laia/memories/ — MEMORY.md y USER.md (frozen snapshot en system prompt)

## Plataformas Soportadas

Telegram, Discord, Slack, WhatsApp, SMS (via Twilio), Email (IMAP/SMTP), 
Matrix, Signal, Mattermost, DingTalk, Feishu, WeChat Work (Wecom), 
Home Assistant, QQBot, BlueBubbles, API Server, Webhook

> 📅 Documentado: 2026-05-08
