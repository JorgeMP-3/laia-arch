# Base Skills — 15 Skills Pre-empaquetadas

## Metadata

- ID: `222`
- Slug: `agora-base-skills`
- Kind: `doc`
- Status: `active`
- Filename: `agora-base-skills.md`
- Parent: `agora`
- Source kind: `manual`
- Created at: `2026-05-19T08:36:18.068621+00:00`
- Updated at: `2026-05-19T08:36:18.068621+00:00`
- Aliases: `agora-base-skills`

## Summary

seed-base-skills.sh publica y aprueba 15 skills base en marketplace. v0.3: delegation, learning, scheduler, self-edit, coordinator, doyouwin. v0.4: linear, airtable, etc.

## Body

# Base Skills — 15 Skills Pre-empaquetadas

> &#x1F4C5; 2026-05-18 | Shell tests verdes

## Proposito

Skills base que vienen pre-instaladas en el marketplace de AGORA.

## Archivos

| Archivo | Rol |
|---------|-----|
| `infra/dev/seed-base-skills.sh` | Publica + aprueba skills via API |
| `examples/marketplace/skills/` | Fuentes markdown de cada skill |

## Skills incluidas

### v0.3 (10 skills)

| Skill | Proposito |
|-------|-----------|
| `agent-delegation` | Como usar spawn_child para delegar |
| `agent-learning` | Como persistir y buscar aprendizajes |
| `agent-scheduler` | Como programar tareas recurrentes |
| `agent-self-edit` | Como el agente se modifica a si mismo |
| `laia-coordinator` | Identidad de LAIA como coordinadora |
| `doyouwin-reference` | Referencia al workspace doyouwin |
| `workspace-read` | Lectura efectiva de workspaces |
| `marketplace-onboarding` | Guia del marketplace |
| `google-workspace` | Integracion Google (stub) |
| `notion` | Integracion Notion (stub) |

### v0.4 (5 skills adicionales)
`linear`, `airtable`, `nano-pdf`, `ocr-and-documents`, `arxiv`, `github-issues`, `maps`

## Flujo

1. Consulta catalogo existente via API
2. Omite skills ya aprobadas (idempotente)
3. Para cada skill nueva: publish -> admin approve
4. Usa `AGORA_TOKEN` para autenticacion

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `agora` (AGORA — Plataforma de usuarios) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Base Skills — 15 Skills Pre-empaquetadas

# Base Skills — 15 Skills Pre-empaquetadas

> &#x1F4C5; 2026-05-18 | Shell tests verdes

## Proposito

Skills base que vienen pre-instaladas en el marketplace de AGORA.

## Archivos

| Archivo | Rol |
|---------|-----|
| `infra/dev/seed-base-skills.sh` | Publica + aprueba skills via API |
| `examples/marketplace/skills/` | Fuentes markdown de cada skill |

## Skills incluidas

### v0.3 (10 skills)

| Skill | Proposito |
|-------|-----------|
| `agent-delegation` | Como usar spawn_child para delegar |
| `agent-learning` | Como persistir y buscar aprendizajes |
| `agent-scheduler` | Como programar tareas recurrentes |
| `agent-self-edit` | Como el agente se modifica a si mismo |
| `laia-coordinator` | Identidad de LAIA como coordinadora |
| `doyouwin-reference` | Referencia al workspace doyouwin |
| `workspace-read` | Lectura efectiva de workspaces |
| `marketplace-onboarding` | Guia del marketplace |
| `google-workspace` | Integracion Google (stub) |
| `notion` | Integracion Notion (stub) |

### v0.4 (5 skills adicionales)
`linear`, `airtable`, `nano-pdf`, `ocr-and-documents`, `arxiv`, `github-issues`, `maps`

## Flujo

1. Consulta catalogo existente via API
2. Omite skills ya aprobadas (idempotente)
3. Para cada skill nueva: publish -> admin approve
4. Usa `AGORA_TOKEN` para autenticacion
