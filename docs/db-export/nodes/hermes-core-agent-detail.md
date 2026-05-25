# Hermes Core — Agent

## Metadata

- ID: `71`
- Slug: `hermes-core-agent-detail`
- Kind: `doc`
- Status: `active`
- Filename: `hermes-core-agent-detail.md`
- Parent: `hermes-core-components`
- Source kind: `manual`
- Created at: `2026-05-08T08:22:37.210293+00:00`
- Updated at: `2026-05-19T11:33:14.566183+00:00`
- Aliases: `hermes-core-agent-detail`

## Summary

Núcleo de ejecución de Hermes: clase AIAgent, agent loop, sub-componentes, parallelización de herramientas y manejo de errores

## Body

# Hermes Core — Agent

El componente Agent es el núcleo de ejecución de Hermes. Centralizado en la clase AIAgent en run_agent.py (~12,400 líneas).

## AIAgent Class

### Init Parameters
```python
class AIAgent:
    def __init__(self,
        model: str = "anthropic/claude-opus-4.6",
        max_iterations: int = 90,
        enabled_toolsets: list = None,
        disabled_toolsets: list = None,
        quiet_mode: bool = False,
        save_trajectories: bool = False,
        platform: str = None,          # "cli", "telegram", etc.
        session_id: str = None,
        skip_context_files: bool = False,
        skip_memory: bool = False,
        # ... provider, api_mode, callbacks, routing params
    )
```

### API Pública
- `chat(message: str) -> str` — interfaz simple, retorna string final
- `run_conversation(user_message, system_message, conversation_history, task_id) -> dict` — interfaz completa con dict de response + messages

### Agent Loop
```python
while api_call_count < max_iterations and iteration_budget.remaining > 0:
    response = client.chat.completions.create(model=model, messages=messages, tools=tool_schemas)
    if response.tool_calls:
        for tool_call in response.tool_calls:
            result = handle_function_call(tool_call.name, tool_call.args, task_id)
            messages.append(tool_result_message(result))
        api_call_count += 1
    else:
        return response.content
```

## Sub-Componentes del Agent

### agent/prompt_builder.py
Armate stateless del system prompt:
- `build_skills_system_prompt()` — skills index + condiciones de platform
- `build_context_files_prompt()` — AGENTS.md, .cursorrules, SOUL.md
- `build_environment_hints()` — cwd, platform, model metadata
- `load_soul_md()` — identity principal
- `_CONTEXT_THREAT_PATTERNS` — detecta prompt injection en context files
- Escaneo de caracteres invisibles unicode (U+200B, etc.)

### agent/memory_manager.py
Orchestrates built-in + ONE external plugin memory provider:
- `add_provider()` — BuiltinMemoryProvider siempre primero, solo UN provider externo
- `build_system_prompt()` — inyecta memory block en system prompt
- `prefetch_all(user_message)` — recall antes del turno
- `sync_all(user_msg, assistant_response)` — persist después del turno
- `sanitize_context()` — strip fence tags y system notes del output

### agent/context_compressor.py
Auto context compression para conversaciones largas:
- Usa auxiliary model (cheap/fast) para resumir
- Protege head + tail del contexto
- SUMMARY_PREFIX: "[CONTEXT COMPACTION — REFERENCE ONLY]"
- Resolved/Pending question tracking
- Tool output pruning pre-pass antes de LLM summarization
- Summary budget proporcional al contenido comprimido (20% ratio)
- Iterative summary updates

### agent/auxiliary_client.py
Cliente LLM secundario para:
- Vision routing (OpenRouter, Nous, Codex, Anthropic, custom OpenAI-compatible)
- Summarization para compression
- Credential pool management
- Retry logic con exponential backoff

### agent/model_metadata.py
Metadata por modelo:
- Context lengths, token estimation
- `fetch_model_metadata()`, `estimate_tokens_rough()`
- `get_next_probe_tier()` — fallback entre modelos
- `parse_context_limit_from_error()` — detecta 400 context length errors
- models.dev registry integration

