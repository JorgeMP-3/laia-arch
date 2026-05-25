# AGORA Backend — Implementacion v2.1

## Metadata

- ID: `200`
- Slug: `backend-agora`
- Kind: `doc`
- Status: `active`
- Filename: `backend-agora.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-12 16:27:25`
- Updated at: `2026-05-19T12:39:09.631646+00:00`
- Aliases: `backend-agora`

## Summary

Backend AGORA en laia-agora: FastAPI :8000. AgentPool, ChatEngine, Control Center, Marketplace, LAIA Coordinator, Delegation, Learnings, Scheduler, Webhooks, Usage, Budget, Auto-Import. 342 tests.

## Body

# AGORA Backend v2.1

## Ubicacion: container laia-agora, proxy LXD host:8088->container:8000

## Componentes principales
app/main.py (964 LOC): 119 endpoints (70 main.py + 49 routers), JWT auth
app/agent_pool.py (~250 LOC): Pool AIAgent, TTL 60min, + _materialize_marketplace_for()
app/admin.py (~500 LOC): Control Center /api/admin/*
app/marketplace.py: Router FastAPI (/api/plugins/catalog, /api/me/plugins/*, /api/me/skills/*, /api/admin/marketplace/*)
app/marketplace_storage.py: CRUD + validacion tarballs + materializacion per-user
app/agent_client.py (194 LOC): HTTPX client para executors
app/storage.py (278 LOC): AgoraStore SQLite + save_user/update_user_llm_config con mcp_servers_json
app/orchestrator.py (316 LOC): LXD orchestration

## DB (agora.db)
users: llm_provider, llm_api_key, llm_model, mcp_servers_json
agents: container_ip, api_token, status
tasks, events, conversations, telegram_links, admin_jobs
plugins: id, slug, version, kind, manifest_json, tarball_b64, author_id, status, created_at
skills: id, slug, version, kind, manifest_json, tarball_b64, author_id, status, created_at
user_plugins: user_id, plugin_id, installed_at
user_skills: user_id, skill_id, installed_at

## Workspace colectivo: workspace.db compartido, tools workspace_* locales (no forwardean)

## Agent Areas (Mayo 2026)

Nuevo modulo: `app/agent_identity.py` — gestion de `agent_areas`.
Nueva tabla: `agent_areas(user_id, agent_display_name, soul_md, instructions_md, memory_preferences_json, behavior_preferences_json)`.
231 tests (de 224). /api/agent/profile ahora lee de DB, no del executor.

> 📅 Actualizado: 2026-05-18

## Sistemas adicionales (Mayo 2026)

| Sistema | Archivos | DB Tables |
|---------|----------|-----------|
| LAIA Coordinator | laia_chat.py, laia_identity.py | coordinator_messages |
| Agent Delegation | child_profiles.py | agent_child_runs |
| Agent Learnings | scheduler.py | agent_learnings |
| Scheduled Jobs | scheduler.py | agent_scheduled_jobs |
| Webhooks | webhooks.py | webhook_subscriptions |
| Usage Ledger | agent_pool.py, pricing.py | usage_ledger |
| Budget | models.py | users(+3 budget cols) |
| Auto-Import | auto_import/ | auto_imports |
| LAIA Init Wizard | laia-init.sh | — |
| TUI v2 (ctl/) | ctl/app.py, ctl/client.py | — |
| Base Skills | seed-base-skills.sh | skill_registry |
| Users LLM config | models.py, storage.py | users(+5 LLM cols, +mcp_servers_json) |
| Agents network | models.py | agents(+container_ip, +api_token) |

351 tests backend (119 endpoints, 20 tablas) + 53 executor tests + shell tests verdes.

> &#x1F4C5; Actualizado: 2026-05-18

## v0.5 Hardening (2026-05-19)

- P0: split laia_coordinator en base/admin toolsets. Empleados ya pueden chatear con LAIA.
- P1: logout con revoke de tokens (tokens_valid_since). POST /api/logout.
- P1: regla ⑥ audit warning en LXD ops (host_admin role definido, migracion pendiente).
- 91 tests verdes en 4 suites.

> &#x1F4C5; 2026-05-19

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# AGORA Backend — Implementacion v2.1

# AGORA Backend v2.1

## Ubicacion: container laia-agora, proxy LXD host:8088->container:8000

## Componentes principales
app/main.py (964 LOC): 119 endpoints (70 main.py + 49 routers), JWT auth
app/agent_pool.py (~250 LOC): Pool AIAgent, TTL 60min, + _materialize_marketplace_for()
app/admin.py (~500 LOC): Control Center /api/admin/*
app/marketplace.py: Router FastAPI (/api/plugins/catalog, /api/me/plugins/*, /api/me/skills/*, /api/admin/marketplace/*)
app/marketplace_storage.py: CRUD + validacion tarballs + materializacion per-user
app/agent_client.py (194 LOC): HTTPX client para executors
app/storage.py (278 LOC): AgoraStore SQLite + save_user/update_user_llm_config con mcp_servers_json
app/orchestrator.py (316 LOC): LXD orchestration

## DB (agora.db)
users: llm_provider, llm_api_key, llm_model, mcp_servers_json
agents: container_ip, api_token, status
tasks, events, conversations, telegram_links, admin_jobs
plugins: id, slug, version, kind, manifest_json, tarball_b64, author_id, status, created_at
skills: id, slug, version, kind, manifest_json, tarball_b64, author_id, status, created_at
user_plugins: user_id, plugin_id, installed_at
user_skills: user_id, skill_id, installed_at

## Workspace colectivo: workspace.db compartido, tools workspace_* locales (no forwardean)

## Agent Areas (Mayo 2026)

Nuevo modulo: `app/agent_identity.py` — gestion de `agent_areas`.
Nueva tabla: `agent_areas(user_id, agent_display_name, soul_md, instructions_md, memory_preferences_json, behavior_preferences_json)`.
231 tests (de 224). /api/agent/profile ahora lee de DB, no del executor.

> 📅 Actualizado: 2026-05-18

## Sistemas adicionales (Mayo 2026)

| Sistema | Archivos | DB Tables |
|---------|----------|-----------|
| LAIA Coordinator | laia_chat.py, laia_identity.py | coordinator_messages |
| Agent Delegation | child_profiles.py | agent_child_runs |
| Agent Learnings | scheduler.py | agent_learnings |
| Scheduled Jobs | scheduler.py | agent_scheduled_jobs |
| Webhooks | webhooks.py | webhook_subscriptions |
| Usage Ledger | agent_pool.py, pricing.py | usage_ledger |
| Budget | models.py | users(+3 budget cols) |
| Auto-Import | auto_import/ | auto_imports |
| LAIA Init Wizard | laia-init.sh | — |
| TUI v2 (ctl/) | ctl/app.py, ctl/client.py | — |
| Base Skills | seed-base-skills.sh | skill_registry |
| Users LLM config | models.py, storage.py | users(+5 LLM cols, +mcp_servers_json) |
| Agents network | models.py | agents(+container_ip, +api_token) |

351 tests backend (119 endpoints, 20 tablas) + 53 executor tests + shell tests verdes.

> &#x1F4C5; Actualizado: 2026-05-18

## v0.5 Hardening (2026-05-19)

- P0: split laia_coordinator en base/admin toolsets. Empleados ya pueden chatear con LAIA.
- P1: logout con revoke de tokens (tokens_valid_since). POST /api/logout.
- P1: regla ⑥ audit warning en LXD ops (host_admin role definido, migracion pendiente).
- 91 tests verdes en 4 suites.

> &#x1F4C5; 2026-05-19
