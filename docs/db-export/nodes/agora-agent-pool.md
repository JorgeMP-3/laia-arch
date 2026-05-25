# AGORA Agent Pool — Instancias AIAgent

## Metadata

- ID: `204`
- Slug: `agora-agent-pool`
- Kind: `doc`
- Status: `active`
- Filename: `agora-agent-pool.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-18T11:03:34.660778+00:00`
- Updated at: `2026-05-18T16:10:02.444774+00:00`
- Aliases: `agora-agent-pool`

## Summary

Pool en memoria: 1 AIAgent por sesion. TTL 60min, LRU eviction. Per-user LLM config. Bootstrap workspace colectivo. Background janitor cada 60s.

## Body

# AGORA Agent Pool

## Clases
AgentSession: user_id, session_id, agent_slug, aiagent, llm_config, last_active, message_history
AgentPool: get_or_create(), evict_idle(ttl=3600), evict_lru(), background_janitor() cada 60s
_PlaceholderAgent: fallback si .laia-core/ no se puede importar

## Per-user LLM: users.llm_provider (deepseek|anthropic|openai|openrouter), users.llm_api_key (cifrada), users.llm_model (opcional)

## Toolset whitelist (AGORA_ENABLED_TOOLSETS): file, terminal, web, vision, image_gen, browser, fetch_url, workspace, clarify, todo, user_runtime
Excluidas: code_execution, cronjob, skills, delegation, moa

## Parametros: idle_ttl=3600s, max_sessions=30, janitor_interval=60s

## Workspace colectivo: _ensure_collective_workspace_env() idempotente: crea config.yaml, symlink auth.json, inicializa workspace.db

## Marketplace v0.1 (Fases A-I)

_materialize_marketplace_for(user_id): extrae plugins y skills instalados por el usuario a directorios bajo /srv/laia/users/{slug}/. Setea LAIA_EXTRA_PLUGIN_DIRS en el entorno del AIAgent. Invalida sesion -> proxima request reconstruye con plugins cargados.

invalidate_user_static(user_id): marca la config estatica del usuario como stale, forzando re-materializacion en la siguiente sesion.

## Agent Areas (Mayo 2026)

Al crear un AIAgent, el pool ahora lee `agent_areas` del usuario:
- `soul_md` + `instructions_md` + `behavior_preferences_json` → `ephemeral_system_prompt`
- Inyectado como prompt del sistema para el LLM
- Si el usuario edita su area → `invalidate_user_static()` → siguiente sesion reconstruye

Nuevos metodos: `_build_ephemeral_prompt(user_id)` → str.

> 📅 Actualizado: 2026-05-18

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# AGORA Agent Pool — Instancias AIAgent

# AGORA Agent Pool

## Clases
AgentSession: user_id, session_id, agent_slug, aiagent, llm_config, last_active, message_history
AgentPool: get_or_create(), evict_idle(ttl=3600), evict_lru(), background_janitor() cada 60s
_PlaceholderAgent: fallback si .laia-core/ no se puede importar

## Per-user LLM: users.llm_provider (deepseek|anthropic|openai|openrouter), users.llm_api_key (cifrada), users.llm_model (opcional)

## Toolset whitelist (AGORA_ENABLED_TOOLSETS): file, terminal, web, vision, image_gen, browser, fetch_url, workspace, clarify, todo, user_runtime
Excluidas: code_execution, cronjob, skills, delegation, moa

## Parametros: idle_ttl=3600s, max_sessions=30, janitor_interval=60s

## Workspace colectivo: _ensure_collective_workspace_env() idempotente: crea config.yaml, symlink auth.json, inicializa workspace.db

## Marketplace v0.1 (Fases A-I)

_materialize_marketplace_for(user_id): extrae plugins y skills instalados por el usuario a directorios bajo /srv/laia/users/{slug}/. Setea LAIA_EXTRA_PLUGIN_DIRS en el entorno del AIAgent. Invalida sesion -> proxima request reconstruye con plugins cargados.

invalidate_user_static(user_id): marca la config estatica del usuario como stale, forzando re-materializacion en la siguiente sesion.

## Agent Areas (Mayo 2026)

Al crear un AIAgent, el pool ahora lee `agent_areas` del usuario:
- `soul_md` + `instructions_md` + `behavior_preferences_json` → `ephemeral_system_prompt`
- Inyectado como prompt del sistema para el LLM
- Si el usuario edita su area → `invalidate_user_static()` → siguiente sesion reconstruye

Nuevos metodos: `_build_ephemeral_prompt(user_id)` → str.

> 📅 Actualizado: 2026-05-18