### agent/display.py
- KawaiiSpinner — animated faces durante API calls
- `build_tool_preview()` — formateo de preview de herramientas
- `get_cute_tool_message()` — emoji + mensaje kawaii por tool
- `_detect_tool_failure()`

### agent/skill_commands.py
Skill slash commands compartidos CLI/gateway:
- Escanea ~/.laia/skills/
- Inyecta como user message (NO system prompt) para preservar prompt caching

### agent/trajectory.py
Trajectory saving helpers:
- `convert_scratchpad_to_think()` — limpia scratchpad de razonamiento
- `has_incomplete_scratchpad()`
- `save_trajectory()` — persiste a archivo

## IterationBudget

Thread-safe counter por agent (parent o subagent):
- Parent: capped at max_iterations (default 90)
- Subagents: capped at delegation.max_iterations (default 50)
- execute_code iterations son refundadas via `refund()`
- Total iterations parent + subagents puede exceder cap del parent

## Parallelización de Herramientas

- `_MAX_TOOL_WORKERS = 8`
- `_NEVER_PARALLEL_TOOLS = {"clarify"}` — siempre sequential
- `_PARALLEL_SAFE_TOOLS` — read-only tools (ha_get_state, read_file, search_files, vision_analyze, web_extract, etc.)
- `_PATH_SCOPED_TOOLS = {"read_file", "write_file", "patch"}` — path overlap detection
- `_should_parallelize_tool_batch()` — decisión de paralelización por batch
- `_paths_overlap()` — detecta si dos paths comparten prefijo

## Destructive Command Detection

Patrones que activan sequential-only y warning:
- rm, rmdir, mv, sed -i, truncate, dd, shred, git reset/clean/checkout
- Output redirects que sobreescriben (>| pero no >>)

## Errores y Retry

- `agent/error_classifier.py` — classify_api_error(), FailoverReason
- `agent/retry_utils.py` — jittered_backoff
- Surrogate UTF-16 sanitization para byte-level reasoning models (xiaomi/mimo, kimi, glm)
- `_sanitize_messages_surrogates()` — recorre content, name, tool_calls, reasoning fields

> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `hermes-core-components` (Hermes Core Components) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Hermes Core — Agent

# Hermes Core — Agent

El componente Agent es el núcleo de ejecución de Hermes. Centralizado en la clase AIAgent en run_agent.py (~12,400 líneas).

## AIAgent Class

### Init Parameters
```python
class AIAgent:
    def __init__(self,
        model: str = "anthropic/claude-opus-4.6",
        max_iterations: int = 90,
        enabled_toolsets: list = None,
        disabled_toolsets: list = None,
        quiet_mode: bool = False,
        save_trajectories: bool = False,
        platform: str = None,          # "cli", "telegram", etc.
        session_id: str = None,
        skip_context_files: bool = False,
        skip_memory: bool = False,
        # ... provider, api_mode, callbacks, routing params
    )
```

### API Pública
- `chat(message: str) -> str` — interfaz simple, retorna string final
- `run_conversation(user_message, system_message, conversation_history, task_id) -> dict` — interfaz completa con dict de response + messages

### Agent Loop
```python
while api_call_count < max_iterations and iteration_budget.remaining > 0:
    response = client.chat.completions.create(model=model, messages=messages, tools=tool_schemas)
    if response.tool_calls:
        for tool_call in response.tool_calls:
            result = handle_function_call(tool_call.name, tool_call.args, task_id)
            messages.append(tool_result_message(result))
        api_call_count += 1
    else:
        return response.content
```

## Sub-Componentes del Agent

