# Command Center Problems

## Metadata

- ID: `103`
- Slug: `problemas-command-center`
- Kind: `doc`
- Status: `active`
- Filename: `problemas-command-center.md`
- Parent: `seguridad`
- Source kind: `manual`
- Created at: `2026-05-08T08:34:05.127658+00:00`
- Updated at: `2026-05-08T08:34:05.127658+00:00`
- Aliases: `problemas-command-center`

## Summary

Vivos en `/home/laia-arch/LAIA/docs/problemas-command-center/README.md`.

## Body

# Problemas Command Center — Sesión 2026-05-07

# Problemas Command Center

Vivos en `/home/laia-arch/LAIA/docs/problemas-command-center/README.md`.

## Resumen de problemas

1. **Bypass mata cc2 y cc-planner** — `permission_mode=bypass` causa muerte instantánea del proceso PTY
2. **Inject de prompt largo mata cc-planner** — spawn sin bypass funciona pero muere tras injectar (~1329 bytes)
3. **Sandbox bwrap restrictivo** — probable causa de los fallos de filesystem
4. **Approval confuso** — `require_user_approval=False` devuelve `pending_approval=True`

## Para resolver

- Debugging completo en `docs/problemas-command-center/`
- ¿Por qué bypass mata procesos?
- ¿Funciona sin bwrap?
- ¿Fluye mejor con prompts más pequeños?


> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `seguridad` (Seguridad y aislamiento) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Command Center Problems

# Problemas Command Center — Sesión 2026-05-07

# Problemas Command Center

Vivos en `/home/laia-arch/LAIA/docs/problemas-command-center/README.md`.

## Resumen de problemas

1. **Bypass mata cc2 y cc-planner** — `permission_mode=bypass` causa muerte instantánea del proceso PTY
2. **Inject de prompt largo mata cc-planner** — spawn sin bypass funciona pero muere tras injectar (~1329 bytes)
3. **Sandbox bwrap restrictivo** — probable causa de los fallos de filesystem
4. **Approval confuso** — `require_user_approval=False` devuelve `pending_approval=True`

## Para resolver

- Debugging completo en `docs/problemas-command-center/`
- ¿Por qué bypass mata procesos?
- ¿Funciona sin bwrap?
- ¿Fluye mejor con prompts más pequeños?


> 📅 Documentado: 2026-05-08
