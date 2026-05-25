# LAIA — Ecosistema v2.6

## Metadata

- ID: `42`
- Slug: `index`
- Kind: `index`
- Status: `active`
- Filename: `00-index.md`
- Parent: `—`
- Source kind: `manual`
- Created at: `2026-05-08T08:00:57.536374+00:00`
- Updated at: `2026-05-19T12:39:09.654827+00:00`
- Aliases: `index`

## Summary

v2.6: hardening reglas ②⑥⑨⑩⑪. Split toolset laia_coordinator, logout revoke, slug reservado. 91 tests verdes.

## Body

# LAIA — Ecosistema v2.1

## Arquitectura

HOST (ARCH intacto)
├── ARCH (.laia-core/ en host) — asistente personal del admin
├── laia-agora (LXD) — CEREBRO: .laia-core/ + AGORA Backend + AgentPool + Forwarder
└── laia-{slug} (LXD) — EXECUTOR: FastAPI :9091, 22 endpoints de ejecucion, root libre, bind mounts

## Tags git

sprint2-snapshot=36f7263 | redesign-v1-functional=64ba0c2 | redesign-v2.0-deployed=2878dad | control-center-v0.2-polished=e2b8ea5

Comparacion sprint 2 vs v2.1: ver nodo agora-rediseno.

## Acceso

- **Workspace UI**: http://100.73.36.92:8077 (documentacion y contexto)
- **AGORA API**: http://localhost:8088 (proxy LXD -> laia-agora:8000)
- **AGORA Frontend**: http://localhost:8090 (servido desde dist/)
- **Admin login**: jorge / dev-admin

## v2.2 — Marketplace v0.1 (Mayo 2026)

- Sistema de publicacion/aprobacion/instalacion de plugins, skills y MCP
- 26 tests nuevos (224 total backend)
- CLI host-side: infra/dev/laia-marketplace.py
- TUI pestana 9: Marketplace
- Doc: ver nodo `agora-marketplace`

### Marketplace v0.1 — Bugs arreglados

- B1: hardcoded path en tests (host vs container). B2: toolsets dinamicos para plugins. B3: convencion de handlers (args: dict -> str).
- 3 ejemplos plantados (marketplace-hello, agora-now, marketplace-onboarding). Ver `agora-marketplace`.

## v2.3 — Agent Areas + Naming agent-* (Mayo 2026)

- Tabla agent_areas: soul, instrucciones, preferencias centralizadas en AGORA DB
- APIs /api/me/agent-area + /api/admin/users/{id}/agent-area
- AgentPool inyecta soul como ephemeral_system_prompt
- Nuevos containers: agent-<slug>
- 231 tests backend + 5 shell verdes

> 📅 Actualizado: 2026-05-18

## v2.4 — Hardening Agent Areas + Naming (Mayo 2026)

- F1: max_length en soul/instructions (seguridad P0)
- F2: naming consistente (admin, rebuild, preflight, cleanup)
- F3: test combinado marketplace + agent-area
- F4: CLI agent-area + TUI pestana 10 "Areas"
- 237 tests backend + 5 shell verdes

> 📅 Actualizado: 2026-05-18

## v2.5 — 10 sistemas nuevos documentados (2026-05-18)

- `agora-laia-coordinator` — LAIA como agente padre en AGORA
- `agora-agent-delegation` — agentes hijos efimeros (spawn_child)
- `agora-agent-learnings` — aprendizaje persistente con decay
- `agora-scheduled-jobs` — tareas programadas (cron)
- `agora-webhooks` — triggers externos HMAC
- `agora-usage-budget` — tracking de costes + limites
- `agora-auto-import` — import desde GitHub/Notion/Linear
- `agora-laia-init` — wizard de instalacion (8 pasos)
- `agora-ctl-tui` — TUI modular v2 (Textual, 14 pestañas)
- `agora-base-skills` — 15 skills pre-empaquetadas

351 backend tests + 53 executor tests + 25 forwarder tests (420+ total).

## v2.6 — Hardening v0.5 (2026-05-19)

- LAIA Coordinator: toolset role-aware (base 2 tools empleados, +admin 6 tools)
- Slug "laia" reservado. Logout con revoke de tokens.
- Regla ⑥ audit trail activo. 91 tests verdes en 4 suites.
- Ver nodo `agora-v05-hardening` para detalle completo.

## Relaciones salientes

- `contains` → `agent-log` (Agent Log — Activity) [peso=1.00]
- `contains` → `agentes-personales` (Agentes personales — Hijos de LAIA (v2.1)) [peso=1.00]
- `contains` → `agora` (AGORA — Plataforma de usuarios) [peso=1.00]
- `contains` → `arch` (ARCH — Contexto admin de LAIA) [peso=1.00]
- `contains` → `hermes` (Hermes — Núcleo técnico) [peso=1.00]
- `contains` → `laia-ecosystem-doc` (LAIA Ecosystem — Documento Definitivo v1.0) [peso=1.00]
- `project_of` → `agora` (AGORA — Plataforma de usuarios) [peso=1.00]
- `project_of` → `arch` (ARCH — Contexto admin de LAIA) [peso=1.00]
- `project_of` → `hermes` (Hermes — Núcleo técnico) [peso=1.00]