### agent/prompt_builder.py
Armate stateless del system prompt:
- `build_skills_system_prompt()` — skills index + condiciones de platform
- `build_context_files_prompt()` — AGENTS.md, .cursorrules, SOUL.md
- `build_environment_hints()` — cwd, platform, model metadata
- `load_soul_md()` — identity principal
- `_CONTEXT_THREAT_PATTERNS` — detecta prompt injection en context files
- Escaneo de caracteres invisibles unicode (U+200B, etc.)

### agent/memory_manager.py
Orchestrates built-in + ONE external plugin memory provider:
- `add_provider()` — BuiltinMemoryProvider siempre primero, solo UN provider externo
- `build_system_prompt()` — inyecta memory block en system prompt
- `prefetch_all(user_message)` — recall antes del turno
- `sync_all(user_msg, assistant_response)` — persist después del turno
- `sanitize_context()` — strip fence tags y system notes del output

### agent/context_compressor.py
Auto context compression para conversaciones largas:
- Usa auxiliary model (cheap/fast) para resumir
- Protege head + tail del contexto
- SUMMARY_PREFIX: "[CONTEXT COMPACTION — REFERENCE ONLY]"
- Resolved/Pending question tracking
- Tool output pruning pre-pass antes de LLM summarization
- Summary budget proporcional al contenido comprimido (20% ratio)
- Iterative summary updates

### agent/auxiliary_client.py
Cliente LLM secundario para:
- Vision routing (OpenRouter, Nous, Codex, Anthropic, custom OpenAI-compatible)
- Summarization para compression
- Credential pool management
- Retry logic con exponential backoff

### agent/model_metadata.py
Metadata por modelo:
- Context lengths, token estimation
- `fetch_model_metadata()`, `estimate_tokens_rough()`
- `get_next_probe_tier()` — fallback entre modelos
- `parse_context_limit_from_error()` — detecta 400 context length errors
- models.dev registry integration

### agent/display.py
- KawaiiSpinner — animated faces durante API calls
- `build_tool_preview()` — formateo de preview de herramientas
- `get_cute_tool_message()` — emoji + mensaje kawaii por tool
- `_detect_tool_failure()`

### agent/skill_commands.py
Skill slash commands compartidos CLI/gateway:
- Escanea ~/.laia/skills/
- Inyecta como user message (NO system prompt) para preservar prompt caching

### agent/trajectory.py
Trajectory saving helpers:
- `convert_scratchpad_to_think()` — limpia scratchpad de razonamiento
- `has_incomplete_scratchpad()`
- `save_trajectory()` — persiste a archivo

## IterationBudget

Thread-safe counter por agent (parent o subagent):
- Parent: capped at max_iterations (default 90)
- Subagents: capped at delegation.max_iterations (default 50)
- execute_code iterations son refundadas via `refund()`
- Total iterations parent + subagents puede exceder cap del parent

## Parallelización de Herramientas

- `_MAX_TOOL_WORKERS = 8`
- `_NEVER_PARALLEL_TOOLS = {"clarify"}` — siempre sequential
- `_PARALLEL_SAFE_TOOLS` — read-only tools (ha_get_state, read_file, search_files, vision_analyze, web_extract, etc.)
- `_PATH_SCOPED_TOOLS = {"read_file", "write_file", "patch"}` — path overlap detection
- `_should_parallelize_tool_batch()` — decisión de paralelización por batch
- `_paths_overlap()` — detecta si dos paths comparten prefijo

## Destructive Command Detection

Patrones que activan sequential-only y warning:
- rm, rmdir, mv, sed -i, truncate, dd, shred, git reset/clean/checkout
- Output redirects que sobreescriben (>| pero no >>)

## Errores y Retry

- `agent/error_classifier.py` — classify_api_error(), FailoverReason
- `agent/retry_utils.py` — jittered_backoff
- Surrogate UTF-16 sanitization para byte-level reasoning models (xiaomi/mimo, kimi, glm)
- `_sanitize_messages_surrogates()` — recorre content, name, tool_calls, reasoning fields

> 📅 Documentado: 2026-05-08
