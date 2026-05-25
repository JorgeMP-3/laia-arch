# AGORA — Decisiones, Riesgos y Gotchas

## Metadata

- ID: `208`
- Slug: `agora-grafo`
- Kind: `important`
- Status: `active`
- Filename: `agora-grafo.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-18T11:03:34.714573+00:00`
- Updated at: `2026-05-19T12:39:09.645690+00:00`
- Aliases: `agora-grafo`

## Summary

Decisiones: cerebro centralizado (D1), HTTP forwarder (D2), per-user LLM keys (D4). Riesgos: RAM pool, latencia, provider down. Gotchas: state files, ghost backend, auth.json.

## Body

# AGORA — Decisiones Clave y Riesgos

## Decisiones
D1: Cerebro UNICO en laia-agora. Executors sin .laia-core/. Trade-off: si laia-agora cae, nadie chatea -> Restart=always en systemd.
D2: HTTP one-shot (POST /exec). WebSocket en futuro. RTT bridge LXD ~5-20ms.
D3: LXD en ARM actual. VM con GPU en P720 produccion.
D4: Per-user LLM keys (cifradas con Fernet en DB). Facturacion independiente.

## Riesgos
AgentPool RAM (30 users x 200MB = 6GB) -> TTL 60min + LRU. En ARM 7GB lim ~10 sesiones
Forwarder latencia bash streaming -> timeout 180s, WS futuro
LLM provider down -> error claro, no crashea
AGORA reinicia con sesiones -> conversations table rehidrata lazy
Usuario malicioso -> Bearer token unico, bridge LXD aisla L3

## Gotchas operacionales
1. State files en /tmp desaparecen -> migrado a ~/.laia/state/
2. Ghost backend host:8088 -> preflight.sh lo detecta
3. auth.json copy vs bind mount -> usar bind mount read-only
4. Forwarder rompe LXD versions -> plugin es agnostico, solo HTTP

## Nuevas decisiones (Mayo 2026)

D5: Identidad del agente centralizada en agent_areas (DB). Container solo executor.
D6: Naming agent-<slug> para nuevos containers. Legacy laia-<slug> protegido.
D7: Soul/instrucciones como ephemeral_system_prompt via AgentPool > 📅 2026-05-18

## Hardening (Mayo 2026)

D8: max_length=50KB en soul/instructions previene DoS de memoria.
D9: GET agent-area auto-crea (nunca 404) — consistente con PATCH.
D10: rebuild-4 destruye legacy por defecto (evita coexistencia agent-* + laia-*).

> 📅 2026-05-18

## v0.5 (2026-05-19)

D11: Toolset laia_coordinator dividido en _base (empleados) y _admin (admins). Regla ⑨-⑪ alineadas.
D12: Slug "laia" reservado via RESERVED_AGENT_SLUGS. Regla ② alineada.
D13: Logout revoke sin JTI denylist (tokens_valid_since cutoff). 
D14: host_admin role definido para regla ⑥ (migracion pendiente).

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# AGORA — Decisiones, Riesgos y Gotchas

# AGORA — Decisiones Clave y Riesgos

## Decisiones
D1: Cerebro UNICO en laia-agora. Executors sin .laia-core/. Trade-off: si laia-agora cae, nadie chatea -> Restart=always en systemd.
D2: HTTP one-shot (POST /exec). WebSocket en futuro. RTT bridge LXD ~5-20ms.
D3: LXD en ARM actual. VM con GPU en P720 produccion.
D4: Per-user LLM keys (cifradas con Fernet en DB). Facturacion independiente.

## Riesgos
AgentPool RAM (30 users x 200MB = 6GB) -> TTL 60min + LRU. En ARM 7GB lim ~10 sesiones
Forwarder latencia bash streaming -> timeout 180s, WS futuro
LLM provider down -> error claro, no crashea
AGORA reinicia con sesiones -> conversations table rehidrata lazy
Usuario malicioso -> Bearer token unico, bridge LXD aisla L3

## Gotchas operacionales
1. State files en /tmp desaparecen -> migrado a ~/.laia/state/
2. Ghost backend host:8088 -> preflight.sh lo detecta
3. auth.json copy vs bind mount -> usar bind mount read-only
4. Forwarder rompe LXD versions -> plugin es agnostico, solo HTTP

## Nuevas decisiones (Mayo 2026)

D5: Identidad del agente centralizada en agent_areas (DB). Container solo executor.
D6: Naming agent-<slug> para nuevos containers. Legacy laia-<slug> protegido.
D7: Soul/instrucciones como ephemeral_system_prompt via AgentPool > 📅 2026-05-18

## Hardening (Mayo 2026)

D8: max_length=50KB en soul/instructions previene DoS de memoria.
D9: GET agent-area auto-crea (nunca 404) — consistente con PATCH.
D10: rebuild-4 destruye legacy por defecto (evita coexistencia agent-* + laia-*).

> 📅 2026-05-18

## v0.5 (2026-05-19)

D11: Toolset laia_coordinator dividido en _base (empleados) y _admin (admins). Regla ⑨-⑪ alineadas.
D12: Slug "laia" reservado via RESERVED_AGENT_SLUGS. Regla ② alineada.
D13: Logout revoke sin JTI denylist (tokens_valid_since cutoff). 
D14: host_admin role definido para regla ⑥ (migracion pendiente).
