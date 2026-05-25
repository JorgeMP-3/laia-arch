# AGORA Build System — Scripts Rebuild

## Metadata

- ID: `206`
- Slug: `agora-build-system`
- Kind: `doc`
- Status: `active`
- Filename: `agora-build-system.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-18T11:03:34.687193+00:00`
- Updated at: `2026-05-18T16:57:23.328534+00:00`
- Aliases: `agora-build-system`

## Summary

4 scripts rebuild (cleanup, images, provision-agora, first-user) + 2 image builders + create-agent.sh. Reconstruccion idempotente desde cero.

## Body

# AGORA Build System

## Scripts (ejecutar como root en orden)
1. rebuild-1-cleanup.sh (207 LOC): PRESERVA laia-jorge + jorge. ELIMINA containers test, bind mounts, DB excepto jorge
2. rebuild-2-images.sh: construye laia-agent (executor) + laia-agora (cerebro)
3. rebuild-3-provision-agora.sh: lanza laia-agora con bind mounts + proxy LXD (host:8088->container:8000)
4. rebuild-4-first-user.sh --slug X (229 LOC): container + user DB + register + smoke test

## Imagenes LXD
laia-agent: Ubuntu 22.04 + laia-executor (SIN .laia-core/). build-base-image.sh
laia-agora: Ubuntu 24.04 + .laia-core/ + agora-backend + workspace_store. build-agora-image.sh (279 LOC)

## create-agent.sh: api_token, container con bind mounts (/srv/laia/users/{slug}/ -> /home/user), executor-token

## Naming v2 (Mayo 2026)

- `create-agent.sh`: crea `agent-$SLUG`
- `rebuild-4-first-user.sh`: registra `container_name="agent-$SLUG"`
- `rebuild-state.sh`: acepta `agent-*` y legacy `laia-*`
- `chat-with-deployed.sh`: lee `.container` del state JSON

> 📅 Actualizado: 2026-05-18

## Hardening (Mayo 2026)

- `rebuild-1`: ahora limpia `agent-*` stray ademas de `laia-*`
- `rebuild-4`: destruye legacy `laia-<slug>` si existe (flag `--keep-legacy` para preservar)
- `preflight.sh`: detecta containers sin state file y sugiere accion

> 📅 Actualizado: 2026-05-18

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# AGORA Build System — Scripts Rebuild

# AGORA Build System

## Scripts (ejecutar como root en orden)
1. rebuild-1-cleanup.sh (207 LOC): PRESERVA laia-jorge + jorge. ELIMINA containers test, bind mounts, DB excepto jorge
2. rebuild-2-images.sh: construye laia-agent (executor) + laia-agora (cerebro)
3. rebuild-3-provision-agora.sh: lanza laia-agora con bind mounts + proxy LXD (host:8088->container:8000)
4. rebuild-4-first-user.sh --slug X (229 LOC): container + user DB + register + smoke test

## Imagenes LXD
laia-agent: Ubuntu 22.04 + laia-executor (SIN .laia-core/). build-base-image.sh
laia-agora: Ubuntu 24.04 + .laia-core/ + agora-backend + workspace_store. build-agora-image.sh (279 LOC)

## create-agent.sh: api_token, container con bind mounts (/srv/laia/users/{slug}/ -> /home/user), executor-token

## Naming v2 (Mayo 2026)

- `create-agent.sh`: crea `agent-$SLUG`
- `rebuild-4-first-user.sh`: registra `container_name="agent-$SLUG"`
- `rebuild-state.sh`: acepta `agent-*` y legacy `laia-*`
- `chat-with-deployed.sh`: lee `.container` del state JSON

> 📅 Actualizado: 2026-05-18

## Hardening (Mayo 2026)

- `rebuild-1`: ahora limpia `agent-*` stray ademas de `laia-*`
- `rebuild-4`: destruye legacy `laia-<slug>` si existe (flag `--keep-legacy` para preservar)
- `preflight.sh`: detecta containers sin state file y sugiere accion

> 📅 Actualizado: 2026-05-18