## Relaciones entrantes

- _(sin relaciones entrantes)_

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# LAIA — Ecosistema v2.6

# LAIA — Ecosistema v2.1

## Arquitectura

HOST (ARCH intacto)
├── ARCH (.laia-core/ en host) — asistente personal del admin
├── laia-agora (LXD) — CEREBRO: .laia-core/ + AGORA Backend + AgentPool + Forwarder
└── laia-{slug} (LXD) — EXECUTOR: FastAPI :9091, 22 endpoints de ejecucion, root libre, bind mounts

## Tags git

sprint2-snapshot=36f7263 | redesign-v1-functional=64ba0c2 | redesign-v2.0-deployed=2878dad | control-center-v0.2-polished=e2b8ea5

Comparacion sprint 2 vs v2.1: ver nodo agora-rediseno.

## Acceso

- **Workspace UI**: http://100.73.36.92:8077 (documentacion y contexto)
- **AGORA API**: http://localhost:8088 (proxy LXD -> laia-agora:8000)
- **AGORA Frontend**: http://localhost:8090 (servido desde dist/)
- **Admin login**: jorge / dev-admin

## v2.2 — Marketplace v0.1 (Mayo 2026)

- Sistema de publicacion/aprobacion/instalacion de plugins, skills y MCP
- 26 tests nuevos (224 total backend)
- CLI host-side: infra/dev/laia-marketplace.py
- TUI pestana 9: Marketplace
- Doc: ver nodo `agora-marketplace`

### Marketplace v0.1 — Bugs arreglados

- B1: hardcoded path en tests (host vs container). B2: toolsets dinamicos para plugins. B3: convencion de handlers (args: dict -> str).
- 3 ejemplos plantados (marketplace-hello, agora-now, marketplace-onboarding). Ver `agora-marketplace`.

## v2.3 — Agent Areas + Naming agent-* (Mayo 2026)

- Tabla agent_areas: soul, instrucciones, preferencias centralizadas en AGORA DB
- APIs /api/me/agent-area + /api/admin/users/{id}/agent-area
- AgentPool inyecta soul como ephemeral_system_prompt
- Nuevos containers: agent-<slug>
- 231 tests backend + 5 shell verdes

> 📅 Actualizado: 2026-05-18

## v2.4 — Hardening Agent Areas + Naming (Mayo 2026)

- F1: max_length en soul/instructions (seguridad P0)
- F2: naming consistente (admin, rebuild, preflight, cleanup)
- F3: test combinado marketplace + agent-area
- F4: CLI agent-area + TUI pestana 10 "Areas"
- 237 tests backend + 5 shell verdes

> 📅 Actualizado: 2026-05-18

## v2.5 — 10 sistemas nuevos documentados (2026-05-18)

- `agora-laia-coordinator` — LAIA como agente padre en AGORA
- `agora-agent-delegation` — agentes hijos efimeros (spawn_child)
- `agora-agent-learnings` — aprendizaje persistente con decay
- `agora-scheduled-jobs` — tareas programadas (cron)
- `agora-webhooks` — triggers externos HMAC
- `agora-usage-budget` — tracking de costes + limites
- `agora-auto-import` — import desde GitHub/Notion/Linear
- `agora-laia-init` — wizard de instalacion (8 pasos)
- `agora-ctl-tui` — TUI modular v2 (Textual, 14 pestañas)
- `agora-base-skills` — 15 skills pre-empaquetadas

351 backend tests + 53 executor tests + 25 forwarder tests (420+ total).

## v2.6 — Hardening v0.5 (2026-05-19)

- LAIA Coordinator: toolset role-aware (base 2 tools empleados, +admin 6 tools)
- Slug "laia" reservado. Logout con revoke de tokens.
- Regla ⑥ audit trail activo. 91 tests verdes en 4 suites.
- Ver nodo `agora-v05-hardening` para detalle completo.

→ Agent Log — Activity: `agent-log.md`
→ Agentes personales — Hijos de LAIA (v2.1): `agentes-personales.md`
→ AGORA — Plataforma de usuarios: `agora.md`
→ ARCH — Contexto admin de LAIA: `arch.md`
→ Hermes — Núcleo técnico: `hermes.md`
→ LAIA Ecosystem — Documento Definitivo v1.0: `laia-ecosystem-doc.md`
→ AGORA — Plataforma de usuarios: `agora.md`
→ ARCH — Contexto admin de LAIA: `arch.md`
→ Hermes — Núcleo técnico: `hermes.md`
