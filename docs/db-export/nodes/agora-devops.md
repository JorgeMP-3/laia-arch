# AGORA DevOps — Preflight, Smoke, State

## Metadata

- ID: `207`
- Slug: `agora-devops`
- Kind: `doc`
- Status: `active`
- Filename: `agora-devops.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-18T11:03:34.701892+00:00`
- Updated at: `2026-05-18T16:57:23.341623+00:00`
- Aliases: `agora-devops`

## Summary

preflight.sh (265L diagnostico), smoke-test.sh (164L E2E), rebuild-state.sh (147L regenera state files), chat-with-deployed.sh. State en ~/.laia/state/.

## Body

# AGORA DevOps Tools

## preflight.sh (265 LOC): diagnostico preventivo. Detecta procesos fantasma, puertos, permisos, state files, drift imagen. --fix repara.

## smoke-test.sh (164 LOC): E2E en 5 pasos: health, admin login, admin status, tests run, chat SSE. --slug jorge-dev, --dry-run.

## rebuild-state.sh (147 LOC): regenera state files desde LXD + DB. --slug, --include-stopped.

## chat-with-deployed.sh: prueba rapida de chat.

## State files: ~/.laia/state/laia-agora-state.json, laia-state-{slug}.json

## Hardening (Mayo 2026)

- `preflight.sh`: detecta containers `agent-*` sin state file → sugiere rebuild-state o delete
- `laia-marketplace.py`: nuevo subcomando `agent-area` (get, set-soul, set-instructions, set-name, set-pref)
- TUI: pestana 10 "Areas" con lista de users + display_name + soul truncado

> 📅 Actualizado: 2026-05-18

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# AGORA DevOps — Preflight, Smoke, State

# AGORA DevOps Tools

## preflight.sh (265 LOC): diagnostico preventivo. Detecta procesos fantasma, puertos, permisos, state files, drift imagen. --fix repara.

## smoke-test.sh (164 LOC): E2E en 5 pasos: health, admin login, admin status, tests run, chat SSE. --slug jorge-dev, --dry-run.

## rebuild-state.sh (147 LOC): regenera state files desde LXD + DB. --slug, --include-stopped.

## chat-with-deployed.sh: prueba rapida de chat.

## State files: ~/.laia/state/laia-agora-state.json, laia-state-{slug}.json

## Hardening (Mayo 2026)

- `preflight.sh`: detecta containers `agent-*` sin state file → sugiere rebuild-state o delete
- `laia-marketplace.py`: nuevo subcomando `agent-area` (get, set-soul, set-instructions, set-name, set-pref)
- TUI: pestana 10 "Areas" con lista de users + display_name + soul truncado

> 📅 Actualizado: 2026-05-18
